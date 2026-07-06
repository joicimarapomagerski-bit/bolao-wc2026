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
]

STATUS_MAP = {
    "SCHEDULED": "NS",
    "TIMED": "NS",
    "IN_PLAY": "AO VIVO",
    "PAUSED": "INT",
    "FINISHED": "FT",
    "POSTPONED": "ADI",
    "SUSPENDED": "SUS",
    "CANCELLED": "CAN",
}

# ==========================================
# BANCO DE DADOS (Configuração Inicial)
# ==========================================
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS palpites_placar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_registro TEXT,
        usuario TEXT,
        gols_time_a INTEGER,
        gols_time_b INTEGER,
        confronto TEXT
    )
""")
conn.commit()

# --- INÍCIO DO BLOCO DE RESGATE AUTOMÁTICO DO EXCEL ---
import os
import pandas as pd

if os.path.exists("historico_pdf.xlsx"):
    try:
        st.info("🔄 Unificando dados salvos do PDF com os novos palpites... Aguarde.")
        
        # 1. Lê o Excel gerado pelo seu script offline do Colab
        df_pdf = pd.read_excel("historico_pdf.xlsx")
        
        # Mapeia os títulos exatos gerados pelo Colab para bater com o Banco de Dados
        df_pdf = df_pdf.rename(columns={
            'placar_time_a': 'gols_time_a',
            'placar_time_b': 'gols_time_b'
        })
        
        # Garante a ordem correta das colunas
        df_pdf = df_pdf[['data_registro', 'usuario', 'gols_time_a', 'gols_time_b', 'confronto']]
        
        # 2. Puxa os palpites NOVOS que já estão no banco de dados para não perder nada
        df_novos = pd.read_sql_query("SELECT data_registro, usuario, gols_time_a, gols_time_b, confronto FROM palpites_placar", conn)
        
        # 3. Junta o passado (PDF) com o presente (novos registros do app)
        df_total = pd.concat([df_pdf, df_novos], ignore_index=True)
        
        # 4. REGRA DO RANKING: Organiza por data cronológica
        df_total['data_registro'] = pd.to_datetime(df_total['data_registro'], errors='coerce')
        df_total = df_total.sort_values('data_registro')
        
        # Remove duplicadas de uma pessoa para o mesmo confronto, mantendo SEMPRE a última alteração (keep='last')
        df_total = df_total.drop_duplicates(subset=['usuario', 'confronto'], keep='last')
        
        # 5. Limpa temporariamente a tabela antiga para reinserir o bloco consolidado sem dar conflitos
        cursor.execute("DELETE FROM palpites_placar")
        for _, linha in df_total.iterrows():
            cursor.execute("""
                INSERT INTO palpites_placar (data_registro, usuario, gols_time_a, gols_time_b, confronto)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(linha['data_registro']),
                str(linha['usuario']).lower().strip(),
                int(linha['gols_time_a']),
                int(linha['gols_time_b']),
                str(linha['confronto']).strip()
            ))
        
        conn.commit()
        
        # 6. Remove o arquivo Excel para que o processo seja executado de forma definitiva apenas uma vez
        os.remove("historico_pdf.xlsx")
        st.success("🎉 Processo concluído! Histórico antigo restaurado e integrado aos novos palpites com sucesso!")
        
    except Exception as e:
        st.error(f"Erro ao processar as colunas do arquivo Excel: {e}")
# --- FIM DO BLOCO DE RESGATE AUTOMÁTICO ---

conn.close()

# ==========================================
# FUNÇÕES DE AUXÍLIO
# ==========================================
def obter_fuso_br():
    return ZoneInfo("America/Sao_Paulo")

def obter_agora_br():
    return datetime.now(obter_fuso_br())

def normalizar_nome_time(nome):
    if not nome:
        return ""
    nome_norm = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("utf-8").lower()
    return re.sub(r"[^a-z0-9\s]", "", nome_norm).strip()

