# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
# import html # Não estritamente necessário se não estivermos gerando HTML complexo
# import os # Não necessário se não estivermos usando local_css

# --- 1. Configuração da Página ---
# (Definido no MainApp.py para apps multipágina)

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App" 
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
ATHLETES_INFO_TAB_NAME = "df" 
ATHLETE_SHEET_NAME_COL = "NAME" 
ATHLETE_SHEET_ID_COL = "ID"     
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID" 
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"

STATUS_TO_NUM = {
    "---": 1,
    "Não Solicitado": 1, 
    "Requested": 2,
    "Done": 3,
    "Pendente": 0, 
    "Não Registrado": 0
}
# Mapeamento reverso para possível uso em tooltips ou legendas se necessário
NUM_TO_STATUS_VERBOSE = {v: k for k, v_list in {
    "Pendente/N/A (0)": [0],
    "Não Solicitado (1)": [1],
    "Solicitado (2)": [2],
    "Concluído (3)": [3]
}.items() for v in v_list}


# --- Funções de Conexão e Carregamento de Dados ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError: 
        st.error("Erro config: Chave GCP `gcp_service_account` ausente.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro API Google/gspread auth: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client: st.error("Cliente gspread não inicializado.", icon="🚨"); st.stop()
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada em '{sheet_name}'.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}' ({sheet_name}): {e}", icon="🚨"); st.stop()

@st.cache_data
def load_fightcard_data(): 
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL)
        if df.empty: return pd.DataFrame()
        df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip() 
        df["Picture"] = df["Picture"].astype(str).str.strip().fillna("") # Garante string e trata NaN
        return df.dropna(subset=["Fighter", "FightOrder"])
    except Exception as e:
        st.error(f"Erro ao carregar dados do Fightcard: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def load_athletes_info_df(sheet_name=MAIN_SHEET_NAME, athletes_tab=ATHLETES_INFO_TAB_NAME):
    g_client = get_gspread_client()
    ws = connect_gsheet_tab(g_client, sheet_name, athletes_tab)
    try:
        df_ath = pd.DataFrame(ws.get_all_records())
        if df_ath.empty: return pd.DataFrame()
        if ATHLETE_SHEET_ID_COL in df_ath.columns:
            df_ath[ATHLETE_SHEET_ID_COL] = df_ath[ATHLETE_SHEET_ID_COL].astype(str).str.strip()
        else: df_ath[ATHLETE_SHEET_ID_COL] = None
        if ATHLETE_SHEET_NAME_COL in df_ath.columns:
            df_ath[ATHLETE_SHEET_NAME_COL] = df_ath[ATHLETE_SHEET_NAME_COL].astype(str).str.strip()
        else: df_ath[ATHLETE_SHEET_NAME_COL] = None
        if "INACTIVE" in df_ath.columns: # Lógica de INACTIVE
            df_ath["INACTIVE"] = df_ath["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        else: df_ath["INACTIVE"] = False
        return df_ath
    except Exception as e: st.error(f"Erro ao carregar infos dos atletas '{athletes_tab}': {e}"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame()
        cols_to_process = [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL]
        if ATTENDANCE_ATHLETE_NAME_COL not in cols_to_process : cols_to_process.append(ATTENDANCE_ATHLETE_NAME_COL)
        for col in cols_to_process:
            if col in df_att.columns: df_att[col] = df_att[col].astype(str).str.strip()
            else: df_att[col] = None 
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar dados da Attendance: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return [] 
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception as e:
        st.error(f"Erro ao carregar TaskList da Config: {e}"); return []

def get_numeric_task_status(athlete_id_to_check, task_name, df_attendance):
    if df_attendance.empty or pd.isna(athlete_id_to_check) or str(athlete_id_to_check).strip() == "" or not task_name:
        return 0 
    if ATTENDANCE_ATHLETE_ID_COL not in df_attendance.columns or \
       ATTENDANCE_TASK_COL not in df_attendance.columns or \
       ATTENDANCE_STATUS_COL not in df_attendance.columns:
        return 0 
    athlete_id_str = str(athlete_id_to_check).strip()
    task_name_str = str(task_name).strip()
    relevant_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == athlete_id_str) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip() == task_name_str)
    ]
    if relevant_records.empty: return 0
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted.loc[:, "Timestamp_dt"] = pd.to_datetime(
                relevant_records_sorted[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce'
            )
            if relevant_records_sorted["Timestamp_dt"].notna().any():
                 latest_record = relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0]
                 return STATUS_TO_NUM.get(str(latest_record[ATTENDANCE_STATUS_COL]).strip(), 0)
            else: return STATUS_TO_NUM.get(str(relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]).strip(), 0)
        except Exception: return STATUS_TO_NUM.get(str(relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]).strip(), 0)
    return STATUS_TO_NUM.get(str(relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]).strip(), 0)

