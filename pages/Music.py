# ==============================================================================
# WALKOUT MUSIC MANAGEMENT SYSTEM - STREAMLIT APP
# ==============================================================================

# --- 0. Import Libraries ---
import streamlit as st
st.set_page_config(page_title="Walkout Music", layout="wide")  # keep as first UI call

import pandas as pd
import numpy as np
from datetime import datetime
import html
import time
import unicodedata
import re

# --- Project Imports ---
from utils import get_gspread_client, connect_gsheet_tab, load_config_data
from auth import check_authentication, display_user_sidebar


# ==============================================================================
# CONSTANTS & CONFIG
# ==============================================================================
class Config:
    """Centralizes constants and column names for consistency."""
    # Sheets / Tabs
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"

    # Fixed Task name for this page
    FIXED_TASK = "Walkout Music"

    # Task aliases (in case historical logs vary)
    TASK_ALIASES = [r"\bwalkout\s*music\b", r"\bwalkout\b", r"\bmusic\b"]

    # Logical statuses
    STATUS_PENDING = ""           # no request in the current event
    STATUS_NOT_REQUESTED = "---"  # explicitly not needed / not requested
    STATUS_REQUESTED = "Requested"
    STATUS_DONE = "Done"

    STATUS_COLOR_MAP = {
        STATUS_DONE: "#143d14",
        STATUS_REQUESTED: "#B08D00",
        STATUS_PENDING: "#1e1e1e",
        STATUS_NOT_REQUESTED: "#6c757d",
        # Raw fallbacks
        "Pending": "#1e1e1e",
        "Not Registred": "#1e1e1e",
        "Issue": "#1e1e1e",
    }

    # Athletes DF columns (normalized lower_snake case)
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

    DEFAULT_EVENT_PLACEHOLDER = "Z"

    # Attendance columns (as they appear in Google Sheet)
    ATT_COL_ROWID = "#"
    ATT_COL_EVENT = "Event"
    ATT_COL_ATHLETE_ID = "Athlete ID"
    ATT_COL_NAME = "Name"
    ATT_COL_FIGHTER = "Fighter"
    ATT_COL_TASK = "Task"
    ATT_COL_STATUS = "Status"
    ATT_COL_USER = "User"
    ATT_COL_TIMESTAMP = "Timestamp"       # kept for compatibility
    ATT_COL_TIMESTAMP_ALT = "TimeStamp"   # required by your spec
    ATT_COL_NOTES = "Notes"

    @staticmethod
    def map_raw_status(raw_status: str) -> str:
        s = "" if raw_status is None else str(raw_status).strip()
        sl = s.lower()
        if sl == "done":
            return Config.STATUS_DONE
        if sl == "requested":
            return Config.STATUS_REQUESTED
        if s == Config.STATUS_NOT_REQUESTED:
            return Config.STATUS_NOT_REQUESTED
        return Config.STATUS_PENDING


# ==============================================================================
# HELPERS
# ==============================================================================
_INVALID_STRS = {"", "none", "None", "null", "NULL", "nan", "NaN", "<NA>"}

def clean_and_normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    return " ".join(text.split())

def parse_ts_series(raw: pd.Series) -> pd.Series:
    if raw is None or raw.empty:
        return pd.Series([], dtype='datetime64[ns]')
    tries = [
        pd.to_datetime(raw, format="%d/%m/%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d/%m/%Y", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, format="%d-%m-%Y", errors="coerce"),
        pd.to_datetime(raw, errors="coerce"),
    ]
    ts_final = tries[0]
    for cand in tries[1:]:
        ts_final = ts_final.fillna(cand)
    return ts_final

def _clean_str_series(s: pd.Series) -> pd.Series:
    if s is None or s.empty:
        return pd.Series([], dtype=str)
    s = s.fillna("").astype(str).str.strip()
    return s.replace({k: "" for k in _INVALID_STRS})

def _fmt_date_from_text(s: str) -> str:
    if s is None:
        return "N/A"
    s = str(s).strip()
    if s in _INVALID_STRS:
        return "N/A"
    dt = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return dt.strftime("%d/%m/%Y") if pd.notna(dt) else "N/A"

