from components.layout import bootstrap_page
import streamlit as st
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import html

# Helpers centralizados (evita duplicar código de credenciais e conexão)
from utils import get_gspread_client, connect_gsheet_tab

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
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty:
            return pd.DataFrame(columns=[ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_EVENT_COL, ATTENDANCE_TIMESTAMP_COL, ATTENDANCE_TIMESTAMP_ALT_COL])

        # Normalizações e garantia de colunas
        for col in [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, ATTENDANCE_EVENT_COL, ATTENDANCE_TIMESTAMP_COL, ATTENDANCE_TIMESTAMP_ALT_COL]:
            if col not in df_att.columns:
                df_att[col] = ""
            df_att[col] = df_att[col].astype(str).str.strip()

        return df_att
    except Exception as e:
        st.error(f"Error loading Attendance: {e}", icon="🚨")
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
# HTML/CSS
# ------------------------------------------------------------------------------
def generate_mirrored_html_dashboard(df_processed: pd.DataFrame, task_list: list[str]) -> str:
    num_tasks = len(task_list)
    html_out = "<div class='dashboard-grid'>"

    if num_tasks > 0:
        html_out += f"<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span {num_tasks + 2};'>BLUE CORNER</div>"
        html_out += f"<div class='grid-item grid-header center-col-header' style='grid-column: {num_tasks + 3}; grid-row: 1 / span 2;'>FIGHT<br>INFO</div>"
        html_out += f"<div class='grid-item grid-header red-corner-header' style='grid-column: {num_tasks + 4} / span {num_tasks + 2};'>RED CORNER</div>"
        for task in reversed(task_list):
            emoji = TASK_EMOJI_MAP.get(task, (task[:1] if task else "•"))
            html_out += f"<div class='grid-item grid-header task-header' title='{html.escape(task)}'>{emoji}</div>"
    else:
        html_out += "<div class='grid-item grid-header blue-corner-header' style='grid-column: 1 / span 2;'>BLUE CORNER</div>"
        html_out += "<div class='grid-item grid-header center-col-header' style='grid-column: 3; grid-row: 1 / span 2;'>FIGHT<br>INFO</div>"
        html_out += "<div class='grid-item grid-header red-corner-header' style='grid-column: 4 / span 2;'>RED CORNER</div>"

    # Segunda linha (rótulos)
    html_out += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    html_out += "<div class='grid-item grid-header photo-header'>Photo</div>"
    html_out += "<div class='grid-item grid-header photo-header'>Photo</div>"
    html_out += "<div class='grid-item grid-header fighter-header'>Fighter</div>"
    if num_tasks > 0:
        for task in task_list:
            emoji = TASK_EMOJI_MAP.get(task, (task[:1] if task else "•"))
            html_out += f"<div class='grid-item grid-header task-header' title='{html.escape(task)}'>{emoji}</div>"

    # Linhas das lutas
    for _, row in df_processed.iterrows():
        # esquerda (Azul) – tarefas invertidas na esquerda
        for task in reversed(task_list):
            status = row.get(f"{task} (Azul)", STATUS_INFO.get("Pending"))
            html_out += f"<div class='grid-item status-cell {status['class']}' title='{html.escape(status['text'])}'></div>"

        html_out += f"<div class='grid-item fighter-name fighter-name-blue'>{html.escape(str(row.get('Lutador Azul', 'N/A')))}</div>"
        html_out += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{html.escape(str(row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')))}'/></div>"

        fight_info_html = (
            f"<div class='fight-info-number'>{html.escape(str(row.get('Fight #', '')))}</div>"
            f"<div class='fight-info-event'>{html.escape(str(row.get('Event', '')))}</div>"
            f"<div class='fight-info-division'>{html.escape(str(row.get('Division', '')))}</div>"
        )
        html_out += f"<div class='grid-item center-info-cell'>{fight_info_html}</div>"

        html_out += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{html.escape(str(row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')))}'/></div>"
        html_out += f"<div class='grid-item fighter-name fighter-name-red'>{html.escape(str(row.get('Lutador Vermelho', 'N/A')))}</div>"

        # direita (Vermelho)
        for task in task_list:
            status = row.get(f"{task} (Vermelho)", STATUS_INFO.get("Pending"))
            html_out += f"<div class='grid-item status-cell {status['class']}' title='{html.escape(status['text'])}'></div>"

    html_out += "</div>"
    return html_out


def get_dashboard_style(font_size_px: int, num_tasks: int, fighter_width_pc: int, division_width_pc: int, division_font_size_px: int) -> str:
    img_size = font_size_px * 3.5
    cell_padding = font_size_px * 0.5
    fighter_font_size = font_size_px * 1.8
    photo_pc = 6.0

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
            padding: {cell_padding}px 8px;
            display: flex; align-items: center; justify-content: center;
            min-height: {img_size + (cell_padding * 2)}px; word-break: break-word;
        }}
        .grid-item:hover {{ background-color: #38383c; }}
        .grid-header {{ background-color: #1c1c1f; font-weight: 600; font-size: 1rem; min-height: auto; }}
        .blue-corner-header {{ background-color: #0d2e4e !important; }}
        .red-corner-header {{ background-color: #5a1d1d !important; }}
        .center-col-header {{ background-color: #111 !important; }}
        .fighter-name {{ font-weight: 700; font-size: {fighter_font_size}px !important; }}
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
        .fight-info-number, .fight-info-event, .fight-info-division {{ font-size: {division_font_size_px}px !important; }}
        .fight-info-number {{ font-weight: bold; color: #fff; }}
        .fight-info-event {{ font-style: italic; color: #ccc; }}
        .fight-info-division {{ color: #ddd; }}
    </style>
    """


# ------------------------------------------------------------------------------
# App
# ------------------------------------------------------------------------------
# Auto-refresh a cada 60s
st_autorefresh(interval=60_000, key="dash_auto_refresh_v15")

with st.spinner("Loading data..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    all_tsks = get_task_list()

# Sidebar
st.sidebar.title("Dashboard Controls")
if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
    st.cache_data.clear()
    st.toast("Data refreshed!", icon="🎉")
    st.rerun()

avail_evs = sorted(df_fc[FC_EVENT_COL].dropna().unique().tolist(), reverse=True) if not df_fc.empty else []
sel_ev_opt = st.sidebar.selectbox("Select Event:", options=["All Events"] + avail_evs)

st.sidebar.markdown("---")
st.sidebar.subheader("Filtro de Tarefas")
selected_tasks = st.sidebar.multiselect("Selecione as tarefas para monitorar:", options=all_tsks, default=all_tsks)

st.sidebar.markdown("---")
st.sidebar.subheader("Configurações de Exibição")

# Guarda preferências simples na sessão
if "table_font_size" not in st.session_state:
    st.session_state.table_font_size = 18
if "fighter_width" not in st.session_state:
    st.session_state.fighter_width = 25
if "division_width" not in st.session_state:
    st.session_state.division_width = 10
if "division_font_size" not in st.session_state:
    st.session_state.division_font_size = 16

st.session_state.table_font_size = st.sidebar.slider("Tamanho Geral da Fonte (px)", 10, 30, st.session_state.table_font_size, 1)
disable_sliders = len(selected_tasks) == 0
st.session_state.fighter_width = st.sidebar.slider("Largura Nome do Lutador (%)", 10, 40, st.session_state.fighter_width, 1, disabled=disable_sliders)
st.session_state.division_width = st.sidebar.slider("Largura Info da Luta (%)", 5, 25, st.session_state.division_width, 1, disabled=disable_sliders)
st.session_state.division_font_size = st.sidebar.slider("Fonte Info da Luta (px)", 10, 30, st.session_state.division_font_size, 1)

st.sidebar.markdown("---")

# Conteúdo
if df_fc.empty:
    st.warning("Could not load Fightcard data. Please check the spreadsheet or filters.")
    st.stop()

st.markdown(
    get_dashboard_style(
        st.session_state.table_font_size,
        len(selected_tasks),
        st.session_state.fighter_width,
        st.session_state.division_width,
        st.session_state.division_font_size,
    ),
    unsafe_allow_html=True,
)

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

if dash_rows:
    df_dash_processed = pd.DataFrame(dash_rows)
    html_grid = generate_mirrored_html_dashboard(df_dash_processed, selected_tasks)
    st.markdown(html_grid, unsafe_allow_html=True)
else:
    st.info(f"No fights processed for '{sel_ev_opt}'.")

st.markdown(
    f"<p style='font-size: 0.8em; text-align: center; color: #888;'>*Dashboard updated at: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*</p>",
    unsafe_allow_html=True,
)
