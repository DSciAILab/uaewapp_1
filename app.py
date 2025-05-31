# 🔹 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.46

### Novidades desta versão:
- Layout visual com 3 colunas mantido
- Restaurado botão de edição/salvamento
- Campos agora podem ser editáveis sob controle do usuário
- Correção do erro de update_cell usando índice original da planilha
- Corrigido erro ao salvar campo inexistente
"""

# 🔑 Importações
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
    return sheet_file.worksheet("App")

# 🔄 Carrega dados
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["original_index"] = df.index  # adiciona índice original
    return df, sheet

# 📂 Salvar valores
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Config inicial
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10000, key="autorefresh")

# 🎨 Estilo
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.athlete-header { display: flex; justify-content: center; align-items: center; gap: 1rem; margin-bottom: 10px; }
.avatar { border-radius: 50%; width: 60px; height: 60px; object-fit: cover; }
.name-tag { font-size: 2rem; font-weight: bold; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 3px; text-transform: uppercase; display: inline-block; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.section-label { font-weight: bold; margin-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# 🗓️ Título
df, sheet = load_data()
st.title("UAE Warriors 59-60")

# 🔍 Filtros
col_evento, col_corner = st.columns(2)
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())

evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
corner_sel = col_corner.multiselect("Corner", corners)

if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# Apenas Fighters
df = df[df['ROLE'].str.lower() == 'fighter']

# 📂 Campos de status e badges
tarefas = ["Black Screen", "Video Status", "Photoshoot", "Blood Test", "Interview", "Stats"]

def gerar_badge(valor, status):
    valor = valor.strip().lower()
    if valor == "done":
        return f"<span class='badge badge-done'>{status.upper()}</span>"
    elif valor == "required":
        return f"<span class='badge badge-required'>{status.upper()}</span>"
    else:
        return f"<span class='badge badge-neutral'>{status.upper()}</span>"

# 👥 Iterar atletas
for j, row in df.iterrows():
    i = int(row["original_index"])  # índice original da planilha
    with st.container():
        cor = "#ff4b4b" if row.get("Corner", "").lower() == "red" else "#0099ff"
        alerta = "⚠️ " if any(str(row.get(t, "")).lower() == "required" for t in tarefas) else ""
        nome_html = f"""
        <div class='athlete-header'>
            <img class='avatar' src='{row.get("Image", "")}'/>
            <span class='name-tag' style='color: {cor};'>{alerta}{row["Name"]}</span>
        </div>
        """
        st.markdown(nome_html, unsafe_allow_html=True)

        editar = st.toggle("Editar dados", key=f"editar_{i}")

        with st.expander("Exibir detalhes"):
            st.markdown(" ".join([gerar_badge(str(row.get(t, "")), t) for t in tarefas]), unsafe_allow_html=True)
            st.markdown(f"Fight {row['Fight Order']} | {row['Division']} | Opponent {row['Oponent']}")

            whatsapp = str(row.get("Whatsapp", "")).strip()
            if whatsapp:
                link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
                st.markdown(f"<div style='text-align: center;'><a href='{link}' target='_blank'>📱 Enviar mensagem no WhatsApp</a></div>", unsafe_allow_html=True)

            st.markdown("<div class='section-label'>Detalhes Pessoais</div>", unsafe_allow_html=True)
            st.text(f"Nationality: {row['Nationality']}  |  DOB: {row['DOB']}  |  Passport: {row['Passport']}")

            st.markdown("<div class='section-label'>Logística</div>", unsafe_allow_html=True)
            flight_link = row['Flight Ticket']
            flight_label = f"[Visualizar Passagem Aérea]({flight_link})" if flight_link else "Passagem não disponível"
            st.markdown(f"<span style='font-weight:bold'>Arrival:</span> {row['Arrival Details']}", unsafe_allow_html=True)
            st.markdown(f"<span style='font-weight:bold'>Departure:</span> {row['Departure Details']}  |  Flight: {flight_label}", unsafe_allow_html=True)

            st.markdown("<div class='section-label'>Hotel</div>", unsafe_allow_html=True)
            st.text(f"Room: {row['Booking Number / Room']}")

            st.markdown("<hr style='border-top:1px solid #444;'>", unsafe_allow_html=True)

            col1, col2, col3 = st.columns(3)
            campos = [c for c in ["Height", "Range", "Weight", "Country", "City", "Fight Style", "Team", "Uniform", "Music 1", "Music 2", "Notes"] if c in df.columns]
            colunas = [col1, col2, col3]
            for idx, campo in enumerate(campos):
                valor = str(row.get(campo, ""))
                coluna = colunas[idx % 3]
                key = f"{campo}_{i}"
                if campo == "Uniform":
                    opcoes = ["Small", "Medium", "Large", "2X-Large"]
                    idx_sel = opcoes.index(valor) if valor in opcoes else 0
                    new_valor = coluna.selectbox(campo, opcoes, index=idx_sel, disabled=not editar, key=key)
                else:
                    new_valor = coluna.text_input(campo, value=valor, key=key, disabled=not editar)

                if editar and new_valor != valor:
                    col_idx = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_idx, new_valor)

        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
