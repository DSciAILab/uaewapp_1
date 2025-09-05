from components.layout import bootstrap_page
import streamlit as st

bootstrap_page("Blood Test")  # <- PRIMEIRA LINHA DA PÁGINA

st.title("Blood Test")



# ==============================================================================
# BLOOD TEST - PAGE
# ==============================================================================
from task_app import render_task_page

PAGE_TITLE = "Blood Test"
FIXED_TASK = "Blood Test"
TASK_ALIASES = [r"\bblood\s*test\b", r"\bblood\b"]

render_task_page(page_title=PAGE_TITLE, fixed_task=FIXED_TASK, task_aliases=TASK_ALIASES)
