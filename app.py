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
WHITELIST_NOMES = [
    "Joici", "Isa", "Dudu", "Gui", "Alan", "Fabio", "Gama", "Fer", 
    "Cabral", "João", "Joãozinho", "Munhoz", "Moises", "Vanderley",
]

STATUS_MAP = {
    "SCHEDULED": "NS", "TIMED": "NS", "IN_PLAY": "LIVE", "PAUSED": "LIVE",
    "FINISHED": "FT", "POSTPONED": "ADIADO", "SUSPENDED": "SUSP", "CANCELLED": "CANCELADO",
}

TEAM_ALIASES = {
    "usa": "unitedstates", "u.s.a": "unitedstates", "us": "unitedstates", "unitedstates": "unitedstates", "unitedstatesofamerica": "unitedstates",
    "korea": "southkorea", "southkorea": "southkorea", "southkorearepublic": "southkorea", "republicofkorea": "southkorea", "korearepublic": "southkorea",
    "bosniaherzegovina": "bosniaherzegovina", "bosniaandherzegovina": "bosniaherzegovina",
    "czechrepublic": "czechia", "curacao": "curacao", "thenetherlands": "netherlands", "saudiarabia": "saudiarabia",
    "southafrica": "southafrica", "newzealand": "newzealand", "costarica": "costarica", "ivorycoast": "ivorycoast",
    "cotedivoire": "ivorycoast", "capeverde": "capeverde", "caboverde": "capeverde", "capeverdeislands": "capeverde",
    "algeria": "algeria", "jordania": "jordan", "jordan": "jordan", "uzbekistan": "uzbekistan", "usbequistao": "uzbekistan",
    "panama": "panama", "congo": "congo", "republicofthecongo": "congo", "congorepublic": "congo", "drcongo": "drcongo",
    "democraticrepublicofthecongo": "drcongo", "rdcongo": "drcongo",
}

