# dashboard_page.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime, timedelta 
import html 

# --- 1. Page Configuration ---
st.set_page_config(layout="wide", page_title="Dashboard de Atletas")

# --- Constants (COPIE AS SUAS CONSTANTES AQUI) ---
MAIN_SHEET_NAME = "UAEW_App" 
ATHLETES_TAB_NAME = "df" 
USERS_TAB_NAME = "Users" 
ATTENDANCE_TAB_NAME = "Attendance"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID" 
NAME_COLUMN_IN_ATTENDANCE = "Fighter" 
CONFIG_TAB_NAME = "Config"
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]
# NO_TASK_SELECTED_LABEL = "-- Selecione uma Tarefa --" # Removido, pois não há filtro de tarefa neste dashboard


# --- Função para Carregar CSS Externo ---
def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Arquivo CSS '{file_name}' não encontrado. Crie-o na mesma pasta do script.")

# --- Funções de Conexão e Carregamento de Dados (COPIE SUAS FUNÇÕES DEFINIDAS AQUI) ---
# Lembre-se de substituir as funções placeholder pelas suas reais
@st.cache_resource(ttl=3600)
def get_gspread_client_placeholder(): 
    if "gcp_service_account" not in st.secrets: st.error("`gcp_service_account` não encontrado."); return None
    try:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e: st.error(f"Falha gspread auth: {e}"); return None

def connect_gsheet_tab_placeholder(gspread_client, sheet_name, tab_name):
    if not gspread_client: return None
    try: return gspread_client.open(sheet_name).worksheet(tab_name)
    except Exception as e: st.error(f"Falha conexão {sheet_name}/{tab_name}: {e}"); return None