MAPA_TRADUCAO = {
    "argentina": "Argentina", "south africa": "África do Sul", "algeria": "Argélia", "australia": "Austrália",
    "austria": "Áustria", "belgium": "Bélgica", "bosnia and herzegovina": "Bósnia e Herzegovina", "bosniaherzegovina": "Bósnia e Herzegovina",
    "brazil": "Brasil", "cape verde": "Cabo Verde", "canada": "Canadá", "qatar": "Catar",
    "colombia": "Colômbia", "congo": "Congo", "congo dr": "Congo", "south korea": "Coreia do Sul",
    "ivory coast": "Costa do Marfim", "croatia": "Croácia", "curacao": "Curaçao", "egypt": "Egito",
    "ecuador": "Equador", "scotland": "Escócia", "spain": "Espanha", "united states": "Estados Unidos",
    "france": "França", "ghana": "Gana", "haiti": "Haiti", "netherlands": "Holanda",
    "england": "Inglaterra", "iran": "Irã", "iraq": "Iraque", "jordan": "Jordânia",
    "japan": "Japão", "morocco": "Marrocos", "mexico": "México", "noruega": "Noruega", "norway": "Noruega",
    "new zealand": "Nova Zelândia", "panama": "Panamá", "paraguay": "Paraguai", "portugal": "Portugal",
    "senegal": "Senegal", "sweden": "Suécia", "switzerland": "Suíça", "czechia": "Tchéquia",
    "tunisia": "Tunísia", "turkey": "Turquia", "uzbekistan": "Usbequistão", "uruguay": "Uruguai",
}

def traduzir_nome_time_ptbr(nome_en):
    norm = normalizar_nome_time(nome_en)
    return MAPA_TRADUCAO.get(norm, nome_en)

@st.cache_data(ttl=300)
def buscar_dados_api():
    headers = {"X-Auth-Token": API_TOKEN}
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            return dados.get("matches", [])
        else:
            return []
    except Exception:
        return []

def carregar_agenda_jogos():
    partidas_api = buscar_dados_api()
    jogos = []
    
    if not partidas_api:
        return []
        
    for m in partidas_api:
        status_en = m.get("status", "SCHEDULED")
        status_pt = STATUS_MAP.get(status_en, "NS")
        
        utc_str = m.get("utcDate", "")
        dt_br = obter_agora_br()
        if utc_str:
            try:
                utc_dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC"))
                dt_br = utc_dt.astimezone(obter_fuso_br())
            except Exception:
                pass
                
        gols_a = None
        gols_b = None
        score = m.get("score", {})
        full_time = score.get("fullTime", {})
        
        if status_pt == "FT" or full_time.get("home") is not None:
            gols_a = full_time.get("home")
            gols_b = full_time.get("away")
            
        jogos.append({
            "id": str(m.get("id")),
            "time_a": m.get("homeTeam", {}).get("name", "Time A"),
            "time_b": m.get("awayTeam", {}).get("name", "Time B"),
            "data_jogo": dt_br,
            "status": status_pt,
            "gols_oficial_a": gols_a,
            "gols_oficial_b": gols_b,
        })
    return jogos

