import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

# 🔐 Conexão com Google Sheets
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

# 🔄 Carregamento dos dados
@st.cache_data(ttl=300)
def load_data(sheet_name):
    client = connect_client()
    try:
        sheet = client.open("UAEW_App").worksheet(sheet_name)
        data = sheet.get_all_records()
        return pd.DataFrame(data), sheet
    except WorksheetNotFound:
        st.error(f"A aba '{sheet_name}' não foi encontrada.")
        st.stop()

# Atualização individual
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Layout
st.set_page_config(page_title="Cartões UAEW", layout="wide")

# 🌑 Estilo escuro
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

st.title("🥋 Ficha de Atletas - UAE Warriors")

# 📊 Carregamento da planilha
df, sheet = load_data("Sheet1")

# 🎯 Filtros
col_filtro1, col_filtro2 = st.columns(2)
eventos = df['EVENT'].dropna().unique()
cantos = df['CORNER'].dropna().unique()

evento_selecionado = col_filtro1.selectbox("Evento", options=["Todos"] + list(eventos))
canto_selecionado = col_filtro2.selectbox("Corner", options=["Todos"] + list(cantos))

# Aplicar filtros
df_filtrado = df.copy()
if evento_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado['EVENT'] == evento_selecionado]
if canto_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado['CORNER'] == canto_selecionado]

# 📄 Interface por atleta
for i, row in df_filtrado.iterrows():
    with st.expander(f"👊 Atleta: {row['NAME']}"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.image(row.get("PHOTO", ""), width=150)
            row["Nationality"] = st.text_input("Nationality", value=row["Nationality"], key=f"nat_{i}")
            row["Residence"] = st.text_input("Residence", value=row["Residence"], key=f"res_{i}")
            row["Hight"] = st.text_input("Hight", value=row["Hight"], key=f"hgt_{i}")

        with col2:
            row["Range"] = st.text_input("Range", value=row["Range"], key=f"rng_{i}")
            row["Weight"] = st.text_input("Weight", value=row["Weight"], key=f"wgt_{i}")
            row["Coach"] = st.text_input("Coach", value=row["Coach"], key=f"cch_{i}")

        with col3:
            row["Music 1"] = st.text_input("Music 1", value=row["Music 1"], key=f"msc1_{i}")
            row["Music 2"] = st.text_input("Music 2", value=row["Music 2"], key=f"msc2_{i}")
            row["Music 3"] = st.text_input("Music 3", value=row["Music 3"], key=f"msc3_{i}")

        if st.button("Salvar", key=f"save_{i}"):
            for campo in [
                "Nationality", "Residence", "Hight", "Range", "Weight",
                "Coach", "Music 1", "Music 2", "Music 3"
            ]:
                try:
                    valor = row[campo]
                    col_index = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_index, valor)
                except Exception as e:
                    st.error(f"Erro ao salvar linha {i}, campo {campo}: {e}")
            st.success("✅ Dados salvos com sucesso!")
