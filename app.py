# UAE Warriors App - v1.3.6
# ✅ Novidades:
# - Badges clicáveis com visual preservado (HTML + st.form)
# - Toggle de edição com bloqueio
# - Três tabelas organizadas lado a lado
# - Filtros, ordenação, e campos editáveis

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🔧 Configuração da página
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000)

# 🔐 Conexão com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open("UAEW_App").worksheet("App")

sheet = connect_sheet()

@st.cache_data(ttl=30)
def load_data():
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "").str.replace("-", "_")
    df["Fight_Order"] = pd.to_numeric(df["Fight_Order"], errors="coerce")
    return df

df = load_data()

campos_editaveis = [
    "Music_1", "Music_2", "Music_3", "Stats", "Weight", "Height", "Reach",
    "Fightstyle", "Nationality_Fight", "Residence", "Team", "Uniform", "Notes"
]
status_cols = ["Photoshoot", "Labs", "Interview", "Black_Screen"]

# 🔧 Utilidades
def salvar_valor(row_idx, col_idx, valor):
    try:
        sheet.update_cell(row_idx + 2, col_idx + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def gerar_badge_html(valor, status):
    classe = {
        "done": "badge-done",
        "required": "badge-required"
    }.get(valor.strip().lower(), "badge-neutral")
    return f"<span class='badge {classe}'>{status.upper()}</span>"

def render_tabela(linhas, row):
    html = "<table class='custom-table'>"
    for linha in linhas:
        html += "<tr>"
        for campo in linha:
            valor = str(row.get(campo, ""))
            if campo == "Whatsapp" and valor:
                valor = f"<a href='https://wa.me/{valor.replace('+','').replace(' ','')}' target='_blank'>{valor}</a>"
            elif campo == "Personal_Doc" and valor:
                valor = f"<a href='{valor}' target='_blank'>📎</a>"
            html += f"<td><b>{campo.replace('_', ' ')}</b><br>{valor}</td>"
        html += "</tr>"
    html += "</table>"
    return html

# 🎨 Estilo
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.custom-table {
    border-collapse: collapse; width: 100%; text-align: center; margin-bottom: 12px;
}
.custom-table td {
    border: 1px solid #444; padding: 6px; font-size: 0.85rem; text-align: center;
}
.stButton>button, .stTextInput>div>div>input {
    background-color: #262730; color: white; border: 1px solid #555;
}
.name-vermelho, .name-azul {
    font-weight: bold; font-size: 1.6rem;
}
.name-vermelho { color: red; }
.name-azul { color: #0099ff; }
.circle-img { width: 70px; height: 70px; border-radius: 50%; overflow: hidden; }
.circle-img img { width: 100%; height: 100%; object-fit: cover; }
.badge {
    padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 700;
    text-transform: uppercase; display: inline-block;
}
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.status-line { text-align: center; margin-bottom: 12px; display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }
.header-container {
    display: flex; align-items: center; justify-content: center;
    gap: 16px; margin-top: 20px; margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# 🧭 Filtros
st.sidebar.title("Filtros")
evento_sel = st.sidebar.selectbox("Evento", ["Todos"] + sorted(df['Event'].dropna().unique()))
corner_sel = st.sidebar.multiselect("Corner", sorted(df['Corner'].dropna().unique()))
status_sel = st.sidebar.radio("Status", ["Todos", "Somente Pendentes", "Somente Completos"])
if st.sidebar.button("🔄 Atualizar Página"):
    st.rerun()

df = df[df["Role"] == "Fighter"]
if evento_sel != "Todos":
    df = df[df["Event"] == evento_sel]
if corner_sel:
    df = df[df["Corner"].isin(corner_sel)]
if status_sel == "Somente Pendentes":
    df = df[df[status_cols].apply(lambda row: "required" in row.str.lower().values, axis=1)]
elif status_sel == "Somente Completos":
    df = df[df[status_cols].apply(lambda row: all(val.strip().lower() == "done" for val in row.values), axis=1)]

df = df.sort_values(by=["Event", "Fight_Order", "Corner"])

# 👤 Atleta
def renderizar_atleta(i, row, df):
    corner = row.get("Corner", "").lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"
    icone_alerta = "⚠️ " if any(str(row.get(s, "")).lower() == "required" for s in status_cols) else ""

    st.markdown(f"<div class='header-container'><div class='circle-img'><img src='{row.get('Image', '')}'></div><div class='{nome_class}'>{icone_alerta}{row.get('Name', '')}</div></div>", unsafe_allow_html=True)

    edit_key = f"edit_mode_{i}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    with st.expander("Exibir detalhes", expanded=st.session_state[edit_key]):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        usuario_atual = "admin"
        lock_idx = df.columns.get_loc("LockBy")
        lockado_por = row.get("LockBy", "").strip()
        bloqueado = bool(lockado_por and lockado_por != usuario_atual)

        if bloqueado:
            st.warning(f"⚠️ Este registro está sendo editado por outro usuário: {lockado_por}")
            toggle = False
        else:
            toggle = st.toggle("✏️ Editar informações", key=f"toggle_{i}")

        if toggle and not st.session_state[edit_key]:
            salvar_valor(i, lock_idx, usuario_atual)
            st.session_state[edit_key] = True

        elif not toggle and st.session_state[edit_key]:
            for campo in campos_editaveis:
                novo_valor = st.session_state.get(f"{campo}_{i}", "")
                if campo in df.columns:
                    salvar_valor(i, df.columns.get_loc(campo), novo_valor)
            salvar_valor(i, lock_idx, "")
            st.success("Salvo com sucesso!")
            st.session_state[edit_key] = False
            st.rerun()

        # 🟢 Badges interativos com visual HTML
        st.markdown("<div class='status-line'>", unsafe_allow_html=True)
        for status in status_cols:
            val_atual = str(row.get(status, "")).strip().lower()
            badge_class = {
                "done": "badge-done",
                "required": "badge-required"
            }.get(val_atual, "badge-neutral")
            if st.session_state[edit_key]:
                with st.form(key=f"form_{i}_{status}", clear_on_submit=True):
                    badge_html = f"<button type='submit' class='badge {badge_class}' style='border:none;background:transparent;'>{status.upper()}</button>"
                    st.markdown(badge_html, unsafe_allow_html=True)
                    if st.form_submit_button(label=""):
                        novo = "done" if val_atual == "required" else "required"
                        salvar_valor(i, df.columns.get_loc(status), novo)
                        st.rerun()
            else:
                st.markdown(f"<span class='badge {badge_class}'>{status.upper()}</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Tabelas laterais
        c1, c2, c3 = st.columns(3)
        c1.markdown(render_tabela([["Fight_Order", "Corner", "Event", "Division"], ["Oponent", "Coach"]], row), unsafe_allow_html=True)
        c2.markdown(render_tabela([["Nationality_Passport", "Passport", "Personal_Doc"], ["DOB", "Whatsapp"]], row), unsafe_allow_html=True)
        c3.markdown(render_tabela([["Weight", "Height", "Reach"], ["Fightstyle", "Team", "Nationality_Fight"]], row), unsafe_allow_html=True)

        if st.session_state[edit_key]:
            col1, col2 = st.columns(2)
            for idx, campo in enumerate(campos_editaveis):
                (col1 if idx % 2 == 0 else col2).text_input(
                    campo, value=row.get(campo, ""), key=f"{campo}_{i}"
                )

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)

# ▶️ Página principal
st.title("UAE Warriors 59-60")
for i, row in df.iterrows():
    renderizar_atleta(i, row, df)
# UAE Warriors App - v1.3.6
# ✅ Novidades:
# - Badges clicáveis com visual preservado (HTML + st.form)
# - Toggle de edição com bloqueio
# - Três tabelas organizadas lado a lado
# - Filtros, ordenação, e campos editáveis

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🔧 Configuração da página
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000)

# 🔐 Conexão com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open("UAEW_App").worksheet("App")

sheet = connect_sheet()

@st.cache_data(ttl=30)
def load_data():
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "").str.replace("-", "_")
    df["Fight_Order"] = pd.to_numeric(df["Fight_Order"], errors="coerce")
    return df

df = load_data()

campos_editaveis = [
    "Music_1", "Music_2", "Music_3", "Stats", "Weight", "Height", "Reach",
    "Fightstyle", "Nationality_Fight", "Residence", "Team", "Uniform", "Notes"
]
status_cols = ["Photoshoot", "Labs", "Interview", "Black_Screen"]

# 🔧 Utilidades
def salvar_valor(row_idx, col_idx, valor):
    try:
        sheet.update_cell(row_idx + 2, col_idx + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def gerar_badge_html(valor, status):
    classe = {
        "done": "badge-done",
        "required": "badge-required"
    }.get(valor.strip().lower(), "badge-neutral")
    return f"<span class='badge {classe}'>{status.upper()}</span>"

def render_tabela(linhas, row):
    html = "<table class='custom-table'>"
    for linha in linhas:
        html += "<tr>"
        for campo in linha:
            valor = str(row.get(campo, ""))
            if campo == "Whatsapp" and valor:
                valor = f"<a href='https://wa.me/{valor.replace('+','').replace(' ','')}' target='_blank'>{valor}</a>"
            elif campo == "Personal_Doc" and valor:
                valor = f"<a href='{valor}' target='_blank'>📎</a>"
            html += f"<td><b>{campo.replace('_', ' ')}</b><br>{valor}</td>"
        html += "</tr>"
    html += "</table>"
    return html

# 🎨 Estilo
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.custom-table {
    border-collapse: collapse; width: 100%; text-align: center; margin-bottom: 12px;
}
.custom-table td {
    border: 1px solid #444; padding: 6px; font-size: 0.85rem; text-align: center;
}
.stButton>button, .stTextInput>div>div>input {
    background-color: #262730; color: white; border: 1px solid #555;
}
.name-vermelho, .name-azul {
    font-weight: bold; font-size: 1.6rem;
}
.name-vermelho { color: red; }
.name-azul { color: #0099ff; }
.circle-img { width: 70px; height: 70px; border-radius: 50%; overflow: hidden; }
.circle-img img { width: 100%; height: 100%; object-fit: cover; }
.badge {
    padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 700;
    text-transform: uppercase; display: inline-block;
}
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.status-line { text-align: center; margin-bottom: 12px; display: flex; justify-content: center; gap: 8px; flex-wrap: wrap; }
.header-container {
    display: flex; align-items: center; justify-content: center;
    gap: 16px; margin-top: 20px; margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# 🧭 Filtros
st.sidebar.title("Filtros")
evento_sel = st.sidebar.selectbox("Evento", ["Todos"] + sorted(df['Event'].dropna().unique()))
corner_sel = st.sidebar.multiselect("Corner", sorted(df['Corner'].dropna().unique()))
status_sel = st.sidebar.radio("Status", ["Todos", "Somente Pendentes", "Somente Completos"])
if st.sidebar.button("🔄 Atualizar Página"):
    st.rerun()

df = df[df["Role"] == "Fighter"]
if evento_sel != "Todos":
    df = df[df["Event"] == evento_sel]
if corner_sel:
    df = df[df["Corner"].isin(corner_sel)]
if status_sel == "Somente Pendentes":
    df = df[df[status_cols].apply(lambda row: "required" in row.str.lower().values, axis=1)]
elif status_sel == "Somente Completos":
    df = df[df[status_cols].apply(lambda row: all(val.strip().lower() == "done" for val in row.values), axis=1)]

df = df.sort_values(by=["Event", "Fight_Order", "Corner"])

# 👤 Atleta
def renderizar_atleta(i, row, df):
    corner = row.get("Corner", "").lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"
    icone_alerta = "⚠️ " if any(str(row.get(s, "")).lower() == "required" for s in status_cols) else ""

    st.markdown(f"<div class='header-container'><div class='circle-img'><img src='{row.get('Image', '')}'></div><div class='{nome_class}'>{icone_alerta}{row.get('Name', '')}</div></div>", unsafe_allow_html=True)

    edit_key = f"edit_mode_{i}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    with st.expander("Exibir detalhes", expanded=st.session_state[edit_key]):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        usuario_atual = "admin"
        lock_idx = df.columns.get_loc("LockBy")
        lockado_por = row.get("LockBy", "").strip()
        bloqueado = bool(lockado_por and lockado_por != usuario_atual)

        if bloqueado:
            st.warning(f"⚠️ Este registro está sendo editado por outro usuário: {lockado_por}")
            toggle = False
        else:
            toggle = st.toggle("✏️ Editar informações", key=f"toggle_{i}")

        if toggle and not st.session_state[edit_key]:
            salvar_valor(i, lock_idx, usuario_atual)
            st.session_state[edit_key] = True

        elif not toggle and st.session_state[edit_key]:
            for campo in campos_editaveis:
                novo_valor = st.session_state.get(f"{campo}_{i}", "")
                if campo in df.columns:
                    salvar_valor(i, df.columns.get_loc(campo), novo_valor)
            salvar_valor(i, lock_idx, "")
            st.success("Salvo com sucesso!")
            st.session_state[edit_key] = False
            st.rerun()

        # 🟢 Badges interativos com visual HTML
        st.markdown("<div class='status-line'>", unsafe_allow_html=True)
        for status in status_cols:
            val_atual = str(row.get(status, "")).strip().lower()
            badge_class = {
                "done": "badge-done",
                "required": "badge-required"
            }.get(val_atual, "badge-neutral")
            if st.session_state[edit_key]:
                with st.form(key=f"form_{i}_{status}", clear_on_submit=True):
                    badge_html = f"<button type='submit' class='badge {badge_class}' style='border:none;background:transparent;'>{status.upper()}</button>"
                    st.markdown(badge_html, unsafe_allow_html=True)
                    if st.form_submit_button(label=""):
                        novo = "done" if val_atual == "required" else "required"
                        salvar_valor(i, df.columns.get_loc(status), novo)
                        st.rerun()
            else:
                st.markdown(f"<span class='badge {badge_class}'>{status.upper()}</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Tabelas laterais
        c1, c2, c3 = st.columns(3)
        c1.markdown(render_tabela([["Fight_Order", "Corner", "Event", "Division"], ["Oponent", "Coach"]], row), unsafe_allow_html=True)
        c2.markdown(render_tabela([["Nationality_Passport", "Passport", "Personal_Doc"], ["DOB", "Whatsapp"]], row), unsafe_allow_html=True)
        c3.markdown(render_tabela([["Weight", "Height", "Reach"], ["Fightstyle", "Team", "Nationality_Fight"]], row), unsafe_allow_html=True)

        if st.session_state[edit_key]:
            col1, col2 = st.columns(2)
            for idx, campo in enumerate(campos_editaveis):
                (col1 if idx % 2 == 0 else col2).text_input(
                    campo, value=row.get(campo, ""), key=f"{campo}_{i}"
                )

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)

# ▶️ Página principal
st.title("UAE Warriors 59-60")
for i, row in df.iterrows():
    renderizar_atleta(i, row, df)
