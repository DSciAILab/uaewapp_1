import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import pytz  # <-- 1. Imported for timezone handling

# --- Page Configuration ---
st.set_page_config(page_title="Task Control", layout="wide")

# --- Session State Initialization ---
# Ensures all keys exist from the start to prevent errors.
if 'name_font_size' not in st.session_state: st.session_state.name_font_size = 18
if 'number_font_size' not in st.session_state: st.session_state.number_font_size = 48
if 'photo_size' not in st.session_state: st.session_state.photo_size = 60
if 'task_locked' not in st.session_state: st.session_state.task_locked = False
if 'task_name_input' not in st.session_state: st.session_state.task_name_input = ""
if 'task_duration' not in st.session_state: st.session_state.task_duration = 5 # Default duration of 5 minutes
if 'selected_timezone' not in st.session_state: st.session_state.selected_timezone = "UTC" # Default timezone


# --- Sidebar Controls ---
with st.sidebar:
    st.header("Task Setup")

    # --- [MODIFIED] --- Define Task section moved to the sidebar
    if not st.session_state.task_locked:
        temp_task_name = st.text_input("1. Enter Task Name:", placeholder="e.g., Photoshoot, Weigh-in...", key="temp_input")
        if st.button("Start Queue for this Task", type="primary"):
            if temp_task_name:
                st.session_state.task_name_input = temp_task_name
                st.session_state.task_locked = True
                st.rerun()
            else:
                st.warning("Please enter a task name.")
    else:
        st.success(f"Active Task: **{st.session_state.task_name_input}**")
        if st.button("Change Task"):
            st.session_state.task_locked = False
            st.session_state.task_name_input = ""
            st.rerun()

    st.divider()
    st.header("Display Controls")
    
    # --- [NEW] --- Task Duration and Timezone selectors
    st.session_state.task_duration = st.number_input("2. Average Task Duration (minutes)", min_value=1, value=st.session_state.task_duration)
    st.session_state.selected_timezone = st.selectbox("3. Select Your Timezone", options=pytz.common_timezones, index=pytz.common_timezones.index(st.session_state.selected_timezone))
    
    st.divider()
    st.session_state.name_font_size = st.slider("Athlete Name Size (px)", 12, 32, st.session_state.name_font_size)
    st.session_state.number_font_size = st.slider("Call Number Size (px)", 24, 96, st.session_state.number_font_size)
    st.session_state.photo_size = st.slider("Photo Size (px)", 40, 120, st.session_state.photo_size)


# --- Dynamic CSS ---
st.markdown(f"""
<style>
    div[data-testid="stToolbar"], #MainMenu, header {{ visibility: hidden; }}
    .athlete-photo {{ width: {st.session_state.photo_size}px; height: {st.session_state.photo_size}px; border-radius: 50%; object-fit: cover; border: 2px solid #4F4F4F; }}
    .finished-photo {{ width: {int(st.session_state.photo_size * 0.7)}px; height: {int(st.session_state.photo_size * 0.7)}px; border-radius: 50%; object-fit: cover; filter: grayscale(100%); opacity: 0.6; }}
    .athlete-name {{ font-size: {st.session_state.name_font_size}px !important; font-weight: bold; line-height: 1.2; margin-bottom: 5px;}}
    .call-number {{ font-size: {st.session_state.number_font_size}px !important; font-weight: bold; text-align: center; color: #17a2b8; }}
    .center-vertically {{ display: flex; justify-content: center; align-items: center; height: 100%; }}
    .eta-text {{ font-size: 0.8em; color: #A0A0A0; }}
</style>
""", unsafe_allow_html=True)


# --- Data Loading ---
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
@st.cache_data(ttl=300)
def load_fightcard_data(url):
    try:
        df = pd.read_csv(url); df.columns = df.columns.str.strip(); df = df.dropna(subset=['AthleteID', 'Fighter'])
        df['AthleteID'] = df['AthleteID'].astype(str); df['Fighter'] = df['Fighter'].str.strip()
        return df
    except Exception as e: st.error(f"Error loading data: {e}"); return pd.DataFrame()

# --- Logic Functions ---
def initialize_task_state(task_name, athletes_df):
    if 'tasks' not in st.session_state: st.session_state.tasks = {}
    st.session_state.tasks[task_name] = {"athletes": {}, "next_checkin_number": 1}
    for _, athlete in athletes_df.iterrows():
        st.session_state.tasks[task_name]['athletes'][athlete['AthleteID']] = {
            "name": athlete['Fighter'], "pic": athlete.get('Picture', 'https://via.placeholder.com/100?text=NA'),
            "status": "aguardando", "checkin_number": None
        }

def update_athlete_status(task_name, athlete_id, new_status):
    task_data = st.session_state.tasks[task_name]; athlete_data = task_data['athletes'][athlete_id]
    if new_status == 'na fila' and athlete_data['status'] == 'aguardando':
        athlete_data['checkin_number'] = task_data['next_checkin_number']; task_data['next_checkin_number'] += 1
    athlete_data['status'] = new_status


