# pages/DashboardNovo.py

# --- Importações de Bibliotecas ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from auth import check_authentication  # ### NOVO ###: Importa o guardião

# --- VERIFICAÇÃO DE AUTENTICAÇÃO ---
# ### NOVO ###: Esta é a primeira coisa que o script faz.
check_authentication()

# --- CONFIGURAÇÃO DA PÁGINA ---
# ... (o resto do seu código de configuração de página continua aqui)
# ...

# --- CONTROLES DA BARRA LATERAL (Sidebar) ---
st.sidebar.title("Dashboard Controls")

# ### NOVO ###: Adiciona as informações do usuário e o botão de logout
st.sidebar.markdown(f"Bem-vindo, **{st.session_state.get('current_user_name', 'Usuário')}**")
if st.sidebar.button("Logout", key="logout_dashboard"):
    # Limpa as chaves de sessão relacionadas ao usuário
    for key in ['user_confirmed', 'current_user_name', 'current_user_ps_id_internal', 'current_user_image_url']:
        if key in st.session_state:
            del st.session_state[key]
    st.switch_page("1_Login.py")

st.sidebar.markdown("---")
# O resto dos seus controles de sidebar continuam aqui...
if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
# ... etc

# ### REMOVER ###: Apague a seção inteira que começava com `with st.container(border=True):`
# que continha o formulário de login. Ela não é mais necessária aqui.
