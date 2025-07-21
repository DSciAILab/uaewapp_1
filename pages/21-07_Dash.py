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
            status = row.get(f'{task} (Azul)', get_task_status(None, task, row.get('Event'), pd.DataFrame())) # Passando o evento da linha
            html += f"<div class='grid-item status-cell {status['class']}' title='{status['text']}'></div>"
        html += f"<div class='grid-item fighter-name fighter-name-blue'>{row.get('Lutador Azul', 'N/A')}</div>"
        html += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')}'/></div>"
        fight_info_html = f"<div class='fight-info-number'>{row.get('Fight #', '')}</div><div class='fight-info-event'>{row.get('Event', '')}</div><div class='fight-info-division'>{row.get('Division', '')}</div>"
        html += f"<div class='grid-item center-info-cell'>{fight_info_html}</div>"
        html += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')}'/></div>"
        html += f"<div class='grid-item fighter-name fighter-name-red'>{row.get('Lutador Vermelho', 'N/A')}</div>"
        for task in task_list:
            status = row.get(f'{task} (Vermelho)', get_task_status(None, task, row.get('Event'), pd.DataFrame())) # Passando o evento da linha
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
            [f"{fighter_width_pc}%", f"{photo_pc}%", f"{division_width_pc}%", f"{photo_pc}%", f"{fighter_width_pc}%"] +
            [f"{task_pc}%"] * num_tasks
        )
    else:
        fighter_width_no_tasks = 35
        division_width_no_tasks = 18
        photo_pc_no_tasks = 6
        grid_template_columns = f"{fighter_width_no_tasks}% {photo_pc_no_tasks}% {division_width_no_tasks}% {photo_pc_no_tasks}% {fighter_width_no_tasks}%"

    return f"""
    <style>
        div[data-testid="stToolbar"], div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"], #MainMenu, header {{
            visibility: hidden; height: 0%; position: fixed;
        }}
        .block-container {{ padding-top: 1rem !important; padding-bottom: 0rem !important; }}
        .dashboard-grid {{
            display: grid;
            grid-template-columns: {grid_template_columns};
            gap: 1px;
            background-color: #4a4a50;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            margin-top: 1rem;
        }}
        .grid-item {{
            background-color: #2a2a2e; color: #e1e1e1;
            padding: {cell_padding}px 8px; display: flex; align-items: center; justify-content: center;
            min-height: {img_size + (cell_padding * 2)}px; word-break: break-word;
        }}
        .grid-item:hover {{ background-color: #38383c; }}
        .grid-header {{
            background-color: #1c1c1f; font-weight: 600; font-size: 1rem; min-height: auto;
        }}
        .blue-corner-header {{ background-color: #0d2e4e !important; }}
        .red-corner-header {{ background-color: #5a1d1d !important; }}
        .center-col-header {{ background-color: #111 !important; }}
        .fighter-name {{
            font-weight: 700; font-size: {fighter_font_size}px !important;
        }}
        .fighter-name-blue {{ justify-content: flex-end !important; text-align: right; padding-right: 15px; }}
        .fighter-name-red {{ justify-content: flex-start !important; text-align: left; padding-left: 15px; }}
        .center-info-cell {{ flex-direction: column; line-height: 1.3; background-color: #333; }}
        .status-done {{ background-color: #4A6D2F; }}
        .status-requested {{ background-color: #FF8C00; }}
        .status-pending {{ background-color: #dc3545; }}
        .status-neutral, .status-neutral:hover {{ background-color: transparent !important; }}
        .status-cell {{ cursor: help; }}
        .fighter-img {{
            width: {img_size}px; height: {img_size}px;
            border-radius: 50%; object-fit: cover; border: 2px solid #666;
        }}
        .fight-info-number, .fight-info-event, .fight-info-division {{
            font-size: {division_font_size_px}px !important;
        }}
        .fight-info-number {{ font-weight: bold; color: #fff; }}
        .fight-info-event {{ font-style: italic; color: #ccc; }}
        .fight-info-division {{ font-style: normal; color: #ddd; }}
    </style>
    """


# --- Aplicação Principal do Streamlit ---

st_autorefresh(interval=60000, key="dash_auto_refresh_v14")

