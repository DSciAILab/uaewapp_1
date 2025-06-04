# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import html

# --- 1. Page Configuration ---
st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600) # Cache do objeto de conexão
def get_gspread_client():
    """Retorna um cliente gspread autorizado."""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client
    except KeyError as e:
        st.error(f"Configuration error: Missing Google Cloud service account key in `st.secrets`. Details: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Error connecting to Google API: {e}", icon="🚨")
        st.stop()

# Esta função não precisa mais de client como argumento se chamada por funções que já têm acesso a ele
# ou se as funções que a usam obtêm o cliente por si mesmas.
def connect_gsheet_tab(gspread_client, sheet_name: str, tab_name: str):
    """Conecta-se a uma aba específica de uma planilha usando um cliente gspread fornecido."""
    try:
        spreadsheet = gspread_client.open(sheet_name)
        worksheet = spreadsheet.worksheet(tab_name)
        return worksheet
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{sheet_name}' não encontrada.", icon="🚨")
        st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Erro: Aba '{tab_name}' não encontrada na planilha '{sheet_name}'.", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao conectar à aba '{tab_name}': {e}", icon="🚨")
        st.stop()

# --- 3. Data Loading and Preprocessing (Atletas) ---
@st.cache_data(ttl=600)
def load_athlete_data():
    """Loads and preprocesses athlete data."""
    st.info("Carregando dados dos atletas...", icon="⏳")
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
        df["EVENT"] = df["EVENT"].fillna("Z")

        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].dt.strftime("%d/%m/%Y").fillna("")

        for col_to_check in ["IMAGE", "PASSPORT IMAGE", "MOBILE"]:
            if col_to_check not in df.columns:
                df[col_to_check] = ""
            df[col_to_check] = df[col_to_check].fillna("")
        
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading or processing athlete data: {e}", icon="🚨")
        st.info("Please check the Google Sheet URL for athletes and its structure.")
        return pd.DataFrame()

# --- 3.5. User Data Loading and Validation ---
@st.cache_data(ttl=300) # Cache da lista de usuários por 5 minutos
def load_users_data(sheet_name: str = "UAEW_App", users_tab_name: str = "Users"): # Não recebe mais gspread_client
    """Carrega todos os dados da aba 'Users'."""
    try:
        # Obtém o cliente gspread aqui dentro
        gspread_client_internal = get_gspread_client() 
        users_worksheet = connect_gsheet_tab(gspread_client_internal, sheet_name, users_tab_name)
        users_data = users_worksheet.get_all_records()
        if not users_data:
            st.warning(f"A aba '{users_tab_name}' está vazia ou não pôde ser lida.", icon="⚠️")
            return []
        return users_data
    except Exception as e:
        st.error(f"Erro ao carregar dados da aba de usuários '{users_tab_name}': {e}", icon="🚨")
        return []

def get_valid_user_info(user_ps_id: str, sheet_name: str = "UAEW_App", users_tab_name: str = "Users"):
    """
    Valida o PS ID do usuário contra os dados carregados da aba 'Users'.
    Retorna um dicionário com dados do usuário se encontrado, None caso contrário.
    """
    if not user_ps_id:
        return None
    
    # Carrega os dados dos usuários (usará o cache se disponível)
    # Não passa gspread_client aqui, pois load_users_data o obtém internamente
    all_users = load_users_data(sheet_name, users_tab_name) 
    
    if not all_users:
        return None

    for user_record in all_users:
        ps_id_from_sheet = str(user_record.get("PS_ID", "")).strip()
        if ps_id_from_sheet == user_ps_id:
            return user_record
    return None

# --- 4. Logging Function ---
def registrar_log(athlete_id: str, nome: str, tipo: str, user_id: str,
                  sheet_name: str = "UAEW_App", attendance_tab_name: str = "Attendance"):
    """Registers an attendance log entry."""
    try:
        # Obtém o cliente gspread aqui dentro para registrar o log
        gspread_client_internal = get_gspread_client()
        log_sheet = connect_gsheet_tab(gspread_client_internal, sheet_name, attendance_tab_name)
        data_registro = datetime.now()
        nova_linha = [
            str(athlete_id), nome, tipo, user_id,
            data_registro.day, data_registro.month, data_registro.year,
            data_registro.strftime("%H:%M")
        ]
        log_sheet.append_row(nova_linha, value_input_option="USER_ENTERED")
        st.success(f"Attendance registered for {nome} ({tipo}).", icon="✍️")
    except Exception as e:
        st.error(f"Error registering attendance: {e}", icon="🚨")
        st.warning("Could not log attendance. Please check sheet permissions or connection.")

# --- 5. Helper Function for Blood Test Expiration ---
def is_blood_test_expired(blood_test_date_str: str) -> bool:
    """Checks if a blood test date is older than 6 months."""
    if not blood_test_date_str: return True
    try:
        blood_test_date = datetime.strptime(blood_test_date_str, "%d/%m/%Y")
        return blood_test_date < (datetime.now() - timedelta(days=182))
    except ValueError: return True

