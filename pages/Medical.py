# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html
# import altair as alt # Removido, pois a seção de estatísticas foi removida
import time

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Task Control", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"
CONFIG_TAB_NAME = "Config"
NO_TASK_SELECTED_LABEL = "-- Choose Task --"

# Define os novos status e suas cores
STATUS_PENDING = "Pending"
STATUS_CLEAR_DOCTOR = "Clear by Doctor"
STATUS_UNDER_OBSERVATION = "Under Observation"
STATUS_STABLE_LOW_RISK = "Stable Low Risk"
STATUS_SERIOUS_AMBULANCE = "Serious Ambulance"

# Lista de todos os status lógicos que o app usará
ALL_LOGICAL_STATUSES = [
    STATUS_PENDING,
    STATUS_CLEAR_DOCTOR,
    STATUS_UNDER_OBSERVATION,
    STATUS_STABLE_LOW_RISK,
    STATUS_SERIOUS_AMBULANCE
]

# Mapa de cores para os novos status (para badges e barra lateral do card)
STATUS_COLOR_MAP = {
    STATUS_CLEAR_DOCTOR: "#28a745",       # Green
    STATUS_UNDER_OBSERVATION: "#ffc107",  # Light Yellow
    STATUS_STABLE_LOW_RISK: "#e0a800",    # Dark Yellow
    STATUS_SERIOUS_AMBULANCE: "#dc3545",  # Red
    STATUS_PENDING: "#6c757d",            # Gray (para pending/não registrado/antigo requested)
    "Not Registred": "#6c757d"            # Trata 'Not Registred' como Pending visualmente
}

# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError as e:
        st.error(f"Erro config: Chave GCP ausente. Detalhes: {e}", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro API Google: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada em '{sheet_name}'.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨"); st.stop()

# --- 3. Data Loading ---
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = MAIN_SHEET_NAME, athletes_tab_name: str = ATHLETES_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name)
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty: return pd.DataFrame()
        if "ROLE" not in df.columns or "INACTIVE" not in df.columns:
            st.error(f"Colunas 'ROLE'/'INACTIVE' não encontradas em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        df.columns = df.columns.str.strip()
        if df["INACTIVE"].dtype == 'object':
            df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        elif pd.api.types.is_numeric_dtype(df["INACTIVE"]):
            df["INACTIVE"] = df["INACTIVE"].map({0: False, 1: True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z") if "EVENT" in df.columns else "Z"
        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
            else: df[col] = ""
        for col_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE"]:
            df[col_check] = df[col_check].fillna("") if col_check in df.columns else ""
        if "NAME" not in df.columns:
            st.error(f"'NAME' não encontrada em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar atletas (gspread): {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name)
        return worksheet.get_all_records() or []
    except Exception as e:
        st.error(f"Erro ao carregar usuários '{users_tab_name}': {e}", icon="🚨"); return []

def get_valid_user_info(user_input: str, sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    if not user_input: return None
    all_users = load_users_data(sheet_name, users_tab_name)
    if not all_users: return None
    proc_input = user_input.strip().upper()
    val_id_input = proc_input[2:] if proc_input.startswith("PS") and len(proc_input) > 2 and proc_input[2:].isdigit() else proc_input
    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip(); name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == val_id_input or ("PS" + ps_sheet) == proc_input or name_sheet == proc_input or ps_sheet == proc_input: return record
    return None

@st.cache_data(ttl=600)
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
        data = worksheet.get_all_values()
        if not data or len(data) < 1: st.error(f"Aba '{config_tab_name}' vazia/sem cabeçalho.", icon="🚨"); return [],[]
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().unique().tolist() if "TaskList" in df_conf.columns else []
        if not tasks: st.warning(f"'TaskList' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        return tasks, [] # Retorna lista de status vazia, pois usaremos status fixos definidos nas constantes
    except Exception as e: st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨"); return [], []

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame(columns=["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"])
        expected_cols_order = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"]
        for col in expected_cols_order:
            if col not in df_att.columns: df_att[col] = pd.NA
        return df_att
    except Exception as e: st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id) if st.session_state.get('user_confirmed') else user_log_id
        next_num = len(log_ws.get_all_values()) + 1
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        load_attendance_data.clear() # Limpa o cache para recarregar dados
        load_athlete_data.clear() # Limpa o cache para recarregar dados (se necessário, para exibir mudanças)
        return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨")
        return False

# --- Helper Function ---
# Função atualizada para retornar status, usuário e timestamp
def get_latest_status_and_user(athlete_id, task, attendance_df):
    status = STATUS_PENDING
    user = "N/A"
    timestamp = "N/A"

    if attendance_df.empty or task is None:
        return status, user, timestamp

    athlete_records = attendance_df[
        (attendance_df[ID_COLUMN_IN_ATTENDANCE].astype(str) == str(athlete_id)) & 
        (attendance_df["Task"] == task)
    ].copy() # Use .copy() para evitar SettingWithCopyWarning

    if athlete_records.empty:
        return status, user, timestamp

    if "Timestamp" in athlete_records.columns:
        athlete_records['TS_dt'] = pd.to_datetime(athlete_records['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        valid_records = athlete_records.dropna(subset=['TS_dt'])
        if not valid_records.empty:
            latest_record = valid_records.sort_values(by="TS_dt", ascending=False).iloc[0]
        else: # Fallback se nenhum timestamp for válido, pega o último registro
            latest_record = athlete_records.iloc[-1]
    else: # Fallback se não houver coluna Timestamp
        latest_record = athlete_records.iloc[-1]
    
    status_raw = latest_record.get("Status", STATUS_PENDING)
    user = latest_record.get("User", "N/A")
    timestamp = latest_record.get("Timestamp", "N/A")

    # Mapeamento de status brutos da planilha para os novos status lógicos
    if status_raw == "Done" or status_raw == STATUS_CLEAR_DOCTOR: # Trata "Done" antigo e o novo "Clear by Doctor" como o mesmo
        status = STATUS_CLEAR_DOCTOR
    elif status_raw == STATUS_UNDER_OBSERVATION:
        status = STATUS_UNDER_OBSERVATION
    elif status_raw == STATUS_STABLE_LOW_RISK:
        status = STATUS_STABLE_LOW_RISK
    elif status_raw == STATUS_SERIOUS_AMBULANCE:
        status = STATUS_SERIOUS_AMBULANCE
    else: # Inclui "Requested", "---", "Pending", "Not Registred" e qualquer outro não mapeado
        status = STATUS_PENDING

    return status, user, timestamp

# --- 6. Main Application Logic ---
st.title("UAEW | Task Control")

# Modificado o default para selected_status para refletir as novas opções ou "Todos"
# selected_badge_tasks será inicializado após o carregamento de tasks_raw
default_ss = {"warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "User", "current_user_image_url": "", "show_personal_data": False, "selected_task": NO_TASK_SELECTED_LABEL, "selected_status": "Todos", "selected_event": "Todos os Eventos", "fighter_search_query": "", "selected_badge_tasks": []}
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k]=v
if 'user_id_input' not in st.session_state: st.session_state['user_id_input']=st.session_state['current_user_id']

# --- User Auth Section ---
with st.container(border=True):
    st.subheader("User")
    col_input_ps, col_user_status_display = st.columns([0.6, 0.4])
    with col_input_ps:
        st.session_state['user_id_input'] = st.text_input("PS Number", value=st.session_state['user_id_input'], max_chars=50, key="uid_w", label_visibility="collapsed", placeholder="Digite os 4 dígitos do seu PS")
        if st.button("Login", key="confirm_b_w", use_container_width=True, type="primary"):
            u_in=st.session_state['user_id_input'].strip()
            if u_in:
                u_inf=get_valid_user_info(u_in)
                if u_inf:
                    st.session_state.update(current_user_ps_id_internal=str(u_inf.get("PS",u_in)).strip(), current_user_id=u_in, current_user_name=str(u_inf.get("USER",u_in)).strip(), current_user_image_url=str(u_inf.get("USER_IMAGE","")).strip(), user_confirmed=True, warning_message=None)
                else:
                    st.session_state.update(user_confirmed=False,current_user_image_url="",warning_message=f"⚠️ Usuário '{u_in}' não encontrado.")
            else:
                st.session_state.update(warning_message="⚠️ ID/Nome do usuário vazio.",user_confirmed=False,current_user_image_url="")
    with col_user_status_display:
        if st.session_state.user_confirmed and st.session_state.current_user_name != "User":
            un, ui = html.escape(st.session_state.current_user_name), html.escape(st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id))
            uim = st.session_state.get('current_user_image_url', "")
            image_html = f"""<img src="{html.escape(uim, True)}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;border:1px solid #555;vertical-align:middle;margin-right:10px;">""" if uim and (uim.startswith("http://") or uim.startswith("https://")) else "<div style='width:50px;height:50px;border-radius:50%;background-color:#333;margin-right:10px;display:inline-block;vertical-align:middle;'></div>"
            st.markdown(f"""<div style="display:flex;align-items:center;height:50px;margin-top:0px;">{image_html}<div style="line-height:1.2;vertical-align:middle;"><span style="font-weight:bold;">{un}</span><br><span style="font-size:0.9em;color:#ccc;">PS: {ui}</span></div></div>""", unsafe_allow_html=True)
        elif st.session_state.get('warning_message'):
            st.warning(st.session_state.warning_message, icon="🚨")

if st.session_state.user_confirmed and st.session_state.current_user_id.strip().upper()!=st.session_state.user_id_input.strip().upper() and st.session_state.user_id_input.strip()!="":
    st.session_state.update(user_confirmed=False,warning_message="⚠️ ID/Nome alterado. Confirme.",current_user_image_url="",selected_task=NO_TASK_SELECTED_LABEL);st.rerun()

# --- Main App Content ---
if st.session_state.user_confirmed and st.session_state.current_user_name!="User":
    with st.spinner("Carregando dados..."):
        tasks_raw, _ = load_config_data() # Nao precisamos da lista de status do config
        df_athletes = load_athlete_data()
        df_attendance = load_attendance_data()

    # Inicializa o selected_badge_tasks com todas as tarefas, se ainda não estiver definido ou vazio
    if not st.session_state.get('selected_badge_tasks'):
        st.session_state.selected_badge_tasks = tasks_raw.copy()

    tasks_for_select = [NO_TASK_SELECTED_LABEL] + tasks_raw
    st.session_state.selected_task = st.selectbox("Selecione a Tarefa:", tasks_for_select, index=tasks_for_select.index(st.session_state.selected_task) if st.session_state.selected_task in tasks_for_select else 0, key="tsel_w")
    sel_task_actual = st.session_state.selected_task if st.session_state.selected_task != NO_TASK_SELECTED_LABEL else None

    if sel_task_actual:
        # Aplica a função de status e usuário/timestamp a todo o DataFrame
        df_athletes[['current_task_status', 'latest_task_user', 'latest_task_timestamp']] = df_athletes['ID'].apply(
            lambda id: pd.Series(get_latest_status_and_user(id, sel_task_actual, df_attendance))
        )
        st.divider() # Mantém o divisor para separação visual

    # Opções de filtro de status para o rádio
    status_options_radio = ["Todos"] + ALL_LOGICAL_STATUSES
    st.session_state.selected_status = st.radio(
        "Filtrar Atletas por Status da Tarefa Selecionada:", 
        options=status_options_radio, 
        index=status_options_radio.index(st.session_state.selected_status) if st.session_state.selected_status in status_options_radio else 0, 
        horizontal=True, 
        key="srad_w", 
        disabled=(not sel_task_actual)
    )

    filter_cols = st.columns(2)
    filter_cols[0].selectbox("Filtrar Evento:", options=["Todos os Eventos"] + sorted([evt for evt in df_athletes["EVENT"].unique() if evt != "Z"]), key="selected_event")
    filter_cols[1].text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")
    st.toggle("Mostrar Dados Pessoais", key="show_personal_data")

    # Novo multibox para filtrar as TAREFAS a serem exibidas nos badges
    st.session_state.selected_badge_tasks = st.multiselect(
        "Selecionar Tarefas para Visualizar nos Badges:",
        options=tasks_raw, # As opções agora são as tarefas em si
        default=st.session_state.selected_badge_tasks, # Usa o valor da sessão (inicializado acima)
        key="badge_task_filter_w",
        help="Escolha quais tarefas você quer ver exibidas como badges abaixo de cada atleta."
    )
    st.divider()

    df_filtered = df_athletes.copy()
    if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]
    search_term = st.session_state.fighter_search_query.strip().lower()
    if search_term: df_filtered = df_filtered[df_filtered["NAME"].str.lower().str.contains(search_term, na=False) | df_filtered["ID"].astype(str).str.contains(search_term, na=False)]

    if sel_task_actual and st.session_state.selected_status != "Todos":
        df_filtered = df_filtered[df_filtered['current_task_status'] == st.session_state.selected_status]

    st.markdown(f"Exibindo **{len(df_filtered)}** atletas.")
    if not sel_task_actual: st.info("Selecione uma tarefa para ver as opções.", icon="ℹ️")

    for i_l, row in df_filtered.iterrows():
        ath_id_d, ath_name_d, ath_event_d = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])

        curr_ath_task_stat = STATUS_PENDING
        latest_user = "N/A"
        latest_ts = "N/A"
        status_bar_color = STATUS_COLOR_MAP[STATUS_PENDING] # Default para cinza
        status_text_html = ""
        user_ts_html = ""

        if sel_task_actual:
            curr_ath_task_stat = row.get('current_task_status', STATUS_PENDING)
            latest_user = row.get('latest_task_user', 'N/A')
            latest_ts = row.get('latest_task_timestamp', 'N/A')

            status_text_html = f"<p style='margin:5px 0 0 0; font-size:1em;'>Status da Tarefa: <strong>{curr_ath_task_stat}</strong></p>"
            user_ts_html = f"<p style='margin:2px 0 0 0; font-size:0.8em; color:#bbb;'>Última Atualização por: <strong>{html.escape(latest_user)}</strong> em: <strong>{html.escape(latest_ts)}</strong></p>"

            status_bar_color = STATUS_COLOR_MAP.get(curr_ath_task_stat, STATUS_COLOR_MAP[STATUS_PENDING])

        col_card, col_buttons = st.columns([2.5, 1])
        with col_card:
            mob_r = str(row.get("MOBILE", "")).strip()
            wa_link_html = ""
            if mob_r:
                phone_digits = "".join(filter(str.isdigit, mob_r))
                if phone_digits.startswith('00'): phone_digits = phone_digits[2:]
                if phone_digits: wa_link_html = f"""<p style='margin-top: 8px; font-size:14px;'><a href='https://wa.me/{html.escape(phone_digits, True)}' target='_blank' style='color:#25D366; text-decoration:none; font-weight:bold;'> WhatsApp</a></p>"""

            pd_content_html = ""
            if st.session_state.show_personal_data:
                pass_img_h = f"<tr><td style='padding: 2px 10px 2px 0;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{html.escape(str(row.get('PASSPORT IMAGE','')),True)}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if pd.notna(row.get("PASSPORT IMAGE")) and row.get("PASSPORT IMAGE") else ""
                pd_content_html = f"""
                <div style='margin-top: 15px; border-top: 1px solid #444; padding-top: 15px;'>
                    <table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'>
                       <tr><td style='padding: 2px 10px 2px 0;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER","")))}</td></tr>
                       <tr><td style='padding: 2px 10px 2px 0;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB","")))}</td></tr>
                       <tr><td style='padding: 2px 10px 2px 0;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY","")))}</td></tr>
                       <tr><td style='padding: 2px 10px 2px 0;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT","")))}</td></tr>
                       <tr><td style='padding: 2px 10px 2px 0;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE","")))}</td></tr>
                       {pass_img_h}
                    </table>
                </div>
                """
            
            st.markdown(f"""
            <div style='background-color:#2E2E2E; border-left: 5px solid {status_bar_color}; padding: 20px; border-radius: 10px;'>
                <div style='display:flex; align-items:center; gap:20px;'>
                    <img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/120?text=No+Image")if pd.notna(row.get("IMAGE"))and row.get("IMAGE")else"https://via.placeholder.com/120?text=No+Image",True)}' style='width:120px; height:120px; border-radius:50%; object-fit:cover;'>
                    <div style='flex-grow: 1;'>
                        <h4 style='margin:0; font-size:1.6em; line-height: 1.2;'>{html.escape(ath_name_d)} <span style='font-size:0.6em; color:#cccccc; font-weight:normal; margin-left: 8px;'>{html.escape(ath_event_d)} (ID: {html.escape(ath_id_d)})</span></h4>
                        {status_text_html}
                        {user_ts_html}
                        {wa_link_html}
                    </div>
                </div>
                {pd_content_html}
            </div>
            """, unsafe_allow_html=True)

            if sel_task_actual:
                badges_html = "<div style='display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px;'>"
                for task_name_in_badge_list in tasks_raw: # Itera sobre todas as tarefas para gerar os badges
                    # Filtra os badges com base na seleção do multibox: exibe apenas as tarefas selecionadas
                    if task_name_in_badge_list not in st.session_state.selected_badge_tasks:
                        continue # Pula esta tarefa se ela não estiver selecionada no multiselect
                    
                    # Obtém o status, usuário e timestamp para a tarefa atual no loop
                    status_for_badge, user_for_badge, ts_for_badge = get_latest_status_and_user(ath_id_d, task_name_in_badge_list, df_attendance)
                    
                    # Usa o mapa de cores para o status da tarefa
                    color = STATUS_COLOR_MAP.get(status_for_badge, STATUS_COLOR_MAP[STATUS_PENDING])
                    badge_style = f"background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;"
                    
                    # Adiciona tooltip para exibir detalhes do badge (usuário e timestamp)
                    tooltip_content = f"Status: {status_for_badge}\\nAtualizado por: {user_for_badge}\\nEm: {ts_for_badge}"
                    badges_html += f"<span style='{badge_style}' title='{html.escape(tooltip_content, quote=True)}'>{html.escape(task_name_in_badge_list)}</span>"
                badges_html += "</div>"
                st.markdown(badges_html, unsafe_allow_html=True)


        with col_buttons:
            if sel_task_actual:
                uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
                st.write(" "); st.write(" ") 

                # Gerar botões dinamicamente para todos os status possíveis
                for target_status in ALL_LOGICAL_STATUSES:
                    if target_status == curr_ath_task_stat:
                        continue # Não oferece a opção de mudar para o status atual

                    # Define o tipo de botão (primary/secondary)
                    button_type = "primary" if target_status == STATUS_CLEAR_DOCTOR else "secondary"
                    
                    # Rótulos específicos para "Pending"
                    if target_status == STATUS_PENDING:
                        button_label = "Marcar como Pendente"
                    else:
                        button_label = f"Mover para '{target_status}'"

                    if st.button(button_label, key=f"move_{target_status.replace(' ', '_').lower()}_{ath_id_d}_{i_l}", type=button_type, use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, target_status, "", uid_l):
                            time.sleep(1.5)
                            st.rerun()
        st.divider()

else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):
        st.warning("🚨 Por favor, faça o login para continuar.", icon="🚨")
