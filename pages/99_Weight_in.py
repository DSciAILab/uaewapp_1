# ==============================================================================
# UAEW Operations App — Weigh-in Page
# ------------------------------------------------------------------------------
# Versão:        1.6.0
# Atualizado:    2025-09-08
#
# 1.6.0
# - Sliders na sidebar para tamanhos: Título da página, Relógio (HH:MM) e
#   títulos das colunas (centralizados).
# - Running Order: 3 colunas (Checked in | Clock | Checked out). Relógio HH:MM.
# - Settings no rodapé (fechado por padrão).
# - (Opcional) Modo "Local buffer (batch save)" para operar sem escrever
#   na planilha a cada clique; UI reflete o buffer; botões Save all/Discard.
# - Em qualquer clique (in/out): st.rerun().
# ==============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import html
import re
import unicodedata

# Bootstrap
bootstrap_page("Weigh-in")

# Auto-refresh opcional p/ o relógio (se lib existir)
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# Helpers de planilha
from utils import get_gspread_client, connect_gsheet_tab


# ==============================================================================
# CONFIG / CONSTANTES
# ==============================================================================
class Config:
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"

    TASK_NAME = "Weigh-in"
    STATUS_CHECKIN  = "Check in"
    STATUS_CHECKOUT = "Check out"

    # df (athletes)
    COL_ID = "id"
    COL_NAME = "name"
    COL_EVENT = "event"
    COL_ROLE = "role"
    COL_INACTIVE = "inactive"
    COL_IMAGE = "image"
    COL_MOBILE = "mobile"
    COL_FIGHT_NUMBER = "fight_number"
    COL_CORNER = "corner"
    DEFAULT_EVENT_PLACEHOLDER = "Z"

    # Attendance (nomes exatos)
    ATT_COL_ROWID = "#"
    ATT_COL_EVENT = "Event"
    ATT_COL_ATHLETE_ID = "Athlete ID"
    ATT_COL_FIGHTER = "Fighter"
    ATT_COL_TASK = "Task"
    ATT_COL_STATUS = "Status"
    ATT_COL_USER = "User"
    ATT_COL_TIMESTAMP_ALT = "TimeStamp"
    ATT_COL_NOTES = "Notes"

    # Cores
    CARD_BG_DEFAULT    = "#1e1e1e"
    CARD_BG_CHECKED    = "#145A32"  # verde (checked in)
    CARD_BG_CHECKEDOUT = "#555555"  # cinza (checked out)
    CORNER_COLOR = {"red": "#d9534f", "blue": "#428bca"}


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

def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if df is None or df.empty:
        return pd.Series([], dtype=object)
    if name in df.columns:
        return df[name]
    return pd.Series([""] * len(df), index=df.index, dtype=object)

def _event_number_key(ev: str) -> tuple:
    s = str(ev or "")
    m = re.search(r"(\d+)", s)
    num = int(m.group(1)) if m else 999999
    return (num, s.upper())

def _corner_color(corner: str) -> str:
    return Config.CORNER_COLOR.get((corner or "").strip().lower(), "#4A4A4A")


# ==============================================================================
# CACHE: leitura de dados
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

        # checks
        if Config.COL_ROLE not in df.columns or Config.COL_INACTIVE not in df.columns:
            st.error("Columns 'ROLE'/'INACTIVE' not found in athletes sheet.", icon="🚨")
            return pd.DataFrame()
        if Config.COL_NAME not in df.columns or Config.COL_ID not in df.columns:
            st.error("'name' or 'id' missing in athletes sheet.", icon="🚨")
            return pd.DataFrame()

        # inativos
        if df[Config.COL_INACTIVE].dtype == "object":
            df[Config.COL_INACTIVE] = (
                df[Config.COL_INACTIVE].astype(str).str.strip().str.upper()
                .map({"FALSE": False, "TRUE": True, "": True})
                .fillna(True)
            )
        elif pd.api.types.is_numeric_dtype(df[Config.COL_INACTIVE]):
            df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].map({0: False, 1: True}).fillna(True)

        # apenas lutadores ativos
        df = df[(df[Config.COL_ROLE] == "1 - Fighter") & (df[Config.COL_INACTIVE] == False)].copy()

        for c in [Config.COL_EVENT, Config.COL_IMAGE, Config.COL_MOBILE, Config.COL_FIGHT_NUMBER, Config.COL_CORNER]:
            if c not in df.columns:
                df[c] = ""
            else:
                df[c] = df[c].fillna("")
        df[Config.COL_EVENT] = df[Config.COL_EVENT].replace(_INVALID_STRS, Config.DEFAULT_EVENT_PLACEHOLDER)

        return df.sort_values(by=[Config.COL_EVENT, Config.COL_NAME]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading athletes: {e}", icon="🚨")
        return pd.DataFrame()


@st.cache_data(ttl=180)
def load_attendance() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB_NAME)
        return pd.DataFrame(ws.get_all_records())
    except Exception as e:
        st.error(f"Error loading Attendance: {e}", icon="🚨")
        return pd.DataFrame()


