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
    "Joici", "Isa", "Dudu", "Gui", "Alan", "Fabio", "Gama", "Fer", "Cabral", "João", "Joãozinho", "Munhoz", "Moises", "Vanderley"
]

STATUS_MAP = {
    "SCHEDULED": "NS", "TIMED": "NS", "IN_PLAY": "LIVE", "PAUSED": "LIVE", "FINISHED": "FT", "POSTPONED": "ADIADO", "SUSPENDED": "SUSP", "CANCELLED": "CANCELADO"
}

TEAM_ALIASES = {
    "usa": "unitedstates", "u.s.a": "unitedstates", "us": "unitedstates", "unitedstates": "unitedstates", "unitedstatesofamerica": "unitedstates",
    "korea": "southkorea", "southkorea": "southkorea", "southkorearepublic": "southkorea", "republicofkorea": "southkorea", "korearepublic": "southkorea",
    "bosniaherzegovina": "bosniaherzegovina", "bosniaandherzegovina": "bosniaherzegovina", "czechrepublic": "czechia", "curacao": "curacao",
    "thenetherlands": "netherlands", "saudiarabia": "saudiarabia", "southafrica": "southafrica", "newzealand": "newzealand", "costarica": "costarica",
    "ivorycoast": "ivorycoast", "cotedivoire": "ivorycoast", "capeverde": "capeverde", "caboverde": "capeverde", "capeverdeislands": "capeverde",
    "algeria": "algeria", "jordania": "jordan", "jordan": "jordan", "uzbekistan": "uzbekistan", "usbequistao": "uzbekistan", "panama": "panama",
    "congo": "congo", "republicofthecongo": "congo", "congorepublic": "congo", "drcongo": "drcongo", "democraticrepublicofthecongo": "drcongo", "rdcongo": "drcongo"
}

