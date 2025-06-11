import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz
import gspread
from google.oauth2.service_account import Credentials

# --- Configuração ---
st.set_page_config(page_title="Task Control", layout="wide")

# --- Constantes Globais ---
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
LIVE_QUEUE_SHEET_NAME = "LiveQueue"  # O nome da sua nova aba
MAIN_SHEET_NAME = "UAEW_App" # O nome do seu arquivo Google Sheets

# --- Conexão e Lógica do Google Sheets ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=15) # Cache baixo para obter dados quase em tempo real
def load_live_queue_data(task_name):
    try:
        client = get_gspread_client()
        sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty:
            return pd.DataFrame(columns=['AthleteID', 'Status', 'CheckinNumber'])
        df_task = df[df['TaskName'] == task_name].copy()
        df_task['Timestamp'] = pd.to_datetime(df_task['Timestamp'], errors='coerce')
        # Pega o status mais recente para cada atleta
        latest_status = df_task.sort_values('Timestamp').groupby('AthleteID').tail(1)
        return latest_status
    except Exception as e:
        st.error(f"Error loading live queue: {e}")
        return pd.DataFrame(columns=['AthleteID', 'Status', 'CheckinNumber'])

def update_athlete_status_on_sheet(task_name, athlete_id, new_status):
    try:
        client = get_gspread_client()
        sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
        
        check_in_number = ""
        if new_status == 'na fila':
            # Calcula o próximo número de check-in lendo o estado atual
            all_records = pd.DataFrame(sheet.get_all_records())
            if not all_records.empty:
                task_records = all_records[all_records['TaskName'] == task_name]
                max_order = pd.to_numeric(task_records['CheckinNumber'], errors='coerce').max()
                check_in_number = int(max_order + 1) if pd.notna(max_order) else 1
            else:
                check_in_number = 1
        
        timestamp = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
        new_row = [timestamp, task_name, str(athlete_id), new_status, str(check_in_number)]
        sheet.append_row(new_row, value_input_option='USER_ENTERED')
        st.cache_data.clear() # Limpa o cache para forçar a releitura
        return True
    except Exception as e:
        st.error(f"Failed to update status: {e}")
        return False

# O resto do seu código da página de controle...
# O código abaixo é uma versão simplificada, integre com o seu layout.
# A principal mudança é que os botões agora chamam `update_athlete_status_on_sheet`.

st.title("Task Control Panel")
task_name = st.text_input("Enter Task Name to Control:")

if task_name:
    st.success(f"Controlling queue for: **{task_name}**")
    live_queue_df = load_live_queue_data(task_name)
    all_athletes_df = pd.read_csv(FIGHTCARD_SHEET_URL)
    
    # Juntar dados para obter nomes e fotos
    all_athletes_df['AthleteID'] = all_athletes_df['AthleteID'].astype(str)
    merged_df = pd.merge(all_athletes_df, live_queue_df, on='AthleteID', how='left').fillna({'Status': 'aguardando'})

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.header("Waiting")
        waiting_df = merged_df[merged_df['Status'] == 'aguardando']
        for _, row in waiting_df.iterrows():
            if st.button(f"Check-in {row['Fighter']}", key=f"in_{row['AthleteID']}"):
                update_athlete_status_on_sheet(task_name, row['AthleteID'], 'na fila')
                st.rerun()
                
    with col2:
        st.header("On Queue")
        on_queue_df = merged_df[merged_df['Status'] == 'na fila'].sort_values('CheckinNumber')
        for _, row in on_queue_df.iterrows():
            if st.button(f"Check-out #{int(row['CheckinNumber'])} - {row['Fighter']}", key=f"out_{row['AthleteID']}"):
                update_athlete_status_on_sheet(task_name, row['AthleteID'], 'finalizado')
                st.rerun()

    with col3:
        st.header("Finished")
        finished_df = merged_df[merged_df['Status'] == 'finalizado']
        for _, row in finished_df.iterrows():
            st.write(f"✅ {row['Fighter']}")
