from components.layout import bootstrap_page
import streamlit as st

# Inicializa a página (config, sidebar unificado, autenticação, etc.)
bootstrap_page("UAEW Operations App")  # <- PRIMEIRA LINHA

st.title("UAEW Operations App")
st.markdown("Use o menu segmentado na barra lateral ou os botões abaixo.")
st.divider()
st.subheader("Quick Navigation")

# --- Fallback: compatibilidade entre st.page_link (mais novo) e st.switch_page (mais antigo) ---
def nav_link(target: str, label: str):
    """
    Renderiza um link de navegação.
    - Usa st.page_link quando disponível (Streamlit mais novo).
    - Caso contrário, usa um botão que chama st.switch_page.
    """
    if hasattr(st, "page_link"):
        # Streamlit recente
        st.page_link(target, label=label, use_container_width=True)
    else:
        # Streamlit mais antigo
        # Observação: st.switch_page aceita caminhos relativos em "pages/..."
        if st.button(label, use_container_width=True):
            try:
                st.switch_page(target)
            except Exception:
                # Em algumas versões, o alvo deve ser só o nome da página sem "pages/"
                # ou com extensão .py exata. Tentamos uma alternativa.
                alt_target = target.split("/")[-1]
                st.switch_page(alt_target)

col1, col2, col3 = st.columns(3)
with col1:
    nav_link("pages/1_Login.py", label="🔐 Login Page")
    nav_link("pages/2_Fightcard.py", label="🥊 Fight Card")

with col2:
    nav_link("pages/3_Dashboard.py", label="📊 Dashboard")
    # Aceita _4_Arrival_List.py também (já tratado no sidebar); aqui usamos a versão canonical:
    nav_link("pages/4_Arrival_List.py", label="🛬 Arrivals")

with col3:
    nav_link("pages/6_Stats.py", label="📈 Fighter Stats")
