# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Desktop Task Manager", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App" 
ATHLETES_TAB_NAME = "df" 
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance" 
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"
CONFIG_TAB_NAME = "Config"
NO_TASK_SELECTED = "-- Select a Task --"

# --- 2. Google Sheets Connection & Data Loading ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Google API Error: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except Exception as e:
        st.error(f"Error connecting to tab '{tab_name}': {e}", icon="🚨"); st.stop()

@st.cache_data(ttl=300)
def load_data():
    try:
        client = get_gspread_client()
        
        # Atletas
        athletes_ws = connect_gsheet_tab(client, MAIN_SHEET_NAME, ATHLETES_TAB_NAME)
        athletes_values = athletes_ws.get_all_values()
        if len(athletes_values) < 2: return pd.DataFrame(), pd.DataFrame(), [], []
        
        df_athletes = pd.DataFrame(athletes_values[1:], columns=athletes_values[0])
        df_athletes = df_athletes.loc[:, ~df_athletes.columns.duplicated()]
        df_athletes = df_athletes[(df_athletes['ROLE'] == '1 - Fighter') & (df_athletes['INACTIVE'].astype(str).str.upper() != 'TRUE')]
        df_athletes = df_athletes[['ID', 'NAME', 'EVENT']].copy()
        df_athletes.columns = df_athletes.columns.str.strip()
        unique_events = sorted(df_athletes['EVENT'].dropna().unique().tolist())

        # Registros de Presença
        attendance_ws = connect_gsheet_tab(client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        attendance_values = attendance_ws.get_all_values()
        df_attendance = pd.DataFrame(attendance_values[1:], columns=attendance_values[0]) if len(attendance_values) > 1 else pd.DataFrame()

        # Configurações
        config_ws = connect_gsheet_tab(client, MAIN_SHEET_NAME, CONFIG_TAB_NAME)
        config_values = config_ws.get_all_values()
        if len(config_values) < 2:
            tasks = []
        else:
            df_config = pd.DataFrame(config_values[1:], columns=config_values[0])
            tasks = df_config['TaskList'].dropna().tolist() if 'TaskList' in df_config.columns else []
        
        return df_athletes, df_attendance, tasks, unique_events
    except Exception as e:
        st.error(f"Failed to load initial data: {e}", icon="🚨")
        return pd.DataFrame(), pd.DataFrame(), [], []

def get_latest_statuses(df_athletes, df_attendance, task):
    if task == NO_TASK_SELECTED or df_attendance.empty:
        df_athletes['Status'] = 'N/A'
        return df_athletes[['ID', 'NAME', 'EVENT', 'Status']]

    if 'Task' not in df_attendance.columns:
        st.error(f"Error: 'Task' column not found in '{ATTENDANCE_TAB_NAME}' sheet.")
        df_athletes['Status'] = 'Error'
        return df_athletes[['ID', 'NAME', 'EVENT', 'Status']]

    task_records = df_attendance[df_attendance['Task'] == task].copy()
    
    if not task_records.empty:
        if ATTENDANCE_TIMESTAMP_COL in task_records.columns:
            task_records[ATTENDANCE_TIMESTAMP_COL] = pd.to_datetime(task_records[ATTENDANCE_TIMESTAMP_COL], format='%d/%m/%Y %H:%M:%S', errors='coerce')
            latest_status_df = task_records.sort_values(ATTENDANCE_TIMESTAMP_COL).groupby(ID_COLUMN_IN_ATTENDANCE).last().reset_index()
        else:
            st.warning(f"Warning: Timestamp column '{ATTENDANCE_TIMESTAMP_COL}' not found. Using last entry as the latest.", icon="⚠️")
            latest_status_df = task_records.groupby(ID_COLUMN_IN_ATTENDANCE).last().reset_index()

        merged_df = pd.merge(df_athletes, latest_status_df[[ID_COLUMN_IN_ATTENDANCE, 'Status']], left_on='ID', right_on=ID_COLUMN_IN_ATTENDANCE, how='left')
        merged_df['Status'] = merged_df['Status'].fillna('Pending')
        return merged_df[['ID', 'NAME', 'EVENT', 'Status']]
    else:
        df_athletes['Status'] = 'Pending'
        return df_athletes[['ID', 'NAME', 'EVENT', 'Status']]

def batch_register_log(athletes_to_update, task, new_status, user_name):
    if not athletes_to_update or task == NO_TASK_SELECTED:
        return
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        
        all_vals = log_ws.get_all_values()
        next_num = len(all_vals)
        
        rows_to_append = []
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        for _, athlete in athletes_to_update.iterrows():
            next_num += 1
            new_row = [
                str(next_num), athlete['EVENT'], athlete['ID'],
                athlete['NAME'], task, new_status, user_name, ts, "Batch Update"
            ]
            rows_to_append.append(new_row)
        
        if rows_to_append:
            log_ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
            st.success(f"{len(rows_to_append)} athletes updated for task '{task}' to status '{new_status}'.")
            load_data.clear()
    except Exception as e:
        st.error(f"Failed to batch update: {e}", icon="🚨")

# --- Lógica de Autenticação ---
st.session_state.user_confirmed = True
st.session_state.current_user_name = "Desktop User"

if 'selected_athletes' not in st.session_state:
    st.session_state.selected_athletes = []

if st.session_state.user_confirmed:
    st.title("🚀 Desktop Task Manager")
    df_athletes, df_attendance, tasks, unique_events = load_data()

    if df_athletes.empty:
        st.warning("No active athletes found. Check your 'df' sheet and filters."); st.stop()

    # --- ATUALIZAÇÃO: Nova seção de filtros com Multiselect ---
    st.header("Controls & Filters")
    filter_cols = st.columns(2)
    with filter_cols[0]:
        selected_task = st.selectbox("1. Select Task to Manage", [NO_TASK_SELECTED] + tasks, key="task_selector")
    with filter_cols[1]:
        selected_events = st.multiselect("2. Filter by Event(s)", options=unique_events, placeholder="All Events")

    search_query = st.text_input("3. Filter by Athlete Name or ID", placeholder="Type to search...")
    
    # --- Lógica de Filtragem ---
    # Começa com a lista completa de atletas e seus status para a tarefa selecionada
    df_display = get_latest_statuses(df_athletes, df_attendance, selected_task)
    
    # 1. Filtra por eventos selecionados
    if selected_events:
        df_display = df_display[df_display['EVENT'].isin(selected_events)]
    
    # 2. Filtra pela busca de texto
    if search_query:
        query = search_query.lower()
        df_display = df_display[
            df_display['NAME'].str.lower().str.contains(query) |
            df_display['ID'].astype(str).str.contains(query)
        ]
    
    df_display['Select'] = False
    
    st.markdown("---")
    
    # --- Ações em Lote ---
    st.header("Batch Actions")
    if selected_task == NO_TASK_SELECTED:
        st.info("Select a task above to enable batch actions.")
    else:
        # (Lógica de botões de ação inalterada)
        action_cols = st.columns(3)
        with action_cols[0]:
            if st.button(f"➡️ Mark Selected as 'Requested'", use_container_width=True, type="primary"):
                if st.session_state.selected_athletes:
                    selected_rows = df_display.loc[st.session_state.selected_athletes]
                    batch_register_log(selected_rows, selected_task, "Requested", st.session_state.current_user_name)
                    time.sleep(1); st.rerun()
                else: st.warning("No athletes selected.")
        with action_cols[1]:
            if st.button(f"✅ Mark Selected as 'Done'", use_container_width=True):
                if st.session_state.selected_athletes:
                    selected_rows = df_display.loc[st.session_state.selected_athletes]
                    batch_register_log(selected_rows, selected_task, "Done", st.session_state.current_user_name)
                    time.sleep(1); st.rerun()
                else: st.warning("No athletes selected.")
        with action_cols[2]:
            if st.button(f"❌ Mark Selected as '---'", use_container_width=True):
                if st.session_state.selected_athletes:
                    selected_rows = df_display.loc[st.session_state.selected_athletes]
                    batch_register_log(selected_rows, selected_task, "---", st.session_state.current_user_name)
                    time.sleep(1); st.rerun()
                else: st.warning("No athletes selected.")

    st.markdown("---")

    # --- Tabela Interativa de Atletas ---
    st.header("Athlete List")
    
    edited_df = st.data_editor(
        df_display,
        column_config={
            "Select": st.column_config.CheckboxColumn(required=True),
            "ID": st.column_config.TextColumn(disabled=True),
            "NAME": st.column_config.TextColumn("Name", disabled=True),
            "EVENT": st.column_config.TextColumn("Event", disabled=True),
            "Status": st.column_config.TextColumn(disabled=True),
        },
        use_container_width=True, hide_index=True, height=500, key="athlete_editor"
    )

    # Armazena os índices das linhas selecionadas
    st.session_state.selected_athletes = edited_df[edited_df['Select']].index.tolist()

    if st.session_state.selected_athletes:
        st.info(f"{len(st.session_state.selected_athletes)} athletes selected.")
    else:
        st.info("No athletes selected. Check the boxes in the first column to perform batch actions.")

else:
    st.warning("Please log in to access the Task Manager.")
