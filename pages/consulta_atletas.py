# --- 0. Import Libraries ---
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. Page Configuration ---
st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# --- 2. Google Sheets Connection ---
@st.cache_resource(ttl=3600)
def connect_gsheet(sheet_name: str, tab_name: str):
    """Establishes and caches a connection to a Google Sheet worksheet."""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        worksheet = gspread.authorize(creds).open(sheet_name).worksheet(tab_name)
        return worksheet
    except KeyError as e:
        st.error(f"Configuration error: Missing Google Cloud service account key in `st.secrets`. Details: {e}", icon="🚨")
        st.stop()
    except Exception as e:
        st.error(f"Error connecting to Google Sheet: {e}", icon="🚨")
        st.stop()

# --- 3. Data Loading and Preprocessing ---
@st.cache_data(ttl=600)
def load_data():
    """Loads and preprocesses athlete data."""
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

        st.success("Athlete data loaded and processed successfully.", icon="✅")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading or processing data: {e}", icon="🚨")
        st.info("Please check the Google Sheet URL and column names.")
        st.stop()

# --- 4. Logging Function ---
def registrar_log(athlete_id: str, nome: str, tipo: str, user_id: str):
    """Registers an attendance log entry."""
    try:
        sheet = connect_gsheet("UAEW_App", "Attendance")
        data_registro = datetime.now()
        nova_linha = [
            str(athlete_id), nome, tipo, user_id,
            data_registro.day, data_registro.month, data_registro.year,
            data_registro.strftime("%H:%M")
        ]
        sheet.append_row(nova_linha, value_input_option="USER_ENTERED")
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