@st.cache_data
def load_fightcard_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    try:
        df = pd.read_csv(url); df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip()
        return df
    except Exception as e: st.error(f"Erro Fightcard: {e}"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data_placeholder(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client_placeholder()
    if not gspread_client: return pd.DataFrame()
    worksheet = connect_gsheet_tab_placeholder(gspread_client, sheet_name, attendance_tab_name)
    if not worksheet: return pd.DataFrame()
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        expected_cols = ["#", ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE, "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected_cols:
            if col not in df_att.columns: df_att[col] = None 
        if ID_COLUMN_IN_ATTENDANCE in df_att.columns: df_att[ID_COLUMN_IN_ATTENDANCE] = df_att[ID_COLUMN_IN_ATTENDANCE].astype(str).str.strip()
        if NAME_COLUMN_IN_ATTENDANCE in df_att.columns: df_att[NAME_COLUMN_IN_ATTENDANCE] = df_att[NAME_COLUMN_IN_ATTENDANCE].astype(str).str.strip()
        if "Task" in df_att.columns: df_att["Task"] = df_att["Task"].astype(str).str.strip()
        if "Status" in df_att.columns: df_att["Status"] = df_att["Status"].astype(str).str.strip()
        return df_att
    except Exception as e: st.error(f"Erro Attendance: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def load_config_data_placeholder(sheet_name=MAIN_SHEET_NAME, config_tab_name=CONFIG_TAB_NAME):
    gspread_client = get_gspread_client_placeholder()
    if not gspread_client: return [], []
    worksheet = connect_gsheet_tab_placeholder(gspread_client, sheet_name, config_tab_name)
    if not worksheet: return [], []
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return [], []
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        return tasks, [] 
    except Exception as e: st.error(f"Erro Config: {e}"); return [], []

def get_task_status_for_athlete(athlete_identifier, task_name, df_attendance, id_col_att, name_col_att, is_id=False):
    if df_attendance.empty or not task_name: return "Pendente"
    col_to_match = id_col_att if is_id else name_col_att
    rel_recs = df_attendance[(df_attendance[col_to_match].astype(str).str.upper()==str(athlete_identifier).upper())&(df_attendance["Task"].astype(str)==task_name)]
    if rel_recs.empty: return "Pendente"
    if "Timestamp" in rel_recs.columns:
        try:
            rel_recs_s = rel_recs.copy(); rel_recs_s["TS_dt"]=pd.to_datetime(rel_recs_s["Timestamp"],format="%d/%m/%Y %H:%M:%S",errors='coerce')
            rel_recs_s.dropna(subset=["TS_dt"],inplace=True)
            if not rel_recs_s.empty: return rel_recs_s.sort_values(by="TS_dt",ascending=False).iloc[0]["Status"]
        except: return rel_recs.iloc[-1]["Status"]
    return rel_recs.iloc[-1]["Status"]

def render_dashboard_html_content(df_fc, df_att, tasks_all, id_ca, name_ca):
    html_str = "" # O CSS será injetado por local_css()
    grouped = df_fc.groupby("Event", sort=False)
    for ev_name, ev_group in grouped:
        html_str += f"<div class='event-header'>{html.escape(str(ev_name))}</div>"
        html_str += "<table class='fightcard-table'><thead><tr><th style='width:40%;'>Blue Corner & Tasks</th><th style='width:20%; text-align:center;'>Fight Details</th><th style='width:40%;'>Red Corner & Tasks</th></tr></thead><tbody>"
        fights = ev_group.sort_values(by="FightOrder").groupby("FightOrder")
        for f_order, f_df in fights:
            blue = f_df[f_df["Corner"]=="blue"].squeeze(); red = f_df[f_df["Corner"]=="red"].squeeze()
            b_name = html.escape(str(blue.get("Fighter",""))) if isinstance(blue,pd.Series) else ""
            r_name = html.escape(str(red.get("Fighter",""))) if isinstance(red,pd.Series) else ""
            b_img = f"<img src='{html.escape(str(blue.get('Picture','')),True)}' class='fightcard-img'>" if isinstance(blue,pd.Series)and blue.get("Picture")and isinstance(blue.get("Picture"),str)and blue.get("Picture").startswith("http")else"<div class='fightcard-img' style='background-color:#222;'></div>"
            r_img = f"<img src='{html.escape(str(red.get('Picture','')),True)}' class='fightcard-img'>" if isinstance(red,pd.Series)and red.get("Picture")and isinstance(red.get("Picture"),str)and red.get("Picture").startswith("http")else"<div class='fightcard-img' style='background-color:#222;'></div>"
            
            b_tasks_h = "<ul class='task-status-list'>"
            if b_name:
                for task_i in tasks_all:
                    stat_v = get_task_status_for_athlete(b_name,task_i,df_att,id_ca,name_ca,is_id=False)
                    stat_c = f"status-text status-{str(stat_v).lower().replace(' ','-').replace('/','-')}"
                    if stat_v in STATUS_PENDING_EQUIVALENTS: stat_c="status-text status-pending"
                    b_tasks_h += f"<li><span class='task-name'>{html.escape(task_i)}:</span> <span class='{stat_c}'>{html.escape(str(stat_v))}</span></li>"
            b_tasks_h += "</ul>"
            
            r_tasks_h = "<ul class='task-status-list'>"
            if r_name:
                for task_i in tasks_all:
                    stat_v = get_task_status_for_athlete(r_name,task_i,df_att,id_ca,name_ca,is_id=False)
                    stat_c = f"status-text status-{str(stat_v).lower().replace(' ','-').replace('/','-')}"
                    if stat_v in STATUS_PENDING_EQUIVALENTS: stat_c="status-text status-pending"
                    r_tasks_h += f"<li><span class='task-name'>{html.escape(task_i)}:</span> <span class='{stat_c}'>{html.escape(str(stat_v))}</span></li>"
            r_tasks_h += "</ul>"
            
            div_val = html.escape(str(blue.get("Division","")if isinstance(blue,pd.Series)else(red.get("Division","")if isinstance(red,pd.Series)else"")))
            f_info = f"FIGHT #{int(f_order)}<br>{div_val}"
            html_str += f"""<tr><td class='blue-corner-col'>{b_img}<span class='fighter-name'>{b_name}</span>{b_tasks_h if b_name else ""}</td><td class='middle-cell'>{f_info}</td><td class='red-corner-col'>{r_img}<span class='fighter-name'>{r_name}</span>{r_tasks_h if r_name else ""}</td></tr>"""
        html_str += "</tbody></table>"
    return html_str

# --- Configuração da Página Streamlit ---
st.markdown("<h1 style='text-align:center; color:white;'>DASHBOARD DE ATLETAS</h1>", unsafe_allow_html=True)
local_css("style.css") # Carrega o CSS do arquivo externo

# --- Carregamento de Todos os Dados ---
with st.spinner("Carregando dados do Fightcard..."): df_fc_data = load_fightcard_data()
with st.spinner("Carregando dados de Presença..."): df_att_data = load_attendance_data_placeholder() 
with st.spinner("Carregando Configurações de Tarefas..."): task_list_data, _ = load_config_data_placeholder() 

# --- Renderização ---
if df_fc_data.empty:
    st.warning("Nenhum dado de Fightcard para exibir.")
elif not task_list_data:
    st.error("TaskList não carregada. Não é possível exibir o status das tarefas.")
else:
    if df_att_data.empty:
        st.info("Dados de presença não encontrados ou vazios. Status das tarefas podem aparecer como 'Pendente'.")
    dashboard_html = render_dashboard_html_content(df_fc_data, df_att_data, task_list_data, ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE)
    st.components.v1.html(dashboard_html, height=6000, scrolling=True)
