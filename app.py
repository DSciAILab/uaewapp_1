# 📦 Importações necessárias
import streamlit as st  # Biblioteca para criar interfaces web interativas
import pandas as pd     # Biblioteca para manipulação de dados
import gspread          # Cliente Python para interagir com o Google Sheets
from google.oauth2.service_account import Credentials  # Autenticação via conta de serviço
from streamlit_autorefresh import st_autorefresh  # Componente do Streamlit para autoatualização

# 📡 Função de conexão ao Google Sheets com cache de recurso para performance
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]  # Lê credenciais da conta de serviço via secrets.toml
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)  # Autoriza cliente com as credenciais
    sheet = client.open("UAEW_App").worksheet("Sheet1")  # Abre planilha específica
    return sheet

# 🔄 Carrega os dados da planilha como DataFrame do Pandas
def load_data(sheet):
    data = sheet.get_all_records()  # Lê todas as linhas como lista de dicionários
    return pd.DataFrame(data)  # Converte em DataFrame

# 💾 Atualiza valor de uma célula específica na planilha
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)  # Ajuste necessário por conta do cabeçalho

# ⚙️ Configuração da página
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")
st_autorefresh(interval=10_000, key="datarefresh")  # Auto-refresh a cada 10 segundos

# 🎨 Estilos visuais customizados via CSS
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    .stButton>button { background-color: #262730; color: white; border: 1px solid #555; }
    .stTextInput>div>div>input { background-color: #3a3b3c; color: white; border: 1px solid #888; }
    .pending-label { background-color: #ffcccc; color: #8b0000; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 600; text-transform: uppercase; }
    .done-label { background-color: #2b3e2b; color: #5efc82; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 600; text-transform: uppercase; }
    .neutral-label { background-color: #444; color: #999; padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; display: inline-block; font-weight: 500; text-transform: uppercase; }
    .athlete-name { font-size: 1.8rem; font-weight: bold; text-align: center; padding: 0.5rem 0; }
    .corner-vermelho { border-top: 4px solid red; padding-top: 6px; }
    .corner-azul { border-top: 4px solid #0099ff; padding-top: 6px; }
    </style>
""", unsafe_allow_html=True)

# 🏷️ Título da página
st.title("UAE Warriors 59-60")

# 📥 Conecta à planilha e carrega dados
sheet = connect_sheet()
df = load_data(sheet)

# 🔍 Filtros de evento e corner
col_evento, col_corner = st.columns([6, 6])
eventos = sorted(df['Event'].dropna().unique())
corners = sorted(df['Corner'].dropna().unique())

evento_sel = col_evento.selectbox("Evento", ["Todos"] + eventos)
corner_sel = col_corner.multiselect("Corner", corners)

# 🔄 Botão manual de atualização
if st.button("🔄 Atualizar Página"):
    st.rerun()

# Aplica os filtros selecionados
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
if corner_sel:
    df = df[df['Corner'].isin(corner_sel)]

# 🧍 Renderização individual por atleta
for i, row in df.iterrows():
    cor_class = "corner-vermelho" if str(row.get("Corner", "")).lower() == "red" else "corner-azul"
    with st.expander(f"{row['Fighter ID']} - {row['Name']}"):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 5])

        # 📷 Exibe imagem e número da luta
        if row.get("Image"):
            try:
                col1.image(row["Image"], width=100)
                col1.markdown(f"**Fight Order:** {row.get('Fight Order', '')}")
            except:
                col1.warning("Imagem inválida")
        else:
            col1.markdown(f"**Fight Order:** {row.get('Fight Order', '')}")

        # 🥋 Informações fixas do atleta
        col1.markdown(f"**Division:** {row['Division']}")
        col1.markdown(f"**Opponent:** {row['Oponent']}")

        # 🏷️ Nome do atleta centralizado
        col2.markdown(f"<div class='athlete-name'>{row['Name']}</div>", unsafe_allow_html=True)

        # 🔁 Alternância entre modo edição e visualização
        edit_key = f"edit_mode_{i}"
        if edit_key not in st.session_state:
            st.session_state[edit_key] = False

        editando = st.session_state[edit_key]
        botao_label = "Salvar" if editando else "Editar"
        if col2.button(botao_label, key=f"botao_toggle_{i}"):
            if editando:
                campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]
                for campo in campos_editaveis:
                    novo_valor = st.session_state.get(f"{campo}_{i}", "")
                    col_index = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_index, novo_valor)
            st.session_state[edit_key] = not editando
            st.rerun()

        # 📝 Campos editáveis
        campo_a, campo_b = col2.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            valor_atual = str(row.get(campo, ""))
            if idx % 2 == 0:
                campo_a.text_input(f"{campo}", value=valor_atual, key=f"{campo}_{i}", disabled=not editando)
            else:
                campo_b.text_input(f"{campo}", value=valor_atual, key=f"{campo}_{i}", disabled=not editando)

        # 📲 Link para WhatsApp
        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            col2.markdown(f"[📞 Enviar mensagem no WhatsApp]({link})", unsafe_allow_html=True)

        # ✅ Campos de status editáveis (visual e update)
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

        # 🔚 Fechamento da div personalizada
        st.markdown("</div>", unsafe_allow_html=True)
