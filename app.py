# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import html
from PIL import Image
import io

# --- 1. Constants ---
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
        statuses = df_conf["TaskStatus"].dropna().unique().tolist() if "TaskStatus" in df_conf.columns else []
        if not tasks: st.warning(f"'TaskList' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        if not statuses: st.warning(f"'TaskStatus' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        return tasks, statuses
    except Exception as e: st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨"); return [], []

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        expected_cols_order = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"]
        for col in expected_cols_order:
            if col not in df_att.columns: df_att[col] = None
        return df_att
    except Exception as e: st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        all_vals = log_ws.get_all_values()
        next_num = 1
        if len(all_vals) > 1:
            last_entry_first_col = all_vals[-1][0] if all_vals[-1] else ''
            if str(last_entry_first_col).isdigit(): next_num = int(last_entry_first_col) + 1
            else: next_num = len(all_vals) 
        elif len(all_vals) == 1: next_num = 1
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id) if st.session_state.get('user_confirmed') else user_log_id
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        load_attendance_data.clear(); return True
    except Exception as e: st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨"); return False

# --- 4. Authentication Function ---
def authenticate_user():
    default_ss = {
        "warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "User",
        "current_user_image_url": "", "show_personal_data": True, "selected_task": NO_TASK_SELECTED_LABEL, 
        "selected_statuses": [], "selected_event": "Todos os Eventos", "fighter_search_query": ""
    }
    for k,v in default_ss.items():
        if k not in st.session_state: st.session_state[k]=v
    if 'user_id_input' not in st.session_state: st.session_state['user_id_input']=st.session_state['current_user_id']
    
    with st.container(border=True):
        st.subheader("User Authentication")
        col_input_ps, col_user_status_display = st.columns([0.6, 0.4]) 
        with col_input_ps:
            st.session_state['user_id_input'] = st.text_input(
                "PS Number", value=st.session_state['user_id_input'], 
                max_chars=50, key="uid_w", label_visibility="collapsed", placeholder="Type 4 digits of your PS"
            )
            if st.button("Login", key="confirm_b_w", use_container_width=True, type="primary"):
                u_in=st.session_state['user_id_input'].strip()
                if u_in:
                    u_inf=get_valid_user_info(u_in)
                    if u_inf: 
                        st.session_state.update(
                            current_user_ps_id_internal=str(u_inf.get("PS",u_in)).strip(), current_user_id=u_in,
                            current_user_name=str(u_inf.get("USER",u_in)).strip(), current_user_image_url=str(u_inf.get("USER_IMAGE","")).strip(),
                            user_confirmed=True, warning_message=None
                        )
                        st.rerun()
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

# --- 5. Page Functions ---
def home_page():
    st.title("UAEW | Task Control - Home")
    
    if not st.session_state.get("user_confirmed", False):
        authenticate_user()
    else:
        st.success(f"Bem-vindo(a), {st.session_state.current_user_name}!")
        
        # Overview statistics
        with st.spinner("Carregando dados..."):
            df_athletes = load_athlete_data()
            df_attendance = load_attendance_data()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Atletas", len(df_athletes))
        with col2:
            if not df_attendance.empty and 'Timestamp' in df_attendance.columns:
                today = datetime.now().strftime("%d/%m/%Y")
                # Convert to string and handle NaN values
                df_attendance['Timestamp_str'] = df_attendance['Timestamp'].astype(str).fillna('')
                today_records = df_attendance[df_attendance['Timestamp_str'].str.startswith(today)]
                st.metric("Registros Hoje", len(today_records))
            else:
                st.metric("Registros Hoje", 0)
        with col3:
            tasks, _ = load_config_data()
            st.metric("Tipos de Tarefas", len(tasks))
        
        st.markdown("---")
        st.subheader("Acesso Rápido")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Controle de Tarefas", use_container_width=True):
                st.switch_page("pages/1_Task_Control.py")
        with col2:
            if st.button("Gerenciamento de Atletas", use_container_width=True):
                st.switch_page("pages/2_Athletes_Management.py")
        with col3:
            if st.button("Relatórios", use_container_width=True):
                st.switch_page("pages/3_Reports.py")
        
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
            
