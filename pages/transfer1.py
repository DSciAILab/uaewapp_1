# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html
import time

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Transfer & Check-In", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
USERS_TAB_NAME = "Users"
DF_TRANSFERS_TAB_NAME = "df [Transfers]"

# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e: st.error(f"Erro API Google: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound: st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound: st.error(f"Erro: Aba '{tab_name}' não encontrada.", icon="🚨"); st.stop()
    except Exception as e: st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨"); st.stop()

# --- 3. Data Loading Functions ---
@st.cache_data(ttl=600)
def load_athlete_data():
    try:
        gspread_client = get_gspread_client(); worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATHLETES_TAB_NAME)
        df = pd.DataFrame(worksheet.get_all_records())
        if df.empty: return pd.DataFrame()
        df.columns = df.columns.str.strip()
        df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        for col_check in ["IMAGE", "NAME", "EVENT", "FIGHT NUMBER", "CORNER"]:
            if col_check not in df.columns: df[col_check] = ""
            df[col_check] = df[col_check].fillna("")
        return df
    except Exception as e: st.error(f"Erro ao carregar atletas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_transfer_checkin_data():
    try: 
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, DF_TRANSFERS_TAB_NAME)
        return pd.DataFrame(worksheet.get_all_records())
    except Exception as e: st.error(f"Erro ao carregar dados de check-in/transfer: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=300)
def load_users_data():
    try: gspread_client = get_gspread_client(); worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, USERS_TAB_NAME); return worksheet.get_all_records() or []
    except Exception as e: st.error(f"Erro ao carregar usuários: {e}", icon="🚨"); return []

def get_valid_user_info(user_input: str):
    if not user_input: return None
    all_users = load_users_data()
    proc_input = user_input.strip().upper()
    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip(); name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == proc_input or name_sheet == proc_input: return record
    return None

# --- 4. Data Writing Functions ---
def save_checkin_record(data: dict):
    try:
        gspread_client = get_gspread_client(); ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, DF_TRANSFERS_TAB_NAME)
        all_records = ws.get_all_records()
        df_checkin = pd.DataFrame(all_records)
        
        existing_row_index = -1
        if not df_checkin.empty and 'athlete_id' in df_checkin.columns and 'event' in df_checkin.columns:
            match = df_checkin[(df_checkin['athlete_id'].astype(str) == str(data['athlete_id'])) & (df_checkin['event'] == data['event'])]
            if not match.empty:
                existing_row_index = match.index[0]

        headers = ['check_in_id', 'athlete_id', 'athlete_name', 'event', 'bus_number', 
                   'passport_status', 'nails_status', 'cups_status', 'uniform_status', 'mouthguard_status',
                   'corner_1_status', 'corner_2_status', 'corner_3_status', 'notes',
                   'transfer_type', 'updated_by', 'updated_at', 'check_in_status']
        
        if existing_row_index != -1:
            row_to_update = existing_row_index + 2
            cell_range = f'B{row_to_update}:{chr(ord("A")+len(headers)-1)}{row_to_update}'
            update_values = [[str(data.get(h, "")) for h in headers if h != 'check_in_id']]
            ws.update(cell_range, update_values, value_input_option="USER_ENTERED")
            st.success(f"Check-in de {data['athlete_name']} atualizado!");
        else:
            next_id = int(df_checkin['check_in_id'].max()) + 1 if not df_checkin.empty and 'check_in_id' in df_checkin.columns and df_checkin['check_in_id'].notna().any() else 1
            data['check_in_id'] = next_id
            new_row = [data.get(h, "") for h in headers]
            ws.append_row(new_row, value_input_option="USER_ENTERED")
            st.success(f"Check-in de {data['athlete_name']} salvo com sucesso!");
        
        load_transfer_checkin_data.clear()
        time.sleep(1) # Pausa curta para ajudar na consistência
        return data # ATUALIZADO: Retorna os dados que foram salvos
    except Exception as e: st.error(f"Erro ao salvar check-in: {e}", icon="🚨"); return None


# --- Main Application Logic ---
st.title("UAEW | Transfer & Check-In")
default_ss = { "user_confirmed": False, "current_user_name": "User", "selected_event": "Todos os Eventos", "fighter_search_query": "", "selected_corner": "Todos os Corners" }
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k]=v

st.session_state['user_confirmed'] = True # Simplificado

