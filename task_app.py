# ==============================================================================
# TASK MANAGEMENT CORE - REUSABLE STREAMLIT MODULE
# Reusable page logic for any fixed task (e.g., Photoshoot, Blood Test, etc.)
# ==============================================================================

# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import html
import time
import unicodedata
import re

# --- Project Imports (your existing helpers) ---
from utils import get_gspread_client, connect_gsheet_tab, load_users_data, get_valid_user_info, load_config_data
from auth import check_authentication, display_user_sidebar


# ==============================================================================
# CONSTANTS & CONFIG
# ==============================================================================
class BaseConfig:
    """Centralized application constants shared by all tasks."""
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"

    # Logical statuses:
    STATUS_PENDING = ""             # no request in current event
    STATUS_NOT_REQUESTED = "---"    # explicitly not required
    STATUS_REQUESTED = "Requested"
    STATUS_DONE = "Done"

    ALL_LOGICAL_STATUSES = [
        STATUS_PENDING, STATUS_NOT_REQUESTED, STATUS_REQUESTED, STATUS_DONE
    ]

    STATUS_COLOR_MAP = {
        STATUS_DONE: "#143d14",
        STATUS_REQUESTED: "#B08D00",
        STATUS_PENDING: "#1e1e1e",        # pending (no request)
        STATUS_NOT_REQUESTED: "#6c757d",  # explicitly not requested
        # extra fallbacks
        "Pending": "#1e1e1e",
        "Not Registred": "#1e1e1e",
        "Issue": "#1e1e1e"
    }

    # Column names (maintainability)
    COL_ID = "id"
    COL_NAME = "name"
    COL_EVENT = "event"
    COL_ROLE = "role"
    COL_INACTIVE = "inactive"
    COL_IMAGE = "image"
    COL_MOBILE = "mobile"
    COL_FIGHT_NUMBER = "fight_number"
    COL_CORNER = "corner"
    COL_PASSPORT_IMAGE = "passport_image"
    COL_ROOM = "room"

    # Attendance columns
    ATT_COL_EVENT = "Event"
    ATT_COL_NAME = "Name"
    ATT_COL_FIGHTER = "Fighter"
    ATT_COL_ATHLETE_ID = "Athlete ID"
    ATT_COL_TASK = "Task"
    ATT_COL_STATUS = "Status"
    ATT_COL_USER = "User"
    ATT_COL_TIMESTAMP = "Timestamp"     # leave this empty when writing
    ATT_COL_TIMESTAMP_ALT = "TimeStamp" # write here
    ATT_COL_NOTES = "Notes"
    ATT_COL_ID = "#"

    DEFAULT_EVENT_PLACEHOLDER = "Z"  # default value for missing events

    @staticmethod
    def map_raw_status_to_logical(raw_status: str) -> str:
        """Map a raw sheet status to our logical set."""
        raw_status = "" if raw_status is None else str(raw_status).strip()
        low = raw_status.lower()
        if low == BaseConfig.STATUS_DONE.lower():
            return BaseConfig.STATUS_DONE
        if low == BaseConfig.STATUS_REQUESTED.lower():
            return BaseConfig.STATUS_REQUESTED
        if raw_status == BaseConfig.STATUS_NOT_REQUESTED:  # exact '---'
            return BaseConfig.STATUS_NOT_REQUESTED
        return BaseConfig.STATUS_PENDING


# ==============================================================================
# UTILS
# ==============================================================================
_INVALID_STRS = {"", "none", "None", "null", "NULL", "nan", "NaN", "<NA>"}

def clean_and_normalize(text: str) -> str:
    """Lowercase, trim, remove accents, collapse spaces."""
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    return " ".join(text.split())

def parse_ts_series(raw: pd.Series) -> pd.Series:
    """Try multiple datetime formats; return datetime series."""
    if raw is None or raw.empty:
        return pd.Series([], dtype='datetime64[ns]')
    tries = [
        pd.to_datetime(raw, format="%d/%m/%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d/%m/%Y", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y", errors="coerce"),
        pd.to_datetime(raw, errors="coerce"),  # ISO fallback
    ]
    out = tries[0]
    for cand in tries[1:]:
        out = out.fillna(cand)
    return out

def _clean_str_series(s: pd.Series) -> pd.Series:
    """Clean string series and remove invalid placeholders."""
    if s is None or s.empty:
        return pd.Series([], dtype=str)
    s = s.fillna("").astype(str).str.strip()
    return s.replace({k: "" for k in _INVALID_STRS})

def _fmt_date_from_text(s: str) -> str:
    """Format any date-ish text to dd/mm/yyyy; else 'N/A'."""
    if s is None:
        return "N/A"
    s = str(s).strip()
    if s in _INVALID_STRS:
        return "N/A"
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt.strftime("%d/%m/%Y") if pd.notna(dt) else "N/A"

def make_task_mask(task_series: pd.Series, fixed_task: str, aliases: list[str] = None) -> pd.Series:
    """Boolean mask to match task name (with aliases)."""
    t = task_series.fillna("").astype(str).str.lower()
    pats = [re.escape(fixed_task.lower())] + list(aliases or [])
    regex = "(" + "|".join(pats) + ")"
    return t.str.contains(regex, regex=True, na=False)

def _slugify(s: str) -> str:
    """Cria um prefixo estável para keys do session_state a partir do título da página."""
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^a-zA-Z0-9]+', '_', s).strip('_').lower()
    return s or "page"

