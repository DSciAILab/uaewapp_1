import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
from st_aggrid import AgGrid, GridOptionsBuilder

# 🔐 Conecta ao Google Sheets usando as credenciais do secrets
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("UAEW_App").worksheet("Sheet1")
    return sheet

# 🔄 Carrega os dados da planilha como DataFrame
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# 📂 Atualiza célula específica
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Configuração da interface
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")

# 🌙 Estilo escuro e tags customizadas
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    .stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
    .stTextInput>div>div>input, .stSelectbox>div>div>div>input { background-color: #3a3b3c; color: #f0f0f0; border: 1px solid #888; }
    </style>
""", unsafe_allow_html=True)

# 📊 Barra lateral com filtros
df_original = load_data()
sheet = connect_sheet()

with st.sidebar:
    st.markdown("## Filtros")
    evento_sel = st.multiselect("Evento", sorted(df_original['Event'].dropna().unique()))
    corner_sel = st.multiselect("Corner", sorted(df_original['Corner'].dropna().unique()))
    modo = st.radio("Visualização", ["Dashboard", "DataGrid"])
    if st.button("🔄 Recarregar Dados"):
        st.cache_data.clear()
        st.rerun()

# 🔍 Filtragem dos dados
df = df_original.copy()
if evento_sel:
    df = df[df['Event'].isin(evento_sel)]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

if modo == "Dashboard":
    st.title("UAE Warriors 59-60")
    for i, row in df.iterrows():
        with st.expander(row['Name'], expanded=False):
            st.markdown(f"### 🥋 {row['Name']}")
            col1, col2, col3 = st.columns(3)

            col1.markdown(f"**Fight Order:** {row.get('Fight Order', '')}")
            col1.markdown(f"**Division:** {row.get('Division', '')}")
            col1.markdown(f"**Opponent:** {row.get('Oponent', '')}")

            coach = st.text_input("Coach", value=row.get("Coach", ""), key=f"coach_{i}")
            music1 = st.text_input("Music 1", value=row.get("Music 1", ""), key=f"music1_{i}")
            music2 = st.text_input("Music 2", value=row.get("Music 2", ""), key=f"music2_{i}")
            music3 = st.text_input("Music 3", value=row.get("Music 3", ""), key=f"music3_{i}")

            if st.button("Salvar", key=f"save_{i}"):
                for field, value in zip(["Coach", "Music 1", "Music 2", "Music 3"], [coach, music1, music2, music3]):
                    col_idx = df.columns.get_loc(field)
                    salvar_valor(sheet, i, col_idx, value)
                st.success("Dados atualizados com sucesso!")

elif modo == "DataGrid":
    st.title("📊 Visão em DataGrid")
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(enabled=True)
    gb.configure_default_column(editable=False, filterable=True)
    gb.configure_grid_options(domLayout='normal')
    grid_options = gb.build()
    AgGrid(df, gridOptions=grid_options, height=600, fit_columns_on_grid_load=True, theme="dark")
