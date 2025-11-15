import streamlit as st
import html

# --- Navegação segura entre versões do Streamlit ---
def _safe_switch_page(target: str):
    """
    Tenta navegar para outra página:
    - Usa st.switch_page quando disponível.
    - Caso contrário, exibe um link clicável para o usuário.
    """
    if hasattr(st, "switch_page"):
        try:
            st.switch_page(target)
            return
        except Exception:
            pass  # cai no fallback abaixo

    # Fallback: mostra um link para o usuário
    st.warning("Navigation fallback: click the link below to go to the login page.")
    st.markdown(f"[Open {html.escape(target)}]({target})")


# auth.py
import streamlit as st
import html

def check_authentication():
    """
    Se não autenticado, redireciona uma única vez para /pages/1_Login.py
    e interrompe a renderização da página atual.
    """
    if st.session_state.get("user_confirmed", False):
        return

    # evita múltiplos redirecionamentos em um mesmo ciclo
    if not st.session_state.get("_did_redirect_to_login", False):
        st.session_state["_did_redirect_to_login"] = True
        st.switch_page("pages/1_Login.py")

    st.stop()


def display_user_sidebar():
    """
    Exibe informações do usuário logado e botão de logout na barra lateral.
    Seta um flag para evitar render duplicado quando há sidebar unificado.
    """
    # Evita render duplo se já houve sidebar unificado
    if st.session_state.get("_unified_sidebar_rendered", False):
        return

    st.sidebar.header("Usuário Logado")

    if st.session_state.get("user_confirmed", False):
        un = html.escape(st.session_state.get("current_user_name", "Usuário"))
        ui = html.escape(st.session_state.get("current_user_ps_id_internal", ""))
        uim = st.session_state.get("current_user_image_url", "")

        image_html = (
            f"""<img src="{html.escape(uim, True)}"
                     style="width:50px;height:50px;border-radius:50%;object-fit:cover;
                            border:1px solid #555;vertical-align:middle;margin-right:10px;">"""
            if (uim and isinstance(uim, str) and uim.startswith("http"))
            else "<div style='width:50px;height:50px;border-radius:50%;background-color:#333;"
                 "margin-right:10px;display:inline-block;vertical-align:middle;'></div>"
        )

        st.sidebar.markdown(
            f"""
            <div style="display:flex;align-items:center;height:50px;margin-top:0px;">
                {image_html}
                <div style="line-height:1.2;vertical-align:middle;">
                    <span style="font-weight:bold;">{un}</span><br>
                    <span style="font-size:0.9em;color:#ccc;">PS: {ui}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.sidebar.button("Logout", use_container_width=True, type="secondary", key="logout_btn"):
            # Limpa toda a sessão e caches de dados; mantém somente flags mínimos se necessário
            keys = list(st.session_state.keys())
            for key in keys:
                try:
                    del st.session_state[key]
                except Exception:
                    pass

            # Limpa caches (caso existam funções cacheadas)
            try:
                st.cache_data.clear()
            except Exception:
                pass
            try:
                st.cache_resource.clear()
            except Exception:
                pass

            _safe_switch_page("pages/1_Login.py")

    # Marca que já renderizamos algo no sidebar (evita duplicidade em páginas que checam esse flag)
    st.session_state["_unified_sidebar_rendered"] = True
