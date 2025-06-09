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

# No restante do script, onde antes havia o uso direto de all_tsks, usar:
# task_headers_display = get_task_headers(all_tsks)
# E iterar com zip(all_tsks, task_headers_display) para construir headers com emojis e manter associação com os dados.

# Exemplo de aplicação na geração de tabela HTML:
# for task, display_name in zip(reversed(task_list), reversed(task_headers_display)):
#     header_html += f"<th class='task-header'>{display_name}</th>"
#     ...
#     # idem para as colunas vermelhas

# E no CSS:
# .fighter-name { width: 20%; font-size: maior }
# .task-header, .status-cell { width: 4%; }
