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

# --- Task to Emoji Mapping ---
TASK_EMOJI_MAP = {
    "Walkout Music": "🎵",
    "Stats": "📊",
    "Black Screen Video": "⬛",
    "Video Shooting": "🎥",
    "Photoshoot": "📸",
    "Blood Test": "🩸",
}


# --- Data Loading and Connection Functions ---
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
        df[FC_ORDER_COL] = pd.to_numeric(df[FC_ORDER_COL], errors="coerce")
        df[FC_CORNER_COL] = df[FC_CORNER_COL].astype(str).str.strip().str.lower()
        df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip()
        df[FC_PICTURE_COL] = df[FC_PICTURE_COL].astype(str).str.strip().fillna("")
        if FC_ATHLETE_ID_COL in df.columns:
            df[FC_ATHLETE_ID_COL] = df[FC_ATHLETE_ID_COL].astype(str).str.strip().fillna("")
        else:
            st.error(f"CRITICAL: Column '{FC_ATHLETE_ID_COL}' not found in Fightcard.")
            df[FC_ATHLETE_ID_COL] = ""
        return df.dropna(subset=[FC_FIGHTER_COL, FC_ORDER_COL, FC_ATHLETE_ID_COL])
    except Exception as e: st.error(f"Error loading Fightcard: {e}"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame()
        cols_to_process = [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL]
        for col in cols_to_process:
            if col in df_att.columns: df_att[col] = df_att[col].astype(str).str.strip()
            else: df_att[col] = None
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

def get_task_status(athlete_id, task_name, df_attendance):
    if df_attendance.empty or pd.isna(athlete_id) or str(athlete_id).strip()=="" or not task_name:
        return STATUS_INFO.get("Pending", {"class": DEFAULT_STATUS_CLASS, "text": "Pending"})
    relevant_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == str(athlete_id).strip()) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip() == str(task_name).strip())]
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

def calculate_task_summary(df_processed, task_list):
    summary = {}
    for task in task_list:
        summary[task] = {"Done": 0, "Requested": 0}
        for corner in ["Azul", "Vermelho"]:
            col_name = f"{task} ({corner})"
            if col_name in df_processed.columns:
                status_texts = df_processed[col_name].apply(lambda x: x.get('text', 'Pending'))
                counts = status_texts.value_counts()
                for status, count in counts.items():
                    if status == "Done": summary[task]["Done"] += count
                    elif status == "Requested": summary[task]["Requested"] += count
    return summary

def generate_mirrored_html_dashboard(df_processed, task_list):
    header_html = "<thead><tr>"
    header_html += f"<th class='blue-corner-header' colspan='{len(task_list) + 2}'>BLUE CORNER</th>"
    header_html += "<th class='center-col-header' rowspan=2>FIGHT<br>INFO</th>"
    header_html += f"<th class='red-corner-header' colspan='{len(task_list) + 2}'>RED CORNER</th>"
    header_html += "</tr><tr>"
    for task in reversed(task_list):
        emoji = TASK_EMOJI_MAP.get(task, task[0])
        header_html += f"<th class='task-header' title='{task}'>{emoji}</th>"
    header_html += "<th>Fighter</th><th>Photo</th>"
    header_html += "<th>Photo</th><th>Fighter</th>"
    for task in task_list:
        emoji = TASK_EMOJI_MAP.get(task, task[0])
        header_html += f"<th class='task-header' title='{task}'>{emoji}</th>"
    header_html += "</tr></thead>"

    body_html = "<tbody>"
    for _, row in df_processed.iterrows():
        body_html += "<tr>"
        for task in reversed(task_list):
            status = row.get(f'{task} (Azul)', get_task_status(None, task, pd.DataFrame()))
            body_html += f"<td class='status-cell {status['class']}' title='{status['text']}'></td>"

        body_html += f"<td class='fighter-name fighter-name-blue'>{row.get('Lutador Azul', 'N/A')}</td>"
        body_html += f"<td class='photo-cell'><img class='fighter-img' src='{row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')}'/></td>"

        fight_info_html = f"""
            <div class='fight-info-number'>{row.get('Fight #', '')}</div>
            <div class='fight-info-event'>{row.get('Event', '')}</div>
            <div class='fight-info-division'>{row.get('Division', '')}</div>
        """
        body_html += f"<td class='center-info-cell'>{fight_info_html}</td>"

        body_html += f"<td class='photo-cell'><img class='fighter-img' src='{row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')}'/></td>"
        body_html += f"<td class='fighter-name fighter-name-red'>{row.get('Lutador Vermelho', 'N/A')}</td>"

        for task in task_list:
            status = row.get(f'{task} (Vermelho)', get_task_status(None, task, pd.DataFrame()))
            body_html += f"<td class='status-cell {status['class']}' title='{status['text']}'></td>"
        body_html += "</tr>"
    body_html += "</tbody>"
    return f"<div class='dashboard-container'><table class='dashboard-table'>{header_html}{body_html}</table></div>"

