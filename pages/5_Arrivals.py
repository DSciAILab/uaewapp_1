# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import html
import pytz

# --- Importações do Projeto ---
from utils import get_gspread_client, connect_gsheet_tab
from auth import check_authentication, display_user_sidebar

# --- Autenticação ---
check_authentication()

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Controle de Voos", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    .card-container {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }
    .info-line {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
    }
    .person-name {
        font-size: 1.25rem;
        font-weight: bold;
        color: white;
    }
    .grey-label {
        background-color: #4A4A4A;
        color: white;
        padding: 3px 10px;
        border-radius: 8px;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
DATA_TAB_NAME = "df"
TIMEZONE = pytz.timezone("Asia/Dubai")

# --- Data Loading ---
@st.cache_data(ttl=600)
def load_flight_data(sheet_name: str = MAIN_SHEET_NAME, data_tab_name: str = DATA_TAB_NAME):
    """Loads and processes flight data from the Google Sheet."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, data_tab_name)
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()

        # Normalize column names
        df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]
        
        # Ensure required columns exist
        required_cols = ['role', 'name', 'arrivalflight', 'arrivaldate', 'arrivaltime', 'arrivalairport', 'reservation', 'transfer_arrival_car']
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""
        
        # Combine Date and Time and convert to datetime object, handling errors
        df['arrival_datetime_str'] = df['arrivaldate'].astype(str) + ' ' + df['arrivaltime'].astype(str)
        df['arrival_datetime'] = pd.to_datetime(df['arrival_datetime_str'], errors='coerce', format='%d/%m/%Y %H:%M')
        
        # Filter out rows where datetime conversion failed
        df.dropna(subset=['arrival_datetime'], inplace=True)
        
        return df.sort_values(by="arrival_datetime").reset_index(drop=True)
        
    except Exception as e:
        st.error(f"Error loading flight data: {e}", icon="🚨")
        return pd.DataFrame()

# --- Main Application ---
st.title("Controle de Voos e Chegadas")
display_user_sidebar()

# --- Session State Initialization ---
if 'date_filter' not in st.session_state:
    st.session_state.date_filter = "Hoje"
if 'role_filter' not in st.session_state:
    st.session_state.role_filter = []

# --- Data Loading ---
with st.spinner("Carregando dados de voos..."):
    df_flights = load_flight_data()

# --- Filters ---
st.subheader("Filtros")
date_filter_options = ["Hoje", "Amanhã", "Todos"]
st.session_state.date_filter = st.radio("Filtrar por Data:", options=date_filter_options, index=0, horizontal=True)

if not df_flights.empty:
    role_options = sorted(df_flights['role'].unique().tolist())
    st.session_state.role_filter = st.multiselect("Filtrar por Função (Role):", options=role_options, default=st.session_state.role_filter)

# --- Filtering Logic ---
df_filtered = df_flights.copy()
now_tz = datetime.now(TIMEZONE)
today_tz = now_tz.date()
tomorrow_tz = today_tz + timedelta(days=1)

if st.session_state.date_filter == "Hoje":
    df_filtered = df_filtered[df_filtered['arrival_datetime'].dt.date == today_tz]
elif st.session_state.date_filter == "Amanhã":
    df_filtered = df_filtered[df_filtered['arrival_datetime'].dt.date == tomorrow_tz]

if st.session_state.role_filter:
    df_filtered = df_filtered[df_filtered['role'].isin(st.session_state.role_filter)]

st.divider()

# --- Card Rendering Loop ---
if df_filtered.empty:
    st.info("Nenhum voo encontrado para os filtros selecionados.")
else:
    st.write(f"**Exibindo {len(df_filtered)} registros.**")
    for _, row in df_filtered.iterrows():
        arrival_dt = TIMEZONE.localize(row['arrival_datetime'])

        # Determine card color
        card_color = "#262730" # Default color
        if arrival_dt.date() == today_tz:
            card_color = "#B08D00" # Yellow for today
        if (arrival_dt > now_tz) and (arrival_dt <= now_tz + timedelta(hours=3)):
            card_color = "#D35400" # Orange for arriving soon

        # --- Card Content ---
        st.markdown(f'''
        <div class="card-container" style="background-color: {card_color};">
            <div class="info-line">
                <span class="person-name">{html.escape(str(row.get("name", "N/A")))}</span>
                <span class="grey-label">{html.escape(str(row.get("role", "N/A")))}</span>
            </div>
            <div class="info-line">
                <span class="grey-label">✈️ {html.escape(str(row.get("arrivalflight", "N/A")))}</span>
                <span class="grey-label">📅 {html.escape(row['arrival_datetime'].strftime('%d/%m/%Y'))}</span>
                <span class="grey-label">⏰ {html.escape(row['arrival_datetime'].strftime('%H:%M'))}</span>
                <span class="grey-label">📍 {html.escape(str(row.get("arrivalairport", "N/A")))}</span>
            </div>
            <div class="info-line">
                <span class="grey-label">🏨 {html.escape(str(row.get("reservation", "N/A")))}</span>
                <span class="grey-label">🚗 {html.escape(str(row.get("transfer_arrival_car", "N/A")))}</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)
