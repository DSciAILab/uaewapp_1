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
ID_COLUMN_IN_ATTENDANCE = "Athlete ID" # Confirme se este é o nome da coluna na sua aba Attendance
CONFIG_TAB_NAME = "Config"
NO_TASK_SELECTED_LABEL = "-- Selecione uma Tarefa --"
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"] # Status que significam "ainda não feito"

# --- 2. Google Sheets Connection (para gspread) ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError as e: 
        st.error(f"Erro config: Chave GCP ausente em `st.secrets`. Detalhes: {e}", icon="🚨"); st.stop()
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

# --- 3. Data Loading and Preprocessing ---
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
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
            else: df[col] = "" 
        for col_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE"]:
            df[col_check] = df[col_check].fillna("") if col_check in df.columns else ""
        if "NAME" not in df.columns:
            st.error(f"'NAME' não encontrada em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar dados dos atletas (gspread): {e}", icon="🚨"); return pd.DataFrame()

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
        ps_sheet = str(record.get("PS", "")).strip()
        name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == val_id_input or ("PS" + ps_sheet) == proc_input or name_sheet == proc_input or ps_sheet == proc_input:
            return record
    return None

@st.cache_data(ttl=600)
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
        data = worksheet.get_all_values()
        if not data or len(data) < 1:
            st.error(f"Aba '{config_tab_name}' vazia/sem cabeçalho.", icon="🚨"); return [],[]
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().unique().tolist() if "TaskList" in df_conf.columns else []
        statuses = df_conf["TaskStatus"].dropna().unique().tolist() if "TaskStatus" in df_conf.columns else []
        if not tasks: st.warning(f"'TaskList' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        if not statuses: st.warning(f"'TaskStatus' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        return tasks, statuses
    except Exception as e:
        st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨"); return [], []

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        expected = ["#", ID_COLUMN_IN_ATTENDANCE, "Name", "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected:
            if col not in df_att.columns: df_att[col] = None
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        all_vals = log_ws.get_all_values()
        next_num = 1
        if len(all_vals) > 1 and all_vals[-1] and all_vals[-1][0] and str(all_vals[-1][0]).isdigit():
            next_num = int(all_vals[-1][0]) + 1
        elif len(all_vals) >= 1 : next_num = len(all_vals) 
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id) if st.session_state.get('user_confirmed') else user_log_id
        new_row_data = [str(next_num), ath_id, ath_name, ath_event, task, status, notes, user_ident, ts]
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        st.cache_data.clear(); return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨"); return False

def is_blood_test_expired(date_str: str) -> bool:
    if not date_str or pd.isna(date_str): return True
    try:
        dt_obj = pd.to_datetime(date_str, format="%d/%m/%Y", errors='coerce').to_pydatetime() if isinstance(date_str, str) else \
                 date_str.to_pydatetime() if isinstance(date_str, pd.Timestamp) else None
        return dt_obj < (datetime.now() - timedelta(days=182)) if dt_obj else True
    except : return True

st.title("Consulta e Registro de Atletas")
default_ss = {"warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "Usuário",
              "current_user_image_url": "", "show_personal_data": True, "selected_task": NO_TASK_SELECTED_LABEL, "selected_statuses": []}
for k, v in default_ss.items():
    if k not in st.session_state: st.session_state[k] = v
if 'user_id_input' not in st.session_state: st.session_state['user_id_input'] = st.session_state['current_user_id']

with st.container(border=True):
    st.subheader("Identificação do Usuário")
    c1, c2 = st.columns([0.7, 0.3])
    with c1: st.session_state['user_id_input'] = st.text_input("PS (ID de usuário) ou Nome", value=st.session_state['user_id_input'], max_chars=50, key="uid_input_w")
    with c2:
        st.markdown("<br>", True)
        if st.button("Confirmar Usuário", key="confirm_user_b_w", use_container_width=True, type="primary"):
            u_input = st.session_state['user_id_input'].strip()
            if u_input:
                u_info = get_valid_user_info(u_input)
                if u_info:
                    st.session_state.update(current_user_ps_id_internal=str(u_info.get("PS",u_input)).strip(), current_user_id=u_input,
                                            current_user_name=str(u_info.get("USER",u_input)).strip(), current_user_image_url=str(u_info.get("USER_IMAGE","")).strip(),
                                            user_confirmed=True, warning_message=None)
                else: st.session_state.update(user_confirmed=False, current_user_image_url="", warning_message=f"⚠️ Usuário '{u_input}' não encontrado.")
            else: st.session_state.update(warning_message="⚠️ ID/Nome do usuário vazio.", user_confirmed=False, current_user_image_url="")
    if st.session_state.user_confirmed and st.session_state.current_user_name!="Usuário":
        uname, uid = html.escape(st.session_state.current_user_name), html.escape(st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id))
        uimg = st.session_state.get('current_user_image_url',"")
        if uimg: st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-top:10px;"><img src="{html.escape(uimg,True)}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;border:1px solid #555;"><div style="line-height:1.2;"><span style="font-weight:bold;">{uname}</span><br><span style="font-size:0.9em;color:#ccc;">PS: {uid}</span></div></div>""", True)
        else: st.success(f"Usuário '{uname}' (PS: {uid}) confirmado!", icon="✅")
    elif st.session_state.get('warning_message'): st.warning(st.session_state.warning_message, icon="🚨")
    else: st.info("ℹ️ Confirme seu ID/Nome de usuário.", icon="ℹ️")
    if st.session_state.user_confirmed and st.session_state.current_user_id.strip().upper()!=st.session_state.user_id_input.strip().upper() and st.session_state.user_id_input.strip()!="":
        st.session_state.update(user_confirmed=False, warning_message="⚠️ ID/Nome alterado. Confirme.", current_user_image_url="", selected_task=NO_TASK_SELECTED_LABEL); st.rerun()

