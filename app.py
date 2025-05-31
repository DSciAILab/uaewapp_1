# 📌 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.0.8

### Novidades desta versão:
- Exibição dos status (badges) logo ao lado do nome do atleta no cabeçalho do `expander`
- Emojis de alerta (⚠️) em atletas com pendências
- Remoção dos badges duplicados abaixo
- Otimização de layout para responsividade
"""

# 📦 Importações
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

# 🔄 Carregamento de dados
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
    .pending-label { background-color: #ffcccc; color: #8b0000; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 600; text-transform: uppercase; }
    .done-label { background-color: #2b3e2b; color: #5efc82; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 600; text-transform: uppercase; }
    .neutral-label { background-color: #444; color: #999; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 500; text-transform: uppercase; }
    .badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin-left: 5px; text-transform: uppercase; display: inline-block; }
    .badge-done { background-color: #2e4f2e; color: #5efc82; }
    .badge-required { background-color: #5c1a1a; color: #ff8080; }
    .badge-neutral { background-color: #444; color: #ccc; }
    .athlete-name { font-size: 1.8rem; font-weight: bold; text-align: center; padding: 0.5rem 0; }
    .corner-vermelho { border-top: 4px solid red; padding-top: 6px; }
    .corner-azul { border-top: 4px solid #0099ff; padding-top: 6px; }
    </style>
""", unsafe_allow_html=True)

# 🏷️ Título principal
st.title("UAE Warriors 59-60")

# 🗓️ Dados e filtros
sheet = connect_sheet()
df = load_data(sheet)

col_evento, col_corner = st.columns([6, 6])
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())

evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
corner_sel = col_corner.multiselect("Corner", corners)

if st.button("\ud83d\udd04 Atualizar Página"):
    st.rerun()

if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# 🔋 Campos e status
campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]
status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]

def gerar_badge(valor, status):
    valor = valor.strip().lower()
    if valor == "done":
        return f"<span class='badge badge-done'>{status.upper()}</span>"
    elif valor == "required":
        return f"<span class='badge badge-required'>{status.upper()}</span>"
    else:
        return f"<span class='badge badge-neutral'>{status.upper()}</span>"

# 🤸️ Renderiza atletas
for i, row in df.iterrows():
    cor_class = "corner-vermelho" if str(row.get("Corner", "")).lower() == "red" else "corner-azul"

    status_tags = " ".join(
        gerar_badge(str(row.get(status, "")), status)
        for status in status_cols
    )

    tem_pendencia = any(str(row.get(status, "")) == "Required" for status in status_cols)
    icone_alerta = " \u26a0\ufe0f" if tem_pendencia else ""

    titulo = f"{row['Fighter ID']} - {row['Name']}{icone_alerta} {status_tags}"

    with st.expander(titulo, unsafe_allow_html=True):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 5])

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
            col2.markdown(f"[\ud83d\udcde Enviar mensagem no WhatsApp]({link})", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
