# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
from streamlit_autorefresh import st_autorefresh 
# import html # Não é estritamente necessário para esta versão
# import os  # Não é estritamente necessário para esta versão

# --- 1. Configuração da Página ---
# Se este script for rodado como uma página de um app multipáginas, 
# st.set_page_config é chamado no script principal (ex: MainApp.py).
# Se este for um app de uma única página, descomente e configure aqui.
# if 'page_config_set_dashboard_novo' not in st.session_state:
#     st.set_page_config(layout="wide", page_title="Dashboard de Atletas v2")
#     st.session_state.page_config_set_dashboard_novo = True


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

STATUS_TO_EMOJI = {
    "Done": "🟩",       
    "Requested": "🟧", 
    "---": "➖",        
    "Não Solicitado": "➖",
    "Pendente": "🟥",      
    "Não Registrado": "🟥" 
}
DEFAULT_EMOJI = "🟥" # Emoji padrão se o status não for reconhecido

# Legenda para o usuário
EMOJI_LEGEND = {
    "🟩": "Done (Concluído)",
    "🟧": "Requested (Solicitado)",
    "➖": "--- (Não Solicitado/Cancelado)",
    "🟥": "Pendente / Sem Info"
}

# --- Funções de Conexão e Carregamento de Dados ---
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

def get_task_status_representation(athlete_id_to_check, task_name, df_attendance):
    if df_attendance.empty or pd.isna(athlete_id_to_check) or str(athlete_id_to_check).strip() == "" or not task_name:
        return STATUS_TO_EMOJI.get("Pendente", DEFAULT_EMOJI) 
    if ATTENDANCE_ATHLETE_ID_COL not in df_attendance.columns or \
       ATTENDANCE_TASK_COL not in df_attendance.columns or \
       ATTENDANCE_STATUS_COL not in df_attendance.columns:
        return STATUS_TO_EMOJI.get("Pendente", DEFAULT_EMOJI) 
    athlete_id_str = str(athlete_id_to_check).strip()
    task_name_str = str(task_name).strip()
    relevant_records = df_attendance[
        (df_attendance[ATTENDANCE_ATHLETE_ID_COL].astype(str).str.strip() == athlete_id_str) &
        (df_attendance[ATTENDANCE_TASK_COL].astype(str).str.strip() == task_name_str)
    ]
    if relevant_records.empty: return STATUS_TO_EMOJI.get("Pendente", DEFAULT_EMOJI)
    latest_status_str = relevant_records.iloc[-1][ATTENDANCE_STATUS_COL] 
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted.loc[:, "Timestamp_dt"] = pd.to_datetime(relevant_records_sorted[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            if relevant_records_sorted["Timestamp_dt"].notna().any():
                 latest_record = relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0]
                 latest_status_str = latest_record[ATTENDANCE_STATUS_COL]
        except Exception: pass 
    return STATUS_TO_EMOJI.get(str(latest_status_str).strip(), DEFAULT_EMOJI)

# --- Início da Página Streamlit ---
st.markdown("<h1 style='text-align: center; font-size: 2.5em; margin-bottom: 5px;'>DASHBOARD DE ATLETAS E TAREFAS</h1>", unsafe_allow_html=True)
refresh_count = st_autorefresh(interval=60 * 1000, limit=None, key="dashboard_auto_refresh")

if 'font_size_preference_dn' not in st.session_state: st.session_state.font_size_preference_dn = "Normal" 
font_size_options = {"Normal": "1.0rem", "Médio": "1.1rem", "Grande": "1.2rem"}
control_cols = st.columns([0.25, 0.25, 0.5])
with control_cols[0]:
    if st.button("🔄 Atualizar Agora", key="refresh_dashboard_manual_btn", use_container_width=True):
        load_fightcard_data.clear(); load_attendance_data.clear(); get_task_list.clear(); load_athletes_info_df.clear()
        st.toast("Dados atualizados!", icon="🎉"); st.rerun()
with control_cols[1]:
    font_selection = st.selectbox("Fonte da Tabela:", options=list(font_size_options.keys()),index=list(font_size_options.keys()).index(st.session_state.font_size_preference_dn),key="font_size_selector_dn")
    if font_selection != st.session_state.font_size_preference_dn:
        st.session_state.font_size_preference_dn = font_selection; st.rerun()
current_font_css = font_size_options[st.session_state.font_size_preference_dn]
st.markdown(f"""<style> div[data-testid="stDataFrameResizable"] div[data-baseweb="table-cell"], div[data-testid="stDataFrameResizable"] div[data-baseweb="table-header-cell"] {{ font-size: {current_font_css} !important; text-align: center !important; vertical-align: middle !important; }} div[data-testid="stDataFrameResizable"] div[data-baseweb="table-header-cell"] {{ font-weight: bold !important; text-transform: uppercase; }} </style>""", unsafe_allow_html=True)
st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)

