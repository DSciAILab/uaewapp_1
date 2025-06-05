# pages/Dashboard.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
import html 
import os # Importar o módulo os

# --- 1. Page Configuration ---
# Removido st.set_page_config(), pois é geralmente definido no script principal do app multipáginas (ex: MainApp.py)
# Se este for o seu único script ou o principal, você pode descomentar e configurar aqui.
# st.set_page_config(layout="wide", page_title="Dashboard de Atletas") 

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App" 
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"  # Confirme este nome na sua aba Attendance
NAME_COLUMN_IN_ATTENDANCE = "Fighter"   # Confirme este nome na sua aba Attendance
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]

# --- Função para Carregar CSS Externo ---
def local_css(file_name):
    current_script_path = os.path.dirname(__file__)
    css_file_path = os.path.join(current_script_path, file_name)
    try:
        with open(css_file_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Arquivo CSS '{file_name}' NÃO encontrado em: {css_file_path}. Verifique o local do arquivo.")
    except Exception as e:
        st.error(f"Erro ao carregar CSS de '{css_file_path}': {e}")

# --- Funções de Conexão e Carregamento de Dados ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets: # Verifica se a chave existe nos segredos
            st.error("Erro: Credenciais `gcp_service_account` não encontradas nos segredos do Streamlit.", icon="🚨")
            st.stop() # Interrompe a execução se as credenciais não estiverem lá
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError: # Especificamente se a chave "gcp_service_account" não existir
        st.error("Erro de configuração: A chave `gcp_service_account` está ausente nos segredos.", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à API do Google / Autenticar gspread: {e}", icon="🚨")
        st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client: 
        st.error("Cliente gspread não inicializado. Verifique a função get_gspread_client.", icon="🚨")
        st.stop()
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada na planilha '{sheet_name}'.", icon="🚨"); st.stop()
    except Exception as e: # Outros erros de gspread ou rede
        st.error(f"Erro ao conectar à aba '{tab_name}' da planilha '{sheet_name}': {e}", icon="🚨"); st.stop()

@st.cache_data
def load_fightcard_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    try:
        df = pd.read_csv(url)
        if df.empty: return pd.DataFrame()
        df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip() 
        return df.dropna(subset=["Fighter", "FightOrder"])
    except Exception as e:
        st.error(f"Erro ao carregar dados do Fightcard da URL: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame()
        expected_cols = ["#", ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE, "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected_cols:
            if col not in df_att.columns: df_att[col] = None 
        if ID_COLUMN_IN_ATTENDANCE in df_att.columns: df_att[ID_COLUMN_IN_ATTENDANCE] = df_att[ID_COLUMN_IN_ATTENDANCE].astype(str).str.strip()
        if NAME_COLUMN_IN_ATTENDANCE in df_att.columns: df_att[NAME_COLUMN_IN_ATTENDANCE] = df_att[NAME_COLUMN_IN_ATTENDANCE].astype(str).str.strip()
        if "Task" in df_att.columns: df_att["Task"] = df_att["Task"].astype(str).str.strip()
        if "Status" in df_att.columns: df_att["Status"] = df_att["Status"].astype(str).str.strip()
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba Attendance: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_config_data(sheet_name=MAIN_SHEET_NAME, config_tab_name=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, config_tab_name)
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return [], [] 
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        return tasks, [] 
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba Config: {e}")
        return [], []

def get_task_status_for_athlete(athlete_identifier, task_name, df_attendance, 
                                id_col_att, name_col_att, is_identifier_id=False):
    if df_attendance.empty or not task_name or pd.isna(athlete_identifier) or athlete_identifier == "":
        return "Pendente"
    col_to_match = id_col_att if is_identifier_id else name_col_att
    if col_to_match not in df_attendance.columns: return "Pendente"
        
    relevant_records = df_attendance[
        (df_attendance[col_to_match].astype(str).str.upper() == str(athlete_identifier).upper()) &
        (df_attendance["Task"].astype(str) == task_name)
    ]
    if relevant_records.empty: return "Pendente"

    if "Timestamp" in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted.loc[:, "Timestamp_dt"] = pd.to_datetime(
                relevant_records_sorted["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce'
            )
            relevant_records_sorted.dropna(subset=["Timestamp_dt"], inplace=True)
            if not relevant_records_sorted.empty:
                return relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False).iloc[0]["Status"]
        except Exception: return relevant_records.iloc[-1]["Status"] 
    return relevant_records.iloc[-1]["Status"]

def render_dashboard_html_content(df_fc, df_att, tasks_all, id_ca, name_ca):
    html_str = "" 
    grouped_events = df_fc.groupby("Event", sort=False)

    for ev_name, ev_group in grouped_events:
        html_str += f"<table class='dashboard-table event-table'><tr><td class='event-header-row' colspan='7'>{html.escape(str(ev_name))}</td></tr></table>"
        html_str += "<table class='dashboard-table'>"
        html_str += """
        <thead>
            <tr>
                <th style="width: 8%;">Foto</th>
                <th style="width: 17%;">Lutador Azul <br/> Info Geral</th>
                <th style="width: 20%;">Tarefas (Azul)</th>
                <th style="width: 10%;">Detalhes da Luta</th>
                <th style="width: 20%;">Tarefas (Vermelho)</th>
                <th style="width: 17%;">Lutador Vermelho <br/> Info Geral</th>
                <th style="width: 8%;">Foto</th>
            </tr>
        </thead>
        <tbody>
        """
        fights = ev_group.sort_values(by="FightOrder").groupby("FightOrder")

        for f_order, f_df in fights:
            blue = f_df[f_df["Corner"]=="blue"].squeeze(axis=0) 
            red = f_df[f_df["Corner"]=="red"].squeeze(axis=0)

            b_name = html.escape(str(blue.get("Fighter",""))) if isinstance(blue,pd.Series) else ""
            r_name = html.escape(str(red.get("Fighter",""))) if isinstance(red,pd.Series) else ""
            b_info_geral = html.escape(str(blue.get("Nationality", ""))) if isinstance(blue,pd.Series) else "" # Exemplo
            r_info_geral = html.escape(str(red.get("Nationality", ""))) if isinstance(red,pd.Series) else ""   # Exemplo
            b_img_src = blue.get('Picture','') if isinstance(blue, pd.Series) else ''
            r_img_src = red.get('Picture','') if isinstance(red, pd.Series) else ''
            b_img = f"<img src='{html.escape(str(b_img_src),True)}' class='fighter-img'>" if b_img_src and isinstance(b_img_src,str)and b_img_src.startswith("http")else"<div class='fighter-img' style='background-color:#222;'></div>"
            r_img = f"<img src='{html.escape(str(r_img_src),True)}' class='fighter-img'>" if r_img_src and isinstance(r_img_src,str)and r_img_src.startswith("http")else"<div class='fighter-img' style='background-color:#222;'></div>"
            
            b_tasks_h = "<div class='task-grid'>"
            if b_name:
                for task_i in tasks_all:
                    stat_v = get_task_status_for_athlete(b_name, task_i, df_att, id_ca, name_ca, is_identifier_id=False)
                    stat_cls = "status-pending" 
                    if stat_v == "Done": stat_cls = "status-done"
                    elif stat_v == "Requested": stat_cls = "status-requested"
                    elif stat_v in ["---", "Não Solicitado"]: stat_cls = "status-not-requested"
                    b_tasks_h += f"<div class='task-item'><span class='task-status-indicator {stat_cls}'></span><span class='task-name'>{html.escape(task_i)}</span></div>"
            b_tasks_h += "</div>"
            
            r_tasks_h = "<div class='task-grid'>"
            if r_name:
                for task_i in tasks_all:
                    stat_v = get_task_status_for_athlete(r_name, task_i, df_att, id_ca, name_ca, is_identifier_id=False)
                    stat_cls = "status-pending"
                    if stat_v == "Done": stat_cls = "status-done"
                    elif stat_v == "Requested": stat_cls = "status-requested"
                    elif stat_v in ["---", "Não Solicitado"]: stat_cls = "status-not-requested"
                    r_tasks_h += f"<div class='task-item'><span class='task-status-indicator {stat_cls}'></span><span class='task-name'>{html.escape(task_i)}</span></div>"
            r_tasks_h += "</div>"
            
            div_val = html.escape(str(blue.get("Division","")if isinstance(blue,pd.Series)else(red.get("Division","")if isinstance(red,pd.Series)else"")))
            f_info = f"FIGHT #{int(f_order)}<br>{div_val}"

            html_str += f"""
            <tr>
                <td class='fighter-cell blue-corner-bg'>{b_img}</td>
                <td class='blue-corner-bg'>
                    <span class='fighter-name'>{b_name}</span>
                    <span class='fighter-info-general'>{b_info_geral}</span>
                </td>
                <td class='tasks-cell blue-corner-bg'>{b_tasks_h if b_name else ""}</td>
                <td class='fight-details-cell'>{f_info}</td>
                <td class='tasks-cell red-corner-bg'>{r_tasks_h if r_name else ""}</td>
                <td class='red-corner-bg'>
                    <span class='fighter-name'>{r_name}</span>
                    <span class='fighter-info-general'>{r_info_geral}</span>
                </td>
                <td class='fighter-cell red-corner-bg'>{r_img}</td>
            </tr>"""
        html_str += "</tbody></table>"
    return html_str

def calculate_height(df_fightcard, base_event_h=70, fight_h_estimate=170, header_footer_h=150): # Aumentado fight_h_estimate
    num_events = df_fightcard["Event"].nunique() if not df_fightcard.empty else 0
    # Contar lutas distintas corretamente (um par de lutadores por FightOrder)
    num_fights = len(df_fightcard.drop_duplicates(subset=["Event", "FightOrder"])) if not df_fightcard.empty else 0
    total_h = (num_events * base_event_h) + (num_fights * fight_h_estimate) + header_footer_h
    return max(total_h, 800) 

# --- Página Streamlit ---
st.markdown("<h1 style='text-align:center; color:white; margin-bottom:10px;'>DASHBOARD DE ATLETAS</h1>", unsafe_allow_html=True) # Reduzido margin-bottom
local_css("style.css") 

# --- Inicialização de Flags de Erro em Session State (para evitar repetição de msgs) ---
if 'fc_load_error_shown' not in st.session_state: st.session_state.fc_load_error_shown = False
if 'task_load_error_shown' not in st.session_state: st.session_state.task_load_error_shown = False
if 'att_empty_info_shown' not in st.session_state: st.session_state.att_empty_info_shown = False

# --- Carregamento de Dados ---
df_fc_data = None; df_att_data = None; task_list_data = []
loading_error = False
error_placeholder = st.empty() # Placeholder para mensagens de erro/warning de carregamento

with st.spinner("Carregando todos os dados... Aguarde!"):
    try:
        df_fc_data = load_fightcard_data() 
        df_att_data = load_attendance_data() 
        task_list_data, _ = load_config_data() 
        
        if df_fc_data.empty and not st.session_state.fc_load_error_shown:
            error_placeholder.warning("Nenhum dado de Fightcard carregado. Verifique a fonte ou se há lutas publicadas.")
            st.session_state.fc_load_error_shown = True
            loading_error = True # Impede renderização do dashboard se fightcard estiver vazio
        if not task_list_data and not st.session_state.task_load_error_shown:
            error_placeholder.error("TaskList não carregada da Configuração. Dashboard não pode exibir status de tarefas.")
            st.session_state.task_load_error_shown = True
            loading_error = True # Impede renderização se não houver lista de tarefas
            
    except Exception as e: 
        error_placeholder.error(f"Erro crítico durante o carregamento de dados: {e}")
        loading_error = True

# --- Botão de Atualizar ---
col_btn_refresh_main, _ = st.columns([0.25, 0.75]) 
with col_btn_refresh_main:
    if st.button("🔄 Atualizar Dados", key="refresh_dashboard_all_btn", use_container_width=True):
        st.session_state.fc_load_error_shown = False 
        st.session_state.task_load_error_shown = False
        st.session_state.att_empty_info_shown = False
        load_fightcard_data.clear(); load_attendance_data.clear(); load_config_data.clear()
        st.toast("Dados atualizados!", icon="🎉"); st.rerun()
st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)


# --- Renderização do Dashboard ---
if not loading_error and df_fc_data is not None and not df_fc_data.empty and task_list_data:
    if df_att_data is None or df_att_data.empty: # Se df_att_data for None após o try-except
        if not st.session_state.att_empty_info_shown:
             st.info("Dados de presença não encontrados ou vazios. Status das tarefas aparecerão como 'Pendente'.")
             st.session_state.att_empty_info_shown = True
        df_att_data = pd.DataFrame() # Garante que é um DataFrame vazio para a função de renderização
    
    dashboard_html_output = render_dashboard_html_content(
        df_fc_data, df_att_data, task_list_data, 
        ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE 
    )
    page_height = calculate_height(df_fc_data)
    st.components.v1.html(dashboard_html_output, height=page_height, scrolling=True)
elif not loading_error: 
    if df_fc_data is not None and df_fc_data.empty and not st.session_state.get('fc_load_error_shown', False):
         pass 
    elif not task_list_data and not st.session_state.get('task_load_error_shown', False):
         pass 
    elif not loading_error: # Se não houve erro crítico, mas ainda não há dados suficientes
        st.info("Aguardando dados suficientes para renderizar o dashboard.")
