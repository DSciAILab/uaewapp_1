# components/layout.py
import streamlit as st
from auth import check_authentication, display_user_sidebar

def _ensure_page_config_once():
    if not st.session_state.get("_page_config_done", False):
        # Ajuste aqui o título e layout global do app
        st.set_page_config(
            page_title="UAEW Operations App",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        st.session_state["_page_config_done"] = True

def bootstrap_page(page_title: str, require_auth: bool = True):
    """
    - Configura a página 1 única vez (set_page_config).
    - Faz gate de autenticação (pula no Login).
    - Desenha o sidebar unificado 1x por render.
    """
    _ensure_page_config_once()

    # Guard de auth: nunca autenticar na página de Login
    is_login_page = page_title.strip().lower() == "login"
    if require_auth and not is_login_page:
        check_authentication()

    # Sidebar unificado (marca que já foi desenhado)
    st.session_state["_unified_sidebar_rendered"] = True
    display_user_sidebar()
