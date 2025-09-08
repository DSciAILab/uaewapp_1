# pages/99_Weight_in.py
# =============================================================================
# UAEW Operations App — Weight-in
# -----------------------------------------------------------------------------
# Versão: 1.8.0
# Resumo:
# - Modo Check in / Check out / Running Order para a tarefa "Weigh-in".
# - Seleção de evento por segmented (apenas no Check in); Checkout/Running order
#   seguem o evento selecionado no Check in.
# - Cartões no padrão do app: cor de corner nos chips (UAEXX | FIGHT N | CORNER).
# - Check in pinta o card de verde; Check out pinta o card de cinza.
# - Running Order em 3 colunas (in | clock | out). Sliders na sidebar para tamanhos.
# - Modo local (batch): grava em buffer e envia tudo com “Save all”.
# - Botão "Sync data" (Running Order) para sincronizar planilha ↔ cache local.
# =============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
import re
import html
from datetime import datetime

# --- Bootstrap ---
bootstrap_page("Weight-in")

# --- Project helpers ---
from utils import get_gspread_client, connect_gsheet_tab

# =============================================================================
# Config
# =============================================================================
class Config:
    MAIN_SHEET = "UAEW_App"
    ATHLETES_TAB = "df"
    ATT_TAB = "Attendance"

    TASK_NAME = "Weigh-in"            # nome final da tarefa
    STATUS_IN = "Check in"
    STATUS_OUT = "Check out"

    # Colunas reais da aba Attendance (na ordem que veremos no header)
    ATT_COLS = ["#", "Event", "Athlete ID", "Fighter", "Task", "Status", "User", "TimeStamp", "Notes"]

    # Campos dos atletas
    COL_ID = "id"
    COL_NAME = "name"
    COL_EVENT = "event"
    COL_ROLE = "role"
    COL_INACTIVE = "inactive"
    COL_IMAGE = "image"
    COL_FIGHT = "fight_number"
    COL_CORNER = "corner"

    DEFAULT_EVENT = "Z"

    # Cores
    CARD_BG_DEFAULT = "#1e1e1e"
    CARD_BG_IN = "#1f5f2b"       # verde (checked in)
    CARD_BG_OUT = "#5a5a5a"      # cinza (checked out)
    CORNER_RED = "#d9534f"
    CORNER_BLUE = "#428bca"

# =============================================================================
# Cache / estado
# =============================================================================
st.session_state.setdefault("weighin_mode", "Check in")             # "Check in" | "Check out" | "Running Order"
st.session_state.setdefault("weighin_event_selected", None)         # evento atual do fluxo
st.session_state.setdefault("weighin_local_mode", False)            # buffer local (batch)
st.session_state.setdefault("weighin_buffer", [])                   # linhas pendentes p/ salvar
st.session_state.setdefault("weighin_overlay", pd.DataFrame())      # sobreposição local ao Attendance

# Sliders (apenas para Running Order)
st.session_state.setdefault("title_size", 52)
st.session_state.setdefault("clock_size", 140)
st.session_state.setdefault("coltitle_size", 22)

# =============================================================================
# Helpers
# =============================================================================
def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    return re.sub(r"\s+", " ", s)

@st.cache_data(ttl=600)
def load_athletes() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET, Config.ATHLETES_TAB)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        # Filtros mínimos
        if Config.COL_ROLE not in df.columns or Config.COL_INACTIVE not in df.columns:
            return pd.DataFrame()
        def _inactive_to_bool(x):
            s = str(x).strip().upper()
            if s in ("FALSE", "0", ""): return False
            if s in ("TRUE", "1"): return True
            return False
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
        # Garante colunas
        for c in Config.ATT_COLS:
            if c not in df.columns: df[c] = ""
        return df
    except Exception:
        return pd.DataFrame(columns=Config.ATT_COLS)

