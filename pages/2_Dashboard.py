import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from auth import check_authentication
from utils import (
    display_user_sidebar,
    load_fightcard_data,
    load_attendance_data,
    get_task_list,
    get_latest_status
)

# --- Autenticação e Configuração ---
check_authentication()
st.set_page_config(layout="wide", page_title="Fight Dashboard")
display_user_sidebar()

# --- Constantes Específicas da Página ---
# ... (Seus mapeamentos de STATUS_INFO e TASK_EMOJI_MAP continuam aqui)

# --- Lógica da Página ---
st.title("Fight Dashboard")
st_autorefresh(interval=60000, key="dash_auto_refresh_v14")

with st.spinner("Carregando dados..."):
    df_fc = load_fightcard_data()
    df_att = load_attendance_data()
    all_tasks = get_task_list()

# --- Sidebar de Controles ---
# ... (Seu código da sidebar de filtros continua aqui)

# --- Lógica Principal do Dashboard ---
# Sua lógica principal para processar e exibir os dados do dashboard
# A única mudança é chamar a nova função get_latest_status
# Exemplo de como adaptar a chamada dentro do seu loop:
# status_info = get_latest_status(id, ev, task, df_att)
# status_class = STATUS_INFO.get(status_info["status"], {}).get("class", DEFAULT_STATUS_CLASS)
# status_text = status_info["status"]
# ... resto do código da página ...
