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

# --- NOVA FUNÇÃO DE GERAÇÃO DE HTML USANDO CSS GRID ---
def generate_mirrored_html_dashboard(df_processed, task_list):
    num_tasks = len(task_list)
    
    html = "<div class='dashboard-grid'>"

    # --- HEADER ROW 1 (CABEÇALHOS PRINCIPAIS) ---
    html += f"<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span {num_tasks + 2};'>BLUE CORNER</div>"
    html += f"<div class='grid-item grid-header center-col-header' style='grid-column: {num_tasks + 3}; grid-row: 1 / span 2;'>FIGHT<br>INFO</div>"
    html += f"<div class='grid-item grid-header red-corner-header' style='grid-column: {num_tasks + 4} / span {num_tasks + 2};'>RED CORNER</div>"
    
    # --- HEADER ROW 2 (ÍCONES E TÍTULOS) ---
    for task in reversed(task_list):
        emoji = TASK_EMOJI_MAP.get(task, task[0])
        html += f"<div class='grid-item grid-header task-header' title='{task}'>{emoji}</div>"
    html += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    html += "<div class='grid-item grid-header photo-header'>Photo</div>"
    # A coluna central já foi posicionada com 'grid-row: span 2', então não adicionamos um placeholder aqui.
    html += "<div class='grid-item grid-header photo-header'>Photo</div>"
    html += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    for task in task_list:
        emoji = TASK_EMOJI_MAP.get(task, task[0])
        html += f"<div class='grid-item grid-header task-header' title='{task}'>{emoji}</div>"

    # --- DATA ROWS (LINHAS DE DADOS) ---
    for _, row in df_processed.iterrows():
        # A grade cuidará do layout, apenas cuspimos as células em ordem.
        for task in reversed(task_list):
            status = row.get(f'{task} (Azul)', get_task_status(None, task, pd.DataFrame()))
            html += f"<div class='grid-item status-cell {status['class']}' title='{status['text']}'></div>"
        
        html += f"<div class='grid-item fighter-name fighter-name-blue'>{row.get('Lutador Azul', 'N/A')}</div>"
        html += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')}'/></div>"

        fight_info_html = f"<div class='fight-info-number'>{row.get('Fight #', '')}</div><div class='fight-info-event'>{row.get('Event', '')}</div><div class='fight-info-division'>{row.get('Division', '')}</div>"
        html += f"<div class='grid-item center-info-cell'>{fight_info_html}</div>"

        html += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')}'/></div>"
        html += f"<div class='grid-item fighter-name fighter-name-red'>{row.get('Lutador Vermelho', 'N/A')}</div>"
        
        for task in task_list:
            status = row.get(f'{task} (Vermelho)', get_task_status(None, task, pd.DataFrame()))
            html += f"<div class='grid-item status-cell {status['class']}' title='{status['text']}'></div>"

    html += "</div>"
    return html

# --- Streamlit Page Configuration ---
st.set_page_config(layout="wide", page_title="Fight Dashboard")

if 'table_font_size' not in st.session_state:
    st.session_state.table_font_size = 18

