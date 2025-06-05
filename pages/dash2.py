# pages/DashboardAtletas.py

import streamlit as st
import pandas as pd
import numpy as np 
import altair as alt 
from datetime import datetime 

# Importações para Google Sheets
import gspread
from google.oauth2.service_account import Credentials # GARANTIDO QUE ESTÁ AQUI

# --- Configuração da Página (geralmente no MainApp.py para apps multipágina) ---
# Se este for seu app principal ou você quiser configurar por página:
# if 'page_config_set_dashboard_atletas' not in st.session_state:
#     st.set_page_config(layout="wide", page_title="Dashboard de Atletas")
#     st.session_state.page_config_set_dashboard_atletas = True

# --- Constantes ---
MAIN_SHEET_NAME = "UAEW_App" 
ATHLETES_TAB_NAME = "df" 
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"
ID_COLUMN_IN_ATTENDANCE = "Athlete ID" 
NAME_COLUMN_IN_ATTENDANCE = "Fighter"
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]

# --- Funções de Conexão e Carregamento de Dados ---
@st.cache_resource(ttl=3600)
def get_gspread_client():
    # SUBSTITUA PELO SEU CÓDIGO REAL OU IMPORTE DE UTILS
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        # USA Credentials AQUI
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except KeyError: 
        st.error("Erro config: Chave GCP `gcp_service_account` ausente.", icon="🚨"); st.stop()
    except Exception as e:
        st.error(f"Erro API Google/gspread auth: {e}", icon="🚨"); st.stop()

def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    # SUBSTITUA PELO SEU CÓDIGO REAL OU IMPORTE DE UTILS
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
def load_athlete_main_data(sheet_name=MAIN_SHEET_NAME, athletes_tab=ATHLETES_TAB_NAME):
    # SUBSTITUA PELO SEU CÓDIGO REAL OU IMPORTE DE UTILS
    g_client = get_gspread_client()
    ws = connect_gsheet_tab(g_client, sheet_name, athletes_tab)
    try:
        df_ath = pd.DataFrame(ws.get_all_records())
        if df_ath.empty: return pd.DataFrame()
        if "INACTIVE" in df_ath.columns:
            if df_ath["INACTIVE"].dtype == 'object':
                 df_ath["INACTIVE"] = df_ath["INACTIVE"].astype(str).str.upper().map({'FALSE': False, 'TRUE': True, '': True}).fillna(True)
            elif pd.api.types.is_numeric_dtype(df_ath["INACTIVE"]):
                 df_ath["INACTIVE"] = df_ath["INACTIVE"].map({0: False, 1: True}).fillna(True)
        else: df_ath["INACTIVE"] = False
        return df_ath
    except Exception as e: st.error(f"Erro ao carregar dados principais dos atletas: {e}"); return pd.DataFrame()

@st.cache_data
def load_fightcard_data_db():
    # SUBSTITUA PELO SEU CÓDIGO REAL OU IMPORTE DE UTILS
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    try:
        df = pd.read_csv(url); df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip()
        return df.dropna(subset=["Fighter", "FightOrder"])
    except Exception as e: st.error(f"Erro Fightcard: {e}"); return pd.DataFrame()

@st.cache_data(ttl=120)
def load_attendance_data_db(sheet_name=MAIN_SHEET_NAME, att_tab=ATTENDANCE_TAB_NAME):
    # SUBSTITUA PELO SEU CÓDIGO REAL OU IMPORTE DE UTILS
    g_client = get_gspread_client()
    ws = connect_gsheet_tab(g_client, sheet_name, att_tab)
    try:
        df_att = pd.DataFrame(ws.get_all_records())
        if df_att.empty: return pd.DataFrame()
        cols_to_str = [ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE, "Task", "Status"]
        for col in cols_to_str:
            if col in df_att.columns: df_att[col] = df_att[col].astype(str).str.strip()
        return df_att
    except Exception as e: st.error(f"Erro Attendance: {e}"); return pd.DataFrame()

@st.cache_data(ttl=600)
def load_config_data_db(sheet_name=MAIN_SHEET_NAME, conf_tab=CONFIG_TAB_NAME):
    # SUBSTITUA PELO SEU CÓDIGO REAL OU IMPORTE DE UTILS
    g_client = get_gspread_client()
    ws = connect_gsheet_tab(g_client, sheet_name, conf_tab)
    try:
        data = ws.get_all_values()
        if not data or len(data) < 1: return [], []
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        statuses = df_conf["TaskStatus"].dropna().astype(str).str.strip().unique().tolist() if "TaskStatus" in df_conf.columns else []
        return tasks, statuses
    except Exception as e: st.error(f"Erro Config: {e}"); return [], []


# --- Título e Cabeçalho da Página ---
st.title("Dashboard de Atletas e Eventos")
st.markdown("---")

# --- Carregamento de Dados para o Dashboard ---
# Inicializa para evitar NameError se alguma carga falhar antes da atribuição
df_athletes_main = pd.DataFrame()
df_fightcard = pd.DataFrame()
df_attendance = pd.DataFrame()
task_list = []
status_list_config = [] # Não usado diretamente nos gráficos atuais, mas carregado

