import sqlite3
import pandas as pd

# 1. Carregar os palpites recuperados do PDF/Excel
# Se o seu arquivo for CSV, use: pd.read_csv("Palpites_Recuperados.xlsx - Sheet1.csv")
df_pdf = pd.read_excel("Palpites_Recuperados_Do_PDF.xlsx")

# Conectar ao banco de dados atual (onde estão os palpites novos)
conn = sqlite3.connect("bolao.db")
cursor = conn.cursor()

print("Buscando palpites novos salvos recentemente...")
try:
    df_novos = pd.read_sql_query("SELECT data_registro, usuario, gols_time_a, gols_time_b, confronto FROM palpites_placar", conn)
except Exception:
    df_novos = pd.DataFrame()

# 2. Juntar os dados antigos do PDF com os novos do aplicativo
if not df_novos.empty:
    print(f"Encontrados {len(df_novos)} palpites novos no sistema.")
    df_total = pd.concat([df_pdf, df_novos], ignore_index=True)
else:
    df_total = df_pdf

# 3. Garantir a regra do ranking: ordenar por data e manter apenas o mais recente
df_total['data_registro'] = pd.to_datetime(df_total['data_registro'], errors='coerce')
df_total = df_total.sort_values('data_registro')

# Remove duplicatas de um mesmo usuário para o mesmo jogo, mantendo o último (keep='last')
df_total = df_total.drop_duplicates(subset=['usuario', 'confronto'], keep='last')

# 4. Inserir de volta no banco de dados limpo
cursor.execute("DELETE FROM palpites_placar") # Limpa para evitar erros de conflito

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
conn.close()
print(f"🎉 Sucesso! Banco de dados atualizado com {len(df_total)} palpites definitivos e unificados.")