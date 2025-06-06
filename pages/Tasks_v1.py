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
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]

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
            if col not in df_att.columns: df_att[col] = None # Garante que a coluna exista, preenchendo com None se ausente
        return df_att
    except Exception as e: st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()


def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        all_vals = log_ws.get_all_values() # Pega todos os valores para determinar o próximo #
        
        next_num_str = "1" # Default para a primeira entrada
        if len(all_vals) > 1: # Se houver mais que o cabeçalho
            last_entry_first_col_val = all_vals[-1][0] if all_vals[-1] and all_vals[-1][0] else ''
            if str(last_entry_first_col_val).strip().isdigit():
                next_num_str = str(int(last_entry_first_col_val) + 1)
            else: # Se o último '#' não for um número, contamos as linhas (descontando o cabeçalho)
                next_num_str = str(len(all_vals)) # len(all_vals) já inclui o cabeçalho, então é len(all_vals) - 1 + 1
        elif len(all_vals) == 1 and all_vals[0]: # Apenas cabeçalho
            next_num_str = "1"
        else: # Planilha completamente vazia (sem cabeçalho) - improvável se connect_gsheet_tab funciona
             next_num_str = "1"


        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id) if st.session_state.get('user_confirmed') else user_log_id
        new_row_data = [next_num_str, ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        
        # Armazenar detalhes da última ação para possível "desfazer"
        st.session_state.last_action_details = {
            "log_id_val": next_num_str, # O valor que foi escrito na coluna '#'
            "athlete_id": ath_id,
            "task": task,
            "user": user_ident,
            "timestamp": ts, # Usar o timestamp exato para maior precisão
            "sheet_name": sheet_name,
            "tab_name": att_tab_name
        }
        load_attendance_data.clear(); return True
    except Exception as e: st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨"); return False

def undo_last_log():
    if 'last_action_details' not in st.session_state or not st.session_state.last_action_details:
        st.warning("Nenhuma ação recente para desfazer.", icon="🤷")
        return

    details = st.session_state.last_action_details
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, details["sheet_name"], details["tab_name"])
        
        all_records = log_ws.get_all_records() # Mais fácil para encontrar a linha pelo conteúdo
        row_to_delete_idx = -1

        # Iterar de trás para frente é mais eficiente se a última entrada é a mais provável
        for i in range(len(all_records) -1, -1, -1):
            record = all_records[i]
            # Comparar os campos para garantir que estamos deletando a linha correta
            # A coluna '#' é crucial aqui. Certifique-se de que ela está presente nos 'all_records'
            # gspread pode nomear colunas com espaços ou caracteres especiais de forma diferente
            # Verifique o nome exato da coluna '#' como gspread a lê.
            # Assumindo que a primeira coluna é lida como '#' por get_all_records()
            
            # Primeiro, verifique se a coluna '#' existe no record.
            # O nome da coluna em all_records pode ser o que está no cabeçalho da planilha.
            header_row = log_ws.row_values(1) # Pega os nomes das colunas como estão na planilha
            id_column_header = header_row[0] if header_row else "#" # Nome da primeira coluna

            if str(record.get(id_column_header, '')) == str(details["log_id_val"]) and \
               str(record.get(ID_COLUMN_IN_ATTENDANCE, '')) == str(details["athlete_id"]) and \
               record.get("Task") == details["task"] and \
               record.get("User") == details["user"] and \
               record.get("Timestamp") == details["timestamp"]:
                row_to_delete_idx = i + 2 # +1 porque all_records é 0-indexado, +1 porque gspread é 1-indexado e tem cabeçalho
                break
        
        if row_to_delete_idx != -1:
            log_ws.delete_rows(row_to_delete_idx)
            st.success(f"Ação de registro para '{details['task']}' do atleta ID {details['athlete_id']} (Log ID: {details['log_id_val']}) foi desfeita.", icon="↩️")
            del st.session_state.last_action_details # Remove para não desfazer duas vezes
            load_attendance_data.clear()
        else:
            st.error("Não foi possível encontrar o registro para desfazer. Pode já ter sido alterado ou excluído.", icon="🚨")
            # Manter 'last_action_details' se não foi encontrado, talvez o usuário queira tentar novamente após recarregar? Ou deletar?
            # Por segurança, vamos deletar para evitar tentativas em dados obsoletos.
            if 'last_action_details' in st.session_state:
                 del st.session_state.last_action_details

    except gspread.exceptions.APIError as e:
        if 'Unable to parse range' in str(e) or 'exceeds grid limits' in str(e):
             st.error(f"Erro ao tentar desfazer: Parece que a linha já foi removida ou a planilha está vazia. Detalhes: {e}", icon="🚨")
        else:
            st.error(f"Erro de API Google ao desfazer: {e}", icon="🚨")
        if 'last_action_details' in st.session_state:
            del st.session_state.last_action_details
    except Exception as e:
        st.error(f"Erro ao desfazer a ação: {e}", icon="🚨")
        if 'last_action_details' in st.session_state:
            del st.session_state.last_action_details