# --- Início da Página Streamlit ---
st.title("DASHBOARD DE ATLETAS E TAREFAS")
st.markdown("---")

# --- Carregamento Inicial de Todos os Dados ---
with st.spinner("Carregando dados das planilhas..."):
    df_fightcard = load_fightcard_data()
    df_attendance = load_attendance_data()
    all_tasks = get_task_list()
    df_athletes_info = load_athletes_info_df()

if df_fightcard.empty or not all_tasks:
    st.error("Não foi possível carregar dados essenciais (Fightcard ou Lista de Tarefas). O dashboard não pode ser gerado."); st.stop()
if df_athletes_info.empty:
    st.warning("Informações detalhadas dos atletas (da aba 'df') não carregadas. Mapeamento de ID pode falhar ou estar incompleto.")
    df_athletes_info = pd.DataFrame(columns=[ATHLETE_SHEET_NAME_COL, ATHLETE_SHEET_ID_COL])

# --- Seletor de Evento ---
available_events = sorted(df_fightcard[FIGHTCARD_EVENT_COL].dropna().unique().tolist(), reverse=True)
if not available_events: st.warning("Nenhum evento encontrado no Fightcard."); st.stop()
event_options = ["Todos os Eventos"] + available_events
selected_event_option = st.selectbox("Selecione o Evento:", options=event_options, index=0)

df_fightcard_display = df_fightcard.copy()
if selected_event_option != "Todos os Eventos":
    df_fightcard_display = df_fightcard[df_fightcard[FIGHTCARD_EVENT_COL] == selected_event_option].copy()
if df_fightcard_display.empty: st.info(f"Nenhuma luta para o evento '{selected_event_option}'."); st.stop()

# --- Preparar Dados para a Tabela do Dashboard ---
dashboard_data_list = []
fighter_to_id_map = {}
if not df_athletes_info.empty and ATHLETE_SHEET_NAME_COL in df_athletes_info.columns and ATHLETE_SHEET_ID_COL in df_athletes_info.columns:
    df_athletes_unique_names = df_athletes_info.drop_duplicates(subset=[ATHLETE_SHEET_NAME_COL], keep='first')
    fighter_to_id_map = pd.Series(
        df_athletes_unique_names[ATHLETE_SHEET_ID_COL].values, 
        index=df_athletes_unique_names[ATHLETE_SHEET_NAME_COL]
    ).to_dict()

