# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Transfer & Check-In", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
USERS_TAB_NAME = "Users"
TRANSFERS_TAB_NAME = "df [Transfers]" # ATUALIZADO: Nome da aba corrigido
CHECKIN_TAB_NAME = "Check_In"

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
        for col_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE", "GENDER", "NAME", "EVENT"]:
            if col_check not in df.columns: df[col_check] = ""
            df[col_check] = df[col_check].fillna("")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e: st.error(f"Erro ao carregar atletas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_transfers_data():
    try: gspread_client = get_gspread_client(); worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, TRANSFERS_TAB_NAME); return pd.DataFrame(worksheet.get_all_records())
    except Exception as e: st.error(f"Erro ao carregar transfers: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_checkin_data():
    try: gspread_client = get_gspread_client(); worksheet = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, CHECKIN_TAB_NAME); return pd.DataFrame(worksheet.get_all_records())
    except Exception as e: st.error(f"Erro ao carregar dados de check-in: {e}", icon="🚨"); return pd.DataFrame()

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
def add_transfer_record(data: dict):
    try:
        gspread_client = get_gspread_client(); ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, TRANSFERS_TAB_NAME)
        all_vals = ws.get_all_values()
        next_id = int(all_vals[-1][0]) + 1 if len(all_vals) > 1 and str(all_vals[-1][0]).isdigit() else len(all_vals) + 1
        
        # ATUALIZADO: Nova estrutura de colunas
        headers = ['transfer_record_id', 'event', 'bus_number', 'dept_date', 'dept_time', 'task', 'updated_by_user', 'updated_at', 'status']
        
        data['transfer_record_id'] = next_id
        new_row = [data.get(h, "") for h in headers]
        
        ws.append_row(new_row, value_input_option="USER_ENTERED")
        st.success(f"Transfer '{data['bus_number']}' para o evento '{data['event']}' adicionado com sucesso!"); 
        load_transfers_data.clear()
        return True
    except Exception as e: st.error(f"Erro ao adicionar transfer: {e}", icon="🚨"); return False

def save_checkin_record(data: dict):
    # (Esta função permanece a mesma, pois já é robusta)
    try:
        gspread_client = get_gspread_client(); ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, CHECKIN_TAB_NAME)
        all_records = ws.get_all_records()
        df_checkin = pd.DataFrame(all_records)
        
        existing_row_index = -1
        if not df_checkin.empty and 'athlete_id' in df_checkin.columns and 'event' in df_checkin.columns:
            match = df_checkin[(df_checkin['athlete_id'].astype(str) == str(data['athlete_id'])) & (df_checkin['event'] == data['event'])]
            if not match.empty:
                existing_row_index = match.index[0]

        headers = ['check_in_id', 'athlete_id', 'athlete_name', 'event', 'assigned_transfer_id', 'passport', 'nails', 'cups', 'uniform', 'corners', 'transfer_type', 'updated_by', 'updated_at']
        
        if existing_row_index != -1:
            row_to_update = existing_row_index + 2
            cell_range = f'B{row_to_update}:M{row_to_update}'
            update_values = [[data.get(h, "") for h in headers if h != 'check_in_id']]
            ws.update(cell_range, update_values, value_input_option="USER_ENTERED")
            st.success(f"Check-in de {data['athlete_name']} atualizado!");
        else:
            next_id = int(df_checkin['check_in_id'].max()) + 1 if not df_checkin.empty and 'check_in_id' in df_checkin.columns and df_checkin['check_in_id'].notna().any() else 1
            data['check_in_id'] = next_id
            new_row = [data.get(h, "") for h in headers]
            ws.append_row(new_row, value_input_option="USER_ENTERED")
            st.success(f"Check-in de {data['athlete_name']} salvo com sucesso!");
        
        load_checkin_data.clear()
        return True
    except Exception as e: st.error(f"Erro ao salvar check-in: {e}", icon="🚨"); return False

