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

# --- Autenticação ---
check_authentication()

# --- 1. Page Configuration ---
st.set_page_config(page_title="Blood Test", layout="wide")

# --- CSS ---
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

# --- Constants ---
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

# --- Helpers ---
_INVALID_STRS = {"", "none", "None", "null", "NULL", "nan", "NaN", "<NA>"}

def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = name.strip().lower()
    name = unicodedata.normalize('NFKD', name)
    name = "".join([c for c in name if not unicodedata.combining(c)])
    return " ".join(name.split())

def parse_ts_series(raw: pd.Series) -> pd.Series:
    """Tenta múltiplos formatos e retorna uma série datetime."""
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
    s = s.fillna("").astype(str).str.strip()
    return s.replace({k: "" for k in _INVALID_STRS})

def _fmt_date_from_text(s: str) -> str:
    """Formata qualquer texto de data/horário para dd/mm/aaaa; se inválido, 'N/A'."""
    if s is None:
        return "N/A"
    s = str(s).strip()
    if s in _INVALID_STRS:
        return "N/A"
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt.strftime("%d/%m/%Y") if pd.notna(dt) else "N/A"

def preprocess_attendance(df_attendance: pd.DataFrame) -> pd.DataFrame:
    """
    NÃO filtra por evento. Cria colunas normalizadas e TS_dt a partir de
    um COALESCE que **prioriza TimeStamp** (e usa Timestamp só se preciso).
    """
    if df_attendance is None or df_attendance.empty:
        return pd.DataFrame()
    df = df_attendance.copy()

    df["fighter_norm"] = df.get("Fighter", "").astype(str).apply(normalize_name)
    df["event_norm"]   = df.get("Event", "").astype(str).apply(normalize_name)
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

def status_for_current_event_by_name(att_df: pd.DataFrame, athlete_name: str, current_event: str, task: str):
    """(status, user, data_dd/mm/aaaa) para o evento atual, buscando por NOME + EVENTO."""
    if att_df is None or att_df.empty:
        return STATUS_BASE, "N/A", "N/A"

    name_n = normalize_name(athlete_name)
    evt_n  = normalize_name(current_event)

    task_is = (
        (att_df["task_norm"] == task.lower()) |
        (att_df["task_norm"].str.contains(r"\bblood\s*test\b", na=False)) |
        (att_df["task_norm"].str.contains("blood", na=False))
    )
    recs = att_df[(att_df["fighter_norm"] == name_n) & (att_df["event_norm"] == evt_n) & task_is].copy()
    if recs.empty:
        return STATUS_BASE, "N/A", "N/A"

    if recs["TS_dt"].notna().any():
        recs = recs.dropna(subset=["TS_dt"]).sort_values("TS_dt", ascending=False)
    else:
        recs = recs.reset_index(drop=False).sort_values("index", ascending=False)

    latest = recs.iloc[0]
    status_raw = str(latest.get("Status", STATUS_BASE)).strip().lower()
    status = STATUS_DONE if status_raw == STATUS_DONE.lower() else (STATUS_REQUESTED if status_raw == STATUS_REQUESTED.lower() else STATUS_BASE)

    if pd.notna(latest.get("TS_dt", pd.NaT)):
        ts_str = latest["TS_dt"].strftime("%d/%m/%Y")
    else:
        ts_str = _fmt_date_from_text(latest.get("TS_raw", latest.get("TimeStamp", latest.get("Timestamp", ""))))
    user_str = str(latest.get("User", "N/A"))
    return status, user_str, ts_str

