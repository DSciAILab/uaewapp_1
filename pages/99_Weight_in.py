# pages/99_Weight_in.py
# =============================================================================
# UAEW Operations App — Weight-in
# -----------------------------------------------------------------------------
# Versão: 1.8.3
# - Running Order: não exibe botões (somente visual).
# - Check in / Check out permanecem com botões.
# =============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import re
import html
from datetime import datetime
from utils import get_gspread_client, connect_gsheet_tab

bootstrap_page("Weight-in")

# =============================================================================
# Config
# =============================================================================
class Config:
    MAIN_SHEET = "UAEW_App"
    ATHLETES_TAB = "df"
    ATT_TAB = "Attendance"

    TASK_NAME = "Weigh-in"
    STATUS_IN = "Check in"
    STATUS_OUT = "Check out"

    ATT_COLS = ["#", "Event", "Athlete ID", "Fighter", "Task", "Status", "User", "TimeStamp", "Notes"]

    COL_ID = "id"
    COL_NAME = "name"
    COL_EVENT = "event"
    COL_ROLE = "role"
    COL_INACTIVE = "inactive"
    COL_IMAGE = "image"
    COL_FIGHT = "fight_number"
    COL_CORNER = "corner"

    DEFAULT_EVENT = "Z"

    CARD_BG_DEFAULT = "#1e1e1e"
    CARD_BG_IN = "#1f5f2b"
    CARD_BG_OUT = "#5a5a5a"
    CORNER_RED = "#d9534f"
    CORNER_BLUE = "#428bca"

# =============================================================================
# State defaults
# =============================================================================
st.session_state.setdefault("weighin_mode", "Check in")
st.session_state.setdefault("weighin_event_selected", None)
st.session_state.setdefault("weighin_local_mode", False)
st.session_state.setdefault("weighin_buffer", [])
st.session_state.setdefault("weighin_overlay", pd.DataFrame())

st.session_state.setdefault("title_size", 52)
st.session_state.setdefault("clock_size", 140)
st.session_state.setdefault("coltitle_size", 22)

# =============================================================================
# Helpers
# =============================================================================
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

@st.cache_data(ttl=600)
def load_athletes() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET, Config.ATHLETES_TAB)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        if Config.COL_ROLE not in df.columns or Config.COL_INACTIVE not in df.columns:
            return pd.DataFrame()

        def _inactive_to_bool(x):
            s = str(x).strip().upper()
            return False if s in ("FALSE", "0", "") else True if s in ("TRUE", "1") else False

        df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].apply(_inactive_to_bool)
        df = df[(df[Config.COL_ROLE] == "1 - Fighter") & (df[Config.COL_INACTIVE] == False)].copy()
        for c in [Config.COL_EVENT, Config.COL_IMAGE, Config.COL_FIGHT, Config.COL_CORNER]:
            if c not in df.columns: df[c] = ""
        df[Config.COL_EVENT] = df[Config.COL_EVENT].fillna(Config.DEFAULT_EVENT)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET, Config.ATT_TAB)
        df = pd.DataFrame(ws.get_all_records())
        for c in Config.ATT_COLS:
            if c not in df.columns: df[c] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=Config.ATT_COLS)

def _attendance_with_overlay() -> pd.DataFrame:
    base = load_attendance().copy()
    ov = st.session_state["weighin_overlay"]
    if not ov.empty:
        for c in Config.ATT_COLS:
            if c not in ov.columns: ov[c] = ""
        base = pd.concat([base, ov[Config.ATT_COLS]], ignore_index=True)
    return base

def _extract_event_num(ev: str) -> int:
    m = re.search(r"(\d+)$", str(ev))
    return int(m.group(1)) if m else 10**9

def _events_from_athletes(df_ath: pd.DataFrame) -> list[str]:
    return sorted(
        [x for x in df_ath[Config.COL_EVENT].unique() if x and x != Config.DEFAULT_EVENT],
        key=_extract_event_num,
    )

