# pages/7_Music.py
from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
from datetime import datetime
import html
import time
import unicodedata
import re

# --- Bootstrap: configura página, autentica e desenha o sidebar unificado ---
bootstrap_page("Walkout Music")
st.title("Walkout Music")

# --- Project Imports ---
from utils import get_gspread_client, connect_gsheet_tab

# ==============================================================================
# CONFIG
# ==============================================================================
class Config:
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"

    FIXED_TASK = "Walkout Music"
    TASK_ALIASES = [r"\bwalkout\s*music\b", r"\bwalkout\b", r"\bmusic\b"]

    # Logical statuses
    STATUS_PENDING = ""              # no log for current event
    STATUS_DONE = "Done"

    DEFAULT_EVENT_PLACEHOLDER = "Z"

    # UI colors
    COLORS = {
        STATUS_DONE: "#143d14",
        STATUS_PENDING: "#1e1e1e",
    }

    # Athlete columns (df)
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


# ==============================================================================
# CSS
# ==============================================================================
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
    @media (max-width: 768px) {
        .mobile-button-row div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important; gap: 10px;
        }
    }
    div.stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# HELPERS
# ==============================================================================
def clean_and_normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    return " ".join(text.split())

def make_task_mask(task_series: pd.Series, fixed_task: str, aliases: list[str]) -> pd.Series:
    t = task_series.fillna("").astype(str).str.lower()
    pats = [re.escape(fixed_task.lower())]
    for al in aliases or []:
        pats.append(al)
    regex = "(" + "|".join(pats) + ")"
    return t.str.contains(regex, regex=True, na=False)

def _clean_str_series(s: pd.Series) -> pd.Series:
    if s is None or len(s) == 0:
        return pd.Series([], dtype=str)
    s = pd.Series(s).fillna("").astype(str).str.strip()
    return s

def parse_ts_series(raw: pd.Series) -> pd.Series:
    if raw is None or len(raw) == 0:
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

# ==============================================================================
# DATA LOADING
# ==============================================================================
@st.cache_data(ttl=600)
def load_athlete_data() -> pd.DataFrame:
    try:
        gspread_client = get_gspread_client()
        ws = connect_gsheet_tab(gspread_client, Config.MAIN_SHEET_NAME, Config.ATHLETES_TAB_NAME)
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        if Config.COL_ROLE not in df.columns or Config.COL_INACTIVE not in df.columns:
            st.error("Required columns 'ROLE'/'INACTIVE' not found.", icon="🚨")
            return pd.DataFrame()

        if df[Config.COL_INACTIVE].dtype == 'object':
            df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        elif pd.api.types.is_numeric_dtype(df[Config.COL_INACTIVE]):
            df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].map({0: False, 1: True}).fillna(True)

        df = df[(df[Config.COL_ROLE] == "1 - Fighter") & (df[Config.COL_INACTIVE] == False)].copy()

        if Config.COL_EVENT in df.columns:
            df[Config.COL_EVENT] = df[Config.COL_EVENT].fillna(Config.DEFAULT_EVENT_PLACEHOLDER)
        else:
            df[Config.COL_EVENT] = Config.DEFAULT_EVENT_PLACEHOLDER

        for c in [Config.COL_IMAGE, Config.COL_MOBILE, Config.COL_FIGHT_NUMBER, Config.COL_CORNER, Config.COL_PASSPORT_IMAGE]:
            if c not in df.columns:
                df[c] = ""
            else:
                df[c] = df[c].fillna("")

        if Config.COL_NAME not in df.columns or Config.COL_ID not in df.columns:
            st.error("Required columns 'name'/'id' not found.", icon="🚨")
            return pd.DataFrame()

        return df.sort_values(by=[Config.COL_EVENT, Config.COL_NAME]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading athletes: {e}", icon="🚨")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_attendance_data() -> pd.DataFrame:
    """
    Robust loader: reads the actual header row from the sheet and adapts.
    No expected_headers (avoids warnings when headers differ).
    """
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB_NAME)
        all_vals = ws.get_all_values()
        if not all_vals:
            return pd.DataFrame()
        headers = [h if h is not None else "" for h in (all_vals[0] if all_vals else [])]
        rows = all_vals[1:] if len(all_vals) > 1 else []
        df = pd.DataFrame(rows, columns=headers)

        # Ensure the columns we use exist (create empty if missing)
        for col in ["Event", "Fighter", "Task", "Status", "User", "TimeStamp", "Timestamp", "Notes"]:
            if col not in df.columns:
                df[col] = ""

        # Keep Athlete ID string if exists
        if "Athlete ID" in df.columns:
            df["Athlete ID"] = df["Athlete ID"].astype(str)

        return df
    except Exception:
        # Fail safe; return empty compatible df
        return pd.DataFrame(columns=["Event", "Fighter", "Task", "Status", "User", "TimeStamp", "Timestamp", "Notes", "Athlete ID"])

