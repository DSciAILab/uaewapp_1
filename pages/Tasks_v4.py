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
    "Done": "green",
    "Requested": "blue",
    "Pending": "orange",
    "---": "gray",
    "N/A": "red",
    "Error": "red"
}
DEFAULT_COLOR = "gray"

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
        df_config = pd.DataFrame(config_values[1:], columns=config_values[0]) if len(config_values) > 1 else pd.DataFrame()
        tasks = df_config['TaskList'].dropna().tolist() if 'TaskList' in df_config.columns else []

        return df_athletes, df_attendance, tasks, unique_events
    except Exception as e:
        st.error(f"Failed to load initial data: {e}", icon="🚨")
        return pd.DataFrame(), pd.DataFrame(), [], []

# Função para pegar o status da TAREFA SELECIONADA (para a coluna da tabela)
def get_latest_status_for_selected_task(df_athletes, df_attendance, task):
    if task == NO_TASK_SELECTED or df_attendance.empty:
        df_athletes['Status'] = 'N/A'
        return df_athletes

    task_records = df_attendance[df_attendance['Task'] == task].copy()
    if not task_records.empty:
        task_records[ATTENDANCE_TIMESTAMP_COL] = pd.to_datetime(task_records[ATTENDANCE_TIMESTAMP_COL], format='%d/%m/%Y %H:%M:%S', errors='coerce')
        latest_status_df = task_records.sort_values(ATTENDANCE_TIMESTAMP_COL).groupby(ID_COLUMN_IN_ATTENDANCE).last().reset_index()
        merged_df = pd.merge(df_athletes, latest_status_df[[ID_COLUMN_IN_ATTENDANCE, 'Status']], left_on='ID', right_on=ID_COLUMN_IN_ATTENDANCE, how='left')
        merged_df['Status'] = merged_df['Status'].fillna('Pending')
    else:
        merged_df = df_athletes.copy()
        merged_df['Status'] = 'Pending'
    return merged_df[['ID', 'NAME', 'EVENT', 'Status']]

