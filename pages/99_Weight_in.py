# ==============================================================================
# UAEW Operations App — Weigh-in Page
# ------------------------------------------------------------------------------
# Versão:    1.0.1
# Gerado em: 2025-09-08
#
# RESUMO
# - Página para controle de Weigh-in com 3 modos: Check in / Check out / Running Order.
# - Cards no padrão do app (sem chips e sem tag de passaporte).
# - Gravação na aba Attendance (alinhada ao cabeçalho real).
# - "Notes" recebe apenas o número da ordem de check in por evento.
#
# CHANGELOG
# 1.0.1
#   - Task = "Weigh-in"; Status = "Check in" e "Check out"; Notes = número puro.
# 1.0.0
#   - Primeira versão com modos e lógica de ordem por evento.
# ==============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import html
import unicodedata
import time

# Helpers do projeto
from utils import get_gspread_client, connect_gsheet_tab

# ------------------------------------------------------------------------------
# Bootstrap / título
# ------------------------------------------------------------------------------
bootstrap_page("Weigh-in")
st.title("Weigh-in")

# ==============================================================================
# CONFIG
# ==============================================================================
class Config:
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB    = "df"
    ATTENDANCE_TAB  = "Attendance"

    # Termos padronizados
    TASK_NAME          = "Weigh-in"   # pesagem (inglês correto)
    STATUS_CHECKIN     = "Check in"   # sem hífen, como solicitado
    STATUS_CHECKOUT    = "Check out"  # sem hífen, como solicitado

    # Colunas (exatamente como na planilha informada)
    COL_ATT_ID         = "#"
    COL_ATT_EVENT      = "Event"
    COL_ATT_ATH_ID     = "Athlete ID"
    COL_ATT_FIGHTER    = "Fighter"
    COL_ATT_TASK       = "Task"
    COL_ATT_STATUS     = "Status"
    COL_ATT_USER       = "User"
    COL_ATT_TIMESTAMP  = "TimeStamp"
    COL_ATT_NOTES      = "Notes"

    # DF atletas (snake_case)
    COL_ID       = "id"
    COL_NAME     = "name"
    COL_EVENT    = "event"
    COL_ROLE     = "role"
    COL_INACTIVE = "inactive"
    COL_IMAGE    = "image"
    COL_MOBILE   = "mobile"
    COL_FIGHT_NO = "fight_number"
    COL_CORNER   = "corner"
    COL_ROOM     = "room"

    DEFAULT_EVENT_PLACEHOLDER = "Z"  # quando event estiver vazio

# ==============================================================================
# UTILS
# ==============================================================================
def _clean_str(s) -> str:
    return "" if s is None else str(s).strip()

def _normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.split())

def _parse_dt_series(raw: pd.Series) -> pd.Series:
    if raw is None or raw.empty:
        return pd.Series([], dtype="datetime64[ns]")
    tries = [
        pd.to_datetime(raw, format="%d/%m/%Y %H:%M:%S", errors="coerce"),
        pd.to_datetime(raw, errors="coerce"),
    ]
    out = tries[0]
    for c in tries[1:]:
        out = out.fillna(c)
    return out

# ==============================================================================
# CACHED RESOURCES
# ==============================================================================
@st.cache_resource(ttl=1800, show_spinner=False)
def get_attendance_ws():
    gc = get_gspread_client()
    return connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB)

# ==============================================================================
# DATA LOADERS
# ==============================================================================
@st.cache_data(ttl=600)
def load_athletes() -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATHLETES_TAB)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return pd.DataFrame()
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        # Somente lutadores ativos
        if Config.COL_ROLE not in df.columns or Config.COL_INACTIVE not in df.columns:
            return pd.DataFrame()

        # normaliza 'inactive'
        if df[Config.COL_INACTIVE].dtype == "object":
            df[Config.COL_INACTIVE] = (
                df[Config.COL_INACTIVE]
                .astype(str).str.strip().str.upper()
                .map({"FALSE": False, "TRUE": True, "": True})
                .fillna(True)
            )
        elif pd.api.types.is_numeric_dtype(df[Config.COL_INACTIVE]):
            df[Config.COL_INACTIVE] = df[Config.COL_INACTIVE].map({0: False, 1: True}).fillna(True)

        df = df[(df[Config.COL_ROLE] == "1 - Fighter") & (df[Config.COL_INACTIVE] == False)].copy()

        # completa colunas
        for c in [Config.COL_EVENT, Config.COL_IMAGE, Config.COL_MOBILE, Config.COL_FIGHT_NO, Config.COL_CORNER, Config.COL_ROOM]:
            if c not in df.columns:
                df[c] = ""
        df[Config.COL_EVENT] = df[Config.COL_EVENT].fillna(Config.DEFAULT_EVENT_PLACEHOLDER)

        return df.sort_values([Config.COL_EVENT, Config.COL_NAME]).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_cached() -> pd.DataFrame:
    """Leitura usual (cacheada) para exibir dados."""
    try:
        ws = get_attendance_ws()
        df = pd.DataFrame(ws.get_all_records())
        # garante colunas
        for c in [
            Config.COL_ATT_ID, Config.COL_ATT_EVENT, Config.COL_ATT_ATH_ID, Config.COL_ATT_FIGHTER,
            Config.COL_ATT_TASK, Config.COL_ATT_STATUS, Config.COL_ATT_USER, Config.COL_ATT_TIMESTAMP, Config.COL_ATT_NOTES
        ]:
            if c not in df.columns:
                df[c] = pd.NA
        return df
    except Exception:
        return pd.DataFrame(columns=[
            Config.COL_ATT_ID, Config.COL_ATT_EVENT, Config.COL_ATT_ATH_ID, Config.COL_ATT_FIGHTER,
            Config.COL_ATT_TASK, Config.COL_ATT_STATUS, Config.COL_ATT_USER, Config.COL_ATT_TIMESTAMP, Config.COL_ATT_NOTES
        ])