# --- 6. Main Application Logic ---
st.title("Consulta de Atletas")

# Removido gspread_client daqui, pois as funções o obterão internamente

for key, default_val in [
    ("presencas", {}), ("warning_message", None), ("user_confirmed", False),
    ("current_user_id", ""), ("current_user_name", "Usuário")
]:
    if key not in st.session_state: st.session_state[key] = default_val
if 'user_id_input' not in st.session_state:
    st.session_state['user_id_input'] = st.session_state['current_user_id']

with st.container():
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        st.session_state['user_id_input'] = st.text_input(
            "Informe seu PS (ID de usuário)", value=st.session_state['user_id_input'],
            max_chars=15, help="Seu ID de usuário para registrar a presença.", key="user_id_input_field"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Confirmar Usuário", key="confirm_user_btn", use_container_width=True):
            user_input_stripped = st.session_state['user_id_input'].strip()
            if user_input_stripped:
                # Não passa gspread_client para get_valid_user_info
                user_info = get_valid_user_info(user_input_stripped) 
                if user_info:
                    st.session_state['current_user_id'] = user_input_stripped
                    st.session_state['current_user_name'] = str(user_info.get("NOME", user_input_stripped)).strip()
                    st.session_state['user_confirmed'] = True
                    st.session_state['warning_message'] = None
                    st.success(f"Usuário '{st.session_state['current_user_name']}' (PS: {user_input_stripped}) confirmado!", icon="✅")
                else:
                    st.session_state['user_confirmed'] = False
                    st.session_state['warning_message'] = (
                        f"⚠️ Usuário com PS '{user_input_stripped}' não encontrado. "
                        "Por favor, verifique o PS ID ou contate o administrador para inclusão."
                    )
            else:
                st.session_state['warning_message'] = "⚠️ O ID do usuário não pode ser vazio."
                st.session_state['user_confirmed'] = False

if st.session_state['user_confirmed'] and \
   st.session_state['current_user_id'] != st.session_state['user_id_input'].strip() and \
   st.session_state['user_id_input'].strip() != "":
    st.session_state['user_confirmed'] = False
    st.session_state['warning_message'] = "⚠️ ID do usuário alterado. Por favor, confirme novamente."

if st.session_state['user_confirmed'] and st.session_state['current_user_id']:
    st.info(f"**Usuário atual:** `{st.session_state['current_user_name']}` (PS: `{st.session_state['current_user_id']}`)", icon="👤")
elif st.session_state.get('warning_message'):
    st.warning(st.session_state['warning_message'], icon="🚨")
else:
    st.warning("🚨 Por favor, digite e confirme seu ID de usuário acima para prosseguir.", icon="🚨")

user_id_for_ops = st.session_state['current_user_id']

if st.session_state['user_confirmed'] and user_id_for_ops:
    if st.button("🔄 Atualizar Dados (Atletas e Usuários)", key="refresh_data_button", help="Recarrega os dados da planilha do Google."):
        st.cache_data.clear()
        st.cache_resource.clear() # Também limpar o cache do cliente gspread para forçar uma nova autenticação se necessário
        st.toast("Dados atualizados! Recarregando...", icon="🔄")
        st.rerun()

    tipo = st.selectbox(
        "Tipo de verificação para REGISTRO", ["Blood Test", "PhotoShoot"],
        help="Selecione o tipo de verificação para registrar a presença do atleta."
    )
    status_view = st.radio(
        "Filtro de exibição (baseado no Tipo de Verificação acima)", ["Todos", "Feitos", "Restantes"],
        horizontal=True, help="Filtre os atletas por status de verificação para o TIPO selecionado."
    )
    
    df_athletes = load_athlete_data()
    
    if df_athletes.empty:
        st.info("Nenhum dado de atleta para exibir no momento.")
    else:
        st.markdown(f"Exibindo **{len(df_athletes)}** atletas.")
        for i, row in df_athletes.iterrows():
            presenca_id_para_tipo_atual = f"{row['NAME']}_{tipo}"
            presenca_registrada_para_tipo_atual = st.session_state["presencas"].get(presenca_id_para_tipo_atual, False)

            if (status_view == "Feitos" and not presenca_registrada_para_tipo_atual) or \
               (status_view == "Restantes" and presenca_registrada_para_tipo_atual):
                continue

            blood_test_date_str = row.get("BLOOD TEST", "")
            has_blood_test_info = pd.notna(blood_test_date_str) and str(blood_test_date_str).strip() != ""
            blood_test_is_expired = is_blood_test_expired(blood_test_date_str) if has_blood_test_info else True
            
            if has_blood_test_info:
                color = "red" if blood_test_is_expired else "#A0F0A0"
                expiry_text = ' <span style="font-weight:bold;">(Expirado)</span>' if blood_test_is_expired else ''
                blood_info_html = f"<p style='margin:0; font-size:13px; color:{color};'>Blood Test: {html.escape(blood_test_date_str)}{expiry_text}</p>"
            else:
                blood_info_html = "<p style='margin:0; font-size:13px; color:orange;'>Blood Test: Não Registrado</p>"

            card_bg_color = "#1e1e1e"
            if presenca_registrada_para_tipo_atual:
                card_bg_color = "#143d14"
            elif tipo == "Blood Test" and not presenca_registrada_para_tipo_atual:
                if has_blood_test_info and not blood_test_is_expired: card_bg_color = "#3D3D00"
                elif blood_test_is_expired or not has_blood_test_info: card_bg_color = "#4D1A00"

            passport_image_link_html = ""
            passport_image_url = str(row.get("PASSPORT IMAGE", "")).strip()
            if passport_image_url:
                safe_passport_image_url = html.escape(passport_image_url, quote=True)
                passport_image_link_html = f"<tr><td style='padding-right:10px;'><b>Passaporte Imagem:</b></td><td><a href='{safe_passport_image_url}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>"

            whatsapp_link_html = ""
            mobile_number_raw = str(row.get("MOBILE", ""))
            mobile_number = mobile_number_raw.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if mobile_number:
                if not mobile_number.startswith('+') and mobile_number.startswith('00'): mobile_number = "+" + mobile_number[2:]
                elif not mobile_number.startswith('+'):
                    if len(mobile_number) >= 9 and not mobile_number.startswith("971"): mobile_number = "+971" + mobile_number.lstrip('0')
                    elif not (mobile_number.startswith("971") or mobile_number.startswith("+")): mobile_number = "+" + mobile_number
                if mobile_number.startswith("+"):
                    safe_mobile_for_link = html.escape(mobile_number.replace('+', ''), quote=True)
                    whatsapp_link_html = f"<tr><td style='padding-right:10px;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{safe_mobile_for_link}' target='_blank' style='color:#00BFFF;'>Enviar Mensagem</a></td></tr>"
            
            display_name = html.escape(str(row["NAME"]))
            display_event = html.escape(str(row["EVENT"]))
            display_id = html.escape(str(row["ID"]))
            display_gender = html.escape(str(row.get("GENDER", "")))
            display_dob = html.escape(str(row.get("DOB", "")))
            display_nationality = html.escape(str(row.get("NATIONALITY", "")))
            display_passport = html.escape(str(row.get("PASSPORT", "")))
            display_passport_expire_date = html.escape(str(row.get("PASSPORT EXPIRE DATE", "")))

            st.markdown(f"""
            <div style='background-color:{card_bg_color}; padding:20px; border-radius:10px; margin-bottom:15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);'>
                <div style='display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:20px;'>
                    <div style='display:flex; align-items:center; gap:15px; flex-basis: 300px; flex-grow: 1;'>
                        <img src='{html.escape(row["IMAGE"] if row["IMAGE"] else "https://via.placeholder.com/80?text=No+Image", quote=True)}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                        <div>
                            <h4 style='margin:0;'>{display_name}</h4>
                            <p style='margin:0; font-size:14px; color:#cccccc;'>{display_event}</p>
                            <p style='margin:0; font-size:13px; color:#cccccc;'>ID: {display_id}</p>
                            {blood_info_html}
                        </div>
                    </div>
                    <div style='flex-basis: 300px; flex-grow: 1;'>
                        <table style='font-size:14px; color:white; border-collapse:collapse; width:100%;'>
                            <tr><td style='padding-right:10px;'><b>Gênero:</b></td><td>{display_gender}</td></tr>
                            <tr><td style='padding-right:10px;'><b>Nascimento:</b></td><td>{display_dob}</td></tr>
                            <tr><td style='padding-right:10px;'><b>Nacionalidade:</b></td><td>{display_nationality}</td></tr>
                            <tr><td style='padding-right:10px;'><b>Passaporte:</b></td><td>{display_passport}</td></tr>
                            <tr><td style='padding-right:10px;'><b>Expira em:</b></td><td>{display_passport_expire_date}</td></tr>
                            {passport_image_link_html}
                            {whatsapp_link_html}
                        </table>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.button(
                f"Marcar '{tipo}' como FEITO{' (Refazer?)' if presenca_registrada_para_tipo_atual else ''}",
                key=f"attend_button_{row['ID']}_{tipo.replace(' ', '_')}_{i}",
                on_click=registrar_log,
                args=(str(row['ID']), row['NAME'], tipo, st.session_state['current_user_id']), # Não precisa mais passar gspread_client
                type="secondary" if presenca_registrada_para_tipo_atual else "primary",
                use_container_width=True
            )
            st.markdown("<hr style='border-top: 1px solid #333; margin-top: 10px; margin-bottom: 25px;'>", unsafe_allow_html=True)
