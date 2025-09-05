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

        display_cols = [
            'INACTIVE', 'ID', 'ROLE', 'CORNER', 'NAME', 'ArrivalFlight', 
            'ArrivalDate', 'ArrivalTime', 'ArrivalAirport', 
            'transfer_arrival_status', 'transfer_arrival_car'
        ]

        existing_cols = [col for col in display_cols if col in df.columns]
        if 'TRANSFERdriver' in df.columns and 'TRANSFERdriver' not in existing_cols:
            existing_cols.append('TRANSFERdriver')

        df = df[existing_cols]

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

if 'INACTIVE' in df_arrivals.columns:
    df_arrivals = df_arrivals[df_arrivals['INACTIVE'].isin([False, "FALSE", "false", "False", 0, "0"])]
    df_arrivals.drop(columns=['INACTIVE'], inplace=True, errors='ignore')

if df_arrivals.empty:
    st.info("No arrival records found with a filled name.")
else:
    with st.expander("Settings", expanded=True):
        filtro = st.segmented_control(
            "Filter arrivals:",
            options=["All", "Only Fighters", "Cars with request"]
        )

        df_filtrado = df_arrivals.copy()
        if filtro == "Only Fighters" and 'ROLE' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['ROLE'].astype(str).str.upper() == "1 - FIGHTER"]
        elif filtro == "Cars with request" and 'transfer_arrival_car' in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado['transfer_arrival_car'].astype(str).str.strip() != ""]

        modo_cards = st.toggle("View as cards", value=True)

        search = st.text_input("Search in any column:")
        df_search = df_filtrado.copy()
        if search:
            mask = pd.Series(False, index=df_search.index)
            for col in df_search.columns:
                mask = mask | df_search[col].astype(str).str.contains(search, case=False, na=False)
            df_search = df_search[mask]

    total_filtered = len(df_search)
    total_all = len(df_arrivals)
    planned_count = df_search[df_search.get('transfer_arrival_status', pd.Series(dtype=str)).astype(str).str.strip().str.upper() == "PLANNED"].shape[0]
    done_count = df_search[df_search.get('transfer_arrival_status', pd.Series(dtype=str)).astype(str).str.strip().str.upper() == "DONE"].shape[0]
    
    summary_html = f'''<div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 10px; margin-top: 10px;">
        <span style="font-weight: bold;">Exibindo {total_filtered} de {total_all} chegadas:</span>
        <span style="background-color: #ffe066; color: #23272f; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Planned: {planned_count}</span>
        <span style="background-color: #27ae60; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">Done: {done_count}</span>
    </div>'''
    st.markdown(summary_html, unsafe_allow_html=True)

    if modo_cards:
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

        groups = df_search.groupby('ArrivalDate') if 'ArrivalDate' in df_search.columns else [(None, df_search)]

        for arrival_date, group in groups:
            st.subheader(f"Arrivals on {arrival_date} ({len(group)})")
            
            for _, row in group.iterrows():
                card_color, text_color = "#23272f", "#f8f9fa"

                arrival_dt = None
                try:
                    if row.get('ArrivalDate') and row.get('ArrivalTime'):
                        arrival_datetime_str = f"{row['ArrivalDate']}/{now.year} {row['ArrivalTime']}"
                        arrival_dt = datetime.datetime.strptime(arrival_datetime_str, '%d/%m/%Y %H:%M')
                except Exception:
                    pass

                is_today = (str(arrival_date) == today_str)
                if arrival_dt:
                    diff = arrival_dt - now
                    if datetime.timedelta(minutes=-30) <= diff <= datetime.timedelta(hours=3):
                        card_color, text_color = "#FF8C00", "#f8f9fa"
                elif is_today:
                    card_color, text_color = "#ffe066", "#23272f"

                corner = str(row.get('CORNER', '')).upper()
                corner_label_color = corner_colors.get(corner, "#888")

                status = str(row.get('transfer_arrival_status', '')).strip().upper()
                if status == "PLANNED":
                    status_label = '<span style="background-color:#ffe066;color:#23272f;padding:2px 8px;border-radius:8px;font-weight:bold;">Planned</span>'
                elif status == "DONE":
                    status_label = '<span style="background-color:#27ae60;color:#fff;padding:2px 8px;border-radius:8px;font-weight:bold;">Done</span>'
                else:
                    safe_status = str(row.get("transfer_arrival_status", ""))
                    status_label = f'<span style="background-color:#888;color:#fff;padding:2px 8px;border-radius:8px;">{safe_status}</span>'

                car_val = str(row.get('transfer_arrival_car', '')).strip()
                driver_val = str(row.get('TRANSFERdriver', '')).strip()

                # só monta a linha se houver carro ou driver
                line_html = ""
                if car_val or driver_val:
                    line_html = '<div style="display:flex;gap:18px;align-items:center;">'
                    if car_val:
                        line_html += f'<span><strong>Car:</strong> {car_val}</span>'
                    if driver_val:
                        line_html += f'<span style="margin-left:12px;opacity:0.9;"><strong>Driver:</strong> {driver_val}</span>'
                    line_html += status_label.strip() + '</div>'
                else:
                    # status sozinho (sem carro/driver)
                    line_html = f'<div style="display:flex;align-items:center;">{status_label.strip()}</div>'

                st.markdown(
                    f"""
                    <div style="background-color: {card_color}; border-radius: 12px; padding: 16px; margin-bottom: 12px; color: {text_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                        <div style="display: flex; align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 20px; font-weight: bold;">{row.get('NAME','')}</span>
                            <span style="background-color: {corner_label_color}; color: #fff; font-size: 14px; font-weight: bold; border-radius: 8px; padding: 2px 10px; margin-left: 12px;">{corner}</span>
                        </div>
                        <div style="display: flex; gap: 18px; margin-bottom: 8px;">
                            <span><strong>Flight:</strong> {row.get('ArrivalFlight','')}</span>
                            <span><strong>Time:</strong> {row.get('ArrivalTime','')}</span>
                            <span><strong>Airport:</strong> {row.get('ArrivalAirport','')}</span>
                        </div>
                        {line_html}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        df_search_sorted = df_search.copy()
        current_year = datetime.datetime.now().year
        if 'ArrivalDate' in df_search_sorted.columns and 'ArrivalTime' in df_search_sorted.columns:
            df_search_sorted['ArrivalDateTime'] = pd.to_datetime(
                df_search_sorted['ArrivalDate'].astype(str) + '/' + str(current_year) + ' ' + df_search_sorted['ArrivalTime'].astype(str),
                format='%d/%m/%Y %H:%M',
                errors='coerce'
            )
            df_search_sorted = df_search_sorted.sort_values(by='ArrivalDateTime', na_position='last').drop(columns=['ArrivalDateTime'])

        if 'TRANSFERdriver' in df_search_sorted.columns:
            df_table = df_search_sorted.drop(columns=['TRANSFERdriver'])
        else:
            df_table = df_search_sorted

        styled_df = df_table.style.apply(highlight_today, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