df_fightcard = None; df_attendance = None; all_tasks = None; df_athletes_info = None; loading_error = False
error_placeholder = st.empty()
with st.spinner("Carregando todos os dados... Aguarde!"):
    try:
        df_fightcard = load_fightcard_data(); df_attendance = load_attendance_data() 
        all_tasks = get_task_list(); df_athletes_info = load_athletes_info_df()
        if df_fightcard.empty: loading_error = True
        if not all_tasks: loading_error = True
    except Exception as e: error_placeholder.error(f"Erro crítico durante carregamento: {e}"); loading_error = True

if loading_error:
    if df_fightcard is not None and df_fightcard.empty : error_placeholder.warning("Fightcard vazio.")
    if not all_tasks : error_placeholder.error("Lista de Tarefas vazia.")
    if not (df_fightcard is not None and df_fightcard.empty) and not (not all_tasks) : st.error("Falha ao carregar dados.")
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
    else: st.warning("Mapeamento de ID de atleta não pôde ser criado.")

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
            fighter_id_display = athlete_id_from_map if athlete_id_from_map else "N/D"
            row_data[f"Lutador {corner_prefix}"] = f"{fighter_id_display} - {fighter_name_fc}" if fighter_name_fc != "N/A" else "N/A"
            
            identifier_for_status = athlete_id_from_map 
            if pd.notna(fighter_name_fc) and fighter_name_fc != "N/A":
                for task in all_tasks:
                    emoji_status = DEFAULT_EMOJI 
                    if identifier_for_status: 
                        emoji_status = get_task_status_representation(identifier_for_status, task, df_attendance)
                    row_data[f"{task} ({corner_prefix})"] = emoji_status
            else:
                for task in all_tasks: row_data[f"{task} ({corner_prefix})"] = STATUS_TO_EMOJI.get("Pendente", DEFAULT_EMOJI)
        row_data["Divisão"] = blue_s.get(FC_DIVISION_COL, red_s.get(FC_DIVISION_COL, "N/A")) if isinstance(blue_s, pd.Series) else (red_s.get(FC_DIVISION_COL, "N/A") if isinstance(red_s, pd.Series) else "N/A")
        dashboard_data_list.append(row_data)

    if not dashboard_data_list: st.info(f"Nenhuma luta processada para '{selected_event_option}'."); st.stop()
    df_dashboard = pd.DataFrame(dashboard_data_list)

    column_config_editor = {
        "Evento": st.column_config.TextColumn(width="small", disabled=True),
        "Luta #": st.column_config.NumberColumn(width="small", format="%d", disabled=True),
        "Foto Azul": st.column_config.ImageColumn("Foto (A)", width="small"),
        "Lutador Azul": st.column_config.TextColumn("Lutador (A)", width="large", disabled=True),
        "Divisão": st.column_config.TextColumn(width="medium", disabled=True),
        "Lutador Vermelho": st.column_config.TextColumn("Lutador (V)", width="large", disabled=True),
        "Foto Vermelho": st.column_config.ImageColumn("Foto (V)", width="small"),
    }
    column_order_list = ["Evento", "Luta #", "Foto Azul", "Lutador Azul"] # Removidas colunas de ID separadas
    for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Azul)")
    column_order_list.append("Divisão")
    for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Vermelho)")
    column_order_list.extend(["Lutador Vermelho", "Foto Vermelho"]) # Removidas colunas de ID separadas
    
    legend_parts = [f"{emoji}: {desc}" for emoji, desc in EMOJI_LEGEND.items() if emoji.strip() != ""]
    help_text_general_legend_disp = ", ".join(legend_parts)

    for task_name_col in all_tasks:
        column_config_editor[f"{task_name_col} (Azul)"] = st.column_config.TextColumn(label=task_name_col, width="small", help=f"Status: {help_text_general_legend_disp}", disabled=True)
        column_config_editor[f"{task_name_col} (Vermelho)"] = st.column_config.TextColumn(label=task_name_col, width="small", help=f"Status: {help_text_general_legend_disp}", disabled=True)

    st.subheader(f"Detalhes das Lutas e Tarefas: {selected_event_option}")
    st.markdown(f"**Legenda Status Tarefas:** {help_text_general_legend_disp}")
    table_height = (len(df_dashboard) + 1) * 45 + 10; table_height = max(400, min(table_height, 1200)) 
    st.data_editor(df_dashboard, column_config=column_config_editor, column_order=column_order_list, hide_index=True, use_container_width=True, num_rows="fixed", disabled=True, height=table_height)
    st.markdown("---")

    st.subheader(f"Estatísticas do Evento: {selected_event_option}")
    if not df_dashboard.empty:
        total_lutas_evento = df_dashboard["Luta #"].nunique()
        unique_fighters_event = set()
        for _, row in df_dashboard.iterrows():
            if row["Lutador Azul"] != "N/A": unique_fighters_event.add(row["Lutador Azul"].split(" - ",1)[0].strip())
            if row["Lutador Vermelho"] != "N/A": unique_fighters_event.add(row["Lutador Vermelho"].split(" - ",1)[0].strip())
        total_atletas_unicos_ev = len(unique_fighters_event)
        
        done_count = 0; req_count = 0; not_sol_count = 0; pend_count = 0; total_task_slots_considered = 0
        for task in all_tasks:
            for corner in ["Azul", "Vermelho"]:
                col_name = f"{task} ({corner})"
                if col_name in df_dashboard.columns:
                    valid_fighter_mask = df_dashboard[f"Lutador {corner}"] != "N/A"
                    task_emojis_series = df_dashboard.loc[valid_fighter_mask, col_name]
                    total_task_slots_considered += len(task_emojis_series)
                    done_count += (task_emojis_series == STATUS_TO_EMOJI["Done"]).sum()
                    req_count += (task_emojis_series == STATUS_TO_EMOJI["Requested"]).sum()
                    not_sol_count += (task_emojis_series == STATUS_TO_EMOJI["---"]).sum() # ou "Não Solicitado"
                    pend_count += (task_emojis_series == STATUS_TO_EMOJI["Pendente"]).sum() # ou "Não Registrado" ou DEFAULT_EMOJI
        
        stat_cols = st.columns(5)
        stat_cols[0].metric("Lutas", total_lutas_evento)
        stat_cols[1].metric("Atletas Únicos", total_atletas_unicos_ev)
        stat_cols[2].metric(f"Tarefas {STATUS_TO_EMOJI['Done']}", done_count, help=f"De {total_task_slots_considered} slots.")
        stat_cols[3].metric(f"Tarefas {STATUS_TO_EMOJI['Requested']}", req_count)
        stat_cols[4].metric(f"Tarefas {STATUS_TO_EMOJI['---']}", not_sol_count)
    else: st.info("Nenhum dado para estatísticas do evento.")
    st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
