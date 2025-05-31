import streamlit as st
st.set_page_config(page_title="UAEW Fighters", layout="wide")

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

# 🔄 Carrega dados e corrige nome da coluna 'CORNER'
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["original_index"] = df.index
    if "CORNER" in df.columns:
        df.rename(columns={"CORNER": "Coach"}, inplace=True)
    return df, sheet

# Atualiza valor individual em uma célula
def salvar_valor(sheet, row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar valor: linha {row+2}, coluna {col_index+1}: {e}")

# 🎨 Estilo visual
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.athlete-header { display: flex; justify-content: center; align-items: center; gap: 1rem; margin: 1rem 0; }
.avatar { border-radius: 50%; width: 65px; height: 65px; object-fit: cover; }
.name-tag { font-size: 1.8rem; font-weight: bold; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 3px; text-transform: uppercase; display: inline-block; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
table { width: 100%; border-collapse: collapse; text-align: center; }
th, td { padding: 4px 8px; border: 1px solid #444; text-align: center; }
</style>
""", unsafe_allow_html=True)

# Auto atualização a cada 10s
st_autorefresh(interval=10000, key="autorefresh")

# Carrega os dados da planilha
df, sheet = load_data()

# 🎛️ Filtros na barra lateral
with st.sidebar:
    st.header("Filtros")
    eventos = sorted(df['Event'].dropna().unique())
    evento_sel = st.selectbox("Evento", ["Todos"] + eventos)
    corner_sel = st.multiselect("Corner", ["Red", "Blue"])
    status_sel = st.radio("Status das tarefas", ["Todos", "Somente pendentes", "Somente completos"])

# Aplica filtros
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# Define tarefas válidas
tarefas_todas = ["Black Screen", "Photoshoot", "Blood Test", "Interview", "Stats"]
tarefas = [t for t in tarefas_todas if t in df.columns]

def is_required(row): return any(str(row.get(t, '')).lower() == "requested" for t in tarefas)
def is_done(row): return all(str(row.get(t, '')).lower() == "done" for t in tarefas)

if status_sel == "Somente pendentes":
    df = df[df.apply(is_required, axis=1)]
elif status_sel == "Somente completos":
    df = df[df.apply(is_done, axis=1)]

if "Role" in df.columns:
    df = df[df["Role"].str.lower() == "fighter"]

st.markdown(f"🔎 **{len(df)} atleta(s) encontrados com os filtros.**")
if df.empty:
    st.warning("Nenhum atleta encontrado.")
    st.stop()

# Texto clicável para tarefas
def render_tarefa_clickavel(tarefa, valor, idx, editar):
    classe = 'badge-required' if valor.lower() == 'requested' else 'badge-done'
    texto = tarefa.upper()
    html_id = f"tarefa_click_{tarefa}_{idx}"
    st.markdown(f"""
        <span class='badge {classe}' id='{html_id}'>{texto}</span>
        <script>
        const el = window.parent.document.getElementById('{html_id}');
        if (el && {str(editar).lower()}) {{
            el.style.cursor = 'pointer';
            el.onclick = () => {{
                const search = new URLSearchParams(window.location.search);
                search.set("clicked", "{html_id}");
                window.location.search = search.toString();
            }};
        }}
        </script>
    """, unsafe_allow_html=True)
    query = st.query_params
    return query.get("clicked", [""])[0] == html_id

# Exibição de cada atleta
for i, row in df.iterrows():
    with st.container():
        st.markdown(f"""
        <div class="athlete-header">
            <img class="avatar" src="{row.get('Image', 'https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png')}" />
            <div class="name-tag" style="color:{'#ff4b4b' if row.get('Corner', '').lower() == 'red' else '#0099ff'};">
                {('⚠️ ' if any(str(row.get(t, '')).lower() == 'requested' for t in tarefas) else '') + row.get('Name', '')}
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("Exibir detalhes"):

            editar = st.toggle("✏️ Editar informações", key=f"edit_toggle_{i}", value=row.get("LockBy") == "1724")

            try:
                headers = [h.strip() for h in sheet.row_values(1)]
            except Exception as e:
                st.error("❌ Erro ao acessar os cabeçalhos da planilha. Verifique a aba 'App' e permissões.")
                st.stop()

            lock_col_idx = headers.index("LockBy") if "LockBy" in headers else None

            if editar and lock_col_idx is not None and row.get("LockBy") != "1724":
                salvar_valor(sheet, row['original_index'], lock_col_idx, "1724")
            elif not editar and lock_col_idx is not None and row.get("LockBy") == "1724":
                salvar_valor(sheet, row['original_index'], lock_col_idx, "")

            if row.get("LockBy") not in ["", "1724"]:
                st.warning(f"🔒 Linha bloqueada por outro usuário: {row.get('LockBy')}")
                continue

            for t in tarefas:
                val_atual = str(row.get(t, ''))
                if render_tarefa_clickavel(t, val_atual, i, editar) and editar:
                    col_idx = headers.index(t)
                    novo_valor = 'done' if val_atual.lower() == 'requested' else 'requested'
                    salvar_valor(sheet, row['original_index'], col_idx, novo_valor)
                    st.experimental_rerun()

            # Informações complementares
            st.markdown(f"""
            <div style='display: flex; justify-content: space-between;'>
                <table><tr><th>Fight</th></tr><tr><td>{row.get('Fight Order', '')}</td></tr></table>
                <table><tr><th>Division</th></tr><tr><td>{row.get('Division', '')}</td></tr></table>
                <table><tr><th>Opponent</th></tr><tr><td>{row.get('Oponent', '')}</td></tr></table>
            </div>
            """, unsafe_allow_html=True)

            wpp = str(row.get("Whatsapp", "")).strip().replace("+", "").replace(" ", "")
            if wpp:
                st.markdown(f"<p style='text-align: center;'>📞 <a href='https://wa.me/{wpp}' target='_blank'>Enviar mensagem no WhatsApp</a></p>", unsafe_allow_html=True)

            st.markdown("""
            <div style='display: flex; gap: 2rem;'>
                <table><tr><th>Nationality</th><th>DOB</th><th>Passport</th></tr><tr><td>{}</td><td>{}</td><td>{}</td></tr></table>
                <table><tr><th>Arrival</th><th>Departure</th><th>Flight</th></tr><tr><td>{}</td><td>{}</td><td>{}</td></tr></table>
                <table><tr><th>Room</th></tr><tr><td>{}</td></tr></table>
            </div>
            """.format(
                row.get("Nationality", ""), row.get("DOB", ""), row.get("Passport", ""),
                row.get("Arrival Details", ""), row.get("Departure Details", ""),
                f"<a href='{row.get('Flight Ticket', '')}' target='_blank'>Ver passagem</a>" if str(row.get("Flight Ticket", "")).startswith("http") else "N/A",
                row.get("Booking Number / Room", "")
            ), unsafe_allow_html=True)

            campos_editaveis = ["Height", "Range", "Weight", "Country", "City", "Fight Style", "Team", "Uniform", "Notes", "Music 1", "Music 2", "Music 3"]
            col1, col2, col3 = st.columns(3)
            for idx, campo in enumerate(campos_editaveis):
                val = str(row.get(campo, ""))
                col = [col1, col2, col3][idx % 3]
                if campo == "Uniform":
                    novo_valor = col.selectbox(campo, ["", "Small", "Medium", "Large", "2X-Large"], index=["", "Small", "Medium", "Large", "2X-Large"].index(val) if val in ["Small", "Medium", "Large", "2X-Large"] else 0, key=f"{campo}_{i}", disabled=not editar)
                else:
                    novo_valor = col.text_input(campo, value=val, key=f"{campo}_{i}", disabled=not editar)
                if editar and novo_valor != val:
                    try:
                        col_idx = headers.index(campo)
                        salvar_valor(sheet, row['original_index'], col_idx, novo_valor)
                    except:
                        st.warning(f"⚠️ Coluna '{campo}' não encontrada.")
