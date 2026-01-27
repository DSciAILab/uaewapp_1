from components.layout import bootstrap_page
import streamlit as st
from utils import get_valid_user_info, get_gspread_client
import html
from datetime import datetime

# Multi-user & Realtime Support
from realtime_utils import get_realtime_sync, setup_auto_refresh, render_sync_indicator

# Inicializa a página (sem require_auth para permitir login)
bootstrap_page("UAEW Operations App", require_auth=False)

# ------------------------------------------------------------------------------
# SE NÃO ESTIVER LOGADO: MOSTRA LOGIN
# ------------------------------------------------------------------------------
if not st.session_state.get("user_confirmed", False):
    if "user_id_input" not in st.session_state:
        st.session_state["user_id_input"] = ""
    
    user_id_input = st.text_input(
        "PS Number",
        value=st.session_state["user_id_input"],
        max_chars=50,
        key="uid_login_input",
        placeholder="Digite os 4 dígitos do seu PS (ex.: 0123) ou 'PS0123'"
    )
    
    if st.button("Login", key="login_button", use_container_width=True, type="primary"):
        u_in = (user_id_input or "").strip()
        if not u_in:
            st.warning("Por favor, insira um ID/Nome de usuário.")
        else:
            # Validação centralizada
            u_inf = get_valid_user_info(u_in)
            if u_inf:
                # Busca robusta para user_type
                possible_type_keys = ["user_type", "USER_TYPE", "type", "TYPE", "cargo", "CARGO", "User_Type"]
                found_type = ""
                for key in possible_type_keys:
                    if key in u_inf:
                        found_type = str(u_inf[key]).strip().lower()
                        break
                
                if not found_type:
                    for k, v in u_inf.items():
                        if "type" in k.lower() or "cargo" in k.lower():
                            found_type = str(v).strip().lower()
                            break

                # Preenche sessão
                st.session_state.update(
                    current_user_ps_id_internal=str(u_inf.get("PS", u_inf.get("ps", u_in))).strip(),
                    current_user_id=u_in,
                    current_user_name=str(u_inf.get("USER", u_inf.get("user", u_in))).strip(),
                    current_user_image_url=str(u_inf.get("USER_IMAGE", u_inf.get("user_image", ""))).strip(),
                    user_confirmed=True,
                    warning_message=None,
                    user_type=found_type,
                )
                st.toast(f"Bem-vindo, {st.session_state.current_user_name}!")
                st.rerun()
            else:
                st.error(f"Usuário '{u_in}' não encontrado ou inválido.")
                # Debug info
                with st.expander("Ver detalhes técnicos do erro"):
                    from utils import load_users_data
                    test_data = load_users_data()
                    if not test_data:
                        st.write("Erro: Não foi possível carregar nenhum dado da planilha.")
                    else:
                        st.write(f"Planilha carregada com {len(test_data)} registros.")
                        st.write("Primeiro registro encontrado:", test_data[0])
                        st.write("Seu input processado:", u_in.strip().upper())
    
    st.stop()

# ------------------------------------------------------------------------------
# SE ESTIVER LOGADO: MOSTRA MENU COM CARDS CUSTOMIZADOS
# ------------------------------------------------------------------------------

# ========== MULTI-USER & REALTIME SETUP ==========
# Auto-refresh mais lento para menu (10 segundos)
refresh_count = setup_auto_refresh(interval_ms=10000, key="menu_autorefresh")

# Inicializa realtime sync
try:
    gc = get_gspread_client()
    realtime_sync = get_realtime_sync(gc, "UAEW_App")
    
    # Registra atividade do usuário
    user_id = st.session_state.get('current_user_id', 'unknown')
    realtime_sync.record_change("Menu", user_id)
    
    # Tracking de última sincronização
    if "menu_last_sync" not in st.session_state:
        st.session_state["menu_last_sync"] = datetime.now()
    
    if refresh_count > 0:
        st.session_state["menu_last_sync"] = datetime.now()
    
    # Busca usuários ativos
    active_users = realtime_sync.get_active_users(minutes=5)
except Exception:
    active_users = []
    if "menu_last_sync" not in st.session_state:
        st.session_state["menu_last_sync"] = datetime.now()
# ========== FIM MULTI-USER SETUP ==========

# CSS simplificado apenas para espaçamento basico
st.markdown("""
<style>
    .stButton button {
        width: 100%;
        height: 80px;
        white-space: normal;
        word-wrap: break-word;
    }
</style>
""", unsafe_allow_html=True)

user_first_name = st.session_state.get('current_user_name', 'Usuário').split(" ")[0].title()
st.title(f"Welcome, {user_first_name}!")

# Indicador de sincronização
render_sync_indicator(
    last_sync=st.session_state.get("menu_last_sync"),
    active_users=active_users
)

st.divider()

# Define as páginas principais (Sem ícones)
main_pages = [
    ("pages/2_Fightcard.py", "Fight Cards", "Gerenciar card de lutas"),
    ("pages/3_Dashboard.py", "Dashboard", "Painel de controle"),
    ("pages/Batch_Operations.py", "Batch Ops", "Operações em lote"),
    ("pages/4_Arrival_List.py", "Arrivals", "Lista de chegadas"),
    ("pages/Bus.py", "Bus", "Transporte"),
    ("pages/99_Weight_in.py", "Weight In", "Pesagem"),
    ("pages/12_Medical_Team.py", "Medical", "Equipe médica"),
    ("pages/6_Stats.py", "Stats", "Estatísticas"),
    ("pages/7_Music.py", "Music", "Músicas de entrada"),
    ("pages/10_Event_Check.py", "Event Check", "Verificação do evento"),
]

# Adiciona Admin se usuário for admin
if st.session_state.get("user_type", "").lower() == "admin":
    main_pages.append(("pages/Admin.py", "Admin", "Painel administrativo"))

# Renderiza menu simplificado com botões nativos
cols_per_row = 3
for i in range(0, len(main_pages), cols_per_row):
    cols = st.columns(cols_per_row)
    batch = main_pages[i:i+cols_per_row]
    
    for idx, (page_path, title, desc) in enumerate(batch):
        with cols[idx]:
            # Botão simples com Título e Descrição
            if st.button(f"**{title}**\n\n{desc}", key=f"nav_{page_path}", use_container_width=True):
                try:
                    st.switch_page(page_path)
                except Exception:
                    st.switch_page(page_path.split("/")[-1])

# Menu expandível com páginas secundárias
st.divider()
with st.expander("Mais Páginas", expanded=False):
    secondary_pages = [
        ("pages/5_Blood_Test.py", "Blood Test"),
        ("pages/8_Photoshoot.py", "Photoshoot"),
        ("pages/9_Video.py", "Video"),
        ("pages/transfers.py", "Transfers"),
        ("pages/Line Order.py", "Line Order"),
        ("pages/100_weight_in_noshow.py", "Weight In No-Show"),
        ("pages/6_Stats_tshirts.py", "Stats T-Shirts"),
    ]
    
    cols = st.columns(3)
    for idx, (path, label) in enumerate(secondary_pages):
        with cols[idx % 3]:
            if st.button(label, key=f"sec_{path}", use_container_width=True):
                try:
                    st.switch_page(path)
                except Exception:
                    st.switch_page(path.split("/")[-1])

# Rodapé
st.markdown("---")
user_name = st.session_state.get("current_user_name", "Usuário")
user_type = st.session_state.get("user_type", "user")
st.caption(f"{user_name} | {user_type.upper()}")
