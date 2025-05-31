# UAE Warriors App - Interface Moderna e Otimizada
# Versão: v2.0.3

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# ⚙️ Configuração do app - DEVE SER A PRIMEIRA OPERAÇÃO STREAMLIT
st.set_page_config(
    page_title="UAE Warriors - Controle de Atletas",
    page_icon="🥋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🔄 Configuração de auto refresh
st_autorefresh(interval=10_000, key="datarefresh")

# 🎨 Configuração de estilo CSS
def apply_custom_css():
    css = """
    <style>
    /* Configurações gerais */
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #0e1117;
        color: #f0f2f6;
    }
    
    /* Layout principal */
    .stApp {
        background: linear-gradient(135deg, #1a1d25 0%, #0e1117 100%);
        padding-top: 2rem;
    }
    
    /* Cabeçalho */
    .header-container {
        background: rgba(15, 23, 42, 0.8);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    
    /* Cards de atleta */
    .athlete-card {
        background: rgba(15, 23, 42, 0.7);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .athlete-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        border: 1px solid rgba(59, 130, 246, 0.3);
    }
    
    .red-corner {
        border-left: 4px solid #ef4444;
    }
    
    .blue-corner {
        border-left: 4px solid #3b82f6;
    }
    
    /* Títulos */
    h1, h2, h3 {
        color: #f8fafc;
        font-weight: 700;
    }
    
    .athlete-name {
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Botões */
    .stButton>button {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        color: white;
        border-radius: 12px;
        border: none;
        padding: 8px 16px;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
    }
    
    /* Campos de entrada */
    .stTextInput>div>div>input {
        background-color: rgba(30, 41, 59, 0.7);
        color: white;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 10px 15px;
    }
    
    .stTextInput>div>div>input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.5);
    }
    
    /* Badges */
    .badge {
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        margin-right: 8px;
        display: inline-block;
    }
    
    .badge-done {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    .badge-required {
        background: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    .badge-neutral {
        background: rgba(148, 163, 184, 0.15);
        color: #94a3b8;
        border: 1px solid rgba(148, 163, 184, 0.3);
    }
    
    /* Status container */
    .status-container {
        display: flex;
        justify-content: space-between;
        margin: 1rem 0;
        flex-wrap: wrap;
        gap: 10px;
    }
    
    .status-item {
        flex: 1;
        min-width: 120px;
        text-align: center;
        padding: 10px;
        border-radius: 12px;
        background: rgba(30, 41, 59, 0.5);
    }
    
    /* Informações do atleta */
    .info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
        margin: 1.5rem 0;
    }
    
    .info-item {
        background: rgba(30, 41, 59, 0.5);
        padding: 12px;
        border-radius: 12px;
        border-left: 3px solid #3b82f6;
    }
    
    .info-label {
        font-size: 0.85rem;
        color: #94a3b8;
        margin-bottom: 4px;
    }
    
    .info-value {
        font-size: 1.1rem;
        font-weight: 600;
    }
    
    /* Filtros */
    .filter-container {
        background: rgba(15, 23, 42, 0.6);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    
    /* Rodapé */
    .footer {
        text-align: center;
        margin-top: 3rem;
        padding: 1rem;
        color: #64748b;
        font-size: 0.9rem;
    }
    
    /* Animações */
    @keyframes pulse {
        0% { opacity: 0.5; }
        50% { opacity: 1; }
        100% { opacity: 0.5; }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# 🔄 Conexão com Google Sheets (sem cache para evitar problemas)
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Sheet1")

# 📂 Carrega os dados da planilha (com cache otimizado)
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# 📝 Atualiza valor de célula
def salvar_valor(row, col_index, valor):
    sheet = connect_sheet()
    sheet.update_cell(row + 2, col_index + 1, valor)
    st.cache_data.clear()

# Aplica o CSS personalizado
apply_custom_css()

# 🏷️ Cabeçalho da página
st.markdown(f"""
    <div class="header-container">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div>
                <h1 style="margin-bottom: 0.2rem;">UAE Warriors 59-60</h1>
                <p style="color: #94a3b8; margin-top: 0;">Controle de Atletas e Status</p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.9rem; color: #94a3b8;">Atualizado em</div>
                <div style="font-weight: 600;">{datetime.now().strftime("%d/%m/%Y %H:%M")}</div>
            </div>
        </div>
    </div>
""", unsafe_allow_html=True)

# 📂 Carrega dados
df = load_data()

# 🔍 Filtros
st.markdown('<div class="filter-container">', unsafe_allow_html=True)
st.subheader("Filtros")

col_evento, col_corner, col_status = st.columns([4, 4, 4])

# Filtro por evento
eventos = ["Todos"] + sorted(df['Event'].dropna().unique())
evento_sel = col_evento.selectbox("Evento", eventos, index=0)

# Filtro por corner
corners = ["Todos"] + sorted(df['Corner'].dropna().unique())
corner_sel = col_corner.selectbox("Corner", corners, index=0)

# Filtro por status
status_options = ["Todos", "Com pendências", "Completos"]
status_sel = col_status.selectbox("Status", status_options, index=0)

st.markdown('</div>', unsafe_allow_html=True)

# Aplicar filtros
if evento_sel != "Todos":
    df = df[df['Event'] == evento_sel]
    
if corner_sel != "Todos":
    df = df[df['Corner'] == corner_sel]
    
if status_sel == "Com pendências":
    status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]
    df = df[df[status_cols].apply(lambda x: x.str.strip().str.lower() == "required").any(axis=1)]
elif status_sel == "Completos":
    status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]
    df = df[df[status_cols].apply(lambda x: x.str.strip().str.lower() == "done").all(axis=1)]

# ⚖️ Campos editáveis e status
campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]
status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]

# Função para gerar badges de status
def gerar_badge(valor, status):
    valor = str(valor).strip().lower()
    if valor == "done":
        return f"<span class='badge badge-done'>{status}</span>"
    elif valor == "required":
        return f"<span class='badge badge-required pulse'>{status}</span>"
    else:
        return f"<span class='badge badge-neutral'>{status}</span>"

# 🧕 Exibição por atleta
if df.empty:
    st.warning("Nenhum atleta encontrado com os filtros selecionados.")
else:
    for i, row in df.iterrows():
        # Determina a classe CSS baseada no corner
        corner_class = "red-corner" if str(row.get("Corner", "")).lower() == "red" else "blue-corner"
        
        # Gera badges de status
        status_tags = "".join(
            gerar_badge(row.get(status, ""), status)
            for status in status_cols
        )
        
        # Verifica se há pendências
        tem_pendencia = any(
            str(row.get(status, "")).strip().lower() == "required" 
            for status in status_cols
        )
        alert_icon = " ⚠️" if tem_pendencia else ""
        
        # Card do atleta
        st.markdown(f"""
            <div class="athlete-card {corner_class}">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <div class="athlete-name">{row['Name']}{alert_icon}</div>
                        <div style="display: flex; gap: 15px; margin-bottom: 10px;">
                            <div><strong>ID:</strong> {row['Fighter ID']}</div>
                            <div><strong>Divisão:</strong> {row['Division']}</div>
                            <div><strong>Evento:</strong> {row['Event']}</div>
                        </div>
                        {status_tags}
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 5px;">Fight Order: {row.get('Fight Order', '')}</div>
                        <div style="background: rgba(30, 41, 59, 0.7); padding: 8px 15px; border-radius: 12px; font-weight: 600;">
                            {row['Corner']} Corner
                        </div>
                    </div>
                </div>
        """, unsafe_allow_html=True)
        
        # Colunas para imagem e informações
        col_img, col_info = st.columns([1, 3])
        
        with col_img:
            if row.get("Image"):
                try:
                    st.image(row["Image"], width=150)
                except:
                    st.warning("Imagem inválida")
            else:
                st.info("Sem imagem disponível")
            
            # Opponent
            st.markdown(f"""
                <div style="margin-top: 15px; background: rgba(30, 41, 59, 0.7); padding: 12px; border-radius: 12px;">
                    <div style="font-size: 0.9rem; color: #94a3b8;">OPPONENT</div>
                    <div style="font-size: 1.2rem; font-weight: 700;">{row['Oponent']}</div>
                </div>
            """, unsafe_allow_html=True)
        
        with col_info:
            # Botão de edição
            edit_key = f"edit_mode_{i}"
            if edit_key not in st.session_state:
                st.session_state[edit_key] = False
                
            editando = st.session_state[edit_key]
            botao_label = "🔄 Salvar Alterações" if editando else "✏️ Editar Informações"
            
            if st.button(botao_label, key=f"botao_toggle_{i}"):
                if editando:
                    # Salvar alterações
                    for campo in campos_editaveis:
                        novo_valor = st.session_state.get(f"{campo}_{i}", "")
                        col_index = df.columns.get_loc(campo)
                        salvar_valor(i, col_index, novo_valor)
                st.session_state[edit_key] = not editando
                st.rerun()
            
            # Campos editáveis
            st.markdown('<div class="info-grid">', unsafe_allow_html=True)
            for campo in campos_editaveis:
                valor_atual = str(row.get(campo, ""))
                st.text_input(
                    label=campo.upper(),
                    value=valor_atual,
                    key=f"{campo}_{i}",
                    disabled=not editando
                )
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Status do atleta
            st.markdown('<div class="status-container">', unsafe_allow_html=True)
            for status in status_cols:
                valor = str(row.get(status, "")).strip().lower()
                
                if valor == "required":
                    st.markdown(f"""
                        <div class="status-item" style="border: 1px solid rgba(239, 68, 68, 0.3);">
                            <div style="color: #ef4444; font-weight: 700;">{status}</div>
                            <div style="font-size: 0.9rem; color: #ef4444;">PENDENTE</div>
                        </div>
                    """, unsafe_allow_html=True)
                elif valor == "done":
                    st.markdown(f"""
                        <div class="status-item" style="border: 1px solid rgba(34, 197, 94, 0.3);">
                            <div style="color: #22c55e; font-weight: 700;">{status}</div>
                            <div style="font-size: 0.9rem; color: #22c55e;">CONCLUÍDO</div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="status-item" style="border: 1px solid rgba(148, 163, 184, 0.3);">
                            <div style="color: #94a3b8; font-weight: 700;">{status}</div>
                            <div style="font-size: 0.9rem; color: #94a3b8;">N/A</div>
                        </div>
                    """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # WhatsApp
            whatsapp = str(row.get("Whatsapp", "")).strip()
            if whatsapp:
                link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
                st.markdown(f"""
                    <a href="{link}" target="_blank" style="text-decoration: none;">
                        <div style="background: linear-gradient(90deg, #25D366, #128C7E); color: white; padding: 12px; border-radius: 12px; text-align: center; margin-top: 15px; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 8px;">
                            <span>Enviar mensagem no WhatsApp</span>
                        </div>
                    </a>
                """, unsafe_allow_html=True)
        
        # Fechar card do atleta
        st.markdown("</div>", unsafe_allow_html=True)

# Rodapé
st.markdown("""
    <div class="footer">
        UAE Warriors App v2.0.3 | Sistema de Gerenciamento de Atletas | Desenvolvido com Streamlit
    </div>
""", unsafe_allow_html=True)
