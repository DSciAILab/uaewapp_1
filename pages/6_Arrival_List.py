# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import datetime

# --- Importações do Projeto ---
from utils import get_gspread_client, connect_gsheet_tab
from auth import check_authentication, display_user_sidebar

# --- Autenticação ---
check_authentication()

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Lista de Chegadas", layout="wide")

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
            st.error("A coluna 'NAME' é essencial e não foi encontrada na planilha.")
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
st.title("Lista de Chegadas")
display_user_sidebar()

with st.spinner("Carregando dados..."):
    df_arrivals = load_arrival_data()

# Filtra apenas registros ativos e remove a coluna INACTIVE
if 'INACTIVE' in df_arrivals.columns:
    # Considera False, "FALSE", "false", 0, etc.
    df_arrivals = df_arrivals[df_arrivals['INACTIVE'].isin([False, "FALSE", "false", "False", 0, "0"])]
    df_arrivals.drop(columns=['INACTIVE'], inplace=True)

st.divider()

if df_arrivals.empty:
    st.info("Nenhum registro de chegada encontrado com nome preenchido.")
else:
    filtro = st.segmented_control(
        "Filtrar chegadas:",
        options=["Todos", "Só Lutadores", "Carros com pedido"]
    )

    df_filtrado = df_arrivals.copy()
    if filtro == "Só Lutadores":
        df_filtrado = df_filtrado[df_filtrado['ROLE'].str.upper() == "1 - FIGHTER"]
    elif filtro == "Carros com pedido":
        df_filtrado = df_filtrado[df_filtrado['transfer_arrival_car'].astype(str).str.strip() != ""]

    # Toggle para modo cards ou tabela
    modo_cards = st.toggle("Visualizar em cards", value=True)

    # Caixa de busca para ambas visualizações
    search = st.text_input("Pesquisar em qualquer coluna:")
    df_search = df_filtrado.copy()
    if search:
        mask = pd.Series(False, index=df_search.index)
        for col in df_search.columns:
            mask = mask | df_search[col].astype(str).str.contains(search, case=False, na=False)
        df_search = df_search[mask]

    if modo_cards:
        # Agrupa por ArrivalDate e exibe cards
        today_str = datetime.datetime.now().strftime('%d/%m')
        for arrival_date, group in df_search.groupby('ArrivalDate'):
            total_chegadas = len(group)
            st.subheader(f"Chegadas em {arrival_date} ({total_chegadas})")
            card_color = "#ffe066" if arrival_date == today_str else "#23272f"
            text_color = "#23272f" if arrival_date == today_str else "#f8f9fa"
            for idx, row in group.iterrows():
                st.markdown(
                    f"""
                    <div style="background-color: {card_color}; border-radius: 12px; padding: 16px; margin-bottom: 12px; color: {text_color}; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                        <strong>Nome:</strong> {row['NAME']}<br>
                        <strong>Voo:</strong> {row['ArrivalFlight']}<br>
                        <strong>Hora:</strong> {row['ArrivalTime']}<br>
                        <strong>Aeroporto:</strong> {row['ArrivalAirport']}<br>
                        <strong>Canto:</strong> {row['CORNER']}<br>
                        <strong>Carro:</strong> {row['transfer_arrival_car']}<br>
                        <strong>Status Transfer:</strong> {row['transfer_arrival_status']}<br>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    else:
        styled_df = df_search.style.apply(highlight_today, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
