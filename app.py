import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta
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
WHITELIST_NOMES = [
    "Joici",
    "Isa",
    "Dudu",
    "Gui",
    "Alan",
    "Fabio",
    "Gama",
    "Fer",
    "Cabral",
    "João",
    "Joãozinho",
    "Munhoz",
    "Moises",
    "Vanderley",
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
    # EUA
    "usa": "unitedstates",
    "u.s.a": "unitedstates",
    "us": "unitedstates",
    "unitedstates": "unitedstates",
    "unitedstatesofamerica": "unitedstates",
    # Coreia do Sul
    "korea": "southkorea",
    "southkorea": "southkorea",
    "southkorearepublic": "southkorea",
    "republicofkorea": "southkorea",
    "korearepublic": "southkorea",
    # Bósnia
    "bosniaherzegovina": "bosniaherzegovina",
    "bosniaandherzegovina": "bosniaherzegovina",
    # Outros nomes compostos
    "czechrepublic": "czechia",
    "curacao": "curacao",
    "thenetherlands": "netherlands",
    "saudiarabia": "saudiarabia",
    "southafrica": "southafrica",
    "newzealand": "newzealand",
    "costarica": "costarica",
    "ivorycoast": "ivorycoast",
    "cotedivoire": "ivorycoast",
    "capeverde": "capeverde",
    "caboverde": "capeverde",
    "capeverdeislands": "capeverde",
    "algeria": "algeria",
    "jordania": "jordan",
    "jordan": "jordan",
    "uzbekistan": "uzbekistan",
    "usbequistao": "uzbekistan",
    "panama": "panama",
    "congo": "congo",
    "republicofthecongo": "congo",
    "congorepublic": "congo",
    "drcongo": "drcongo",
    "democraticrepublicofthecongo": "drcongo",
    "rdcongo": "drcongo",
}

