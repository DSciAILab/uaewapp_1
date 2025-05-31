# UAE Warriors App - v1.3.5
# ✅ Alterações:
# - Tabelas lado a lado com 3 colunas
# - Badges clicáveis quando toggle ativado
# - Lock por usuário com campo "LockBy"
# - Toggle em vez de botão "Editar"

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10000)

# 🔐 Conectar com Google Sheets
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

# 📌 Campos
campos_editaveis = [
    "Music_1", "Music_2", "Music_3", "Stats", "Weight", "Height", "Reach",
    "Fightstyle", "Nationality_Fight", "Residence", "Team", "Uniform", "Notes"
]
status_cols = ["Photoshoot", "Labs", "Interview", "Black_Screen"]

# 🔧 Utilitários
def salvar_valor(row_idx, col_idx, valor):
    try:
        sheet.update_cell(row_idx + 2, col_idx + 1, valor)
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def gerar_badge(valor, status):
    classe = {
        "done": "badge-done",
        "required": "badge-required"
    }.get(str(valor).strip().lower(), "badge-neutral")
    return f"<span class='badge {classe}'>{status.upper()}</span>"

def render_tabela(linhas, row):
    html = "<table class='custom-table'>"
    for linha in linhas:
        html += "<tr>"
        for col in linha:
            valor = str(row.get(col, ""))
            if col in ["Whatsapp", "Personal_Doc", "Passport"] and valor:
                if col == "Whatsapp":
                    link = f"https://wa.me/{valor.replace('+', '').replace(' ', '')}"
                else:
                    link = valor
                valor = f"<a href='{link}' target='_blank'>📎</a>"
            html += f"<td><b>{col.replace('_', ' ')}</b><br>{valor}</td>"
        html += "</tr>"
    html += "</table>"
    return html

# 🎨 Estilo
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.custom-table {
    border-collapse: collapse;
    width: 100%;
    text-align: center;
}
.custom-table td {
    border: 1px solid #444;
    padding: 6px;
    font-size: 0.8rem;
}
.stButton>button, .stTextInput>div>div>input {
    background-color: #262730;
    color: white;
    border: 1px solid #555;
}
.name-vermelho, .name-azul {
    font-weight: bold; font-size: 1.6rem;
}
.name-vermelho { color: red; }
.name-azul { color: #0099ff; }
.circle-img { width: 70px; height: 70px; border-radius: 50%; overflow: hidden; }
.circle-img img { width: 100%; height: 100%; object-fit: cover; }
.badge {
    padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700;
    margin: 0 4px; text-transform: uppercase; display: inline-block;
}
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.corner-vermelho, .corner-azul {
    background-color: rgba(255, 0, 0, 0.05); padding: 10px; border-radius: 10px;
}
.corner-azul { background-color: rgba(0, 153, 255, 0.05); }
.status-line { text-align: center; margin-bottom: 8px; }
.fight-info { text-align: center; color: #ccc; font-size: 0.9rem; margin-bottom: 8px; }
.wa-button { text-align: center; margin-bottom: 10px; }
.header-container {
    display: flex; align-items: center; justify-content: center;
    gap: 16px; margin-top: 20px; margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# 🧭 Filtros
st.sidebar.title("Filtros")
eventos = sorted(df["Event"].dropna().unique())
evento_sel = st.sidebar.selectbox("Evento", ["Todos"] + eventos)
corners = sorted(df["Corner"].dropna().unique())
corner_sel = st.sidebar.multiselect("Corner", corners, default=corners)
status_sel = st.sidebar.radio("Status", ["Todos", "Somente Pendentes", "Somente Completos"])
if st.sidebar.button("🔄 Atualizar"):
    st.rerun()

df = df[df["Role"] == "Fighter"]
if evento_sel != "Todos":
    df = df[df["Event"] == evento_sel]
if corner_sel:
    df = df[df["Corner"].isin(corner_sel)]
if status_sel == "Somente Pendentes":
    df = df[df[status_cols].apply(lambda r: "required" in r.str.lower().values, axis=1)]
elif status_sel == "Somente Completos":
    df = df[df[status_cols].apply(lambda r: all(v.lower().strip() == "done" for v in r), axis=1)]

df = df.sort_values(by=["Event", "Fight_Order", "Corner"])

# 👤 Atleta
def renderizar_atleta(i, row, df):
    corner = row.get("Corner", "").lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"
    tem_pendencia = any(str(row.get(s, "")).lower() == "required" for s in status_cols)
    icone_alerta = "⚠️ " if tem_pendencia else ""

    nome_html = f"<div class='{nome_class}'>{icone_alerta}{row.get('Name', '')}</div>"
    img_html = f"<div class='circle-img'><img src='{row.get('Image', '')}'></div>" if row.get("Image") else ""
    st.markdown(f"<div class='header-container'>{img_html}{nome_html}</div>", unsafe_allow_html=True)

    edit_key = f"edit_mode_{i}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    with st.expander("Exibir detalhes", expanded=st.session_state[edit_key]):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        usuario_atual = "admin"
        lock_idx = df.columns.get_loc("LockBy")
        lockado_por = row.get("LockBy", "").strip()
        bloqueado = bool(lockado_por and lockado_por != usuario_atual)
        toggle_key = f"toggle_{i}"

        if bloqueado:
            st.warning(f"⚠️ Este registro está sendo editado por outro usuário: {lockado_por}")
            toggle = False
        else:
            toggle = st.toggle("✏️ Editar informações", key=toggle_key)

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

        # Badges clicáveis
        st.markdown("<div class='status-line'>", unsafe_allow_html=True)
        for status in status_cols:
            val_atual = str(row.get(status, "")).lower()
            col_idx = df.columns.get_loc(status)
            if st.session_state[edit_key]:
                if st.button(status.upper(), key=f"{status}_{i}"):
                    novo = "done" if val_atual == "required" else "required"
                    salvar_valor(i, col_idx, novo)
                    st.rerun()
            else:
                st.markdown(gerar_badge(val_atual, status), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Tabelas
        c1, c2, c3 = st.columns(3)
        c1.markdown(render_tabela([["Fight_Order", "Corner", "Event", "Division"], ["Oponent", "Coach"]], row), unsafe_allow_html=True)
        c2.markdown(render_tabela([["Nationality_Passport", "Passport", "Personal_Doc"], ["DOB", "Whatsapp"]], row), unsafe_allow_html=True)
        c3.markdown(render_tabela([["Weight", "Height", "Reach"], ["Fightstyle", "Team", "Nationality_Fight"]], row), unsafe_allow_html=True)

        # Campos editáveis
        ed_cols = st.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            ed_cols[idx % 2].text_input(campo, value=row.get(campo, ""), key=f"{campo}_{i}", disabled=not st.session_state[edit_key])

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)

# 🏁 Renderizar atletas
st.title("UAE Warriors 59-60")
for i, row in df.iterrows():
    renderizar_atleta(i, row, df)
