# dashboard_page.py (ou o nome do seu arquivo)

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime, timedelta 
import html 

# --- 1. Page Configuration ---
st.set_page_config(layout="wide", page_title="Dashboard de Atletas")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App" 
# ATHLETES_TAB_NAME = "df" # Não usado para carregar dados de atletas neste script, fightcard é a fonte.
USERS_TAB_NAME = "Users" # Usado por get_valid_user_info, pode não ser necessário para este dashboard específico.
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"

# !!! IMPORTANTE: AJUSTE ESTES NOMES DE COLUNA CONFORME SUA ABA "Attendance" !!!
ID_COLUMN_IN_ATTENDANCE = "Athlete ID"  # Coluna de ID do atleta na aba Attendance.
NAME_COLUMN_IN_ATTENDANCE = "Fighter"   # Coluna de NOME do atleta na aba Attendance.

STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]
# NO_TASK_SELECTED_LABEL não é usado neste dashboard, pois exibimos todas as tarefas.

# --- Função para Carregar CSS Externo ---
def local_css(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Arquivo CSS '{file_name}' não encontrado. Crie-o na mesma pasta do script.")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")

# --- Funções de Conexão e Carregamento de Dados ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError as e: 
        st.error(f"Erro config: Chave GCP ausente. Detalhes: {e}", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro API Google: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    if not gspread_client: st.error("Cliente gspread não inicializado."); st.stop()
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨"); st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada em '{sheet_name}'.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨"); st.stop()

@st.cache_data
def load_fightcard_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip() 
        return df.dropna(subset=["Fighter", "FightOrder"]) # Remove lutas sem lutador ou ordem
    except Exception as e:
        st.error(f"Erro ao carregar dados do Fightcard: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        # Garante que colunas esperadas existam e tenham os tipos corretos
        expected_cols = ["#", ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE, "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected_cols:
            if col not in df_att.columns: df_att[col] = None 
        
        # Converte colunas chave para string e remove espaços para consistência nas comparações
        if ID_COLUMN_IN_ATTENDANCE in df_att.columns:
            df_att[ID_COLUMN_IN_ATTENDANCE] = df_att[ID_COLUMN_IN_ATTENDANCE].astype(str).str.strip()
        if NAME_COLUMN_IN_ATTENDANCE in df_att.columns:
            df_att[NAME_COLUMN_IN_ATTENDANCE] = df_att[NAME_COLUMN_IN_ATTENDANCE].astype(str).str.strip()
        if "Task" in df_att.columns:
            df_att["Task"] = df_att["Task"].astype(str).str.strip()
        if "Status" in df_att.columns:
            df_att["Status"] = df_att["Status"].astype(str).str.strip()
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
        if not data or len(data) < 1: return [], [] # Retorna tupla vazia
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        # statuses = df_conf["TaskStatus"].dropna().astype(str).str.strip().unique().tolist() if "TaskStatus" in df_conf.columns else []
        return tasks, [] # Só precisamos da task_list para este dashboard
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba Config: {e}")
        return [], []

def get_task_status_for_athlete(athlete_identifier, task_name, df_attendance, 
                                id_col_att, name_col_att, is_identifier_id=False):
    if df_attendance.empty or not task_name or not athlete_identifier:
        return "Pendente" # Default se não houver dados para checar

    col_to_match = id_col_att if is_identifier_id else name_col_att
    
    # Assegura que a coluna de match exista no df_attendance
    if col_to_match not in df_attendance.columns:
        # st.warning(f"Coluna '{col_to_match}' não encontrada em Attendance para buscar status do atleta.")
        return "Pendente"
        
    relevant_records = df_attendance[
        (df_attendance[col_to_match].astype(str).str.upper() == str(athlete_identifier).upper()) &
        (df_attendance["Task"].astype(str) == task_name)
    ]

    if relevant_records.empty:
        return "Pendente"

    if "Timestamp" in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted.loc[:, "Timestamp_dt"] = pd.to_datetime(
                relevant_records_sorted["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce'
            )
            relevant_records_sorted.dropna(subset=["Timestamp_dt"], inplace=True)
            if not relevant_records_sorted.empty:
                return relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False).iloc[0]["Status"]
        except Exception: # Se ordenação falhar, usa o último pela ordem original
            return relevant_records.iloc[-1]["Status"] 
    
    return relevant_records.iloc[-1]["Status"] # Fallback se não houver timestamp

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
            
            b_info_geral = html.escape(str(blue.get("Nationality", ""))) if isinstance(blue,pd.Series) else "" 
            r_info_geral = html.escape(str(red.get("Nationality", ""))) if isinstance(red,pd.Series) else ""   

            b_img = f"<img src='{html.escape(str(blue.get('Picture','')),True)}' class='fighter-img'>" if isinstance(blue,pd.Series)and blue.get("Picture")and isinstance(blue.get("Picture"),str)and blue.get("Picture").startswith("http")else"<div class='fighter-img' style='background-color:#222; display:inline-block;'></div>"
            r_img = f"<img src='{html.escape(str(red.get('Picture','')),True)}' class='fighter-img'>" if isinstance(red,pd.Series)and red.get("Picture")and isinstance(red.get("Picture"),str)and red.get("Picture").startswith("http")else"<div class='fighter-img' style='background-color:#222; display:inline-block;'></div>"
            
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
            </tr>
            """
        html_str += "</tbody></table>"
    return html_str

def calculate_height(df_fightcard, base_event_h=80, fight_h_estimate=150, header_footer_h=200):
    num_events = df_fightcard["Event"].nunique() if not df_fightcard.empty else 0
    num_fights = len(df_fightcard.groupby(["Event", "FightOrder"])) if not df_fightcard.empty else 0
    total_h = (num_events * base_event_h) + (num_fights * fight_h_estimate) + header_footer_h
    return max(total_h, 800) 

# --- Configuração da Página Streamlit ---
st.markdown("<h1 style='text-align:center; color:white;'>DASHBOARD DE ATLETAS</h1>", unsafe_allow_html=True)
local_css("style.css") 

# --- Carregamento de Todos os Dados ---
df_fc_data = None
df_att_data = None
task_list_data = []

with st.spinner("Carregando dados... Aguarde!"):
    df_fc_data = load_fightcard_data() 
    df_att_data = load_attendance_data() 
    task_list_data, _ = load_config_data() 

# --- Botão de Atualizar ---
if st.button("🔄 Atualizar Todos os Dados", key="refresh_dashboard_all"):
    load_fightcard_data.clear()
    load_attendance_data.clear()
    load_config_data.clear()
    st.toast("Dados atualizados! Recarregando...", icon="🎉")
    st.rerun()

# --- Renderização ---
if df_fc_data is None or df_fc_data.empty:
    st.warning("Nenhum dado de Fightcard para exibir. Verifique a fonte de dados ou aguarde o carregamento.")
elif not task_list_data:
    st.error("TaskList não carregada da Configuração. Não é possível exibir o status das tarefas.")
else:
    if df_att_data is None or df_att_data.empty:
        st.info("Dados de presença não encontrados ou vazios. Status das tarefas podem aparecer como 'Pendente'.")
        df_att_data = pd.DataFrame() # Garante que é um DataFrame vazio para a função de renderização
    
    dashboard_html_output = render_dashboard_html_content(
        df_fc_data, 
        df_att_data, 
        task_list_data, 
        ID_COLUMN_IN_ATTENDANCE, 
        NAME_COLUMN_IN_ATTENDANCE 
    )
    page_height = calculate_height(df_fc_data)
    st.components.v1.html(dashboard_html_output, height=page_height, scrolling=True)
