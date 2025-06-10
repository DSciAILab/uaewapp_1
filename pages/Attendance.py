# pages/Attendance.py

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Live Attendance Station")

# --- Constantes Globais ---
MAIN_SHEET_NAME = "UAEW_App"
ATTENDANCE_TAB_NAME = "Attendance"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

ATTENDANCE_ATHLETE_ID_COL = "Athlete ID"
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"
ATTENDANCE_ORDER_COL = "Check-in Order"

FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_ATHLETE_ID_COL = "AthleteID"
FC_PICTURE_COL = "Picture"
FC_CORNER_COL = "Corner"
FC_DIVISION_COL = "Division"

# --- ESTILOS CSS PARA OS CARDS ---
st.markdown("""
<style>
    div[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 10px;
        padding: 1rem;
    }
    .card-checked-in { background-color: #4A4A50; }
    .card-done { background-color: #1C4B2C; }
    .card-checked-in p, .card-done p, .card-checked-in small, .card-done small,
    .card-checked-in h3, .card-done h3 { color: #FFFFFF !important; }
</style>
""", unsafe_allow_html=True)


# --- Funções de Conexão e Carregamento de Dados ---

@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets: st.error("CRITICAL: `gcp_service_account` not in secrets.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e: st.error(f"CRITICAL: Gspread client error: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client: st.error("CRITICAL: Gspread client not initialized.", icon="🚨"); st.stop()
    try: return gspread_client.open(sheet_name).worksheet(tab_name)
    except Exception as e: st.error(f"CRITICAL: Error connecting to {sheet_name}/{tab_name}: {e}", icon="🚨"); st.stop()

@st.cache_data
def load_fightcard_data():
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=[FC_FIGHTER_COL, FC_ATHLETE_ID_COL, FC_EVENT_COL])
        for col in [FC_ATHLETE_ID_COL, FC_FIGHTER_COL, FC_CORNER_COL, FC_DIVISION_COL]:
            df[col] = df[col].astype(str).str.strip()
        return df
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

# --- FUNÇÃO DE ESCRITA SIMPLIFICADA ---
def record_attendance(athlete_id: str, task_name: str, status: str, order_number: int = None):
    """Grava o registro na planilha. O número da ordem agora é pré-calculado."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        # O order_number é passado como argumento, não mais calculado aqui.
        row_order = str(order_number) if order_number is not None else ''
        
        new_row = [timestamp, str(athlete_id), task_name, status, row_order]
        worksheet.append_row(new_row, value_input_option='USER_ENTERED')
        return True
    except Exception as e: st.error(f"Failed to record attendance for {athlete_id}: {e}"); return False

def get_athlete_task_status(athlete_id: str, task_name: str, df_attendance: pd.DataFrame):
    if df_attendance.empty or not task_name: return {"status": "Pending", "order": None}
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

# --- APLICAÇÃO PRINCIPAL ---
st.title("Live Attendance Station")

with st.spinner("Loading data..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    
if df_fc.empty:
    st.error("Could not load Fight Card data. Please check the spreadsheet URL and format."); st.stop()

st.header("Controls")
event_list = sorted(df_fc[FC_EVENT_COL].unique())
selected_events = st.multiselect("Step 1: Select Event(s)", options=event_list, default=event_list)
task_name = st.text_input("Step 2: Enter the Current Task Name", key="task_input").strip()

st.markdown("---")

if not selected_events:
    st.info("Please select at least one event.")
elif not task_name:
    st.info("Please enter a task name to manage attendance.")
else:
    st.header(f"Athletes for '{task_name}'")
    
    # --- LÓGICA DO RUNNING ORDER CORRIGIDA ---
    # 1. Filtra os registros de presença da tarefa atual
    task_records = df_att[df_att[ATTENDANCE_TASK_COL] == task_name]
    # 2. Encontra o maior número de ordem já registrado
    current_max_order = 0
    if not task_records.empty and task_records[ATTENDANCE_ORDER_COL].notna().any():
        current_max_order = task_records[ATTENDANCE_ORDER_COL].max()
    # 3. Calcula o próximo número da fila
    next_order_number = int(current_max_order + 1)
    
    athletes_in_scope = df_fc[df_fc[FC_EVENT_COL].isin(selected_events)].copy()
    
    status_list = []
    for index, athlete in athletes_in_scope.iterrows():
        status_info = get_athlete_task_status(athlete[FC_ATHLETE_ID_COL], task_name, df_att)
        status_list.append({**status_info, 'original_index': index})

    df_status = pd.DataFrame(status_list)
    athletes_to_display = athletes_in_scope.merge(df_status, left_index=True, right_on='original_index')

    status_order_map = {"Pending": 0, "Checked-in": 1, "Done": 2}
    athletes_to_display['sort_order'] = athletes_to_display['status'].map(status_order_map)
    athletes_to_display = athletes_to_display.sort_values(by=['sort_order', FC_FIGHTER_COL])

    for _, athlete in athletes_to_display.iterrows():
        athlete_id, status, order = athlete[FC_ATHLETE_ID_COL], athlete['status'], athlete['order']
        
        css_class = "card-checked-in" if status == "Checked-in" else "card-done" if status == "Done" else ""
        st.html(f"<div class='{css_class}'></div>")
        
        with st.container(border=True):
            cols = st.columns([1.5, 3, 2.5, 2])
            
            with cols[0]:
                st.image(athlete.get(FC_PICTURE_COL, "https://via.placeholder.com/100"), width=80)
                if status == "Checked-in": st.metric("Order #", f"{int(order)}")
                elif status == "Done": st.metric("Finished #", f"{int(order)}")

            with cols[1]:
                st.subheader(athlete[FC_FIGHTER_COL])
                st.caption(f"{athlete[FC_DIVISION_COL]} | {athlete[FC_CORNER_COL].title()} Corner")
                st.caption(f"Event: {athlete[FC_EVENT_COL]}")

            with cols[2]:
                if status == "Pending":
                    st.write("") # Espaçador
                elif status == "Checked-in":
                    st.info("⏳ Waiting for Check-out...")
                elif status == "Done":
                    st.success("✅ Task Completed!")
            
            with cols[3]:
                # --- LÓGICA DOS BOTÕES CORRIGIDA ---
                if status == "Pending":
                    if st.button("Check-in", key=f"in_{athlete_id}", use_container_width=True):
                        with st.spinner(f"Checking in {athlete[FC_FIGHTER_COL]}..."):
                            # Passa o número da ordem pré-calculado
                            if record_attendance(athlete_id, task_name, "Checked-in", order_number=next_order_number):
                                st.toast(f"Checked-in {athlete[FC_FIGHTER_COL]} as #{next_order_number}", icon="✅")
                                st.cache_data.clear(); time.sleep(0.5); st.rerun()
                elif status == "Checked-in":
                    if st.button("Check-out", key=f"out_{athlete_id}", use_container_width=True, type="primary"):
                        with st.spinner(f"Checking out {athlete[FC_FIGHTER_COL]}..."):
                            # Não precisa passar a ordem no check-out
                            if record_attendance(athlete_id, task_name, "Done"):
                                st.toast(f"Task completed for {athlete[FC_FIGHTER_COL]}!", icon="🎉")
                                st.cache_data.clear(); time.sleep(0.5); st.rerun()