# --- Main App Interface ---
col_title, col_clock = st.columns([3, 1])
with col_title: st.title("Dynamic Queue Task Control")
with col_clock: clock_placeholder = st.empty()

st_autorefresh(interval=1000, key="clock_refresh")
# --- [MODIFIED] --- Clock now uses the selected timezone
tz = pytz.timezone(st.session_state.selected_timezone)
now_in_tz = datetime.now(tz)
clock_placeholder.markdown(f"<h3 style='text-align: right; color: #A0A0A0;'>{now_in_tz.strftime('%H:%M:%S')}</h3>", unsafe_allow_html=True)

all_athletes_df = load_fightcard_data(FIGHTCARD_SHEET_URL)
if all_athletes_df.empty: st.stop()


# The main content only runs if a task is locked
if st.session_state.task_locked and st.session_state.task_name_input:
    task_name = st.session_state.task_name_input
    if task_name not in st.session_state.get('tasks', {}): initialize_task_state(task_name, all_athletes_df)
    
    st.header("Athlete Search")
    search_query = st.text_input("Search by Name or ID:", key=f"search_{task_name}").lower()
    df_filtered = all_athletes_df[all_athletes_df['Fighter'].str.lower().str.contains(search_query) | all_athletes_df['AthleteID'].str.contains(search_query)] if search_query else all_athletes_df

    st.divider()
    st.header("Queue Management")

    waiting_list, checked_in_list, finished_list = [], [], []
    for _, row in df_filtered.iterrows():
        athlete_id = row['AthleteID']
        status_data = st.session_state.tasks[task_name]['athletes'].get(athlete_id)
        if status_data:
            item = (athlete_id, status_data)
            if status_data['status'] == 'aguardando': waiting_list.append(item)
            elif status_data['status'] == 'na fila': checked_in_list.append(item)
            else: finished_list.append(item)
    
    checked_in_list.sort(key=lambda item: item[1]['checkin_number'])
    
    if not search_query:
        totals = {s: len([a for a in st.session_state.tasks[task_name]['athletes'].values() if a['status'] == s]) for s in ['aguardando', 'na fila', 'finalizado']}
    else:
        totals = {'aguardando': len(waiting_list), 'na fila': len(checked_in_list), 'finalizado': len(finished_list)}

    col1, col2, col3 = st.columns(3)

    with col1:
        st.header(f"Waiting ({totals['aguardando']})")
        for athlete_id, athlete in waiting_list:
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 2])
                with pic_col: st.markdown(f'<div class="center-vertically"><img class="athlete-photo" src="{athlete["pic"]}"></div>', unsafe_allow_html=True)
                with name_col:
                    st.markdown(f"<p class='athlete-name'>{athlete['name']}</p>", unsafe_allow_html=True)
                    st.button("➡️ Check-in", key=f"checkin_{task_name}_{athlete_id}", on_click=update_athlete_status, args=(task_name, athlete_id, 'na fila'), use_container_width=True, type="secondary")

    with col2:
        st.header(f"On Queue ({totals['na fila']})")
        for index, (athlete_id, athlete) in enumerate(checked_in_list):
            is_next = index == 0
            container_border_color = "#00BFFF" if is_next else "#808495"
            with st.container(border=True):
                num_col, pic_col, name_col = st.columns([1, 1, 2])
                with num_col: st.markdown(f"<div class='center-vertically'><p class='call-number' style='color:{container_border_color};'>{athlete['checkin_number']}</p></div>", unsafe_allow_html=True)
                with pic_col: st.markdown(f'<div class="center-vertically"><img class="athlete-photo" style="border-color:{container_border_color};" src="{athlete["pic"]}"></div>', unsafe_allow_html=True)
                with name_col:
                    st.markdown(f"<p class='athlete-name'>{athlete['name']}</p>", unsafe_allow_html=True)
                    # --- [NEW] --- ETA Calculation and Display
                    duration = st.session_state.task_duration
                    eta = now_in_tz + timedelta(minutes=index * duration)
                    st.markdown(f"<p class='eta-text'>ETA: {eta.strftime('%H:%M')}</p>", unsafe_allow_html=True)
                    
                    if is_next: st.markdown("⭐ **NEXT!**")
                    st.button("🏁 Check-out", key=f"checkout_{task_name}_{athlete_id}", on_click=update_athlete_status, args=(task_name, athlete_id, 'finalizado'), use_container_width=True, type="primary")

    with col3:
        st.header(f"Finished ({totals['finalizado']})")
        for athlete_id, athlete in finished_list:
             with st.container(border=True):
                pic_col, name_col = st.columns([1, 4])
                with pic_col: st.markdown(f'<div class="center-vertically"><img class="finished-photo" src="{athlete["pic"]}"></div>', unsafe_allow_html=True)
                with name_col: st.markdown(f"<p class='athlete-name' style='text-decoration: line-through; color: #808495;'>{athlete['name']}</p>", unsafe_allow_html=True)

else:
    st.info("Define a task in the sidebar to begin.")
