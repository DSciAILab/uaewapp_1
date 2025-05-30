import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🔒 Conecta à planilha do Google usando credenciais seguras do Streamlit (secrets.toml)
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("UAEW_App").worksheet("Sheet1")  # Nome da planilha
    return sheet

# 📥 Carrega os dados da planilha em um DataFrame do pandas
def load_data(sheet):
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# 💾 Salva valor em uma célula específica (linha e coluna) da planilha
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)  # +2 porque a primeira linha é o cabeçalho

# 🖥️ Configurações da página e estilo
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000, key="datarefresh")  # Atualiza a cada 10 segundos

# 🌙 Estilo escuro personalizado
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    .stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
    .stTextInput>div>div>input { background-color: #3a3b3c; color: white; border: 1px solid #888; }
    .pending-label { background-color: #ffcccc; color: #8b0000; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }
    .done-label { background-color: #2b3e2b; color: #5efc82; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }
    .neutral-label { background-color: #444; color: #999; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; font-weight: 500; text-transform: uppercase; }
    .athlete-name { font-size: 1.8rem; font-weight: bold; text-align: center; padding: 0.5rem 0; }
    .corner-vermelho { border-top: 4px solid red; padding-top: 6px; }
    .corner-azul { border-top: 4px solid #0099ff; padding-top: 6px; }
    </style>
""", unsafe_allow_html=True)

# 🏷️ Título principal
st.title("UAE Warriors 59-60")

# 📊 Carregamento dos dados
sheet = connect_sheet()
df = load_data(sheet)

# 🔍 Filtros de evento e corner
col_evento, col_corner = st.columns([6, 6])
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())

evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
corner_sel = col_corner.multiselect("Corner", corners)

# 🔄 Botão de atualização manual
if st.button("🔄 Atualizar Página"):
    st.rerun()

# 🎯 Filtragem de dados
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# 🧾 Campos que o usuário pode editar
campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]

# 🧍 Renderiza cada atleta como uma "expander"
for i, row in df.iterrows():
    cor_class = "corner-vermelho" if str(row.get("Corner", "")).lower() == "red" else "corner-azul"
    with st.expander(f"{row['Fighter ID']} - {row['Name']}"):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        col1, col2 = st.columns([1, 5])

        # 🖼️ Imagem do atleta e dados básicos
        if row.get("Image"):
            try:
                col1.image(row["Image"], width=100)
                col1.markdown(f"**Fight Order:** {row.get('Fight Order', '')}")
            except:
                col1.warning("Imagem inválida")
        else:
            col1.markdown(f"**Fight Order:** {row.get('Fight Order', '')}")

        col1.markdown(f"**Division:** {row['Division']}")
        col1.markdown(f"**Opponent:** {row['Oponent']}")

        # 🏷️ Nome em destaque
        col2.markdown(f"<div class='athlete-name'>{row['Name']}</div>", unsafe_allow_html=True)

        # 🔄 Alterna entre edição e visualização
        edit_key = f"edit_mode_{i}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        editando = st.session_state[edit_key]
        botao_label = "Salvar" if editando else "Editar"

        if col2.button(botao_label, key=f"botao_toggle_{i}"):
            if editando:
                for campo in campos_editaveis:
                    novo_valor = st.session_state.get(f"{campo}_{i}", "")
                    col_index = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_index, novo_valor)
            st.session_state[edit_key] = not editando
            st.rerun()

        # 📝 Campos editáveis em colunas lado a lado
        campo_a, campo_b = col2.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            valor_atual = str(row.get(campo, ""))
            if idx % 2 == 0:
                campo_a.text_input(f"{campo}", value=valor_atual, key=f"{campo}_{i}", disabled=not editando)
            else:
                campo_b.text_input(f"{campo}", value=valor_atual, key=f"{campo}_{i}", disabled=not editando)

        # 📲 Link direto para WhatsApp se disponível
        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            col2.markdown(f"[📞 Enviar mensagem no WhatsApp]({link})", unsafe_allow_html=True)

        # ✅ Status dos procedimentos médicos e logísticos
        status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]
        colx = st.columns(len(status_cols))

        for idx, status in enumerate(status_cols):
            col_idx = df.columns.get_loc(status)
            valor = str(row[status]).strip().lower()

            if valor == "required":
                if editando and colx[idx].button(f"⚠️ {status}", key=f"{status}_{i}"):
                    salvar_valor(sheet, i, col_idx, "Done")
                    st.rerun()
                else:
                    colx[idx].markdown(f"<span class='pending-label'>{status}</span>", unsafe_allow_html=True)
            elif valor == "done":
                colx[idx].markdown(f"<span class='done-label'>{status}</span>", unsafe_allow_html=True)
            elif valor == "---":
                colx[idx].markdown(f"<span class='neutral-label'>{status}</span>", unsafe_allow_html=True)
            else:
                colx[idx].markdown(f"<span style='color:green'>{status}</span>", unsafe_allow_html=True)

        # 🔚 Fecha o bloco estilizado
        st.markdown("</div>", unsafe_allow_html=True)
