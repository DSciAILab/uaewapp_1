# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html
import altair as alt
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
STATUS_PENDING_LIKE = ["Pending", "Not Registred"]
ATTENDANCE_ORDER_COL = "Check-in Order"
STATUS_CHECKED_IN = "Checked-in"


# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro API Google: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨"); st.stop()

# --- 3. Data Loading ---
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = MAIN_SHEET_NAME, athletes_tab_name: str = ATHLETES_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name)
        df = pd.DataFrame(worksheet.get_all_records())
        if df.empty: return pd.DataFrame()
        df.columns = df.columns.str.strip()
        if "ROLE" not in df.columns or "INACTIVE" not in df.columns: return pd.DataFrame()
        df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e: st.error(f"Erro ao carregar atletas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name)
        return worksheet.get_all_records() or []
    except Exception: return []

def get_valid_user_info(user_input: str, all_users: list):
    if not user_input or not all_users: return None
    proc_input = user_input.strip().upper()
    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip().upper()
        name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == proc_input or name_sheet == proc_input:
            return record
    return None

@st.cache_data(ttl=600)
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return []
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception: return []

@st.cache_data(ttl=20)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        expected_cols = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes", ATTENDANCE_ORDER_COL]
        for col in expected_cols:
            if col not in df_att.columns: df_att[col] = None
        return df_att[expected_cols]
    except Exception: return pd.DataFrame(columns=expected_cols)

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        
        all_records_df = pd.DataFrame(log_ws.get_all_records())
        
        check_in_order_num = ''
        # ** ESTA É A LÓGICA DE NUMERAÇÃO SEQUENCIAL **
        # Ela só é ativada quando o status é "Checked-in".
        if status == STATUS_CHECKED_IN:
            # Garante que a coluna de ordem exista no DataFrame lido
            if ATTENDANCE_ORDER_COL not in all_records_df.columns:
                all_records_df[ATTENDANCE_ORDER_COL] = None
            
            # Filtra os registros apenas para a tarefa atual para criar uma sequência por tarefa
            task_records = all_records_df[all_records_df['Task'] == task]
            task_orders = pd.to_numeric(task_records[ATTENDANCE_ORDER_COL], errors='coerce')
            
            # Encontra o maior número já usado e adiciona 1. Se não houver, começa em 1.
            max_order = task_orders.max()
            check_in_order_num = int(max_order + 1) if pd.notna(max_order) else 1

        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        next_num = len(all_records_df) + 2
        
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes, str(check_in_order_num)]
        
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.toast(f"'{status}' registrado para {ath_name}.", icon="✅")
        
        load_attendance_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar: {e}", icon="🚨")
        return False