# --- 5. Page Rendering Functions ---
def page_gerenciar_transfers():
    st.header("Gerenciar Transfers")
    
    df_athletes = load_athlete_data()
    event_list = sorted([e for e in df_athletes["EVENT"].unique() if e and e != "Z"]) if not df_athletes.empty else []

    with st.form("new_transfer_form", clear_on_submit=True):
        st.subheader("Adicionar Novo Transfer")
        
        # ATUALIZADO: Novos campos no formulário
        cols = st.columns(2)
        with cols[0]:
            bus_number = st.text_input("Número/Nome do Ônibus", help="Ex: Ônibus 01, Van Aeroporto")
            event = st.selectbox("Evento Associado", event_list, index=0 if event_list else None)
            task = st.text_input("Tarefa/Rota", help="Ex: Hotel > Arena (Manhã)")
        with cols[1]:
            dept_date = st.date_input("Data de Partida")
            dept_time = st.time_input("Horário de Partida")
            status = st.selectbox("Status", ["Active", "Inactive"])
            
        submitted = st.form_submit_button("Adicionar Transfer", use_container_width=True)
        if submitted and bus_number and event and task:
            transfer_data = {
                "bus_number": bus_number,
                "event": event,
                "dept_date": dept_date.strftime("%d/%m/%Y"),
                "dept_time": dept_time.strftime("%H:%M"),
                "task": task,
                "status": status,
                "updated_by_user": st.session_state.get('current_user_name', 'System'),
                "updated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
            add_transfer_record(transfer_data)
    
    st.markdown("---")
    st.subheader("Lista de Transfers Cadastrados")
    df_transfers = load_transfers_data()
    if not df_transfers.empty:
        st.dataframe(df_transfers, use_container_width=True)
    else:
        st.info("Nenhum transfer cadastrado.")

def page_checkin_atletas():
    st.header("Check-In e Atribuição de Atletas")
    
    df_athletes = load_athlete_data()
    df_transfers = load_transfers_data()
    df_checkin = load_checkin_data()

    c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
    with c1: 
        event_list = ["Todos os Eventos"] + sorted([e for e in df_athletes["EVENT"].unique() if e and e != "Z"]) if not df_athletes.empty else []
        st.selectbox("Filtrar Evento:", options=event_list, key="selected_event")
    with c2: st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")
    with c3: st.markdown("<br>", True); st.button("🔄 Atualizar", on_click=lambda:(load_athlete_data.clear(), load_transfers_data.clear(), load_checkin_data.clear(), st.toast("Dados atualizados!")))

    df_filtered = df_athletes.copy()
    if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]
    if st.session_state.fighter_search_query:
        term = st.session_state.fighter_search_query.strip().lower()
        df_filtered = df_filtered[df_filtered.apply(lambda r: term in str(r['NAME']).lower() or term in str(r['ID']), axis=1)]

    st.markdown(f"Exibindo **{len(df_filtered)}** atletas.")

    for i, row in df_filtered.iterrows():
        ath_id, ath_name, ath_event = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
        
        st.markdown(f"""
        <div style='background-color:#1e1e1e;padding:15px;border-radius:10px;margin-bottom:10px;display:flex;align-items:center;gap:15px;'>
            <img src='{html.escape(row.get("IMAGE",""))}' style='width:60px;height:60px;border-radius:50%;object-fit:cover;'>
            <div><h5 style='margin:0;'>{html.escape(ath_name)}</h5><small style='color:#ccc;'>ID: {html.escape(ath_id)} | Evento: {html.escape(ath_event)}</small></div>
        </div>""", unsafe_allow_html=True)

        current_checkin = None
        if not df_checkin.empty:
            match = df_checkin[(df_checkin['athlete_id'].astype(str) == ath_id) & (df_checkin['event'] == ath_event)]
            if not match.empty: current_checkin = match.iloc[0]

        # ATUALIZADO: Cria a lista de opções de transfer com a nova descrição detalhada
        active_transfers_for_event = df_transfers[(df_transfers['status'] == 'Active') & (df_transfers['event'] == ath_event)] if not df_transfers.empty else pd.DataFrame()
        transfer_options = {
            row['transfer_record_id']: f"{row['bus_number']} | {row['dept_date']} {row['dept_time']} | {row['task']}" 
            for index, row in active_transfers_for_event.iterrows()
        }
        transfer_options_list = ["-- Nenhum --"] + list(transfer_options.values())

        cols = st.columns([1, 1, 1, 1, 2, 2])
        with cols[0]:
            st.checkbox("Passport", key=f"passport_{ath_id}", value=current_checkin is not None and current_checkin.get('passport') == 'TRUE')
            st.checkbox("Nails", key=f"nails_{ath_id}", value=current_checkin is not None and current_checkin.get('nails') == 'TRUE')
        with cols[1]:
            st.checkbox("Cups", key=f"cups_{ath_id}", value=current_checkin is not None and current_checkin.get('cups') == 'TRUE')
            st.checkbox("Uniform", key=f"uniform_{ath_id}", value=current_checkin is not None and current_checkin.get('uniform') == 'TRUE')
        with cols[2]:
            corners_val = int(current_checkin['corners']) if current_checkin is not None and str(current_checkin.get('corners')).isdigit() else 1
            st.selectbox("Corners", [1, 2, 3], key=f"corners_{ath_id}", index=corners_val - 1)
        with cols[3]:
            transfer_type_val = current_checkin['transfer_type'] if current_checkin is not None and current_checkin.get('transfer_type') else "Bus"
            st.selectbox("Transporte", ["Bus", "Own Transport"], key=f"transfer_type_{ath_id}", index=["Bus", "Own Transport"].index(transfer_type_val))
        with cols[4]:
            assigned_id_str = str(current_checkin['assigned_transfer_id']) if current_checkin is not None else None
            current_selection = next((desc for id, desc in transfer_options.items() if str(id) == assigned_id_str), "-- Nenhum --")
            st.selectbox("Atribuir Transfer", transfer_options_list, key=f"assigned_transfer_{ath_id}", index=transfer_options_list.index(current_selection))
        with cols[5]:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Salvar Status", key=f"save_{ath_id}", use_container_width=True):
                selected_transfer_desc = st.session_state[f"assigned_transfer_{ath_id}"]
                assigned_transfer_id = [id for id, desc in transfer_options.items() if desc == selected_transfer_desc]
                
                checkin_data = {
                    'athlete_id': ath_id, 'athlete_name': ath_name, 'event': ath_event,
                    'assigned_transfer_id': assigned_transfer_id[0] if assigned_transfer_id else "",
                    'passport': st.session_state[f"passport_{ath_id}"], 'nails': st.session_state[f"nails_{ath_id}"],
                    'cups': st.session_state[f"cups_{ath_id}"], 'uniform': st.session_state[f"uniform_{ath_id}"],
                    'corners': st.session_state[f"corners_{ath_id}"], 'transfer_type': st.session_state[f"transfer_type_{ath_id}"],
                    'updated_by': st.session_state.get('current_user_name', 'System'),
                    'updated_at': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }
                save_checkin_record(checkin_data)

        st.markdown("<hr>", unsafe_allow_html=True)


# --- Main App ---
if 'user_confirmed' not in st.session_state: st.session_state['user_confirmed'] = False

st.session_state['user_confirmed'] = True # Simplificado

if st.session_state.user_confirmed:
    st.sidebar.title("Navegação")
    page_options = ["Check-In de Atletas", "Gerenciar Transfers"]
    page = st.sidebar.selectbox("Escolha a página", page_options, key="page_selection")

    if page == "Check-In de Atletas":
        page_checkin_atletas()
    elif page == "Gerenciar Transfers":
        page_gerenciar_transfers()
else:
    st.warning("Por favor, faça o login para continuar.")
