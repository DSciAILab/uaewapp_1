# ==============================================================================
# UAEW Operations App — Weigh-in Page
# ------------------------------------------------------------------------------
# Versão:        1.0.1
# Gerado em:     2025-09-08
# Autor:         Assistente (GPT)
#
# RESUMO
# - Página "Weigh-in" para controlar Check in / Check out e ver Running Order.
# - Cards no estilo das outras páginas (sem chip de Passport e sem “último check”).
# - Chips (Event | FIGHT # | CORNER) coloridos pelo corner (blue/red).
# - Botão único por modo:
#     * Check in -> grava na Attendance com Notes = ordem sequencial por evento.
#     * Check out -> grava na Attendance com Notes = "".
# - Card fica VERDE quando o atleta já tem Check in no evento selecionado.
# - Running Order lista por Notes (ordem) do evento selecionado.
# - Escrita na planilha alinha à ordem real do cabeçalho:
#   ["#", "Event", "Athlete ID", "Fighter", "Task", "Status", "User", "TimeStamp", "Notes"]
# ==============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import html
import unicodedata
import re

# --- Bootstrap ---
bootstrap_page("Weigh-in")
st.title("Weigh-in")

# --- Helpers de planilha ---
from utils import get_gspread_client, connect_gsheet_tab


# ==============================================================================
# CONFIG / CONSTANTES
# ==============================================================================
class Config:
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"

    TASK_NAME = "Weigh-in"          # nome exato da tarefa
    STATUS_CHECKIN = "Check in"     # com espaço
    STATUS_CHECKOUT = "Check out"   # com espaço

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

    # UI
    CARD_BG_DEFAULT = "#1e1e1e"
    CARD_BG_CHECKED = "#145A32"  # verde escuro
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

        # validações
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

        # garante colunas
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
    """
    Append de UMA linha na aba Attendance alinhando à ordem real do cabeçalho.
      Campos: "#", "Event", "Athlete ID", "Fighter",
              "Task", "Status", "User", "TimeStamp", "Notes"
    """
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB_NAME)

        # 1) Cabeçalho real
        header = ws.row_values(1)
        if not header:
            header = [
                Config.ATT_COL_ROWID, Config.ATT_COL_EVENT, Config.ATT_COL_ATHLETE_ID, Config.ATT_COL_FIGHTER,
                Config.ATT_COL_TASK, Config.ATT_COL_STATUS, Config.ATT_COL_USER, Config.ATT_COL_TIMESTAMP_ALT,
                Config.ATT_COL_NOTES
            ]
            ws.append_row(header, value_input_option="USER_ENTERED")

        # 2) Próximo "#"
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

        # 3) Monta dict
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

        # 4) Alinha na ordem do header
        row_to_append = [row_map.get(col, "") for col in header]
        ws.append_row(row_to_append, value_input_option="USER_ENTERED")

        # 5) Limpa cache
        load_attendance.clear()
        return True
    except Exception as e:
        st.error(f"Error writing Attendance: {e}", icon="🚨")
        return False


# ==============================================================================
# Lógica: status e ordem
# ==============================================================================
def get_checked_in_id_set(df_att: pd.DataFrame, event: str) -> set[str]:
    if df_att.empty:
        return set()
    df = df_att.copy()
    return set(
        df[
            (df.get("Event", "").astype(str) == str(event)) &
            (df.get("Task", "").astype(str).str.lower() == Config.TASK_NAME.lower()) &
            (df.get("Status", "").astype(str).str.lower() == Config.STATUS_CHECKIN.lower())
        ].get("Athlete ID", pd.Series([], dtype=str)).astype(str).tolist()
    )

def next_checkin_order(df_att: pd.DataFrame, event: str) -> int:
    if df_att.empty:
        return 1
    df = df_att[
        (df.get("Event", "").astype(str) == str(event)) &
        (df.get("Task", "").astype(str).str.lower() == Config.TASK_NAME.lower()) &
        (df.get("Status", "").astype(str).str.lower() == Config.STATUS_CHECKIN.lower())
    ].copy()
    if df.empty:
        return 1
    notes_num = pd.to_numeric(df.get("Notes", pd.Series([], dtype=str)), errors="coerce")
    max_num = int(notes_num.dropna().max()) if notes_num.notna().any() else 0
    return max_num + 1 if max_num > 0 else (len(df) + 1)

