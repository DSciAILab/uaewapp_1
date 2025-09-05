from components.layout import bootstrap_page
import streamlit as st

bootstrap_page("UAEW Operations App")  # <- PRIMEIRA LINHA

st.title("UAEW Operations App")
st.markdown("Use o menu segmentado na barra lateral ou os botões abaixo.")
st.divider()
st.subheader("Quick Navigation")

col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/1_Login.py", label="🔐 Login Page", use_container_width=True)
    st.page_link("pages/2_Fightcard.py", label="🥊 Fight Card", use_container_width=True)
with col2:
    st.page_link("pages/3_Dashboard.py", label="📊 Dashboard", use_container_width=True)
    # aceita _4_Arrival_List.py também (já tratado no sidebar)
    st.page_link("pages/4_Arrival_List.py", label="🛬 Arrivals", use_container_width=True)
with col3:
    st.page_link("pages/6_Stats.py", label="📈 Fighter Stats", use_container_width=True)
