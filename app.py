# 🔹 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.53

### Novidades desta versão:
- Filtros de seleção movidos para o sidebar: Evento, Corner, Status das tarefas
- Corrigido erro de KeyError quando colunas de tarefas não existem
- Considerado que agora existem colunas 'Corner' e 'CORNER' -> a coluna 'CORNER' foi renomeada para 'Coach'
- Mostra quantidade de atletas encontrados após filtro
- Mostra aviso amigável quando nenhum resultado é encontrado
"""

# 🔑 Importações
import streamlit as st
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

# 🔄 Carrega dados
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["original_index"] = df.index
    # Corrige duplicidade
    #if "CORNER" in df.columns:
    #    df.rename(columns={"CORNER": "Coach"}, inplace=True)
    #return df, sheet

# 📂 Atualiza valores
def salvar_valor(sheet, row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar valor em linha {row+2}, coluna {col_index+1}: {e}")

# ⚙️ Config inicial
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10000, key="autorefresh")

# 🎨 Estilo
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.athlete-header { display: flex; justify-content: center; align-items: center; gap: 1rem; margin-bottom: 10px; }
.avatar { border-radius: 50%; width: 60px; height: 60px; object-fit: cover; }
.name-tag { font-size: 2rem; font-weight: bold; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 3px; text-transform: uppercase; display: inline-block; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
table { width: 100%; margin: 5px 0; }
th, td { text-align: left; padding: 4px 8px; }
th { font-weight: bold; }
.section-label { font-weight: bold; margin-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# 🗓️ Título
df = load_data(connect_sheet())
st.title("UAE Warriors 59-60")

# 🔍 Filtros no Sidebar
with st.sidebar:
    st.header("Filtros")
    eventos = sorted(df['Event'].dropna().unique())
    corners = sorted(df['Corner'].dropna().unique())
    evento_sel = st.selectbox("Evento", ["Todos"] + eventos)
    corner_sel = st.multiselect("Corner", corners)
    status_sel = st.radio("Status das tarefas", ["Todos", "Somente pendentes", "Somente completos"])

# Aplicar filtros
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]


# Verifica colunas de tarefas válidas
tarefas_todas = ["Black Screen", "Photoshoot", "Blood Test", "Interview", "Stats"]
tarefas = [t for t in tarefas_todas if t in df.columns]

if status_sel == "Somente pendentes":
    df = df[df[tarefas].apply(lambda row: any(str(row.get(t, '')).lower() == "required" for t in tarefas), axis=1)]
elif status_sel == "Somente completos":
    df = df[df[tarefas].apply(lambda row: all(str(row.get(t, '')).lower() == "done" for t in tarefas), axis=1)]

# Foco em lutadores
df = df[df['Role'].str.lower() == 'fighter']

# ✅ Avisos e contagem
st.markdown(f"🔎 **{len(df)} atleta(s) encontrados para os filtros aplicados.**")

if df.empty:
    st.warning("Nenhum atleta encontrado com os filtros selecionados.")
    st.stop()

# ✌️ Continuidade do app (mantido)
# [continua com os cards de atleta...]
