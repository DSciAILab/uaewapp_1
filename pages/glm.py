# ==============================================================================
# BLOOD TEST MANAGEMENT SYSTEM - STREAMLIT APP
# ==============================================================================

# --- 0. Import Libraries --- 
import streamlit as st
import pandas as pd
from datetime import datetime
import html
import time
import unicodedata
# --- Importações do Projeto ---
from utils import get_gspread_client, connect_gsheet_tab, load_users_data, get_valid_user_info, load_config_data
from auth import check_authentication, display_user_sidebar

# ==============================================================================
# CONSTANTES E CONFIGURAÇÕES
# ==============================================================================
class Config:
    """Classe para centralizar todas as constantes do aplicativo."""
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"
    FIXED_TASK = "Blood Test"
    STATUS_PENDING_EQUIVALENTS = ["Pending", "---", "Not Registred"]
    STATUS_BASE = "---"
    STATUS_REQUESTED = "Requested"
    STATUS_DONE = "Done"
    ALL_LOGICAL_STATUSES = [STATUS_BASE, STATUS_REQUESTED, STATUS_DONE]
    
    STATUS_COLOR_MAP = {
        STATUS_DONE: "#143d14",
        STATUS_REQUESTED: "#B08D00",
        STATUS_BASE: "#1e1e1e",
        "Pending": "#1e1e1e",
        "Not Registred": "#1e1e1e",
        "Issue": "#1e1e1e"
    }

# ==============================================================================
# FUNÇÕES AUXILIARES (UTILITÁRIOS)
# ==============================================================================
_INVALID_STRS = {"", "none", "None", "null", "NULL", "nan", "NaN", "<NA>"}

def clean_and_normalize(text: str) -> str:
    """
    Normaliza uma string de texto: remove acentos, converte para minúsculas e remove espaços extras.
    Args:
        text (str): Texto a ser normalizado.
    Returns:
        str: Texto normalizado.
    """
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    return " ".join(text.split())

