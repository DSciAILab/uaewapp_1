# 📍 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.24

### Mudanças nesta versão:
- Status badges movidos para a primeira linha dentro do expander
- Layout reorganizado para priorizar clareza visual
- Estilo refinado com centralização de imagem e nome
- Nome do atleta estilizado de acordo com o corner

### 🗓️ Última atualização: 2025-05-31
"""

# 🏖️ Importações
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 📱 Conexão com Google Sheets
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

# 🔀 Carregamento de dados
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# 📂 Atualização de célula
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Layout e Auto-refresh
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000, key="datarefresh")

# 🎨 Estilo CSS
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    .stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
    .stTextInput>div>div>input { background-color: #3a3b3c; color: white; border: 1px solid #888; }
    .athlete-name { font-size: 1.8rem; font-weight: bold; text-align: center; padding: 0.5rem 0; }
    .corner-vermelho { background-color: rgba(255, 0, 0, 0.1); border-radius: 10px; padding: 10px; }
    .corner-azul { background-color: rgba(0, 153, 255, 0.1); border-radius: 10px; padding: 10px; }
    .badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 0 3px; text-transform: uppercase; display: inline-block; }
    .badge-done { background-color: #2e4f2e; color: #5efc82; }
    .badge-required { background-color: #5c1a1a; color: #ff8080; }
    .badge-neutral { background-color: #444; color: #ccc; }
    .status-line { padding-top: 6px; margin-bottom: 5px; }
    .name-vermelho { color: red; font-weight: bold; font-size: 1.8rem; }
    .name-azul { color: #0099ff; font-weight: bold; font-size: 1.8rem; }
    .row-header { display: flex; align-items: center; justify-content: center; gap: 20px; margin-bottom: -10px; }
    </style>
""", unsafe_allow_html=True)

# 🏇 Título principal
st.title("UAE Warriors 59-60")

# 🗓️ Dados e filtros
sheet = connect_sheet()
df = load_data(sheet)

col_evento, col_corner = st.columns([6, 6])
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())

evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
corner_sel = col_corner.multiselect("Corner", corners)

if st.button("Atualizar Página"):
    st.rerun()

if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# 🔋 Campos e status
campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]
status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]

# 🦢 Função para gerar badges
def gerar_badge(valor, status):
    valor = valor.strip().lower()
    if valor == "done":
        return f"<span class='badge badge-done'>{status.upper()}</span>"
    elif valor == "required":
        return f"<span class='badge badge-required'>{status.upper()}</span>"
    else:
        return f"<span class='badge badge-neutral'>{status.upper()}</span>"

# 🦕 Renderiza atletas
for i, row in df.iterrows():
    corner = str(row.get("Corner", "")).lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"

    tem_pendencia = any(str(row.get(status, "")).lower() == "required" for status in status_cols)
    icone_alerta = "⚠️ " if tem_pendencia else ""

    st.markdown("<div class='row-header'>", unsafe_allow_html=True)
    if row.get("Image"):
        try:
            st.image(row["Image"], width=80)
        except:
            st.warning("Imagem inválida")
    st.markdown(f"{icone_alerta}<span class='{nome_class}'>{row['Name']}</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Exibir detalhes"):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        # Linha 1 - BADGES
        status_badges = "".join(gerar_badge(str(row.get(status, "")), status) for status in status_cols)
        st.markdown(f"<div class='status-line'>{status_badges}</div>", unsafe_allow_html=True)

        # Linha 2 - detalhes da luta
        detalhes_luta = f"Fight {row['Fight Order']} | {row['Division']} | Opponent {row['Oponent']}"
        st.markdown(f"<div style='font-size: 0.9rem; color: #ccc; margin-bottom: 6px;'>{detalhes_luta}</div>", unsafe_allow_html=True)

        col1, col2 = st.columns([1, 5])

        edit_key = f"edit_mode_{i}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        editando = st.session_state[edit_key]
        botao_label = "Salvar" if editando else "Editar"
        if col2.button(botao_label, key=f"botao_toggle_{i}"):
            if editando:
                for campo in campos_editaveis:
                    novo_valor = st.session_state.get(f"{campo}_{i}", "")
                    col_index = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_index, novo_valor)
            st.session_state[edit_key] = not editando
            st.rerun()

        campo_1, campo_2 = col2.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            valor_atual = str(row.get(campo, ""))
            if idx % 2 == 0:
                campo_1.text_input(f"{campo}", value=valor_atual, key=f"{campo}_{i}", disabled=not editando)
            else:
                campo_2.text_input(f"{campo}", value=valor_atual, key=f"{campo}_{i}", disabled=not editando)

        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            col2.markdown(f"<a href='{link}' target='_blank'>📞 Enviar mensagem no WhatsApp</a>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
