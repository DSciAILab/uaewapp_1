import streamlit as st
import html
from google.oauth2.service_account import Credentials
import gspread

# --- Funções de Autenticação (Copie as suas funções para cá) ---
# É uma boa prática manter as funções que a página usa no mesmo local.

@st.cache_resource(ttl=3600)
def get_gspread_client():
    # ... (seu código da função get_gspread_client) ...
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("Erro: Credenciais `gcp_service_account` não encontradas.", icon="🚨"); st.stop()
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro API Google: {e}", icon="🚨"); st.stop()

@st.cache_data(ttl=300)
def load_users_data(sheet_name="UAEW_App", users_tab_name="Users"):
    # ... (seu código da função load_users_data) ...
    try:
        gspread_client = get_gspread_client()
        spreadsheet = gspread_client.open(sheet_name)
        worksheet = spreadsheet.worksheet(users_tab_name)
        return worksheet.get_all_records() or []
    except Exception as e:
        st.error(f"Erro ao carregar usuários '{users_tab_name}': {e}", icon="🚨"); return []

def get_valid_user_info(user_input, sheet_name="UAEW_App", users_tab_name="Users"):
    # ... (seu código da função get_valid_user_info) ...
    if not user_input: return None
    all_users = load_users_data(sheet_name, users_tab_name)
    if not all_users: return None
    proc_input = user_input.strip().upper()
    val_id_input = proc_input[2:] if proc_input.startswith("PS") and len(proc_input) > 2 and proc_input[2:].isdigit() else proc_input
    for record in all_users:
        ps_sheet = str(record.get("PS", "")).strip(); name_sheet = str(record.get("USER", "")).strip().upper()
        if ps_sheet == val_id_input or ("PS" + ps_sheet) == proc_input or name_sheet == proc_input or ps_sheet == proc_input: return record
    return None

# --- Configuração da Página de Login ---
st.set_page_config(page_title="UAEW Login", layout="centered")

st.title("UAEW | Controle de Acesso")
st.markdown("Por favor, faça o login para continuar.")

# Inicializa o session_state se necessário
if 'user_confirmed' not in st.session_state:
    st.session_state['user_confirmed'] = False

# --- Formulário de Login ---
user_id_input = st.text_input(
    "Digite seu PS ou Nome de Usuário",
    key="login_user_input",
    placeholder="Ex: 1234 ou John Doe"
)

if st.button("Login", key="login_button", type="primary"):
    if user_id_input:
        user_info = get_valid_user_info(user_id_input)
        if user_info:
            # SUCESSO! Armazena as informações do usuário no session_state
            st.session_state['user_confirmed'] = True
            st.session_state['current_user_name'] = str(user_info.get("USER", user_id_input)).strip()
            st.session_state['current_user_ps_id_internal'] = str(user_info.get("PS", user_id_input)).strip()
            st.session_state['current_user_image_url'] = str(user_info.get("USER_IMAGE", "")).strip()
            
            st.toast(f"Bem-vindo, {st.session_state['current_user_name']}!", icon="👋")
            
            # Redireciona para a página principal do dashboard
            st.switch_page("pages/DashboardNovo.py") 
            
        else:
            st.error("Usuário não encontrado. Verifique os dados e tente novamente.", icon="🚨")
    else:
        st.warning("Por favor, insira seu ID ou nome de usuário.", icon="⚠️")
