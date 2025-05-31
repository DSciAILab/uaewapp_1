# 🔹 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.50

### Novidades desta versão:
- Estruturado três blocos lado a lado: Detalhes Pessoais | Logística | Hotel
- Corrigido layout com caixas editáveis de música
- Corrigido salvamento com mensagens de erro descritivas e seguras
- Melhoria visual nas seções logísticas e links com hyperlink
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
    df["original_index"] = df.index
    return df, sheet

# 📂 Atualiza valores
def salvar_valor(sheet, row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar valor em linha {row+2}, coluna {col_index+1}: {e}")

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
table { width: 100%; margin: 5px 0; }
th, td { text-align: left; padding: 4px 8px; }
th { font-weight: bold; }
.section-label { font-weight: bold; margin-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# 🗓️ Título
st.title("UAE Warriors 59-60")
df, sheet = load_data()

# 🔍 Filtros
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())
col_evento, col_corner = st.columns(2)
evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
corner_sel = col_corner.multiselect("Corner", corners)
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

df = df[df['ROLE'].str.lower() == 'fighter']
tarefas = ["Black Screen", "Video Status", "Photoshoot", "Blood Test", "Interview", "Stats"]

# 👤 Cards
for j, row in df.iterrows():
    i = int(row["original_index"])
    cor = "#ff4b4b" if row.get("Corner", "").lower() == "red" else "#0099ff"
    alerta = "⚠️ " if any(str(row.get(t, "")).lower() == "required" for t in tarefas) else ""
    nome_html = f"""
    <div class='athlete-header'>
        <img class='avatar' src='{row.get("Image", "")}'/>
        <span class='name-tag' style='color: {cor};'>{alerta}{row['Name']}</span>
    </div>"""
    st.markdown(nome_html, unsafe_allow_html=True)

    editar = st.toggle("Editar dados", key=f"editar_{i}")
    with st.expander("Exibir detalhes"):
        st.markdown(" ".join([f"<span class='badge {('badge-required' if str(row.get(t, '')).lower()=='required' else ('badge-done' if str(row.get(t, '')).lower()=='done' else 'badge-neutral'))}'>{t.upper()}</span>" for t in tarefas]), unsafe_allow_html=True)

        st.markdown(f"<div style='text-align:center;'>Fight {row['Fight Order']} | {row['Division']} | Opponent {row['Oponent']}</div>", unsafe_allow_html=True)
        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            st.markdown(f"<div style='text-align: center;'><a href='{link}' target='_blank'>📱 Enviar mensagem no WhatsApp</a></div>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        col1.markdown("<div class='section-label'>Detalhes Pessoais</div>", unsafe_allow_html=True)
        col1.markdown(f"""
        <table>
        <tr><th>Nationality</th><th>DOB</th><th>Passport</th></tr>
        <tr><td>{row['Nationality']}</td><td>{row['DOB']}</td><td>{row['Passport']}</td></tr>
        </table>""", unsafe_allow_html=True)

        col2.markdown("<div class='section-label'>Logística</div>", unsafe_allow_html=True)
        col2.markdown(f"<b>Arrival:</b> {row['Arrival Details']}", unsafe_allow_html=True)
        col2.markdown(f"<b>Departure:</b> {row['Departure Details']}", unsafe_allow_html=True)
        ticket = row['Flight Ticket']
        if ticket:
            col2.markdown(f"<a href='{ticket}' target='_blank'>🌍 Ver passagem</a>", unsafe_allow_html=True)

        col3.markdown("<div class='section-label'>Hotel</div>", unsafe_allow_html=True)
        col3.markdown(f"Room: {row['Booking Number / Room']}")

        st.markdown("<hr style='border-top:1px solid #444;'>", unsafe_allow_html=True)

        campos = [c for c in ["Height", "Range", "Weight", "Country", "City", "Fight Style", "Team", "Uniform", "Music 1", "Music 2", "Music 3", "Notes"] if c in df.columns]
        col1, col2, col3 = st.columns(3)
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

    st.markdown("<hr style='border-top: 1px solid #666;'>", unsafe_allow_html=True)