def last_blood_test_other_event_by_name(att_df: pd.DataFrame, athlete_name: str, current_event: str, task: str, fallback_any_event: bool = True):
    """
    Retorna ("dd/mm/aaaa", "EVENTO") do último Blood Test (Done) em OUTRO evento.
    Se não houver e fallback=True, usa o último em QUALQUER evento.
    """
    if att_df is None or att_df.empty:
        return "N/A", ""

    name_n = normalize_name(athlete_name)
    evt_n  = normalize_name(current_event)

    task_is = (
        (att_df["task_norm"] == task.lower()) |
        (att_df["task_norm"].str.contains(r"\bblood\s*test\b", na=False)) |
        (att_df["task_norm"].str.contains("blood", na=False))
    )
    status_done = att_df["status_norm"].str.fullmatch(r"\s*done\s*", case=False, na=False)
    base_mask = (att_df["fighter_norm"] == name_n) & task_is & status_done

    cand = att_df[base_mask & (att_df["event_norm"] != evt_n)].copy()
    if not cand.empty:
        if cand["TS_dt"].notna().any():
            cand = cand.dropna(subset=["TS_dt"]).sort_values("TS_dt", ascending=False)
        else:
            cand = cand.reset_index(drop=False).sort_values("index", ascending=False)

    if cand.empty and fallback_any_event:
        cand = att_df[base_mask].copy()
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

# --- Data Loading ---
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = MAIN_SHEET_NAME, athletes_tab_name: str = ATHLETES_TAB_NAME):
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
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
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