def get_running_order(df_att: pd.DataFrame, event: str) -> pd.DataFrame:
    if df_att.empty:
        return pd.DataFrame(columns=["Order", "Fighter", "Athlete ID", "Time"])
    df = df_att[
        (df.get("Event", "").astype(str) == str(event)) &
        (df.get("Task", "").astype(str).str.lower() == Config.TASK_NAME.lower()) &
        (df.get("Status", "").astype(str).str.lower() == Config.STATUS_CHECKIN.lower())
    ].copy()
    if df.empty:
        return pd.DataFrame(columns=["Order", "Fighter", "Athlete ID", "Time"])
    df["Order"] = pd.to_numeric(df.get("Notes"), errors="coerce")
    df["Time"] = df.get("TimeStamp", "")
    df = df.dropna(subset=["Order"])
    return df[["Order", "Fighter", "Athlete ID", "Time"]].sort_values(by="Order", ascending=True).reset_index(drop=True)


# ==============================================================================
# UI — estilos e render dos cards
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
  .wa-chip {
      background-color: #25D366; color: #fff; padding: 3px 10px;
      border-radius: 8px; font-size: .8rem; font-weight: 700; text-decoration: none;
  }
  .badge {
      color: #fff; padding: 3px 10px; border-radius: 8px; font-size: .8rem; font-weight: 700;
      display: inline-flex; align-items: center; gap: 6px;
  }
