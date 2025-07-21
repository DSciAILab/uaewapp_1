# pages/DashboardNovo.py

# --- Importações de Bibliotecas ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÃO DA PÁGINA ---
if 'layout_mode' not in st.session_state:
    st.session_state.layout_mode = "wide"

st.set_page_config(layout=st.session_state.layout_mode, page_title="Fight Dashboard")


# --- Constantes Globais ---
MAIN_SHEET_NAME = "UAEW_App"
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID"
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"
ATTENDANCE_EVENT_COL = "Event"
FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_ATHLETE_ID_COL = "AthleteID"
FC_CORNER_COL = "Corner"
FC_ORDER_COL = "FightOrder"
FC_PICTURE_COL = "Picture"
FC_DIVISION_COL = "Division"

# Mapeamento de Status para Classes CSS e Texto
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

# Mapeamento de Tarefas para Emojis
TASK_EMOJI_MAP = {
    "Walkout Music": "🎵", "Stats": "📊", "Black Screen Video": "⬛",
    "Video Shooting": "🎥", "Photoshoot": "📸", "Blood Test": "🩸",
}

# --- Funções de Carregamento de Dados e Conexão ---

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

        # Limpeza e conversão de tipos
        df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip()
        df[FC_CORNER_COL] = df[FC_CORNER_COL].astype(str).str.strip().str.lower()
        df[FC_PICTURE_COL] = df[FC_PICTURE_COL].astype(str).str.strip().fillna("")
        df[FC_ORDER_COL] = pd.to_numeric(df[FC_ORDER_COL], errors="coerce") # Converte para número, erros viram NaN

        # Garante que a coluna AthleteID exista e seja tratada como string
        if FC_ATHLETE_ID_COL in df.columns:
            df[FC_ATHLETE_ID_COL] = df[FC_ATHLETE_ID_COL].astype(str).str.strip().fillna("")
        else:
            st.error(f"CRITICAL: Column '{FC_ATHLETE_ID_COL}' not found in Fightcard.")
            df[FC_ATHLETE_ID_COL] = ""

        # --- INÍCIO DA CORREÇÃO ---
        # Removemos o FC_ORDER_COL do dropna.
        # Agora, só descartamos uma linha se o nome do lutador OU seu ID estiverem faltando.
        # Isso impede que um lutador com FightOrder em branco seja removido.
        df.dropna(subset=[FC_FIGHTER_COL, FC_ATHLETE_ID_COL], inplace=True)
        # --- FIM DA CORREÇÃO ---

        # Preenche qualquer FightOrder NaN com um número alto (ex: 999) para que apareçam no final
        df[FC_ORDER_COL] = df[FC_ORDER_COL].fillna(999)

        return df

    except Exception as e:
        st.error(f"Error loading Fightcard: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame()
        cols_to_process = [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_EVENT_COL]
        for col in cols_to_process:
            if col in df_att.columns: df_att[col] = df_att[col].astype(str).str.strip()
            else: df_att[col] = ""
        return df_att
    except Exception as e: st.error(f"Error loading Attendance: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return []
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception as e: st.error(f"Error loading TaskList from Config: {e}"); return []

# --- Funções de Lógica e Processamento ---
def get_task_status(athlete_id, task_name, event_name, df_attendance):
    if df_attendance.empty or pd.isna(athlete_id) or str(athlete_id).strip() == "" or not task_name or not event_name:
        return STATUS_INFO.get("Pending", {"class": DEFAULT_STATUS_CLASS, "text": "Pending"})

    relevant_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == str(athlete_id).strip()) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip() == str(task_name).strip()) &
        (df_attendance[ATTENDANCE_EVENT_COL].astype(str).str.strip() == str(event_name).strip())
    ]
    
    if relevant_records.empty: return STATUS_INFO.get("Pending", {"class": DEFAULT_STATUS_CLASS, "text": "Pending"})
    
    latest_status_str = relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            rel_sorted = relevant_records.copy()
            rel_sorted["Timestamp_dt"]=pd.to_datetime(rel_sorted[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            if rel_sorted["Timestamp_dt"].notna().any():
                latest_status_str = rel_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0][ATTENDANCE_STATUS_COL]
        except: pass
    return STATUS_INFO.get(str(latest_status_str).strip(), {"class": DEFAULT_STATUS_CLASS, "text": latest_status_str})

# --- Geração da Interface (HTML & CSS) ---
def generate_mirrored_html_dashboard(df_processed, task_list):
    num_tasks = len(task_list)
    html = "<div class='dashboard-grid'>"
    if num_tasks > 0:
        html += f"<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span {num_tasks + 2};'>BLUE CORNER</div>"
        html += f"<div class='grid-item grid-header center-col-header' style='grid-column: {num_tasks + 3}; grid-row: 1 / span 2;'>FIGHT<br>INFO</div>"
        html += f"<div class='grid-item grid-header red-corner-header' style='grid-column: {num_tasks + 4} / span {num_tasks + 2};'>RED CORNER</div>"
        for task in reversed(task_list):
            emoji = TASK_EMOJI_MAP.get(task, task[0])
            html += f"<div class='grid-item grid-header task-header' title='{task}'>{emoji}</div>"
    else:
        html += f"<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span 2;'>BLUE CORNER</div>"
        html += f"<div class='grid-item grid-header center-col-header' style='grid-column: 3; grid-row: 1 / span 2;'>FIGHT<br>INFO</div>"
        html += f"<div class='grid-item grid-header red-corner-header' style='grid-column: 4 / span 2;'>RED CORNER</div>"

    html += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    html += "<div class='grid-item grid-header photo-header'>Photo</div>"
    html += "<div class='grid-item grid-header photo-header'>Photo</div>"
    html += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    if num_tasks > 0:
        for task in task_list:
            emoji = TASK_EMOJI_MAP.get(task, task[0])
            html += f"<div class='grid-item grid-header task-header' title='{task}'>{emoji}</div>"

    for _, row in df_processed.iterrows():
        for task in reversed(task_list):
            status = row.get(f'{task} (Azul)', get_task_status(None, task, row.get('Event'), pd.DataFrame()))
            html += f"<div class='grid-item status-cell {status['class']}' title='{status['text']}'></div>"
        html += f"<div class='grid-item fighter-name fighter-name-blue'>{row.get('Lutador Azul', 'N/A')}</div>"
        html += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')}'/></div>"
        fight_info_html = f"<div class='fight-info-number'>{row.get('Fight #', '')}</div><div class='fight-info-event'>{row.get('Event', '')}</div><div class='fight-info-division'>{row.get('Division', '')}</div>"
        html += f"<div class='grid-item center-info-cell'>{fight_info_html}</div>"
        html += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')}'/></div>"
        html += f"<div class='grid-item fighter-name fighter-name-red'>{row.get('Lutador Vermelho', 'N/A')}</div>"
        for task in task_list:
            status = row.get(f'{task} (Vermelho)', get_task_status(None, task, row.get('Event'), pd.DataFrame()))
            html += f"<div class='grid-item status-cell {status['class']}' title='{status['text']}'></div>"
    html += "</div>"
    return html

def get_dashboard_style(font_size_px, num_tasks, fighter_width_pc, division_width_pc, division_font_size_px):
    img_size = font_size_px * 3.5
    cell_padding = font_size_px * 0.5
    fighter_font_size = font_size_px * 1.8
    photo_pc = 6.0
    
    if num_tasks > 0:
        used_space = (fighter_width_pc * 2) + division_width_pc + (photo_pc * 2)
        remaining_space_for_tasks = 100 - used_space
        num_total_task_cols = num_tasks * 2
        task_pc = (remaining_space_for_tasks / num_total_task_cols) if num_total_task_cols > 0 else 0
        if task_pc < 0: task_pc = 0
        grid_template_columns = " ".join(
            [f"{task_pc}%"] * num_tasks +
            [f"{fighter_width_pc}%", f"{photo_pc}%", f"{division_width_pc}%", f"{photo_pc}%", f"{fighter_
