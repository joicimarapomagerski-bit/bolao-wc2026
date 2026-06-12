import re
import sqlite3
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import streamlit as st

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
API_LOGIN_EMAIL = "joicimara.pomagerskii@gmail.com"

# =========================
# AJUSTE AQUI A LISTA BRANCA
# =========================
WHITELIST_NOMES = [
    "joici",
    "gui",
    "dudu",
    # adicione mais nomes aqui
]

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
    "u.s.a": "unitedstates",
    "czechrepublic": "czechia",
    "republicofkorea": "southkorea",
    "korearepublic": "southkorea",
    "bosniaandherzegovina": "bosniaherzegovina",
    "bosniaherzegovina": "bosniaherzegovina",
    "curacao": "curacao",
    "mexico": "mexico",
}

TEAM_TO_COUNTRY = {
    "argentina": "🇦🇷",
    "australia": "🇦🇺",
    "austria": "🇦🇹",
    "belgium": "🇧🇪",
    "brazil": "🇧🇷",
    "bosniaherzegovina": "🇧🇦",
    "canada": "🇨🇦",
    "cameroon": "🇨🇲",
    "chile": "🇨🇱",
    "colombia": "🇨🇴",
    "croatia": "🇭🇷",
    "curacao": "🇨🇼",
    "czechia": "🇨🇿",
    "denmark": "🇩🇰",
    "ecuador": "🇪🇨",
    "egypt": "🇪🇬",
    "england": "🏴",
    "france": "🇫🇷",
    "germany": "🇩🇪",
    "ghana": "🇬🇭",
    "haiti": "🇭🇹",
    "iran": "🇮🇷",
    "iraq": "🇮🇶",
    "ireland": "🇮🇪",
    "italy": "🇮🇹",
    "japan": "🇯🇵",
    "korea": "🇰🇷",
    "southkorea": "🇰🇷",
    "mexico": "🇲🇽",
    "morocco": "🇲🇦",
    "netherlands": "🇳🇱",
    "newzealand": "🇳🇿",
    "nigeria": "🇳🇬",
    "norway": "🇳🇴",
    "paraguay": "🇵🇾",
    "peru": "🇵🇪",
    "poland": "🇵🇱",
    "portugal": "🇵🇹",
    "qatar": "🇶🇦",
    "romania": "🇷🇴",
    "saudiarabia": "🇸🇦",
    "scotland": "🏴",
    "senegal": "🇸🇳",
    "serbia": "🇷🇸",
    "southafrica": "🇿🇦",
    "spain": "🇪🇸",
    "sweden": "🇸🇪",
    "switzerland": "🇨🇭",
    "turkey": "🇹🇷",
    "unitedstates": "🇺🇸",
    "uruguay": "🇺🇾",
    "wales": "🏴",
    "tunisia": "🇹🇳",
}

