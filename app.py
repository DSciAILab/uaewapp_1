import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
import time
import json

# Configuração inicial
st.set_page_config(page_title="Controle de Atletas MMA - UAE Warriors", layout="wide", page_icon="🥊")

# CSS aprimorado
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; font-family: 'Roboto', sans-serif; }
    .stButton>button {
        background-color: #262730; color: white; border: 1px solid #555;
        border-radius: 8px; padding: 8px 16px; transition: all 0.3s;
    }
    .stButton>button:hover { background-color: #4CAF50; border-color: #4CAF50; }
    .stTextInput>div>div>input {
        background-color: #2a2b2e; color: white; border: 1px solid #888;
        border-radius: 6px; padding: 8px;
    }
    .athlete-name { font-size: 1.8rem; font-weight: 700; text-align: center; padding: 0.75rem 0; }
    .corner-vermelho { border-top: 4px solid #e63946; padding-top: 8px; }
    .corner-azul { border-top: 4px solid #1d4ed8; padding-top: 8px; }
    .status-text { font-size: 0.9rem; color: #a1a1a1; }
    .expander-header { font-size: 1.1rem; }
    .st-expander { background-color: #1a1c22; border-radius: 8px; margin-bottom: 1rem; }
    .chart-container { background-color: #1a1c22; padding: 1rem; border-radius: 8px; }
    @media (max-width: 600px) {
        .athlete-name { font-size: 1.4rem; }
        .stButton>button { padding: 6px 12px; font-size: 0.9rem; }
        .stTextInput>div>div>input { font-size: 0.9rem; }
    }
    </style>
""", unsafe_allow_html=True)

# Conexão com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("UAEW_App").worksheet("Sheet1")
    return sheet

# Carregamento de dados com cache
@st.cache_data(show_spinner=False)
def load_data(_sheet):
    data = _sheet.get_all_records()
    return pd.DataFrame(data)

# Validação de entrada
def validar_entrada(campo, valor):
    try:
        if campo in ["Hight", "Range", "Weight"]:
            valor_float = float(valor)
            if campo == "Hight" and not (1.0 <= valor_float <= 2.5):
                return False, "Altura deve estar entre 1.0 e 2.5 metros"
            if campo == "Weight" and not (30 <= valor_float <= 200):
                return False, "Peso deve estar entre 30 e 200 kg"
            if campo == "Range" and not (0 <= valor_float <= 3.0):
                return False, "Alcance deve estar entre 0 e 3.0 metros"
        return True, ""
    except ValueError:
        return False, f"{campo} deve ser um número válido"

# Atualização de célula com feedback
def salvar_valor(sheet, row, col_index, valor, campo):
    valido, mensagem = validar_entrada(campo, valor)
    if not valido:
        st.error(mensagem)
        return False
    try:
        with st.spinner(f"Salvando {campo}..."):
            sheet.update_cell(row + 2, col_index + 1, valor)
            time.sleep(0.5)  # Simula latência para feedback
        st.success(f"{campo} atualizado com sucesso!")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar {campo}: {str(e)}")
        return False

# Função para gerar texto de status
def gerar_status_texto(row):
    status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]
    status_list = []
    for status in status_cols:
        valor = str(row.get(status, "")).strip().lower()
        if valor == "done":
            status_list.append(f"[{status.upper()} ✅]")
        elif valor == "required":
            status_list.append(f"[{status.upper()} ⚠️]")
    return " ".join(status_list)

# Título principal
st.title("UAE Warriors 59-60")

# Auto-refresh
st_autorefresh(interval=10_000, key="datarefresh")

# Filtros e Paginação
sheet = connect_sheet()
df = load_data(sheet)

# Resumo com gráfico
st.subheader("Resumo de Status")
status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]
status_data = {
    "labels": status_cols,
    "datasets": [
        {
            "label": "Completos",
            "data": [df[df[col] == "done"].shape[0] for col in status_cols],
            "backgroundColor": "#4CAF50",
            "borderColor": "#388E3C",
            "borderWidth": 1
        },
        {
            "label": "Pendentes",
            "data": [df[df[col] == "required"].shape[0] for col in status_cols],
            "backgroundColor": "#e63946",
            "borderColor": "#d00000",
            "borderWidth": 1
        }
    ]
}
st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
st.json({
    "type": "bar",
    "data": status_data,
    "options": {
        "scales": {
            "y": {"beginAtZero": True}
        },
        "plugins": {
            "legend": {"position": "top"}
        }
    }
}, expanded=False)
st.markdown("</div>", unsafe_allow_html=True)

col_filtros, col_export = st.columns([8, 4])
with col_filtros:
    col_evento, col_corner, col_paginacao = st.columns(3)
    eventos = sorted(df['Event'].dropna().unique())
    corners = sorted(df['Corner'].dropna().unique())
    evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
    corner_sel = col_corner.multiselect("Corner", corners)
    itens_por_pagina = col_paginacao.selectbox("Atletas por página", [5, 10, 20, 50], index=1)

with col_export:
    if st.button("Exportar como CSV"):
        csv = df.to_csv(index=False)
        st.download_button("Baixar CSV", csv, "atletas.csv", "text/csv")

if st.button("🔄 Atualizar Página"):
    st.cache_data.clear()
    st.rerun()

# Filtrar dados
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# Paginação
total_itens = len(df)
pagina_atual = st.number_input("Página", min_value=1, max_value=max(1, (total_itens // itens_por_pagina) + 1), value=1)
inicio = (pagina_atual - 1) * itens_por_pagina
fim = inicio + itens_por_pagina
df_paginado = df.iloc[inicio:fim]

# Renderiza atletas
campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]

for i, row in df_paginado.iterrows():
    cor_class = "corner-vermelho" if str(row.get("Corner", "")).lower() == "red" else "corner-azul"
    status_titulo = gerar_status_texto(row)
    tem_pendencia = any(str(row.get(status, "")).lower() == "required" for status in status_cols)
    icone_alerta = " ⚠️" if tem_pendencia else ""

    titulo_base = f"{row['Fighter ID']} - {row['Name']}{icone_alerta} {status_titulo}"

    with st.expander(titulo_base, expanded=False):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        col1, col2 = st.columns([1, 5])

        # Imagem e informações básicas
        if row.get("Image"):
            try:
                col1.image(row["Image"], width=100)
                col1.markdown(f"**Fight Order:** {row.get('Fight Order', '')}")
            except:
                col1.warning("Imagem inválida")
        else:
            col1.markdown(f"**Fight Order:** {row.get('Fight Order', '')}")

        col1.markdown(f"**Division:** {row['Division']}")
        col1.markdown(f"**Opponent:** {row['Oponent']}")

        col2.markdown(f"<div class='athlete-name'>{row['Name']}</div>", unsafe_allow_html=True)

        # Edição por campo
        campo_1, campo_2 = col2.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            valor_atual = str(row.get(campo, ""))
            edit_key = f"edit_mode_{i}_{campo}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            editando = st.session_state[edit_key]
            botao_label = "Salvar" if editando else "Editar"

            if idx % 2 == 0:
                target_col = campo_1
            else:
                target_col = campo_2

            with target_col:
                input_valor = st.text_input(f"{campo}", value=valor_atual, key=f"{campo}_{i}", disabled=not editando)
                if st.button(botao_label, key=f"botao_{campo}_{i}"):
                    if editando:
                        col_index = df.columns.get_loc(campo)
                        if salvar_valor(sheet, i, col_index, input_valor, campo):
                            st.session_state[edit_key] = False
                    else:
                        st.session_state[edit_key] = True
                    st.rerun()

        # Link WhatsApp
        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            col2.markdown(f"[📞 Enviar mensagem no WhatsApp]({link})", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

# Exibir informações de paginação
st.markdown(f"Mostrando {inicio + 1} a {min(fim, total_itens)} de {total_itens} atletas")