for order, group in df_fightcard_display.sort_values(by=[FIGHTCARD_EVENT_COL, FIGHTCARD_FIGHTORDER_COL]).groupby(
    [FIGHTCARD_EVENT_COL, FIGHTCARD_FIGHTORDER_COL]
):
    event, fight_order = order
    blue_s = group[group[FIGHTCARD_CORNER_COL] == "blue"].squeeze(axis=0)
    red_s = group[group[FIGHTCARD_CORNER_COL] == "red"].squeeze(axis=0)
    row_data = {"Evento": event, "Luta #": int(fight_order) if pd.notna(fight_order) else ""}

    for corner_prefix, series_data in [("Azul", blue_s), ("Vermelho", red_s)]:
        fighter_name_fc = str(series_data.get(FIGHTCARD_FIGHTER_NAME_COL, "N/A")).strip() if isinstance(series_data, pd.Series) else "N/A"
        athlete_id_from_map = fighter_to_id_map.get(fighter_name_fc, None) 
        pic_url = series_data.get(FIGHTCARD_PICTURE_COL, "") if isinstance(series_data, pd.Series) else ""
        row_data[f"Foto {corner_prefix}"] = pic_url if isinstance(pic_url, str) and pic_url.startswith("http") else None
        row_data[f"Lutador {corner_prefix}"] = fighter_name_fc
        row_data[f"ID {corner_prefix}"] = athlete_id_from_map if athlete_id_from_map else "N/D"
        
        if pd.notna(fighter_name_fc) and fighter_name_fc != "N/A" and athlete_id_from_map:
            for task in all_tasks:
                status_num = get_numeric_task_status(athlete_id_from_map, task, df_attendance)
                row_data[f"{task} ({corner_prefix})"] = status_num
        else:
            for task in all_tasks: row_data[f"{task} ({corner_prefix})"] = 0 
    row_data["Divisão"] = blue_s.get(FIGHTCARD_DIVISION_COL, red_s.get(FIGHTCARD_DIVISION_COL, "N/A")) if isinstance(blue_s, pd.Series) else (red_s.get(FIGHTCARD_DIVISION_COL, "N/A") if isinstance(red_s, pd.Series) else "N/A")
    dashboard_data_list.append(row_data)

if not dashboard_data_list: st.info(f"Nenhuma luta processada para '{selected_event_option}'."); st.stop()
df_dashboard = pd.DataFrame(dashboard_data_list)

# --- Configuração das Colunas para st.data_editor ---
column_config_editor = {
    "Evento": st.column_config.TextColumn(width="small", disabled=True),
    "Luta #": st.column_config.NumberColumn(width="small", format="%d", disabled=True),
    "Foto Azul": st.column_config.ImageColumn("Foto (A)", width="small"), # Imagem será quadrada por padrão
    "ID Azul": st.column_config.TextColumn("ID (A)", width="small", disabled=True),
    "Lutador Azul": st.column_config.TextColumn("Lutador (A)", width="medium", disabled=True),
    "Divisão": st.column_config.TextColumn(width="medium", disabled=True),
    "ID Vermelho": st.column_config.TextColumn("ID (V)", width="small", disabled=True),
    "Lutador Vermelho": st.column_config.TextColumn("Lutador (V)", width="medium", disabled=True),
    "Foto Vermelho": st.column_config.ImageColumn("Foto (V)", width="small"),
}
# Ordem das colunas na tabela
column_order_list = ["Evento", "Luta #", "Foto Azul", "ID Azul", "Lutador Azul"]
for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Azul)")
column_order_list.append("Divisão")
for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Vermelho)")
column_order_list.extend(["Lutador Vermelho", "ID Vermelho", "Foto Vermelho"])

# Configuração para cada coluna de tarefa
for task_name_col in all_tasks:
    help_text = f"Status de {task_name_col}. Legenda: " + ", ".join([f"{v}={k.split(' (')[0]}" for k,v_list in NUM_TO_STATUS_VERBOSE.items() for v in v_list])
    column_config_editor[f"{task_name_col} (Azul)"] = st.column_config.NumberColumn(label=task_name_col, width="small", help=help_text, disabled=True)
    column_config_editor[f"{task_name_col} (Vermelho)"] = st.column_config.NumberColumn(label=task_name_col, width="small", help=help_text, disabled=True)

