import streamlit as st
import sqlite3
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# Configuração do Fuso Horário de Brasília
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# 1. INICIALIZAR O BANCO DE DADOS (Com a coluna de auditoria de horário)
def inicializar_banco():
    conexao = sqlite3.connect('bolao.db')
    cursor = conexao.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS palpites_placar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            jogo_id TEXT NOT NULL,
            gols_time_a INTEGER NOT NULL,
            gols_time_b INTEGER NOT NULL
        )
    ''')
    # Força a inclusão da coluna de horário caso ela não exista no banco do servidor
    try:
        cursor.execute('ALTER TABLE palpites_placar ADD COLUMN data_registro TEXT')
    except sqlite3.OperationalError:
        pass
    conexao.commit()
    conexao.close()

inicializar_banco()

# 2. BUSCAR JOGOS E PLACARES EM TEMPO REAL VIA API (FOOTBALL-DATA.ORG)
@st.cache_data(ttl=60) # Atualiza os dados da API a cada 1 minuto
def buscar_jogos_api_football_data():
    # Código 'WC' puxa a World Cup (Copa do Mundo de 2026)
    url = "https://api.football-data.org/v4/competitions/WC/matches"
    
    # Token público e ativo para a Copa do Mundo
    headers = {"X-Auth-Token": "3ffa7e87c87e447ab012984b3026120a"}
    
    try:
        resposta = requests.get(url, headers=headers, timeout=5)
        if resposta.status_code == 200:
            dados = resposta.json()
            jogos_formatados = []
            
            for item in dados.get('matches', []):
                # A API envia a data em UTC (ex: "2026-06-11T21:00:00Z")
                data_utc = datetime.fromisoformat(item['utcDate'].replace('Z', '+00:00'))
                # Converte instantaneamente para o horário de Brasília
                data_br = data_utc.astimezone(FUSO_BR)
                
                # Traduz o status da API para o nosso padrão (FT = Finalizado, NS = Aberto)
                status_real = "FT" if item['status'] == "FINISHED" else "NS"
                
                jogos_formatados.append({
                    "id": str(item['id']),
                    "time_a": item['homeTeam']['name'],
                    "time_b": item['awayTeam']['name'],
                    "data_jogo": data_br,
                    "gols_real_a": item['score']['fullTime']['home'],
                    "gols_real_b": item['score']['fullTime']['away'],
                    "status": status_real
                })
            return sorted(jogos_formatados, key=lambda x: x['data_jogo'])
    except:
        pass

    # SE A API FALHAR: Mantém o bolão online com os jogos da rodada inicial
    return [
        {"id": "api_fallback_1", "time_a": "Coreia", "time_b": "Tchéquia", "data_jogo": datetime(2026, 6, 11, 21, 0, tzinfo=FUSO_BR), "gols_real_a": None, "gols_real_b": None, "status": "NS"},
        {"id": "api_fallback_2", "time_a": "Canadá", "time_b": "Bósnia", "data_jogo": datetime(2026, 6, 12, 13, 0, tzinfo=FUSO_BR), "gols_real_a": None, "gols_real_b": None, "status": "NS"},
        {"id": "api_fallback_3", "time_a": "Estados Unidos", "time_b": "Paraguai", "data_jogo": datetime(2026, 6, 12, 16, 0, tzinfo=FUSO_BR), "gols_real_a": None, "gols_real_b": None, "status": "NS"},
        {"id": "api_fallback_4", "time_a": "Catar", "time_b": "Suíça", "data_jogo": datetime(2026, 6, 13, 13, 0, tzinfo=FUSO_BR), "gols_real_a": None, "gols_real_b": None, "status": "NS"},
        {"id": "api_fallback_5", "time_a": "Brasil", "time_b": "Marrocos", "data_jogo": datetime(2026, 6, 13, 16, 0, tzinfo=FUSO_BR), "gols_real_a": None, "gols_real_b": None, "status": "NS"}
    ]

# 3. MATEMÁTICA DO BOLÃO
def calcular_pontos_simples(gols_p_a, gols_p_b, gols_r_a, gols_r_b):
    if gols_r_a is None or gols_r_b is None: return 0
    gols_r_a, gols_r_b = int(gols_r_a), int(gols_r_b)
    
    vencedor_real = "A" if gols_r_a > gols_r_b else ("B" if gols_r_b > gols_r_a else "Empate")
    vencedor_palpite = "A" if gols_p_a > gols_p_b else ("B" if gols_p_b > gols_p_a else "Empate")
    
    if gols_p_a == gols_r_a and gols_p_b == gols_r_b: return 25  # Cravou placar
    elif vencedor_palpite == vencedor_real and (gols_p_a - gols_p_b) == (gols_r_a - gols_r_b): return 15  # Saldo
    elif vencedor_palpite == vencedor_real: return 10  # Vencedor simples
    return 0

# --- INTERFACE ---
st.set_page_config(page_title="Bolão Copa 2026", layout="centered")
st.title("🏆 Bolão da Copa 2026")

aba_palpites, aba_ranking = st.tabs(["🔮 Palpites & Agenda", "📊 Ranking Geral"])
jogos_copa = buscar_jogos_api_football_data()

with aba_palpites:
    usuario = st.text_input("Insira seu nome para começar:", placeholder=" ")
    
    if usuario:
        st.write("⚽ Próximas Partidas Sincronizadas da API:")
        st.markdown("---")
        agora = datetime.now(FUSO_BR)
        
        for jogo in jogos_copa:
            # BLOQUEIO CIRÚRGICO: Trava se a API marcar como FINISHED (FT) ou se o relógio de Brasília passou do horário do jogo
            foi_bloqueado = jogo['status'] == "FT" or agora >= jogo['data_jogo']
            
            st.subheader(f"🏟️ {jogo['time_a']} vs {jogo['time_b']}")
            
            if foi_bloqueado:
                st.error("🔒 Palpites encerrados para esta partida.")
                if jogo['gols_real_a'] is not None:
                    st.info(f"Placar Oficial: {jogo['time_a']} {int(jogo['gols_real_a'])} x {int(jogo['gols_real_b'])} {jogo['time_b']}")
            else:
                st.success(f"⏳ Disponível! Horário do jogo: {jogo['data_jogo'].strftime('%d/%m às %H:%M')}")
                
            col_g1, _ , col_g2 = st.columns([2, 1, 2])
            with col_g1:
                gols_a = st.number_input(f"Gols {jogo['time_a']}", min_value=0, max_value=10, value=0, key=f"ga_{jogo['id']}", disabled=foi_bloqueado)
            with col_g2:
                gols_b = st.number_input(f"Gols {jogo['time_b']}", min_value=0, max_value=10, value=0, key=f"gb_{jogo['id']}", disabled=foi_bloqueado)
                
            if not foi_bloqueado:
                if st.button(f"Salvar {gols_a} x {gols_b}", key=f"btn_{jogo['id']}"):
                    # Captura o horário preciso de Brasília no clique
                    horario_salvo = datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S")
                    
                    conexao = sqlite3.connect('bolao.db')
                    cursor = conexao.cursor()
                    cursor.execute('DELETE FROM palpites_placar WHERE usuario = ? AND jogo_id = ?', (usuario, jogo['id']))
                    cursor.execute('''
                        INSERT INTO palpites_placar (usuario, jogo_id, gols_time_a, gols_time_b, data_registro) 
                        VALUES (?, ?, ?, ?, ?)
                    ''', (usuario, jogo['id'], gols_a, gols_b, horario_salvo))
                    conexao.commit()
                    conexao.close()
                    st.success(f"Palpite registrado com sucesso às {horario_salvo}!")
            st.markdown("---")

with aba_ranking:
    st.subheader("🏅 Classificação dos Participantes")
    conexao = sqlite3.connect('bolao.db')
    cursor = conexao.cursor()
    cursor.execute('SELECT usuario, jogo_id, gols_time_a, gols_time_b, data_registro FROM palpites_placar')
    todos_palpites = cursor.fetchall()
    conexao.close()
    
    pontuacao_jogadores = {}
    mapa_jogos = {j['id']: j for j in jogos_copa}
    
    for palpite in todos_palpites:
        jogador, jogo_id, p_gols_a, p_gols_b = palpite[0], palpite[1], palpite[2], palpite[3]
        dt_reg = palpite[4] if len(palpite) > 4 else "Horário antigo"
            
        if jogador not in pontuacao_jogadores: pontuacao_jogadores[jogador] = 0.0
        if jogo_id in mapa_jogos:
            j = mapa_jogos[jogo_id]
            pontos = calcular_pontos_simples(p_gols_a, p_gols_b, j['gols_real_a'], j['gols_real_b'])
            pontuacao_jogadores[jogador] += pontos
            
    ranking_ordenado = sorted(pontuacao_jogadores.items(), key=lambda x: x[1], reverse=True)
    if ranking_ordenado:
        for posicao, (jogador, pontos) in enumerate(ranking_ordenado, start=1):
            st.write(f"**{posicao}º Lugar:** {jogador} — 🌟 {pontos} pontos")
            
        st.markdown("---")
        st.write("📋 **Histórico Geral de Palpites:**")
        for palpite in todos_palpites:
            jogador, jogo_id, p_gols_a, p_gols_b = palpite[0], palpite[1], palpite[2], palpite[3]
            dt_reg = palpite[4] if len(palpite) > 4 else "Horário antigo"
            if jogo_id in mapa_jogos:
                j = mapa_jogos[jogo_id]
                st.caption(f"⏱️ **{jogador}** jogou {p_gols_a}x{p_gols_b} em *{j['time_a']} vs {j['time_b']}* enviado às {dt_reg}")
    else:
        st.info("Nenhum palpite registrado ainda.")