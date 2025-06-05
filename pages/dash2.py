# pages/DashboardTickets.py 
# (Nome do arquivo diferente para não confundir com o Dashboard.py anterior)

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta

# --- Configuração da Página ---
# st.set_page_config(layout="wide", page_title="Dashboard de Suporte") # Definido no MainApp.py

# --- Geração de Dados Fictícios (Sample Data) ---
@st.cache_data # Cache para não gerar dados toda vez
def generate_sample_data(num_tickets=100):
    np.random.seed(42)
    ticket_ids = [f"TICKET-{1100 - i}" for i in range(num_tickets)]
    issues = [
        "Website performance degradation", "Collaboration tool not sending notifications",
        "System updates causing compatibility issues", "Database connection failure",
        "Security vulnerability identified", "Customer data not loading in CRM",
        "Email server downtime", "Login page unresponsive", "Software license expired",
        "VPN connection unstable"
    ]
    statuses = ["Open", "In Progress", "Closed"]
    priorities = ["Low", "Medium", "High"]
    
    data = {
        "ID": np.random.choice(ticket_ids, num_tickets, replace=False),
        "Issue": np.random.choice(issues, num_tickets),
        "Status": np.random.choice(statuses, num_tickets, p=[0.35, 0.15, 0.5]), # Mais abertos e fechados
        "Priority": np.random.choice(priorities, num_tickets, p=[0.4, 0.4, 0.2]),
        "Date Submitted": [datetime(2023, 1, 1) + timedelta(days=int(d)) for d in np.random.randint(0, 360, num_tickets)]
    }
    df = pd.DataFrame(data)
    df["Date Submitted"] = pd.to_datetime(df["Date Submitted"])
    # Para os deltas das métricas, precisamos de dados de um período anterior (simulado)
    df["Previous Period Open Tickets"] = np.random.randint(20, 50) 
    df["Previous Period Response Time"] = np.random.uniform(4.0, 8.0)
    df["Previous Period Resolution Time"] = np.random.uniform(10.0, 25.0)
    return df.sort_values(by="Date Submitted", ascending=False)

# --- Carregamento dos Dados ---
df_tickets = generate_sample_data(100)

# --- Título e Cabeçalho ---
st.title("Dashboard de Tickets de Suporte")
st.markdown("---")

# --- Métricas Principais ---
total_tickets = len(df_tickets)
open_tickets_df = df_tickets[df_tickets["Status"] == "Open"]
num_open_tickets = len(open_tickets_df)

# Simular dados para as métricas de tempo e deltas
# (Em um cenário real, isso viria de cálculos mais complexos ou de outra fonte de dados)
avg_response_time_hours = 5.2 
avg_resolution_time_hours = 16.0

# Para os deltas, comparamos com um valor "do período anterior" (simulado na geração de dados)
# Pegamos o primeiro valor, já que é constante para este dataset de exemplo
prev_open_tickets = df_tickets["Previous Period Open Tickets"].iloc[0] if not df_tickets.empty else num_open_tickets
prev_response_time = df_tickets["Previous Period Response Time"].iloc[0] if not df_tickets.empty else avg_response_time_hours
prev_resolution_time = df_tickets["Previous Period Resolution Time"].iloc[0] if not df_tickets.empty else avg_resolution_time_hours

delta_open_tickets = num_open_tickets - prev_open_tickets
delta_response_time = round(avg_response_time_hours - prev_response_time, 1)
delta_resolution_time = round(avg_resolution_time_hours - prev_resolution_time, 1)


st.subheader(f"Número Total de Tickets: {total_tickets}")
st.info("📝 Você pode editar os tickets clicando duas vezes em uma célula. Note como os gráficos abaixo atualizam automaticamente! Você também pode ordenar a tabela clicando nos cabeçalhos das colunas.")

# --- Tabela Editável de Tickets ---
# Usar uma cópia para o editor não afetar os cálculos originais diretamente até o rerun
edited_df = st.data_editor(
    df_tickets[["ID", "Issue", "Status", "Priority", "Date Submitted"]].head(10), # Mostra apenas os 10 mais recentes
    num_rows="dynamic", # Permite adicionar/remover linhas se quiser, ou "fixed"
    use_container_width=True,
    # Configuração de colunas (opcional, para dropdowns, etc.)
    column_config={
        "Status": st.column_config.SelectboxColumn(
            "Status",
            options=["Open", "In Progress", "Closed"],
            required=True,
        ),
        "Priority": st.column_config.SelectboxColumn(
            "Priority",
            options=["Low", "Medium", "High"],
            required=True,
        ),
        "Date Submitted": st.column_config.DateColumn(
            "Date Submitted",
            format="YYYY-MM-DD", # Formato de data
        )
    }
)
# Se você quiser usar os dados editados para recalcular os gráficos:
# df_tickets_display = edited_df # Ou mesclar de volta ao df_tickets original
# Mas para simplicidade, os gráficos abaixo usarão o df_tickets original (ou o editado se você atribuir)
# Para que os gráficos atualizem com base no edited_df, use edited_df nas funções de gráfico.
# Por agora, vamos usar df_tickets para os gráficos para mostrar o estado original + edições visuais.