# --- Exibição da Tabela Principal ---
st.subheader(f"Detalhes das Lutas e Tarefas: {selected_event_option}")
st.markdown(f"**Legenda Status Tarefas:** `0`:{NUM_TO_STATUS_VERBOSE.get(0)}, `1`:{NUM_TO_STATUS_VERBOSE.get(1)}, `2`:{NUM_TO_STATUS_VERBOSE.get(2)}, `3`:{NUM_TO_STATUS_VERBOSE.get(3)}")

# Aumentar a fonte globalmente para o data_editor (pode não funcionar perfeitamente para todos os temas)
st.markdown(""" <style> .stDataFrame div[data-testid="stHorizontalBlock"] > div { font-size: 16px !important; } </style> """, unsafe_allow_html=True)

table_height = (len(df_dashboard) + 1) * 40 + 10 # Aprox. 40px por linha + cabeçalho
table_height = max(400, min(table_height, 900)) # Limita altura

st.data_editor( 
    df_dashboard,
    column_config=column_config_editor,
    column_order=column_order_list,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    disabled=True, 
    height=table_height
)
st.markdown("---")

# --- Estatísticas do Evento Selecionado ---
st.subheader(f"Estatísticas do Evento: {selected_event_option}")
if not df_dashboard.empty:
    total_lutas_evento = df_dashboard["Luta #"].nunique()
    atletas_azuis_evento = df_dashboard["Lutador Azul"].drop_duplicates().tolist()
    atletas_vermelhos_evento = df_dashboard["Lutador Vermelho"].drop_duplicates().tolist()
    atletas_azuis_evento = [ath for ath in atletas_azuis_evento if ath and ath != "N/A"]
    atletas_vermelhos_evento = [ath for ath in atletas_vermelhos_evento if ath and ath != "N/A"]
    total_atletas_unicos_evento = len(set(atletas_azuis_evento + atletas_vermelhos_evento))
    total_celulas_tarefa_evento = 0; tarefas_done_evento = 0; tarefas_requested_evento = 0; tarefas_not_solicited_evento = 0; tarefas_pendentes_evento = 0
    for task_stat in all_tasks:
        col_azul = f"{task_stat} (Azul)"; col_verm = f"{task_stat} (Vermelho)"
        if col_azul in df_dashboard.columns:
            total_celulas_tarefa_evento += df_dashboard[col_azul].count() 
            tarefas_done_evento += (df_dashboard[col_azul] == 3).sum()
            tarefas_requested_evento += (df_dashboard[col_azul] == 2).sum()
            tarefas_not_solicited_evento += (df_dashboard[col_azul] == 1).sum()
            tarefas_pendentes_evento += (df_dashboard[col_azul] == 0).sum()
        if col_verm in df_dashboard.columns:
            total_celulas_tarefa_evento += df_dashboard[col_verm].count()
            tarefas_done_evento += (df_dashboard[col_verm] == 3).sum()
            tarefas_requested_evento += (df_dashboard[col_verm] == 2).sum()
            tarefas_not_solicited_evento += (df_dashboard[col_verm] == 1).sum()
            tarefas_pendentes_evento += (df_dashboard[col_verm] == 0).sum()

    stat_cols = st.columns(5)
    stat_cols[0].metric("Total de Lutas", total_lutas_evento)
    stat_cols[1].metric("Atletas Únicos", total_atletas_unicos_evento)
    stat_cols[2].metric("Tarefas 'Done' (3)", tarefas_done_evento, help=f"De {total_celulas_tarefa_evento} possíveis slots de tarefa.")
    stat_cols[3].metric("Tarefas 'Requested' (2)", tarefas_requested_evento)
    stat_cols[4].metric("Tarefas '---' (1)", tarefas_not_solicited_evento)
    # st.metric("Tarefas Pendentes (0)", tarefas_pendentes_evento) # Pode adicionar se quiser
else: st.info("Nenhum dado para exibir estatísticas do evento selecionado.")

