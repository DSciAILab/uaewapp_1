# pages/DashboardNovo.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
import html 
import os 

# --- Constantes (COPIE AS SUAS CONSTANTES AQUI) ---
# ... (Mantenha as constantes como na versão anterior) ...
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
# NUM_TO_STATUS_VERBOSE não será usado diretamente na tabela HTML, mas pode ser para legenda.
NUM_TO_STATUS_VERBOSE = {
    0: "Pendente/N/A", 1: "Não Solicitado (---)", 
    2: "Solicitado (Requested)", 3: "Concluído (Done)"
}

# --- Função para Carregar CSS Externo ---
def local_css(file_name):
    current_script_path = os.path.dirname(__file__)
    css_file_path = os.path.join(current_script_path, file_name)
    try:
        with open(css_file_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS '{file_name}' NÃO encontrado em: {css_file_path}.")
    except Exception as e:
        st.error(f"Erro ao carregar CSS '{css_file_path}': {e}")

# --- Funções de Conexão e Carregamento de Dados (COPIE SUAS FUNÇÕES REAIS AQUI) ---
# get_gspread_client, connect_gsheet_tab, load_fightcard_data, 
# load_athletes_info_df, load_attendance_data, get_task_list
# (Mantenha as funções como na versão anterior do script completo)
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
    
    latest_status_str = relevant_records.iloc[-1][ATTENDANCE_STATUS_COL] # Fallback
    if ATTENDANCE_TIMESTAMP_COL in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted.loc[:, "Timestamp_dt"] = pd.to_datetime(relevant_records_sorted[ATTENDANCE_TIMESTAMP_COL], format="%d/%m/%Y %H:%M:%S", errors='coerce')
            if relevant_records_sorted["Timestamp_dt"].notna().any():
                 latest_record = relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0]
                 latest_status_str = latest_record[ATTENDANCE_STATUS_COL]
        except Exception: pass # Usa o fallback se a ordenação falhar
    return STATUS_TO_NUM.get(str(latest_status_str).strip(), 0)


# --- Função para Renderizar a Tabela HTML com Tarefas Coloridas ---
def render_fight_table_html_with_colored_tasks(df_fc, df_att, tasks_all, fighter_id_map):
    html_content = ""
    grouped_events = df_fc.groupby(FC_EVENT_COL, sort=False)
    colspan_val = 4 + (2 * len(tasks_all)) # Foto, Nome, (Tarefas), Detalhes, (Tarefas), Nome, Foto

    for ev_name, ev_group in grouped_events:
        html_content += f"<table><tr><td colspan='{colspan_val}' class='event-header-cell'>{html.escape(str(ev_name))}</td></tr></table>"
        html_content += "<table class='dashboard-fight-table'>"
        
        header_html = "<thead><tr><th>Foto</th><th>Lutador Azul</th>"
        for task in tasks_all: header_html += f"<th>{html.escape(task)}</th>"
        header_html += "<th>Detalhes</th>"
        for task in tasks_all: header_html += f"<th>{html.escape(task)}</th>"
        header_html += "<th>Lutador Vermelho</th><th>Foto</th></tr></thead><tbody>"
        html_content += header_html

        fights = ev_group.sort_values(by=FC_ORDER_COL).groupby(FC_ORDER_COL)
        for f_order, f_df in fights:
            blue_s = f_df[f_df[FC_CORNER_COL] == "blue"].squeeze(axis=0)
            red_s = f_df[f_df[FC_CORNER_COL] == "red"].squeeze(axis=0)

            html_content += "<tr>"
            for corner_prefix_render, series_data, name_class_color in [("Azul", blue_s, "blue-corner-text"), ("Vermelho", red_s, "red-corner-text")]:
                fighter_name = html.escape(str(series_data.get(FC_FIGHTER_COL, ""))) if isinstance(series_data, pd.Series) else ""
                athlete_id = fighter_id_map.get(str(series_data.get(FC_FIGHTER_COL, "")).strip(), None) if isinstance(series_data, pd.Series) else None
                
                img_src = series_data.get(FC_PICTURE_COL, '') if isinstance(series_data, pd.Series) else ''
                img_tag = f"<img src='{html.escape(str(img_src))}' class='fighter-img'>" if img_src and isinstance(img_src, str) and img_src.startswith("http") else "<div class='fighter-img' style='background-color:#333;'></div>"

                if corner_prefix_render == "Azul":
                    html_content += f"<td class='fighter-img-cell'>{img_tag}</td>"
                    html_content += f"<td class='fighter-name-cell {name_class_color}'>{fighter_name}</td>"
                
                if fighter_name and fighter_name != "N/A" and athlete_id:
                    for task_item in tasks_all:
                        status_num = get_numeric_task_status(athlete_id, task_item, df_att)
                        status_class = f"status-cell-{status_num}" # Ex: status-cell-3
                        html_content += f"<td class='task-status-html-cell {status_class}'>{status_num}</td>"
                else:
                    for _ in tasks_all: html_content += "<td class='task-status-html-cell status-cell-0'>0</td>" # Ou N/A

                if corner_prefix_render == "Azul": # Detalhes da luta após as tarefas do azul
                    division = html.escape(str(series_data.get(FC_DIVISION_COL, red_s.get(FC_DIVISION_COL, "") if isinstance(red_s, pd.Series) else "")))
                    fight_order_disp = int(f_order) if pd.notna(f_order) else ""
                    html_content += f"<td class='fight-details-cell'>FIGHT #{fight_order_disp}<br>{division}</td>"

            # Adiciona nome e foto do lutador vermelho no final da linha
            fighter_name_red = html.escape(str(red_s.get(FC_FIGHTER_COL, ""))) if isinstance(red_s, pd.Series) else ""
            img_src_red = red_s.get(FC_PICTURE_COL, '') if isinstance(red_s, pd.Series) else ''
            img_tag_red = f"<img src='{html.escape(str(img_src_red))}' class='fighter-img'>" if img_src_red and isinstance(img_src_red, str) and img_src_red.startswith("http") else "<div class='fighter-img' style='background-color:#333;'></div>"
            html_content += f"<td class='fighter-name-cell red-corner-text'>{fighter_name_red}</td>"
            html_content += f"<td class='fighter-img-cell'>{img_tag_red}</td>"
            html_content += "</tr>"
        html_content += "</tbody></table>"
    return html_content


