import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Constantes Globais ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

ID_COLUMN = "ID"
EVENT_COLUMN = "EVENT"
TASK_COLUMN = "Task"
STATUS_COLUMN = "Status"
TIMESTAMP_COLUMN = "Timestamp"

# --- Conexão com Google Sheets ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"CRITICAL: Gspread client error: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(sheet_name: str, tab_name: str):
    client = get_gspread_client()
    try:
        return client.open(sheet_name).worksheet(tab_name)
    except Exception as e:
        st.error(f"CRITICAL: Error connecting to {sheet_name}/{tab_name}: {e}", icon="🚨"); st.stop()

# --- Funções de Carregamento de Dados ---
@st.cache_data(ttl=600)
def load_athlete_data():
    worksheet = connect_gsheet_tab(MAIN_SHEET_NAME, ATHLETES_TAB_NAME)
    df = pd.DataFrame(worksheet.get_all_records())
    if df.empty: return pd.DataFrame()
    df.columns = df.columns.str.strip()
    df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
    df = df[(df.get("ROLE") == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
    df[EVENT_COLUMN] = df[EVENT_COLUMN].fillna("Z")
    return df.sort_values(by=[EVENT_COLUMN, "NAME"]).reset_index(drop=True)

@st.cache_data(ttl=120)
def load_attendance_data():
    worksheet = connect_gsheet_tab(MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
    df = pd.DataFrame(worksheet.get_all_records())
    # Garante que as colunas essenciais existam
    for col in ["Athlete ID", TASK_COLUMN, STATUS_COLUMN, EVENT_COLUMN, TIMESTAMP_COLUMN]:
        if col not in df.columns: df[col] = pd.NA
    df["Athlete ID"] = df["Athlete ID"].astype(str) # Garante consistência
    return df

@st.cache_data(ttl=600)
def load_config_data():
    worksheet = connect_gsheet_tab(MAIN_SHEET_NAME, CONFIG_TAB_NAME)
    df = pd.DataFrame(worksheet.get_all_records())
    tasks = df["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df.columns else []
    statuses = df["TaskStatus"].dropna().astype(str).str.strip().unique().tolist() if "TaskStatus" in df.columns else []
    return tasks, statuses

@st.cache_data(ttl=300)
def load_users_data():
    worksheet = connect_gsheet_tab(MAIN_SHEET_NAME, USERS_TAB_NAME)
    return worksheet.get_all_records() or []

def get_valid_user_info(user_input: str):
    if not user_input: return None
    all_users = load_users_data()
    proc_input = user_input.strip().upper()
    for record in all_users:
        ps = str(record.get("PS", "")).strip()
        name = str(record.get("USER", "")).strip().upper()
        if proc_input in [ps, name, f"PS{ps}"]:
            return record
    return None

# --- Funções de Lógica e UI ---
def registrar_log(ath_id, ath_name, ath_event, task, status, notes=""):
    try:
        log_ws = connect_gsheet_tab(MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', 'System')
        next_num = len(log_ws.get_all_values()) + 1
        new_row = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row, value_input_option="USER_ENTERED")
        st.success(f"'{task}' for {ath_name} registered as '{status}'.", icon="✍️")
        load_attendance_data.clear() # Força o recarregamento na próxima interação
        return True
    except Exception as e:
        st.error(f"Erro ao registrar log: {e}", icon="🚨"); return False

def get_latest_status(athlete_id, event_name, task_name, attendance_df):
    default = {"status": "Pending", "user": "N/A", "timestamp": "N/A"}
    if attendance_df.empty or pd.isna(athlete_id) or not event_name or not task_name:
        return default

    records = attendance_df[
        (attendance_df["Athlete ID"] == str(athlete_id)) &
        (attendance_df[EVENT_COLUMN] == str(event_name)) &
        (attendance_df[TASK_COLUMN] == str(task_name))
    ].copy()

    if records.empty: return default

    records['TS_dt'] = pd.to_datetime(records[TIMESTAMP_COLUMN], format="%d/%m/%Y %H:%M:%S", errors='coerce')
    latest = records.sort_values(by="TS_dt", ascending=False).iloc[0]

    return {
        "status": latest.get(STATUS_COLUMN, "Pending"),
        "user": latest.get("User", "N/A"),
        "timestamp": latest.get(TIMESTAMP_COLUMN, "N/A")
    }

def display_user_sidebar():
    st.sidebar.title("UAEW App")
    st.sidebar.markdown(f"Bem-vindo, **{st.session_state.get('current_user_name', 'Usuário')}**!")
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.switch_page("1_Login.py")
    st.sidebar.markdown("---")
