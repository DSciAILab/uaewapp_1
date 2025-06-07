# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Desktop Task Manager", layout="wide")

# --- Constants (alguns traduzidos para clareza no código) ---
MAIN_SHEET_NAME = "UAEW_App" 
ATHLETES_TAB_NAME = "df" 
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance" 
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"
CONFIG_TAB_NAME = "Config"
NO_TASK_SELECTED = "-- Select a Task --"
STATUS_PENDING = ["Pending", "---", "Not Registered"] 

# --- 2. Google Sheets Connection & Data Loading (sem grandes alterações na lógica) ---
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
        df_athletes = pd.DataFrame(athletes_ws.get_all_records())
        df_athletes = df_athletes[(df_athletes['ROLE'] == '1 - Fighter') & (df_athletes['INACTIVE'].astype(str).str.upper() != 'TRUE')]
        df_athletes = df_athletes[['ID', 'NAME', 'EVENT']].copy()
        df_athletes.columns = df_athletes.columns.str.strip()

        # Registros de Presença
        attendance_ws = connect_gsheet_tab(client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        df_attendance = pd.DataFrame(attendance_ws.get_all_records())

        # Configurações (Tarefas)
        config_ws = connect_gsheet_tab(client, MAIN_SHEET_NAME, CONFIG_TAB_NAME)
        tasks = [row['TaskList'] for row in config_ws.get_all_records() if 'TaskList' in row and row['TaskList']]
        
        return df_athletes, df_attendance, tasks
    except Exception as e:
        st.error(f"Failed to load initial data: {e}", icon="🚨")
        return pd.DataFrame(), pd.DataFrame(), []

def get_latest_statuses(df_athletes, df_attendance, task):
    """Cria um DataFrame com o status mais recente de uma tarefa para cada atleta."""
    if task == NO_TASK_SELECTED or df_attendance.empty:
        df_athletes['Status'] = 'N/A'
        return df_athletes[['ID', 'NAME', 'EVENT', 'Status']]

    # Filtra registros apenas para a tarefa selecionada
    task_records = df_attendance[df_attendance['Task'] == task].copy()
    if not task_records.empty:
        task_records['Timestamp'] = pd.to_datetime(task_records['Timestamp'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        # Pega o último registro para cada atleta
        latest_status_df = task_records.sort_values('Timestamp').groupby(ID_COLUMN_IN_ATTENDANCE).last().reset_index()
        # Junta com a lista de atletas
        merged_df = pd.merge(df_athletes, latest_status_df[[ID_COLUMN_IN_ATTENDANCE, 'Status']], left_on='ID', right_on=ID_COLUMN_IN_ATTENDANCE, how='left')
        merged_df['Status'] = merged_df['Status'].fillna('Pending')
        return merged_df[['ID', 'NAME', 'EVENT', 'Status']]
    else:
        df_athletes['Status'] = 'Pending'
        return df_athletes[['ID', 'NAME', 'EVENT', 'Status']]

def batch_register_log(athletes_to_update, task, new_status, user_name):
    """Registra uma lista de atletas de uma vez na planilha."""
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
                str(next_num),
                athlete['EVENT'],
                athlete['ID'],
                athlete['NAME'],
                task,
                new_status,
                user_name,
                ts,
                "Batch Update"
            ]
            rows_to_append.append(new_row)
        
        if rows_to_append:
            log_ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
            st.success(f"{len(rows_to_append)} athletes updated for task '{task}' to status '{new_status}'.")
            load_data.clear() # Limpa o cache principal
    except Exception as e:
        st.error(f"Failed to batch update: {e}", icon="🚨")

# --- Lógica de Autenticação (simplificada para focar na UI) ---
# Em um app real, use a sua lógica de autenticação completa.
st.session_state.user_confirmed = True
st.session_state.current_user_name = "Desktop User"
# --- Fim da Autenticação ---

if 'selected_athletes' not in st.session_state:
    st.session_state.selected_athletes = []

if st.session_state.user_confirmed:
    st.title("🚀 Desktop Task Manager")

    # Carrega todos os dados
    df_athletes, df_attendance, tasks = load_data()

    if df_athletes.empty:
        st.warning("No active athletes found.")
        st.stop()

    # --- Controles e Filtros ---
    st.header("Controls & Filters")
    controls_cols = st.columns([0.4, 0.4, 0.2])
    with controls_cols[0]:
        selected_task = st.selectbox("1. Select Task to Manage", [NO_TASK_SELECTED] + tasks, key="task_selector")
    with controls_cols[1]:
        search_query = st.text_input("2. Filter Athletes by Name or ID", placeholder="Type to search...")
    with controls_cols[2]:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Data", use_container_width=True):
            load_data.clear()
            st.rerun()

    # Obtém a tabela de status com base na tarefa selecionada
    df_status = get_latest_statuses(df_athletes, df_attendance, selected_task)
    
    # Aplica o filtro de busca
    if search_query:
        query = search_query.lower()
        df_status = df_status[
            df_status['NAME'].str.lower().str.contains(query) |
            df_status['ID'].astype(str).str.contains(query)
        ]
    
    # Adiciona a coluna de seleção
    df_status['Select'] = False
    
    st.markdown("---")
    
    # --- Ações em Lote ---
    st.header("Batch Actions")
    if selected_task == NO_TASK_SELECTED:
        st.info("Select a task above to enable batch actions.")
    else:
        action_cols = st.columns(3)
        with action_cols[0]:
            if st.button(f"➡️ Mark Selected as 'Requested'", use_container_width=True, type="primary"):
                selected_rows = df_status.loc[st.session_state.selected_athletes]
                batch_register_log(selected_rows, selected_task, "Requested", st.session_state.current_user_name)
                time.sleep(1) # Dá tempo para a API processar antes de recarregar
                st.rerun()
        with action_cols[1]:
            if st.button(f"✅ Mark Selected as 'Done'", use_container_width=True):
                selected_rows = df_status.loc[st.session_state.selected_athletes]
                batch_register_log(selected_rows, selected_task, "Done", st.session_state.current_user_name)
                time.sleep(1)
                st.rerun()
        with action_cols[2]:
            if st.button(f"❌ Mark Selected as '---'", use_container_width=True):
                selected_rows = df_status.loc[st.session_state.selected_athletes]
                batch_register_log(selected_rows, selected_task, "---", st.session_state.current_user_name)
                time.sleep(1)
                st.rerun()

    st.markdown("---")

    # --- Tabela Interativa de Atletas ---
    st.header("Athlete List")
    
    edited_df = st.data_editor(
        df_status,
        column_config={
            "Select": st.column_config.CheckboxColumn(required=True),
            "ID": st.column_config.TextColumn(disabled=True),
            "NAME": st.column_config.TextColumn("Name", disabled=True),
            "EVENT": st.column_config.TextColumn("Event", disabled=True),
            "Status": st.column_config.TextColumn(disabled=True),
        },
        use_container_width=True,
        hide_index=True,
        height=500, # Altura fixa para melhor visualização em desktop
        key="athlete_editor"
    )

    # Lógica para armazenar os atletas selecionados
    st.session_state.selected_athletes = edited_df[edited_df['Select']].index.tolist()

    if st.session_state.selected_athletes:
        st.info(f"{len(st.session_state.selected_athletes)} athletes selected.")
    else:
        st.info("No athletes selected. Check the boxes in the first column to perform batch actions.")

else:
    st.warning("Please log in to access the Task Manager.")
