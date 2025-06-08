# pages/1_Controle_de_Tarefas.py

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
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
NO_TASK_SELECTED_LABEL = "-- Selecione uma Tarefa --"
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
        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            if col in df.columns: df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
            else: df[col] = "" 
        for col_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE"]:
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

# CORREÇÃO: Adicionando a chave 'user_id_input' ao dicionário de valores padrão.
default_ss = {
    "warning_message": None, 
    "user_confirmed": False, 
    "current_user_id": "", 
    "current_user_name": "Usuário",
    "current_user_image_url": "", 
    "show_personal_data": True, 
    "selected_task": NO_TASK_SELECTED_LABEL, 
    "selected_statuses": [], 
    "search_query": "",
    "user_id_input": "" # Chave que estava faltando
}
# Este loop agora inicializará 'user_id_input' na primeira execução.
for k,v in default_ss.items():
    if k not in st.session_state: 
        st.session_state[k] = v

with st.container(border=True):
    st.subheader("Usuário")
    col_input_ps, col_user_status_display = st.columns([0.6, 0.4]) 
    with col_input_ps:
        # Agora, na primeira execução, st.session_state['user_id_input'] já existe e é uma string vazia.
        st.session_state['user_id_input'] = st.text_input("PS Number", value=st.session_state['user_id_input'], key="uid_w", label_visibility="collapsed", placeholder="Digite seu PS ou Nome")
        
        if st.button("Login", key="confirm_b_w", use_container_width=True, type="primary"):
            u_in=st.session_state['user_id_input'].strip()
            if u_in:
                u_inf=get_valid_user_info(u_in)
                if u_inf: 
                    st.session_state.update(
                        current_user_ps_id_internal=str(u_inf.get("PS",u_in)).strip(),
                        current_user_id=u_in, current_user_name=str(u_inf.get("USER",u_in)).strip(),
                        current_user_image_url=str(u_inf.get("USER_IMAGE","")).strip(),
                        user_confirmed=True, warning_message=None
                    )
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

    # Esta lógica de verificação agora funcionará corretamente.
    current_input_upper = st.session_state.user_id_input.strip().upper()
    current_id_upper = st.session_state.current_user_id.strip().upper()
    if st.session_state.user_confirmed and current_id_upper != current_input_upper and current_input_upper != "":
        st.session_state.update(user_confirmed=False, warning_message="⚠️ ID/Nome alterado. Confirme.", selected_task=NO_TASK_SELECTED_LABEL)
        st.rerun()