# ==============================================================================
# PREPROCESS ATTENDANCE
# ==============================================================================
@st.cache_data(ttl=180)
def preprocess_attendance(df_attendance: pd.DataFrame) -> pd.DataFrame:
    if df_attendance is None or df_attendance.empty:
        return pd.DataFrame()
    df = df_attendance.copy()

    # normals
    df["fighter_norm"] = df.get("Fighter", "").astype(str).apply(clean_and_normalize)
    df["event_norm"]   = df.get("Event", "").astype(str).apply(clean_and_normalize)
    df["task_norm"]    = df.get("Task", "").astype(str).str.strip().str.lower()
    df["status_norm"]  = df.get("Status", "").astype(str).str.strip().str.lower()

    # Time source: prefer TimeStamp if available
    t2 = df.get("TimeStamp")
    t1 = df.get("Timestamp")
    if t2 is None and t1 is None:
        df["TS_raw"] = ""
    else:
        s2 = _clean_str_series(t2) if t2 is not None else pd.Series([""]*len(df))
        s1 = _clean_str_series(t1) if t1 is not None else pd.Series([""]*len(df))
        df["TS_raw"] = s2.where(s2 != "", s1)

    df["TS_dt"] = parse_ts_series(df["TS_raw"])
    return df

def current_status_for_event(df_att: pd.DataFrame, name: str, event: str) -> str:
    if df_att is None or df_att.empty:
        return Config.STATUS_PENDING
    name_n = clean_and_normalize(name)
    evt_n  = clean_and_normalize(event)
    mask = (df_att["fighter_norm"] == name_n) & (df_att["event_norm"] == evt_n) & make_task_mask(df_att["task_norm"], Config.FIXED_TASK, Config.TASK_ALIASES)
    if not mask.any():
        return Config.STATUS_PENDING
    logs = df_att.loc[mask].copy()
    if logs.empty:
        return Config.STATUS_PENDING
    if logs["TS_dt"].notna().any():
        logs = logs.dropna(subset=["TS_dt"]).sort_values("TS_dt", ascending=False)
    else:
        logs = logs.reset_index(drop=False).sort_values("index", ascending=False)
    last = logs.iloc[0]
    st_raw = str(last.get("Status", "")).strip().lower()
    return Config.STATUS_DONE if st_raw == "done" else Config.STATUS_PENDING

def previous_event_music_links(df_att: pd.DataFrame, name: str, current_event: str) -> list[tuple[str, str]]:
    """
    Return up to 3 (label, url) from the last DIFFERENT event where Walkout Music = Done.
    Label: "<EVENT> | Music N"
    """
    out = []
    if df_att is None or df_att.empty:
        return out
    name_n = clean_and_normalize(name)
    evt_n  = clean_and_normalize(current_event)

    base_mask = (df_att["fighter_norm"] == name_n) & make_task_mask(df_att["task_norm"], Config.FIXED_TASK, Config.TASK_ALIASES) & (df_att["status_norm"] == "done")
    cand = df_att[base_mask & (df_att["event_norm"] != evt_n)].copy()
    if cand.empty:
        return out

    # choose most recent other event
    if cand["TS_dt"].notna().any():
        latest_event = cand.sort_values("TS_dt", ascending=False).iloc[0]["Event"]
    else:
        latest_event = cand.tail(1).iloc[0]["Event"]

    ev_mask = (df_att["fighter_norm"] == name_n) & (df_att["Event"].astype(str) == str(latest_event)) & make_task_mask(df_att["task_norm"], Config.FIXED_TASK, Config.TASK_ALIASES)
    ev_recs = df_att.loc[ev_mask].copy()
    if ev_recs.empty:
        return out
    if ev_recs["TS_dt"].notna().any():
        ev_recs = ev_recs.dropna(subset=["TS_dt"]).sort_values("TS_dt", ascending=False)
    else:
        ev_recs = ev_recs.reset_index(drop=False).sort_values("index", ascending=False)

    n = 0
    for _, r in ev_recs.iterrows():
        url = str(r.get("Notes", "") or "").strip()
        if url:
            n += 1
            out.append((f"{latest_event} | Music {n}", url))
        if n >= 3:
            break
    return out

