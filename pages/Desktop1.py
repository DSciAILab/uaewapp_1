# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
from streamlit_autorefresh import st_autorefresh 

# --- Constants (unchanged) ---
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

# --- Data Loading and Connection Functions (unchanged) ---
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
        summary[task] = {"Done": 0, "Requested": 0, "Pending": 0}
        for corner in ["Azul", "Vermelho"]:
            col_name = f"{task} ({corner})"
            if col_name in df_processed.columns:
                status_texts = df_processed[col_name].apply(lambda x: x.get('text', 'Pending'))
                counts = status_texts.value_counts()
                for status, count in counts.items():
                    if status == "Done": summary[task]["Done"] += count
                    elif status == "Requested": summary[task]["Requested"] += count
                    elif status in ["Pending", "Not Registered"]: summary[task]["Pending"] += count
    return summary

def generate_mirrored_html_dashboard(df_processed, task_list):
    header_html = "<thead><tr>"
    header_html += f"<th class='blue-corner-header' colspan='{len(task_list) + 2}'>BLUE CORNER</th>"
    header_html += "<th class='center-col-header' rowspan=2>FIGHT #</th>"
    header_html += "<th class='center-col-header' rowspan=2>EVENT</th>"
    header_html += "<th class='center-col-header' rowspan=2>DIVISION</th>"
    header_html += f"<th class='red-corner-header' colspan='{len(task_list) + 2}'>RED CORNER</th>"
    header_html += "</tr><tr>"
    for task in reversed(task_list): header_html += f"<th class='task-header'>{task}</th>"
    header_html += "<th>Fighter</th><th>Photo</th>"
    header_html += "<th>Photo</th><th>Fighter</th>"
    for task in task_list: header_html += f"<th class='task-header'>{task}</th>"
    header_html += "</tr></thead>"
    body_html = "<tbody>"
    for _, row in df_processed.iterrows():
        body_html += "<tr>"
        for task in reversed(task_list):
            status = row.get(f'{task} (Azul)', get_task_status(None, task, pd.DataFrame()))
            body_html += f"<td class='status-cell {status['class']}' title='{status['text']}'></td>"
        body_html += f"<td class='fighter-name fighter-name-blue'>{row.get('Lutador Azul', 'N/A')}</td>"
        body_html += f"<td><img class='fighter-img' src='{row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')}'/></td>"
        body_html += f"<td class='fight-number-cell'>{row.get('Fight #', '')}</td>"
        body_html += f"<td class='event-cell'>{row.get('Event', '')}</td>"
        body_html += f"<td class='division-cell'>{row.get('Division', '')}</td>"
        body_html += f"<td><img class='fighter-img' src='{row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')}'/></td>"
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
    st.session_state.table_font_size = 16