TEAM_TO_PTBR = {
    "argentina": "Argentina",
    "australia": "Austrália",
    "austria": "Áustria",
    "belgium": "Bélgica",
    "brazil": "Brasil",
    "bosniaherzegovina": "Bósnia e Herzegovina",
    "canada": "Canadá",
    "cameroon": "Camarões",
    "chile": "Chile",
    "colombia": "Colômbia",
    "croatia": "Croácia",
    "curacao": "Curaçao",
    "czechia": "Tchéquia",
    "denmark": "Dinamarca",
    "ecuador": "Equador",
    "egypt": "Egito",
    "england": "Inglaterra",
    "france": "França",
    "germany": "Alemanha",
    "ghana": "Gana",
    "haiti": "Haiti",
    "iran": "Irã",
    "iraq": "Iraque",
    "ireland": "Irlanda",
    "italy": "Itália",
    "japan": "Japão",

@st.cache_data(ttl=300, show_spinner=False)
def buscar_odds_native_stats():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    resp = requests.get(NATIVE_STATS_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    html = resp.text

    texto = re.sub(r"<[^>]+>", " ", html)
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    texto = extrair_secao_jogos(texto)

    padrao = re.compile(
        r"(20\d{2}/\d{2}/\d{2},\s*\d{2}h\d{2})\s+"
        r"(.+?)\s+([A-Z]{3})\s+-\s+(.+?)\s+([A-Z]{3})\s+"
        r"([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)"
    )

    odds = []
    vistos = set()
    for m in padrao.finditer(texto):
        data_txt = m.group(1)
        time_a = limpar_rotulo_time(m.group(2))
        time_b = limpar_rotulo_time(m.group(4))
        if not time_a or not time_b:
            continue

        chave = (normalizar_nome_time(time_a), normalizar_nome_time(time_b), data_txt)
        if chave in vistos:
            continue
        vistos.add(chave)

        try:
            data_jogo = datetime.strptime(data_txt, "%Y/%m/%d, %Hh%M").replace(tzinfo=FUSO_BR)
        except Exception:
            data_jogo = None

        odds.append({
            "time_a": time_a,
            "time_b": time_b,
            "data_jogo": data_jogo,
            "odd_time_a": float(m.group(6)),
            "odd_empate": float(m.group(7)),
            "odd_time_b": float(m.group(8)),
            "odds_atualizadas_em": datetime.now(FUSO_BR).isoformat(),
            "fonte_odds": "native-stats",
        })

    return odds


def salvar_jogos_no_banco(jogos):
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


def encontrar_jogo_por_times(indice, time_a, time_b):
    na = normalizar_nome_time(time_a)
    nb = normalizar_nome_time(time_b)
    if (na, nb) in indice:
        return indice[(na, nb)]
    for (db_a, db_b), jogo_id in indice.items():
        if (na in db_a or db_a in na) and (nb in db_b or db_b in nb):
            return jogo_id
    return None


def salvar_odds_no_banco(lista_odds):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, time_a, time_b FROM jogos_oficiais")
    jogos_db = cur.fetchall()

    indice = {}
    for jogo_id, time_a, time_b in jogos_db:
        indice[(normalizar_nome_time(time_a), normalizar_nome_time(time_b))] = jogo_id

    atualizados = 0
    for item in lista_odds:
        jogo_id = encontrar_jogo_por_times(indice, item["time_a"], item["time_b"])
        if not jogo_id:
            continue
        cur.execute("""
            UPDATE jogos_oficiais
               SET odd_time_a = ?, odd_empate = ?, odd_time_b = ?,
                   odds_atualizadas_em = ?, fonte_odds = ?
             WHERE id = ?
        """, (
            item["odd_time_a"], item["odd_empate"], item["odd_time_b"],
            item["odds_atualizadas_em"], item["fonte_odds"], jogo_id
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
        salvar_jogos_no_banco(jogos)
        msgs.append(f"Agenda OK ({len(jogos)} jogos)")
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


def buscar_palpite_usuario(usuario, jogo_id):
    if not usuario:
        return (0, 0)
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT gols_time_a, gols_time_b FROM palpites_placar WHERE usuario = ? AND jogo_id = ?", (usuario, jogo_id))
    row = cur.fetchone()
    conn.close()
    return row if row else (0, 0)


def salvar_palpite(usuario, jogo_id, gols_a, gols_b):
    horario_salvo = datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")
    conn = conectar()
    cur = conn.cursor()

    # histórico: salva TODAS as alterações
    cur.execute("""
        INSERT INTO palpites_historico (usuario, jogo_id, gols_time_a, gols_time_b, data_registro)
        VALUES (?, ?, ?, ?, ?)
    """, (usuario, jogo_id, gols_a, gols_b, horario_salvo))

    # vigente: mantém apenas o último palpite do usuário para o jogo
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


def carregar_historico(limit=300):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT usuario, jogo_id, gols_time_a, gols_time_b, data_registro
          FROM palpites_historico
         ORDER BY id DESC
         LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


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

st.markdown("### Usuário")
usuario = st.text_input("Digite seu nome:", placeholder="Seu nome")
usuario = usuario.strip()
autorizado = usuario_autorizado(usuario) if usuario else False

if not usuario:
    st.info("A agenda está liberada para visualização. Para registrar palpites, informe um usuário da lista.")
elif not autorizado:
    st.warning("Seu nome não está na lista. Você consegue ver a agenda, mas não consegue registrar palpites.")
else:
    st.success(f"Usuário autorizado: {usuario}")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("🔄 Atualizar agora", use_container_width=True):
        buscar_jogos_api.clear()
        buscar_odds_native_stats.clear()
        st.rerun()
with col2:
    st.caption("Atualização automática a cada 60 segundos.")

jogos_copa = carregar_jogos_do_banco()
aba_palpites, aba_ranking = st.tabs(["🔮 Agenda & Palpites", "📊 Ranking Geral"])

with aba_palpites:
    if not jogos_copa:
        st.info("Nenhum jogo disponível ainda.")

    agora = datetime.now(FUSO_BR)
    for jogo in jogos_copa:
        foi_bloqueado = jogo["status"] == "FT" or agora >= jogo["data_jogo"]
        pode_palpitar = autorizado and not foi_bloqueado
        palpite_salvo_a, palpite_salvo_b = buscar_palpite_usuario(usuario, jogo["id"])

        flag_a = bandeira_time(jogo['time_a'])
        flag_b = bandeira_time(jogo['time_b'])
        st.subheader(f"{flag_a} {jogo['time_a']} vs {flag_b} {jogo['time_b']}")
        st.caption(f"Status: {jogo['status']} | Horário: {jogo['data_jogo'].strftime('%d/%m/%Y %H:%M')}")

        if jogo["odd_time_a"] is not None and jogo["odd_empate"] is not None and jogo["odd_time_b"] is not None:
            favorito, odd_favorito = determinar_favorito(
                jogo["time_a"], jogo["time_b"], jogo["odd_time_a"], jogo["odd_empate"], jogo["odd_time_b"]
            )
            probs = calcular_probabilidades_implicitas(
                jogo["odd_time_a"], jogo["odd_empate"], jogo["odd_time_b"]
            )

            st.markdown(badge_favorito_markdown(favorito, odd_favorito), unsafe_allow_html=True)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            c_odd1, c_oddx, c_odd2 = st.columns(3)
            with c_odd1:
                st.metric(label=f"{flag_a} {jogo['time_a']}", value=f"{float(jogo['odd_time_a']):.2f}", delta=f"{probs['a']:.1f}%" if probs else None)
            with c_oddx:
                st.metric(label="🤝 Empate", value=f"{float(jogo['odd_empate']):.2f}", delta=f"{probs['e']:.1f}%" if probs else None)
            with c_odd2:
                st.metric(label=f"{flag_b} {jogo['time_b']}", value=f"{float(jogo['odd_time_b']):.2f}", delta=f"{probs['b']:.1f}%" if probs else None)

            if jogo.get("odds_atualizadas_em"):
                try:
                    dt_odds = datetime.fromisoformat(jogo["odds_atualizadas_em"]).strftime('%d/%m/%Y %H:%M:%S')
                    st.caption(f"Odds atualizadas em: {dt_odds} | Fonte: {jogo.get('fonte_odds', 'N/D')}")
                except Exception:
                    st.caption(f"Fonte: {jogo.get('fonte_odds', 'N/D')}")
        else:
            st.caption("Odds indisponíveis no momento.")

        if foi_bloqueado:
            st.error("🔒 Palpites encerrados para esta partida.")
            if jogo["gols_real_a"] is not None and jogo["gols_real_b"] is not None:
                st.info(f"Placar oficial: {jogo['time_a']} {int(jogo['gols_real_a'])} x {int(jogo['gols_real_b'])} {jogo['time_b']}")
        elif autorizado:
            st.success("⏳ Palpite liberado.")
        else:
            st.info("Visualização liberada. Para registrar palpites, use um usuário autorizado.")

        c1, _, c2 = st.columns([2, 1, 2])
        with c1:
            gols_a = st.number_input(
                f"Gols {jogo['time_a']}",
                min_value=0, max_value=20,
                value=int(palpite_salvo_a),
                key=f"ga_{jogo['id']}",
                disabled=not pode_palpitar,
            )
        with c2:
            gols_b = st.number_input(
                f"Gols {jogo['time_b']}",
                min_value=0, max_value=20,
                value=int(palpite_salvo_b),
                key=f"gb_{jogo['id']}",
                disabled=not pode_palpitar,
            )

        if pode_palpitar:
            if st.button(f"Salvar {gols_a} x {gols_b}", key=f"btn_{jogo['id']}", use_container_width=True):
                horario = salvar_palpite(usuario, jogo["id"], gols_a, gols_b)
                st.success(f"Palpite salvo às {horario}. O histórico de alterações foi registrado.")
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
        for pos, (usuario_nome, pontos) in enumerate(ranking, start=1):
            st.write(f"**{pos}º Lugar:** {usuario_nome} — 🌟 {pontos} pontos")
    else:
        st.info("Nenhum palpite registrado ainda.")

    st.markdown("---")
    st.write("📋 **Palpites para o ranking**")
    if todos_palpites:
        for usuario_nome, jogo_id, pga, pgb, dt_reg in todos_palpites:
            jogo = mapa_jogos.get(jogo_id)
            if jogo:
                st.caption(f"⏱️ {usuario_nome} → {pga}x{pgb} ({jogo['time_a']} x {jogo['time_b']}) em: {dt_reg}")

    st.markdown("---")
    st.write("🕘 **Histórico de alterações**")
    historico = carregar_historico(limit=500)
    if historico:
        for usuario_nome, jogo_id, pga, pgb, dt_reg in historico:
            jogo = mapa_jogos.get(jogo_id)
            if jogo:
                st.caption(f"{dt_reg} • {usuario_nome} alterou para {pga}x{pgb} em {jogo['time_a']} x {jogo['time_b']}")
    else:
        st.info("Nenhuma alteração registrada ainda.")