def load_attendance_fresh() -> pd.DataFrame:
    """Leitura sem cache (para calcular ordem na hora do clique, evitando empate)."""
    try:
        ws = get_attendance_ws()
        df = pd.DataFrame(ws.get_all_records())
        for c in [
            Config.COL_ATT_ID, Config.COL_ATT_EVENT, Config.COL_ATT_ATH_ID, Config.COL_ATT_FIGHTER,
            Config.COL_ATT_TASK, Config.COL_ATT_STATUS, Config.COL_ATT_USER, Config.COL_ATT_TIMESTAMP, Config.COL_ATT_NOTES
        ]:
            if c not in df.columns:
                df[c] = pd.NA
        return df
    except Exception:
        return pd.DataFrame(columns=[
            Config.COL_ATT_ID, Config.COL_ATT_EVENT, Config.COL_ATT_ATH_ID, Config.COL_ATT_FIGHTER,
            Config.COL_ATT_TASK, Config.COL_ATT_STATUS, Config.COL_ATT_USER, Config.COL_ATT_TIMESTAMP, Config.COL_ATT_NOTES
        ])

# ==============================================================================
# ATTENDANCE WRITER (header-aligned)
# ==============================================================================
def _ensure_header(ws) -> list:
    """Lê a linha 1 do header. Se não existir, cria com as 9 colunas informadas."""
    header = ws.row_values(1)
    if not header:
        header = [
            Config.COL_ATT_ID, Config.COL_ATT_EVENT, Config.COL_ATT_ATH_ID, Config.COL_ATT_FIGHTER,
            Config.COL_ATT_TASK, Config.COL_ATT_STATUS, Config.COL_ATT_USER, Config.COL_ATT_TIMESTAMP, Config.COL_ATT_NOTES
        ]
        ws.append_row(header, value_input_option="USER_ENTERED")
    return header

def _next_row_number(ws, header: list) -> str:
    """Calcula próximo valor para coluna '#' olhando a própria coluna."""
    if Config.COL_ATT_ID not in header:
        return ""
    col_idx = header.index(Config.COL_ATT_ID) + 1
    col_vals = ws.col_values(col_idx)  # inclui header
    if len(col_vals) <= 1:
        return "1"
    last = None
    for v in reversed(col_vals[1:]):
        vv = str(v).strip()
        if vv:
            last = vv; break
    if last and last.isdigit():
        return str(int(last) + 1)
    return str(len(col_vals))  # fallback

def append_attendance_row(event: str, athlete_id: str, fighter: str, task: str, status: str, notes: str) -> bool:
    """
    Alinha a linha pelo header real e faz append.
    """
    try:
        ws = get_attendance_ws()
        header = _ensure_header(ws)
        ts_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get("current_user_name") or st.session_state.get("current_user_id") or "System"
        rownum = _next_row_number(ws, header)

        values = {
            Config.COL_ATT_ID:        rownum,
            Config.COL_ATT_EVENT:     event,
            Config.COL_ATT_ATH_ID:    str(athlete_id),
            Config.COL_ATT_FIGHTER:   fighter,
            Config.COL_ATT_TASK:      task,
            Config.COL_ATT_STATUS:    status,
            Config.COL_ATT_USER:      user_ident,
            Config.COL_ATT_TIMESTAMP: ts_now,
            Config.COL_ATT_NOTES:     notes or "",
        }
        row_list = [values.get(col, "") for col in header]
        ws.append_row(row_list, value_input_option="USER_ENTERED")
        # limpa cache de leitura
        load_attendance_cached.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao gravar Attendance: {e}", icon="🚨")
        return False

