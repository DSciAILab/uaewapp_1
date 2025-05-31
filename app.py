import streamlit as st
st.set_page_config(page_title="UAEW Fighters", layout="wide")

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🔐 Conexão com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet_file = client.open("UAEW_App")
    return sheet_file.worksheet("App")

# 🔄 Carrega dados e mostra cabeçalhos para diagnóstico
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()

    # 🧪 Diagnóstico direto nos cabeçalhos
    try:
        raw = sheet.row_values(1)
        headers = [h.strip() for h in raw]
        st.success("✅ Cabeçalhos da planilha lidos com sucesso:")
        st.code(headers)
    except Exception as e:
        st.error("❌ ERRO ao acessar os cabeçalhos da planilha.")
        st.write("Mensagem de erro:", str(e))
        st.stop()

    # Carrega dados normalmente se os cabeçalhos forem acessados
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["original_index"] = df.index
    if "CORNER" in df.columns:
        df.rename(columns={"CORNER": "Coach"}, inplace=True)
    return df, sheet

# 📂 Atualiza valor na célula
def salvar_valor(sheet, row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar valor: linha {row+2}, coluna {col_index+1}: {e}")

# 🌐 Estilo visual
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.athlete-header { display: flex; justify-content: center; align-items: center; gap: 1rem; margin: 1rem 0; }
.avatar { border-radius: 50%; width: 65px; height: 65px; object-fit: cover; }
.name-tag { font-size: 1.8rem; font-weight: bold; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 3px; text-transform: uppercase; display: inline-block; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
table { width: 100%; border-collapse: collapse; text-align: center; }
th, td { padding: 4px 8px; border: 1px solid #444; text-align: center; }
</style>
""", unsafe_allow_html=True)

# 🔁 Autorefresh
st_autorefresh(interval=10000, key="autorefresh")

# 🚀 Carrega dados (e mostra cabeçalhos)
df, sheet = load_data()

# Mensagem pós-diagnóstico
st.success("🚀 Dados carregados com sucesso. Pode continuar com o desenvolvimento do app.")