# ---- NEW: draw user sidebar only if unified wasn't rendered ----
def _safe_display_user_sidebar():
    """Renderiza o header do usuário no sidebar apenas se o sidebar unificado não foi desenhado."""
    if not st.session_state.get("_unified_sidebar_rendered", False):
        display_user_sidebar()


# ==============================================================================
# DATA LOADING (CACHED)
# ==============================================================================
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str, athletes_tab_name: str, cfg: BaseConfig) -> pd.DataFrame:
    """Load athletes sheet, apply filters and normalizations."""
    try:
        gspread_client = get_gspread_client()
        ws = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name)
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

        if cfg.COL_ROLE not in df.columns or cfg.COL_INACTIVE not in df.columns:
            st.error(f"Columns '{cfg.COL_ROLE.upper()}'/'{cfg.COL_INACTIVE.upper()}' not found in '{athletes_tab_name}'.", icon="🚨")
            return pd.DataFrame()

        if df[cfg.COL_INACTIVE].dtype == 'object':
            df[cfg.COL_INACTIVE] = df[cfg.COL_INACTIVE].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        elif pd.api.types.is_numeric_dtype(df[cfg.COL_INACTIVE]):
            df[cfg.COL_INACTIVE] = df[cfg.COL_INACTIVE].map({0: False, 1: True}).fillna(True)

        df = df[(df[cfg.COL_ROLE] == "1 - Fighter") & (df[cfg.COL_INACTIVE] == False)].copy()

        df[cfg.COL_EVENT] = df[cfg.COL_EVENT].fillna(cfg.DEFAULT_EVENT_PLACEHOLDER) if cfg.COL_EVENT in df.columns else cfg.DEFAULT_EVENT_PLACEHOLDER
        for col_check in [cfg.COL_IMAGE, cfg.COL_MOBILE, cfg.COL_FIGHT_NUMBER, cfg.COL_CORNER, cfg.COL_PASSPORT_IMAGE, cfg.COL_ROOM]:
            if col_check not in df.columns:
                df[col_check] = ""
            else:
                df[col_check] = df[col_check].fillna("")

        if cfg.COL_NAME not in df.columns:
            st.error(f"'{cfg.COL_NAME.upper()}' not found in '{athletes_tab_name}'.", icon="🚨")
            return pd.DataFrame()

        return df.sort_values(by=[cfg.COL_EVENT, cfg.COL_NAME]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading athletes (gspread): {e}", icon="🚨")
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str, attendance_tab_name: str, cfg: BaseConfig) -> pd.DataFrame:
    """Load attendance sheet and ensure required columns exist."""
    try:
        gspread_client = get_gspread_client()
        ws = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(ws.get_all_records())
        if df_att.empty:
            return pd.DataFrame(columns=[
                cfg.ATT_COL_ID, cfg.ATT_COL_EVENT, cfg.ATT_COL_NAME, cfg.ATT_COL_FIGHTER,
                cfg.ATT_COL_ATHLETE_ID, cfg.ATT_COL_TASK, cfg.ATT_COL_STATUS, cfg.ATT_COL_USER,
                cfg.ATT_COL_TIMESTAMP, cfg.ATT_COL_TIMESTAMP_ALT, cfg.ATT_COL_NOTES
            ])
        for col in [
            cfg.ATT_COL_ID, cfg.ATT_COL_EVENT, cfg.ATT_COL_NAME, cfg.ATT_COL_FIGHTER,
            cfg.ATT_COL_ATHLETE_ID, cfg.ATT_COL_TASK, cfg.ATT_COL_STATUS, cfg.ATT_COL_USER,
            cfg.ATT_COL_TIMESTAMP, cfg.ATT_COL_TIMESTAMP_ALT, cfg.ATT_COL_NOTES
        ]:
            if col not in df_att.columns:
                df_att[col] = pd.NA
        return df_att
    except Exception as e:
        st.error(f"Error loading attendance '{attendance_tab_name}': {e}", icon="🚨")
        return pd.DataFrame()


