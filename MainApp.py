# MainApp.py
import streamlit as st

st.set_page_config(
    page_title="UAE Warriors App",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("Navegação")
# Adicione aqui links para outras páginas se tiver, ou deixe apenas o título.
# O Streamlit gera automaticamente a navegação para as páginas na pasta `pages`.

st.title("Bem-vindo ao UAE Warriors App")
st.write("Selecione uma página na barra lateral.")

# Você pode adicionar mais conteúdo à sua página principal aqui.