def is_blood_test_expired(date_str: str) -> bool:
    if not date_str or pd.isna(date_str): return True
    try:
        dt_obj = pd.to_datetime(date_str, format="%d/%m/%Y", errors='coerce').to_pydatetime() if isinstance(date_str, str) else \
                 (date_str.to_pydatetime() if isinstance(date_str, pd.Timestamp) else None)
        return dt_obj < (datetime.now() - timedelta(days=182)) if dt_obj else True
    except: return True

# --- 6. Main Application Logic ---
st.title("Consulta e Registro de Atletas")
default_ss = {"warning_message":None, "user_confirmed":False, "current_user_id":"", "current_user_name":"Usuário",
              "current_user_image_url":"", "show_personal_data":True, "selected_task":NO_TASK_SELECTED_LABEL, "selected_statuses":[],
              "pending_confirmation": None, "last_action_details": None} # Adicionado pending_confirmation e last_action_details
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k]=v
if 'user_id_input' not in st.session_state: st.session_state['user_id_input']=st.session_state['current_user_id']

with st.container(border=True): # User Auth Section
    st.subheader("Identificação do Usuário")
    col_input_ps, col_user_status_display = st.columns([0.6, 0.4])
    with col_input_ps:
        st.session_state['user_id_input'] = st.text_input(
            "PS (ID de usuário) ou Nome", value=st.session_state['user_id_input'],
            max_chars=50, key="uid_w", label_visibility="collapsed", placeholder="Digite seu PS ou Nome"
        )
        if st.button("Confirmar Usuário", key="confirm_b_w", use_container_width=True, type="primary"):
            u_in=st.session_state['user_id_input'].strip()
            if u_in:
                u_inf=get_valid_user_info(u_in)
                if u_inf:
                    st.session_state.update(
                        current_user_ps_id_internal=str(u_inf.get("PS",u_in)).strip(),
                        current_user_id=u_in,
                        current_user_name=str(u_inf.get("USER",u_in)).strip(),
                        current_user_image_url=str(u_inf.get("USER_IMAGE","")).strip(),
                        user_confirmed=True, warning_message=None,
                        pending_confirmation=None, # Resetar confirmações pendentes ao trocar de usuário
                        last_action_details=None # Resetar última ação ao trocar de usuário
                    )
                else:
                    st.session_state.update(user_confirmed=False,current_user_image_url="",warning_message=f"⚠️ Usuário '{u_in}' não encontrado.")
            else:
                st.session_state.update(warning_message="⚠️ ID/Nome do usuário vazio.",user_confirmed=False,current_user_image_url="")
    with col_user_status_display:
        if st.session_state.user_confirmed and st.session_state.current_user_name != "Usuário":
            un, ui = html.escape(st.session_state.current_user_name), html.escape(st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id))
            uim = st.session_state.get('current_user_image_url', "")
            image_html = ""
            if uim and (uim.startswith("http://") or uim.startswith("https://")):
                image_html = f"""<img src="{html.escape(uim, True)}" style="width:50px;height:50px;border-radius:50%;object-fit:cover;border:1px solid #555;vertical-align:middle;margin-right:10px;">"""
            else:
                image_html = "<div style='width:50px;height:50px;border-radius:50%;background-color:#333;margin-right:10px;display:inline-block;vertical-align:middle;'></div>"
            st.markdown(f"""<div style="display:flex;align-items:center;height:50px;margin-top:0px;">{image_html}<div style="line-height:1.2;vertical-align:middle;"><span style="font-weight:bold;">{un}</span><br><span style="font-size:0.9em;color:#ccc;">PS: {ui}</span></div></div>""", unsafe_allow_html=True)
        elif st.session_state.get('warning_message'):
            st.warning(st.session_state.warning_message, icon="🚨")

    if st.session_state.user_confirmed and st.session_state.current_user_id.strip().upper()!=st.session_state.user_id_input.strip().upper() and st.session_state.user_id_input.strip()!="":
        st.session_state.update(user_confirmed=False,warning_message="⚠️ ID/Nome alterado. Confirme.",current_user_image_url="",selected_task=NO_TASK_SELECTED_LABEL, pending_confirmation=None, last_action_details=None);st.rerun()

