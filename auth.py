import streamlit as st

def check_authentication():
    """
    Verifica se o usuário está logado.
    Se não estiver, redireciona para a página de login.
    """
    # Acessa o st.session_state para verificar a flag 'user_confirmed'
    # Usamos .get() para evitar erros caso a chave ainda não exista
    if not st.session_state.get("user_confirmed", False):
        # Se não estiver confirmada, redireciona para a página de login e para a execução.
        st.switch_page("1_Login.py")