def make_task_mask(task_series: pd.Series, fixed_task: str, aliases: list[str] = None) -> pd.Series:
    t = task_series.fillna("").astype(str).str.lower()
    pats = [re.escape(fixed_task.lower())] + list(aliases or [])
    regex = "(" + "|".join(pats) + ")"
    return t.str.contains(regex, regex=True, na=False)

def join_links(*links: str) -> str:
    """Join non-empty links as a newline-separated string for Notes."""
    vals = [l.strip() for l in links if isinstance(l, str) and l.strip()]
    return "\n".join(vals)


# ==============================================================================
# DATA LOADING (with cache)
# ==============================================================================
@st.cache_data(ttl=600)
def load_athletes() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATHLETES_TAB_NAME)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        if Config.COL_ROLE not in df.columns or Config.COL_INACTIVE not in df.columns:
            st.error("Columns 'ROLE'/'INACTIVE' not found in athletes sheet.", icon="🚨")
            return pd.DataFrame()

        if df[Config.COL_INACTIVE].dtype == "object":
            df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].astype(str).str.upper().map(
                {"FALSE": False, "TRUE": True, "": True}
            ).fillna(True)
        elif pd.api.types.is_numeric_dtype(df[Config.COL_INACTIVE]):
            df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].map({0: False, 1: True}).fillna(True)

        df = df[(df[Config.COL_ROLE] == "1 - Fighter") & (df[Config.COL_INACTIVE] == False)].copy()

        df[Config.COL_EVENT] = df.get(Config.COL_EVENT, "").fillna(Config.DEFAULT_EVENT_PLACEHOLDER)
        for col in [Config.COL_IMAGE, Config.COL_MOBILE, Config.COL_FIGHT_NUMBER, Config.COL_CORNER, Config.COL_PASSPORT_IMAGE, Config.COL_ROOM]:
            if col not in df.columns:
                df[col] = ""
            else:
                df[col] = df[col].fillna("")

        if Config.COL_NAME not in df.columns or Config.COL_ID not in df.columns:
            st.error("'name' or 'id' missing in athletes sheet.", icon="🚨")
            return pd.DataFrame()

        return df.sort_values(by=[Config.COL_EVENT, Config.COL_NAME]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading athletes: {e}", icon="🚨")
        return pd.DataFrame()


@st.cache_data(ttl=120)
def load_attendance() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB_NAME)
        df_att = pd.DataFrame(ws.get_all_records())
        if df_att.empty:
            return pd.DataFrame(columns=[
                Config.ATT_COL_ROWID, Config.ATT_COL_EVENT, Config.ATT_COL_ATHLETE_ID,
                Config.ATT_COL_NAME, Config.ATT_COL_FIGHTER, Config.ATT_COL_TASK, Config.ATT_COL_STATUS,
                Config.ATT_COL_USER, Config.ATT_COL_TIMESTAMP, Config.ATT_COL_TIMESTAMP_ALT, Config.ATT_COL_NOTES
            ])
        for col in [
            Config.ATT_COL_ROWID, Config.ATT_COL_EVENT, Config.ATT_COL_ATHLETE_ID,
            Config.ATT_COL_NAME, Config.ATT_COL_FIGHTER, Config.ATT_COL_TASK, Config.ATT_COL_STATUS,
            Config.ATT_COL_USER, Config.ATT_COL_TIMESTAMP, Config.ATT_COL_TIMESTAMP_ALT, Config.ATT_COL_NOTES
        ]:
            if col not in df_att.columns:
                df_att[col] = pd.NA
        df_att[Config.ATT_COL_ATHLETE_ID] = df_att[Config.ATT_COL_ATHLETE_ID].astype(str)
        return df_att
    except Exception as e:
        st.error(f"Error loading attendance: {e}", icon="🚨")
        return pd.DataFrame()


