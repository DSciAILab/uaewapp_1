import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials

# --- Page Configuration ---
st.set_page_config(page_title="Task Control", layout="wide")

# --- Dynamic CSS ---
# --- [CORRECTED] --- Added .main-columns-wrapper for top alignment.
st.markdown("""
<style>
.main-columns-wrapper {
    display: flex;
    align-items: flex-start; /* Aligns columns to the top */
}
.athlete-photo-circle { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; }
.finished-photo-circle { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; filter: grayscale(100%); }
/* This rule centers content *within* a card */
div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] > div {
    display: flex;
    flex-direction: column;
    justify-content: center;
}
</style>
""", unsafe_allow_html=True)


# --- Global Constants ---
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
LIVE_QUEUE_SHEET_NAME = "LiveQueue"
MAIN_SHEET_NAME = "UAEW_App"

# --- Session State Initialization ---
if 'selected_events' not in st.session_state: st.session_state.selected_events = []
if 'selected_corner' not in st.session_state: st.session_state.selected_corner = "All"
if 'create_new_task' not in st.session_state: st.session_state.create_new_task = False

# --- Data Loading and Backend Functions ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def load_base_athlete_data(url):
    try:
        df = pd.read_csv(url); df.columns = df.columns.str.strip(); df = df.dropna(subset=['AthleteID', 'Fighter', 'Event'])
        df['AthleteID'] = df['AthleteID'].astype(str); df['Fighter'] = df['Fighter'].str.strip()
        if 'Corner' in df.columns: df['Corner'] = df['Corner'].str.lower()
        df['Picture'] = df.get('Picture', pd.Series(dtype=str)).fillna('https://via.placeholder.com/100?text=NA')
        df.loc[df['Picture'] == '', 'Picture'] = 'https://via.placeholder.com/100?text=NA'
        return df
    except Exception as e: st.error(f"Error loading base athlete data: {e}"); return pd.DataFrame()

@st.cache_data(ttl=10)
def load_live_queue_data_all():
    try:
        client = get_gspread_client()
        sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty: return pd.DataFrame(columns=['TaskName', 'AthleteID', 'Status', 'CheckinNumber', 'Timestamp'])
        df['AthleteID'] = df['AthleteID'].astype(str)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        return df.sort_values('Timestamp').groupby(['TaskName', 'AthleteID']).tail(1)
    except Exception as e: st.error(f"Error loading live queue: {e}"); return pd.DataFrame(columns=['TaskName', 'AthleteID', 'Status', 'CheckinNumber', 'Timestamp'])

def update_athlete_status_on_sheet(task_name, athlete_id, new_status):
    try:
        client = get_gspread_client(); sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
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
        st.cache_data.clear()
        return True
    except Exception as e: st.error(f"Failed to update status: {e}"); return False

# --- Main App Interface ---
st.title("Task Control Panel")
base_athletes_df = load_base_athlete_data(FIGHTCARD_SHEET_URL)
task_name = ""

live_queue_df_all = load_live_queue_data_all()
if not live_queue_df_all.empty:
    unique_tasks = live_queue_df_all['TaskName'].unique()
    existing_tasks = sorted([task for task in unique_tasks if isinstance(task, str) and task.strip()])
else:
    existing_tasks = []

with st.sidebar:
    st.header("Task Selection")
    st.session_state.create_new_task = st.toggle("Create New Task", value=st.session_state.create_new_task)
    if st.session_state.create_new_task:
        new_task_name = st.text_input("Enter New Task Name:", key="new_task_input")
        if new_task_name: task_name = new_task_name.strip()
    else:
        selected_task = st.selectbox("Load Existing Task:", options=["-"] + existing_tasks)
        if selected_task and selected_task != "-": task_name = selected_task
    
    st.divider()
    st.header("Filters")
    if not base_athletes_df.empty:
        event_options = sorted(base_athletes_df['Event'].unique().tolist())
        st.session_state.selected_events = st.multiselect("Filter by Event:", options=event_options, default=st.session_state.selected_events)
        st.radio("Filter by Corner:", options=["All", "Red", "Blue"], key="selected_corner", horizontal=True)
    else:
        st.warning("Could not load athlete data for filtering.")

if task_name:
    st.success(f"Controlling queue for: **{task_name}**")
    
    live_queue_df_task = live_queue_df_all[live_queue_df_all['TaskName'] == task_name] if not live_queue_df_all.empty else pd.DataFrame(columns=['AthleteID', 'Status', 'CheckinNumber'])
    
    athletes_to_display_df = base_athletes_df
    if st.session_state.selected_events:
        athletes_to_display_df = athletes_to_display_df[athletes_to_display_df['Event'].isin(st.session_state.selected_events)]
    if st.session_state.selected_corner != "All":
        athletes_to_display_df = athletes_to_display_df[athletes_to_display_df['Corner'] == st.session_state.selected_corner.lower()]

    merged_df = pd.merge(athletes_to_display_df, live_queue_df_task, on='AthleteID', how='left')
    merged_df['Status'] = merged_df['Status'].fillna('aguardando')

    # --- [CORRECTED] --- Wrap the columns in the custom div
    st.markdown('<div class="main-columns-wrapper">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([0.6, 1, 0.6])
    
    with col1:
        waiting_df = merged_df[merged_df['Status'] == 'aguardando'].sort_values('Fighter')
        st.header(f"Waiting ({len(waiting_df)})")
        for _, row in waiting_df.iterrows():
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 2])
                with pic_col:
                    st.markdown(f'<img src="{row["Picture"]}" class="athlete-photo-circle">', unsafe_allow_html=True)
                with name_col:
                    st.write(f"**{row['Fighter']}**")
                    if st.button("➡️ Check-in", key=f"checkin_{task_name}_{row['AthleteID']}"):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'na fila')
                        st.rerun()

    with col2:
        on_queue_df = merged_df[merged_df['Status'] == 'na fila'].sort_values('CheckinNumber')
        st.header(f"On Queue ({len(on_queue_df)})")
        for _, row in on_queue_df.iterrows():
            with st.container(border=True):
                num_col, pic_col, name_col = st.columns([1, 1, 2])
                with num_col:
                    st.markdown(f"<h1 style='text-align: center;'>{int(row['CheckinNumber'])}</h1>", unsafe_allow_html=True)
                with pic_col:
                    st.markdown(f'<img src="{row["Picture"]}" class="athlete-photo-circle">', unsafe_allow_html=True)
                with name_col:
                    st.write(f"**{row['Fighter']}**")
                    if st.button("🏁 Check-out", key=f"checkout_{task_name}_{row['AthleteID']}", type="primary", use_container_width=True):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'finalizado')
                        st.rerun()
                    if st.button("↩️ Remove from Queue", key=f"remove_{task_name}_{row['AthleteID']}", use_container_width=True):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'aguardando')
                        st.rerun()

    with col3:
        finished_df = merged_df[merged_df['Status'] == 'finalizado']
        st.header(f"Finished ({len(finished_df)})")
        for _, row in finished_df.iterrows():
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 4])
                with pic_col:
                    st.markdown(f'<img src="{row["Picture"]}" class="finished-photo-circle">', unsafe_allow_html=True)
                with name_col:
                    st.write(f"~~{row['Fighter']}~~")
    
    st.markdown('</div>', unsafe_allow_html=True) # Close the wrapper div
else:
    st.info("Select or create a task in the sidebar to begin.")
