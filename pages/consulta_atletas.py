import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Constantes (Opcional, mas bom para nomes de colunas) ---
COL_NAME = "NAME"
COL_ROLE = "ROLE"
COL_INACTIVE = "INACTIVE"
COL_EVENT = "EVENT"
COL_DOB = "DOB"
COL_PASSPORT_EXPIRE = "PASSPORT EXPIRE DATE"
COL_MOBILE = "MOBILE"
COL_PASSPORT_IMG = "PASSPORT IMAGE"
COL_GENDER = "GENDER"
COL_NATIONALITY = "NATIONALITY"
COL_PASSPORT_NO = "PASSPORT"
COL_IMAGE_URL = "IMAGE"

# --- Configuração da Página ---
st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# --- Estilos CSS ---
def load_css():
    st.markdown("""
    <style>
        .athlete-card {
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            color: white; /* Cor base do texto no card */
        }
        .athlete-card.present {
            background-color: #143d14; /* Verde escuro para presença registrada */
        }
        .athlete-card.absent {
            background-color: #1e1e1e; /* Cinza escuro para pendente */
        }
        .athlete-image {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            border: 2px solid white;
            object-fit: cover;
            display: block;
            margin-left: auto;
            margin-right: auto;
        }
        .athlete-name {
            margin-top: 10px;
            margin-bottom: 5px;
            text-align: center;
        }
        .athlete-event {
            margin: 0;
            font-size: 14px;
            text-align: center;
            margin-bottom: 15px;
        }
        .athlete-details-table {
            width: 100%;
            font-size: 14px;
            margin-top: 10px; /* Ajustado de 20px para 10px */
        }
        .athlete-details-table td {
            padding: 5px; /* Ajustado de 6px para 5px */
            vertical-align: top;
        }
        .athlete-details-table td:first-child {
            font-weight: bold;
            width: 40%; /* Para alinhar melhor os dois pontos */
        }
        .athlete-details-table a {
            color: #87cefa; /* Light sky blue para links, mais visível */
            text-decoration: none;
        }
        .athlete-details-table a:hover {
            text-decoration: underline;
        }
    </style>
    """, unsafe_allow_html=True)

load_css()

# --- Conexão com Google Sheets ---
@st.cache_resource
def connect_gsheet(sheet_name, tab_name):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        worksheet = client.open(sheet_name).worksheet(tab_name)
        return worksheet
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha '{sheet_name}/{tab_name}': {e}")
        st.stop() # Interrompe a execução se a conexão falhar

# --- Carregar Dados dos Atletas ---
@st.cache_data
def load_data():
    try:
        url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip() # Limpa espaços nos nomes das colunas

        # Verificação de colunas essenciais
        required_cols = [COL_ROLE, COL_INACTIVE, COL_EVENT, COL_NAME, COL_DOB, COL_PASSPORT_EXPIRE, COL_IMAGE_URL]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"Erro: A coluna '{col}' não foi encontrada na planilha. Verifique a URL ou o nome da aba.")
                st.stop()
        
        df = df[(df[COL_ROLE] == "1 - Fighter") & (df[COL_INACTIVE] == False)]
        df[COL_EVENT] = df[COL_EVENT].fillna("Z") # Para ordenação, "Z" vai para o final
        
        # Conversão de datas com tratamento de erro e formatação
        df[COL_DOB] = pd.to_datetime(df[COL_DOB], errors='coerce').dt.strftime("%d/%m/%Y")
        df[COL_PASSPORT_EXPIRE] = pd.to_datetime(df[COL_PASSPORT_EXPIRE], errors='coerce').dt.strftime("%d/%m/%Y")
        
        # Lidar com NaT (Not a Time) que vira 'NaT/NaT/NaT' ou similar após strftime
        df[COL_DOB] = df[COL_DOB].replace('NaT/NaT/NaT', 'N/A')
        df[COL_PASSPORT_EXPIRE] = df[COL_PASSPORT_EXPIRE].replace('NaT/NaT/NaT', 'N/A')

        return df.sort_values(by=[COL_EVENT, COL_NAME])
    except Exception as e:
        st.error(f"Erro ao carregar ou processar dados dos atletas: {e}")
        st.stop()

# --- Registrar Log ---
def registrar_log(nome_atleta, tipo_verificacao, user_id_logger):
    try:
        sheet_log = connect_gsheet("UAEW_App", "Attendance") # Nome da sua planilha de log
        if sheet_log:
            data_registro = datetime.now().strftime("%d/%m/%Y %H:%M:%S") # Adicionado segundos
            nova_linha = [nome_atleta, data_registro, tipo_verificacao, user_id_logger]
            sheet_log.append_row(nova_linha, value_input_option="USER_ENTERED")
            return True
    except Exception as e:
        st.error(f"Erro ao registrar log para {nome_atleta}: {e}")
    return False

