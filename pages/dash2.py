# pages/Dashboard.py

import streamlit as st
import pandas as pd
import gspread 
from google.oauth2.service_account import Credentials 
from datetime import datetime
import html 
import os 

# --- 1. Page Configuration ---
# Definido no MainApp.py para apps multipágina

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App" 
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID" 
NAME_COLUMN_IN_ATTENDANCE = "Fighter"  
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]

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

# --- Funções de Conexão e Carregamento de Dados (SUBSTITUA PELAS SUAS REAIS) ---
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
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    try:
        df = pd.read_csv(url)
        if df.empty: return pd.DataFrame()
        df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip() 
        df["Picture"] = df["Picture"].astype(str).str.strip() 
        return df.dropna(subset=["Fighter", "FightOrder"])
    except Exception as e:
        st.error(f"Erro ao carregar dados do Fightcard: {e}"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME):
    gspread_client = get_gspread_client()
    worksheet = connect_gsheet_tab(gspread_client, sheet_name, attendance_tab_name)
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        if df_att.empty: return pd.DataFrame()
        # Colunas esperadas na aba Attendance
        expected_cols = ["#", ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE, "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected_cols:
            if col not in df_att.columns: df_att[col] = None 
        # Garante que colunas chave são string e sem espaços extras
        if ID_COLUMN_IN_ATTENDANCE in df_att.columns: df_att[ID_COLUMN_IN_ATTENDANCE] = df_att[ID_COLUMN_IN_ATTENDANCE].astype(str).str.strip()
        if NAME_COLUMN_IN_ATTENDANCE in df_att.columns: df_att[NAME_COLUMN_IN_ATTENDANCE] = df_att[NAME_COLUMN_IN_ATTENDANCE].astype(str).str.strip()
        if "Task" in df_att.columns: df_att["Task"] = df_att["Task"].astype(str).str.strip()
        if "Status" in df_att.columns: df_att["Status"] = df_att["Status"].astype(str).str.strip()
        return df_att
    except Exception as e:
        st.error(f"Erro ao carregar dados da Attendance: {e}"); return pd.DataFrame()

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
        st.error(f"Erro ao carregar dados da Config: {e}"); return [], []

def get_task_status_for_athlete(athlete_name, task_name, df_attendance, name_col_att_in_attendance):
    if df_attendance.empty or not task_name or pd.isna(athlete_name) or str(athlete_name).strip() == "":
        return "Pendente"
    if name_col_att_in_attendance not in df_attendance.columns: return "Pendente"
        
    athlete_name_str = str(athlete_name).strip().upper()
    task_name_str = str(task_name).strip()
    relevant_records = df_attendance[
        (df_attendance[name_col_att_in_attendance].astype(str).str.strip().str.upper() == athlete_name_str) &
        (df_attendance["Task"].astype(str).str.strip() == task_name_str)
    ]
    if relevant_records.empty: return "Pendente"
    if "Timestamp" in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted.loc[:, "Timestamp_dt"] = pd.to_datetime(
                relevant_records_sorted["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce'
            )
            if relevant_records_sorted["Timestamp_dt"].notna().any():
                 latest_record = relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False, na_position='last').iloc[0]
                 return latest_record["Status"]
            else: return relevant_records.iloc[-1]["Status"]
        except Exception: return relevant_records.iloc[-1]["Status"] 
    return relevant_records.iloc[-1]["Status"]

def render_fight_table_html(df_fc, df_att, tasks_all, name_col_in_att):
    html_content = ""
    grouped_events = df_fc.groupby("Event", sort=False)
    colspan_val = 7 + 2 * len(tasks_all) # Foto, Nome, Tarefas, Detalhes, Tarefas, Nome, Foto

    for ev_name, ev_group in grouped_events:
        html_content += f"<table><tr><td colspan='{colspan_val}' class='event-header-cell'>{html.escape(str(ev_name))}</td></tr></table>"
        html_content += "<table class='dashboard-fight-table'>"
        header_html = "<thead><tr><th>Foto</th><th>Lutador Azul</th>"
        for task in tasks_all: header_html += f"<th>{html.escape(task)}</th>"
        header_html += "<th>Detalhes</th>"
        for task in tasks_all: header_html += f"<th>{html.escape(task)}</th>"
        header_html += "<th>Lutador Vermelho</th><th>Foto</th></tr></thead><tbody>"
        html_content += header_html

        fights = ev_group.sort_values(by="FightOrder").groupby("FightOrder")
        for f_order, f_df in fights:
            blue = f_df[f_df["Corner"] == "blue"].squeeze(axis=0)
            red = f_df[f_df["Corner"] == "red"].squeeze(axis=0)
            b_name = html.escape(str(blue.get("Fighter", ""))) if isinstance(blue, pd.Series) else ""
            r_name = html.escape(str(red.get("Fighter", ""))) if isinstance(red, pd.Series) else ""
            b_img_src = blue.get('Picture', '') if isinstance(blue, pd.Series) else ''
            r_img_src = red.get('Picture', '') if isinstance(red, pd.Series) else ''
            b_img_tag = f"<img src='{html.escape(str(b_img_src))}' class='fighter-img'>" if b_img_src and isinstance(b_img_src, str) and b_img_src.startswith("http") else "<div class='fighter-img' style='background-color:#333;'></div>"
            r_img_tag = f"<img src='{html.escape(str(r_img_src))}' class='fighter-img'>" if r_img_src and isinstance(r_img_src, str) and r_img_src.startswith("http") else "<div class='fighter-img' style='background-color:#333;'></div>"

            html_content += "<tr>"
            html_content += f"<td class='fighter-img-cell'>{b_img_tag}</td>"
            html_content += f"<td class='fighter-name-cell blue-corner-bg-text'>{b_name}</td>"
            if b_name:
                for task_item in tasks_all:
                    status_val = get_task_status_for_athlete(b_name, task_item, df_att, name_col_in_att)
                    status_class = "status-pending"
                    if status_val == "Done": status_class = "status-done"
                    elif status_val == "Requested": status_class = "status-requested"
                    elif status_val in ["---", "Não Solicitado"]: status_class = "status-not-requested"
                    html_content += f"<td class='task-status-cell {status_class}'>{html.escape(status_val)}</td>"
            else:
                for _ in tasks_all: html_content += "<td class='task-status-cell status-pending'>N/A</td>"
            
            div_val = html.escape(str(blue.get("Division", "") if isinstance(blue, pd.Series) else (red.get("Division", "") if isinstance(red, pd.Series) else "")))
            fight_order_display = int(f_order) if pd.notna(f_order) else ""
            html_content += f"<td class='fight-details-cell'>FIGHT #{fight_order_display}<br>{div_val}</td>"

            if r_name:
                for task_item in tasks_all:
                    status_val = get_task_status_for_athlete(r_name, task_item, df_att, name_col_in_att)
                    status_class = "status-pending"
                    if status_val == "Done": status_class = "status-done"
                    elif status_val == "Requested": status_class = "status-requested"
                    elif status_val in ["---", "Não Solicitado"]: status_class = "status-not-requested"
                    html_content += f"<td class='task-status-cell {status_class}'>{html.escape(status_val)}</td>"
            else:
                for _ in tasks_all: html_content += "<td class='task-status-cell status-pending'>N/A</td>"
            html_content += f"<td class='fighter-name-cell red-corner-bg-text'>{r_name}</td>"
            html_content += f"<td class='fighter-img-cell'>{r_img_tag}</td>"
            html_content += "</tr>"
        html_content += "</tbody></table>"
    return html_content

def calculate_table_height(df_fightcard, tasks_all, base_event_h=60, fight_h_estimate=85, header_footer_h=100):
    num_events = df_fightcard["Event"].nunique() if not df_fightcard.empty else 0
    num_fights = len(df_fightcard.drop_duplicates(subset=["Event", "FightOrder"])) if not df_fightcard.empty else 0
    total_h = (num_events * base_event_h) + (num_fights * fight_h_estimate) + header_footer_h
    return max(total_h, 600) 

# --- Página Streamlit ---
st.markdown("<h1 style='text-align:center; color:white; margin-bottom:10px;'>DASHBOARD DE ATLETAS</h1>", unsafe_allow_html=True)
local_css("style.css") 

df_fc_data = None; df_att_data = None; task_list_data = []
loading_error = False

with st.spinner("Carregando todos os dados... Aguarde!"):
    try:
        df_fc_data = load_fightcard_data() 
        df_att_data = load_attendance_data() 
        task_list_data, _ = load_config_data() 
        
        if df_fc_data is None or df_fc_data.empty: loading_error = True
        if not task_list_data: loading_error = True
            
    except Exception as e: 
        st.error(f"Erro crítico durante o carregamento inicial dos dados: {e}")
        loading_error = True

col_btn_refresh_main, _ = st.columns([0.25, 0.75]) 
with col_btn_refresh_main:
    if st.button("🔄 Atualizar Dados", key="refresh_dashboard_all_btn", use_container_width=True):
        load_fightcard_data.clear(); load_attendance_data.clear(); load_config_data.clear()
        st.toast("Dados atualizados!", icon="🎉"); st.rerun()
st.markdown("<hr style='margin-top: 5px; margin-bottom: 15px;'>", unsafe_allow_html=True)

# --- Renderização do Dashboard ---
if loading_error:
    st.error("Falha ao carregar dados essenciais. O dashboard não pode ser renderizado. Verifique as mensagens de erro acima ou os logs.")
elif df_fc_data.empty:
    st.warning("Nenhum dado de Fightcard carregado ou os dados estão vazios. Verifique a fonte de dados da aba 'Fightcard'.")
elif not task_list_data:
    st.error("A lista de tarefas (TaskList) não foi carregada da aba 'Config'. O dashboard não pode exibir o status das tarefas.")
else:
    # Se chegamos aqui, df_fc_data e task_list_data estão OK.
    # df_att_data pode estar vazio ou None, o que é tratado por get_task_status_for_athlete
    if df_att_data is None: 
        df_att_data = pd.DataFrame() 
        st.warning("Dados de presença (Attendance) não puderam ser carregados. Status podem estar incorretos.")
    elif df_att_data.empty:
        st.info("Dados de presença (Attendance) estão vazios. Status das tarefas aparecerão como 'Pendente'.")
    
    # Mensagem de sucesso apenas se tudo parece bem até agora
    # st.success("Dados carregados. Renderizando dashboard...") 
    
    dashboard_html_output = render_fight_table_html(df_fc_data, df_att_data, task_list_data, NAME_COLUMN_IN_ATTENDANCE)
    page_height = calculate_table_height(df_fc_data, task_list_data)
    st.components.v1.html(dashboard_html_output, height=page_height, scrolling=True)
