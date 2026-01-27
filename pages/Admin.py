from components.layout import bootstrap_page
import streamlit as st

# --- Admin-only page protection ---
current_role = str(st.session_state.get("user_type", "")).strip().lower()

# Mostra o cargo atual para facilitar o ajuste na planilha
if current_role != "admin":
    st.warning(f"Cargo atual na sessão: '{current_role or 'Não definido'}'")
    st.info("Para acessar, a coluna 'user_type' na planilha deve dizer 'admin'.")

if current_role != "admin":
    st.error("Acesso negado. Apenas administradores podem ver esta página.", icon="🚨")
    st.stop()

bootstrap_page("Admin Panel")
st.title("Admin Panel")

st.markdown("### Page Visibility Management")

# List all pages (Python files in pages directory)
import os

PAGES_DIR = os.path.dirname(__file__)
all_pages = [
    f for f in os.listdir(PAGES_DIR)
    if f.endswith(".py") and f != "Admin.py"
]

# Load visibility configuration stored in session_state
if "page_visibility" not in st.session_state:
    st.session_state["page_visibility"] = {p: True for p in all_pages}

# Toggle list
for page in sorted(all_pages):
    current = st.session_state["page_visibility"].get(page, True)
    new_val = st.toggle(f"{page}", value=current)
    st.session_state["page_visibility"][page] = new_val

st.success("Changes saved automatically.")
