# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time

# --- 1. Page Configuration ---
st.set_page_config(page_title="UAEW | Desktop Task Manager", layout="wide")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App"
ATHLETES_TAB_NAME = "df"
USERS_TAB_NAME = "Users"
ATTENDANCE_TAB_NAME = "Attendance"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"
CONFIG_TAB_NAME = "Config"
NO_TASK_SELECTED = "-- Selecione uma Tarefa --"

# Cores para os status das tarefas para as labels
STATUS_COLORS = {
    "Done": "#28a745",      # Verde
    "Requested": "#007bff", # Azul
    "Pending": "#ffc107",   # Amarelo
    "---": "#6c757d",       # Cinza
    "N/A": "#dc3545",       # Vermelho
    "Error": "#dc3545"      # Vermelho
}
DEFAULT_COLOR = "#6c757d" # Cinza para status não mapeados

# --- 2. Google Sheets Connection & Data Loading ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Google API Error: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except Exception as e:
        st.error(f"Error connecting to tab '{tab_name}': {e}", icon="🚨"); st.stop()

@st.cache_data(ttl=300)
def load_data():
    try:
        client = get_gspread_client()

        # Atletas
        athletes_ws = connect_gsheet_tab(client, MAIN_SHEET_NAME, ATHLETES_TAB_NAME)
        athletes_values = athletes_ws.get_all_values()
        if len(athletes_values) < 2: return pd.DataFrame(), pd.DataFrame(), [], []

        df_athletes = pd.DataFrame(athletes_values[1:], columns=athletes_values[0])
        df_athletes = df_athletes.loc[:, ~df_athletes.columns.duplicated()]
        df_athletes = df_athletes[(df_athletes['ROLE'] == '1 - Fighter') & (df_athletes['INACTIVE'].astype(str).str.upper() != 'TRUE')]
        df_athletes = df_athletes[['ID', 'NAME', 'EVENT']].copy()
        df_athletes.columns = df_athletes.columns.str.strip()
        unique_events = sorted(df_athletes['EVENT'].dropna().unique().tolist())

        # Registros de Presença
        attendance_ws = connect_gsheet_tab(client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)
        attendance_values = attendance_ws.get_all_values()
        df_attendance = pd.DataFrame(attendance_values[1:], columns=attendance_values[0]) if len(attendance_values) > 1 else pd.DataFrame()

        # Configurações
        config_ws = connect_gsheet_tab(client, MAIN_SHEET_NAME, CONFIG_TAB_NAME)
        config_values = config_ws.get_all_values()
        if len(config_values) < 2:
            tasks = []
        else:
            df_config = pd.DataFrame(config_values[1:], columns=config_values[0])
            tasks = df_config['TaskList'].dropna().tolist() if 'TaskList' in df_config.columns else []

        return df_athletes, df_attendance, tasks, unique_events
    except Exception as e:
        st.error(f"Failed to load initial data: {e}", icon="🚨")
        return pd.DataFrame(), pd.DataFrame(), [], []

