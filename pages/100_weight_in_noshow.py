# pages/99_Weight_in.py
# =============================================================================
# UAEW Operations App — Weigh-in
# -----------------------------------------------------------------------------
# Versão: 2.4.0
# - Mantida a estrutura da v2.3.3 (a melhor versão aprovada por você)
# - Acrescentado "No show" (apenas na aba Check in):
#     * Loga na Attendance com Status = "No show"
#     * Atleta volta a ficar disponível para novo Check in
#     * Mostra chip "No show" vermelho no card quando disponível
#     * No Running Order, aparece na coluna da direita (Checked out) em VERMELHO
# - Nenhuma outra mudança de layout/fluxo além do descrito acima
# =============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import re, html
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

from utils import get_gspread_client, connect_gsheet_tab

# >>> Importante: não exigir auth aqui para não derrubar a Running Order
bootstrap_page("Weight-in", require_auth=False)

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
    STATUS_NOSHOW = "No show"       # <<< novo status

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
    CARD_BG_IN = "#1f5f2b"   # verde (checked-in)
    CARD_BG_OUT = "#5a5a5a"  # cinza (checked-out)
    CARD_BG_NOSHOW = "#8e1d1d"  # vermelho (no show) no display
    CORNER_RED = "#d9534f"
    CORNER_BLUE = "#428bca"

    CHIP_NOSHOW_BG = "#c0392b"  # chip "No show" quando disponível

# =============================================================================
# State defaults
# =============================================================================
st.session_state.setdefault("weighin_mode", "Check in")  # "Check in" | "Check out" | "Running Order"
st.session_state.setdefault("weighin_event_selected", None)
st.session_state.setdefault("weighin_local_mode", False)
st.session_state.setdefault("weighin_buffer", [])
st.session_state.setdefault("weighin_overlay", pd.DataFrame())

# Sliders (sidebar) — display do Running Order
st.session_state.setdefault("title_size", 56)
st.session_state.setdefault("clock_size", 160)
st.session_state.setdefault("coltitle_size", 24)
st.session_state.setdefault("ro_refresh_sec", 10)

# =============================================================================
# Helpers
# =============================================================================
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def _extract_event_num(ev: str) -> int:
    m = re.search(r"(\d+)$", str(ev))
    return int(m.group(1)) if m else 10**9

@st.cache_data(ttl=600, show_spinner=False)
def load_athletes() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET, Config.ATHLETES_TAB)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty: return pd.DataFrame()
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

@st.cache_data(ttl=120, show_spinner=False)
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

def _events_from_athletes(df_ath: pd.DataFrame) -> list[str]:
    evts = [x for x in df_ath[Config.COL_EVENT].unique() if x and x != Config.DEFAULT_EVENT]
    evts_sorted = sorted(evts, key=_extract_event_num)  # menor número é padrão
    return evts_sorted

