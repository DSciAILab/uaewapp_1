import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta # Import timedelta for date comparisons

# --- Configuration ---
st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# --- Google Sheets Authentication and Connection ---
# Use st.secrets more robustly and handle potential missing keys
@st.cache_resource(ttl=3600) # Cache connection for 1 hour
def connect_gsheet(sheet_name: str, tab_name: str):
    """
    Establishes and caches a connection to a Google Sheet worksheet.
    """
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        # Ensure 'gcp_service_account' is correctly structured in st.secrets
        # It should be a dictionary-like object with all service account keys
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        worksheet = client.open(sheet_name).worksheet(tab_name)
        st.success(f"Successfully connected to Google Sheet: '{sheet_name}' tab: '{tab_name}'")
        return worksheet
    except KeyError as e:
        st.error(f"Configuration error: Missing Google Cloud service account key in `st.secrets`. Details: {e}")
        st.stop() # Stop execution if credentials are not found
    except Exception as e:
        st.error(f"Error connecting to Google Sheet: {e}")
        st.stop() # Stop execution on connection failure

# --- Data Loading ---
@st.cache_data(ttl=600) # Cache data for 10 minutes (adjust as needed)
def load_data():
    """
    Loads and preprocesses athlete data from a Google Sheet CSV export.
    Filters by 'ROLE' and 'INACTIVE' status, and formats date columns.
    """
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()

        # Filter initial dataframe for performance
        df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy() # Use .copy() to avoid SettingWithCopyWarning

        # Standardize column names for easier access if they might vary
        # (Assuming your sheet columns are always 'EVENT', 'DOB', 'PASSPORT EXPIRE DATE', 'BLOOD TEST', 'IMAGE', 'NAME', 'GENDER', 'NATIONALITY', 'PASSPORT')

        # Fill 'EVENT' NaN values before sorting
        df["EVENT"] = df["EVENT"].fillna("Z")

        # Convert and format date columns, handle errors gracefully
        date_cols = ["DOB", "PASSPORT EXPIRE DATE", "BLOOD TEST"]
        for col in date_cols:
            # Use errors='coerce' to turn unparseable dates into NaT (Not a Time)
            df[col] = pd.to_datetime(df[col], errors="coerce")
            # Only format valid dates, otherwise leave as NaT or empty string
            df[col] = df[col].dt.strftime("%d/%m/%Y").fillna("") # Fill NaT with empty string for display

        # Ensure 'IMAGE' column exists and handle potential NaNs if images are optional
        if "IMAGE" not in df.columns:
            df["IMAGE"] = "" # Add an empty column if not present
        df["IMAGE"] = df["IMAGE"].fillna("") # Fill any NaN image URLs with empty string

        st.success("Athlete data loaded and processed successfully.")
        return df.sort_values(by=["EVENT", "NAME"]).reset_index(drop=True) # Reset index after sorting and filtering
    except Exception as e:
        st.error(f"Error loading or processing data: {e}")
        st.info("Please check the Google Sheet URL and column names.")
        st.stop() # Stop execution on data loading failure

# --- Logging Function ---
def registrar_log(nome: str, tipo: str, user_id: str):
    """
    Registers an attendance log entry in the 'Attendance' Google Sheet.
    """
    try:
        sheet = connect_gsheet("UAEW_App", "Attendance") # Reconnect if necessary or use cached connection
        data_registro = datetime.now().strftime("%d/%m/%Y %H:%M")
        nova_linha = [nome, data_registro, tipo, user_id]
        sheet.append_row(nova_linha, value_input_option="USER_ENTERED")
        st.success(f"Attendance registered for {nome} ({tipo}).")
    except Exception as e:
        st.error(f"Error registering attendance: {e}")
        st.warning("Could not log attendance. Please check sheet permissions or connection.")

# --- Helper Function for Blood Test Expiration ---
def is_blood_test_expired(blood_test_date_str: str) -> bool:
    """
    Checks if a blood test date is older than 6 months.
    Expects date in "DD/MM/YYYY" format.
    """
    if not blood_test_date_str: # If no date provided
        return True # Consider it expired/invalid
    try:
        blood_test_date = datetime.strptime(blood_test_date_str, "%d/%m/%Y")
        six_months_ago = datetime.now() - timedelta(days=180) # Approximately 6 months
        return blood_test_date < six_months_ago
    except ValueError:
        return True # Invalid date format, consider it expired for safety

# --- Streamlit UI ---
st.title("Consulta de Atletas")

# Input fields at the top
user_id = st.text_input("Informe seu PS (ID de usuário)", max_chars=15, help="Seu ID de usuário para registrar a presença.")
tipo = st.selectbox("Tipo de verificação", ["Blood Test", "PhotoShoot"], help="Selecione o tipo de verificação para o atleta.")
status_view = st.radio("Filtro", ["Todos", "Feitos", "Restantes"], horizontal=True, help="Filtre os atletas por status de verificação.")

# Load data once
df = load_data()

# Initialize session state for attendance tracking if not already present
if "presencas" not in st.session_state:
    st.session_state["presencas"] = {}

# Display athlete cards
if df.empty:
    st.info("No athletes found matching the criteria.")
else:
    for i, row in df.iterrows():
        presenca_id = f"{row['NAME']}_{tipo}"
        presenca_registrada = st.session_state["presencas"].get(presenca_id, False)

        # Apply filters
        if status_view == "Feitos" and not presenca_registrada:
            continue
        if status_view == "Restantes" and presenca_registrada:
            continue

        # Prepare blood test information and styling
        blood_info = ""
        blood_test_date_display = row.get("BLOOD TEST", "")
        is_expired = False

        if tipo == "Blood Test":
            if pd.notna(blood_test_date_display) and str(blood_test_date_display).strip() != "":
                is_expired = is_blood_test_expired(blood_test_date_display)
                color = "red" if is_expired else "white" # Red for expired, white for valid
                blood_info = f"<p style='margin:0; font-size:13px; color:{color};'>Blood Test in: {blood_test_date_display}{' (Expired)' if is_expired else ''}</p>"
            else:
                blood_info = "<p style='margin:0; font-size:13px; color:red;'>Blood Test: Not Recorded</p>"


        # Dynamic button text
        button_text = f"Subscrever attendance por uma nova?" if presenca_registrada else "Registrar Attendance"
        button_color = "darkgreen" if presenca_registrada else "#007bff" # Use a more standard blue for default button

        # HTML for the athlete card
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
            <div style='margin-top:15px; text-align:right;'>
                <button style='background-color:{button_color}; color:white; padding:10px 20px; border:none; border-radius:5px; cursor:pointer; font-size:16px;'
                        onclick="window.parent.document.querySelector('[data-testid=\"stButton-primary-{i}\"] button').click();">
                    {button_text}
                </button>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Streamlit button to trigger the action (hidden, but clicked by the HTML button)
        # This is a common workaround to style buttons with custom HTML and still use Streamlit's callback
        if st.button(f"Hidden button for {row['NAME']} - {button_text}", key=f"attend_button_{i}", help="This is a hidden button to trigger attendance registration.",
                     use_container_width=False, # Important to prevent it from taking full width
                     type="secondary" if presenca_registrada else "primary"): # Use type for default styling if not hidden
            if not user_id.strip():
                st.warning("⚠️ Informe seu PS antes de registrar a presença.", icon="🚨")
            else:
                st.session_state["presencas"][presenca_id] = True
                registrar_log(row["NAME"], tipo, user_id)
                st.rerun() # Rerun to update the UI status

