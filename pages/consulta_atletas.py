import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import html # Importar o módulo html para escapar caracteres

# --- Constantes ---
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
            margin-bottom: 10px; /* Reduzido para aproximar o botão */
            color: white;
            border: 1px solid #333; /* Adiciona uma borda sutil */
        }
        .athlete-card.present {
            background-color: #143d14;
        }
        .athlete-card.absent {
            background-color: #2e2e2e; /* Um pouco mais claro que o anterior */
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
            font-size: 1.5em;
        }
        .athlete-event {
            margin: 0;
            font-size: 1em;
            text-align: center;
            margin-bottom: 15px;
        }
        .athlete-details-table {
            width: 100%;
            font-size: 0.9em;
            margin-top: 10px;
        }
        .athlete-details-table td {
            padding: 6px 4px; /* Ajustado */
            vertical-align: top;
        }
        .athlete-details-table td:first-child {
            font-weight: bold;
            width: 35%; /* Ajustado */
        }
        .athlete-details-table a {
            color: #87cefa;
            text-decoration: none;
        }
        .athlete-details-table a:hover {
            text-decoration: underline;
        }
        /* Estilo para o container do botão, para manter o espaçamento */
        .button-container {
            margin-bottom: 20px; /* Espaçamento após o botão, antes do próximo card */
            margin-top: -5px; /* Para aproximar o botão do card */
        }
    </style>
    """, unsafe_allow_html=True)

load_css()

# --- Conexão com Google Sheets ---
@st.cache_resource(ttl=600) # Cache por 10 minutos
def connect_gsheet(sheet_name, tab_name):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        worksheet = client.open(sheet_name).worksheet(tab_name)
        return worksheet
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha '{sheet_name}/{tab_name}': {e}")
        st.stop()

# --- Carregar Dados dos Atletas ---
@st.cache_data(ttl=600) # Cache por 10 minutos
def load_data_from_gsheet():
    try:
        url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.upper() # Padroniza nomes das colunas

        required_cols = [COL_ROLE, COL_INACTIVE, COL_EVENT, COL_NAME, COL_DOB, COL_PASSPORT_EXPIRE, COL_IMAGE_URL]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"Erro: A coluna '{col}' não foi encontrada na planilha. Verifique a planilha ou as constantes de nome de coluna.")
                st.stop()
        
        df_filtered = df[(df[COL_ROLE] == "1 - Fighter") & (df[COL_INACTIVE] == False)].copy() # Usar .copy() para evitar SettingWithCopyWarning
        
        df_filtered.loc[:, COL_EVENT] = df_filtered[COL_EVENT].fillna("Z")
        
        for date_col in [COL_DOB, COL_PASSPORT_EXPIRE]:
            df_filtered.loc[:, date_col] = pd.to_datetime(df_filtered[date_col], errors='coerce').dt.strftime("%d/%m/%Y")
            df_filtered.loc[:, date_col] = df_filtered[date_col].replace('NaT/NaT/NaT', 'N/A').replace('nan/nan/nan', 'N/A')

        return df_filtered.sort_values(by=[COL_EVENT, COL_NAME])
    except Exception as e:
        st.error(f"Erro ao carregar ou processar dados dos atletas: {e}")
        st.stop()

# --- Registrar Log ---
def registrar_log(nome_atleta, tipo_verificacao, user_id_logger):
    try:
        sheet_log = connect_gsheet("UAEW_App", "Attendance")
        if sheet_log:
            data_registro = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            nova_linha = [nome_atleta, data_registro, tipo_verificacao, user_id_logger]
            sheet_log.append_row(nova_linha, value_input_option="USER_ENTERED")
            return True
    except Exception as e:
        st.error(f"Erro ao registrar log para {html.escape(nome_atleta)}: {e}")
    return False

# --- Função para exibir o Card do Atleta ---
def display_athlete_card(athlete_data, presenca_registrada_status, verification_type, user_id_input):
    card_class = "athlete-card present" if presenca_registrada_status else "athlete-card absent"
    
    # Escapar dados do atleta para segurança em HTML
    athlete_name_safe = html.escape(str(athlete_data.get(COL_NAME, 'N/A')))
    athlete_event_safe = html.escape(str(athlete_data.get(COL_EVENT, 'N/A')))
    gender_safe = html.escape(str(athlete_data.get(COL_GENDER, 'N/A')))
    dob_safe = html.escape(str(athlete_data.get(COL_DOB, 'N/A')))
    nationality_safe = html.escape(str(athlete_data.get(COL_NATIONALITY, 'N/A')))
    passport_no_safe = html.escape(str(athlete_data.get(COL_PASSPORT_NO, 'N/A')))
    passport_expire_safe = html.escape(str(athlete_data.get(COL_PASSPORT_EXPIRE, 'N/A')))

    whatsapp_num = athlete_data.get(COL_MOBILE)
    whatsapp_link_html = ""
    if pd.notna(whatsapp_num) and str(whatsapp_num).strip():
        # Limpa o número de telefone para o link wa.me, mas exibe o original
        whatsapp_num_cleaned = "".join(filter(str.isdigit, str(whatsapp_num)))
        if not whatsapp_num_cleaned.startswith('+') and len(whatsapp_num_cleaned) > 7 : # Heurística simples para DDI
             # Tenta adicionar DDI se não presente e parecer número internacional (suposição)
             # Você pode precisar de uma lógica mais robusta para formatar números de telefone.
             pass # Deixe como está ou adicione lógica de DDI se necessário
        
        whatsapp_link_html = f"<tr><td><b>📱 WhatsApp:</b></td><td><a href='https://wa.me/{whatsapp_num_cleaned}' target='_blank'>{html.escape(str(whatsapp_num))}</a></td></tr>"

    passport_img_url = athlete_data.get(COL_PASSPORT_IMG)
    passport_img_link_html = ""
    if pd.notna(passport_img_url) and str(passport_img_url).strip():
        passport_img_link_html = f"<tr><td><b>📄 Passaporte:</b></td><td><a href='{html.escape(str(passport_img_url))}' target='_blank'>Ver Imagem</a></td></tr>"

    image_url = athlete_data.get(COL_IMAGE_URL, "https://via.placeholder.com/100x100.png?text=Sem+Foto")
    if pd.isna(image_url) or not str(image_url).strip():
        image_url = "https://via.placeholder.com/100x100.png?text=Sem+Foto"
    
    # Construir o HTML COMPLETO do card (com <div> de abertura e fechamento)
    html_card_content_completo = f"""
    <div class='{card_class}'>
        <img src='{html.escape(image_url)}' class='athlete-image' alt='Foto de {athlete_name_safe}'>
        <h3 class='athlete-name'>{athlete_name_safe}</h3>
        <p class='athlete-event'>Evento: <b>{athlete_event_safe}</b></p>
        
        <table class='athlete-details-table'>
            <tr><td>Gênero:</td><td>{gender_safe}</td></tr>
            <tr><td>Nascimento:</td><td>{dob_safe}</td></tr>
            <tr><td>Nacionalidade:</td><td>{nationality_safe}</td></tr>
            <tr><td>Passaporte №:</td><td>{passport_no_safe}</td></tr>
            <tr><td>Expira em:</td><td>{passport_expire_safe}</td></tr>
            {whatsapp_link_html}
            {passport_img_link_html}
        </table>
    </div>
    """
    st.markdown(html_card_content_completo, unsafe_allow_html=True)

    # Renderizar o botão Streamlit e o aviso DEPOIS do bloco HTML do card,
    # mas dentro de um container para controlar o espaçamento inferior.
    with st.container(): # Usar st.container para agrupar o botão e o aviso
        if not presenca_registrada_status:
            # Chave do botão mais robusta (sem espaços ou caracteres especiais)
            clean_name_for_key = "".join(filter(str.isalnum, athlete_data[COL_NAME]))
            button_key = f"btn_register_{clean_name_for_key}_{verification_type}"
            
            button_disabled = not user_id_input.strip()
            button_text = f"Registrar {verification_type} de {athlete_name_safe}"

            if st.button(button_text, key=button_key, disabled=button_disabled, use_container_width=True):
                presenca_id = f"{athlete_data[COL_NAME]}_{verification_type}" # Usar nome original para ID de presença
                if registrar_log(athlete_data[COL_NAME], verification_type, user_id_input): # Log com nome original
                    st.session_state.presencas[presenca_id] = True
                    st.toast(f"{verification_type} de {athlete_name_safe} registrado!", icon="✅")
                    st.rerun()
                else:
                    st.toast(f"Falha ao registrar {verification_type} de {athlete_name_safe}", icon="❌")
            
            if button_disabled:
                 st.markdown(f"<small style='color: #FFC107; display: block; text-align: center;'>⚠️ _Informe seu PS (ID de usuário) para registrar {athlete_name_safe}._</small>", unsafe_allow_html=True)
        
        st.markdown("<div class='button-container'></div>", unsafe_allow_html=True) # Apenas para o margin-bottom


# --- Interface Principal ---
st.markdown("<h1 style='font-size: 2.2em; margin-bottom: 20px; text-align:center;'>📋 Consulta e Registro de Atletas</h1>", unsafe_allow_html=True)

# Inputs do Usuário
col1_user, col2_user = st.columns([0.6, 0.4]) # Ajustar proporção das colunas
with col1_user:
    user_id = st.text_input("🆔 **Seu PS (ID de usuário):**", max_chars=15, key="user_id_input",
                            help="Seu identificador único para registrar as verificações.")
with col2_user:
    tipo_verificacao = st.selectbox("🔍 **Tipo de verificação:**", 
                                    ["Blood Test", "PhotoShoot", "Check-in Geral", "Uniforme", "Credencial"], 
                                    key="tipo_verif_select")

status_view = st.radio(" atletas:", ["Todos", "✅ Verificados", "⏳ Pendentes"], 
                       horizontal=True, key="status_view_radio", 
                       captions=["Exibe todos os atletas.", "Apenas atletas já verificados.", "Apenas atletas com verificação pendente."])

# Carrega os dados
with st.spinner("Carregando e processando dados dos atletas... Aguarde. 🏋️‍♂️"):
    df_atletas = load_data_from_gsheet()

if df_atletas is None or df_atletas.empty:
    st.warning("Nenhum dado de atleta carregado ou encontrado com os filtros aplicados na planilha.")
    st.stop()

# Inicializa o estado da sessão
if "presencas" not in st.session_state:
    st.session_state.presencas = {}

# Exibição dos Atletas
num_cols_interface = st.select_slider("Atletas por linha:", options=[1, 2, 3, 4], value=2)
cols_display = st.columns(num_cols_interface)
col_idx = 0
filtered_athletes_count = 0

for index, atleta_row in df_atletas.iterrows():
    presenca_id_atleta = f"{atleta_row[COL_NAME]}_{tipo_verificacao}"
    presenca_foi_registrada = st.session_state.presencas.get(presenca_id_atleta, False)

    if status_view == "✅ Verificados" and not presenca_foi_registrada:
        continue
    if status_view == "⏳ Pendentes" and presenca_foi_registrada:
        continue
    
    filtered_athletes_count += 1
    with cols_display[col_idx % num_cols_interface]:
        display_athlete_card(atleta_row, presenca_foi_registrada, tipo_verificacao, user_id)
    col_idx += 1

if filtered_athletes_count == 0:
    if status_view == "✅ Verificados":
        st.info(f"Nenhum atleta verificado para '{tipo_verificacao}' ainda. Seja o primeiro! 👍")
    elif status_view == "⏳ Pendentes":
        st.success(f"🎉 Todos os atletas foram verificados para '{tipo_verificacao}'! Bom trabalho!")
    else:
        st.info("Nenhum atleta corresponde aos critérios de busca na planilha.")

st.markdown("---")
st.markdown(f"<p style='text-align:center; font-size:0.9em;'>Total de atletas listados: <b>{filtered_athletes_count}</b> | Total na base (após filtros iniciais): <b>{len(df_atletas)}</b></p>", unsafe_allow_html=True)