def task_control_page():
    st.title("UAEW | Task Control")
    
    if not st.session_state.get("user_confirmed", False):
        authenticate_user()
        if not st.session_state.get("user_confirmed", False):
            return
    
    # Navigation
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("Home", use_container_width=True):
            st.switch_page("app.py")
    with col2:
        st.button("Controle de Tarefas", use_container_width=True, disabled=True)
    with col3:
        if st.button("Gerenciamento de Atletas", use_container_width=True):
            st.switch_page("pages/2_Athletes_Management.py")
    with col4:
        if st.button("Relatórios", use_container_width=True):
            st.switch_page("pages/3_Reports.py")
    
    st.markdown("---")
    
    with st.spinner("Carregando dados..."):
        tasks_raw,statuses_list_cfg=load_config_data()
        df_athletes=load_athlete_data()
    
    tasks_for_select=[NO_TASK_SELECTED_LABEL]+tasks_raw
    if not tasks_raw:st.error("Lista de tarefas não carregada.",icon="🚨");st.stop()
    if not statuses_list_cfg:statuses_list_cfg=STATUS_PENDING_EQUIVALENTS+["Requested","Done","Approved","Rejected","Issue"]
    
    cc1,cc2,cc3=st.columns([0.4,0.4,0.2]) 
    with cc1:st.session_state.selected_task=st.selectbox("Tipo de verificação:",tasks_for_select,index=tasks_for_select.index(st.session_state.selected_task) if st.session_state.selected_task in tasks_for_select else 0,key="tsel_w")
    with cc2:st.session_state.selected_statuses=st.multiselect("Filtrar Status:",statuses_list_cfg,default=st.session_state.selected_statuses or [],key="smul_w",disabled=(st.session_state.selected_task==NO_TASK_SELECTED_LABEL))
    with cc3:st.markdown("<br>",True);st.button("🔄 Atualizar",key="ref_b_w",help="Recarrega dados.",on_click=lambda:(load_athlete_data.clear(), load_users_data.clear(), load_config_data.clear(), load_attendance_data.clear(), st.toast("Dados atualizados!",icon="🔄"),st.rerun()),use_container_width=True)
    
    col_filter1, col_filter2 = st.columns([0.4, 0.6])
    with col_filter1:
        event_list = sorted([evt for evt in df_athletes["EVENT"].unique() if evt != "Z"]) if not df_athletes.empty and "EVENT" in df_athletes.columns else []
        event_options = ["Todos os Eventos"] + event_list
        st.session_state.selected_event = st.selectbox("Filtrar Evento:", options=event_options, key="event_filter_w")
    with col_filter2:
        st.session_state.fighter_search_query = st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_w")
    st.session_state.show_personal_data=st.toggle("Mostrar Dados Pessoais",value=st.session_state.show_personal_data,key="tgl_pd_w")
    st.markdown("---")
    with st.spinner("Carregando registros..."): df_attendance=load_attendance_data()
        
    sel_task_actual=st.session_state.selected_task if st.session_state.selected_task!=NO_TASK_SELECTED_LABEL else None
    
    if df_athletes.empty: st.info("Nenhum atleta para exibir.")
    else:
        df_filtered = df_athletes.copy() 
        if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["EVENT"] == st.session_state.selected_event]
        search_term = st.session_state.fighter_search_query.strip().lower()
        if search_term: df_filtered = df_filtered[df_filtered["NAME"].str.lower().str.contains(search_term, na=False) | df_filtered["ID"].astype(str).str.lower().str.contains(search_term, na=False)]
        
        if sel_task_actual and st.session_state.selected_statuses:
            show_ids=set()
            df_att_filt=df_attendance.copy()
            if ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns: df_att_filt[ID_COLUMN_IN_ATTENDANCE]=df_att_filt[ID_COLUMN_IN_ATTENDANCE].astype(str)
            for _,ath_r in df_filtered.iterrows():
                ath_id_f=str(ath_r["ID"])
                ath_event_f = str(ath_r["EVENT"])
                rel_att=df_att_filt[(df_att_filt[ID_COLUMN_IN_ATTENDANCE]==ath_id_f) & (df_att_filt["Task"]==sel_task_actual) & (df_att_filt["Event"]==ath_event_f)] if ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns and "Task" in df_att_filt.columns else pd.DataFrame()
                if not rel_att.empty:
                    if "Status" in rel_att.columns and any(s in st.session_state.selected_statuses for s in rel_att["Status"].unique()):show_ids.add(ath_id_f)
                elif rel_att.empty and any(s in st.session_state.selected_statuses for s in STATUS_PENDING_EQUIVALENTS):show_ids.add(ath_id_f)
            df_filtered=df_filtered[df_filtered["ID"].astype(str).isin(list(show_ids))]
            
        st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
        if not sel_task_actual: st.info("Selecione uma tarefa para opções de registro e filtro.",icon="ℹ️")
        for i_l,row in df_filtered.iterrows(): 
            ath_id_d,ath_name_d,ath_event_d=str(row["ID"]),str(row["NAME"]),str(row["EVENT"])
            task_stat_disp="Pendente / Não Registrado";latest_rec_task=None
            
            df_att_chk = pd.DataFrame()
            if not df_attendance.empty:
                df_att_chk=df_attendance.copy()
                if ID_COLUMN_IN_ATTENDANCE in df_att_chk.columns: df_att_chk[ID_COLUMN_IN_ATTENDANCE]=df_att_chk[ID_COLUMN_IN_ATTENDANCE].astype(str)
            if sel_task_actual and not df_att_chk.empty:
                ath_task_recs=df_att_chk[
                    (df_att_chk.get(ID_COLUMN_IN_ATTENDANCE)==ath_id_d) & 
                    (df_att_chk.get("Task")==sel_task_actual) &
                    (df_att_chk.get("Event")==ath_event_d)
                ]
                if not ath_task_recs.empty and "Status" in ath_task_recs.columns:
                    latest_rec_task = ath_task_recs.iloc[-1].copy()
                    if "Timestamp" in ath_task_recs.columns:
                        try:
                            tmp_df=ath_task_recs.copy();tmp_df["TS_dt"]=pd.to_datetime(tmp_df["Timestamp"],format="%d/%m/%Y %H:%M:%S",errors='coerce')
                            tmp_df.dropna(subset=["TS_dt"],inplace=True)
                            if not tmp_df.empty:latest_rec_task=tmp_df.sort_values(by="TS_dt",ascending=False).iloc[0].copy()
                        except:pass
                    
                    if latest_rec_task is not None and pd.notna(latest_rec_task.get('Status')):
                        status_val = str(latest_rec_task.get('Status', ''))
                        timestamp_str = str(latest_rec_task.get('Timestamp', ''))
                        date_part = timestamp_str.split(' ')[0] if ' ' in timestamp_str else ''
                        user_val = str(latest_rec_task.get('User', ''))
                        task_stat_disp = f"**{html.escape(status_val)}** | {html.escape(date_part)} | *{html.escape(user_val)}*"
            
            card_bg_col="#1e1e1e";curr_stat_color=latest_rec_task.get('Status') if latest_rec_task is not None else None
            if curr_stat_color=="Done":card_bg_col="#143d14"
            elif curr_stat_color=="Requested":card_bg_col="#B08D00"
            pass_img_h=f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{html.escape(str(row.get('PASSPORT IMAGE','')),True)}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if pd.notna(row.get("PASSPORT IMAGE"))and row.get("PASSPORT IMAGE")else ""
            mob_r = str(row.get("MOBILE", "")).strip()
            wa_h = ""
            if mob_r:
                phone_digits = "".join(filter(str.isdigit, mob_r))
                if phone_digits.startswith('00'): phone_digits = phone_digits[2:]
                if phone_digits: wa_h = f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{html.escape(phone_digits, True)}' target='_blank' style='color:#00BFFF;'>Msg</a></td></tr>"
            pd_tbl_h=f"""<div style='flex-basis:350px;flex-grow:1;'><table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'><tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE","")))}</td></tr>{pass_img_h}{wa_h}</table></div>"""if st.session_state.show_personal_data else"<div style='flex-basis:300px;flex-grow:1;font-style:italic;color:#ccc;font-size:13px;text-align:center;'>Dados pessoais ocultos.</div>"
            st.markdown(f"""<div style='background-color:{card_bg_col};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'><div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'><div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'><img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/80?text=No+Image")if pd.notna(row.get("IMAGE"))and row.get("IMAGE")else"https://via.placeholder.com/80?text=No+Image",True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'><div><h4 style='margin:0;text-align:center;font-size:1.5em;'>{html.escape(ath_name_d)}</h4><p style='margin:0;font-size:14px;color:#cccccc;text-align:center;'>{html.escape(ath_event_d)}</p><p style='margin:0;font-size:13px;color:#cccccc;text-align:center;'>ID: {html.escape(ath_id_d)}</p><p style='margin:0;font-size:13px;color:#a0f0a0;text-align:center;'>{task_stat_disp}</p></div></div>{pd_tbl_h}</div></div>""",True)
            
            badges_html = "<div style='display: flex; flex-wrap: wrap; gap: 8px; margin-top: -5px; margin-bottom: 20px;'>"
            status_color_map = {"Requested": "#D35400", "Done": "#1E8449", "---": "#34495E"}
            default_color = "#C0392B"
            for task_name in tasks_raw:
                status_for_badge = "Pending"
                if not df_att_chk.empty:
                    task_records = df_att_chk[
                        (df_att_chk.get(ID_COLUMN_IN_ATTENDANCE) == ath_id_d) & 
                        (df_att_chk.get("Task") == task_name) &
                        (df_att_chk.get("Event") == ath_event_d)
                    ]
                    if not task_records.empty:
                        if "Timestamp" in task_records.columns:
                            task_records['TS_dt'] = pd.to_datetime(task_records['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
                            latest_record = task_records.sort_values(by="TS_dt", ascending=False).iloc[0]
                            status_for_badge = latest_record.get("Status", "Pending")
                        else:
                            status_for_badge = task_records.iloc[-1].get("Status", "Pending")
                
                color = status_color_map.get(status_for_badge, default_color)
                if status_for_badge in STATUS_PENDING_EQUIVALENTS: color = default_color
                badge_style = f"background-color: {color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;"
                badges_html += f"<span style='{badge_style}'>{html.escape(task_name)}</span>"
            
            badges_html += "</div>"
            st.markdown(badges_html, unsafe_allow_html=True)
            
            if sel_task_actual: 
                if sel_task_actual=="Walkout Music":
                    m_keys=[f"music_link_1_{ath_id_d}",f"music_link_2_{ath_id_d}",f"music_link_3_{ath_id_d}"]
                    for mk in m_keys:
                        if mk not in st.session_state:st.session_state[mk]=""
                    st.markdown("##### Links para Walkout Music:")
                    for j,mk_k in enumerate(m_keys):st.session_state[mk_k]=st.text_input(f"Música {j+1}",value=st.session_state[mk_k],key=f"m{j+1}_in_{ath_id_d}_{i_l}",placeholder="Link YouTube")
                    if st.button(f"Registrar Músicas para {ath_name_d}",key=f"reg_m_b_{ath_id_d}_{i_l}",type="primary",use_container_width=True):
                        any_m_reg=False
                        for idx,link_u in enumerate([st.session_state[k_] for k_ in m_keys]):
                            if link_u and link_u.strip():
                                uid_l=st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id)
                                if registrar_log(ath_id_d,ath_name_d,ath_event_d,"Walkout Music","Done",link_u.strip(),uid_l):any_m_reg=True;st.session_state[m_keys[idx]]=""
                        if any_m_reg:st.rerun()
                        else:st.warning("Nenhum link de música válido.",icon="⚠️")
                else:
                    curr_ath_task_stat_btn=latest_rec_task.get('Status') if latest_rec_task is not None else None
                    if curr_ath_task_stat_btn=="Requested":
                        col_btn_act1,col_btn_act2=st.columns(2)
                        with col_btn_act1:
                            if st.button(f"CONCLUIR '{sel_task_actual}' (Done)",key=f"mark_done_b_{ath_id_d}_{sel_task_actual.replace(' ','_')}_{i_l}",type="primary",use_container_width=True):
                                uid_l=st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id);registrar_log(ath_id_d,ath_name_d,ath_event_d,sel_task_actual,"Done","",uid_l);st.rerun()
                        with col_btn_act2:
                            if st.button(f"CANCELAR SOL. '{sel_task_actual}' (---)",key=f"mark_pending_b_{ath_id_d}_{sel_task_actual.replace(' ','_')}_{i_l}",type="secondary",use_container_width=True):
                                uid_l=st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id);registrar_log(ath_id_d,ath_name_d,ath_event_d,sel_task_actual,"---","",uid_l);st.rerun()
                    else:
                        next_stat_log="Requested"
                        btn_lbl_task=f"SOLICITAR '{sel_task_actual}'"
                        btn_type_task="primary"
                        if curr_ath_task_stat_btn=="Done": btn_lbl_task=f"'{sel_task_actual}' FEITO. Solicitar Novamente?";btn_type_task="secondary"
                        if st.button(btn_lbl_task,key=f"mark_stat_b_{ath_id_d}_{sel_task_actual.replace(' ','_')}_{i_l}",type=btn_type_task,use_container_width=True):
                            uid_l=st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id);registrar_log(ath_id_d,ath_name_d,ath_event_d,sel_task_actual,next_stat_log,"",uid_l);st.rerun()
            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>",True)

