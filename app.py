import re
import sqlite3
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import streamlit as st

# Auto refresh opcional
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_OK = True
except ModuleNotFoundError:
    AUTOREFRESH_OK = False

FUSO_BR = ZoneInfo("America/Sao_Paulo")
DB_PATH = "bolao.db"
API_URL = "https://api.football-data.org/v4/competitions/WC/matches"
API_TOKEN = "3ffa7e87c87e447ab012984b3026120a"
NATIVE_STATS_URL = "https://native-stats.org/competition/WC/"
API_LOGIN_EMAIL = "joicimara.pomagerskii@gmail.com"  # usar se algum fluxo futuro da API exigir login manual

STATUS_MAP = {
    "SCHEDULED": "NS",
    "TIMED": "NS",
    "IN_PLAY": "LIVE",
    "PAUSED": "LIVE",
    "FINISHED": "FT",
    "POSTPONED": "ADIADO",
    "SUSPENDED": "SUSP",
    "CANCELLED": "CANCELADO",
}

TEAM_ALIASES = {
    "usa": "unitedstates",
    "unitedstatesofamerica": "unitedstates",
    "czechrepublic": "czechia",
    "republicofkorea": "southkorea",
    "korearepublic": "southkorea",
    "bosniaandherzegovina": "bosniaherzegovina",
    "curacao": "curacao",
    "méxico": "mexico",
}


def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def adicionar_coluna_se_nao_existir(cursor, tabela, definicao_coluna):
    nome_coluna = definicao_coluna.split()[0]
    try:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {definicao_coluna}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise e


