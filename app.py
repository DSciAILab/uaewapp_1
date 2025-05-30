import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🔐 Conecta ao Google Sheets usando as credenciais do secrets
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

# 🔄 Carrega os dados da planilha como DataFrame
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# 📂 Atualiza célula específica
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Configuração da interface
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000, key="datarefresh")

# 🎨 Estilo escuro e componentes visuais
st.markdown("""
    <style>
    body, .stApp { background-color: #0e1117; color: white; }
    .stButton>button, .stTextInput>div>div>input {
        background-color: #262730; color: white; border: 1px solid #555;
    }
    .pending-label, .done-label, .neutral-label {
        padding: 4px 10px; border-radius: 8px; font-size: 0.85rem;
        display: inline-block; text-transform: uppercase; font-weight: 600;
    }
    .pending-label { background-color: #ffcccc; color: #8b0000; }
    .done-label { background-color: #2b3e2b; color: #5efc82; }
    .neutral-label { background-color: #444; color: #ccc; font-weight: 500; }
    .athlete-name-header { font-size: 1.8rem; font-weight: bold; text-align: center; margin-bottom: 0.5rem; }
    .corner-vermelho { border-top: 4px solid red; padding-top: 6px; margin-top: 0.5rem; }
    .corner-azul { border-top: 4px solid #0099ff; padding-top: 6px; margin-top: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# 🏷️ Título
st.title("UAE Warriors 59-60")

# 🔗 Dados da planilha
sheet = connect_sheet()
df = load_data(sheet)

# 🔍 Filtros
col_evento, col_corner = st.columns([6, 6])
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())

evento_sel = col_evento.multiselect("Evento", eventos)
corner_sel = col_corner.multiselect("Corner", corners)

if st.button("🔄 Atualizar Página"):
    st.rerun()

if evento_sel:
    df = df[df['Event'].isin(evento_sel)]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# 🧍‍♂️ Exibição dos atletas
for i, row in df.iterrows():
    corner = str(row.get("Corner", "")).lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"

    status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]
    titulo_expander = f"{row['Name']}"

    with st.expander(titulo_expander):
        st.markdown(f"<div class='athlete-name-header'>{row['Name']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1.5, 5])

        # Imagem ou fallback
        imagem = str(row.get("Image", "")).strip()
        if imagem:
            try:
                col1.image(imagem, width=100)
            except:
                col1.image("https://via.placeholder.com/100x100.png?text=No+Image", width=100)
        else:
            col1.image("https://via.placeholder.com/100x100.png?text=No+Image", width=100)

        # Detalhes básicos
        col2.markdown(f"**Fight:** {row.get('Fight Order', '')}")
        col2.markdown(f"{row.get('Division', '')}")
        col2.markdown(f"**Opponent:** {row.get('Oponent', '')}")

        # Tags de status
        for status in status_cols:
            col_idx = df.columns.get_loc(status)
            valor = str(row.get(status, "")).strip().lower()

            if valor == "required":
                if st.session_state.get(f"edit_mode_{i}", False) and col2.button(f"⚠️ {status}", key=f"{status}_{i}"):
                    salvar_valor(sheet, i, col_idx, "Done")
                    st.rerun()
                else:
                    col2.markdown(f"<span class='pending-label'>{status}</span>", unsafe_allow_html=True)
            elif valor == "done":
                col2.markdown(f"<span class='done-label'>{status}</span>", unsafe_allow_html=True)
            elif valor == "---":
                col2.markdown(f"<span class='neutral-label'>{status}</span>", unsafe_allow_html=True)
            else:
                col2.markdown(f"<span style='color:green'>{status}</span>", unsafe_allow_html=True)

        # Editar / Salvar campos
        edit_key = f"edit_mode_{i}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        editando = st.session_state[edit_key]
        botao_label = "Salvar" if editando else "Editar"
        if col3.button(botao_label, key=f"botao_toggle_{i}"):
            if editando:
                campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]
                for campo in campos_editaveis:
                    novo_valor = st.session_state.get(f"{campo}_{i}", "")
                    col_index = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_index, novo_valor)
            st.session_state[edit_key] = not editando
            st.rerun()

        # Campos editáveis
        campo_a, campo_b = col3.columns(2)
        campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]
        for idx, campo in enumerate(campos_editaveis):
            valor_atual = str(row.get(campo, ""))
            coluna = campo_a if idx % 2 == 0 else campo_b
            coluna.text_input(f"{campo}", value=valor_atual, key=f"{campo}_{i}", disabled=not editando)

        # WhatsApp
        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            col3.markdown(f"[📥 Enviar mensagem no WhatsApp]({link})", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
