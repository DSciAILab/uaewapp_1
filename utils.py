import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html

# --- Constantes Globais ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

ID_COLUMN_IN_ATTENDANCE = "Athlete ID"
ATTENDANCE_EVENT_COL = "Event"
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"

# --- Conexão com Google Sheets ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("CRITICAL: `gcp_service_account` not in secrets.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"CRITICAL: Gspread client error: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client:
        st.error("CRITICAL: Gspread client not initialized.", icon="🚨"); st.stop()
    try:
        return gspread_client.open(sheet_name).worksheet(tab_name)
    except Exception as e:
        st.error(f"CRITICAL: Error connecting to {sheet_name}/{tab_name}: {e}", icon="🚨"); st.stop()

# --- Carregamento de Dados ---
@st.cache_data(ttl=600)
def load_athlete_data():
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATHLETES_TAB_NAME)
        df = pd.DataFrame(worksheet.get_all_records())
        if df.empty: return pd.DataFrame()
        # ... (Sua lógica de limpeza e formatação do df de atletas)
        df.columns = df.columns.str.strip()
        df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar atletas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data():
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        df_att = pd.DataFrame(worksheet.get_all_records())
        # Garante que as colunas essenciais existam
        for col in [ID_COLUMN_IN_ATTENDANCE, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_EVENT_COL, ATTENDANCE_TIMESTAMP_COL]:
            if col not in df_att.columns:
                df_att[col] = pd.NA
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar presença: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=600)
def load_config_data():
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, CONFIG_TAB_NAME)
        df_conf = pd.DataFrame(worksheet.get_all_records())
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        statuses = df_conf["TaskStatus"].dropna().astype(str).str.strip().unique().tolist() if "TaskStatus" in df_conf.columns else []
        return tasks, statuses
    except Exception as e:
        st.error(f"Erro ao carregar config: {e}", icon="🚨"); return [], []

# --- Funções de Usuário e Autenticação ---
@st.cache_data(ttl=300)
def load_users_data():
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, USERS_TAB_NAME)
        return worksheet.get_all_records() or []
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}", icon="🚨"); return []

def get_valid_user_info(user_input: str):
    if not user_input: return None
    all_users = load_users_data()
    if not all_users: return None
    proc_input = user_input.strip().upper()
    val_id_input = proc_input[2:] if proc_input.startswith("PS") and len(proc_input) > 2 and proc_input[2:].isdigit() else proc_input
    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip()
        name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == val_id_input or ("PS" + ps_sheet) == proc_input or name_sheet == proc_input or ps_sheet == proc_input:
            return record
    return None

# --- Funções de Lógica de Negócio ---
def registrar_log(ath_id, ath_name, ath_event, task, status, notes, user_log_id):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        next_num = len(log_ws.get_all_values()) + 1
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        # Limpa caches para forçar recarregamento na próxima interação
        load_attendance_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar log: {e}", icon="🚨"); return False

def get_latest_status(athlete_id, event_name, task, attendance_df):
    """
    Busca o status mais recente para um atleta, evento e tarefa específicos.
    Retorna um dicionário com status, usuário e timestamp.
    """
    default_return = {"status": "Pending", "user": "N/A", "timestamp": "N/A"}
    if attendance_df.empty or pd.isna(athlete_id) or not event_name or not task:
        return default_return

    # Filtro corrigido e centralizado
    records = attendance_df[
        (attendance_df[ID_COLUMN_IN_ATTENDANCE].astype(str) == str(athlete_id)) &
        (attendance_df[ATTENDANCE_EVENT_COL].astype(str) == str(event_name)) &
        (attendance_df[ATTENDANCE_TASK_COL].astype(str) == str(task))
    ].copy()

    if records.empty:
        return default_return

    records['TS_dt'] = pd.to_datetime(records[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
    latest = records.sort_values(by="TS_dt", ascending=False).iloc[0]

    return {
        "status": latest.get(ATTENDANCE_STATUS_COL, "Pending"),
        "user": latest.get("User", "N/A"),
        "timestamp": latest.get(ATTENDANCE_TIMESTAMP_COL, "N/A")
    }

# --- Componentes de UI ---
def display_user_sidebar():
    """Cria a sidebar padrão de usuário e logout."""
    st.sidebar.title("UAEW App")
    st.sidebar.markdown(f"Bem-vindo, **{st.session_state.get('current_user_name', 'Usuário')}**!")

    if st.sidebar.button("Logout", key="global_logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            # Limpa o estado da sessão para um logout completo
            del st.session_state[key]
        st.switch_page("1_Login.py")

    st.sidebar.markdown("---")
