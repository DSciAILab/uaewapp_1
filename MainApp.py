# MainApp.py
import streamlit as st

# st.set_page_config só pode ser chamado uma vez e como o primeiro comando Streamlit
# Se você já o define em outras páginas, pode precisar de uma estratégia diferente
# ou defini-lo apenas aqui.
if 'page_config_set' not in st.session_state:
    st.set_page_config(
        page_title="UAE Warriors App",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.session_state.page_config_set = True


st.sidebar.title("Navegação")
# O Streamlit gera automaticamente a navegação para as páginas na pasta `pages`

# Conteúdo da página principal (opcional)
if 'main_app_content_loaded' not in st.session_state:
    st.title("Bem-vindo ao Aplicativo UAE Warriors")
    st.write("Selecione uma opção na barra lateral para começar.")
    # Tenta carregar uma imagem. Se falhar, não quebra o app.
    try:
        st.image("https://uaewarriors.com/wp-content/uploads/2023/02/UAE-Warriors-Logo-Transparent.png", width=300)
    except Exception:
        st.write("Logo UAE Warriors") # Fallback text
    st.session_state.main_app_content_loaded = True