def athletes_management_page():
    st.title("UAEW | Athletes Management")
    
    if not st.session_state.get("user_confirmed", False):
        authenticate_user()
        if not st.session_state.get("user_confirmed", False):
            return
    
    # Navigation
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("Home", use_container_width=True):
            st.switch_page("app.py")
    with col2:
        if st.button("Controle de Tarefas", use_container_width=True):
            st.switch_page("pages/1_Task_Control.py")
    with col3:
        st.button("Gerenciamento de Atletas", use_container_width=True, disabled=True)
    with col4:
        if st.button("Relatórios", use_container_width=True):
            st.switch_page("pages/3_Reports.py")
    
    st.markdown("---")
    
    with st.spinner("Carregando dados..."):
        df_athletes = load_athlete_data()
        df_attendance = load_attendance_data()
    
    if df_athletes.empty:
        st.error("Nenhum atleta encontrado.")
        return
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        event_list = sorted([evt for evt in df_athletes["EVENT"].unique() if evt != "Z"]) if not df_athletes.empty and "EVENT" in df_athletes.columns else []
        event_options = ["Todos os Eventos"] + event_list
        selected_event = st.selectbox("Filtrar Evento:", options=event_options)
    with col2:
        search_query = st.text_input("Pesquisar Atleta:", placeholder="Nome ou ID...")
    
    # Apply filters
    df_filtered = df_athletes.copy()
    if selected_event != "Todos os Eventos":
        df_filtered = df_filtered[df_filtered["EVENT"] == selected_event]
    
    if search_query:
        search_term = search_query.strip().lower()
        df_filtered = df_filtered[df_filtered["NAME"].str.lower().str.contains(search_term, na=False) | 
                                  df_filtered["ID"].astype(str).str.lower().str.contains(search_term, na=False)]
    
    st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
    
    # Display athletes in a table
    display_cols = ["ID", "NAME", "EVENT", "GENDER", "NATIONALITY", "MOBILE"]
    if "IMAGE" in df_filtered.columns:
        display_cols.insert(2, "IMAGE")
    
    # Create a copy for display
    df_display = df_filtered[display_cols].copy()
    
    # Format image column to show thumbnails
    if "IMAGE" in df_display.columns:
        df_display["IMAGE"] = df_display["IMAGE"].apply(lambda x: f'<img src="{x}" width="50">' if x and (x.startswith("http://") or x.startswith("https://")) else "")
    
    # Display the table
    st.dataframe(
        df_display,
        column_config={
            "ID": "ID",
            "NAME": "Nome",
            "EVENT": "Evento",
            "GENDER": "Gênero",
            "NATIONALITY": "Nacionalidade",
            "MOBILE": "Telefone",
            "IMAGE": st.column_config.ImageColumn("Foto")
        },
        use_container_width=True,
        hide_index=True
    )
    
    # Athlete details section
    st.markdown("---")
    st.subheader("Detalhes do Atleta")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_athlete_id = st.selectbox(
            "Selecione um atleta:",
            options=df_filtered["ID"].tolist(),
            format_func=lambda x: f"{x} - {df_filtered[df_filtered['ID'] == x]['NAME'].values[0]}"
        )
    
    if selected_athlete_id:
        athlete_data = df_filtered[df_filtered["ID"] == selected_athlete_id].iloc[0]
        
        with col2:
            col_img, col_info = st.columns([1, 3])
            
            with col_img:
                img_url = athlete_data.get("IMAGE", "")
                if img_url and (img_url.startswith("http://") or img_url.startswith("https://")):
                    st.image(img_url, width=150)
                else:
                    st.image("https://via.placeholder.com/150?text=No+Image", width=150)
            
            with col_info:
                st.markdown(f"### {athlete_data['NAME']}")
                st.markdown(f"**ID:** {athlete_data['ID']}")
                st.markdown(f"**Evento:** {athlete_data['EVENT']}")
                st.markdown(f"**Gênero:** {athlete_data.get('GENDER', '')}")
                st.markdown(f"**Nacionalidade:** {athlete_data.get('NATIONALITY', '')}")
                st.markdown(f"**Data de Nascimento:** {athlete_data.get('DOB', '')}")
                st.markdown(f"**Passaporte:** {athlete_data.get('PASSPORT', '')}")
                st.markdown(f"**Validade do Passaporte:** {athlete_data.get('PASSPORT EXPIRE DATE', '')}")
                st.markdown(f"**Telefone:** {athlete_data.get('MOBILE', '')}")
                
                if athlete_data.get("PASSPORT IMAGE"):
                    st.markdown(f"[Ver Imagem do Passaporte]({athlete_data['PASSPORT IMAGE']})")
                
                if athlete_data.get("MOBILE"):
                    phone_digits = "".join(filter(str.isdigit, athlete_data["MOBILE"]))
                    if phone_digits.startswith('00'): phone_digits = phone_digits[2:]
                    if phone_digits:
                        st.markdown(f"[Enviar WhatsApp](https://wa.me/{phone_digits})")
        
        # Task history for this athlete
        st.markdown("---")
        st.subheader("Histórico de Tarefas")
        
        if not df_attendance.empty:
            athlete_attendance = df_attendance[df_attendance[ID_COLUMN_IN_ATTENDANCE] == str(selected_athlete_id)].copy()
            
            if not athlete_attendance.empty:
                # Sort by timestamp (most recent first)
                if "Timestamp" in athlete_attendance.columns:
                    athlete_attendance["TS_dt"] = pd.to_datetime(athlete_attendance["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
                    athlete_attendance = athlete_attendance.sort_values("TS_dt", ascending=False)
                    athlete_attendance = athlete_attendance.drop(columns=["TS_dt"])
                
                # Display relevant columns
                display_cols = ["#", "Task", "Status", "User", "Timestamp", "Notes"]
                for col in display_cols:
                    if col not in athlete_attendance.columns:
                        athlete_attendance[col] = ""
                
                st.dataframe(
                    athlete_attendance[display_cols],
                    column_config={
                        "#": "#",
                        "Task": "Tarefa",
                        "Status": "Status",
                        "User": "Usuário",
                        "Timestamp": "Data/Hora",
                        "Notes": "Observações"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Nenhum registro de tarefas encontrado para este atleta.")
        else:
            st.info("Nenhum registro de tarefas encontrado.")

def reports_page():
    st.title("UAEW | Reports")
    
    if not st.session_state.get("user_confirmed", False):
        authenticate_user()
        if not st.session_state.get("user_confirmed", False):
            return
    
    # Navigation
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        if st.button("Home", use_container_width=True):
            st.switch_page("app.py")
    with col2:
        if st.button("Controle de Tarefas", use_container_width=True):
            st.switch_page("pages/1_Task_Control.py")
    with col3:
        if st.button("Gerenciamento de Atletas", use_container_width=True):
            st.switch_page("pages/2_Athletes_Management.py")
    with col4:
        st.button("Relatórios", use_container_width=True, disabled=True)
    
    st.markdown("---")
    
    with st.spinner("Carregando dados..."):
        df_athletes = load_athlete_data()
        df_attendance = load_attendance_data()
        tasks_raw, _ = load_config_data()
    
    # Report type selection
    report_type = st.selectbox(
        "Selecione o tipo de relatório:",
        ["Resumo Geral", "Status por Tarefa", "Atividade por Usuário", "Atividade por Evento"]
    )
    
    if report_type == "Resumo Geral":
        st.subheader("Resumo Geral")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Atletas", len(df_athletes))
        with col2:
            if not df_attendance.empty:
                total_records = len(df_attendance)
                st.metric("Total de Registros", total_records)
            else:
                st.metric("Total de Registros", 0)
        with col3:
            if not df_attendance.empty and "User" in df_attendance.columns:
                active_users = df_attendance["User"].nunique()
                st.metric("Usuários Ativos", active_users)
            else:
                st.metric("Usuários Ativos", 0)
        
        # Task completion rates
        st.markdown("---")
        st.subheader("Taxa de Conclusão por Tarefa")
        
        if not df_attendance.empty and tasks_raw:
            task_stats = []
            
            for task in tasks_raw:
                task_records = df_attendance[df_attendance["Task"] == task]
                if not task_records.empty:
                    total = len(task_records)
                    done = len(task_records[task_records["Status"] == "Done"])
                    completion_rate = (done / total) * 100 if total > 0 else 0
                    task_stats.append({
                        "Tarefa": task,
                        "Total": total,
                        "Concluídos": done,
                        "Taxa de Conclusão": f"{completion_rate:.1f}%"
                    })
                else:
                    task_stats.append({
                        "Tarefa": task,
                        "Total": 0,
                        "Concluídos": 0,
                        "Taxa de Conclusão": "0%"
                    })
            
            df_task_stats = pd.DataFrame(task_stats)
            st.dataframe(df_task_stats, use_container_width=True, hide_index=True)
            
            # Visualize with bar chart
            st.bar_chart(df_task_stats.set_index("Tarefa")["Taxa de Conclusão"])
        else:
            st.info("Não há dados suficientes para gerar este relatório.")
    
    elif report_type == "Status por Tarefa":
        st.subheader("Status por Tarefa")
        
        if not df_attendance.empty and tasks_raw:
            selected_task = st.selectbox("Selecione uma tarefa:", tasks_raw)
            
            task_records = df_attendance[df_attendance["Task"] == selected_task]
            
            if not task_records.empty:
                # Count by status
                status_counts = task_records["Status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Contagem"]
                
                st.dataframe(status_counts, use_container_width=True, hide_index=True)
                
                # Visualize with pie chart
                st.write("Distribuição de Status:")
                st.bar_chart(status_counts.set_index("Status")["Contagem"])
                
                # Show details
                st.markdown("---")
                st.write("Registros Detalhados:")
                
                # Sort by timestamp (most recent first)
                if "Timestamp" in task_records.columns:
                    # Convert to string and handle NaN values before parsing
                    task_records["Timestamp_str"] = task_records["Timestamp"].astype(str).fillna('')
                    task_records["TS_dt"] = pd.to_datetime(
                        task_records["Timestamp_str"], 
                        format="%d/%m/%Y %H:%M:%S", 
                        errors="coerce"
                    )
                    task_records = task_records.sort_values("TS_dt", ascending=False)
                    task_records = task_records.drop(columns=["TS_dt", "Timestamp_str"])
                
                # Display relevant columns
                display_cols = ["#", "Name", "Event", "Status", "User", "Timestamp", "Notes"]
                for col in display_cols:
                    if col not in task_records.columns:
                        task_records[col] = ""
                
                st.dataframe(
                    task_records[display_cols],
                    column_config={
                        "#": "#",
                        "Name": "Nome",
                        "Event": "Evento",
                        "Status": "Status",
                        "User": "Usuário",
                        "Timestamp": "Data/Hora",
                        "Notes": "Observações"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"Nenhum registro encontrado para a tarefa '{selected_task}'.")
        else:
            st.info("Não há dados suficientes para gerar este relatório.")
    
    elif report_type == "Atividade por Usuário":
        st.subheader("Atividade por Usuário")
        
        if not df_attendance.empty and "User" in df_attendance.columns:
            user_activity = df_attendance["User"].value_counts().reset_index()
            user_activity.columns = ["Usuário", "Registros"]
            
            st.dataframe(user_activity, use_container_width=True, hide_index=True)
            
            # Visualize with bar chart
            st.bar_chart(user_activity.set_index("Usuário")["Registros"])
            
            # Detailed activity for selected user
            st.markdown("---")
            selected_user = st.selectbox("Selecione um usuário para ver detalhes:", user_activity["Usuário"].tolist())
            
            user_records = df_attendance[df_attendance["User"] == selected_user]
            
            if not user_records.empty:
                # Sort by timestamp (most recent first)
                if "Timestamp" in user_records.columns:
                    # Convert to string and handle NaN values before parsing
                    user_records["Timestamp_str"] = user_records["Timestamp"].astype(str).fillna('')
                    user_records["TS_dt"] = pd.to_datetime(
                        user_records["Timestamp_str"], 
                        format="%d/%m/%Y %H:%M:%S", 
                        errors="coerce"
                    )
                    user_records = user_records.sort_values("TS_dt", ascending=False)
                    user_records = user_records.drop(columns=["TS_dt", "Timestamp_str"])
                
                # Display relevant columns
                display_cols = ["#", "Name", "Event", "Task", "Status", "Timestamp", "Notes"]
                for col in display_cols:
                    if col not in user_records.columns:
                        user_records[col] = ""
                
                st.dataframe(
                    user_records[display_cols],
                    column_config={
                        "#": "#",
                        "Name": "Nome",
                        "Event": "Evento",
                        "Task": "Tarefa",
                        "Status": "Status",
                        "Timestamp": "Data/Hora",
                        "Notes": "Observações"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"Nenhum registro encontrado para o usuário '{selected_user}'.")
        else:
            st.info("Não há dados suficientes para gerar este relatório.")
    
    elif report_type == "Atividade por Evento":
        st.subheader("Atividade por Evento")
        
        if not df_attendance.empty and "Event" in df_attendance.columns:
            event_activity = df_attendance["Event"].value_counts().reset_index()
            event_activity.columns = ["Evento", "Registros"]
            
            st.dataframe(event_activity, use_container_width=True, hide_index=True)
            
            # Visualize with bar chart
            st.bar_chart(event_activity.set_index("Evento")["Registros"])
            
            # Detailed activity for selected event
            st.markdown("---")
            selected_event = st.selectbox("Selecione um evento para ver detalhes:", event_activity["Evento"].tolist())
            
            event_records = df_attendance[df_attendance["Event"] == selected_event]
            
            if not event_records.empty:
                # Sort by timestamp (most recent first)
                if "Timestamp" in event_records.columns:
                    # Convert to string and handle NaN values before parsing
                    event_records["Timestamp_str"] = event_records["Timestamp"].astype(str).fillna('')
                    event_records["TS_dt"] = pd.to_datetime(
                        event_records["Timestamp_str"], 
                        format="%d/%m/%Y %H:%M:%S", 
                        errors="coerce"
                    )
                    event_records = event_records.sort_values("TS_dt", ascending=False)
                    event_records = event_records.drop(columns=["TS_dt", "Timestamp_str"])
                
                # Display relevant columns
                display_cols = ["#", "Name", "Task", "Status", "User", "Timestamp", "Notes"]
                for col in display_cols:
                    if col not in event_records.columns:
                        event_records[col] = ""
                
                st.dataframe(
                    event_records[display_cols],
                    column_config={
                        "#": "#",
                        "Name": "Nome",
                        "Task": "Tarefa",
                        "Status": "Status",
                        "User": "Usuário",
                        "Timestamp": "Data/Hora",
                        "Notes": "Observações"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"Nenhum registro encontrado para o evento '{selected_event}'.")
        else:
            st.info("Não há dados suficientes para gerar este relatório.")
    
    # Export data option
    st.markdown("---")
    st.subheader("Exportar Dados")
    
    if st.button("Exportar Dados de Registros"):
        if not df_attendance.empty:
            csv = df_attendance.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"uaew_attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime='text/csv'
            )
        else:
            st.warning("Não há dados para exportar.")