# --- NOVA FUNÇÃO DE ESTILO USANDO CSS GRID ---
def get_dashboard_style(font_size_px, num_tasks=6):
    img_size = font_size_px * 3.5
    cell_padding = font_size_px * 0.5
    fighter_font_size = font_size_px * 1.8 

    # Definição explícita e robusta das colunas da grade
    task_col_width = "30px"
    photo_col_width = "90px"
    center_col_width = "100px"
    fighter_col_width = "1fr"  # '1fr' significa 1 fração do espaço livre. Isso faz com que as colunas do nome se expandam.

    # Cria a string do template de colunas
    grid_template_columns = " ".join(
        [task_col_width] * num_tasks + 
        [fighter_col_width, photo_col_width, center_col_width, photo_col_width, fighter_col_width] + 
        [task_col_width] * num_tasks
    )

    return f"""
    <style>
        div[data-testid="stToolbar"] {{ visibility: hidden; height: 0%; position: fixed; }}
        div[data-testid="stDecoration"] {{ visibility: hidden; height: 0%; position: fixed; }}
        div[data-testid="stStatusWidget"] {{ visibility: hidden; height: 0%; position: fixed; }}
        #MainMenu {{ visibility: hidden; height: 0%; }}
        header {{ visibility: hidden; height: 0%; }}
        .block-container {{ padding-top: 1rem !important; padding-bottom: 0rem !important; }}
        
        .dashboard-grid {{
            display: grid;
            grid-template-columns: {grid_template_columns};
            gap: 1px;
            background-color: #4a4a50; /* A cor do 'gap' se torna a borda */
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            margin-top: 1rem;
        }}
        
        .grid-item {{
            background-color: #2a2a2e;
            color: #e1e1e1;
            padding: {cell_padding}px 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: {img_size + (cell_padding * 2)}px;
            word-break: break-word;
        }}
        
        .grid-item:hover {{
             background-color: #38383c;
        }}
        
        .grid-header {{
            background-color: #1c1c1f;
            font-weight: 600;
            font-size: 1rem;
            min-height: auto;
        }}

        .blue-corner-header {{ background-color: #0d2e4e !important; }}
        .red-corner-header {{ background-color: #5a1d1d !important; }}
        .center-col-header {{ background-color: #111 !important; }}

        .fighter-name {{
            font-weight: 700;
            font-size: {fighter_font_size}px !important;
        }}
        .fighter-name-blue {{ justify-content: flex-end !important; text-align: right; padding-right: 15px; }}
        .fighter-name-red {{ justify-content: flex-start !important; text-align: left; padding-left: 15px; }}

        .photo-cell {{
             padding: 4px;
        }}

        .center-info-cell {{
            flex-direction: column;
            line-height: 1.2;
            background-color: #333;
        }}
        
        .status-done {{ background-color: #556B2F; }}
        .status-requested {{ background-color: #F0E68C; }}
        .status-pending {{ background-color: #dc3545; }}
        .status-neutral, .status-neutral:hover {{ background-color: transparent !important; }}
        .status-cell {{ cursor: help; }}

        .fighter-img {{
            width: {img_size}px;
            height: {img_size}px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #666;
        }}
        .fight-info-number {{ font-weight: bold; font-size: 1.2em; color: #fff; }}
        .fight-info-event {{ font-style: italic; font-size: 0.8em; color: #ccc; }}
        .fight-info-division {{ font-style: normal; font-size: 0.85em; color: #ddd; }}

        .summary-container {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 20px; }}
    </style>
    """

# --- Main Page Content ---
st_autorefresh(interval=60000, key="dash_auto_refresh_v14")

st.sidebar.title("Dashboard Controls")
if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
    st.cache_data.clear()
    st.toast("Data refreshed!", icon="🎉")
    st.rerun()

st.session_state.table_font_size = st.sidebar.slider(
    "Table Font Size (px)", min_value=12, max_value=30, value=st.session_state.table_font_size, step=1
)
st.sidebar.markdown("---")

with st.spinner("Loading data..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    all_tsks = get_task_list()

if df_fc is None or df_fc.empty or not all_tsks:
    st.warning("Could not load Fightcard data or Task List. Please check the spreadsheets.")
    st.stop()

# Injeta o CSS na página
st.markdown(get_dashboard_style(st.session_state.table_font_size, len(all_tsks)), unsafe_allow_html=True)

avail_evs = sorted(df_fc[FC_EVENT_COL].dropna().unique().tolist(), reverse=True)
if not avail_evs:
    st.warning("No events found in Fightcard data.")
    st.stop()

sel_ev_opt = st.sidebar.selectbox("Select Event:", options=["All Events"] + avail_evs)

df_fc_disp = df_fc.copy()
if sel_ev_opt != "All Events":
    df_fc_disp = df_fc[df_fc[FC_EVENT_COL] == sel_ev_opt]

if df_fc_disp.empty:
    st.info(f"No fights found for event '{sel_ev_opt}'.")
    st.stop()

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

    # Usa a nova função para gerar o HTML
    html_grid = generate_mirrored_html_dashboard(df_dash_processed, all_tsks)
    st.markdown(html_grid, unsafe_allow_html=True)

else:
    st.info(f"No fights processed for '{sel_ev_opt}'.")
    
st.markdown(f"<p style='font-size: 0.8em; text-align: center; color: #888;'>*Dashboard updated at: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*</p>", unsafe_allow_html=True, help="This page auto-refreshes every 60 seconds.")