</style>
""", unsafe_allow_html=True)

def _corner_color(corner: str) -> str:
    return Config.CORNER_COLOR.get((corner or "").strip().lower(), "#4A4A4A")

def render_card(row: pd.Series, btn_label: str, on_click, highlight: bool):
    aid = str(row.get(Config.COL_ID, ""))
    name = str(row.get(Config.COL_NAME, ""))
    event = str(row.get(Config.COL_EVENT, ""))
    fight_n = str(row.get(Config.COL_FIGHT_NUMBER, ""))
    corner = str(row.get(Config.COL_CORNER, ""))
    img = str(row.get(Config.COL_IMAGE, "https://via.placeholder.com/60?text=NA"))
    mobile = str(row.get(Config.COL_MOBILE, "")).strip()

    chip_color = _corner_color(corner)
    bits = []
    if event and event != Config.DEFAULT_EVENT_PLACEHOLDER:
        bits.append(html.escape(event))
    if fight_n:
        bits.append(f"FIGHT {html.escape(fight_n)}")
    if corner:
        bits.append(html.escape(corner.upper()))
    chip_html = f"<span class='badge' style='background:{chip_color}'>{' | '.join(bits)}</span>" if bits else ""

    wa_html = ""
    if mobile:
        phone_digits = "".join(filter(str.isdigit, mobile))
        if phone_digits.startswith("00"):
            phone_digits = phone_digits[2:]
        if phone_digits:
            wa_html = f"<a class='wa-chip' href='https://wa.me/{html.escape(phone_digits, True)}' target='_blank'>WhatsApp</a>"

    bg = Config.CARD_BG_CHECKED if highlight else Config.CARD_BG_DEFAULT
    card_html = f"""
    <div class='card-container' style='background-color:{bg};'>
      <img src='{html.escape(img, True)}' class='card-img'>
      <div class='card-info'>
        <div class='info-line'><span class='fighter-name'>{html.escape(name)} | {html.escape(aid)}</span></div>
        <div class='info-line'>{chip_html}</div>
        <div class='info-line'>{wa_html}</div>
      </div>
    </div>
    """
    left, right = st.columns([2.5, 1])
    with left:
        st.markdown(card_html, unsafe_allow_html=True)
    with right:
        if st.button(btn_label, key=f"{btn_label.replace(' ','_').lower()}_{aid}", use_container_width=True):
            on_click(aid, name, event)
    st.divider()


# ==============================================================================
# EXPANDER (filtros + modo) — sem atribuir valores a session_state dentro do widget
# ==============================================================================
# Defaults
st.session_state.setdefault("weighin_mode", "Check in")
st.session_state.setdefault("weighin_event", "All Events")
st.session_state.setdefault("weighin_search", "")

with st.expander("Settings", expanded=True):
    st.segmented_control(
        "Mode:",
        options=["Check in", "Check out", "Running Order"],
        key="weighin_mode",
    )

    df_ath_all = load_athletes()
    events = ["All Events"]
    if not df_ath_all.empty:
        events += sorted([e for e in df_ath_all[Config.COL_EVENT].unique() if e and e != Config.DEFAULT_EVENT_PLACEHOLDER])

    # NÃO atribua o retorno do widget à session_state; passe key e pronto.
    st.selectbox(
        "Event:",
        options=events,
        index=events.index(st.session_state["weighin_event"]) if st.session_state["weighin_event"] in events else 0,
        key="weighin_event"
    )

    st.text_input("Search Athlete:", key="weighin_search", placeholder="Type name or ID...")

# Lê os valores (agora, sim):
mode = st.session_state["weighin_mode"]
sel_event = st.session_state["weighin_event"]
search_q = (st.session_state["weighin_search"] or "").strip().lower()


# ==============================================================================
# APLICA FILTROS E RENDERIZA
# ==============================================================================
df_ath = df_ath_all.copy()
if df_ath.empty:
    st.info("No athletes found.")
    st.stop()

if sel_event != "All Events":
    df_ath = df_ath[df_ath[Config.COL_EVENT] == sel_event]

if search_q:
    df_ath = df_ath[
        df_ath[Config.COL_NAME].str.lower().str.contains(search_q, na=False) |
        df_ath[Config.COL_ID].astype(str).str.lower().str.contains(search_q, na=False)
    ]

df_ath = df_ath.sort_values(by=[Config.COL_NAME]).reset_index(drop=True)

df_att = load_attendance()
checked_in_ids = set()
if sel_event != "All Events":
    checked_in_ids = get_checked_in_id_set(df_att, sel_event)


# ==============================================================================
# HANDLERS
# ==============================================================================
def on_check_in(aid: str, name: str, event: str):
    if not event or event == Config.DEFAULT_EVENT_PLACEHOLDER:
        st.warning("Select a valid event to check in.", icon="⚠️")
        return
    order_num = next_checkin_order(load_attendance(), event)
    ok = append_attendance_row(
        event=event,
        athlete_id=aid,
        fighter=name,
        status=Config.STATUS_CHECKIN,
        notes=order_num
    )
    if ok:
        st.toast(f"Check in registrado (ordem {order_num}).", icon="✅")
        # pinta o card de verde localmente
        checked_in_ids.add(str(aid))

def on_check_out(aid: str, name: str, event: str):
    if not event or event == Config.DEFAULT_EVENT_PLACEHOLDER:
        st.warning("Select a valid event to check out.", icon="⚠️")
        return
    ok = append_attendance_row(
        event=event,
        athlete_id=aid,
        fighter=name,
        status=Config.STATUS_CHECKOUT,
        notes=""
    )
    if ok:
        st.toast("Check out registrado.", icon="✅")


# ==============================================================================
# RENDER POR MODO
# ==============================================================================
if mode == "Running Order":
    if sel_event == "All Events":
        st.info("Select an Event to see the Running Order.")
    else:
        df_order = get_running_order(load_attendance(), sel_event)
        if df_order.empty:
            st.info("No check-ins yet for this event.")
        else:
            st.dataframe(df_order, use_container_width=True, hide_index=True)
else:
    for _, r in df_ath.iterrows():
        already_in = str(r.get(Config.COL_ID, "")) in checked_in_ids
        if mode == "Check in":
            render_card(r, "Check in", on_check_in, highlight=already_in)
        else:  # Check out
            render_card(r, "Check out", on_check_out, highlight=already_in)
