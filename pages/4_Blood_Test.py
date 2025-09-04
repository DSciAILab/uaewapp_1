# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
from datetime import datetime
import html
import time

# --- Importações do Projeto ---
from utils import get_gspread_client, connect_gsheet_tab, load_users_data, get_valid_user_info
from auth import check_authentication, display_user_sidebar

# --- Autenticação ---
check_authentication()

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Blood Test", layout="wide")

# --- CSS for Responsive Cards ---
st.markdown("""
<style>
    /* --- General Card Styles --- */
    .card-container {
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
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
    }
    .card-header {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 5px;
    }
    .fighter-name {
        font-size: 1.25rem;
        font-weight: bold;
        margin: 0;
        color: white;
    }
    .fight-details, .contact-details {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
    }

    /* --- Mobile Styles --- */
    @media (max-width: 768px) {
        .card-container {
            align-items: flex-start;
        }
        .card-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 8px;
        }
        .card-body {
            padding-top: 8px;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
ATTENDANCE_TAB_NAME = "Attendance"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"
FIXED_TASK = "Blood Test" # Tarefa fixa para esta página

# Status específicos para o fluxo: Solicitar -> Concluir/Cancelar
STATUS_BASE = "---"
STATUS_REQUESTED = "Requested"
STATUS_DONE = "Done"

ALL_LOGICAL_STATUSES = [
    STATUS_BASE,
    STATUS_REQUESTED,
    STATUS_DONE,
]

# Mapa de cores para os status
STATUS_COLOR_MAP = {
    STATUS_DONE: "#143d14",       # Verde
    STATUS_REQUESTED: "#B08D00",  # Amarelo/Laranja
    STATUS_BASE: "#1e1e1e",       # Cinza escuro (cor padrão do card)
    "Pending": "#1e1e1e",
    "Not Registred": "#1e1e1e",
    "Issue": "#1e1e1e" # Mapeia Issue para a cor padrão também
}

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

        # Normaliza os nomes das colunas para minúsculas e com underscores
        # Isso torna o código mais robusto a variações nos nomes das colunas na planilha
        # Ex: "Hotel Room Number" ou "hotel_room_number" se tornam "hotel_room_number"
        df.columns = [str(col).strip().lower().replace(' ', '_') for col in df.columns]

        if "role" not in df.columns or "inactive" not in df.columns:
            st.error(f"Colunas 'ROLE'/'INACTIVE' não encontradas em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()

        if df["inactive"].dtype == 'object':
            df["inactive"] = df["inactive"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        elif pd.api.types.is_numeric_dtype(df["inactive"]):
            df["inactive"] = df["inactive"].map({0: False, 1: True}).fillna(True)
        df = df[(df["role"] == "1 - Fighter") & (df["inactive"] == False)].copy()
        df["event"] = df["event"].fillna("Z") if "event" in df.columns else "Z"
        for col_check in ["image", "mobile", "fight_number", "corner", "passport_image", "room"]:
            if col_check not in df.columns:
                df[col_check] = "" # Cria a coluna se não existir
            else:
                df[col_check] = df[col_check].fillna("") # Preenche valores nulos se existir
        if "name" not in df.columns:
            st.error(f"'NAME' não encontrada em '{athletes_tab_name}'.", icon="🚨"); return pd.DataFrame()
        return df.sort_values(by=["event", "name"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Erro ao carregar atletas (gspread): {e}", icon="🚨"); return pd.DataFrame()

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
        user_ident = st.session_state.get('current_user_name', user_log_id)
        next_num = len(log_ws.get_all_values()) + 1
        new_row_data = [str(next_num), ath_event, ath_id, ath_name, task, status, user_ident, ts, notes]
        log_ws.append_row(new_row_data, value_input_option="USER_ENTERED")
        st.success(f"'{task}' para {ath_name} registrado como '{status}'.", icon="✍️")
        load_attendance_data.clear()
        return True
    except Exception as e:
        st.error(f"Erro ao registrar em '{att_tab_name}': {e}", icon="🚨")
        return False

# --- Helper Function ---
def get_latest_status_info(athlete_id, task, attendance_df):
    status = STATUS_BASE # Default status
    user = "N/A"
    timestamp = "N/A"

    if attendance_df.empty or task is None:
        return status, user, timestamp

    athlete_records = attendance_df[
        (attendance_df[ID_COLUMN_IN_ATTENDANCE].astype(str) == str(athlete_id)) & 
        (attendance_df["Task"] == task)
    ].copy()

    if athlete_records.empty:
        return status, user, timestamp

    if "Timestamp" in athlete_records.columns:
        athlete_records['TS_dt'] = pd.to_datetime(athlete_records['Timestamp'], format="%d/%m/%Y %H:%M:%S", errors='coerce')
        valid_records = athlete_records.dropna(subset=['TS_dt'])
        latest_record = valid_records.sort_values(by="TS_dt", ascending=False).iloc[0] if not valid_records.empty else athlete_records.iloc[-1]
    else:
        latest_record = athlete_records.iloc[-1]
    
    status_raw = latest_record.get("Status", STATUS_BASE)
    user = latest_record.get("User", "N/A")
    timestamp = latest_record.get("Timestamp", "N/A")

    # Mapeamento de status da planilha para os status lógicos desta página
    if status_raw == STATUS_DONE:
        status = STATUS_DONE
    elif status_raw == STATUS_REQUESTED:
        status = STATUS_REQUESTED
    else: # Qualquer outro status (Pending, ---, Issue, etc.) é tratado como o status base.
        status = STATUS_BASE

    return status, user, timestamp

# --- 6. Main Application Logic ---
st.title(f"UAEW | {FIXED_TASK} Control")

display_user_sidebar()

default_ss = {
    "selected_status": "Todos", 
    "selected_event": "Todos os Eventos", 
    "fighter_search_query": "",
    "sort_by": "Nome"
}
for k,v in default_ss.items():
    if k not in st.session_state: st.session_state[k]=v

with st.spinner("Carregando dados..."):
    df_athletes = load_athlete_data()
    df_attendance = load_attendance_data()

if not df_athletes.empty:
    df_athletes[['current_task_status', 'latest_task_user', 'latest_task_timestamp']] = df_athletes['id'].apply(
        lambda id: pd.Series(get_latest_status_info(id, FIXED_TASK, df_attendance))
    )

with st.expander("⚙️ Filtros e Ordenação", expanded=True):
    # --- Linha 1: Filtro de Status e Ordenação ---
    col_status, col_sort = st.columns(2)
    with col_status:
        STATUS_FILTER_LABELS = {
            "Todos": "Todos",
            STATUS_BASE: "Pendente / Cancelado",
            STATUS_REQUESTED: "Requisitado",
            STATUS_DONE: "Concluído"
        }
        status_filter_options = ["Todos", STATUS_BASE, STATUS_REQUESTED, STATUS_DONE]
        st.segmented_control(
            "Filtrar por Status:",
            options=status_filter_options,
            format_func=lambda x: STATUS_FILTER_LABELS.get(x, x),
            key="selected_status"
        )

    with col_sort:
        # Botão de Ordenação
        st.segmented_control(
            "Ordenar por:",
            options=["Nome", "Ordem de Luta"],
            key="sort_by",
            help="Escolha como ordenar a lista de atletas."
        )

    # --- Linha 2: Filtros Adicionais ---
    event_list = sorted([evt for evt in df_athletes["event"].unique() if evt != "Z"]) if not df_athletes.empty else []
    if len(event_list) == 1:
        st.session_state.selected_event = event_list[0]
        st.info(f"Exibindo evento: **{st.session_state.selected_event}**")
    elif len(event_list) > 1:
        event_options = ["Todos os Eventos"] + event_list
        st.selectbox("Filtrar Evento:", options=event_options, key="selected_event")
    else:
        st.session_state.selected_event = "Todos os Eventos"
        st.warning("Nenhum evento encontrado.")

    st.text_input("Pesquisar Lutador:", placeholder="Digite o nome ou ID do lutador...", key="fighter_search_query")

# --- Lógica de Filtragem ---
df_filtered = df_athletes.copy()
if not df_filtered.empty:
    if st.session_state.selected_event != "Todos os Eventos": df_filtered = df_filtered[df_filtered["event"] == st.session_state.selected_event]
    search_term = st.session_state.fighter_search_query.strip().lower()
    if search_term: df_filtered = df_filtered[df_filtered["name"].str.lower().str.contains(search_term, na=False) | df_filtered["id"].astype(str).str.contains(search_term, na=False)]
    if st.session_state.selected_status != "Todos": df_filtered = df_filtered[df_filtered['current_task_status'] == st.session_state.selected_status]

    if st.session_state.get('sort_by', 'Nome') == 'Ordem de Luta':
        df_filtered['FIGHT_NUMBER_NUM'] = pd.to_numeric(df_filtered['fight_number'], errors='coerce').fillna(999)
        df_filtered['CORNER_SORT'] = df_filtered['corner'].str.lower().map({'blue': 0, 'red': 1}).fillna(2)
        df_filtered = df_filtered.sort_values(by=['FIGHT_NUMBER_NUM', 'CORNER_SORT'], ascending=[True, True])
    else:
        df_filtered = df_filtered.sort_values(by='name', ascending=True)

# --- Linha de Resumo de Status ---
if not df_filtered.empty:
    done_count = (df_filtered['current_task_status'] == STATUS_DONE).sum()
    requested_count = (df_filtered['current_task_status'] == STATUS_REQUESTED).sum()
    pending_count = (df_filtered['current_task_status'] == STATUS_BASE).sum()

    summary_html = f'''
    <div style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center; margin-bottom: 10px; margin-top: 10px;">
        <span style="font-weight: bold;">Exibindo {len(df_filtered)} de {len(df_athletes)} atletas:</span>
        <span style="background-color: {STATUS_COLOR_MAP[STATUS_DONE]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">
            Done: {done_count}
        </span>
        <span style="background-color: {STATUS_COLOR_MAP[STATUS_REQUESTED]}; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">
            Requested: {requested_count}
        </span>
        <span style="background-color: #6c757d; color: white; padding: 4px 12px; border-radius: 15px; font-size: 0.9em; font-weight: bold;">
            Pending/Cancelled: {pending_count}
        </span>
    </div>'''
    st.markdown(summary_html, unsafe_allow_html=True)

st.divider()

# --- Exibição dos Cards ---
for i_l, row in df_filtered.iterrows():
    ath_id_d, ath_name_d, ath_event_d = str(row.get("id", "")), str(row.get("name", "")), str(row.get("event", ""))
    ath_fight_number = str(row.get("fight_number", ""))
    ath_corner_color = str(row.get("corner", ""))
    mobile_number = str(row.get("mobile", ""))
    passport_image_url = str(row.get("passport_image", ""))
    room_number = str(row.get("room", ""))

    # Cria o label/tag para o WhatsApp
    whatsapp_tag_html = ""
    if mobile_number:
        phone_digits = "".join(filter(str.isdigit, mobile_number))
        if phone_digits.startswith('00'): phone_digits = phone_digits[2:]
        if phone_digits:
            whatsapp_tag_html = f'''<a href='https://wa.me/{html.escape(phone_digits, True)}' target='_blank' style='text-decoration: none;'>
                                   <span style='background-color: #25D366; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>📞 WhatsApp</span>
                               </a>'''

    # Cria o label/tag para o Passaporte
    passport_tag_html = ""
    if passport_image_url and passport_image_url.startswith("http"):
        passport_tag_html = f'''<a href='{html.escape(passport_image_url, True)}' target='_blank' style='text-decoration: none;'>
                                 <span style='background-color: #007BFF; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>🛂 Passaporte</span>
                             </a>'''

    curr_ath_task_stat = row.get('current_task_status', STATUS_BASE)

    # Define a cor de fundo do card com base no status
    card_bg_col = STATUS_COLOR_MAP.get(curr_ath_task_stat, STATUS_COLOR_MAP[STATUS_BASE])

    fight_number_html = f"<span style='background-color: #4A4A4A; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>LUTA {html.escape(ath_fight_number)}</span>" if ath_fight_number else ""
    #fight_number_html = f"<span style='background-color: #4A4A4A; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.9em; font-weight: bold; margin-left: 10px;'>LUTA {html.escape(ath_fight_number)}</span>" if ath_fight_number else ""
    corner_tag_html = ""
    if ath_corner_color.lower() == 'red':
        corner_tag_html = "<span style='background-color: #d9534f; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>RED</span>"
    elif ath_corner_color.lower() == 'blue':
        corner_tag_html = "<span style='background-color: #428bca; color: white; padding: 3px 10px; border-radius: 8px; font-size: 0.8em; font-weight: bold;'>BLUE</span>"
    
    info_line = f"ID: {html.escape(ath_id_d)} | Evento: {html.escape(ath_event_d)}"
    if room_number:
        info_line += f" | Arrival Status: <b>{html.escape(room_number)}</b>"
    status_line = f"Blood Test: <b>{html.escape(curr_ath_task_stat)}</b>"

    col_card, col_buttons = st.columns([2.5, 1])
    with col_card:
        st.markdown(f'''
        <div class='card-container' style='background-color:{card_bg_col};'>
            <img src='{html.escape(row.get("image","https://via.placeholder.com/60?text=NA"), True)}' class='card-img'>
            <div class='card-info'>
                <div class='card-header'>
                    <span class='fighter-name'>{html.escape(ath_name_d)}</span>
                    <span class='fight-details'>{corner_tag_html}{fight_number_html}</span>
                    <span class='contact-details'>{whatsapp_tag_html}{passport_tag_html}</span>
                </div>
                <div class='card-body'>
                    <small style='color:#ccc; line-height: 1.4;'>{info_line}<br>{status_line}</small>
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

    with col_buttons:
        uid_l = st.session_state.get("current_user_ps_id_internal", st.session_state.current_user_id)
        st.write(" "); st.write(" ") # Espaçamento vertical

        if curr_ath_task_stat == STATUS_REQUESTED:
            # Se a tarefa foi solicitada, mostrar opções de Concluir e Cancelar
            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                if st.button("Concluir", key=f"done_{ath_id_d}_{i_l}", type="primary", use_container_width=True):
                    if registrar_log(ath_id_d, ath_name_d, ath_event_d, FIXED_TASK, STATUS_DONE, "", uid_l):
                        time.sleep(1); st.rerun()
            with btn_c2:
                if st.button("Cancelar", key=f"cancel_{ath_id_d}_{i_l}", use_container_width=True):
                    if registrar_log(ath_id_d, ath_name_d, ath_event_d, FIXED_TASK, STATUS_BASE, "Solicitação cancelada", uid_l):
                        time.sleep(1); st.rerun()
        else:
            # Se estiver Pendente ou Concluído, mostrar botão para (re)solicitar
            btn_label = "Solicitar Novamente" if curr_ath_task_stat == STATUS_DONE else "Solicitar"
            btn_type = "secondary" if curr_ath_task_stat == STATUS_DONE else "primary"
            if st.button(btn_label, key=f"request_{ath_id_d}_{i_l}", type=btn_type, use_container_width=True):
                if registrar_log(ath_id_d, ath_name_d, ath_event_d, FIXED_TASK, STATUS_REQUESTED, "", uid_l):
                    time.sleep(1); st.rerun()
    st.divider()