# ==============================================================================
# LÓGICA DE ORDEM & RUNNING ORDER
# ==============================================================================
def next_checkin_order_for_event(event_name: str) -> int:
    """
    Conta quantos registros 'Weigh-in' + 'Check in' existem no evento => próximo é +1.
    Usa leitura sem cache para evitar empates simultâneos.
    """
    df = load_attendance_fresh()
    if df.empty:
        return 1
    mask = (
        (df[Config.COL_ATT_EVENT].astype(str) == str(event_name)) &
        (df[Config.COL_ATT_TASK].astype(str).str.strip().str.lower() == Config.TASK_NAME.lower()) &
        (df[Config.COL_ATT_STATUS].astype(str).str.strip().str.lower() == Config.STATUS_CHECKIN.lower())
    )
    return int(mask.sum()) + 1

def get_running_order(event_name: str) -> pd.DataFrame:
    """
    Lista de check ins (para o evento), em ordem de TimeStamp (asc), enumerada.
    """
    df = load_attendance_cached()
    if df.empty:
        return pd.DataFrame(columns=["Order", "Fighter", "Time", "User"])
    df["_dt_"] = _parse_dt_series(df.get(Config.COL_ATT_TIMESTAMP, pd.Series(dtype=str)))
    mask = (
        (df[Config.COL_ATT_EVENT].astype(str) == str(event_name)) &
        (df[Config.COL_ATT_TASK].astype(str).str.strip().str.lower() == Config.TASK_NAME.lower()) &
        (df[Config.COL_ATT_STATUS].astype(str).str.strip().str.lower() == Config.STATUS_CHECKIN.lower())
    )
    dd = df.loc[mask].sort_values("_dt_", ascending=True).copy()
    if dd.empty:
        return pd.DataFrame(columns=["Order", "Fighter", "Time", "User"])
    dd["Order"] = np.arange(1, len(dd) + 1)
    dd["Fighter"] = dd[Config.COL_ATT_FIGHTER].astype(str)
    dd["Time"] = dd["_dt_"].dt.strftime("%d/%m/%Y %H:%M:%S").fillna("")
    dd["User"] = dd[Config.COL_ATT_USER].fillna("")
    return dd[["Order", "Fighter", "Time", "User"]]

