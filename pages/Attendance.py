# pages/Attendance.py

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Attendance Control")

# --- Constantes Globais ---
MAIN_SHEET_NAME = "UAEW_App"
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID"
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"
ATTENDANCE_ORDER_COL = "Check-in Order"

FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_ATHLETE_ID_COL = "AthleteID"
FC_PICTURE_COL = "Picture"

# --- Funções de Conexão e Carregamento de Dados ---

@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("CRITICAL: `gcp_service_account` not in secrets.", icon="🚨")
            st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"CRITICAL: Gspread client error: {e}", icon="🚨")
        st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client:
        st.error("CRITICAL: Gspread client not initialized.", icon="🚨")
        st.stop()
    try:
        return gspread_client.open(sheet_name).worksheet(tab_name)
    except Exception as e:
        st.error(f"CRITICAL: Error connecting to {sheet_name}/{tab_name}: {e}", icon="🚨")
        st.stop()

@st.cache_data
def load_fightcard_data():
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=[FC_FIGHTER_COL, FC_ATHLETE_ID_COL])
        df[FC_ATHLETE_ID_COL] = df[FC_ATHLETE_ID_COL].astype(str).str.strip()
        df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip()
        return df.drop_duplicates(subset=[FC_ATHLETE_ID_COL])
    except Exception as e:
        st.error(f"Error loading Fightcard: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        for col in [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_ORDER_COL]:
            if col not in df_att.columns:
                df_att[col] = None
        df_att[ATTENDANCE_ATHLETE_ID_COL] = df_att[ATTENDANCE_ATHLETE_ID_COL].astype(str)
        df_att[ATTENDANCE_ORDER_COL] = pd.to_numeric(df_att[ATTENDANCE_ORDER_COL], errors='coerce')
        return df_att
    except Exception as e:
        st.error(f"Error loading Attendance: {e}")
        return pd.DataFrame()

# --- NOVA FUNÇÃO PARA CARREGAR DADOS DA ABA "Config" ---
@st.cache_data(ttl=600)
def load_config_data(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    """Carrega a lista de tarefas (TaskList) e a lista de eventos (TaskAttendance) da aba Config."""
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    task_list = []
    event_list = []
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1:
            st.warning(f"A aba '{config_tab}' na planilha está vazia.")
            return task_list, event_list

        headers = data[0]
        df_conf = pd.DataFrame(data[1:], columns=headers)

        # Carrega a lista de tarefas
        if "TaskList" in df_conf.columns:
            task_series = df_conf["TaskList"]
            if isinstance(task_series, pd.DataFrame):
                task_series = task_series.iloc[:, 0]
            task_list = task_series.dropna().astype(str).str.strip().unique().tolist()
        else:
            st.error(f"Erro: Coluna 'TaskList' não encontrada na aba '{config_tab}'.")

        # Carrega a lista de eventos para attendance
        if "TaskAttendance" in df_conf.columns:
            event_series = df_conf["TaskAttendance"]
            if isinstance(event_series, pd.DataFrame):
                event_series = event_series.iloc[:, 0]
            event_list = event_series.dropna().astype(str).str.strip().unique().tolist()
        else:
            st.error(f"Erro: Coluna 'TaskAttendance' não encontrada na aba '{config_tab}'.")
        
        return task_list, event_list

    except Exception as e:
        st.error(f"Erro ao carregar dados da aba Config: {e}")
        return task_list, event_list

# --- Funções de Lógica e Interação ---

def record_attendance(athlete_id: str, task_name: str, status: str):
    """Grava um novo registro na planilha de Attendance."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        order_number = ''
        if status == "Checked-in":
            all_attendance = pd.DataFrame(worksheet.get_all_records())
            if not all_attendance.empty:
                task_attendance = all_attendance[all_attendance[ATTENDANCE_TASK_COL] == task_name]
                if not task_attendance.empty and ATTENDANCE_ORDER_COL in task_attendance.columns:
                    max_order = pd.to_numeric(task_attendance[ATTENDANCE_ORDER_COL], errors='coerce').max()
                    order_number = int(max_order + 1) if pd.notna(max_order) else 1
                else: order_number = 1
            else: order_number = 1

        new_row = [timestamp, str(athlete_id), task_name, status, str(order_number)]
        worksheet.append_row(new_row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Failed to record attendance for {athlete_id}: {e}")
        return False

def get_athlete_task_status(athlete_id: str, task_name: str, df_attendance: pd.DataFrame):
    """Obtém o status mais recente de um atleta para uma tarefa específica."""
    if df_attendance.empty: return {"status": "Pending", "order": None}

    athlete_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).strip() == str(athlete_id).strip()) &
        (df_attendance[ATTENDANCE_TASK_COL] == task_name)
    ]

    if athlete_records.empty: return {"status": "Pending", "order": None}
    
    athlete_records = athlete_records.copy()
    if ATTENDANCE_TIMESTAMP_COL in athlete_records.columns:
        athlete_records[ATTENDANCE_TIMESTAMP_COL] = pd.to_datetime(athlete_records[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        latest_record = athlete_records.sort_values(by=ATTENDANCE_TIMESTAMP_COL, ascending=False).iloc[0]
    else: latest_record = athlete_records.iloc[-1]

    status = latest_record[ATTENDANCE_STATUS_COL]
    order = latest_record.get(ATTENDANCE_ORDER_COL)
    
    if status == "Done":
        checked_in_record = athlete_records[athlete_records[ATTENDANCE_STATUS_COL] == "Checked-in"]
        if not checked_in_record.empty:
            order = checked_in_record.sort_values(by=ATTENDANCE_TIMESTAMP_COL, ascending=False).iloc[0].get(ATTENDANCE_ORDER_COL)
    
    return {"status": status, "order": int(order) if pd.notna(order) else None}


# --- APLICAÇÃO PRINCIPAL ---
st.title("✔️ Attendance Control")
st.markdown("Select a task and event to manage athlete check-ins and check-outs.")

with st.spinner("Loading initial data..."):
    task_list, event_list_from_config = load_config_data()
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    
if df_fc.empty or not task_list or not event_list_from_config:
    st.error("Could not load Fight Card or required lists from Config sheet. Please check the spreadsheet configuration.")
    st.stop()

# --- Filtros de Seleção ---
col1, col2 = st.columns(2)
with col1:
    selected_task = st.selectbox("Select a Task to manage:", options=task_list, index=None, placeholder="Choose a task...")
with col2:
    # A lista de eventos agora vem da coluna "TaskAttendance" da aba Config
    event_options = ["All Events"] + sorted(event_list_from_config, reverse=True)
    selected_event = st.selectbox("Filter by Event:", options=event_options)

if not selected_task:
    st.info("Please select a task from the dropdown to begin.")
    st.stop()

# Filtrar atletas pelo evento selecionado
if selected_event != "All Events":
    athletes_to_display = df_fc[df_fc[FC_EVENT_COL] == selected_event].copy()
else:
    # Se "All Events" for selecionado, mostre atletas de todos os eventos listados em TaskAttendance
    athletes_to_display = df_fc[df_fc[FC_EVENT_COL].isin(event_list_from_config)].copy()

if athletes_to_display.empty:
    st.warning(f"No athletes found for the event '{selected_event}'.")
    st.stop()

# --- Exibição e Interação ---
st.markdown("---")
st.header(f"Athletes for '{selected_task}' at '{selected_event}'")

status_list = []
for _, athlete in athletes_to_display.iterrows():
    status_info = get_athlete_task_status(athlete[FC_ATHLETE_ID_COL], selected_task, df_att)
    status_list.append({
        'athlete_id': athlete[FC_ATHLETE_ID_COL],
        'status': status_info['status'],
        'order': status_info['order'] if status_info['order'] is not None else float('inf')
    })

if status_list:
    df_status = pd.DataFrame(status_list)
    athletes_to_display = athletes_to_display.merge(df_status, left_on=FC_ATHLETE_ID_COL, right_on='athlete_id')

    status_order = {'Checked-in': 0, 'Pending': 1, 'Done': 2}
    athletes_to_display['status_order'] = athletes_to_display['status'].map(status_order)
    athletes_to_display = athletes_to_display.sort_values(by=['status_order', 'order'])

for _, athlete in athletes_to_display.iterrows():
    athlete_id = athlete[FC_ATHLETE_ID_COL]
    status_info = {"status": athlete['status'], "order": athlete['order'] if athlete['order'] != float('inf') else None}
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1, 4, 2, 2])
        
        with c1:
            st.image(athlete.get(FC_PICTURE_COL, "https://via.placeholder.com/100"), width=80)

        with c2:
            st.subheader(athlete[FC_FIGHTER_COL])
            status = status_info['status']
            order = status_info['order']

            if status == "Done":
                st.markdown(f"Status: **<span style='color: #28a745;'>✅ Completed</span>** (Order: #{order})", unsafe_allow_html=True)
            elif status == "Checked-in":
                st.markdown(f"Status: **<span style='color: #ffc107;'>⏳ Waiting...</span>**", unsafe_allow_html=True)
                st.metric(label="Check-in Order", value=f"#{order}")
            else: # Pending
                st.markdown(f"Status: **<span style='color: #dc3545;'>⌛ Pending Check-in</span>**", unsafe_allow_html=True)

        with c3:
            if st.button("Check-in", key=f"in_{athlete_id}", use_container_width=True, disabled=(status != "Pending")):
                with st.spinner("Checking in..."):
                    if record_attendance(athlete_id, selected_task, "Checked-in"):
                        st.toast(f"{athlete[FC_FIGHTER_COL]} checked in!", icon="✅")
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()

        with c4:
            if st.button("Check-out", key=f"out_{athlete_id}", type="primary", use_container_width=True, disabled=(status != "Checked-in")):
                with st.spinner("Checking out..."):
                    if record_attendance(athlete_id, selected_task, "Done"):
                        st.toast(f"Task completed for {athlete[FC_FIGHTER_COL]}!", icon="🎉")
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()
