# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import datetime

# --- Project Imports ---
from utils import get_gspread_client, connect_gsheet_tab
from auth import check_authentication, display_user_sidebar

# --- Authentication ---
check_authentication()

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Arrival List", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
DATA_TAB_NAME = "df"

# --- Data Loading ---
@st.cache_data(ttl=600)
def load_arrival_data(sheet_name: str = MAIN_SHEET_NAME, data_tab_name: str = DATA_TAB_NAME):
    """Loads and processes arrival data from the Google Sheet."""
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, data_tab_name)
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()

        # Use original column names as requested
        display_cols = [
            'INACTIVE', 'ID', 'ROLE', 'CORNER', 'NAME', 'ArrivalFlight', 
            'ArrivalDate', 'ArrivalTime', 'ArrivalAirport', 
            'transfer_arrival_status', 'transfer_arrival_car'
        ]

        # Filter for existing columns to avoid errors
        existing_cols = [col for col in display_cols if col in df.columns]
        df = df[existing_cols]

        # Filter out rows where NAME is empty or just whitespace
        if 'NAME' in df.columns:
            df.dropna(subset=['NAME'], inplace=True)
            df = df[df['NAME'].astype(str).str.strip() != ''].copy()
        else:
            st.error("The 'NAME' column is essential and was not found in the sheet.")
            return pd.DataFrame()

        return df
        
    except Exception as e:
        st.error(f"Error loading arrival data: {e}", icon="🚨")
        return pd.DataFrame()

def highlight_today(row):
    today = datetime.datetime.now().strftime('%d/%m')
    if 'ArrivalDate' in row and str(row['ArrivalDate']) == today:
        return ['background-color: #ffe066'] * len(row)
    return [''] * len(row)

# --- Main Application ---
st.title("Arrival List")
display_user_sidebar()

with st.spinner("Loading data..."):
    df_arrivals = load_arrival_data()

# Filter only active records and remove the INACTIVE column
if 'INACTIVE' in df_arrivals.columns:
    # Consider False, "FALSE", "false", 0, etc.
    df_arrivals = df_arrivals[df_arrivals['INACTIVE'].isin([False, "FALSE", "false", "False", 0, "0"])]
    df_arrivals.drop(columns=['INACTIVE'], inplace=True)

#st.divider()

if df_arrivals.empty:
    st.info("No arrival records found with a filled name.")
else:
    with st.expander("⚙️ Filtros e Pesquisa", expanded=True):
        filtro = st.segmented_control(
            "Filter arrivals:",
            options=["All", "Only Fighters", "Cars with request"]
        )

        df_filtrado = df_arrivals.copy()
        if filtro == "Only Fighters":
            df_filtrado = df_filtrado[df_filtrado['ROLE'].str.upper() == "1 - FIGHTER"]
        elif filtro == "Cars with request":
            df_filtrado = df_filtrado[df_filtrado['transfer_arrival_car'].astype(str).str.strip() != ""]

        # Toggle for cards or table view
        modo_cards = st.toggle("View as cards", value=True)

        # Search box for both views
        search = st.text_input("Search in any column:")
        df_search = df_filtrado.copy()
        if search:
            mask = pd.Series(False, index=df_search.index)
            for col in df_search.columns:
                mask = mask | df_search[col].astype(str).str.contains(search, case=False, na=False)
            df_search = df_search[mask]

    total_filtered = len(df_search)
    total_all = len(df_arrivals)
    planned_count = df_search[df_search['transfer_arrival_status'].astype(str).str.strip().str.upper() == "PLANNED"].shape[0]
    done_count = df_search[df_search['transfer_arrival_status'].astype(str).str.strip().str.upper() == "DONE"].shape[0]
    
    summary_html = f'''<div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 10px; margin-top: 10px;">
        <span style="font-weight: bold;">Exibindo {total_filtered} de {total_all} chegadas:</span>
        <span style="background-color: #ffe066; color: #23272f; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Planned: {planned_count}</span>
        <span style="background-color: #27ae60; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Done: {done_count}</span>
    </div>'''
    st.markdown(summary_html, unsafe_allow_html=True)