# ==============================================================================
# CSS (cards sem chips/passaporte)
# ==============================================================================
st.markdown("""
<style>
  .card-container { padding: 15px; border-radius: 10px; margin-bottom: 10px; display: flex; align-items: flex-start; gap: 15px; background-color:#1e1e1e; }
  .card-img { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
  .card-info { width: 100%; display: flex; flex-direction: column; gap: 8px; }
  .info-line { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
  .fighter-name { font-size: 1.25rem; font-weight: bold; margin: 0; color: white; }
  .tag { background-color: #25D366; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold; text-decoration: none; }
  .label-chip { background-color:#428bca; color:#fff; padding:3px 10px; border-radius:8px; font-size:0.8em; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# FILTROS (expander no mesmo estilo das outras páginas)
# ==============================================================================
with st.expander("Filtros", expanded=True):
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        search = st.text_input("Buscar atleta", placeholder="Nome ou ID...")
    with c2:
        # Carregamos atletas para puxar lista de eventos
        df_ath = load_athletes()
        ev_opts = ["All Events"]
        if not df_ath.empty:
            ev_opts += sorted([e for e in df_ath[Config.COL_EVENT].dropna().unique().tolist() if e != Config.DEFAULT_EVENT_PLACEHOLDER])
        sel_event = st.selectbox("Evento", options=ev_opts, index=0)
    with c3:
        sort_by = st.segmented_control("Ordenação", options=["Name", "Fight Order"], key="weighin_sort", help="Como ordenar os cards.")

# ==============================================================================
# MODO (segmented principal)
# ==============================================================================
mode = st.segmented_control("Modo", options=[Config.STATUS_CHECKIN, Config.STATUS_CHECKOUT, "Running Order"], key="weighin_mode")

# ==============================================================================
# APLICA FILTROS AOS ATLETAS
# ==============================================================================
df_view = df_ath.copy()
if not df_view.empty:
    if sel_event != "All Events":
        df_view = df_view[df_view[Config.COL_EVENT].astype(str) == sel_event]
    if search and search.strip():
        s = search.strip().lower()
        df_view = df_view[
            df_view[Config.COL_NAME].astype(str).str.lower().str.contains(s, na=False) |
            df_view[Config.COL_ID].astype(str).str.contains(s, na=False)
        ]
    if sort_by == "Fight Order":
        df_view["__fno__"] = pd.to_numeric(df_view[Config.COL_FIGHT_NO], errors="coerce").fillna(9999)
        df_view["__corner__"] = df_view[Config.COL_CORNER].astype(str).str.lower().map({"blue":0,"red":1}).fillna(2)
        df_view = df_view.sort_values(["__fno__", "__corner__", Config.COL_NAME], ascending=[True, True, True])
    else:
        df_view = df_view.sort_values(Config.COL_NAME, ascending=True)

# ==============================================================================
# UIs POR MODO
# ==============================================================================
def _whatsapp_tag(mobile: str) -> str:
    mob = _clean_str(mobile)
    if not mob:
        return ""
    digits = "".join(ch for ch in mob if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return ""
    return f"<a class='tag' href='https://wa.me/{html.escape(digits, True)}' target='_blank'>WhatsApp</a>"

def _fight_label(event, fno, corner) -> str:
    parts = []
    if event and event != Config.DEFAULT_EVENT_PLACEHOLDER:
        parts.append(html.escape(str(event)))
    if fno:
        parts.append(f"FIGHT {html.escape(str(fno))}")
    if corner:
        parts.append(html.escape(str(corner)).upper())
    return f"<span class='label-chip'>{' | '.join(parts)}</span>" if parts else ""

def render_card(row: pd.Series, button_label: str, on_click):
    name = _clean_str(row.get(Config.COL_NAME, "N/A"))
    aid  = _clean_str(row.get(Config.COL_ID, ""))
    evt  = _clean_str(row.get(Config.COL_EVENT, ""))
    img  = _clean_str(row.get(Config.COL_IMAGE, ""))
    mob  = _clean_str(row.get(Config.COL_MOBILE, ""))
    fno  = _clean_str(row.get(Config.COL_FIGHT_NO, ""))
    cor  = _clean_str(row.get(Config.COL_CORNER, ""))

    if not img:
        img = "https://via.placeholder.com/60?text=NA"

    label_html = _fight_label(evt, fno, cor)
    wa_html = _whatsapp_tag(mob)

    card_html = f"""
    <div class='card-container'>
      <img src='{html.escape(img, True)}' class='card-img'>
      <div class='card-info'>
        <div class='info-line'><span class='fighter-name'>{html.escape(name)} | {html.escape(aid)}</span></div>
        <div class='info-line'>{label_html}</div>
        <div class='info-line'>{wa_html}</div>
      </div>
    </div>
    """

    col_card, col_btn = st.columns([2.5, 1])
    with col_card:
        st.markdown(card_html, unsafe_allow_html=True)
    with col_btn:
        if st.button(button_label, use_container_width=True, key=f"btn_{button_label.replace(' ','_')}_{aid}"):
            on_click(aid, name, evt)

    st.divider()

# --- modo CHECK IN -------------------------------------------------------------
if mode == Config.STATUS_CHECKIN:
    if sel_event == "All Events":
        st.info("Selecione um evento para iniciar o Check in.")
    elif df_view.empty:
        st.info("Nenhum atleta encontrado com os filtros atuais.")
    else:
        def do_checkin(aid, fighter_name, event_name):
            # recarrega attendance (sem cache) para calcular ordem atualizada
            order = next_checkin_order_for_event(event_name)
            notes = f"{order}"  # somente o número
            ok = append_attendance_row(
                event=event_name, athlete_id=aid, fighter=fighter_name,
                task=Config.TASK_NAME, status=Config.STATUS_CHECKIN, notes=notes
            )
            if ok:
                st.success(f"Check in registrado para {fighter_name} (ordem {order}).", icon="✅")
                time.sleep(0.3)
                st.rerun()

        for _, r in df_view.iterrows():
            render_card(r, "Check in", do_checkin)

# --- modo CHECK OUT ------------------------------------------------------------
elif mode == Config.STATUS_CHECKOUT:
    if sel_event == "All Events":
        st.info("Selecione um evento para Check out.")
    elif df_view.empty:
        st.info("Nenhum atleta encontrado com os filtros atuais.")
    else:
        def do_checkout(aid, fighter_name, event_name):
            ok = append_attendance_row(
                event=event_name, athlete_id=aid, fighter=fighter_name,
                task=Config.TASK_NAME, status=Config.STATUS_CHECKOUT, notes=""
            )
            if ok:
                st.success(f"Check out registrado para {fighter_name}.", icon="✅")
                time.sleep(0.3)
                st.rerun()

        for _, r in df_view.iterrows():
            render_card(r, "Check out", do_checkout)

# --- modo RUNNING ORDER --------------------------------------------------------
else:  # "Running Order"
    if sel_event == "All Events":
        st.info("Selecione um evento para ver o Running Order.")
    else:
        df_ro = get_running_order(sel_event)
        if df_ro.empty:
            st.info("Nenhum check in registrado ainda para este evento.")
        else:
            st.markdown(f"**Running Order – {html.escape(sel_event)}**")
            st.dataframe(df_ro, use_container_width=True, hide_index=True)
