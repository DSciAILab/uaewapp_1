aimport streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
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
if 'selected_events' not in st.session_state: st.session_state.selected_events = []
if 'selected_corner' not in st.session_state: st.session_state.selected_corner = "All" # Default to show all corners

# --- Data Loading and Backend Functions ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def load_base_athlete_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['AthleteID', 'Fighter', 'Event'])
        df['AthleteID'] = df['AthleteID'].astype(str)
        df['Fighter'] = df['Fighter'].str.strip()
        # Ensure 'Corner' column is lowercase for consistent filtering
        if 'Corner' in df.columns:
            df['Corner'] = df['Corner'].str.lower()
        if 'Picture' not in df.columns:
            df['Picture'] = 'https://via.placeholder.com/100?text=NA'
        else:
            df['Picture'] = df['Picture'].fillna('https://via.placeholder.com/100?text=NA')
            df.loc[df['Picture'] == '', 'Picture'] = 'https://via.placeholder.com/100?text=NA'
        return df
    except Exception as e:
        st.error(f"Error loading base athlete data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=10)
def load_live_queue_data(task_name):
    try:
        client = get_gspread_client()
        sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty: return pd.DataFrame(columns=['AthleteID', 'Status', 'CheckinNumber'])
        
        df_task = df[df['TaskName'] == task_name].copy()
        if df_task.empty: return pd.DataFrame(columns=['AthleteID', 'Status', 'CheckinNumber'])
        
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
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Failed to update status: {e}")
        return False

# --- Main App Interface ---
st.title("Task Control Panel")

base_athletes_df = load_base_athlete_data(FIGHTCARD_SHEET_URL)
with st.sidebar:
    st.header("Filters")
    if not base_athletes_df.empty:
        event_options = sorted(base_athletes_df['Event'].unique().tolist())
        st.session_state.selected_events = st.multiselect(
            "Filter by Event:",
            options=event_options,
            default=st.session_state.selected_events
        )
        # --- [NEW] --- Corner filter radio buttons
        st.radio(
            "Filter by Corner:",
            options=["All", "Red", "Blue"],
            key="selected_corner",
            horizontal=True
        )
    else:
        st.warning("Could not load athlete data for filtering.")

task_name = st.text_input("Enter Task Name to Control:")

if task_name:
    st.success(f"Controlling queue for: **{task_name}**")
    
    live_queue_df = load_live_queue_data(task_name)
    
    # Start with the full dataset
    athletes_to_display_df = base_athletes_df
    
    # Apply event filter if any events are selected
    if st.session_state.selected_events:
        athletes_to_display_df = athletes_to_display_df[athletes_to_display_df['Event'].isin(st.session_state.selected_events)]
    
    # --- [NEW] --- Apply corner filter
    if st.session_state.selected_corner != "All":
        athletes_to_display_df = athletes_to_display_df[athletes_to_display_df['Corner'] == st.session_state.selected_corner.lower()]


    merged_df = pd.merge(athletes_to_display_df, live_queue_df, on='AthleteID', how='left')
    merged_df['Status'] = merged_df['Status'].fillna('aguardando')

    col1, col2, col3 = st.columns([0.6, 1, 0.6])
    
    with col1:
        waiting_df = merged_df[merged_df['Status'] == 'aguardando'].sort_values('Fighter')
        st.header(f"Waiting ({len(waiting_df)})")
        for _, row in waiting_df.iterrows():
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 2])
                with pic_col:
                    st.image(row['Picture'], width=60)
                with name_col:
                    st.write(f"**{row['Fighter']}**")
                    if st.button("➡️ Check-in", key=f"checkin_{row['AthleteID']}"):
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
                    st.image(row['Picture'], width=60)
                with name_col:
                    st.write(f"**{row['Fighter']}**")
                    if st.button("🏁 Check-out", key=f"checkout_{row['AthleteID']}", type="primary", use_container_width=True):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'finalizado')
                        st.rerun()
                    if st.button("↩️ Remove from Queue", key=f"remove_{row['AthleteID']}", use_container_width=True):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'aguardando')
                        st.rerun()

    with col3:
        finished_df = merged_df[merged_df['Status'] == 'finalizado']
        st.header(f"Finished ({len(finished_df)})")
        for _, row in finished_df.iterrows():
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 4])
                with pic_col:
                    st.image(row['Picture'], width=40, clamp=True)
                with name_col:
                    st.write(f"~~{row['Fighter']}~~")
