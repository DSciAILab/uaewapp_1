import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

# 🔐 Conexão com o Google Sheets
@st.cache_resource
def connect_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client

# 🔄 Carregamento da planilha
@st.cache_data(ttl=300)
def load_data(sheet_name):
    client = connect_client()
    try:
        sheet = client.open("UAEW_App").worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except WorksheetNotFound:
        st.error(f"A aba '{sheet_name}' não foi encontrada.")
        st.stop()

# Configuração do layout
st.set_page_config(page_title="Dashboard UAEW", layout="wide")

# Estilo visual (tema escuro)
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

# Título
st.title("📋 Dashboard de Atletas - UAEW")

# Carregar dados
df = load_data("Sheet1")

# Exibir tabela completa
st.dataframe(df, use_container_width=True)
