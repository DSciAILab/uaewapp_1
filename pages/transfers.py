# pages/transfers.py
# =============================================================================
# UAEW Operations App — Transfers (Arrival / Departure)
# -----------------------------------------------------------------------------
# - Segmented "Arrival / Departure" dentro do expander Settings
# - Hora sempre mostrada como HH:MM (corrige "30/12/1899" -> vazio)
# - Ordenação via segmented: Guest | Car number | Date & Time
# =============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import datetime
import re

# --- Bootstrap / Título ---
bootstrap_page("Transfers")
st.title("Transfers")

# --- Project Imports ---
from utils import get_gspread_client, connect_gsheet_tab

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App"
DATA_TAB_NAME = "df"

# ----------------------------- Helpers ---------------------------------------
def _fmt_hhmm(val) -> str:
    """
    Normaliza horários variados para 'HH:MM'.

    Aceita:
      - strings: '13:45', '13:45:00', '1:45 PM', '07h05', '07.05'
      - números seriais (Sheets/Excel): 0.5 (=12:00), 0.315972... (=07:35)
      - datetimes com data base '1899-12-30' (pega só HH:MM)
      - se vier só '30/12/1899' (data base sem hora) -> retorna vazio
    """
    if val is None:
        return ""

    s = str(val).strip()
    if s == "":
        return ""

    # 0) Se for exatamente uma data base 30/12/1899 sem hora -> vazio
    if re.fullmatch(r"\s*30[/-]12[/-]1899\s*$", s):
        return ""

    # 1) Numérico -> serial (fração do dia)
    try:
        if re.fullmatch(r"[-+]?\d+(\.\d+)?", s):
            x = float(s)
            frac = x % 1  # ignora parte inteira (data)
            total_minutes = int(round(frac * 24 * 60))
            hh = (total_minutes // 60) % 24
            mm = total_minutes % 60
            return f"{hh:02d}:{mm:02d}"
    except Exception:
        pass

    # 2) Data/hora parseável
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors="raise")
        if pd.notna(dt):
            # Caso “data base do Excel”
            if dt.year == 1899 and dt.month == 12 and dt.day == 30:
                # Se tiver hora/minuto, usamos só a hora. Se não tiver, vazio.
                if dt.hour or dt.minute:
                    return f"{dt.hour:02d}:{dt.minute:02d}"
                return ""
            # Em outros casos, se houver hora, retorna; senão vazio
            if dt.hour or dt.minute:
                return f"{dt.hour:02d}:{dt.minute:02d}"
            return ""
    except Exception:
        pass

    # 3) Padrões típicos de hora textual
    m = re.match(r'^\s*(\d{1,2})[:h\.](\d{1,2})', s, re.IGNORECASE)
    if m:
        hh = int(m.group(1)); mm = int(m.group(2))
        return f"{hh:02d}:{mm:02d}"

    # Fallback: se nada casou, retorna vazio em vez de poluir com uma "data"
    return ""

def _norm_status_arrival(x: str) -> str:
    s = ("" if x is None else str(x)).strip().upper()
    return "CANCELED" if s in ("CANCELLED", "CANCELED") else s

def _car_number_key(val: str) -> int:
    """
    Extrai o primeiro número do texto do carro (ex.: 'DXB_CAR - 53' -> 53).
    Se não houver número, retorna grande para ir ao final.
    """
    s = "" if val is None else str(val)
    m = re.search(r"(\d+)", s)
    if not m:
        return 10**9
    try:
        return int(m.group(1))
    except Exception:
        return 10**9

