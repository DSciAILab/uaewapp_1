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
        df.columns = df.columns.str.strip()
        if "ROLE" not in df.columns or "INACTIVE" not in df.columns:
            st.error(f"Colunas 'ROLE'/'INACTIVE' não encontradas em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        if df["INACTIVE"].dtype == 'object':
            df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        elif pd.api.types.is_numeric_dtype(df["INACTIVE"]):
            df["INACTIVE"] = df["INACTIVE"].map({0: False, 1: True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z") if "EVENT" in df.columns else "Z"
        if "NAME" not in df.columns:
            st.error(f"'NAME' não encontrada em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar atletas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    # Simpler and safer loading
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name)
        return worksheet.get_all_records() or []
    except Exception as e:
        st.error(f"Erro ao carregar usuários '{users_tab_name}': {e}", icon="🚨"); return []


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
        if not data or len(data) < 1: st.error(f"Aba '{config_tab_name}' vazia/sem cabeçalho.", icon="🚨"); return [],[]
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        if not tasks: st.warning(f"'TaskList' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        return tasks
    except Exception as e: st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨"); return []

@st.cache_data(ttl=30)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty:
            return pd.DataFrame(columns=["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes", ATTENDANCE_ORDER_COL])
        expected_cols = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes", ATTENDANCE_ORDER_COL]
        for col in expected_cols:
            if col not in df_att.columns: df_att[col] = pd.NA
        return df_att[expected_cols]
    except Exception as e: st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        
        # Lê os dados mais recentes para garantir a sequência correta
        all_records_df = pd.DataFrame(log_ws.get_all_records())
        
        check_in_order_num = ''
        if status == STATUS_CHECKED_IN:
            if not all_records_df.empty and ATTENDANCE_ORDER_COL in all_records_df.columns:
                task_records = all_records_df[all_records_df['Task'] == task]
                task_orders = pd.to_numeric(task_records[ATTENDANCE_ORDER_COL], errors='coerce')
                max_order = task_orders.max()
                check_in_order_num = int(max_order + 1) if pd.notna(max_order) else 1
            else:
                check_in_order_num = 1 # Primeiro check-in para esta tarefa

        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        next_num = len(all_records_df) + 2
        
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes, str(check_in_order_num)]
        
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        
        load_attendance_data.clear()
        load_athlete_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨")
        return False

def get_latest_status_and_order(athlete_id, task, attendance_df):
    if attendance_df.empty or task is None:
        return "Pending", None
    
    athlete_records = attendance_df[(attendance_df[ID_COLUMN_IN_ATTENDANCE].astype(str) == str(athlete_id)) & (attendance_df["Task"] == task)]
    if athlete_records.empty:
        return "Pending", None
    
    athlete_records = athlete_records.copy()
    athlete_records['TS_dt'] = pd.to_datetime(athlete_records['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
    valid_records = athlete_records.dropna(subset=['TS_dt']).sort_values(by="TS_dt", ascending=False)
    
    if valid_records.empty: return "Pending", None
    
    latest_record = valid_records.iloc[0]
    latest_status = latest_record.get("Status", "Pending")
    
    check_in_record = valid_records[valid_records['Status'] == STATUS_CHECKED_IN]
    check_in_order = check_in_record.iloc[0].get(ATTENDANCE_ORDER_COL) if not check_in_record.empty else None

    return latest_status, check_in_order

# --- Main Application Logic ---
st.title("UAEW | Task Control")

# Session State
default_ss = {"warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "User", "selected_task": NO_TASK_SELECTED_LABEL, "selected_status": "Todos", "selected_event": "Todos os Eventos", "fighter_search_query": ""}
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k]=v

# --- User Auth Section ---
with st.container(border=True):
    st.subheader("User")
    all_users_data = load_users_data() # Load once
    
    col_input_ps, col_user_status_display = st.columns([0.6, 0.4])
    with col_input_ps:
        user_id_input = st.text_input("PS Number or Name", value=st.session_state.get('current_user_id', ''), max_chars=50, key="uid_w", label_visibility="collapsed", placeholder="Digite seu PS ou Nome")
        if st.button("Login", key="confirm_b_w", use_container_width=True, type="primary"):
            if user_id_input:
                user_info = get_valid_user_info(user_id_input, all_users_data)
                if user_info:
                    st.session_state.update(current_user_id=user_id_input, current_user_name=str(user_info.get("USER", user_id_input)).strip(), user_confirmed=True, warning_message=None)
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
    with st.spinner("Carregando dados..."):
        tasks_raw = load_config_data()
        df_athletes = load_athlete_data()
        df_attendance = load_attendance_data()

    tasks_for_select = [NO_TASK_SELECTED_LABEL] + tasks_raw
    st.session_state.selected_task = st.selectbox("Selecione a Tarefa:", tasks_for_select, index=tasks_for_select.index(st.session_state.selected_task) if st.session_state.selected_task in tasks_for_select else 0, key="tsel_w")
    sel_task_actual = st.session_state.selected_task if st.session_state.selected_task != NO_TASK_SELECTED_LABEL else None

    if sel_task_actual:
        status_order_df = df_athletes['ID'].apply(lambda id: pd.Series(get_latest_status_and_order(id, sel_task_actual, df_attendance)))
        df_athletes[['current_task_status', 'current_task_order']] = status_order_df

        status_counts = df_athletes['current_task_status'].value_counts().to_dict()
        chart_data = pd.DataFrame([
            {"Status": "Done", "Count": status_counts.get('Done', 0)}, 
            {"Status": STATUS_CHECKED_IN, "Count": status_counts.get(STATUS_CHECKED_IN, 0)},
            {"Status": "Requested", "Count": status_counts.get('Requested', 0)}, 
            {"Status": "Pending", "Count": status_counts.get('Pending', 0)}
        ])
        color_scale = alt.Scale(domain=['Done', STATUS_CHECKED_IN, 'Requested', 'Pending'], range=['#28a745', '#17a2b8', '#ffc107', '#dc3545'])
        chart = alt.Chart(chart_data).mark_bar().encode(x=alt.X('Status:N', sort=None, title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y('Count:Q', title="Nº de Atletas"), color=alt.Color('Status:N', scale=color_scale, legend=None)).properties(height=200)
        st.altair_chart(chart, use_container_width=True)
        st.divider()

    status_options = ["Todos", "Requested", STATUS_CHECKED_IN, "Done", "Pending"]
    st.session_state.selected_status = st.radio("Filtrar por Status:", options=status_options, index=status_options.index(st.session_state.selected_status) if st.session_state.selected_status in status_options else 0, horizontal=True, key="srad_w", disabled=(not sel_task_actual))

    filter_cols = st.columns(2)
    filter_cols[0].selectbox("Filtrar Evento:", options=["Todos os Eventos"] + sorted([evt for evt in df_athletes["EVENT"].unique() if evt != "Z"]), key="selected_event")
    filter_cols[1].text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")
    st.divider()

    df_filtered = df_athletes.copy()
    if sel_task_actual:
        df_filtered = df_filtered.sort_values(by=['current_task_order'], na_position='last')

    if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]
    search_term = st.session_state.fighter_search_query.strip().lower()
    if search_term: df_filtered = df_filtered[df_filtered["NAME"].str.lower().str.contains(search_term, na=False) | df_filtered["ID"].astype(str).str.contains(search_term, na=False)]

    if sel_task_actual and st.session_state.selected_status != "Todos":
        df_filtered = df_filtered[df_filtered['current_task_status'] == st.session_state.selected_status]

    st.markdown(f"Exibindo **{len(df_filtered)}** atletas.")
    if not sel_task_actual: st.info("Selecione uma tarefa para ver as opções.", icon="ℹ️")

    for i_l, row in df_filtered.iterrows():
        ath_id_d, ath_name_d, ath_event_d = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])

        status_bar_color = "#2E2E2E"
        status_text_html = ""
        
        if sel_task_actual:
            curr_ath_task_stat = row.get('current_task_status', 'Pending')
            curr_ath_task_order = row.get('current_task_order')

            if curr_ath_task_stat == "Done":
                status_bar_color = "#28a745"
                status_text_html = f"<p style='margin:5px 0 0 0; font-size:1em;'>Status: <strong>Finalizado</strong></p>"
                if pd.notna(curr_ath_task_order):
                    status_text_html += f"<p style='margin:5px 0 0 0; font-size:0.9em;color:#A9A9A9;'>Ordem de Atendimento: <strong>#{int(float(curr_ath_task_order))}</strong></p>"
            elif curr_ath_task_stat == STATUS_CHECKED_IN:
                status_bar_color = "#17a2b8"
                if pd.notna(curr_ath_task_order):
                    status_text_html = f"""<div style='background-color:#0d7a8b; color:white; padding: 5px 10px; border-radius: 8px; text-align:center;'>
                                            <span style='font-size:0.8em; display:block;'>EM ATENDIMENTO</span>
                                            <span style='font-size:1.5em; font-weight:bold;'>#{int(float(curr_ath_task_order))}</span>
                                         </div>"""
            elif curr_ath_task_stat == "Requested":
                status_bar_color = "#ffc107"
                status_text_html = f"<p style='margin:5px 0 0 0; font-size:1em;'>Status: <strong>Aguardando na Fila</strong></p>"
            else:
                status_bar_color = "#dc3545"
                status_text_html = f"<p style='margin:5px 0 0 0; font-size:1em;'>Status: <strong>Pendente</strong></p>"

        col_card, col_buttons = st.columns([2.5, 1])
        with col_card:
            st.markdown(f"""
            <div style='background-color:#2E2E2E; border-left: 5px solid {status_bar_color}; padding: 20px; border-radius: 10px; min-height: 160px;'>
                <div style='display:flex; align-items:center; gap:20px;'>
                    <img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/120?text=No+Image") if pd.notna(row.get("IMAGE")) and row.get("IMAGE") else "https://via.placeholder.com/120?text=No+Image")}' style='width:120px; height:120px; border-radius:50%; object-fit:cover;'>
                    <div style='flex-grow: 1;'>
                        <h4 style='margin:0; font-size:1.6em; line-height: 1.2;'>{html.escape(ath_name_d)} <span style='font-size:0.6em; color:#cccccc; font-weight:normal; margin-left: 8px;'>ID: {html.escape(ath_id_d)}</span></h4>
                        <div style='margin-top:10px;'>{status_text_html}</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)
            
        with col_buttons:
            if sel_task_actual:
                uid_l = st.session_state.current_user_name
                st.write(" "); st.write(" ") 

                if curr_ath_task_stat == "Requested":
                    if st.button("✅ CHECK-IN", key=f"checkin_b_{ath_id_d}_{i_l}", type="primary", use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, STATUS_CHECKED_IN, "", uid_l):
                            time.sleep(1)
                            st.rerun()

                elif curr_ath_task_stat == STATUS_CHECKED_IN:
                    if st.button("🏁 CHECK-OUT (Concluir)", key=f"checkout_b_{ath_id_d}_{i_l}", type="primary", use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Done", "", uid_l):
                            time.sleep(1)
                            st.rerun()
                    if st.button("↩️ Retornar para Fila", key=f"requeue_b_{ath_id_d}_{i_l}", use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Requested", "Retornou para fila", uid_l):
                            time.sleep(1)
                            st.rerun()

                elif curr_ath_task_stat in STATUS_PENDING_LIKE:
                    if st.button("➕ REQUISITAR TAREFA", key=f"req_b_{ath_id_d}_{i_l}", type="primary", use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Requested", "", uid_l):
                            time.sleep(1)
                            st.rerun()
                
                elif curr_ath_task_stat == "Done":
                    if st.button("🔁 SOLICITAR NOVAMENTE", key=f"req_again_b_{ath_id_d}_{i_l}", use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Requested", "Solicitado novamente", uid_l):
                            time.sleep(1)
                            st.rerun()
        st.divider()

else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):
        st.warning("🚨 Por favor, faça o login para continuar.", icon="🚨")