else:
    st.info("Enter a task name to begin.")import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
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
if 'selected_events' not in st.session_state:
    st.session_state.selected_events = []

# --- Data Loading and Backend Functions ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def load_base_athlete_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['AthleteID', 'Fighter', 'Event'])
        df['AthleteID'] = df['AthleteID'].astype(str)
        df['Fighter'] = df['Fighter'].str.strip()
        if 'Picture' not in df.columns:
            df['Picture'] = 'https://via.placeholder.com/100?text=NA'
        else:
            df['Picture'] = df['Picture'].fillna('https://via.placeholder.com/100?text=NA')
            df.loc[df['Picture'] == '', 'Picture'] = 'https://via.placeholder.com/100?text=NA'
        return df
    except Exception as e:
        st.error(f"Error loading base athlete data: {e}")
        return pd.DataFrame()

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
        # The logic to calculate check-in number is only needed for the "on queue" status
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
    except Exception as e:
        st.error(f"Failed to update status: {e}")
        return False

# --- Main App Interface ---
st.title("Task Control Panel")

# --- [NEW] Sidebar for Event Filtering ---
base_athletes_df = load_base_athlete_data(FIGHTCARD_SHEET_URL)
with st.sidebar:
    st.header("Filters")
    if not base_athletes_df.empty:
        event_options = sorted(base_athletes_df['Event'].unique().tolist())
        st.session_state.selected_events = st.multiselect(
            "Filter by Event:",
            options=event_options,
            default=st.session_state.selected_events
        )
    else:
        st.warning("Could not load athlete data for filtering.")

task_name = st.text_input("Enter Task Name to Control:")

if task_name:
    st.success(f"Controlling queue for: **{task_name}**")
    
    live_queue_df = load_live_queue_data(task_name)
    
    # Apply event filter if any events are selected
    if st.session_state.selected_events:
        athletes_to_display_df = base_athletes_df[base_athletes_df['Event'].isin(st.session_state.selected_events)]
    else:
        athletes_to_display_df = base_athletes_df

    merged_df = pd.merge(athletes_to_display_df, live_queue_df, on='AthleteID', how='left')
    merged_df['Status'] = merged_df['Status'].fillna('aguardando')

    col1, col2, col3 = st.columns([0.6, 1, 0.6])
    
    with col1:
        # --- [MODIFIED] --- Added .sort_values('Fighter') for alphabetical order
        waiting_df = merged_df[merged_df['Status'] == 'aguardando'].sort_values('Fighter')
        st.header(f"Waiting ({len(waiting_df)})")
        for _, row in waiting_df.iterrows():
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 2])
                with pic_col:
                    st.image(row['Picture'], width=60)
                with name_col:
                    st.write(f"**{row['Fighter']}**")
                    if st.button("➡️ Check-in", key=f"checkin_{row['AthleteID']}"):
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
                    st.image(row['Picture'], width=60)
                with name_col:
                    st.write(f"**{row['Fighter']}**")
                    if st.button("🏁 Check-out", key=f"checkout_{row['AthleteID']}", type="primary", use_container_width=True):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'finalizado')
                        st.rerun()
                    # --- [NEW] --- Button to remove from queue
                    if st.button("↩️ Remove from Queue", key=f"remove_{row['AthleteID']}", use_container_width=True):
                        update_athlete_status_on_sheet(task_name, row['AthleteID'], 'aguardando')
                        st.rerun()

    with col3:
        finished_df = merged_df[merged_df['Status'] == 'finalizado']
        st.header(f"Finished ({len(finished_df)})")
        for _, row in finished_df.iterrows():
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 4])
                with pic_col:
                    st.image(row['Picture'], width=40, clamp=True)
                with name_col:
                    st.write(f"~~{row['Fighter']}~~")
else:
    st.info("Enter a task name to begin.")
