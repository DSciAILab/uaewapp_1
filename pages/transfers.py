from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import datetime
import html

# --- Bootstrap: configura página, autentica e desenha o sidebar unificado ---
bootstrap_page("Arrival/Departure List")

# --- Modo (Arrival | Departure) ---
st.session_state.setdefault("arrdep_mode", "Arrival")
st.session_state["arrdep_mode"] = st.segmented_control(
    "Mode:",
    options=["Arrival", "Departure"],
    key="arrdep_mode",
)
MODE = st.session_state["arrdep_mode"]

st.title(f"{MODE} List")

# --- Project Imports ---
from utils import get_gspread_client, connect_gsheet_tab

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
DATA_TAB_NAME = "df"

# ----------------------------
# Colunas por modo (mapeamento)
# ----------------------------
if MODE == "Arrival":
    DATE_COL   = "ArrivalDate"
    TIME_COL   = "ArrivalTime"
    FLIGHT_COL = "ArrivalFlight"
    APT_COL    = "ArrivalAirport"
    STATUS_COL = "transfer_arrival_status"
    CAR_COL    = "transfer_arrival_car"
    DRIVER_COL = "transfer_arrival_driver"
    PICKUP_COL = None  # não se aplica em arrival
    GROUP_LABEL = "Arrivals on"
    CAR_FILTER_LABEL = "Cars with request"
else:
    DATE_COL   = "DepartureDate"
    TIME_COL   = "DepartureTime"
    FLIGHT_COL = "DepartureFlight"
    APT_COL    = "DepartureAirport"
    STATUS_COL = "transfer_departure_status"
    CAR_COL    = "transfer_departure_car"
    DRIVER_COL = "transfer_departure_driver"
    PICKUP_COL = "transfer_departure_pickup"  # nova coluna solicitada
    GROUP_LABEL = "Departures on"
    CAR_FILTER_LABEL = "Cars with request"

