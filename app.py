# 🔹 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.61

### Novidades desta versão:
- Comentários linha a linha adicionados
- Filtro "Corner" agora só permite seleção entre "Red" e "Blue"
- Campo "Editar" agora usa `st.toggle` para destravar as caixas
- Corrigido erro ao editar colunas ausentes com try/except
- Informações de luta organizadas em tabelas lado a lado (Fight, Division, Opponent)
- Toggle ativa e bloqueia linha via coluna LockBy = "1724"
- Tarefas interativas com toggle: clique para alternar entre Required e Done
- Centralização dos textos das tabelas
"""

# 🔑 Importações necessárias
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

# 🔄 Carrega dados e corrige nomes duplicados
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["original_index"] = df.index
    if "CORNER" in df.columns:
        df.rename(columns={"CORNER": "Coach"}, inplace=True)
    return df, sheet

# 📂 Atualiza valores de célula individual
def salvar_valor(sheet, row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar valor em linha {row+2}, coluna {col_index+1}: {e}")

# ⚙️ Configuração inicial da página
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10000, key="autorefresh")

# 🎨 Estilo customizado em HTML e CSS
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.athlete-header { display: flex; justify-content: center; align-items: center; gap: 1rem; margin: 1rem 0; }
.avatar { border-radius: 50%; width: 65px; height: 65px; object-fit: cover; }
.name-tag { font-size: 1.8rem; font-weight: bold; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 3px; text-transform: uppercase; display: inline-block; cursor: pointer; text-align: center; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
table { width: 100%; margin: 5px 0; border-collapse: collapse; text-align: center; }
th, td { text-align: center; padding: 4px 8px; border: 1px solid #444; }
th { font-weight: bold; }
.section-label { font-weight: bold; margin-top: 1rem; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)