# ==============================================================================
# DATA PROCESSING
# ==============================================================================
@st.cache_data(ttl=120)
def preprocess_attendance(df_attendance: pd.DataFrame, cfg: BaseConfig) -> pd.DataFrame:
    """Normalize columns and parse timestamps."""
    if df_attendance is None or df_attendance.empty:
        return pd.DataFrame()
    df = df_attendance.copy()
    df["fighter_norm"] = df.get(cfg.ATT_COL_FIGHTER, "").astype(str).apply(clean_and_normalize)
    df["event_norm"]   = df.get(cfg.ATT_COL_EVENT, "").astype(str).apply(clean_and_normalize)
    # --- FIX: linha corrigida (sem syntax error) ---
    df["task_norm"]    = df.get(cfg.ATT_COL_TASK, "").astype(str).str.strip().str.lower()
    df["status_norm"]  = df.get(cfg.ATT_COL_STATUS, "").astype(str).str.strip().str.lower()

    # Prefer TimeStamp then fallback to Timestamp
    t2 = df.get(cfg.ATT_COL_TIMESTAMP_ALT)
    t1 = df.get(cfg.ATT_COL_TIMESTAMP)
    if t2 is None and t1 is None:
        df["TS_raw"] = ""
    else:
        s2 = _clean_str_series(t2) if t2 is not None else pd.Series([""]*len(df))
        s1 = _clean_str_series(t1) if t1 is not None else pd.Series([""]*len(df))
        df["TS_raw"] = s2.where(s2 != "", s1)

    df["TS_dt"] = parse_ts_series(df["TS_raw"])
    return df