def calculate_table_height_html(df_fightcard, base_event_h=60, fight_h_estimate=95, header_footer_h=100):
    num_events = df_fightcard[FC_EVENT_COL].nunique() if not df_fightcard.empty else 0
    num_fights = len(df_fightcard.drop_duplicates(subset=[FC_EVENT_COL, FC_ORDER_COL])) if not df_fightcard.empty else 0
    total_h = (num_events * base_event_h) + (num_fights * fight_h_estimate) + header_footer_h
    return max(total_h, 700) 

# --- Início da Página Streamlit ---
st.title("DASHBOARD DE ATLETAS E TAREFAS")
local_css("style.css") # Carrega o CSS externo
st.markdown("---")

# --- Carregamento de Dados ---
df_fc_data = None; df_att_data = None; all_tasks_list = []; df_athletes_lookup = None
loading_error_flag = False

with st.spinner("Carregando todos os dados... Aguarde!"):
    try:
        df_fc_data = load_fightcard_data() 
        df_att_data = load_attendance_data() 
        all_tasks_list = get_task_list() 
        df_athletes_lookup = load_athletes_info_df()

        if df_fc_data.empty: loading_error_flag = True; st.error("Fightcard vazio ou não carregado.")
        if not all_tasks_list: loading_error_flag = True; st.error("Lista de Tarefas vazia ou não carregada.")
        if df_athletes_lookup.empty : st.warning("Infos de Atletas (aba 'df') vazias. Mapeamento de ID pode falhar.")
            
    except Exception as e: 
        st.error(f"Erro crítico durante carregamento: {e}"); loading_error_flag = True

# --- Botão de Atualizar ---
col_btn_refresh, _ = st.columns([0.25, 0.75]) 
with col_btn_refresh:
    if st.button("🔄 Atualizar Dados", key="refresh_dashboard_btn", use_container_width=True):
        load_fightcard_data.clear(); load_attendance_data.clear(); get_task_list.clear(); load_athletes_info_df.clear()
        st.toast("Dados atualizados!", icon="🎉"); st.rerun()
st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)