def _last_status_for_event(df_att: pd.DataFrame, event: str) -> pd.DataFrame:
    if df_att.empty: return pd.DataFrame(columns=["Athlete ID","Status","Notes","TS","Fighter"])
    df = df_att.copy()
    df = df[(df["Event"].astype(str)==str(event)) & (df["Task"].astype(str)==Config.TASK_NAME)]
    if df.empty: return pd.DataFrame(columns=["Athlete ID","Status","Notes","TS","Fighter"])
    ts = pd.to_datetime(df["TimeStamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df = df.assign(_ts=ts).sort_values(by=["Athlete ID","_ts"], ascending=[True, True])
    latest = df.groupby("Athlete ID", as_index=False).tail(1)
    latest = latest.rename(columns={"Status":"Status", "Notes":"Notes", "Fighter":"Fighter"})
    latest["TS"] = latest["_ts"]
    return latest[["Athlete ID","Status","Notes","TS","Fighter"]]

def _order_from_notes(x):
    try: return int(str(x).strip())
    except Exception: return None

def _checked_partitions(df_ath: pd.DataFrame, df_att: pd.DataFrame, event: str):
    last = _last_status_for_event(df_att, event)
    last.index = last["Athlete ID"].astype(str)

    def _row_status(row):
        aid = str(row.get(Config.COL_ID, ""))
        if aid in last.index:
            stt = str(last.loc[aid, "Status"])
            return "IN" if stt == Config.STATUS_IN else "OUT" if stt == Config.STATUS_OUT else "NONE"
        return "NONE"

    df_ev = df_ath[df_ath[Config.COL_EVENT]==event].copy()
    if df_ev.empty: return df_ev.copy(), df_ev.copy(), df_ev.copy()

    df_ev["__st__"] = df_ev.apply(_row_status, axis=1)
    df_ev["__order__"] = df_ev[Config.COL_ID].astype(str).map(
        lambda aid: _order_from_notes(last.loc[str(aid), "Notes"]) if str(aid) in last.index else None
    )
    df_in  = df_ev[df_ev["__st__"]=="IN"].copy().sort_values(by=["__order__", Config.COL_NAME])
    df_out = df_ev[df_ev["__st__"]=="OUT"].copy().sort_values(by=[Config.COL_NAME])
    df_rest= df_ev[df_ev["__st__"]=="NONE"].copy().sort_values(by=[Config.COL_NAME])
    return df_in, df_out, df_rest

def _next_checkin_order(df_att: pd.DataFrame, event: str) -> int:
    last = _last_status_for_event(df_att, event)
    return 1 if last.empty else int((last["Status"]==Config.STATUS_IN).sum()) + 1

def sync_data():
    load_attendance.clear()
    st.session_state["weighin_overlay"] = pd.DataFrame()
    st.toast("Data synced.", icon="🔄")

# =============================================================================
# UI helpers
# =============================================================================
def _corner_chip(ev: str, fight: str, corner: str) -> str:
    c = str(corner).strip().lower()
    bg = Config.CORNER_RED if c=="red" else Config.CORNER_BLUE if c=="blue" else "#555"
    txt = f"{ev} | FIGHT {fight or '?'} | {corner.upper() or '?'}"
    return f"<span style='background:{bg};color:#fff;padding:6px 10px;border-radius:10px;font-weight:700;font-size:12px;'>{html.escape(txt)}</span>"

def render_card(row: pd.Series, label_btn: str | None, on_click, bg_color=None, show_number=None, dimmed=False, context_key=""):
    """Se label_btn=None, não cria botão (somente visual)."""
    aid = str(row.get(Config.COL_ID,""))
    name = str(row.get(Config.COL_NAME,""))
    event = str(row.get(Config.COL_EVENT,""))
    fight = str(row.get(Config.COL_FIGHT,""))
    corner = str(row.get(Config.COL_CORNER,""))
    img = str(row.get(Config.COL_IMAGE,""))
    chip = _corner_chip(event, fight, corner)

    bg = bg_color or Config.CARD_BG_DEFAULT
    if dimmed: bg = Config.CARD_BG_OUT

    num_html = f"<div style='width:48px;height:48px;border-radius:10px;display:flex;align-items:center;justify-content:center;background:#0b3b1b;color:#fff;font-weight:800;'>{show_number}</div>" if show_number is not None else ""

    avatar = f"<img src='{html.escape(img or 'https://via.placeholder.com/48?text=NA', True)}' style='width:48px;height:48px;border-radius:8px;object-fit:cover;'>"

    card = f"""
    <div style='background:{bg};padding:12px 14px;border-radius:12px;display:flex;align-items:center;gap:12px;'>
        <div style='display:flex;gap:10px;align-items:center;'>{num_html}{avatar}</div>
        <div style='display:flex;flex-direction:column;gap:6px;'>
            <div style='font-weight:800;font-size:18px;color:#fff;'>{html.escape(name)} | {html.escape(aid)}</div>
            <div>{chip}</div>
        </div>
    </div>
    """
    st.markdown(card, unsafe_allow_html=True)
    if label_btn:
        key = f"btn_{context_key}_{label_btn}_{aid}_{event}"
        if st.button(label_btn, key=key, use_container_width=True):
            on_click(aid, name, event)

# =============================================================================
# Expanders
# =============================================================================
def _settings_expander_top(events):
    with st.expander("Settings", expanded=True):
        st.segmented_control("Mode:", options=["Check in","Check out","Running Order"], key="weighin_mode")
        if st.session_state["weighin_mode"] == "Check in":
            if not events:
                st.warning("No events found.")
            else:
                default_event = events[0]
                st.session_state.setdefault("weighin_event_selected", default_event)
                if st.session_state["weighin_event_selected"] not in events:
                    st.session_state["weighin_event_selected"] = default_event
                st.segmented_control("Event:", options=events, key="weighin_event_selected")

def _settings_expander_bottom():
    with st.expander("Settings", expanded=False):
        st.segmented_control("Mode:", options=["Check in","Check out","Running Order"], key="weighin_mode")
        if st.button("Sync data", use_container_width=True):
            sync_data()
            st.rerun()

# =============================================================================
# Main render
# =============================================================================
df_ath = load_athletes()
events = _events_from_athletes(df_ath)

mode = st.session_state.get("weighin_mode","Check in")
if mode in ("Check in","Check out"):
    _settings_expander_top(events)
else:
    _settings_expander_bottom()

if st.session_state.get("weighin_event_selected") is None and events:
    st.session_state["weighin_event_selected"] = events[0]

selected_event = st.session_state.get("weighin_event_selected") or (events[0] if events else "")
st.markdown(
    f"<h1 style='text-align:center;font-size:{st.session_state['title_size']}px;margin:10px 0 20px 0;'>"
    f"{html.escape(selected_event)} | Weigh-in</h1>",
    unsafe_allow_html=True
)

df_att_full = _attendance_with_overlay()
df_in, df_out, df_rest = _checked_partitions(df_ath, df_att_full, selected_event)

# ----------------- Check in -----------------
if mode == "Check in":
    for _, r in pd.concat([df_in, df_rest]).iterrows():
        already_in = r["__st__"]=="IN"
        render_card(r, "Check in" if not already_in else None, lambda *a,**k: None,
                    bg_color=Config.CARD_BG_IN if already_in else None,
                    show_number=r["__order__"] if already_in else None,
                    context_key="in")

# ----------------- Check out -----------------
elif mode == "Check out":
    for _, r in df_in.iterrows():
        render_card(r, "Check out", lambda *a,**k: None,
                    bg_color=Config.CARD_BG_IN, context_key="out")

# ----------------- Running Order -----------------
else:
    cL, cM, cR = st.columns([1.2, 1, 1.2])
    col_title_css = f"font-size:{st.session_state['coltitle_size']}px;text-align:center;margin:10px 0 14px 0;font-weight:800;color:#ddd;"

    with cL:
        st.markdown(f"<div style='{col_title_css}'>Checked in</div>", unsafe_allow_html=True)
        for _, r in df_in.iterrows():
            render_card(r, None, lambda *a,**k: None, bg_color=Config.CARD_BG_IN,
                        show_number=r["__order__"], context_key="ro_in")

    with cM:
        st.markdown(
            f"<div style='display:flex;align-items:center;justify-content:center;height:100%;min-height:240px;'>"
            f"<div style='font-size:{st.session_state['clock_size']}px;font-weight:900;letter-spacing:2px;color:#eaeaea;'>"
            f"{datetime.now().strftime('%H:%M')}</div></div>",
            unsafe_allow_html=True
        )

    with cR:
        st.markdown(f"<div style='{col_title_css}'>Checked out</div>", unsafe_allow_html=True)
        for _, r in df_out.iterrows():
            render_card(r, None, lambda *a,**k: None, bg_color=Config.CARD_BG_OUT,
                        dimmed=True, context_key="ro_out")
