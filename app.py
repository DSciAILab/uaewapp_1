# 📍 UAE Warriors App - Versão Corrigida v1.1.35

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# ⚙️ Configuração inicial obrigatória
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000)

# 🎨 Estilo visual
st.markdown("""
<style>
body, .stApp {
    background-color: #0e1117;
    color: white;
}
.stButton>button {
    background-color: #262730;
    color: white;
    border: 1px solid #555;
}
.stTextInput>div>div>input {
    background-color: #3a3b3c;
    color: white;
    border: 1px solid #888;
}
.name-vermelho, .name-azul {
    font-weight: bold;
    font-size: 1.6rem;
    display: inline-block;
}
.name-vermelho { color: red; }
.name-azul { color: #0099ff; }
.circle-img {
    width: 70px;
    height: 70px;
    border-radius: 50%;
    overflow: hidden;
}
.circle-img img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.badge {
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 700;
    margin: 0 3px;
    text-transform: uppercase;
    display: inline-block;
}
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.corner-vermelho {
    background-color: rgba(255, 0, 0, 0.1);
    border-radius: 10px;
    padding: 10px;
}
.corner-azul {
    background-color: rgba(0, 153, 255, 0.1);
    border-radius: 10px;
    padding: 10px;
}
hr.divisor {
    border: none;
    height: 1px;
    background: #333;
    margin: 20px 0;
}
.status-line {
    text-align: center;
    margin-bottom: 8px;
}
.fight-info {
    text-align: center;
    color: #ccc;
    font-size: 0.9rem;
    margin-bottom: 8px;
}
.wa-button {
    text-align: center;
    margin-bottom: 10px;
}
.header-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-top: 20px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# 🔐 Conexão ao Google Sheets
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

# 📦 Carregamento dos dados
@st.cache_data(ttl=30)
def load_data():
    return pd.DataFrame(sheet.get_all_records())

df = load_data()

df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "").str.replace("-", "_")

# 👇 Debug visual: mostra as colunas carregadas
st.subheader("🧩 Colunas carregadas após normalização")
st.code(df.columns.tolist())


# 🧼 Padronizar nomes de colunas
df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "").str.replace("-", "_")

# ✅ Configurações
campos_editaveis = [
    "Music_1", "Music_2", "Music_3", "Stats", "Weight", "Height", "Reach",
    "Fightstyle", "Nationality_Fight", "Residence", "Team", "Uniform", "Notes"
]
status_cols = ["Photoshoot", "Labs", "Interview", "Black_Screen"]

# 💾 Atualização segura
def salvar_valor(row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")

# 🏷️ Badge de status
def gerar_badge(valor, status):
    classe = {
        "done": "badge-done",
        "required": "badge-required"
    }.get(str(valor).strip().lower(), "badge-neutral")
    return f"<span class='badge {classe}'>{status.upper()}</span>"

# 👤 Renderizar atleta
def renderizar_atleta(i, row, df):
    corner = row.get("Corner", "").lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"
    tem_pendencia = any(str(row.get(status, "")).lower() == "required" for status in status_cols)
    icone_alerta = "⚠️ " if tem_pendencia else ""

    nome_html = f"<div class='{nome_class}'>{icone_alerta}{row.get('Name', '')}</div>"
    img_html = f"<div class='circle-img'><img src='{row.get('Image', '')}'></div>" if row.get("Image") else ""

    st.markdown(f"""
        <div class='header-container'>
            {img_html}{nome_html}
        </div>""", unsafe_allow_html=True)

    with st.expander("Exibir detalhes"):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        badges_html = "".join(gerar_badge(row.get(status, ""), status) for status in status_cols)
        st.markdown(f"<div class='status-line'>{badges_html}</div>", unsafe_allow_html=True)

        fight_order = row.get("Fight_Order", "N/A")
        opponent = row.get("Opponent", "N/A")
        division = row.get("Division", "N/A")
        luta_info = f"Fight {fight_order} | {division} | Opponent {opponent}"
        st.markdown(f"<div class='fight-info'>{luta_info}</div>", unsafe_allow_html=True)

        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            st.markdown(f"<div class='wa-button'><a href='{link}' target='_blank'>📡 WhatsApp</a></div>", unsafe_allow_html=True)

        edit_key = f"edit_mode_{i}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        if st.button("Salvar" if st.session_state[edit_key] else "Editar", key=f"toggle_{i}"):
            if st.session_state[edit_key]:
                with st.spinner('Salvando alterações...'):
                    for campo in campos_editaveis:
                        novo_valor = st.session_state.get(f"{campo}_{i}", "")
                        if campo in df.columns:
                            col_index = df.columns.get_loc(campo)
                            salvar_valor(i, col_index, novo_valor)
                        else:
                            st.warning(f"Campo '{campo}' não encontrado.")
                st.success('Alterações salvas com sucesso!')
            st.session_state[edit_key] = not st.session_state[edit_key]
            st.rerun()

        cols = st.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            target_col = cols[idx % 2]
            target_col.text_input(
                campo,
                value=row.get(campo, ""),
                key=f"{campo}_{i}",
                disabled=not st.session_state[edit_key]
            )

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)

# 🧭 Filtros e título
st.title("UAE Warriors 59-60")

col_evento, col_corner = st.columns(2)
evento_sel = col_evento.selectbox("Evento", ["Todos"] + sorted(df['Event'].dropna().unique()))
corner_sel = col_corner.multiselect("Corner", sorted(df['Corner'].dropna().unique()))

if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

if st.button("🔄 Atualizar Página"):
    st.rerun()

# ▶️ Renderizar cada atleta
for i, row in df.iterrows():
    renderizar_atleta(i, row, df)