if st.session_state.user_confirmed and st.session_state.current_user_name!="Usuário": # Main App Content
    st.markdown("---")
    with st.spinner("Carregando configurações..."):tasks_raw,statuses_list_cfg=load_config_data()
    tasks_for_select=[NO_TASK_SELECTED_LABEL]+tasks_raw
    if not tasks_raw:st.error("Lista de tarefas não carregada.",icon="🚨");st.stop()
    if not statuses_list_cfg:statuses_list_cfg=STATUS_PENDING_EQUIVALENTS+["Requested","Done","Approved","Rejected","Issue"]

    cc1,cc2,cc3_refresh, cc3_undo = st.columns([0.35,0.35,0.15,0.15])
    with cc1:st.session_state.selected_task=st.selectbox("Tipo de verificação:",tasks_for_select,index=tasks_for_select.index(st.session_state.selected_task) if st.session_state.selected_task in tasks_for_select else 0,key="tsel_w")
    with cc2:st.session_state.selected_statuses=st.multiselect("Filtrar Status:",statuses_list_cfg,default=st.session_state.selected_statuses or [],key="smul_w",disabled=(st.session_state.selected_task==NO_TASK_SELECTED_LABEL))
    with cc3_refresh:
        st.markdown("<br>",True)
        if st.button("🔄 Atualizar",key="ref_b_w",help="Recarrega dados.",on_click=lambda:(load_athlete_data.clear(), load_users_data.clear(), load_config_data.clear(), load_attendance_data.clear(), st.toast("Dados atualizados!",icon="🔄"), setattr(st.session_state, 'pending_confirmation', None), st.rerun()),use_container_width=True): # Limpa pending_confirmation ao atualizar
            pass # Ação já está no on_click
    with cc3_undo:
        st.markdown("<br>",True)
        if st.session_state.last_action_details:
            if st.button("↩️ Desfazer", key="undo_b_w", help="Desfaz o último registro realizado.", use_container_width=True, type="secondary"):
                undo_last_log()
                st.rerun() # Rerun para atualizar a UI após desfazer
        else:
            st.button("↩️ Desfazer", key="undo_b_w_disabled", help="Nenhuma ação para desfazer.", use_container_width=True, disabled=True)


    st.session_state.show_personal_data=st.toggle("Mostrar Dados Pessoais",value=st.session_state.show_personal_data,key="tgl_pd_w")
    st.markdown("---")

    with st.spinner("Carregando atletas..."):df_athletes=load_athlete_data()
    with st.spinner("Carregando registros..."):df_attendance=load_attendance_data()
    sel_task_actual=st.session_state.selected_task if st.session_state.selected_task!=NO_TASK_SELECTED_LABEL else None

    if df_athletes.empty:st.info("Nenhum atleta para exibir.")
    else:
        df_filtered=df_athletes.copy()
        if sel_task_actual and st.session_state.selected_statuses:
            show_ids=set()
            df_att_filt=df_attendance.copy()
            if ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns:df_att_filt[ID_COLUMN_IN_ATTENDANCE]=df_att_filt[ID_COLUMN_IN_ATTENDANCE].astype(str)
            else: # Se a coluna ID_COLUMN_IN_ATTENDANCE não existir em df_attendance, não podemos filtrar por ela
                st.warning(f"A coluna '{ID_COLUMN_IN_ATTENDANCE}' não foi encontrada nos registros de presença. O filtro de status pode não funcionar como esperado.", icon="⚠️")

            for _,ath_r in df_filtered.iterrows():
                ath_id_f=str(ath_r["ID"])
                rel_att=pd.DataFrame()
                if ID_COLUMN_IN_ATTENDANCE in df_att_filt.columns and "Task" in df_att_filt.columns:
                    rel_att=df_att_filt[(df_att_filt[ID_COLUMN_IN_ATTENDANCE]==ath_id_f)&(df_att_filt["Task"]==sel_task_actual)]
                if not rel_att.empty:
                    if "Status" in rel_att.columns and any(s in st.session_state.selected_statuses for s in rel_att["Status"].unique()):show_ids.add(ath_id_f)
                elif rel_att.empty and any(s in st.session_state.selected_statuses for s in STATUS_PENDING_EQUIVALENTS):show_ids.add(ath_id_f)
            df_filtered=df_filtered[df_filtered["ID"].astype(str).isin(list(show_ids))]
        st.markdown(f"Exibindo **{len(df_filtered)}** de **{len(df_athletes)}** atletas.")
        if not sel_task_actual:st.info("Selecione uma tarefa para opções de registro e filtro.",icon="ℹ️")

        for i_l,row in df_filtered.iterrows():
            ath_id_d,ath_name_d,ath_event_d=str(row["ID"]),str(row["NAME"]),str(row["EVENT"])
            task_stat_disp="Status: Pendente / Não Registrado";latest_rec_task=None;ath_task_recs=pd.DataFrame()
            if sel_task_actual:
                if ID_COLUMN_IN_ATTENDANCE in df_attendance.columns and "Task" in df_attendance.columns:
                    df_att_chk=df_attendance.copy()
                    if ID_COLUMN_IN_ATTENDANCE in df_att_chk:df_att_chk[ID_COLUMN_IN_ATTENDANCE]=df_att_chk[ID_COLUMN_IN_ATTENDANCE].astype(str)
                    ath_task_recs=df_att_chk[(df_att_chk.get(ID_COLUMN_IN_ATTENDANCE)==ath_id_d)&(df_att_chk.get("Task")==sel_task_actual)]
                if not ath_task_recs.empty and "Status" in ath_task_recs.columns:
                    latest_rec_task=ath_task_recs.iloc[-1].copy()
                    if "Timestamp" in ath_task_recs.columns:
                        try:
                            tmp_df=ath_task_recs.copy();tmp_df["TS_dt"]=pd.to_datetime(tmp_df["Timestamp"],format="%d/%m/%Y %H:%M:%S",errors='coerce')
                            tmp_df.dropna(subset=["TS_dt"],inplace=True)
                            if not tmp_df.empty:latest_rec_task=tmp_df.sort_values(by="TS_dt",ascending=False).iloc[0].copy()
                        except:pass
                    task_stat_disp=f"Status ({sel_task_actual}): **{latest_rec_task.get('Status','N/A')}**"
                    if "Notes" in latest_rec_task and pd.notna(latest_rec_task.get('Notes')) and latest_rec_task.get('Notes'):task_stat_disp+=f" (Notas: {html.escape(str(latest_rec_task.get('Notes')))})"

            card_bg_col="#1e1e1e";curr_stat_color=latest_rec_task.get('Status') if latest_rec_task is not None else None
            if curr_stat_color=="Done":card_bg_col="#143d14" # Verde
            elif curr_stat_color=="Requested":card_bg_col="#B08D00" # Amarelo

            pass_img_h=f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{html.escape(str(row.get('PASSPORT IMAGE','')),True)}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if pd.notna(row.get("PASSPORT IMAGE"))and row.get("PASSPORT IMAGE")else ""
            mob_r=str(row.get("MOBILE","")).strip().replace(" ","").replace("-","").replace("(","").replace(")","");wa_h=""
            if mob_r:
                mob_p=("+"+mob_r[2:])if mob_r.startswith("00")else("+971"+mob_r.lstrip("0"))if len(mob_r)>=9 and not mob_r.startswith("971")and not mob_r.startswith("+")else("+"+mob_r)if not mob_r.startswith("+")else mob_r
                if mob_p.startswith("+"):wa_h=f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{html.escape(mob_p.replace('+',''),True)}' target='_blank' style='color:#00BFFF;'>Msg</a></td></tr>"
            bt_d_h,bt_ex_h=str(row.get("BLOOD TEST","")),is_blood_test_expired(str(row.get("BLOOD TEST","")))
            bt_html=f"<tr style='color:{"red"if bt_ex_h else("#A0F0A0"if bt_d_h else"orange")};'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>{html.escape(bt_d_h)if bt_d_h else'Não Registrado'}{f'<span style="font-weight:bold;">(Expirado)</span>'if bt_ex_h and bt_d_h else''}</td></tr>"
            pd_tbl_h=f"""<div style='flex-basis:350px;flex-grow:1;'><table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'><tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE","")))}</td></tr>{pass_img_h}{wa_h}{bt_html}</table></div>"""if st.session_state.show_personal_data else"<div style='flex-basis:300px;flex-grow:1;font-style:italic;color:#ccc;font-size:13px;text-align:center;'>Dados pessoais ocultos.</div>"

            st.markdown(f"""<div style='background-color:{card_bg_col};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'><div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'><div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'><img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/80?text=No+Image")if pd.notna(row.get("IMAGE"))and row.get("IMAGE")else"https://via.placeholder.com/80?text=No+Image",True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'><div><h4 style='margin:0;text-align:center;font-size:1.5em;'>{html.escape(ath_name_d)}</h4><p style='margin:0;font-size:14px;color:#cccccc;text-align:center;'>{html.escape(ath_event_d)}</p><p style='margin:0;font-size:13px;color:#cccccc;text-align:center;'>ID: {html.escape(ath_id_d)}</p><p style='margin:0;font-size:13px;color:#a0f0a0;text-align:center;'><i>{task_stat_disp}</i></p></div></div>{pd_tbl_h}</div></div>""",True)

            # --- Lógica de Confirmação e Ação ---
            action_key_base = f"{ath_id_d}_{sel_task_actual.replace(' ','_')}_{i_l}" if sel_task_actual else ""

            if sel_task_actual:
                # Verifica se há uma confirmação pendente para esta ação específica
                if st.session_state.pending_confirmation and st.session_state.pending_confirmation.get("action_key") == action_key_base:
                    confirm_details = st.session_state.pending_confirmation
                    st.warning(f"Tem certeza que deseja {confirm_details['message_verb']} '{sel_task_actual}' para {ath_name_d} como '{confirm_details['status_to_set']}'?", icon="❓")
                    
                    col_sim, col_nao = st.columns(2)
                    with col_sim:
                        if st.button("✅ Sim, confirmar", key=f"confirm_yes_{action_key_base}", use_container_width=True, type="primary"):
                            uid_l=st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id)
                            registrar_log(
                                ath_id_d, ath_name_d, ath_event_d, sel_task_actual,
                                confirm_details['status_to_set'], confirm_details['notes'], uid_l
                            )
                            st.session_state.pending_confirmation = None # Limpa confirmação
                            st.rerun()
                    with col_nao:
                        if st.button("❌ Cancelar", key=f"confirm_no_{action_key_base}", use_container_width=True):
                            st.session_state.pending_confirmation = None # Limpa confirmação
                            st.rerun()
                else: # Se não há confirmação pendente, exibe os botões de ação normais
                    m_keys=[f"music_link_1_{ath_id_d}",f"music_link_2_{ath_id_d}",f"music_link_3_{ath_id_d}"]
                    for mk in m_keys:
                        if mk not in st.session_state:st.session_state[mk]=""
                    
                    if sel_task_actual=="Walkout Music":
                        st.markdown("##### Links para Walkout Music:")
                        for j,mk_k in enumerate(m_keys):st.session_state[mk_k]=st.text_input(f"Música {j+1}",value=st.session_state[mk_k],key=f"m{j+1}_in_{action_key_base}",placeholder="Link YouTube")
                        
                        action_key_music = f"reg_m_b_{action_key_base}"
                        if st.button(f"Registrar Músicas para {ath_name_d}",key=action_key_music,type="primary",use_container_width=True):
                            music_links_to_register = [st.session_state[k_].strip() for k_ in m_keys if st.session_state[k_].strip()]
                            if music_links_to_register:
                                st.session_state.pending_confirmation = {
                                    "action_key": action_key_base, # Usamos a base para consistência, mesmo que o botão seja diferente
                                    "type": "walkout_music",
                                    "message_verb": "registrar músicas",
                                    "status_to_set": "Done", # Default status para música
                                    "notes": music_links_to_register, # Passa a lista de links como 'notes'
                                    "music_keys_to_clear": m_keys # Para limpar os inputs após confirmação
                                }
                                st.rerun()
                            else:
                                st.warning("Nenhum link de música válido para registrar.",icon="⚠️")
                        
                        # Confirmação para Walkout Music (se pendente)
                        if st.session_state.pending_confirmation and \
                           st.session_state.pending_confirmation.get("action_key") == action_key_base and \
                           st.session_state.pending_confirmation.get("type") == "walkout_music":
                            
                            confirm_details_music = st.session_state.pending_confirmation
                            links_str = ", ".join(confirm_details_music['notes'])
                            st.warning(f"Tem certeza que deseja registrar as seguintes músicas para {ath_name_d}: {links_str}?", icon="❓")
                            
                            col_sim_m, col_nao_m = st.columns(2)
                            with col_sim_m:
                                if st.button("✅ Sim, registrar músicas", key=f"confirm_yes_music_{action_key_base}", use_container_width=True, type="primary"):
                                    uid_l=st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id)
                                    any_m_reg=False
                                    for link_u in confirm_details_music['notes']:
                                        if registrar_log(ath_id_d,ath_name_d,ath_event_d,sel_task_actual,"Done",link_u,uid_l):
                                            any_m_reg=True
                                    if any_m_reg:
                                        for mk_clear in confirm_details_music['music_keys_to_clear']:
                                            st.session_state[mk_clear] = "" # Limpa os inputs
                                    st.session_state.pending_confirmation = None
                                    st.rerun()
                            with col_nao_m:
                                if st.button("❌ Cancelar Registro de Músicas", key=f"confirm_no_music_{action_key_base}", use_container_width=True):
                                    st.session_state.pending_confirmation = None
                                    st.rerun()

                    else: # Lógica para outras tarefas (não Walkout Music)
                        curr_ath_task_stat_btn=latest_rec_task.get('Status') if latest_rec_task is not None else None
                        
                        if curr_ath_task_stat_btn=="Requested":
                            col_btn_act1,col_btn_act2=st.columns(2)
                            with col_btn_act1:
                                if st.button(f"CONCLUIR '{sel_task_actual}' (Done)",key=f"mark_done_b_{action_key_base}",type="primary",use_container_width=True):
                                    st.session_state.pending_confirmation = {
                                        "action_key": action_key_base, "type": "status_change",
                                        "message_verb": "marcar", "status_to_set": "Done", "notes": ""
                                    }
                                    st.rerun()
                            with col_btn_act2:
                                if st.button(f"CANCELAR SOL. '{sel_task_actual}' (---)",key=f"mark_pending_b_{action_key_base}",type="secondary",use_container_width=True):
                                    st.session_state.pending_confirmation = {
                                        "action_key": action_key_base, "type": "status_change",
                                        "message_verb": "marcar", "status_to_set": "---", "notes": ""
                                    }
                                    st.rerun()
                        else:
                            next_stat_log_btn="Requested";btn_lbl_task_btn=f"SOLICITAR '{sel_task_actual}'";btn_type_task_btn="primary"
                            if curr_ath_task_stat_btn is None or curr_ath_task_stat_btn in STATUS_PENDING_EQUIVALENTS:
                                pass # Mantém defaults
                            elif curr_ath_task_stat_btn=="Done":
                                btn_lbl_task_btn=f"'{sel_task_actual}' FEITO. Solicitar Novamente?" ;btn_type_task_btn="secondary"
                            
                            if st.button(btn_lbl_task_btn,key=f"mark_stat_b_{action_key_base}",type=btn_type_task_btn,use_container_width=True):
                                st.session_state.pending_confirmation = {
                                    "action_key": action_key_base, "type": "status_change",
                                    "message_verb": "marcar", "status_to_set": next_stat_log_btn, "notes": ""
                                }
                                st.rerun()
            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>",True)
else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):st.warning("🚨 Confirme seu ID/Nome de usuário.",icon="🚨")
