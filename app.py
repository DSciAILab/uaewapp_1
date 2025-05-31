# 🔹 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.54

### Novidades desta versão:
- Renderização dos cards de atleta novamente incluída com layout aprovado na versão 1.1.29
- Layout com imagem circular ao lado do nome, ambos centralizados
- Tarefas, detalhes da luta e WhatsApp no topo do expander
- Conteúdo reorganizado em blocos: Tarefas, Detalhes Pessoais, Logística, Hotel e Campos Editáveis
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
    #if "CORNER" in df.columns:
    #    df.rename(columns={"CORNER": "Coach"}, inplace=True)
    #return df, sheet

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

# 🗓️ Título
df, sheet = load_data()

# 🔍 Filtros no Sidebar
with st.sidebar:
    st.header("Filtros")
    eventos = sorted(df['Event'].dropna().unique())
    corners = sorted(df['Corner'].dropna().unique())
    evento_sel = st.selectbox("Evento", ["Todos"] + eventos)
    corner_sel = st.multiselect("Corner", corners)
    status_sel = st.radio("Status das tarefas", ["Todos", "Somente pendentes", "Somente completos"])

# Aplicar filtros
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# Verifica colunas de tarefas válidas
tarefas_todas = ["Black Screen", "Video Status", "Photoshoot", "Blood Test", "Interview", "Stats"]
tarefas = [t for t in tarefas_todas if t in df.columns]

if status_sel == "Somente pendentes":
    df = df[df[tarefas].apply(lambda row: any(str(row.get(t, '')).lower() == "required" for t in tarefas), axis=1)]
elif status_sel == "Somente completos":
    df = df[df[tarefas].apply(lambda row: all(str(row.get(t, '')).lower() == "done" for t in tarefas), axis=1)]

# Foco em lutadores
df = df[df['Role'].str.lower() == 'fighter']

# ✅ Avisos e contagem
st.markdown(f"🔎 **{len(df)} atleta(s) encontrados para os filtros aplicados.**")

if df.empty:
    st.warning("Nenhum atleta encontrado com os filtros selecionados.")
    st.stop()

# 👊 Renderiza cards por atleta
for i, row in df.iterrows():
    with st.container():
        st.markdown("""
        <div class="athlete-header">
            <img class="avatar" src="{img}" />
            <div class="name-tag" style="color:{cor};">{nome}</div>
        </div>
        """.format(
            img=row.get("Image", "https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png"),
            nome=("\u26a0\ufe0f " if any(str(row.get(t, '')).lower() == "required" for t in tarefas) else "") + row.get("Name", ""),
            cor="#ff4b4b" if row.get("Corner", "").lower() == "red" else "#0099ff"
        ), unsafe_allow_html=True)

        with st.expander("Exibir detalhes"):
            # Pendências
            st.markdown(" ".join([
                f"<span class='badge {('badge-required' if str(row[t]).lower()=='required' else ('badge-done' if str(row[t]).lower()=='done' else 'badge-neutral'))}'>{t.upper()}</span>"
                for t in tarefas
            ]), unsafe_allow_html=True)

            # Detalhes da luta
            st.markdown(f"<p style='text-align: center; margin-top: 0.5rem;'>Fight {row.get('Fight Order')} | {row.get('Division')} | Opponent {row.get('Oponent')}</p>", unsafe_allow_html=True)

            # WhatsApp
            wpp = str(row.get("Whatsapp", "")).strip().replace("+", "").replace(" ", "")
            if wpp:
                st.markdown(f"<p style='text-align: center;'>📞 <a href='https://wa.me/{wpp}' target='_blank'>Enviar mensagem no WhatsApp</a></p>", unsafe_allow_html=True)

            # Detalhes pessoais em tabela
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

            # Campos editáveis
            campos_editaveis = [
                "Height", "Range", "Weight",
                "Country", "City", "Fight Style",
                "Team", "Uniform", "Notes",
                "Music 1", "Music 2", "Music 3"
            ]
            edit_key = f"edit_{i}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False
            col_ed = st.columns(2)
            if st.session_state[edit_key]:
                st.button("Salvar", key=f"salvar_{i}")
                col1, col2, col3 = st.columns(3)
                for idx, campo in enumerate(campos_editaveis):
                    val = str(row.get(campo, ""))
                    col = [col1, col2, col3][idx % 3]
                    if campo == "Uniform":
                        novo_valor = col.selectbox(campo, ["", "Small", "Medium", "Large", "2X-Large"], index=["", "Small", "Medium", "Large", "2X-Large"].index(val) if val in ["Small", "Medium", "Large", "2X-Large"] else 0, key=f"{campo}_{i}")
                    else:
                        novo_valor = col.text_input(campo, value=val, key=f"{campo}_{i}")
                    if novo_valor != val:
                        col_idx = df.columns.get_loc(campo)
                        salvar_valor(sheet, i, col_idx, novo_valor)
            else:
                if st.button("Editar", key=f"editar_{i}"):
                    st.session_state[edit_key] = True
