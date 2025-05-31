# 📍 UAE Warriors App - v1.4.0
# ✅ Melhorias:
# - Correção do selectbox de Uniform sem valor padrão forçado
# - Centralização vertical dos textos das tabelas
# - Badge toggle funcionando corretamente
# - Layout mantido conforme solicitado

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")

# 🎨 Estilo visual
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.name-vermelho, .name-azul {
    font-weight: bold; font-size: 1.6rem; display: inline-block;
}
.name-vermelho { color: red; }
.name-azul { color: #0099ff; }
.circle-img { width: 70px; height: 70px; border-radius: 50%; overflow: hidden; }
.circle-img img { width: 100%; height: 100%; object-fit: cover; }
.badge {
    padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700;
    margin: 0 5px; text-transform: uppercase; display: inline-block;
}
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.corner-vermelho { background-color: rgba(255, 0, 0, 0.1); border-radius: 10px; padding: 10px; }
.corner-azul { background-color: rgba(0, 153, 255, 0.1); border-radius: 10px; padding: 10px; }
hr.divisor { border: none; height: 1px; background: #333; margin: 20px 0; }
.header-container {
    display: flex; align-items: center; justify-content: center;
    gap: 16px; margin-top: 20px; margin-bottom: 10px;
}
table.custom-table {
    width: 100%; border-collapse: collapse; margin-bottom: 15px;
}
table.custom-table td {
    border: 1px solid #555; padding: 6px 10px; font-size: 0.85rem;
    text-align: center; vertical-align: middle;
}
table.custom-table td.title {
    font-weight: bold; background-color: #222; color: #ddd;
}
</style>
""", unsafe_allow_html=True)

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

def render_tabela_fight(row):
    return f"""
    <table class='custom-table'>
        <tr><td class='title'>Fight Order</td><td class='title'>Corner</td><td class='title'>Event</td></tr>
        <tr><td>{row.get("Fight_Order", "")}</td><td>{row.get("Corner", "")}</td><td>{row.get("Event", "")}</td></tr>
        <tr><td class='title'>Division</td><td class='title'>Opponent</td><td class='title'>Coach</td></tr>
        <tr><td>{row.get("Division", "")}</td><td>{row.get("Opponent", "")}</td><td>{row.get("Coach", "")}</td></tr>
    </table>
    """

def render_tabela_documentos(row):
    doc = row.get("Personal_Doc", "")
    doc_link = f"<a href='{doc}' target='_blank'>Visualizar</a>" if doc else "—"
    whatsapp = str(row.get("Whatsapp", "")).strip()
    whatsapp_link = f"<a href='https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}' target='_blank'>{whatsapp}</a>" if whatsapp else "—"
    return f"""
    <table class='custom-table'>
        <tr><td class='title'>Nationality</td><td class='title'>Passport</td><td class='title'>Document</td></tr>
        <tr><td>{row.get("Nationality_Passport", "")}</td><td>{row.get("Passport", "")}</td><td>{doc_link}</td></tr>
        <tr><td class='title'>Date of Birth</td><td class='title'>Whatsapp</td><td class='title'> </td></tr>
        <tr><td>{row.get("DOB", "")}</td><td>{whatsapp_link}</td><td> </td></tr>
    </table>
    """

def render_tabela_voo(row):
    ticket = row.get("Flight_Ticket", "")
    ticket_link = f"<a href='{ticket}' target='_blank'>View</a>" if ticket else "—"
    return f"""
    <table class='custom-table'>
        <tr><td class='title'>Arrivals</td><td class='title'>Departure</td></tr>
        <tr><td>{row.get("Arrivals", "")}</td><td>{row.get("Departure", "")}</td></tr>
        <tr><td class='title'>Flight_Ticket</td><td class='title'>Hotel</td></tr>
        <tr><td>{ticket_link}</td><td>{row.get("Hotel", "")}</td></tr>
    </table>
    """

def renderizar_atleta(i, row, df):
    corner = row.get("Corner", "").lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"
    tem_pendencia = any(str(row.get(status, "")).lower() == "required" for status in status_cols)
    icone_alerta = "⚠️ " if tem_pendencia else ""

    nome_html = f"<div class='{nome_class}'>{icone_alerta}{row.get('Name', '')}</div>"
    img_html = f"<div class='circle-img'><img src='{row.get('Image', '')}'></div>" if row.get("Image") else ""

    st.markdown(f"<div class='header-container'>{img_html}{nome_html}</div>", unsafe_allow_html=True)

    edit_key = f"edit_mode_{i}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    with st.expander("Exibir detalhes", expanded=st.session_state[edit_key]):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns(5)
        toggle = c1.toggle("✏️ Editar", key=f"toggle_{i}")
        if toggle != st.session_state[edit_key]:
            st.session_state[edit_key] = toggle
            st.rerun()

        if st.session_state[edit_key]:
            def status_btn(col, nome, emoji):
                if col.button(f"{emoji} {nome.upper()}", key=f"{nome}_{i}"):
                    atual = str(row.get(nome, "")).strip().lower()
                    novo = "done" if atual == "required" else "required"
                    salvar_valor(i, df.columns.get_loc(nome), novo)
                    st.rerun()
            status_btn(c2, "Photoshoot", "📸")
            status_btn(c3, "Labs", "🧪")
            status_btn(c4, "Interview", "🎤")
            status_btn(c5, "Black_Screen", "🖥️")

        st.markdown("".join(gerar_badge(row.get(status, ""), status) for status in status_cols), unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        with col1: st.markdown(render_tabela_fight(row), unsafe_allow_html=True)
        with col2: st.markdown(render_tabela_documentos(row), unsafe_allow_html=True)
        with col3: st.markdown(render_tabela_voo(row), unsafe_allow_html=True)

        cols = st.columns(3)
        for idx, campo in enumerate(campos_editaveis):
            target = cols[idx % 3]
            if campo == "Uniform":
                opcoes_uniform = ["Small", "Medium", "Large", "X-Large", "2X-Large", "3X-Large"]
                valor_atual = str(row.get(campo, "")).strip()
                index_uniform = opcoes_uniform.index(valor_atual) if valor_atual in opcoes_uniform else None

                if index_uniform is not None:
                    target.selectbox(
                        campo,
                        options=opcoes_uniform,
                        index=index_uniform,
                        key=f"{campo}_{i}",
                        disabled=not st.session_state[edit_key]
                    )
                else:
                    target.selectbox(
                        campo,
                        options=[""] + opcoes_uniform,
                        index=0,
                        key=f"{campo}_{i}",
                        disabled=not st.session_state[edit_key]
                    )
            else:
                target.text_input(campo, value=row.get(campo, ""), key=f"{campo}_{i}", disabled=not st.session_state[edit_key])

        if st.session_state[edit_key]:
            if st.button("Salvar alterações", key=f"salvar_{i}"):
                for campo in campos_editaveis:
                    novo_valor = st.session_state.get(f"{campo}_{i}", "")
                    if campo in df.columns:
                        salvar_valor(i, df.columns.get_loc(campo), novo_valor)
                st.success("Alterações salvas com sucesso!")
                st.session_state[edit_key] = False
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)

# 🎛️ Filtros
st.sidebar.title("Filtros")
if st.sidebar.button("🔄 Atualizar Página"):
    st.rerun()

evento_sel = st.sidebar.selectbox("Evento", ["Todos"] + sorted(df['Event'].dropna().unique()))
corner_sel = st.sidebar.multiselect("Corner", sorted(df['Corner'].dropna().unique()))
status_sel = st.sidebar.radio("Status", ["Todos", "Somente Pendentes", "Somente Completos"])

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
st.title("UAE Warriors 59-60")
for i, row in df.iterrows():
    renderizar_atleta(i, row, df)