# --- Data Loading ---
@st.cache_data(ttl=600)
def load_transfers_df(sheet_name: str = MAIN_SHEET_NAME, data_tab_name: str = DATA_TAB_NAME) -> pd.DataFrame:
    """Carrega a aba 'df' com todos os dados."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, data_tab_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data or [])
    except Exception as e:
        st.error(f"Error loading data: {e}", icon="🚨")
        return pd.DataFrame()

def highlight_today(row, date_col: str):
    today = datetime.datetime.now().strftime('%d/%m')
    if date_col in row and str(row[date_col]) == today:
        return ['background-color: #ffe066'] * len(row)
    return [''] * len(row)

# ------------------------------ Main -----------------------------------------
with st.spinner("Loading data..."):
    df_all = load_transfers_df()

# Filtra INACTIVE
if not df_all.empty and 'INACTIVE' in df_all.columns:
    df_all = df_all[df_all['INACTIVE'].isin([False, "FALSE", "false", "False", 0, "0"])].copy()

# ================== SETTINGS (segmented dentro do expander) ===================
with st.expander("Settings", expanded=True):
    st.segmented_control(
        "Mode:",
        options=["Arrival", "Departure"],
        key="arrdep_mode"
    )

    # Filtro de tipo (fighters / car request)
    st.segmented_control(
        "Filter list:",
        options=["All", "Only Fighters", "Cars with request"],
        key="role_car_filter",
        default="All"
    )

    # Filtro de status
    st.segmented_control(
        "Filter by status:",
        options=["All", "Planned", "Done", "Canceled", "No Show"],
        key="status_filter",
        default="All"
    )

    # Ordenação
    st.segmented_control(
        "Order by:",
        options=["Guest", "Car number", "Date & Time"],
        key="order_by",
        default="Date & Time"
    )

    # Toggles
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.toggle("View as cards", value=True, key="view_as_cards")
    with col_t2:
        st.toggle(
            "Hide airport: Resident",
            value=False,
            key="hide_resident_cards",
            help="When ON, hides cards where Airport = Resident (cards view only)."
        )

    # Busca
    search = st.text_input("Search in any column:")

mode = st.session_state.get("arrdep_mode", "Arrival")

# Mapas por modo
if mode == "Arrival":
    FLIGHT_COL = "ArrivalFlight"
    DATE_COL   = "ArrivalDate"
    TIME_COL   = "ArrivalTime"
    AIRP_COL   = "ArrivalAirport"
    STATUS_COL = "transfer_arrival_status"
    CAR_COL    = "transfer_arrival_car"
    DRIVER_COL = "transfer_arrival_driver"
    PICKUP_COL = None
    title_mode = "Arrivals"
else:
    FLIGHT_COL = "DepartureFlight"
    DATE_COL   = "DepartureDate"
    TIME_COL   = "DepartureTime"
    AIRP_COL   = "DepartureAirport"
    STATUS_COL = "transfer_departure_status"
    CAR_COL    = "transfer_departure_car"
    DRIVER_COL = "transfer_departure_driver"
    PICKUP_COL = "transfer_departure_pickup"
    title_mode = "Departures"

# Mantém colunas relevantes
base_cols = [
    'ID', 'ROLE', 'CORNER', 'NAME',
    FLIGHT_COL, DATE_COL, TIME_COL, AIRP_COL,
    STATUS_COL, CAR_COL, DRIVER_COL
]
if PICKUP_COL:
    base_cols.append(PICKUP_COL)

existing_cols = [c for c in base_cols if c in df_all.columns]
df = df_all[existing_cols].copy() if not df_all.empty else pd.DataFrame(columns=existing_cols)

# NAME é essencial
if 'NAME' not in df.columns:
    st.error("The 'NAME' column is essential and was not found in the sheet.")
    st.stop()

df.dropna(subset=['NAME'], inplace=True)
df = df[df['NAME'].astype(str).str.strip() != ''].copy()

# -------------------- Filtros do Settings ------------------------------------
df_filtrado = df.copy()

# Only Fighters
if st.session_state.get("role_car_filter") == "Only Fighters" and 'ROLE' in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado['ROLE'].astype(str).str.upper() == "1 - FIGHTER"]

# Cars with request
elif st.session_state.get("role_car_filter") == "Cars with request" and CAR_COL in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado[CAR_COL].astype(str).str.strip() != ""]

# Status
sel_status = st.session_state.get("status_filter", "All")
if sel_status != "All" and STATUS_COL in df_filtrado.columns:
    target = sel_status.upper()
    df_filtrado = df_filtrado[df_filtrado[STATUS_COL].apply(_norm_status_arrival) == target]

# Search
df_search = df_filtrado.copy()
if search:
    mask = pd.Series(False, index=df_search.index)
    for col in df_search.columns:
        mask = mask | df_search[col].astype(str).str.contains(search, case=False, na=False)
    df_search = df_search[mask]

# --------------------- Chaves de ordenação ------------------------------------
order_by = st.session_state.get("order_by", "Date & Time")

df_order = df_search.copy()
now = datetime.datetime.now()
current_year = now.year

# Chave por data/hora
df_order["__HHMM__"] = df_order.get(TIME_COL, "").apply(_fmt_hhmm)
if DATE_COL in df_order.columns:
    df_order["__DT__"] = pd.to_datetime(
        df_order[DATE_COL].astype(str) + "/" + str(current_year) + " " + df_order["__HHMM__"].astype(str),
        format="%d/%m/%Y %H:%M",
        errors="coerce"
    )
else:
    df_order["__DT__"] = pd.NaT

# Chave por carro
df_order["__CARKEY__"] = df_order.get(CAR_COL, "").apply(_car_number_key)

# Ordena
if order_by == "Guest":
    df_order = df_order.sort_values(by=["NAME"], na_position="last")
elif order_by == "Car number":
    df_order = df_order.sort_values(by=["__CARKEY__", "NAME"], na_position="last")
else:  # Date & Time
    df_order = df_order.sort_values(by=["__DT__", "NAME"], na_position="last")

# ---------------------------- Métricas ----------------------------------------
def norm_status_series(series):
    s = series.astype(str).str.strip().str.upper().replace({"CANCELLED": "CANCELED"})
    return s

status_series = norm_status_series(df_order.get(STATUS_COL, pd.Series(dtype=str)))

total_filtered = len(df_order)
total_all = len(df)
planned_count  = (status_series == "PLANNED").sum()
done_count     = (status_series == "DONE").sum()
canceled_count = (status_series == "CANCELED").sum()
noshow_count   = (status_series == "NO SHOW").sum()

summary_html = f'''
<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0;">
    <span style="font-weight:bold;">Showing {total_filtered} of {total_all} {title_mode.lower()}:</span>
    <span style="background-color:#ffe066;color:#23272f;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Planned: {planned_count}</span>
    <span style="background-color:#27ae60;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Done: {done_count}</span>
    <span style="background-color:#e74c3c;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Canceled: {canceled_count}</span>
    <span style="background-color:#95a5a6;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">No Show: {noshow_count}</span>
</div>'''
st.markdown(summary_html, unsafe_allow_html=True)

# ---------------------------- Visualização ------------------------------------
if st.session_state.get("view_as_cards", True):
    # Aplica "hide resident" nos cards
    df_cards = df_order.copy()
    if st.session_state.get("hide_resident_cards", False) and AIRP_COL in df_cards.columns:
        df_cards = df_cards[~df_cards[AIRP_COL].astype(str).str.strip().str.lower().eq('resident')]

    today_str = now.strftime('%d/%m')

    corner_colors = {
        "RED": "#e74c3c",
        "BLUE": "#3498db",
        "GREEN": "#27ae60",
        "YELLOW": "#f1c40f",
        "BLACK": "#23272f",
        "WHITE": "#f8f9fa"
    }

    groups = df_cards.groupby(DATE_COL) if DATE_COL in df_cards.columns else [(None, df_cards)]

    for date_val, group in groups:
        st.subheader(f"{title_mode} on {date_val} ({len(group)})")

        for _, row in group.iterrows():
            card_color, text_color = "#23272f", "#f8f9fa"

            # janela crítica (laranja) próximas 3h / últimas 30min
            dt_event = row.get("__DT__")
            if pd.notna(dt_event):
                diff = dt_event - now
                if datetime.timedelta(minutes=-30) <= diff <= datetime.timedelta(hours=3):
                    card_color, text_color = "#FF8C00", "#f8f9fa"
            elif str(date_val) == today_str:
                card_color, text_color = "#ffe066", "#23272f"

            corner = str(row.get('CORNER', '')).upper()
            corner_label_color = corner_colors.get(corner, "#888")

            # status chip
            raw_status = str(row.get(STATUS_COL, '')).strip().upper()
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
                safe = str(row.get(STATUS_COL, ""))
                status_label = f'<span style="background-color:#888;color:#fff;padding:2px 8px;border-radius:8px;">{safe}</span>'

            car_val = str(row.get(CAR_COL, '')).strip()
            driver_val = str(row.get(DRIVER_COL, '')).strip()
            pickup_val = str(row.get(PICKUP_COL, '')).strip() if PICKUP_COL else ""

            # linha inferior (car / driver / pickup / status)
            line_html = '<div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;">'
            if car_val:
                line_html += f'<span><strong>Car:</strong> {car_val}</span>'
            if driver_val:
                line_html += f'<span><strong>Driver:</strong> {driver_val}</span>'
            if pickup_val:
                line_html += f'<span><strong>Pickup:</strong> {pickup_val}</span>'
            line_html += status_label + '</div>'

            st.markdown(
                f"""
                <div style="background-color: {card_color}; border-radius: 12px; padding: 16px; margin-bottom: 12px; color: {text_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                    <div style="display: flex; align-items: center; margin-bottom: 8px; gap:10px;">
                        <span style="font-size: 20px; font-weight: bold;">{row.get('NAME','')}</span>
                        <span style="background-color: {corner_label_color}; color: #fff; font-size: 14px; font-weight: bold; border-radius: 8px; padding: 2px 10px;">{corner}</span>
                    </div>
                    <div style="display: flex; gap: 18px; margin-bottom: 8px; flex-wrap:wrap;">
                        <span><strong>Flight:</strong> {row.get(FLIGHT_COL,'')}</span>
                        <span><strong>Time:</strong> {row.get('__HHMM__','')}</span>
                        <span><strong>Airport:</strong> {row.get(AIRP_COL,'')}</span>
                    </div>
                    {line_html}
                </div>
                """,
                unsafe_allow_html=True
            )
else:
    # --- Tabela ---
    df_table = df_order.copy()
    # substituir a coluna de hora pela HH:MM já calculada
    if TIME_COL in df_table.columns:
        df_table[TIME_COL] = df_table["__HHMM__"]
    # ordenar já foi feito; apenas destacar hoje
    styled_df = df_table.drop(columns=["__DT__", "__CARKEY__", "__HHMM__"], errors="ignore") \
                        .style.apply(lambda r: highlight_today(r, DATE_COL), axis=1)
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