def get_latest_status_and_order(athlete_id, task, attendance_df):
    if attendance_df.empty or task is None: return "Pending", None
    
    athlete_records = attendance_df[(attendance_df[ID_COLUMN_IN_ATTENDANCE].astype(str) == str(athlete_id)) & (attendance_df["Task"] == task)]
    if athlete_records.empty: return "Pending", None
    
    athlete_records = athlete_records.copy()
    athlete_records['TS_dt'] = pd.to_datetime(athlete_records['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
    valid_records = athlete_records.dropna(subset=['TS_dt']).sort_values(by="TS_dt", ascending=False)
    
    if valid_records.empty: return "Pending", None
    
    latest_status = valid_records.iloc[0].get("Status", "Pending")
    
    check_in_record = valid_records[valid_records['Status'] == STATUS_CHECKED_IN]
    check_in_order = check_in_record.iloc[0].get(ATTENDANCE_ORDER_COL) if not check_in_record.empty else None

    return latest_status, check_in_order

# --- Main Application Logic ---
st.title("UAEW | Task Control")

# Session State
default_ss = {k: v for k, v in {"warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "User", "selected_task": NO_TASK_SELECTED_LABEL, "selected_status": "Todos", "selected_event": "Todos os Eventos", "fighter_search_query": ""}.items() if k not in st.session_state}
st.session_state.update(default_ss)

# --- User Auth Section ---
with st.container(border=True):
    st.subheader("User")
    all_users_data = load_users_data()
    
    col_input_ps, col_user_status_display = st.columns([0.6, 0.4])
    with col_input_ps:
        user_id_input = st.text_input("PS Number or Name", value=st.session_state.current_user_id, max_chars=50, key="uid_w", label_visibility="collapsed", placeholder="Digite seu PS ou Nome")
        if st.button("Login", key="confirm_b_w", use_container_width=True, type="primary"):
            st.session_state.current_user_id = user_id_input
            if user_id_input:
                user_info = get_valid_user_info(user_id_input, all_users_data)
                if user_info:
                    st.session_state.update(current_user_name=str(user_info.get("USER", user_id_input)).strip(), user_confirmed=True, warning_message=None)
                    st.rerun()
                else:
                    st.session_state.update(user_confirmed=False, warning_message=f"⚠️ Usuário '{user_id_input}' não encontrado.")
            else:
                st.session_state.update(warning_message="⚠️ ID/Nome do usuário vazio.", user_confirmed=False)

    with col_user_status_display:
        if st.session_state.user_confirmed:
            st.markdown(f"✅ Logado como: **{html.escape(st.session_state.current_user_name)}**")
        elif st.session_state.get('warning_message'):
            st.warning(st.session_state.warning_message, icon="🚨")

# --- Main App Content ---
if st.session_state.user_confirmed:
    tasks_raw = load_config_data()
    df_athletes = load_athlete_data()
    df_attendance = load_attendance_data()

    if df_athletes.empty and tasks_raw:
        st.warning("Não foi possível carregar os dados dos atletas. Verifique a planilha 'df'.")
        st.stop()

    tasks_for_select = [NO_TASK_SELECTED_LABEL] + tasks_raw
    st.session_state.selected_task = st.selectbox("Selecione a Tarefa:", tasks_for_select, index=tasks_for_select.index(st.session_state.selected_task) if st.session_state.selected_task in tasks_for_select else 0, key="tsel_w")
    sel_task_actual = st.session_state.selected_task if st.session_state.selected_task != NO_TASK_SELECTED_LABEL else None

    if sel_task_actual:
        status_order_df = df_athletes['ID'].apply(lambda id: pd.Series(get_latest_status_and_order(id, sel_task_actual, df_attendance)))
        df_athletes[['current_task_status', 'current_task_order']] = status_order_df
    
    # Filtering and Display
    status_options = ["Todos", "Requested", STATUS_CHECKED_IN, "Done", "Pending"]
    st.session_state.selected_status = st.radio("Filtrar por Status:", options=status_options, index=status_options.index(st.session_state.selected_status) if st.session_state.selected_status in status_options else 0, horizontal=True, key="srad_w", disabled=(not sel_task_actual))
    
    df_filtered = df_athletes.copy()
    if sel_task_actual and st.session_state.selected_status != "Todos":
        df_filtered = df_filtered[df_filtered['current_task_status'] == st.session_state.selected_status]
    
    st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
    if not sel_task_actual: st.info("Selecione uma tarefa para ver as opções de registro.", icon="ℹ️")

    for i_l, row in df_filtered.iterrows():
        ath_id_d, ath_name_d, ath_event_d = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
        status_bar_color, status_text_html = "#2E2E2E", ""

        if sel_task_actual:
            curr_ath_task_stat = row.get('current_task_status', 'Pending')
            curr_ath_task_order = row.get('current_task_order')

            if curr_ath_task_stat == "Done":
                status_bar_color, status_text_html = "#28a745", f"<p>Status: <strong>Finalizado</strong> (Ordem: #{int(float(curr_ath_task_order))})</p>" if pd.notna(curr_ath_task_order) else "<p>Status: <strong>Finalizado</strong></p>"
            elif curr_ath_task_stat == STATUS_CHECKED_IN:
                status_bar_color = "#17a2b8"
                status_text_html = f"<div style='background-color:#0d7a8b;color:white;padding:5px 10px;border-radius:8px;text-align:center;'><span style='font-size:0.8em;display:block;'>EM ATENDIMENTO</span><span style='font-size:1.5em;font-weight:bold;'>#{int(float(curr_ath_task_order))}</span></div>" if pd.notna(curr_ath_task_order) else ""
            elif curr_ath_task_stat == "Requested":
                status_bar_color, status_text_html = "#ffc107", "<p>Status: <strong>Aguardando na Fila</strong></p>"
            else:
                status_bar_color, status_text_html = "#dc3545", "<p>Status: <strong>Pendente</strong></p>"
        
        col_card, col_buttons = st.columns([2.5, 1])
        with col_card:
            st.markdown(f"""<div style='background-color:#2E2E2E; border-left: 5px solid {status_bar_color}; padding: 20px; border-radius: 10px; min-height: 160px;'>
                <div style='display:flex; align-items:center; gap:20px;'>
                    <img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/120?text=NA") or "https://via.placeholder.com/120?text=NA")}' style='width:120px; height:120px; border-radius:50%; object-fit:cover;'>
                    <div>
                        <h4 style='margin:0;font-size:1.6em;'>{html.escape(ath_name_d)}<span style='font-size:0.6em;color:#ccc;font-weight:normal;margin-left:8px;'>ID: {ath_id_d}</span></h4>
                        <div style='margin-top:10px;'>{status_text_html}</div>
                    </div></div></div>""", unsafe_allow_html=True)
            
        with col_buttons:
            if sel_task_actual:
                uid_l = st.session_state.current_user_name
                st.write(" "); st.write(" ") 

                # ** LÓGICA DE BOTÕES CONDICIONAIS **
                def handle_click(ath_id, ath_name, ath_event, task, new_status, notes=""):
                    with st.spinner("Registrando..."):
                        if registrar_log(ath_id, ath_name, ath_event, task, new_status, notes, uid_l):
                            time.sleep(0.5) # Pausa curta para ajudar na sincronização com o Google
                            st.rerun()

                if curr_ath_task_stat == "Requested":
                    st.button("✅ CHECK-IN", on_click=handle_click, args=(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, STATUS_CHECKED_IN), key=f"checkin_{ath_id_d}", type="primary", use_container_width=True)
                elif curr_ath_task_stat == STATUS_CHECKED_IN:
                    st.button("🏁 CHECK-OUT (Concluir)", on_click=handle_click, args=(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Done"), key=f"checkout_{ath_id_d}", type="primary", use_container_width=True)
                    st.button("↩️ Retornar para Fila", on_click=handle_click, args=(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Requested", "Retornou para fila"), key=f"requeue_{ath_id_d}", use_container_width=True)
                elif curr_ath_task_stat in STATUS_PENDING_LIKE:
                    st.button("➕ REQUISITAR TAREFA", on_click=handle_click, args=(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Requested"), key=f"req_{ath_id_d}", type="primary", use_container_width=True)
                elif curr_ath_task_stat == "Done":
                    st.button("🔁 SOLICITAR NOVAMENTE", on_click=handle_click, args=(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Requested", "Solicitado novamente"), key=f"req_again_{ath_id_d}", use_container_width=True)
        st.divider()

else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):
        st.warning("🚨 Por favor, faça o login para continuar.", icon="🚨")
