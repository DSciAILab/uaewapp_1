# UAE Warriors App - v1.3.2

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# Configuração
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000)

# Estilo CSS
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
.stTextInput>div>div>input { background-color: #3a3b3c; color: white; border: 1px solid #888; text-align: center; }
.name-vermelho, .name-azul { font-weight: bold; font-size: 1.6rem; display: inline-block; }
.name-vermelho { color: red; }
.name-azul { color: #0099ff; }
.circle-img { width: 70px; height: 70px; border-radius: 50%; overflow: hidden; }
.circle-img img { width: 100%; height: 100%; object-fit: cover; }
.badge {
    padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700;
    margin: 0 3px; text-transform: uppercase; display: inline-block;
}
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.corner-vermelho { background-color: rgba(255, 0, 0, 0.1); border-radius: 10px; padding: 10px; }
.corner-azul { background-color: rgba(0, 153, 255, 0.1); border-radius: 10px; padding: 10px; }
hr.divisor { border: none; height: 1px; background: #333; margin: 20px 0; }
.status-line { text-align: center; margin-bottom: 8px; }
.fight-info { text-align: center; color: #ccc; font-size: 0.9rem; margin-bottom: 8px; }
.wa-button { text-align: center; margin-bottom: 10px; }
.header-container {
    display: flex; align-items: center; justify-content: center;
    gap: 16px; margin-top: 20px; margin-bottom: 10px;
}
.tabela-custom {
    width: 100%; border-collapse: collapse; margin-bottom: 8px;
}
.tabela-custom td {
    border: 1px solid #555; padding: 5px; text-align: center;
}
</style>
""", unsafe_allow_html=True)

# Autenticação com o Google Sheets
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("App")

sheet = connect_sheet()

@st.cache_data(ttl=30)
def load_data():
    return pd.DataFrame(sheet.get_all_records())

df = load_data()
df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "").str.replace("-", "_")
df["Fight_Order"] = pd.to_numeric(df["Fight_Order"], errors="coerce")

campos_editaveis = [
    "Music_1", "Music_2", "Music_3", "Stats", "Weight", "Height", "Reach",
    "Fightstyle", "Nationality_Fight", "Residence", "Team", "Uniform", "Notes"
]
status_cols = ["Photoshoot", "Labs", "Interview", "Black_Screen"]

def salvar_valor(row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")

def gerar_badge(valor, status):
    classe = {
        "done": "badge-done",
        "required": "badge-required"
    }.get(str(valor).strip().lower(), "badge-neutral")
    return f"<span class='badge {classe}'>{status.upper()}</span>"

def renderizar_atleta(i, row, df):
    corner = row.get("Corner", "").lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"
    tem_pendencia = any(str(row.get(status, "")).lower() == "required" for status in status_cols)
    icone_alerta = "⚠️ " if tem_pendencia else ""

    st.markdown(f"<div class='header-container'><div class='circle-img'><img src='{row.get('Image', '')}'></div><div class='{nome_class}'>{icone_alerta}{row.get('Name', '')}</div></div>", unsafe_allow_html=True)

    edit_key = f"edit_mode_{i}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    with st.expander("Exibir detalhes", expanded=st.session_state[edit_key]):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        # ⛳ BADGES
        badges_html = "".join(gerar_badge(row.get(status, ""), status) for status in status_cols)
        st.markdown(f"<div class='status-line'>{badges_html}</div>", unsafe_allow_html=True)

        # Tabelas lado a lado
        col1, col2, col3 = st.columns(3)

        with col1:
            tabela1 = f"""
            <table class="tabela-custom">
                <tr><td>{row.get("Fight_Order", "")}</td><td>{row.get("Corner", "")}</td><td>{row.get("Event", "")}</td></tr>
                <tr><td>{row.get("Oponent", "")}</td><td>{row.get("Division", "")}</td><td>{row.get("Coach", "")}</td></tr>
            </table>
            """
            st.markdown("<b>📊 Fight Details</b>", unsafe_allow_html=True)
            st.markdown(tabela1, unsafe_allow_html=True)

        with col2:
            dob = row.get("DOB", "")
            whatsapp = row.get("Whatsapp", "")
            whatsapp_link = f"<a href='https://wa.me/{whatsapp}' target='_blank'>{whatsapp}</a>" if whatsapp else ""
            docs_table = f"""
            <table class="tabela-custom">
                <tr><td>{row.get("Nationality_Passport", "")}</td><td>{row.get("Passport", "")}</td><td>{row.get("Personal_Doc", "")}</td></tr>
                <tr><td>{dob}</td><td colspan='2'>{whatsapp_link}</td></tr>
            </table>
            """
            st.markdown("<b>🧾 Documentos Pessoais</b>", unsafe_allow_html=True)
            st.markdown(docs_table, unsafe_allow_html=True)

        with col3:
            stats_table = f"""
            <table class="tabela-custom">
                <tr><td>{row.get("Weight", "")}</td><td>{row.get("Height", "")}</td><td>{row.get("Reach", "")}</td></tr>
                <tr><td>{row.get("Fightstyle", "")}</td><td>{row.get("Nationality_Fight", "")}</td><td>{row.get("Residence", "")}</td></tr>
            </table>
            """
            st.markdown("<b>💪 Dados Técnicos</b>", unsafe_allow_html=True)
            st.markdown(stats_table, unsafe_allow_html=True)

        # Lógica do toggle com LockBy
        usuario_atual = "admin"
        lockby_col_index = df.columns.get_loc("LockBy")
        lockado_por = row.get("LockBy", "").strip()
        toggle_key = f"toggle_{i}"
        bloqueado = bool(lockado_por and lockado_por != usuario_atual)

        toggle = st.toggle("✏️ Editar informações", key=toggle_key, disabled=bloqueado)
        if toggle and not st.session_state[edit_key]:
            if not lockado_por or lockado_por == usuario_atual:
                salvar_valor(i, lockby_col_index, usuario_atual)
                st.session_state[edit_key] = True
            else:
                st.warning(f"⚠️ Registro em uso por {lockado_por}")
        elif not toggle and st.session_state[edit_key]:
            with st.spinner("Salvando..."):
                for campo in campos_editaveis:
                    novo_valor = st.session_state.get(f"{campo}_{i}", "")
                    if campo in df.columns:
                        salvar_valor(i, df.columns.get_loc(campo), novo_valor)
                salvar_valor(i, lockby_col_index, "")  # Libera edição
            st.success("Salvo com sucesso!")
            st.session_state[edit_key] = False
            st.rerun()

        # Campos editáveis
        if st.session_state[edit_key]:
            col1, col2 = st.columns(2)
            for idx, campo in enumerate(campos_editaveis):
                (col1 if idx % 2 == 0 else col2).text_input(campo, value=row.get(campo, ""), key=f"{campo}_{i}")

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)

# Filtros
st.sidebar.title("Filtros")
eventos = sorted(df["Event"].dropna().unique())
evento_sel = st.sidebar.selectbox("Selecionar Evento", ["Todos"] + eventos)
corners = sorted(df["Corner"].dropna().unique())
corner_sel = st.sidebar.multiselect("Selecionar Corner", options=corners, default=corners)
status_sel = st.sidebar.radio("Status", ["Todos", "Somente Pendentes", "Somente Completos"])

df = df[df["Role"] == "Fighter"]
if evento_sel != "Todos": df = df[df["Event"] == evento_sel]
if corner_sel: df = df[df["Corner"].isin(corner_sel)]
if status_sel == "Somente Pendentes":
    df = df[df[status_cols].apply(lambda r: "required" in r.str.lower().values, axis=1)]
elif status_sel == "Somente Completos":
    df = df[df[status_cols].apply(lambda r: all(str(v).lower() == "done" for v in r), axis=1)]

df = df.sort_values(by=["Event", "Fight_Order", "Corner"])

if st.sidebar.button("🔄 Atualizar Página"): st.rerun()
st.title("UAE Warriors - Controle de Atletas")
for i, row in df.iterrows():
    renderizar_atleta(i, row, df)