# --- Função para exibir o Card do Atleta ---
def display_athlete_card(athlete_data, presenca_registrada_status, verification_type, user_id_input):
    card_class = "athlete-card present" if presenca_registrada_status else "athlete-card absent"
    
    # Usar get com valor padrão para evitar KeyError se alguma coluna opcional não existir
    whatsapp_num = athlete_data.get(COL_MOBILE)
    whatsapp_link = ""
    if pd.notna(whatsapp_num) and str(whatsapp_num).strip():
        whatsapp_link = f"<tr><td><b>📱 WhatsApp:</b></td><td><a href='https://wa.me/{str(whatsapp_num).replace(' ', '')}' target='_blank'>{str(whatsapp_num)}</a></td></tr>"

    passport_img_url = athlete_data.get(COL_PASSPORT_IMG)
    passport_img_link = ""
    if pd.notna(passport_img_url) and str(passport_img_url).strip():
        passport_img_link = f"<tr><td><b>📄 Passaporte:</b></td><td><a href='{str(passport_img_url)}' target='_blank'>Ver Imagem</a></td></tr>"

    # Fallback para imagem se a URL estiver vazia ou for NaN
    image_url = athlete_data.get(COL_IMAGE_URL, "https://via.placeholder.com/100?text=Sem+Foto")
    if pd.isna(image_url) or not str(image_url).strip():
        image_url = "https://via.placeholder.com/100?text=Sem+Foto"

    html_content = f"""
    <div class='{card_class}'>
        <img src='{image_url}' class='athlete-image' alt='Foto de {athlete_data[COL_NAME]}'>
        <h3 class='athlete-name'>{athlete_data[COL_NAME]}</h3>
        <p class='athlete-event'>Evento: <b>{athlete_data[COL_EVENT]}</b></p>
        
        <table class='athlete-details-table'>
            <tr><td><b>Gênero:</b></td><td>{athlete_data.get(COL_GENDER, 'N/A')}</td></tr>
            <tr><td><b>Nascimento:</b></td><td>{athlete_data.get(COL_DOB, 'N/A')}</td></tr>
            <tr><td><b>Nacionalidade:</b></td><td>{athlete_data.get(COL_NATIONALITY, 'N/A')}</td></tr>
            <tr><td><b>Passaporte №:</b></td><td>{athlete_data.get(COL_PASSPORT_NO, 'N/A')}</td></tr>
            <tr><td><b>Expira em:</b></td><td>{athlete_data.get(COL_PASSPORT_EXPIRE, 'N/A')}</td></tr>
            {whatsapp_link}
            {passport_img_link}
        </table>
    """
    st.markdown(html_content, unsafe_allow_html=True)

    if not presenca_registrada_status:
        button_key = f"btn_register_{athlete_data[COL_NAME]}_{verification_type}".replace(" ", "_") # Chave mais robusta
        button_disabled = not user_id_input.strip()

        if st.button(f"Registrar {verification_type} de {athlete_data[COL_NAME]}", key=button_key, disabled=button_disabled, use_container_width=True):
            presenca_id = f"{athlete_data[COL_NAME]}_{verification_type}"
            if registrar_log(athlete_data[COL_NAME], verification_type, user_id_input):
                st.session_state.presencas[presenca_id] = True
                st.toast(f"{verification_type} de {athlete_data[COL_NAME]} registrado!", icon="✅")
                st.rerun()
            else:
                st.toast(f"Falha ao registrar {verification_type} de {athlete_data[COL_NAME]}", icon="❌")
        
        if button_disabled and not presenca_registrada_status: # Mostra aviso se o botão estiver desabilitado
             st.caption("ℹ️ _Informe seu PS (ID de usuário) acima para habilitar o registro._")
    
    st.markdown("</div>", unsafe_allow_html=True) # Fecha o div do card (mesmo que o original)

# --- Interface Principal ---
st.markdown("<h1 style='font-size: 38px; margin-bottom: 10px;'>Consulta de Atletas</h1>", unsafe_allow_html=True)

# Inputs do Usuário
col1_user, col2_user = st.columns(2)
with col1_user:
    user_id = st.text_input("Informe seu PS (ID de usuário)", max_chars=15, key="user_id_input",
                            help="Seu identificador único para registrar as verificações.")
with col2_user:
    tipo_verificacao = st.selectbox("Tipo de verificação", ["Blood Test", "PhotoShoot", "Check-in Geral"], key="tipo_verif_select")

status_view = st.radio("Filtrar atletas:", ["Todos", "Verificados", "Pendentes"], 
                       horizontal=True, key="status_view_radio", 
                       captions=["Exibe todos os atletas.", "Apenas atletas já verificados.", "Apenas atletas com verificação pendente."])

# Carrega os dados (com spinner)
with st.spinner("Carregando e processando dados dos atletas... Por favor, aguarde."):
    df_atletas = load_data()

if df_atletas is None or df_atletas.empty:
    st.warning("Nenhum dado de atleta carregado ou encontrado com os filtros aplicados.")
    st.stop()

# Inicializa o estado da sessão para presenças se não existir
if "presencas" not in st.session_state:
    st.session_state.presencas = {}

# --- Exibição dos Atletas ---
# Usar colunas para melhor layout
num_cols = st.number_input("Atletas por linha:", min_value=1, max_value=4, value=2, step=1) # Permite ao usuário escolher colunas
cols = st.columns(num_cols)
col_idx = 0

filtered_athletes_count = 0

for index, atleta in df_atletas.iterrows():
    presenca_id_atleta = f"{atleta[COL_NAME]}_{tipo_verificacao}"
    presenca_foi_registrada = st.session_state.presencas.get(presenca_id_atleta, False)

    if status_view == "Verificados" and not presenca_foi_registrada:
        continue
    if status_view == "Pendentes" and presenca_foi_registrada:
        continue
    
    filtered_athletes_count += 1
    with cols[col_idx % num_cols]:
        display_athlete_card(atleta, presenca_foi_registrada, tipo_verificacao, user_id)
    col_idx += 1

if filtered_athletes_count == 0:
    if status_view == "Verificados":
        st.info(f"Nenhum atleta verificado para '{tipo_verificacao}' ainda.")
    elif status_view == "Pendentes":
        st.info(f"Todos os atletas foram verificados para '{tipo_verificacao}'!")
    else: # Todos
        st.info("Nenhum atleta corresponde aos critérios de busca.")

st.markdown("---")
st.caption(f"Total de atletas listados: {filtered_athletes_count}")
st.caption(f"Total de atletas na base (após filtros iniciais): {len(df_atletas)}")