# --- Data Loading ---
@st.cache_data(ttl=600)
def load_arrdep_data(sheet_name: str = MAIN_SHEET_NAME, data_tab_name: str = DATA_TAB_NAME):
    """Loads and processes arrival/departure data from the Google Sheet."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, data_tab_name)
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()

        # mantém apenas colunas relevantes que existirem (inclui as duas direções)
        display_cols = [
            'INACTIVE', 'ID', 'ROLE', 'CORNER', 'NAME',
            # ARRIVAL
            'ArrivalFlight', 'ArrivalDate', 'ArrivalTime', 'ArrivalAirport',
            'transfer_arrival_status', 'transfer_arrival_car', 'transfer_arrival_driver',
            # DEPARTURE
            'DepartureFlight', 'DepartureDate', 'DepartureTime', 'DepartureAirport',
            'transfer_departure_status', 'transfer_departure_car', 'transfer_departure_driver',
            'transfer_departure_pickup',  # nova coluna
        ]
        existing_cols = [c for c in display_cols if c in df.columns]
        df = df[existing_cols]

        # NAME é essencial
        if 'NAME' in df.columns:
            df.dropna(subset=['NAME'], inplace=True)
            df = df[df['NAME'].astype(str).str.strip() != ''].copy()
        else:
            st.error("The 'NAME' column is essential and was not found in the sheet.")
            return pd.DataFrame()

        return df
        
    except Exception as e:
        st.error(f"Error loading data: {e}", icon="🚨")
        return pd.DataFrame()

def highlight_today(row):
    today = datetime.datetime.now().strftime('%d/%m')
    if DATE_COL in row and str(row[DATE_COL]) == today:
        return ['background-color: #ffe066'] * len(row)
    return [''] * len(row)

# --- Main Application ---
with st.spinner("Loading data..."):
    df_all = load_arrdep_data()

# Filtra INACTIVE
if 'INACTIVE' in df_all.columns:
    df_all = df_all[df_all['INACTIVE'].isin([False, "FALSE", "false", "False", 0, "0"])]
    df_all.drop(columns=['INACTIVE'], inplace=True, errors='ignore')

# Recorte por modo: mantém linhas que têm pelo menos a coluna de data do modo
df_mode = df_all.copy()
if DATE_COL in df_mode.columns:
    # Se existir a coluna de data do modo, priorizamos visualizar quem tem esse campo preenchido
    # (mas se você preferir, pode remover esse filtro — mantive bem leve)
    pass

if df_mode.empty:
    st.info(f"No {MODE.lower()} records found with a filled name.")
else:
    with st.expander("Settings", expanded=True):
        # Filtro de tipo (fighters / car request)
        filtro = st.segmented_control(
            f"Filter {MODE.lower()}s:",
            options=["All", "Only Fighters", CAR_FILTER_LABEL],
            key=f"role_car_filter_{MODE}",
            default="All"  # evita None
        )

        df_filtrado = df_mode.copy()
        if filtro == "Only Fighters" and 'ROLE' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['ROLE'].astype(str).str.upper() == "1 - FIGHTER"]
        elif filtro == CAR_FILTER_LABEL and CAR_COL in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado[CAR_COL].astype(str).str.strip() != ""]

        # --- Filtro por STATUS (coluna STATUS_COL) ---
        status_filter = st.segmented_control(
            "Filter by status:",
            options=["All", "Planned", "Done", "Canceled", "No Show"],
            key=f"status_filter_{MODE}",
            default="All"  # evita None
        )

        if status_filter != "All" and STATUS_COL in df_filtrado.columns:
            target = status_filter.upper()

            def _norm_status(x):
                s = ("" if x is None else str(x)).strip().upper()
                return "CANCELED" if s in ("CANCELLED", "CANCELED") else s

            df_filtrado = df_filtrado[df_filtrado[STATUS_COL].apply(_norm_status) == target]

        # === Toggles lado a lado ===
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            modo_cards = st.toggle("View as cards", value=True, key=f"view_as_cards_{MODE}")
        with col_t2:
            hide_resident = st.toggle(
                f"Hide airport: Resident ({MODE.lower()}s)",
                value=False,
                key=f"hide_resident_cards_{MODE}",
                help=f"When ON, hides cards where {APT_COL} = Resident (cards view only)."
            )

        # Search box para ambas visões
        search = st.text_input("Search in any column:", key=f"search_{MODE}")
        df_search = df_filtrado.copy()
        if search:
            mask = pd.Series(False, index=df_search.index)
            for col in df_search.columns:
                mask = mask | df_search[col].astype(str).str.contains(search, case=False, na=False)
            df_search = df_search[mask]

    # --- Métricas (baseadas em df_search) ---
    def norm_status_series(s):
        s = s.astype(str).str.strip().str.upper()
        s = s.replace({"CANCELLED": "CANCELED"})  # mapeia variação britânica
        return s

    status_series = norm_status_series(
        df_search.get(STATUS_COL, pd.Series(dtype=str))
    )

    total_filtered = len(df_search)
    total_all = len(df_mode)
    planned_count  = (status_series == "PLANNED").sum()
    done_count     = (status_series == "DONE").sum()
    canceled_count = (status_series == "CANCELED").sum()
    noshow_count   = (status_series == "NO SHOW").sum()

    summary_html = f'''
    <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0;">
        <span style="font-weight:bold;">Showing {total_filtered} of {total_all} {MODE.lower()}s:</span>
        <span style="background-color:#ffe066;color:#23272f;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Planned: {planned_count}</span>
        <span style="background-color:#27ae60;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Done: {done_count}</span>
        <span style="background-color:#e74c3c;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">Canceled: {canceled_count}</span>
        <span style="background-color:#95a5a6;color:#fff;padding:4px 12px;border-radius:15px;font-size:0.9em;font-weight:bold;">No Show: {noshow_count}</span>
    </div>'''
    st.markdown(summary_html, unsafe_allow_html=True)

    if modo_cards:
        # Aplica o "hide resident" apenas nos cards
        df_cards = df_search.copy()
        if hide_resident and APT_COL in df_cards.columns:
            df_cards = df_cards[~df_cards[APT_COL].astype(str).str.strip().str.lower().eq('resident')]

        now = datetime.datetime.now()
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
            st.subheader(f"{GROUP_LABEL} {date_val} ({len(group)})")
            
            for _, row in group.iterrows():
                card_color, text_color = "#23272f", "#f8f9fa"

                # calcula janela crítica (laranja) para próximas 3h / últimas 30min
                dt_full = None
                try:
                    if row.get(DATE_COL) and row.get(TIME_COL):
                        dt_str = f"{row[DATE_COL]}/{now.year} {row[TIME_COL]}"
                        dt_full = datetime.datetime.strptime(dt_str, '%d/%m/%Y %H:%M')
                except Exception:
                    pass

                is_today = (str(date_val) == today_str)
                if dt_full:
                    diff = dt_full - now
                    if datetime.timedelta(minutes=-30) <= diff <= datetime.timedelta(hours=3):
                        card_color, text_color = "#FF8C00", "#f8f9fa"
                elif is_today:
                    card_color, text_color = "#ffe066", "#23272f"

                corner = str(row.get('CORNER', '')).upper()
                corner_label_color = corner_colors.get(corner, "#888")

                # status chip (inclui CANCELED e NO SHOW)
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
                    status_label = f'<span style="background-color:#888;color:#fff;padding:2px 8px;border-radius:8px;">{html.escape(safe)}</span>'

                car_val = str(row.get(CAR_COL, '')).strip()
                driver_val = str(row.get(DRIVER_COL, '')).strip()
                pickup_val = str(row.get(PICKUP_COL, '')).strip() if PICKUP_COL else ""

                # monta a linha inferior (car / driver / pickup / status)
                pieces = []
                if car_val:
                    pieces.append(f'<span><strong>Car:</strong> {html.escape(car_val)}</span>')
                if driver_val:
                    pieces.append(f'<span style="opacity:0.9;"><strong>Driver:</strong> {html.escape(driver_val)}</span>')
                if pickup_val:
                    pieces.append(f'<span style="opacity:0.9;"><strong>Pickup:</strong> {html.escape(pickup_val)}</span>')
                line_html = '<div style="display:flex;gap:18px;align-items:center;">' + (
                    " ".join(pieces) + " " if pieces else ""
                ) + status_label + '</div>'

                st.markdown(
                    f"""
                    <div style="background-color: {card_color}; border-radius: 12px; padding: 16px; margin-bottom: 12px; color: {text_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                        <div style="display: flex; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 20px; font-weight: bold;">{html.escape(str(row.get('NAME','')))}</span>
                            <span style="background-color: {corner_label_color}; color: #fff; font-size: 14px; font-weight: bold; border-radius: 8px; padding: 2px 10px; margin-left: 12px;">{html.escape(corner)}</span>
                        </div>
                        <div style="display: flex; gap: 18px; margin-bottom: 8px;">
                            <span><strong>Flight:</strong> {html.escape(str(row.get(FLIGHT_COL,'')))}</span>
                            <span><strong>Time:</strong> {html.escape(str(row.get(TIME_COL,'')))}</span>
                            <span><strong>{'Airport' if MODE=='Arrival' else 'Airport'}</strong>: {html.escape(str(row.get(APT_COL,'')))}</span>
                        </div>
                        {line_html}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        # --- Tabela ---
        df_search_sorted = df_search.copy()
        current_year = datetime.datetime.now().year
        if DATE_COL in df_search_sorted.columns and TIME_COL in df_search_sorted.columns:
            df_search_sorted['__DateTime__'] = pd.to_datetime(
                df_search_sorted[DATE_COL].astype(str) + '/' + str(current_year) + ' ' + df_search_sorted[TIME_COL].astype(str),
                format='%d/%m/%Y %H:%M',
                errors='coerce'
            )
            df_search_sorted = df_search_sorted.sort_values(by='__DateTime__', na_position='last').drop(columns=['__DateTime__'])

        # remove driver na visão tabela (para limpar, igual ao original)
        drop_cols = []
        if DRIVER_COL in df_search_sorted.columns:
            drop_cols.append(DRIVER_COL)
        df_table = df_search_sorted.drop(columns=drop_cols) if drop_cols else df_search_sorted

        styled_df = df_table.style.apply(highlight_today, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
