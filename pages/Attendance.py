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

# --- Funções de Conexão e Carregamento de Dados (sem alterações) ---

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
    if not gspread_client: st.error("CRITICAL: Gspread client not initialized.", icon="🚨"); st.stop()
    try: return gspread_client.open(sheet_name).worksheet(tab_name)
    except Exception as e: st.error(f"CRITICAL: Error connecting to {sheet_name}/{tab_name}: {e}", icon="🚨"); st.stop()

@st.cache_data
def load_fightcard_data():
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=[FC_FIGHTER_COL, FC_ATHLETE_ID_COL])
        df[FC_ATHLETE_ID_COL] = df[FC_ATHLETE_ID_COL].astype(str).str.strip()
        df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip()
        return df.drop_duplicates(subset=[FC_ATHLETE_ID_COL])
    except Exception as e: st.error(f"Error loading Fightcard: {e}"); return pd.DataFrame()

@st.cache_data(ttl=30)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        for col in [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_ORDER_COL]:
            if col not in df_att.columns: df_att[col] = None
        df_att[ATTENDANCE_ATHLETE_ID_COL] = df_att[ATTENDANCE_ATHLETE_ID_COL].astype(str)
        df_att[ATTENDANCE_ORDER_COL] = pd.to_numeric(df_att[ATTENDANCE_ORDER_COL], errors='coerce')
        return df_att
    except Exception as e: st.error(f"Error loading Attendance: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def load_config_df(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1:
            st.warning(f"A aba '{config_tab}' na planilha está vazia.")
            return pd.DataFrame()
        headers = data[0]
        df_conf = pd.DataFrame(data[1:], columns=headers).fillna('')
        return df_conf
    except Exception as e: st.error(f"Erro ao carregar dados da aba Config: {e}"); return pd.DataFrame()

def record_attendance(athlete_id: str, task_name: str, status: str):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        order_number = ''
        if status == "Checked-in":
            all_attendance = pd.DataFrame(worksheet.get_all_records())
            # A ordem de check-in é por tarefa, então filtramos por ela
            task_attendance = all_attendance[all_attendance[ATTENDANCE_TASK_COL] == task_name]
            if not task_attendance.empty and ATTENDANCE_ORDER_COL in task_attendance.columns:
                max_order = pd.to_numeric(task_attendance[ATTENDANCE_ORDER_COL], errors='coerce').max()
                order_number = int(max_order + 1) if pd.notna(max_order) else 1
            else: order_number = 1
        
        new_row = [timestamp, str(athlete_id), task_name, status, str(order_number)]
        worksheet.append_row(new_row, value_input_option='USER_ENTERED')
        return True
    except Exception as e: st.error(f"Failed to record attendance for {athlete_id}: {e}"); return False

def get_athlete_task_status(athlete_id: str, task_name: str, df_attendance: pd.DataFrame):
    if df_attendance.empty: return {"status": "Pending", "order": None}
    athlete_records = df_attendance[(df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == str(athlete_id).strip()) & (df_attendance[ATTENDANCE_TASK_COL] == task_name)]
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
        if not checked_in_record.empty: order = checked_in_record.sort_values(by=ATTENDANCE_TIMESTAMP_COL, ascending=False).iloc[0].get(ATTENDANCE_ORDER_COL)
    return {"status": status, "order": int(order) if pd.notna(order) else None}

# --- APLICAÇÃO PRINCIPAL (LÓGICA ATUALIZADA) ---
st.title("✔️ Athlete Attendance Control")
st.markdown("Select an event to manage all tasks for each athlete.")

with st.spinner("Loading initial data..."):
    df_config = load_config_df()
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    
if df_fc.empty or df_config.empty:
    st.error("Could not load Fight Card or Config sheet. Please check the spreadsheet configuration.")
    st.stop()

# --- SELEÇÃO DO EVENTO ---
st.header("Step 1: Select an Event")
event_list = df_config["TaskAttendance"].str.strip().replace('', pd.NA).dropna().unique().tolist()
event_options = [""] + sorted(event_list)
selected_event = st.selectbox(
    "Select the active Event:", 
    options=event_options,
    format_func=lambda x: "Choose an event..." if x == "" else x
)

# A aplicação continua apenas se um evento for selecionado
if selected_event:
    st.markdown("---")
    st.header(f"Athlete Status for '{selected_event}'")

    # Pega as tarefas relevantes para o evento selecionado
    relevant_tasks_df = df_config[(df_config["TaskAttendance"] == selected_event) | (df_config["TaskAttendance"] == "")]
    tasks_for_event = relevant_tasks_df["TaskList"].str.strip().replace('', pd.NA).dropna().unique().tolist()

    # Pega os atletas relevantes para o evento
    athletes_to_display = df_fc[df_fc[FC_EVENT_COL] == selected_event].copy()

    if athletes_to_display.empty:
        st.warning(f"No athletes found in the Fight Card for the event '{selected_event}'.")
        st.stop()

    if not tasks_for_event:
        st.warning(f"No tasks found in the Config sheet for the event '{selected_event}'.")
        st.stop()
        
    # Exibe um card para cada atleta
    for _, athlete in athletes_to_display.iterrows():
        athlete_id = athlete[FC_ATHLETE_ID_COL]
        
        with st.container(border=True):
            # Seção de informações do atleta
            info_cols = st.columns([1, 5])
            with info_cols[0]:
                st.image(athlete.get(FC_PICTURE_COL, "https://via.placeholder.com/100"), width=80)
            with info_cols[1]:
                st.subheader(athlete[FC_FIGHTER_COL])
                st.caption(f"Athlete ID: {athlete_id}")

            st.markdown("---")

            # Seção de tarefas para o atleta
            st.write("**Tasks Status**")
            # Loop aninhado: para cada atleta, itere sobre todas as tarefas do evento
            for task in tasks_for_event:
                # O key do botão precisa ser único para cada atleta E cada tarefa
                button_key_suffix = f"{athlete_id}_{task}".replace(" ", "_")
                
                status_info = get_athlete_task_status(athlete_id, task, df_att)
                status = status_info['status']

                task_cols = st.columns([3, 2, 1, 1])
                with task_cols[0]:
                    st.write(task)
                with task_cols[1]:
                    if status == "Done": st.markdown("✅ **Completed**")
                    elif status == "Checked-in": st.markdown(f"⏳ **Waiting** (Order: #{status_info['order']})")
                    else: st.markdown("⌛ Pending")
                with task_cols[2]:
                    if st.button("Check-in", key=f"in_{button_key_suffix}", use_container_width=True, disabled=(status != "Pending")):
                        with st.spinner(f"Checking in {athlete[FC_FIGHTER_COL]} for {task}..."):
                            if record_attendance(athlete_id, task, "Checked-in"):
                                st.toast(f"{athlete[FC_FIGHTER_COL]} checked in for {task}!", icon="✅")
                                st.cache_data.clear(); time.sleep(0.5); st.rerun()
                with task_cols[3]:
                    if st.button("Check-out", key=f"out_{button_key_suffix}", use_container_width=True, disabled=(status != "Checked-in")):
                        with st.spinner(f"Checking out {athlete[FC_FIGHTER_COL]} for {task}..."):
                            if record_attendance(athlete_id, task, "Done"):
                                st.toast(f"Task '{task}' completed for {athlete[FC_FIGHTER_COL]}!", icon="🎉")
                                st.cache_data.clear(); time.sleep(0.5); st.rerun()
else:
    st.info("Please select an event to view athlete attendance status.")
