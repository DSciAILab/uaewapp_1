from components.layout import bootstrap_page
import streamlit as st
from datetime import datetime
import pandas as pd
import html

# Helpers centralizados (evita duplicar código de credenciais e conexão)
from utils import get_gspread_client, connect_gsheet_tab
from realtime_utils import setup_auto_refresh  # Auto-refresh seguro

# ------------------------------------------------------------------------------
# Bootstrap da página (config/layout/sidebar centralizados)
# ------------------------------------------------------------------------------
bootstrap_page("UAEW Task Status")  # <- PRIMEIRA LINHA DA PÁGINA
st.markdown("<h1 style='text-align: center; font-size: 5em;'>UAEW Task Status</h1>", unsafe_allow_html=True) #<h1 style='text-align: center; font-size: 3em;'>UAEW Task Status</h1>", unsafe_allow_html=True)
#st.markdown("<h1 style='text-align: center;'>Dashboard</h1>", unsafe_allow_html=True)
#/*******  cd4e7d66-3406-496f-bc30-8a7f9af6cb3e  *******/

#/*******  ca144cf6-dad0-4497-a3ce-af936fe2ee7e  *******/
# ------------------------------------------------------------------------------
# Constantes Globais
# ------------------------------------------------------------------------------
MAIN_SHEET_NAME = "UAEW_App"
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/"
    "gviz/tq?tqx=out:csv&sheet=Fightcard"
)

ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID"
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"     # pode vir vazio
ATTENDANCE_TIMESTAMP_ALT_COL = "TimeStamp" # onde gravamos
ATTENDANCE_EVENT_COL = "Event"

FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_ATHLETE_ID_COL = "AthleteID"
FC_CORNER_COL = "Corner"
FC_ORDER_COL = "FightOrder"
FC_PICTURE_COL = "Picture"
FC_DIVISION_COL = "Division"

# Mapeamento de Status para CSS/Texto (mantém camel case "oficial")
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

# ➜ Versão normalizada (todas as chaves em minúsculas) para lookup case-insensitive
STATUS_INFO_NORM = {
    "done": STATUS_INFO["Done"],
    "requested": STATUS_INFO["Requested"],
    "---": STATUS_INFO["---"],
    "pending": STATUS_INFO["Pending"],
    "pendente": STATUS_INFO["Pendente"],
    "não registrado": STATUS_INFO["Não Registrado"],
    "nao registrado": STATUS_INFO["Não Registrado"],  # sem acento
    "não solicitado": STATUS_INFO["Não Solicitado"],
    "nao solicitado": STATUS_INFO["Não Solicitado"],  # sem acento
    "canceled": {"class": "status-neutral", "text": "Canceled"},
    "cancelled": {"class": "status-neutral", "text": "Canceled"},
}