TEAM_META = {
    "argentina": {"flag": "🇦🇷", "ptbr": "Argentina"}, "australia": {"flag": "🇦🇺", "ptbr": "Austrália"}, "austria": {"flag": "🇦🇹", "ptbr": "Áustria"},
    "belgium": {"flag": "🇧🇪", "ptbr": "Bélgica"}, "brazil": {"flag": "🇧🇷", "ptbr": "Brasil"}, "bosniaherzegovina": {"flag": "🇧🇦", "ptbr": "Bósnia e Herzegovina"},
    "canada": {"flag": "🇨🇦", "ptbr": "Canadá"}, "cameroon": {"flag": "🇨🇲", "ptbr": "Camarões"}, "chile": {"flag": "🇨🇱", "ptbr": "Chile"},
    "colombia": {"flag": "🇨🇴", "ptbr": "Colômbia"}, "costarica": {"flag": "🇨🇷", "ptbr": "Costa Rica"}, "croatia": {"flag": "🇭🇷", "ptbr": "Croácia"},
    "curacao": {"flag": "🇨🇼", "ptbr": "Curaçao"}, "czechia": {"flag": "🇨🇿", "ptbr": "Tchéquia"}, "denmark": {"flag": "🇩🇰", "ptbr": "Dinamarca"},
    "ecuador": {"flag": "🇪🇨", "ptbr": "Equador"}, "egypt": {"flag": "🇪🇬", "ptbr": "Egito"}, "england": {"flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "ptbr": "Inglaterra"},
    "france": {"flag": "🇫🇷", "ptbr": "França"}, "germany": {"flag": "🇩🇪", "ptbr": "Alemanha"}, "ghana": {"flag": "🇬🇭", "ptbr": "Gana"},
    "haiti": {"flag": "🇭🇹", "ptbr": "Haiti"}, "iran": {"flag": "🇮🇷", "ptbr": "Irã"}, "iraq": {"flag": "🇮🇶", "ptbr": "Iraque"},
    "ireland": {"flag": "🇮🇪", "ptbr": "Irlanda"}, "italy": {"flag": "🇮🇹", "ptbr": "Itália"}, "japan": {"flag": "🇯🇵", "ptbr": "Japão"},
    "southkorea": {"flag": "🇰🇷", "ptbr": "Coreia do Sul"}, "mexico": {"flag": "🇲🇽", "ptbr": "México"}, "morocco": {"flag": "🇲🇦", "ptbr": "Marrocos"},
    "netherlands": {"flag": "🇳🇱", "ptbr": "Holanda"}, "newzealand": {"flag": "🇳🇿", "ptbr": "Nova Zelândia"}, "nigeria": {"flag": "🇳🇬", "ptbr": "Nigéria"},
    "norway": {"flag": "🇳🇴", "ptbr": "Noruega"}, "paraguay": {"flag": "🇵🇾", "ptbr": "Paraguai"}, "peru": {"flag": "🇵🇪", "ptbr": "Peru"},
    "poland": {"flag": "🇵🇱", "ptbr": "Polônia"}, "portugal": {"flag": "🇵🇹", "ptbr": "Portugal"}, "qatar": {"flag": "🇶🇦", "ptbr": "Catar"},
    "romania": {"flag": "🇷🇴", "ptbr": "Romênia"}, "saudiarabia": {"flag": "🇸🇦", "ptbr": "Arábia Saudita"}, "scotland": {"flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "ptbr": "Escócia"},
    "senegal": {"flag": "🇸🇳", "ptbr": "Senegal"}, "serbia": {"flag": "🇷🇸", "ptbr": "Sérvia"}, "southafrica": {"flag": "🇿🇦", "ptbr": "África do Sul"},
    "spain": {"flag": "🇪🇸", "ptbr": "Espanha"}, "sweden": {"flag": "🇸🇪", "ptbr": "Suécia"}, "switzerland": {"flag": "🇨🇭", "ptbr": "Suíça"},
    "turkey": {"flag": "🇹🇷", "ptbr": "Turquia"}, "unitedstates": {"flag": "🇺🇸", "ptbr": "Estados Unidos"}, "uruguay": {"flag": "🇺🇾", "ptbr": "Uruguai"},
    "wales": {"flag": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "ptbr": "País de Gales"}, "tunisia": {"flag": "🇹🇳", "ptbr": "Tunísia"}, "algeria": {"flag": "🇩🇿", "ptbr": "Argélia"},
    "capeverde": {"flag": "🇨🇻", "ptbr": "Cabo Verde"}, "ivorycoast": {"flag": "🇨🇮", "ptbr": "Costa do Marfim"}, "cotedivoire": {"flag": "🇨🇮", "ptbr": "Costa do Marfim"},
    "jordan": {"flag": "🇯🇴", "ptbr": "Jordânia"}, "uzbekistan": {"flag": "🇺🇿", "ptbr": "Usbequistão"}, "congodr": {"flag": "🇨🇩", "ptbr": "Congo"},
    "drcongo": {"flag": "🇨🇩", "ptbr": "República Democrática do Congo"}, "democraticrepublicofthecongo": {"flag": "🇨🇩", "ptbr": "República Democrática do Congo"}, "panama": {"flag": "🇵🇦", "ptbr": "Panamá"}
}

def conectar():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def adicionar_coluna_se_nao_existir(cursor, tabela, definicao_coluna):
    try:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {definicao_coluna}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise

def normalizar_texto(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = txt.strip().lower().replace("&", " and ")
    txt = re.sub(r"[^a-z0-9 ]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()

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

def usuario_autorizado(nome: str) -> bool:
    if not nome: return False
    wl = {normalizar_texto(x) for x in WHITELIST_NOMES if x.strip()}
    return normalizar_texto(nome) in wl

def inicializar_banco():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS palpites_placar (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, jogo_id TEXT NOT NULL, gols_time_a INTEGER NOT NULL, gols_time_b INTEGER NOT NULL, data_registro TEXT, confronto TEXT, UNIQUE(usuario, jogo_id))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS palpites_historico (id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, jogo_id TEXT NOT NULL, gols_time_a INTEGER NOT NULL, gols_time_b INTEGER NOT NULL, data_registro TEXT NOT NULL, confronto TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS jogos_oficiais (id TEXT PRIMARY KEY, time_a TEXT NOT NULL, time_b TEXT NOT NULL, data_jogo TEXT NOT NULL, gols_real_a INTEGER, gols_real_b INTEGER, status TEXT NOT NULL, stage TEXT, ultima_atualizacao TEXT)""")
    adicionar_coluna_se_nao_existir(cur, "palpites_placar", "confronto TEXT")
    adicionar_coluna_se_nao_existir(cur, "palpites_historico", "confronto TEXT")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_time_a REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_empate REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odd_time_b REAL")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "odds_atualizadas_em TEXT")
    adicionar_coluna_se_nao_existir(cur, "jogos_oficiais", "fonte_odds TEXT")
    conn.commit()
    conn.close()

def limpar_rotulo_time(rotulo: str) -> str:
    rotulo = re.sub(r"\s+", " ", (rotulo or "").strip())
    palavras = rotulo.split()
    if len(palavras) % 2 == 0 and palavras[:len(palavras)//2] == palavras[len(palavras)//2:]:
        rotulo = " ".join(palavras[:len(palavras)//2])
    return rotulo.strip(" -")

@st.cache_data(ttl=60, show_spinner=False)
def buscar_jogos_api():
    headers = {"X-Auth-Token": API_TOKEN}
    resp = requests.get(API_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    jogos = []
    for item in resp.json().get("matches", []):
        data_br = datetime.fromisoformat(item["utcDate"].replace("Z", "+00:00")).astimezone(FUSO_BR)
        score = item.get("score", {}) or {}
        reg_time = score.get("regularTime")
        gols_a = reg_time.get("home") if reg_time and reg_time.get("home") is not None else score.get("fullTime", {}).get("home")
        gols_b = reg_time.get("away") if reg_time and reg_time.get("away") is not None else score.get("fullTime", {}).get("away")
        jogos.append({"id": str(item["id"]), "time_a": item.get("homeTeam", {}).get("name", "A Definir"), "time_b": item.get("awayTeam", {}).get("name", "A Definir"), "data_jogo": data_br.isoformat(), "gols_real_a": gols_a, "gols_real_b": gols_b, "status": STATUS_MAP.get(item.get("status"), item.get("status")), "stage": item.get("stage"), "ultima_atualizacao": datetime.now(FUSO_BR).isoformat()})
    return sorted(jogos, key=lambda x: x["data_jogo"])

@st.cache_data(ttl=300, show_spinner=False)
def buscar_odds_native_stats():
    try:
        texto = re.sub(r"<[^>]+>", " ", requests.get(NATIVE_STATS_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text).replace("\xa0", " ")
        texto = re.sub(r"\s+", " ", texto)[texto.find("Next matches:"):texto.find("Standings:")]
        padrao = re.compile(r"(20\d{2}/\d{2}/\d{2},\s*\d{2}h\d{2})\s+(.+?)\s+([A-Z]{3})\s+-\s+(.+?)\s+([A-Z]{3})\s+([0-9.]+) \s*/\s*([0-9.]+) \s*/\s*([0-9.]+)")
        odds = []
        for m in padrao.finditer(texto):
            odds.append({"time_a": limpar_rotulo_time(m.group(2)), "time_b": limpar_rotulo_time(m.group(4)), "odd_time_a": float(m.group(6)), "odd_empate": float(m.group(7)), "odd_time_b": float(m.group(8)), "odds_atualizadas_em": datetime.now(FUSO_BR).isoformat(), "fonte_odds": "native-stats"})
        return odds
    except: return []

def salvar_jogos_no_banco(jogos):
    conn = conectar()
    cur = conn.cursor()
    for j in jogos:
        cur.execute("INSERT INTO jogos_oficiais (id, time_a, time_b, data_jogo, gols_real_a, gols_real_b, status, stage, ultima_atualizacao) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET time_a=excluded.time_a, time_b=excluded.time_b, data_jogo=excluded.data_jogo, gols_real_a=excluded.gols_real_a, gols_real_b=excluded.gols_real_b, status=excluded.status, stage=excluded.stage, ultima_atualizacao=excluded.ultima_atualizacao", (j["id"], j["time_a"], j["time_b"], j["data_jogo"], j["gols_real_a"], j["gols_real_b"], j["status"], j["stage"], j["ultima_atualizacao"]))
    conn.commit()
    conn.close()

def salvar_odds_no_banco(lista_odds):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, time_a, time_b FROM jogos_oficiais")
    indice = {(normalizar_nome_time(ta), normalizar_nome_time(tb)): j_id for j_id, ta, tb in cur.fetchall()}
    atualizados = 0
    for item in lista_odds:
        na, nb = normalizar_nome_time(item["time_a"]), normalizar_nome_time(item["time_b"])
        j_id = indice.get((na, nb)) or next((v for (da, db), v in indice.items() if (na in da and nb in db)), None)
        if j_id:
            cur.execute("UPDATE jogos_oficiais SET odd_time_a=?, odd_empate=?, odd_time_b=?, odds_atualizadas_em=?, fonte_odds=? WHERE id=?", (item["odd_time_a"], item["odd_empate"], item["odd_time_b"], item["odds_atualizadas_em"], item["fonte_odds"], j_id))
            if cur.rowcount: atualizados += 1
    conn.commit()
    conn.close()
    return atualizados

def carregar_jogos_do_banco():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, time_a, time_b, data_jogo, gols_real_a, gols_real_b, status, ultima_atualizacao, odd_time_a, odd_empate, odd_time_b, odds_atualizadas_em, fonte_odds FROM jogos_oficiais ORDER BY data_jogo")
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "time_a": r[1], "time_b": r[2], "data_jogo": datetime.fromisoformat(r[3]), "gols_real_a": r[4], "gols_real_b": r[5], "status": r[6], "ultima_atualizacao": r[7], "odd_time_a": r[8], "odd_empate": r[9], "odd_time_b": r[10], "odds_atualizadas_em": r[11], "fonte_odds": r[12]} for r in rows]

def sincronizar_agenda_e_odds():
    msgs = []
    try:
        jogos = buscar_jogos_api()
        salvar_jogos_no_banco(jogos)
        msgs.append(f"Agenda OK ({len(jogos)} jogos)")
    except Exception as e: msgs.append(f"Agenda falhou: {e}")
    try:
        msgs.append(f"Odds OK ({salvar_odds_no_banco(buscar_odds_native_stats())} jogos atualizados)")
    except Exception as e: msgs.append(f"Odds falharam: {e}")
    return msgs

def calcular_pontos(gp_a, gp_b, gr_a, gr_b):
    if gr_a is None or gr_b is None: return 0
    if gp_a == gr_a and gp_b == gr_b: return 25
    if (gp_a > gp_b and gr_a > gr_b) or (gp_a < gp_b and gr_a < gp_b) or (gp_a == gp_b and gr_a == gr_b):
        return 15 if (gp_a - gp_b) == (gr_a - gr_b) else 10
    return 0

def buscar_palpite_usuario(usuario, jogo_id):
    if not usuario: return (0, 0, False)
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT gols_time_a, gols_time_b FROM palpites_placar WHERE usuario=? AND jogo_id=?", (usuario, jogo_id))
    row = cur.fetchone()
    conn.close()
    return (row[0], row[1], True) if row else (0, 0, False)

def salvar_palpite(usuario, jogo_id, gols_a, gols_b):
    horario_salvo = datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")
    conn = conectar()
    cur = conn.cursor()
    cur.execute("INSERT INTO palpites_historico (usuario, jogo_id, gols_time_a, gols_time_b, data_registro, confronto) VALUES (?, ?, ?, ?, ?, ?)", (usuario, jogo_id, gols_a, gols_b, horario_salvo, ""))
    cur.execute("INSERT INTO palpites_placar (usuario, jogo_id, gols_time_a, gols_time_b, data_registro, confronto) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(usuario, jogo_id) DO UPDATE SET gols_time_a=excluded.gols_time_a, gols_time_b=excluded.gols_time_b, data_registro=excluded.data_registro", (usuario, jogo_id, gols_a, gols_b, horario_salvo, ""))
    conn.commit()
    conn.close()
    return horario_salvo

def carregar_historico(limit=300):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT usuario, jogo_id, gols_time_a, gols_time_b, data_registro, confronto FROM palpites_historico ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows

def processar_recuperacao_excel():
    import os
    import pandas as pd
    if os.path.exists("historico_pdf.xlsx"):
        try:
            st.info("🔄 Processando arquivo Excel de recuperação... Aguarde.")
            df_pdf = pd.read_excel("historico_pdf.xlsx")
            
            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id, time_a, time_b FROM jogos_oficiais")
            jogos_db = cur.fetchall()
            
            mapa_confrontos_id = {}
            for j_id, ta, tb in jogos_db:
                ta_pt = nome_time_ptbr(ta)
                tb_pt = nome_time_ptbr(tb)
                mapa_confrontos_id[f"{normalizar_nome_time(ta_pt)}x{normalizar_nome_time(tb_pt)}"] = str(j_id)
                mapa_confrontos_id[f"{normalizar_nome_time(tb_pt)}x{normalizar_nome_time(ta_pt)}"] = str(j_id)
                mapa_confrontos_id[f"{normalizar_nome_time(ta)}x{normalizar_nome_time(tb)}"] = str(j_id)
                mapa_confrontos_id[f"{normalizar_nome_time(tb)}x{normalizar_nome_time(ta)}"] = str(j_id)
                
            palpites_pdf_convertidos = []
            for _, linha in df_pdf.iterrows():
                confronto_txt = str(linha['confronto'])
                partes_times = re.split(r"\s+[xX]\s+", confronto_txt)
                if len(partes_times) < 2: continue
                
                t_a_limpo = partes_times[0].strip()
                t_b_limpo = partes_times[1].strip()
                chave_busca = f"{normalizar_nome_time(t_a_limpo)}x{normalizar_nome_time(t_b_limpo)}"
                
                # Se não mapear id oficial, gera uma string segura para não descartar o palpite
                j_id_final = mapa_confrontos_id.get(chave_busca, f"TXT_{chave_busca}")
                chave_confronto_formatada = f"{nome_time_ptbr(t_a_limpo)} x {nome_time_ptbr(t_b_limpo)}"
                
                palpites_pdf_convertidos.append({
                    "data_registro": str(linha['data_registro']),
                    "usuario": str(linha['usuario']).lower().strip(),
                    "jogo_id": j_id_final,
                    "gols_time_a": int(linha['placar_time_a']),
                    "gols_time_b": int(linha['placar_time_b']),
                    "confronto": chave_confronto_formatada
                })
            
            df_pdf_estruturado = pd.DataFrame(palpites_pdf_convertidos)
            if not df_pdf_estruturado.empty:
                df_novos = pd.read_sql_query("SELECT data_registro, usuario, jogo_id, gols_time_a, gols_time_b, confronto FROM palpites_placar", conn)
                df_total = pd.concat([df_pdf_estruturado, df_novos], ignore_index=True)
                df_total['data_registro'] = pd.to_datetime(df_total['data_registro'], errors='coerce')
                df_total = df_total.sort_values('data_registro')
                df_total = df_total.drop_duplicates(subset=['usuario', 'jogo_id'], keep='last')
                
                cur.execute("DELETE FROM palpites_placar")
                for _, row_p in df_total.iterrows():
                    cur.execute("INSERT INTO palpites_placar (usuario, jogo_id, gols_time_a, gols_time_b, data_registro, confronto) VALUES (?, ?, ?, ?, ?, ?)", (str(row_p['usuario']), str(row_p['jogo_id']), int(row_p['gols_time_a']), int(row_p['gols_time_b']), str(row_p['data_registro']), str(row_p['confronto'])))
                
                for _, row_h in df_pdf_estruturado.iterrows():
                    cur.execute("INSERT INTO palpites_historico (usuario, jogo_id, gols_time_a, gols_time_b, data_registro, confronto) VALUES (?, ?, ?, ?, ?, ?)", (str(row_h['usuario']), str(row_h['jogo_id']), int(row_h['gols_time_a']), int(row_h['gols_time_b']), str(row_h['data_registro']), str(row_h['confronto'])))
                
                conn.commit()
                os.remove("historico_pdf.xlsx")
                st.success("🎉 Sensacional! Todos os palpites antigos e novos foram unificados com sucesso!")
                st.rerun()
            conn.close()
        except Exception as e:
            st.error(f"Erro no processamento do arquivo de recuperação: {e}")

st.set_page_config(page_title="Bolão Copa 2026", layout="centered")
inicializar_banco()
st.caption(" | ".join(sincronizar_agenda_e_odds()))
processar_recuperacao_excel()

if AUTOREFRESH_OK: st_autorefresh(interval=60000, key="refresh_agenda")

st.title("🏆 Bolão da Copa 2026")
try:
    with open(DB_PATH, "rb") as file:
        st.download_button(label="📥 Baixar Banco de Dados (Backup)", data=file, file_name="bolao_backup.db", mime="application/octet-stream")
except: pass

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("🔄 Atualizar agora", use_container_width=True):
        buscar_jogos_api.clear()
        buscar_odds_native_stats.clear()
        st.rerun()

usuario_input = st.text_input("👤 Usuário:", placeholder="Digite seu nome").strip()
autorizado = usuario_autorizado(usuario_input)
usuario = usuario_input.lower() if autorizado else ""

if not usuario_input: st.info("Informe um usuário autorizado para palpitar.")
elif not autorizado: st.warning("Usuário não encontrado.")
else: st.success(f"✅ Usuário: {usuario_input.title()}")

jogos_copa = carregar_jogos_do_banco()
jogos_ativos = [j for j in jogos_copa if j["status"] != "FT"]
jogos_finalizados = [j for j in jogos_copa if j["status"] == "FT"]

aba_palpites, aba_finalizados, aba_ranking, aba_historico = st.tabs(["🔮 Agenda & Palpites", "📁 Jogos Finalizados", "📊 Ranking Geral", "📜 Histórico"])

with aba_palpites:
    agora = datetime.now(FUSO_BR)
    for jogo in jogos_ativos:
        foi_bloqueado = agora >= jogo["data_jogo"]
        pode_palpitar = autorizado and not foi_bloqueado
        pga, pgb, ja_palpitou = buscar_palpite_usuario(usuario, jogo["id"])
        
        with st.container(border=True):
            c_time_a, c_gols_a, c_x, c_gols_b, c_time_b, c_btn = st.columns([3, 1, 0.5, 1, 3, 2])
            with c_time_a: st.markdown(f"<div style='text-align: right; margin-top: 5px;'><b>{nome_time_ptbr(jogo['time_a'])}</b> {bandeira_time(jogo['time_a'])}</div>", unsafe_allow_html=True)
            with c_gols_a: gols_a = st.number_input("GA", min_value=0, max_value=20, value=int(pga), key=f"ga_{jogo['id']}", disabled=not pode_palpitar, label_visibility="collapsed")
            with c_x: st.markdown("<div style='text-align: center; color: gray; margin-top: 5px;'>x</div>", unsafe_allow_html=True)
            with c_gols_b: gols_b = st.number_input("GB", min_value=0, max_value=20, value=int(pgb), key=f"gb_{jogo['id']}", disabled=not pode_palpitar, label_visibility="collapsed")
            with c_time_b: st.markdown(f"<div style='text-align: left; margin-top: 5px;'>{bandeira_time(jogo['time_b'])} <b>{nome_time_ptbr(jogo['time_b'])}</b></div>", unsafe_allow_html=True)
            with c_btn:
                if pode_palpitar:
                    if st.button("Salvar", key=f"btn_{jogo['id']}", use_container_width=True):
                        salvar_palpite(usuario, jogo["id"], gols_a, gols_b)
                        st.rerun()
                if ja_palpitou: st.markdown(f"<div style='text-align: center; color: #10b981; font-size: 12px;'>✅ {pga} x {pgb}</div>", unsafe_allow_html=True)

with aba_finalizados:
    for Urban_jogo in jogos_finalizados:
        pga, pgb, ja_palpitou = buscar_palpite_usuario(usuario, Urban_jogo["id"])
        with st.container(border=True):
            st.markdown(f"⚽ **{nome_time_ptbr(Urban_jogo['time_a'])} {Urban_jogo['gols_real_a']} x {Urban_jogo['gols_real_b']} {nome_time_ptbr(Urban_jogo['time_b'])}**")
            if ja_palpitou:
                pts = calcular_pontos(pga, pgb, Urban_jogo["gols_real_a"], Urban_jogo["gols_real_b"])
                st.caption(f"Seu palpite: {pga} x {pgb} ({'+' if pts>0 else ''}{pts} pontos)")

with aba_ranking:
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT usuario, jogo_id, gols_time_a, gols_time_b FROM palpites_placar")
    todos_palpites = cur.fetchall()
    conn.close()
    
    pontuacao = {n.lower(): 0 for n in WHITELIST_NOMES}
    mapa_jogos = {j["id"]: j for j in jogos_copa}
    
    for u, j_id, pga, pgb in todos_palpites:
        jogo = mapa_jogos.get(j_id)
        if jogo:
            if u in pontuacao:
                pontuacao[u] += calcular_pontos(pga, pgb, jogo["gols_real_a"], jogo["gols_real_b"])
                
    df_rank = pd.DataFrame([{"Participante": k.title(), "Pontos": v} for k, v in pontuacao.items()]).sort_values(by="Pontos", ascending=False).reset_index(drop=True)
    df_rank.index += 1
    st.table(df_rank)

    st.markdown("---")
    st.write("📋 **Palpites válidos para o Ranking**")
    if todos_palpites:
        palpites_por_jogo = {}
        for usuario_nome, jogo_id, pga, pgb in todos_palpites:
            palpites_por_jogo.setdefault(jogo_id, []).append((usuario_nome, pga, pgb))
            
        for jogo in jogos_copa:
            if jogo["id"] in palpites_por_jogo:
                nome_a = nome_time_ptbr(jogo["time_a"])
                nome_b = nome_time_ptbr(jogo["time_b"])
                jogo_bloqueado = jogo["status"] == "FT" or agora >= jogo["data_jogo"]
                status_txt = "✅" if (jogo["status"] == "FT") else ("🔒" if jogo_bloqueado else "⏳")
                
                with st.expander(f"{bandeira_time(jogo['time_a'])} {nome_a} x {nome_b} {bandeira_time(jogo['time_b'])} | {status_txt}"):
                    for usuario_nome, pga, pgb in palpites_por_jogo[jogo["id"]]:
                        if jogo_bloqueado or usuario_nome.lower() == usuario:
                            st.markdown(f"**{usuario_nome.title()}** ➔ {pga} x {pgb}", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{usuario_nome.title()}** ➔ 🔒", unsafe_allow_html=True)
                            
        for j_id, lista_p in palpites_por_jogo.items():
            if j_id.startswith("TXT_"):
                # Captura palpites de texto forçados que a API ainda não indexou no banco local
                with st.expander(f"🔮 Jogo Manual (Resgatado) | 🔒 Forçado"):
                    for usuario_nome, pga, pgb in lista_p:
                        st.markdown(f"**{usuario_nome.title()}** ➔ {pga} x {pgb}", unsafe_allow_html=True)

with aba_historico:
    st.subheader("📜 Linhas do Histórico")
    historico = carregar_historico(limit=500)
    if historico:
        for u, j_id, pga, pgb, dt_reg, conf_db in urban_hist := historico:
            jogo = mapa_jogos.get(j_id)
            nome_conf = conf_db if conf_db else f"Jogo ID {j_id}"
            if jogo:
                nome_conf = f"{nome_time_ptbr(jogo['time_a'])} x {nome_time_ptbr(jogo['time_b'])}"
            st.caption(f"{dt_reg} • {u.title()} alterou para {pga}x{pgb} em {nome_conf}")
    else:
        st.info("Nenhuma alteração registrada ainda.")
        
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