if st.session_state.user_confirmed and st.session_state.current_user_name!="Usuário":
    st.markdown("---")
    with st.spinner("Carregando configurações..."): tasks_raw, statuses_list = load_config_data()
    tasks_for_select = [NO_TASK_SELECTED_LABEL] + tasks_raw
    if not tasks_raw: st.error("Lista de tarefas não carregada.", icon="🚨"); st.stop()
    if not statuses_list: statuses_list = STATUS_PENDING_EQUIVALENTS + ["Requested","Done","Approved","Rejected","Issue"] # Garante que Pendente e Requested existem
    
    cc1,cc2,cc3 = st.columns([0.4,0.4,0.2])
    with cc1: st.session_state.selected_task = st.selectbox("Tipo de verificação:", tasks_for_select, index=tasks_for_select.index(st.session_state.selected_task) if st.session_state.selected_task in tasks_for_select else 0, key="task_sel_w")
    with cc2: st.session_state.selected_statuses = st.multiselect("Filtrar Status:", statuses_list, default=st.session_state.selected_statuses or [], key="status_multi_w", disabled=(st.session_state.selected_task==NO_TASK_SELECTED_LABEL))
    with cc3: st.markdown("<br>",True); st.button("🔄 Atualizar", key="refresh_b_w", help="Recarrega dados.", on_click=lambda:(st.cache_data.clear(),st.cache_resource.clear(),st.toast("Dados atualizados!",icon="🔄"),st.rerun()), use_container_width=True)
    st.session_state.show_personal_data = st.toggle("Mostrar Dados Pessoais", value=st.session_state.show_personal_data, key="toggle_pd_w")
    st.markdown("---")
    
    with st.spinner("Carregando atletas..."): df_athletes = load_athlete_data()
    with st.spinner("Carregando registros..."): df_attendance = load_attendance_data()
    
    sel_task_actual = st.session_state.selected_task if st.session_state.selected_task!=NO_TASK_SELECTED_LABEL else None
    if df_athletes.empty: st.info("Nenhum atleta para exibir.")
    else:
        df_filtered = df_athletes.copy()
        if sel_task_actual and st.session_state.selected_statuses:
            show_ids = set()
            df_att_filt = df_attendance.copy()
            if ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns: df_att_filt[ID_COLUMN_IN_ATTENDANCE] = df_att_filt[ID_COLUMN_IN_ATTENDANCE].astype(str)
            for _, ath_row in df_filtered.iterrows():
                ath_id_filt = str(ath_row["ID"])
                rel_att_recs = pd.DataFrame()
                if ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns and "Task" in df_att_filt.columns:
                    rel_att_recs = df_att_filt[(df_att_filt[ID_COLUMN_IN_ATTENDANCE] == ath_id_filt) & (df_att_filt["Task"] == sel_task_actual)]
                if not rel_att_recs.empty:
                    if "Status" in rel_att_recs.columns and any(s in st.session_state.selected_statuses for s in rel_att_recs["Status"].unique()):
                        show_ids.add(ath_id_filt)
                elif rel_att_recs.empty and any(s in st.session_state.selected_statuses for s in STATUS_PENDING_EQUIVALENTS):
                    show_ids.add(ath_id_filt)
            df_filtered = df_filtered[df_filtered["ID"].astype(str).isin(list(show_ids))]
        
        st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
        if not sel_task_actual: st.info("Selecione uma tarefa para opções de registro e filtro.", icon="ℹ️")

        for i_l, row in df_filtered.iterrows():
            ath_id_disp, ath_name_disp, ath_event_disp = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
            curr_task_stat_disp = "Status: Pendente / Não Registrado"
            ath_task_recs_df = pd.DataFrame() 
            latest_rec_for_task = None # Para armazenar o último registro da tarefa

            if sel_task_actual:
                if ID_COLUMN_IN_ATTENDANCE in df_attendance.columns and "Task" in df_attendance.columns:
                    df_att_chk_disp = df_attendance.copy()
                    if ID_COLUMN_IN_ATTENDANCE in df_att_chk_disp: df_att_chk_disp[ID_COLUMN_IN_ATTENDANCE] = df_att_chk_disp[ID_COLUMN_IN_ATTENDANCE].astype(str)
                    ath_task_recs_df = df_att_chk_disp[(df_att_chk_disp.get(ID_COLUMN_IN_ATTENDANCE)==ath_id_disp) & (df_att_chk_disp.get("Task")==sel_task_actual)]
                if not ath_task_recs_df.empty and "Status" in ath_task_recs_df.columns:
                    latest_rec_for_task = ath_task_recs_df.iloc[-1].copy() # Fallback
                    if "Timestamp" in ath_task_recs_df.columns:
                        try:
                            temp_df = ath_task_recs_df.copy()
                            temp_df["Timestamp_dt"] = pd.to_datetime(temp_df["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce')
                            temp_df.dropna(subset=["Timestamp_dt"], inplace=True)
                            if not temp_df.empty: latest_rec_for_task = temp_df.sort_values(by="Timestamp_dt", ascending=False).iloc[0].copy()
                        except: pass
                    curr_task_stat_disp = f"Status ({sel_task_actual}): **{latest_rec_for_task.get('Status','N/A')}**"
                    if "Notes" in latest_rec_for_task and pd.notna(latest_rec_for_task.get('Notes')) and latest_rec_for_task.get('Notes'): curr_task_stat_disp += f" (Notas: {html.escape(str(latest_rec_for_task.get('Notes')))})"
            
            # --- Lógica de Cor do Card CORRIGIDA ---
            card_bg = "#1e1e1e" # Default
            current_status_for_color = None
            if latest_rec_for_task is not None: # Se temos um latest_rec_for_task
                current_status_for_color = latest_rec_for_task.get('Status')

            if current_status_for_color == "Done": card_bg = "#143d14" # Verde
            elif current_status_for_color == "Requested": card_bg = "#634806" # Laranja escuro/marrom para Requested
            # Adicionar outras cores para outros status aqui se necessário
            
            if sel_task_actual == "Blood Test": # Lógica de Blood Test sobrescreve
                bt_date, has_bt = row.get("BLOOD TEST",""), pd.notna(row.get("BLOOD TEST","")) and str(row.get("BLOOD TEST","")).strip()!=""
                bt_exp = is_blood_test_expired(bt_date) if has_bt else True
                if has_bt and not bt_exp: card_bg="#3D3D00"
                elif bt_exp or not has_bt: card_bg="#4D1A00"
            
            pass_img_html = f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{html.escape(str(row.get("PASSPORT IMAGE","")),True)}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if pd.notna(row.get("PASSPORT IMAGE")) and row.get("PASSPORT IMAGE") else ""
            mob_raw = str(row.get("MOBILE","")).strip().replace(" ","").replace("-","").replace("(","").replace(")","")
            wa_html = ""
            if mob_raw:
                mob_proc = ("+"+mob_raw[2:]) if mob_raw.startswith("00") else ("+971"+mob_raw.lstrip("0")) if len(mob_raw)>=9 and not mob_raw.startswith("971") and not mob_raw.startswith("+") else ("+"+mob_raw) if not mob_raw.startswith("+") else mob_raw
                if mob_proc.startswith("+"): wa_html=f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{html.escape(mob_proc.replace('+',''),True)}' target='_blank' style='color:#00BFFF;'>Enviar Mensagem</a></td></tr>"
            bt_date_html, bt_exp_html = str(row.get("BLOOD TEST","")), is_blood_test_expired(str(row.get("BLOOD TEST","")))
            bt_html = f"<tr style='color:{"red" if bt_exp_html else "#A0F0A0"};'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>{html.escape(bt_date_html)}{f'<span style="font-weight:bold;">(Expirado)</span>' if bt_exp_html else ''}</td></tr>" if bt_date_html else "<tr style='color:orange;'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>Não Registrado</td></tr>"
            pd_table_html = f"""<div style='flex-basis:350px;flex-grow:1;'><table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'><tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE","")))}</td></tr>{pass_img_html}{wa_html}{bt_html}</table></div>""" if st.session_state.show_personal_data else "<div style='flex-basis:300px;flex-grow:1;font-style:italic;color:#ccc;font-size:13px;text-align:center;'>Dados pessoais ocultos.</div>"
            st.markdown(f"""<div style='background-color:{card_bg};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'><div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'><div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'><img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/80?text=No+Image") if pd.notna(row.get("IMAGE")) and row.get("IMAGE") else "https://via.placeholder.com/80?text=No+Image",True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'><div><h4 style='margin:0;'>{html.escape(ath_name_disp)}</h4><p style='margin:0;font-size:14px;color:#cccccc;'>{html.escape(ath_event_disp)}</p><p style='margin:0;font-size:13px;color:#cccccc;'>ID: {html.escape(ath_id_disp)}</p><p style='margin:0;font-size:13px;color:#a0f0a0;'><i>{curr_task_stat_disp}</i></p></div></div>{pd_table_html}</div></div>""",True)

            if sel_task_actual:
                music_keys = [f"music_link_1_{ath_id_disp}",f"music_link_2_{ath_id_disp}",f"music_link_3_{ath_id_disp}"]
                for mk in music_keys:
                    if mk not in st.session_state:st.session_state[mk]=""
                
                if sel_task_actual=="Walkout Music":
                    st.markdown("##### Links para Walkout Music:")
                    for j,mk_k in enumerate(music_keys): st.session_state[mk_k]=st.text_input(f"Música {j+1}",value=st.session_state[mk_k],key=f"music{j+1}_in_{ath_id_disp}_{i_l}",placeholder="Link YouTube")
                    if st.button(f"Registrar Músicas para {ath_name_disp}",key=f"reg_music_b_{ath_id_disp}_{i_l}",type="primary",use_container_width=True):
                        any_reg=False
                        for idx,link_url in enumerate([st.session_state[k] for k in music_keys]):
                            if link_url and link_url.strip():
                                uid_log = st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id)
                                if registrar_log(ath_id_disp,ath_name_disp,ath_event_disp,"Walkout Music","Done",link_url.strip(),uid_log): any_reg=True;st.session_state[music_keys[idx]]=""
                        if any_reg:st.rerun()
                        else:st.warning("Nenhum link de música válido fornecido.",icon="⚠️")
                else: # --- Lógica do Botão Dinâmico CORRIGIDA ---
                    current_athlete_task_status_for_button = None
                    if latest_rec_for_task is not None:
                        current_athlete_task_status_for_button = latest_rec_for_task.get('Status')

                    next_status_to_log = "Requested" # Default action
                    button_label_task = f"Marcar '{sel_task_actual}' como SOLICITADO"
                    button_type_task = "primary"

                    if current_athlete_task_status_for_button is None or current_athlete_task_status_for_button in STATUS_PENDING_EQUIVALENTS:
                        next_status_to_log = "Requested"
                        button_label_task = f"Marcar '{sel_task_actual}' como SOLICITADO (Requested)"
                    elif current_athlete_task_status_for_button == "Done":
                        next_status_to_log = "Requested" 
                        button_label_task = f"'{sel_task_actual}' FEITO. Solicitar Novamente (Requested)?"
                        button_type_task = "secondary"
                    elif current_athlete_task_status_for_button == "Requested":
                        next_status_to_log = "Done" # Ação principal quando está "Requested"
                        button_label_task = f"Marcar '{sel_task_actual}' como CONCLUÍDO (Done)"
                        # Você poderia adicionar um segundo botão aqui para "Cancelar Solicitação" (registrar como "---") se quisesse.
                        # Ex: if st.button("Cancelar Solicitação", key=f"cancel_req_button_{...}"): registrar_log(..., "---", ...)

                    if st.button(button_label_task, 
                                 key=f"mark_status_button_{ath_id_disp}_{sel_task_actual.replace(' ', '_')}_{i_l}", 
                                 type=button_type_task, 
                                 use_container_width=True):
                        uid_log=st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id)
                        registrar_log(ath_id_disp,ath_name_disp,ath_event_disp,sel_task_actual,next_status_to_log,"",uid_log)
                        st.rerun()
            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>",True)
else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'): st.warning("🚨 Confirme seu ID/Nome de usuário para acessar.",icon="🚨")
