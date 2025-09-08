# ==============================================================================
# UAEW Operations App — Weigh-in Page
# ------------------------------------------------------------------------------
# Versão:        1.0.0
# Gerado em:     2025-09-08
# Autor:         Assistente (GPT)
#
# RESUMO
# - Página "Weigh-in" para controlar a chegada dos atletas (Check in / Check out)
#   e exibir a ordem (Running Order) por evento.
# - Cards no mesmo estilo de Blood Test / Photoshoot:
#     * Chips (evento | FIGHT # | CORNER) coloridos pelo corner (blue/red)
#     * Sem chip de Passport e sem chip de "último check"
#     * Atalho de WhatsApp (se houver celular)
# - Ao clicar "Check in":
#     * Grava na aba Attendance com:
#         Task   = "Weigh-in"
#         Status = "Check in"
#         Notes  = número sequencial da ordem no EVENTO selecionado
# - Ao clicar "Check out":
#     * Grava na aba Attendance com:
#         Task   = "Weigh-in"
#         Status = "Check out"
#         Notes  = "" (vazio)
# - Cards ficam VERDES para atletas que já têm "Check in" no evento selecionado.
# - "Running Order" lista (Notes numérico) na ordem ascendente para o evento.
#
# Observações:
# - Escrita na planilha é alinhada ao cabeçalho real (linha 1) para evitar
#   deslocamentos de coluna, usando apenas estes campos:
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

# --- Bootstrap (título/side bar/autenticação unificada) ---
bootstrap_page("Weigh-in")
st.title("Weigh-in")

# --- Projeto: helpers de planilha ---
from utils import get_gspread_client, connect_gsheet_tab


# ==============================================================================
# CONFIG / CONSTANTES
# ==============================================================================
class Config:
    # Planilhas / Abas
    MAIN_SHEET_NAME = "UAEW_App"
    ATHLETES_TAB_NAME = "df"
    ATTENDANCE_TAB_NAME = "Attendance"

    # Tarefa fixa desta página
    TASK_NAME = "Weigh-in"         # (exatamente assim)

    # Status usados
    STATUS_CHECKIN = "Check in"    # com espaço, capitalização normal
    STATUS_CHECKOUT = "Check out"  # com espaço, capitalização normal

    # Colunas do DF de atletas (snake_case)
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

    # Colunas da aba Attendance (exatamente como estão)
    ATT_COL_ROWID = "#"
    ATT_COL_EVENT = "Event"
    ATT_COL_ATHLETE_ID = "Athlete ID"
    ATT_COL_FIGHTER = "Fighter"
    ATT_COL_TASK = "Task"
    ATT_COL_STATUS = "Status"
    ATT_COL_USER = "User"
    ATT_COL_TIMESTAMP_ALT = "TimeStamp"   # onde gravamos a data/hora
    ATT_COL_NOTES = "Notes"

    # Cores e estilo
    CARD_BG_DEFAULT = "#1e1e1e"
    CARD_BG_CHECKED = "#145A32"  # verde escuro quando já tem Check in
    CORNER_COLOR = {"red": "#d9534f", "blue": "#428bca"}


# ==============================================================================
# HELPERS (strings, normalização, etc.)
# ==============================================================================
_INVALID_STRS = {"", "none", "None", "null", "NULL", "nan", "NaN", "<NA>"}

