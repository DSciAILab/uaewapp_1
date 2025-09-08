# ==============================================================================
# UAEW Operations App — Weigh-in Page
# ------------------------------------------------------------------------------
# Versão:        1.3.0
# Atualizado:    2025-09-08
#
# RESUMO
# - Check in / Check out e Running Order com layout de 2 colunas (FHD).
# - Running Order: esquerda = Check in (verde) com número; direita = Check out (cinza).
# - Chips (Event | FIGHT # | CORNER) coloridos pelo corner.
# - Ao fazer Check in: grava Notes com ordem sequencial do evento.
# - Após qualquer clique (Check in/Check out): st.rerun().
# ==============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import html
import unicodedata

# --- Bootstrap ---
bootstrap_page("Weigh-in")

# --- Helpers de planilha ---
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
    ATT_COL_TIMESTAMP_ALT = "TimeStamp"   # onde gravamos
    ATT_COL_NOTES = "Notes"

    # UI cores
    CARD_BG_DEFAULT    = "#1e1e1e"
    CARD_BG_CHECKED    = "#145A32"  # verde
    CARD_BG_CHECKEDOUT = "#555555"  # cinza
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
    """Garante uma Series do tamanho do DF, mesmo se a coluna não existir."""
    if df is None or df.empty:
        return pd.Series([], dtype=object)
    if name in df.columns:
        return df[name]
    return pd.Series([""] * len(df), index=df.index, dtype=object)


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

        # 5) Limpa cache para releitura imediata
        load_attendance.clear()
        return True
    except Exception as e:
        st.error(f"Error writing Attendance: {e}", icon="🚨")
        return False


# ==============================================================================
# Lógica: status, ordem e utilitários para Running Order
# ==============================================================================
def next_checkin_order(df_att: pd.DataFrame, event: str) -> int:
    if df_att is None or df_att.empty:
        return 1
    ev = _col(df_att, "Event").astype(str)
    task = _col(df_att, "Task").astype(str).str.lower()
    status = _col(df_att, "Status").astype(str).str.lower()
    notes = _col(df_att, "Notes")

    mask = (
        (ev == str(event)) &
        (task == Config.TASK_NAME.lower()) &
        (status == Config.STATUS_CHECKIN.lower())
    )
    df = df_att[mask].copy()
    if df.empty:
        return 1

    notes_num = pd.to_numeric(notes[mask], errors="coerce")
    if notes_num.notna().any():
        return int(notes_num.max()) + 1
    return len(df) + 1

def latest_status_map(df_att: pd.DataFrame, event: str) -> dict[str, str]:
    """{athlete_id(str) -> ultimo_status_lower} para o EVENTO (apenas tarefa Weigh-in)."""
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
    """
    Retorna {athlete_id -> ordem (Notes)} do ÚLTIMO registro de Check in no evento.
    """
    out: dict[str, int] = {}
    if df_att is None or df_att.empty:
        return out
    ev = _col(df_att, "Event").astype(str)
    task = _col(df_att, "Task").astype(str).str.lower()
    status = _col(df_att, "Status").astype(str).str.lower()
    notes = _col(df_att, "Notes")
    ts = _col(df_att, "TimeStamp")
    aid = _col(df_att, "Athlete ID").astype(str)

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
# UI — estilos e render dos cards
# ==============================================================================
st.markdown("""
<style>
  .card-container { padding: 15px; border-radius: 10px; margin-bottom: 10px;
      display: grid; grid-template-columns: 64px 64px 1fr; gap: 12px; align-items: center; }
  .order-pill { display:flex; align-items:center; justify-content:center;
      width: 64px; height: 64px; border-radius: 12px; background:#0b2840; color:#fff;
      font-weight: 900; font-size: 1.25rem; }
  .card-img { width: 64px; height: 64px; border-radius: 50%; object-fit: cover; }
  .card-info { display: flex; flex-direction: column; gap: 6px; }
  .info-line { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
  .fighter-name { font-size: 1.15rem; font-weight: 800; margin: 0; color: white; }
  .badge { color:#fff; padding:3px 10px; border-radius:8px; font-size:.8rem; font-weight:700; display:inline-flex; }
  .wa-chip { background:#25D366; color:#fff; padding:3px 10px; border-radius:8px; font-weight:700; text-decoration:none; }
</style>
""", unsafe_allow_html=True)