def inicializar_banco():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS palpites_placar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            jogo_id TEXT NOT NULL,
            gols_time_a INTEGER NOT NULL,
            gols_time_b INTEGER NOT NULL,
            data_registro TEXT,
            UNIQUE(usuario, jogo_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS jogos_oficiais (
            id TEXT PRIMARY KEY,
            time_a TEXT NOT NULL,
            time_b TEXT NOT NULL,
            data_jogo TEXT NOT NULL,
            gols_real_a INTEGER,
            gols_real_b INTEGER,
            status TEXT NOT NULL,
            stage TEXT,
            ultima_atualizacao TEXT
        )
    """)

    # Colunas extras para odds
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_time_a REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_empate REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_time_b REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odds_atualizadas_em TEXT")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "fonte_odds TEXT")

    conn.commit()
    conn.close()


def mapear_status(status_api: str) -> str:
    return STATUS_MAP.get(status_api, status_api)


def normalizar_nome_time(nome: str) -> str:
    if not nome:
        return ""
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = nome.lower().strip()
    nome = nome.replace("&", "and")
    nome = re.sub(r"[^a-z0-9]", "", nome)
    return TEAM_ALIASES.get(nome, nome)


@st.cache_data(ttl=60, show_spinner=False)
def buscar_jogos_api():
    headers = {"X-Auth-Token": API_TOKEN}
    resp = requests.get(API_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    dados = resp.json()

    jogos = []
    for item in dados.get("matches", []):
        if item.get("stage") != "GROUP_STAGE":
            continue

        data_utc = datetime.fromisoformat(item["utcDate"].replace("Z", "+00:00"))
        data_br = data_utc.astimezone(FUSO_BR)
        score = item.get("score", {}) or {}
        full_time = score.get("fullTime", {}) or {}

        jogos.append({
            "id": str(item["id"]),
            "time_a": item["homeTeam"]["name"],
            "time_b": item["awayTeam"]["name"],
            "data_jogo": data_br.isoformat(),
            "gols_real_a": full_time.get("home"),
            "gols_real_b": full_time.get("away"),
            "status": mapear_status(item.get("status")),
            "stage": item.get("stage"),
            "ultima_atualizacao": datetime.now(FUSO_BR).isoformat(),
        })

    return sorted(jogos, key=lambda x: x["data_jogo"])


@st.cache_data(ttl=300, show_spinner=False)
def buscar_odds_native_stats():
    """
    Extrai odds 1X2 da página pública da competição da Copa no Native Stats.
    Formato esperado na página: 1.47 / 4.11 / 6.79
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    resp = requests.get(NATIVE_STATS_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    html = resp.text

    # Reduz ruído do HTML
    texto = re.sub(r"<[^>]+>", " ", html)
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)

    # Captura somente jogos com odds 1X2 presentes
    padrao = re.compile(
        r"(20\d{2}/\d{2}/\d{2},\s*\d{2}h\d{2})\s+"
        r"([A-Za-zÀ-ÿ'\- ]+?)\s+([A-Z]{3})\s+-\s+"
        r"([A-Za-zÀ-ÿ'\- ]+?)\s+([A-Z]{3})\s+"
        r"([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)"
    )

    odds = []
    vistos = set()
    for m in padrao.finditer(texto):
        data_txt = m.group(1)
        time_a = " ".join(m.group(2).split())
        sigla_a = m.group(3).strip()
        time_b = " ".join(m.group(4).split())
        sigla_b = m.group(5).strip()
        odd_a = float(m.group(6))
        odd_e = float(m.group(7))
        odd_b = float(m.group(8))

        chave = (normalizar_nome_time(time_a), normalizar_nome_time(time_b), data_txt)
        if chave in vistos:
            continue
        vistos.add(chave)

        try:
            dt = datetime.strptime(data_txt, "%Y/%m/%d, %Hh%M").replace(tzinfo=FUSO_BR)
        except Exception:
            dt = None

        odds.append({
            "time_a": time_a,
            "sigla_a": sigla_a,
            "time_b": time_b,
            "sigla_b": sigla_b,
            "data_jogo": dt,
            "odd_time_a": odd_a,
            "odd_empate": odd_e,
            "odd_time_b": odd_b,
            "fonte_odds": "native-stats",
            "odds_atualizadas_em": datetime.now(FUSO_BR).isoformat(),
        })

    return odds


def salvar_jogos_no_banco(jogos: list[dict]):
    conn = conectar()
    cur = conn.cursor()

    for jogo in jogos:
        cur.execute("""
            INSERT INTO jogos_oficiais (
                id, time_a, time_b, data_jogo, gols_real_a, gols_real_b, status, stage, ultima_atualizacao
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                time_a = excluded.time_a,
                time_b = excluded.time_b,
                data_jogo = excluded.data_jogo,
                gols_real_a = excluded.gols_real_a,
                gols_real_b = excluded.gols_real_b,
                status = excluded.status,
                stage = excluded.stage,
                ultima_atualizacao = excluded.ultima_atualizacao
        """, (
            jogo["id"], jogo["time_a"], jogo["time_b"], jogo["data_jogo"],
            jogo["gols_real_a"], jogo["gols_real_b"], jogo["status"],
            jogo["stage"], jogo["ultima_atualizacao"]
        ))

    conn.commit()
    conn.close()


def salvar_odds_no_banco(lista_odds: list[dict]):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, time_a, time_b FROM jogos_oficiais")
    jogos_db = cur.fetchall()

    indice = {}
    for jogo_id, time_a, time_b in jogos_db:
        chave = (normalizar_nome_time(time_a), normalizar_nome_time(time_b))
        indice[chave] = jogo_id

    atualizados = 0
    for item in lista_odds:
        chave = (normalizar_nome_time(item["time_a"]), normalizar_nome_time(item["time_b"]))
        jogo_id = indice.get(chave)
        if not jogo_id:
            continue

        cur.execute("""
            UPDATE jogos_oficiais
            SET odd_time_a = ?, odd_empate = ?, odd_time_b = ?,
                odds_atualizadas_em = ?, fonte_odds = ?
            WHERE id = ?
        """, (
            item["odd_time_a"],
            item["odd_empate"],
            item["odd_time_b"],
            item["odds_atualizadas_em"],
            item["fonte_odds"],
            jogo_id,
        ))
        if cur.rowcount:
            atualizados += 1

    conn.commit()
    conn.close()
    return atualizados


def carregar_jogos_do_banco():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, time_a, time_b, data_jogo, gols_real_a, gols_real_b, status,
               ultima_atualizacao, odd_time_a, odd_empate, odd_time_b, odds_atualizadas_em, fonte_odds
        FROM jogos_oficiais
        ORDER BY data_jogo
    """)
    rows = cur.fetchall()
    conn.close()

    jogos = []
    for row in rows:
        jogos.append({
            "id": row[0],
            "time_a": row[1],
            "time_b": row[2],
            "data_jogo": datetime.fromisoformat(row[3]),
            "gols_real_a": row[4],
            "gols_real_b": row[5],
            "status": row[6],
            "ultima_atualizacao": row[7],
            "odd_time_a": row[8],
            "odd_empate": row[9],
            "odd_time_b": row[10],
            "odds_atualizadas_em": row[11],
            "fonte_odds": row[12],
        })
    return jogos


def sincronizar_agenda_e_odds():
    msgs = []
    try:
        jogos = buscar_jogos_api()
        if jogos:
            salvar_jogos_no_banco(jogos)
            msgs.append(f"Agenda OK ({len(jogos)} jogos)")
        else:
            msgs.append("Agenda vazia")
    except Exception as e:
        msgs.append(f"Agenda falhou: {e}")

    try:
        odds = buscar_odds_native_stats()
        atualizados = salvar_odds_no_banco(odds)
        msgs.append(f"Odds OK ({atualizados} jogos atualizados)")
    except Exception as e:
        msgs.append(f"Odds falharam: {e}")

    return msgs


def calcular_pontos(gp_a, gp_b, gr_a, gr_b):
    if gr_a is None or gr_b is None:
        return 0

    vencedor_real = "A" if gr_a > gr_b else ("B" if gr_b > gr_a else "Empate")
    vencedor_palpite = "A" if gp_a > gp_b else ("B" if gp_b > gp_a else "Empate")

    if gp_a == gr_a and gp_b == gr_b:
        return 25
    if vencedor_palpite == vencedor_real and (gp_a - gp_b) == (gr_a - gr_b):
        return 15
    if vencedor_palpite == vencedor_real:
        return 10
    return 0


def buscar_palpite_usuario(usuario: str, jogo_id: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT gols_time_a, gols_time_b FROM palpites_placar WHERE usuario = ? AND jogo_id = ?",
        (usuario, jogo_id),
    )
    row = cur.fetchone()
    conn.close()
    return row if row else (0, 0)


def salvar_palpite(usuario: str, jogo_id: str, gols_a: int, gols_b: int):
    horario_salvo = datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO palpites_placar (usuario, jogo_id, gols_time_a, gols_time_b, data_registro)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(usuario, jogo_id) DO UPDATE SET
            gols_time_a = excluded.gols_time_a,
            gols_time_b = excluded.gols_time_b,
            data_registro = excluded.data_registro
    """, (usuario, jogo_id, gols_a, gols_b, horario_salvo))
    conn.commit()
    conn.close()
    return horario_salvo