# ==============================================================================
# Escrita na Attendance (alinhada ao cabeçalho real)
# ==============================================================================
def append_attendance_row(event: str, athlete_id: str, fighter: str,
                          status: str, notes: str | int = "") -> bool:
    """Append de UMA linha na aba Attendance alinhando ao header real."""
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB_NAME)

        # header real
        header = ws.row_values(1)
        if not header:
            header = [
                Config.ATT_COL_ROWID, Config.ATT_COL_EVENT, Config.ATT_COL_ATHLETE_ID, Config.ATT_COL_FIGHTER,
                Config.ATT_COL_TASK, Config.ATT_COL_STATUS, Config.ATT_COL_USER, Config.ATT_COL_TIMESTAMP_ALT,
                Config.ATT_COL_NOTES
            ]
            ws.append_row(header, value_input_option="USER_ENTERED")

        # próximo "#"
        next_num = ""
        if Config.ATT_COL_ROWID in header:
            col_idx = header.index(Config.ATT_COL_ROWID) + 1
            col_vals = ws.col_values(col_idx)
            if len(col_vals) <= 1:
                next_num = "1"
            else:
                last_val = ""
                for v in reversed(col_vals[1:]):
                    vv = str(v).strip()
                    if vv:
                        last_val = vv
                        break
                next_num = str(int(last_val) + 1) if last_val.isdigit() else str(len(col_vals))

        # dados
        ts_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get("current_user_name") or st.session_state.get("current_user_id") or "System"
        row_map = {
            Config.ATT_COL_ROWID: next_num,
            Config.ATT_COL_EVENT: event,
            Config.ATT_COL_ATHLETE_ID: str(athlete_id or ""),
            Config.ATT_COL_FIGHTER: fighter,
            Config.ATT_COL_TASK: Config.TASK_NAME,
            Config.ATT_COL_STATUS: status,
            Config.ATT_COL_USER: user_ident,
            Config.ATT_COL_TIMESTAMP_ALT: ts_now,
            Config.ATT_COL_NOTES: str(notes) if notes is not None else ""
        }

        ws.append_row([row_map.get(col, "") for col in header], value_input_option="USER_ENTERED")
        load_attendance.clear()
        return True
    except Exception as e:
        st.error(f"Error writing Attendance: {e}", icon="🚨")
        return False


# ==============================================================================
# Lógica de status/ordem (Sheet)
# ==============================================================================
def next_checkin_order(df_att: pd.DataFrame, event: str) -> int:
    if df_att is None or df_att.empty:
        return 1
    ev = _col(df_att, "Event").astype(str)
    task = _col(df_att, "Task").astype(str).str.lower()
    status = _col(df_att, "Status").astype(str).str.lower()
    notes = _col(df_att, "Notes")
    mask = (ev == str(event)) & (task == Config.TASK_NAME.lower()) & (status == Config.STATUS_CHECKIN.lower())
    df = df_att[mask].copy()
    if df.empty:
        return 1
    notes_num = pd.to_numeric(notes[mask], errors="coerce")
    return int(notes_num.max()) + 1 if notes_num.notna().any() else len(df) + 1

