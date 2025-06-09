# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID"
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"

FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_ATHLETE_ID_COL = "AthleteID"
FC_CORNER_COL = "Corner"
FC_ORDER_COL = "FightOrder"
FC_PICTURE_COL = "Picture"
FC_DIVISION_COL = "Division"

STATUS_INFO = {
    "Done": {"class": "status-done", "text": "Done"},
    "Requested": {"class": "status-requested", "text": "Requested"},
    "---": {"class": "status-neutral", "text": "---"},
    "Pending": {"class": "status-pending", "text": "Pending"},
    "Pendente": {"class": "status-pending", "text": "Pending"},
    "Não Registrado": {"class": "status-pending", "text": "Not Registered"},
    "Não Solicitado": {"class": "status-neutral", "text": "Not Requested"},
}
DEFAULT_STATUS_CLASS = "status-pending"

TASK_EMOJIS = {
    "Walkout Music": "🎵",
    "Stats": "📊",
    "Black Screen Video": "🎬",
    "Video Shooting": "📹",
    "Photoshoot": "📸",
    "Blood Test": "💉"
}

@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1:
            return []
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        raw_tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        return raw_tasks
    except Exception as e:
        st.error(f"Error loading TaskList from Config: {e}")
        return []

def get_task_headers(task_list):
    return [TASK_EMOJIS.get(t, t) for t in task_list]

# ⚠️ Exemplo de uso onde for necessário:
# task_headers_display = get_task_headers(all_tsks)
# for task, display in zip(task_list, task_headers_display):
#     use display como label na interface ou header

# 🧑‍🎨 CSS:
# .fighter-name {
#     width: 20%;
#     font-size: maior (eg. 24px se font_size_px = 12)
# }
# .task-header, .status-cell {
#     width: 4%;
# }

# A partir daqui, substitua headers e use task_headers_display nos locais apropriados do HTML e Streamlit.