def _last_status_for_event(df_att: pd.DataFrame, event: str) -> pd.DataFrame:
    if df_att.empty: return pd.DataFrame(columns=["Athlete ID","Status","Notes","TS","Fighter"])
    df = df_att.copy()
    df = df[(df["Event"].astype(str)==str(event)) & (df["Task"].astype(str)==Config.TASK_NAME)]
    if df.empty: return pd.DataFrame(columns=["Athlete ID","Status","Notes","TS","Fighter"])
    ts = pd.to_datetime(df["TimeStamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df = df.assign(_ts=ts).sort_values(by=["Athlete ID","_ts"], ascending=[True, True])
    latest = df.groupby("Athlete ID", as_index=False).tail(1)
    latest["TS"] = latest["_ts"]
    return latest[["Athlete ID","Status","Notes","TS","Fighter"]]

def _order_from_notes(x):
    try: return int(str(x).strip())
    except Exception: return None

def _checked_partitions(df_ath: pd.DataFrame, df_att: pd.DataFrame, event: str, *, for_running_display: bool = False):
    """
    Particiona atletas em:
      - df_in  : último status = Check in
      - df_out : último status = Check out (ou No show quando for_running_display=True)
      - df_rest: disponíveis (sem status, ou No show quando for_running_display=False)
    Também anota:
      - __order__: número inteiro do running order (se houver)
      - __noshow__: True se último status foi No show
    """
    last = _last_status_for_event(df_att, event)
    last.index = last["Athlete ID"].astype(str)

    def _row_status(row):
        aid = str(row.get(Config.COL_ID, ""))
        if aid in last.index:
            stt = str(last.loc[aid, "Status"])
            if stt == Config.STATUS_IN:
                return "IN"
            if stt == Config.STATUS_OUT:
                return "OUT"
            if stt == Config.STATUS_NOSHOW:
                # No show aparece como OUT apenas no display (Running Order),
                # e como NONE nas telas interativas (para poder fazer novo check in).
                return "OUT" if for_running_display else "NONE"
        return "NONE"

    df_ev = df_ath[df_ath[Config.COL_EVENT]==event].copy()
    if df_ev.empty: 
        return df_ev.copy(), df_ev.copy(), df_ev.copy()

    df_ev["__st__"] = df_ev.apply(_row_status, axis=1)
    df_ev["__order__"] = df_ev[Config.COL_ID].astype(str).map(
        lambda aid: _order_from_notes(last.loc[str(aid), "Notes"]) if str(aid) in last.index else None
    )

    def _was_noshow(aid: str) -> bool:
        if aid in last.index:
            return str(last.loc[aid, "Status"]) == Config.STATUS_NOSHOW
        return False
    df_ev["__noshow__"] = df_ev[Config.COL_ID].astype(str).map(_was_noshow)

    df_in  = df_ev[df_ev["__st__"]=="IN"].copy().sort_values(by=["__order__", Config.COL_NAME])
    df_out = df_ev[df_ev["__st__"]=="OUT"].copy().sort_values(by=[Config.COL_NAME])
    df_rest= df_ev[df_ev["__st__"]=="NONE"].copy().sort_values(by=[Config.COL_NAME])

    return df_in, df_out, df_rest

def _next_checkin_order(df_att: pd.DataFrame, event: str) -> int:
    last = _last_status_for_event(df_att, event)
    return 1 if last.empty else int((last["Status"]==Config.STATUS_IN).sum()) + 1

# ---------------- Append helpers ----------------
def _append_attendance_row(values: dict):
    gc = get_gspread_client()
    ws = connect_gsheet_tab(gc, Config.MAIN_SHEET, Config.ATT_TAB)

    header = ws.row_values(1)
    if not header:
        header = Config.ATT_COLS[:]
        ws.append_row(header, value_input_option="USER_ENTERED")

    next_num = ""
    if "#" in header:
        col_idx = header.index("#") + 1
        col_vals = ws.col_values(col_idx)
        if len(col_vals) > 1:
            last = None
            for v in reversed(col_vals[1:]):
                vv = str(v).strip()
                if vv:
                    last = vv; break
            next_num = str(int(last) + 1) if (last and last.isdigit()) else str(len(col_vals))
        else:
            next_num = "1"

    values = dict(values)
    values["#"] = next_num
    row = [values.get(col, "") for col in header]
    ws.append_row(row, value_input_option="USER_ENTERED")

def _queue_overlay(values: dict):
    df = st.session_state["weighin_overlay"]
    new = pd.DataFrame([values], columns=Config.ATT_COLS)
    st.session_state["weighin_overlay"] = pd.concat([df, new], ignore_index=True)
    st.session_state["weighin_buffer"].append(values)

def flush_buffer():
    if not st.session_state["weighin_buffer"]:
        st.info("No pending rows to save.")
        return
    for row in st.session_state["weighin_buffer"]:
        _append_attendance_row(row)
    st.session_state["weighin_buffer"].clear()
    st.session_state["weighin_overlay"] = pd.DataFrame()
    load_attendance.clear()
    st.success("Buffered rows saved.", icon="✅")
    st.rerun()

def _log_action(athlete_id: str, fighter_name: str, event: str, status: str, notes: str):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    user_ident = st.session_state.get("current_user_name") or st.session_state.get("current_user_id") or "System"

    payload = {
        "#": "",
        "Event": event,
        "Athlete ID": str(athlete_id),
        "Fighter": fighter_name,
        "Task": Config.TASK_NAME,
        "Status": status,
        "User": user_ident,
        "TimeStamp": ts,
        "Notes": notes,
    }

    if st.session_state["weighin_local_mode"]:
        _queue_overlay(payload)
        st.toast("Added to local buffer.", icon="📝")
    else:
        _append_attendance_row(payload)
        load_attendance.clear()
        st.toast("Saved to sheet.", icon="💾")
    st.rerun()

# =============================================================================
# UI helpers (cards)
# =============================================================================
def _corner_chip(ev: str, fight: str, corner: str) -> str:
    c = str(corner).strip().lower()
    bg = Config.CORNER_RED if c=="red" else Config.CORNER_BLUE if c=="blue" else "#555"
    txt = f"{ev} | FIGHT {fight or '?'} | {corner.upper() or '?'}"
    return f"<span style='background:{bg};color:#fff;padding:6px 10px;border-radius:10px;font-weight:700;font-size:12px;'>{html.escape(txt)}</span>"

def render_card(row: pd.Series, label_btn: str | None, on_click, *,
                bg_color=None, show_number=None, dimmed=False, context_key="",
                second_btn_label: str | None = None, second_on_click=None):
    aid = str(row.get(Config.COL_ID,""))
    name = str(row.get(Config.COL_NAME,""))
    event = str(row.get(Config.COL_EVENT,""))
    fight = str(row.get(Config.COL_FIGHT,""))
    corner = str(row.get(Config.COL_CORNER,""))
    img = str(row.get(Config.COL_IMAGE,""))

    bg = bg_color or Config.CARD_BG_DEFAULT
    if dimmed: 
        bg = Config.CARD_BG_OUT

    # número grande, inteiro, ocupando bem o quadrado
    num_html = (
        f"<div style='width:56px;height:56px;border-radius:10px;display:flex;align-items:center;justify-content:center;"
        f"background:#0b3b1b;color:#fff;font-weight:900;font-size:32px;line-height:1;'>{int(show_number)}</div>"
        if show_number is not None else ""
    )
    avatar = f"<img src='{html.escape(img or 'https://via.placeholder.com/56?text=NA', True)}' style='width:56px;height:56px;border-radius:8px;object-fit:cover;'>"

    # chip de evento/corner
    corner_bg = Config.CORNER_RED if str(corner).strip().lower()=="red" else Config.CORNER_BLUE if str(corner).strip().lower()=="blue" else "#555"
    chip_txt = f"{event} | FIGHT {fight or '?'} | {str(corner).upper() or '?'}"
    chip_corner = f"<span style='background:{corner_bg};color:#fff;padding:6px 10px;border-radius:10px;font-weight:700;font-size:12px;'>{html.escape(chip_txt)}</span>"

    # chip de No show quando o atleta está disponível e teve No show por último
    chip_noshow = ""
    if bool(row.get("__noshow__", False)):
        chip_noshow = (
            f"<span style='background:{Config.CHIP_NOSHOW_BG};color:#fff;padding:6px 10px;border-radius:10px;"
            f"font-weight:800;font-size:12px;margin-left:6px;'>No show</span>"
        )

    chips_html = f"{chip_corner}{chip_noshow}"

    card_html = f"""
    <div style='background:{bg};padding:12px 14px;border-radius:12px;display:flex;align-items:center;gap:12px;'>
        <div style='display:flex;gap:10px;align-items:center;'>{num_html}{avatar}</div>
        <div style='display:flex;flex-direction:column;gap:6px;flex:1;'>
            <div style='font-weight:800;font-size:18px;color:#fff;'>{html.escape(name)} | {html.escape(aid)}</div>
            <div>{chips_html}</div>
        </div>
    </div>
    """
    if label_btn:
        left, right = st.columns([1, 0.4])
        with left:
            st.markdown(card_html, unsafe_allow_html=True)
        with right:
            # um ou dois botões na coluna da direita
            if second_btn_label and second_on_click:
                b1, b2 = st.columns(2)
                with b1:
                    key1 = f"btn_{context_key}_{label_btn.replace(' ','_')}_{aid}_{event}"
                    if st.button(label_btn, key=key1, use_container_width=True):
                        on_click(aid, name, event)
                with b2:
                    key2 = f"btn_{context_key}_{second_btn_label.replace(' ','_')}_{aid}_{event}"
                    if st.button(second_btn_label, key=key2, use_container_width=True):
                        second_on_click(aid, name, event)
            else:
                key = f"btn_{context_key}_{label_btn.replace(' ','_')}_{aid}_{event}"
                if st.button(label_btn, key=key, use_container_width=True):
                    on_click(aid, name, event)
    else:
        st.markdown(card_html, unsafe_allow_html=True)

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

# =============================================================================
# Expander blocks
# =============================================================================
def _settings_expander_top(events: list[str]):
    with st.expander("Settings", expanded=True):
        st.segmented_control("Mode:", options=["Check in", "Check out", "Running Order"], key="weighin_mode")

        if st.session_state["weighin_mode"] == "Check in":
            if not events:
                st.warning("No events found.")
            else:
                default_event = events[0]
                st.session_state.setdefault("weighin_event_selected", default_event)
                if st.session_state["weighin_event_selected"] not in events:
                    st.session_state["weighin_event_selected"] = default_event
                st.segmented_control("Event:", options=events, key="weighin_event_selected")

        st.checkbox("Local mode (batch save)", key="weighin_local_mode", help="When ON, actions go to a local buffer. Click 'Save all' to commit to the sheet.")
        st.write(f"**Buffered rows:** {len(st.session_state['weighin_buffer'])}")
        c1, c2 = st.columns([1,1])
        with c1:
            if st.button("Save all", use_container_width=True, disabled=(not st.session_state["weighin_buffer"])):
                flush_buffer()
        with c2:
            if st.button("Sync data", use_container_width=True):
                st.session_state["weighin_overlay"] = pd.DataFrame()
                st.session_state["weighin_buffer"].clear()
                load_attendance.clear()
                st.rerun()

def _settings_expander_bottom():
    """Somente no Running Order: no rodapé, fechado e sem 'Sync data'."""
    with st.expander("Settings", expanded=False):
        st.segmented_control("Mode:", options=["Check in", "Check out", "Running Order"], key="weighin_mode")
        # (sem Sync data aqui)

# =============================================================================
# Sidebar controls
# =============================================================================
with st.sidebar:
    st.markdown("### Display settings")
    st.session_state["title_size"] = st.slider("Title size", 36, 96, st.session_state["title_size"])
    st.session_state["clock_size"] = st.slider("Clock size", 80, 220, st.session_state["clock_size"])
    st.session_state["coltitle_size"] = st.slider("Column title size", 16, 40, st.session_state["coltitle_size"])
    st.session_state["ro_refresh_sec"] = st.slider(
        "Running Order refresh (sec)", 3, 60, st.session_state["ro_refresh_sec"],
        help="Intervalo de atualização automática da tela pública."
    )

# =============================================================================
# MAIN
# =============================================================================
df_ath = load_athletes()
events = _events_from_athletes(df_ath)

mode = st.session_state.get("weighin_mode","Check in")

# >>> Gate de autenticação só para modos com ação
if mode in ("Check in", "Check out") and not st.session_state.get("user_confirmed", False):
    st.error("Você precisa estar logado para usar Check in / Check out. Abra a página **Login** neste dispositivo, faça login e retorne.")
    st.stop()
# <<<

if mode in ("Check in","Check out"):
    _settings_expander_top(events)
# (no Running Order o settings fica no rodapé)

if st.session_state.get("weighin_event_selected") is None and events:
    st.session_state["weighin_event_selected"] = events[0]
selected_event = st.session_state.get("weighin_event_selected") or (events[0] if events else "")

# Cabeçalho por aba
header_map = {
    "Check in": "Check in",
    "Check out": "Check out",
    "Running Order": "Weigh-in"
}
header_label = header_map.get(mode, "Weigh-in")

st.markdown(
    f"<h1 style='text-align:center;font-size:{st.session_state['title_size']}px;margin:8px 0 18px 0;'>"
    f"{html.escape(selected_event)} | {html.escape(header_label)}</h1>",
    unsafe_allow_html=True
)

df_att_full = _attendance_with_overlay()

# Particionamento:
# - telas interativas: No show volta para disponíveis (NONE)
# - display (running): No show aparece em OUT (coluna da direita) e vermelho
if mode == "Running Order":
    df_in, df_out, df_rest = _checked_partitions(df_ath, df_att_full, selected_event, for_running_display=True)
else:
    df_in, df_out, df_rest = _checked_partitions(df_ath, df_att_full, selected_event, for_running_display=False)

def on_check_in(aid, name, event):
    order_num = _next_checkin_order(_attendance_with_overlay(), event)
    _log_action(aid, name, event, Config.STATUS_IN, str(order_num))

def on_check_out(aid, name, event):
    _log_action(aid, name, event, Config.STATUS_OUT, "")

def on_no_show(aid, name, event):
    _log_action(aid, name, event, Config.STATUS_NOSHOW, "")

# ----------------- Check in -----------------
if mode == "Check in":
    for _, r in pd.concat([df_in, df_rest]).iterrows():
        already_in = r["__st__"] == "IN"
        # Quando já está IN, não mostra botões; quando está disponível, mostra "Check in" + "No show"
        render_card(
            r,
            None if already_in else "Check in",
            on_check_in,
            bg_color=Config.CARD_BG_IN if already_in else None,
            show_number=(r["__order__"] if already_in else None),
            context_key="in",
            second_btn_label=(None if already_in else "No show"),
            second_on_click=(None if already_in else on_no_show)
        )

# ----------------- Check out -----------------
elif mode == "Check out":
    for _, r in df_in.iterrows():
        render_card(
            r,
            "Check out",
            on_check_out,
            bg_color=Config.CARD_BG_IN,
            show_number=r["__order__"],
            context_key="out"
        )

# ----------------- Running Order (display-only) -----------------
else:
    # Auto-refresh suave que mantém a mesma sessão (não derruba o login)
    sec = int(st.session_state["ro_refresh_sec"])
    st_autorefresh(interval=max(1, sec) * 1000, key="weighin_ro_autorefresh_v4")

    cL, cM, cR = st.columns([1.2, 1, 1.2])
    col_title_css = f"font-size:{st.session_state['coltitle_size']}px;text-align:center;margin:10px 0 14px 0;font-weight:800;color:#ddd;"

    with cL:
        st.markdown(f"<div style='{col_title_css}'>Checked in</div>", unsafe_allow_html=True)
        for _, r in df_in.iterrows():
            render_card(r, None, lambda *a,**k: None, bg_color=Config.CARD_BG_IN, show_number=r['__order__'], context_key="ro_in")

    with cM:
        # Relógio em Dubai
        if ZoneInfo:
            now_dubai = datetime.now(ZoneInfo("Asia/Dubai"))
        else:
            now_dubai = datetime.now(timezone.utc) + timedelta(hours=4)
        hhmm = now_dubai.strftime("%H:%M")
        st.markdown(
            f"<div style='display:flex;align-items:center;justify-content:center;height:100%;min-height:260px;'>"
            f"<div style='font-size:{st.session_state['clock_size']}px;font-weight:900;letter-spacing:2px;color:#eaeaea;'>{hhmm}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    with cR:
        st.markdown(f"<div style='{col_title_css}'>Checked out</div>", unsafe_allow_html=True)
        for _, r in df_out.iterrows():
            # Se foi No show, pinta em vermelho; senão, cinza padrão
            bg = Config.CARD_BG_NOSHOW if bool(r.get("__noshow__", False)) else Config.CARD_BG_OUT
            render_card(r, None, lambda *a,**k: None, bg_color=bg, dimmed=not bool(r.get("__noshow__", False)), context_key="ro_out")

    # Settings específico da Running Order no rodapé (sem Sync data)
    _settings_expander_bottom()
