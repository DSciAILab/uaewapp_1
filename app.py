# 📍 UAE Warriors App - v1.2.7
# ✅ Alterações:
# - Tabelas "Fight Details" e "Documentos Pessoais" foram adicionadas lado a lado, com layout tabular e visual consistente
# - Interface ajustada com colunas para visualização compacta e clara

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🎯 Configuração da página
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000)

# 🎨 Estilo visual
st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: white; }
.stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
.stTextInput>div>div>input { background-color: #3a3b3c; color: white; border: 1px solid #888; }
.name-vermelho, .name-azul {
    font-weight: bold; font-size: 1.6rem; display: inline-block;
}
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
.tabela-info {
    border: 1px solid #555; border-radius: 6px; padding: 10px;
    font-size: 0.85rem; margin-bottom: 10px;
}
.tabela-info th, .tabela-info td {
    padding: 5px 10px; border: 1px solid #555;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

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
    return client.open("UAEW_App").worksheet("App")

sheet = connect_sheet()

# 📥 Carregar dados
@st.cache_data(ttl=30)
def load_data():
    return pd.DataFrame(sheet.get_all_records())

df = load_data()
df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "").str.replace("-", "_")
df["Fight_Order"] = pd.to_numeric(df["Fight_Order"], errors="coerce")

# 🎯 Campos configuráveis
campos_editaveis = [
    "Music_1", "Music_2", "Music_3", "Stats", "Weight", "Height", "Reach",
    "Fightstyle", "Nationality_Fight", "Residence", "Team", "Uniform", "Notes"
]
status_cols = ["Photoshoot", "Labs", "Interview", "Black_Screen"]

# 💾 Atualizar célula
def salvar_valor(row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")

# 🏷️ Badges de status
def gerar_badge(valor, status):
    classe = {
        "done": "badge-done",
        "required": "badge-required"
    }.get(str(valor).strip().lower(), "badge-neutral")
    return f"<span class='badge {classe}'>{status.upper()}</span>"

# 🧾 Função para gerar tabela HTML
def gerar_tabela(campos, row, titulo):
    linhas = ""
    for linha in campos:
        linhas += "<tr>" + "".join(
            f"<td>{str(row.get(campo, '')).strip()}</td>" for campo in linha
        ) + "</tr>"
    return f"""
    <div class='tabela-info'>
    <b>{titulo}</b>
    <table style='width: 100%; border-collapse: collapse;'>
        {linhas}
    </table>
    </div>
    """

# 👤 Renderizar atleta
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

        # Badges
        badges_html = "".join(gerar_badge(row.get(status, ""), status) for status in status_cols)
        st.markdown(f"<div class='status-line'>{badges_html}</div>", unsafe_allow_html=True)

        # Tabelas lado a lado
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(gerar_tabela(
                [["Fight_Order", "Corner", "Event", "Division"],
                 ["Opponent", "Coach"]],
                row, "Fight Details"), unsafe_allow_html=True)
        with col2:
            st.markdown(gerar_tabela(
                [["Nationality_Passport", "Passport", "Personal_Doc"],
                 ["DOB", "Whatsapp"]],
                row, "Documentos Pessoais"), unsafe_allow_html=True)

        # WhatsApp
        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            st.markdown(f"<div class='wa-button'><a href='{link}' target='_blank'>📡 WhatsApp</a></div>", unsafe_allow_html=True)

        # Botão editar/salvar
        if st.button("Salvar" if st.session_state[edit_key] else "Editar", key=f"toggle_{i}"):
            if st.session_state[edit_key]:
                with st.spinner('Salvando alterações...'):
                    for campo in campos_editaveis:
                        novo_valor = st.session_state.get(f"{campo}_{i}", "")
                        if campo in df.columns:
                            col_index = df.columns.get_loc(campo)
                            salvar_valor(i, col_index, novo_valor)
                st.success('Alterações salvas com sucesso!')
            st.session_state[edit_key] = not st.session_state[edit_key]
            st.rerun()

        # Campos editáveis
        cols = st.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            target_col = cols[idx % 2]
            target_col.text_input(campo, value=row.get(campo, ""), key=f"{campo}_{i}", disabled=not st.session_state[edit_key])

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)

# 🧭 Filtros na barra lateral
st.sidebar.title("Filtros")

eventos = sorted(df["Event"].dropna().unique())
evento_sel = st.sidebar.selectbox("Selecionar Evento", ["Todos"] + eventos)

corners = sorted(df["Corner"].dropna().unique())
corner_sel = st.sidebar.multiselect("Selecionar Corner", options=corners, default=corners)

status_sel = st.sidebar.radio("Status", ["Todos", "Somente Pendentes", "Somente Completos"])

# Aplicar filtros
df = df[df["Role"] == "Fighter"]
if evento_sel != "Todos":
    df = df[df["Event"] == evento_sel]
if corner_sel:
    df = df[df["Corner"].isin(corner_sel)]

if status_sel == "Somente Pendentes":
    df = df[df[status_cols].apply(lambda row: "required" in row.str.lower().values, axis=1)]
elif status_sel == "Somente Completos":
    df = df[df[status_cols].apply(lambda row: all(val.strip().lower() == "done" for val in row.values), axis=1)]

# Ordenação
df = df.sort_values(by=["Event", "Fight_Order", "Corner"])

# Botão de atualizar
if st.sidebar.button("🔄 Atualizar Página"):
    st.rerun()

st.title("UAE Warriors 59-60")

# Renderizar cada atleta
for i, row in df.iterrows():
    renderizar_atleta(i, row, df)