def _corner_color(corner: str) -> str:
    return Config.CORNER_COLOR.get((corner or "").strip().lower(), "#4A4A4A")

def render_card_action(row: pd.Series, btn_label: str, on_click, bg_color: str):
    """Card com botão (usado em Check in / Check out)."""
    aid = str(row.get(Config.COL_ID, ""))
    name = str(row.get(Config.COL_NAME, ""))
    event = str(row.get(Config.COL_EVENT, ""))
    fight_n = str(row.get(Config.COL_FIGHT_NUMBER, ""))
    corner = str(row.get(Config.COL_CORNER, ""))
    img = str(row.get(Config.COL_IMAGE, "https://via.placeholder.com/64?text=NA"))
    mobile = str(row.get(Config.COL_MOBILE, "")).strip()

    chip_color = _corner_color(corner)
    bits = []
    if event and event != Config.DEFAULT_EVENT_PLACEHOLDER: bits.append(html.escape(event))
    if fight_n: bits.append(f"FIGHT {html.escape(fight_n)}")
    if corner:  bits.append(html.escape(corner.upper()))
    chip_html = f"<span class='badge' style='background:{chip_color}'>{' | '.join(bits)}</span>" if bits else ""

    wa_html = ""
    if mobile:
        phone_digits = "".join(filter(str.isdigit, mobile))
        if phone_digits.startswith("00"): phone_digits = phone_digits[2:]
        if phone_digits: wa_html = f"<a class='wa-chip' href='https://wa.me/{html.escape(phone_digits, True)}' target='_blank'>WhatsApp</a>"

    # grid de 2 colunas: card + botão
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
                <div class='info-line'>{wa_html}</div>
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
    """Card do Running Order com número à esquerda (sem botões)."""
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


# ==============================================================================
# EXPANDER (modo e filtros)
# ==============================================================================
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

    # Esconde Event/Search quando Running Order
    if st.session_state["weighin_mode"] != "Running Order":
        st.selectbox(
            "Event:",
            options=events,
            index=events.index(st.session_state["weighin_event"]) if st.session_state["weighin_event"] in events else 0,
            key="weighin_event"
        )
        st.text_input("Search Athlete:", key="weighin_search", placeholder="Type name or ID...")

# Valores
mode = st.session_state["weighin_mode"]
sel_event = st.session_state["weighin_event"]
search_q = (st.session_state["weighin_search"] or "").strip().lower()

# Título da página (evento | Weigh-in)
if sel_event != "All Events":
    st.title(f"{sel_event} | Weigh-in")
else:
    st.title("Weigh-in")

# Base atletas
df_ath = df_ath_all.copy()
if df_ath.empty:
    st.info("No athletes found.")
    st.stop()

# Filtros (não aplicados no Running Order para exibir todos do evento)
if sel_event != "All Events":
    df_ath = df_ath[df_ath[Config.COL_EVENT] == sel_event]

if mode != "Running Order" and search_q:
    df_ath = df_ath[
        df_ath[Config.COL_NAME].str.lower().str.contains(search_q, na=False) |
        df_ath[Config.COL_ID].astype(str).str.lower().str.contains(search_q, na=False)
    ]

df_ath = df_ath.sort_values(by=[Config.COL_NAME]).reset_index(drop=True)
df_att = load_attendance()

# Mapas/ordens para o evento
last_status = {}
order_by_id = {}
if sel_event != "All Events":
    last_status = latest_status_map(df_att, sel_event)            # {id -> 'check in'/'check out'}
    order_by_id = last_checkin_order_by_id(df_att, sel_event)     # {id -> order number}