# ==============================================================================
# LOG WRITER (robust to header differences)
# ==============================================================================
def registrar_log_music_link(
    ath_id: str,
    ath_name: str,
    ath_event: str,
    link_url: str,
    user_log_id: str,
) -> bool:
    """
    Append ONE row to Attendance for ONE link using the sheet's actual headers.
    """
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB_NAME)

        all_vals = ws.get_all_values()
        headers = all_vals[0] if all_vals else []
        # compute next '#'
        if len(all_vals) > 1 and str(all_vals[-1][0]).isdigit():
            next_num = int(all_vals[-1][0]) + 1
        else:
            next_num = len(all_vals) + 1

        ts_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)

        row_values = []
        for h in headers:
            h_raw = (h or "").strip()
            # exact-case matching first (important for Timestamp vs TimeStamp)
            if h_raw == "#":
                row_values.append(str(next_num))
            elif h_raw == "Event":
                row_values.append(ath_event)
            elif h_raw == "Athlete ID":
                row_values.append(ath_id)
            elif h_raw == "Name":
                row_values.append(ath_name)
            elif h_raw == "Fighter":
                row_values.append(ath_name)
            elif h_raw == "Task":
                row_values.append(Config.FIXED_TASK)
            elif h_raw == "Status":
                row_values.append(Config.STATUS_DONE)
            elif h_raw == "User":
                row_values.append(user_ident)
            elif h_raw == "Timestamp":
                row_values.append("")            # leave blank if exists
            elif h_raw == "TimeStamp":
                row_values.append(ts_now)        # write here if exists
            elif h_raw == "Notes":
                row_values.append(link_url)
            else:
                # unknown or extra column -> blank
                row_values.append("")
        if not headers:
            # if the sheet is empty, append with a safe default order
            row_values = [
                str(next_num), ath_event, ath_id, ath_name, Config.FIXED_TASK,
                Config.STATUS_DONE, user_ident, ts_now, link_url
            ]
        ws.append_row(row_values, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.error(f"Error writing Attendance: {e}", icon="🚨")
        return False

# ==============================================================================
# SESSION DEFAULTS
# ==============================================================================
defaults = {
    "wm_selected_status": "All",           # All / Done / Pending
    "wm_selected_event": "All Events",
    "wm_search": "",
    "wm_sort_by": "Name",                  # << adicionado para evitar aviso
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# LOAD DATA
# ==============================================================================
with st.spinner("Loading data..."):
    df_athletes = load_athlete_data()
    df_att_raw = load_attendance_data()
    df_att = preprocess_attendance(df_att_raw)

# ==============================================================================
# FILTERS
# ==============================================================================
with st.expander("Settings", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.segmented_control(
            "Filter by Status:",
            options=["All", "Done", "Pending"],
            key="wm_selected_status"    # sem default
        )
    with col2:
        st.segmented_control(
            "Sort by:",
            options=["Name", "Fight Order"],
            key="wm_sort_by",           # sem default
            help="Choose how to sort the athlete list."
        )
    event_opts = ["All Events"] + (sorted([e for e in df_athletes[Config.COL_EVENT].unique() if e != Config.DEFAULT_EVENT_PLACEHOLDER]) if not df_athletes.empty else [])
    st.selectbox("Filter by Event:", options=event_opts, key="wm_selected_event")
    st.text_input("Search Athlete:", placeholder="Type athlete name or ID...", key="wm_search")

# Apply filters
df_show = df_athletes.copy()
if not df_show.empty:
    if st.session_state.wm_selected_event != "All Events":
        df_show = df_show[df_show[Config.COL_EVENT] == st.session_state.wm_selected_event]

    term = st.session_state.wm_search.strip().lower()
    if term:
        df_show = df_show[
            df_show[Config.COL_NAME].str.lower().str.contains(term, na=False) |
            df_show[Config.COL_ID].astype(str).str.contains(term, na=False)
        ]

    # attach current status
    if not df_show.empty:
        df_show["__status__"] = df_show.apply(lambda r: current_status_for_event(df_att, r[Config.COL_NAME], r[Config.COL_EVENT]), axis=1)

        if st.session_state.wm_selected_status == "Done":
            df_show = df_show[df_show["__status__"] == Config.STATUS_DONE]
        elif st.session_state.wm_selected_status == "Pending":
            df_show = df_show[df_show["__status__"] == Config.STATUS_PENDING]

        if st.session_state.get("wm_sort_by", "Name") == "Fight Order":
            df_show['FNO'] = pd.to_numeric(df_show[Config.COL_FIGHT_NUMBER], errors='coerce').fillna(999)
            df_show['COR'] = df_show[Config.COL_CORNER].str.lower().map({'blue': 0, 'red': 1}).fillna(2)
            df_show = df_show.sort_values(by=['FNO', 'COR'], ascending=[True, True])
        else:
            df_show = df_show.sort_values(by=Config.COL_NAME, ascending=True)

# Summary
if not df_show.empty:
    done_c = (df_show["__status__"] == Config.STATUS_DONE).sum()
    pend_c = (df_show["__status__"] == Config.STATUS_PENDING).sum()
    st.markdown(
        f"""<div style="display:flex;flex-wrap:wrap;gap:15px;align-items:center;margin:10px 0;">
        <span style="font-weight:bold;">Showing {len(df_show)} of {len(df_athletes)} athletes:</span>
        <span style="background:{Config.COLORS[Config.STATUS_DONE]};color:white;padding:4px 12px;border-radius:15px;font-size:.9em;font-weight:bold;">Done: {done_c}</span>
        <span style="background:{Config.COLORS[Config.STATUS_PENDING]};color:white;padding:4px 12px;border-radius:15px;font-size:.9em;font-weight:bold;">Pending: {pend_c}</span>
        </div>""",
        unsafe_allow_html=True
    )

st.divider()

# ==============================================================================
# RENDER LIST
# ==============================================================================
for i, row in df_show.iterrows():
    aid   = str(row[Config.COL_ID])
    name  = str(row[Config.COL_NAME])
    event = str(row[Config.COL_EVENT])
    fight = str(row.get(Config.COL_FIGHT_NUMBER, ""))
    corner= str(row.get(Config.COL_CORNER, "")).upper()
    mobile= str(row.get(Config.COL_MOBILE, ""))
    pimg  = str(row.get(Config.COL_PASSPORT_IMAGE, ""))
    img   = str(row.get(Config.COL_IMAGE, "https://via.placeholder.com/60?text=NA"))

    status = row["__status__"]
    card_bg = Config.COLORS.get(status, Config.COLORS[Config.STATUS_PENDING])

    # previous event links (pills; clean output if none)
    prev_links = previous_event_music_links(df_att, name, event)
    if prev_links:
        pills = "".join(
            f"<a href='{html.escape(u, True)}' target='_blank' "
            f"style='text-decoration:none;background:#2d2f34;color:#fff;padding:4px 10px;border-radius:12px;"
            f"font-size:12px;font-weight:bold;margin-right:8px;display:inline-block;'>{html.escape(lbl)}</a>"
            for (lbl, u) in prev_links if u
        )
        pills_block = f"<div class='info-line'>{pills}</div>"
    else:
        pills_block = "<!-- no previous links -->"

    info_parts = []
    if event and event != Config.DEFAULT_EVENT_PLACEHOLDER: info_parts.append(html.escape(event))
    if fight: info_parts.append(f"FIGHT {html.escape(fight)}")
    if corner: info_parts.append(html.escape(corner))
    fight_label = " | ".join(info_parts)
    cc = {'RED': '#d9534f', 'BLUE': '#428bca'}.get(corner.upper(), '#4A4A4A')

    whatsapp_tag_html = ""
    if mobile:
        digits = "".join(filter(str.isdigit, mobile))
        if digits.startswith("00"): digits = digits[2:]
        if digits:
            whatsapp_tag_html = (
                f"<a href='https://wa.me/{html.escape(digits, True)}' target='_blank' style='text-decoration:none;'>"
                f"<span style='background:#25D366;color:#fff;padding:3px 10px;border-radius:8px;font-size:.8em;font-weight:bold;'>WhatsApp</span>"
                f"</a>"
            )

    passport_tag_html = ""
    if pimg and pimg.startswith("http"):
        passport_tag_html = (
            f"<a href='{html.escape(pimg, True)}' target='_blank' style='text-decoration:none;'>"
            f"<span style='background:#007BFF;color:#fff;padding:3px 10px;border-radius:8px;font-size:.8em;font-weight:bold;'>Passport</span>"
            f"</a>"
        )

    card_html = f"""<div class='card-container' style='background:{card_bg};'>
        <img src='{html.escape(img, True)}' class='card-img'>
        <div class='card-info'>
            <div class='info-line'><span class='fighter-name'>{html.escape(name)} | {html.escape(aid)}</span></div>
            <div class='info-line'>
                <span style='background:{cc};color:#fff;padding:3px 10px;border-radius:8px;font-size:.8em;font-weight:bold;margin-right:8px;'>{fight_label}</span>
            </div>
            <div class='info-line'>{whatsapp_tag_html}{passport_tag_html}</div>
            <div class='info-line'><small style='color:#ccc;'>{Config.FIXED_TASK}: <b>{html.escape(status or "Pending")}</b></small></div>
            <hr style='border-color:#444;margin:5px 0;width:100%;'>
            {pills_block}
        </div>
    </div>"""

    c_card, c_right = st.columns([2.5, 1])
    with c_card:
        st.markdown(card_html, unsafe_allow_html=True)

    # -------- Inputs & Buttons (below card) --------
    edit_key = f"wm_edit_{aid}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    k1 = f"wm_link1_{aid}"
    k2 = f"wm_link2_{aid}"
    k3 = f"wm_link3_{aid}"
    for kk in (k1, k2, k3):
        if kk not in st.session_state:
            st.session_state[kk] = ""

    with c_right:
        st.empty()

    c_l1, c_l2, c_l3 = st.columns(3)
    disabled_inputs = not st.session_state[edit_key]
    with c_l1:
        st.text_input("Music Link 1", key=k1, placeholder="Paste URL (YouTube, Spotify, etc.)", disabled=disabled_inputs)
    with c_l2:
        st.text_input("Music Link 2 (optional)", key=k2, placeholder="Paste URL (optional)", disabled=disabled_inputs)
    with c_l3:
        st.text_input("Music Link 3 (optional)", key=k3, placeholder="Paste URL (optional)", disabled=disabled_inputs)

    b1, b2 = st.columns([1, 2])
    with b1:
        if not st.session_state[edit_key]:
            if st.button("Edit Music Links", key=f"wm_edit_btn_{aid}", use_container_width=True):
                st.session_state[edit_key] = True
                st.rerun()
        else:
            if st.button("Cancel Edit", key=f"wm_cancel_btn_{aid}", use_container_width=True):
                st.session_state[edit_key] = False
                st.rerun()

    with b2:
        if st.button("Save Links", key=f"wm_save_btn_{aid}", type="primary", use_container_width=True, disabled=not st.session_state[edit_key]):
            user_id = st.session_state.get("current_user_ps_id_internal", st.session_state.get("current_user_id", ""))
            links = [st.session_state[k1].strip(), st.session_state[k2].strip(), st.session_state[k3].strip()]
            links = [u for u in links if u]
            if not links:
                st.warning("Please provide at least one link.", icon="⚠️")
            else:
                ok_any = False
                for url in links:
                    if registrar_log_music_link(aid, name, event, url, user_id):
                        ok_any = True
                        time.sleep(0.05)
                if ok_any:
                    # refresh data + leave values in inputs; status updates to Done
                    load_attendance_data.clear(); preprocess_attendance.clear()
                    st.session_state[edit_key] = False
                    st.success("Links saved!", icon="✅")
                    st.rerun()

    st.divider()
