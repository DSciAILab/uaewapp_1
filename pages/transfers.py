# pages/transfers.py
# =============================================================================
# Transfers (Arrival / Departure)
# -----------------------------------------------------------------------------
# - Segmented dentro do expander: Arrival | Departure
# - Ordenação: Guest | Car | Date & Time
# - "Time" exibido sempre em HH:MM (corrige 30/12/1899, 2300, 0,75 etc.)
# - Mantém a estrutura/cards que você aprovou
# =============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import datetime as dt
import re

# --- Bootstrap ---
bootstrap_page("Transfers")
st.title("Transfers")

# --- Project Imports ---
from utils import get_gspread_client, connect_gsheet_tab

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App"
DATA_TAB_NAME = "df"

ARR_FIELDS = dict(
    flight="ArrivalFlight",
    date="ArrivalDate",
    time="ArrivalTime",
    airport="ArrivalAirport",
    status="transfer_arrival_status",
    car="transfer_arrival_car",
    driver="transfer_arrival_driver",
    pickup="transfer_arrival_pickup",  # se existir
)
DEP_FIELDS = dict(
    flight="DepartureFlight",
    date="DepartureDate",
    time="DepartureTime",
    airport="DepartureAirport",
    status="transfer_departure_status",
    car="transfer_departure_car",
    driver="transfer_departure_driver",
    pickup="transfer_departure_pickup",
)

BASE_DISPLAY_COLS = [
    'INACTIVE', 'ID', 'ROLE', 'CORNER', 'NAME'
]

# =============================================================================
# Utils
# =============================================================================

