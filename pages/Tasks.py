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
MAIN_SHEET_NAME = "UAEW_App" # CONFIRME O NOME DA SUA PLANILHA PRINCIPAL
ATHLETES_TAB_NAME = "df"
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"

# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client
    except KeyError as e:
        st.error(f"Configuration error: Missing Google Cloud service account key in `st.secrets`. Details: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Error connecting to Google API: {e}", icon="🚨")
        st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        worksheet = spreadsheet.worksheet(tab_name)
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨")
        st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada na planilha '{sheet_name}'.", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨")
        st.stop()

# --- 3. Data Loading and Preprocessing ---

# --- 3.1 Athlete Data ---
@st.cache_data(ttl=600)
def load_athlete_data():
    if 'google_sheet_id' not in st.secrets:
        st.error("Erro: `google_sheet_id` não encontrado nos segredos do Streamlit. Necessário para carregar dados dos atletas.")
        return pd.DataFrame()
    url = f"https://docs.google.com/spreadsheets/d/{st.secrets['google_sheet_id']}/gviz/tq?tqx=out:csv&sheet={ATHLETES_TAB_NAME}"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z")
        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].dt.strftime("%d/%m/%Y").fillna("")
        for col_to_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE"]:
            if col_to_check not in df.columns: df[col_to_check] = ""
            df[col_to_check] = df[col_to_check].fillna("")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading or processing athlete data from URL: {e}", icon="🚨")
        return pd.DataFrame()

# --- 3.2 User Data ---
@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        users_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, users_tab_name)
        users_data = users_worksheet.get_all_records()
        if not users_data: return []
        return users_data
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba de usuários '{users_tab_name}': {e}", icon="🚨")
        return []

def get_valid_user_info(user_ps_id_input: str, sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    if not user_ps_id_input: return None
    all_users = load_users_data(sheet_name, users_tab_name)
    if not all_users: return None
    processed_user_input = user_ps_id_input.strip().upper()
    validation_id_from_input = processed_user_input
    if processed_user_input.startswith("PS"):
        if len(processed_user_input) > 2 and processed_user_input[2:].isdigit():
            validation_id_from_input = processed_user_input[2:]
    elif not processed_user_input.isdigit():
        return None
    for user_record in all_users:
        ps_id_from_sheet = str(user_record.get("PS", "")).strip()
        if ps_id_from_sheet == validation_id_from_input:
            return user_record
    return None

# --- 3.3 Config Data (TaskList, TaskStatus) ---
@st.cache_data(ttl=600)
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        config_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, config_tab_name)
        data = config_worksheet.get_all_values()
        if not data or len(data) < 1:
            st.error(f"Aba de configuração '{config_tab_name}' está vazia ou não tem cabeçalho.", icon="🚨")
            return [],[]
        df_config = pd.DataFrame(data[1:], columns=data[0])
        task_list = []
        if "TaskList" in df_config.columns:
            task_list = df_config["TaskList"].dropna().unique().tolist()
        else:
            st.warning(f"Coluna 'TaskList' não encontrada na aba '{config_tab_name}'.", icon="⚠️")
        task_status_list = []
        if "TaskStatus" in df_config.columns:
            task_status_list = df_config["TaskStatus"].dropna().unique().tolist()
        else:
            st.warning(f"Coluna 'TaskStatus' não encontrada na aba '{config_tab_name}'.", icon="⚠️")
        return task_list, task_status_list
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba de configuração '{config_tab_name}': {e}", icon="🚨")
        return [], []