def _normalize_status_key(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "pending"
    low = s.lower()
    # equivalências úteis
    if low in ("canceled", "cancelled"):
        return "canceled"
    if low in ("---", "not requested"):
        return "---"
    return low

# Emojis das tarefas (fallback na primeira letra)
TASK_EMOJI_MAP = {
    "Walkout Music": "🎵", "Stats": "📊", "Black Screen Video": "⬛",
    "Video Shooting": "🎥", "Photoshoot": "📸", "Blood Test": "🩸",
}

# Importação do dashboard utils
from dashboard_utils import load_dashboard_config, save_dashboard_config

# ... (rest of imports/helpers)

# ------------------------------------------------------------------------------
# HTML/CSS - BROADCAST PREMIUM
# ------------------------------------------------------------------------------
def get_auto_scroll_js(enabled: bool) -> str:
    # ... (same as before)
    if not enabled: return ""
    return """
    <script>
        function autoScroll() {
            window.scrollBy(0, 1);
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight) {
                setTimeout(() => window.scrollTo(0, 0), 2000);
            }
            setTimeout(autoScroll, 50);
        }
        setTimeout(autoScroll, 1000);
    </script>
    """

def get_dashboard_style(font_size_px: int, num_tasks: int, fighter_width_pc: int, division_width_pc: int, division_font_size_px: int, tv_mode: bool) -> str:
    img_size = font_size_px * 3.5
    cell_padding = font_size_px * 0.5
    fighter_font_size = font_size_px * 1.8
    photo_pc = 6.0
    
    header_visibility = "hidden" if tv_mode else "visible"
    main_title_display = "none" if tv_mode else "block"
    page_bg = "#000000" if tv_mode else "#0e1117"

    # Grid Template Calculation (same as before)
    if num_tasks > 0:
        used_space = (fighter_width_pc * 2) + division_width_pc + (photo_pc * 2)
        remaining = max(0.0, 100.0 - used_space)
        num_task_cols = max(1, num_tasks * 2)
        task_pc = remaining / num_task_cols
        grid_template_columns = " ".join(
            [f"{task_pc}%"] * num_tasks
            + [f"{fighter_width_pc}%", f"{photo_pc}%", f"{division_width_pc}%", f"{photo_pc}%", f"{fighter_width_pc}%"]
            + [f"{task_pc}%"] * num_tasks
        )
    else:
        fighter_width_no_tasks = 35
        division_width_no_tasks = 18
        photo_pc_no_tasks = 6
        grid_template_columns = f"{fighter_width_no_tasks}% {photo_pc_no_tasks}% {division_width_no_tasks}% {photo_pc_no_tasks}% {fighter_width_no_tasks}%"

    return f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&family=Roboto:wght@400;700&display=swap');

        /* Global Defaults */
        .stApp {{
            background-color: {page_bg};
        }}
        
        div[data-testid="stToolbar"],
        div[data-testid="stStatusWidget"], #MainMenu {{
            visibility: hidden; height: 0%; position: fixed;
        }}
        
        header[data-testid="stHeader"] {{
            background-color: transparent;
            visibility: visible; 
            z-index: 999;
        }}
        
        h1 {{
            display: {main_title_display} !important;
        }}

        .block-container {{ 
            padding-top: { "0rem" if tv_mode else "1rem" } !important; 
            padding-bottom: 0rem !important; 
            max_width: 100% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }}

        .dashboard-grid {{
            display: grid;
            grid-template-columns: {grid_template_columns};
            gap: 2px;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            margin-top: { "0rem" if tv_mode else "1rem" };
            font-family: 'Roboto', sans-serif;
        }}

        .grid-item {{
            background: rgba(30, 30, 35, 0.7);
            color: #e1e1e1;
            padding: {cell_padding}px 4px;
            display: flex; align-items: center; justify-content: center;
            min-height: {img_size + (cell_padding * 2)}px; 
            word-break: break-word;
            transition: background 0.3s ease;
        }}
        .grid-item:hover {{ background: rgba(50, 50, 60, 0.9); }}

        /* Icon Styling is NOT needed for emojis */
        
        /* Headers */
        .grid-header {{ 
            font-family: 'Oswald', sans-serif;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 700; 
            font-size: 1.1rem; 
            min-height: auto;
            border-bottom: 2px solid rgba(255,255,255,0.1);
        }}
        
        .blue-corner-header {{ 
            background: linear-gradient(90deg, #0a1f35 0%, #0d467d 100%) !important; 
            text-shadow: 0 0 10px #00aaff;
            border-bottom: 2px solid #00aaff;
        }}
        .red-corner-header {{ 
            background: linear-gradient(90deg, #5a1d1d 0%, #8b0000 100%) !important; 
            text-shadow: 0 0 10px #ff4444;
            border-bottom: 2px solid #ff4444;
        }}
        .center-col-header {{ 
            background: #111 !important; 
            color: #ffd700;
            border-bottom: 2px solid #ffd700;
        }}
        .task-header {{
            font-size: 1.5rem; /* Larger for emojis */
            background: #222;
        }}

        /* ... (Keep existing fighter name/img styles) ... */
        .fighter-name {{ 
            font-family: 'Oswald', sans-serif;
            text-transform: uppercase;
            font-weight: 700; 
            font-size: {fighter_font_size}px !important; 
            line-height: 1.1;
        }}
        .fighter-name-blue {{ 
            justify-content: flex-end !important; 
            text-align: right; 
            padding-right: 15px; 
            color: #e6f2ff;
        }}
        .fighter-name-red {{ 
            justify-content: flex-start !important; 
            text-align: left; 
            padding-left: 15px; 
            color: #ffe6e6;
        }}

        .center-info-cell {{ 
            flex-direction: column; 
            line-height: 1.2; 
            background: rgba(0, 0, 0, 0.4);
            border-left: 1px solid rgba(255,255,255,0.05);
            border-right: 1px solid rgba(255,255,255,0.05);
        }}
        .fight-info-number, .fight-info-event, .fight-info-division {{ font-size: {division_font_size_px}px !important; }}
        .fight-info-number {{ font-family: 'Oswald', sans-serif; font-weight: bold; color: #ffd700; font-size: {division_font_size_px * 1.2}px !important; }}
        .fight-info-event {{ color: #aaa; font-size: {division_font_size_px * 0.8}px !important; }}
        .fight-info-division {{ color: #ccc; font-weight: 300; }}

        .status-cell {{ 
            cursor: help; 
            border-radius: 4px;
            margin: 4px;
            box-shadow: inset 0 0 5px rgba(0,0,0,0.5);
            transition: all 0.2s;
        }}
        .status-cell:hover {{ transform: scale(1.1); }}
        
        .status-done {{ background-color: #4A6D2F; box-shadow: 0 0 8px #4A6D2F; }}
        .status-requested {{ background-color: #e67e22; box-shadow: 0 0 8px #e67e22; }}
        .status-pending {{ background-color: #c0392b; box-shadow: 0 0 8px #c0392b; }}
        .status-neutral, .status-neutral:hover {{ background-color: transparent !important; box-shadow: none; border: 1px solid #333; }}

        .fighter-img {{
            width: {img_size}px; height: {img_size}px;
            border-radius: 50%; 
            object-fit: cover; 
            border: 3px solid #444;
            box-shadow: 0 4px 8px rgba(0,0,0,0.5);
        }}
        .photo-cell {{ padding: 0 !important; }}
    </style>
    """

def generate_mirrored_html_dashboard(df_processed: pd.DataFrame, task_list: list[str]) -> str:
    num_tasks = len(task_list)
    html_out = "<div class='dashboard-grid'>"

    if num_tasks > 0:
        html_out += f"<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span {num_tasks + 2};'>BLUE CORNER</div>"
        html_out += f"<div class='grid-item grid-header center-col-header' style='grid-column: {num_tasks + 3}; grid-row: 1 / span 2;'>VS</div>"
        html_out += f"<div class='grid-item grid-header red-corner-header' style='grid-column: {num_tasks + 4} / span {num_tasks + 2};'>RED CORNER</div>"
        for task in reversed(task_list):
            # Use icon map
            icon = TASK_ICON_MAP.get(task, (task[:1] if task else "•"))
            if icon == task[:1] or icon == "•": # Fallback if not mapped
                html_out += f"<div class='grid-item grid-header task-header' title='{html.escape(task)}'>{html.escape(icon)}</div>"
            else:
                html_out += f"<div class='grid-item grid-header task-header' title='{html.escape(task)}'>{icon}</div>"

    else:
        html_out += "<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span 2;'>BLUE CORNER</div>"
        html_out += "<div class='grid-item grid-header center-col-header' style='grid-column: 3; grid-row: 1 / span 2;'>VS</div>"
        html_out += "<div class='grid-item grid-header red-corner-header' style='grid-column: 4 / span 2;'>RED CORNER</div>"

    # Segunda linha (rótulos)
    html_out += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    html_out += "<div class='grid-item grid-header photo-header'></div>" 
    html_out += "<div class='grid-item grid-header photo-header'></div>"
    html_out += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    if num_tasks > 0:
        for task in task_list:
            icon = TASK_ICON_MAP.get(task, (task[:1] if task else "•"))
            if icon == task[:1] or icon == "•": 
                html_out += f"<div class='grid-item grid-header task-header' title='{html.escape(task)}'>{html.escape(icon)}</div>"
            else:
                 html_out += f"<div class='grid-item grid-header task-header' title='{html.escape(task)}'>{icon}</div>"

    # Linhas das lutas (same structure)
    for _, row in df_processed.iterrows():
        # esquerda (Azul)
        for task in reversed(task_list):
            status = row.get(f"{task} (Azul)", STATUS_INFO.get("Pending"))
            html_out += f"<div class='grid-item status-cell {status['class']}' title='{html.escape(status['text'])}'></div>"

        html_out += f"<div class='grid-item fighter-name fighter-name-blue'>{html.escape(str(row.get('Lutador Azul', 'N/A')))}</div>"
        html_out += f"<div class='grid-item photo-cell'><img class='fighter-img' style='border-color: #00aaff;' src='{html.escape(str(row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')))}'/></div>"

        fight_info_html = (
            f"<div class='fight-info-number'>#{html.escape(str(row.get('Fight #', '')))}</div>"
            f"<div class='fight-info-division'>{html.escape(str(row.get('Division', '')))}</div>"
            f"<div class='fight-info-event'>{html.escape(str(row.get('Event', '')))}</div>"
        )
        html_out += f"<div class='grid-item center-info-cell'>{fight_info_html}</div>"

        html_out += f"<div class='grid-item photo-cell'><img class='fighter-img' style='border-color: #ff4444;' src='{html.escape(str(row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')))}'/></div>"
        html_out += f"<div class='grid-item fighter-name fighter-name-red'>{html.escape(str(row.get('Lutador Vermelho', 'N/A')))}</div>"

        # direita (Vermelho)
        for task in task_list:
            status = row.get(f"{task} (Vermelho)", STATUS_INFO.get("Pending"))
            html_out += f"<div class='grid-item status-cell {status['class']}' title='{html.escape(status['text'])}'></div>"

    html_out += "</div>"
    return html_out

# ------------------------------------------------------------------------------
# Carregamento de dados
# ------------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_fightcard_data() -> pd.DataFrame:
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL)
        df.columns = df.columns.str.strip()
        # Garante colunas essenciais
        for col in (FC_EVENT_COL, FC_FIGHTER_COL, FC_ATHLETE_ID_COL, FC_CORNER_COL, FC_ORDER_COL, FC_PICTURE_COL, FC_DIVISION_COL):
            if col not in df.columns:
                df[col] = pd.NA

        # Normalizações
        df[FC_EVENT_COL] = df[FC_EVENT_COL].astype(str).str.strip()
        df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip()
        df[FC_ATHLETE_ID_COL] = df[FC_ATHLETE_ID_COL].astype(str).str.strip()
        df[FC_CORNER_COL] = df[FC_CORNER_COL].astype(str).str.strip().str.lower()
        df[FC_PICTURE_COL] = df[FC_PICTURE_COL].astype(str).str.strip()
        df[FC_ORDER_COL] = pd.to_numeric(df[FC_ORDER_COL], errors="coerce")

        # Filtra registros válidos
        df = df[df[FC_FIGHTER_COL].ne("") & df[FC_ATHLETE_ID_COL].ne("")]
        return df
    except Exception as e:
        st.error(f"Error loading Fightcard: {e}", icon="🚨")
        return pd.DataFrame(columns=[FC_EVENT_COL, FC_FIGHTER_COL, FC_ATHLETE_ID_COL, FC_CORNER_COL, FC_ORDER_COL, FC_PICTURE_COL, FC_DIVISION_COL])


@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME) -> pd.DataFrame:
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        
        # Usa get_all_values para evitar erro de header duplicado
        data = worksheet.get_all_values()
        if not data or len(data) < 2:
            return pd.DataFrame(columns=[ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_EVENT_COL, ATTENDANCE_TIMESTAMP_COL, ATTENDANCE_TIMESTAMP_ALT_COL])

        # Cria DataFrame usando primeira linha como header
        headers = data[0]
        rows = data[1:]
        df_att = pd.DataFrame(rows, columns=headers)

        # Normalizações e garantia de colunas
        for col in [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_EVENT_COL, ATTENDANCE_TIMESTAMP_COL, ATTENDANCE_TIMESTAMP_ALT_COL]:
            if col not in df_att.columns:
                df_att[col] = ""
            df_att[col] = df_att[col].astype(str).str.strip()

        return df_att
    except Exception as e:
        # Se falhar silenciosamente retorna vazio para não quebrar a página
        st.error(f"Error loading Attendance: {e}")
        return pd.DataFrame(columns=[ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_EVENT_COL, ATTENDANCE_TIMESTAMP_COL, ATTENDANCE_TIMESTAMP_ALT_COL])


@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME) -> list[str]:
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
        data = worksheet.get_all_values()
        if not data or len(data) < 1:
            return []
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception as e:
        st.error(f"Error loading TaskList from Config: {e}", icon="🚨")
        return []


# ------------------------------------------------------------------------------
# Lógica
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# Lógica
# ------------------------------------------------------------------------------
def _latest_status_row(relevant_records: pd.DataFrame) -> pd.Series | None:
    """
    Retorna a linha mais recente, considerando primeiro TimeStamp (ALT) e depois Timestamp.
    """
    if relevant_records.empty:
        return None

    df = relevant_records.copy()
    # Converte ambas as colunas para datetime (considera formatos comuns)
    df["TS_dt_alt"] = pd.to_datetime(df.get(ATTENDANCE_TIMESTAMP_ALT_COL, ""), format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df["TS_dt"] = pd.to_datetime(df.get(ATTENDANCE_TIMESTAMP_COL, ""), errors="coerce", dayfirst=True)

    # Usa a melhor disponível
    df["TS_best"] = df["TS_dt_alt"].where(df["TS_dt_alt"].notna(), df["TS_dt"])

    # Ordena do mais recente para o mais antigo (NaT por último)
    df = df.sort_values(by=["TS_best"], ascending=False, na_position="last")
    return df.iloc[0] if not df.empty else None


def get_task_status(athlete_id: str, task_name: str, event_name: str, df_attendance: pd.DataFrame) -> dict:
    """
    Retorna {class, text} para colorir a célula do grid.
    Faz matching por Athlete ID + Task + Event e mapeia Status de forma case-insensitive.
    """
    if (
        df_attendance.empty
        or not str(athlete_id).strip()
        or not str(task_name).strip()
        or not str(event_name).strip()
    ):
        return STATUS_INFO_NORM["pending"]

    mask = (
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL] == str(athlete_id).strip())
        & (df_attendance[ATTENDANCE_TASK_COL] == str(task_name).strip())
        & (df_attendance[ATTENDANCE_EVENT_COL] == str(event_name).strip())
    )
    relevant = df_attendance.loc[mask]
    if relevant.empty:
        return STATUS_INFO_NORM["pending"]

    last_row = _latest_status_row(relevant)
    latest_status_str = str(last_row[ATTENDANCE_STATUS_COL]).strip() if last_row is not None else "Pending"
    key = _normalize_status_key(latest_status_str)

    return STATUS_INFO_NORM.get(key, STATUS_INFO_NORM["pending"])


# ------------------------------------------------------------------------------
# HTML/CSS - BROADCAST PREMIUM
# ------------------------------------------------------------------------------
def get_auto_scroll_js(enabled: bool) -> str:
    if not enabled:
        return ""
    return """
    <script>
        function autoScroll() {
            window.scrollBy(0, 1);
            if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight) {
                setTimeout(() => window.scrollTo(0, 0), 2000); // Wait 2s at bottom then reset
            }
            setTimeout(autoScroll, 50); // Speed control
        }
        setTimeout(autoScroll, 1000);
    </script>
    """

def get_dashboard_style(font_size_px: int, num_tasks: int, fighter_width_pc: int, division_width_pc: int, division_font_size_px: int, tv_mode: bool) -> str:
    img_size = font_size_px * 3.5
    cell_padding = font_size_px * 0.5
    fighter_font_size = font_size_px * 1.8
    photo_pc = 6.0
    
    # Header hiding logic for TV Mode
    header_visibility = "hidden" if tv_mode else "visible"
    header_bg = "transparent" if tv_mode else "unset"
    main_title_display = "none" if tv_mode else "block"
    page_bg = "#000000" if tv_mode else "#0e1117" # Pure black for TV mode contrast

    if num_tasks > 0:
        used_space = (fighter_width_pc * 2) + division_width_pc + (photo_pc * 2)
        remaining = max(0.0, 100.0 - used_space)
        num_task_cols = max(1, num_tasks * 2)
        task_pc = remaining / num_task_cols
        grid_template_columns = " ".join(
            [f"{task_pc}%"] * num_tasks
            + [f"{fighter_width_pc}%", f"{photo_pc}%", f"{division_width_pc}%", f"{photo_pc}%", f"{fighter_width_pc}%"]
            + [f"{task_pc}%"] * num_tasks
        )
    else:
        fighter_width_no_tasks = 35
        division_width_no_tasks = 18
        photo_pc_no_tasks = 6
        grid_template_columns = f"{fighter_width_no_tasks}% {photo_pc_no_tasks}% {division_width_no_tasks}% {photo_pc_no_tasks}% {fighter_width_no_tasks}%"

    # Double CSS brackets {{ }} where needed for f-string
    return f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&family=Roboto:wght@400;700&display=swap');

        /* Global Defaults */
        .stApp {{
            background-color: {page_bg};
        }}
        
        div[data-testid="stToolbar"],
        div[data-testid="stStatusWidget"], #MainMenu {{
            visibility: hidden; height: 0%; position: fixed;
        }}
        
        /* Sidebar Toggle Visibility */
        header[data-testid="stHeader"] {{
            background-color: transparent;
            visibility: visible; 
            z-index: 999;
        }}
        
        /* Hide Main Title in TV Mode */
        h1 {{
            display: {main_title_display} !important;
        }}

        .block-container {{ 
            padding-top: { "0rem" if tv_mode else "1rem" } !important; 
            padding-bottom: 0rem !important; 
            max_width: 100% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }}

        /* Dashboard Grid Container - Glassmorphism */
        .dashboard-grid {{
            display: grid;
            grid-template-columns: {grid_template_columns};
            gap: 2px;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            margin-top: { "0rem" if tv_mode else "1rem" };
            font-family: 'Roboto', sans-serif;
        }}

        /* Grid Items */
        .grid-item {{
            background: rgba(30, 30, 35, 0.7);
            color: #e1e1e1;
            padding: {cell_padding}px 4px; /* Reduced side padding */
            display: flex; align-items: center; justify-content: center;
            min-height: {img_size + (cell_padding * 2)}px; 
            word-break: break-word;
            transition: background 0.3s ease;
        }}
        .grid-item:hover {{ background: rgba(50, 50, 60, 0.9); }}

        /* Headers */
        .grid-header {{ 
            font-family: 'Oswald', sans-serif;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 700; 
            font-size: 1.1rem; 
            min-height: auto;
            border-bottom: 2px solid rgba(255,255,255,0.1);
        }}
        
        .blue-corner-header {{ 
            background: linear-gradient(90deg, #0a1f35 0%, #0d467d 100%) !important; 
            text-shadow: 0 0 10px #00aaff;
            border-bottom: 2px solid #00aaff;
        }}
        .red-corner-header {{ 
            background: linear-gradient(90deg, #5a1d1d 0%, #8b0000 100%) !important; 
            text-shadow: 0 0 10px #ff4444;
            border-bottom: 2px solid #ff4444;
        }}
        .center-col-header {{ 
            background: #111 !important; 
            color: #ffd700;
            border-bottom: 2px solid #ffd700;
        }}
        .task-header {{
            font-size: 1.2rem;
            background: #222;
        }}

        /* Fighter Names */
        .fighter-name {{ 
            font-family: 'Oswald', sans-serif;
            text-transform: uppercase;
            font-weight: 700; 
            font-size: {fighter_font_size}px !important; 
            line-height: 1.1;
        }}
        .fighter-name-blue {{ 
            justify-content: flex-end !important; 
            text-align: right; 
            padding-right: 15px; 
            color: #e6f2ff;
        }}
        .fighter-name-red {{ 
            justify-content: flex-start !important; 
            text-align: left; 
            padding-left: 15px; 
            color: #ffe6e6;
        }}

        /* Fight Info Middle */
        .center-info-cell {{ 
            flex-direction: column; 
            line-height: 1.2; 
            background: rgba(0, 0, 0, 0.4);
            border-left: 1px solid rgba(255,255,255,0.05);
            border-right: 1px solid rgba(255,255,255,0.05);
        }}
        .fight-info-number, .fight-info-event, .fight-info-division {{ font-size: {division_font_size_px}px !important; }}
        .fight-info-number {{ font-family: 'Oswald', sans-serif; font-weight: bold; color: #ffd700; font-size: {division_font_size_px * 1.2}px !important; }}
        .fight-info-event {{ color: #aaa; font-size: {division_font_size_px * 0.8}px !important; }}
        .fight-info-division {{ color: #ccc; font-weight: 300; }}

        /* Status Cells */
        .status-cell {{ 
            cursor: help; 
            border-radius: 4px;
            margin: 4px;
            box-shadow: inset 0 0 5px rgba(0,0,0,0.5);
            transition: all 0.2s;
        }}
        .status-cell:hover {{ transform: scale(1.1); }}
        
        .status-done {{ background-color: #4A6D2F; box-shadow: 0 0 8px #4A6D2F; }}
        .status-requested {{ background-color: #e67e22; box-shadow: 0 0 8px #e67e22; }}
        .status-pending {{ background-color: #c0392b; box-shadow: 0 0 8px #c0392b; }}
        .status-neutral, .status-neutral:hover {{ background-color: transparent !important; box-shadow: none; border: 1px solid #333; }}

        /* Photos */
        .fighter-img {{
            width: {img_size}px; height: {img_size}px;
            border-radius: 50%; 
            object-fit: cover; 
            border: 3px solid #444;
            box-shadow: 0 4px 8px rgba(0,0,0,0.5);
        }}
        .photo-cell {{ padding: 0 !important; }}
    </style>
    """

def generate_mirrored_html_dashboard(df_processed: pd.DataFrame, task_list: list[str]) -> str:
    # Same HTML structure, CSS handles the visuals
    num_tasks = len(task_list)
    html_out = "<div class='dashboard-grid'>"

    if num_tasks > 0:
        html_out += f"<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span {num_tasks + 2};'>BLUE CORNER</div>"
        html_out += f"<div class='grid-item grid-header center-col-header' style='grid-column: {num_tasks + 3}; grid-row: 1 / span 2;'>VS</div>"
        html_out += f"<div class='grid-item grid-header red-corner-header' style='grid-column: {num_tasks + 4} / span {num_tasks + 2};'>RED CORNER</div>"
        for task in reversed(task_list):
            emoji = TASK_EMOJI_MAP.get(task, (task[:1] if task else "•"))
            html_out += f"<div class='grid-item grid-header task-header' title='{html.escape(task)}'>{emoji}</div>"
    else:
        html_out += "<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span 2;'>BLUE CORNER</div>"
        html_out += "<div class='grid-item grid-header center-col-header' style='grid-column: 3; grid-row: 1 / span 2;'>VS</div>"
        html_out += "<div class='grid-item grid-header red-corner-header' style='grid-column: 4 / span 2;'>RED CORNER</div>"

    # Segunda linha (rótulos)
    html_out += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    html_out += "<div class='grid-item grid-header photo-header'></div>" # Empty header for photo column cleanliness
    html_out += "<div class='grid-item grid-header photo-header'></div>"
    html_out += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    if num_tasks > 0:
        for task in task_list:
            emoji = TASK_EMOJI_MAP.get(task, (task[:1] if task else "•"))
            html_out += f"<div class='grid-item grid-header task-header' title='{html.escape(task)}'>{emoji}</div>"

    # Linhas das lutas
    for _, row in df_processed.iterrows():
        # esquerda (Azul)
        for task in reversed(task_list):
            status = row.get(f"{task} (Azul)", STATUS_INFO.get("Pending"))
            html_out += f"<div class='grid-item status-cell {status['class']}' title='{html.escape(status['text'])}'></div>"

        html_out += f"<div class='grid-item fighter-name fighter-name-blue'>{html.escape(str(row.get('Lutador Azul', 'N/A')))}</div>"
        html_out += f"<div class='grid-item photo-cell'><img class='fighter-img' style='border-color: #00aaff;' src='{html.escape(str(row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')))}'/></div>"

        # Center Info
        fight_info_html = (
            f"<div class='fight-info-number'>#{html.escape(str(row.get('Fight #', '')))}</div>"
            f"<div class='fight-info-division'>{html.escape(str(row.get('Division', '')))}</div>"
            f"<div class='fight-info-event'>{html.escape(str(row.get('Event', '')))}</div>"
        )
        html_out += f"<div class='grid-item center-info-cell'>{fight_info_html}</div>"

        html_out += f"<div class='grid-item photo-cell'><img class='fighter-img' style='border-color: #ff4444;' src='{html.escape(str(row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')))}'/></div>"
        html_out += f"<div class='grid-item fighter-name fighter-name-red'>{html.escape(str(row.get('Lutador Vermelho', 'N/A')))}</div>"

        # direita (Vermelho)
        for task in task_list:
            status = row.get(f"{task} (Vermelho)", STATUS_INFO.get("Pending"))
            html_out += f"<div class='grid-item status-cell {status['class']}' title='{html.escape(status['text'])}'></div>"

    html_out += "</div>"
    return html_out


# ------------------------------------------------------------------------------
# App
# ------------------------------------------------------------------------------
# Auto-refresh a cada 60s (seguro - não quebra se módulo não instalado)
setup_auto_refresh(interval_ms=60_000, key="dash_auto_refresh_v15")

# --- LOAD CONFIGURATION FROM SHEET (ONCE) ---
if "dash_config_loaded" not in st.session_state:
    with st.spinner("Loading Dashboard Config..."):
        loaded_conf = load_dashboard_config(MAIN_SHEET_NAME)
        
        # Apply to session state if keys exist, otherwise defaults will be used below
        if "selected_event" in loaded_conf:
            st.session_state["dash_selected_event"] = loaded_conf["selected_event"]
        
        if "selected_tasks" in loaded_conf:
            tasks_str = loaded_conf["selected_tasks"]
            if tasks_str:
                st.session_state["dash_selected_tasks"] = [t.strip() for t in tasks_str.split(",")]
        
        # Numeric/Boolean settings
        for key, typ in [
            ("table_font_size", int), ("fighter_width", int), 
            ("division_width", int), ("division_font_size", int),
            ("dash_tv_mode", bool), ("dash_auto_scroll", bool) # New bools
        ]:
            if key in loaded_conf:
                try: 
                    # Handle boolean strings specifically
                    if typ == bool:
                        st.session_state[key] = (loaded_conf[key].lower() == 'true')
                    else:
                        st.session_state[key] = typ(loaded_conf[key])
                except: pass
            
    st.session_state["dash_config_loaded"] = True


with st.spinner("Loading data..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    all_tsks = get_task_list()


# --- SAVE CONFIGURATION CALLBACK ---
def save_current_config():
    """Reads current session state and saves to sheet."""
    config_to_save = {
        "selected_event": st.session_state.get("dash_selected_event", "All Events"),
        "selected_tasks": ",".join(st.session_state.get("dash_selected_tasks", [])),
        "table_font_size": st.session_state.get("table_font_size", 18),
        "fighter_width": st.session_state.get("fighter_width", 25),
        "division_width": st.session_state.get("division_width", 10),
        "division_font_size": st.session_state.get("division_font_size", 16),
        "dash_tv_mode": str(st.session_state.get("dash_tv_mode", False)),
        "dash_auto_scroll": str(st.session_state.get("dash_auto_scroll", False))
    }
    save_dashboard_config(MAIN_SHEET_NAME, config_to_save)
    st.toast("Dashboard configuration saved!", icon="💾")


# Sidebar
st.sidebar.markdown("## 🎛️ Control Panel")

# Group 1: Data & Event
col1, col2 = st.sidebar.columns([0.8, 0.2])
with col1:
    avail_evs = sorted(df_fc[FC_EVENT_COL].dropna().unique().tolist(), reverse=True) if not df_fc.empty else []
    
    # Initialize/Validate Event
    if "dash_selected_event" not in st.session_state:
        st.session_state["dash_selected_event"] = "All Events"
    
    current_ev_sel = st.session_state["dash_selected_event"]
    if current_ev_sel not in ["All Events"] + avail_evs:
         current_ev_sel = "All Events"
    
    sel_ev_opt = st.selectbox(
        "📅 Select Event", 
        options=["All Events"] + avail_evs,
        key="dash_selected_event",
        index=(["All Events"] + avail_evs).index(current_ev_sel),
        on_change=save_current_config,
        label_visibility="collapsed" # Save space, header implies purpose
    )

with col2:
    if st.button("🔄", help="Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.toast("Data refreshed!", icon="🎉")
        st.rerun()

st.sidebar.divider()

# Group 2: View Modes
st.sidebar.caption("📺 DISPLAY MODES")
c1, c2 = st.sidebar.columns(2)
with c1:
    st.toggle("TV Mode", key="dash_tv_mode", on_change=save_current_config, help="Max contrast, hides headers")
with c2:
    st.toggle("Auto Scroll", key="dash_auto_scroll", on_change=save_current_config, help="Cycles through list automatically")

st.sidebar.divider()

# Group 3: Task Filters
st.sidebar.caption("🎯 TASK FILTERS")
if "dash_selected_tasks" not in st.session_state:
    st.session_state["dash_selected_tasks"] = all_tsks

valid_tasks = [t for t in st.session_state["dash_selected_tasks"] if t in all_tsks]
if not valid_tasks: valid_tasks = all_tsks

selected_tasks = st.sidebar.multiselect(
    "Select Tasks:", 
    options=all_tsks, 
    default=valid_tasks, 
    key="dash_selected_tasks",
    on_change=save_current_config,
    label_visibility="collapsed"
)

st.sidebar.divider()

# Group 4: Appearance (Expander)
with st.sidebar.expander("🎨 Appearance Settings", expanded=False):
    if "table_font_size" not in st.session_state: st.session_state.table_font_size = 18
    if "fighter_width" not in st.session_state: st.session_state.fighter_width = 25
    if "division_width" not in st.session_state: st.session_state.division_width = 10
    if "division_font_size" not in st.session_state: st.session_state.division_font_size = 16

    st.caption("Font Sizes")
    st.session_state.table_font_size = st.slider("Main Font (px)", 10, 30, st.session_state.table_font_size, 1, on_change=save_current_config)
    st.session_state.division_font_size = st.slider("Info Font (px)", 10, 30, st.session_state.division_font_size, 1, on_change=save_current_config)
    
    st.markdown("---")
    st.caption("Common Widths")
    disable_sliders = len(selected_tasks) == 0
    st.session_state.fighter_width = st.slider("Fighter Name Width (%)", 10, 40, st.session_state.fighter_width, 1, disabled=disable_sliders, on_change=save_current_config)
    st.session_state.division_width = st.slider("Center Info Width (%)", 5, 25, st.session_state.division_width, 1, disabled=disable_sliders, on_change=save_current_config)

# Defaults for toggles if not checked above (safety)
if "dash_tv_mode" not in st.session_state: st.session_state.dash_tv_mode = False
if "dash_auto_scroll" not in st.session_state: st.session_state.dash_auto_scroll = False

# Conteúdo
if df_fc.empty:
    st.warning("Could not load Fightcard data. Please check the spreadsheet or filters.")
    st.stop()

# Inject Styles and JS
st.markdown(
    get_dashboard_style(
        st.session_state.table_font_size,
        len(selected_tasks),
        st.session_state.fighter_width,
        st.session_state.division_width,
        st.session_state.division_font_size,
        st.session_state.dash_tv_mode
    ),
    unsafe_allow_html=True,
)

if st.session_state.dash_auto_scroll:
    st.markdown(get_auto_scroll_js(True), unsafe_allow_html=True)

df_fc_disp = df_fc.copy()
if sel_ev_opt != "All Events":
    df_fc_disp = df_fc_disp[df_fc_disp[FC_EVENT_COL] == sel_ev_opt]

if df_fc_disp.empty:
    st.info(f"No fights found for event '{sel_ev_opt}'.")
    st.stop()

dash_rows = []
# Ordena por Evento e FightOrder asc (NaN por último)
for (ev, f_ord), group in df_fc_disp.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL], na_position="last").groupby([FC_EVENT_COL, FC_ORDER_COL]):
    # Corner Azul
    blue_df = group[group[FC_CORNER_COL] == "blue"]
    bl_s = blue_df.iloc[0] if not blue_df.empty else pd.Series()

    # Corner Vermelho
    red_df = group[group[FC_CORNER_COL] == "red"]
    rd_s = red_df.iloc[0] if not red_df.empty else pd.Series()
    
    # Alert logic (kept same)
    if not blue_df.empty and len(blue_df) > 1:
        st.warning(f"Atenção: múltiplas entradas para o canto Azul na luta {f_ord} (Evento: {ev}). Usando a primeira.")
    if not red_df.empty and len(red_df) > 1:
        st.warning(f"Atenção: múltiplas entradas para o canto Vermelho na luta {f_ord} (Evento: {ev}). Usando a primeira.")

    fight_number_display = (int(f_ord) if pd.notna(f_ord) else "N/A")

    row_d = {"Event": ev, "Fight #": fight_number_display}
    # Azul
    if isinstance(bl_s, pd.Series) and not bl_s.empty:
        name = bl_s.get(FC_FIGHTER_COL, "N/A")
        athlete_id = bl_s.get(FC_ATHLETE_ID_COL, "")
        pic = bl_s.get(FC_PICTURE_COL, "")
        row_d["Foto Azul"] = pic if isinstance(pic, str) and pic.startswith(("http://", "https://")) else "https://via.placeholder.com/50?text=N/A"
        row_d["Lutador Azul"] = f"{name}"
        for task in selected_tasks:
            row_d[f"{task} (Azul)"] = get_task_status(athlete_id, task, ev, df_att)
    else:
        row_d["Foto Azul"] = "https://via.placeholder.com/50?text=N/A"
        row_d["Lutador Azul"] = "N/A"
        for task in selected_tasks:
            row_d[f"{task} (Azul)"] = STATUS_INFO_NORM["pending"]

    # Vermelho
    if isinstance(rd_s, pd.Series) and not rd_s.empty:
        name = rd_s.get(FC_FIGHTER_COL, "N/A")
        athlete_id = rd_s.get(FC_ATHLETE_ID_COL, "")
        pic = rd_s.get(FC_PICTURE_COL, "")
        row_d["Foto Vermelho"] = pic if isinstance(pic, str) and pic.startswith(("http://", "https://")) else "https://via.placeholder.com/50?text=N/A"
        row_d["Lutador Vermelho"] = f"{name}"
        for task in selected_tasks:
            row_d[f"{task} (Vermelho)"] = get_task_status(athlete_id, task, ev, df_att)
    else:
        row_d["Foto Vermelho"] = "https://via.placeholder.com/50?text=N/A"
        row_d["Lutador Vermelho"] = "N/A"
        for task in selected_tasks:
            row_d[f"{task} (Vermelho)"] = STATUS_INFO_NORM["pending"]

    # Division (prioriza do azul; se vazio usa vermelho)
    row_d["Division"] = bl_s.get(FC_DIVISION_COL, rd_s.get(FC_DIVISION_COL, "N/A")) if isinstance(bl_s, pd.Series) else rd_s.get(FC_DIVISION_COL, "N/A")
    dash_rows.append(row_d)

def get_summary_badges_html(counts: dict) -> str:
    """Generates HTML for top summary badges."""
    badges_html = "<div style='display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; justify-content: center;'>"
    for task, count in counts.items():
        if count > 0:
            emoji = TASK_EMOJI_MAP.get(task, "")
            # IMPORTANT: formatting must be left-aligned to avoid markdown code-block interpretation
            badges_html += f"<div style='background: linear-gradient(135deg, #e67e22 0%, #d35400 100%); color: white; padding: 5px 12px; border-radius: 20px; font-family: \"Roboto\", sans-serif; font-weight: bold; font-size: 0.9em; box-shadow: 0 4px 6px rgba(0,0,0,0.3); display: flex; align-items: center; gap: 5px;'><span style='font-size: 1.2em;'>{emoji}</span> {task}: <span style='font-size: 1.2em; background: rgba(0,0,0,0.2); padding: 0 6px; border-radius: 10px; margin-left: 5px;'>{count}</span></div>"
    badges_html += "</div>"
    return badges_html

if dash_rows:
    df_dash_processed = pd.DataFrame(dash_rows)
    
    # Calculate Requested Totals
    badges_counts = {}
    for task in selected_tasks:
        total_req = 0
        # Check col exist
        col_blue = f"{task} (Azul)"
        col_red = f"{task} (Vermelho)"
        
        if col_blue in df_dash_processed.columns:
            # Value is dict like {'class': '...', 'text': 'Requested'}
            # We need to count where text == 'Requested'
            total_req += df_dash_processed[col_blue].apply(lambda x: 1 if isinstance(x, dict) and x.get("text") == "Requested" else 0).sum()
            
        if col_red in df_dash_processed.columns:
             total_req += df_dash_processed[col_red].apply(lambda x: 1 if isinstance(x, dict) and x.get("text") == "Requested" else 0).sum()
        
        badges_counts[task] = total_req

    # Display Badges
    st.markdown(get_summary_badges_html(badges_counts), unsafe_allow_html=True)

    html_grid = generate_mirrored_html_dashboard(df_dash_processed, selected_tasks)
    st.markdown(html_grid, unsafe_allow_html=True)
else:
    st.info(f"No fights processed for '{sel_ev_opt}'.")

st.markdown(
    f"<p style='font-size: 0.8em; text-align: center; color: #888;'>*Dashboard updated at: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*</p>",
    unsafe_allow_html=True,
)
