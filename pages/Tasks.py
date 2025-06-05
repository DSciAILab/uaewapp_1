# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import html

# --- 1. Page Configuration ---
st.set_page_config(page_title="Consulta e Registro de Atletas", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App" 
ATHLETES_TAB_NAME = "df" 
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"
NO_TASK_SELECTED_LABEL = "-- Selecione uma Tarefa --"

# --- 2. Google Sheets Connection (para gspread) ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas nos segredos. Necessárias para gspread.", icon="🚨")
            st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client
    except KeyError as e: 
        st.error(f"Erro de configuração: Chave da conta de serviço Google Cloud ausente em `st.secrets`. Detalhes: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à API do Google: {e}", icon="🚨")
        st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        worksheet = spreadsheet.worksheet(tab_name)
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada na planilha '{sheet_name}'.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨"); st.stop()

# --- 3. Data Loading and Preprocessing ---

# --- 3.1 Athlete Data (via gspread API) ---
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = MAIN_SHEET_NAME, athletes_tab_name: str = ATHLETES_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        athletes_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, athletes_tab_name)
        data = athletes_worksheet.get_all_records() # Retorna lista de dicionários
        
        if not data:
            # st.warning(f"Nenhum dado encontrado na aba de atletas '{athletes_tab_name}'.", icon="⚠️")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()

        # Verificar se as colunas principais existem
        if "ROLE" not in df.columns or "INACTIVE" not in df.columns:
            st.error(f"Colunas 'ROLE' ou 'INACTIVE' não encontradas na aba de atletas '{athletes_tab_name}'. Verifique os cabeçalhos.", icon="🚨")
            return pd.DataFrame()

        df.columns = df.columns.str.strip()
        
        # Converter INACTIVE para booleano
        if df["INACTIVE"].dtype == 'object': # Comum com gspread
            df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True) # '' (vazio) como True/Inactive
        elif pd.api.types.is_numeric_dtype(df["INACTIVE"]): # 0 ou 1
            df["INACTIVE"] = df["INACTIVE"].map({0: False, 1: True}).fillna(True)
        # Se já for booleano, não faz nada

        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        
        if "EVENT" not in df.columns: df["EVENT"] = "Z"
        else: df["EVENT"] = df["EVENT"].fillna("Z")

        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            if col in df.columns:
                # gspread pode retornar datas como strings, então a conversão é importante
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df[col] = df[col].dt.strftime("%d/%m/%Y").fillna("")
            else: df[col] = "" 

        for col_to_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE"]:
            if col_to_check not in df.columns: df[col_to_check] = ""
            else: df[col_to_check] = df[col_to_check].fillna("") # Garante que strings vazias ou NaN sejam ""
        
        if "NAME" not in df.columns:
            st.error(f"Coluna 'NAME' não encontrada na aba de atletas '{athletes_tab_name}'. Necessária para ordenação.", icon="🚨")
            return pd.DataFrame() # Retorna DF vazio se NAME é crucial
            
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar ou processar dados dos atletas via gspread: {e}", icon="🚨")
        return pd.DataFrame()

# --- 3.2 User Data (via gspread) ---
@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        users_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, users_tab_name)
        users_data = users_worksheet.get_all_records()
        return users_data if users_data else []
    except Exception as e:
        st.error(f"Erro ao carregar dados de usuários '{users_tab_name}': {e}", icon="🚨"); return []

