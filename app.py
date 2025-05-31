# UAE Warriors App - Design Otimizado
# Versão: v3.0.0

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# ⚙️ Configuração inicial
st.set_page_config(
    page_title="UAE Warriors - Controle de Atletas",
    page_icon="🥋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🔄 Auto-refresh
st_autorefresh(interval=10_000, key="datarefresh")

# 🎨 Estilos CSS modernizados
st.markdown("""
    <style>
    /* Configurações gerais */
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #0e1117;
        color: #f0f2f6;
    }
    
    .stApp {
        background: linear-gradient(135deg, #1a1d25 0%, #0e1117 100%);
        padding: 2rem 1.5rem;
    }
    
    /* Cabeçalho principal */
    .header-container {
        background: rgba(15, 23, 42, 0.8);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    
    /* Cards de atleta - Design compacto */
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
    
    /* Cabeçalho do card - Layout compacto */
    .card-header {
        display: flex;
        gap: 20px;
        align-items: flex-start;
        margin-bottom: 1.2rem;
    }
    
    .athlete-img {
        border-radius: 12px;
        overflow: hidden;
        width: 90px;
        height: 90px;
        flex-shrink: 0;
        border: 2px solid rgba(255, 255, 255, 0.1);
    }
    
    .athlete-info {
        flex: 1;
    }
    
    .athlete-name {
        font-size: 1.7rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .athlete-meta {
        display: flex;
        gap: 15px;
        font-size: 0.95rem;
        color: #94a3b8;
        margin-bottom: 0.8rem;
        flex-wrap: wrap;
    }
    
    .fight-order {
        background: rgba(30, 41, 59, 0.7);
        padding: 8px 15px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 1.1rem;
        text-align: center;
    }
    
    /* Badges de status */
    .badges-container {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-top: 5px;
    }
    
    .badge {
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
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
        animation: pulse 2s infinite;
    }
    
    .badge-neutral {
        background: rgba(148, 163, 184, 0.15);
        color: #94a3b8;
        border: 1px solid rgba(148, 163, 184, 0.3);
    }
    
    /* Informações do oponente */
    .opponent-card {
        background: rgba(30, 41, 59, 0.7);
        padding: 12px;
        border-radius: 12px;
        margin-top: 15px;
    }
    
    .opponent-label {
        font-size: 0.9rem;
        color: #94a3b8;
        margin-bottom: 4px;
    }
    
    .opponent-name {
        font-size: 1.2rem;
        font-weight: 700;
    }
    
    /* Campos editáveis */
    .edit-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
        margin: 1.2rem 0;
    }
    
    /* Botão WhatsApp */
    .whatsapp-btn {
        background: linear-gradient(90deg, #25D366, #128C7E);
        color: white;
        padding: 12px;
        border-radius: 12px;
        text-align: center;
        margin-top: 15px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        text-decoration: none !important;
    }
    
    /* Animações */
    @keyframes pulse {
        0% { opacity: 0.7; }
        50% { opacity: 1; }
        100% { opacity: 0.7; }
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
    </style>
""", unsafe_allow_html=True)

# 🔄 Conexão com Google Sheets
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Sheet1")

# 📂 Carregar dados
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data)

# 📝 Atualizar dados
def salvar_valor(row, col_index, valor):
    sheet = connect_sheet()
    sheet.update_cell(row + 2, col_index + 1, valor)
    st.cache_data.clear()

# 🏷️ Cabeçalho da aplicação
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

# 📂 Carregar dados
df = load_data()

# 🔍 Filtros
with st.container():
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
    
status_cols = ["Photoshoot", "Blood Test", "Interview", "Black Scheen"]
if status_sel == "Com pendências":
    df = df[df[status_cols].apply(lambda x: x.str.strip().str.lower() == "required").any(axis=1)]
elif status_sel == "Completos":
    df = df[df[status_cols].apply(lambda x: x.str.strip().str.lower() == "done").all(axis=1)]

