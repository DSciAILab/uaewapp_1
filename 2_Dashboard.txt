import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from auth import check_authentication
from utils import (
    display_user_sidebar,
    load_attendance_data,
    get_task_list,
    get_latest_status,
    FIGHTCARD_SHEET_URL  # Importa a constante da URL
)

# --- 1. Autenticação e Configuração da Página ---
check_authentication()

# A configuração da página agora pode ser mais simples, pois o layout é gerenciado no estado da sessão
if 'layout_mode' not in st.session_state:
    st.session_state.layout_mode = "wide"
st.set_page_config(layout=st.session_state.layout_mode, page_title="Fight Dashboard")

display_user_sidebar() # Exibe a sidebar padrão de usuário e logout


# --- 2. Constantes e Funções Específicas da Página ---

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

# Esta função de carregamento é específica para o fight card via URL pública,
# por isso faz sentido mantê-la aqui em vez de no utils.py
@st.cache_data
def load_fightcard_data_from_url():
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL)
        df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip()
        df["Picture"] = df["Picture"].astype(str).str.strip().fillna("")
        if "AthleteID" in df.columns:
            df["AthleteID"] = df["AthleteID"].astype(str).str.strip().fillna("")
        else:
            st.error("CRITICAL: Column 'AthleteID' not found in Fightcard.")
            df["AthleteID"] = ""
        return df.dropna(subset=["Fighter", "FightOrder", "AthleteID"])
    except Exception as e:
        st.error(f"Error loading Fightcard from URL: {e}"); return pd.DataFrame()

def get_dashboard_style(font_size_px, num_tasks, fighter_width_pc, division_width_pc, division_font_size_px):
    # Esta função é puramente de UI e específica para esta página, então ela fica aqui.
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
        fighter_width_no_tasks, division_width_no_tasks, photo_pc_no_tasks = 35, 18, 6
        grid_template_columns = f"{fighter_width_no_tasks}% {photo_pc_no_tasks}% {division_width_no_tasks}% {photo_pc_no_tasks}% {fighter_width_no_tasks}%"

    return f"""
    <style>
        div[data-testid="stToolbar"], div[data-testid="stDecoration"], div[data-testid="stStatusWidget"], #MainMenu, header {{ visibility: hidden; height: 0%; position: fixed; }}
        .block-container {{ padding-top: 1rem !important; padding-bottom: 0rem !important; }}
        .dashboard-grid {{ display: grid; grid-template-columns: {grid_template_columns}; gap: 1px; background-color: #4a4a50; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); margin-top: 1rem; }}
        .grid-item {{ background-color: #2a2a2e; color: #e1e1e1; padding: {cell_padding}px 8px; display: flex; align-items: center; justify-content: center; min-height: {img_size + (cell_padding * 2)}px; word-break: break-word; }}
        .grid-item:hover {{ background-color: #38383c; }}
        .grid-header {{ background-color: #1c1c1f; font-weight: 600; font-size: 1rem; min-height: auto; }}
        .blue-corner-header {{ background-color: #0d2e4e !important; }} .red-corner-header {{ background-color: #5a1d1d !important; }} .center-col-header {{ background-color: #111 !important; }}
        .fighter-name {{ font-weight: 700; font-size: {fighter_font_size}px !important; }}
        .fighter-name-blue {{ justify-content: flex-end !important; text-align: right; padding-right: 15px; }} .fighter-name-red {{ justify-content: flex-start !important; text-align: left; padding-left: 15px; }}
        .center-info-cell {{ flex-direction: column; line-height: 1.3; background-color: #333; }}
        .status-done {{ background-color: #4A6D2F; }} .status-requested {{ background-color: #FF8C00; }} .status-pending {{ background-color: #dc3545; }}
        .status-neutral, .status-neutral:hover {{ background-color: transparent !important; }}
        .status-cell {{ cursor: help; }}
        .fighter-img {{ width: {img_size}px; height: {img_size}px; border-radius: 50%; object-fit: cover; border: 2px solid #666; }}
        .fight-info-number, .fight-info-event, .fight-info-division {{ font-size: {division_font_size_px}px !important; }}
        .fight-info-number {{ font-weight: bold; color: #fff; }} .fight-info-event {{ font-style: italic; color: #ccc; }} .fight-info-division {{ font-style: normal; color: #ddd; }}
    </style>
    """

def generate_mirrored_html_dashboard(df_processed, task_list):
    # Esta função é puramente de UI e específica para esta página, então ela fica aqui.
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

    html += "<div class='grid-item grid-header fighter-header'>Fighter</div><div class='grid-item grid-header photo-header'>Photo</div>"
    html += "<div class='grid-item grid-header photo-header'>Photo</div><div class='grid-item grid-header fighter-header'>Fighter</div>"
    if num_tasks > 0:
        for task in task_list:
            html += f"<div class='grid-item grid-header task-header' title='{TASK_EMOJI_MAP.get(task, task[0])}'>{TASK_EMOJI_MAP.get(task, task[0])}</div>"

    for _, row in df_processed.iterrows():
        for task in reversed(task_list):
            status = row.get(f'{task}_status_Azul', {})
            html += f"<div class='grid-item status-cell {status.get('class', '')}' title='{status.get('text', '')}'></div>"
        html += f"<div class='grid-item fighter-name fighter-name-blue'>{row.get('Lutador Azul', 'N/A')}</div>"
        html += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{row.get('Foto Azul', 'https://via.placeholder.com/50?text=N/A')}'/></div>"
        fight_info_html = f"<div class='fight-info-number'>{row.get('Fight #', '')}</div><div class='fight-info-event'>{row.get('Event', '')}</div><div class='fight-info-division'>{row.get('Division', '')}</div>"
        html += f"<div class='grid-item center-info-cell'>{fight_info_html}</div>"
        html += f"<div class='grid-item photo-cell'><img class='fighter-img' src='{row.get('Foto Vermelho', 'https://via.placeholder.com/50?text=N/A')}'/></div>"
        html += f"<div class='grid-item fighter-name fighter-name-red'>{row.get('Lutador Vermelho', 'N/A')}</div>"
        for task in task_list:
            status = row.get(f'{task}_status_Vermelho', {})
            html += f"<div class='grid-item status-cell {status.get('class', '')}' title='{status.get('text', '')}'></div>"
    html += "</div>"
    return html


