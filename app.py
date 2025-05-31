# 🔹 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.37

### Novidades desta versão:
- Exibindo apenas atletas com ROLE == Fighter
- Estilo de layout atualizado para tarefas, logística e dados pessoais em linha
- Restaurado estilo de cabeçalho da versão 1.1.29
"""

# 🖖️ Importações
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🔐 Conexão com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet_file = client.open("UAEW_App")
    abas = [ws.title for ws in sheet_file.worksheets()]
    if "App" in abas:
        sheet = sheet_file.worksheet("App")
    else:
        st.error("A aba 'App' não foi encontrada. Verifique o nome da aba na planilha.")
        st.stop()
    return sheet

# 🔄 Carrega dados
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df = df[df["ROLE"].str.lower() == "fighter"]  # filtra apenas lutadores
    return df, sheet

# 📂 Salvar valores no Google Sheets
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Configuração inicial
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10000, key="autorefresh")

# 🎨 Estilo
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
.stTextInput>div>div>input { background-color: #3a3b3c; color: white; border: 1px solid #888; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 3px; text-transform: uppercase; display: inline-block; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.athlete-name-header { font-size: 2rem; font-weight: bold; color: white; text-align: center; margin-top: 10px; margin-bottom: 10px; }
.athlete-sub { text-align: center; margin-bottom: 10px; color: #ccc; }
.avatar { border-radius: 50%; width: 60px; height: 60px; object-fit: cover; margin-right: 12px; }
.divider { height: 2px; background-color: #444; margin: 20px 0; border: none; }
</style>
""", unsafe_allow_html=True)

# 🔖 Carregamento
df, sheet = load_data()
st.title("UAE Warriors 59-60")

# 🔍 Filtros
col_evento, col_corner = st.columns([6, 6])
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())

evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
corner_sel = col_corner.multiselect("Corner", corners)

if st.button("Atualizar"):
    st.rerun()

if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# 🚩 Campos por setor
campos_setores = {
    "Tarefas": ["Black Screen", "Video Status", "Photoshoot", "Blood Test", "Interview", "Stats"],
    "Logística": ["Booking Number / Room", "Arrival Details", "Departure Details", "Flight Ticket"],
    "Pessoais": ["Nationality", "DOB", "Passport", "Doc (Download)"],
    "Evento": ["Country", "City", "Fight Style", "Team", "Weight", "Uniform", "Height", "Range", "Music 1", "Music 2", "Notes"]
}

status_cols = campos_setores["Tarefas"]

# 📋 Badges visuais
def gerar_badge(valor, status):
    valor = valor.strip().lower()
    if valor == "done":
        return f"<span class='badge badge-done'>{status.upper()}</span>"
    elif valor == "required":
        return f"<span class='badge badge-required'>{status.upper()}</span>"
    else:
        return f"<span class='badge badge-neutral'>{status.upper()}</span>"

# 👥 Iteração por atleta
for i, row in df.iterrows():
    corner_color = "#0099ff" if str(row.get("Corner", "")).lower() == "blue" else "#ff4b4b"
    nome_html = f"<span style='color:{corner_color}; font-size: 1.8rem; font-weight: bold;'>"
    nome_html += ("\u26a0\ufe0f " if any(str(row.get(col, "")).lower() == "required" for col in status_cols) else "")
    nome_html += f"{row['Name']}</span>"

    with st.container():
        col_img, col_nome = st.columns([1, 10])
        with col_img:
            if row.get("Image"):
                try:
                    st.image(row["Image"], width=60)
                except:
                    st.empty()
        with col_nome:
            st.markdown(nome_html, unsafe_allow_html=True)

        st.markdown(
            "<div class='athlete-sub'>" +
            f"{' '.join([gerar_badge(str(row.get(s, '')), s) for s in status_cols])}" +
            "</div>", unsafe_allow_html=True
        )
        st.markdown(
            f"<div class='athlete-sub'>Fight {row.get('Fight Order', '?')} | {row.get('Division', '')} | Opponent {row.get('Oponent', '')}</div>",
            unsafe_allow_html=True
        )
        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            st.markdown(f"<div style='text-align: center;'><a href='{link}' target='_blank'>\ud83d\udcf1 Enviar mensagem no WhatsApp</a></div>", unsafe_allow_html=True)

        with st.expander("Exibir detalhes"):
            for setor, campos in campos_setores.items():
                st.subheader(setor)
                col1, col2 = st.columns(2)
                for idx, campo in enumerate(campos):
                    valor_atual = str(row.get(campo, ""))
                    if setor in ["Tarefas", "Logística", "Pessoais"]:
                        if idx % 2 == 0:
                            col1.markdown(f"**{campo}**: {valor_atual}")
                        else:
                            col2.markdown(f"**{campo}**: {valor_atual}")
                    elif setor == "Evento":
                        if campo == "Uniform":
                            options = ["Small", "Medium", "Large", "2X-Large"]
                            selected = valor_atual if valor_atual in options else options[0]
                            if idx % 2 == 0:
                                col1.selectbox(campo, options, index=options.index(selected), key=f"{campo}_{i}", disabled=True)
                            else:
                                col2.selectbox(campo, options, index=options.index(selected), key=f"{campo}_{i}", disabled=True)
                        else:
                            if idx % 2 == 0:
                                col1.text_input(campo, value=valor_atual, key=f"{campo}_{i}", disabled=True)
                            else:
                                col2.text_input(campo, value=valor_atual, key=f"{campo}_{i}", disabled=True)

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