# ⚖️ Configurações
campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight"]

# 🧕 Exibição por atleta
if df.empty:
    st.warning("Nenhum atleta encontrado com os filtros selecionados.")
else:
    for i, row in df.iterrows():
        # Determinar classe CSS baseada no corner
        corner_class = "red-corner" if str(row.get("Corner", "")).lower() == "red" else "blue-corner"
        
        # Verificar pendências
        tem_pendencia = any(
            str(row.get(status, "")).strip().lower() == "required" 
            for status in status_cols
        )
        alert_icon = " ⚠️" if tem_pendencia else ""
        
        # Gerar badges de status
        def gerar_badge(valor, status):
            valor = str(valor).strip().lower()
            if valor == "done":
                return f"<div class='badge badge-done'>{status}</div>"
            elif valor == "required":
                return f"<div class='badge badge-required'>{status}</div>"
            else:
                return f"<div class='badge badge-neutral'>{status}</div>"
        
        status_tags = "".join(
            gerar_badge(row.get(status, ""), status)
            for status in status_cols
        )
        
        # Card do atleta - Layout otimizado
        with st.container():
            st.markdown(f"""
                <div class="athlete-card {corner_class}">
                    <div class="card-header">
                        <div class="athlete-img">
                            {f'<img src="{row["Image"]}" width="90" height="90">' if row.get("Image") else '<div style="background:#1e293b; width:90px;height:90px;display:flex;align-items:center;justify-content:center;color:#64748b">Sem imagem</div>'}
                        </div>
                        
                        <div class="athlete-info">
                            <div class="athlete-name">{row['Name']}{alert_icon}</div>
                            <div class="athlete-meta">
                                <div><strong>ID:</strong> {row['Fighter ID']}</div>
                                <div><strong>Divisão:</strong> {row['Division']}</div>
                                <div><strong>Evento:</strong> {row['Event']}</div>
                            </div>
                            <div class="badges-container">
                                {status_tags}
                            </div>
                        </div>
                        
                        <div class="fight-order">
                            Fight Order: {row.get('Fight Order', '')}
                        </div>
                    </div>
            """, unsafe_allow_html=True)
            
            # Colunas para informações
            col_img, col_info = st.columns([1, 3])
            
            with col_img:
                # Card do oponente
                st.markdown(f"""
                    <div class="opponent-card">
                        <div class="opponent-label">OPPONENT</div>
                        <div class="opponent-name">{row['Oponent']}</div>
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
                        for campo in campos_editaveis:
                            novo_valor = st.session_state.get(f"{campo}_{i}", "")
                            col_index = df.columns.get_loc(campo)
                            salvar_valor(i, col_index, novo_valor)
                    st.session_state[edit_key] = not editando
                    st.rerun()
                
                # Campos editáveis
                st.markdown('<div class="edit-grid">', unsafe_allow_html=True)
                for campo in campos_editaveis:
                    valor_atual = str(row.get(campo, ""))
                    st.text_input(
                        label=campo.upper(),
                        value=valor_atual,
                        key=f"{campo}_{i}",
                        disabled=not editando
                    )
                st.markdown('</div>', unsafe_allow_html=True)
                
                # WhatsApp
                whatsapp = str(row.get("Whatsapp", "")).strip()
                if whatsapp:
                    link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
                    st.markdown(f"""
                        <a href="{link}" target="_blank" class="whatsapp-btn">
                            <span>Enviar mensagem no WhatsApp</span>
                        </a>
                    """, unsafe_allow_html=True)
            
            # Fechar card do atleta
            st.markdown("</div>", unsafe_allow_html=True)

# Rodapé
st.markdown("""
    <div class="footer">
        UAE Warriors App v3.0.0 | Sistema de Gerenciamento de Atletas | Desenvolvido com Streamlit
    </div>
""", unsafe_allow_html=True)
