# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html
import time

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Bus Attendance", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"
CONFIG_TAB_NAME = "Config"

ACTIVE_TASK_NAME = "Bus Attendance"
STATUS_PENDING = "Pending"
STATUS_CHECKED_IN = "Checked in Bus"
STATUS_PRIVATE_CAR = "Private Car"

BUS_ATTENDANCE_STATUSES = [
    STATUS_PENDING,
    STATUS_CHECKED_IN,
    STATUS_PRIVATE_CAR
]

STATUS_COLOR_MAP = {
    STATUS_CHECKED_IN: "#28a745",
    STATUS_PRIVATE_CAR: "#28a745",
    STATUS_PENDING: "#6c757d",
    "Not Registred": "#6c757d",
    "Done": "#28a745",
    "Clear by Doctor": "#28a745",
    "Under Observation": "#ffc107",
    "Stable Low Risk": "#e0a800",
    "Serious Ambulance": "#dc3545",
}

# --- 2. Google Sheets Connection (código inalterado) ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de conexão com o Google: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada.", icon="🚨"); st.stop()

# --- 3. Data Loading (código inalterado) ---
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = MAIN_SHEET_NAME, athletes_tab_name: str = ATHLETES_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name)
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)

        for col in ["ROLE", "INACTIVE", "EVENT", "IMAGE", "MOBILE", "NAME", "ID"]:
            if col not in df.columns:
                df[col] = "" if col != "EVENT" else "Z"

        df.columns = df.columns.str.strip()
        df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        
        df["EVENT"] = df["EVENT"].fillna("Z")
        df["IMAGE"] = df["IMAGE"].fillna("")
        df["MOBILE"] = df["MOBILE"].fillna("")
        
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar dados dos atletas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name)
    return worksheet.get_all_records() or []

def get_valid_user_info(user_input: str):
    if not user_input: return None
    all_users = load_users_data()
    proc_input = user_input.strip().upper()
    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip()
        name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == proc_input or name_sheet == proc_input: return record
    return None

@st.cache_data(ttl=600)
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
    data = worksheet.get_all_values()
    if not data: return []
    df_conf = pd.DataFrame(data[1:], columns=data[0])
    tasks = df_conf["TaskList"].dropna().unique().tolist() if "TaskList" in df_conf.columns else []
    return tasks

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    data = worksheet.get_all_records()
    
    expected_cols = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"]

    if not data:
        return pd.DataFrame(columns=expected_cols)

    df_att = pd.DataFrame(data)
    for col in expected_cols:
        if col not in df_att.columns:
            df_att[col] = pd.NA
            
    return df_att

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        next_num = len(log_ws.get_all_values()) + 1
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        load_attendance_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar log: {e}", icon="🚨")
        return False

