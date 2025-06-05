# dashboard_page.py (ou como você chamar o novo arquivo .py)

import streamlit as st
import pandas as pd
import gspread # Necessário se não estiver no script de utils
from google.oauth2.service_account import Credentials # Necessário
from datetime import datetime, timedelta # datetime é usado, timedelta não neste esqueleto, mas pode ser útil
import html 

# --- 1. Page Configuration ---
st.set_page_config(layout="wide", page_title="Dashboard de Atletas")

# --- Constants ---
MAIN_SHEET_NAME = "UAEW_App" 
ATHLETES_TAB_NAME = "df" 
USERS_TAB_NAME = "Users" # Não usado diretamente neste dashboard, mas pode ser parte do seu get_gspread_client
ATTENDANCE_TAB_NAME = "Attendance"
CONFIG_TAB_NAME = "Config"
# !!! IMPORTANTE: AJUSTE ESTE NOME DE COLUNA SE NECESSÁRIO !!!
ID_COLUMN_IN_ATTENDANCE = "Athlete ID" # Nome da coluna de ID do atleta na sua aba Attendance. Se for "ID", mude aqui.
                                       # E também na lista expected_cols em load_attendance_data
NAME_COLUMN_IN_ATTENDANCE = "Fighter" # Nome da coluna do NOME do atleta na sua aba Attendance
STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]
NO_TASK_SELECTED_LABEL = "-- Selecione uma Tarefa --" # Se quiser filtro de tarefa no dashboard

