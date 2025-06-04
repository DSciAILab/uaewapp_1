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
        client = gspread.authorize(creds)
        worksheet = client.open(sheet_name).worksheet(tab_name)
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

        st.success("Athlete data loaded and processed successfully.", icon="✅")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True)
    except Exception as e:
        st.error(f"Error loading or processing data: {e}", icon="🚨")
        st.info("Please check the Google Sheet URL and column names.")
        st.stop()

# --- Logging Function ---
def registrar_log(nome: str, tipo: str, user_id: str):
    """
    Registers an attendance log entry in the 'Attendance' Google Sheet.
    """
    try:
        sheet = connect_gsheet("UAEW_App", "Attendance")
        data_registro = datetime.now().strftime("%d/%m/%Y %H:%M")
        nova_linha = [nome, data_registro, tipo, user_id]
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
        # Define 6 months as 182 days (approx. average for 6 months)
        six_months_ago = datetime.now() - timedelta(days=182)
        return blood_test_date < six_months_ago
    except ValueError:
        return True

# --- Main Application Logic ---
st.title("Consulta de Atletas")

# Input fields
user_id = st.text_input("Informe seu PS (ID de usuário)", max_chars=15, help="Seu ID de usuário para registrar a presença.")
tipo = st.selectbox("Tipo de verificação", ["Blood Test", "PhotoShoot"], help="Selecione o tipo de verificação para o atleta.")
status_view = st.radio("Filtro", ["Todos", "Feitos", "Restantes"], horizontal=True, help="Filtre os atletas por status de verificação.")

df = load_data()

# Initialize session state for attendance tracking
if "presencas" not in st.session_state:
    st.session_state["presencas"] = {}

# Function to handle button clicks
def handle_attendance_click(athlete_name, current_tipo, user_id_val):
    """Callback function for attendance button clicks."""
    presenca_id = f"{athlete_name}_{current_tipo}"
    if not user_id_val.strip():
        st.session_state['warning_message'] = "⚠️ Informe seu PS antes de registrar a presença."
    else:
        st.session_state["presencas"][presenca_id] = True
        registrar_log(athlete_name, current_tipo, user_id_val)
        st.session_state['warning_message'] = None # Clear any previous warning
        st.rerun()

# Display athlete cards
if df.empty:
    st.info("No athletes found matching the criteria.", icon="ℹ️")
else:
    # Display warning if present (cleared on successful action or input)
    if 'warning_message' in st.session_state and st.session_state['warning_message']:
        st.warning(st.session_state['warning_message'], icon="🚨")


    for i, row in df.iterrows():
        presenca_id = f"{row['NAME']}_{tipo}"
        presenca_registrada = st.session_state["presencas"].get(presenca_id, False)

        if status_view == "Feitos" and not presenca_registrada:
            continue
        if status_view == "Restantes" and presenca_registrada:
            continue

        blood_info = ""
        blood_test_date_display = row.get("BLOOD TEST", "")
        is_expired = False

        if tipo == "Blood Test":
            if pd.notna(blood_test_date_display) and str(blood_test_date_display).strip() != "":
                is_expired = is_blood_test_expired(blood_test_date_display)
                color = "red" if is_expired else "#A0F0A0" # Lighter green for valid, red for expired
                blood_info = f"<p style='margin:0; font-size:13px; color:{color};'>Blood Test in: {blood_test_date_display}{' <span style=\"font-weight:bold;\">(Expired)</span>' if is_expired else ''}</p>"
            else:
                blood_info = "<p style='margin:0; font-size:13px; color:red;'>Blood Test: Not Recorded</p>"

        button_text = "Subscrever attendance por uma nova?" if presenca_registrada else "Registrar Attendance"
        button_color = "darkgreen" if presenca_registrada else "#007bff" # Original dark green / blue

        # Main athlete card using markdown
        st.markdown(f"""
        <div style='background-color:{"#143d14" if presenca_registrada else "#1e1e1e"}; padding:20px; border-radius:10px; margin-bottom:15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.3);'>
            <div style='display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:20px;'>
                <div style='display:flex; align-items:center; gap:15px;'>
                    <img src='{row["IMAGE"] if row["IMAGE"] else "https://via.placeholder.com/80?text=No+Image"}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                    <div>
                        <h4 style='margin:0;'>{row["NAME"]}</h4>
                        <p style='margin:0; font-size:14px; color:#cccccc;'>{row["EVENT"]}</p>
                        {blood_info}
                    </div>
                </div>
                <table style='font-size:14px; color:white; border-collapse:collapse; min-width: 250px;'>
                    <tr><td style='padding-right:10px;'><b>Gênero:</b></td><td>{row["GENDER"]}</td></tr>
                    <tr><td style='padding-right:10px;'><b>Nascimento:</b></td><td>{row["DOB"]}</td></tr>
                    <tr><td style='padding-right:10px;'><b>Nacionalidade:</b></td><td>{row["NATIONALITY"]}</td></tr>
                    <tr><td style='padding-right:10px;'><b>Passaporte:</b></td><td>{row["PASSPORT"]}</td></tr>
                    <tr><td style='padding-right:10px;'><b>Expira em:</b></td><td>{row["PASSPORT EXPIRE DATE"]}</td></tr>
                </table>
            </div>
            </div>
        """, unsafe_allow_html=True)

        # Directly place the Streamlit button OUTSIDE the markdown, after the card div
        # This button will now be styled by Streamlit and trigger the callback
        st.button(
            button_text,
            key=f"attend_button_{i}",
            on_click=handle_attendance_click,
            args=(row['NAME'], tipo, user_id), # Pass arguments to the callback
            type="secondary" if presenca_registrada else "primary", # Uses Streamlit's default styling types
            use_container_width=True # Make button take full width of its column
        )

        # Add a small separator for visual clarity between athlete cards and their buttons
        st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True) # Increased space
