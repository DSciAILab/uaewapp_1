import streamlit as st
from utils import get_valid_user_info

st.set_page_config(page_title="UAEW Login", layout="centered")

if st.session_state.get("user_confirmed"):
    st.switch_page("pages/2_Dashboard.py")

st.title("UAEW | Controle de Acesso")
st.markdown("Por favor, faça o login para continuar.")

user_id_input = st.text_input("PS Number ou Nome de Usuário", key="login_user_input")

if st.button("Login", type="primary", use_container_width=True):
    if user_id_input:
        user_info = get_valid_user_info(user_id_input)
        if user_info:
            st.session_state['user_confirmed'] = True
            st.session_state['current_user_name'] = str(user_info.get("USER", user_id_input)).strip()
            # ... Armazene outras informações do usuário se precisar
            st.toast(f"Bem-vindo, {st.session_state['current_user_name']}!", icon="👋")
            st.switch_page("pages/2_Dashboard.py")
        else:
            st.error("Usuário não encontrado.", icon="🚨")
