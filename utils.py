# Em utils.py

def display_user_sidebar():
    st.sidebar.title("UAEW App")
    st.sidebar.markdown(f"Bem-vindo, **{st.session_state.get('current_user_name', 'Usuário')}**!")

    if st.sidebar.button("Logout", use_container_width=True):
        # Limpa o estado da sessão para um logout completo
        st.session_state.clear()
        
        # Esta chamada está CORRETA, pois redireciona para a página
        # de login que está na raiz do projeto.
        st.switch_page("1_Login.py") 

    st.sidebar.markdown("---")