def registrar_palpite_db(usuario, confronto, ga, gb):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    agora_str = obter_agora_br().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO palpites_placar (data_registro, usuario, gols_time_a, gols_time_b, confronto)
        VALUES (?, ?, ?, ?, ?)
    """, (agora_str, usuario.lower().strip(), int(ga), int(gb), confronto.strip()))
    
    conn.commit()
    conn.close()

def carregar_palpites_efetivos():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT data_registro, usuario, gols_time_a, gols_time_b, confronto FROM palpites_placar", conn)
    conn.close()
    
    if df.empty:
        return pd.DataFrame(columns=['usuario', 'confronto', 'gols_time_a', 'gols_time_b', 'data_registro'])
        
    df['data_registro'] = pd.to_datetime(df['data_registro'], errors='coerce')
    df = df.sort_values('data_registro')
    df = df.drop_duplicates(subset=['usuario', 'confronto'], keep='last')
    return df

def calcular_pontos(ga_p, gb_p, ga_o, gb_o):
    if ga_o is None or gb_o is None:
        return 0
    if ga_p == ga_o and gb_p == gb_o:
        return 25
    vendedor_p = 1 if ga_p > gb_p else (-1 if ga_p < gb_p else 0)
    vendedor_o = 1 if ga_o > gb_o else (-1 if ga_o < gb_o else 0)
    
    if vendedor_p == vendedor_o:
        saldo_p = ga_p - gb_p
        saldo_o = ga_o - gb_o
        if saldo_p == saldo_o:
            return 15
        return 10
    return 0

# ==========================================
# INTERFACE DO STREAMLIT
# ==========================================
if AUTOREFRESH_OK:
    st_autorefresh(interval=60000, key="datarefresh")

st.sidebar.header("🔑 Identificação")
usuario_input = st.sidebar.text_input("Usuário:", value="", key="user_input_field")
usuario = usuario_input.strip().lower()

autorizado = False
nome_formatado = ""
if usuario:
    for nome in WHITELIST_NOMES:
        if nome.lower() == usuario:
            autorizado = True
            nome_formatado = nome
            break
    if not autorizado:
        st.sidebar.error("Usuário não cadastrado.")
else:
    st.sidebar.info("Informe seu usuário cadastrado para dar palpites.")

jogos = carregar_agenda_jogos()
df_palpites = carregar_palpites_efetivos()

aba_agenda, aba_finalizados, aba_ranking, aba_historico = st.tabs([
    "📅 Agenda & Palpites", 
    "✅ Jogos Finalizados", 
    "🏆 Ranking Geral", 
    "📜 Histórico"
])

# --- ABA 1: AGENDA & PALPITES ---
with aba_agenda:
    st.subheader("Próximos Jogos")
    agora = obter_agora_br()
    jogos_ativos = [j for j in jogos if j["status"] != "FT" and agora < j["data_jogo"]]
    
    if jogos_ativos:
        for j in jogos_ativos:
            ta_pt = traduzir_nome_time_ptbr(j["time_a"])
            tb_pt = traduzir_nome_time_ptbr(j["time_b"])
            chave_confronto = f"{ta_pt} x {tb_pt}"
            
            data_formatada = j["data_jogo"].strftime("%d/%m %H:%M")
            st.markdown(f"**{ta_pt} x {tb_pt}** — 🕒 {data_formatada}")
            
            palpite_atual = df_palpites[(df_palpites['usuario'] == usuario) & (df_palpites['confronto'] == chave_confronto)]
            val_a, val_b = 0, 0
            if not palpite_atual.empty:
                val_a = int(palpite_atual.iloc[0]['gols_time_a'])
                val_b = int(palpite_atual.iloc[0]['gols_time_b'])
                st.caption(f"Seu palpite salvo: {val_a} x {val_b}")
                
            if autorizado:
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    ga = st.number_input(f"Gols {ta_pt}", min_value=0, max_value=20, value=val_a, step=1, key=f"ga_{j['id']}")
                with col2:
                    gb = st.number_input(f"Gols {tb_pt}", min_value=0, max_value=20, value=val_b, step=1, key=f"gb_{j['id']}")
                with col3:
                    st.write("")
                    st.write("")
                    if st.button("Salvar Palpite", key=f"btn_{j['id']}"):
                        registrar_palpite_db(usuario, chave_confronto, ga, gb)
                        st.success("Palpite registrado!")
                        st.rerun()
            else:
                st.info("Insira um usuário autorizado na barra lateral para palpitar.")
            st.divider()
    else:
        st.info("Nenhum jogo agendado ou aberto para palpites.")

# --- ABA 2: JOGOS FINALIZADOS ---
with aba_finalizados:
    st.subheader("Resultados Encerrados")
    jogos_encerrados = [j for j in jogos if j["status"] == "FT" or (j["gols_oficial_a"] is not None)]
    
    if jogos_encerrados:
        for j in jogos_encerrados:
            ta_pt = traduzir_nome_time_ptbr(j["time_a"])
            tb_pt = traduzir_nome_time_ptbr(j["time_b"])
            st.markdown(f"⚽ **{ta_pt} {j['gols_oficial_a']} x {j['gols_oficial_b']} {tb_pt}**")
            
            chave_confronto = f"{ta_pt} x {tb_pt}"
            palpites_jogo = df_palpites[df_palpites['confronto'] == chave_confronto]
            
            if not palpites_jogo.empty:
                for _, p in palpites_jogo.iterrows():
                    pts = calcular_pontos(p['gols_time_a'], p['gols_time_b'], j['gols_oficial_a'], j['gols_oficial_b'])
                    user_nome = next((n for n in WHITELIST_NOMES if n.lower() == p['usuario']), p['usuario'])
                    st.caption(f"• {user_nome}: {p['gols_time_a']} x {p['gols_time_b']} ({pts} pts)")
            else:
                st.caption("Ninguém palpitou neste confronto.")
            st.divider()
    else:
        st.info("Nenhuma partida encerrada registrada ainda.")

# --- ABA 3: RANKING GERAL ---
with aba_ranking:
    st.subheader("Classificação dos Participantes")
    pontuacao = {nome.lower(): 0 for nome in WHITELIST_NOMES}
    
    for j in jogos:
        if j["gols_oficial_a"] is not None and j["gols_oficial_b"] is not None:
            ta_pt = traduzir_nome_time_ptbr(j["time_a"])
            tb_pt = traduzir_nome_time_ptbr(j["time_b"])
            chave_confronto = f"{ta_pt} x {tb_pt}"
            
            palpites_jogo = df_palpites[df_palpites['confronto'] == chave_confronto]
            for _, p in palpites_jogo.iterrows():
                if p['usuario'] in pontuacao:
                    pts = calcular_pontos(p['gols_time_a'], p['gols_time_b'], j['gols_oficial_a'], j['gols_oficial_b'])
                    pontuacao[p['usuario']] += pts
                    
    ranking = []
    for nome in WHITELIST_NOMES:
        ranking.append({
            "Participante": nome,
            "Pontos": pontuacao[nome.lower()]
        })
        
    df_rank = pd.DataFrame(ranking).sort_values(by="Pontos", ascending=False).reset_index(drop=True)
    df_rank.index += 1
    st.table(df_rank)

# --- ABA 4: HISTÓRICO ---
with aba_historico:
    st.subheader("Histórico de Alterações")
    conn = sqlite3.connect(DB_PATH)
    df_completo = pd.read_sql_query("SELECT data_registro, usuario, gols_time_a, gols_time_b, confronto FROM palpites_placar ORDER BY data_registro DESC", conn)
    conn.close()
    
    if not df_completo.empty:
        agora = obter_agora_br()
        for _, p in df_completo.iterrows():
            user_lower = p['usuario'].strip().lower()
            nome_formatado = next((n for n in WHITELIST_NOMES if n.lower() == user_lower), p['usuario'])
            
            jogo_encontrado = None
            for j in jogos:
                ta_pt = traduzir_nome_time_ptbr(j["time_a"])
                tb_pt = traduzir_nome_time_ptbr(j["time_b"])
                if f"{ta_pt} x {tb_pt}" == p['confronto']:
                    jogo_encontrado = j
                    break
                    
            jogo_bloqueado = False
            if jogo_encontrado:
                jogo_bloqueado = jogo_encontrado["status"] == "FT" or agora >= jogo_encontrado["data_jogo"]
                
            if jogo_bloqueado or usuario == user_lower:
                st.caption(f"{p['data_registro']} • {nome_formatado} alterou para {p['gols_time_a']}x{p['gols_time_b']} em {p['confronto']}")
            else:
                st.caption(f"{p['data_registro']} • {nome_formatado} atualizou o palpite em {p['confronto']} (🔒)")
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
