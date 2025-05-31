# 📍 UAE Warriors App - Versão Corrigida v1.1.33

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# Conexão única ao Google Sheets
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Sheet1")

sheet = connect_sheet()

# Carregamento otimizado dos dados
@st.cache_data(ttl=30)
def load_data():
    return pd.DataFrame(sheet.get_all_records())

# Atualização segura de célula
def salvar_valor(row, col_index, valor):
    try:
        sheet.update_cell(row + 2, col_index + 1, valor)
    except Exception as e:
        st.error(f"Erro ao atualizar: {e}")

# Geração otimizada das badges
def gerar_badge(valor, status):
    classe = {
        "done": "badge-done",
        "required": "badge-required"
    }.get(valor.strip().lower(), "badge-neutral")
    return f"<span class='badge {classe}'>{status.upper()}</span>"

# Renderização modular de cada atleta
def renderizar_atleta(i, row, df):
    corner = row.get("Corner", "").lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"
    tem_pendencia = any(row.get(status, "").lower() == "required" for status in status_cols)
    icone_alerta = "⚠️ " if tem_pendencia else ""

    nome_html = f"<div class='{nome_class}'>{icone_alerta}{row['Name']}</div>"
    img_html = f"<div class='circle-img'><img src='{row['Image']}'></div>" if row.get("Image") else ""

    st.markdown(f"""
        <div class='header-container'>
            {img_html}{nome_html}
        </div>""", unsafe_allow_html=True)

    with st.expander("Exibir detalhes"):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        badges_html = "".join(gerar_badge(row.get(status, ""), status) for status in status_cols)
        st.markdown(f"<div class='status-line'>{badges_html}</div>", unsafe_allow_html=True)

        luta_info = f"Fight {row['Fight_Order']} | {row['Division']} | Opponent {row['Oponent']}"
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

# Configuração principal da página
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000)

campos_editaveis = ["Music_1", "Music_2", "Music_3", "Stats", "Weight", "Height", "Reach", "Fightstyle", "Nationality_Fight", "Residence", "Team", "Uniform", "Notes"]
status_cols = ["Photoshoot", "Labs", "Interview", "Black_Screen"]

st.title("UAE Warriors 59-60")
df = load_data()

col_evento, col_corner = st.columns(2)
evento_sel = col_evento.selectbox("Evento", ["Todos"] + sorted(df['Event'].dropna().unique()))
corner_sel = col_corner.multiselect("Corner", sorted(df['Corner'].dropna().unique()))

if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

if st.button("🔄 Atualizar Página"):
    st.rerun()

# Renderizar atletas com dataframe corrigido
for i, row in df.iterrows():
    renderizar_atleta(i, row, df)