def parse_ts_series(raw: pd.Series) -> pd.Series:
    """
    Tenta múltiplos formatos de data/hora e retorna uma série datetime.
    Args:
        raw (pd.Series): Série com strings de data/hora.
    Returns:
        pd.Series: Série convertida para datetime.
    """
    tries = [
        pd.to_datetime(raw, format="%d/%m/%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d/%m/%Y", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y", errors="coerce"),
        pd.to_datetime(raw, errors="coerce"),  # fallback ISO
    ]
    ts_final = tries[0]
    for cand in tries[1:]:
        ts_final = ts_final.fillna(cand)
    return ts_final

def _clean_str_series(s: pd.Series) -> pd.Series:
    """Limpa uma série de strings, removendo valores inválidos."""
    s = s.fillna("").astype(str).str.strip()
    return s.replace({k: "" for k in _INVALID_STRS})

def _fmt_date_from_text(s: str) -> str:
    """
    Formata qualquer texto de data/horário para dd/mm/aaaa; se inválido, 'N/A'.
    Args:
        s (str): Texto de data/hora.
    Returns:
        str: Data formatada ou 'N/A'.
    """
    if s is None:
        return "N/A"
    s = str(s).strip()
    if s in _INVALID_STRS:
        return "N/A"
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt.strftime("%d/%m/%Y") if pd.notna(dt) else "N/A"

# ==============================================================================
# FUNÇÕES DE CARREGAMENTO DE DADOS (COM CACHE)
# ==============================================================================
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = Config.MAIN_SHEET_NAME, athletes_tab_name: str = Config.ATHLETES_TAB_NAME):
    """
    Carrega os dados dos atletas da planilha, aplicando filtros e normalizações.
    Args:
        sheet_name (str): Nome da planilha principal.
        athletes_tab_name (str): Nome da aba com dados dos atletas.
    Returns:
        pd.DataFrame: DataFrame com dados dos atletas.
    """
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name)
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]
        if "role" not in df.columns or "inactive" not in df.columns:
            st.error(f"Colunas 'ROLE'/'INACTIVE' não encontradas em '{athletes_tab_name}'.", icon="🚨")
            return pd.DataFrame()
        if df["inactive"].dtype == 'object':
            df["inactive"] = df["inactive"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        elif pd.api.types.is_numeric_dtype(df["inactive"]):
            df["inactive"] = df["inactive"].map({0: False, 1: True}).fillna(True)
        df = df[(df["role"] == "1 - Fighter") & (df["inactive"] == False)].copy()
        df["event"] = df["event"].fillna("Z") if "event" in df.columns else "Z"
        for col_check in ["image", "mobile", "fight_number", "corner", "passport_image", "room"]:
            if col_check not in df.columns:
                df[col_check] = ""
            else:
                df[col_check] = df[col_check].fillna("")
        if "name" not in df.columns:
            st.error(f"'NAME' não encontrada em '{athletes_tab_name}'.", icon="🚨")
            return pd.DataFrame()
        return df.sort_values(by=["event", "name"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar atletas (gspread): {e}", icon="🚨")
        return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = Config.MAIN_SHEET_NAME, attendance_tab_name: str = Config.ATTENDANCE_TAB_NAME):
    """
    Carrega os dados de presença da planilha.
    Args:
        sheet_name (str): Nome da planilha principal.
        attendance_tab_name (str): Nome da aba com dados de presença.
    Returns:
        pd.DataFrame: DataFrame com dados de presença.
    """
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty:
            return pd.DataFrame(columns=["#", "Event", "Name", "Fighter", "Task", "Status", "User", "Timestamp", "TimeStamp", "Notes"])
        for col in ["#", "Event", "Name", "Fighter", "Task", "Status", "User", "Timestamp", "TimeStamp", "Notes"]:
            if col not in df_att.columns:
                df_att[col] = pd.NA
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨")
        return pd.DataFrame()

# ==============================================================================
# FUNÇÕES DE PROCESSAMENTO DE DADOS
# ==============================================================================
@st.cache_data(ttl=120)
def preprocess_attendance(df_attendance: pd.DataFrame) -> pd.DataFrame:
    """
    Pré-processa o DataFrame de presença: normaliza colunas e tenta converter timestamps.
    Args:
        df_attendance (pd.DataFrame): DataFrame bruto de presença.
    Returns:
        pd.DataFrame: DataFrame pré-processado.
    """
    if df_attendance is None or df_attendance.empty:
        return pd.DataFrame()
    df = df_attendance.copy()
    df["fighter_norm"] = df.get("Fighter", "").astype(str).apply(clean_and_normalize)
    df["event_norm"]   = df.get("Event", "").astype(str).apply(clean_and_normalize)
    df["task_norm"]    = df.get("Task", "").astype(str).str.strip().str.lower()
    df["status_norm"]  = df.get("Status", "").astype(str).str.strip().str.lower()
    t2 = df.get("TimeStamp")  # PRIORIDADE
    t1 = df.get("Timestamp")
    if t2 is None and t1 is None:
        df["TS_raw"] = ""
    else:
        s2 = _clean_str_series(t2) if t2 is not None else pd.Series([""]*len(df))
        s1 = _clean_str_series(t1) if t1 is not None else pd.Series([""]*len(df))
        df["TS_raw"] = s2.where(s2 != "", s1)  # usa TimeStamp; se vazio, cai para Timestamp
    df["TS_dt"] = parse_ts_series(df["TS_raw"])
    return df

def get_all_athletes_status(df_athletes: pd.DataFrame, df_attendance: pd.DataFrame, fixed_task: str) -> pd.DataFrame:
    """
    Obtém o status atual da tarefa fixa para todos os atletas, processando em massa.
    Args:
        df_athletes (pd.DataFrame): DataFrame de atletas.
        df_attendance (pd.DataFrame): DataFrame de presença pré-processado.
        fixed_task (str): Nome da tarefa fixa (ex: "Blood Test").
    Returns:
        pd.DataFrame: DataFrame com colunas de status adicionadas.
    """
    if df_attendance.empty:
        return pd.DataFrame({
            'name': df_athletes['name'],
            'event': df_athletes['event'],
            'current_task_status': Config.STATUS_BASE,
            'latest_task_user': 'N/A',
            'latest_task_timestamp': 'N/A'
        })
    
    # Normalizar dados dos atletas
    df_athletes['name_norm'] = df_athletes['name'].apply(clean_and_normalize)
    df_athletes['event_norm'] = df_athletes['event'].apply(clean_and_normalize)
    
    # Filtrar registros relevantes na presença
    task_mask = (
        (df_attendance["task_norm"] == fixed_task.lower()) |
        (df_attendance["task_norm"].str.contains(r"\bblood\s*test\b", na=False))
    )
    df_task = df_attendance[task_mask].copy()
    
    if df_task.empty:
        return pd.DataFrame({
            'name': df_athletes['name'],
            'event': df_athletes['event'],
            'current_task_status': Config.STATUS_BASE,
            'latest_task_user': 'N/A',
            'latest_task_timestamp': 'N/A'
        })
    
    # Merge entre atletas e presença
    merged = pd.merge(
        df_athletes[['name', 'event', 'name_norm', 'event_norm']],
        df_task,
        left_on=['name_norm', 'event_norm'],
        right_on=['fighter_norm', 'event_norm'],
        how='left'
    )
    
    # Ordenar e manter apenas registros mais recentes por atleta e evento
    merged = merged.sort_values(['name_norm', 'event_norm', 'TS_dt'], ascending=[True, True, False])
    latest_records = merged.drop_duplicates(subset=['name_norm', 'event_norm'], keep='first')
    
    # Mapear status e formatar timestamps
    latest_records['current_task_status'] = latest_records['Status'].apply(
        lambda x: Config.STATUS_DONE if str(x).strip().lower() == Config.STATUS_DONE.lower() 
                 else (Config.STATUS_REQUESTED if str(x).strip().lower() == Config.STATUS_REQUESTED.lower() 
                       else Config.STATUS_BASE)
    )
    
    latest_records['latest_task_timestamp'] = latest_records.apply(
        lambda row: row['TS_dt'].strftime("%d/%m/%Y") if pd.notna(row.get('TS_dt', pd.NaT))
        else _fmt_date_from_text(row.get('TS_raw', row.get('TimeStamp', ''))),
        axis=1
    )
    
    latest_records['latest_task_user'] = latest_records['User'].fillna('N/A')
    
    return latest_records[['name', 'event', 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]

@st.cache_data(ttl=600)
def last_blood_test_other_event_by_name(df_attendance: pd.DataFrame, athlete_name: str, current_event: str, task: str, fallback_any_event: bool = True) -> tuple:
    """
    Retorna a data e o evento do último Blood Test (Done) em OUTRO evento.
    Args:
        df_attendance (pd.DataFrame): DataFrame de presença pré-processado.
        athlete_name (str): Nome do atleta.
        current_event (str): Evento atual.
        task (str): Tarefa (ex: "Blood Test").
        fallback_any_event (bool): Se True, busca em qualquer evento se não encontrar em outro.
    Returns:
        tuple: (data_formatada, evento) ou ("N/A", "")
    """
    if df_attendance is None or df_attendance.empty:
        return "N/A", ""
    name_n = clean_and_normalize(athlete_name)
    evt_n  = clean_and_normalize(current_event)
    task_is = (
        (df_attendance["task_norm"] == task.lower()) |
        (df_attendance["task_norm"].str.contains(r"\bblood\s*test\b", na=False)) |
        (df_attendance["task_norm"].str.contains("blood", na=False))
    )
    status_done = df_attendance["status_norm"].str.fullmatch(r"\s*done\s*", case=False, na=False)
    base_mask = (df_attendance["fighter_norm"] == name_n) & task_is & status_done
    cand = df_attendance[base_mask & (df_attendance["event_norm"] != evt_n)].copy()
    if not cand.empty:
        if cand["TS_dt"].notna().any():
            cand = cand.dropna(subset=["TS_dt"]).sort_values("TS_dt", ascending=False)
        else:
            cand = cand.reset_index(drop=False).sort_values("index", ascending=False)
    if cand.empty and fallback_any_event:
        cand = df_attendance[base_mask].copy()
        if not cand.empty:
            if cand["TS_dt"].notna().any():
                cand = cand.dropna(subset=["TS_dt"]).sort_values("TS_dt", ascending=False)
            else:
                cand = cand.reset_index(drop=False).sort_values("index", ascending=False)
    if cand.empty:
        return "N/A", ""
    row = cand.iloc[0]
    ev_label = str(row.get("Event", "")).strip()
    if pd.notna(row.get("TS_dt", pd.NaT)):
        dt_str = row["TS_dt"].strftime("%d/%m/%Y")
    else:
        dt_str = _fmt_date_from_text(row.get("TS_raw", row.get("TimeStamp", row.get("Timestamp", ""))))
    return dt_str, ev_label

# ==============================================================================
# FUNÇÕES DE RENDERIZAÇÃO DE UI
# ==============================================================================
def render_athlete_card(row: pd.Series, last_blood_test_info: tuple, badges_html: str) -> str:
    """
    Gera o HTML para o card de um atleta.
    Args:
        row (pd.Series): Dados do atleta.
        last_blood_test_info (tuple): (data, evento) do último blood test em outro evento.
        badges_html (str): HTML com badges de outras tarefas.
    Returns:
        str: HTML do card do atleta.
    """
    ath_id_d = str(row.get("id", ""))
    ath_name_d = str(row.get("name", ""))
    ath_event_d = str(row.get("event", ""))
    ath_fight_number = str(row.get("fight_number", ""))
    ath_corner_color = str(row.get("corner", ""))
    mobile_number = str(row.get("mobile", ""))
    passport_image_url = str(row.get("passport_image", ""))
    room_number = str(row.get("room", ""))
    curr_ath_task_stat = row.get('current_task_status', Config.STATUS_BASE)
    card_bg_col = Config.STATUS_COLOR_MAP.get(curr_ath_task_stat, Config.STATUS_COLOR_MAP[Config.STATUS_BASE])
    
    corner_color_map = {'red': '#d9534f', 'blue': '#428bca'}
    label_color = corner_color_map.get(ath_corner_color.lower(), '#4A4A4A')
    info_parts = []
    if ath_event_d != 'Z': info_parts.append(html.escape(ath_event_d))
    if ath_fight_number:   info_parts.append(f"LUTA {html.escape(ath_fight_number)}")
    if ath_corner_color:   info_parts.append(html.escape(ath_corner_color.upper()))
    fight_info_text = " | ".join(info_parts)
    fight_info_label_html = f"<span style='background-color: {label_color}; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>{fight_info_text}</span>" if fight_info_text else ""
    
    whatsapp_tag_html = ""
    if mobile_number:
        phone_digits = "".join(filter(str.isdigit, mobile_number))
        if phone_digits.startswith('00'): phone_digits = phone_digits[2:]
        if phone_digits:
            escaped_phone = html.escape(phone_digits, True)
            whatsapp_tag_html = f"<a href='https://wa.me/{escaped_phone}' target='_blank' style='text-decoration: none;'><span style='background-color: #25D366; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>📞 WhatsApp</span></a>"
    
    passport_tag_html = f"<a href='{html.escape(passport_image_url, True)}' target='_blank' style='text-decoration: none;'><span style='background-color: #007BFF; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>🛂 Passaporte</span></a>" if passport_image_url and passport_image_url.startswith("http") else ""
    
    blood_test_status_html = f"<small style='color:#ccc;'>Blood Test: <b>{html.escape(curr_ath_task_stat)}</b></small>"
    arrival_status_html = f"<small style='color:#ccc;'>Arrival Status: <b>{html.escape(room_number)}</b></small>" if room_number else ""
    
    last_dt_str, last_event_str = last_blood_test_info
    if last_dt_str != "N/A" and last_event_str:
        last_blood_test_html = f"<span class='event-badge'>{html.escape(last_event_str)} | {html.escape(last_dt_str)}</span>"
    else:
        last_blood_test_html = "N/A"
    
    card_html = f"""<div class='card-container' style='background-color:{card_bg_col};'>
        <img src='{html.escape(row.get("image","https://via.placeholder.com/60?text=NA"), True)}' class='card-img'>
        <div class='card-info'>
            <div class='info-line'><span class='fighter-name'>{html.escape(ath_name_d)} | {html.escape(ath_id_d)}</span></div>
            <div class='info-line'>{fight_info_label_html}</div>
            <div class='info-line'>{whatsapp_tag_html}{passport_tag_html}</div>
            <div class='info-line'>{blood_test_status_html}</div>
            <div class='info-line'>{arrival_status_html}</div>
            <hr style='border-color: #444; margin: 5px 0; width: 100%;'>
            <div class='task-badges'>{badges_html}</div>
            <div class='info-line' style='margin-top:6px;'>
                <small style='color:#ccc;'>Last Blood Test: <b>{last_blood_test_html}</b></small>
            </div>
        </div>
    </div>"""
    return card_html

# ==============================================================================
# FUNÇÕES DE REGISTRO (LOG)
# ==============================================================================
def registrar_log(ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = Config.MAIN_SHEET_NAME, att_tab_name: str = Config.ATTENDANCE_TAB_NAME) -> bool:
    """
    Registra um log na planilha de presença.
    Args:
        ath_name (str): Nome do atleta.
        ath_event (str): Evento do atleta.
        task (str): Tarefa.
        status (str): Status.
        notes (str): Observações.
        user_log_id (str): ID do usuário que registrou.
        sheet_name (str): Nome da planilha.
        att_tab_name (str): Nome da aba de presença.
    Returns:
        bool: True se sucesso, False se erro.
    """
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        next_num = len(log_ws.get_all_values()) + 1
        new_row_data = [str(next_num), ath_event, ath_name, ath_name, task, status, user_ident, ts, notes]
        # Ordem: #, Event, Name, Fighter, Task, Status, User, Timestamp, Notes
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        load_attendance_data.clear()  # Limpa cache para forçar recarregamento
        return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨")
        return False

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA E AUTENTICAÇÃO
# ==============================================================================
check_authentication()
st.set_page_config(page_title="Blood Test", layout="wide")

# CSS
st.markdown("""
<style>
    .card-container {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        align-items: flex-start;
        gap: 15px;
    }
    .card-img {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        object-fit: cover;
        flex-shrink: 0;
    }
    .card-info {
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .info-line {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
    }
    .fighter-name {
        font-size: 1.25rem;
        font-weight: bold;
        margin: 0;
        color: white;
    }
    .task-badges { display: flex; flex-wrap: wrap; gap: 8px; }
    .event-badge {
        background-color: #428bca;
        color: #fff;
        padding: 3px 8px;
        border-radius: 8px;
        font-size: 0.75rem;
        font-weight: bold;
        display: inline-block;
    }
    @media (max-width: 768px) {
        .mobile-button-row div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important; gap: 10px;
        }
    }
    div.stButton > button { width: 100%; }
    .green-button button { background-color: #28a745; color: white !important; border: 1px solid #28a745; }
    .green-button button:hover { background-color: #218838; color: white !important; border: 1px solid #218838; }
    .red-button button { background-color: #dc3545; color: white !important; border: 1px solid #dc3545; }
    .red-button button:hover { background-color: #c82333; color: white !important; border: 1px solid #c82333; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# LÓGICA PRINCIPAL DO APLICATIVO
# ==============================================================================
st.title("Blood Test")
display_user_sidebar()

# Estado inicial da sessão
default_ss = {"selected_status": "Todos", "selected_event": "Todos os Eventos", "fighter_search_query": "", "sort_by": "Nome"}
for k, v in default_ss.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Carregar dados
with st.spinner("Carregando dados..."):
    df_athletes = load_athlete_data()
    df_attendance_raw = load_attendance_data()
    tasks_raw, _ = load_config_data()

# Pré-processar dados de presença
df_attendance = preprocess_attendance(df_attendance_raw)

# Obter status atual da tarefa fixa para todos os atletas
if not df_athletes.empty:
    athletes_status = get_all_athletes_status(df_athletes, df_attendance, Config.FIXED_TASK)
    df_athletes = pd.merge(df_athletes, athletes_status, on=['name', 'event'], how='left')
    df_athletes.fillna({
        'current_task_status': Config.STATUS_BASE,
        'latest_task_user': 'N/A',
        'latest_task_timestamp': 'N/A'
    }, inplace=True)

# Filtros e ordenação
with st.expander("Settings", expanded=True):
    col_status, col_sort = st.columns(2)
    with col_status:
        STATUS_FILTER_LABELS = { "Todos": "Todos", Config.STATUS_BASE: "Pendente", Config.STATUS_REQUESTED: "Requisitado", Config.STATUS_DONE: "Concluído"}
        st.segmented_control(
            "Filtrar por Status:",
            options=["Todos", Config.STATUS_BASE, Config.STATUS_REQUESTED, Config.STATUS_DONE],
            format_func=lambda x: STATUS_FILTER_LABELS.get(x, x),
            key="selected_status"
        )
    with col_sort:
        st.segmented_control("Ordenar por:", options=["Nome", "Ordem de Luta"], key="sort_by", help="Escolha como ordenar a lista de atletas.")
    event_options = ["Todos os Eventos"] + (sorted([evt for evt in df_athletes["event"].unique() if evt != "Z"]) if not df_athletes.empty else [])
    st.selectbox("Filtrar Evento:", options=event_options, key="selected_event")
    st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")

# Aplicar filtros
df_filtered = df_athletes.copy()
if not df_filtered.empty:
    if st.session_state.selected_event != "Todos os Eventos":
        df_filtered = df_filtered[df_filtered["event"] == st.session_state.selected_event]
    search_term = st.session_state.fighter_search_query.strip().lower()
    if search_term:
        df_filtered = df_filtered[
            df_filtered["name"].str.lower().str.contains(search_term, na=False) |
            df_filtered["id"].astype(str).str.contains(search_term, na=False)
        ]
    if st.session_state.selected_status != "Todos":
        df_filtered = df_filtered[df_filtered['current_task_status'] == st.session_state.selected_status]
    if st.session_state.get('sort_by', 'Nome') == 'Ordem de Luta':
        df_filtered['FIGHT_NUMBER_NUM'] = pd.to_numeric(df_filtered['fight_number'], errors='coerce').fillna(999)
        df_filtered['CORNER_SORT'] = df_filtered['corner'].str.lower().map({'blue': 0, 'red': 1}).fillna(2)
        df_filtered = df_filtered.sort_values(by=['FIGHT_NUMBER_NUM', 'CORNER_SORT'], ascending=[True, True])
    else:
        df_filtered = df_filtered.sort_values(by='name', ascending=True)

# Resumo de status
if not df_filtered.empty:
    done_count = (df_filtered['current_task_status'] == Config.STATUS_DONE).sum()
    requested_count = (df_filtered['current_task_status'] == Config.STATUS_REQUESTED).sum()
    pending_count = (df_filtered['current_task_status'] == Config.STATUS_BASE).sum()
    summary_html = f'''<div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 10px; margin-top: 10px;">
        <span style="font-weight: bold;">Exibindo {len(df_filtered)} de {len(df_athletes)} atletas:</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_DONE]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Done: {done_count}</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_REQUESTED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Requested: {requested_count}</span>
        <span style="background-color: #6c757d; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Pending/Cancelled: {pending_count}</span>
    </div>'''
    st.markdown(summary_html, unsafe_allow_html=True)

st.divider()

# Renderizar cards dos atletas
for i_l, row in df_filtered.iterrows():
    # Obter informações do último blood test em outro evento
    last_dt_str, last_event_str = last_blood_test_other_event_by_name(
        df_attendance, row["name"], row["event"], Config.FIXED_TASK, fallback_any_event=True
    )
    
    # Gerar badges para outras tarefas
    badges_html = ""
    if tasks_raw:
        status_color_map_badge = {"Requested": "#D35400", "Done": "#1E8449", "---": "#34495E"}
        default_color = "#34495E"
        name_n = clean_and_normalize(row["name"])
        evt_n  = clean_and_normalize(row["event"])
        for task_name in tasks_raw:
            if task_name == Config.FIXED_TASK:
                continue
            status_for_badge = "---"
            if not df_attendance.empty:
                t_norm = str(task_name).strip().lower()
                mask_t = (df_attendance["task_norm"] == t_norm)
                mask = (df_attendance["fighter_norm"] == name_n) & (df_attendance["event_norm"] == evt_n) & mask_t
                task_records = df_attendance.loc[mask].copy()
                if not task_records.empty:
                    if task_records["TS_dt"].notna().any():
                        latest_record = task_records.sort_values("TS_dt", ascending=False).iloc[0]
                    else:
                        latest_record = task_records.tail(1).iloc[0]
                    status_for_badge = str(latest_record.get("Status","---"))
            color = status_color_map_badge.get(status_for_badge, default_color)
            if status_for_badge in Config.STATUS_PENDING_EQUIVALENTS: color = default_color
            badges_html += f"<span style='background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;'>{html.escape(task_name)}</span>"
    
    # Renderizar card
    card_html = render_athlete_card(row, (last_dt_str, last_event_str), badges_html)
    col_card, col_buttons = st.columns([2.5, 1])
    with col_card:
        st.markdown(card_html, unsafe_allow_html=True)
    with col_buttons:
        uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
        curr_ath_task_stat = row.get('current_task_status', Config.STATUS_BASE)
        if curr_ath_task_stat == Config.STATUS_REQUESTED:
            st.markdown("<div class='mobile-button-row' style='padding-top: 20px'>", unsafe_allow_html=True)
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                st.markdown("<div class='green-button'>", unsafe_allow_html=True)
                if st.button("✅ Done", key=f"done_{row['name']}_{i_l}", use_container_width=True):
                    if registrar_log(row['name'], row['event'], Config.FIXED_TASK, Config.STATUS_DONE, "", uid_l):
                        time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with btn_c2:
                st.markdown("<div class='red-button'>", unsafe_allow_html=True)
                if st.button("❌ Cancel", key=f"cancel_{row['name']}_{i_l}", use_container_width=True):
                    if registrar_log(row['name'], row['event'], Config.FIXED_TASK, Config.STATUS_BASE, "Solicitação cancelada", uid_l):
                        time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='padding-top: 20px'>", unsafe_allow_html=True)
            btn_label = "📝 Request Again" if curr_ath_task_stat == Config.STATUS_DONE else "📝 Request"
            btn_type = "secondary" if curr_ath_task_stat == Config.STATUS_DONE else "primary"
            if st.button(btn_label, key=f"request_{row['name']}_{i_l}", type=btn_type, use_container_width=True):
                if registrar_log(row['name'], row['event'], Config.FIXED_TASK, Config.STATUS_REQUESTED, "", uid_l):
                    time.sleep(1); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    st.divider()

# ==============================================================================
# RESUMO DO CÓDIGO
# ==============================================================================
"""
RESUMO DO CÓDIGO:

Este aplicativo Streamlit foi desenvolvido para gerenciar o status de exames de sangue (Blood Test) de atletas.

PRINCIPAIS FUNCIONALIDADES:
1. Autenticação de usuários via módulo `auth`.
2. Carregamento de dados de atletas e registros de presença a partir de planilhas Google.
3. Pré-processamento de dados para normalização e conversão de timestamps.
4. Filtros por status, evento e busca por nome/ID.
5. Ordenação por nome ou ordem de luta.
6. Exibição de cards com informações detalhadas dos atletas.
7. Botões para atualizar o status do exame de sangue (Request, Done, Cancel).
8. Exibição de badges para outras tarefas e histórico do último exame.

OTIMIZAÇÕES APLICADAS:
1. Cache de dados com `@st.cache_data` para evitar recarregamentos desnecessários.
2. Processamento em massa de status de atletas para melhorar performance.
3. Separação de responsabilidades em funções e módulos.
4. Centralização de constantes na classe `Config`.
5. Melhoria no tratamento de erros e mensagens.
6. Otimização de funções auxiliares (ex: normalização de texto).
7. Renderização de UI separada em funções específicas.

ESTRUTURA:
- Constantes e configurações: classe `Config`.
- Funções auxiliares: normalização, parse de datas, etc.
- Carregamento de dados: funções com cache para atletas e presença.
- Processamento de dados: pré-processamento e obtenção de status em massa.
- Renderização de UI: função para gerar cards de atletas.
- Registro de logs: função para atualizar a planilha de presença.
- Lógica principal: fluxo do aplicativo com filtros, ordenação e exibição.

O código foi projetado para ser modular, eficiente e fácil de manter.
"""