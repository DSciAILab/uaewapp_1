import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import gspread
from google.oauth2.service_account import Credentials

# --- Page Configuration ---
st.set_page_config(page_title="Live Dashboard", layout="wide")

# --- Global Constants ---
LIVE_QUEUE_SHEET_NAME = "LiveQueue"
MAIN_SHEET_NAME = "UAEW_App"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

# --- Session State Initialization for UI Controls ---
if 'dash_name_font_size' not in st.session_state: st.session_state.dash_name_font_size = 24
if 'dash_number_font_size' not in st.session_state: st.session_state.dash_number_font_size = 60
if 'dash_photo_size' not in st.session_state: st.session_state.dash_photo_size = 80
if 'dash_selected_task' not in st.session_state: st.session_state.dash_selected_task = None


# --- Connection and Data Loading ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=5)
def load_live_data():
    try:
        client = get_gspread_client()
        sheet = client.open(MAIN_SHEET_NAME).worksheet(LIVE_QUEUE_SHEET_NAME)
        df = pd.DataFrame(sheet.get_all_records())
        if df.empty:
            return pd.DataFrame(columns=['TaskName', 'AthleteID', 'Status', 'CheckinNumber'])
        df['AthleteID'] = df['AthleteID'].astype(str)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
        latest_status = df.sort_values('Timestamp').groupby(['TaskName', 'AthleteID']).tail(1)
        return latest_status
    except Exception as e:
        st.error(f"Error loading live data: {e}")
        return pd.DataFrame(columns=['TaskName', 'AthleteID', 'Status', 'CheckinNumber'])

@st.cache_data(ttl=300)
def load_athlete_details(url):
    try:
        df = pd.read_csv(url)
        df['AthleteID'] = df['AthleteID'].astype(str)
        # Clean the picture data to prevent errors
        if 'Picture' not in df.columns:
            df['Picture'] = 'https://via.placeholder.com/100?text=NA'
        else:
            df['Picture'] = df['Picture'].fillna('https://via.placeholder.com/100?text=NA')
            df.loc[df['Picture'] == '', 'Picture'] = 'https://via.placeholder.com/100?text=NA'
        return df[['AthleteID', 'Fighter', 'Picture']]
    except Exception as e:
        st.error(f"Error loading athlete details: {e}")
        return pd.DataFrame()


# --- Main App ---
st_autorefresh(interval=5000, key="dashboard_refresh")

live_df = load_live_data()
all_athletes_df = load_athlete_details(FIGHTCARD_SHEET_URL)

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Dashboard Controls")
    if not live_df.empty:
        task_options = live_df['TaskName'].unique().tolist()
        st.session_state.dash_selected_task = st.selectbox(
            "Select Task to Display:",
            options=task_options,
            index=task_options.index(st.session_state.dash_selected_task) if st.session_state.dash_selected_task in task_options else 0
        )
    else:
        st.info("No active tasks found.")
        st.session_state.dash_selected_task = None
    
    st.divider()
    st.header("Display Size")
    st.session_state.dash_name_font_size = st.slider("Athlete Name Size (px)", 12, 48, st.session_state.dash_name_font_size)
    st.session_state.dash_number_font_size = st.slider("Call Number Size (px)", 24, 120, st.session_state.dash_number_font_size)
    st.session_state.dash_photo_size = st.slider("Photo Size (px)", 40, 150, st.session_state.dash_photo_size)

# --- Dynamic Title and CSS ---
selected_task = st.session_state.dash_selected_task
st.title(f"Live Dashboard: {selected_task}" if selected_task else "Live Dashboard")

st.markdown(f"""
<style>
    div[data-testid="stToolbar"], #MainMenu, header {{ visibility: hidden; }}
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] {{ align-items: center; }}
    .next-in-queue {{ background-color: #1c2833; border: 1px solid #00BFFF; border-radius: 0.5rem; padding: 1rem; margin-bottom: 1rem; }}
    .athlete-photo {{ width: {st.session_state.dash_photo_size}px; height: {st.session_state.dash_photo_size}px; border-radius: 50%; object-fit: cover; }}
    .finished-photo {{ width: {int(st.session_state.dash_photo_size * 0.7)}px; height: {int(st.session_state.dash_photo_size * 0.7)}px; border-radius: 50%; object-fit: cover; filter: grayscale(100%); }}
    .athlete-name {{ font-size: {st.session_state.dash_name_font_size}px !important; font-weight: bold; }}
    .call-number {{ font-size: {st.session_state.dash_number_font_size}px !important; font-weight: bold; text-align: center; }}
</style>
""", unsafe_allow_html=True)


if selected_task:
    task_df = live_df[live_df['TaskName'] == selected_task]
    display_df = pd.merge(task_df, all_athletes_df, on='AthleteID', how='left')

    col1, col2 = st.columns(2)

    with col1:
        st.header(f"On Queue ({len(display_df[display_df['Status'] == 'na fila'])})")
        on_queue_df = display_df[display_df['Status'] == 'na fila'].sort_values('CheckinNumber')
        for index, row in on_queue_df.iterrows():
            is_next = index == 0
            container_class = "next-in-queue" if is_next else ""
            with st.markdown(f'<div class="{container_class}">', unsafe_allow_html=True) if is_next else st.container(border=True):
                num_col, pic_col, name_col = st.columns([1, 1, 2])
                with num_col:
                    st.markdown(f"<p class='call-number' style='color:{'#00BFFF' if is_next else '#808495'};'>{int(row['CheckinNumber'])}</p>", unsafe_allow_html=True)
                with pic_col:
                    st.image(row['Picture'], width=st.session_state.dash_photo_size)
                with name_col:
                    st.markdown(f"<p class='athlete-name'>{row.get('Fighter', 'N/A')}</p>", unsafe_allow_html=True)
                    if is_next:
                        st.markdown("⭐ **NEXT!**")

            if is_next: st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.header(f"Finished ({len(display_df[display_df['Status'] == 'finalizado'])})")
        finished_df = display_df[display_df['Status'] == 'finalizado']
        for _, row in finished_df.iterrows():
            with st.container(border=True):
                pic_col, name_col = st.columns([1, 4])
                with pic_col:
                    st.image(row['Picture'], width=int(st.session_state.dash_photo_size * 0.7))
                with name_col:
                    st.markdown(f"<p class='athlete-name' style='text-decoration: line-through; color: #808495;'>{row.get('Fighter', 'N/A')}</p>", unsafe_allow_html=True)
else:
    st.info("Select an active task from the sidebar to view the dashboard.")