with st.spinner("Carregando dados..."):
    df_athletes_main = load_athlete_main_data() 
    df_fightcard = load_fightcard_data_db()
    df_attendance = load_attendance_data_db()
    task_list, status_list_config = load_config_data_db()

# --- Cálculos para as Métricas ---
num_total_athletes = len(df_athletes_main)
num_active_athletes = len(df_athletes_main[df_athletes_main["INACTIVE"] == False]) if "INACTIVE" in df_athletes_main.columns else num_total_athletes
num_events = df_fightcard["Event"].nunique() if not df_fightcard.empty else 0
total_tasks_recorded = len(df_attendance)
done_tasks_recorded = len(df_attendance[df_attendance["Status"] == "Done"]) if "Status" in df_attendance.columns and not df_attendance.empty else 0
perc_done_tasks = (done_tasks_recorded / total_tasks_recorded * 100) if total_tasks_recorded > 0 else 0

# --- Exibição das Métricas ---
st.subheader("Visão Geral")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Atletas Registrados", num_total_athletes)
col2.metric("Atletas Ativos", num_active_athletes)
col3.metric("Eventos no Fightcard", num_events)
col4.metric("Tarefas Concluídas", f"{perc_done_tasks:.1f}%", help=f"{done_tasks_recorded} de {total_tasks_recorded} tarefas.")

st.markdown("---")

# --- Tabela de Lutas do Fightcard ---
st.subheader("Lutas Agendadas")
if not df_fightcard.empty:
    fights_display_list = []
    for order, group in df_fightcard.sort_values(by=["Event", "FightOrder"]).groupby(["Event", "FightOrder"]):
        event, fight_order = order
        blue = group[group["Corner"] == "blue"].squeeze(axis=0)
        red = group[group["Corner"] == "red"].squeeze(axis=0)
        fight_entry = {
            "Evento": event,
            "Luta #": int(fight_order) if pd.notna(fight_order) else "",
            "Canto Azul": blue.get("Fighter", "N/A") if isinstance(blue, pd.Series) else "N/A",
            "Canto Vermelho": red.get("Fighter", "N/A") if isinstance(red, pd.Series) else "N/A",
            "Divisão": blue.get("Division", red.get("Division", "N/A")) if isinstance(blue, pd.Series) else (red.get("Division", "N/A") if isinstance(red, pd.Series) else "N/A")
        }
        fights_display_list.append(fight_entry)
    if fights_display_list:
        df_fights_display = pd.DataFrame(fights_display_list)
        st.dataframe(df_fights_display, use_container_width=True, hide_index=True)
    else: st.info("Nenhuma luta formatada para exibir.")
else: st.info("Nenhum dado de fightcard para exibir tabela de lutas.")

st.markdown("---")

# --- Status Geral das Tarefas ---
st.subheader("Status Agregado das Tarefas")
if not df_attendance.empty and "Status" in df_attendance.columns and "Task" in df_attendance.columns:
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("##### Contagem por Status")
        status_counts = df_attendance["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Contagem"]
        status_colors_domain = ['Done', 'Requested', 'Pendente', '---'] + [s for s in status_counts["Status"].unique() if s not in ['Done', 'Requested', 'Pendente', '---']]
        status_colors_range = ['#2ECC71', '#F1C40F', '#7F8C8D', '#A6E22E'] + ['#A9A9A9'] * (len(status_counts["Status"].unique()) - 4)
        
        chart_status_agg = alt.Chart(status_counts).mark_bar().encode(
            x=alt.X('Status:N', sort='-y', title='Status'),
            y=alt.Y('Contagem:Q', title='Nº de Registros'),
            color=alt.Color('Status:N', scale=alt.Scale(domain=status_colors_domain, range=status_colors_range), legend=None),
            tooltip=['Status', 'Contagem']
        ).properties(height=350) # Aumentado altura
        st.altair_chart(chart_status_agg, use_container_width=True)

    with col_chart2:
        st.markdown("##### Distribuição por Tipo de Tarefa")
        task_type_counts = df_attendance["Task"].value_counts().reset_index()
        task_type_counts.columns = ["Tarefa", "Contagem"]
        chart_task_type = alt.Chart(task_type_counts).mark_arc(innerRadius=60, outerRadius=100).encode( # Ajustado raio
            theta=alt.Theta(field="Contagem", type="quantitative"),
            color=alt.Color(field="Tarefa", type="nominal", legend=alt.Legend(title="Tipo de Tarefa", orient="right")), # Legenda à direita
            tooltip=['Tarefa', 'Contagem']
        ).properties(height=350) # Aumentado altura
        st.altair_chart(chart_task_type, use_container_width=True)
else:
    st.info("Sem dados de presença para gerar gráficos de status de tarefas.")

st.markdown("---")
st.caption(f"Dashboard de Atletas - Dados atualizados em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
