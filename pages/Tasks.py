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
CONFIG_TAB_NAME = "Config"

# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client
    except KeyError as e:
        st.error(f"Configuration error: Missing Google Cloud service account key in `st.secrets`. Details: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Error connecting to Google API: {e}", icon="🚨")
        st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        worksheet = spreadsheet.worksheet(tab_name)
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨")
        st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada na planilha '{sheet_name}'.", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨")
        st.stop()

# --- 3. Data Loading and Preprocessing ---
@st.cache_data(ttl=600)
def load_athlete_data():
    if 'google_sheet_id' not in st.secrets:
        st.error("Erro: `google_sheet_id` não encontrado nos segredos do Streamlit.", icon="🚨")
        return pd.DataFrame()
    url = f"https://docs.google.com/spreadsheets/d/{st.secrets['google_sheet_id']}/gviz/tq?tqx=out:csv&sheet={ATHLETES_TAB_NAME}"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z")
        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].dt.strftime("%d/%m/%Y").fillna("")
        for col_to_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE"]:
            if col_to_check not in df.columns: df[col_to_check] = ""
            df[col_to_check] = df[col_to_check].fillna("")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading or processing athlete data: {e}", icon="🚨")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_users_data(sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        users_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, users_tab_name)
        users_data = users_worksheet.get_all_records()
        return users_data if users_data else []
    except Exception as e:
        st.error(f"Erro ao carregar dados de usuários '{users_tab_name}': {e}", icon="🚨")
        return []

def get_valid_user_info(user_ps_id_input: str, sheet_name: str = MAIN_SHEET_NAME, users_tab_name: str = USERS_TAB_NAME):
    if not user_ps_id_input: return None
    all_users = load_users_data(sheet_name, users_tab_name)
    if not all_users: return None
    processed_user_input = user_ps_id_input.strip().upper()
    validation_id = processed_user_input[2:] if processed_user_input.startswith("PS") and len(processed_user_input) > 2 and processed_user_input[2:].isdigit() else processed_user_input
    if not validation_id.isdigit() and not processed_user_input.startswith("PS"): return None # allow full PS string if not just digits
    
    for user_record in all_users:
        ps_id_from_sheet = str(user_record.get("PS", "")).strip()
        if ps_id_from_sheet == validation_id or ("PS" + ps_id_from_sheet) == processed_user_input: # Check both forms
            return user_record
    return None