TEAM_META = {
    "argentina": {"flag": "🇦🇷", "ptbr": "Argentina"}, "australia": {"flag": "🇦🇺", "ptbr": "Austrália"},
    "austria": {"flag": "🇦🇹", "ptbr": "Áustria"}, "belgium": {"flag": "🇧🇪", "ptbr": "Bélgica"},
    "brazil": {"flag": "🇧🇷", "ptbr": "Brasil"}, "bosniaherzegovina": {"flag": "🇧🇦", "ptbr": "Bósnia e Herzegovina"},
    "canada": {"flag": "🇨🇦", "ptbr": "Canadá"}, "cameroon": {"flag": "🇨🇲", "ptbr": "Camarões"},
    "chile": {"flag": "🇨🇱", "ptbr": "Chile"}, "colombia": {"flag": "🇨🇴", "ptbr": "Colômbia"},
    "costarica": {"flag": "🇨🇷", "ptbr": "Costa Rica"}, "croatia": {"flag": "🇭🇷", "ptbr": "Croácia"},
    "curacao": {"flag": "🇨🇼", "ptbr": "Curaçao"}, "czechia": {"flag": "🇨🇿", "ptbr": "Tchéquia"},
    "denmark": {"flag": "🇩🇰", "ptbr": "Dinamarca"}, "ecuador": {"flag": "🇪🇨", "ptbr": "Equador"},
    "egypt": {"flag": "🇪🇬", "ptbr": "Egito"}, "england": {"flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "ptbr": "Inglaterra"},
    "france": {"flag": "🇫🇷", "ptbr": "França"}, "germany": {"flag": "🇩🇪", "ptbr": "Alemanha"},
    "ghana": {"flag": "🇬🇭", "ptbr": "Gana"}, "haiti": {"flag": "🇭🇹", "ptbr": "Haiti"},
    "iran": {"flag": "🇮🇷", "ptbr": "Irã"}, "iraq": {"flag": "🇮🇶", "ptbr": "Iraque"},
    "ireland": {"flag": "🇮🇪", "ptbr": "Irlanda"}, "italy": {"flag": "🇮🇹", "ptbr": "Itália"},
    "japan": {"flag": "🇯🇵", "ptbr": "Japão"}, "southkorea": {"flag": "🇰🇷", "ptbr": "Coreia do Sul"},
    "mexico": {"flag": "🇲🇽", "ptbr": "México"}, "morocco": {"flag": "🇲🇦", "ptbr": "Marrocos"},
    "netherlands": {"flag": "🇳🇱", "ptbr": "Holanda"}, "newzealand": {"flag": "🇳🇿", "ptbr": "Nova Zelândia"},
    "nigeria": {"flag": "🇳🇬", "ptbr": "Nigéria"}, "norway": {"flag": "🇳🇴", "ptbr": "Noruega"},
    "paraguay": {"flag": "🇵🇾", "ptbr": "Paraguai"}, "peru": {"flag": "🇵🇪", "ptbr": "Peru"},
    "poland": {"flag": "🇵🇱", "ptbr": "Polônia"}, "portugal": {"flag": "🇵🇹", "ptbr": "Portugal"},
    "qatar": {"flag": "🇶🇦", "ptbr": "Catar"}, "romania": {"flag": "🇷🇴", "ptbr": "Romênia"},
    "saudiarabia": {"flag": "🇸🇦", "ptbr": "Arábia Saudita"}, "scotland": {"flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "ptbr": "Escócia"},
    "senegal": {"flag": "🇸🇳", "ptbr": "Senegal"}, "serbia": {"flag": "🇷🇸", "ptbr": "Sérvia"},
    "southafrica": {"flag": "🇿🇦", "ptbr": "África do Sul"}, "spain": {"flag": "🇪🇸", "ptbr": "Espanha"},
    "sweden": {"flag": "🇸🇪", "ptbr": "Suécia"}, "switzerland": {"flag": "🇨🇭", "ptbr": "Suíça"},
    "turkey": {"flag": "🇹🇷", "ptbr": "Turquia"}, "unitedstates": {"flag": "🇺🇸", "ptbr": "Estados Unidos"},
    "uruguay": {"flag": "🇺🇾", "ptbr": "Uruguai"}, "wales": {"flag": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "ptbr": "País de Gales"},
    "tunisia": {"flag": "🇹🇳", "ptbr": "Tunísia"}, "algeria": {"flag": "🇩🇿", "ptbr": "Argélia"},
    "capeverde": {"flag": "🇨🇻", "ptbr": "Cabo Verde"}, "ivorycoast": {"flag": "🇨🇮", "ptbr": "Costa do Marfim"},
    "cotedivoire": {"flag": "🇨🇮", "ptbr": "Costa do Marfim"}, "jordan": {"flag": "🇯🇴", "ptbr": "Jordânia"},
    "uzbekistan": {"flag": "🇺🇿", "ptbr": "Usbequistão"}, "congo": {"flag": "🇨🇬", "ptbr": "Congo"},
    "drcongo": {"flag": "🇨🇩", "ptbr": "República Democrática do Congo"}, "panama": {"flag": "🇵🇦", "ptbr": "Panamá"},
}

def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def adicionar_coluna_se_nao_existir(cursor, tabela, definicao_coluna):
    try:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {definicao_coluna}")
    except sqlite3.OperationalError:
        pass

def inicializar_banco():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS palpites_placar (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, jogo_id TEXT NOT NULL, gols_time_a INTEGER NOT NULL, gols_time_b INTEGER NOT NULL, data_registro TEXT, UNIQUE(usuario, jogo_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS palpites_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, jogo_id TEXT NOT NULL, gols_time_a INTEGER NOT NULL, gols_time_b INTEGER NOT NULL, data_registro TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS jogos_oficiais (id TEXT PRIMARY KEY, time_a TEXT NOT NULL, time_b TEXT NOT NULL, data_jogo TEXT NOT NULL, gols_real_a INTEGER, gols_real_b INTEGER, status TEXT NOT NULL, stage TEXT, ultima_atualizacao TEXT)")
    conn.commit(); conn.close()

def normalizar_texto(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "").strip().lower()
    return re.sub(r"[^a-z0-9 ]", " ", txt)

def nome_time_ptbr(nome_time: str) -> str:
    return TEAM_META.get(normalizar_texto(nome_time).replace(" ", ""), {}).get("ptbr", nome_time)

def bandeira_time(nome_time: str) -> str:
    return TEAM_META.get(normalizar_texto(nome_time).replace(" ", ""), {}).get("flag", "🏳️")

def usuario_autorizado(nome: str) -> bool:
    return normalizar_texto(nome) in [normalizar_texto(x) for x in WHITELIST_NOMES]

def calcular_pontos(gp_a, gp_b, gr_a, gr_b):
    if gr_a is None or gr_b is None: return 0
    v_real = "A" if gr_a > gr_b else ("B" if gr_b > gr_a else "E")
    v_palp = "A" if gp_a > gp_b else ("B" if gp_b > gp_a else "E")
    if gp_a == gr_a and gp_b == gr_b: return 25
    if v_palp == v_real and (gp_a - gp_b) == (gr_a - gr_b): return 15
    if v_palp == v_real: return 10
    return 0

def buscar_palpite_usuario(usuario, jogo_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT gols_time_a, gols_time_b FROM palpites_placar WHERE usuario = ? AND jogo_id = ?", (usuario, jogo_id))
    row = cur.fetchone()
    conn.close()
    return (row[0], row[1], True) if row else (0, 0, False)

# FUNÇÃO SALVAR ATUALIZADA COM MODO "JOICI" (SEM REGISTRO NO HISTÓRICO)
def salvar_palpite(usuario, jogo_id, gols_a, gols_b, silencioso=False):
    horario_salvo = datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")
    conn = conectar()
    cur = conn.cursor()
    
    if not silencioso:
        cur.execute("INSERT INTO palpites_historico (usuario, jogo_id, gols_time_a, gols_time_b, data_registro) VALUES (?, ?, ?, ?, ?)", (usuario, jogo_id, gols_a, gols_b, horario_salvo))
    
    cur.execute("INSERT INTO palpites_placar (usuario, jogo_id, gols_time_a, gols_time_b, data_registro) VALUES (?, ?, ?, ?, ?) ON CONFLICT(usuario, jogo_id) DO UPDATE SET gols_time_a = excluded.gols_time_a, gols_time_b = excluded.gols_time_b, data_registro = excluded.data_registro", (usuario, jogo_id, gols_a, gols_b, horario_salvo))
    
    conn.commit(); conn.close()
    return horario_salvo

def carregar_jogos_do_banco():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jogos_oficiais ORDER BY data_jogo")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "time_a": r[1], "time_b": r[2], "data_jogo": datetime.fromisoformat(r[3]), "gols_real_a": r[4], "gols_real_b": r[5], "status": r[6]} for r in rows]

# --- UI ---
st.set_page_config(page_title="Bolão", layout="centered")
inicializar_banco()
st.title("🏆 Bolão da Copa 2026")

usuario_input = st.text_input("Usuário:").strip()
usuario = usuario_input.lower()
autorizado = usuario_autorizado(usuario)

if autorizado:
    st.success(f"Logado: {usuario.title()}")
    jogos_copa = carregar_jogos_do_banco()
    
    aba1, aba2, aba3 = st.tabs(["🔮 Agenda & Palpites", "📁 Jogos Finalizados", "📊 Ranking Geral"])
    
    with aba1:
        agora = datetime.now(FUSO_BR)
        for jogo in [j for j in jogos_copa if j["status"] != "FT"]:
            foi_bloqueado = agora >= jogo["data_jogo"]
            # JOICI PODE EDITAR TUDO
            pode_palpitar = (not foi_bloqueado or usuario == "joici")
            pga, pgb, ja_palpitou = buscar_palpite_usuario(usuario, jogo["id"])
            
            with st.container(border=True):
                st.write(f"{bandeira_time(jogo['time_a'])} {nome_time_ptbr(jogo['time_a'])} x {nome_time_ptbr(jogo['time_b'])} {bandeira_time(jogo['time_b'])}")
                c_a, c_b, c_btn = st.columns(3)
                ga = c_a.number_input("Gols A", value=int(pga), key=f"a_{jogo['id']}", disabled=not pode_palpitar)
                gb = c_b.number_input("Gols B", value=int(pgb), key=f"b_{jogo['id']}", disabled=not pode_palpitar)
                
                if pode_palpitar:
                    if c_btn.button("Salvar", key=f"btn_{jogo['id']}"):
                        # Se for a Joici editando jogo bloqueado, não registra no histórico
                        eh_admin_silencioso = (usuario == "joici" and foi_bloqueado)
                        salvar_palpite(usuario, jogo['id'], ga, gb, silencioso=eh_admin_silencioso)
                        st.rerun()

    with aba_ranking:
        todos_palpites = conectar().execute("SELECT usuario, jogo_id, gols_time_a, gols_time_b FROM palpites_placar").fetchall()
        pontuacao, detalhes = {}, {}
        for u, j_id, pga, pgb in todos_palpites:
            nome = u.title()
            jogo = next((j for j in jogos_copa if j["id"] == j_id), None)
            if jogo and jogo["gols_real_a"] is not None:
                pts = calcular_pontos(pga, pgb, jogo["gols_real_a"], jogo["gols_real_b"])
                pontuacao[nome] = pontuacao.get(nome, 0) + pts
                if pts > 0:
                    detalhes.setdefault(nome, []).append((jogo, pga, pgb, pts))

        for nome, pts in sorted(pontuacao.items(), key=lambda x: x[1], reverse=True):
            with st.expander(f"{nome} — 🌟 {pts} pontos"):
                for j, pga, pgb, pts_j in detalhes.get(nome, []):
                    st.write(f"🌟 +{pts_j} pts | {nome_time_ptbr(j['time_a'])} {j['gols_real_a']}x{j['gols_real_b']} {nome_time_ptbr(j['time_b'])} (Palpite: {pga}x{pgb})")
