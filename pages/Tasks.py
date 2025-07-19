# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html

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
STATUS_PENDING_EQUIVALENTS = ["Pending", "---", "Not Registred"]

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
        df = pd.DataFrame(worksheet.get_all_records())
        if df.empty: return pd.DataFrame()

        df.columns = df.columns.str.strip()
        required_cols = ["ROLE", "INACTIVE", "NAME", "ID"]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"Coluna obrigatória '{col}' não encontrada na aba de atletas.", icon="🚨"); return pd.DataFrame()

        df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        
        df["EVENT"] = df["EVENT"].fillna("Z") if "EVENT" in df.columns else "Z"
        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
        
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar dados dos atletas: {e}", icon="🚨"); return pd.DataFrame()

@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, users_tab_name)
        return pd.DataFrame(worksheet.get_all_records())
    except Exception as e:
        st.error(f"Erro ao carregar usuários '{users_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def get_valid_user_info(user_input: str, users_df: pd.DataFrame):
    if not user_input or users_df.empty: return None
    
    proc_input = user_input.strip().upper()
    val_id_input = proc_input[2:] if proc_input.startswith("PS") and len(proc_input) > 2 and proc_input[2:].isdigit() else proc_input
    
    users_df['PS_str'] = users_df['PS'].astype(str).str.strip()
    users_df['USER_upper'] = users_df['USER'].astype(str).str.strip().str.upper()

    user_record = users_df[
        (users_df['PS_str'] == val_id_input) | 
        ("PS" + users_df['PS_str'] == proc_input) |
        (users_df['USER_upper'] == proc_input)
    ]
    
    if not user_record.empty:
        return user_record.iloc[0].to_dict()
    return None

@st.cache_data(ttl=600)
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
        df_conf = pd.DataFrame(worksheet.get_all_records())
        tasks = df_conf["TaskList"].dropna().unique().tolist() if "TaskList" in df_conf.columns else []
        statuses = df_conf["TaskStatus"].dropna().unique().tolist() if "TaskStatus" in df_conf.columns else []
        return tasks, statuses
    except Exception as e: st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨"); return [], []

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame(columns=["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"])
        
        df_att[ID_COLUMN_IN_ATTENDANCE] = df_att[ID_COLUMN_IN_ATTENDANCE].astype(str)
        df_att['TS_dt'] = pd.to_datetime(df_att['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        return df_att
    except Exception as e: st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        
        all_vals = log_ws.get_all_values()
        next_num = len(all_vals) if all_vals else 1
        
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        load_attendance_data.clear()
        return True
    except Exception as e: st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨"); return False

# --- 4. UI Components & Logic Functions ---

def initialize_session_state():
    """Initializes all required session state keys."""
    default_ss = {
        "user_confirmed": False,
        "current_user_id": "",
        "current_user_name": "User",
        "current_user_image_url": "",
        "user_id_input": "",
        "show_personal_data": True,
        "selected_task": NO_TASK_SELECTED_LABEL,
        "selected_statuses": [],
        "selected_event": "Todos os Eventos",
        "fighter_search_query": ""
    }
    for k, v in default_ss.items():
        if k not in st.session_state:
            st.session_state[k] = v

def handle_logout():
    """Resets session state upon user logout."""
    st.session_state.user_confirmed = False
    st.session_state.current_user_id = ""
    st.session_state.current_user_name = "User"
    st.session_state.current_user_image_url = ""
    st.session_state.user_id_input = ""
    st.toast("Logout realizado com sucesso!", icon="👋")

def display_login_form():
    """Displays the login form and handles authentication logic."""
    with st.container(border=True):
        st.subheader("Login de Usuário")
        users_df = load_users_data()
        
        user_input = st.text_input(
            "Digite seu PS ou Nome de Usuário",
            value=st.session_state.user_id_input,
            key="user_id_input_widget",
            placeholder="Ex: 1234 ou John Doe"
        )

        if st.button("Login", type="primary", use_container_width=True):
            if user_input:
                user_info = get_valid_user_info(user_input, users_df)
                if user_info:
                    st.session_state.update(
                        user_confirmed=True,
                        current_user_id=str(user_info.get("PS", "")).strip(),
                        current_user_name=str(user_info.get("USER", "")).strip(),
                        current_user_image_url=str(user_info.get("USER_IMAGE", "")).strip(),
                        user_id_input=user_input
                    )
                    st.rerun()
                else:
                    st.error(f"Usuário '{user_input}' não encontrado.", icon="🚨")
            else:
                st.warning("Por favor, insira seu PS ou nome.", icon="⚠️")

def display_logged_in_header():
    """Displays the header for a logged-in user with their info and a logout button."""
    with st.container(border=True):
        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            name = html.escape(st.session_state.current_user_name)
            uid = html.escape(st.session_state.current_user_id)
            img_url = st.session_state.current_user_image_url
            
            image_html = f"""<img src="{html.escape(img_url, True)}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:10px;">""" if img_url else ""
            st.markdown(f"""
            <div style="display:flex;align-items:center;height:50px;">
                {image_html}
                <div>
                    <span style="font-weight:bold;font-size:1.1em;">Bem-vindo, {name}</span><br>
                    <span style="font-size:0.9em;color:#ccc;">PS: {uid}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.button("Logout", on_click=handle_logout, use_container_width=True)

def get_latest_task_status(df_attendance, athlete_id, event, task_name):
    """Finds the most recent record for a specific task, athlete, and event."""
    if df_attendance.empty or not task_name:
        return None
    
    task_records = df_attendance[
        (df_attendance[ID_COLUMN_IN_ATTENDANCE] == athlete_id) &
        (df_attendance["Task"] == task_name) &
        (df_attendance["Event"] == event)
    ]
    
    if task_records.empty:
        return None
        
    # Sort by timestamp (TS_dt) and return the latest one
    latest_record = task_records.sort_values(by="TS_dt", ascending=False).iloc[0]
    return latest_record.to_dict()

def display_athlete_card(athlete_row, tasks_list, statuses_list, df_attendance):
    """Renders a single athlete information card including their task statuses."""
    ath_id = str(athlete_row["ID"])
    ath_name = str(athlete_row["NAME"])
    ath_event = str(athlete_row["EVENT"])
    sel_task = st.session_state.selected_task if st.session_state.selected_task != NO_TASK_SELECTED_LABEL else None

    # --- Card Header & Status Display ---
    latest_rec_task = get_latest_task_status(df_attendance, ath_id, ath_event, sel_task) if sel_task else None
    
    task_stat_disp = "Pendente / Não Registrado"
    card_bg_col = "#1e1e1e" # Default background
    
    if latest_rec_task:
        status_val = str(latest_rec_task.get('Status', ''))
        timestamp_str = str(latest_rec_task.get('Timestamp', '')).split(' ')[0]
        user_val = str(latest_rec_task.get('User', ''))
        task_stat_disp = f"**{html.escape(status_val)}** | {html.escape(timestamp_str)} | *by {html.escape(user_val)}*"
        
        # Color coding
        if status_val == "Done": card_bg_col = "#143d14"
        elif status_val == "Requested": card_bg_col = "#B08D00"
        elif status_val == "Issue": card_bg_col = "#8b0000"

    # --- Personal Data HTML ---
    pd_html = ""
    if st.session_state.show_personal_data:
        pass_img_html = f"<tr><td><b>Passaporte Img:</b></td><td><a href='{html.escape(str(athlete_row.get('PASSPORT IMAGE','')),True)}' target='_blank'>Ver</a></td></tr>" if pd.notna(athlete_row.get("PASSPORT IMAGE")) and athlete_row.get("PASSPORT IMAGE") else ""
        pd_html = f"""
        <div style='flex-basis:350px;flex-grow:1;'>
            <table style='font-size:14px;'>
                <tr><td><b>Nascimento:</b></td><td>{html.escape(str(athlete_row.get("DOB","")))}</td></tr>
                <tr><td><b>Passaporte:</b></td><td>{html.escape(str(athlete_row.get("PASSPORT","")))}</td></tr>
                <tr><td><b>Expira em:</b></td><td>{html.escape(str(athlete_row.get("PASSPORT EXPIRE DATE","")))}</td></tr>
                {pass_img_html}
            </table>
        </div>"""
    
    # --- Main Card Structure ---
    st.markdown(f"""
    <div style='background-color:{card_bg_col};padding:20px;border-radius:10px;margin-bottom:5px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'>
        <div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'>
            <div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'>
                <img src='{html.escape(athlete_row.get("IMAGE", "https://via.placeholder.com/80?text=No+Img") or "https://via.placeholder.com/80?text=No+Img", True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;'>
                <div>
                    <h4 style='margin:0;font-size:1.5em;'>{html.escape(ath_name)}</h4>
                    <p style='margin:0;color:#ccc;'>{html.escape(ath_event)} | ID: {html.escape(ath_id)}</p>
                    <p style='margin:0;color:#a0f0a0;'>{task_stat_disp}</p>
                </div>
            </div>
            {pd_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Task Status Badges ---
    badges_html = "<div style='display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; margin-bottom: 20px;'>"
    status_color_map = {"Requested": "#D35400", "Done": "#1E8449", "Approved": "#27AE60", "Rejected": "#C0392B", "Issue": "#E74C3C"}
    default_color = "#34495E"

    for task in tasks_list:
        latest_badge_rec = get_latest_task_status(df_attendance, ath_id, ath_event, task)
        status = latest_badge_rec.get("Status") if latest_badge_rec and latest_badge_rec.get("Status") not in STATUS_PENDING_EQUIVALENTS else "Pending"
        color = status_color_map.get(status, default_color)
        badge_style = f"background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px;"
        badges_html += f"<span style='{badge_style}'>{html.escape(task)}</span>"
    badges_html += "</div>"
    st.markdown(badges_html, unsafe_allow_html=True)
    
    # --- Action Buttons ---
    if sel_task:
        uid = st.session_state.get("current_user_id", "Unknown")
        btn_key_base = f"{ath_id}_{sel_task.replace(' ','_')}"

        if sel_task == "Walkout Music":
            # Specific UI for Walkout Music
            music_link = st.text_input("Link da Música (YouTube)", key=f"music_link_{ath_id}", placeholder="Cole o link aqui...")
            if st.button(f"Registrar Música", key=f"reg_music_{btn_key_base}", type="primary"):
                if music_link and music_link.strip():
                    if registrar_log(ath_id, ath_name, ath_event, sel_task, "Done", music_link.strip(), uid):
                        st.rerun()
                else:
                    st.warning("O link da música não pode estar vazio.", icon="⚠️")
        else:
            # Generic buttons for other tasks
            current_status = latest_rec_task.get('Status') if latest_rec_task else None
            
            if current_status == "Requested":
                c1, c2 = st.columns(2)
                with c1:
                    if c1.button(f"CONCLUIR", key=f"done_btn_{btn_key_base}", use_container_width=True):
                        if registrar_log(ath_id, ath_name, ath_event, sel_task, "Done", "", uid): st.rerun()
                with c2:
                    if c2.button(f"CANCELAR SOL.", key=f"cancel_btn_{btn_key_base}", type="secondary", use_container_width=True):
                        if registrar_log(ath_id, ath_name, ath_event, sel_task, "---", "", uid): st.rerun()
            else:
                btn_label = "SOLICITAR"
                btn_type = "primary"
                if current_status == "Done":
                    btn_label = "Solicitar Novamente"
                    btn_type = "secondary"
                
                if st.button(btn_label, key=f"request_btn_{btn_key_base}", type=btn_type, use_container_width=True):
                    if registrar_log(ath_id, ath_name, ath_event, sel_task, "Requested", "", uid): st.rerun()
    
    st.markdown("<hr style='border-top:1px solid #333;margin-bottom:25px;'>", unsafe_allow_html=True)


# --- 5. Main Application ---
st.title("UAEW | Task Control")
initialize_session_state()

# --- Authentication Flow ---
if not st.session_state.user_confirmed:
    display_login_form()
    st.stop() # Stop execution if not logged in

# --- Main App (when logged in) ---
display_logged_in_header()
st.markdown("---")

# Load data once
with st.spinner("Carregando dados do aplicativo..."):
    df_athletes = load_athlete_data()
    df_attendance = load_attendance_data()
    tasks_raw, statuses_list_cfg = load_config_data()

if df_athletes.empty:
    st.warning("Nenhum atleta ativo encontrado.", icon="ℹ️")
    st.stop()

# --- Filters ---
tasks_for_select = [NO_TASK_SELECTED_LABEL] + tasks_raw
if not statuses_list_cfg: statuses_list_cfg = STATUS_PENDING_EQUIVALENTS + ["Requested", "Done", "Approved", "Rejected", "Issue"] 

c1, c2, c3 = st.columns([0.4, 0.4, 0.2])
with c1: st.selectbox("Tipo de verificação:", tasks_for_select, key="selected_task")
with c2: st.multiselect("Filtrar Status:", statuses_list_cfg, key="selected_statuses", disabled=(st.session_state.selected_task == NO_TASK_SELECTED_LABEL))
with c3: 
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Atualizar Dados", use_container_width=True, help="Força a recarga de todos os dados do Google Sheets"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.toast("Dados atualizados!", icon="🔄")
        st.rerun()

cf1, cf2 = st.columns([0.4, 0.6])
with cf1:
    event_list = sorted([evt for evt in df_athletes["EVENT"].unique() if evt != "Z"])
    st.selectbox("Filtrar Evento:", ["Todos os Eventos"] + event_list, key="selected_event")
with cf2:
    st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID...", key="fighter_search_query")

st.toggle("Mostrar Dados Pessoais", key="show_personal_data")
st.markdown("---")

# --- Filtering Logic ---
df_filtered = df_athletes.copy()

if st.session_state.selected_event != "Todos os Eventos":
    df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]

search_term = st.session_state.fighter_search_query.strip().lower()
if search_term:
    df_filtered = df_filtered[
        df_filtered["NAME"].str.lower().str.contains(search_term, na=False) |
        df_filtered["ID"].astype(str).str.lower().str.contains(search_term, na=False)
    ]

# Filter by task status
if st.session_state.selected_task != NO_TASK_SELECTED_LABEL and st.session_state.selected_statuses:
    athlete_ids_to_show = set()
    for _, row in df_filtered.iterrows():
        latest_status_rec = get_latest_task_status(df_attendance, str(row["ID"]), str(row["EVENT"]), st.session_state.selected_task)
        
        current_status = "Pending" # Default if no record found
        if latest_status_rec and latest_status_rec.get("Status") and latest_status_rec.get("Status") not in STATUS_PENDING_EQUIVALENTS:
            current_status = latest_status_rec.get("Status")

        if current_status in st.session_state.selected_statuses or \
           ("Pending" in st.session_state.selected_statuses and current_status in STATUS_PENDING_EQUIVALENTS):
            athlete_ids_to_show.add(str(row["ID"]))
            
    df_filtered = df_filtered[df_filtered["ID"].astype(str).isin(athlete_ids_to_show)]

# --- Display Athletes ---
st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
if st.session_state.selected_task == NO_TASK_SELECTED_LABEL:
    st.info("Selecione uma tarefa para ver os status e habilitar as ações de registro.", icon="ℹ️")

if df_filtered.empty:
    st.info("Nenhum atleta corresponde aos filtros selecionados.")
else:
    for _, row in df_filtered.iterrows():
        display_athlete_card(row, tasks_raw, statuses_list_cfg, df_attendance)
