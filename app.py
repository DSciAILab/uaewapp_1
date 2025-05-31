import streamlit as st
st.set_page_config(page_title="UAEW Fighters", layout="wide")

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

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

@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df["original_index"] = df.index
    return df, sheet

def salvar_valor(sheet, row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar valor: linha {row+2}, coluna {col_index+1}: {e}")

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

st_autorefresh(interval=10000, key="autorefresh")

df, sheet = load_data()

with st.sidebar:
    st.header("Filtros")
    eventos = sorted(df['Event'].dropna().unique())
    evento_sel = st.selectbox("Evento", ["Todos"] + eventos)
    corner_sel = st.multiselect("Corner", ["Red", "Blue"])
    status_sel = st.radio("Status das tarefas", ["Todos", "Somente pendentes", "Somente completos"])

if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

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
                st.error("❌ Erro ao acessar os cabeçalhos da planilha.")
                st.code(str(e))  # <--- Exibe mensagem detalhada
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