#st.divider() - Removi para deixar mais compacto

    if modo_cards:
        # Group by ArrivalDate and show cards
        now = datetime.datetime.now()
        today_str = now.strftime('%d/%m')
        
        # Colors for corners
        corner_colors = {
            "RED": "#e74c3c",
            "BLUE": "#3498db",
            "GREEN": "#27ae60",
            "YELLOW": "#f1c40f",
            "BLACK": "#23272f",
            "WHITE": "#f8f9fa"
        }
        for arrival_date, group in df_search.groupby('ArrivalDate'):
            total_chegadas = len(group)
            st.subheader(f"Arrivals on {arrival_date} ({total_chegadas})")
            
            for idx, row in group.iterrows():
                card_color = "#23272f" # Default color
                text_color = "#f8f9fa" # Default text color

                # Parse arrival date and time
                try:
                    # Assuming ArrivalDate is DD/MM and ArrivalTime is HH:MM
                    arrival_datetime_str = f"{row['ArrivalDate']}/{now.year} {row['ArrivalTime']}"
                    arrival_dt = datetime.datetime.strptime(arrival_datetime_str, '%d/%m/%Y %H:%M')
                except ValueError:
                    arrival_dt = None # Handle cases where date/time format is unexpected

                is_today = (arrival_date == today_str)
                is_soon = False
                if arrival_dt:
                    time_diff = arrival_dt - now
                    if datetime.timedelta(minutes=-30) <= time_diff <= datetime.timedelta(hours=3): # 30 min before to 3 hours after
                        is_soon = True

                if is_soon:
                    card_color = "#FF8C00" # Darker Orange for "soon"
                    text_color = "#f8f9fa"
                elif is_today:
                    card_color = "#ffe066" # Yellow for "today"
                    text_color = "#23272f"
                
                # Corner label
                corner = str(row['CORNER']).upper()
                corner_label_color = corner_colors.get(corner, "#888")
                # Status label
                status = str(row['transfer_arrival_status']).strip().upper()
                if status == "PLANNED":
                    status_label = '<span style="background-color:#ffe066;color:#23272f;padding:2px 8px;border-radius:8px;font-weight:bold;">Planned</span>'
                elif status == "DONE":
                    status_label = '<span style="background-color:#27ae60;color:#fff;padding:2px 8px;border-radius:8px;font-weight:bold;">Done</span>'
                else:
                    status_label = f'<span style="background-color:#888;color:#fff;padding:2px 8px;border-radius:8px;">{row["transfer_arrival_status"]}</span>'
                st.markdown(
                    f"""
                    <div style="background-color: {card_color}; border-radius: 12px; padding: 16px; margin-bottom: 12px; color: {text_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                        <div style="display: flex; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 20px; font-weight: bold;">{row['NAME']}</span>
                            <span style="background-color: {corner_label_color}; color: #fff; font-size: 14px; font-weight: bold; border-radius: 8px; padding: 2px 10px; margin-left: 12px;">{corner}</span>
                        </div>
                        <div style="display: flex; gap: 18px; margin-bottom: 8px;">
                            <span><strong>Flight:</strong> {row['ArrivalFlight']}</span>
                            <span><strong>Time:</strong> {row['ArrivalTime']}</span>
                            <span><strong>Airport:</strong> {row['ArrivalAirport']}</span>
                        </div>
                        <div style="display: flex; gap: 18px;">
                            <span><strong>Car:</strong> {row['transfer_arrival_car']}</span>
                            {status_label}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        # Prepare for sorting by date and time
        df_search_sorted = df_search.copy()
        
        # Combine ArrivalDate and ArrivalTime into a single datetime column for sorting
        # Assuming ArrivalDate is DD/MM and ArrivalTime is HH:MM
        # Add a dummy year (current year) for parsing
        current_year = datetime.datetime.now().year
        df_search_sorted['ArrivalDateTime'] = pd.to_datetime(
            df_search_sorted['ArrivalDate'].astype(str) + '/' + str(current_year) + ' ' + df_search_sorted['ArrivalTime'].astype(str),
            format='%d/%m/%Y %H:%M',
            errors='coerce' # Coerce errors will turn invalid parsing into NaT (Not a Time)
        )
        
        # Sort by the new datetime column, putting NaT (invalid dates) at the end
        df_search_sorted = df_search_sorted.sort_values(by='ArrivalDateTime', na_position='last').drop(columns=['ArrivalDateTime'])

        styled_df = df_search_sorted.style.apply(highlight_today, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
