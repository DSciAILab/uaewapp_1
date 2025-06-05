# dashboard_page.py (ou como você chamar o novo arquivo .py)

import streamlit as st
import pandas as pd
import gspread # (Necessário se não estiver no script de utils)
from google.oauth2.service_account import Credentials # (Necessário)
from datetime import datetime # (Necessário)
import html # (Necessário)

# --- Constantes (adapte dos seus outros scripts) ---
# MAIN_SHEET_NAME = "UAEW_App"
# ATHLETES_TAB_NAME = "df" # Para dados detalhados dos atletas se necessário além do Fightcard
# ATTENDANCE_TAB_NAME = "Attendance"
# CONFIG_TAB_NAME = "Config"
# ID_COLUMN_IN_ATTENDANCE = "Athlete ID" # ou "ID"
# STATUS_PENDING_EQUIVALENTS = ["Pendente", "---", "Não Registrado"]

# --- Funções de Conexão e Carregamento de Dados (adapte/importe dos seus outros scripts) ---
# @st.cache_resource
# def get_gspread_client(): ...
# def connect_gsheet_tab(...): ...

# @st.cache_data
# def load_athlete_details_data(): # Carrega da aba 'df' se precisar de mais detalhes que o Fightcard não tem
#     # ... similar ao load_athlete_data() anterior, mas focado nos detalhes que podem faltar no fightcard
#     pass

# @st.cache_data
# def load_attendance_data(): # Carrega da aba 'Attendance'
#     # ... como no script anterior ...
#     pass

# @st.cache_data
# def load_config_data(): # Carrega TaskList da aba 'Config'
#     # ... como no script anterior, retornando (task_list, task_status_list) ...
#     pass

@st.cache_data
def load_fightcard_data(): # A função que você já tem
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=Fightcard"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    df["Corner"] = df["Corner"].str.strip().str.lower()
    return df

