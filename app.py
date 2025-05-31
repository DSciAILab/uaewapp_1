import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

# 🔐 Conecta ao Google Sheets
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

# 🔄 Carrega dados da aba
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

# Configuração da interface
st.set_page_config(page_title="Cartões de Atletas", layout="wide")

# Estilo escuro
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

# Título principal
st.title("🥋 UAE Warriors - Cartões de Atletas")

# Carregamento da planilha
df = load_data("Sheet1")

# Exibição por atleta com expanders
for i, row in df.iterrows():
    with st.expander(f"👤 {row['NAME']}"):
        st.write(f"📍 Nacionalidade: {row['Nationality']}")
        st.write(f"🏠 Residência: {row['Residence']}")
        st.write(f"📏 Altura: {row['Hight']}")
        st.write(f"📐 Alcance: {row['Range']}")
        st.write(f"⚖️ Peso: {row['Weight']}")
        st.write(f"🧑‍🏫 Técnico: {row.get('Coach', '')}")
        st.write(f"🎵 Música 1: {row.get('Music 1', '')}")
        st.write(f"🎵 Música 2: {row.get('Music 2', '')}")
        st.write(f"🎵 Música 3: {row.get('Music 3', '')}")
