from components.layout import bootstrap_page
import streamlit as st

bootstrap_page("Medical Team")  # <- PRIMEIRA LINHA DA PÁGINA

st.title("Medical Team")

# CSS para os cards no estilo Music
st.markdown("""
<style>
    .card-container {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        align-items: flex-start;
        gap: 15px;
    }
    .card-img {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        object-fit: cover;
        flex-shrink: 0;
    }
    .card-info {
        width: 100%;
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    .info-line {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
    }
    .fighter-name {
        font-size: 1.25rem;
        font-weight: bold;
        margin: 0;
        color: white;
    }
    .task-badges { display: flex; flex-wrap: wrap; gap: 8px; }
    div.stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)


# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html
# import altair as alt # Removido, pois a seção de estatísticas foi removida
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
# NO_TASK_SELECTED_LABEL = "-- Choose Task --" # Não é mais necessário, pois a tarefa é fixa

# Define os novos status e suas cores
STATUS_PENDING = "Pending"
STATUS_CLEAR_DOCTOR = "Clear by Doctor"
STATUS_UNDER_OBSERVATION = "Under Observation"
STATUS_STABLE_LOW_RISK = "Stable Low Risk"
STATUS_SERIOUS_AMBULANCE = "Serious Ambulance"

# Lista de todos os status lógicos que o app usará
ALL_LOGICAL_STATUSES = [
    STATUS_PENDING,
    STATUS_CLEAR_DOCTOR,
    STATUS_UNDER_OBSERVATION,
    STATUS_STABLE_LOW_RISK,
    STATUS_SERIOUS_AMBULANCE
]

# Mapa de cores para os novos status (para badges e barra lateral do card)
STATUS_COLOR_MAP = {
    STATUS_CLEAR_DOCTOR: "#28a745",       # Green
    STATUS_UNDER_OBSERVATION: "#ffc107",  # Light Yellow
    STATUS_STABLE_LOW_RISK: "#e0a800",    # Dark Yellow
    STATUS_SERIOUS_AMBULANCE: "#dc3545",  # Red
    STATUS_PENDING: "#6c757d",            # Gray (para pending/não registrado/antigo requested)
    "Not Registred": "#6c757d"            # Trata 'Not Registred' como Pending visualmente
}

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
        for col_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE", "FIGHT NUMBER", "CORNER"]:
            df[col_check] = df[col_check].fillna("") if col_check in df.columns else ""
        if "NAME" not in df.columns:
            st.error(f"'NAME' não encontrada em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        # Ordenar por EVENT, FIGHT NUMBER (numérico), CORNER (blue antes de red), e depois NAME
        df["FIGHT_NUMBER_NUM"] = pd.to_numeric(df["FIGHT NUMBER"], errors="coerce").fillna(999)
        df["CORNER_SORT"] = df["CORNER"].astype(str).str.lower().map({"blue": 0, "red": 1}).fillna(2)
        return df.sort_values(by=["EVENT", "FIGHT_NUMBER_NUM", "CORNER_SORT", "NAME"]).reset_index(drop=True)
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
        if not tasks: st.warning(f"'TaskList' não encontrada/vazia em '{config_tab_name}'.", icon="⚠️")
        return tasks, [] # Retorna lista de status vazia, pois usaremos status fixos definidos nas constantes
    except Exception as e: st.error(f"Erro ao carregar config '{config_tab_name}': {e}", icon="🚨"); return [], []

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name: str = MAIN_SHEET_NAME, attendance_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame(columns=["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"])
        expected_cols_order = ["#", "Event", ID_COLUMN_IN_ATTENDANCE, "Name", "Task", "Status", "User", "Timestamp", "Notes"]
        for col in expected_cols_order:
            if col not in df_att.columns: df_att[col] = pd.NA
        return df_att
    except Exception as e: st.error(f"Erro ao carregar presença '{attendance_tab_name}': {e}", icon="🚨"); return pd.DataFrame()

def registrar_log(ath_id: str, ath_name: str, ath_event: str, task: str, status: str, notes: str, user_log_id: str,
                  sheet_name: str = MAIN_SHEET_NAME, att_tab_name: str = ATTENDANCE_TAB_NAME):
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, sheet_name, att_tab_name)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        user_ident = st.session_state.get('current_user_name', user_log_id) if st.session_state.get('user_confirmed') else user_log_id
        next_num = len(log_ws.get_all_values()) + 1
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        load_attendance_data.clear() # Limpa o cache para recarregar dados
        load_athlete_data.clear() # Limpa o cache para recarregar dados (se necessário, para exibir mudanças)
        return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨")
        return False

# --- Helper Function ---
# Função atualizada para retornar status, usuário e timestamp (filtrado por evento)
def get_latest_status_and_user(athlete_id, task, attendance_df, event=None):
    status = STATUS_PENDING
    user = "N/A"
    timestamp = "N/A"

    if attendance_df.empty or task is None:
        return status, user, timestamp

    # Filtrar por atleta e tarefa
    mask = (
        (attendance_df[ID_COLUMN_IN_ATTENDANCE].astype(str) == str(athlete_id)) &
        (attendance_df["Task"] == task)
    )
    
    # Se evento for fornecido, filtrar por evento também
    if event is not None and "Event" in attendance_df.columns:
        mask = mask & (attendance_df["Event"].astype(str) == str(event))
    
    athlete_records = attendance_df[mask].copy() # Use .copy() para evitar SettingWithCopyWarning

    if athlete_records.empty:
        return status, user, timestamp

    if "Timestamp" in athlete_records.columns:
        athlete_records['TS_dt'] = pd.to_datetime(athlete_records['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        valid_records = athlete_records.dropna(subset=['TS_dt'])
        if not valid_records.empty:
            latest_record = valid_records.sort_values(by="TS_dt", ascending=False).iloc[0]
        else: # Fallback se nenhum timestamp for válido, pega o último registro
            latest_record = athlete_records.iloc[-1]
    else: # Fallback se não houver coluna Timestamp
        latest_record = athlete_records.iloc[-1]
    
    status_raw = latest_record.get("Status", STATUS_PENDING)
    user = latest_record.get("User", "N/A")
    timestamp = latest_record.get("Timestamp", "N/A")

    # Mapeamento de status brutos da planilha para os novos status lógicos
    if status_raw == "Done" or status_raw == STATUS_CLEAR_DOCTOR: # Trata "Done" antigo e o novo "Clear by Doctor" como o mesmo
        status = STATUS_CLEAR_DOCTOR
    elif status_raw == STATUS_UNDER_OBSERVATION:
        status = STATUS_UNDER_OBSERVATION
    elif status_raw == STATUS_STABLE_LOW_RISK:
        status = STATUS_STABLE_LOW_RISK
    elif status_raw == STATUS_SERIOUS_AMBULANCE:
        status = STATUS_SERIOUS_AMBULANCE
    else: # Inclui "Requested", "---", "Pending", "Not Registred" e qualquer outro não mapeado
        status = STATUS_PENDING

    return status, user, timestamp

# --- 6. Main Application Logic ---

# selected_badge_tasks começará vazia conforme solicitado
default_ss = {
    "show_personal_data": False,
    "selected_task": "Medical", # Definir a tarefa padrão como "Medical"
    "selected_status": "Todos",
    "selected_event": "Todos os Eventos",
    "fighter_search_query": "",
    "selected_badge_tasks": [] # Começa vazia
}
for k, v in default_ss.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- Main App Content ---
# A autenticação é gerenciada pelo bootstrap_page no início do arquivo
with st.spinner("Carregando dados..."):
    tasks_raw, _ = load_config_data() # Ainda carregamos todas as tarefas para o multibox de badges
    df_athletes = load_athlete_data()
    df_attendance = load_attendance_data()

# REMOVIDA: A seleção da tarefa (selectbox)
# A tarefa selecionada é agora fixada como "Medical"
sel_task_actual = "Medical"

if sel_task_actual:  # Esta condição agora sempre será verdadeira
    # Aplica a função de status e usuário/timestamp a todo o DataFrame, filtrando por evento
    df_athletes[['current_task_status', 'latest_task_user', 'latest_task_timestamp']] = df_athletes.apply(
        lambda row: pd.Series(get_latest_status_and_user(row['ID'], sel_task_actual, df_attendance, row.get('EVENT', None))),
        axis=1
    )
    st.divider()  # Mantém o divisor para separação visual

# Garantir que as colunas auxiliares de ordenação existam e ordenar DEPOIS de aplicar função de status
if "FIGHT_NUMBER_NUM" not in df_athletes.columns:
    df_athletes["FIGHT_NUMBER_NUM"] = pd.to_numeric(df_athletes.get("FIGHT NUMBER", ""), errors="coerce").fillna(999)
if "CORNER_SORT" not in df_athletes.columns:
    df_athletes["CORNER_SORT"] = df_athletes.get("CORNER", "").astype(str).str.lower().map({"blue": 0, "red": 1}).fillna(2)
# Ordenar o DataFrame principal após aplicar função de status
df_athletes = df_athletes.sort_values(by=["EVENT", "FIGHT_NUMBER_NUM", "CORNER_SORT", "NAME"]).reset_index(drop=True)

# ==========================
# FILTERS (same layout as Music page)
# ==========================
with st.expander("Settings", expanded=False):
    # Ensure default status is always "All"
    if "med_selected_status" not in st.session_state:
        st.session_state["med_selected_status"] = "All"
    col1, col2 = st.columns(2)
    with col1:
        st.segmented_control(
            "Filter by Status:",
            options=["All"] + ALL_LOGICAL_STATUSES,
            key="med_selected_status"
        )
    with col2:
        st.segmented_control(
            "Sort by:",
            options=["Name", "Fight Order"],
            key="med_sort_by"
        )

    event_opts = ["All Events"] + sorted(df_athletes["EVENT"].dropna().unique())
    st.selectbox("Filter by Event:", options=event_opts, key="med_selected_event")
    st.text_input("Search Athlete:", placeholder="Type athlete name or ID...", key="med_search")

# --- Filtering logic ---
# Apply filters
df_main = df_athletes
df_filter = df_main.copy()

if st.session_state.med_selected_event != "All Events":
    df_filter = df_filter[df_filter["EVENT"] == st.session_state.med_selected_event]

term = st.session_state.med_search.strip().lower()
if term:
    df_filter = df_filter[
        df_filter["NAME"].str.lower().str.contains(term, na=False) |
        df_filter["ID"].astype(str).str.contains(term, na=False)
    ]

if st.session_state.med_selected_status != "All":
    df_filter = df_filter[df_filter["current_task_status"] == st.session_state.med_selected_status]

if st.session_state.med_sort_by == "Fight Order":
    df_filter["fno"] = pd.to_numeric(df_filter["FIGHT NUMBER"], errors="coerce").fillna(999)
    df_filter["cor"] = df_filter["CORNER"].astype(str).str.lower().map({"blue": 0, "red": 1}).fillna(2)
    df_filter = df_filter.sort_values(by=["fno", "cor"])
else:
    df_filter = df_filter.sort_values(by="NAME")

st.markdown(f"Exibindo **{len(df_filter)}** atletas.")

for i_l, row in df_filter.iterrows():
    ath_id_d, ath_name_d, ath_event_d = str(row["ID"]), str(row["NAME"]), str(row["EVENT"])

    curr_ath_task_stat = STATUS_PENDING
    latest_user = "N/A"
    latest_ts = "N/A"
    status_bar_color = STATUS_COLOR_MAP[STATUS_PENDING] # Default para cinza
    status_text_html = ""
    user_ts_html = ""

    if sel_task_actual: # Esta condição sempre será verdadeira
        curr_ath_task_stat = row.get('current_task_status', STATUS_PENDING)
        latest_user = row.get('latest_task_user', 'N/A')
        latest_ts = row.get('latest_task_timestamp', 'N/A')

        status_text_html = f"<p style='margin:5px 0 0 0; font-size:1em;'>Status da Tarefa: <strong>{html.escape(str(curr_ath_task_stat))}</strong></p>"
        user_ts_html = f"<p style='margin:2px 0 0 0; font-size:0.8em; color:#bbb;'>Última Atualização por: <strong>{html.escape(str(latest_user))}</strong> em: <strong>{html.escape(str(latest_ts))}</strong></p>"

        status_bar_color = STATUS_COLOR_MAP.get(curr_ath_task_stat, STATUS_COLOR_MAP[STATUS_PENDING])

    # Preparar dados para o card no estilo Music
    mob_r = str(row.get("MOBILE", "")).strip()
    
    col_card, col_buttons = st.columns([2.5, 1])
    with col_card:
        fight_num = str(row.get("FIGHT NUMBER", "")).strip()
        corner = str(row.get("CORNER", "")).strip().upper()
        img_url = str(row.get("IMAGE", "https://via.placeholder.com/60?text=NA"))
        if not img_url or img_url == "nan" or not pd.notna(row.get("IMAGE")):
            img_url = "https://via.placeholder.com/60?text=NA"
        
        # Informações de luta
        info_parts = []
        if ath_event_d and ath_event_d != "Z": 
            info_parts.append(html.escape(ath_event_d))
        if fight_num: 
            info_parts.append(f"FIGHT {html.escape(fight_num)}")
        if corner: 
            info_parts.append(html.escape(corner))
        fight_label = " | ".join(info_parts)
        corner_color = {'RED': '#d9534f', 'BLUE': '#428bca'}.get(corner, '#4A4A4A')
        
        # WhatsApp e Passport como badges
        whatsapp_tag_html = ""
        if mob_r:
            phone_digits = "".join(filter(str.isdigit, mob_r))
            if phone_digits.startswith("00"): 
                phone_digits = phone_digits[2:]
            if phone_digits:
                whatsapp_tag_html = (
                    f"<a href='https://wa.me/{html.escape(phone_digits, True)}' target='_blank' style='text-decoration:none;'>"
                    f"<span style='background:#25D366;color:#fff;padding:3px 10px;border-radius:8px;font-size:.8em;font-weight:bold;'>WhatsApp</span>"
                    f"</a>"
                )
        
        passport_tag_html = ""
        pimg = str(row.get("PASSPORT IMAGE", "")).strip()
        if pimg and pimg.startswith("http"):
            passport_tag_html = (
                f"<a href='{html.escape(pimg, True)}' target='_blank' style='text-decoration:none;'>"
                f"<span style='background:#007BFF;color:#fff;padding:3px 10px;border-radius:8px;font-size:.8em;font-weight:bold;'>Passport</span>"
                f"</a>"
            )
        
        # Dados pessoais removidos (não exibidos)
        pd_content_html = ""
        
        # Card HTML no estilo Music
        card_bg = status_bar_color if status_bar_color != STATUS_COLOR_MAP[STATUS_PENDING] else "#1e1e1e"
        card_html = f"""<div class='card-container' style='background:{card_bg};'>
            <img src='{html.escape(img_url, True)}' class='card-img'>
            <div class='card-info'>
                <div class='info-line'><span class='fighter-name'>{html.escape(ath_name_d)} | {html.escape(ath_id_d)}</span></div>
                <div class='info-line'>
                    <span style='background:{corner_color};color:#fff;padding:3px 10px;border-radius:8px;font-size:.8em;font-weight:bold;margin-right:8px;'>{fight_label}</span>
                </div>
                <div class='info-line'>{whatsapp_tag_html}{passport_tag_html}</div>
                <div class='info-line'><small style='color:#ccc;'>{sel_task_actual}: <b>{html.escape(str(curr_ath_task_stat) or "Pending")}</b></small></div>
                {f"<div class='info-line'><small style='color:#bbb;font-size:0.75em;'>Atualizado por: {html.escape(str(latest_user))} em {html.escape(str(latest_ts))}</small></div>" if (str(latest_user) != "N/A" and not pd.isna(latest_user)) and (str(latest_ts) != "N/A" and not pd.isna(latest_ts)) else ""}
"""
        # Remove the two closing </div> tags at the end of the card_html f-string
        st.markdown(card_html, unsafe_allow_html=True)

#        # Badges de outras tarefas
#        if sel_task_actual and tasks_raw:
#            badge_list = []
#            for task_name_in_badge_list in tasks_raw:
#                if task_name_in_badge_list not in st.session_state.selected_badge_tasks:
#                    continue
#                status_for_badge, user_for_badge, ts_for_badge = get_latest_status_and_user(ath_id_d, task_name_in_badge_list, df_attendance, ath_event_d)
#                color = STATUS_COLOR_MAP.get(status_for_badge, STATUS_COLOR_MAP[STATUS_PENDING])
#                tooltip_content = f"Status: {str(status_for_badge)}\\nAtualizado por: {str(user_for_badge)}\\nEm: {str(ts_for_badge)}"
#                badge_list.append(
#                    f"<span style='background-color:{color};color:white;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:bold;' "
#                    f"title='{html.escape(tooltip_content, quote=True)}'>{html.escape(str(task_name_in_badge_list))}</span>"
#                )
#            if badge_list:
#                badges_html = f"<div class='info-line'>{''.join(badge_list)}</div>"
#                st.markdown(badges_html, unsafe_allow_html=True)

    with col_buttons:
        if sel_task_actual:  # Esta condição sempre será verdadeira
            uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
            st.write(" "); st.write(" ")

            # Gerar botões dinamicamente para todos os status possíveis
            for target_status in ALL_LOGICAL_STATUSES:
                if target_status == curr_ath_task_stat:
                    continue  # Não oferece a opção de mudar para o status atual

                # Define o tipo de botão (primary/secondary)
                button_type = "primary" if target_status == STATUS_CLEAR_DOCTOR else "secondary"

                # Novo: o rótulo do botão é simplesmente o nome do status alvo
                button_label = target_status

                if st.button(button_label, key=f"move_{target_status.replace(' ', '_').lower()}_{ath_id_d}_{i_l}", type=button_type, use_container_width=True):
                    if registrar_log(ath_id_d, ath_name_d, ath_event_d, sel_task_actual, target_status, "", uid_l):
                        time.sleep(1.5)
                        st.rerun()
    st.divider()
