# MainApp.py
import streamlit as st

if 'page_config_set' not in st.session_state:
    st.set_page_config(
        page_title="UAE Warriors App",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.session_state.page_config_set = True

st.sidebar.title("Navegação")

if 'main_app_content_loaded' not in st.session_state: 
    st.title("Bem-vindo ao Aplicativo UAE Warriors")
    st.write("Selecione uma opção na barra lateral para começar.")
    try:
        st.image("https://uaewarriors.com/wp-content/uploads/2023/02/UAE-Warriors-Logo-Transparent.png", width=300)
    except Exception:
        st.write("Logo UAE Warriors") 
    st.session_state.main_app_content_loaded = True