# --- 3.4 Attendance Data ---
@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        attendance_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, attendance_tab_name)
        records = attendance_worksheet.get_all_records()
        df_attendance = pd.DataFrame(records)
        expected_cols = ["#", "Athlete ID", "Name", "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected_cols:
            if col not in df_attendance.columns:
                df_attendance[col] = None
        return df_attendance
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba de presença '{attendance_tab_name}': {e}", icon="🚨")
        return pd.DataFrame()

# --- 4. Logging Function ---
def registrar_log(athlete_id: str, athlete_name: str, athlete_event: str,
                  task_type: str, task_status: str, notes: str, user_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        log_sheet = connect_gsheet_tab(gspread_client_internal, sheet_name, attendance_tab_name)
        all_values = log_sheet.get_all_values()
        next_hash_num = 1
        if len(all_values) > 1:
            try:
                if all_values[-1] and all_values[-1][0] != '':
                    last_hash_num = int(all_values[-1][0])
                    next_hash_num = last_hash_num + 1
                else:
                    next_hash_num = len(all_values)
            except (ValueError, IndexError):
                 next_hash_num = len(all_values)
        elif len(all_values) == 1:
            next_hash_num = 1
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        nova_linha = [
            str(next_hash_num), athlete_id, athlete_name, athlete_event,
            task_type, task_status, notes, user_id, timestamp
        ]
        log_sheet.append_row(nova_linha, value_input_option="USER_ENTERED")
        st.success(f"'{task_type}' para {athlete_name} registrado como '{task_status}'.", icon="✍️")
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar na planilha '{attendance_tab_name}': {e}", icon="🚨")
        return False

# --- 5. Helper Function for Blood Test Expiration ---
def is_blood_test_expired(blood_test_date_str: str) -> bool:
    if not blood_test_date_str: return True
    try:
        blood_test_date = datetime.strptime(blood_test_date_str, "%d/%m/%Y")
        return blood_test_date < (datetime.now() - timedelta(days=182))
    except ValueError: return True

# --- 6. Main Application Logic ---
st.title("Consulta e Registro de Atletas")

default_session_state = {
    "warning_message": None, "user_confirmed": False,
    "current_user_id": "", "current_user_name": "Usuário",
    "current_user_image_url": "",
    "show_personal_data": True,
    "selected_task": None, "selected_statuses": [],
}
for key, default_val in default_session_state.items():
    if key not in st.session_state: st.session_state[key] = default_val

if 'user_id_input' not in st.session_state:
    st.session_state['user_id_input'] = st.session_state['current_user_id']

with st.container(border=True):
    st.subheader("Identificação do Usuário")
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        st.session_state['user_id_input'] = st.text_input(
            "Informe seu PS (ID de usuário)", value=st.session_state['user_id_input'],
            max_chars=15, help="Seu ID de usuário para registrar.", key="user_id_input_field"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Confirmar Usuário", key="confirm_user_btn", use_container_width=True, type="primary"):
            user_input_stripped = st.session_state['user_id_input'].strip()
            if user_input_stripped:
                user_info = get_valid_user_info(user_input_stripped)
                if user_info:
                    st.session_state['current_user_id'] = user_input_stripped
                    st.session_state['current_user_name'] = str(user_info.get("USER", user_input_stripped)).strip()
                    st.session_state['current_user_image_url'] = str(user_info.get("USER_IMAGE", "")).strip()
                    st.session_state['user_confirmed'] = True
                    st.session_state['warning_message'] = None
                else:
                    st.session_state['user_confirmed'] = False; st.session_state['current_user_image_url'] = ""
                    st.session_state['warning_message'] = f"⚠️ Usuário '{user_input_stripped}' não encontrado."
            else:
                st.session_state['warning_message'] = "⚠️ O ID do usuário não pode ser vazio."; st.session_state['user_confirmed'] = False; st.session_state['current_user_image_url'] = ""

    if st.session_state['user_confirmed'] and st.session_state['current_user_id']:
        user_name_display = html.escape(st.session_state['current_user_name'])
        user_id_display = html.escape(st.session_state['current_user_id'])
        user_image_url = st.session_state.get('current_user_image_url', "")
        greeting_html = ""
        if user_image_url:
            safe_image_url = html.escape(user_image_url, quote=True)
            greeting_html = f"""<div style="display: flex; align-items: center; gap: 10px; margin-top:10px;"><img src="{safe_image_url}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover; border: 1px solid #555;"><div style="line-height: 1.2;"><span style="font-weight: bold;">{user_name_display}</span><br><span style="font-size: 0.9em; color: #ccc;">PS: {user_id_display}</span></div></div>"""
            st.markdown(greeting_html, unsafe_allow_html=True)
        else:
            st.success(f"Usuário '{user_name_display}' (PS: {user_id_display}) confirmado!", icon="✅")
    elif st.session_state.get('warning_message'):
        st.warning(st.session_state['warning_message'], icon="🚨")
    else:
        st.info("ℹ️ Por favor, confirme seu ID de usuário para prosseguir.", icon="ℹ️")

    if st.session_state['user_confirmed'] and \
    st.session_state['current_user_id'].strip().upper() != st.session_state['user_id_input'].strip().upper() and \
    st.session_state['user_id_input'].strip() != "":
        st.session_state['user_confirmed'] = False; st.session_state['warning_message'] = "⚠️ ID alterado. Confirme novamente."; st.session_state['current_user_image_url'] = ""; st.rerun()

if st.session_state['user_confirmed'] and st.session_state['current_user_id']:
    st.markdown("---")
    TASK_LIST, TASK_STATUS_LIST = load_config_data()
    if not TASK_LIST:
        st.error("Lista de tarefas não carregada da 'Config'. Verifique.", icon="🚨"); st.stop()
    if not TASK_STATUS_LIST: TASK_STATUS_LIST = ["Pendente", "Requested", "Done", "Approved", "Rejected", "Issue"]

    col_control1, col_control2, col_control3 = st.columns([0.4, 0.4, 0.2])
    with col_control1:
        st.session_state.selected_task = st.selectbox(
            "Tipo de verificação para REGISTRO:", options=TASK_LIST,
            index=TASK_LIST.index(st.session_state.selected_task) if st.session_state.selected_task and st.session_state.selected_task in TASK_LIST else 0,
            key="task_selector")
    with col_control2:
        st.session_state.selected_statuses = st.multiselect(
            "Filtrar por Status da Tarefa:", options=TASK_STATUS_LIST,
            default=st.session_state.selected_statuses if st.session_state.selected_statuses else [],
            key="status_multiselect")
    with col_control3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar Dados", key="refresh_data_button", help="Recarrega dados.", use_container_width=True):
            st.cache_data.clear(); st.cache_resource.clear(); st.toast("Dados atualizados!", icon="🔄"); st.rerun()

    st.session_state.show_personal_data = st.toggle("Mostrar Dados Pessoais do Atleta", value=st.session_state.show_personal_data, key="toggle_personal_data")
    st.markdown("---")

    with st.spinner("Carregando atletas..."): df_athletes = load_athlete_data()
    with st.spinner("Carregando registros..."): df_attendance = load_attendance_data()

    if df_athletes.empty:
        st.info("Nenhum atleta para exibir.")
    else:
        filtered_athletes = df_athletes.copy()
        task_to_filter = st.session_state.selected_task
        statuses_to_filter = st.session_state.selected_statuses

        if task_to_filter and statuses_to_filter:
            athletes_to_show_ids = set()
            df_attendance_str_id = df_attendance.copy()
            if "Athlete ID" in df_attendance_str_id.columns:
                 df_attendance_str_id["Athlete ID"] = df_attendance_str_id["Athlete ID"].astype(str)
            for index, athlete_row in filtered_athletes.iterrows():
                athlete_id = str(athlete_row["ID"])
                relevant_attendance = pd.DataFrame()
                if "Athlete ID" in df_attendance_str_id.columns and "Task" in df_attendance_str_id.columns:
                    relevant_attendance = df_attendance_str_id[
                        (df_attendance_str_id["Athlete ID"] == athlete_id) &
                        (df_attendance_str_id["Task"] == task_to_filter)]
                if not relevant_attendance.empty:
                    if "Status" in relevant_attendance.columns and any(status in statuses_to_filter for status in relevant_attendance["Status"].unique()):
                        athletes_to_show_ids.add(athlete_id)
                elif any(s in statuses_to_filter for s in ["Pendente", "---", "Não Registrado"]):
                    athletes_to_show_ids.add(athlete_id)
            filtered_athletes = filtered_athletes[filtered_athletes["ID"].astype(str).isin(list(athletes_to_show_ids))]
        
        st.markdown(f"Exibindo **{len(filtered_athletes)}** de **{len(df_athletes)}** atletas.")

        for i, row in filtered_athletes.iterrows():
            athlete_id_str = str(row["ID"])
            athlete_name = str(row["NAME"])
            athlete_event = str(row["EVENT"])
            current_task_status_info = "Status: Pendente / Não Registrado"
            athlete_task_records = pd.DataFrame()
            if "Athlete ID" in df_attendance.columns and "Task" in df_attendance.columns:
                df_attendance_task_check = df_attendance.copy()
                df_attendance_task_check["Athlete ID"] = df_attendance_task_check["Athlete ID"].astype(str)
                athlete_task_records = df_attendance_task_check[
                    (df_attendance_task_check["Athlete ID"] == athlete_id_str) &
                    (df_attendance_task_check["Task"] == st.session_state.selected_task)]
            if not athlete_task_records.empty and "Status" in athlete_task_records.columns:
                latest_record = athlete_task_records.sort_values(by="Timestamp", ascending=False).iloc[0]
                current_task_status_info = f"Status Atual: **{latest_record['Status']}**"
                if "Notes" in latest_record and pd.notna(latest_record['Notes']) and latest_record['Notes']:
                     current_task_status_info += f" (Notas: {html.escape(str(latest_record['Notes']))})"
            card_bg_color = "#1e1e1e"
            if not athlete_task_records.empty and "Status" in athlete_task_records.columns and "Done" in athlete_task_records["Status"].values:
                 card_bg_color = "#143d14" 
            elif st.session_state.selected_task == "Blood Test":
                bt_date_str = row.get("BLOOD TEST", ""); has_bt = pd.notna(bt_date_str) and str(bt_date_str).strip() != ""
                bt_expired = is_blood_test_expired(bt_date_str) if has_bt else True
                if has_bt and not bt_expired: card_bg_color = "#3D3D00"
                elif bt_expired or not has_bt: card_bg_color = "#4D1A00"
            
            st.markdown(f"""
            <div style='background-color:{card_bg_color}; padding:20px; border-radius:10px; margin-bottom:15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);'>
                <div style='display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:20px;'>
                    <div style='display:flex; align-items:center; gap:15px; flex-basis: 300px; flex-grow: 1;'>
                        <img src='{html.escape(row["IMAGE"] if pd.notna(row["IMAGE"]) and row["IMAGE"] else "https://via.placeholder.com/80?text=No+Image", quote=True)}'
                             style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                        <div>
                            <h4 style='margin:0;'>{html.escape(athlete_name)}</h4>
                            <p style='margin:0; font-size:14px; color:#cccccc;'>{html.escape(athlete_event)}</p>
                            <p style='margin:0; font-size:13px; color:#cccccc;'>ID: {html.escape(athlete_id_str)}</p>
                            <p style='margin:0; font-size:13px; color:#a0f0a0;'><i>{current_task_status_info}</i></p>
                        </div>
                    </div>
                    {f'''<div style='flex-basis: 350px; flex-grow: 1;'>
                        <table style='font-size:14px; color:white; border-collapse:collapse; width:100%;'>
                            <tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER", ""))) }</td></tr>
                            <tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB", ""))) }</td></tr>
                            <tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY", ""))) }</td></tr>
                            <tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT", ""))) }</td></tr>
                            <tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE", ""))) }</td></tr>
                            {"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='"+html.escape(str(row.get("PASSPORT IMAGE","")),quote=True)+"' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if pd.notna(row.get("PASSPORT IMAGE")) and row.get("PASSPORT IMAGE") else ""}
                            {(lambda m: "<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/"+html.escape(m.replace("+",""),quote=True)+"' target='_blank' style='color:#00BFFF;'>Enviar Mensagem</a></td></tr>" if m else "")((lambda raw: ("+" + raw[2:] if raw.startswith("00") else ("+971" + raw.lstrip("0") if len(raw) >= 9 and not raw.startswith("971") and not raw.startswith("+") else ("+" + raw if not raw.startswith("+") else raw)) if raw else "")(str(row.get("MOBILE", "")).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")))}
                            {(lambda bt_str, bt_exp: f"<tr style='color:{"red" if bt_exp else "#A0F0A0"};'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>{html.escape(bt_str)}{(f'<span style="font-weight:bold;">(Expirado)</span>' if bt_exp else '')}</td></tr>" if bt_str else "<tr style='color:orange;'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>Não Registrado</td></tr>")(str(row.get("BLOOD TEST", "")), is_blood_test_expired(str(row.get("BLOOD TEST", ""))))}
                        </table>
                    </div>''' if st.session_state.show_personal_data else "<div style='flex-basis: 300px; flex-grow: 1; font-style:italic; color:#ccc; font-size:13px; text-align:center;'>Dados pessoais ocultos.</div>"}
                </div>
            </div>
            """, unsafe_allow_html=True)

            current_selected_task = st.session_state.selected_task
            music_link_keys = [f"music_link_1_{athlete_id_str}", f"music_link_2_{athlete_id_str}", f"music_link_3_{athlete_id_str}"]
            for key_music in music_link_keys:
                if key_music not in st.session_state: st.session_state[key_music] = ""

            if current_selected_task == "Walkout Music":
                st.markdown("##### Links para Walkout Music:")
                st.session_state[music_link_keys[0]] = st.text_input(f"Música 1 (YouTube)", value=st.session_state[music_link_keys[0]], key=f"music1_{athlete_id_str}_{i}", placeholder="Link do YouTube")
                st.session_state[music_link_keys[1]] = st.text_input(f"Música 2 (YouTube)", value=st.session_state[music_link_keys[1]], key=f"music2_{athlete_id_str}_{i}", placeholder="Link do YouTube")
                st.session_state[music_link_keys[2]] = st.text_input(f"Música 3 (YouTube)", value=st.session_state[music_link_keys[2]], key=f"music3_{athlete_id_str}_{i}", placeholder="Link do YouTube")
                if st.button(f"Registrar Músicas para {athlete_name}", key=f"register_music_{athlete_id_str}_{i}", type="primary", use_container_width=True):
                    links_to_register = [st.session_state[k] for k in music_link_keys]
                    registered_any = False
                    for idx, link_url in enumerate(links_to_register):
                        if link_url and link_url.strip():
                            success = registrar_log(
                                athlete_id=athlete_id_str, athlete_name=athlete_name, athlete_event=athlete_event,
                                task_type="Walkout Music", task_status="Done",
                                notes=link_url.strip(), user_id=st.session_state['current_user_id'])
                            if success: registered_any = True; st.session_state[music_link_keys[idx]] = ""
                    if registered_any: st.rerun()
                    else: st.warning("Nenhum link de música fornecido.", icon="⚠️")
            else:
                is_already_done = False
                if not athlete_task_records.empty and "Status" in athlete_task_records.columns:
                    if "Done" in athlete_task_records["Status"].values: is_already_done = True
                button_label = f"Marcar '{current_selected_task}' como CONCLUÍDO"
                button_type = "primary"
                if is_already_done:
                    button_label = f"'{current_selected_task}' CONCLUÍDO (Registrar novamente?)"; button_type = "secondary"
                if st.button(button_label, key=f"mark_done_{athlete_id_str}_{current_selected_task.replace(' ', '_')}_{i}", type=button_type, use_container_width=True):
                    registrar_log(
                        athlete_id=athlete_id_str, athlete_name=athlete_name, athlete_event=athlete_event,
                        task_type=current_selected_task, task_status="Done", notes="",
                        user_id=st.session_state['current_user_id'])
                    st.rerun()
            st.markdown("<hr style='border-top: 1px solid #333; margin-top: 10px; margin-bottom: 25px;'>", unsafe_allow_html=True)
else:
    if not st.session_state['user_confirmed'] and not st.session_state.get('warning_message'):
         st.warning("🚨 Confirme seu ID de usuário para acessar.", icon="🚨")