@st.cache_data(ttl=120)
def preprocess_attendance(df_attendance: pd.DataFrame) -> pd.DataFrame:
    if df_attendance is None or df_attendance.empty:
        return pd.DataFrame()
    df = df_attendance.copy()
    df["fighter_norm"] = df.get(Config.ATT_COL_FIGHTER, "").astype(str).apply(clean_and_normalize)
    df["event_norm"]   = df.get(Config.ATT_COL_EVENT, "").astype(str).apply(clean_and_normalize)
    df["task_norm"]    = df.get(Config.ATT_COL_TASK, "").astype(str).str.strip().str.lower()
    df["status_norm"]  = df.get(Config.ATT_COL_STATUS, "").astype(str).str.strip().str.lower()

    t2 = df.get(Config.ATT_COL_TIMESTAMP_ALT)  # prioritize TimeStamp
    t1 = df.get(Config.ATT_COL_TIMESTAMP)
    if t2 is None and t1 is None:
        df["TS_raw"] = ""
    else:
        s2 = _clean_str_series(t2) if t2 is not None else pd.Series([""]*len(df))
        s1 = _clean_str_series(t1) if t1 is not None else pd.Series([""]*len(df))
        df["TS_raw"] = s2.where(s2 != "", s1)

    df["TS_dt"] = parse_ts_series(df["TS_raw"])
    return df


