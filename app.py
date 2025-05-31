# 🔹 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.56

### Novidades desta versão:
- Comentários linha a linha adicionados
- Filtro "Corner" agora só permite seleção entre "Red" e "Blue"
- Campo "Editar" agora usa `st.toggle` para destravar as caixas
"""

# 🔑 Importações necessárias
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

# 🔄 Carrega dados e corrige nomes duplicados
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["original_index"] = df.index
    if "CORNER" in df.columns:
        df.rename(columns={"CORNER": "Coach"}, inplace=True)
    return df, sheet

# 📂 Atualiza valores de célula individual
def salvar_valor(sheet, row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar valor em linha {row+2}, coluna {col_index+1}: {e}")

# ⚙️ Configuração inicial da página
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10000, key="autorefresh")

# 🎨 Estilo customizado em HTML e CSS
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.athlete-header { display: flex; justify-content: center; align-items: center; gap: 1rem; margin: 1rem 0; }
.avatar { border-radius: 50%; width: 65px; height: 65px; object-fit: cover; }
.name-tag { font-size: 1.8rem; font-weight: bold; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 3px; text-transform: uppercase; display: inline-block; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
table { width: 100%; margin: 5px 0; }
th, td { text-align: left; padding: 4px 8px; }
th { font-weight: bold; }
.section-label { font-weight: bold; margin-top: 1rem; font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

# 🗂️ Carrega dados e exibe título
df, sheet = load_data()

# 🔍 Filtros no Sidebar
with st.sidebar:
    st.header("Filtros")
    eventos = sorted(df['Event'].dropna().unique())
    evento_sel = st.selectbox("Evento", ["Todos"] + eventos)
    corner_sel = st.multiselect("Corner", ["Red", "Blue"])
    status_sel = st.radio("Status das tarefas", ["Todos", "Somente pendentes", "Somente completos"])

# 🎯 Aplica os filtros ao DataFrame
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

tarefas_todas = ["Black Screen", "Video Status", "Photoshoot", "Blood Test", "Interview", "Stats"]
tarefas = [t for t in tarefas_todas if t in df.columns]

if status_sel == "Somente pendentes":
    df = df[df[tarefas].apply(lambda row: any(str(row.get(t, '')).lower() == "required" for t in tarefas), axis=1)]
elif status_sel == "Somente completos":
    df = df[df[tarefas].apply(lambda row: all(str(row.get(t, '')).lower() == "done" for t in tarefas), axis=1)]

# 🎭 Exibir apenas lutadores
if "ROLE" in df.columns:
    df = df[df['ROLE'].str.lower() == 'fighter']

# 📌 Contagem
st.markdown(f"🔎 **{len(df)} atleta(s) encontrados para os filtros aplicados.**")

if df.empty:
    st.warning("Nenhum atleta encontrado com os filtros selecionados.")
    st.stop()

# 👤 Exibição de cada atleta
for i, row in df.iterrows():
    with st.container():
        st.markdown("""
        <div class="athlete-header">
            <img class="avatar" src="{}" />
            <div class="name-tag" style="color:{};">{}</div>
        </div>
        """.format(
            row.get("Image", "https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png"),
            "#ff4b4b" if row.get("Corner", "").lower() == "red" else "#0099ff",
            ("⚠️ " if any(str(row.get(t, '')).lower() == "required" for t in tarefas) else "") + row.get("Name", "")
        ), unsafe_allow_html=True)

        with st.expander("Exibir detalhes"):
            st.markdown(" ".join([
                f"<span class='badge {('badge-required' if str(row[t]).lower()=='required' else ('badge-done' if str(row[t]).lower()=='done' else 'badge-neutral'))}'>" + t.upper() + "</span>"
                for t in tarefas
            ]), unsafe_allow_html=True)

            st.markdown(f"<p style='text-align: center; margin-top: 0.5rem;'>Fight {row.get('Fight Order')} | {row.get('Division')} | Opponent {row.get('Oponent')}</p>", unsafe_allow_html=True)

            wpp = str(row.get("Whatsapp", "")).strip().replace("+", "").replace(" ", "")
            if wpp:
                st.markdown(f"<p style='text-align: center;'>📞 <a href='https://wa.me/{wpp}' target='_blank'>Enviar mensagem no WhatsApp</a></p>", unsafe_allow_html=True)

            st.markdown("""
            <div style='display: flex; gap: 2rem;'>
            <table>
                <tr><th>Nationality</th><th>DOB</th><th>Passport</th></tr>
                <tr><td>{}</td><td>{}</td><td>{}</td></tr>
            </table>
            <table>
                <tr><th>Arrival</th><th>Departure</th><th>Flight</th></tr>
                <tr><td>{}</td><td>{}</td><td>{}</td></tr>
            </table>
            <table>
                <tr><th>Room</th></tr>
                <tr><td>{}</td></tr>
            </table>
            </div>
            """.format(
                row.get("Nationality", ""), row.get("DOB", ""), row.get("Passport", ""),
                row.get("Arrival Details", ""), row.get("Departure Details", ""),
                f"<a href='{row.get('Flight Ticket', '')}' target='_blank'>Ver passagem</a>" if row.get("Flight Ticket", "").startswith("http") else "Passagem não disponível",
                row.get("Booking Number / Room", "")
            ), unsafe_allow_html=True)

            campos_editaveis = [
                "Height", "Range", "Weight",
                "Country", "City", "Fight Style",
                "Team", "Uniform", "Notes",
                "Music 1", "Music 2", "Music 3"
            ]

            toggle_key = f"edit_toggle_{i}"
            editar = st.toggle("✏️ Editar informações", key=toggle_key)

            col1, col2, col3 = st.columns(3)
            for idx, campo in enumerate(campos_editaveis):
                val = str(row.get(campo, ""))
                col = [col1, col2, col3][idx % 3]
                if campo == "Uniform":
                    novo_valor = col.selectbox(campo, ["", "Small", "Medium", "Large", "2X-Large"], index=["", "Small", "Medium", "Large", "2X-Large"].index(val) if val in ["Small", "Medium", "Large", "2X-Large"] else 0, key=f"{campo}_{i}", disabled=not editar)
                else:
                    novo_valor = col.text_input(campo, value=val, key=f"{campo}_{i}", disabled=not editar)
                if editar and novo_valor != val:
                    col_idx = sheet.row_values(1).index(campo)
                    salvar_valor(sheet, row['original_index'], col_idx, novo_valor)
