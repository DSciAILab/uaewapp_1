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
        st.switch_page("app.py")

    st.stop()


def display_user_sidebar():
    """
    Exibe informações do usuário logado e botão de logout na barra lateral.
    Seta um flag para evitar render duplicado quando há sidebar unificado.
    """
    # Evita render duplo se já houve sidebar unificado
    if st.session_state.get("_unified_sidebar_rendered", False):
        return

    st.sidebar.divider()
    st.sidebar.subheader("Perfil")

    if st.session_state.get("user_confirmed", False):
        un = html.escape(st.session_state.get("current_user_name", "Usuário"))
        ui = html.escape(st.session_state.get("current_user_ps_id_internal", ""))
        uim = st.session_state.get("current_user_image_url", "")
        ut = html.escape(st.session_state.get("user_type", "").upper())

        image_html = (
            f"""<img src="{html.escape(uim, True)}"
                     style="width:40px;height:40px;border-radius:50%;object-fit:cover;
                            border:2px solid #666;vertical-align:middle;margin-right:10px;">"""
            if (uim and isinstance(uim, str) and uim.startswith("http"))
            else "<div style='width:40px;height:40px;border-radius:50%;background-color:#444;"
                 "margin-right:10px;display:inline-block;vertical-align:middle;text-align:center;line-height:40px;'></div>"
        )

        st.sidebar.markdown(
            f"""
            <div style="
                display:flex;
                align-items:center;
                background-color: #262730;
                padding: 10px;
                border-radius: 8px;
                margin-bottom: 10px;
                border: 1px solid #444;
            ">
                {image_html}
                <div style="line-height:1.2; overflow:hidden;">
                    <div style="font-weight:bold; font-size: 0.95em; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{un}</div>
                    <div style="font-size:0.8em; color:#aaa;">ID: {ui}</div>
                    <div style="font-size:0.75em; color:#4caf50; font-weight:bold;">{ut}</div>
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

            _safe_switch_page("app.py")

    # Marca que já renderizamos algo no sidebar (evita duplicidade em páginas que checam esse flag)
    st.session_state["_unified_sidebar_rendered"] = True