st.markdown("---")
st.caption(f"Dashboard - Dados de {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
import html 
import os 

# --- 1. Configuração da Página ---
# (Definido no MainApp.py para apps multipágina)

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App" 
CONFIG_TAB_NAME = "Config"
# Para Fightcard, usamos a URL pública direta
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"

# Aba 'df' para informações adicionais de atletas (como ID canônico)
ATHLETES_INFO_TAB_NAME = "df" 
ATHLETE_SHEET_NAME_COL = "NAME" 
ATHLETE_SHEET_ID_COL = "ID"     

# Aba 'Attendance'
ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID" 
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"

# Mapeamento de Status para Números
STATUS_TO_NUM = {
    "---": 1,
    "Não Solicitado": 1, 
    "Requested": 2,
    "Done": 3,
    "Pendente": 0, 
    "Não Registrado": 0
}
# NUM_TO_STATUS_VERBOSE não é usado neste script, mas pode ser útil para legendas.

# --- Funções de Conexão e Carregamento de Dados (USANDO AS VERSÕES ESTABELECIDAS) ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError: 
        st.error("Erro config: Chave GCP `gcp_service_account` ausente.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro API Google/gspread auth: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client: st.error("Cliente gspread não inicializado.", icon="🚨"); st.stop()
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada em '{sheet_name}'.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}' ({sheet_name}): {e}", icon="🚨"); st.stop()

@st.cache_data
def load_fightcard_data(): # Carrega da URL pública
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL)
        if df.empty: return pd.DataFrame()
        df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip() 
        df["Picture"] = df["Picture"].astype(str).str.strip() 
        return df.dropna(subset=["Fighter", "FightOrder"])
    except Exception as e:
        st.error(f"Erro ao carregar dados do Fightcard da URL: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600) # Cache um pouco maior para infos de atletas
def load_athletes_info_df(sheet_name=MAIN_SHEET_NAME, athletes_tab=ATHLETES_INFO_TAB_NAME):
    g_client = get_gspread_client()
    ws = connect_gsheet_tab(g_client, sheet_name, athletes_tab)
    try:
        df_ath = pd.DataFrame(ws.get_all_records())
        if df_ath.empty: return pd.DataFrame()
        # Processamento básico: garantir que colunas de ID e Nome existam e sejam string
        if ATHLETE_SHEET_ID_COL in df_ath.columns:
            df_ath[ATHLETE_SHEET_ID_COL] = df_ath[ATHLETE_SHEET_ID_COL].astype(str).str.strip()
        else: df_ath[ATHLETE_SHEET_ID_COL] = None # ou pd.NA

        if ATHLETE_SHEET_NAME_COL in df_ath.columns:
            df_ath[ATHLETE_SHEET_NAME_COL] = df_ath[ATHLETE_SHEET_NAME_COL].astype(str).str.strip()
        else: df_ath[ATHLETE_SHEET_NAME_COL] = None

        # Contar ativos, se a coluna INACTIVE existir
        if "INACTIVE" in df_ath.columns:
            if df_ath["INACTIVE"].dtype == 'object':
                 df_ath["INACTIVE"] = df_ath["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
            elif pd.api.types.is_numeric_dtype(df_ath["INACTIVE"]):
                 df_ath["INACTIVE"] = df_ath["INACTIVE"].map({0: False, 1: True}).fillna(True)
        else: df_ath["INACTIVE"] = False # Assume ativo se coluna não existir
        return df_ath
    except Exception as e: st.error(f"Erro ao carregar informações dos atletas da aba '{athletes_tab}': {e}"); return pd.DataFrame()


@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame()
        # Garante que colunas chave são string e sem espaços extras
        cols_to_process = [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL]
        if ATTENDANCE_ATHLETE_NAME_COL not in cols_to_process : cols_to_process.append(ATTENDANCE_ATHLETE_NAME_COL)

        for col in cols_to_process:
            if col in df_att.columns: df_att[col] = df_att[col].astype(str).str.strip()
            else: df_att[col] = None # Adiciona coluna se não existir para evitar KeyError depois
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar dados da Attendance: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return [] 
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        return tasks
    except Exception as e:
        st.error(f"Erro ao carregar TaskList da Config: {e}"); return []
# --- FIM DAS FUNÇÕES DE CARREGAMENTO ---


# --- Função para obter o status numérico da tarefa ---
def get_numeric_task_status(athlete_id_to_check, task_name, df_attendance):
    if df_attendance.empty or pd.isna(athlete_id_to_check) or str(athlete_id_to_check).strip() == "" or not task_name:
        return 0 
    if ATTENDANCE_ATHLETE_ID_COL not in df_attendance.columns or \
       ATTENDANCE_TASK_COL not in df_attendance.columns or \
       ATTENDANCE_STATUS_COL not in df_attendance.columns:
        return 0 

    athlete_id_str = str(athlete_id_to_check).strip()
    task_name_str = str(task_name).strip()

    relevant_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == athlete_id_str) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip() == task_name_str)
    ]
    if relevant_records.empty: return 0

    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted.loc[:, "Timestamp_dt"] = pd.to_datetime(
                relevant_records_sorted[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce'
            )
            if relevant_records_sorted["Timestamp_dt"].notna().any():
                 latest_record = relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0]
                 return STATUS_TO_NUM.get(str(latest_record[ATTENDANCE_STATUS_COL]).strip(), 0)
            else: return STATUS_TO_NUM.get(str(relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]).strip(), 0)
        except Exception: return STATUS_TO_NUM.get(str(relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]).strip(), 0)
    return STATUS_TO_NUM.get(str(relevant_records.iloc[-1][ATTENDANCE_STATUS_COL]).strip(), 0)