def clean_and_normalize(text: str) -> str:
    """Lowercase, sem acentos, e espaços colapsados."""
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
    """
    Lê a aba 'df', filtra '1 - Fighter' ativos e normaliza colunas usadas.
    """
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATHLETES_TAB_NAME)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return pd.DataFrame()

        # normaliza nomes das colunas
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

        # checks básicos
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

        # garante campos usados
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
    """
    Lê a aba 'Attendance'. Não infere schema — usa exatamente as colunas existentes.
    """
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
    Faz append de UMA linha na aba Attendance alinhando à ordem real do cabeçalho.
    Campos usados:
      "#", "Event", "Athlete ID", "Fighter", "Task", "Status", "User", "TimeStamp", "Notes"
    """
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, Config.MAIN_SHEET_NAME, Config.ATTENDANCE_TAB_NAME)

        # 1) Cabeçalho real
        header = ws.row_values(1)
        if not header:
            # cria um header mínimo se não houver
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
                # pega o último valor não vazio na coluna
                last_val = ""
                for v in reversed(col_vals[1:]):
                    vv = str(v).strip()
                    if vv:
                        last_val = vv
                        break
                next_num = str(int(last_val) + 1) if last_val.isdigit() else str(len(col_vals))

        # 3) Monta dict com os nomes do header
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

        # 4) Alinha na ordem do header real
        row_to_append = [row_map.get(col, "") for col in header]
        ws.append_row(row_to_append, value_input_option="USER_ENTERED")

        # limpa cache p/ refletir na tela
        load_attendance.clear()
        return True
    except Exception as e:
        st.error(f"Error writing Attendance: {e}", icon="🚨")
        return False


# ==============================================================================
# LÓGICA DE NEGÓCIO (ordem, check-in existentes, etc.)
# ==============================================================================
def get_checked_in_id_set(df_att: pd.DataFrame, event: str) -> set[str]:
    """Retorna o set de Athlete ID que já tem 'Weigh-in'/'Check in' no evento."""
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
    """
    Calcula o próximo número de ordem (Notes) para Check in no evento informado.
    Pega o maior Notes numérico existente (+1). Se não houver, retorna 1.
    """
    if df_att.empty:
        return 1
    df = df_att[
        (df.get("Event", "").astype(str) == str(event)) &
        (df.get("Task", "").astype(str).str.lower() == Config.TASK_NAME.lower()) &
        (df.get("Status", "").astype(str).str.lower() == Config.STATUS_CHECKIN.lower())
    ].copy()
    if df.empty:
        return 1
    # Notes pode vir string — tentamos converter
    notes_num = pd.to_numeric(df.get("Notes", pd.Series([], dtype=str)), errors="coerce")
    max_num = int(notes_num.dropna().max()) if notes_num.notna().any() else 0
    return max_num + 1 if max_num > 0 else (len(df) + 1)

def get_running_order(df_att: pd.DataFrame, event: str) -> pd.DataFrame:
    """Retorna DataFrame com (Order, Fighter, Athlete ID, Time) para o evento."""
    if df_att.empty:
        return pd.DataFrame(columns=["Order", "Fighter", "Athlete ID", "Time"])
    df = df_att[
        (df.get("Event", "").astype(str) == str(event)) &
        (df.get("Task", "").astype(str).str.lower() == Config.TASK_NAME.lower()) &
        (df.get("Status", "").astype(str).str.lower() == Config.STATUS_CHECKIN.lower())
    ].copy()
    if df.empty:
        return pd.DataFrame(columns=["Order", "Fighter", "Athlete ID", "Time"])
    df["Order"] = pd.to_numeric(df["Notes"], errors="coerce")
    df["Time"] = df.get("TimeStamp", "")
    df = df.dropna(subset=["Order"])
    return df[["Order", "Fighter", "Athlete ID", "Time"]].sort_values(by="Order", ascending=True).reset_index(drop=True)


# ==============================================================================
# UI (estilo dos cards e render)
# ==============================================================================
# CSS (mesmo estilo base dos outros cards; cor do fundo muda se já fez check in)
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
    """
    Renderiza um card de atleta com:
    - chip info (Event | FIGHT # | CORNER) com cor do corner
    - WhatsApp (se existir)
    - 1 botão de ação (Check in / Check out)
    - fundo verde se highlight=True (já fez Check in)
    """
    aid = str(row.get(Config.COL_ID, ""))
    name = str(row.get(Config.COL_NAME, ""))
    event = str(row.get(Config.COL_EVENT, ""))
    fight_n = str(row.get(Config.COL_FIGHT_NUMBER, ""))
    corner = str(row.get(Config.COL_CORNER, ""))
    img = str(row.get(Config.COL_IMAGE, "https://via.placeholder.com/60?text=NA"))
    mobile = str(row.get(Config.COL_MOBILE, "")).strip()

    # chip com cor do corner
    chip_color = _corner_color(corner)
    bits = []
    if event and event != Config.DEFAULT_EVENT_PLACEHOLDER:
        bits.append(html.escape(event))
    if fight_n:
        bits.append(f"FIGHT {html.escape(fight_n)}")
    if corner:
        bits.append(html.escape(corner.upper()))
    chip_html = ""
    if bits:
        chip_html = f"<span class='badge' style='background:{chip_color}'>{' | '.join(bits)}</span>"

    # WhatsApp (se tiver celular)
    wa_html = ""
    if mobile:
        phone_digits = "".join(filter(str.isdigit, mobile))
        if phone_digits.startswith("00"):
            phone_digits = phone_digits[2:]
        if phone_digits:
            wa_html = f"<a class='wa-chip' href='https://wa.me/{html.escape(phone_digits, True)}' target='_blank'>WhatsApp</a>"

    # Fundo do card
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
    # layout: card à esquerda, botão à direita (simetria com outras páginas)
    left, right = st.columns([2.5, 1])
    with left:
        st.markdown(card_html, unsafe_allow_html=True)
    with right:
        if st.button(btn_label, key=f"{btn_label.replace(' ','_').lower()}_{aid}", use_container_width=True):
            on_click(aid, name, event)
    st.divider()


# ==============================================================================
# EXPANDER (filtros + modo)
# ==============================================================================
# Estado inicial dos widgets
st.session_state.setdefault("weighin_event", "All Events")
st.session_state.setdefault("weighin_search", "")
st.session_state.setdefault("weighin_mode", "Check in")  # Check in | Check out | Running Order

with st.expander("Settings", expanded=True):
    # Segmentado: 3 opções
    st.session_state.weighin_mode = st.segmented_control(
        "Mode:",
        options=["Check in", "Check out", "Running Order"],
        key="weighin_mode",
    )

    # Carrega dados base para popular os filtros
    df_ath = load_athletes()
    events = ["All Events"]
    if not df_ath.empty:
        events += sorted([e for e in df_ath[Config.COL_EVENT].unique() if e and e != Config.DEFAULT_EVENT_PLACEHOLDER])

    st.session_state.weighin_event = st.selectbox(
        "Event:",
        options=events,
        index=events.index(st.session_state.weighin_event) if st.session_state.weighin_event in events else 0,
        key="weighin_event"
    )

    st.text_input("Search Athlete:", key="weighin_search", placeholder="Type name or ID...")


# ==============================================================================
# APLICA FILTROS E RENDERIZA
# ==============================================================================
df_ath = load_athletes()
if df_ath.empty:
    st.info("No athletes found.")
    st.stop()

# Filtro de evento
sel_event = st.session_state.weighin_event
if sel_event != "All Events":
    df_ath = df_ath[df_ath[Config.COL_EVENT] == sel_event]

# Busca
q = (st.session_state.weighin_search or "").strip().lower()
if q:
    df_ath = df_ath[
        df_ath[Config.COL_NAME].str.lower().str.contains(q, na=False) |
        df_ath[Config.COL_ID].astype(str).str.lower().str.contains(q, na=False)
    ]

# Ordenação padrão por nome; se quiser Fight Order, é fácil de incluir
df_ath = df_ath.sort_values(by=[Config.COL_NAME]).reset_index(drop=True)

# Attendance para status/ordem
df_att = load_attendance()
checked_in_ids = set()
if sel_event != "All Events":
    checked_in_ids = get_checked_in_id_set(df_att, sel_event)


# ==============================================================================
# HANDLERS (ações de clique)
# ==============================================================================
def on_check_in(aid: str, name: str, event: str):
    """Grava Weigh-in / Check in com Notes = ordem sequencial do evento."""
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
        # Atualiza estado local para pintar o card de verde
        checked_in_ids.add(str(aid))

def on_check_out(aid: str, name: str, event: str):
    """Grava Weigh-in / Check out (Notes vazio)."""
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
mode = st.session_state.weighin_mode

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
    # Render cards (com fundo verde se já fez Check in)
    for _, r in df_ath.iterrows():
        already_in = str(r.get(Config.COL_ID, "")) in checked_in_ids
        if mode == "Check in":
            render_card(r, "Check in", on_check_in, highlight=already_in)
        else:  # Check out
            render_card(r, "Check out", on_check_out, highlight=already_in)