checked_in_now  = {aid for aid, s in last_status.items() if s == Config.STATUS_CHECKIN.lower()}
checked_out_now = {aid for aid, s in last_status.items() if s == Config.STATUS_CHECKOUT.lower()}


# ==============================================================================
# HANDLERS (com rerun)
# ==============================================================================
def on_check_in(aid: str, name: str, event: str):
    if not event or event == Config.DEFAULT_EVENT_PLACEHOLDER:
        st.warning("Select a valid event to check in.", icon="⚠️")
        return
    order_num = next_checkin_order(load_attendance(), event)
    ok = append_attendance_row(event=event, athlete_id=aid, fighter=name,
                               status=Config.STATUS_CHECKIN, notes=order_num)
    if ok:
        st.toast(f"Check in registrado (ordem {order_num}).", icon="✅")
        st.rerun()

def on_check_out(aid: str, name: str, event: str):
    if not event or event == Config.DEFAULT_EVENT_PLACEHOLDER:
        st.warning("Select a valid event to check out.", icon="⚠️")
        return
    # Só permite check out de quem está com último status = check in
    if sel_event != "All Events" and aid not in checked_in_now:
        st.warning("Only athletes currently checked in can be checked out.", icon="⚠️")
        return
    ok = append_attendance_row(event=event, athlete_id=aid, fighter=name,
                               status=Config.STATUS_CHECKOUT, notes="")
    if ok:
        st.toast("Check out registrado.", icon="✅")
        st.rerun()


# ==============================================================================
# RENDER POR MODO
# ==============================================================================
if mode == "Running Order":
    if sel_event == "All Events":
        st.info("Select an Event in another mode first, then switch to Running Order.")
    else:
        # Conjuntos
        left_ids  = [aid for aid in checked_in_now]            # em fila
        right_ids = [aid for aid in checked_out_now]           # já saiu

        # Dataframes correspondentes
        left_df  = df_ath[df_ath[Config.COL_ID].astype(str).isin(left_ids)].copy()
        right_df = df_ath[df_ath[Config.COL_ID].astype(str).isin(right_ids)].copy()

        # Ordena a esquerda pela ordem (Notes)
        left_df["__ord__"] = left_df[Config.COL_ID].astype(str).map(order_by_id).fillna(1e9).astype(float)
        left_df = left_df.sort_values(by="__ord__", ascending=True)

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Checked in")
            if left_df.empty:
                st.info("No check-ins yet.")
            else:
                for _, r in left_df.iterrows():
                    order_num = order_by_id.get(str(r.get(Config.COL_ID, "")))
                    render_board_card(r, order_num, bg_color=Config.CARD_BG_CHECKED)

        with col_right:
            st.subheader("Checked out")
            if right_df.empty:
                st.info("No check-outs yet.")
            else:
                for _, r in right_df.iterrows():
                    render_board_card(r, order_num=None, bg_color=Config.CARD_BG_CHECKEDOUT)

else:
    # Se for Check out, mostrar somente quem está checked in
    if mode == "Check out" and sel_event != "All Events":
        df_ath = df_ath[df_ath[Config.COL_ID].astype(str).isin(checked_in_now)].copy()

    for _, r in df_ath.iterrows():
        aid = str(r.get(Config.COL_ID, ""))
        # cor do card conforme último status (se evento selecionado)
        if sel_event != "All Events":
            if aid in checked_in_now:
                bg = Config.CARD_BG_CHECKED
            elif aid in checked_out_now:
                bg = Config.CARD_BG_CHECKEDOUT
            else:
                bg = Config.CARD_BG_DEFAULT
        else:
            bg = Config.CARD_BG_DEFAULT

        if mode == "Check in":
            render_card_action(r, "Check in", on_check_in, bg_color=bg)
        else:  # Check out
            render_card_action(r, "Check out", on_check_out, bg_color=bg)
