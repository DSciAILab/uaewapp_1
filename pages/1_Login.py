from components.layout import bootstrap_page
import streamlit as st
from utils import get_valid_user_info
import html

# ------------------------------------------------------------------------------
# Bootstrap da página (config/layout/sidebar centralizados)
# ------------------------------------------------------------------------------
bootstrap_page("Login", require_auth=False)  # <- PRIMEIRA LINHA DA PÁGINA

# ------------------------------------------------------------------------------
# Helpers de navegação (compatibilidade entre versões do Streamlit)
# ------------------------------------------------------------------------------
def _safe_switch_page(target: str):
    """
    Tenta navegar para outra página:
    - Usa st.switch_page quando disponível.
    - Caso contrário, mostra um link clicável como fallback.
    """
    if hasattr(st, "switch_page"):
        try:
            st.switch_page(target)
            return
        except Exception:
            pass  # fallback abaixo
    st.warning("Navigation fallback: click the link below to proceed.", icon="🧭")
    st.markdown(f"[Open {html.escape(target)}]({target})")

def _nav_home(label: str = "🏠 Go to Home"):
    """
    Mostra um link/botão para a Home com fallback.
    """
    if hasattr(st, "page_link"):
        st.page_link("Home.py", label=label, use_container_width=True)
    else:
        if st.button(label, use_container_width=True):
            _safe_switch_page("Home.py")

# ------------------------------------------------------------------------------
# Se já estiver logado, oferece ir para Home ou Logout
# ------------------------------------------------------------------------------
st.title("UAEW App – Login")

if st.session_state.get("user_confirmed", False):
    st.success(f"Você já está logado como **{st.session_state.get('current_user_name', 'Usuário')}**.")
    col_home, col_logout = st.columns([1, 1])
    with col_home:
        _nav_home("🏠 Ir para a Home")
    with col_logout:
        if st.button("Fazer logout", use_container_width=True, type="secondary"):
            # Limpa sessão e caches para um logout completo
            for key in list(st.session_state.keys()):
                try:
                    del st.session_state[key]
                except Exception:
                    pass
            try:
                st.cache_data.clear()
            except Exception:
                pass
            try:
                st.cache_resource.clear()
            except Exception:
                pass
            st.rerun()
    st.stop()

# ------------------------------------------------------------------------------
# Formulário de Login
# ------------------------------------------------------------------------------
st.write("Por favor, insira seu PS Number para continuar.")

# Estado inicial do input (opcional)
if "user_id_input" not in st.session_state:
    st.session_state["user_id_input"] = ""

user_id_input = st.text_input(
    "PS Number",
    value=st.session_state["user_id_input"],
    max_chars=50,
    key="uid_login_input",
    placeholder="Digite os 4 dígitos do seu PS (ex.: 0123) ou 'PS0123'"
)

if st.button("Login", key="login_button", use_container_width=True, type="primary"):
    u_in = (user_id_input or "").strip()
    if not u_in:
        st.warning("Por favor, insira um ID/Nome de usuário.", icon="⚠️")
    else:
        # Validação centralizada no utils.get_valid_user_info (aceita 'PS123', '123' ou nome)
        u_inf = get_valid_user_info(u_in)
        if u_inf:
            # Preenche sessão
            st.session_state.update(
                current_user_ps_id_internal=str(u_inf.get("PS", u_in)).strip(),
                current_user_id=u_in,
                current_user_name=str(u_inf.get("USER", u_in)).strip(),
                current_user_image_url=str(u_inf.get("USER_IMAGE", "")).strip(),
                user_confirmed=True,
                warning_message=None,
                user_type=str(u_inf.get("USER_TYPE", "")).strip().lower(),
            )
            st.toast(f"Bem-vindo, {st.session_state.current_user_name}!", icon="🎉")
            _safe_switch_page("Home.py")
        else:
            st.error(f"Usuário '{u_in}' não encontrado ou inválido.", icon="🚨")
