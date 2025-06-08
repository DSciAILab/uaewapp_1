# pages/1_Controle_de_Tarefas.py

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html

# --- 1. Page Configuration ---
st.set_page_config(page_title="Controle de Tarefas", page_icon="✍️", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App" 
ATHLETES_TAB_NAME = "df" 
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance" 
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"
CONFIG_TAB_NAME = "Config"
NO_TASK_SELECTED_LABEL = "-- Selecione uma Tarefa para Ação --"
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"] 

# --- 2. Google Sheets Connection (código inalterado) ---
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

# --- 3. Data Loading (código inalterado) ---
@st.cache_data(ttl=600)
def load_athlete_data(sheet_name: str = MAIN_SHEET_NAME, athletes_tab_name: str = ATHLETES_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, athletes_tab_name)
        data = worksheet.get_all_records()
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        if df.empty or "ROLE" not in df.columns or "INACTIVE" not in df.columns:
            return pd.DataFrame()
        df.columns = df.columns.str.strip()
        if df["INACTIVE"].dtype == 'object':
            df["INACTIVE"] = df["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        else:
            df["INACTIVE"] = df["INACTIVE"].map({0: False, 1: True}).fillna(True)
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z") if "EVENT" in df.columns else "Z"
        date_cols = ["DOB", "PASSPORT EXPIRE DATE"]
        for col in date_cols:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
            else: df[col] = "" 
        for col_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE", "BLOOD TEST"]:
            if col_check in df.columns: df[col_check] = df[col_check].fillna("") 
            else: df[col_check] = ""
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
        if not data or len(data) < 1: return [],[]
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist()
        statuses = df_conf["TaskStatus"].dropna().astype(str).str.strip().unique().tolist()
        return tasks, statuses
    except Exception as e:
        st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨"); return [], []

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        expected_cols = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"]
        for col in expected_cols:
            if col not in df_att.columns: df_att[col] = None
        if ID_COLUMN_IN_ATTENDANCE in df_att.columns:
            df_att[ID_COLUMN_IN_ATTENDANCE] = df_att[ID_COLUMN_IN_ATTENDANCE].astype(str)
        if 'Task' in df_att.columns:
            df_att['Task'] = df_att['Task'].astype(str)
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(ath_id, ath_name, ath_event, task, status, notes, user_log_id):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        all_vals = log_ws.get_all_values()
        next_num = len(all_vals) + 1
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id)
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        load_attendance_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{ATTENDANCE_TAB_NAME}': {e}", icon="🚨"); return False

# --- 6. Main Application Logic ---
st.title("UAEW | Controle de Tarefas")
default_ss = {
    "warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "Usuário",
    "current_user_image_url": "", "show_personal_data": True, "selected_task": NO_TASK_SELECTED_LABEL, 
    "selected_statuses": [], "search_query": "", "user_id_input": ""
}
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k] = v

with st.container(border=True):
    # (Código de autenticação inalterado)
    st.subheader("Usuário")
    col_input_ps, col_user_status_display = st.columns([0.6, 0.4]) 
    with col_input_ps:
        st.session_state['user_id_input'] = st.text_input("PS Number", value=st.session_state.user_id_input, key="uid_w", label_visibility="collapsed", placeholder="Digite seu PS ou Nome")
        if st.button("Login", key="confirm_b_w", use_container_width=True, type="primary"):
            u_in=st.session_state.user_id_input.strip()
            if u_in:
                u_inf=get_valid_user_info(u_in)
                if u_inf: 
                    st.session_state.update(current_user_ps_id_internal=str(u_inf.get("PS",u_in)).strip(), current_user_id=u_in, current_user_name=str(u_inf.get("USER",u_in)).strip(), current_user_image_url=str(u_inf.get("USER_IMAGE","")).strip(), user_confirmed=True, warning_message=None)
                else: 
                    st.session_state.update(user_confirmed=False,current_user_image_url="",warning_message=f"⚠️ Usuário '{u_in}' não encontrado.")
            else: 
                st.session_state.update(warning_message="⚠️ ID/Nome do usuário vazio.",user_confirmed=False)
    with col_user_status_display:
        if st.session_state.user_confirmed and st.session_state.current_user_name != "Usuário":
            un, ui = html.escape(st.session_state.current_user_name), html.escape(st.session_state.get("current_user_ps_id_internal", ""))
            uim = st.session_state.get('current_user_image_url', "")
            image_html = f'<img src="{html.escape(uim, True)}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;border:1px solid #555;vertical-align:middle;margin-right:10px;">' if uim and uim.startswith("http") else "<div style='width:50px;height:50px;border-radius:50%;background-color:#333;margin-right:10px;display:inline-block;vertical-align:middle;'></div>"
            st.markdown(f'<div style="display:flex;align-items:center;height:50px;">{image_html}<div><span><b>{un}</b></span><br><span style="font-size:0.9em;color:#ccc;">PS: {ui}</span></div></div>', unsafe_allow_html=True)
        elif st.session_state.get('warning_message'): 
            st.warning(st.session_state.warning_message, icon="🚨")
    current_input_upper = st.session_state.user_id_input.strip().upper()
    current_id_upper = st.session_state.current_user_id.strip().upper()
    if st.session_state.user_confirmed and current_id_upper != current_input_upper and current_input_upper != "":
        st.session_state.update(user_confirmed=False, warning_message="⚠️ ID/Nome alterado. Confirme.", selected_task=NO_TASK_SELECTED_LABEL); st.rerun()

