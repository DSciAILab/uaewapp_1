import streamlit as st
import html

def check_authentication():
    """
    Verifica se o usuário está autenticado na sessão do Streamlit.
    Se não estiver, redireciona para a página de login.
    Esta função deve ser a primeira chamada em qualquer página protegida.
    """
    if not st.session_state.get("user_confirmed", False):
        st.switch_page("pages/1_Login.py")

def display_user_sidebar():
    """
    Exibe as informações do usuário logado e um botão de logout na barra lateral.
    """
    st.sidebar.header("Usuário Logado")
    if st.session_state.get("user_confirmed", False):
        un = html.escape(st.session_state.get("current_user_name", "Usuário"))
        ui = html.escape(st.session_state.get("current_user_ps_id_internal", ""))
        uim = st.session_state.get('current_user_image_url', "")
        
        image_html = f"""<img src="{html.escape(uim, True)}" 
                             style="width:50px;height:50px;border-radius:50%;object-fit:cover;
                                    border:1px solid #555;vertical-align:middle;margin-right:10px;">""" \
                     if uim and uim.startswith("http") else \
                     "<div style='width:50px;height:50px;border-radius:50%;background-color:#333;" \
                     "margin-right:10px;display:inline-block;vertical-align:middle;'></div>"
        
        st.sidebar.markdown(f"""
            <div style="display:flex;align-items:center;height:50px;margin-top:0px;">
                {image_html}
                <div style="line-height:1.2;vertical-align:middle;">
                    <span style="font-weight:bold;">{un}</span><br>
                    <span style="font-size:0.9em;color:#ccc;">PS: {ui}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.sidebar.button("Logout", use_container_width=True, type="secondary", key="logout_btn"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.switch_page("pages/1_Login.py")