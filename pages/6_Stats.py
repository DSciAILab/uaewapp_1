# pages/6_Stats.py
from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import html
import time
import unicodedata
import re

# --- Bootstrap: configura página, autentica e desenha o sidebar unificado ---
bootstrap_page("Stats")

st.title("Stats")

# --- Project Imports ---
from utils import get_gspread_client, connect_gsheet_tab

# ==============================================================================
# CONSTANTS & CONFIG
# ==============================================================================
class Config:
    """Centralizes constants and column names for consistency."""
    # Sheets / Tabs
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"
    STATS_TAB_NAME = "df [Stats]"

    # Fixed Task name for this page
    FIXED_TASK = "Stats"

    # Task aliases (in case historical logs vary)
    TASK_ALIASES = [r"\bstats?\b", r"\bstatistic(s)?\b"]

    # Logical statuses for STATS FLOW (only Done or Pending)
    STATUS_PENDING = ""           # no confirmation yet
    STATUS_DONE = "Done"

    # Colors (same palette used in other pages)
    STATUS_COLOR_MAP = {
        STATUS_DONE: "#143d14",
        STATUS_PENDING: "#1e1e1e",
        # Raw fallbacks
        "Requested": "#1e1e1e",
        "---": "#1e1e1e",
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
    ATT_COL_TIMESTAMP_ALT = "TimeStamp"   # REQUIRED by your spec
    ATT_COL_NOTES = "Notes"

    # Stats supported fields
    STATS_FIELDS = [
        'weight_kg', 'height_cm', 'reach_cm', 'fight_style',
        'country_of_representation', 'residence_city', 'team_name',
        'tshirt_size', 'tshirt_size_c1', 'tshirt_size_c2', 'tshirt_size_c3'
    ]

    # Dropdown options (English)
    T_SHIRT_SIZES = ["-- Select --", "S", "M", "L", "XL", "XXL", "3XL"]
    COUNTRY_LIST = [
        "-- Select --", "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
        "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh",
        "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina",
        "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia",
        "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros",
        "Congo, Democratic Republic of the", "Congo, Republic of the", "Costa Rica", "Cote d'Ivoire", "Croatia",
        "Cuba", "Cyprus", "Czechia", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt",
        "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France",
        "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau",
        "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel",
        "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan",
        "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg",
        "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius",
        "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar",
        "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea",
        "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine State", "Panama", "Papua New Guinea",
        "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda",
        "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino",
        "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore",
        "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain",
        "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania",
        "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan",
        "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States of America",
        "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
    ]

    @staticmethod
    def map_raw_status_stats(raw_status: str) -> str:
        """For STATS: only 'Done' counts as Done; anything else => Pending."""
        s = "" if raw_status is None else str(raw_status).strip()
        return Config.STATUS_DONE if s.lower() == "done" else Config.STATUS_PENDING


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

def field_is_empty(value) -> bool:
    """Detects if a value should be considered 'missing' for red label highlight."""
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        return (s == "") or (s == "-- Select --")
    if isinstance(value, (int, float)):
        try:
            return float(value) == 0.0
        except Exception:
            return False
    return False


# ==============================================================================
# DATA LOADING
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


@st.cache_data(ttl=600)
def load_stats() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.STATS_TAB_NAME)
        df = pd.DataFrame(ws.get_all_records())
        return df
    except Exception as e:
        st.error(f"Error loading stats: {e}", icon="🚨")
        return pd.DataFrame()


def add_stats_record(row_dict: dict) -> bool:
    """Append an aligned record to 'df [Stats]'."""
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.STATS_TAB_NAME)
        all_vals = ws.get_all_values()

        default_header = [
            'stats_record_id', 'fighter_id', 'fighter_event_name', 'gender',
            'weight_kg', 'height_cm', 'reach_cm', 'fight_style',
            'country_of_representation', 'residence_city', 'team_name',
            'tshirt_size', 'updated_by_user', 'updated_at', 'event',
            'tshirt_size_c1', 'tshirt_size_c2', 'tshirt_size_c3', 'operation'
        ]

        if not all_vals:
            ws.append_row(default_header, value_input_option="USER_ENTERED")
            header = default_header
            next_id = 1
        else:
            header = all_vals[0]
            if set(default_header) - set(header):
                header = header + [c for c in default_header if c not in header]
                ws.update(f"A1:{chr(64+len(header))}1", [header])
            next_id = len(all_vals)  # header + existing rows

        row_dict = dict(row_dict)
        row_dict['stats_record_id'] = row_dict.get('stats_record_id', next_id)
        aligned = [row_dict.get(c, "") for c in header]
        ws.append_row(aligned, value_input_option="USER_ENTERED")
        st.success("Stats saved.", icon="💾")
        load_stats.clear()
        return True
    except Exception as e:
        st.error(f"Error saving stats: {e}", icon="🚨")
        return False


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
            ts,  # "TimeStamp" (required)
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