# --- Início da Página Streamlit ---
st.title("DASHBOARD DE ATLETAS E TAREFAS")
st.markdown("---")

# --- Carregamento Inicial de Todos os Dados ---
with st.spinner("Carregando dados das planilhas..."):
    df_fightcard = load_fightcard_data()
    df_attendance = load_attendance_data()
    all_tasks = get_task_list()
    df_athletes_info = load_athletes_info_df()

if df_fightcard.empty:
    st.error("Não foi possível carregar os dados do Fightcard. O dashboard não pode ser gerado."); st.stop()
if not all_tasks:
    st.error("Não foi possível carregar a lista de tarefas da Config. O dashboard não pode ser gerado."); st.stop()
if df_athletes_info.empty:
    st.warning("Não foi possível carregar informações dos atletas (da aba 'df'). Mapeamento de ID pode falhar.")
    df_athletes_info = pd.DataFrame(columns=[ATHLETE_SHEET_NAME_COL, ATHLETE_SHEET_ID_COL]) # Evita erro de NoneType

# --- Seletor de Evento ---
available_events = sorted(df_fightcard[FIGHTCARD_EVENT_COL].dropna().unique().tolist(), reverse=True)
if not available_events:
    st.warning("Nenhum evento encontrado no Fightcard."); st.stop()
event_options = ["Todos os Eventos"] + available_events
selected_event_option = st.selectbox("Selecione o Evento:", options=event_options, index=0)

df_fightcard_display = df_fightcard.copy()
if selected_event_option != "Todos os Eventos":
    df_fightcard_display = df_fightcard[df_fightcard[FIGHTCARD_EVENT_COL] == selected_event_option].copy()

if df_fightcard_display.empty:
    st.info(f"Nenhuma luta encontrada para o evento '{selected_event_option}'."); st.stop()

# --- Preparar Dados para a Tabela do Dashboard ---
dashboard_data_list = []
fighter_to_id_map = {}
if not df_athletes_info.empty and ATHLETE_SHEET_NAME_COL in df_athletes_info.columns and ATHLETE_SHEET_ID_COL in df_athletes_info.columns:
    # Remove duplicados pelo nome, mantendo o primeiro ID encontrado (ou o mais relevante se houver lógica)
    df_athletes_unique_names = df_athletes_info.drop_duplicates(subset=[ATHLETE_SHEET_NAME_COL], keep='first')
    fighter_to_id_map = pd.Series(
        df_athletes_unique_names[ATHLETE_SHEET_ID_COL].values, 
        index=df_athletes_unique_names[ATHLETE_SHEET_NAME_COL]
    ).to_dict()

