# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
import html 
import os 

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App" 
CONFIG_TAB_NAME = "Config"
FIGHTCARD_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
ATHLETES_INFO_TAB_NAME = "df" 
ATHLETE_SHEET_NAME_COL = "NAME" 
ATHLETE_SHEET_ID_COL = "ID"     
ATTENDANCE_TAB_NAME = "Attendance"
ATTENDANCE_ATHLETE_ID_COL = "Athlete ID" 
ATTENDANCE_TASK_COL = "Task"
ATTENDANCE_STATUS_COL = "Status"
ATTENDANCE_TIMESTAMP_COL = "Timestamp"
NAME_COLUMN_IN_ATTENDANCE = "Fighter"  

FC_EVENT_COL = "Event"
FC_FIGHTER_COL = "Fighter"
FC_CORNER_COL = "Corner"
FC_ORDER_COL = "FightOrder"
FC_PICTURE_COL = "Picture"
FC_DIVISION_COL = "Division"

STATUS_TO_NUM = {
    "---": 1, "Não Solicitado": 1, "Requested": 2, "Done": 3,
    "Pendente": 0, "Não Registrado": 0
}
NUM_TO_STATUS_VERBOSE = {
    0: "Pendente/N/A", 1: "Não Solicitado (---)", 
    2: "Solicitado (Requested)", 3: "Concluído (Done)"
}

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
        df[FC_ORDER_COL] = pd.to_numeric(df[FC_ORDER_COL], errors="coerce")
        df[FC_CORNER_COL] = df[FC_CORNER_COL].astype(str).str.strip().str.lower()
        df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip() 
        df[FC_PICTURE_COL] = df[FC_PICTURE_COL].astype(str).str.strip().fillna("") 
        return df.dropna(subset=[FC_FIGHTER_COL, FC_ORDER_COL])
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
        if "INACTIVE" in df_ath.columns: 
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
        if NAME_COLUMN_IN_ATTENDANCE not in cols_to_process: cols_to_process.append(NAME_COLUMN_IN_ATTENDANCE)
        for col in cols_to_process:
            if col in df_att.columns: df_att[col] = df_att[col].astype(str).str.strip()
            else: df_att[col] = None 
        expected_cols_for_logic = ["#", ATTENDANCE_ATHLETE_ID_COL, NAME_COLUMN_IN_ATTENDANCE, "Event", ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, "Notes", "User", ATTENDANCE_TIMESTAMP_COL]
        for col_exp in expected_cols_for_logic:
            if col_exp not in df_att.columns: df_att[col_exp] = None
        return df_att
    except Exception as e: st.error(f"Erro ao carregar Attendance: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def get_task_list(sheet_name=MAIN_SHEET_NAME, config_tab=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab)
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return [] 
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception as e: st.error(f"Erro ao carregar TaskList da Config: {e}"); return []

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

with st.spinner("Carregando dados das planilhas..."):
    df_fightcard = load_fightcard_data()
    df_attendance = load_attendance_data()
    all_tasks = get_task_list()
    df_athletes_info = load_athletes_info_df()

if df_fightcard.empty or not all_tasks:
    st.error("CRÍTICO: Falha ao carregar Fightcard ou Lista de Tarefas. Dashboard não pode ser gerado."); st.stop()
if df_athletes_info.empty:
    st.warning("Aviso: Infos de atletas (da aba 'df') não carregadas. Mapeamento de ID pode falhar.")
    df_athletes_info = pd.DataFrame(columns=[ATHLETE_SHEET_NAME_COL, ATHLETE_SHEET_ID_COL])

available_events = sorted(df_fightcard[FC_EVENT_COL].dropna().unique().tolist(), reverse=True) 
if not available_events: st.warning("Nenhum evento encontrado no Fightcard."); st.stop()
event_options = ["Todos os Eventos"] + available_events
selected_event_option = st.selectbox("Selecione o Evento:", options=event_options, index=0)

df_fightcard_display = df_fightcard.copy()
if selected_event_option != "Todos os Eventos":
    df_fightcard_display = df_fightcard[df_fightcard[FC_EVENT_COL] == selected_event_option].copy()
if df_fightcard_display.empty: st.info(f"Nenhuma luta para o evento '{selected_event_option}'."); st.stop()

dashboard_data_list = []
fighter_to_id_map = {}
if not df_athletes_info.empty and ATHLETE_SHEET_NAME_COL in df_athletes_info.columns and ATHLETE_SHEET_ID_COL in df_athletes_info.columns:
    df_athletes_unique_names = df_athletes_info.dropna(subset=[ATHLETE_SHEET_NAME_COL]).drop_duplicates(subset=[ATHLETE_SHEET_NAME_COL], keep='first')
    fighter_to_id_map = pd.Series(
        df_athletes_unique_names[ATHLETE_SHEET_ID_COL].values, 
        index=df_athletes_unique_names[ATHLETE_SHEET_NAME_COL].astype(str).str.strip()
    ).to_dict()

for order, group in df_fightcard_display.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby(
    [FC_EVENT_COL, FC_ORDER_COL]
):
    event, fight_order = order
    blue_s = group[group[FC_CORNER_COL] == "blue"].squeeze(axis=0)
    red_s = group[group[FC_CORNER_COL] == "red"].squeeze(axis=0)
    row_data = {"Evento": event, "Luta #": int(fight_order) if pd.notna(fight_order) else ""}

    for corner_prefix, series_data in [("Azul", blue_s), ("Vermelho", red_s)]:
        fighter_name_fc = str(series_data.get(FC_FIGHTER_COL, "N/A")).strip() if isinstance(series_data, pd.Series) else "N/A"
        athlete_id_from_map = fighter_to_id_map.get(fighter_name_fc, None) 
        pic_url = series_data.get(FC_PICTURE_COL, "") if isinstance(series_data, pd.Series) else ""
        row_data[f"Foto {corner_prefix}"] = pic_url if isinstance(pic_url, str) and pic_url.startswith("http") else None
        row_data[f"Lutador {corner_prefix}"] = fighter_name_fc
        row_data[f"ID {corner_prefix}"] = athlete_id_from_map if athlete_id_from_map else "N/D"
        
        if pd.notna(fighter_name_fc) and fighter_name_fc != "N/A" and athlete_id_from_map:
            for task in all_tasks:
                status_num = get_numeric_task_status(athlete_id_from_map, task, df_attendance)
                row_data[f"{task} ({corner_prefix})"] = status_num
        else:
            for task in all_tasks: row_data[f"{task} ({corner_prefix})"] = 0 
    row_data["Divisão"] = blue_s.get(FC_DIVISION_COL, red_s.get(FC_DIVISION_COL, "N/A")) if isinstance(blue_s, pd.Series) else (red_s.get(FC_DIVISION_COL, "N/A") if isinstance(red_s, pd.Series) else "N/A")
    dashboard_data_list.append(row_data)

if not dashboard_data_list: st.info(f"Nenhuma luta processada para '{selected_event_option}'."); st.stop()
df_dashboard = pd.DataFrame(dashboard_data_list)

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

# --- CORREÇÃO APLICADA AQUI ---
status_legends_parts = [] 
for key_num, value_desc in NUM_TO_STATUS_VERBOSE.items():
    status_legends_parts.append(f"`{key_num}`: {value_desc.split(' (')[0]}") 
help_text_general_legend = ", ".join(status_legends_parts)
# --- FIM DA CORREÇÃO ---

for task_name_col in all_tasks:
    column_config_editor[f"{task_name_col} (Azul)"] = st.column_config.NumberColumn(label=task_name_col, width="small", help=f"Status de {task_name_col}. Legenda: {help_text_general_legend}", disabled=True)
    column_config_editor[f"{task_name_col} (Vermelho)"] = st.column_config.NumberColumn(label=task_name_col, width="small", help=f"Status de {task_name_col}. Legenda: {help_text_general_legend}", disabled=True)

st.subheader(f"Detalhes das Lutas e Tarefas: {selected_event_option}")
st.markdown(f"**Legenda Status Tarefas:** {help_text_general_legend}")
st.markdown(""" <style> .stDataFrame div[data-testid="stHorizontalBlock"] > div { font-size: 15px !important; } </style> """, unsafe_allow_html=True)
table_height = (len(df_dashboard) + 1) * 38 + 10; table_height = max(400, min(table_height, 1000))
st.data_editor(df_dashboard, column_config=column_config_editor, column_order=column_order_list, hide_index=True, use_container_width=True, num_rows="fixed", disabled=True, height=table_height)
st.markdown("---")

st.subheader(f"Estatísticas do Evento: {selected_event_option}")
if not df_dashboard.empty:
    total_lutas_evento = df_dashboard["Luta #"].nunique()
    atletas_azuis = [ath for ath in df_dashboard["Lutador Azul"].dropna().unique() if ath != "N/A"]
    atletas_vermelhos = [ath for ath in df_dashboard["Lutador Vermelho"].dropna().unique() if ath != "N/A"]
    total_atletas_unicos = len(set(atletas_azuis + atletas_vermelhos))
    total_slots_tarefas = 0; done_count = 0; req_count = 0; not_sol_count = 0; pend_count = 0
    for task in all_tasks:
        for corner in ["Azul", "Vermelho"]:
            col_name = f"{task} ({corner})"
            if col_name in df_dashboard.columns:
                valid_fighter_mask = df_dashboard[f"Lutador {corner}"] != "N/A"
                # Garante que estamos somando apenas números (status 0,1,2,3)
                task_values = pd.to_numeric(df_dashboard.loc[valid_fighter_mask, col_name], errors='coerce').dropna()
                total_slots_tarefas += len(task_values) # Conta apenas os numéricos válidos
                done_count += (task_values == 3).sum()
                req_count += (task_values == 2).sum()
                not_sol_count += (task_values == 1).sum()
                pend_count += (task_values == 0).sum()
    stat_cols = st.columns(5)
    stat_cols[0].metric("Lutas", total_lutas_evento)
    stat_cols[1].metric("Atletas Únicos", total_atletas_unicos)
    stat_cols[2].metric("Tarefas 'Done' (3)", done_count, help=f"De {total_slots_tarefas} slots de tarefa considerados para atletas válidos.")
    stat_cols[3].metric("Tarefas 'Requested' (2)", req_count)
    stat_cols[4].metric("Tarefas '---' (1)", not_sol_count)
else: st.info("Nenhum dado para estatísticas do evento selecionado.")
st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
