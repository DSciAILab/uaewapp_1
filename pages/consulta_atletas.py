import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- Configuration ---
st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# --- Google Sheets Authentication and Connection ---
@st.cache_resource(ttl=3600)
def connect_gsheet(sheet_name: str, tab_name: str):
    """
    Establishes and caches a connection to a Google Sheet worksheet.
    """
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        worksheet = gspread.authorize(creds).open(sheet_name).worksheet(tab_name)
        st.success(f"Successfully connected to Google Sheet: '{sheet_name}' tab: '{tab_name}'", icon="✅")
        return worksheet
    except KeyError as e:
        st.error(f"Configuration error: Missing Google Cloud service account key in `st.secrets`. Details: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Error connecting to Google Sheet: {e}", icon="🚨")
        st.stop()

# --- Data Loading ---
@st.cache_data(ttl=600)
def load_data():
    """
    Loads and preprocesses athlete data from a Google Sheet CSV export.
    Filters by 'ROLE' and 'INACTIVE' status, and formats date columns.
    """
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

        if "IMAGE" not in df.columns:
            df["IMAGE"] = ""
        df["IMAGE"] = df["IMAGE"].fillna("")

        if "PASSPORT IMAGE" not in df.columns:
            df["PASSPORT IMAGE"] = ""
        df["PASSPORT IMAGE"] = df["PASSPORT IMAGE"].fillna("")

        if "MOBILE" not in df.columns:
            df["MOBILE"] = ""
        df["MOBILE"] = df["MOBILE"].fillna("")

        st.success("Athlete data loaded and processed successfully.", icon="✅")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading or processing data: {e}", icon="🚨")
        st.info("Please check the Google Sheet URL and column names.")
        st.stop()

# --- Logging Function ---
def registrar_log(athlete_id: str, nome: str, tipo: str, user_id: str):
    """
    Registers an attendance log entry in the 'Attendance' Google Sheet.
    Order: ID, NAME, Tipo de verificação, usuário, Dia, Mês, Ano, Hora.
    """
    try:
        sheet = connect_gsheet("UAEW_App", "Attendance")
        data_registro = datetime.now()
        
        dia = data_registro.day
        mes = data_registro.month
        ano = data_registro.year
        hora = data_registro.strftime("%H:%M")
        
        nova_linha = [athlete_id, nome, tipo, user_id, dia, mes, ano, hora]
        sheet.append_row(nova_linha, value_input_option="USER_ENTERED")
        st.success(f"Attendance registered for {nome} ({tipo}).", icon="✍️")
    except Exception as e:
        st.error(f"Error registering attendance: {e}", icon="🚨")
        st.warning("Could not log attendance. Please check sheet permissions or connection.")

# --- Helper Function for Blood Test Expiration ---
def is_blood_test_expired(blood_test_date_str: str) -> bool:
    """
    Checks if a blood test date is older than 6 months.
    Expects date in "DD/MM/YYYY" format.
    """
    if not blood_test_date_str:
        return True
    try:
        blood_test_date = datetime.strptime(blood_test_date_str, "%d/%m/%Y")
        six_months_ago = datetime.now() - timedelta(days=182)
        return blood_test_date < six_months_ago
    except ValueError:
        return True

# --- Main Application Logic ---
st.title("Consulta de Atletas")

# Initialize session state variables if not already present
if "presencas" not in st.session_state:
    st.session_state["presencas"] = {}
if 'warning_message' not in st.session_state:
    st.session_state['warning_message'] = None
if 'user_confirmed' not in st.session_state:
    st.session_state['user_confirmed'] = False
if 'current_user_id' not in st.session_state: # Store the confirmed user ID
    st.session_state['current_user_id'] = ""

# --- User Confirmation Logic ---
# Use a form or columns for better layout of input and button
with st.container():
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        # We need a temporary text input to allow changes without immediate reruns
        # And a session state variable to hold the actual confirmed ID
        temp_user_id = st.text_input(
            "Informe seu PS (ID de usuário)", 
            value=st.session_state['current_user_id'], # Display current confirmed ID
            max_chars=15, 
            help="Seu ID de usuário para registrar a presença.",
            key="user_id_input" # Unique key for the text input
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True) # Add some space for vertical alignment
        if st.button("Confirmar Usuário", key="confirm_user_btn", use_container_width=True):
            if temp_user_id.strip():
                st.session_state['current_user_id'] = temp_user_id.strip()
                st.session_state['user_confirmed'] = True
                st.session_state['warning_message'] = None # Clear warnings on confirmation
                st.success(f"Usuário '{st.session_state['current_user_id']}' confirmado!", icon="✅")
                # No rerun needed here, unless you want immediate UI change
            else:
                st.session_state['warning_message'] = "⚠️ O ID do usuário não pode ser vazio."
                st.session_state['user_confirmed'] = False # Reset confirmation if empty
                st.warning(st.session_state['warning_message'], icon="🚨")

# Display confirmed user ID or prompt
if st.session_state['user_confirmed'] and st.session_state['current_user_id']:
    st.info(f"**Usuário atual confirmado:** `{st.session_state['current_user_id']}`", icon="👤")
else:
    st.warning("🚨 Por favor, digite e confirme seu ID de usuário acima para prosseguir.", icon="🚨")

# Reset confirmation if the user starts typing again
if st.session_state['current_user_id'] != st.session_state['user_id_input'] and st.session_state['user_confirmed']:
    st.session_state['user_confirmed'] = False
    st.session_state['warning_message'] = "⚠️ ID do usuário alterado. Por favor, confirme novamente."
    st.warning(st.session_state['warning_message'], icon="🚨")