with st.spinner("Loading data..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    all_tsks = get_task_list()

# --- Controles da Barra Lateral (Sidebar) ---
st.sidebar.title("Dashboard Controls")
if st.sidebar.button("🔄 Refresh Now", use_container_width=True): st.cache_data.clear(); st.toast("Data refreshed!", icon="🎉"); st.rerun()

avail_evs = sorted(df_fc[FC_EVENT_COL].dropna().unique().tolist(), reverse=True) if not df_fc.empty else []
sel_ev_opt = st.sidebar.selectbox("Select Event:", options=["All Events"] + avail_evs)

st.sidebar.markdown("---")
st.sidebar.subheader("Filtro de Tarefas")
selected_tasks = st.sidebar.multiselect("Selecione as tarefas para monitorar:", options=all_tsks, default=all_tsks)

st.sidebar.markdown("---")
st.sidebar.subheader("Configurações de Exibição")
is_wide_mode = st.sidebar.toggle(
    "Modo Tela Cheia (Wide)",
    value=(st.session_state.layout_mode == "wide"),
    key="layout_toggle"
)
new_layout = "wide" if is_wide_mode else "centered"
if new_layout != st.session_state.layout_mode:
    st.session_state.layout_mode = new_layout
    st.rerun()

if 'table_font_size' not in st.session_state: st.session_state.table_font_size = 18
st.session_state.table_font_size = st.sidebar.slider(
    "Tamanho Geral da Fonte (px)", min_value=10, max_value=30, value=st.session_state.table_font_size, step=1
)
st.sidebar.subheader("Ajustes Finos de Layout")
if 'fighter_width' not in st.session_state: st.session_state.fighter_width = 25
if 'division_width' not in st.session_state: st.session_state.division_width = 10
if 'division_font_size' not in st.session_state: st.session_state.division_font_size = 16
disable_sliders = len(selected_tasks) == 0
st.session_state.fighter_width = st.sidebar.slider(
    "Largura Nome do Lutador (%)", min_value=10, max_value=40, value=st.session_state.fighter_width, step=1,
    disabled=disable_sliders
)
st.session_state.division_width = st.sidebar.slider(
    "Largura Info da Luta (%)", min_value=5, max_value=25, value=st.session_state.division_width, step=1,
    disabled=disable_sliders
)
st.session_state.division_font_size = st.sidebar.slider(
    "Fonte Info da Luta (px)", min_value=10, max_value=30, value=st.session_state.division_font_size, step=1
)
st.sidebar.markdown("---")


# --- Lógica Principal do Dashboard ---
if df_fc.empty:
    st.warning("Could not load Fightcard data. Please check the spreadsheet.")
    st.stop()

st.markdown(get_dashboard_style(st.session_state.table_font_size, len(selected_tasks), st.session_state.fighter_width, st.session_state.division_width, st.session_state.division_font_size), unsafe_allow_html=True)

df_fc_disp = df_fc.copy()
if sel_ev_opt != "All Events":
    df_fc_disp = df_fc[df_fc[FC_EVENT_COL] == sel_ev_opt]

if df_fc_disp.empty:
    st.info(f"No fights found for event '{sel_ev_opt}'.")
    st.stop()

dash_data_list = []
for order, group in df_fc_disp.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby([FC_EVENT_COL, FC_ORDER_COL]):
    ev, f_ord = order
    
    # --- INÍCIO DA CORREÇÃO ---
    # Lógica robusta para extrair dados do lutador.
    # Filtra e pega a primeira linha (.iloc[0]) para evitar erros com dados duplicados.
    
    blue_df = group[group[FC_CORNER_COL] == "blue"]
    bl_s = blue_df.iloc[0] if not blue_df.empty else pd.Series()
    if len(blue_df) > 1:
        st.warning(f"Atenção: Múltiplas entradas para o canto Azul na luta {f_ord} (Evento: {ev}). Usando a primeira.")

    red_df = group[group[FC_CORNER_COL] == "red"]
    rd_s = red_df.iloc[0] if not red_df.empty else pd.Series()
    if len(red_df) > 1:
        st.warning(f"Atenção: Múltiplas entradas para o canto Vermelho na luta {f_ord} (Evento: {ev}). Usando a primeira.")
    # --- FIM DA CORREÇÃO ---

    row_d = {"Event": ev, "Fight #": int(f_ord) if pd.notna(f_ord) else ""}
    
    for prefix, series in [("Azul", bl_s), ("Vermelho", rd_s)]:
        if isinstance(series, pd.Series) and not series.empty:
            name = series.get(FC_FIGHTER_COL, "N/A")
            id = series.get(FC_ATHLETE_ID_COL, "")
            pic = series.get(FC_PICTURE_COL, "")
            row_d[f"Foto {prefix}"] = pic if isinstance(pic, str) and pic.startswith("http") else ""
            row_d[f"Lutador {prefix}"] = f"{name}"
            for task in selected_tasks:
                row_d[f"{task} ({prefix})"] = get_task_status(id, task, ev, df_att)
        else:
            row_d[f"Foto {prefix}"] = ""
            row_d[f"Lutador {prefix}"] = "N/A"
            for task in selected_tasks:
                row_d[f"{task} ({prefix})"] = get_task_status(None, task, ev, df_att)
                
    row_d["Division"] = bl_s.get(FC_DIVISION_COL, rd_s.get(FC_DIVISION_COL, "N/A"))
    dash_data_list.append(row_d)

if dash_data_list:
    df_dash_processed = pd.DataFrame(dash_data_list)
    html_grid = generate_mirrored_html_dashboard(df_dash_processed, selected_tasks)
    st.markdown(html_grid, unsafe_allow_html=True)
else:
    st.info(f"No fights processed for '{sel_ev_opt}'.")

st.markdown(f"<p style='font-size: 0.8em; text-align: center; color: #888;'>*Dashboard updated at: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*</p>", unsafe_allow_html=True, help="This page auto-refreshes every 60 seconds.")