def _fmt_hhmm(val) -> str:
    """
    Converte vários formatos para 'HH:MM'.

    Aceita:
      - strings: '13:45', '13:45:00', '1:45 PM', '07h05', '07.05', '2300'
      - números seriais (Sheets/Excel): 0.5 (=12:00), 0.31597... (=07:35)
      - números com vírgula: '0,75' (=18:00)
      - datetimes com data-base '30/12/1899 23:00' (pega só HH:MM)
      - se vier só '30/12/1899' (data base sem hora) -> vazio
    """
    if val is None:
        return ""
    s = str(val).strip()
    if s == "":
        return ""

    # data-base pura (sem hora)
    if re.fullmatch(r"\s*30[/-]12[/-]1899\s*$", s):
        return ""

    # números com vírgula
    s_num = s.replace(",", ".")
    # serial numérico (float/str float/int)
    try:
        if re.fullmatch(r"[-+]?\d+(\.\d+)?", s_num):
            x = float(s_num)
            frac = x % 1  # fração do dia
            total_minutes = int(round(frac * 24 * 60))
            hh = (total_minutes // 60) % 24
            mm = total_minutes % 60
            # Se x é inteiro (>=1) e sem fração -> não há hora
            if x >= 1 and frac == 0:
                return ""
            return f"{hh:02d}:{mm:02d}"
    except Exception:
        pass

    # "2300" -> 23:00
    if re.fullmatch(r"\d{4}", s):
        hh = int(s[:2]); mm = int(s[2:])
        if 0 <= hh < 24 and 0 <= mm < 60:
            return f"{hh:02d}:{mm:02d}"

    # "HH:MM", "HH.MM", "HHhMM"
    m = re.match(r'^\s*(\d{1,2})[:h\.](\d{1,2})', s, re.IGNORECASE)
    if m:
        hh = int(m.group(1)); mm = int(m.group(2))
        if 0 <= hh < 24 and 0 <= mm < 60:
            return f"{hh:02d}:{mm:02d}"

    # AM/PM e datetimes (inclui '30/12/1899 23:00')
    try:
        dt_val = pd.to_datetime(s, dayfirst=True, errors="raise")
        if pd.notna(dt_val):
            if dt_val.year == 1899 and dt_val.month == 12 and dt_val.day == 30:
                return f"{dt_val.hour:02d}:{dt_val.minute:02d}" if (dt_val.hour or dt_val.minute) else ""
            return f"{dt_val.hour:02d}:{dt_val.minute:02d}" if (dt_val.hour or dt_val.minute) else ""
    except Exception:
        pass

    return ""

def _norm_status(x: str) -> str:
    s = ("" if x is None else str(x)).strip().upper()
    return "CANCELED" if s in ("CANCELLED", "CANCELED") else s

def highlight_today(row, date_col: str):
    try:
        today = dt.datetime.now().strftime('%d/%m')
        if date_col in row and str(row[date_col]) == today:
            return ['background-color: #ffe066'] * len(row)
    except Exception:
        pass
    return [''] * len(row)

# =============================================================================
# Data
# =============================================================================

@st.cache_data(ttl=600)
def load_transfers(sheet_name: str = MAIN_SHEET_NAME, data_tab_name: str = DATA_TAB_NAME) -> pd.DataFrame:
    try:
        gc = get_gspread_client()
        ws = connect_gsheet_tab(gc, sheet_name, data_tab_name)
        data = ws.get_all_records()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Error loading transfer data: {e}", icon="🚨")
        return pd.DataFrame()

with st.spinner("Loading data..."):
    df_raw = load_transfers()

# Filtro INACTIVE
if 'INACTIVE' in df_raw.columns:
    df_raw = df_raw[df_raw['INACTIVE'].isin([False, "FALSE", "false", "False", 0, "0"])].copy()

# =============================================================================
# Settings (expander)
# =============================================================================
with st.expander("Settings", expanded=True):
    # Arrival | Departure
    st.session_state["arrdep_mode"] = st.segmented_control(
        "Mode:",
        options=["Arrival", "Departure"],
        key="arrdep_mode",
        default="Arrival"
    )

    # Ordenação
    st.session_state["order_by"] = st.segmented_control(
        "Order by:",
        options=["Guest", "Car", "Date & Time"],
        key="order_by",
        default="Date & Time"
    )

    # Cards vs Table + filtro de Resident
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        modo_cards = st.toggle("View as cards", value=True, key="view_as_cards")
    with col_t2:
        hide_resident = st.toggle(
            "Hide airport: Resident (cards only)",
            value=False,
            key="hide_resident_cards"
        )

    # Busca
    search = st.text_input("Search in any column:")

mode = st.session_state.get("arrdep_mode", "Arrival")
FIELDS = ARR_FIELDS if mode == "Arrival" else DEP_FIELDS

# Mantém apenas colunas relevantes que existirem
display_cols = BASE_DISPLAY_COLS + [FIELDS[k] for k in FIELDS if FIELDS[k] in df_raw.columns]
existing_cols = [c for c in display_cols if c in df_raw.columns]
df = df_raw[existing_cols].copy()

# NAME é essencial
if 'NAME' not in df.columns:
    st.error("The 'NAME' column is essential and was not found.")
    st.stop()

# Normaliza Status
if FIELDS["status"] in df.columns:
    df[FIELDS["status"]] = df[FIELDS["status"]].apply(_norm_status)

# Busca geral
if search:
    mask = pd.Series(False, index=df.index)
    for col in df.columns:
        mask = mask | df[col].astype(str).str.contains(search, case=False, na=False)
    df = df[mask]

# Ordenação
def _build_sort_keys(df: pd.DataFrame):
    # DateTime parse seguro (Date & Time)
    dt_col = None
    if FIELDS["date"] in df.columns and FIELDS["time"] in df.columns:
        # cria HH:MM a partir de "time"
        hhmm = df[FIELDS["time"]].apply(_fmt_hhmm)
        # concatena com ano corrente para ordenar
        cur_year = dt.datetime.now().year
        dt_str = df[FIELDS["date"]].astype(str).str.strip() + f"/{cur_year} " + hhmm
        dt_parsed = pd.to_datetime(dt_str, format="%d/%m/%Y %H:%M", errors="coerce")
        dt_col = dt_parsed
    return hhmm if 'hhmm' in locals() else pd.Series([""]*len(df), index=df.index), dt_col

hhmm_series, dt_series = _build_sort_keys(df)

order_by = st.session_state.get("order_by", "Date & Time")
if order_by == "Guest":
    df = df.sort_values(by=['NAME'])
elif order_by == "Car" and FIELDS["car"] in df.columns:
    df = df.sort_values(by=[FIELDS["car"], 'NAME'])
else:
    # Date & Time
    if dt_series is not None:
        df = df.assign(__dt__=dt_series).sort_values(by=['__dt__','NAME'], na_position='last').drop(columns=['__dt__'])
    else:
        df = df.sort_values(by=['NAME'])

# =============================================================================
# Métricas
# =============================================================================
def norm_status_series(s):
    s = s.astype(str).str.strip().str.upper().replace({"CANCELLED":"CANCELED"})
    return s

status_series = norm_status_series(df.get(FIELDS["status"], pd.Series(dtype=str)))
total_all = len(df)
planned_count  = (status_series == "PLANNED").sum()
done_count     = (status_series == "DONE").sum()
canceled_count = (status_series == "CANCELED").sum()
noshow_count   = (status_series == "NO SHOW").sum()

summary_html = f'''
<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0;">
    <span style="font-weight:bold;">Showing {total_all} {mode.lower()}s</span>
    <span style="background-color:#ffe066;color:#23272f;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Planned: {planned_count}</span>
    <span style="background-color:#27ae60;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Done: {done_count}</span>
    <span style="background-color:#e74c3c;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Canceled: {canceled_count}</span>
    <span style="background-color:#95a5a6;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">No Show: {noshow_count}</span>
</div>'''
st.markdown(summary_html, unsafe_allow_html=True)

# =============================================================================
# Render
# =============================================================================
if df.empty:
    st.info(f"No {mode.lower()} records found with a filled name.")
    st.stop()

# Cores para o chip do corner
corner_colors = {
    "RED": "#e74c3c",
    "BLUE": "#3498db",
    "GREEN": "#27ae60",
    "YELLOW": "#f1c40f",
    "BLACK": "#23272f",
    "WHITE": "#f8f9fa"
}

if st.session_state.get("view_as_cards", True):
    # Hide Resident (cards only)
    data_cards = df.copy()
    if st.session_state.get("hide_resident_cards", False) and FIELDS["airport"] in data_cards.columns:
        data_cards = data_cards[~data_cards[FIELDS["airport"]].astype(str).str.strip().str.lower().eq('resident')]

    groups = data_cards.groupby(FIELDS["date"]) if FIELDS["date"] in data_cards.columns else [(None, data_cards)]

    for dval, group in groups:
        st.subheader(f"{mode}s on {dval} ({len(group)})")

        for _, row in group.iterrows():
            # Base colors
            card_color, text_color = "#23272f", "#f8f9fa"

            # Laranja se dentro da janela (±3h / -30min) — só quando temos datetime válido
            now = dt.datetime.now()
            hhmm = _fmt_hhmm(row.get(FIELDS["time"]))
            arrival_dt = None
            try:
                if row.get(FIELDS["date"]) and hhmm:
                    arrival_dt = dt.datetime.strptime(f"{row[FIELDS['date']]}/{now.year} {hhmm}", "%d/%m/%Y %H:%M")
            except Exception:
                pass
            if arrival_dt:
                diff = arrival_dt - now
                if dt.timedelta(minutes=-30) <= diff <= dt.timedelta(hours=3):
                    card_color, text_color = "#FF8C00", "#f8f9fa"

            corner = str(row.get('CORNER', '')).upper()
            corner_label_color = corner_colors.get(corner, "#888")

            # status chip
            raw_status = str(row.get(FIELDS["status"], "")).strip().upper()
            status = "CANCELED" if raw_status in ("CANCELLED", "CANCELED") else raw_status

            if status == "PLANNED":
                status_label = '<span style="background-color:#ffe066;color:#23272f;padding:2px 8px;border-radius:8px;font-weight:bold;">Planned</span>'
            elif status == "DONE":
                status_label = '<span style="background-color:#27ae60;color:#fff;padding:2px 8px;border-radius:8px;font-weight:bold;">Done</span>'
            elif status == "CANCELED":
                status_label = '<span style="background-color:#e74c3c;color:#fff;padding:2px 8px;border-radius:8px;font-weight:bold;">Canceled</span>'
            elif status == "NO SHOW":
                status_label = '<span style="background-color:#95a5a6;color:#fff;padding:2px 8px;border-radius:8px;font-weight:bold;">No Show</span>'
            else:
                safe = str(row.get(FIELDS["status"], ""))
                status_label = f'<span style="background-color:#888;color:#fff;padding:2px 8px;border-radius:8px;">{safe}</span>'

            car_val = str(row.get(FIELDS["car"], "")).strip()
            driver_val = str(row.get(FIELDS["driver"], "")).strip()
            pickup_val = str(row.get(FIELDS["pickup"], "")).strip()

            # Time sempre HH:MM
            hhmm = _fmt_hhmm(row.get(FIELDS["time"]))

            # Linha de car/driver/status/pickup
            addons = []
            if car_val:
                addons.append(f"<span><strong>Car:</strong> {car_val}</span>")
            if driver_val:
                addons.append(f"<span><strong>Driver:</strong> {driver_val}</span>")
            if pickup_val:
                addons.append(f"<span><strong>Pickup:</strong> {pickup_val}</span>")
            addons.append(status_label)
            line_html = '<div style="display:flex;gap:18px;align-items:center;">' + "  ".join(addons) + "</div>"

            st.markdown(
                f"""
                <div style="background-color:{card_color};border-radius:12px;padding:16px;margin-bottom:12px;color:{text_color};box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                    <div style="display:flex;align-items:center;margin-bottom:8px;">
                        <span style="font-size:20px;font-weight:bold;">{row.get('NAME','')}</span>
                        <span style="background-color:{corner_label_color};color:#fff;font-size:14px;font-weight:bold;border-radius:8px;padding:2px 10px;margin-left:12px;">{corner}</span>
                    </div>
                    <div style="display:flex;gap:18px;margin-bottom:8px;">
                        <span><strong>Flight:</strong> {row.get(FIELDS['flight'],'')}</span>
                        <span><strong>Time:</strong> {hhmm}</span>
                        <span><strong>Airport:</strong> {row.get(FIELDS['airport'],'')}</span>
                    </div>
                    {line_html}
                </div>
                """,
                unsafe_allow_html=True
            )
else:
    # Tabela
    df_table = df.copy()
    # substitui Time por HH:MM
    if FIELDS["time"] in df_table.columns:
        df_table[FIELDS["time"]] = df_table[FIELDS["time"]].apply(_fmt_hhmm)

    # remove driver na visão tabela (para enxugar) — ajuste só se existir
    drop_cols = []
    if FIELDS["driver"] in df_table.columns:
        drop_cols.append(FIELDS["driver"])
    if drop_cols:
        df_table = df_table.drop(columns=drop_cols)

    # ordena por DateTime se possível
    cur_year = dt.datetime.now().year
    if FIELDS["date"] in df_table.columns and FIELDS["time"] in df_table.columns:
        aux_dt = pd.to_datetime(
            df_table[FIELDS["date"]].astype(str) + f'/{cur_year} ' + df_table[FIELDS["time"]].astype(str),
            format='%d/%m/%Y %H:%M',
            errors='coerce'
        )
        df_table = df_table.assign(__dt__=aux_dt).sort_values(by='__dt__', na_position='last').drop(columns='__dt__')

    styled = df_table.style.apply(lambda r: highlight_today(r, FIELDS["date"]), axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)
