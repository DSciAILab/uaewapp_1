import streamlit as st

# Importa o guardião de autenticação
from auth import check_authentication

# A verificação de autenticação deve ser a primeira coisa a ser executada
check_authentication()

# --- Configuração da Página ---
st.set_page_config(
    page_title="UAEW App - Home",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Exibe a barra lateral com informações do usuário e botão de logout
from auth import display_user_sidebar
display_user_sidebar()

st.title("Bem-vindo ao UAEW App! 👋")
st.markdown("Use o menu na barra lateral para navegar entre as diferentes seções do aplicativo.")