# --- 6.1. Initialize Session State ---
for key, default_val in [
    ("presencas", {}),
    ("warning_message", None),
    ("user_confirmed", False),
    ("current_user_id", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default_val
if 'user_id_input' not in st.session_state: # Initialize with current_user_id or empty
    st.session_state['user_id_input'] = st.session_state['current_user_id']


# --- 6.2. User ID Confirmation Section ---
with st.container():
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        st.session_state['user_id_input'] = st.text_input(
            "Informe seu PS (ID de usuário)",
            value=st.session_state['user_id_input'],
            max_chars=15,
            help="Seu ID de usuário para registrar a presença.",
            key="user_id_input_field"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Confirmar Usuário", key="confirm_user_btn", use_container_width=True):
            user_input_stripped = st.session_state['user_id_input'].strip()
            if user_input_stripped:
                st.session_state['current_user_id'] = user_input_stripped
                st.session_state['user_confirmed'] = True
                st.session_state['warning_message'] = None
                st.success(f"Usuário '{st.session_state['current_user_id']}' confirmado!", icon="✅")
            else:
                st.session_state['warning_message'] = "⚠️ O ID do usuário não pode ser vazio."
                st.session_state['user_confirmed'] = False
                # No need to call st.warning here, it will be handled below

# Handle user ID change after confirmation
if st.session_state['user_confirmed'] and \
   st.session_state['current_user_id'] != st.session_state['user_id_input'].strip():
    st.session_state['user_confirmed'] = False
    st.session_state['warning_message'] = "⚠️ ID do usuário alterado. Por favor, confirme novamente."

# Display relevant messages based on confirmation status
if st.session_state['user_confirmed'] and st.session_state['current_user_id']:
    st.info(f"**Usuário atual confirmado:** `{st.session_state['current_user_id']}`", icon="👤")
elif st.session_state.get('warning_message'):
    st.warning(st.session_state['warning_message'], icon="🚨")
else: # Not confirmed, no specific warning yet (initial state)
    st.warning("🚨 Por favor, digite e confirme seu ID de usuário acima para prosseguir.", icon="🚨")

user_id_for_ops = st.session_state['current_user_id']

# --- 6.3. Main Application UI (Filters and Athlete Cards) ---
if st.session_state['user_confirmed'] and user_id_for_ops:
    tipo = st.selectbox(
        "Tipo de verificação para REGISTRO",
        ["Blood Test", "PhotoShoot"],
        help="Selecione o tipo de verificação para registrar a presença do atleta."
    )
    status_view = st.radio(
        "Filtro de exibição (baseado no Tipo de Verificação acima)",
        ["Todos", "Feitos", "Restantes"], horizontal=True,
        help="Filtre os atletas por status de verificação para o TIPO selecionado."
    )

    df_athletes = load_data()

    def handle_attendance_click(athlete_id_val, athlete_name, current_tipo):
        presenca_id = f"{athlete_name}_{current_tipo}"
        registrar_log(str(athlete_id_val), athlete_name, current_tipo, st.session_state['current_user_id'])
        st.session_state["presencas"][presenca_id] = True
        st.session_state['warning_message'] = None
        st.rerun()

    if df_athletes.empty:
        st.info("No athletes found matching the criteria.", icon="ℹ️")
    else:
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
                expiry_text = ' <span style="font-weight:bold;">(Expired)</span>' if blood_test_is_expired else ''
                blood_info_html = f"<p style='margin:0; font-size:13px; color:{color};'>Blood Test: {blood_test_date_str}{expiry_text}</p>"
            else:
                blood_info_html = "<p style='margin:0; font-size:13px; color:orange;'>Blood Test: Not Recorded</p>"

            card_bg_color = "#1e1e1e"
            if presenca_registrada_para_tipo_atual:
                card_bg_color = "#143d14"
            elif tipo == "Blood Test" and not presenca_registrada_para_tipo_atual:
                if has_blood_test_info and not blood_test_is_expired: card_bg_color = "#3D3D00"
                elif blood_test_is_expired or not has_blood_test_info: card_bg_color = "#4D1A00"

            passport_image_link_html = ""
            if row.get("PASSPORT IMAGE") and str(row["PASSPORT IMAGE"]).strip():
                passport_image_link_html = f"<tr><td style='padding-right:10px;'><b>Passaporte Imagem:</b></td><td><a href='{row['PASSPORT IMAGE']}' target='_blank' style='color:#00BFFF;'>Ver Imagem</a></td></tr>"

            whatsapp_link_html = ""
            mobile_number = str(row.get("MOBILE", "")).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if mobile_number:
                if not mobile_number.startswith('+') and mobile_number.startswith('00'): mobile_number = "+" + mobile_number[2:]
                elif not mobile_number.startswith('+'):
                    if len(mobile_number) >= 9 and not mobile_number.startswith("971"): mobile_number = "+971" + mobile_number.lstrip('0')
                    elif not (mobile_number.startswith("971") or mobile_number.startswith("+")): mobile_number = "+" + mobile_number # General prefix if not already international
                if mobile_number.startswith("+"): # Only form link if it seems like a valid international number
                    whatsapp_link_html = f"<tr><td style='padding-right:10px;'><b>WhatsApp:</b></td><td><a href='https://wa.me/{mobile_number.replace('+', '')}' target='_blank' style='color:#00BFFF;'>Enviar Mensagem</a></td></tr>"
            
            # --- Card HTML Structure (CLEANED) ---
            st.markdown(f"""
            <div style='background-color:{card_bg_color}; padding:20px; border-radius:10px; margin-bottom:15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);'>
                <div style='display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:20px;'>
                    <div style='display:flex; align-items:center; gap:15px; flex-basis: 300px; flex-grow: 1;'>
                        <img src='{row["IMAGE"] if row["IMAGE"] else "https://via.placeholder.com/80?text=No+Image"}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                        <div>
                            <h4 style='margin:0;'>{row["NAME"]}</h4>
                            <p style='margin:0; font-size:14px; color:#cccccc;'>{row["EVENT"]}</p>
                            <p style='margin:0; font-size:13px; color:#cccccc;'>ID: {row["ID"]}</p>
                            {blood_info_html}
                        </div>
                    </div>
                    <div style='flex-basis: 300px; flex-grow: 1;'>
                        <table style='font-size:14px; color:white; border-collapse:collapse; width:100%;'>
                            <tr><td style='padding-right:10px;'><b>Gênero:</b></td><td>{row["GENDER"]}</td></tr>
                            <tr><td style='padding-right:10px;'><b>Nascimento:</b></td><td>{row["DOB"]}</td></tr>
                            <tr><td style='padding-right:10px;'><b>Nacionalidade:</b></td><td>{row["NATIONALITY"]}</td></tr>
                            <tr><td style='padding-right:10px;'><b>Passaporte:</b></td><td>{row["PASSPORT"]}</td></tr>
                            <tr><td style='padding-right:10px;'><b>Expira em:</b></td><td>{row["PASSPORT EXPIRE DATE"]}</td></tr>
                            {passport_image_link_html}
                            {whatsapp_link_html}
                        </table>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            button_text = f"Marcar '{tipo}' como FEITO"
            if presenca_registrada_para_tipo_atual:
                button_text = f"'{tipo}' já foi feito (Refazer?)"

            st.button(
                button_text,
                key=f"attend_button_{row['ID']}_{tipo.replace(' ', '_')}_{i}", # Added index i for max key uniqueness
                on_click=handle_attendance_click,
                args=(row['ID'], row['NAME'], tipo),
                type="secondary" if presenca_registrada_para_tipo_atual else "primary",
                use_container_width=True
            )
            st.markdown("<hr style='border-top: 1px solid #333; margin-top: 10px; margin-bottom: 25px;'>", unsafe_allow_html=True)
