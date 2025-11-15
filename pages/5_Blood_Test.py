from components.layout import bootstrap_page
import streamlit as st

bootstrap_page("Blood Test")  # <- PRIMEIRA LINHA DA PÁGINA

# ==============================================================================
# BLOOD TEST - PAGE
# ==============================================================================
from task_app import render_task_page

PAGE_TITLE = "Blood Test"
FIXED_TASK = "Blood Test"
# Use aliases simples; a função de mask já normaliza/escapa
TASK_ALIASES = ["blood test", "blood"]

render_task_page(page_title=PAGE_TITLE, fixed_task=FIXED_TASK, task_aliases=TASK_ALIASES)