def latest_status_map(df_att: pd.DataFrame, event: str) -> dict[str, str]:
    if df_att is None or df_att.empty:
        return {}
    ev = _col(df_att, "Event").astype(str)
    task = _col(df_att, "Task").astype(str).str.lower()
    status = _col(df_att, "Status").astype(str)
    ts = _col(df_att, "TimeStamp")
    aid = _col(df_att, "Athlete ID").astype(str)

    mask = (ev == str(event)) & (task == Config.TASK_NAME.lower())
    sub = df_att[mask].copy()
    if sub.empty:
        return {}

    sub["__ts__"] = pd.to_datetime(ts[mask], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    sub["__idx__"] = np.arange(len(sub))
    sub = sub.sort_values(by=["__ts__", "__idx__"], ascending=[True, True])

    last_by_id = {}
    for _, r in sub.iterrows():
        last_by_id[str(r.get("Athlete ID", ""))] = str(r.get("Status", "")).strip().lower()
    return last_by_id

def last_checkin_order_by_id(df_att: pd.DataFrame, event: str) -> dict[str, int]:
    out: dict[str, int] = {}
    if df_att is None or df_att.empty:
        return out
    ev = _col(df_att, "Event").astype(str)
    task = _col(df_att, "Task").astype(str).str.lower()
    status = _col(df_att, "Status").astype(str).str.lower()
    notes = _col(df_att, "Notes")
    ts = _col(df_att, "TimeStamp")

    mask = (ev == str(event)) & (task == Config.TASK_NAME.lower()) & (status == Config.STATUS_CHECKIN.lower())
    sub = df_att[mask].copy()
    if sub.empty:
        return out

    sub["__ts__"] = pd.to_datetime(ts[mask], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    sub["__idx__"] = np.arange(len(sub))
    sub = sub.sort_values(by=["__ts__", "__idx__"], ascending=[True, True])

    for aid_str in sub["Athlete ID"].astype(str).unique():
        last_row = sub[sub["Athlete ID"].astype(str) == aid_str].iloc[-1]
        n = pd.to_numeric(last_row.get("Notes", ""), errors="coerce")
        if pd.notna(n):
            out[aid_str] = int(n)
    return out


# ==============================================================================
# UI — estilos
# ==============================================================================
st.markdown("""
<style>
  .card-container { padding: 15px; border-radius: 12px; margin-bottom: 12px;
      display: grid; grid-template-columns: 64px 64px 1fr; gap: 12px; align-items: center; }
  .order-pill { display:flex; align-items:center; justify-content:center;
      width: 64px; height: 64px; border-radius: 12px; background:#0b2840; color:#fff;
      font-weight: 900; font-size: 1.25rem; }
  .card-img { width: 64px; height: 64px; border-radius: 50%; object-fit: cover; }
  .card-info { display: flex; flex-direction: column; gap: 6px; }
  .info-line { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
  .fighter-name { font-size: 1.15rem; font-weight: 800; margin: 0; color: white; }
  .badge { color:#fff; padding:3px 10px; border-radius:8px; font-size:.8rem; font-weight:700; display:inline-flex; }
  .clock-wrap { min-height: 60vh; display:flex; align-items:center; justify-content:center; }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# ESTADO / SIDEBAR (sliders)
# ==============================================================================
st.session_state.setdefault("weighin_mode", "Check in")
st.session_state.setdefault("weighin_event", None)
st.session_state.setdefault("weighin_search", "")
st.session_state.setdefault("weighin_buffer", [])         # lista de dicts pendentes
st.session_state.setdefault("weighin_local_mode", False)  # batch save

with st.sidebar:
    st.header("Display")
    title_px = st.slider("Title size (px)", 28, 96, 48, 1, key="weighin_title_px")
    clock_px = st.slider("Clock size (px)", 40, 200, 110, 1, key="weighin_clock_px")
    coltitle_px = st.slider("Column title size (px)", 14, 48, 22, 1, key="weighin_coltitle_px")

# === Leitura bases ===
df_ath_all = load_athletes()

# Eventos válidos
valid_events = []
if not df_ath_all.empty:
    valid_events = sorted(
        [e for e in df_ath_all[Config.COL_EVENT].unique() if e and e != Config.DEFAULT_EVENT_PLACEHOLDER],
        key=_event_number_key
    )

if st.session_state["weighin_event"] is None and valid_events:
    st.session_state["weighin_event"] = valid_events[0]

sel_event = st.session_state["weighin_event"]

# === TÍTULO (tamanho via slider) ===
title_text = f"{sel_event} | Weigh-in" if sel_event else "Weigh-in"
st.markdown(
    f"<h1 style='text-align:center; font-size:{title_px}px; margin-top:.25rem;'>{html.escape(title_text)}</h1>",
    unsafe_allow_html=True
)

if not sel_event:
    st.info("No valid events to display.")
    st.stop()

df_ath = df_ath_all[df_ath_all[Config.COL_EVENT] == sel_event].copy().sort_values(by=[Config.COL_NAME]).reset_index(drop=True)
df_att = load_attendance()

# ==============================================================================
# LÓGICA DE OVERLAY LOCAL (buffer) — para operar sem gravar a cada clique
# ==============================================================================
def _buffer_for_event(event: str):
    return [x for x in st.session_state["weighin_buffer"] if x.get("Event") == event]

def _apply_buffer_overlays(event: str, last_status: dict[str, str], order_by_id: dict[str, int]) -> tuple[dict[str,str], dict[str,int]]:
    """Aplica pendências do buffer no mapa de status e nas ordens."""
    ls = dict(last_status)
    ob = dict(order_by_id)
    for row in _buffer_for_event(event):
        aid = str(row.get("Athlete ID", ""))
        status = str(row.get("Status","")).strip().lower()
        ls[aid] = status
        if status == Config.STATUS_CHECKIN.lower():
            n = row.get("Notes", "")
            try:
                nn = int(n)
                ob[aid] = nn
            except Exception:
                pass
        elif status == Config.STATUS_CHECKOUT.lower():
            # no running order number for checked out
            pass
    return ls, ob

def _next_checkin_order_overlay(base_df_att: pd.DataFrame, event: str) -> int:
    """Próxima ordem considerando também o buffer local."""
    base = next_checkin_order(base_df_att, event)
    extra = sum(1 for r in _buffer_for_event(event) if str(r.get("Status","")).strip().lower() == Config.STATUS_CHECKIN.lower())
    return base + extra

# mapas nativos da planilha
last_status_sheet = latest_status_map(df_att, sel_event)
order_by_id_sheet = last_checkin_order_by_id(df_att, sel_event)

# aplica overlay local se ativado
use_local = st.session_state["weighin_local_mode"]
if use_local:
    last_status, order_by_id = _apply_buffer_overlays(sel_event, last_status_sheet, order_by_id_sheet)
else:
    last_status, order_by_id = last_status_sheet, order_by_id_sheet

checked_in_now  = {aid for aid, s in last_status.items() if s == Config.STATUS_CHECKIN.lower()}
checked_out_now = {aid for aid, s in last_status.items() if s == Config.STATUS_CHECKOUT.lower()}

# ==============================================================================
# HANDLERS (respeitam o modo local/planilha)
# ==============================================================================
def _queue_buffer(event, athlete_id, fighter, status, notes=""):
    st.session_state["weighin_buffer"].append({
        "Event": event,
        "Athlete ID": str(athlete_id),
        "Fighter": fighter,
        "Task": Config.TASK_NAME,
        "Status": status,
        "User": st.session_state.get("current_user_name") or st.session_state.get("current_user_id") or "System",
        "TimeStamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "Notes": notes,
    })

def on_check_in(aid: str, name: str, event: str):
    if use_local:
        order_num = _next_checkin_order_overlay(df_att, event)
        _queue_buffer(event, aid, name, Config.STATUS_CHECKIN, order_num)
        st.toast(f"Check in (local) — ordem {order_num}.", icon="✅")
        st.rerun()
    else:
        order_num = next_checkin_order(load_attendance(), event)
        if append_attendance_row(event=event, athlete_id=aid, fighter=name,
                                 status=Config.STATUS_CHECKIN, notes=order_num):
            st.toast(f"Check in registrado (ordem {order_num}).", icon="✅")
            st.rerun()

def on_check_out(aid: str, name: str, event: str):
    # precisa estar IN (considerando overlay local)
    if aid not in checked_in_now:
        st.warning("Only athletes currently checked in can be checked out.", icon="⚠️")
        return
    if use_local:
        _queue_buffer(event, aid, name, Config.STATUS_CHECKOUT, "")
        st.toast("Check out (local).", icon="✅")
        st.rerun()
    else:
        if append_attendance_row(event=event, athlete_id=aid, fighter=name,
                                 status=Config.STATUS_CHECKOUT, notes=""):
            st.toast("Check out registrado.", icon="✅")
            st.rerun()


# ==============================================================================
# RENDER HELPERS
# ==============================================================================
def render_card_action(row: pd.Series, btn_label: str, on_click, bg_color: str):
    aid = str(row.get(Config.COL_ID, ""))
    name = str(row.get(Config.COL_NAME, ""))
    event = str(row.get(Config.COL_EVENT, ""))
    fight_n = str(row.get(Config.COL_FIGHT_NUMBER, ""))
    corner = str(row.get(Config.COL_CORNER, ""))
    img = str(row.get(Config.COL_IMAGE, "https://via.placeholder.com/64?text=NA"))

    chip_color = _corner_color(corner)
    bits = []
    if event and event != Config.DEFAULT_EVENT_PLACEHOLDER: bits.append(html.escape(event))
    if fight_n: bits.append(f"FIGHT {html.escape(fight_n)}")
    if corner:  bits.append(html.escape(corner.upper()))
    chip_html = f"<span class='badge' style='background:{chip_color}'>{' | '.join(bits)}</span>" if bits else ""

    left, right = st.columns([2.5, 1])
    with left:
        st.markdown(
            f"""
            <div class='card-container' style='grid-template-columns: 0px 64px 1fr; background:{bg_color};'>
              <div></div>
              <img src='{html.escape(img, True)}' class='card-img'>
              <div class='card-info'>
                <div class='info-line'><span class='fighter-name'>{html.escape(name)} | {html.escape(aid)}</span></div>
                <div class='info-line'>{chip_html}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with right:
        if st.button(btn_label, key=f"{btn_label.replace(' ','_').lower()}_{aid}", use_container_width=True):
            on_click(aid, name, event)
    st.divider()

def render_board_card(row: pd.Series, order_num: int | None, bg_color: str):
    aid = str(row.get(Config.COL_ID, ""))
    name = str(row.get(Config.COL_NAME, ""))
    event = str(row.get(Config.COL_EVENT, ""))
    fight_n = str(row.get(Config.COL_FIGHT_NUMBER, ""))
    corner = str(row.get(Config.COL_CORNER, ""))
    img = str(row.get(Config.COL_IMAGE, "https://via.placeholder.com/64?text=NA"))

    chip_color = _corner_color(corner)
    bits = []
    if event and event != Config.DEFAULT_EVENT_PLACEHOLDER: bits.append(html.escape(event))
    if fight_n: bits.append(f"FIGHT {html.escape(fight_n)}")
    if corner:  bits.append(html.escape(corner.upper()))
    chip_html = f"<span class='badge' style='background:{chip_color}'>{' | '.join(bits)}</span>" if bits else ""

    st.markdown(
        f"""
        <div class='card-container' style='background:{bg_color};'>
          <div class='order-pill'>{html.escape(str(order_num)) if order_num is not None else '-'}</div>
          <img src='{html.escape(img, True)}' class='card-img'>
          <div class='card-info'>
            <div class='info-line'><span class='fighter-name'>{html.escape(name)} | {html.escape(aid)}</span></div>
            <div class='info-line'>{chip_html}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def col_title(text: str, size_px: int):
    st.markdown(f"<div style='text-align:center; font-size:{size_px}px; font-weight:800; margin:.25rem 0 .75rem 0;'>{html.escape(text)}</div>", unsafe_allow_html=True)


# ==============================================================================
# CONTEÚDO (por modo)
# ==============================================================================
mode = st.session_state["weighin_mode"]

if mode == "Running Order":
    if st_autorefresh:
        st_autorefresh(interval=1000, key="weighin_clock_tick")

    left_ids  = [aid for aid in checked_in_now]
    right_ids = [aid for aid in checked_out_now]

    left_df  = df_ath[df_ath[Config.COL_ID].astype(str).isin(left_ids)].copy()
    right_df = df_ath[df_ath[Config.COL_ID].astype(str).isin(right_ids)].copy()

    left_df["__ord__"] = left_df[Config.COL_ID].astype(str).map(order_by_id).fillna(1e9).astype(float)
    left_df = left_df.sort_values(by="__ord__", ascending=True)

    cL, cM, cR = st.columns([1, 0.65, 1])

    with cL:
        col_title("Checked in", st.session_state["weighin_coltitle_px"])
        if left_df.empty:
            st.info("No check-ins yet.")
        else:
            for _, r in left_df.iterrows():
                order_num = order_by_id.get(str(r.get(Config.COL_ID, "")))
                render_board_card(r, order_num, bg_color=Config.CARD_BG_CHECKED)

    with cM:
        now = datetime.now().strftime("%H:%M")
        st.markdown(
            f"<div class='clock-wrap'><div style='font-size:{st.session_state['weighin_clock_px']}px; font-weight:900; color:#eaeaea; line-height:1;'>{now}</div></div>",
            unsafe_allow_html=True
        )

    with cR:
        col_title("Checked out", st.session_state["weighin_coltitle_px"])
        if right_df.empty:
            st.info("No check-outs yet.")
        else:
            for _, r in right_df.iterrows():
                render_board_card(r, order_num=None, bg_color=Config.CARD_BG_CHECKEDOUT)

elif mode == "Check out":
    st.text_input("Search Athlete:", key="weighin_search", placeholder="Type name or ID...")

    df_view = df_ath[df_ath[Config.COL_ID].astype(str).isin(checked_in_now)].copy()
    q = (st.session_state.get("weighin_search","") or "").strip().lower()
    if q:
        df_view = df_view[
            df_view[Config.COL_NAME].str.lower().str.contains(q, na=False) |
            df_view[Config.COL_ID].astype(str).str.lower().str.contains(q, na=False)
        ]

    for _, r in df_view.iterrows():
        render_card_action(r, "Check out", on_check_out, bg_color=Config.CARD_BG_CHECKED)

else:  # Check in
    # Evento via segmented (sem "All Events")
    if valid_events:
        st.session_state["weighin_event"] = st.segmented_control(
            "Event:",
            options=valid_events,
            key="weighin_event_segmented_header",
        )
        sel_event = st.session_state["weighin_event"]  # refletir possível troca
    st.text_input("Search Athlete:", key="weighin_search", placeholder="Type name or ID...")

    q = (st.session_state.get("weighin_search","") or "").strip().lower()
    df_view = df_ath.copy()
    if q:
        df_view = df_view[
            df_view[Config.COL_NAME].str.lower().str.contains(q, na=False) |
            df_view[Config.COL_ID].astype(str).str.lower().str.contains(q, na=False)
        ]

    for _, r in df_view.iterrows():
        aid = str(r.get(Config.COL_ID, ""))
        if aid in checked_in_now:
            bg = Config.CARD_BG_CHECKED
        elif aid in checked_out_now:
            bg = Config.CARD_BG_CHECKEDOUT
        else:
            bg = Config.CARD_BG_DEFAULT
        render_card_action(r, "Check in", on_check_in, bg_color=bg)


# ==============================================================================
# SETTINGS — RODAPÉ (fechado)
# ==============================================================================
with st.expander("Settings", expanded=False):
    st.segmented_control(
        "Mode:",
        options=["Check in", "Check out", "Running Order"],
        key="weighin_mode",
    )

    # Evento apenas em Check in (como combinado)
    if st.session_state["weighin_mode"] == "Check in" and valid_events:
        st.session_state["weighin_event"] = st.segmented_control(
            "Event:",
            options=valid_events,
            key="weighin_event_segmented_footer",
        )

    st.checkbox("Local mode (batch save)", key="weighin_local_mode", help="Acumula alterações em memória e salva depois.")
    if st.session_state["weighin_local_mode"]:
        c1, c2, c3 = st.columns([1,1,3])
        with c1:
            if st.button("Save all", use_container_width=True):
                # grava todas as linhas do buffer
                pending = list(st.session_state["weighin_buffer"])
                ok = True
                for row in pending:
                    if not append_attendance_row(
                        event=row["Event"],
                        athlete_id=row["Athlete ID"],
                        fighter=row["Fighter"],
                        status=row["Status"],
                        notes=row["Notes"]
                    ):
                        ok = False
                        break
                if ok:
                    st.session_state["weighin_buffer"].clear()
                    st.success("All buffered rows saved.", icon="✅")
                    st.rerun()
        with c2:
            if st.button("Discard", use_container_width=True):
                st.session_state["weighin_buffer"].clear()
                st.info("Buffer discarded.")
                st.rerun()
        with c3:
            st.write(f"Buffered rows: **{len(st.session_state['weighin_buffer'])}**")
