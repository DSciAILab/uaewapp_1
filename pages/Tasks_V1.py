
# Home.py

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- Configuração da Página ---
st.set_page_config(
    page_title="UAEW App - Home",
    page_icon="🏠",
    layout="wide"
)

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
ATTENDANCE_TAB_NAME = "Attendance"

# --- Conexão e Carregamento de Dados ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception:
        return None

@st.cache_data(ttl=600)
def load_summary_data(sheet_name):
    try:
        client = get_gspread_client()
        if client is None:
            st.error("Erro de conexão com a API do Google. Verifique as credenciais.", icon="🚨")
            return None, None
        
        spreadsheet = client.open(sheet_name)
        
        athletes_ws = spreadsheet.worksheet(ATHLETES_TAB_NAME).get_all_records()
        df_athletes = pd.DataFrame(athletes_ws)
        if not df_athletes.empty and "INACTIVE" in df_athletes.columns and "ROLE" in df_athletes.columns:
             df_athletes["INACTIVE"] = df_athletes["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
             df_athletes = df_athletes[(df_athletes["ROLE"] == "1 - Fighter") & (df_athletes["INACTIVE"] == False)]
        
        attendance_ws = spreadsheet.worksheet(ATTENDANCE_TAB_NAME).get_all_records()
        df_attendance = pd.DataFrame(attendance_ws)

        return df_athletes, df_attendance
    except Exception as e:
        st.error(f"Erro ao carregar dados para o resumo: {e}", icon="🚨")
        return None, None

# --- Layout da Página Principal ---

st.sidebar.success("Selecione uma ferramenta acima.")

st.title("🏠 Bem-vindo ao App de Gerenciamento UAEW")
st.markdown("---")

st.header("Visão Geral")

df_athletes, df_attendance = load_summary_data(MAIN_SHEET_NAME)

if df_athletes is not None and df_attendance is not None:
    total_athletes = len(df_athletes) if not df_athletes.empty else 0
    total_registros = len(df_attendance) if not df_attendance.empty else 0
    
    last_activity_time = "Nenhuma"
    # CORREÇÃO: Adicionada a verificação se a coluna 'Timestamp' existe ANTES de usá-la.
    if not df_attendance.empty and "Timestamp" in df_attendance.columns:
        df_attendance["Timestamp_dt"] = pd.to_datetime(df_attendance["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        if not df_attendance["Timestamp_dt"].isna().all():
            last_activity_time = df_attendance["Timestamp_dt"].max().strftime("%d/%m/%Y %H:%M")

    col1, col2, col3 = st.columns(3)
    col1.metric(label="👥 Total de Atletas Ativos", value=total_athletes)
    col2.metric(label="✍️ Total de Registros", value=total_registros)
    col3.metric(label="⏱️ Última Atividade", value=last_activity_time)
    
    st.markdown("---")

    st.subheader("Atividades por Tarefa")
    if not df_attendance.empty and "Task" in df_attendance.columns:
        task_counts = df_attendance["Task"].value_counts()
        st.bar_chart(task_counts)
    else:
        st.info("Ainda não há registros de atividades para exibir um gráfico.")
else:
    st.warning("Não foi possível carregar os dados para o dashboard.")

st.markdown("---")
st.header("Como Usar")
st.markdown("""
- **Use a barra lateral à esquerda** para navegar entre as diferentes ferramentas.
- **Controle de Tarefas:** Nesta página, você pode consultar atletas e registrar o status de tarefas.
- **Dashboard:** A página inicial oferece uma visão geral e rápida das operações.
""")
