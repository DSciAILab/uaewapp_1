# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
from streamlit_autorefresh import st_autorefresh # Para auto-atualização

# --- 1. Configuração da Página ---
# Se este for o script principal ou você quer garantir layout wide por página:
if 'page_config_set_dashboard_novo' not in st.session_state:
    st.set_page_config(layout="wide", page_title="Dashboard de Atletas v2")
    st.session_state.page_config_set_dashboard_novo = True

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
# Modificado para incluir o emoji para o status 2
NUM_TO_STATUS_VERBOSE = {
    0: "Pendente/N/A", 
    1: "Não Solicitado (---)", 
    2: "Solicitado (Requested) ✅", # Adicionado Emoji aqui
    3: "Concluído (Done)"
}

# --- Funções de Conexão e Carregamento de Dados (MANTENHA SUAS FUNÇÕES FUNCIONAIS) ---
# ... (Cole suas funções get_gspread_client, connect_gsheet_tab, load_fightcard_data, 
#      load_athletes_info_df, load_attendance_data, get_task_list, get_numeric_task_status
#      da versão anterior do script. Elas não precisam de grandes mudanças para estes requisitos.)
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets: st.error("CRÍTICO: `gcp_service_account` não nos segredos.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e: st.error(f"CRÍTICO: Erro gspread client: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client: st.error("CRÍTICO: Cliente gspread não inicializado.", icon="🚨"); st.stop()
    try: return gspread_client.open(sheet_name).worksheet(tab_name)
    except Exception as e: st.error(f"CRÍTICO: Erro ao conectar {sheet_name}/{tab_name}: {e}", icon="🚨"); st.stop()

@st.cache_data
def load_fightcard_data(): 
    try:
        df = pd.read_csv(FIGHTCARD_SHEET_URL);
        if df.empty: return pd.DataFrame()
        df.columns = df.columns.str.strip()
        df[FC_ORDER_COL] = pd.to_numeric(df[FC_ORDER_COL], errors="coerce")
        df[FC_CORNER_COL] = df[FC_CORNER_COL].astype(str).str.strip().str.lower()
        df[FC_FIGHTER_COL] = df[FC_FIGHTER_COL].astype(str).str.strip() 
        df[FC_PICTURE_COL] = df[FC_PICTURE_COL].astype(str).str.strip().fillna("") 
        return df.dropna(subset=[FC_FIGHTER_COL, FC_ORDER_COL])
    except Exception as e: st.error(f"Erro ao carregar Fightcard: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def load_athletes_info_df(sheet_name=MAIN_SHEET_NAME, athletes_tab=ATHLETES_INFO_TAB_NAME):
    g_client = get_gspread_client()
    ws = connect_gsheet_tab(g_client, sheet_name, athletes_tab)
    try:
        df_ath = pd.DataFrame(ws.get_all_records());
        if df_ath.empty: return pd.DataFrame()
        if ATHLETE_SHEET_ID_COL in df_ath.columns: df_ath[ATHLETE_SHEET_ID_COL] = df_ath[ATHLETE_SHEET_ID_COL].astype(str).str.strip()
        else: df_ath[ATHLETE_SHEET_ID_COL] = None
        if ATHLETE_SHEET_NAME_COL in df_ath.columns: df_ath[ATHLETE_SHEET_NAME_COL] = df_ath[ATHLETE_SHEET_NAME_COL].astype(str).str.strip()
        else: df_ath[ATHLETE_SHEET_NAME_COL] = None
        if "INACTIVE" in df_ath.columns: df_ath["INACTIVE"] = df_ath["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
        else: df_ath["INACTIVE"] = False
        return df_ath
    except Exception as e: st.error(f"Erro ao carregar infos dos atletas '{athletes_tab}': {e}"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records()); 
        if df_att.empty: return pd.DataFrame()
        cols_to_process = [ATTENDANCE_ATHLETE_ID_COL, ATTENDANCE_TASK_COL, ATTENDANCE_STATUS_COL, NAME_COLUMN_IN_ATTENDANCE]
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
        data = worksheet.get_all_values();
        if not data or len(data) < 1: return [] 
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        return df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
    except Exception as e: st.error(f"Erro ao carregar TaskList da Config: {e}"); return []

def get_numeric_task_status(athlete_id_to_check, task_name, df_attendance):
    if df_attendance.empty or pd.isna(athlete_id_to_check) or str(athlete_id_to_check).strip() == "" or not task_name: return 0 
    if ATTENDANCE_ATHLETE_ID_COL not in df_attendance.columns or ATTENDANCE_TASK_COL not in df_attendance.columns or ATTENDANCE_STATUS_COL not in df_attendance.columns: return 0 
    athlete_id_str = str(athlete_id_to_check).strip()
    task_name_str = str(task_name).strip()
    relevant_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == athlete_id_str) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip() == task_name_str)
    ]
    if relevant_records.empty: return 0
    latest_status_str = relevant_records.iloc[-1][ATTENDANCE_STATUS_COL] 
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted.loc[:, "Timestamp_dt"] = pd.to_datetime(relevant_records_sorted[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            if relevant_records_sorted["Timestamp_dt"].notna().any():
                 latest_record = relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0]
                 latest_status_str = latest_record[ATTENDANCE_STATUS_COL]
        except Exception: pass 
    return STATUS_TO_NUM.get(str(latest_status_str).strip(), 0)

# --- Início da Página Streamlit ---
st.markdown("<h1 style='text-align: center; font-size: 2.5em; margin-bottom: 5px;'>DASHBOARD DE ATLETAS E TAREFAS</h1>", unsafe_allow_html=True)

# --- Auto-refresh e Controle de Tamanho da Fonte ---
refresh_interval = st_autorefresh(interval=60 * 1000, limit=None, key="dashboard_refresh") # 60 segundos

if 'font_size_preference_dn' not in st.session_state: # Usar chave única para esta página
    st.session_state.font_size_preference_dn = "Normal" 

font_size_options = {"Normal": "1.0rem", "Médio": "1.1rem", "Grande": "1.2rem"} # Ajustado para ser mais sutil

# Colocar controles no topo
control_cols = st.columns([0.25, 0.25, 0.5])
with control_cols[0]:
    if st.button("🔄 Atualizar Agora", key="refresh_dashboard_manual_btn", use_container_width=True):
        load_fightcard_data.clear(); load_attendance_data.clear(); get_task_list.clear(); load_athletes_info_df.clear()
        st.toast("Dados atualizados!", icon="🎉"); st.rerun()
with control_cols[1]:
    font_selection = st.selectbox(
        "Fonte da Tabela:", options=list(font_size_options.keys()),
        index=list(font_size_options.keys()).index(st.session_state.font_size_preference_dn),
        key="font_size_selector_dn"
    )
    if font_selection != st.session_state.font_size_preference_dn:
        st.session_state.font_size_preference_dn = font_selection
        st.rerun() # Força rerun para aplicar novo CSS

current_font_css = font_size_options[st.session_state.font_size_preference_dn]
st.markdown(f"""
<style>
    div[data-testid="stDataFrameResizable"] div[data-baseweb="table-cell"],
    div[data-testid="stDataFrameResizable"] div[data-baseweb="table-header-cell"] {{
        font-size: {current_font_css} !important;
    }}
    div[data-testid="stDataFrameResizable"] div[data-baseweb="table-header-cell"] {{
        font-weight: bold !important; text-transform: uppercase;
    }}
</style>""", unsafe_allow_html=True)
st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)

