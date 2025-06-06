# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
import html 
import os 

# --- Constantes (COPIE AS SUAS CONSTANTES AQUI) ---
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
NAME_COLUMN_IN_ATTENDANCE = "Fighter" # Coluna com nome do lutador na aba Attendance 

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
    0: "Pendente", 1: "---", 2: "Requested", 3: "Done"
} # Legenda mais curta para os labels

# --- Função para Carregar CSS Externo ---
def local_css(file_name):
    current_script_path = os.path.dirname(__file__)
    css_file_path = os.path.join(current_script_path, file_name)
    try:
        with open(css_file_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError: st.error(f"CSS '{file_name}' NÃO encontrado em: {css_file_path}.")
    except Exception as e: st.error(f"Erro ao carregar CSS '{css_file_path}': {e}")

# --- Funções de Conexão e Carregamento de Dados (MANTENHA SUAS FUNÇÕES FUNCIONAIS) ---
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
        # A coluna INACTIVE não é usada neste dashboard específico, mas mantida se sua função a necessitar
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

def get_numeric_task_status(athlete_id_to_check, task_name, df_attendance): # Função como antes
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

# --- Nova Função para Renderizar Tabela HTML com Task Labels ---
def render_fight_table_with_task_labels(df_fc, df_att, tasks_all, fighter_id_map_param):
    html_content = ""
    grouped_events = df_fc.groupby(FC_EVENT_COL, sort=False)

    for ev_name, ev_group in grouped_events:
        html_content += f"<table><tr><td colspan='5' class='event-header-cell'>{html.escape(str(ev_name))}</td></tr></table>" # 5 colunas agora
        html_content += "<table class='dashboard-fight-table'>" # Reutiliza a classe se os estilos gerais forem os mesmos
        html_content += """
        <thead>
            <tr>
                <th style="width: 10%;">Foto</th>
                <th style="width: 35%;">Lutador Azul & Tarefas</th>
                <th style="width: 10%;">Detalhes</th>
                <th style="width: 35%;">Lutador Vermelho & Tarefas</th>
                <th style="width: 10%;">Foto</th>
            </tr>
        </thead>
        <tbody>
        """
        fights = ev_group.sort_values(by=FC_ORDER_COL).groupby(FC_ORDER_COL)
        for f_order, f_df in fights:
            blue_s = f_df[f_df[FC_CORNER_COL] == "blue"].squeeze(axis=0)
            red_s = f_df[f_df[FC_CORNER_COL] == "red"].squeeze(axis=0)
            html_content += "<tr>"

            for corner_data in [(blue_s, "blue-corner-text"), (red_s, "red-corner-text")]:
                series_data, name_class_color = corner_data
                fighter_name_val = str(series_data.get(FC_FIGHTER_COL, "")).strip() if isinstance(series_data, pd.Series) else ""
                athlete_id_val = fighter_id_map_param.get(fighter_name_val, None) if fighter_name_val else None
                
                img_src_val = series_data.get(FC_PICTURE_COL, '') if isinstance(series_data, pd.Series) else ''
                img_tag_html = f"<img src='{html.escape(str(img_src_val))}' class='fighter-img'>" if img_src_val and isinstance(img_src_val, str) and img_src_val.startswith("http") else "<div class='fighter-img' style='background-color:#333;'></div>"

                task_labels_html = ""
                if fighter_name_val and fighter_name_val != "N/A" and athlete_id_val:
                    task_labels_html += "<div class='task-labels-container'>"
                    for task_item in tasks_all:
                        status_num = get_numeric_task_status(athlete_id_val, task_item, df_att)
                        status_text_short = NUM_TO_STATUS_VERBOSE.get(status_num, str(status_num)) # Pega a legenda curta
                        label_class = f"label-status-{status_num}"
                        task_labels_html += f"<span class='task-label {label_class}'>{html.escape(task_item)}: {html.escape(status_text_short)}</span>"
                    task_labels_html += "</div>"
                
                # Info Geral (exemplo: Nacionalidade) - pode ser adicionado abaixo do nome
                info_geral_val = html.escape(str(series_data.get("Nationality", ""))) if isinstance(series_data, pd.Series) else ""


                if corner_data[0] is blue_s: # Lutador Azul
                    html_content += f"<td class='fighter-cell'>{img_tag_html}</td>"
                    html_content += f"<td class='fighter-details-cell {name_class_color}'>"
                    html_content += f"<span class='fighter-name-main'>{html.escape(fighter_name_val)}</span>"
                    if info_geral_val: html_content += f"<span class='fighter-info-general'>{info_geral_val}</span>"
                    html_content += task_labels_html
                    html_content += "</td>"
                
                if corner_data[0] is blue_s: # Detalhes da luta após o lutador azul
                    division = html.escape(str(series_data.get(FC_DIVISION_COL, red_s.get(FC_DIVISION_COL, "") if isinstance(red_s, pd.Series) else "")))
                    fight_order_disp = int(f_order) if pd.notna(f_order) else ""
                    html_content += f"<td class='fight-details-cell'>FIGHT #{fight_order_disp}<br>{division}</td>"

                if corner_data[0] is red_s: # Lutador Vermelho
                    html_content += f"<td class='fighter-details-cell {name_class_color}'>"
                    html_content += f"<span class='fighter-name-main'>{html.escape(fighter_name_val)}</span>"
                    if info_geral_val: html_content += f"<span class='fighter-info-general'>{info_geral_val}</span>"
                    html_content += task_labels_html
                    html_content += "</td>"
                    html_content += f"<td class='fighter-cell'>{img_tag_html}</td>"
            html_content += "</tr>"
        html_content += "</tbody></table>"
    return html_content

def calculate_table_height_html_labels(df_fightcard, base_event_h=60, fight_h_estimate=120, header_footer_h=100): # fight_h_estimate pode ser maior com labels
    num_events = df_fightcard[FC_EVENT_COL].nunique() if not df_fightcard.empty else 0
    num_fights = len(df_fightcard.drop_duplicates(subset=[FC_EVENT_COL, FC_ORDER_COL])) if not df_fightcard.empty else 0
    total_h = (num_events * base_event_h) + (num_fights * fight_h_estimate) + header_footer_h
    return max(total_h, 700) 

# --- Início da Página Streamlit ---
st.markdown("<h1 style='text-align: center; font-size: 2.8em; margin-bottom: 5px;'>DASHBOARD DE ATLETAS</h1>", unsafe_allow_html=True)
local_css("style.css") 
st.markdown("---")

# ... (Carregamento de dados e seletor de evento como antes) ...
df_fc_data = None; df_att_data = None; all_tasks_list = []; df_athletes_lookup = None
loading_error_flag = False; error_placeholder = st.empty()

with st.spinner("Carregando todos os dados... Aguarde!"):
    try:
        df_fc_data = load_fightcard_data(); df_att_data = load_attendance_data() 
        all_tasks_list = get_task_list(); df_athletes_lookup = load_athletes_info_df()
        if df_fc_data.empty: loading_error_flag = True
        if not all_tasks_list: loading_error_flag = True
    except Exception as e: error_placeholder.error(f"Erro crítico durante carregamento: {e}"); loading_error_flag = True

col_btn_refresh_main, col_font_selector, _ = st.columns([0.25, 0.25, 0.5]) 
with col_btn_refresh_main:
    if st.button("🔄 Atualizar Dados", key="refresh_dashboard_btn_novo", use_container_width=True):
        load_fightcard_data.clear(); load_attendance_data.clear(); get_task_list.clear(); load_athletes_info_df.clear()
        st.toast("Dados atualizados!", icon="🎉"); st.rerun()

# --- Controle de Tamanho da Fonte (Adicionado) ---
font_size_options_map = {"Normal": "16px", "Médio": "18px", "Grande": "20px"} # Mapeia label para valor CSS
if 'font_size_label_pref' not in st.session_state:
    st.session_state.font_size_label_pref = "Normal"

with col_font_selector:
    st.session_state.font_size_label_pref = st.selectbox(
        "Fonte da Tabela:",
        options=list(font_size_options_map.keys()),
        index=list(font_size_options_map.keys()).index(st.session_state.font_size_label_pref),
        key="font_size_table_selector"
    )
selected_font_size_css = font_size_options_map[st.session_state.font_size_label_pref]

# Injeta CSS para o tamanho da fonte da tabela dinamicamente
st.markdown(f"""
<style>
    .dashboard-fight-table td, .dashboard-fight-table th {{
        font-size: {selected_font_size_css} !important;
    }}
    .fighter-name-main {{ font-size: calc({selected_font_size_css} * 1.2) !important; }}
    .task-label {{ font-size: calc({selected_font_size_css} * 0.8) !important; }}
    .event-header-cell {{ font-size: calc({selected_font_size_css} * 1.3) !important; }}
</style>
""", unsafe_allow_html=True)
st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)