def get_all_athletes_status(df_athletes: pd.DataFrame, df_attendance: pd.DataFrame, fixed_task: str, aliases: list[str], cfg: BaseConfig) -> pd.DataFrame:
    """Compute current fixed-task status for each athlete+event."""
    if df_athletes is None or df_athletes.empty:
        return pd.DataFrame(columns=[cfg.COL_NAME, cfg.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp'])

    base = df_athletes.copy()
    base['name_norm'] = base[cfg.COL_NAME].apply(clean_and_normalize)
    base['event_norm'] = base[cfg.COL_EVENT].apply(clean_and_normalize)

    if df_attendance is None or df_attendance.empty:
        base['current_task_status'] = cfg.STATUS_PENDING
        base['latest_task_user'] = 'N/A'
        base['latest_task_timestamp'] = 'N/A'
        return base[[cfg.COL_NAME, cfg.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]

    task_mask = make_task_mask(df_attendance["task_norm"], fixed_task, aliases)
    df_task = df_attendance[task_mask].copy()

    if df_task.empty:
        base['current_task_status'] = cfg.STATUS_PENDING
        base['latest_task_user'] = 'N/A'
        base['latest_task_timestamp'] = 'N/A'
        return base[[cfg.COL_NAME, cfg.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]

    df_task["__idx__"] = np.arange(len(df_task))

    merged = pd.merge(
        base[[cfg.COL_NAME, cfg.COL_EVENT, 'name_norm', 'event_norm']],
        df_task,
        left_on=['name_norm', 'event_norm'],
        right_on=['fighter_norm', 'event_norm'],
        how='left'
    ).sort_values(by=['name_norm', 'event_norm', 'TS_dt', '__idx__'], ascending=[True, True, False, False])

    latest = merged.drop_duplicates(subset=['name_norm', 'event_norm'], keep='first')

    latest['current_task_status'] = latest[cfg.ATT_COL_STATUS].apply(cfg.map_raw_status_to_logical)
    latest['latest_task_timestamp'] = latest.apply(
        lambda row: row['TS_dt'].strftime("%d/%m/%Y") if pd.notna(row.get('TS_dt', pd.NaT))
        else _fmt_date_from_text(row.get('TS_raw', row.get(cfg.ATT_COL_TIMESTAMP_ALT, row.get(cfg.ATT_COL_TIMESTAMP, '')))),
        axis=1
    )
    latest['latest_task_user'] = latest[cfg.ATT_COL_USER].fillna('N/A')

    return latest[[cfg.COL_NAME, cfg.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]


@st.cache_data(ttl=600)
def last_task_other_event_by_name(
    df_attendance: pd.DataFrame,
    athlete_name: str,
    current_event: str,
    fixed_task: str,
    aliases: list[str],
    cfg: BaseConfig,
    fallback_any_event: bool = True
) -> tuple[str, str]:
    """Return (date_str, event_name) of the last DONE record for the fixed task in a different event."""
    if df_attendance is None or df_attendance.empty:
        return "N/A", ""

    name_n = clean_and_normalize(athlete_name)
    evt_n  = clean_and_normalize(current_event)

    task_is = make_task_mask(df_attendance["task_norm"], fixed_task, aliases)
    status_done = df_attendance["status_norm"].str.fullmatch(cfg.STATUS_DONE.lower(), case=False, na=False)
    base_mask = (df_attendance["fighter_norm"] == name_n) & task_is & status_done

    cand = df_attendance[base_mask & (df_attendance["event_norm"] != evt_n)].copy()
    if not cand.empty:
        cand["__idx__"] = np.arange(len(cand))
        cand = cand.sort_values(by=["TS_dt", "__idx__"], ascending=[False, False])

    if cand.empty and fallback_any_event:
        cand = df_attendance[base_mask].copy()
        if not cand.empty:
            cand["__idx__"] = np.arange(len(cand))
            cand = cand.sort_values(by=["TS_dt", "__idx__"], ascending=[False, False])

    if cand.empty:
        return "N/A", ""

    row = cand.iloc[0]
    ev_label = str(row.get(cfg.ATT_COL_EVENT, "")).strip()
    if pd.notna(row.get("TS_dt", pd.NaT)):
        dt_str = row["TS_dt"].strftime("%d/%m/%Y")
    else:
        dt_str = _fmt_date_from_text(row.get("TS_raw", row.get(cfg.ATT_COL_TIMESTAMP_ALT, row.get(cfg.ATT_COL_TIMESTAMP, ""))))
    return dt_str, ev_label


# ==============================================================================
# LOGGING
# ==============================================================================
def _append_row_by_header(ws, values_by_colname: dict, cfg: BaseConfig) -> bool:
    """
    Append a row aligning values by existing header order.
    Creates a default header if the sheet is empty.
    """
    all_values = ws.get_all_values()
    if not all_values:
        header = [
            cfg.ATT_COL_ID, cfg.ATT_COL_EVENT, cfg.ATT_COL_NAME, cfg.ATT_COL_FIGHTER,
            cfg.ATT_COL_ATHLETE_ID, cfg.ATT_COL_TASK, cfg.ATT_COL_STATUS, cfg.ATT_COL_USER,
            cfg.ATT_COL_TIMESTAMP, cfg.ATT_COL_TIMESTAMP_ALT, cfg.ATT_COL_NOTES
        ]
        ws.append_row(header, value_input_option="USER_ENTERED")
        header_row = header
    else:
        header_row = all_values[0]

    next_num = len(all_values) + 1  # includes header row
    values_by_colname = dict(values_by_colname)
    values_by_colname.setdefault(cfg.ATT_COL_ID, str(next_num))

    aligned_row = [values_by_colname.get(h, "") for h in header_row]
    ws.append_row(aligned_row, value_input_option="USER_ENTERED")
    return True


def registrar_log(
    athlete_id: str,
    ath_name: str,
    ath_event: str,
    task: str,
    status: str,
    notes: str,
    user_log_id: str,
    cfg: BaseConfig
) -> bool:
    """
    Append a row to attendance, writing:
    - Athlete ID to 'Athlete ID'
    - Status ("" / "Requested" / "Done" / "---")
    - Notes to 'Notes'
    - ONLY write timestamp to 'TimeStamp' (leave 'Timestamp' empty)
    """
    try:
        gspread_client = get_gspread_client()
        ws = connect_gsheet_tab(gspread_client, cfg.MAIN_SHEET_NAME, cfg.ATTENDANCE_TAB_NAME)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)

        values = {
            cfg.ATT_COL_EVENT: ath_event,
            cfg.ATT_COL_NAME: ath_name,
            cfg.ATT_COL_FIGHTER: ath_name,
            cfg.ATT_COL_ATHLETE_ID: str(athlete_id or ""),
            cfg.ATT_COL_TASK: task,
            cfg.ATT_COL_STATUS: status,
            cfg.ATT_COL_USER: user_ident,
            cfg.ATT_COL_TIMESTAMP: "",     # keep empty
            cfg.ATT_COL_TIMESTAMP_ALT: ts, # write here
            cfg.ATT_COL_NOTES: notes or ""
        }

        _append_row_by_header(ws, values, cfg)

        lbl = "(empty/pending)" if status == cfg.STATUS_PENDING else ("Not Requested" if status == cfg.STATUS_NOT_REQUESTED else status)
        st.success(f"'{task}' for {ath_name} recorded as '{lbl}'.", icon="✍️")
        load_attendance_data.clear()  # force cache refresh
        return True
    except Exception as e:
        st.error(f"Error logging: {e}", icon="🚨")
        return False


# ==============================================================================
# UI RENDERING
# ==============================================================================
def render_athlete_card(row: pd.Series, last_info: tuple[str, str], badges_html: str, fixed_task: str, cfg: BaseConfig) -> str:
    """Return HTML card for an athlete."""
    ath_id_d = str(row.get(cfg.COL_ID, ""))
    ath_name_d = str(row.get(cfg.COL_NAME, ""))
    ath_event_d = str(row.get(cfg.COL_EVENT, ""))
    ath_fight_number = str(row.get(cfg.COL_FIGHT_NUMBER, ""))
    ath_corner_color = str(row.get(cfg.COL_CORNER, ""))
    mobile_number = str(row.get(cfg.COL_MOBILE, ""))
    passport_image_url = str(row.get(cfg.COL_PASSPORT_IMAGE, ""))
    room_number = str(row.get(cfg.COL_ROOM, ""))
    curr_ath_task_stat = row.get('current_task_status', cfg.STATUS_PENDING)
    card_bg_col = cfg.STATUS_COLOR_MAP.get(curr_ath_task_stat, cfg.STATUS_COLOR_MAP[cfg.STATUS_PENDING])

    corner_color_map = {'red': '#d9534f', 'blue': '#428bca'}
    label_color = corner_color_map.get(ath_corner_color.lower(), '#4A4A4A')
    info_parts = []
    if ath_event_d != cfg.DEFAULT_EVENT_PLACEHOLDER: info_parts.append(html.escape(ath_event_d))
    if ath_fight_number:   info_parts.append(f"FIGHT {html.escape(ath_fight_number)}")
    if ath_corner_color:   info_parts.append(html.escape(ath_corner_color.upper()))
    fight_info_text = " | ".join(info_parts)
    fight_info_label_html = (
        f"<span style='background-color: {label_color}; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>{fight_info_text}</span>"
        if fight_info_text else ""
    )

    whatsapp_tag_html = ""
    if mobile_number:
        phone_digits = "".join(filter(str.isdigit, mobile_number))
        if phone_digits.startswith('00'):
            phone_digits = phone_digits[2:]
        if phone_digits:
            escaped_phone = html.escape(phone_digits, True)
            whatsapp_tag_html = (
                f"<a href='https://wa.me/{escaped_phone}' target='_blank' style='text-decoration: none;'>"
                f"<span style='background-color: #25D366; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>WhatsApp</span>"
                f"</a>"
            )

    passport_tag_html = (
        f"<a href='{html.escape(passport_image_url, True)}' target='_blank' style='text-decoration: none;'>"
        f"<span style='background-color: #007BFF; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>Passport</span>"
        f"</a>"
        if passport_image_url and passport_image_url.startswith("http") else ""
    )

    task_label = html.escape(fixed_task)
    stat_text = "Pending" if curr_ath_task_stat in [cfg.STATUS_PENDING, None] else curr_ath_task_stat
    task_status_html = f"<small style='color:#ccc;'>{task_label}: <b>{html.escape(stat_text)}</b></small>"

    arrival_status_html = (
        f"<small style='color:#ccc;'>Arrival Status: <b>{html.escape(room_number)}</b></small>"
        if room_number else ""
    )

    last_dt_str, last_event_str = last_info
    last_label = f"Last {task_label}"
    last_html = (
        f"<span class='event-badge'>{html.escape(last_event_str)} | {html.escape(last_dt_str)}</span>"
        if last_dt_str != 'N/A' and last_event_str else "N/A"
    )

    card_html = f"""<div class='card-container' style='background-color:{card_bg_col};'>
        <img src='{html.escape(row.get(cfg.COL_IMAGE,"https://via.placeholder.com/60?text=NA"), True)}' class='card-img'>
        <div class='card-info'>
            <div class='info-line'><span class='fighter-name'>{html.escape(ath_name_d)} | {html.escape(ath_id_d)}</span></div>
            <div class='info-line'>{fight_info_label_html}</div>
            <div class='info-line'>{whatsapp_tag_html}{passport_tag_html}</div>
            <div class='info-line'>{task_status_html}</div>
            <div class='info-line'>{arrival_status_html}</div>
            <hr style='border-color: #444; margin: 5px 0; width: 100%;'>
            <div class='task-badges'>{badges_html}</div>
            <div class='info-line' style='margin-top:6px;'>
                <small style='color:#ccc;'>{html.escape(last_label)}: <b>{last_html}</b></small>
            </div>
        </div>
    </div>"""
    return card_html


# ==============================================================================
# PAGE RENDERER (ENTRYPOINT)
# ==============================================================================
#def render_task_page(page_title: str, fixed_task: str, task_aliases: list[str]):
#    """
#    Render a full Streamlit page for a single fixed task.
#    Garante filtros padrão: Status="All" e Event="All Events" por página.
#    """
#    # Só configura página e autentica se o sidebar unificado AINDA não foi renderizado.
#    if not st.session_state.get("_unified_sidebar_rendered", False):
#        st.set_page_config(page_title=page_title, layout="wide")  # primeira chamada UI
#        check_authentication()#

##    # Título e header do usuário (evita duplicar se já há sidebar unificado)
#    st.title(page_title)
#    _safe_display_user_sidebar()


def render_task_page(page_title: str, fixed_task: str, task_aliases: list[str]):
    # Config & auth já vieram do bootstrap_page()
    st.title(page_title)




    cfg = BaseConfig  # alias

    # Prefixo único para as chaves desta página
    _kpref = _slugify(page_title)

    # Global CSS
    st.markdown("""
    <style>
        .card-container { padding: 15px; border-radius: 10px; margin-bottom: 10px; display: flex; align-items: flex-start; gap: 15px; }
        .card-img { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
        .card-info { width: 100%; display: flex; flex-direction: column; gap: 8px; }
        .info-line { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
        .fighter-name { font-size: 1.25rem; font-weight: bold; margin: 0; color: white; }
        .task-badges { display: flex; flex-wrap: wrap; gap: 8px; }
        .event-badge { background-color: #428bca; color: #fff; padding: 3px 8px; border-radius: 8px; font-size: 0.75rem; font-weight: bold; display: inline-block; }
        .button-group-row { display: flex; gap: 10px; margin-top: 10px; width: 100%; }
        .button-group-row > div { flex: 1; }
        div.stButton > button { width: 100%; }
        .green-button button { background-color: #28a745; color: white !important; border: 1px solid #28a745; }
        .green-button button:hover { background-color: #218838; color: white !important; border: 1px solid #218838; }
        .red-button button { background-color: #dc3545; color: white !important; border: 1px solid #dc3545; }
        .red-button button:hover { background-color: #c82333; color: white !important; border: 1px solid #c82333; }
    </style>
    """, unsafe_allow_html=True)

    # Chaves de estado únicas por página
    K_STATUS = f"{_kpref}_selected_status"
    K_EVENT  = f"{_kpref}_selected_event"
    K_SEARCH = f"{_kpref}_fighter_search_query"
    K_SORT   = f"{_kpref}_sort_by"

    # Defaults garantidos (primeiro load da página)
    if K_STATUS not in st.session_state:
        st.session_state[K_STATUS] = "All"
    if K_EVENT not in st.session_state:
        st.session_state[K_EVENT] = "All Events"
    if K_SEARCH not in st.session_state:
        st.session_state[K_SEARCH] = ""
    if K_SORT not in st.session_state:
        st.session_state[K_SORT] = "Name"

    # Load data
    with st.spinner("Loading data..."):
        df_athletes = load_athlete_data(cfg.MAIN_SHEET_NAME, cfg.ATHLETES_TAB_NAME, cfg)
        df_attendance_raw = load_attendance_data(cfg.MAIN_SHEET_NAME, cfg.ATTENDANCE_TAB_NAME, cfg)
        tasks_raw, _ = load_config_data()
        tasks_raw = [str(x) for x in (tasks_raw or [])]

    # Preprocess
    df_attendance = preprocess_attendance(df_attendance_raw, cfg)

    # Status per athlete
    if not df_athletes.empty:
        athletes_status = get_all_athletes_status(df_athletes, df_attendance, fixed_task, task_aliases, cfg)
        df_athletes = pd.merge(df_athletes, athletes_status, on=[cfg.COL_NAME, cfg.COL_EVENT], how='left')
        df_athletes.fillna({
            'current_task_status': cfg.STATUS_PENDING,
            'latest_task_user': 'N/A',
            'latest_task_timestamp': 'N/A'
        }, inplace=True)

    # Filters & sorting
    with st.expander("Settings", expanded=True):
        col_status, col_sort = st.columns(2)
        with col_status:
            STATUS_FILTER_LABELS = {
                "All": "All",
                cfg.STATUS_PENDING: "Pending",
                cfg.STATUS_REQUESTED: "Requested",
                cfg.STATUS_DONE: "Done",
                cfg.STATUS_NOT_REQUESTED: "Not Requested (---)"
            }
            st.segmented_control(
                "Filter by Status:",
                options=["All", cfg.STATUS_PENDING, cfg.STATUS_REQUESTED, cfg.STATUS_DONE, cfg.STATUS_NOT_REQUESTED],
                format_func=lambda x: STATUS_FILTER_LABELS.get(x, x if x else "Pending"),
                key=K_STATUS
            )
        with col_sort:
            st.segmented_control(
                "Sort by:",
                options=["Name", "Fight Order"],
                key=K_SORT,
                help="Choose how to sort the athletes list."
            )

        # Eventos disponíveis
        event_options = ["All Events"] + (
            sorted([evt for evt in df_athletes[cfg.COL_EVENT].unique() if evt != cfg.DEFAULT_EVENT_PLACEHOLDER])
            if not df_athletes.empty else []
        )
        # Se o valor salvo não existe mais (ou é primeira vez), força "All Events"
        if st.session_state[K_EVENT] not in event_options:
            st.session_state[K_EVENT] = "All Events"

        st.selectbox("Filter by Event:", options=event_options, key=K_EVENT)
        st.text_input("Search Athlete:", placeholder="Type athlete name or ID...", key=K_SEARCH)

    # Valores atuais dos filtros (por página)
    selected_status = st.session_state[K_STATUS]
    selected_event  = st.session_state[K_EVENT]
    search_query    = st.session_state[K_SEARCH]
    sort_by         = st.session_state[K_SORT]

    # Apply filters
    df_filtered = df_athletes.copy()
    if not df_filtered.empty:
        if selected_event != "All Events":
            df_filtered = df_filtered[df_filtered[cfg.COL_EVENT] == selected_event]

        search_term = search_query.strip().lower()
        if search_term:
            df_filtered = df_filtered[
                df_filtered[cfg.COL_NAME].str.lower().str.contains(search_term, na=False) |
                df_filtered[cfg.COL_ID].astype(str).str.contains(search_term, na=False)
            ]

        if selected_status != "All":
            df_filtered = df_filtered[df_filtered['current_task_status'] == selected_status]

        if sort_by == 'Fight Order':
            df_filtered['FIGHT_NUMBER_NUM'] = pd.to_numeric(df_filtered[cfg.COL_FIGHT_NUMBER], errors='coerce').fillna(999)
            df_filtered['CORNER_SORT'] = df_filtered[cfg.COL_CORNER].str.lower().map({'blue': 0, 'red': 1}).fillna(2)
            df_filtered = df_filtered.sort_values(by=['FIGHT_NUMBER_NUM', 'CORNER_SORT'], ascending=[True, True])
        else:
            df_filtered = df_filtered.sort_values(by=cfg.COL_NAME, ascending=True)

    # Status summary
    if not df_filtered.empty:
        done_count = (df_filtered['current_task_status'] == cfg.STATUS_DONE).sum()
        requested_count = (df_filtered['current_task_status'] == cfg.STATUS_REQUESTED).sum()
        pending_count = (df_filtered['current_task_status'] == cfg.STATUS_PENDING).sum()
        notreq_count = (df_filtered['current_task_status'] == cfg.STATUS_NOT_REQUESTED).sum()
        summary_html = f'''<div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 10px; margin-top: 10px;">
            <span style="font-weight: bold;">Showing {len(df_filtered)} of {len(df_athletes)} athletes:</span>
            <span style="background-color: {cfg.STATUS_COLOR_MAP[cfg.STATUS_DONE]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Done: {done_count}</span>
            <span style="background-color: {cfg.STATUS_COLOR_MAP[cfg.STATUS_REQUESTED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Requested: {requested_count}</span>
            <span style="background-color: {cfg.STATUS_COLOR_MAP[cfg.STATUS_PENDING]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Pending: {pending_count}</span>
            <span style="background-color: {cfg.STATUS_COLOR_MAP[cfg.STATUS_NOT_REQUESTED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Not Requested: {notreq_count}</span>
        </div>'''
        st.markdown(summary_html, unsafe_allow_html=True)

    st.divider()

    # Render athlete cards
    for i_l, row in df_filtered.iterrows():
        # Last fixed-task info in another event
        last_dt_str, last_event_str = last_task_other_event_by_name(
            df_attendance, row[cfg.COL_NAME], row[cfg.COL_EVENT], fixed_task, task_aliases, cfg, fallback_any_event=True
        )

        # Badges for other tasks
        badges_html = ""
        if tasks_raw:
            status_color_map_badge = {
                cfg.STATUS_REQUESTED: "#D35400",
                cfg.STATUS_DONE: "#1E8449",
                cfg.STATUS_NOT_REQUESTED: "#6c757d",
                cfg.STATUS_PENDING: "#34495E"
            }
            default_color = "#34495E"
            name_n = clean_and_normalize(row[cfg.COL_NAME])
            evt_n  = clean_and_normalize(row[cfg.COL_EVENT])
            for task_name in tasks_raw:
                if str(task_name).strip().lower() == fixed_task.lower():
                    continue
                status_for_badge = cfg.STATUS_PENDING
                if not df_attendance.empty:
                    t_norm = str(task_name).strip().lower()
                    mask_t = (df_attendance["task_norm"] == t_norm)
                    mask = (df_attendance["fighter_norm"] == name_n) & (df_attendance["event_norm"] == evt_n) & mask_t
                    task_records = df_attendance.loc[mask].copy()
                    if not task_records.empty:
                        task_records["__idx__"] = np.arange(len(task_records))
                        task_records = task_records.sort_values(by=["TS_dt", "__idx__"], ascending=[False, False])
                        status_for_badge = cfg.map_raw_status_to_logical(str(task_records.iloc[0].get(cfg.ATT_COL_STATUS, cfg.STATUS_PENDING)))

                color = status_color_map_badge.get(status_for_badge, default_color)
                badges_html += (
                    f"<span style='background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; "
                    f"font-size: 12px; font-weight: bold;'>{html.escape(task_name)}</span>"
                )

        # Card
        card_html = render_athlete_card(row, (last_dt_str, last_event_str), badges_html, fixed_task, cfg)
        col_card, col_buttons = st.columns([2.5, 1])
        with col_card:
            st.markdown(card_html, unsafe_allow_html=True)

        with col_buttons:
            uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
            curr = row.get('current_task_status', cfg.STATUS_PENDING)
            athlete_id_val = row.get(cfg.COL_ID, "")

            # Per-card notes
            notes_key = f"notes_input_{i_l}"
            st.text_area("Notes", key=notes_key, placeholder="Add notes here...", height=50)
            current_notes = st.session_state.get(notes_key, "")

            st.markdown("<div class='button-group-row'>", unsafe_allow_html=True)

            if curr == cfg.STATUS_REQUESTED:
                # Requested → Done / Cancel (Cancel marks Not Requested with canned note)
                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    st.markdown("<div class='green-button'>", unsafe_allow_html=True)
                    if st.button("Done", key=f"done_{row[cfg.COL_NAME]}_{i_l}", use_container_width=True, help="Mark task as completed"):
                        if registrar_log(athlete_id_val, row[cfg.COL_NAME], row[cfg.COL_EVENT], fixed_task, cfg.STATUS_DONE, current_notes, uid_l, cfg):
                            time.sleep(1); st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                with btn_c2:
                    st.markdown("<div class='red-button'>", unsafe_allow_html=True)
                    if st.button("Cancel", key=f"cancel_{row[cfg.COL_NAME]}_{i_l}", use_container_width=True, help="Cancel request and set status to Not Requested"):
                        if registrar_log(athlete_id_val, row[cfg.COL_NAME], row[cfg.COL_EVENT], fixed_task, cfg.STATUS_NOT_REQUESTED, "Canceled by user", uid_l, cfg):
                            time.sleep(1); st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

            else:
                # Default flow:
                # - If NOT_REQUESTED: only show Request (hide Not Requested button)
                # - If PENDING or DONE: show Request and Not Requested
                if curr == cfg.STATUS_NOT_REQUESTED:
                    if st.button("Request", key=f"request_{row[cfg.COL_NAME]}_{i_l}", type="primary", use_container_width=True, help="Create a new request"):
                        if registrar_log(athlete_id_val, row[cfg.COL_NAME], row[cfg.COL_EVENT], fixed_task, cfg.STATUS_REQUESTED, current_notes, uid_l, cfg):
                            time.sleep(1); st.rerun()
                else:
                    btn_l, btn_r = st.columns(2)
                    with btn_l:
                        btn_label = "Request Again" if curr == cfg.STATUS_DONE else "Request"
                        btn_type = "secondary" if curr == cfg.STATUS_DONE else "primary"
                        if st.button(btn_label, key=f"request_{row[cfg.COL_NAME]}_{i_l}", type=btn_type, use_container_width=True, help="Create a new request"):
                            if registrar_log(athlete_id_val, row[cfg.COL_NAME], row[cfg.COL_EVENT], fixed_task, cfg.STATUS_REQUESTED, current_notes, uid_l, cfg):
                                time.sleep(1); st.rerun()
                    with btn_r:
                        if st.button("Not Requested", key=f"notrequested_{row[cfg.COL_NAME]}_{i_l}", use_container_width=True, help="Mark that this athlete does not need this task for this event"):
                            if registrar_log(athlete_id_val, row[cfg.COL_NAME], row[cfg.COL_EVENT], fixed_task, cfg.STATUS_NOT_REQUESTED, current_notes, uid_l, cfg):
                                time.sleep(1); st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