@st.cache_data(ttl=600)
def load_config_data(sheet_name: str = MAIN_SHEET_NAME, config_tab_name: str = CONFIG_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        config_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, config_tab_name)
        data = config_worksheet.get_all_values()
        if not data or len(data) < 1:
            st.error(f"Aba '{config_tab_name}' vazia ou sem cabeçalho.", icon="🚨"); return [],[]
        df_config = pd.DataFrame(data[1:], columns=data[0])
        task_list = df_config["TaskList"].dropna().unique().tolist() if "TaskList" in df_config.columns else []
        task_status_list = df_config["TaskStatus"].dropna().unique().tolist() if "TaskStatus" in df_config.columns else []
        if not task_list: st.warning(f"'TaskList' não encontrada ou vazia em '{config_tab_name}'.", icon="⚠️")
        if not task_status_list: st.warning(f"'TaskStatus' não encontrada ou vazia em '{config_tab_name}'.", icon="⚠️")
        return task_list, task_status_list
    except Exception as e:
        st.error(f"Erro ao carregar config da aba '{config_tab_name}': {e}", icon="🚨"); return [], []

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        attendance_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, attendance_tab_name)
        records = attendance_worksheet.get_all_records()
        df_attendance = pd.DataFrame(records)
        expected_cols = ["#", "Athlete ID", "Name", "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected_cols:
            if col not in df_attendance.columns: df_attendance[col] = None
        return df_attendance
    except Exception as e:
        st.error(f"Erro ao carregar dados de presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(athlete_id: str, athlete_name: str, athlete_event: str,
                  task_type: str, task_status: str, notes: str, user_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client_internal = get_gspread_client()
        log_sheet = connect_gsheet_tab(gspread_client_internal, sheet_name, attendance_tab_name)
        all_values = log_sheet.get_all_values()
        next_hash_num = 1
        if len(all_values) > 1: # header + data
            try:
                if all_values[-1] and all_values[-1][0] and str(all_values[-1][0]).isdigit():
                    next_hash_num = int(all_values[-1][0]) + 1
                else: # Last '#' is not a number or empty, count rows (excluding header)
                    next_hash_num = len(all_values) 
            except (ValueError, IndexError): next_hash_num = len(all_values)
        elif len(all_values) == 1: next_hash_num = 1 # Only header
        
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        nova_linha = [str(next_hash_num), athlete_id, athlete_name, athlete_event, task_type, task_status, notes, user_id, timestamp]
        log_sheet.append_row(nova_linha, value_input_option="USER_ENTERED")
        st.success(f"'{task_type}' para {athlete_name} registrado como '{task_status}'.", icon="✍️")
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar na planilha '{attendance_tab_name}': {e}", icon="🚨"); return False

def is_blood_test_expired(blood_test_date_str: str) -> bool:
    if not blood_test_date_str: return True
    try:
        return datetime.strptime(blood_test_date_str, "%d/%m/%Y") < (datetime.now() - timedelta(days=182))
    except ValueError: return True

st.title("Consulta e Registro de Atletas")
default_ss = {"warning_message": None, "user_confirmed": False, "current_user_id": "", "current_user_name": "Usuário",
              "current_user_image_url": "", "show_personal_data": True, "selected_task": None, "selected_statuses": []}
for k, v in default_ss.items():
    if k not in st.session_state: st.session_state[k] = v
if 'user_id_input' not in st.session_state: st.session_state['user_id_input'] = st.session_state['current_user_id']

with st.container(border=True):
    st.subheader("Identificação do Usuário")
    c1, c2 = st.columns([0.7, 0.3])
    with c1:
        st.session_state['user_id_input'] = st.text_input("PS (ID de usuário)", value=st.session_state['user_id_input'], max_chars=15, key="user_id_field")
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Confirmar Usuário", key="confirm_user_b", use_container_width=True, type="primary"):
            uid_stripped = st.session_state['user_id_input'].strip()
            if uid_stripped:
                u_info = get_valid_user_info(uid_stripped)
                if u_info:
                    st.session_state.update({"current_user_id": uid_stripped, "current_user_name": str(u_info.get("USER", uid_stripped)).strip(),
                                             "current_user_image_url": str(u_info.get("USER_IMAGE", "")).strip(), "user_confirmed": True, "warning_message": None})
                else:
                    st.session_state.update({"user_confirmed": False, "current_user_image_url": "", "warning_message": f"⚠️ Usuário '{uid_stripped}' não encontrado."})
            else:
                st.session_state.update({"warning_message": "⚠️ ID do usuário vazio.", "user_confirmed": False, "current_user_image_url": ""})

    if st.session_state['user_confirmed'] and st.session_state['current_user_id']:
        uname_disp = html.escape(st.session_state['current_user_name']); uid_disp = html.escape(st.session_state['current_user_id'])
        uimg_url = st.session_state.get('current_user_image_url', "")
        greet_html = f"""<div style="display:flex;align-items:center;gap:10px;margin-top:10px;"><img src="{html.escape(uimg_url,quote=True)}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;border:1px solid #555;"><div style="line-height:1.2;"><span style="font-weight:bold;">{uname_disp}</span><br><span style="font-size:0.9em;color:#ccc;">PS: {uid_disp}</span></div></div>""" if uimg_url else f"Usuário '{uname_disp}' (PS: {uid_disp}) confirmado!"
        if uimg_url: st.markdown(greet_html, unsafe_allow_html=True)
        else: st.success(greet_html, icon="✅")
    elif st.session_state.get('warning_message'): st.warning(st.session_state['warning_message'], icon="🚨")
    else: st.info("ℹ️ Confirme seu ID de usuário para prosseguir.", icon="ℹ️")

    if st.session_state['user_confirmed'] and st.session_state['current_user_id'].strip().upper() != st.session_state['user_id_input'].strip().upper() and st.session_state['user_id_input'].strip():
        st.session_state.update({"user_confirmed": False, "warning_message": "⚠️ ID alterado. Confirme.", "current_user_image_url": ""}); st.rerun()

if st.session_state['user_confirmed'] and st.session_state['current_user_id']:
    st.markdown("---")
    TASK_LIST, TASK_STATUS_LIST = load_config_data()
    if not TASK_LIST: st.error("Lista de tarefas não carregada.", icon="🚨"); st.stop()
    if not TASK_STATUS_LIST: TASK_STATUS_LIST = ["Pendente", "Requested", "Done", "Approved", "Rejected", "Issue"] # Fallback

    cc1, cc2, cc3 = st.columns([0.4, 0.4, 0.2])
    with cc1: st.session_state.selected_task = st.selectbox("Tipo de verificação:", TASK_LIST, index=TASK_LIST.index(st.session_state.selected_task) if st.session_state.selected_task in TASK_LIST else 0, key="task_sel")
    with cc2: st.session_state.selected_statuses = st.multiselect("Filtrar Status:", TASK_STATUS_LIST, default=st.session_state.selected_statuses, key="status_multi")
    with cc3: st.markdown("<br>",True); st.button("🔄 Atualizar", key="refresh_b", help="Recarrega dados.", on_click=lambda: (st.cache_data.clear(), st.cache_resource.clear(), st.toast("Dados atualizados!", icon="🔄"), st.rerun()), use_container_width=True)
    st.session_state.show_personal_data = st.toggle("Mostrar Dados Pessoais", value=st.session_state.show_personal_data, key="toggle_pd")
    st.markdown("---")

    with st.spinner("Carregando atletas..."): df_athletes = load_athlete_data()
    with st.spinner("Carregando registros..."): df_attendance = load_attendance_data()

    if df_athletes.empty: st.info("Nenhum atleta para exibir.")
    else:
        filtered_athletes = df_athletes.copy()
        task_to_filter, statuses_to_filter = st.session_state.selected_task, st.session_state.selected_statuses
        if task_to_filter and statuses_to_filter:
            show_ids = set()
            df_att_copy = df_attendance.copy()
            if "Athlete ID" in df_att_copy.columns: df_att_copy["Athlete ID"] = df_att_copy["Athlete ID"].astype(str)
            for _, athlete_row in filtered_athletes.iterrows():
                ath_id = str(athlete_row["ID"])
                rel_att = pd.DataFrame()
                if "Athlete ID" in df_att_copy.columns and "Task" in df_att_copy.columns:
                    rel_att = df_att_copy[(df_att_copy["Athlete ID"] == ath_id) & (df_att_copy["Task"] == task_to_filter)]
                if not rel_att.empty:
                    if "Status" in rel_att.columns and any(s in statuses_to_filter for s in rel_att["Status"].unique()): show_ids.add(ath_id)
                elif any(s in statuses_to_filter for s in ["Pendente", "---", "Não Registrado"]): show_ids.add(ath_id) # Default status check
            filtered_athletes = filtered_athletes[filtered_athletes["ID"].astype(str).isin(list(show_ids))]
        
        st.markdown(f"Exibindo **{len(filtered_athletes)}** de **{len(df_athletes)}** atletas.")

        for i, row in filtered_athletes.iterrows():
            athlete_id_str, athlete_name, athlete_event = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])
            current_task_status_info = "Status: Pendente / Não Registrado"
            ath_task_recs = pd.DataFrame()
            if "Athlete ID" in df_attendance.columns and "Task" in df_attendance.columns:
                df_att_task_check = df_attendance.copy(); df_att_task_check["Athlete ID"] = df_att_task_check["Athlete ID"].astype(str)
                ath_task_recs = df_att_task_check[(df_att_task_check["Athlete ID"] == athlete_id_str) & (df_att_task_check["Task"] == st.session_state.selected_task)]
            if not ath_task_recs.empty and "Status" in ath_task_recs.columns:
                latest_rec = ath_task_recs.sort_values(by="Timestamp", ascending=False).iloc[0]
                current_task_status_info = f"Status Atual: **{latest_rec['Status']}**"
                if "Notes" in latest_rec and pd.notna(latest_rec['Notes']) and latest_rec['Notes']:
                    current_task_status_info += f" (Notas: {html.escape(str(latest_rec['Notes']))})"
            
            card_bg_color = "#1e1e1e"
            if not ath_task_recs.empty and "Status" in ath_task_recs.columns and "Done" in ath_task_recs["Status"].values: card_bg_color = "#143d14"
            elif st.session_state.selected_task == "Blood Test":
                bt_d_str, has_bt = row.get("BLOOD TEST", ""), pd.notna(row.get("BLOOD TEST", "")) and str(row.get("BLOOD TEST", "")).strip() != ""
                bt_exp = is_blood_test_expired(bt_d_str) if has_bt else True
                if has_bt and not bt_exp: card_bg_color = "#3D3D00"
                elif bt_exp or not has_bt: card_bg_color = "#4D1A00"

            passport_image_html_part = ""
            if pd.notna(row.get("PASSPORT IMAGE")) and row.get("PASSPORT IMAGE"):
                passport_url = html.escape(str(row.get("PASSPORT IMAGE", "")), quote=True)
                passport_image_html_part = f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte Img:</b></td><td><a href='{passport_url}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>"

            whatsapp_html_part = ""
            mobile_raw_val = str(row.get("MOBILE", "")).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if mobile_raw_val:
                mob_proc = ("+" + mobile_raw_val[2:]) if mobile_raw_val.startswith("00") else \
                           ("+971" + mobile_raw_val.lstrip("0")) if len(mobile_raw_val) >= 9 and not mobile_raw_val.startswith("971") and not mobile_raw_val.startswith("+") else \
                           ("+" + mobile_raw_val) if not mobile_raw_val.startswith("+") else mobile_raw_val
                if mob_proc.startswith("+"):
                    wa_link_safe = html.escape(mob_proc.replace("+", ""), quote=True)
                    whatsapp_html_part = f"<tr><td style='padding-right:10px;white-space:nowrap;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{wa_link_safe}' target='_blank' style='color:#00BFFF;'>Enviar Mensagem</a></td></tr>"

            blood_test_html_part = ""
            bt_date_str_val = str(row.get("BLOOD TEST", ""))
            bt_is_expired_val = is_blood_test_expired(bt_date_str_val)
            if bt_date_str_val:
                bt_color = "red" if bt_is_expired_val else "#A0F0A0"
                exp_span = f'<span style="font-weight:bold;">(Expirado)</span>' if bt_is_expired_val else ''
                blood_test_html_part = f"<tr style='color:{bt_color};'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>{html.escape(bt_date_str_val)}{exp_span}</td></tr>"
            else:
                blood_test_html_part = "<tr style='color:orange;'><td style='padding-right:10px;white-space:nowrap;'><b>Blood Test:</b></td><td>Não Registrado</td></tr>"

            personal_data_table_html = f"""<div style='flex-basis: 350px; flex-grow: 1;'>
                    <table style='font-size:14px; color:white; border-collapse:collapse; width:100%;'>
                        <tr><td style='padding-right:10px;white-space:nowrap;'><b>Gênero:</b></td><td>{html.escape(str(row.get("GENDER", ""))) }</td></tr>
                        <tr><td style='padding-right:10px;white-space:nowrap;'><b>Nascimento:</b></td><td>{html.escape(str(row.get("DOB", ""))) }</td></tr>
                        <tr><td style='padding-right:10px;white-space:nowrap;'><b>Nacionalidade:</b></td><td>{html.escape(str(row.get("NATIONALITY", ""))) }</td></tr>
                        <tr><td style='padding-right:10px;white-space:nowrap;'><b>Passaporte:</b></td><td>{html.escape(str(row.get("PASSPORT", ""))) }</td></tr>
                        <tr><td style='padding-right:10px;white-space:nowrap;'><b>Expira em:</b></td><td>{html.escape(str(row.get("PASSPORT EXPIRE DATE", ""))) }</td></tr>
                        {passport_image_html_part} {whatsapp_html_part} {blood_test_html_part}
                    </table></div>""" if st.session_state.show_personal_data else "<div style='flex-basis:300px;flex-grow:1;font-style:italic;color:#ccc;font-size:13px;text-align:center;'>Dados pessoais ocultos.</div>"

            st.markdown(f"""<div style='background-color:{card_bg_color};padding:20px;border-radius:10px;margin-bottom:15px;box-shadow:2px 2px 5px rgba(0,0,0,0.3);'>
                <div style='display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:20px;'>
                <div style='display:flex;align-items:center;gap:15px;flex-basis:300px;flex-grow:1;'><img src='{html.escape(row["IMAGE"] if pd.notna(row["IMAGE"]) and row["IMAGE"] else "https://via.placeholder.com/80?text=No+Image", quote=True)}' style='width:80px;height:80px;border-radius:50%;object-fit:cover;border:2px solid white;'><div>
                <h4 style='margin:0;'>{html.escape(athlete_name)}</h4><p style='margin:0;font-size:14px;color:#cccccc;'>{html.escape(athlete_event)}</p><p style='margin:0;font-size:13px;color:#cccccc;'>ID: {html.escape(athlete_id_str)}</p><p style='margin:0;font-size:13px;color:#a0f0a0;'><i>{current_task_status_info}</i></p></div></div>
                {personal_data_table_html}</div></div>""", unsafe_allow_html=True)

            sel_task = st.session_state.selected_task
            music_keys = [f"music_link_{j}_{athlete_id_str}" for j in range(1,4)]
            for mk in music_keys:
                if mk not in st.session_state: st.session_state[mk] = ""
            if sel_task == "Walkout Music":
                st.markdown("##### Links para Walkout Music:")
                for j, mk_key in enumerate(music_keys):
                    st.session_state[mk_key] = st.text_input(f"Música {j+1}", value=st.session_state[mk_key], key=f"music{j+1}_{athlete_id_str}_{i}", placeholder="Link YouTube")
                if st.button(f"Registrar Músicas para {athlete_name}", key=f"reg_music_{athlete_id_str}_{i}", type="primary", use_container_width=True):
                    any_reg = False
                    for idx, k_music in enumerate(music_keys):
                        if st.session_state[k_music] and st.session_state[k_music].strip():
                            if registrar_log(athlete_id_str, athlete_name, athlete_event, "Walkout Music", "Done", st.session_state[k_music].strip(), st.session_state['current_user_id']):
                                any_reg = True; st.session_state[k_music] = "" # Clear on success
                    if any_reg: st.rerun()
                    else: st.warning("Nenhum link de música fornecido.", icon="⚠️")
            else:
                done = "Done" in ath_task_recs["Status"].values if not ath_task_recs.empty and "Status" in ath_task_recs.columns else False
                btn_lbl = f"Marcar '{sel_task}' CONCLUÍDO{' (Refazer?)' if done else ''}"
                if st.button(btn_lbl, key=f"mark_done_{athlete_id_str}_{sel_task.replace(' ','_')}_{i}", type="secondary" if done else "primary", use_container_width=True):
                    registrar_log(athlete_id_str, athlete_name, athlete_event, sel_task, "Done", "", st.session_state['current_user_id']); st.rerun()
            st.markdown("<hr style='border-top:1px solid #333;margin-top:10px;margin-bottom:25px;'>", unsafe_allow_html=True)
else:
    if not st.session_state['user_confirmed'] and not st.session_state.get('warning_message'):
         st.warning("🚨 Confirme seu ID de usuário para acessar.", icon="🚨")