# Get the confirmed user_id for operations
user_id_for_ops = st.session_state['current_user_id']

# Only show these controls if user is confirmed
if st.session_state['user_confirmed'] and user_id_for_ops:
    tipo = st.selectbox("Tipo de verificação", ["Blood Test", "PhotoShoot"], help="Selecione o tipo de verificação para o atleta.")
    status_view = st.radio("Filtro", ["Todos", "Feitos", "Restantes"], horizontal=True, help="Filtre os atletas por status de verificação.")

    df = load_data() # Load data only after user is confirmed (optional, but logical)

    # Function to handle button clicks (now uses confirmed user_id)
    def handle_attendance_click(athlete_id_val, athlete_name, current_tipo): # Removed user_id_val arg
        """Callback function for attendance button clicks."""
        presenca_id = f"{athlete_name}_{current_tipo}"
        # Use the confirmed user_id from session state
        registrar_log(athlete_id_val, athlete_name, current_tipo, st.session_state['current_user_id'])
        st.session_state["presencas"][presenca_id] = True # Marcar como presente após o registro bem-sucedido
        st.session_state['warning_message'] = None # Limpar qualquer aviso anterior
        st.rerun()

    # Display athlete cards
    if df.empty:
        st.info("No athletes found matching the criteria.", icon="ℹ️")
    else:
        for i, row in df.iterrows():
            presenca_id = f"{row['NAME']}_{tipo}"
            presenca_registrada = st.session_state["presencas"].get(presenca_id, False)

            if status_view == "Feitos" and not presenca_registrada:
                continue
            if status_view == "Restantes" and presenca_registrada:
                continue

            blood_info = ""
            blood_test_date_display = row.get("BLOOD TEST", "")
            has_blood_test_info = pd.notna(blood_test_date_display) and str(blood_test_date_display).strip() != ""
            is_expired = False

            if tipo == "Blood Test":
                if has_blood_test_info:
                    is_expired = is_blood_test_expired(blood_test_date_display)
                    color = "red" if is_expired else "#A0F0A0"
                    blood_info = f"<p style='margin:0; font-size:13px; color:{color};'>Blood Test in: {blood_test_date_display}{' <span style=\"font-weight:bold;\">(Expired)</span>' if is_expired else ''}</p>"
                else:
                    blood_info = "<p style='margin:0; font-size:13px; color:red;'>Blood Test: Not Recorded</p>"

            card_bg_color = "#1e1e1e"
            if presenca_registrada:
                card_bg_color = "#143d14"
            elif has_blood_test_info and tipo == "Blood Test":
                card_bg_color = "#4D4600"

            passport_image_link = ""
            if row.get("PASSPORT IMAGE") and str(row["PASSPORT IMAGE"]).strip():
                passport_image_link = f"<tr><td style='padding-right:10px;'><b>Passaporte Imagem:</b></td><td><a href='{row['PASSPORT IMAGE']}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>"

            whatsapp_link = ""
            mobile_number = str(row.get("MOBILE", "")).strip().replace(" ", "").replace("-", "")
            if mobile_number:
                if not mobile_number.startswith('+'):
                    if len(mobile_number) >= 9:
                        mobile_number = "+971" + mobile_number
                whatsapp_link = f"<tr><td style='padding-right:10px;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{mobile_number}' target='_blank' style='color:#00BFFF;'>Enviar Mensagem</a></td></tr>"


            st.markdown(f"""
            <div style='background-color:{card_bg_color}; padding:20px; border-radius:10px; margin-bottom:15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);'>
                <div style='display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:20px;'>
                    <div style='display:flex; align-items:center; gap:15px;'>
                        <img src='{row["IMAGE"] if row["IMAGE"] else "https://via.placeholder.com/80?text=No+Image"}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                        <div>
                            <h4 style='margin:0;'>{row["NAME"]}</h4>
                            <p style='margin:0; font-size:14px; color:#cccccc;'>{row["EVENT"]}</p>
                            <p style='margin:0; font-size:13px; color:#cccccc;'>ID: {row["ID"]}</p>
                            {blood_info}
                        </div>
                    </div>
                    <table style='font-size:14px; color:white; border-collapse:collapse; min-width: 250px;'>
                        <tr><td style='padding-right:10px;'><b>Gênero:</b></td><td>{row["GENDER"]}</td></tr>
                        <tr><td style='padding-right:10px;'><b>Nascimento:</b></td><td>{row["DOB"]}</td></tr>
                        <tr><td style='padding-right:10px;'><b>Nacionalidade:</b></td><td>{row["NATIONALITY"]}</td></tr>
                        <tr><td style='padding-right:10px;'><b>Passaporte:</b></td><td>{row["PASSPORT"]}</td></tr>
                        <tr><td style='padding-right:10px;'><b>Expira em:</b></td><td>{row["PASSPORT EXPIRE DATE"]}</td></tr>
                        {passport_image_link}
                        {whatsapp_link}
                    </table>
                </div>
            </div>
            """, unsafe_allow_html=True)

            button_text = "Subscrever attendance por uma nova?" if presenca_registrada else "Registrar Attendance"
            st.button(
                button_text,
                key=f"attend_button_{i}",
                on_click=handle_attendance_click,
                args=(row['ID'], row['NAME'], tipo), # user_id is now taken from session_state
                type="secondary" if presenca_registrada else "primary",
                use_container_width=True
            )

            st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
else:
    # If user is not confirmed, only show the confirmation prompt
    # and hide the rest of the UI (filters, athlete cards)
    pass # Already handled by the 'if st.session_state['user_confirmed']' block