# --- Defaults centralizados no Session State (sem default nos widgets) ---
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
    df_stats = load_stats()

df_att = preprocess_attendance(df_att_raw)

# --- Compute current status per athlete (for Task = Stats) ---
def compute_task_status_for_athletes(df_athletes, df_attendance, fixed_task: str) -> pd.DataFrame:
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

    latest['current_task_status'] = latest[Config.ATT_COL_STATUS].apply(Config.map_raw_status_stats)
    latest['latest_task_timestamp'] = latest.apply(
        lambda r: r['TS_dt'].strftime("%d/%m/%Y") if pd.notna(r.get('TS_dt', pd.NaT))
        else _fmt_date_from_text(r.get('TS_raw', r.get(Config.ATT_COL_TIMESTAMP_ALT, r.get(Config.ATT_COL_TIMESTAMP, '')))),
        axis=1
    )
    latest['latest_task_user'] = latest[Config.ATT_COL_USER].fillna('N/A')

    return latest[[Config.COL_NAME, Config.COL_EVENT, 'current_task_status', 'latest_task_user', 'latest_task_timestamp']]


if not df_athletes.empty:
    st_status = compute_task_status_for_athletes(df_athletes, df_att, Config.FIXED_TASK)
    df_athletes = pd.merge(df_athletes, st_status, on=[Config.COL_NAME, Config.COL_EVENT], how='left')
    df_athletes.fillna({
        'current_task_status': Config.STATUS_PENDING,
        'latest_task_user': 'N/A',
        'latest_task_timestamp': 'N/A'
    }, inplace=True)