# --- O resto do código permanece o mesmo ---
if st.session_state.user_confirmed and st.session_state.current_user_name!="Usuário":
    # ... (código inalterado)
    st.markdown("---")
    with st.spinner("Carregando configurações..."):
        tasks_raw, statuses_list_cfg = load_config_data()
    tasks_for_select=[NO_TASK_SELECTED_LABEL] + tasks_raw
    if not tasks_raw: st.error("Lista de tarefas não carregada.", icon="🚨"); st.stop()
    
    cc1, cc2, cc3 = st.columns([0.4, 0.4, 0.2]) 
    with cc1: st.selectbox("Filtrar por Tarefa:", tasks_for_select, key="selected_task")
    with cc2: st.multiselect("Filtrar por Status:", statuses_list_cfg if statuses_list_cfg else [], key="selected_statuses", disabled=(st.session_state.selected_task == NO_TASK_SELECTED_LABEL))
    with cc3:
        st.markdown("<br>", True)
        st.button("🔄 Atualizar", help="Recarrega dados.", on_click=lambda:(load_athlete_data.clear(), load_users_data.clear(), load_config_data.clear(), load_attendance_data.clear(), st.toast("Dados atualizados!",icon="🔄"), st.rerun()), use_container_width=True)
    
    st.text_input("Buscar por Nome ou ID do Atleta:", key="search_query", placeholder="Digite para buscar...")
    st.toggle("Mostrar Dados Pessoais", value=st.session_state.show_personal_data, key="tgl_pd_w")
    st.markdown("---")

    with st.spinner("Carregando atletas..."): df_athletes = load_athlete_data()
    with st.spinner("Carregando registros..."): df_attendance = load_attendance_data()
    sel_task_actual = st.session_state.selected_task if st.session_state.selected_task != NO_TASK_SELECTED_LABEL else None
    
    if df_athletes.empty:
        st.info("Nenhum atleta para exibir.")
    else:
        df_filtered = df_athletes.copy()
        
        if sel_task_actual and st.session_state.selected_statuses:
            show_ids=set()
            df_att_filt = df_attendance.copy()
            if not df_att_filt.empty and ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns:
                df_att_filt[ID_COLUMN_IN_ATTENDANCE]=df_att_filt[ID_COLUMN_IN_ATTENDANCE].astype(str)
            for _,ath_r in df_filtered.iterrows():
                ath_id_f=str(ath_r["ID"])
                rel_att=pd.DataFrame()
                if not df_att_filt.empty and "Task" in df_att_filt.columns:
                    rel_att=df_att_filt[(df_att_filt[ID_COLUMN_IN_ATTENDANCE]==ath_id_f)&(df_att_filt["Task"]==sel_task_actual)]
                if not rel_att.empty:
                    if "Status" in rel_att.columns and any(s in st.session_state.selected_statuses for s in rel_att["Status"].unique()): show_ids.add(ath_id_f)
                elif any(s in st.session_state.selected_statuses for s in STATUS_PENDING_EQUIVALENTS): show_ids.add(ath_id_f)
            df_filtered=df_filtered[df_filtered["ID"].astype(str).isin(list(show_ids))]

        if st.session_state.search_query:
            query = st.session_state.search_query.lower()
            df_filtered = df_filtered[df_filtered.apply(lambda row: query in str(row['NAME']).lower() or query in str(row['ID']).lower(), axis=1)]

        st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
        if not sel_task_actual: st.info("Selecione uma tarefa para opções de registro e filtro.", icon="ℹ️")

        for i_l, row in df_filtered.iterrows(): 
            ath_id_d,ath_name_d,ath_event_d=str(row.get("ID","")),str(row.get("NAME","")),str(row.get("EVENT",""))
            task_stat_disp="Status: Pendente"; latest_rec_task=None
            
            if sel_task_actual and not df_attendance.empty:
                df_att_chk = df_attendance[df_attendance[ID_COLUMN_IN_ATTENDANCE].astype(str) == ath_id_d]
                ath_task_recs = df_att_chk[df_att_chk["Task"] == sel_task_actual] if "Task" in df_att_chk.columns else pd.DataFrame()
                if not ath_task_recs.empty:
                    if "Timestamp" in ath_task_recs.columns:
                        ath_task_recs["TS_dt"] = pd.to_datetime(ath_task_recs["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce')
                        latest_rec_task = ath_task_recs.sort_values(by="TS_dt", ascending=False).iloc[0].copy()
                    else:
                        latest_rec_task = ath_task_recs.iloc[-1].copy()
                    
                    task_stat_disp=f"Status: {latest_rec_task.get('Status','Pendente')}"
            
            card_bg_col="#1e1e1e"
            if latest_rec_task is not None:
                if latest_rec_task.get('Status')=="Done": card_bg_col="#143d14"
                elif latest_rec_task.get('Status')=="Requested": card_bg_col="#B08D00"
            
            pass_img_h = f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{html.escape(str(row.get('PASSPORT IMAGE','')))}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if row.get("PASSPORT IMAGE") else ""
            mob_r = str(row.get("MOBILE","")).strip().replace(" ","").replace("-","").replace("(","").replace(")","")
            wa_h = ""
            if mob_r:
                mob_p_clean = ''.join(filter(str.isdigit, mob_r))
                wa_h = f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{mob_p_clean}' target='_blank' style='color:#00BFFF;'>Msg</a></td></tr>"
            
            pd_tbl_h = f"""<div style='flex-basis:350px;flex-grow:1;'><table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'>
                <tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER","")))}</td></tr>
                <tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB","")))}</td></tr>
                <tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY","")))}</td></tr>
                <tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT","")))}</td></tr>
                <tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE","")))}</td></tr>
                {pass_img_h}{wa_h}
            </table></div>""" if st.session_state.show_personal_data else "..."
            
            st.markdown(f"""<div style='background-color:{card_bg_col};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'><div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'>
                <div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'>
                    <img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/80?text=No+Image"))}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'>
                    <div>
                        <h4 style='margin:0;text-align:center;font-size:1.5em;'>{html.escape(ath_name_d)}</h4>
                        <p style='margin:0;font-size:14px;color:#cccccc;text-align:center;'>{html.escape(ath_event_d)}</p>
                        <p style='margin:0;font-size:13px;color:#cccccc;text-align:center;'>ID: {html.escape(ath_id_d)}</p>
                    </div>
                </div>
                {pd_tbl_h}
            </div></div>""", unsafe_allow_html=True)

            if sel_task_actual:
                status_color_map = {"Done": "#143d14", "Requested": "#B08D00", "---": "#1e1e1e", "Pendente": "#dc3545"}
                curr_status = latest_rec_task.get('Status', 'Pendente') if latest_rec_task is not None else 'Pendente'
                if curr_status not in status_color_map: curr_status = 'Pendente'
                bg_color = status_color_map[curr_status]

                with st.container(border=False):
                    status_cols = st.columns([0.4, 0.3, 0.3])
                    with status_cols[0]:
                        st.markdown(f"""<div style='background-color:{bg_color}; padding: 10px; border-radius: 5px; text-align:center; color:white;'><b>{sel_task_actual}:</b> {curr_status}</div>""", unsafe_allow_html=True)
                    uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
                    if curr_status == 'Requested':
                        with status_cols[1]:
                            if st.button(f"✅ Concluir", key=f"done_{ath_id_d}_{i_l}", use_container_width=True):
                                registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, "Done", "", uid_l); st.rerun()
                        with status_cols[2]:
                            if st.button(f"❌ Cancelar Sol.", key=f"cancel_{ath_id_d}_{i_l}", use_container_width=True):
                                registrar_log(ath_id_d, ath_name_d, ath_event_d, "---", "", uid_l); st.rerun()
                    elif curr_status in ['Pendente', '---', 'Done']:
                         with status_cols[1]:
                            if st.button(f"🟨 Solicitar", key=f"req_{ath_id_d}_{i_l}", use_container_width=True, type="primary"):
                                registrar_log(ath_id_d, ath_name_d, ath_event_d, "Requested", "", uid_l); st.rerun()

            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>", True)
else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):
        st.warning("🚨 Confirme seu ID/Nome de usuário para continuar.", icon="🚨")