st.set_page_config(page_title="Bolão Copa 2026", layout="centered")
inicializar_banco()

if AUTOREFRESH_OK:
    st_autorefresh(interval=60000, key="refresh_agenda")

st.title("🏆 Bolão da Copa 2026")

mensagens_sync = sincronizar_agenda_e_odds()
if any("falhou" in m.lower() for m in mensagens_sync):
    st.warning(" | ".join(mensagens_sync))
else:
    st.caption(" | ".join(mensagens_sync))

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("🔄 Atualizar agora", use_container_width=True):
        buscar_jogos_api.clear()
        buscar_odds_native_stats.clear()
        st.rerun()
with col2:
    st.caption("Atualização automática a cada 60 segundos.")

jogos_copa = carregar_jogos_do_banco()
aba_palpites, aba_ranking = st.tabs(["🔮 Palpites & Agenda", "📊 Ranking Geral"])

with aba_palpites:
    usuario = st.text_input("Insira seu nome para começar:", placeholder=" ").strip()

    if usuario and not jogos_copa:
        st.info("Nenhum jogo disponível ainda.")

    if usuario:
        agora = datetime.now(FUSO_BR)
        for jogo in jogos_copa:
            foi_bloqueado = jogo["status"] == "FT" or agora >= jogo["data_jogo"]
            palpite_salvo_a, palpite_salvo_b = buscar_palpite_usuario(usuario, jogo["id"])

            st.subheader(f"🏟️ {jogo['time_a']} vs {jogo['time_b']}")
            st.caption(f"Status: {jogo['status']} | Horário: {jogo['data_jogo'].strftime('%d/%m/%Y %H:%M')}")

            if jogo["odd_time_a"] is not None:
                st.caption(
                    f"Odds 1X2: {jogo['time_a']} {float(jogo['odd_time_a']):.2f} | "
                    f"Empate {float(jogo['odd_empate']):.2f} | "
                    f"{jogo['time_b']} {float(jogo['odd_time_b']):.2f}"
                )

            if foi_bloqueado:
                st.error("🔒 Palpites encerrados para esta partida.")
                if jogo["gols_real_a"] is not None and jogo["gols_real_b"] is not None:
                    st.info(f"Placar oficial: {jogo['time_a']} {int(jogo['gols_real_a'])} x {int(jogo['gols_real_b'])} {jogo['time_b']}")
            else:
                st.success("⏳ Palpite liberado.")

            c1, _, c2 = st.columns([2, 1, 2])
            with c1:
                gols_a = st.number_input(
                    f"Gols {jogo['time_a']}", min_value=0, max_value=20,
                    value=int(palpite_salvo_a), key=f"ga_{jogo['id']}", disabled=foi_bloqueado
                )
            with c2:
                gols_b = st.number_input(
                    f"Gols {jogo['time_b']}", min_value=0, max_value=20,
                    value=int(palpite_salvo_b), key=f"gb_{jogo['id']}", disabled=foi_bloqueado
                )

            if not foi_bloqueado:
                if st.button(f"Salvar {gols_a} x {gols_b}", key=f"btn_{jogo['id']}", use_container_width=True):
                    horario = salvar_palpite(usuario, jogo["id"], gols_a, gols_b)
                    st.success(f"Palpite salvo às {horario}.")
                    st.rerun()

            st.markdown("---")

