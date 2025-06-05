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
ID_COLUMN_IN_ATTENDANCE = "Athlete ID" 
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

def is_blood_test_expired(date_str: str) -> bool:
    if not date_str or pd.isna(date_str): return True
    try:
        dt_obj = pd.to_datetime(date_str, format="%d/%m/%Y", errors='coerce').to_pydatetime() if isinstance(date_str, str) else \
                 (date_str.to_pydatetime() if isinstance(date_str, pd.Timestamp) else None)
        return dt_obj < (datetime.now() - timedelta(days=182)) if dt_obj else True
    except: return True

st.title("Consulta e Registro de Atletas")
default_ss = {"warning_message":None, "user_confirmed":False, "current_user_id":"", "current_user_name":"Usuário",
              "current_user_image_url":"", "show_personal_data":True, "selected_task":NO_TASK_SELECTED_LABEL, "selected_statuses":[]}
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k]=v
if 'user_id_input' not in st.session_state: st.session_state['user_id_input']=st.session_state['current_user_id']

with st.container(border=True):
    st.subheader("Identificação do Usuário")
    c1,c2=st.columns([0.7,0.3])
    with c1: st.session_state['user_id_input']=st.text_input("PS (ID de usuário) ou Nome",value=st.session_state['user_id_input'],max_chars=50,key="uid_w")
    with c2:
        st.markdown("<br>",True)
        if st.button("Confirmar Usuário",key="confirm_b_w",use_container_width=True,type="primary"):
            u_in=st.session_state['user_id_input'].strip()
            if u_in:
                u_inf=get_valid_user_info(u_in)
                if u_inf: st.session_state.update(current_user_ps_id_internal=str(u_inf.get("PS",u_in)).strip(),current_user_id=u_in,current_user_name=str(u_inf.get("USER",u_in)).strip(),current_user_image_url=str(u_inf.get("USER_IMAGE","")).strip(),user_confirmed=True,warning_message=None)
                else: st.session_state.update(user_confirmed=False,current_user_image_url="",warning_message=f"⚠️ Usuário '{u_in}' não encontrado.")
            else: st.session_state.update(warning_message="⚠️ ID/Nome do usuário vazio.",user_confirmed=False,current_user_image_url="")
    if st.session_state.user_confirmed and st.session_state.current_user_name!="Usuário":
        un,ui=html.escape(st.session_state.current_user_name),html.escape(st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id))
        uim=st.session_state.get('current_user_image_url',"")
        if uim: st.markdown(f"""<div style="display:flex;align-items:center;gap:10px;margin-top:10px;"><img src="{html.escape(uim,True)}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;border:1px solid #555;"><div style="line-height:1.2;"><span style="font-weight:bold;">{un}</span><br><span style="font-size:0.9em;color:#ccc;">PS: {ui}</span></div></div>""",True)
        else: st.success(f"Usuário '{un}' (PS: {ui}) confirmado!",icon="✅")
    elif st.session_state.get('warning_message'): st.warning(st.session_state.warning_message,icon="🚨")
    else: st.info("ℹ️ Confirme seu ID/Nome de usuário.",icon="ℹ️")
    if st.session_state.user_confirmed and st.session_state.current_user_id.strip().upper()!=st.session_state.user_id_input.strip().upper() and st.session_state.user_id_input.strip()!="":
        st.session_state.update(user_confirmed=False,warning_message="⚠️ ID/Nome alterado. Confirme.",current_user_image_url="",selected_task=NO_TASK_SELECTED_LABEL);st.rerun()

