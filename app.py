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
st.markdown("Use os botões abaixo para navegar entre as diferentes seções do aplicativo, ou use o menu na barra lateral.")

st.divider()

st.subheader("Acesso Rápido")

# Cria colunas para os botões de navegação
col1, col2, col3 = st.columns(3)

with col1:
    st.page_link("pages/1_Dashboard.py", label="📊 Dashboard Geral", icon="📊", use_container_width=True)
    st.page_link("pages/2_Tasks.py", label="📋 Controle de Tarefas", icon="📋", use_container_width=True)
    st.page_link("pages/3_Stats.py", label="📈 Controle de Estatísticas", icon="📈", use_container_width=True)

with col2:
    st.page_link("pages/4_Blood_Test.py", label="🩸 Exame de Sangue", icon="🩸", use_container_width=True)
    st.page_link("pages/transfer1.py", label="✈️ Transfer & Check-in", icon="✈️", use_container_width=True)
    st.page_link("pages/Bus.py", label="🚌 Controle de Ônibus", icon="🚌", use_container_width=True)

with col3:
    st.page_link("pages/Fightcard.py", label="🥊 Fightcard", icon="🥊", use_container_width=True)
    st.page_link("pages/Attendance [Register].py", label="⏳ Fila de Atendimento", icon="⏳", use_container_width=True)
