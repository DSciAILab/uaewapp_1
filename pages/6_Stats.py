# ==============================================================================
# UAEW Operations App — Stats Page (Card igual ao Blood Test, filtros no expander)
# ------------------------------------------------------------------------------
# Versão:        1.5.1
# Gerado em:     2025-09-07
# Autor:         Assistente (GPT)
#
# RESUMO
# - Página "Stats" com o MESMO card de atleta usado em Blood Test:
#   * Foto, nome/ID, “Event | FIGHT N | CORNER”, atalhos WhatsApp/Passport,
#   * linha de status da tarefa fixa (Stats),
#   * chips para OUTRAS tarefas (somente se Done/Requested),
#   * “Last Stats” (data + evento) vindo do Attendance (outro evento).
# - Formulário de edição/confirmar dos campos de Stats permanece igual.
# - Filtros de Status, Sort, Event e Search agora todos dentro de um expander.
# ==============================================================================

from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import html
import time
import unicodedata
import re
from typing import Tuple, List

# --- Bootstrap / título
bootstrap_page("Stats")
st.title("Stats")

# --- Imports do projeto
from utils import get_gspread_client, connect_gsheet_tab, load_config_data

# ----------------------------------------------------------------------
# (demais classes/helpers/loaders/funcs são idênticos à versão anterior)
# ... [mantém tudo igual: Config, helpers, load_athletes, load_attendance,
# preprocess_attendance, load_stats, compute_task_status_for_athletes,
# last_task_other_event_by_name, add_stats_record, registrar_log, CSS etc.]
# ----------------------------------------------------------------------

# ==============================================================================
# UI — Filtros (todos no expander)
# ==============================================================================
default_ss = {
    "selected_status": "All",
    "selected_event": "All Events",
    "fighter_search_query": "",
    "sort_by": "Name",
}
for k, v in default_ss.items():
    if k not in st.session_state:
        st.session_state[k] = v

with st.expander("Settings", expanded=True):
    col_status, col_sort = st.columns(2)
    with col_status:
        STATUS_FILTER_LABELS = {
            "All": "All",
            Config.STATUS_PENDING: "Pending",
            Config.STATUS_DONE: "Done",
        }
        st.segmented_control(
            "Filter by Status:",
            options=["All", Config.STATUS_DONE, Config.STATUS_PENDING],
            format_func=lambda x: STATUS_FILTER_LABELS.get(x, x if x else "Pending"),
            key="selected_status"
        )
    with col_sort:
        st.segmented_control(
            "Sort by:",
            options=["Name", "Fight Order"],
            key="sort_by",
            help="Choose how to sort the athletes list."
        )

    # >>> agora estes dois também estão no expander <<<
    event_options = ["All Events"] + (
        sorted([evt for evt in df_athletes[Config.COL_EVENT].unique()
                if evt != Config.DEFAULT_EVENT_PLACEHOLDER])
        if not df_athletes.empty else []
    )
    st.selectbox("Filter by Event:", options=event_options, key="selected_event")
    st.text_input("Search Athlete:", placeholder="Type athlete name or ID...", key="fighter_search_query")

# ==============================================================================
# (demais blocos: load/prep dos dfs, resumo Done/Pending, loop dos cards,
# formulário de edição/confirmar, etc. continuam exatamente iguais)
# ==============================================================================
