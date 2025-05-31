# UAE Warriors App v1.1.60

import streamlit as st
import pandas as pd
from utils import load_data, salvar_valor

# Carrega dados do Google Sheets
df, sheet = load_data()
headers = [h.strip() for h in sheet.row_values(1)]
tarefas = [t for t in headers if t.upper() in ["PHOTOSHOOT", "BLOOD TEST", "UNIFORM", "MUSIC", "STATS"]]

# Sidebar com filtros
st.sidebar.title("📂 Filtros")
eventos = ["Todos"] + sorted(df["Event"].dropna().unique().tolist())
corner_opts = ["Blue", "Red"]
status_opts = ["Todos", "Somente Pendentes", "Somente Concluídos"]

selected_event = st.sidebar.selectbox("Event", eventos)
selected_corner = st.sidebar.selectbox("Corner", corner_opts)
selected_status = st.sidebar.selectbox("Status das Tarefas", status_opts)

# Aplica filtros
if selected_event != "Todos":
    df = df[df["Event"] == selected_event]
df = df[df["Corner"] == selected_corner]

if selected_status == "Somente Pendentes":
    df = df[df[tarefas].apply(lambda row: any(str(row[t]).lower() == "required" for t in tarefas), axis=1)]
elif selected_status == "Somente Concluídos":
    df = df[df[tarefas].apply(lambda row: all(str(row[t]).lower() == "done" for t in tarefas), axis=1)]

# Loop por atleta
for _, row in df.iterrows():
    lock = row.get("LockBy", "")
    id_unico = f"lock_{row['original_index']}"
    edicao_liberada = st.toggle("Editar", key=id_unico, value=(lock == "1724"), disabled=(lock not in ["", "1724"]))

    # Atualiza LockBy
    if edicao_liberada and lock != "1724":
        salvar_valor(sheet, row['original_index'], headers.index("LockBy"), "1724")
    elif not edicao_liberada and lock == "1724":
        salvar_valor(sheet, row['original_index'], headers.index("LockBy"), "")

    # Cabeçalho
    st.markdown("<hr>", unsafe_allow_html=True)
    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        st.image(row.get("Avatar"), width=100)
    with col2:
        st.markdown(f"<div class='name-tag'>{row.get('Name')}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<p style='text-align: center;'>Fight {row.get('Fight Order')} | {row.get('Division')} | Opponent {row.get('Oponent')}</p>",
            unsafe_allow_html=True
        )

    # Informações em tabelas
    info1, info2 = st.columns(2)
    with info1:
        st.markdown("<div class='section-label'>Detalhes Pessoais</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <table><tr><th>Event</th><td>{row.get('Event')}</td></tr>
        <tr><th>Corner</th><td>{row.get('Corner')}</td></tr>
        <tr><th>Weight</th><td>{row.get('Weight')}</td></tr></table>
        """, unsafe_allow_html=True)

        st.markdown("<div class='section-label'>Hotel</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <table><tr><th>Check-in</th><td>{row.get('Check-in')}</td></tr>
        <tr><th>Check-out</th><td>{row.get('Check-out')}</td></tr>
        <tr><th>Room</th><td>{row.get('Room')}</td></tr></table>
        """, unsafe_allow_html=True)

    with info2:
        st.markdown("<div class='section-label'>Logística</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <table><tr><th>Flight</th><td>{row.get('Flight')}</td></tr>
        <tr><th>Arrival</th><td>{row.get('Arrival')}</td></tr>
        <tr><th>Coach</th><td>{row.get('Coach')}</td></tr></table>
        """, unsafe_allow_html=True)

        st.markdown("<div class='section-label'>Notas</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <table><tr><th>Note</th><td>{row.get('Note')}</td></tr>
        <tr><th>Comments</th><td>{row.get('Comments')}</td></tr></table>
        """, unsafe_allow_html=True)

    # Tarefas com status interativo
    st.markdown("<div class='section-label'>Tarefas</div>", unsafe_allow_html=True)
    badge_line = []
    for t in tarefas:
        valor_atual = str(row.get(t, "")).lower()
        classe = "badge-neutral"
        if valor_atual == "required":
            classe = "badge-required"
        elif valor_atual == "done":
            classe = "badge-done"

        if edicao_liberada:
            if st.button(t.upper(), key=f"{t}_{row['original_index']}"):
                novo_valor = "done" if valor_atual == "required" else "required"
                salvar_valor(sheet, row['original_index'], headers.index(t), novo_valor)
                st.experimental_rerun()

        badge_line.append(f"<span class='badge {classe}'>{t.upper()}</span>")

    st.markdown(" ".join(badge_line), unsafe_allow_html=True)