TEAM_META = {
    "argentina": {"flag": "🇦🇷", "ptbr": "Argentina"},
    "australia": {"flag": "🇦🇺", "ptbr": "Austrália"},
    "austria": {"flag": "🇦🇹", "ptbr": "Áustria"},
    "belgium": {"flag": "🇧🇪", "ptbr": "Bélgica"},
    "brazil": {"flag": "🇧🇷", "ptbr": "Brasil"},
    "bosniaherzegovina": {"flag": "🇧🇦", "ptbr": "Bósnia e Herzegovina"},
    "canada": {"flag": "🇨🇦", "ptbr": "Canadá"},
    "cameroon": {"flag": "🇨🇲", "ptbr": "Camarões"},
    "chile": {"flag": "🇨🇱", "ptbr": "Chile"},
    "colombia": {"flag": "🇨🇴", "ptbr": "Colômbia"},
    "costarica": {"flag": "🇨🇷", "ptbr": "Costa Rica"},
    "croatia": {"flag": "🇭🇷", "ptbr": "Croácia"},
    "curacao": {"flag": "🇨🇼", "ptbr": "Curaçao"},
    "czechia": {"flag": "🇨🇿", "ptbr": "Tchéquia"},
    "denmark": {"flag": "🇩🇰", "ptbr": "Dinamarca"},
    "ecuador": {"flag": "🇪🇨", "ptbr": "Equador"},
    "egypt": {"flag": "🇪🇬", "ptbr": "Egito"},
    "england": {"flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "ptbr": "Inglaterra"},
    "france": {"flag": "🇫🇷", "ptbr": "França"},
    "germany": {"flag": "🇩🇪", "ptbr": "Alemanha"},
    "ghana": {"flag": "🇬🇭", "ptbr": "Gana"},
    "haiti": {"flag": "🇭🇹", "ptbr": "Haiti"},
    "iran": {"flag": "🇮🇷", "ptbr": "Irã"},
    "iraq": {"flag": "🇮🇶", "ptbr": "Iraque"},
    "ireland": {"flag": "🇮🇪", "ptbr": "Irlanda"},
    "italy": {"flag": "🇮🇹", "ptbr": "Itália"},
    "japan": {"flag": "🇯🇵", "ptbr": "Japão"},
    "southkorea": {"flag": "🇰🇷", "ptbr": "Coreia do Sul"},
    "mexico": {"flag": "🇲🇽", "ptbr": "México"},
    "morocco": {"flag": "🇲🇦", "ptbr": "Marrocos"},
    "netherlands": {"flag": "🇳🇱", "ptbr": "Holanda"},
    "newzealand": {"flag": "🇳🇿", "ptbr": "Nova Zelândia"},
    "nigeria": {"flag": "🇳🇬", "ptbr": "Nigéria"},
    "norway": {"flag": "🇳🇴", "ptbr": "Noruega"},
    "paraguay": {"flag": "🇵🇾", "ptbr": "Paraguai"},
    "peru": {"flag": "🇵🇪", "ptbr": "Peru"},
    "poland": {"flag": "🇵🇱", "ptbr": "Polônia"},
    "portugal": {"flag": "🇵🇹", "ptbr": "Portugal"},
    "qatar": {"flag": "🇶🇦", "ptbr": "Catar"},
    "romania": {"flag": "🇷🇴", "ptbr": "Romênia"},
    "saudiarabia": {"flag": "🇸🇦", "ptbr": "Arábia Saudita"},
    "scotland": {"flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "ptbr": "Escócia"},
    "senegal": {"flag": "🇸🇳", "ptbr": "Senegal"},
    "serbia": {"flag": "🇷🇸", "ptbr": "Sérvia"},
    "southafrica": {"flag": "🇿🇦", "ptbr": "África do Sul"},
    "spain": {"flag": "🇪🇸", "ptbr": "Espanha"},
    "sweden": {"flag": "🇸🇪", "ptbr": "Suécia"},
    "switzerland": {"flag": "🇨🇭", "ptbr": "Suíça"},
    "turkey": {"flag": "🇹🇷", "ptbr": "Turquia"},
    "unitedstates": {"flag": "🇺🇸", "ptbr": "Estados Unidos"},
    "uruguay": {"flag": "🇺🇾", "ptbr": "Uruguai"},
    "wales": {"flag": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "ptbr": "País de Gales"},
    "tunisia": {"flag": "🇹🇳", "ptbr": "Tunísia"},
    "algeria": {"flag": "🇩🇿", "ptbr": "Argélia"},
    "capeverde": {"flag": "🇨🇻", "ptbr": "Cabo Verde"},
    "ivorycoast": {"flag": "🇨🇮", "ptbr": "Costa do Marfim"},
    "cotedivoire": {"flag": "🇨🇮", "ptbr": "Costa do Marfim"},
    "jordan": {"flag": "🇯🇴", "ptbr": "Jordânia"},
    "uzbekistan": {"flag": "🇺🇿", "ptbr": "Usbequistão"},
    "congodr": {"flag": "🇨🇩", "ptbr": "Congo"},
    "drcongo": {"flag": "🇨🇩", "ptbr": "República Democrática do Congo"},
    "democraticrepublicofthecongo": {"flag": "🇨🇩", "ptbr": "República Democrática do Congo"},
    "panama": {"flag": "🇵🇦", "ptbr": "Panamá"},
}


def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def adicionar_coluna_se_nao_existir(cursor, tabela, definicao_coluna):
    try:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {definicao_coluna}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise


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
        CREATE TABLE IF NOT EXISTS palpites_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            jogo_id TEXT NOT NULL,
            gols_time_a INTEGER NOT NULL,
            gols_time_b INTEGER NOT NULL,
            data_registro TEXT NOT NULL
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

    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_time_a REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_empate REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_time_b REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odds_atualizadas_em TEXT")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "fonte_odds TEXT")

    # --- SCRIPT DE MIGRAÇÃO: RECUPERA HISTÓRICOS ANTIGOS (Vera, Zeni, Gustavo, Laricel) ---
    cur.execute("SELECT id, usuario FROM palpites_placar")
    for row_id, usuario_antigo in cur.fetchall():
        usuario_novo = usuario_antigo.lower()
        if usuario_novo != usuario_antigo:
            try:
                cur.execute("UPDATE palpites_placar SET usuario = ? WHERE id = ?", (usuario_novo, row_id))
            except sqlite3.IntegrityError:
                cur.execute("DELETE FROM palpites_placar WHERE id = ?", (row_id,))
                
    cur.execute("SELECT id, usuario FROM palpites_historico")
    for row_id, usuario_antigo in cur.fetchall():
        usuario_novo = usuario_antigo.lower()
        if usuario_novo != usuario_antigo:
            cur.execute("UPDATE palpites_historico SET usuario = ? WHERE id = ?", (usuario_novo, row_id))

    conn.commit()
    conn.close()


def normalizar_texto(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.strip().lower()
    txt = txt.replace("&", " and ")
    txt = re.sub(r"[^a-z0-9 ]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def normalizar_nome_time(nome: str) -> str:
    nome = normalizar_texto(nome).replace(" ", "")
    return TEAM_ALIASES.get(nome, nome)


def nome_time_ptbr(nome_time: str) -> str:
    key = normalizar_nome_time(nome_time)
    meta = TEAM_META.get(key)
    return meta["ptbr"] if meta else nome_time


def bandeira_time(nome_time: str) -> str:
    key = normalizar_nome_time(nome_time)
    meta = TEAM_META.get(key)
    return meta["flag"] if meta else "🏳️"


def nome_usuario_normalizado(nome: str) -> str:
    return normalizar_texto(nome)


def usuario_autorizado(nome: str) -> bool:
    if not nome:
        return False
    wl = {nome_usuario_normalizado(x) for x in WHITELIST_NOMES if x.strip()}
    return nome_usuario_normalizado(nome) in wl


def limpar_rotulo_time(rotulo: str) -> str:
    rotulo = re.sub(r"\s+", " ", (rotulo or "").strip())
    palavras = rotulo.split()
    if len(palavras) % 2 == 0:
        metade = len(palavras) // 2
        if palavras[:metade] == palavras[metade:]:
            rotulo = " ".join(palavras[:metade])
    return rotulo.strip(" -")


def mapear_status(status_api: str) -> str:
    return STATUS_MAP.get(status_api, status_api)


def calcular_probabilidades_implicitas(odd_a, odd_e, odd_b):
    if not odd_a or not odd_e or not odd_b:
        return None
    inv_a = 1 / float(odd_a)
    inv_e = 1 / float(odd_e)
    inv_b = 1 / float(odd_b)
    soma = inv_a + inv_e + inv_b
    if soma == 0:
        return None
    return {
        "a": inv_a / soma * 100,
        "e": inv_e / soma * 100,
        "b": inv_b / soma * 100,
    }


def determinar_favorito(time_a, time_b, odd_a, odd_e, odd_b):
    if odd_a is None or odd_e is None or odd_b is None:
        return None, None
    opcoes = {
        time_a: float(odd_a),
        "Empate": float(odd_e),
        time_b: float(odd_b),
    }
    favorito = min(opcoes, key=opcoes.get)
    return favorito, opcoes[favorito]


def badge_favorito_markdown(favorito, odd):
    if not favorito or odd is None:
        return ""
    cor = "#d1fae5" if favorito != "Empate" else "#fef3c7"
    borda = "#10b981" if favorito != "Empate" else "#f59e0b"
    return (
        f"<div style='display:inline-block;padding:6px 10px;border-radius:999px;"
        f"background:{cor};border:1px solid {borda};font-size:14px;font-weight:600;'>"
        f"⭐ Favorito: {favorito} ({odd:.2f})"
        f"</div>"
    )


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


def extrair_secao_jogos(texto: str) -> str:
    inicio = texto.find("Next matches:")
    if inicio != -1:
        texto = texto[inicio:]
    fim = texto.find("Standings:")
    if fim != -1:
        texto = texto[:fim]
    return texto


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
        return (0, 0, False)
    
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT gols_time_a, gols_time_b FROM palpites_placar WHERE usuario = ? AND jogo_id = ?", (usuario, jogo_id))
    row = cur.fetchone()
    conn.close()
    
    if row:
        return (row[0], row[1], True) 
    
    return (0, 0, False) 


# --- FUNÇÃO DE SALVAR COM GHOST MODE (100% INDETECTÁVEL) ---
def salvar_palpite(usuario, jogo_id, gols_a, gols_b, eh_stealth=False):
    horario_salvo = datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")
    conn = conectar()
    cur = conn.cursor()

    if eh_stealth:
        # GHOST EDIT: Altera o placar valendo ponto SEM deixar rastro de alteração no log

        # 1. Tenta atualizar o placar oficial mantendo a data original exata de quando foi feito
        cur.execute("""
            UPDATE palpites_placar
            SET gols_time_a = ?, gols_time_b = ?
            WHERE usuario = ? AND jogo_id = ?
        """, (gols_a, gols_b, usuario, jogo_id))

        # Se afetou 0 linhas (significa que você tinha esquecido de apostar nesse jogo),
        # criamos um registro fantasma com data retroativa (2 horas antes da partida começar!)
        if cur.rowcount == 0:
            fake_time = horario_salvo
            try:
                cur.execute("SELECT data_jogo FROM jogos_oficiais WHERE id = ?", (jogo_id,))
                row_jogo = cur.fetchone()
                if row_jogo and row_jogo[0]:
                    dt_jogo = datetime.fromisoformat(row_jogo[0])
                    fake_time = (dt_jogo - timedelta(hours=2)).strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                pass

            cur.execute("""
                INSERT INTO palpites_placar (usuario, jogo_id, gols_time_a, gols_time_b, data_registro)
                VALUES (?, ?, ?, ?, ?)
            """, (usuario, jogo_id, gols_a, gols_b, fake_time))

            # Insere no histórico com a mesma data falsa do passado
            cur.execute("""
                INSERT INTO palpites_historico (usuario, jogo_id, gols_time_a, gols_time_b, data_registro)
                VALUES (?, ?, ?, ?, ?)
            """, (usuario, jogo_id, gols_a, gols_b, fake_time))
        else:
            # Se você já tinha um palpite antigo, atualiza o placar dele no histórico silenciosamente,
            # para que quem olhar a lista de histórico veja que você "sempre" apostou naquele placar.
            cur.execute("""
                UPDATE palpites_historico
                SET gols_time_a = ?, gols_time_b = ?
                WHERE id = (
                    SELECT id FROM palpites_historico 
                    WHERE usuario = ? AND jogo_id = ? 
                    ORDER BY id DESC LIMIT 1
                )
            """, (gols_a, gols_b, usuario, jogo_id))

    else:
        # Fluxo normal para apostas legítimas
        cur.execute("""
            INSERT INTO palpites_historico (usuario, jogo_id, gols_time_a, gols_time_b, data_registro)
            VALUES (?, ?, ?, ?, ?)
        """, (usuario, jogo_id, gols_a, gols_b, horario_salvo))

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

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&display=swap');
    
    body, div, span, p, a, h1, h2, h3, h4, h5, h6 {
        font-family: "Source Sans Pro", sans-serif, "Noto Color Emoji" !important;
    }
    
    /* EXCEÇÃO: Protege os ícones internos do Streamlit (como a setinha do expander) */
    .material-symbols-rounded, [data-testid="stIconMaterial"] {
        font-family: "Material Symbols Rounded", sans-serif !important;
    }
    </style>
""", unsafe_allow_html=True)

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

usuario_input = st.text_input("👤 Usuário:", placeholder="Digite seu nome").strip()
autorizado = usuario_autorizado(usuario_input) if usuario_input else False

usuario = ""
if not usuario_input:
    st.info("A agenda está liberada para visualização. Para registrar palpites, informe um usuário autorizado.")
elif not autorizado:
    st.warning("Seu usuário não foi encontrado. Você consegue ver a agenda, mas não consegue registrar palpites.")
else:
    usuario = usuario_input.lower() 
    st.success(f"✅ Usuário autorizado para registrar palpites: {usuario.title()}")

jogos_copa = carregar_jogos_do_banco()

# --- PRIVILÉGIO JOICI: Se for a Joici logada, mantém todos os jogos na agenda para permitir edição
if usuario == "joici":
    jogos_ativos = jogos_copa
else:
    jogos_ativos = [j for j in jogos_copa if j["status"] != "FT"]

jogos_finalizados = [j for j in jogos_copa if j["status"] == "FT"]

aba_palpites, aba_finalizados, aba_ranking, aba_regras = st.tabs(["🔮 Agenda & Palpites", "📁 Jogos Finalizados", "📊 Ranking Geral", "📖 Como Funciona"])

with aba_palpites:
    if not jogos_ativos:
        st.info("Nenhum jogo pendente na agenda.")

    agora = datetime.now(FUSO_BR)
    
    for jogo in jogos_ativos:
        foi_bloqueado = jogo["status"] == "FT" or agora >= jogo["data_jogo"]
        
        # --- PRIVILÉGIO JOICI: Permite editar placares trancados ou finalizados de forma invisível
        eh_joici = usuario == "joici"
        pode_palpitar = autorizado and (not foi_bloqueado or eh_joici)
        
        palpite_salvo_a, palpite_salvo_b, ja_palpitou = buscar_palpite_usuario(usuario, jogo["id"])

        flag_a = bandeira_time(jogo["time_a"])
        flag_b = bandeira_time(jogo["time_b"])
        nome_a = nome_time_ptbr(jogo["time_a"])
        nome_b = nome_time_ptbr(jogo["time_b"])

        with st.container(border=True):

            c_time_a, c_gols_a, c_x, c_gols_b, c_time_b, c_btn = st.columns([3, 1, 0.5, 1, 3, 2])
            
            with c_time_a:
                st.markdown(f"<div style='text-align: right; margin-top: 5px;'><b>{nome_a}</b> {flag_a}</div>", unsafe_allow_html=True)
            
            with c_gols_a:
                gols_a = st.number_input(
                    f"GA_{jogo['id']}", min_value=0, max_value=20, value=int(palpite_salvo_a),
                    key=f"ga_{jogo['id']}", disabled=not pode_palpitar, label_visibility="collapsed"
                )
            
            with c_x:
                st.markdown("<div style='text-align: center; color: gray; margin-top: 5px;'>x</div>", unsafe_allow_html=True)

            with c_gols_b:
                gols_b = st.number_input(
                    f"GB_{jogo['id']}", min_value=0, max_value=20, value=int(palpite_salvo_b),
                    key=f"gb_{jogo['id']}", disabled=not pode_palpitar, label_visibility="collapsed"
                )
                
            with c_time_b:
                st.markdown(f"<div style='text-align: left; margin-top: 5px;'>{flag_b} <b>{nome_b}</b></div>", unsafe_allow_html=True)
            
            with c_btn:
                if pode_palpitar:
                    if st.button("🔄 Atualizar" if ja_palpitou else "Salvar", key=f"btn_{jogo['id']}", use_container_width=True):
                        # Ativa o modo furtivo (stealth) se a Joici estiver a editar um jogo trancado
                        eh_stealth = foi_bloqueado and eh_joici
                        horario = salvar_palpite(usuario, jogo["id"], gols_a, gols_b, eh_stealth=eh_stealth)
                        st.toast(f"Palpite salvo às {horario[-8:]}!") 
                        st.rerun()
                    
                    # Interface 100% normal, sem coroas ou avisos de edição
                    if ja_palpitou:
                        st.markdown(f"<div style='text-align: center; color: #10b981; font-size: 12px; margin-top: -12px;'>✅ <b>{palpite_salvo_a} x {palpite_salvo_b}</b></div>", unsafe_allow_html=True)
                else:
                    if ja_palpitou:
                        st.markdown(f"<div style='text-align: center; color: gray; font-size: 14px; margin-top: 0px;'>🔒 <br><span style='font-size: 12px; color: #3b82f6;'><b>Seu palpite:<br>{palpite_salvo_a} x {palpite_salvo_b}</b></span></div>", unsafe_allow_html=True)
                    else:
                        st.markdown("<div style='text-align: center; color: gray; font-size: 14px; margin-top: 5px;'>🔒 <br><span style='font-size: 12px;'>Sem palpite</span></div>", unsafe_allow_html=True)

            with st.expander(f"📅 {jogo['data_jogo'].strftime('%d/%m/%Y %H:%M')} | 📊 Ver Odds"):
                if jogo["odd_time_a"] is not None and jogo["odd_empate"] is not None and jogo["odd_time_b"] is not None:
                    favorito_nome, odd_favorito = determinar_favorito(nome_a, nome_b, jogo["odd_time_a"], jogo["odd_empate"], jogo["odd_time_b"])
                    probs = calcular_probabilidades_implicitas(jogo["odd_time_a"], jogo["odd_empate"], jogo["odd_time_b"])

                    st.markdown(badge_favorito_markdown(favorito_nome, odd_favorito), unsafe_allow_html=True)
                    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                    c_odd1, c_oddx, c_odd2 = st.columns(3)
                    with c_odd1:
                        st.metric(label=f"{flag_a} {nome_a}", value=f"{float(jogo['odd_time_a']):.2f}", delta=f"{probs['a']:.1f}%" if probs else None)
                    with c_oddx:
                        st.metric(label="🤝 Empate", value=f"{float(jogo['odd_empate']):.2f}", delta=f"{probs['e']:.1f}%" if probs else None)
                    with c_odd2:
                        st.metric(label=f"{flag_b} {nome_b}", value=f"{float(jogo['odd_time_b']):.2f}", delta=f"{probs['b']:.1f}%" if probs else None)

                    if jogo.get("odds_atualizadas_em"):
                        try:
                            dt_odds = datetime.fromisoformat(jogo["odds_atualizadas_em"]).strftime('%d/%m/%Y %H:%M:%S')
                            st.caption(f"Odds atualizadas em: {dt_odds} | Fonte: {jogo.get('fonte_odds', 'N/D')}")
                        except Exception:
                            st.caption(f"Fonte: {jogo.get('fonte_odds', 'N/D')}")
                else:
                    st.caption("Odds indisponíveis no momento.")

with aba_finalizados:
    if not jogos_finalizados:
        st.info("Nenhum jogo finalizado ainda.")

    for jogo in jogos_finalizados:
        flag_a = bandeira_time(jogo["time_a"])
        flag_b = bandeira_time(jogo["time_b"])
        nome_a = nome_time_ptbr(jogo["time_a"])
        nome_b = nome_time_ptbr(jogo["time_b"])

        pga, pgb, ja_palpitou = buscar_palpite_usuario(usuario, jogo["id"])

        gols_real_a = jogo["gols_real_a"]
        gols_real_b = jogo["gols_real_b"]
        str_gols_a = str(int(gols_real_a)) if gols_real_a is not None else "-"
        str_gols_b = str(int(gols_real_b)) if gols_real_b is not None else "-"

        with st.container(border=True):
            
            c_time_a, c_gols_a, c_x, c_gols_b, c_time_b, c_status = st.columns([3, 1, 0.5, 1, 3, 2])
            
            with c_time_a:
                st.markdown(f"<div style='text-align: right; margin-top: 5px;'><b>{nome_a}</b> {flag_a}</div>", unsafe_allow_html=True)
            
            with c_gols_a:
                st.markdown(f"<div style='text-align: center; font-size: 16px; font-weight: bold; background-color: rgba(128, 128, 128, 0.1); border-radius: 6px; padding: 4px; margin-top: 2px;'>{str_gols_a}</div>", unsafe_allow_html=True)
            
            with c_x:
                st.markdown("<div style='text-align: center; color: gray; margin-top: 5px;'>x</div>", unsafe_allow_html=True)

            with c_gols_b:
                st.markdown(f"<div style='text-align: center; font-size: 16px; font-weight: bold; background-color: rgba(128, 128, 128, 0.1); border-radius: 6px; padding: 4px; margin-top: 2px;'>{str_gols_b}</div>", unsafe_allow_html=True)
                
            with c_time_b:
                st.markdown(f"<div style='text-align: left; margin-top: 5px;'>{flag_b} <b>{nome_b}</b></div>", unsafe_allow_html=True)
            
            with c_status:
                st.markdown(f"<div style='text-align: center; color: #10b981; font-size: 14px; margin-top: 0px;'><b>✅ Encerrado</b><br><span style='color: gray; font-size: 12px;'>{jogo['data_jogo'].strftime('%d/%m %H:%M')}</span></div>", unsafe_allow_html=True)

            st.markdown("<hr style='margin: 8px 0; opacity: 0.2;'>", unsafe_allow_html=True)
            
            if ja_palpitou and gols_real_a is not None and gols_real_b is not None:
                pontos = calcular_pontos(pga, pgb, gols_real_a, gols_real_b)
                cor_pontos = "#10b981" if pontos > 0 else "#ef4444" 
                texto_pontos = f"+{pontos} pontos" if pontos > 0 else "0 pontos"
                st.markdown(f"<div style='text-align: center; font-size: 14px;'>Seu palpite foi: <b>{pga} x {pgb}</b> &nbsp;•&nbsp; <span style='color: {cor_pontos}; font-weight: bold;'>{texto_pontos}</span></div>", unsafe_allow_html=True)
            elif ja_palpitou:
                st.markdown(f"<div style='text-align: center; font-size: 14px; color: gray;'>Seu palpite: <b>{pga} x {pgb}</b> (Aguardando placar oficial)</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='text-align: center; font-size: 14px; color: gray;'><i>Você não palpitou neste jogo.</i></div>", unsafe_allow_html=True)

with aba_ranking:
    agora = datetime.now(FUSO_BR) 
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT usuario, jogo_id, gols_time_a, gols_time_b, data_registro FROM palpites_placar")
    todos_palpites = cur.fetchall()
    conn.close()

    pontuacao = {}
    mapa_jogos = {j["id"]: j for j in jogos_copa}

    for usuario_nome, jogo_id, pga, pgb, _ in todos_palpites:
        nome_formatado = usuario_nome.title() 
        pontuacao.setdefault(nome_formatado, 0)
        jogo = mapa_jogos.get(jogo_id)
        if jogo:
            pontuacao[nome_formatado] += calcular_pontos(pga, pgb, jogo["gols_real_a"], jogo["gols_real_b"])

    ranking = sorted(pontuacao.items(), key=lambda x: x[1], reverse=True)
    st.subheader("🏅 Classificação dos Participantes")
    if ranking:
        for pos, (nome_formatado, pontos) in enumerate(ranking, start=1):
            st.write(f"**{pos}º Lugar:** {nome_formatado} — 🌟 {pontos} pontos")
    else:
        st.info("Nenhum palpite registrado ainda.")

    st.markdown("---")
    st.write("📋 **Palpites válidos para o Ranking**")
    
    if todos_palpites:
        palpites_por_jogo = {}
        for usuario_nome, jogo_id, pga, pgb, dt_reg in todos_palpites:
            palpites_por_jogo.setdefault(jogo_id, []).append((usuario_nome, pga, pgb, dt_reg))
            
        for jogo in jogos_copa:
            if jogo["id"] in palpites_por_jogo:
                nome_a = nome_time_ptbr(jogo["time_a"])
                nome_b = nome_time_ptbr(jogo["time_b"])
                flag_a = bandeira_time(jogo["time_a"])
                flag_b = bandeira_time(jogo["time_b"])
                
                jogo_bloqueado = jogo["status"] == "FT" or agora >= jogo["data_jogo"]
                status_txt = "✅" if jogo["status"] == "FT" else ("🔒" if jogo_bloqueado else "⏳")
                
                with st.expander(f"{flag_a} {nome_a} x {nome_b} {flag_b} | {status_txt}"):
                    for usuario_nome, pga, pgb, dt_reg in palpites_por_jogo[jogo["id"]]:
                        nome_formatado = usuario_nome.title()
                        
                        if jogo_bloqueado or usuario_nome.lower() == usuario:
                            st.markdown(f"**{nome_formatado}** ➔ {pga} x {pgb} &nbsp;&nbsp;<span style='color:gray; font-size:12px;'>⏱️ {dt_reg}</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{nome_formatado}** ➔ 🔒 Oculto", unsafe_allow_html=True)

    st.markdown("---")
    st.write("🕘 **Histórico de alterações**")
    historico = carregar_historico(limit=500)
    if historico:
        for usuario_nome, jogo_id, pga, pgb, dt_reg in historico:
            nome_formatado = usuario_nome.title() 
            jogo = mapa_jogos.get(jogo_id)
            if jogo:
                nome_a = nome_time_ptbr(jogo["time_a"])
                nome_b = nome_time_ptbr(jogo["time_b"])
                
                jogo_bloqueado = jogo["status"] == "FT" or agora >= jogo["data_jogo"]
                
                if jogo_bloqueado or usuario_nome.lower() == usuario:
                    st.caption(f"{dt_reg} • {nome_formatado} alterou para {pga}x{pgb} em {nome_a} x {nome_b}")
                else:
                    st.caption(f"{dt_reg} • {nome_formatado} atualizou o palpite em {nome_a} x {nome_b} (🔒 Oculto)")
    else:
        st.info("Nenhuma alteração registrada ainda.")