# --- 3. Lógica Principal da Página ---

st.title("Fight Dashboard")
st_autorefresh(interval=60000, key="dash_auto_refresh_v14")

# Carregamento dos dados usando as funções (uma local, outras de utils.py)
with st.spinner("Carregando dados..."):
    df_fc = load_fightcard_data_from_url()
    df_att = load_attendance_data()
    all_tasks = get_task_list()

# --- Controles da Barra Lateral ---
st.sidebar.header("Controles do Dashboard")
if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
    st.cache_data.clear(); st.toast("Dados atualizados!", icon="🔄"); st.rerun()

avail_evs = sorted(df_fc["Event"].dropna().unique().tolist(), reverse=True) if not df_fc.empty else []
sel_ev_opt = st.sidebar.selectbox("Selecionar Evento:", options=["All Events"] + avail_evs)
st.sidebar.markdown("---")

st.sidebar.subheader("Filtro de Tarefas")
selected_tasks = st.sidebar.multiselect("Monitorar Tarefas:", options=all_tasks, default=all_tasks)
st.sidebar.markdown("---")

st.sidebar.subheader("Configurações de Exibição")
is_wide_mode = st.sidebar.toggle("Modo Tela Cheia", value=(st.session_state.layout_mode == "wide"), key="layout_toggle")
new_layout = "wide" if is_wide_mode else "centered"
if new_layout != st.session_state.layout_mode:
    st.session_state.layout_mode = new_layout
    st.rerun()

font_size = st.sidebar.slider("Tamanho Geral da Fonte (px)", 10, 30, 18, 1)
fighter_width = st.sidebar.slider("Largura Nome do Lutador (%)", 10, 40, 25, 1, disabled=not selected_tasks)
division_width = st.sidebar.slider("Largura Info da Luta (%)", 5, 25, 10, 1, disabled=not selected_tasks)
division_font_size = st.sidebar.slider("Fonte Info da Luta (px)", 10, 30, 16, 1)

# --- Processamento e Exibição ---

st.markdown(get_dashboard_style(font_size, len(selected_tasks), fighter_width, division_width, division_font_size), unsafe_allow_html=True)

df_fc_disp = df_fc.copy()
if sel_ev_opt != "All Events":
    df_fc_disp = df_fc[df_fc["Event"] == sel_ev_opt]

if df_fc_disp.empty:
    st.info(f"Nenhuma luta encontrada para o evento '{sel_ev_opt}'.")
else:
    dash_data_list = []
    for order, group in df_fc_disp.sort_values(by=["Event", "FightOrder"]).groupby(["Event", "FightOrder"]):
        ev, f_ord = order
        bl_s = group[group["Corner"] == "blue"].squeeze(axis=0)
        rd_s = group[group["Corner"] == "red"].squeeze(axis=0)
        row_d = {"Event": ev, "Fight #": int(f_ord) if pd.notna(f_ord) else ""}

        for prefix, series in [("Azul", bl_s), ("Vermelho", rd_s)]:
            if isinstance(series, pd.Series) and not series.empty:
                ath_id, pic, name = series.get("AthleteID"), series.get("Picture"), series.get("Fighter")
                row_d[f"Foto {prefix}"] = pic if isinstance(pic, str) and pic.startswith("http") else ""
                row_d[f"Lutador {prefix}"] = name
                for task in selected_tasks:
                    status_dict = get_latest_status(ath_id, ev, task, df_att)
                    row_d[f"{task}_status_{prefix}"] = STATUS_INFO.get(status_dict["status"], {"class": DEFAULT_STATUS_CLASS, "text": status_dict["status"]})
            else:
                row_d[f"Foto {prefix}"], row_d[f"Lutador {prefix}"] = "", "N/A"
                for task in selected_tasks: row_d[f"{task}_status_{prefix}"] = {}

        division = bl_s.get("Division", rd_s.get("Division", "N/A"))
        row_d["Division"] = division if isinstance(division, str) else "N/A"
        dash_data_list.append(row_d)

    if dash_data_list:
        df_dash_processed = pd.DataFrame(dash_data_list)
        html_grid = generate_mirrored_html_dashboard(df_dash_processed, selected_tasks)
        st.markdown(html_grid, unsafe_allow_html=True)
    else:
        st.info(f"Nenhuma luta processada para '{sel_ev_opt}'.")

st.markdown(f"<p style='font-size: 0.8em; text-align: center; color: #888;'>*Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*</p>", unsafe_allow_html=True, help="Esta página atualiza automaticamente a cada 60 segundos.")