# --- Streamlit Page Configuration ---
st.set_page_config(layout="wide", page_title="Fight Dashboard")

if 'table_font_size' not in st.session_state:
    st.session_state.table_font_size = 18

# --- NEW AND FINAL CSS FUNCTION ---
def get_dashboard_style(font_size_px):
    img_size = font_size_px * 3.5
    cell_padding = font_size_px * 0.5
    fighter_font_size = font_size_px * 2.0 

    return f"""
    <style>
        div[data-testid="stToolbar"] {{ visibility: hidden; height: 0%; position: fixed; }}
        div[data-testid="stDecoration"] {{ visibility: hidden; height: 0%; position: fixed; }}
        div[data-testid="stStatusWidget"] {{ visibility: hidden; height: 0%; position: fixed; }}
        #MainMenu {{ visibility: hidden; height: 0%; }}
        header {{ visibility: hidden; height: 0%; }}
        .block-container {{ padding-top: 1rem !important; padding-bottom: 0rem !important; }}
        
        .dashboard-container {{ font-family: 'Segoe UI', sans-serif; }}
        .dashboard-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background-color: #2a2a2e;
            color: #e1e1e1;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            border-radius: 12px;
            overflow: hidden;
            table-layout: fixed; /* ESSENCIAL PARA O CONTROLE DA LARGURA */
        }}
        .dashboard-table th, .dashboard-table td {{
            border-right: 1px solid #4a4a50;
            border-bottom: 1px solid #4a4a50;
            padding: {cell_padding}px 8px;
            text-align: center;
            vertical-align: middle;
            word-break: break-word;
        }}
        .dashboard-table td {{ font-size: {font_size_px}px !important; }}
        .dashboard-table tr:hover td {{ background-color: #38383c; }}

        .dashboard-table th {{
            background-color: #1c1c1f;
            font-size: 1.5rem;
            font-weight: 600;
            white-space: normal;
        }}
        .blue-corner-header, .red-corner-header, .center-col-header {{
            font-size: 0.8rem !important;
            text-transform: uppercase;
        }}
        .blue-corner-header {{ background-color: #0d2e4e !important; }}
        .red-corner-header {{ background-color: #5a1d1d !important; }}
        .center-col-header {{ background-color: #111 !important; }}

        /* === AJUSTE DE LARGURA CORRIGIDO === */

        /* 1. Definir larguras FIXAS e PEQUENAS para colunas de status e utilitárias */
        .task-header, .status-cell {{
            width: 25px; /* Largura bem pequena e fixa */
        }}
        .photo-cell {{
            width: {img_size + 16}px; /* Largura fixa baseada no tamanho da imagem */
        }}
        .center-info-cell {{
            width: 95px; /* Largura fixa */
            background-color: #333;
            padding: 5px !important;
        }}

        /* 2. NÃO definir largura para a coluna do nome. Ela se expandirá para preencher o espaço. */
        .fighter-name {{
            font-weight: 700;
            font-size: {fighter_font_size}px !important; /* Apenas estilo, sem largura */
            /* A largura será calculada automaticamente pelo table-layout: fixed */
        }}
        .fighter-name-blue {{ text-align: right !important; padding-right: 15px !important; }}
        .fighter-name-red {{ text-align: left !important; padding-left: 15px !important; }}

        /* 3. CORES PERSONALIZADAS */
        .status-done {{ background-color: #556B2F; }} /* Verde Musgo */
        .status-requested {{ background-color: #F0E68C; }} /* Amarelo Pastel */
        
        /* === FIM DAS MUDANÇAS === */
        
        .fighter-img {{
            width: {img_size}px;
            height: {img_size}px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #666;
        }}
        .fight-info-number {{ font-weight: bold; font-size: 1.2em; color: #fff; line-height: 1.2; }}
        .fight-info-event {{ font-style: italic; font-size: 0.8em; color: #ccc; line-height: 1; }}
        .fight-info-division {{ font-style: normal; font-size: 0.85em; color: #ddd; line-height: 1.2; }}

        .status-cell {{ cursor: help; }}
        .status-pending {{ background-color: #dc3545; }}
        .status-neutral {{ background-color: transparent; }}

        .summary-container {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 20px;
            margin-bottom: 20px;
        }}
    </style>
    """

