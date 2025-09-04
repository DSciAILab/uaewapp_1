import streamlit as st
from utils import get_valid_user_info

# --- Configuração da Página ---
st.set_page_config(page_title="UAEW App - Login", layout="centered")

# Se o usuário já está logado, mostra uma mensagem e opções para navegar ou deslogar.
if st.session_state.get("user_confirmed", False):
    st.success(f"Você já está logado como **{st.session_state.get('current_user_name')}**.")
    st.page_link("app.py", label="Ir para a Home", icon="🏠")
    
    if st.button("Fazer logout"):
        # Limpa todas as chaves da sessão para um logout completo
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.stop()

# --- Formulário de Login ---
st.title("UAEW App Login")
st.write("Por favor, insira seu PS Number para continuar.")

if 'user_id_input' not in st.session_state:
    st.session_state['user_id_input'] = ""

user_id_input = st.text_input(
    "PS Number", 
    value=st.session_state['user_id_input'], 
    max_chars=50, 
    key="uid_login_input",
    placeholder="Digite os 4 dígitos do seu PS"
)

if st.button("Login", key="login_button", use_container_width=True, type="primary"):
    u_in = user_id_input.strip()
    if u_in:
        # Usa a função centralizada para validar o usuário
        u_inf = get_valid_user_info(u_in)
        if u_inf:
            # Armazena as informações do usuário na sessão
            st.session_state.update(
                current_user_ps_id_internal=str(u_inf.get("PS", u_in)).strip(),
                current_user_id=u_in,
                current_user_name=str(u_inf.get("USER", u_in)).strip(),
                current_user_image_url=str(u_inf.get("USER_IMAGE", "")).strip(),
                user_confirmed=True,
                warning_message=None
            )
            st.toast(f"Bem-vindo, {st.session_state.current_user_name}!", icon="🎉")
            # Redireciona para a página principal após o login
            st.switch_page("app.py")
        else:
            st.error(f"Usuário '{u_in}' não encontrado ou inválido.", icon="🚨")
    else:
        st.warning("Por favor, insira um ID/Nome de usuário.", icon="⚠️")