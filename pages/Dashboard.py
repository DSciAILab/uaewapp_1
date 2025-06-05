# dashboard_page.py
import streamlit as st
import pandas as pd
# ... (suas outras importações: gspread, Credentials, datetime, html)

# --- Constantes (como definido antes) ---
# MAIN_SHEET_NAME, ATHLETES_TAB_NAME, USERS_TAB_NAME, 
# ATTENDANCE_TAB_NAME, ID_COLUMN_IN_ATTENDANCE, NAME_COLUMN_IN_ATTENDANCE, 
# CONFIG_TAB_NAME, STATUS_PENDING_EQUIVALENTS

# --- Função para Carregar CSS Externo ---
def local_css(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f: # Adicionado encoding
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Arquivo CSS '{file_name}' não encontrado. Crie-o na mesma pasta do script.")
    except Exception as e:
        st.error(f"Erro ao carregar CSS: {e}")


# --- Suas Funções de Conexão e Carregamento de Dados (get_gspread_client, etc.) ---
# ... (COPIE SUAS FUNÇÕES REAIS AQUI) ...
# Substitua as funções _placeholder no exemplo anterior pelas suas.

# --- Função get_task_status_for_athlete (como definida antes) ---
# ...

# --- Função render_dashboard_html_content (a nova versão acima) ---
# ...

# --- Configuração da Página Streamlit ---
st.markdown("<h1 style='text-align:center; color:white;'>DASHBOARD DE ATLETAS</h1>", unsafe_allow_html=True)
local_css("style.css") # Carrega o CSS

# --- Carregamento de Todos os Dados ---
# Use suas funções de carregamento reais aqui
with st.spinner("Carregando dados do Fightcard..."): 
    df_fc_data = load_fightcard_data() # Sua função real
with st.spinner("Carregando dados de Presença..."): 
    df_att_data = load_attendance_data_placeholder() # Sua função real, usando ATTENDANCE_TAB_NAME
with st.spinner("Carregando Configurações de Tarefas..."): 
    task_list_data, _ = load_config_data_placeholder() # Sua função real

# --- Renderização ---
if df_fc_data.empty:
    st.warning("Nenhum dado de Fightcard para exibir.")
elif not task_list_data:
    st.error("TaskList não carregada. Não é possível exibir o status das tarefas.")
else:
    if df_att_data.empty:
        st.info("Dados de presença não encontrados. Status das tarefas podem aparecer como 'Pendente'.")
    
    # Certifique-se que os nomes de coluna para ID e Nome em Attendance estão corretos
    dashboard_html_output = render_dashboard_html_content(
        df_fc_data, 
        df_att_data, 
        task_list_data, 
        ID_COLUMN_IN_ATTENDANCE, 
        NAME_COLUMN_IN_ATTENDANCE 
    )
    st.components.v1.html(dashboard_html_output, height=calculate_height(df_fc_data), scrolling=True)

# Função para calcular altura dinâmica (opcional, mas útil)
def calculate_height(df_fightcard, base_height_per_event=100, height_per_fight=180):
    num_events = df_fightcard["Event"].nunique() if not df_fightcard.empty else 0
    num_fights = len(df_fightcard.groupby(["Event", "FightOrder"])) if not df_fightcard.empty else 0
    total_height = (num_events * base_height_per_event) + (num_fights * height_per_fight) + 200 # +200 para padding e cabeçalho geral
    return max(total_height, 800) # Altura mínima de 800px