# Função para pegar TODOS os status de TODAS as tarefas (para o painel de detalhes)
@st.cache_data(ttl=300)
def get_all_task_statuses(_df_attendance, tasks):
    if _df_attendance.empty or not tasks:
        return {}
    
    _df_attendance[ATTENDANCE_TIMESTAMP_COL] = pd.to_datetime(_df_attendance[ATTENDANCE_TIMESTAMP_COL], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    _df_attendance.dropna(subset=[ATTENDANCE_TIMESTAMP_COL], inplace=True)
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

        # Prepara as linhas para adicionar
        rows_to_append = []
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        for _, athlete in athletes_to_update.iterrows():
            # O número sequencial será adicionado pelo Google Sheets se a coluna for uma fórmula
            new_row = ["", athlete['EVENT'], athlete['ID'], athlete['NAME'], task, new_status, user_name, ts, "Batch Update"]
            rows_to_append.append(new_row)

        if rows_to_append:
            log_ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
            st.success(f"{len(rows_to_append)} atletas atualizados para a tarefa '{task}' com o status '{new_status}'.")
            load_data.clear() # Limpa o cache para recarregar os dados
            get_all_task_statuses.clear()
    except Exception as e:
        st.error(f"Falha ao atualizar em lote: {e}", icon="🚨")

# --- Lógica de Autenticação (simplificada) ---
st.session_state.user_confirmed = True
st.session_state.current_user_name = "Desktop User"

if 'selected_athlete_indices' not in st.session_state:
    st.session_state.selected_athlete_indices = []

if st.session_state.user_confirmed:
    st.title("🚀 Desktop Task Manager")
    df_athletes, df_attendance, tasks, unique_events = load_data()

    if df_athletes.empty:
        st.warning("Nenhum atleta ativo encontrado. Verifique sua planilha 'df' e os filtros."); st.stop()

    # --- Seção de filtros e busca ---
    st.header("Controles e Filtros")
    filter_cols = st.columns([2, 2, 3])
    with filter_cols[0]:
        selected_task = st.selectbox("1. Selecione a Tarefa para Gerenciar", [NO_TASK_SELECTED] + tasks, key="task_selector")
    with filter_cols[1]:
        selected_events = st.multiselect("2. Filtrar por Evento(s)", options=unique_events, placeholder="Deixe em branco para todos")
    with filter_cols[2]:
        search_query = st.text_input("3. Pesquisar por Nome ou ID do Atleta", placeholder="Digite para pesquisar...")

    # --- Lógica de Filtragem ---
    df_with_status = get_latest_status_for_selected_task(df_athletes, df_attendance, selected_task)
    
    # Aplica os filtros na tabela a ser exibida
    df_display = df_with_status.copy()
    if selected_events:
        df_display = df_display[df_display['EVENT'].isin(selected_events)]
    if search_query:
        query = search_query.lower()
        df_display = df_display[df_display['NAME'].str.lower().str.contains(query) | df_display['ID'].astype(str).str.contains(query)]
    
    # Adiciona a coluna de seleção
    df_display.insert(0, 'Select', False)
    
    st.markdown("---")
    
    # --- Ações em Lote ---
    st.header("Ações em Lote")
    if selected_task == NO_TASK_SELECTED:
        st.info("Selecione uma tarefa acima para habilitar as ações em lote.")
    else:
        action_cols = st.columns(3)
        # Os botões agora são definidos aqui, mas a lógica de execução virá depois da tabela
        btn_requested = action_cols[0].button(f"➡️ Marcar Selecionados como 'Requested'", use_container_width=True, type="primary")
        btn_done = action_cols[1].button(f"✅ Marcar Selecionados como 'Done'", use_container_width=True)
        btn_clear = action_cols[2].button(f"❌ Marcar Selecionados como '---'", use_container_width=True)

    st.markdown("---")

    # --- Tabela Interativa de Atletas ---
    st.header(f"Lista de Atletas ({len(df_display)})")
    
    edited_df = st.data_editor(
        df_display,
        column_config={
            "Select": st.column_config.CheckboxColumn("Selecionar", required=True),
            "ID": st.column_config.TextColumn("ID", disabled=True),
            "NAME": st.column_config.TextColumn("Nome", disabled=True),
            "EVENT": st.column_config.TextColumn("Evento", disabled=True),
            "Status": st.column_config.TextColumn(f"Status ({selected_task})", disabled=True),
        },
        use_container_width=True, hide_index=True, height=500, key="athlete_editor"
    )

    # Captura os atletas selecionados
    selected_rows = edited_df[edited_df['Select']]
    
    # Lógica de execução dos botões de ação em lote
    if btn_requested:
        if not selected_rows.empty:
            batch_register_log(selected_rows, selected_task, "Requested", st.session_state.current_user_name)
            time.sleep(1); st.rerun()
        else: st.warning("Nenhum atleta selecionado.")
            
    if btn_done:
        if not selected_rows.empty:
            batch_register_log(selected_rows, selected_task, "Done", st.session_state.current_user_name)
            time.sleep(1); st.rerun()
        else: st.warning("Nenhum atleta selecionado.")

    if btn_clear:
        if not selected_rows.empty:
            batch_register_log(selected_rows, selected_task, "---", st.session_state.current_user_name)
            time.sleep(1); st.rerun()
        else: st.warning("Nenhum atleta selecionado.")

    # --- NOVO: Painel de Detalhes do Atleta Selecionado ---
    st.markdown("---")
    st.header("Detalhes do Atleta")
    
    if len(selected_rows) == 1:
        # Pega o ID do único atleta selecionado
        selected_athlete_id = selected_rows.iloc[0]['ID']
        selected_athlete_name = selected_rows.iloc[0]['NAME']
        
        st.subheader(f"Todas as Tarefas de: {selected_athlete_name}")

        # Carrega todos os status para o painel de detalhes
        all_statuses_map = get_all_task_statuses(df_attendance, tasks)
        athlete_tasks = all_statuses_map.get(selected_athlete_id, {})
        
        # Exibe as labels
        label_cols = st.columns(4) # Exibe em até 4 colunas
        col_idx = 0
        for task in tasks:
            status = athlete_tasks.get(task, "Pending")
            color = STATUS_COLORS.get(status, DEFAULT_COLOR)
            label_cols[col_idx % 4].markdown(f"**{task}**: :{color}[{status}]")
            col_idx += 1
            
    elif len(selected_rows) > 1:
        st.info(f"{len(selected_rows)} atletas selecionados. Selecione apenas um para ver os detalhes completos.")
    else:
        st.info("Selecione um atleta na tabela acima para ver o status de todas as suas tarefas.")

else:
    st.warning("Por favor, faça o login para acessar o Gerenciador de Tarefas.")