# --- Settings (sem default nos widgets; usa session_state) ---
with st.expander("Settings", expanded=True):
    col_status, col_sort = st.columns(2)
    with col_status:
        STATUS_FILTER_LABELS = {
            "All": "All",
            Config.STATUS_PENDING: "Pending",
            Config.STATUS_DONE: "Done",
        }
        st.segmented_control(
            "Filter by Status:",
            options=["All", Config.STATUS_DONE, Config.STATUS_PENDING],  # All / Done / Pending
            format_func=lambda x: STATUS_FILTER_LABELS.get(x, x if x else "Pending"),
            key="selected_status"   # <-- sem default
        )
    with col_sort:
        st.segmented_control(
            "Sort by:",
            options=["Name", "Fight Order"],
            key="sort_by",          # <-- sem default
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

# --- Summary badges (Done / Pending only) ---
if not df_filtered.empty:
    done_count = (df_filtered['current_task_status'] == Config.STATUS_DONE).sum()
    pending_count = len(df_filtered) - done_count
    summary_html = f'''<div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin: 10px 0;">
        <span style="font-weight: bold;">Showing {len(df_filtered)} of {len(df_athletes)} athletes:</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_DONE]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Done: {done_count}</span>
        <span style="background-color: {Config.STATUS_COLOR_MAP[Config.STATUS_PENDING]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Pending: {pending_count}</span>
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

# --- Render loop (cards + STATS FORM WITH RED LABELS) ---
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
    stat_text = "Done" if curr_status == Config.STATUS_DONE else "Pending"
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

    col_card, col_actions = st.columns([2.5, 1])

    # --- Left: Card & STATS FORM ---
    with col_card:
        st.markdown(card_html, unsafe_allow_html=True)

        # Load latest stats for this athlete (by name on df [Stats])
        latest_stats = None
        if not df_stats.empty and 'fighter_event_name' in df_stats.columns:
            df_one = df_stats[df_stats['fighter_event_name'].astype(str).str.lower() == ath_name.lower()].copy()
            if not df_one.empty and 'updated_at' in df_one.columns:
                df_one['__ts__'] = pd.to_datetime(df_one['updated_at'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
                latest_stats = df_one.sort_values('__ts__', ascending=False).iloc[0]

        # Edit-mode per athlete
        edit_mode_key = f"edit_mode_{ath_id}"
        if edit_mode_key not in st.session_state:
            st.session_state[edit_mode_key] = False
        is_editing = st.session_state[edit_mode_key]

        # Initialize session defaults for each field from latest stats
        if latest_stats is not None:
            for f in Config.STATS_FIELDS:
                k = f"stat_{f}_{ath_id}"
                if k not in st.session_state:
                    v = latest_stats.get(f, "")
                    try:
                        if f in ['weight_kg', 'height_cm', 'reach_cm']:
                            st.session_state[k] = float(v) if str(v).strip() != "" else 0.0
                        else:
                            st.session_state[k] = str(v) if str(v).strip() != "" else ("-- Select --" if "tshirt" in f or "country" in f else "")
                    except Exception:
                        st.session_state[k] = 0.0 if f in ['weight_kg', 'height_cm', 'reach_cm'] else ""
        else:
            for f in Config.STATS_FIELDS:
                k = f"stat_{f}_{ath_id}"
                if k not in st.session_state:
                    st.session_state[k] = 0.0 if f in ['weight_kg', 'height_cm', 'reach_cm'] else ("-- Select --" if "tshirt" in f or "country" in f else "")

        # Top buttons: Confirm Data (DONE) + Edit Data / Cancel Edit
        btn_row = st.columns([0.66, 0.17, 0.17])
        with btn_row[1]:
            if st.button("Confirm Data", key=f"confirm_{ath_id}", use_container_width=True):
                # Save a confirm record and log Done
                data_to_save = {
                    'fighter_id': ath_id,
                    'fighter_event_name': ath_name,
                    'event': ath_event,
                    'updated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    'updated_by_user': st.session_state.get('current_user_name', 'System'),
                    'operation': "confirmed"
                }
                for f in Config.STATS_FIELDS:
                    data_to_save[f] = st.session_state.get(f"stat_{f}_{ath_id}")
                if add_stats_record(data_to_save):
                    if registrar_log(ath_id, ath_name, ath_event, Config.FIXED_TASK, Config.STATUS_DONE, st.session_state.get('current_user_name', 'System')):
                        time.sleep(1); st.rerun()
        with btn_row[2]:
            if st.button("Edit Data" if not is_editing else "Cancel Edit", key=f"toggle_edit_{ath_id}", use_container_width=True, type="secondary" if not is_editing else "primary"):
                st.session_state[edit_mode_key] = not is_editing
                st.rerun()

        # --------- STATS FORM (labels in RED if empty; numeric keypad on mobile) ----------
        c1, c2, c3 = st.columns(3)
        cols = [c1, c2, c3]
        field_labels = {
            'weight_kg': "Weight (kg)",
            'height_cm': "Height (cm)",
            'reach_cm':  "Reach (cm)",
            'fight_style': "Fight Style",
            'country_of_representation': "Country (Representation)",
            'residence_city': "Residence City",
            'team_name': "Team Name",
            'tshirt_size': "T-Shirt (Athlete)",
            'tshirt_size_c1': "T-Shirt (C1)",
            'tshirt_size_c2': "T-Shirt (C2)",
            'tshirt_size_c3': "T-Shirt (C3)",
        }

        disabled = not is_editing

        def label_html(text: str, empty: bool) -> str:
            return f"<div style='margin-top:8px; margin-bottom:4px; font-weight:600; color:{'#ff4d4f' if empty else '#ddd'};'>{html.escape(text)}</div>"

        i = 0
        for f in Config.STATS_FIELDS:
            key = f"stat_{f}_{ath_id}"
            with cols[i % 3]:
                val = st.session_state.get(key)
                empty = field_is_empty(val)  # label red if empty
                st.markdown(label_html(field_labels.get(f, f), empty), unsafe_allow_html=True)

                if f in ['weight_kg', 'height_cm', 'reach_cm']:
                    st.number_input(
                        label="",
                        key=key,
                        min_value=0.0,
                        step=0.10,
                        format="%.2f",
                        disabled=disabled,
                        label_visibility="collapsed"
                    )
                elif f == 'country_of_representation':
                    st.selectbox(
                        label="",
                        options=Config.COUNTRY_LIST,
                        key=key,
                        disabled=disabled,
                        label_visibility="collapsed"
                    )
                elif 'tshirt' in f:
                    st.selectbox(
                        label="",
                        options=Config.T_SHIRT_SIZES,
                        key=key,
                        disabled=disabled,
                        label_visibility="collapsed"
                    )
                else:
                    st.text_input(
                        label="",
                        key=key,
                        disabled=disabled,
                        label_visibility="collapsed"
                    )
            i += 1

        if is_editing:
            if st.button(f"Save Changes for {ath_name}", key=f"save_stats_{ath_id}", type="primary", use_container_width=True):
                new_data = {
                    'fighter_id': ath_id,
                    'fighter_event_name': ath_name,
                    'event': ath_event,
                    'updated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    'updated_by_user': st.session_state.get('current_user_name', 'System'),
                    'operation': "updated" if latest_stats is not None else "created"
                }
                for f in Config.STATS_FIELDS:
                    new_data[f] = st.session_state.get(f"stat_{f}_{ath_id}")

                if add_stats_record(new_data):
                    if registrar_log(ath_id, ath_name, ath_event, Config.FIXED_TASK, Config.STATUS_DONE, st.session_state.get('current_user_name', 'System')):
                        st.session_state[edit_mode_key] = False
                        time.sleep(1); st.rerun()

    # --- Right: reserved column (visual symmetry) ---
    with col_actions:
        st.empty()

    st.divider()