# --- Main Page Content ---
st_autorefresh(interval=60000, key="dash_auto_refresh_v14")

# --- Sidebar Controls ---
st.sidebar.title("Dashboard Controls")
if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
    st.cache_data.clear(); st.toast("Data refreshed!", icon="🎉"); st.rerun()

st.session_state.table_font_size = st.sidebar.slider(
    "Table Font Size (px)",
    min_value=12, max_value=30, value=st.session_state.table_font_size, step=1
)
st.sidebar.markdown("---")

st.markdown(get_dashboard_style(st.session_state.table_font_size), unsafe_allow_html=True)

with st.spinner("Loading data..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    all_tsks = get_task_list()

if df_fc is None or df_fc.empty or not all_tsks:
    st.warning("Could not load Fightcard data or Task List. Please check the spreadsheets."); st.stop()

avail_evs = sorted(df_fc[FC_EVENT_COL].dropna().unique().tolist(), reverse=True)
if not avail_evs: st.warning("No events found in Fightcard data."); st.stop()

sel_ev_opt = st.sidebar.selectbox("Select Event:", options=["All Events"] + avail_evs)

# --- Data Processing and Display Logic ---
df_fc_disp = df_fc.copy()
if sel_ev_opt != "All Events":
    df_fc_disp = df_fc[df_fc[FC_EVENT_COL] == sel_ev_opt]

if df_fc_disp.empty: st.info(f"No fights found for event '{sel_ev_opt}'."); st.stop()

dash_data_list = []
for order, group in df_fc_disp.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby([FC_EVENT_COL, FC_ORDER_COL]):
    ev, f_ord = order
    bl_s = group[group[FC_CORNER_COL] == "blue"].squeeze(axis=0)
    rd_s = group[group[FC_CORNER_COL] == "red"].squeeze(axis=0)
    row_d = {"Event": ev, "Fight #": int(f_ord) if pd.notna(f_ord) else ""}
    for prefix, series in [("Azul", bl_s), ("Vermelho", rd_s)]:
        if isinstance(series, pd.Series) and not series.empty:
            name, id, pic = series.get(FC_FIGHTER_COL, "N/A"), series.get(FC_ATHLETE_ID_COL, ""), series.get(FC_PICTURE_COL, "")
            row_d[f"Foto {prefix}"] = pic if isinstance(pic, str) and pic.startswith("http") else ""
            row_d[f"Lutador {prefix}"] = f"{name}"
            for task in all_tsks: row_d[f"{task} ({prefix})"] = get_task_status(id, task, df_att)
        else:
            row_d[f"Foto {prefix}"], row_d[f"Lutador {prefix}"] = "", "N/A"
            for task in all_tsks: row_d[f"{task} ({prefix})"] = get_task_status(None, task, df_att)
    row_d["Division"] = bl_s.get(FC_DIVISION_COL, rd_s.get(FC_DIVISION_COL, "N/A")) if isinstance(bl_s, pd.Series) else (rd_s.get(FC_DIVISION_COL, "N/A") if isinstance(rd_s, pd.Series) else "N/A")
    dash_data_list.append(row_d)

if dash_data_list:
    df_dash_processed = pd.DataFrame(dash_data_list)
    
    task_summary = calculate_task_summary(df_dash_processed, all_tsks)
    
    st.write("<div class='summary-container'>", unsafe_allow_html=True)
    cols = st.columns(len(all_tsks))
    col_index = 0
    for task, data in task_summary.items():
        emoji = TASK_EMOJI_MAP.get(task, "")
        with cols[col_index]:
            st.metric(
                label=f"{emoji} {task}",
                value=f"{data.get('Done', 0)} Done",
                delta=f"{data.get('Requested', 0)} Req.",
                delta_color="off"
            )
        col_index += 1
    st.write("</div>", unsafe_allow_html=True)

    html_table = generate_mirrored_html_dashboard(df_dash_processed, all_tsks)
    st.markdown(html_table, unsafe_allow_html=True)

else:
    st.info(f"No fights processed for '{sel_ev_opt}'.")
    
st.markdown(f"<p style='font-size: 0.8em; text-align: center; color: #888;'>*Dashboard updated at: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*</p>", unsafe_allow_html=True, help="This page auto-refreshes every 60 seconds.")