# --- CSS Global para a Página ---
# Movido para fora da função de renderização para melhor organização
# Se o seu CSS for muito extenso, considere colocá-lo em um arquivo .css separado e carregá-lo.
PAGE_CSS = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700&display=swap');
        body, .main {
            background-color: #0e1117; /* Cor de fundo geral */
            color: white;
            font-family: 'Barlow Condensed', sans-serif;
        }
        .fightcard-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 50px;
            table-layout: fixed; /* Ajuda a controlar larguras das colunas */
        }
        .fightcard-table th, .fightcard-table td {
            padding: 10px; /* Reduzido um pouco */
            text-align: center;
            vertical-align: top; /* Alinha conteúdo ao topo da célula */
            font-size: 15px; /* Ajustado */
            color: white;
            border-bottom: 1px solid #444;
        }
        .fightcard-img {
            width: 80px; /* Reduzido um pouco */
            height: 80px;
            object-fit: cover;
            border-radius: 8px;
            margin-bottom: 5px; /* Espaço abaixo da imagem */
        }
        .blue-corner-col { /* Coluna inteira do Blue Corner */
            background-color: #0d2d51; /* Azul escuro */
        }
        .red-corner-col { /* Coluna inteira do Red Corner */
            background-color: #3b1214; /* Vermelho escuro */
        }
        .fighter-name {
            font-weight: bold;
            font-size: 1.1em; /* Um pouco maior */
            display: block; /* Para que o margin-bottom funcione */
            margin-bottom: 8px;
        }
        .middle-cell {
            background-color: #2f2f2f;
            font-weight: bold;
            font-size: 14px;
            vertical-align: middle; /* Detalhes da luta centralizados verticalmente */
        }
        .event-header {
            background-color: #111;
            color: white;
            font-weight: bold;
            text-align: center;
            font-size: 22px; /* Aumentado */
            padding: 15px; /* Aumentado */
            text-transform: uppercase;
        }
        .fightcard-table th { /* Cabeçalhos da tabela (Blue Corner, Fight Details, Red Corner) */
            background-color: #1c1c1c;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-size: 16px;
        }
        .task-status-list {
            list-style-type: none;
            padding-left: 0;
            font-size: 13px; /* Menor para caber mais tarefas */
            text-align: left;
            margin-top: 8px; /* Espaço acima da lista de tarefas */
        }
        .task-status-list li {
            margin-bottom: 3px; /* Menor espaçamento entre tarefas */
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dotted #555; /* Linha sutil entre tarefas */
            padding-bottom: 3px;
        }
        .task-status-list li:last-child {
            border-bottom: none; /* Remove a borda do último item */
        }
        .task-name {
            font-weight: normal;
            color: #b0bec5; /* Cinza azulado claro */
            margin-right: 10px; /* Espaço entre nome da tarefa e status */
        }
        .status-text { /* Classe genérica para o texto do status */
            font-weight: bold;
            text-align: right;
        }
        .status-done { color: #4CAF50; } /* Verde mais vibrante */
        .status-requested { color: #FFC107; } /* Amarelo âmbar */
        .status-pending { color: #9E9E9E; font-weight: normal; } /* Cinza */
        /* Adicione mais classes de status conforme necessário */
        /* .status-outro-status { color: #cor; } */

        @media screen and (max-width: 768px) {
            .fightcard-table td, .fightcard-table th {
                font-size: 12px; /* Ainda menor para mobile */
                padding: 6px;
            }
            .fightcard-img {
                width: 50px;
                height: 50px;
            }
            .event-header { font-size: 18px; padding: 10px; }
            .task-status-list { font-size: 11px; }
            .fighter-name { font-size: 1em; }
        }
    </style>
"""

# --- Funções de Conexão e Carregamento de Dados (COPIE SUAS FUNÇÕES DEFINIDAS AQUI) ---
# Se você tem um utils.py, use: from utils import get_gspread_client, ... etc.

@st.cache_resource(ttl=3600)
def get_gspread_client_placeholder(): # Substitua pelo seu get_gspread_client real
    # Esta é uma implementação placeholder para o script rodar sem erro de nome.
    # No seu ambiente, você terá as credenciais e a lógica real.
    if "gcp_service_account" not in st.secrets:
        st.error("`gcp_service_account` não encontrado nos segredos.")
        return None # Ou st.stop()
    try:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], 
                                                      scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Falha ao autorizar gspread: {e}")
        return None

def connect_gsheet_tab_placeholder(gspread_client, sheet_name, tab_name): # Substitua pela sua real
    if not gspread_client: return None
    try:
        spreadsheet = gspread_client.open(sheet_name)
        return spreadsheet.worksheet(tab_name)
    except Exception as e:
        st.error(f"Falha ao conectar à aba '{tab_name}' da planilha '{sheet_name}': {e}")
        return None

@st.cache_data
def load_fightcard_data():
    # Usando um link público direto para Fightcard como no seu exemplo
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
        df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
        df["Fighter"] = df["Fighter"].astype(str).str.strip() # Garante que Fighter é string e sem espaços extras
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados do Fightcard: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=120) # Cache menor para attendance, pois pode mudar mais frequentemente
def load_attendance_data_placeholder(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME): # Substitua pela sua real
    gspread_client = get_gspread_client_placeholder()
    if not gspread_client: return pd.DataFrame()
    worksheet = connect_gsheet_tab_placeholder(gspread_client, sheet_name, attendance_tab_name)
    if not worksheet: return pd.DataFrame()
    try:
        df_att = pd.DataFrame(worksheet.get_all_records())
        # Garante que colunas esperadas existam
        expected_cols = ["#", ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE, "Event", "Task", "Status", "Notes", "User", "Timestamp"]
        for col in expected_cols:
            if col not in df_att.columns:
                df_att[col] = None 
        # Garante tipos corretos para colunas chave usadas na lógica
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
def load_config_data_placeholder(sheet_name=MAIN_SHEET_NAME, config_tab_name=CONFIG_TAB_NAME): # Substitua pela sua real
    gspread_client = get_gspread_client_placeholder()
    if not gspread_client: return [], []
    worksheet = connect_gsheet_tab_placeholder(gspread_client, sheet_name, config_tab_name)
    if not worksheet: return [], []
    try:
        data = worksheet.get_all_values()
        if not data or len(data) < 1: return [], []
        df_conf = pd.DataFrame(data[1:], columns=data[0])
        tasks = df_conf["TaskList"].dropna().astype(str).str.strip().unique().tolist() if "TaskList" in df_conf.columns else []
        # statuses = df_conf["TaskStatus"].dropna().astype(str).str.strip().unique().tolist() if "TaskStatus" in df_conf.columns else [] # Não usado diretamente no dashboard
        return tasks, [] # Retorna apenas tasks por enquanto
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba Config: {e}")
        return [], []

# --- Função Auxiliar para obter status da tarefa ---
def get_task_status_for_athlete(athlete_identifier, task_name, df_attendance, 
                                id_col_in_attendance, name_col_in_attendance, 
                                is_identifier_id=False): # Novo parâmetro para saber se o identificador é ID
    """
    Busca o status mais recente de uma tarefa específica para um atleta.
    athlete_identifier pode ser nome ou ID.
    """
    if df_attendance.empty or not task_name:
        return "Pendente"

    # Filtra registros para o atleta e a tarefa
    if is_identifier_id:
        relevant_records = df_attendance[
            (df_attendance[id_col_in_attendance].astype(str).str.upper() == str(athlete_identifier).upper()) &
            (df_attendance["Task"].astype(str) == task_name)
        ]
    else: # identifier is name
        relevant_records = df_attendance[
            (df_attendance[name_col_in_attendance].astype(str).str.upper() == str(athlete_identifier).upper()) &
            (df_attendance["Task"].astype(str) == task_name)
        ]

    if relevant_records.empty:
        return "Pendente"

    if "Timestamp" in relevant_records.columns:
        try:
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted["Timestamp_dt"] = pd.to_datetime(
                relevant_records_sorted["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce'
            )
            relevant_records_sorted.dropna(subset=["Timestamp_dt"], inplace=True)
            if not relevant_records_sorted.empty:
                return relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False).iloc[0]["Status"]
        except Exception:
            return relevant_records.iloc[-1]["Status"] # Fallback
    
    return relevant_records.iloc[-1]["Status"]

# --- Função Principal de Renderização do Dashboard ---
def render_dashboard_html_content(df_fightcard, df_attendance, task_list_all, 
                                  id_col_att, name_col_att):
    
    html_string = PAGE_CSS # Adiciona o CSS no início

    grouped_events = df_fightcard.groupby("Event", sort=False) # sort=False para manter ordem da planilha

    for event_name, event_group in grouped_events:
        html_string += f"<div class='event-header'>{html.escape(str(event_name))}</div>"
        html_string += "<table class='fightcard-table'><thead><tr>"
        html_string += "<th style='width:50%;'>Blue Corner & Tasks</th>" # Uma célula larga para cada lutador
        html_string += "<th style='width:0%; display:none;'></th>" # Coluna do meio oculta ou muito fina
        html_string += "<th style='width:50%;'>Red Corner & Tasks</th>"
        html_string += "</tr></thead><tbody>"

        # Ordenar lutas dentro do evento
        fights_in_event = event_group.sort_values(by="FightOrder").groupby("FightOrder")

        for fight_order, fight_df in fights_in_event:
            blue_s = fight_df[fight_df["Corner"] == "blue"].squeeze()
            red_s = fight_df[fight_df["Corner"] == "red"].squeeze()

            blue_name_val = html.escape(str(blue_s.get("Fighter", ""))) if isinstance(blue_s, pd.Series) else ""
            red_name_val = html.escape(str(red_s.get("Fighter", ""))) if isinstance(red_s, pd.Series) else ""
            
            blue_img_tag = f"<img src='{html.escape(str(blue_s.get('Picture', '')),True)}' class='fightcard-img'>" if isinstance(blue_s, pd.Series) and blue_s.get("Picture") and isinstance(blue_s.get("Picture"), str) and blue_s.get("Picture").startswith("http") else "<div class='fightcard-img' style='background-color:#222;'></div>"
            red_img_tag = f"<img src='{html.escape(str(red_s.get('Picture', '')),True)}' class='fightcard-img'>" if isinstance(red_s, pd.Series) and red_s.get("Picture") and isinstance(red_s.get("Picture"), str) and red_s.get("Picture").startswith("http") else "<div class='fightcard-img' style='background-color:#222;'></div>"
            
            # Supondo que você tem um ID de atleta no df_fightcard, se não, usará o nome.
            # blue_id_val = blue_s.get("AthleteID_from_df_sheet", None) # Exemplo
            # red_id_val = red_s.get("AthleteID_from_df_sheet", None)   # Exemplo

            blue_tasks_disp = "<ul class='task-status-list'>"
            if blue_name_val:
                for task_item in task_list_all:
                    # Se tiver ID, use-o, senão use o nome. Ajuste is_identifier_id=True se passar ID.
                    # status_val = get_task_status_for_athlete(blue_id_val if blue_id_val else blue_name_val, task_item, df_attendance, id_col_att, name_col_att, is_identifier_id=(blue_id_val is not None))
                    status_val = get_task_status_for_athlete(blue_name_val, task_item, df_attendance, id_col_att, name_col_att, is_identifier_id=False) # Usando nome por enquanto
                    
                    status_cls = f"status-text status-{str(status_val).lower().replace(' ', '-').replace('/','-')}"
                    if status_val in STATUS_PENDING_EQUIVALENTS: status_cls = "status-text status-pending"
                    blue_tasks_disp += f"<li><span class='task-name'>{html.escape(task_item)}:</span> <span class='{status_cls}'>{html.escape(str(status_val))}</span></li>"
            blue_tasks_disp += "</ul>"

            red_tasks_disp = "<ul class='task-status-list'>"
            if red_name_val:
                for task_item in task_list_all:
                    # status_val = get_task_status_for_athlete(red_id_val if red_id_val else red_name_val, task_item, df_attendance, id_col_att, name_col_att, is_identifier_id=(red_id_val is not None))
                    status_val = get_task_status_for_athlete(red_name_val, task_item, df_attendance, id_col_att, name_col_att, is_identifier_id=False) # Usando nome

                    status_cls = f"status-text status-{str(status_val).lower().replace(' ', '-').replace('/','-')}"
                    if status_val in STATUS_PENDING_EQUIVALENTS: status_cls = "status-text status-pending"
                    red_tasks_disp += f"<li><span class='task-name'>{html.escape(task_item)}:</span> <span class='{status_cls}'>{html.escape(str(status_val))}</span></li>"
            red_tasks_disp += "</ul>"
            
            division_val = html.escape(str(blue_s.get("Division", "") if isinstance(blue_s, pd.Series) else (red_s.get("Division", "") if isinstance(red_s, pd.Series) else "")))
            fight_info_val = f"FIGHT #{int(fight_order)}<br>{division_val}"

            # Estrutura com 2 colunas principais para os lutadores e uma central fina/oculta para os detalhes
            html_string += f"""
            <tr>
                <td class='blue-corner-col'>
                    {blue_img_tag}
                    <span class='fighter-name'>{blue_name_val}</span>
                    {blue_tasks_disp if blue_name_val else ""}
                </td>
                <td class='middle-cell' style="width:180px; max-width:180px; min-width:150px; font-size:13px; white-space:normal;">{fight_info_val}</td> {/* Coluna do meio com largura fixa */}
                <td class='red-corner-col'>
                    {red_img_tag}
                    <span class='fighter-name'>{red_name_val}</span>
                    {red_tasks_disp if red_name_val else ""}
                </td>
            </tr>
            """
        html_string += "</tbody></table>"
    return html_string

# --- Configuração da Página Streamlit ---
st.markdown("<h1 style='text-align:center; color:white;'>DASHBOARD DE ATLETAS</h1>", unsafe_allow_html=True)

# --- Carregamento de Todos os Dados ---
df_fc = load_fightcard_data()
df_att = load_attendance_data_placeholder() 
tasks, _ = load_config_data_placeholder() 

# --- Renderização ---
if df_fc.empty:
    st.warning("Nenhum dado de Fightcard para exibir.")
elif not tasks:
    st.error("TaskList não carregada. Não é possível exibir o status das tarefas.")
else:
    # Se df_att estiver vazio, get_task_status_for_athlete retornará "Pendente"
    dashboard_html_output = render_dashboard_html_content(df_fc, df_att, tasks, ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE)
    st.components.v1.html(dashboard_html_output, height=6000, scrolling=True)