for order, group in df_fightcard_display.sort_values(by=[FIGHTCARD_EVENT_COL, FIGHTCARD_FIGHTORDER_COL]).groupby(
    [FIGHTCARD_EVENT_COL, FIGHTCARD_FIGHTORDER_COL]
):
    event, fight_order = order
    blue_s = group[group[FIGHTCARD_CORNER_COL].astype(str).str.lower() == "blue"].squeeze(axis=0)
    red_s = group[group[FIGHTCARD_CORNER_COL].astype(str).str.lower() == "red"].squeeze(axis=0)
    row_data = {"Evento": event, "Luta #": int(fight_order) if pd.notna(fight_order) else ""}

    for corner_prefix, series_data in [("Azul", blue_s), ("Vermelho", red_s)]:
        fighter_name_fc = str(series_data.get(FIGHTCARD_FIGHTER_NAME_COL, "N/A")).strip() if isinstance(series_data, pd.Series) else "N/A"
        athlete_id_from_map = fighter_to_id_map.get(fighter_name_fc, None) 
        
        row_data[f"Foto {corner_prefix}"] = series_data.get(FIGHTCARD_PICTURE_COL, None) if isinstance(series_data, pd.Series) else None
        row_data[f"Lutador {corner_prefix}"] = fighter_name_fc
        row_data[f"ID {corner_prefix}"] = athlete_id_from_map if athlete_id_from_map else "N/D"
        
        if pd.notna(fighter_name_fc) and fighter_name_fc != "N/A" and athlete_id_from_map: # Só busca status se tiver ID
            for task in all_tasks:
                status_num = get_numeric_task_status(athlete_id_from_map, task, df_attendance)
                row_data[f"{task} ({corner_prefix})"] = status_num
        else:
            for task in all_tasks:
                row_data[f"{task} ({corner_prefix})"] = 0 
    row_data["Divisão"] = blue_s.get(FIGHTCARD_DIVISION_COL, red_s.get(FIGHTCARD_DIVISION_COL, "N/A")) if isinstance(blue_s, pd.Series) else (red_s.get(FIGHTCARD_DIVISION_COL, "N/A") if isinstance(red_s, pd.Series) else "N/A")
    dashboard_data_list.append(row_data)

if not dashboard_data_list: st.info(f"Nenhuma luta para processar para '{selected_event_option}'."); st.stop()
df_dashboard = pd.DataFrame(dashboard_data_list)

# --- Configuração das Colunas para st.data_editor ---
column_config_editor = {
    "Evento": st.column_config.TextColumn(width="small", disabled=True),
    "Luta #": st.column_config.NumberColumn(width="small", format="%d", disabled=True),
    "Foto Azul": st.column_config.ImageColumn("Foto (A)", width="small"),
    "ID Azul": st.column_config.TextColumn("ID (A)", width="small", disabled=True),
    "Lutador Azul": st.column_config.TextColumn("Lutador (A)", width="medium", disabled=True),
    "Divisão": st.column_config.TextColumn(width="medium", disabled=True),
    "ID Vermelho": st.column_config.TextColumn("ID (V)", width="small", disabled=True),
    "Lutador Vermelho": st.column_config.TextColumn("Lutador (V)", width="medium", disabled=True),
    "Foto Vermelho": st.column_config.ImageColumn("Foto (V)", width="small"),
}
column_order_list = ["Evento", "Luta #", "Foto Azul", "ID Azul", "Lutador Azul"]
for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Azul)")
column_order_list.append("Divisão")
for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Vermelho)")
column_order_list.extend(["Lutador Vermelho", "ID Vermelho", "Foto Vermelho"])

