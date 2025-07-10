import streamlit as st

def check_authentication():
    if not st.session_state.get("user_confirmed", False):
        st.switch_page("1_Login.py")