def get_valid_user_info(user_ps_id_input: str, sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    if not user_ps_id_input: return None
    all_users = load_users_data(sheet_name, users_tab_name)
    if not all_users: return None
    processed_user_input = user_ps_id_input.strip().upper()
    validation_id_from_input = processed_user_input
    if processed_user_input.startswith("PS") and len(processed_user_input) > 2 and processed_user_input[2:].isdigit():
        validation_id_from_input = processed_user_input[2:]
    for user_record in all_users:
        ps_id_from_sheet = str(user_record.get("PS", "")).strip()
        user_name_from_sheet = str(user_record.get("USER", "")).strip().upper()
        if ps_id_from_sheet == validation_id_from_input or \
           ("PS" + ps_id_from_sheet) == processed_user_input or \
           user_name_from_sheet == processed_user_input or \
           ps_id_from_sheet == processed_user_input:
            return user_record
    return None

# --- 3.3 Config Data (via gspread) ---
@st.cache_data(ttl=600)
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        config_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, config_tab_name)
        data = config_worksheet.get_all_values()
        if not data or len(data) < 1:
            st.error(f"Aba '{config_tab_name}' vazia ou sem cabeçalho.", icon="🚨"); return [],[]
        df_config = pd.DataFrame(data[1:], columns=data[0])
        task_list = df_config["TaskList"].dropna().unique().tolist() if "TaskList" in df_config.columns else []
        task_status_list = df_config["TaskStatus"].dropna().unique().tolist() if "TaskStatus" in df_config.columns else []
        if not task_list: st.warning(f"'TaskList' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        if not task_status_list: st.warning(f"'TaskStatus' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        return task_list, task_status_list
    except Exception as e:
        st.error(f"Erro ao carregar config da aba '{config_tab_name}': {e}", icon="🚨"); return [], []

# --- 3.4 Attendance Data (via gspread) ---
@st.cache_data(ttl=120) # Cache menor para attendance
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        attendance_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, attendance_tab_name)
        records = attendance_worksheet.get_all_records()
        df_attendance = pd.DataFrame(records)
        expected_cols = ["#", "Athlete ID", "Name", "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected_cols:
            if col not in df_attendance.columns: df_attendance[col] = None
        return df_attendance
    except Exception as e:
        st.error(f"Erro ao carregar dados de presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

# --- 4. Logging Function (via gspread) ---
def registrar_log(athlete_id: str, athlete_name: str, athlete_event: str,
                  task_type: str, task_status: str, notes: str, user_id_for_log: str,
                  sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        log_sheet = connect_gsheet_tab(gspread_client_internal, sheet_name, attendance_tab_name)
        all_values = log_sheet.get_all_values()
        next_hash_num = 1
        if len(all_values) > 1: 
            try:
                if all_values[-1] and all_values[-1][0] and str(all_values[-1][0]).isdigit():
                    next_hash_num = int(all_values[-1][0]) + 1
                else: next_hash_num = len(all_values) 
            except (ValueError, IndexError): next_hash_num = len(all_values)
        elif len(all_values) == 1: next_hash_num = 1 
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        log_user_identifier = user_id_for_log 
        if st.session_state.get('user_confirmed') and st.session_state.get('current_user_name') != "Usuário":
            log_user_identifier = st.session_state['current_user_name']
        nova_linha = [str(next_hash_num), athlete_id, athlete_name, athlete_event, task_type, task_status, notes, log_user_identifier, timestamp]
        log_sheet.append_row(nova_linha, value_input_option="USER_ENTERED")
        st.success(f"'{task_type}' para {athlete_name} registrado como '{task_status}'.", icon="✍️")
        st.cache_data.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao registrar na planilha '{attendance_tab_name}': {e}", icon="🚨"); return False

# --- 5. Helper Function for Blood Test Expiration ---
def is_blood_test_expired(blood_test_date_str: str) -> bool:
    if not blood_test_date_str or pd.isna(blood_test_date_str): return True
    try:
        if isinstance(blood_test_date_str, pd.Timestamp): blood_test_date = blood_test_date_str.to_pydatetime()
        else: blood_test_date = datetime.strptime(str(blood_test_date_str), "%d/%m/%Y")
        return blood_test_date < (datetime.now() - timedelta(days=182))
    except ValueError: return True

# --- 6. Main Application Logic ---
st.title("Consulta e Registro de Atletas")

default_ss_keys = {
    "warning_message": None, "user_confirmed": False, "current_user_id": "", 
    "current_user_name": "Usuário", "current_user_image_url": "", 
    "show_personal_data": True, "selected_task": NO_TASK_SELECTED_LABEL, # Inicia sem tarefa
    "selected_statuses": [] 
}
for k_ss, v_ss in default_ss_keys.items():
    if k_ss not in st.session_state: st.session_state[k_ss] = v_ss
if 'user_id_input' not in st.session_state: 
    st.session_state['user_id_input'] = st.session_state['current_user_id']

with st.container(border=True):
    st.subheader("Identificação do Usuário")
    auth_col1, auth_col2 = st.columns([0.7, 0.3])
    with auth_col1:
        st.session_state['user_id_input'] = st.text_input("PS (ID de usuário) ou Nome", value=st.session_state['user_id_input'], max_chars=50, key="user_id_input_widget")
    with auth_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Confirmar Usuário", key="confirm_user_button", use_container_width=True, type="primary"):
            user_input_val = st.session_state['user_id_input'].strip()
            if user_input_val:
                user_info_val = get_valid_user_info(user_input_val)
                if user_info_val:
                    st.session_state.current_user_ps_id_internal = str(user_info_val.get("PS", user_input_val)).strip()
                    st.session_state.current_user_id = user_input_val 
                    st.session_state.current_user_name = str(user_info_val.get("USER", user_input_val)).strip()
                    st.session_state.current_user_image_url = str(user_info_val.get("USER_IMAGE", "")).strip()
                    st.session_state.user_confirmed = True; st.session_state.warning_message = None
                else: st.session_state.update({"user_confirmed": False, "current_user_image_url": "", "warning_message": f"⚠️ Usuário '{user_input_val}' não encontrado."})
            else: st.session_state.update({"warning_message": "⚠️ O ID/Nome do usuário não pode ser vazio.", "user_confirmed": False, "current_user_image_url": ""})

    if st.session_state.user_confirmed and st.session_state.current_user_name != "Usuário":
        user_name_disp = html.escape(st.session_state.current_user_name); user_id_disp = html.escape(st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id))
        user_image_disp_url = st.session_state.get('current_user_image_url', "")
        if user_image_disp_url: st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-top:10px;"><img src="{html.escape(user_image_disp_url, quote=True)}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;border:1px solid #555;"><div style="line-height:1.2;"><span style="font-weight:bold;">{user_name_disp}</span><br><span style="font-size:0.9em;color:#ccc;">PS: {user_id_disp}</span></div></div>""", unsafe_allow_html=True)
        else: st.success(f"Usuário '{user_name_disp}' (PS: {user_id_disp}) confirmado!", icon="✅")
    elif st.session_state.get('warning_message'): st.warning(st.session_state.warning_message, icon="🚨")
    else: st.info("ℹ️ Confirme seu ID/Nome de usuário para prosseguir.", icon="ℹ️")

    if st.session_state.user_confirmed and st.session_state.current_user_id.strip().upper() != st.session_state.user_id_input.strip().upper() and st.session_state.user_id_input.strip() != "":
        st.session_state.update({"user_confirmed": False, "warning_message": "⚠️ ID/Nome alterado. Confirme.", "current_user_image_url": "", "selected_task": NO_TASK_SELECTED_LABEL}); st.rerun() # Reseta tarefa selecionada

if st.session_state.user_confirmed and st.session_state.current_user_name != "Usuário":
    st.markdown("---")
    
    with st.spinner("Carregando configurações..."): TASK_LIST_DATA_RAW, TASK_STATUS_LIST_DATA = load_config_data()
    
    # Adiciona a opção "Selecione uma tarefa" no início da lista de tarefas
    TASK_LIST_FOR_SELECTBOX = [NO_TASK_SELECTED_LABEL] + TASK_LIST_DATA_RAW
    
    if not TASK_LIST_DATA_RAW: st.error("Lista de tarefas não carregada da 'Config'.", icon="🚨"); st.stop() # Verifica a lista original
    if not TASK_STATUS_LIST_DATA: TASK_STATUS_LIST_DATA = ["Pendente", "Requested", "Done", "Approved", "Rejected", "Issue"] 

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([0.4, 0.4, 0.2])
    with ctrl_col1: 
        # Garante que o valor inicial do selectbox seja NO_TASK_SELECTED_LABEL
        current_selection_index = 0 # Default to "Selecione..."
        if st.session_state.selected_task in TASK_LIST_FOR_SELECTBOX:
            current_selection_index = TASK_LIST_FOR_SELECTBOX.index(st.session_state.selected_task)

        st.session_state.selected_task = st.selectbox(
            "Tipo de verificação para REGISTRO:", options=TASK_LIST_FOR_SELECTBOX,
            index=current_selection_index, 
            key="task_selector_widget"
        )
    with ctrl_col2: 
        st.session_state.selected_statuses = st.multiselect(
            "Filtrar por Status da Tarefa:", options=TASK_STATUS_LIST_DATA,
            default=st.session_state.selected_statuses if st.session_state.selected_statuses else [], 
            key="status_multiselect_widget",
            disabled=(st.session_state.selected_task == NO_TASK_SELECTED_LABEL) # Desabilita se nenhuma tarefa selecionada
        )
    with ctrl_col3: 
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🔄 Atualizar Dados", key="refresh_data_main_button", help="Recarrega dados.", on_click=lambda: (st.cache_data.clear(), st.cache_resource.clear(), st.toast("Dados atualizados!", icon="🔄"), st.rerun()), use_container_width=True)

    st.session_state.show_personal_data = st.toggle("Mostrar Dados Pessoais", value=st.session_state.show_personal_data, key="toggle_personal_data_widget")
    st.markdown("---")

    with st.spinner("Carregando dados dos atletas..."): df_athletes_loaded = load_athlete_data()      
    with st.spinner("Carregando registros de atividades..."): df_attendance_loaded = load_attendance_data()

    actual_selected_task = st.session_state.selected_task if st.session_state.selected_task != NO_TASK_SELECTED_LABEL else None

    if df_athletes_loaded.empty: st.info("Nenhum dado de atleta para exibir.") 
    else:
        filtered_athletes_df = df_athletes_loaded.copy()
        # Só filtra se uma tarefa real e status forem selecionados
        if actual_selected_task and st.session_state.selected_statuses:
            task_to_filter_val = actual_selected_task
            statuses_to_filter_val = st.session_state.selected_statuses
            
            athletes_to_show_ids_set = set()
            df_attendance_for_filter = df_attendance_loaded.copy()
            if "Athlete ID" in df_attendance_for_filter.columns:
                 df_attendance_for_filter["Athlete ID"] = df_attendance_for_filter["Athlete ID"].astype(str)

            for _, athlete_row_filter in filtered_athletes_df.iterrows():
                athlete_id_filter = str(athlete_row_filter["ID"])
                relevant_attendance_records = pd.DataFrame()
                if "Athlete ID" in df_attendance_for_filter.columns and "Task" in df_attendance_for_filter.columns:
                    relevant_attendance_records = df_attendance_for_filter[(df_attendance_for_filter.get("Athlete ID") == athlete_id_filter) & (df_attendance_for_filter.get("Task") == task_to_filter_val)]
                
                if not relevant_attendance_records.empty:
                    if "Status" in relevant_attendance_records.columns and any(status in statuses_to_filter_val for status in relevant_attendance_records["Status"].unique()):
                        athletes_to_show_ids_set.add(athlete_id_filter)
                elif any(s in statuses_to_filter_val for s in ["Pendente", "---", "Não Registrado"]): 
                    athletes_to_show_ids_set.add(athlete_id_filter)
            filtered_athletes_df = filtered_athletes_df[filtered_athletes_df["ID"].astype(str).isin(list(athletes_to_show_ids_set))]
        
        st.markdown(f"Exibindo **{len(filtered_athletes_df)}** de **{len(df_athletes_loaded)}** atletas.")

        if not actual_selected_task:
            st.info("Selecione uma tarefa acima para ver as opções de registro e filtrar por status.", icon="ℹ️")

        for i_loop, row_data in filtered_athletes_df.iterrows():
            athlete_id_display, athlete_name_display, athlete_event_display = str(row_data["ID"]), str(row_data["NAME"]), str(row_data["EVENT"])
            current_task_status_display = "Status: Pendente / Não Registrado" # Default if no task selected or no records
            
            if actual_selected_task: # Só busca status se uma tarefa real estiver selecionada
                athlete_task_records_df = pd.DataFrame()
                if "Athlete ID" in df_attendance_loaded.columns and "Task" in df_attendance_loaded.columns:
                    df_att_task_check_disp = df_attendance_loaded.copy()
                    if "Athlete ID" in df_att_task_check_disp: df_att_task_check_disp["Athlete ID"] = df_att_task_check_disp["Athlete ID"].astype(str)
                    athlete_task_records_df = df_att_task_check_disp[(df_att_task_check_disp.get("Athlete ID") == athlete_id_display) & (df_att_task_check_disp.get("Task") == actual_selected_task)]
                if not athlete_task_records_df.empty and "Status" in athlete_task_records_df.columns:
                    latest_record_data = athlete_task_records_df.iloc[-1] 
                    try:
                        if "Timestamp" in athlete_task_records_df.columns:
                            # Use .loc para evitar SettingWithCopyWarning
                            athlete_task_records_df.loc[:, "Timestamp_dt"] = pd.to_datetime(athlete_task_records_df["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce')
                            latest_record_data = athlete_task_records_df.sort_values(by="Timestamp_dt", ascending=False).iloc[0]
                    except Exception: pass 
                    current_task_status_display = f"Status ({actual_selected_task}): **{latest_record_data.get('Status', 'N/A')}**"
                    if "Notes" in latest_record_data and pd.notna(latest_record_data['Notes']) and latest_record_data['Notes']:
                         current_task_status_display += f" (Notas: {html.escape(str(latest_record_data['Notes']))})"
            
            card_bg_color_val = "#1e1e1e" # Default
            if actual_selected_task: # Lógica de cor só se tarefa selecionada
                if not athlete_task_records_df.empty and "Status" in athlete_task_records_df.columns and "Done" in athlete_task_records_df["Status"].values: card_bg_color_val = "#143d14" 
                elif actual_selected_task == "Blood Test":
                    bt_date_str_card, has_bt_card = row_data.get("BLOOD TEST", ""), pd.notna(row_data.get("BLOOD TEST", "")) and str(row_data.get("BLOOD TEST", "")).strip() != ""
                    bt_expired_card = is_blood_test_expired(bt_date_str_card) if has_bt_card else True
                    if has_bt_card and not bt_expired_card: card_bg_color_val = "#3D3D00"
                    elif bt_expired_card or not has_bt_card: card_bg_color_val = "#4D1A00"
            
            passport_image_html_card = f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{html.escape(str(row_data.get("PASSPORT IMAGE", "")), quote=True)}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if pd.notna(row_data.get("PASSPORT IMAGE")) and row_data.get("PASSPORT IMAGE") else ""
            mobile_raw_card = str(row_data.get("MOBILE", "")).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            whatsapp_html_card = ""
            if mobile_raw_card:
                mob_proc_card = ("+" + mobile_raw_card[2:]) if mobile_raw_card.startswith("00") else ("+971" + mobile_raw_card.lstrip("0")) if len(mobile_raw_card) >= 9 and not mobile_raw_card.startswith("971") and not mobile_raw_card.startswith("+") else ("+" + mobile_raw_card) if not mobile_raw_card.startswith("+") else mobile_raw_card
                if mob_proc_card.startswith("+"): whatsapp_html_card = f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{html.escape(mob_proc_card.replace("+", ""), quote=True)}' target='_blank' style='color:#00BFFF;'>Enviar Mensagem</a></td></tr>"
            bt_date_str_html, bt_is_expired_html = str(row_data.get("BLOOD TEST", "")), is_blood_test_expired(str(row_data.get("BLOOD TEST", "")))
            blood_test_html_card = f"<tr style='color:{"red" if bt_is_expired_html else "#A0F0A0"};'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>{html.escape(bt_date_str_html)}{f'<span style="font-weight:bold;">(Expirado)</span>' if bt_is_expired_html else ''}</td></tr>" if bt_date_str_html else "<tr style='color:orange;'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>Não Registrado</td></tr>"
            personal_data_table_html_content = f"""<div style='flex-basis:350px;flex-grow:1;'><table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'><tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row_data.get("GENDER","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row_data.get("DOB","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row_data.get("NATIONALITY","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row_data.get("PASSPORT","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row_data.get("PASSPORT EXPIRE DATE","")))}</td></tr>{passport_image_html_card}{whatsapp_html_card}{blood_test_html_card}</table></div>""" if st.session_state.show_personal_data else "<div style='flex-basis:300px;flex-grow:1;font-style:italic;color:#ccc;font-size:13px;text-align:center;'>Dados pessoais ocultos.</div>"
            st.markdown(f"""<div style='background-color:{card_bg_color_val};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'><div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'><div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'><img src='{html.escape(row_data.get("IMAGE", "https://via.placeholder.com/80?text=No+Image") if pd.notna(row_data.get("IMAGE")) and row_data.get("IMAGE") else "https://via.placeholder.com/80?text=No+Image", quote=True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'><div><h4 style='margin:0;'>{html.escape(athlete_name_display)}</h4><p style='margin:0;font-size:14px;color:#cccccc;'>{html.escape(athlete_event_display)}</p><p style='margin:0;font-size:13px;color:#cccccc;'>ID: {html.escape(athlete_id_display)}</p><p style='margin:0;font-size:13px;color:#a0f0a0;'><i>{current_task_status_display}</i></p></div></div>{personal_data_table_html_content}</div></div>""", unsafe_allow_html=True)

            if actual_selected_task: # Só mostra botões de ação se uma tarefa real estiver selecionada
                music_link_keys_list = [f"music_link_1_{athlete_id_display}", f"music_link_2_{athlete_id_display}", f"music_link_3_{athlete_id_display}"]
                for key_music_link in music_link_keys_list:
                    if key_music_link not in st.session_state: st.session_state[key_music_link] = ""
                
                if actual_selected_task == "Walkout Music":
                    st.markdown("##### Links para Walkout Music:")
                    st.session_state[music_link_keys_list[0]] = st.text_input(f"Música 1 (YouTube)", value=st.session_state[music_link_keys_list[0]], key=f"music1_input_{athlete_id_display}_{i_loop}", placeholder="Link YouTube")
                    st.session_state[music_link_keys_list[1]] = st.text_input(f"Música 2 (YouTube)", value=st.session_state[music_link_keys_list[1]], key=f"music2_input_{athlete_id_display}_{i_loop}", placeholder="Link YouTube")
                    st.session_state[music_link_keys_list[2]] = st.text_input(f"Música 3 (YouTube)", value=st.session_state[music_link_keys_list[2]], key=f"music3_input_{athlete_id_display}_{i_loop}", placeholder="Link YouTube")
                    if st.button(f"Registrar Músicas para {athlete_name_display}", key=f"register_music_button_{athlete_id_display}_{i_loop}", type="primary", use_container_width=True):
                        any_music_registered = False
                        for idx_music, link_url_music in enumerate([st.session_state[k_m] for k_m in music_link_keys_list]):
                            if link_url_music and link_url_music.strip():
                                user_identifier_for_log = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
                                if registrar_log(athlete_id_display, athlete_name_display, athlete_event_display, "Walkout Music", "Done", link_url_music.strip(), user_identifier_for_log):
                                    any_music_registered = True; st.session_state[music_link_keys_list[idx_music]] = "" 
                        if any_music_registered: st.rerun() 
                        else: st.warning("Nenhum link de música válido fornecido.", icon="⚠️")
                else: 
                    is_task_already_done = False
                    if not athlete_task_records_df.empty and "Status" in athlete_task_records_df.columns and "Done" in athlete_task_records_df["Status"].values: is_task_already_done = True
                    button_label_task, button_type_task = (f"'{actual_selected_task}' JÁ CONCLUÍDO (Refazer?)", "secondary") if is_task_already_done else (f"Marcar '{actual_selected_task}' como CONCLUÍDO", "primary")
                    if st.button(button_label_task, key=f"mark_done_button_{athlete_id_display}_{actual_selected_task.replace(' ', '_')}_{i_loop}", type=button_type_task, use_container_width=True):
                        user_identifier_for_log = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
                        registrar_log(athlete_id_display, athlete_name_display, athlete_event_display, actual_selected_task, "Done", "", user_identifier_for_log); st.rerun() 
            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>", unsafe_allow_html=True)
else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):
         st.warning("🚨 Confirme seu ID/Nome de usuário para acessar.", icon="🚨")