# --- Carregamento Inicial de Dados ---
# ... (lógica de carregamento como antes, com with st.spinner) ...
df_fightcard = None; df_attendance = None; all_tasks = None; df_athletes_info = None
loading_error = False; error_placeholder = st.empty()
with st.spinner("Carregando todos os dados... Aguarde!"):
    try:
        df_fightcard = load_fightcard_data(); df_attendance = load_attendance_data() 
        all_tasks = get_task_list(); df_athletes_info = load_athletes_info_df()
        if df_fightcard.empty: loading_error = True
        if not all_tasks: loading_error = True
    except Exception as e: error_placeholder.error(f"Erro crítico durante carregamento: {e}"); loading_error = True

# --- Lógica de Exibição Principal ---
if loading_error:
    # ... (lógica de erro como antes) ...
    if df_fightcard is not None and df_fightcard.empty : error_placeholder.warning("Fightcard vazio ou não carregado.")
    if not all_tasks : error_placeholder.error("Lista de Tarefas vazia ou não carregada.")
    if not (df_fightcard is not None and df_fightcard.empty) and not (not all_tasks) : st.error("Falha ao carregar dados. Verifique logs.")
elif df_fightcard.empty: st.warning("Nenhum dado de Fightcard para exibir.")
elif not all_tasks: st.error("A lista de tarefas (TaskList) não foi carregada.")
else:
    available_events = sorted(df_fightcard[FC_EVENT_COL].dropna().unique().tolist(), reverse=True) 
    if not available_events: st.warning("Nenhum evento no Fightcard para selecionar."); st.stop()
    event_options = ["Todos os Eventos"] + available_events
    selected_event_option = st.selectbox("Selecione o Evento:", options=event_options, index=0, key="event_selector_dashboard_novo")
    df_fightcard_display = df_fightcard.copy()
    if selected_event_option != "Todos os Eventos":
        df_fightcard_display = df_fightcard[df_fightcard[FC_EVENT_COL] == selected_event_option].copy()
    if df_fightcard_display.empty: st.info(f"Nenhuma luta para o evento '{selected_event_option}'."); st.stop()

    fighter_to_id_map = {}
    if not df_athletes_info.empty and ATHLETE_SHEET_NAME_COL in df_athletes_info.columns and ATHLETE_SHEET_ID_COL in df_athletes_info.columns:
        df_ath_unique = df_athletes_info.dropna(subset=[ATHLETE_SHEET_NAME_COL]).drop_duplicates(subset=[ATHLETE_SHEET_NAME_COL], keep='first')
        fighter_to_id_map = pd.Series(df_ath_unique[ATHLETE_SHEET_ID_COL].astype(str).str.strip().values, index=df_ath_unique[ATHLETE_SHEET_NAME_COL].astype(str).str.strip()).to_dict()
    else: st.warning("Mapeamento de ID de atleta não pôde ser criado (infos de atletas ausentes).")

    dashboard_data_list = []
    for order, group in df_fightcard_display.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby([FC_EVENT_COL, FC_ORDER_COL]):
        event, fight_order = order
        blue_s = group[group[FC_CORNER_COL] == "blue"].squeeze(axis=0); red_s = group[group[FC_CORNER_COL] == "red"].squeeze(axis=0)
        row_data = {"Evento": event, "Luta #": int(fight_order) if pd.notna(fight_order) else ""}

        for corner_prefix, series_data in [("Azul", blue_s), ("Vermelho", red_s)]:
            fighter_name_fc = str(series_data.get(FC_FIGHTER_COL, "N/A")).strip() if isinstance(series_data, pd.Series) else "N/A"
            athlete_id_from_map = fighter_to_id_map.get(fighter_name_fc, None) 
            pic_url = series_data.get(FC_PICTURE_COL, "") if isinstance(series_data, pd.Series) else ""
            
            row_data[f"Foto {corner_prefix}"] = pic_url if isinstance(pic_url, str) and pic_url.startswith("http") else None
            
            # --- Combina ID e Nome do Lutador ---
            fighter_id_display = athlete_id_from_map if athlete_id_from_map else "N/D"
            row_data[f"Lutador {corner_prefix} (ID)"] = f"{fighter_id_display} - {fighter_name_fc}" if fighter_name_fc != "N/A" else "N/A"
            
            identifier_for_status = athlete_id_from_map 
            if pd.notna(fighter_name_fc) and fighter_name_fc != "N/A":
                for task in all_tasks:
                    status_num = 0 
                    if identifier_for_status: status_num = get_numeric_task_status(identifier_for_status, task, df_attendance)
                    # Se o status for 2, armazena o emoji ✅, senão o número
                    row_data[f"{task} ({corner_prefix})"] = "✅" if status_num == 2 else status_num
            else:
                for task in all_tasks: row_data[f"{task} ({corner_prefix})"] = 0 # Ou "" para não mostrar 0 para N/A
        row_data["Divisão"] = blue_s.get(FC_DIVISION_COL, red_s.get(FC_DIVISION_COL, "N/A")) if isinstance(blue_s, pd.Series) else (red_s.get(FC_DIVISION_COL, "N/A") if isinstance(red_s, pd.Series) else "N/A")
        dashboard_data_list.append(row_data)

    if not dashboard_data_list: st.info(f"Nenhuma luta processada para '{selected_event_option}'."); st.stop()
    df_dashboard = pd.DataFrame(dashboard_data_list)

    # --- Configuração das Colunas para st.data_editor ---
    column_config_editor = {
        "Evento": st.column_config.TextColumn(width="small", disabled=True),
        "Luta #": st.column_config.NumberColumn(width="small", format="%d", disabled=True),
        "Foto Azul": st.column_config.ImageColumn("Foto (A)", width="small"),
        "Lutador Azul (ID)": st.column_config.TextColumn("Lutador (A)", width="large", disabled=True), # Ajustado
        "Divisão": st.column_config.TextColumn(width="medium", disabled=True),
        "Lutador Vermelho (ID)": st.column_config.TextColumn("Lutador (V)", width="large", disabled=True), # Ajustado
        "Foto Vermelho": st.column_config.ImageColumn("Foto (V)", width="small"),
    }
    # Ordem das colunas na tabela
    column_order_list = ["Evento", "Luta #", "Foto Azul", "Lutador Azul (ID)"]
    for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Azul)")
    column_order_list.append("Divisão")
    for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Vermelho)")
    column_order_list.extend(["Lutador Vermelho (ID)", "Foto Vermelho"])
    
    status_legends_parts_disp = [] 
    for key_n, value_d in NUM_TO_STATUS_VERBOSE.items(): 
        status_legends_parts_disp.append(f"`{key_n if key_n != 2 else '✅'}`: {value_d.split(' (')[0].replace('Requested', 'Solicitado')}") 
    help_text_general_legend_disp = ", ".join(status_legends_parts_disp)

    for task_name_col in all_tasks:
        # Para colunas de tarefa, agora são TextColumn para acomodar o emoji
        column_config_editor[f"{task_name_col} (Azul)"] = st.column_config.TextColumn(
            label=task_name_col, width="small", help=f"Status: {help_text_general_legend_disp}", disabled=True
        )
        column_config_editor[f"{task_name_col} (Vermelho)"] = st.column_config.TextColumn(
            label=task_name_col, width="small", help=f"Status: {help_text_general_legend_disp}", disabled=True
        )

    st.subheader(f"Detalhes das Lutas e Tarefas: {selected_event_option}")
    st.markdown(f"**Legenda Status Tarefas:** {help_text_general_legend_disp}")
    
    table_height = (len(df_dashboard) + 1) * 45 + 10; table_height = max(400, min(table_height, 1200)) 
    st.data_editor(
        df_dashboard,
        column_config=column_config_editor,
        column_order=column_order_list,
        hide_index=True,
        use_container_width=True, # Garante que a tabela tente usar a largura total
        num_rows="fixed",
        disabled=True, 
        height=table_height
    )
    st.markdown("---")

    # --- Estatísticas do Evento Selecionado ---
    st.subheader(f"Estatísticas do Evento: {selected_event_option}")
    if not df_dashboard.empty:
        # ... (lógica de estatísticas como antes, precisa ser ajustada se as colunas de tarefa agora contêm emojis) ...
        # Para as estatísticas, precisaríamos reverter o emoji para número ou contar strings.
        # Por simplicidade, vou remover a parte de contagem de status das estatísticas por enquanto.
        total_lutas_evento = df_dashboard["Luta #"].nunique()
        atletas_azuis_ev = [ath for ath in df_dashboard["Lutador Azul (ID)"].dropna().unique() if ath != "N/A"]
        atletas_vermelhos_ev = [ath for ath in df_dashboard["Lutador Vermelho (ID)"].dropna().unique() if ath != "N/A"]
        
        # Para contar atletas únicos, precisamos extrair os nomes/IDs dos campos combinados
        unique_fighters = set()
        for fighter_id_combo in atletas_azuis_ev + atletas_vermelhos_ev:
            if isinstance(fighter_id_combo, str) and '-' in fighter_id_combo:
                 unique_fighters.add(fighter_id_combo.split('-',1)[0].strip()) # Pega o ID
            elif fighter_id_combo != "N/A":
                 unique_fighters.add(str(fighter_id_combo).strip())


        total_atletas_unicos_ev = len(unique_fighters)
        
        stat_cols = st.columns(2) # Reduzido para 2 métricas simples
        stat_cols[0].metric("Lutas no Evento", total_lutas_evento)
        stat_cols[1].metric("Atletas Únicos no Evento", total_atletas_unicos_ev)
    else: 
        st.info("Nenhum dado para estatísticas do evento.")
    st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