with aba_ranking:
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT usuario, jogo_id, gols_time_a, gols_time_b, data_registro FROM palpites_placar")
    todos_palpites = cur.fetchall()
    conn.close()

    pontuacao = {}
    mapa_jogos = {j["id"]: j for j in jogos_copa}

    for usuario_nome, jogo_id, pga, pgb, _ in todos_palpites:
        pontuacao.setdefault(usuario_nome, 0)
        jogo = mapa_jogos.get(jogo_id)
        if jogo:
            pontuacao[usuario_nome] += calcular_pontos(pga, pgb, jogo["gols_real_a"], jogo["gols_real_b"])

    ranking = sorted(pontuacao.items(), key=lambda x: x[1], reverse=True)

    st.subheader("🏅 Classificação dos Participantes")
    if ranking:
        for pos, usuario_info in enumerate(ranking, start=1):
            usuario_nome, pontos = usuario_info
            st.write(f"**{pos}º Lugar:** {usuario_nome} — 🌟 {pontos} pontos")

        st.markdown("---")
        st.write("📋 **Histórico de Palpites**")
        for usuario_nome, jogo_id, pga, pgb, dt_reg in todos_palpites:
            jogo = mapa_jogos.get(jogo_id)
            if jogo:
                st.caption(f"⏱️ {usuario_nome} enviou {pga}x{pgb} ({jogo['time_a']} x {jogo['time_b']}) em: {dt_reg}")
    else:
        st.info("Nenhum palpite registrado ainda.")