def get_dashboard_style(font_size_px):
    img_size = font_size_px * 4
    cell_padding = font_size_px * 0.8
    
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
            table-layout: fixed;
        }}
        .dashboard-table th, .dashboard-table td {{
            border-right: 1px solid #4a4a50;
            border-bottom: 1px solid #4a4a50;
            padding: {cell_padding}px 8px;
            text-align: center;
            vertical-align: middle;
            word-break: break-word; /* ATUALIZAÇÃO: Garante que texto longo quebre a linha */
        }}
        .dashboard-table th {{
            background-color: #1c1c1f;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: normal;
        }}
        .blue-corner-header {{ background-color: #0d2e4e !important; }}
        .red-corner-header {{ background-color: #5a1d1d !important; }}
        .center-col-header {{ background-color: #111 !important; }}
        .dashboard-table td {{ font-size: {font_size_px}px !important; }}
        .dashboard-table tr:hover td {{ background-color: #38383c; }}
        .fighter-img {{
            width: {img_size}px;
            height: {img_size}px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #666;
        }}
        .fighter-name {{ font-weight: 600; width: 250px; }}
        .fighter-name-blue {{ text-align: right !important; padding-right: 15px !important; }}
        .fighter-name-red {{ text-align: left !important; padding-left: 15px !important; }}
        
        .fight-number-cell, .event-cell, .division-cell {{ background-color: #333; }}
        
        /* ATUALIZAÇÃO: Otimização das colunas centrais para serem mais compactas */
        .fight-number-cell {{ 
            width: 60px; /* Reduzido de 70px */
            font-weight: bold; 
            font-size: 1.1em; /* Reduzido de 1.2em */
        }}
        .event-cell {{ 
            width: 100px; /* Reduzido de 120px */
            font-style: italic; 
            font-size: 0.8em; /* Reduzido de 0.85em */
            color: #ccc; 
        }}
        .division-cell {{ 
            width: 110px; /* Reduzido de 150px */
            font-style: italic; 
            font-size: 0.9em;
        }}
        
        .status-cell, .task-header {{
            width: 8%;
        }}
        .status-cell {{ cursor: help; }}
        .status-done {{ background-color: #28a745; }}
        .status-requested {{ background-color: #ffc107; }}
        .status-pending {{ background-color: #dc3545; }}
        .status-neutral {{ background-color: transparent; }}
        
        .compact-header {{ margin-block-start: 0em; margin-block-end: 0.5em; }}
    </style>
    """

# --- Main Page Content ---
st.markdown("<h1 style='text-align: center; margin-block-start: 0em; margin-block-end: 0.5em;'>FIGHTER & TASK DASHBOARD</h1>", unsafe_allow_html=True)
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
            row_d[f"Lutador {prefix}"] = f"{id} - {name}" if name != "N/A" else "N/A"
            for task in all_tsks: row_d[f"{task} ({prefix})"] = get_task_status(id, task, df_att)
        else:
            row_d[f"Foto {prefix}"], row_d[f"Lutador {prefix}"] = "", "N/A"
            for task in all_tsks: row_d[f"{task} ({prefix})"] = get_task_status(None, task, df_att)
    row_d["Division"] = bl_s.get(FC_DIVISION_COL, rd_s.get(FC_DIVISION_COL, "N/A")) if isinstance(bl_s, pd.Series) else (rd_s.get(FC_DIVISION_COL, "N/A") if isinstance(rd_s, pd.Series) else "N/A")
    dash_data_list.append(row_d)

if dash_data_list:
    df_dash_processed = pd.DataFrame(dash_data_list)
    
    st.markdown("<h3 class='compact-header'>Overall Task Status</h3>", unsafe_allow_html=True)
    task_summary = calculate_task_summary(df_dash_processed, all_tsks)
    
    MAX_COLS = len(all_tsks) if all_tsks else 1
    cols = st.columns(MAX_COLS)
    col_index = 0
    
    for task, data in task_summary.items():
        if col_index < len(cols):
            with cols[col_index]:
                with st.container(border=True):
                    st.markdown(f"<h3 style='text-align: center; margin-bottom: 10px; font-size: 1.1em;'>{task}</h3>", unsafe_allow_html=True)
                    m_cols = st.columns(3)
                    m_cols[0].metric("✅ Done", data.get("Done", 0))
                    m_cols[1].metric("🟨 Requested", data.get("Requested", 0))
                    m_cols[2].metric("🟥 Pending", data.get("Pending", 0))
            col_index += 1
    
    st.markdown(f"<h3 class='compact-header'>Fight Status: {sel_ev_opt}</h3>", unsafe_allow_html=True)
    html_table = generate_mirrored_html_dashboard(df_dash_processed, all_tsks)
    st.markdown(html_table, unsafe_allow_html=True)
    
else:
    st.info(f"No fights processed for '{sel_ev_opt}'.")
    
st.markdown(f"<p style='font-size: 0.8em; text-align: center; color: #888;'>*Dashboard updated at: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*</p>", unsafe_allow_html=True, help="This page auto-refreshes every 60 seconds.")