for task_name_col in all_tasks:
    column_config_editor[f"{task_name_col} (Azul)"] = st.column_config.NumberColumn(label=task_name_col, width="small", help="0:Pendente, 1:---, 2:Requested, 3:Done", disabled=True)
    column_config_editor[f"{task_name_col} (Vermelho)"] = st.column_config.NumberColumn(label=task_name_col, width="small", help="0:Pendente, 1:---, 2:Requested, 3:Done", disabled=True)

# --- Exibição da Tabela Principal ---
st.subheader(f"Detalhes das Lutas e Tarefas: {selected_event_option}")
st.markdown("""
<style>
    /* Aumenta a fonte da tabela */
    .stDataFrame td, .stDataFrame th {
        font-size: 15px !important; /* Ajuste o tamanho conforme necessário */
    }
    /* Para o data_editor, pode ser mais complexo aplicar estilo global assim */
    /* As larguras de coluna no column_config ajudam mais no data_editor */
</style>
""", unsafe_allow_html=True)
st.info("Status: 0=Pendente, 1=Não Solicitado (---), 2=Solicitado (Requested), 3=Concluído (Done)")

# Ajusta a altura do Data Editor
table_height = (len(df_dashboard) + 1) * 35 + 10 # 35px por linha + cabeçalho + padding
table_height = max(200, min(table_height, 800)) # Limita entre 200 e 800px

st.data_editor( 
    df_dashboard,
    column_config=column_config_editor,
    column_order=column_order_list,
    hide_index=True,
    use_container_width=True,
    num_rows="fixed",
    disabled=True, # Torna a tabela inteira não editável
    height=table_height
)
st.markdown("---")

# --- Estatísticas do Evento Selecionado ---
st.subheader(f"Estatísticas do Evento: {selected_event_option}")
if not df_dashboard.empty:
    total_lutas_evento = df_dashboard["Luta #"].nunique()
    atletas_azuis_evento = df_dashboard["Lutador Azul"].drop_duplicates().tolist()
    atletas_vermelhos_evento = df_dashboard["Lutador Vermelho"].drop_duplicates().tolist()
    # Remove "N/A" ou placeholders se existirem antes de contar atletas únicos
    atletas_azuis_evento = [ath for ath in atletas_azuis_evento if ath and ath != "N/A"]
    atletas_vermelhos_evento = [ath for ath in atletas_vermelhos_evento if ath and ath != "N/A"]
    total_atletas_unicos_evento = len(set(atletas_azuis_evento + atletas_vermelhos_evento))

    total_celulas_tarefa_evento = 0; tarefas_done_evento = 0; tarefas_requested_evento = 0; tarefas_not_solicited_evento = 0
    for task_stat in all_tasks:
        col_azul = f"{task_stat} (Azul)"; col_verm = f"{task_stat} (Vermelho)"
        total_celulas_tarefa_evento += df_dashboard[col_azul].count() + df_dashboard[col_verm].count()
        tarefas_done_evento += (df_dashboard[col_azul] == 3).sum() + (df_dashboard[col_verm] == 3).sum()
        tarefas_requested_evento += (df_dashboard[col_azul] == 2).sum() + (df_dashboard[col_verm] == 2).sum()
        tarefas_not_solicited_evento += (df_dashboard[col_azul] == 1).sum() + (df_dashboard[col_verm] == 1).sum()

    stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)
    stat_col1.metric("Total de Lutas", total_lutas_evento)
    stat_col2.metric("Atletas Únicos", total_atletas_unicos_evento)
    stat_col3.metric("Tarefas 'Done'", tarefas_done_evento, help=f"De {total_celulas_tarefa_evento} possíveis slots de tarefa.")
    stat_col4.metric("Tarefas 'Requested'", tarefas_requested_evento)
    stat_col5.metric("Tarefas '---'", tarefas_not_solicited_evento)
else: st.info("Nenhum dado para exibir estatísticas do evento selecionado.")

st.markdown("---")
st.caption(f"Dashboard - Dados de {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