if st.session_state.user_confirmed and st.session_state.current_user_name!="Usuário":
    st.markdown("---")
    with st.spinner("Carregando configurações..."):tasks_raw,statuses_list_cfg=load_config_data()
    tasks_for_select=[NO_TASK_SELECTED_LABEL]+tasks_raw
    if not tasks_raw:st.error("Lista de tarefas não carregada.",icon="🚨");st.stop()
    if not statuses_list_cfg:statuses_list_cfg=STATUS_PENDING_EQUIVALENTS+["Requested","Done","Approved","Rejected","Issue"]
    cc1,cc2,cc3=st.columns([0.4,0.4,0.2])
    with cc1:st.session_state.selected_task=st.selectbox("Tipo de verificação:",tasks_for_select,index=tasks_for_select.index(st.session_state.selected_task) if st.session_state.selected_task in tasks_for_select else 0,key="tsel_w")
    with cc2:st.session_state.selected_statuses=st.multiselect("Filtrar Status:",statuses_list_cfg,default=st.session_state.selected_statuses or [],key="smul_w",disabled=(st.session_state.selected_task==NO_TASK_SELECTED_LABEL))
    with cc3:st.markdown("<br>",True);st.button("🔄 Atualizar",key="ref_b_w",help="Recarrega dados.",on_click=lambda:(load_athlete_data.clear(), load_users_data.clear(), load_config_data.clear(), load_attendance_data.clear(), st.toast("Dados atualizados!",icon="🔄"),st.rerun()),use_container_width=True)
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
            
            # --- Lógica de Cor do Card PADRONIZADA ---
            card_bg_col = "#1e1e1e" # Default - Cor do background (sem highlight)
            current_status_for_color = latest_rec_task.get('Status') if latest_rec_task is not None else None

            if current_status_for_color == "Done":
                card_bg_col = "#143d14"  # Verde
            elif current_status_for_color == "Requested":
                card_bg_col = "#B08D00"  # Amarelo (Ex: #B08D00, #CCCC00, #FFD700)
            # Se for "---", "Pendente", ou qualquer outro, permanece o default #1e1e1e
            
            pass_img_h=f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{html.escape(str(row.get("PASSPORT IMAGE","")),True)}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>" if pd.notna(row.get("PASSPORT IMAGE"))and row.get("PASSPORT IMAGE")else ""
            mob_r=str(row.get("MOBILE","")).strip().replace(" ","").replace("-","").replace("(","").replace(")","");wa_h=""
            if mob_r:
                mob_p=("+"+mob_r[2:])if mob_r.startswith("00")else("+971"+mob_r.lstrip("0"))if len(mob_r)>=9 and not mob_r.startswith("971")and not mob_r.startswith("+")else("+"+mob_r)if not mob_r.startswith("+")else mob_r
                if mob_p.startswith("+"):wa_h=f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{html.escape(mob_p.replace('+',''),True)}' target='_blank' style='color:#00BFFF;'>Msg</a></td></tr>"
            bt_d_h,bt_ex_h=str(row.get("BLOOD TEST","")),is_blood_test_expired(str(row.get("BLOOD TEST","")))
            # A cor do texto do Blood Test (vermelho/verde/laranja) é mantida, mas a cor de fundo do card é padronizada.
            bt_html = f"<tr style='color:{"red" if bt_ex_h else ("#A0F0A0" if bt_d_h else "orange")};'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>{html.escape(bt_d_h) if bt_d_h else 'Não Registrado'}{f'<span style="font-weight:bold;">(Expirado)</span>' if bt_ex_h and bt_d_h else ''}</td></tr>"
            pd_tbl_h=f"""<div style='flex-basis:350px;flex-grow:1;'><table style='font-size:14px;color:white;border-collapse:collapse;width:100%;'><tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT","")))}</td></tr><tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE","")))}</td></tr>{pass_img_h}{wa_h}{bt_html}</table></div>"""if st.session_state.show_personal_data else"<div style='flex-basis:300px;flex-grow:1;font-style:italic;color:#ccc;font-size:13px;text-align:center;'>Dados pessoais ocultos.</div>"
            st.markdown(f"""<div style='background-color:{card_bg_col};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'><div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'><div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'><img src='{html.escape(row.get("IMAGE","https://via.placeholder.com/80?text=No+Image")if pd.notna(row.get("IMAGE"))and row.get("IMAGE")else"https://via.placeholder.com/80?text=No+Image",True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'><div><h4 style='margin:0;'>{html.escape(ath_name_d)}</h4><p style='margin:0;font-size:14px;color:#cccccc;'>{html.escape(ath_event_d)}</p><p style='margin:0;font-size:13px;color:#cccccc;'>ID: {html.escape(ath_id_d)}</p><p style='margin:0;font-size:13px;color:#a0f0a0;'><i>{task_stat_disp}</i></p></div></div>{pd_tbl_h}</div></div>""",True)

            if sel_task_actual: 
                m_keys=[f"music_link_1_{ath_id_d}",f"music_link_2_{ath_id_d}",f"music_link_3_{ath_id_d}"]
                for mk in m_keys:
                    if mk not in st.session_state:st.session_state[mk]=""
                if sel_task_actual=="Walkout Music":
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
                else: # Botão Dinâmico para outras tarefas
                    curr_ath_task_stat_btn=latest_rec_task.get('Status') if latest_rec_task is not None else None
                    next_stat_log="Requested";btn_lbl_task=f"Marcar '{sel_task_actual}' como SOLICITADO";btn_type_task="primary"
                    if curr_ath_task_stat_btn is None or curr_ath_task_stat_btn in STATUS_PENDING_EQUIVALENTS:
                        next_stat_log="Requested";btn_lbl_task=f"Marcar '{sel_task_actual}' como SOLICITADO (Requested)"
                    elif curr_ath_task_stat_btn=="Done":
                        next_stat_log="Requested";btn_lbl_task=f"'{sel_task_actual}' FEITO. Solicitar Novamente (Requested)?";btn_type_task="secondary"
                    elif curr_ath_task_stat_btn=="Requested":
                        next_stat_log="Done";btn_lbl_task=f"Marcar '{sel_task_actual}' como CONCLUÍDO (Done)"
                    if st.button(btn_lbl_task,key=f"mark_stat_b_{ath_id_d}_{sel_task_actual.replace(' ','_')}_{i_l}",type=btn_type_task,use_container_width=True):
                        uid_l=st.session_state.get("current_user_ps_id_internal",st.session_state.current_user_id)
                        registrar_log(ath_id_d,ath_name_d,ath_event_d,sel_task_actual,next_stat_log,"",uid_l);st.rerun()
            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>",True)
else:
    if not st.session_state.user_confirmed and not st.session_state.get('warning_message'):st.warning("🚨 Confirme seu ID/Nome de usuário.",icon="🚨")