if st.session_state.user_confirmed:
    st.header("Check-In e Atribuição de Atletas")
    
    df_athletes = load_athlete_data()
    df_checkin = load_transfer_checkin_data()

    c1, c2, c3, c4 = st.columns([0.25, 0.25, 0.3, 0.2])
    with c1: 
        event_list = ["Todos os Eventos"] + sorted([e for e in df_athletes["EVENT"].unique() if e and e != "Z"]) if not df_athletes.empty else []
        st.selectbox("Filtrar Evento:", options=event_list, key="selected_event")
    with c2: st.selectbox("Filtrar Corner:", ["Todos os Corners", "Red", "Blue"], key="selected_corner")
    with c3: st.text_input("Pesquisar Lutador:", placeholder="Digite nome ou ID...", key="fighter_search_query")
    with c4: st.markdown("<br>", True); st.button("🔄 Atualizar", on_click=lambda:(load_athlete_data.clear(), load_transfer_checkin_data.clear(), st.toast("Dados atualizados!")))

    st.markdown("---")

    df_filtered = df_athletes.copy()
    if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]
    if st.session_state.selected_corner != "Todos os Corners": df_filtered = df_filtered[df_filtered['CORNER'].str.lower() == st.session_state.selected_corner.lower()]
    if st.session_state.fighter_search_query:
        term = st.session_state.fighter_search_query.strip().lower()
        df_filtered = df_filtered[df_filtered.apply(lambda r: term in str(r['NAME']).lower() or term in str(r['ID']), axis=1)]

    if 'FIGHT NUMBER' in df_filtered.columns:
        df_filtered['FIGHT_NUMBER_NUM'] = pd.to_numeric(df_filtered['FIGHT NUMBER'], errors='coerce')
        df_filtered = df_filtered.sort_values(by='FIGHT_NUMBER_NUM', ascending=True, na_position='last')

    st.markdown(f"Exibindo **{len(df_filtered)}** atletas.")

    for i, row in df_filtered.iterrows():
        ath_id, ath_name, ath_event = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
        ath_fight_number, ath_corner_color = str(row.get("FIGHT NUMBER", "")), str(row.get("CORNER", ""))
        
        current_checkin = None
        if not df_checkin.empty and 'athlete_id' in df_checkin.columns and 'event' in df_checkin.columns:
            match = df_checkin[(df_checkin['athlete_id'].astype(str) == ath_id) & (df_checkin['event'] == ath_event)]
            if not match.empty: current_checkin = match.iloc[0].to_dict() # Use .to_dict() para facilitar a manipulação

        checkin_status = current_checkin.get('check_in_status', 'Pending') if current_checkin is not None else 'Pending'
        card_bg_col = "#1e1e1e"
        if checkin_status == 'Checked-In': card_bg_col = "#B08D00"
        elif checkin_status == 'Boarded': card_bg_col = "#143d14"

        # ... (código do card do atleta, que está correto)
        
        is_locked = checkin_status in ['Checked-In', 'Boarded']
        
        # ... (código dos widgets de check-in, que está correto)

        cols_bottom = st.columns([1, 2, 1])
        with cols_bottom[0]:
            bus_number_val = str(current_checkin.get('bus_number', '')) if current_checkin is not None else ""
            st.text_input("Ônibus", key=f"bus_number_{ath_id}", value=bus_number_val, disabled=is_locked)
        with cols_bottom[1]:
            notes_val = str(current_checkin.get('notes', '')) if current_checkin is not None else ""
            st.text_area("Notes", key=f"notes_{ath_id}", value=notes_val, height=100, disabled=is_locked)
        with cols_bottom[2]:
            st.markdown("<br>", unsafe_allow_html=True)
            if checkin_status == 'Boarded':
                st.success("Boarding Completo!")
            elif checkin_status == 'Checked-In':
                if st.button("Boarding", key=f"board_{ath_id}", use_container_width=True):
                    data_to_board = current_checkin
                    data_to_board.update({
                        'updated_by': st.session_state.get('current_user_name', 'System'),
                        'updated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        'check_in_status': "Boarded"
                    })
                    saved_data = save_checkin_record(data_to_board)
                    if saved_data:
                        # ATUALIZADO: Atualiza o DataFrame local
                        idx_to_update = df_checkin[(df_checkin['athlete_id'].astype(str) == ath_id) & (df_checkin['event'] == ath_event)].index
                        for col, value in saved_data.items():
                            if col in df_checkin.columns:
                                df_checkin.loc[idx_to_update, col] = value
                        st.rerun()
            else: # Status é 'Pending'
                if st.button("Salvar Status", key=f"save_{ath_id}", use_container_width=True):
                    transfer_type = st.session_state[f"transfer_type_{ath_id}"]
                    bus_number_to_save = st.session_state[f"bus_number_{ath_id}"] if transfer_type == "Bus" else ""
                    checkin_data = {
                        'athlete_id': ath_id, 'athlete_name': ath_name, 'event': ath_event, 'bus_number': bus_number_to_save,
                        'passport_status': st.session_state[f"passport_{ath_id}"], 'nails_status': st.session_state[f"nails_{ath_id}"],
                        'cups_status': st.session_state[f"cups_{ath_id}"], 'uniform_status': st.session_state[f"uniform_{ath_id}"],
                        'mouthguard_status': st.session_state[f"mouthguard_{ath_id}"],
                        'corner_1_status': st.session_state[f"c1_{ath_id}"], 'corner_2_status': st.session_state[f"c2_{ath_id}"], 'corner_3_status': st.session_state[f"c3_{ath_id}"],
                        'notes': st.session_state[f"notes_{ath_id}"], 'transfer_type': transfer_type,
                        'updated_by': st.session_state.get('current_user_name', 'System'),
                        'updated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        'check_in_status': "Checked-In"
                    }
                    saved_data = save_checkin_record(checkin_data)
                    if saved_data:
                        # ATUALIZADO: Atualiza ou adiciona a linha no DataFrame local
                        idx_to_update = df_checkin[(df_checkin['athlete_id'].astype(str) == ath_id) & (df_checkin['event'] == ath_event)].index
                        if not idx_to_update.empty:
                             for col, value in saved_data.items():
                                if col in df_checkin.columns:
                                    df_checkin.loc[idx_to_update, col] = value
                        else:
                             new_row_df = pd.DataFrame([saved_data])
                             df_checkin = pd.concat([df_checkin, new_row_df], ignore_index=True)
                        st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)
else:
    st.warning("Por favor, faça o login para continuar.")