# --- Helper Function (código inalterado) ---
def get_latest_status_and_user(athlete_id, task, attendance_df):
    if attendance_df.empty or task is None:
        return STATUS_PENDING, "N/A", "N/A"

    athlete_records = attendance_df[
        (attendance_df[ID_COLUMN_IN_ATTENDANCE].astype(str) == str(athlete_id)) & 
        (attendance_df["Task"] == task)
    ].copy()

    if athlete_records.empty:
        return STATUS_PENDING, "N/A", "N/A"
    
    athlete_records['TS_dt'] = pd.to_datetime(athlete_records['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
    latest_record = athlete_records.sort_values(by="TS_dt", ascending=False, na_position='first').iloc[-1]
    
    status = latest_record.get("Status", STATUS_PENDING)
    user = latest_record.get("User", "N/A")
    timestamp = latest_record.get("Timestamp", "N/A")

    return status, user, timestamp

# --- 6. Main Application Logic ---
st.title(f"UAEW | {ACTIVE_TASK_NAME}")

# --- Session State Initialization ---
default_ss = {
    "user_confirmed": False, "current_user_id": "", "current_user_name": "User", 
    "current_user_image_url": "", "selected_status": "Todos", 
    "selected_event": "Todos os Eventos", "fighter_search_query": "", 
    "selected_badge_tasks": [],
    "hide_comments": False
}
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k]=v

# --- User Auth Section (código inalterado) ---
with st.container(border=True):
    st.subheader("User")
    col_input_ps, col_user_status_display = st.columns([0.6, 0.4])
    with col_input_ps:
        user_id_input = st.text_input("PS Number", value=st.session_state.current_user_id, max_chars=50, key="uid_w", label_visibility="collapsed", placeholder="Digite os 4 dígitos do seu PS")
        if st.button("Login", key="confirm_b_w", use_container_width=True, type="primary"):
            u_in = user_id_input.strip()
            if u_in:
                u_inf = get_valid_user_info(u_in)
                if u_inf:
                    st.session_state.update(current_user_id=u_in, current_user_name=str(u_inf.get("USER",u_in)).strip(), current_user_image_url=str(u_inf.get("USER_IMAGE","")).strip(), user_confirmed=True)
                else:
                    st.session_state.update(user_confirmed=False, current_user_image_url="", current_user_name="User")
                    st.warning(f"⚠️ Usuário '{u_in}' não encontrado.")
            else:
                st.warning("⚠️ ID do usuário não pode ser vazio.")
    with col_user_status_display:
        if st.session_state.user_confirmed:
            un = html.escape(st.session_state.current_user_name)
            ui = html.escape(st.session_state.current_user_id)
            uim = st.session_state.current_user_image_url
            image_html = f"""<img src="{html.escape(uim, True)}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:10px;">""" if uim else ""
            st.markdown(f"""<div style="display:flex;align-items:center;height:50px;">{image_html}<div><span style="font-weight:bold;">{un}</span><br><span style="font-size:0.9em;color:#ccc;">PS: {ui}</span></div></div>""", unsafe_allow_html=True)

# --- Main App Content ---
if st.session_state.user_confirmed:
    with st.spinner("Carregando dados..."):
        all_tasks_from_config = load_config_data()
        df_athletes = load_athlete_data()
        df_attendance = load_attendance_data()

    # --- Sidebar Section ---
    with st.sidebar:
        st.header("Filtros")
        st.selectbox("Filtrar Evento:", options=["Todos os Eventos"] + sorted([evt for evt in df_athletes["EVENT"].unique() if evt != "Z"]), key="selected_event")
        
        selected_tasks = st.multiselect(
            "Exibir Badges de Tarefas:",
            options=all_tasks_from_config,
            default=st.session_state.selected_badge_tasks,
            help="Escolha quais tarefas concluídas aparecerão como badges em cada atleta."
        )
        st.session_state.selected_badge_tasks = selected_tasks
        
        st.divider()

        hide_actions = st.toggle(
            "Ocultar Comentários", 
            value=st.session_state.hide_comments,
            help="Oculta a caixa de notas para uma visualização mais limpa."
        )
        st.session_state.hide_comments = hide_actions

    df_athletes[['current_task_status', 'latest_task_user', 'latest_task_timestamp']] = df_athletes['ID'].apply(
        lambda id: pd.Series(get_latest_status_and_user(id, ACTIVE_TASK_NAME, df_attendance))
    )
    st.divider()

    status_options_radio = ["Todos"] + BUS_ATTENDANCE_STATUSES
    st.radio("Filtrar por Status:", options=status_options_radio, horizontal=True, key="selected_status")
    st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID...", key="fighter_search_query")
    st.divider()

    df_filtered = df_athletes.copy()
    if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]
    if st.session_state.selected_status != "Todos": df_filtered = df_filtered[df_filtered['current_task_status'] == st.session_state.selected_status]
    search_term = st.session_state.fighter_search_query.strip().lower()
    if search_term: df_filtered = df_filtered[df_filtered.apply(lambda row: search_term in str(row['NAME']).lower() or search_term in str(row['ID']).lower(), axis=1)]

    st.markdown(f"Exibindo **{len(df_filtered)}** atletas.")

    for i_l, row in df_filtered.iterrows():
        ath_id_d, ath_name_d, ath_event_d = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
        curr_ath_task_stat = row.get('current_task_status', STATUS_PENDING)
        status_bar_color = STATUS_COLOR_MAP.get(curr_ath_task_stat, STATUS_COLOR_MAP[STATUS_PENDING])
        
        # ### ALTERAÇÃO APLICADA AQUI ###
        # O `border=True` foi removido para eliminar a linha externa.
        with st.container(border=False):
            col_card, col_buttons = st.columns([2.5, 1])

            with col_card:
                mob_r = str(row.get("MOBILE", "")).strip()
                wa_link_html = ""
                if mob_r:
                    phone_digits = "".join(filter(str.isdigit, mob_r))
                    if phone_digits.startswith('00'): phone_digits = phone_digits[2:]
                    if phone_digits: wa_link_html = f"""<p style='margin-top: 8px; font-size:14px;'><a href='https://wa.me/{html.escape(phone_digits, True)}' target='_blank' style='color:#25D366; text-decoration:none; font-weight:bold;'> WhatsApp</a></p>"""

                st.markdown(f"""
                <div style='background-color:#2E2E2E; border-left: 5px solid {status_bar_color}; padding: 15px; border-radius: 10px; min-height: 130px;'>
                    <div style='display:flex; align-items:center; gap:20px;'>
                        <img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/120?text=No+Image"), True)}' style='width:100px; height:100px; border-radius:50%; object-fit:cover;'>
                        <div style='flex-grow: 1;'>
                            <h4 style='margin:0; font-size:1.5em; line-height: 1.2;'>{html.escape(ath_name_d)} <span style='font-size:0.6em; color:#cccccc;'>{html.escape(ath_event_d)} (ID: {html.escape(ath_id_d)})</span></h4>
                            <p style='margin:5px 0 0 0;'>Status: <strong>{html.escape(str(curr_ath_task_stat))}</strong></p>
                            {wa_link_html}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.session_state.selected_badge_tasks:
                    badges_html = "<div style='display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; margin-left: 5px;'>"
                    for task_for_badge in st.session_state.selected_badge_tasks:
                        status_for_badge, user_for_badge, ts_for_badge = get_latest_status_and_user(ath_id_d, task_for_badge, df_attendance)
                        color = STATUS_COLOR_MAP.get(status_for_badge, STATUS_COLOR_MAP[STATUS_PENDING])
                        badge_style = f"background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px;"
                        tooltip_content = f"Status: {str(status_for_badge)}\\nAtualizado por: {str(user_for_badge)}\\nEm: {str(ts_for_badge)}"
                        badges_html += f"<span style='{badge_style}' title='{html.escape(tooltip_content, quote=True)}'>{html.escape(str(task_for_badge))}</span>"
                    badges_html += "</div>"
                    st.markdown(badges_html, unsafe_allow_html=True)
                
                notes_input = ""
                if not st.session_state.hide_comments:
                    st.write("")
                    notes_input = st.text_area("Adicionar Nota (opcional):", key=f"notes_{ath_id_d}_{i_l}", height=80, placeholder="Ex: Acompanhado pelo treinador...")

            with col_buttons:
                st.write("") 
                uid_l = st.session_state.current_user_id
                
                if curr_ath_task_stat == STATUS_PENDING:
                    if st.button("Check in Bus", key=f"checkin_{ath_id_d}_{i_l}", type="primary", use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, ACTIVE_TASK_NAME, STATUS_CHECKED_IN, notes_input, uid_l):
                            time.sleep(1); st.rerun()
                    if st.button("Private Car", key=f"private_{ath_id_d}_{i_l}", use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, ACTIVE_TASK_NAME, STATUS_PRIVATE_CAR, notes_input, uid_l):
                            time.sleep(1); st.rerun()
                else:
                    st.success(f"Status: **{curr_ath_task_stat}**")
                    if st.button("Reverter para Pendente", key=f"revert_{ath_id_d}_{i_l}", use_container_width=True):
                        if registrar_log(ath_id_d, ath_name_d, ath_event_d, ACTIVE_TASK_NAME, STATUS_PENDING, f"Revertido de '{curr_ath_task_stat}'", uid_l):
                            time.sleep(1); st.rerun()
        # Adiciona um separador visual entre os atletas
        st.divider()

else:
    st.warning("🚨 Por favor, faça o login para continuar.", icon="🚨")
