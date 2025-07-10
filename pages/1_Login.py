import streamlit as st
from google.oauth2.service_account import Credentials
import gspread

# ... (cole aqui as funções get_gspread_client, load_users_data, get_valid_user_info) ...

st.set_page_config(page_title="UAEW Login", layout="centered")
st.title("UAEW | Controle de Acesso")
st.markdown("Por favor, faça o login para continuar.")

if 'user_confirmed' not in st.session_state:
    st.session_state['user_confirmed'] = False

user_id_input = st.text_input("Digite seu PS ou Nome de Usuário", key="login_user_input")

if st.button("Login", type="primary"):
    if user_id_input:
        user_info = get_valid_user_info(user_id_input)
        if user_info:
            st.session_state['user_confirmed'] = True
            st.session_state['current_user_name'] = str(user_info.get("USER", user_id_input)).strip()
            st.session_state['current_user_ps_id_internal'] = str(user_info.get("PS", "")).strip()
            st.session_state['current_user_image_url'] = str(user_info.get("USER_IMAGE", "")).strip()
            st.toast(f"Bem-vindo, {st.session_state['current_user_name']}!", icon="👋")
            st.switch_page("pages/2_Dashboard.py")
        else:
            st.error("Usuário não encontrado.", icon="🚨")
    else:
        st.warning("Por favor, insira seus dados.", icon="⚠️")