# --- Função Auxiliar para obter status da tarefa ---
def get_task_status_for_athlete(athlete_name_or_id, task_name, df_attendance, id_col_attendance, name_col_attendance="Name"):
    """
    Busca o status mais recente de uma tarefa específica para um atleta.
    Assume que df_attendance tem colunas 'Timestamp', id_col_attendance (ou 'Name'), 'Task', 'Status'.
    """
    # Primeiro tenta por ID se id_col_attendance for diferente de "Name" e athlete_name_or_id for um ID
    # Esta parte precisa de um mapeamento robusto entre nome do Fightcard e ID da Attendance
    # Por simplicidade inicial, vamos focar no nome, assumindo que "Name" existe em Attendance
    
    # Filtra registros para o atleta e a tarefa
    # A coluna de nome do atleta na aba Attendance pode ser "Name" ou "Fighter"
    # Vamos assumir "Name" por enquanto, ajuste se necessário
    relevant_records = df_attendance[
        (df_attendance[name_col_attendance].astype(str).str.upper() == str(athlete_name_or_id).upper()) &
        (df_attendance["Task"].astype(str) == task_name)
    ]

    if relevant_records.empty:
        return "Pendente" # Ou "---"

    # Ordena por Timestamp para pegar o mais recente
    if "Timestamp" in relevant_records.columns:
        try:
            # Cria cópia para evitar SettingWithCopyWarning
            relevant_records_sorted = relevant_records.copy()
            relevant_records_sorted["Timestamp_dt"] = pd.to_datetime(
                relevant_records_sorted["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors='coerce'
            )
            relevant_records_sorted.dropna(subset=["Timestamp_dt"], inplace=True)
            if not relevant_records_sorted.empty:
                return relevant_records_sorted.sort_values(by="Timestamp_dt", ascending=False).iloc[0]["Status"]
        except Exception:
            # Se falhar a ordenação, pega o último pela ordem original
            return relevant_records.iloc[-1]["Status"]
    
    return relevant_records.iloc[-1]["Status"] # Fallback

# --- Função Principal de Renderização do Dashboard ---
def render_dashboard_html(df_fightcard, df_attendance, task_list, id_col_attendance):
    # df_athlete_details pode ser passado se necessário
    
    # Seu CSS (pode ser colocado fora da função se for estático)
    html_output = '''
    <style>
        /* Seu CSS da página Fightcard ... */
        /* Adicionar estilos para a lista de tarefas e status */
        .task-status-list {
            list-style-type: none;
            padding-left: 0;
            font-size: 14px; /* Ajuste conforme necessário */
            text-align: left; /* Alinhar texto da lista à esquerda */
        }
        .task-status-list li {
            margin-bottom: 4px;
            display: flex; /* Para alinhar nome da tarefa e status */
            justify-content: space-between; /* Espaçar nome da tarefa e status */
        }
        .task-name {
            font-weight: normal;
            color: #ccc; /* Cor mais clara para nome da tarefa */
        }
        .status-done { color: #34A853; font-weight: bold; } /* Verde */
        .status-requested { color: #FFD700; font-weight: bold; } /* Amarelo/Dourado */
        .status-pending { color: #E5E5E5; font-weight: normal; } /* Cinza claro */
        /* Adicione mais classes de status conforme necessário */
    </style>
    '''

    grouped_events = df_fightcard.groupby("Event")

    for event_name, event_group in grouped_events:
        html_output += f"<div class='event-header'>{event_name}</div>"
        html_output += "<table class='fightcard-table'><thead><tr>"
        html_output += "<th colspan='2'>Blue Corner & Tasks</th>" # Colspan ajustado
        html_output += "<th>Fight Details</th>"
        html_output += "<th colspan='2'>Red Corner & Tasks</th>" # Colspan ajustado
        html_output += "</tr></thead><tbody>"

        fights_in_event = event_group.groupby("FightOrder")

        for fight_order, fight_df in fights_in_event:
            blue_fighter_series = fight_df[fight_df["Corner"] == "blue"].squeeze()
            red_fighter_series = fight_df[fight_df["Corner"] == "red"].squeeze()

            blue_name = blue_fighter_series.get("Fighter", "") if isinstance(blue_fighter_series, pd.Series) else ""
            red_name = red_fighter_series.get("Fighter", "") if isinstance(red_fighter_series, pd.Series) else ""
            
            # Construir HTML para as tarefas do lutador AZUL
            blue_tasks_html = "<ul class='task-status-list'>"
            if blue_name: # Só processa tarefas se houver um lutador
                for task in task_list:
                    status = get_task_status_for_athlete(blue_name, task, df_attendance, id_col_attendance)
                    status_class = f"status-{str(status).lower().replace(' ', '-')}" # Ex: status-done, status-requested
                    if status in ["Pendente", "---", "Não Registrado"]: status_class = "status-pending"
                    blue_tasks_html += f"<li><span class='task-name'>{html.escape(task)}:</span> <span class='{status_class}'>{html.escape(status)}</span></li>"
            blue_tasks_html += "</ul>"

            # Construir HTML para as tarefas do lutador VERMELHO
            red_tasks_html = "<ul class='task-status-list'>"
            if red_name: # Só processa tarefas se houver um lutador
                for task in task_list:
                    status = get_task_status_for_athlete(red_name, task, df_attendance, id_col_attendance)
                    status_class = f"status-{str(status).lower().replace(' ', '-')}"
                    if status in ["Pendente", "---", "Não Registrado"]: status_class = "status-pending"
                    red_tasks_html += f"<li><span class='task-name'>{html.escape(task)}:</span> <span class='{status_class}'>{html.escape(status)}</span></li>"
            red_tasks_html += "</ul>"

            blue_img_html = f"<img src='{blue_fighter_series.get('Picture', '')}' class='fightcard-img'>" if isinstance(blue_fighter_series, pd.Series) and blue_fighter_series.get("Picture") else "<div style='width:100px; height:100px; background-color:#222; border-radius:8px;'></div>" # Placeholder
            red_img_html = f"<img src='{red_fighter_series.get('Picture', '')}' class='fightcard-img'>" if isinstance(red_fighter_series, pd.Series) and red_fighter_series.get("Picture") else "<div style='width:100px; height:100px; background-color:#222; border-radius:8px;'></div>" # Placeholder
            
            division = blue_fighter_series.get("Division", "") if isinstance(blue_fighter_series, pd.Series) else red_fighter_series.get("Division", "")
            fight_info = f"FIGHT #{int(fight_order)}<br>{division}"

            html_output += f"""
            <tr>
                <td class='blue'>{blue_img_html}<br/><strong>{html.escape(blue_name)}</strong>{blue_tasks_html if blue_name else ""}</td>
                <td class='blue' style="display:none;"></td> {/* Coluna vazia para manter colspan, pode ser ocultada/removida se ajustar colspan */}
                <td class='middle-cell'>{fight_info}</td>
                <td class='red'>{red_img_html}<br/><strong>{html.escape(red_name)}</strong>{red_tasks_html if red_name else ""}</td>
                <td class='red' style="display:none;"></td> {/* Coluna vazia para manter colspan */}
            </tr>
            """
            # Se você quiser que nome/foto e tarefas fiquem em células separadas, ajuste o colspan e adicione mais <td>
            # Por exemplo, colspan='1' para a imagem/nome, e uma nova <td> para as tarefas.
            # A estrutura acima coloca tarefas abaixo do nome na mesma célula grande.
            # Para ter imagem/nome em uma célula e tarefas em outra, a estrutura da tabela precisaria de mais colunas (ex: 3 para cada lado).
            # Exemplo alternativo para células separadas (requer ajuste de colspan e th):
            # html_output += f"""
            # <tr>
            #     <td class='blue'>{blue_img_html}<br/><strong>{html.escape(blue_name)}</strong></td>
            #     <td class='blue' style="text-align:left;">{blue_tasks_html if blue_name else ""}</td>
            #     <td class='middle-cell'>{fight_info}</td>
            #     <td class='red' style="text-align:left;">{red_tasks_html if red_name else ""}</td>
            #     <td class='red'>{red_img_html}<br/><strong>{html.escape(red_name)}</strong></td>
            # </tr>
            # """


        html_output += "</tbody></table>"
    return html_output

# --- Configuração da Página Streamlit ---
st.set_page_config(layout="wide", page_title="Dashboard de Atletas")
st.markdown("<h1 style='text-align:center; color:white;'>DASHBOARD DE ATLETAS</h1>", unsafe_allow_html=True)

# --- Carregamento de Todos os Dados ---
# Presume que as funções de carregamento e gspread estão definidas ou importadas.
# Se estiverem em outro arquivo (ex: utils.py), importe-as.
# Exemplo: from utils import get_gspread_client, connect_gsheet_tab, load_attendance_data, load_config_data

# Se as funções estiverem no mesmo arquivo, defina-as antes desta seção.
# Para este exemplo, vou colocar placeholders das funções que você já tem:

# Placeholder para funções de conexão e carregamento (substitua pelas suas reais)
# Assume que MAIN_SHEET_NAME, ATTENDANCE_TAB_NAME, CONFIG_TAB_NAME, ID_COLUMN_IN_ATTENDANCE
# estão definidos globalmente ou passados corretamente.

# @st.cache_resource
# def get_gspread_client(): ... # Sua função existente
# def connect_gsheet_tab(gspread_client, sheet_name, tab_name): ... # Sua função existente

# @st.cache_data
# def load_attendance_data(sheet_name=MAIN_SHEET_NAME, attendance_tab_name=ATTENDANCE_TAB_NAME): ... # Sua função existente
    # Lembre-se de que esta função deve retornar um DataFrame com a coluna ID_COLUMN_IN_ATTENDANCE, "Task", "Status", "Timestamp"

# @st.cache_data
# def load_config_data(sheet_name=MAIN_SHEET_NAME, config_tab_name=CONFIG_TAB_NAME): ... # Sua função existente
    # Deve retornar (task_list, task_status_list)

# --- CARREGAMENTO REAL DOS DADOS ---
df_fightcard_loaded = load_fightcard_data()
df_attendance_loaded = load_attendance_data() # Adapte os argumentos se necessário
task_list_loaded, _ = load_config_data()      # Só precisamos da task_list aqui

# --- Renderização ---
if df_fightcard_loaded.empty:
    st.warning("Nenhum dado de Fightcard para exibir.")
elif df_attendance_loaded.empty:
    st.warning("Nenhum dado de Attendance para buscar status. O status das tarefas será 'Pendente'.")
    # Ainda renderiza o fightcard, mas todos os status serão "Pendente"
    dashboard_html = render_dashboard_html(df_fightcard_loaded, pd.DataFrame(), task_list_loaded, ID_COLUMN_IN_ATTENDANCE)
    st.components.v1.html(dashboard_html, height=6000, scrolling=True)
elif not task_list_loaded:
    st.error("TaskList não carregada da Configuração. Não é possível exibir o status das tarefas.")
else:
    dashboard_html = render_dashboard_html(df_fightcard_loaded, df_attendance_loaded, task_list_loaded, ID_COLUMN_IN_ATTENDANCE)
    st.components.v1.html(dashboard_html, height=6000, scrolling=True)