# --- Seletor de Evento ---
if not loading_error_flag:
    available_events_list = sorted(df_fc_data[FC_EVENT_COL].dropna().unique().tolist(), reverse=True)
    if not available_events_list: st.warning("Nenhum evento no Fightcard."); st.stop()
    
    event_options_list = ["Todos os Eventos"] + available_events_list
    selected_event_val = st.selectbox("Selecione o Evento:", options=event_options_list, index=0)

    df_fc_display = df_fc_data.copy()
    if selected_event_val != "Todos os Eventos":
        df_fc_display = df_fc_data[df_fc_data[FC_EVENT_COL] == selected_event_val].copy()
    
    if df_fc_display.empty: st.info(f"Nenhuma luta para o evento '{selected_event_val}'."); st.stop()

    # --- Mapeamento de Nome para ID ---
    fighter_id_mapping = {}
    if not df_athletes_lookup.empty and ATHLETE_SHEET_NAME_COL in df_athletes_lookup.columns and ATHLETE_SHEET_ID_COL in df_athletes_lookup.columns:
        df_ath_unique = df_athletes_lookup.dropna(subset=[ATHLETE_SHEET_NAME_COL]).drop_duplicates(subset=[ATHLETE_SHEET_NAME_COL], keep='first')
        fighter_id_mapping = pd.Series(
            df_ath_unique[ATHLETE_SHEET_ID_COL].astype(str).str.strip().values, 
            index=df_ath_unique[ATHLETE_SHEET_NAME_COL].astype(str).str.strip()
        ).to_dict()
    else:
        st.warning("Mapeamento de ID de atleta não pôde ser criado (dados da aba 'df' ausentes ou incompletos). Status podem não ser precisos.")


    # --- Renderização da Tabela HTML ---
    st.subheader(f"Detalhes das Lutas e Tarefas: {selected_event_val}")
    status_legend_display = ", ".join([f"`{k}`: {v.split(' (')[0]}" for k, v in NUM_TO_STATUS_VERBOSE.items()])
    st.markdown(f"**Legenda Status Tarefas:** {status_legend_display}")

    if df_att_data is None: df_att_data = pd.DataFrame() # Garante que não é None
    
    html_table_output = render_fight_table_html_with_colored_tasks(df_fc_display, df_att_data, all_tasks_list, fighter_id_mapping)
    table_render_height = calculate_table_height_html(df_fc_display, all_tasks_list)
    st.components.v1.html(html_table_output, height=table_render_height, scrolling=True)
    st.markdown("---")

    # --- Estatísticas (mantidas como antes, mas adaptadas às constantes) ---
    st.subheader(f"Estatísticas do Evento: {selected_event_val}")
    # ... (código das estatísticas como na versão anterior, adaptando nomes de colunas se necessário) ...
    # Exemplo:
    if not df_fc_display.empty: # Usar df_fc_display para estatísticas do evento selecionado
        total_lutas_evento = df_fc_display[FC_ORDER_COL].nunique()
        # Recalcular atletas únicos para o df_fc_display
        atletas_azuis_ev = [ath for ath in df_fc_display[df_fc_display[FC_CORNER_COL]=='blue'][FC_FIGHTER_COL].dropna().unique() if ath != "N/A"]
        atletas_vermelhos_ev = [ath for ath in df_fc_display[df_fc_display[FC_CORNER_COL]=='red'][FC_FIGHTER_COL].dropna().unique() if ath != "N/A"]
        total_atletas_unicos_ev = len(set(atletas_azuis_ev + atletas_vermelhos_ev))

        # As estatísticas de tarefas precisariam ser re-calculadas com base nos IDs dos atletas do df_fc_display e df_attendance
        # Esta parte fica mais complexa se quiser estatísticas de tarefas *apenas* para o evento selecionado
        # Por simplicidade, vamos manter as estatísticas globais de tarefas por enquanto
        total_slots_tarefas_glob = 0; done_count_glob = 0; req_count_glob = 0; 
        if not df_attendance.empty and all_tasks_list:
             all_athlete_ids_in_event = []
             if fighter_id_mapping:
                 all_athlete_ids_in_event.extend([fighter_id_mapping.get(name) for name in atletas_azuis_ev if fighter_id_mapping.get(name) is not None])
                 all_athlete_ids_in_event.extend([fighter_id_mapping.get(name) for name in atletas_vermelhos_ev if fighter_id_mapping.get(name) is not None])
                 all_athlete_ids_in_event = list(set(all_athlete_ids_in_event))

             if all_athlete_ids_in_event:
                 df_att_evento = df_attendance[df_attendance[ATTENDANCE_ATHLETE_ID_COL].isin(all_athlete_ids_in_event)]
                 for task in all_tasks_list:
                     # Esta contagem agora é para o evento filtrado
                     relevant_statuses = df_att_evento[df_att_evento[ATTENDANCE_TASK_COL] == task][ATTENDANCE_STATUS_COL]
                     total_slots_tarefas_glob += len(relevant_statuses) # Simplificado, idealmente seria (atletas_unicos_ev * 1) por tarefa
                     done_count_glob += (relevant_statuses == "Done").sum()
                     req_count_glob += (relevant_statuses == "Requested").sum()
        
        stat_cols = st.columns(4) # Ajustado para 4 colunas de stats
        stat_cols[0].metric("Lutas no Evento", total_lutas_evento)
        stat_cols[1].metric("Atletas Únicos no Evento", total_atletas_unicos_ev)
        stat_cols[2].metric("Tarefas 'Done' (Evento)", done_count_glob, help=f"Contagem de status 'Done' para atletas deste evento.")
        stat_cols[3].metric("Tarefas 'Requested' (Evento)", req_count_glob)
    else: st.info("Nenhum dado para estatísticas do evento selecionado.")

else:
    st.error("Falha ao carregar dados essenciais. O dashboard não pôde ser renderizado. Verifique as mensagens de erro acima.")

st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