def compute_task_status_for_athletes(df_athletes, df_attendance, fixed_task: str) -> pd.DataFrame:
    """Compute current status by athlete & current event for the fixed task."""
    if df_athletes is None or df_athletes.empty:
        return pd.DataFrame(columns=[Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp'])

    base = df_athletes.copy()
    base['name_norm'] = base[Config.COL_NAME].apply(clean_and_normalize)
    base['event_norm'] = base[Config.COL_EVENT].apply(clean_and_normalize)

    if df_attendance is None or df_attendance.empty:
        base['current_task_status'] = Config.STATUS_PENDING
        base['latest_task_user'] = 'N/A'
        base['latest_task_timestamp'] = 'N/A'
        return base[[Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]

    task_mask = make_task_mask(df_attendance["task_norm"], fixed_task, Config.TASK_ALIASES)
    df_task = df_attendance[task_mask].copy()
    if df_task.empty:
        base['current_task_status'] = Config.STATUS_PENDING
        base['latest_task_user'] = 'N/A'
        base['latest_task_timestamp'] = 'N/A'
        return base[[Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]

    df_task["__idx__"] = np.arange(len(df_task))
    merged = pd.merge(
        base[[Config.COL_NAME, Config.COL_EVENT, 'name_norm', 'event_norm']],
        df_task,
        left_on=['name_norm', 'event_norm'],
        right_on=['fighter_norm', 'event_norm'],
        how='left'
    )
    merged = merged.sort_values(by=['name_norm', 'event_norm', 'TS_dt', '__idx__'], ascending=[True, True, False, False])
    latest = merged.drop_duplicates(subset=['name_norm', 'event_norm'], keep='first')

    latest['current_task_status'] = latest[Config.ATT_COL_STATUS].apply(Config.map_raw_status)
    latest['latest_task_timestamp'] = latest.apply(
        lambda r: r['TS_dt'].strftime("%d/%m/%Y") if pd.notna(r.get('TS_dt', pd.NaT))
        else _fmt_date_from_text(r.get('TS_raw', r.get(Config.ATT_COL_TIMESTAMP_ALT, r.get(Config.ATT_COL_TIMESTAMP, '')))),
        axis=1
    )
    latest['latest_task_user'] = latest[Config.ATT_COL_USER].fillna('N/A')

    return latest[[Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]


def registrar_log(
    athlete_id: str,
    ath_name: str,
    ath_event: str,
    task: str,
    status: str,
    user_log_id: str,
    notes: str = ""
) -> bool:
    """
    Append a row to Attendance with columns:
    ["#", "Event", "Athlete ID", "Name", "Fighter", "Task", "Status", "User", "Timestamp", "TimeStamp", "Notes"]
    """
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB_NAME)
        all_vals = ws.get_all_values()
        next_num = (int(all_vals[-1][0]) + 1) if (len(all_vals) > 1 and str(all_vals[-1][0]).isdigit()) else (len(all_vals) + 1)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)

        new_row = [
            str(next_num),
            ath_event,
            str(athlete_id),
            ath_name,
            ath_name,
            task,
            status,
            user_ident,
            ts,  # "Timestamp"
            ts,  # "TimeStamp"
            notes
        ]
        ws.append_row(new_row, value_input_option="USER_ENTERED")
        load_attendance.clear()
        return True
    except Exception as e:
        st.error(f"Error writing Attendance: {e}", icon="🚨")
        return False


# ==============================================================================
# PAGE UI & LOGIC
# ==============================================================================
check_authentication()
st.title("Walkout Music")
display_user_sidebar()

# --- Defaults ---
default_ss = {
    "selected_status": "All",
    "selected_event": "All Events",
    "fighter_search_query": "",
    "sort_by": "Name",
}
for k, v in default_ss.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- Load Data ---
with st.spinner("Loading data..."):
    df_athletes = load_athletes()
    df_att_raw = load_attendance()
    tasks_raw, _ = load_config_data()

df_att = preprocess_attendance(df_att_raw)

# --- Compute current status per athlete (for Task = Walkout Music) ---
if not df_athletes.empty:
    st_status = compute_task_status_for_athletes(df_athletes, df_att, Config.FIXED_TASK)
    df_athletes = pd.merge(df_athletes, st_status, on=[Config.COL_NAME, Config.COL_EVENT], how='left')
    df_athletes.fillna({
        'current_task_status': Config.STATUS_PENDING,
        'latest_task_user': 'N/A',
        'latest_task_timestamp': 'N/A'
    }, inplace=True)

# --- Settings ---
with st.expander("Settings", expanded=True):
    col_status, col_sort = st.columns(2)
    with col_status:
        STATUS_FILTER_LABELS = {
            "All": "All",
            Config.STATUS_PENDING: "Pending",
            Config.STATUS_REQUESTED: "Requested",
            Config.STATUS_DONE: "Done",
            Config.STATUS_NOT_REQUESTED: "Not Requested"
        }
        st.segmented_control(
            "Filter by Status:",
            options=["All", Config.STATUS_PENDING, Config.STATUS_REQUESTED, Config.STATUS_DONE, Config.STATUS_NOT_REQUESTED],
            format_func=lambda x: STATUS_FILTER_LABELS.get(x, x if x else "Pending"),
            key="selected_status"
        )
    with col_sort:
        st.segmented_control(
            "Sort by:",
            options=["Name", "Fight Order"],
            key="sort_by",
            help="Choose how to sort the athletes list."
        )

    event_options = ["All Events"] + (
        sorted([evt for evt in df_athletes[Config.COL_EVENT].unique() if evt != Config.DEFAULT_EVENT_PLACEHOLDER])
        if not df_athletes.empty else []
    )
    st.selectbox("Filter by Event:", options=event_options, key="selected_event")
    st.text_input("Search Athlete:", placeholder="Type athlete name or ID...", key="fighter_search_query")

# --- Apply filters/sorting ---
df_filtered = df_athletes.copy()
if not df_filtered.empty:
    if st.session_state.selected_event != "All Events":
        df_filtered = df_filtered[df_filtered[Config.COL_EVENT] == st.session_state.selected_event]

    term = st.session_state.fighter_search_query.strip().lower()
    if term:
        df_filtered = df_filtered[
            df_filtered[Config.COL_NAME].str.lower().str.contains(term, na=False) |
            df_filtered[Config.COL_ID].astype(str).str.contains(term, na=False)
        ]

    if st.session_state.selected_status != "All":
        df_filtered = df_filtered[df_filtered['current_task_status'] == st.session_state.selected_status]

    if st.session_state.get('sort_by', 'Name') == 'Fight Order':
        df_filtered['FIGHT_NUMBER_NUM'] = pd.to_numeric(df_filtered[Config.COL_FIGHT_NUMBER], errors='coerce').fillna(999)
        df_filtered['CORNER_SORT'] = df_filtered[Config.COL_CORNER].str.lower().map({'blue': 0, 'red': 1}).fillna(2)
        df_filtered = df_filtered.sort_values(by=['FIGHT_NUMBER_NUM', 'CORNER_SORT'], ascending=[True, True])
    else:
        df_filtered = df_filtered.sort_values(by=Config.COL_NAME, ascending=True)

# --- Summary badges ---
if not df_filtered.empty:
    done_count = (df_filtered['current_task_status'] == Config.STATUS_DONE).sum()
    requested_count = (df_filtered['current_task_status'] == Config.STATUS_REQUESTED).sum()
    pending_count = (df_filtered['current_task_status'] == Config.STATUS_PENDING).sum()
    not_needed_count = (df_filtered['current_task_status'] == Config.STATUS_NOT_REQUESTED).sum()
    summary_html = f'''<div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin: 10px 0;">
        <span style="font-weight: bold;">Showing {len(df_filtered)} of {len(df_athletes)} athletes:</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_DONE]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Done: {done_count}</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_REQUESTED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Requested: {requested_count}</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_PENDING]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Pending: {pending_count}</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_NOT_REQUESTED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Not Requested: {not_needed_count}</span>
    </div>'''
    st.markdown(summary_html, unsafe_allow_html=True)

st.divider()

# --- CSS (same as other pages) ---
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
    .button-group-row {
        display: flex;
        gap: 10px;
        margin-top: 10px;
        width: 100%;
    }
    .button-group-row > div { flex: 1; }
    div.stButton > button { width: 100%; }
    .green-button button { background-color: #28a745; color: white !important; border: 1px solid #28a745; }
    .green-button button:hover { background-color: #218838; color: white !important; border: 1px solid #218838; }
    .red-button button { background-color: #dc3545; color: white !important; border: 1px solid #dc3545; }
    .red-button button:hover { background-color: #c82333; color: white !important; border: 1px solid #c82333; }
</style>
""", unsafe_allow_html=True)

# --- Render loop (cards + action panel with music links) ---
for i_l, row in df_filtered.iterrows():
    ath_id = str(row.get(Config.COL_ID, ""))
    ath_name = str(row.get(Config.COL_NAME, ""))
    ath_event = str(row.get(Config.COL_EVENT, ""))

    curr_status = row.get('current_task_status', Config.STATUS_PENDING)
    card_bg_col = Config.STATUS_COLOR_MAP.get(curr_status, Config.STATUS_COLOR_MAP[Config.STATUS_PENDING])

    # Compose label (Event | Fight N | Corner)
    corner_color_map = {'red': '#d9534f', 'blue': '#428bca'}
    label_color = corner_color_map.get(str(row.get(Config.COL_CORNER, "")).lower(), '#4A4A4A')
    info_parts = []
    if ath_event != Config.DEFAULT_EVENT_PLACEHOLDER:
        info_parts.append(html.escape(ath_event))
    if row.get(Config.COL_FIGHT_NUMBER, ""):
        info_parts.append(f"FIGHT {html.escape(str(row.get(Config.COL_FIGHT_NUMBER, '')))}")
    if row.get(Config.COL_CORNER, ""):
        info_parts.append(html.escape(str(row.get(Config.COL_CORNER, "")).upper()))
    fight_info_text = " | ".join(info_parts)
    fight_info_label_html = (
        f"<span style='background-color: {label_color}; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>{fight_info_text}</span>"
        if fight_info_text else ""
    )

    # Quick tags
    whatsapp_tag_html = ""
    mob = str(row.get(Config.COL_MOBILE, "")).strip()
    if mob:
        phone_digits = "".join(filter(str.isdigit, mob))
        if phone_digits.startswith('00'):
            phone_digits = phone_digits[2:]
        if phone_digits:
            escaped_phone = html.escape(phone_digits, True)
            whatsapp_tag_html = (
                f"<a href='https://wa.me/{escaped_phone}' target='_blank' style='text-decoration: none;'>"
                f"<span style='background-color: #25D366; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>WhatsApp</span>"
                f"</a>"
            )
    passport_url = str(row.get(Config.COL_PASSPORT_IMAGE, ""))
    passport_tag_html = (
        f"<a href='{html.escape(passport_url, True)}' target='_blank' style='text-decoration: none;'>"
        f"<span style='background-color: #007BFF; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>Passport</span>"
        f"</a>"
        if passport_url and passport_url.startswith("http") else ""
    )

    # Status line
    stat_text = (
        "Not Requested" if curr_status == Config.STATUS_NOT_REQUESTED else
        ("Requested" if curr_status == Config.STATUS_REQUESTED else ("Done" if curr_status == Config.STATUS_DONE else "Pending"))
    )
    latest_user = row.get("latest_task_user", "N/A") or "N/A"
    latest_dt = row.get("latest_task_timestamp", "N/A") or "N/A"
    task_status_html = f"<small style='color:#ccc;'>{html.escape(Config.FIXED_TASK)}: <b>{html.escape(stat_text)}</b> <i>({html.escape(latest_dt)} • {html.escape(latest_user)})</i></small>"

    # Card HTML
    card_html = f"""<div class='card-container' style='background-color:{card_bg_col};'>
        <img src='{html.escape(row.get(Config.COL_IMAGE, "https://via.placeholder.com/60?text=NA"), True)}' class='card-img'>
        <div class='card-info'>
            <div class='info-line'><span class='fighter-name'>{html.escape(ath_name)} | {html.escape(ath_id)}</span></div>
            <div class='info-line'>{fight_info_label_html}</div>
            <div class='info-line'>{whatsapp_tag_html}{passport_tag_html}</div>
            <div class='info-line'>{task_status_html}</div>
        </div>
    </div>"""

    col_card, col_buttons = st.columns([2.5, 1])

    with col_card:
        st.markdown(card_html, unsafe_allow_html=True)

    with col_buttons:
        uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.get("current_user_id", ""))
        curr = row.get('current_task_status', Config.STATUS_PENDING)

        # --- Music links (always visible) ---
        key1 = f"music_link_1_{i_l}"
        key2 = f"music_link_2_{i_l}"
        key3 = f"music_link_3_{i_l}"
        st.text_input("Music Link 1", key=key1, placeholder="Paste URL (YouTube, Spotify, etc.)")
        st.text_input("Music Link 2", key=key2, placeholder="Paste URL (optional)")
        st.text_input("Music Link 3", key=key3, placeholder="Paste URL (optional)")

        # Save links => DONE (stores into Notes)
        if st.button("Save Links", key=f"save_links_{i_l}", use_container_width=True):
            notes_val = join_links(st.session_state.get(key1, ""), st.session_state.get(key2, ""), st.session_state.get(key3, ""))
            if notes_val:
                if registrar_log(ath_id, ath_name, ath_event, Config.FIXED_TASK, Config.STATUS_DONE, uid_l, notes_val):
                    time.sleep(1); st.rerun()
            else:
                st.warning("Please provide at least one valid link.", icon="⚠️")

        st.markdown("<div class='button-group-row'>", unsafe_allow_html=True)

        # Action buttons based on current status
        if curr == Config.STATUS_REQUESTED:
            # When already requested -> show Done and Cancel
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                st.markdown("<div class='green-button'>", unsafe_allow_html=True)
                if st.button("Done", key=f"done_{i_l}", use_container_width=True):
                    # If user presses Done without links, still log Done; links can be saved separately
                    if registrar_log(ath_id, ath_name, ath_event, Config.FIXED_TASK, Config.STATUS_DONE, uid_l, ""):
                        time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with btn_c2:
                st.markdown("<div class='red-button'>", unsafe_allow_html=True)
                if st.button("Cancel", key=f"cancel_{i_l}", use_container_width=True):
                    # Cancel => mark as Not Requested ("---") and write "Canceled by user"
                    if registrar_log(ath_id, ath_name, ath_event, Config.FIXED_TASK, Config.STATUS_NOT_REQUESTED, uid_l, "Canceled by user"):
                        time.sleep(1); st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        else:
            # Default flow: Request + Not Requested (hide Not Requested if already Not Requested)
            btn_l, btn_r = st.columns(2)
            with btn_l:
                btn_label = "Request Again" if curr == Config.STATUS_DONE else "Request"
                btn_type = "secondary" if curr == Config.STATUS_DONE else "primary"
                if st.button(btn_label, key=f"request_{i_l}", type=btn_type, use_container_width=True):
                    if registrar_log(ath_id, ath_name, ath_event, Config.FIXED_TASK, Config.STATUS_REQUESTED, uid_l, ""):
                        time.sleep(1); st.rerun()
            with btn_r:
                if curr != Config.STATUS_NOT_REQUESTED:
                    if st.button("Not Requested", key=f"notneeded_{i_l}", use_container_width=True):
                        if registrar_log(ath_id, ath_name, ath_event, Config.FIXED_TASK, Config.STATUS_NOT_REQUESTED, uid_l, ""):
                            time.sleep(1); st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