def _attendance_with_overlay() -> pd.DataFrame:
    """Junta planilha + overlay local (sem duplicar cabeçalhos)."""
    base = load_attendance().copy()
    ov = st.session_state["weighin_overlay"]
    if not ov.empty:
        base = pd.concat([base, ov[Config.ATT_COLS]], ignore_index=True)
    return base

def _extract_event_num(ev: str) -> int:
    m = re.search(r"(\d+)$", str(ev))
    return int(m.group(1)) if m else 10**9

def _events_from_athletes(df_ath: pd.DataFrame) -> list[str]:
    evs = sorted([x for x in df_ath[Config.COL_EVENT].unique() if x and x != Config.DEFAULT_EVENT],
                 key=_extract_event_num)
    return evs

def _last_status_for_event(df_att: pd.DataFrame, event: str) -> pd.DataFrame:
    """Último status por Athlete ID para a TASK no evento."""
    if df_att.empty: return pd.DataFrame(columns=["Athlete ID","Status","Notes","TS","Fighter"])
    df = df_att.copy()
    df = df[(df["Event"].astype(str)==str(event)) & (df["Task"].astype(str)==Config.TASK_NAME)]
    if df.empty: return pd.DataFrame(columns=["Athlete ID","Status","Notes","TS","Fighter"])
    # Time (TimeStamp é o campo usado)
    ts = pd.to_datetime(df["TimeStamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df = df.assign(_ts=ts).sort_values(by=["Athlete ID","_ts"], ascending=[True, True])
    latest = df.groupby("Athlete ID", as_index=False).tail(1)
    latest = latest.rename(columns={"Status":"Status", "Notes":"Notes", "Fighter":"Fighter"})
    latest["TS"] = latest["_ts"]
    return latest[["Athlete ID","Status","Notes","TS","Fighter"]]

def _order_from_notes(x):
    try:
        return int(str(x).strip())
    except Exception:
        return None

def _checked_partitions(df_ath: pd.DataFrame, df_att: pd.DataFrame, event: str):
    """Retorna (df_in, df_out, df_rest) para o evento."""
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
        return "NONE"
    df_ev = df_ath[df_ath[Config.COL_EVENT]==event].copy()
    if df_ev.empty:
        return df_ev.copy(), df_ev.copy(), df_ev.copy()
    df_ev["__st__"] = df_ev.apply(_row_status, axis=1)
    # junta ordem
    df_ev["__order__"] = df_ev[Config.COL_ID].astype(str).map(
        lambda aid: _order_from_notes(last.loc[str(aid), "Notes"]) if str(aid) in last.index else None
    )
    df_in  = df_ev[df_ev["__st__"]=="IN"].copy()
    df_out = df_ev[df_ev["__st__"]=="OUT"].copy()
    df_rest= df_ev[df_ev["__st__"]=="NONE"].copy()
    # ordena in por ordem, depois nome
    df_in = df_in.sort_values(by=["__order__", Config.COL_NAME], ascending=[True, True])
    df_out = df_out.sort_values(by=[Config.COL_NAME])
    df_rest = df_rest.sort_values(by=[Config.COL_NAME])
    return df_in, df_out, df_rest

def _next_checkin_order(df_att: pd.DataFrame, event: str) -> int:
    last = _last_status_for_event(df_att, event)
    if last.empty: return 1
    # conta quantos ainda estão IN (último status foi IN)
    cnt = (last["Status"]==Config.STATUS_IN).sum()
    return int(cnt) + 1

def _ensure_header(ws) -> list[str]:
    header = ws.row_values(1)
    if not header:
        ws.append_row(Config.ATT_COLS, value_input_option="USER_ENTERED")
        return Config.ATT_COLS
    return header

def _append_row_aligned(values_by_name: dict) -> bool:
    """Append em Attendance, alinhado ao header real."""
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET, Config.ATT_TAB)
        header = _ensure_header(ws)
        # próximo "#"
        next_num = ""
        if "#" in header:
            col_idx = header.index("#")+1
            col_vals = ws.col_values(col_idx)
            if len(col_vals)>1 and str(col_vals[-1]).strip().isdigit():
                next_num = str(int(col_vals[-1])+1)
            else:
                next_num = str(len(col_vals))
        values_by_name["#"] = next_num
        row = [values_by_name.get(h, "") for h in header]
        ws.append_row(row, value_input_option="USER_ENTERED")
        load_attendance.clear()
        return True
    except Exception as e:
        st.error(f"Append error: {e}", icon="🚨")
        return False

def _queue_buffer(event, athlete_id, fighter, status, notes):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    user_ident = st.session_state.get("current_user_name", "System")
    st.session_state["weighin_buffer"].append({
        "Event": event,
        "Athlete ID": str(athlete_id),
        "Fighter": fighter,
        "Task": Config.TASK_NAME,
        "Status": status,
        "User": user_ident,
        "TimeStamp": ts,
        "Notes": str(notes) if notes is not None else "",
    })
    # Mantém também uma sobreposição local para o estado atual
    ov = st.session_state["weighin_overlay"]
    add = pd.DataFrame([st.session_state["weighin_buffer"][-1]])
    st.session_state["weighin_overlay"] = pd.concat([ov, add], ignore_index=True)

def flush_buffer():
    buf = st.session_state["weighin_buffer"]
    if not buf:
        st.info("Nothing to save.")
        return
    ok = 0
    for rec in buf:
        if _append_row_aligned(rec): ok += 1
    st.session_state["weighin_buffer"].clear()
    st.session_state["weighin_overlay"] = pd.DataFrame()
    st.success(f"Saved {ok} rows.", icon="✅")

def sync_data():
    """Recarrega planilha e limpa overlay local (não mexe no buffer)."""
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

def render_card(row: pd.Series, label_btn: str, on_click, bg_color=None, disabled=False, show_number=None, dimmed=False):
    """Card com (número da fila) | foto | texto + botão único."""
    aid = str(row.get(Config.COL_ID,""))
    name = str(row.get(Config.COL_NAME,""))
    event = str(row.get(Config.COL_EVENT,""))
    fight = str(row.get(Config.COL_FIGHT,""))
    corner = str(row.get(Config.COL_CORNER,""))
    img = str(row.get(Config.COL_IMAGE,""))
    chip = _corner_chip(event, fight, corner)

    bg = bg_color or Config.CARD_BG_DEFAULT
    if dimmed: bg = Config.CARD_BG_OUT

    num_html = ""
    if show_number is not None:
        num_html = f"<div style='width:48px;height:48px;border-radius:10px;display:flex;align-items:center;justify-content:center;background:#0b3b1b;color:#fff;font-weight:800;'>{show_number}</div>"

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
    c1, c2 = st.columns([4,1])
    with c1: st.markdown(card, unsafe_allow_html=True)
    with c2:
        btn = st.button(label_btn, use_container_width=True, disabled=disabled)
        if btn:
            on_click(aid, name, event)

# =============================================================================
# Handlers (NÃO alterar st.session_state["weighin_mode"] aqui)
# =============================================================================
def on_check_in(aid: str, name: str, event: str):
    use_local = st.session_state["weighin_local_mode"]
    df_att = _attendance_with_overlay()
    order_num = _next_checkin_order(df_att, event)
    if use_local:
        _queue_buffer(event, aid, name, Config.STATUS_IN, order_num)
        st.toast(f"Check in (order {order_num}) — local.", icon="✅")
        st.rerun()
    else:
        rec = {
            "Event": event, "Athlete ID": str(aid), "Fighter": name,
            "Task": Config.TASK_NAME, "Status": Config.STATUS_IN,
            "User": st.session_state.get("current_user_name","System"),
            "TimeStamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Notes": str(order_num),
        }
        if _append_row_aligned(rec):
            st.toast(f"Check in saved (order {order_num}).", icon="✅")
            st.rerun()

def on_check_out(aid: str, name: str, event: str):
    use_local = st.session_state["weighin_local_mode"]
    # valida: só quem está IN pode sair
    df_att = _attendance_with_overlay()
    df_in, _, _ = _checked_partitions(load_athletes(), df_att, event)
    if aid not in set(df_in[Config.COL_ID].astype(str)):
        st.warning("Only athletes currently checked in can be checked out.", icon="⚠️")
        return
    if use_local:
        _queue_buffer(event, aid, name, Config.STATUS_OUT, "")
        st.toast("Check out (local).", icon="✅")
        st.rerun()
    else:
        rec = {
            "Event": event, "Athlete ID": str(aid), "Fighter": name,
            "Task": Config.TASK_NAME, "Status": Config.STATUS_OUT,
            "User": st.session_state.get("current_user_name","System"),
            "TimeStamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "Notes": "",
        }
        if _append_row_aligned(rec):
            st.toast("Check out saved.", icon="✅")
            st.rerun()

# =============================================================================
# Layout principal
# =============================================================================
st.sidebar.header("Display")
if st.session_state["weighin_mode"] == "Running Order":
    st.session_state["title_size"] = st.sidebar.slider("Page title size", 30, 96, st.session_state["title_size"])
    st.session_state["clock_size"] = st.sidebar.slider("Clock size (HH:MM)", 60, 220, st.session_state["clock_size"])
    st.session_state["coltitle_size"] = st.sidebar.slider("Column titles size", 14, 40, st.session_state["coltitle_size"])

# Barra de status do buffer
st.sidebar.caption(f"Buffered rows: **{len(st.session_state['weighin_buffer'])}**")
if st.sidebar.button("Save all", use_container_width=True, type="primary", disabled=(len(st.session_state['weighin_buffer'])==0)):
    flush_buffer()
    st.rerun()

# Carrega dados base
df_ath = load_athletes()
events = _events_from_athletes(df_ath)

# ===========================
# Expander (topo para IN/OUT)
# ===========================
def _settings_expander_top():
    with st.expander("Settings", expanded=True):
        st.session_state["weighin_mode"] = st.segmented_control(
            "Mode:",
            options=["Check in","Check out","Running Order"],
            key="weighin_mode",
        )
        # Evento apenas no Check in
        if st.session_state["weighin_mode"] == "Check in":
            if not events:
                st.warning("No events found for athletes.")
            else:
                # Sem "All"; default = menor número; se 1 evento, já seleciona
                default_event = events[0]
                st.session_state.setdefault("weighin_event_selected", default_event)
                # Se a seleção não está na lista (mudança no sheet), force para default
                if st.session_state["weighin_event_selected"] not in events:
                    st.session_state["weighin_event_selected"] = default_event
                # segmented de eventos
                st.session_state["weighin_event_selected"] = st.segmented_control(
                    "Event:",
                    options=events,
                    key="weighin_event_segmented"
                )
            st.session_state["weighin_local_mode"] = st.checkbox("Local mode (batch save)  ", value=st.session_state["weighin_local_mode"], help="Keep clicks in a local buffer to save in batch later.")
        else:
            # Nas outras abas, NUNCA mostramos o seletor de evento; usamos o que veio do Check in
            if st.session_state.get("weighin_event_selected") is None and events:
                st.session_state["weighin_event_selected"] = events[0]

# ==============================
# Expander (rodapé do RUN ORDER)
# ==============================
def _settings_expander_bottom():
    with st.expander("Settings", expanded=False):
        # Modo (permite trocar aba aqui também)
        st.session_state["weighin_mode"] = st.segmented_control(
            "Mode:",
            options=["Check in","Check out","Running Order"],
            key="weighin_mode_bottom",
        )
        # Sync exclusivo aqui
        if st.button("Sync data", use_container_width=True):
            sync_data()
            st.rerun()

# ----------------- Render -----------------
mode = st.session_state["weighin_mode"]

# Expander topo para Check in / out
if mode in ("Check in","Check out"):
    _settings_expander_top()
else:
    # Running order: sem expander de topo
    pass

selected_event = st.session_state.get("weighin_event_selected") or (events[0] if events else "")

# Título
title_css = f"<h1 style='text-align:center;font-size:{st.session_state['title_size']}px;margin:10px 0 20px 0;'>{html.escape(selected_event)} | Weigh-in</h1>"
st.markdown(title_css, unsafe_allow_html=True)

df_att_full = _attendance_with_overlay()
df_in, df_out, df_rest = _checked_partitions(df_ath, df_att_full, selected_event)

# ----------------- Modo: Check in -----------------
if mode == "Check in":
    # Busca rápida
    st.text_input("Search Athlete:", key="weighin_search", placeholder="Type name or ID...")
    term = (st.session_state.get("weighin_search","") or "").strip().lower()
    # Lista: IN primeiro (para mostrar verdes), depois rest
    listing = pd.concat([df_in, df_rest], ignore_index=True)
    if term:
        listing = listing[
            listing[Config.COL_NAME].str.lower().str.contains(term, na=False) |
            listing[Config.COL_ID].astype(str).str.contains(term, na=False)
        ]
    # Render
    for _, r in listing.iterrows():
        already_in = r["__st__"]=="IN"
        render_card(
            r,
            "Check in",
            on_check_in,
            bg_color=Config.CARD_BG_IN if already_in else None,
            disabled=already_in,   # não deixa fazer check-in de novo
            show_number=(r["__order__"] if already_in else None)
        )
        st.divider()

# ----------------- Modo: Check out -----------------
elif mode == "Check out":
    st.text_input("Search Athlete:", key="weighin_search_out", placeholder="Type name or ID...")
    term = (st.session_state.get("weighin_search_out","") or "").strip().lower()
    listing = df_in.copy()  # apenas quem está in
    if term:
        listing = listing[
            listing[Config.COL_NAME].str.lower().str.contains(term, na=False) |
            listing[Config.COL_ID].astype(str).str.contains(term, na=False)
        ]
    if listing.empty:
        st.info("No athletes currently checked in.")
    for _, r in listing.iterrows():
        render_card(
            r,
            "Check out",
            on_check_out,
            bg_color=Config.CARD_BG_IN,   # mostra verde enquanto está in
        )
        st.divider()

# ----------------- Modo: Running Order -----------------
else:
    # 3 colunas: IN | CLOCK | OUT
    cL, cM, cR = st.columns([1.2, 1, 1.2])

    col_title_css = f"font-size:{st.session_state['coltitle_size']}px;text-align:center;margin:10px 0 14px 0;font-weight:800;color:#ddd;"

    with cL:
        st.markdown(f"<div style='{col_title_css}'>Checked in</div>", unsafe_allow_html=True)
        if df_in.empty:
            st.info("No one checked in yet.")
        for _, r in df_in.iterrows():
            render_card(r, "Check out", on_check_out, bg_color=Config.CARD_BG_IN, show_number=r["__order__"])
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    with cM:
        # Relógio centralizado H:MM
        st.markdown(
            f"""
            <div style='display:flex;align-items:center;justify-content:center;height:100%;min-height:240px;'>
                <div style='font-size:{st.session_state['clock_size']}px;font-weight:900;letter-spacing:2px;color:#eaeaea;'>
                    {datetime.now().strftime('%H:%M')}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with cR:
        st.markdown(f"<div style='{col_title_css}'>Checked out</div>", unsafe_allow_html=True)
        if df_out.empty:
            st.info("No one checked out yet.")
        for _, r in df_out.iterrows():
            render_card(r, "Checked out", lambda *args, **kwargs: None, bg_color=Config.CARD_BG_OUT, disabled=True, show_number=None, dimmed=True)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Expander no rodapé com Sync
    _settings_expander_bottom()