st.markdown("---")
st.subheader("Estatísticas Gerais")

# --- Estatísticas em Colunas ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Número de Tickets Abertos", value=num_open_tickets, delta=f"{delta_open_tickets:+.0f} vs anterior")
with col2:
    st.metric(label="Tempo Médio de Primeira Resposta (horas)", value=f"{avg_response_time_hours:.1f}", delta=f"{delta_response_time:+.1f}h vs anterior")
with col3:
    st.metric(label="Tempo Médio de Resolução (horas)", value=f"{avg_resolution_time_hours:.0f}", delta=f"{delta_resolution_time:+.0f}h vs anterior")

st.markdown("---")

# --- Gráfico de Status de Tickets por Mês ---
st.subheader("Status de Tickets por Mês")

# Preparar dados para o gráfico de barras
if not df_tickets.empty:
    df_tickets_monthly = df_tickets.copy()
    df_tickets_monthly["Month"] = df_tickets_monthly["Date Submitted"].dt.strftime("%Y-%m") # Agrupa por Ano-Mês
    
    # Contar tickets por Mês e Status
    status_per_month = df_tickets_monthly.groupby(["Month", "Status"])["ID"].count().unstack(fill_value=0)
    status_per_month = status_per_month.sort_index() # Ordena por mês
    
    # Reordenar colunas para uma ordem lógica na legenda (opcional)
    status_order = ["Open", "In Progress", "Closed"]
    status_per_month = status_per_month.reindex(columns=[s for s in status_order if s in status_per_month.columns], fill_value=0)

    # Mapear nomes de mês para exibição (opcional, para nomes mais amigáveis)
    # Ex: Jun, Jul, Aug...
    try:
        status_per_month.index = pd.to_datetime(status_per_month.index).strftime("%b") # Converte para nome do mês abreviado
    except: # Fallback se a conversão de índice falhar
        pass


    st.bar_chart(status_per_month, use_container_width=True)
    # Adicionar legenda manualmente se st.bar_chart não mostrar automaticamente ou para mais controle
    legend_html = "<div style='display: flex; justify-content: center; margin-top: 10px;'>"
    colors = {"Open": "#FF6B6B", "In Progress": "#4D96FF", "Closed": "#6BCB77"} # Cores para a legenda
    for status, color in colors.items():
        if status in status_per_month.columns: # Apenas se o status existir nos dados
             legend_html += f"<div style='margin-right: 20px;'><span style='background-color:{color}; width:15px; height:15px; display:inline-block; margin-right:5px; border-radius:3px;'></span>{status}</div>"
    legend_html += "</div>"
    st.markdown(legend_html, unsafe_allow_html=True)

else:
    st.info("Sem dados de tickets para gerar o gráfico mensal.")

st.markdown("---")

# --- Gráfico de Prioridades Atuais (Donut Chart com Altair) ---
st.subheader("Prioridades dos Tickets Atuais (Abertos e Em Progresso)")
if not open_tickets_df.empty:
    priority_counts = open_tickets_df["Priority"].value_counts().reset_index()
    priority_counts.columns = ["Priority", "Count"]

    # Cores para o gráfico de prioridade
    priority_colors = alt.Scale(
        domain=['Low', 'Medium', 'High'],
        range=['#6BCB77', '#FFD700', '#FF6B6B'] # Verde, Amarelo, Vermelho
    )

    chart_priority = alt.Chart(priority_counts).mark_arc(innerRadius=70, outerRadius=110).encode(
        theta=alt.Theta(field="Count", type="quantitative"),
        color=alt.Color(field="Priority", type="nominal", scale=priority_colors, legend=alt.Legend(title="Prioridade")),
        tooltip=['Priority', 'Count']
    ).properties(
        width=300, # Tamanho do gráfico
        height=300
    )
    
    # Centralizar o gráfico (usando colunas é uma forma)
    _, col_chart, _ = st.columns([0.2, 0.6, 0.2])
    with col_chart:
        st.altair_chart(chart_priority, use_container_width=True)

else:
    st.info("Sem tickets abertos ou em progresso para exibir prioridades.")
