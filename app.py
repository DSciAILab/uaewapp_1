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
@st.cache_data(ttl=300)
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# 📂 Atualiza célula específica
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Configuração da interface
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")

# 🌙 Estilo escuro e tags customizadas
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    .stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
    .stTextInput>div>div>input, .stSelectbox>div>div>div>input { background-color: #3a3b3c; color: #f0f0f0; border: 1px solid #888; }
    .pending-label { background-color: #ffcccc; color: #8b0000; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 600; text-transform: uppercase; }
    .done-label { background-color: #2b3e2b; color: #5efc82; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 600; text-transform: uppercase; }
    .neutral-label { background-color: #444; color: #ccc; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 500; text-transform: uppercase; }
    .athlete-name-header { font-size: 1.8rem; font-weight: bold; margin-bottom: 0.5rem; color: #f4f4f4; text-align: center; }
    .corner-vermelho { border-top: 4px solid red; padding-top: 6px; margin-top: 0.5rem; }
    .corner-azul { border-top: 4px solid #0099ff; padding-top: 6px; margin-top: 0.5rem; }
    </style>
""", unsafe_allow_html=True)

# 📊 Barra lateral com filtros
sheet = connect_sheet()
df_original = load_data(sheet)

with st.sidebar:
    evento_sel = st.multiselect("Evento", sorted(df_original['Event'].dropna().unique()))
    corner_sel = st.multiselect("Corner", sorted(df_original['Corner'].dropna().unique()))
    if st.button("🔄 Recarregar Dados"):
        st.cache_data.clear()
        st.rerun()

# 🔍 Filtragem dos dados
df = df_original.copy()
if evento_sel:
    df = df[df['Event'].isin(evento_sel)]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# 🏣 Título da Página
st.title("UAE Warriors 59-60")

# 👊 Exibição dos atletas
for i, row in df.iterrows():
    cor_class = "corner-vermelho" if str(row.get("Corner", "")).lower() == "red" else "corner-azul"
    status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]

    with st.expander(row['Name'], expanded=False):
        st.markdown(f"<div class='athlete-name-header'>{row['Name']}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1.5, 5])

        if row.get("Image"):
            try:
                col1.image(row["Image"], width=100)
            except:
                col1.warning("Imagem inválida")

        col2.markdown(f"**Fight:** {row.get('Fight Order', '')}")
        col2.markdown(f"{row['Division']}")
        col2.markdown(f"**Opponent:** {row['Oponent']}")

        for status in status_cols:
            col_idx = df.columns.get_loc(status)
            valor = str(row[status]).strip().lower()
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

        edit_key = f"edit_mode_{i}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        editando = st.session_state[edit_key]
        botao_label = "Salvar" if editando else "Editar"
        if col3.button(botao_label, key=f"botao_toggle_{i}"):
            if editando:
                campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight", "Coach", "Music 1", "Music 2", "Music 3"]
                for campo in campos_editaveis:
                    novo_valor = st.session_state.get(f"{campo}_{i}", "")
                    col_index = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_index, novo_valor)
            st.session_state[edit_key] = not editando
            st.rerun()

        campo_a, campo_b = col3.columns(2)
        campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight", "Coach", "Music 1", "Music 2", "Music 3"]
        lista_paises = ["UAE", "Brazil", "USA", "Russia", "Philippines", "Egypt", "India", "Morocco", "Iran"]

        for idx, campo in enumerate(campos_editaveis):
            valor_atual = str(row.get(campo, ""))
            if campo == "Nationality":
                input_widget = st.selectbox
                args = (f"{campo}", lista_paises)
                kwargs = {"index": lista_paises.index(valor_atual) if valor_atual in lista_paises else 0, "key": f"{campo}_{i}", "disabled": not editando}
            else:
                input_widget = st.text_input
                args = (f"{campo}",)
                kwargs = {"value": valor_atual, "key": f"{campo}_{i}", "disabled": not editando, "max_chars": 50 if "Music" in campo else None}

            if idx % 2 == 0:
                campo_a.__getattribute__(input_widget.__name__)(*args, **kwargs)
            else:
                campo_b.__getattribute__(input_widget.__name__)(*args, **kwargs)

        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            col3.markdown(f"[📥 Enviar mensagem no WhatsApp]({link})", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

# Modo TV (visualização somente)
if st.sidebar.checkbox("🖥️ Modo TV"):
    st.markdown("""
    <style>
        .stApp { zoom: 1.25; }
        .streamlit-expanderHeader {font-size: 1.5rem;}
        .athlete-name-header { font-size: 2rem; }
    </style>
    """, unsafe_allow_html=True)
