import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import gspread
from google.oauth2.service_account import Credentials

# --- Configuração ---
st.set_page_config(page_title="Live Dashboard", layout="wide")
LIVE_QUEUE_SHEET_NAME = "LiveQueue"
MAIN_SHEET_NAME = "UAEW_App"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

# --- Conexão e Lógica ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=5) # Cache muito baixo para dashboard em tempo real
def load_live_data():
    try:
        client = get_gspread_client()
        sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty:
            return pd.DataFrame(columns=['TaskName', 'AthleteID', 'Status', 'CheckinNumber'])
        
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        latest_status = df.sort_values('Timestamp').groupby(['TaskName', 'AthleteID']).tail(1)
        return latest_status
    except Exception:
        return pd.DataFrame(columns=['TaskName', 'AthleteID', 'Status', 'CheckinNumber'])

st_autorefresh(interval=5000, key="dashboard_refresh")
st.title("Live Queue Dashboard")

live_df = load_live_data()

if live_df.empty:
    st.info("No task data found. Please start a task on the Control Panel page.")
    st.stop()
    
# Carrega dados dos atletas para obter nomes e fotos
all_athletes_df = pd.read_csv(FIGHTCARD_SHEET_URL)
all_athletes_df['AthleteID'] = all_athletes_df['AthleteID'].astype(str)

# Filtro de Tarefa
task_options = live_df['TaskName'].unique().tolist()
selected_task = st.selectbox("Select a Task to Display:", options=task_options)

if selected_task:
    task_df = live_df[live_df['TaskName'] == selected_task]
    
    # Juntar para obter detalhes do atleta
    display_df = pd.merge(task_df, all_athletes_df, on='AthleteID', how='left')

    col1, col2 = st.columns(2)

    with col1:
        st.header("On Queue")
        on_queue_df = display_df[display_df['Status'] == 'na fila'].sort_values('CheckinNumber')
        for _, row in on_queue_df.iterrows():
            st.write(f"#{int(row['CheckinNumber'])} - {row['Fighter']}")

    with col2:
        st.header("Finished")
        finished_df = display_df[display_df['Status'] == 'finalizado']
        for _, row in finished_df.iterrows():
            st.write(f"✅ {row['Fighter']}")