def registrar_log(ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    """Log por NOME + EVENTO (não usa ID)."""
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
        load_attendance_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨")
        return False

# --- Main Application Logic ---
st.title(f"UAEW | {FIXED_TASK} Control")
display_user_sidebar()

# defaults da página (padrão: Status=Todos, Ordenar=Nome)
default_ss = {"selected_status": "Todos", "selected_event": "Todos os Eventos", "fighter_search_query": "", "sort_by": "Nome"}
for k, v in default_ss.items():
    if k not in st.session_state:
        st.session_state[k] = v

with st.spinner("Carregando dados..."):
    df_athletes = load_athlete_data()
    df_attendance_raw = load_attendance_data()
    tasks_raw, _ = load_config_data()

# Preprocess Attendance (SEM filtrar por evento)
df_attendance = preprocess_attendance(df_attendance_raw)

# --- Status atual do FIXED_TASK por atleta (por NOME + EVENTO) ---
if not df_athletes.empty:
    def _row_status(r):
        return pd.Series(status_for_current_event_by_name(
            df_attendance, r.get("name",""), r.get("event",""), FIXED_TASK
        ), index=["current_task_status", "latest_task_user", "latest_task_timestamp"])
    df_athletes[["current_task_status","latest_task_user","latest_task_timestamp"]] = df_athletes.apply(_row_status, axis=1)

# --- Filtros e ordenação ---
with st.expander("⚙️ Filtros e Ordenação", expanded=True):
    col_status, col_sort = st.columns(2)
    with col_status:
        STATUS_FILTER_LABELS = { "Todos": "Todos", STATUS_BASE: "Pendente", STATUS_REQUESTED: "Requisitado", STATUS_DONE: "Concluído"}
        st.segmented_control(
            "Filtrar por Status:",
            options=["Todos", STATUS_BASE, STATUS_REQUESTED, STATUS_DONE],
            format_func=lambda x: STATUS_FILTER_LABELS.get(x, x),
            key="selected_status"
        )
    with col_sort:
        st.segmented_control("Ordenar por:", options=["Nome", "Ordem de Luta"], key="sort_by", help="Escolha como ordenar a lista de atletas.")
    event_options = ["Todos os Eventos"] + (sorted([evt for evt in df_athletes["event"].unique() if evt != "Z"]) if not df_athletes.empty else [])
    st.selectbox("Filtrar Evento:", options=event_options, key="selected_event")
    st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")

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

if not df_filtered.empty:
    done_count = (df_filtered['current_task_status'] == STATUS_DONE).sum()
    requested_count = (df_filtered['current_task_status'] == STATUS_REQUESTED).sum()
    pending_count = (df_filtered['current_task_status'] == STATUS_BASE).sum()
    summary_html = f'''<div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 10px; margin-top: 10px;">
        <span style="font-weight: bold;">Exibindo {len(df_filtered)} de {len(df_athletes)} atletas:</span>
        <span style="background-color: {STATUS_COLOR_MAP[STATUS_DONE]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Done: {done_count}</span>
        <span style="background-color: {STATUS_COLOR_MAP[STATUS_REQUESTED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Requested: {requested_count}</span>
        <span style="background-color: #6c757d; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Pending/Cancelled: {pending_count}</span>
    </div>'''
    st.markdown(summary_html, unsafe_allow_html=True)

st.divider()

for i_l, row in df_filtered.iterrows():
    ath_id_d          = str(row.get("id", ""))
    ath_name_d        = str(row.get("name", ""))
    ath_event_d       = str(row.get("event", ""))
    ath_fight_number  = str(row.get("fight_number", ""))
    ath_corner_color  = str(row.get("corner", ""))
    mobile_number     = str(row.get("mobile", ""))
    passport_image_url= str(row.get("passport_image", ""))
    room_number       = str(row.get("room", ""))

    curr_ath_task_stat = row.get('current_task_status', STATUS_BASE)
    card_bg_col = STATUS_COLOR_MAP.get(curr_ath_task_stat, STATUS_COLOR_MAP[STATUS_BASE])

    # --- HTML Components ---
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

    # --- Badges para demais tasks (por NOME + EVENTO; sem ID) ---
    badges_html = ""
    if tasks_raw:
        status_color_map_badge = {"Requested": "#D35400", "Done": "#1E8449", "---": "#34495E"}
        default_color = "#34495E"
        name_n = normalize_name(ath_name_d)
        evt_n  = normalize_name(ath_event_d)
        for task_name in tasks_raw:
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
            if status_for_badge in STATUS_PENDING_EQUIVALENTS: color = default_color
            badges_html += f"<span style='background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;'>{html.escape(task_name)}</span>"

    # --- Último Blood Test (outro evento; badge "EVENTO | DATA") ---
    last_dt_str, last_event_str = last_blood_test_other_event_by_name(
        df_attendance, ath_name_d, ath_event_d, FIXED_TASK, fallback_any_event=True
    )
    if last_dt_str != "N/A" and last_event_str:
        last_blood_test_html = f"<span class='event-badge'>{html.escape(last_event_str)} | {html.escape(last_dt_str)}</span>"
    else:
        last_blood_test_html = "N/A"

    # --- Card Assembly ---
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

    col_card, col_buttons = st.columns([2.5, 1])

    with col_card:
        st.markdown(card_html, unsafe_allow_html=True)

    with col_buttons:
        uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
        if curr_ath_task_stat == STATUS_REQUESTED:
            st.markdown("<div class='mobile-button-row' style='padding-top: 20px'>", unsafe_allow_html=True)
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                st.markdown("<div class='green-button'>", unsafe_allow_html=True)
                if st.button("✅ Done", key=f"done_{ath_name_d}_{i_l}", use_container_width=True):
                    if registrar_log(ath_name_d, ath_event_d, FIXED_TASK, STATUS_DONE, "", uid_l):
                        time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with btn_c2:
                st.markdown("<div class='red-button'>", unsafe_allow_html=True)
                if st.button("❌ Cancel", key=f"cancel_{ath_name_d}_{i_l}", use_container_width=True):
                    if registrar_log(ath_name_d, ath_event_d, FIXED_TASK, STATUS_BASE, "Solicitação cancelada", uid_l):
                        time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='padding-top: 20px'>", unsafe_allow_html=True)
            btn_label = "📝 Request Again" if curr_ath_task_stat == STATUS_DONE else "📝 Request"
            btn_type = "secondary" if curr_ath_task_stat == STATUS_DONE else "primary"
            if st.button(btn_label, key=f"request_{ath_name_d}_{i_l}", type=btn_type, use_container_width=True):
                if registrar_log(ath_name_d, ath_event_d, FIXED_TASK, STATUS_REQUESTED, "", uid_l):
                    time.sleep(1); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
