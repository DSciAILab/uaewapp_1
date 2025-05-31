# 📍 UAE Warriors App - Interface Interativa com Google Sheets via Streamlit

"""
Versão: v1.1.29

### Mudanças nesta versão:
- Centralização horizontal: imagem e nome lado a lado
- Estilo do nome ajustado com tamanho maior e em negrito
- Expander com bordas neutras
- Divisor horizontal entre atletas mantido
- Layout final consolidado

### 🍛 Última atualização: 2025-05-31
"""

# 🏓️ Importações
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 📱 Conexão com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("UAEW_App").worksheet("Sheet1")
    return sheet

# 🔀 Carregamento de dados
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# 📂 Atualização de célula
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Layout e Auto-refresh
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000, key="datarefresh")

# 🎨 CSS
st.markdown("""
<style>
body { background-color: #0e1117; color: white; }
.stApp { background-color: #0e1117; }
.stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
.stTextInput>div>div>input { background-color: #3a3b3c; color: white; border: 1px solid #888; }
.name-vermelho, .name-azul {
  font-weight: bold;
  font-size: 1.6rem;
  display: inline-block;
}
.name-vermelho { color: red; }
.name-azul { color: #0099ff; }
.circle-img { width: 70px; height: 70px; border-radius: 50%; overflow: hidden; }
.circle-img img { width: 100%; height: 100%; object-fit: cover; }
.badge { padding: 3px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin: 0 3px; text-transform: uppercase; display: inline-block; }
.badge-done { background-color: #2e4f2e; color: #5efc82; }
.badge-required { background-color: #5c1a1a; color: #ff8080; }
.badge-neutral { background-color: #444; color: #ccc; }
.corner-vermelho { background-color: rgba(255, 0, 0, 0.1); border-radius: 10px; padding: 10px; }
.corner-azul { background-color: rgba(0, 153, 255, 0.1); border-radius: 10px; padding: 10px; }
hr.divisor { border: none; height: 1px; background: #333; margin: 20px 0; }
.status-line { text-align: center; margin-bottom: 8px; }
.fight-info { text-align: center; color: #ccc; font-size: 0.9rem; margin-bottom: 8px; }
.wa-button { text-align: center; margin-bottom: 10px; }
.header-container { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 20px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# 🏇 Título
df = load_data(connect_sheet())
st.title("UAE Warriors 59-60")

col_evento, col_corner = st.columns([6, 6])
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())

evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
corner_sel = col_corner.multiselect("Corner", corners)

if st.button("Atualizar Página"):
    st.rerun()
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# 🔋 Campos
campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]
status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]

def gerar_badge(valor, status):
    valor = valor.strip().lower()
    if valor == "done": return f"<span class='badge badge-done'>{status.upper()}</span>"
    elif valor == "required": return f"<span class='badge badge-required'>{status.upper()}</span>"
    else: return f"<span class='badge badge-neutral'>{status.upper()}</span>"

# 🦉 Renderizar cada atleta
for i, row in df.iterrows():
    corner = str(row.get("Corner", "")).lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"
    tem_pendencia = any(str(row.get(status, "")).lower() == "required" for status in status_cols)
    icone_alerta = "⚠️ " if tem_pendencia else ""

    # ✅ Nome + Imagem centralizados
    nome_html = f"<div class='{nome_class}'>{icone_alerta}{row['Name']}</div>"
    if row.get("Image"):
        img_html = f"<div class='circle-img'><img src='{row['Image']}'></div>"
    else:
        img_html = ""
    st.markdown(f"""
    <div class='header-container'>
        {img_html}
        {nome_html}
    </div>
    """, unsafe_allow_html=True)

    with st.expander("Exibir detalhes"):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        badges = "".join(gerar_badge(str(row.get(status, "")), status) for status in status_cols)
        st.markdown(f"<div class='status-line'>{badges}</div>", unsafe_allow_html=True)

        luta_info = f"Fight {row['Fight Order']} | {row['Division']} | Opponent {row['Oponent']}"
        st.markdown(f"<div class='fight-info'>{luta_info}</div>", unsafe_allow_html=True)

        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            st.markdown(f"<div class='wa-button'><a href='{link}' target='_blank'>📡 Enviar mensagem no WhatsApp</a></div>", unsafe_allow_html=True)

        col1, col2 = st.columns([1, 5])
        edit_key = f"edit_mode_{i}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False
        editando = st.session_state[edit_key]
        if col2.button("Salvar" if editando else "Editar", key=f"toggle_{i}"):
            if editando:
                for campo in campos_editaveis:
                    novo_valor = st.session_state.get(f"{campo}_{i}", "")
                    col_index = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_index, novo_valor)
            st.session_state[edit_key] = not editando
            st.rerun()

        campo_1, campo_2 = col2.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            valor_atual = str(row.get(campo, ""))
            target = campo_1 if idx % 2 == 0 else campo_2
            target.text_input(campo, value=valor_atual, key=f"{campo}_{i}", disabled=not editando)

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)
