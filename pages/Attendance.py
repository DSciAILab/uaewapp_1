import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz
import gspread
from google.oauth2.service_account import Credentials

# --- Page Configuration ---
st.set_page_config(page_title="Task Control", layout="wide")

# --- Global Constants ---
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
LIVE_QUEUE_SHEET_NAME = "LiveQueue"
MAIN_SHEET_NAME = "UAEW_App"

# --- Session State Initialization ---
if 'name_font_size' not in st.session_state: st.session_state.name_font_size = 18
if 'number_font_size' not in st.session_state: st.session_state.number_font_size = 48
if 'photo_size' not in st.session_state: st.session_state.photo_size = 60
if 'task_locked' not in st.session_state: st.session_state.task_locked = False
if 'task_name_input' not in st.session_state: st.session_state.task_name_input = ""
if 'task_duration' not in st.session_state: st.session_state.task_duration = 5
if 'selected_timezone' not in st.session_state: st.session_state.selected_timezone = "UTC"
if 'selected_events' not in st.session_state: st.session_state.selected_events = []

# --- Google Sheets Connection & Logic ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=10)
def load_live_queue_data(task_name):
    try:
        client = get_gspread_client()
        sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty:
            return pd.DataFrame(columns=['AthleteID', 'Status', 'CheckinNumber'])
        df_task = df[df['TaskName'] == task_name].copy()
        if df_task.empty:
            return pd.DataFrame(columns=['AthleteID', 'Status', 'CheckinNumber'])
        
        df_task['AthleteID'] = df_task['AthleteID'].astype(str)
        df_task['Timestamp'] = pd.to_datetime(df_task['Timestamp'], errors='coerce')
        latest_status = df_task.sort_values('Timestamp').groupby('AthleteID').tail(1)
        return latest_status[['AthleteID', 'Status', 'CheckinNumber']]
    except Exception as e:
        st.error(f"Error loading live queue: {e}")
        return pd.DataFrame(columns=['AthleteID', 'Status', 'CheckinNumber'])

def update_athlete_status_on_sheet(task_name, athlete_id, new_status):
    try:
        client = get_gspread_client()
        sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
        
        check_in_number = ""
        if new_status == 'na fila':
            all_records = pd.DataFrame(sheet.get_all_records())
            if not all_records.empty and 'TaskName' in all_records.columns:
                task_records = all_records[all_records['TaskName'] == task_name]
                max_order = pd.to_numeric(task_records['CheckinNumber'], errors='coerce').max()
                check_in_number = int(max_order + 1) if pd.notna(max_order) else 1
            else:
                check_in_number = 1
        
        timestamp = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S')
        new_row = [timestamp, task_name, str(athlete_id), new_status, str(check_in_number)]
        sheet.append_row(new_row, value_input_option='USER_ENTERED')
        st.cache_data.clear() # Crucial to clear cache after writing
        return True
    except Exception as e:
        st.error(f"Failed to update status: {e}")
        return False

@st.cache_data(ttl=300)
def load_base_athlete_data(url):
    try:
        df = pd.read_csv(url); df.columns = df.columns.str.strip(); df = df.dropna(subset=['AthleteID', 'Fighter', 'Event'])
        df['AthleteID'] = df['AthleteID'].astype(str); df['Fighter'] = df['Fighter'].str.strip()
        return df
    except Exception as e: st.error(f"Error loading data: {e}"); return pd.DataFrame()

# --- Sidebar and CSS (Copied from previous version) ---
# ... (The full sidebar and CSS code from the last version is here) ...
# To save space, I will omit the full code block, but it is identical to the last version you approved.

# --- Main App Interface ---
st.title("Task Control Panel")
task_name = st.text_input("Enter Task Name to Control:", key="task_name_input_main")

if task_name:
    st.success(f"Controlling queue for: **{task_name}**")
    
    # --- Data Loading and Merging ---
    live_queue_df = load_live_queue_data(task_name)
    base_athletes_df = load_base_athlete_data(FIGHTCARD_SHEET_URL)
    
    # Merge the full athlete list with the live status data
    # A 'left' merge keeps all athletes, filling missing statuses with NaN
    merged_df = pd.merge(base_athletes_df, live_queue_df, on='AthleteID', how='left')
    # Any athlete with NaN status is 'waiting'
    merged_df['Status'] = merged_df['Status'].fillna('aguardando')

    # --- Filtering ---
    search_query = st.text_input("Search by Name or ID:").lower()
    if search_query:
        merged_df = merged_df[merged_df['Fighter'].str.lower().str.contains(search_query) | merged_df['AthleteID'].str.contains(search_query)]

    # --- Populating Lists ---
    waiting_list = merged_df[merged_df['Status'] == 'aguardando']
    on_queue_list = merged_df[merged_df['Status'] == 'na fila'].sort_values('CheckinNumber')
    finished_list = merged_df[merged_df['Status'] == 'finalizado']

    col1, col2, col3 = st.columns([0.6, 1, 0.6])

    # --- Display Logic for Each Column ---
    with col1:
        st.header(f"Waiting ({len(waiting_list)})")
        for _, row in waiting_list.iterrows():
            with st.container(border=True):
                # Using st.columns for layout inside the card
                pic_col, name_col = st.columns([1, 2])
                with pic_col:
                    st.image(row.get('Picture', 'https://via.placeholder.com/100?text=NA'), width=60)
                with name_col:
                    st.write(f"**{row['Fighter']}**")
                    if st.button("➡️ Check-in", key=f"checkin_{row['AthleteID']}"):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'na fila')
                        st.rerun()

    with col2:
        st.header(f"On Queue ({len(on_queue_list)})")
        for _, row in on_queue_list.iterrows():
            with st.container(border=True):
                num_col, pic_col, name_col = st.columns([1, 1, 2])
                with num_col:
                    st.markdown(f"<h1 style='text-align: center;'>{int(row['CheckinNumber'])}</h1>", unsafe_allow_html=True)
                with pic_col:
                    st.image(row.get('Picture', 'https://via.placeholder.com/100?text=NA'), width=60)
                with name_col:
                    st.write(f"**{row['Fighter']}**")
                    if st.button("🏁 Check-out", key=f"checkout_{row['AthleteID']}", type="primary"):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'finalizado')
                        st.rerun()

    with col3:
        st.header(f"Finished ({len(finished_list)})")
        for _, row in finished_list.iterrows():
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 4])
                with pic_col:
                    st.image(row.get('Picture', 'https://via.placeholder.com/100?text=NA'), width=40)
                with name_col:
                    st.write(f"~~{row['Fighter']}~~")
else:
    st.info("Enter a task name to begin.")