@st.cache_data(ttl=300)
def get_all_task_statuses(_df_attendance, tasks):
    """
    NOVO: Processa todos os registros de presença para obter o status mais recente
    de CADA tarefa para CADA atleta. Retorna um dicionário para consulta rápida.
    Estrutura: { 'athlete_id_1': {'Task A': 'Done', 'Task B': 'Pending'}, ... }
    """
    if _df_attendance.empty or not tasks:
        return {}

    # Garante que as colunas necessárias existem
    required_cols = ['Task', ID_COLUMN_IN_ATTENDANCE, 'Status', ATTENDANCE_TIMESTAMP_COL]
    if not all(col in _df_attendance.columns for col in required_cols):
        st.error(f"A planilha '{ATTENDANCE_TAB_NAME}' deve conter as colunas: {required_cols}")
        return {}

    # Converte timestamp para ordenação
    _df_attendance[ATTENDANCE_TIMESTAMP_COL] = pd.to_datetime(_df_attendance[ATTENDANCE_TIMESTAMP_COL], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    
    # Remove linhas com timestamp inválido
    _df_attendance.dropna(subset=[ATTENDANCE_TIMESTAMP_COL], inplace=True)

    # Ordena e pega o último status para cada combinação de atleta/tarefa
    latest_statuses = _df_attendance.sort_values(ATTENDANCE_TIMESTAMP_COL).groupby([ID_COLUMN_IN_ATTENDANCE, 'Task']).last()

    athlete_status_map = {}
    for (athlete_id, task), row in latest_statuses.iterrows():
        if athlete_id not in athlete_status_map:
            athlete_status_map[athlete_id] = {}
        athlete_status_map[athlete_id][task] = row['Status']

    return athlete_status_map


def batch_register_log(athletes_to_update, task, new_status, user_name):
    if athletes_to_update.empty or task == NO_TASK_SELECTED:
        return
    try:
        gspread_client = get_gspread_client()
        log_ws = connect_gsheet_tab(gspread_client, MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME)

        all_vals = log_ws.get_all_values()
        next_num = len(all_vals)

        rows_to_append = []
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        for _, athlete in athletes_to_update.iterrows():
            next_num += 1
            new_row = [str(next_num), athlete['EVENT'], athlete['ID'], athlete['NAME'], task, new_status, user_name, ts, "Batch Update"]
            rows_to_append.append(new_row)

        if rows_to_append:
            log_ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
            st.success(f"{len(rows_to_append)} atletas atualizados para a tarefa '{task}' com o status '{new_status}'.")
            # Limpa os caches para forçar a recarga dos dados
            load_data.clear()
            get_all_task_statuses.clear()
    except Exception as e:
        st.error(f"Falha ao atualizar em lote: {e}", icon="🚨")


def create_status_label(task, status):
    """Cria uma label HTML colorida para a tarefa e status."""
    color = STATUS_COLORS.get(status, DEFAULT_COLOR)
    return f"""
    <span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin: 2px; display: inline-block;">
        {task}: <b>{status}</b>
    </span>
    """

# --- Lógica de Autenticação (simplificada) ---
st.session_state.user_confirmed = True
st.session_state.current_user_name = "Desktop User"

# Inicializa o dicionário de seleção se não existir
if 'athlete_selection' not in st.session_state:
    st.session_state.athlete_selection = {}


if st.session_state.user_confirmed:
    st.title("🚀 Desktop Task Manager")
    df_athletes, df_attendance, tasks, unique_events = load_data()
    all_athlete_statuses = get_all_task_statuses(df_attendance, tasks)


    if df_athletes.empty:
        st.warning("Nenhum atleta ativo encontrado. Verifique sua planilha 'df' e os filtros."); st.stop()

    # --- INÍCIO: Seção de filtros com Multiselect e Pesquisa ---
    st.header("Controles e Filtros")
    filter_cols = st.columns([2, 2, 3])
    with filter_cols[0]:
        selected_task = st.selectbox("1. Selecione a Tarefa Principal", [NO_TASK_SELECTED] + tasks, key="task_selector")
    with filter_cols[1]:
        # NOVO: Filtro de Evento
        selected_events = st.multiselect("2. Filtrar por Evento(s)", options=unique_events, placeholder="Todos os eventos")
    with filter_cols[2]:
        # NOVO: Campo de Busca
        search_query = st.text_input("3. Pesquisar por Nome ou ID do Atleta", placeholder="Digite para pesquisar...")

    # --- Lógica de Filtragem ---
    df_display = df_athletes.copy()

    # 1. Filtra por eventos selecionados
    if selected_events:
        df_display = df_display[df_display['EVENT'].isin(selected_events)]

    # 2. Filtra pela busca de texto
    if search_query:
        query = search_query.lower()
        df_display = df_display[
            df_display['NAME'].str.lower().str.contains(query) |
            df_display['ID'].astype(str).str.contains(query)
        ]
    
    df_display = df_display.sort_values('NAME').reset_index(drop=True)
    # --- FIM: Seção de filtros ---
    
    st.markdown("---")

    # --- Ações em Lote ---
    st.header("Ações em Lote")
    if selected_task == NO_TASK_SELECTED:
        st.info("Selecione uma tarefa principal acima para habilitar as ações em lote.")
    else:
        # Pega os IDs dos atletas selecionados no novo sistema de checkbox
        selected_ids = [athlete_id for athlete_id, is_selected in st.session_state.athlete_selection.items() if is_selected]
        
        action_cols = st.columns(3)
        with action_cols[0]:
            if st.button(f"➡️ Marcar Selecionados como 'Requested'", use_container_width=True, type="primary"):
                if selected_ids:
                    selected_rows = df_athletes[df_athletes['ID'].isin(selected_ids)]
                    batch_register_log(selected_rows, selected_task, "Requested", st.session_state.current_user_name)
                    time.sleep(1); st.rerun()
                else: st.warning("Nenhum atleta selecionado.")
        with action_cols[1]:
            if st.button(f"✅ Marcar Selecionados como 'Done'", use_container_width=True):
                if selected_ids:
                    selected_rows = df_athletes[df_athletes['ID'].isin(selected_ids)]
                    batch_register_log(selected_rows, selected_task, "Done", st.session_state.current_user_name)
                    time.sleep(1); st.rerun()
                else: st.warning("Nenhum atleta selecionado.")
        with action_cols[2]:
            if st.button(f"❌ Marcar Selecionados como '---'", use_container_width=True):
                if selected_ids:
                    selected_rows = df_athletes[df_athletes['ID'].isin(selected_ids)]
                    batch_register_log(selected_rows, selected_task, "---", st.session_state.current_user_name)
                    time.sleep(1); st.rerun()
                else: st.warning("Nenhum atleta selecionado.")
        
        num_selected = len(selected_ids)
        if num_selected > 0:
            st.info(f"{num_selected} atleta(s) selecionado(s).")
        else:
            st.info("Nenhum atleta selecionado. Marque as caixas de seleção abaixo.")


    st.markdown("---")

    # --- NOVO: Exibição em Cards com Labels de Tarefas ---
    st.header(f"Lista de Atletas ({len(df_display)})")

    if df_display.empty:
        st.warning("Nenhum atleta corresponde aos filtros aplicados.")
    else:
        # Layout em 3 colunas para os cards de atletas
        cols = st.columns(3)
        for index, athlete in df_display.iterrows():
            athlete_id = athlete['ID']
            col = cols[index % 3] # Distribui os atletas pelas colunas
            
            with col:
                with st.container(border=True):
                    # Checkbox para seleção em lote
                    is_selected = st.checkbox(
                        f"**{athlete['NAME']}**", 
                        key=f"select_{athlete_id}",
                        value=st.session_state.athlete_selection.get(athlete_id, False)
                    )
                    st.session_state.athlete_selection[athlete_id] = is_selected

                    st.caption(f"ID: {athlete_id} | Evento: {athlete['EVENT']}")
                    
                    # Container para as labels de tarefas
                    with st.container():
                        athlete_tasks = all_athlete_statuses.get(athlete_id, {})
                        labels_html = ""
                        for task in tasks:
                            status = athlete_tasks.get(task, "Pending")
                            labels_html += create_status_label(task, status)
                        
                        st.markdown(labels_html, unsafe_allow_html=True)
    
else:
    st.warning("Por favor, faça o login para acessar o Gerenciador de Tarefas.")