if st.session_state.user_confirmed and st.session_state.current_user_name!="Usuário":
    st.markdown("---")
    with st.spinner("Carregando configurações..."):
        tasks_raw, statuses_list_cfg = load_config_data()
    tasks_for_select=[NO_TASK_SELECTED_LABEL] + tasks_raw
    if not tasks_raw: st.error("Lista de tarefas não carregada.", icon="🚨"); st.stop()
    
    st.subheader("Filtros e Ações")
    cc1, cc2, cc3 = st.columns([0.4, 0.4, 0.2]) 
    with cc1: st.selectbox("Selecione uma Tarefa para Ação:", tasks_for_select, key="selected_task")
    with cc2: st.multiselect("Filtrar por Status (da tarefa selecionada):", statuses_list_cfg if statuses_list_cfg else [], key="selected_statuses", disabled=(st.session_state.selected_task == NO_TASK_SELECTED_LABEL))
    with cc3:
        st.markdown("<br>", True)
        st.button("🔄 Atualizar Dados", help="Recarrega todos os dados das planilhas.", on_click=lambda:(load_athlete_data.clear(), load_users_data.clear(), load_config_data.clear(), load_attendance_data.clear(), st.toast("Dados atualizados!",icon="🔄"), st.rerun()), use_container_width=True)
    
    st.text_input("Buscar por Nome ou ID do Atleta:", key="search_query", placeholder="Digite para buscar...")
    st.toggle("Mostrar Dados Pessoais", value=st.session_state.show_personal_data, key="tgl_pd_w")
    st.markdown("---")

    with st.spinner("Carregando dados dos atletas..."): df_athletes = load_athlete_data()
    with st.spinner("Carregando registros de presença..."): df_attendance = load_attendance_data()
    sel_task_actual = st.session_state.selected_task if st.session_state.selected_task != NO_TASK_SELECTED_LABEL else None
    
    if df_athletes.empty:
        st.info("Nenhum atleta ativo para exibir.")
    else:
        df_filtered = df_athletes.copy()
        
        if sel_task_actual and st.session_state.selected_statuses:
            show_ids=set()
            for _,ath_r in df_filtered.iterrows():
                ath_id_f=str(ath_r["ID"])
                rel_att=pd.DataFrame()
                if not df_attendance.empty and "Task" in df_attendance.columns:
                    rel_att=df_attendance[(df_attendance[ID_COLUMN_IN_ATTENDANCE]==ath_id_f)&(df_attendance["Task"]==sel_task_actual)]
                if not rel_att.empty:
                    if "Status" in rel_att.columns and any(s in st.session_state.selected_statuses for s in rel_att["Status"].unique()): show_ids.add(ath_id_f)
                elif any(s in st.session_state.selected_statuses for s in STATUS_PENDING_EQUIVALENTS): show_ids.add(ath_id_f)
            df_filtered=df_filtered[df_filtered["ID"].astype(str).isin(list(show_ids))]

        if st.session_state.search_query:
            query = st.session_state.search_query.lower()
            df_filtered = df_filtered[df_filtered.apply(lambda row: query in str(row['NAME']).lower() or query in str(row['ID']).lower(), axis=1)]

        st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
        
        for i_l, row in df_filtered.iterrows():
            with st.container(border=True):
                ath_id_d,ath_name_d,ath_event_d=str(row.get("ID","")),str(row.get("NAME","")),str(row.get("EVENT",""))
                
                col1, col2 = st.columns([0.4, 0.6])
                with col1:
                    # CORREÇÃO: Validar a URL da imagem antes de passar para st.image
                    image_url = row.get("IMAGE", "")
                    if isinstance(image_url, str) and image_url.startswith("http"):
                        st.image(image_url, width=150)
                    else:
                        st.image("https://via.placeholder.com/150?text=No+Image", width=150)
                    
                    st.subheader(ath_name_d)
                    st.caption(f"ID: {ath_id_d} | Evento: {ath_event_d}")

                with col2:
                    if st.session_state.show_personal_data:
                        mob_r = str(row.get("MOBILE","")).strip().replace(" ","").replace("-","").replace("(","").replace(")","")
                        wa_link = f"[Msg](https://wa.me/{''.join(filter(str.isdigit, mob_r))})" if mob_r else "N/A"
                        pass_img_link = f"[Ver Imagem]({row.get('PASSPORT IMAGE')})" if row.get('PASSPORT IMAGE') else "N/A"
                        personal_data = {
                            "Gênero": row.get("GENDER", "N/A"), "Nascimento": row.get("DOB", "N/A"),
                            "Nacionalidade": row.get("NATIONALITY", "N/A"), "Passaporte": row.get("PASSPORT", "N/A"),
                            "Expira em": row.get("PASSPORT EXPIRE DATE", "N/A"), "WhatsApp": wa_link,
                            "Passaporte Img.": pass_img_link}
                        st.table(pd.DataFrame(personal_data.items(), columns=["Campo", "Valor"]).set_index("Campo"))

                st.markdown("---")
                st.markdown("**Status de Todas as Tarefas:**")
                
                athlete_statuses = {}
                if not df_attendance.empty:
                    df_athlete_att = df_attendance[df_attendance[ID_COLUMN_IN_ATTENDANCE] == ath_id_d]
                    for task in tasks_raw:
                        task_records = df_athlete_att[df_athlete_att['Task'] == task]
                        if not task_records.empty:
                            latest = task_records.sort_values(by="Timestamp", ascending=False).iloc[0]
                            athlete_statuses[task] = latest.get("Status", "Pendente")
                        else:
                            athlete_statuses[task] = "Pendente"
                else:
                    for task in tasks_raw: athlete_statuses[task] = "Pendente"
                
                status_color_map = {"Done": "#143d14", "Requested": "#B08D00", "---": "#262730", "Pendente": "#dc3545"}
                cols_per_row = 4
                status_cols = st.columns(cols_per_row)
                col_idx = 0
                for task, status in athlete_statuses.items():
                    bg_color = status_color_map.get(status, "#dc3545")
                    with status_cols[col_idx]:
                        st.markdown(f"""<div style='background-color:{bg_color}; padding: 8px; border-radius: 5px; text-align:center; color:white; margin-bottom: 5px;'><small>{task}</small><br><b>{status}</b></div>""", unsafe_allow_html=True)
                    col_idx = (col_idx + 1) % cols_per_row

                if sel_task_actual:
                    st.markdown("---")
                    st.markdown(f"**Ações para: *{sel_task_actual}***")
                    uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
                    current_task_status = athlete_statuses.get(sel_task_actual, "Pendente")
                    action_cols = st.columns(3)
                    with action_cols[0]:
                        if current_task_status in ['Pendente', '---', 'Done']:
                            if st.button(f"🟨 Solicitar", key=f"req_{ath_id_d}_{i_l}", use_container_width=True, type="primary"):
                                registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Requested", "", uid_l); st.rerun()
                    with action_cols[1]:
                        if current_task_status == 'Requested':
                            if st.button(f"✅ Concluir", key=f"done_{ath_id_d}_{i_l}", use_container_width=True):
                                registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Done", "", uid_l); st.rerun()
                    with action_cols[2]:
                        if current_task_status == 'Requested':
                             if st.button(f"❌ Cancelar Sol.", key=f"cancel_{ath_id_d}_{i_l}", use_container_width=True):
                                registrar_log(ath_id_d, ath_name_d, ath_event_d, "---", "", uid_l); st.rerun()

else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):
        st.warning("🚨 Confirme seu ID/Nome de usuário para continuar.", icon="🚨")