# --- Lógica de Exibição Principal ---
if loading_error_flag:
    # ... (lógica de erro como antes) ...
    if df_fc_data is not None and df_fc_data.empty : error_placeholder.warning("Fightcard vazio.")
    if not all_tasks_list : error_placeholder.error("Lista de Tarefas vazia.")
    if not (df_fc_data is not None and df_fc_data.empty) and not (not all_tasks_list) : st.error("Falha ao carregar dados.")
elif df_fc_data.empty: st.warning("Nenhum dado de Fightcard para exibir.")
elif not all_tasks_list: st.error("A lista de tarefas (TaskList) não foi carregada.")
else:
    available_events_list = sorted(df_fc_data[FC_EVENT_COL].dropna().unique().tolist(), reverse=True)
    if not available_events_list: st.warning("Nenhum evento no Fightcard para selecionar."); st.stop()
    event_options_list = ["Todos os Eventos"] + available_events_list
    selected_event_val = st.selectbox("Selecione o Evento:", options=event_options_list, index=0, key="event_selector_dashboard_labels")
    df_fc_display = df_fc_data.copy()
    if selected_event_val != "Todos os Eventos":
        df_fc_display = df_fc_data[df_fc_data[FC_EVENT_COL] == selected_event_val].copy()
    if df_fc_display.empty: st.info(f"Nenhuma luta para o evento '{selected_event_val}'."); st.stop()

    fighter_id_mapping = {}
    if not df_athletes_lookup.empty and ATHLETE_SHEET_NAME_COL in df_athletes_lookup.columns and ATHLETE_SHEET_ID_COL in df_athletes_lookup.columns:
        df_ath_unique = df_athletes_lookup.dropna(subset=[ATHLETE_SHEET_NAME_COL]).drop_duplicates(subset=[ATHLETE_SHEET_NAME_COL], keep='first')
        fighter_id_mapping = pd.Series(df_ath_unique[ATHLETE_SHEET_ID_COL].astype(str).str.strip().values, index=df_ath_unique[ATHLETE_SHEET_NAME_COL].astype(str).str.strip()).to_dict()
    else: st.warning("Mapeamento de ID de atleta não pôde ser criado.")

    st.subheader(f"Detalhes das Lutas e Tarefas: {selected_event_val}")
    # Legenda não é mais necessária se os labels mostrarem o status diretamente
    # status_legend_parts_disp = [] 
    # for key_n, value_d in NUM_TO_STATUS_VERBOSE.items(): status_legends_parts_disp.append(f"`{key_n}`: {value_d.split(' (')[0]}") 
    # help_text_general_legend_disp = ", ".join(status_legends_parts_disp)
    # st.markdown(f"**Legenda Status Tarefas:** {help_text_general_legend_disp}")

    if df_att_data is None: df_att_data = pd.DataFrame() 
    elif df_att_data.empty and not st.session_state.get('att_empty_info_shown_dn_labels', False): # Nova chave de session_state
        st.info("Dados de presença vazios. Status como 'Pendente'."); st.session_state.att_empty_info_shown_dn_labels = True
    
    html_table_output = render_fight_table_with_task_labels(df_fc_display, df_att_data, all_tasks_list, fighter_id_mapping)
    table_render_height = calculate_table_height_html_labels(df_fc_display)
    st.components.v1.html(html_table_output, height=table_render_height, scrolling=True)
    st.markdown("---")

    # --- Estatísticas (mantidas como antes) ---
    st.subheader(f"Estatísticas do Evento: {selected_event_val}")
    # ... (seu código de estatísticas) ...
    if not df_fc_display.empty:
        total_lutas_evento = df_fc_display[FC_ORDER_COL].nunique()
        atletas_azuis_ev = [ath for ath in df_fc_display[df_fc_display[FC_CORNER_COL]=='blue'][FC_FIGHTER_COL].dropna().unique() if ath != "N/A"]
        atletas_vermelhos_ev = [ath for ath in df_fc_display[df_fc_display[FC_CORNER_COL]=='red'][FC_FIGHTER_COL].dropna().unique() if ath != "N/A"]
        total_atletas_unicos_ev = len(set(atletas_azuis_ev + atletas_vermelhos_ev))
        done_count_glob = 0; req_count_glob = 0; not_sol_count_glob = 0
        if not df_att_data.empty and all_tasks_list:
             all_athlete_ids_in_event = []
             if fighter_id_mapping:
                 all_athlete_ids_in_event.extend([fighter_id_mapping.get(name) for name in atletas_azuis_ev if fighter_id_mapping.get(name) is not None])
                 all_athlete_ids_in_event.extend([fighter_id_mapping.get(name) for name in atletas_vermelhos_ev if fighter_id_mapping.get(name) is not None])
                 all_athlete_ids_in_event = list(set(all_athlete_ids_in_event))
             if all_athlete_ids_in_event:
                 df_att_evento = df_att_data[df_att_data[ATTENDANCE_ATHLETE_ID_COL].isin(all_athlete_ids_in_event)]
                 if not df_att_evento.empty:
                    for task in all_tasks_list:
                        # Recalcula o status numérico para cada tarefa/atleta no evento
                        for ath_id_ev in all_athlete_ids_in_event:
                            status_num_ev = get_numeric_task_status(ath_id_ev, task, df_att_evento)
                            if status_num_ev == 3: done_count_glob +=1
                            elif status_num_ev == 2: req_count_glob +=1
                            elif status_num_ev == 1: not_sol_count_glob +=1
        stat_cols = st.columns(4) 
        stat_cols[0].metric("Lutas no Evento", total_lutas_evento)
        stat_cols[1].metric("Atletas Únicos no Evento", total_atletas_unicos_ev)
        stat_cols[2].metric("Tarefas 'Done'", done_count_glob)
        stat_cols[3].metric("Tarefas 'Requested'", req_count_glob)
    else: st.info("Nenhum dado para estatísticas do evento.")
st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
