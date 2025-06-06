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
# Reutilizamos algumas constantes para acessar os dados
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
ATTENDANCE_TAB_NAME = "Attendance"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"

# --- Conexão e Carregamento de Dados (versão simplificada para o dashboard) ---
# Usamos cache para não sobrecarregar a API na página principal.
@st.cache_resource(ttl=3600)
def get_gspread_client():
    """Conecta ao Google Sheets."""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de conexão com a API do Google: {e}", icon="🚨")
        return None

@st.cache_data(ttl=600) # Cache de 10 minutos
def load_summary_data(sheet_name):
    """Carrega apenas os dados necessários para o resumo da página inicial."""
    try:
        client = get_gspread_client()
        if client is None:
            return None, None
        spreadsheet = client.open(sheet_name)
        
        # Carrega dados dos atletas para contar o total
        athletes_ws = spreadsheet.worksheet(ATHLETES_TAB_NAME).get_all_records()
        df_athletes = pd.DataFrame(athletes_ws)
        # Filtra para contar apenas atletas ativos
        if "INACTIVE" in df_athletes.columns and "ROLE" in df_athletes.columns:
             df_athletes["INACTIVE"] = df_athletes["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
             df_athletes = df_athletes[(df_athletes["ROLE"] == "1 - Fighter") & (df_athletes["INACTIVE"] == False)]
        
        # Carrega os registros de presença para contar as atividades
        attendance_ws = spreadsheet.worksheet(ATTENDANCE_TAB_NAME).get_all_records()
        df_attendance = pd.DataFrame(attendance_ws)

        return df_athletes, df_attendance
    except gspread.exceptions.APIError as e:
        if e.response.status_code == 429:
            st.warning("Atingido o limite de requisições da API. Os dados do dashboard podem não ser os mais recentes. Tente novamente em um minuto.", icon="⏱️")
            return None, None
        else:
            st.error(f"Erro de API do Google: {e}", icon="🚨")
            return None, None
    except Exception as e:
        st.error(f"Erro ao carregar dados para o resumo: {e}", icon="🚨")
        return None, None


# --- Layout da Página Principal ---

st.sidebar.success("Selecione uma ferramenta acima.")

st.title("🏠 Bem-vindo ao App de Gerenciamento UAEW")
st.markdown("---")

st.header("Visão Geral")

# Carrega os dados para o dashboard
df_athletes, df_attendance = load_summary_data(MAIN_SHEET_NAME)

if df_athletes is not None and df_attendance is not None:
    # --- Métricas do Dashboard ---
    total_athletes = len(df_athletes) if not df_athletes.empty else 0
    total_registros = len(df_attendance) if not df_attendance.empty else 0
    
    # Encontra a última atividade registrada
    last_activity_time = "Nenhuma"
    if not df_attendance.empty and "Timestamp" in df_attendance.columns:
        # Garante que a coluna de timestamp seja do tipo datetime para ordenação
        df_attendance["Timestamp_dt"] = pd.to_datetime(df_attendance["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        last_activity_time = df_attendance["Timestamp_dt"].max().strftime("%d/%m/%Y %H:%M") if not df_attendance["Timestamp_dt"].isna().all() else "Nenhuma"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="👥 Total de Atletas Ativos", value=total_athletes)
    with col2:
        st.metric(label="✍️ Total de Registros", value=total_registros)
    with col3:
        st.metric(label="⏱️ Última Atividade", value=last_activity_time)
    
    st.markdown("---")

    # --- Gráfico Simples de Atividades por Tarefa ---
    st.subheader("Atividades por Tarefa")
    if not df_attendance.empty and "Task" in df_attendance.columns:
        task_counts = df_attendance["Task"].value_counts()
        st.bar_chart(task_counts)
    else:
        st.info("Ainda não há registros de atividades para exibir um gráfico.")

else:
    st.warning("Não foi possível carregar os dados para o dashboard. Verifique a conexão e as permissões da planilha.")


st.markdown("---")
st.header("Como Usar")
st.markdown("""
Esta plataforma foi desenvolvida para centralizar e facilitar o gerenciamento de informações e tarefas relacionadas aos atletas.

- **Use a barra lateral à esquerda** para navegar entre as diferentes ferramentas disponíveis.
- **Registro de Atletas:** Nesta página, você pode consultar a ficha de cada atleta e registrar o status de diferentes tarefas (como 'Check-in', 'Medical', etc.).
- **Dashboard:** A página inicial oferece uma visão geral e rápida do status atual das operações.

Para começar, selecione **'Registro de Atletas'** na barra de navegação ao lado.
""")
