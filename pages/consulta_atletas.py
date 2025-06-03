import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- Autenticação com Google Sheets ---
@st.cache_resource
def authenticate_gsheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_file("gs_credentials.json", scopes=scope)
    return gspread.authorize(credentials)

# --- Carregar dados da aba "df" ---
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)]
    df["EVENT"] = df["EVENT"].fillna("No Event")
    df["NAME"] = df["NAME"].fillna("Unknown")
    df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce").dt.strftime("%d/%m/%Y")
    df["PASSPORT EXPIRE DATE"] = pd.to_datetime(df["PASSPORT EXPIRE DATE"], errors="coerce").dt.strftime("%d/%m/%Y")
    return df.sort_values(by=["EVENT", "NAME"])

# --- Registrar presença na aba Attendance ---
def log_attendance(gclient, name, user_id, tipo):
    sheet = gclient.open_by_key("1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58")
    worksheet = sheet.worksheet("Attendance")
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    worksheet.append_row([name, now, tipo, user_id])

# --- Página Streamlit ---
st.set_page_config(layout="wide", page_title="Athlete Check")

st.markdown("<h2 style='text-align:center; color:white;'>ATHLETE ATTENDANCE SYSTEM</h2>", unsafe_allow_html=True)
st.markdown("---")

user_id = st.text_input("🔐 Enter your PS ID to proceed:")
tipo = st.selectbox("📋 Select Check Type:", ["Blood Test", "PhotoShoot"])
status_filter = st.radio("📊 Show:", ["Restantes", "Feitos", "Todos"], horizontal=True)

df = load_data()
gclient = authenticate_gsheet()

if "checked" not in st.session_state:
    st.session_state.checked = {}

for idx, row in df.iterrows():
    name = row["NAME"]
    event = row["EVENT"]

    if status_filter == "Feitos" and not st.session_state.checked.get(name):
        continue
    if status_filter == "Restantes" and st.session_state.checked.get(name):
        continue

    pic = row.get("PICTURE", "")
    whatsapp = row.get("MOBILE", "")
    passport = row.get("PASSPORT IMAGE", "")

    # Estilo visual
    style = """
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 15px;
        margin-bottom: 10px;
        background-color: #111;
        border: 1px solid #444;
        border-radius: 10px;
    """
    if st.session_state.checked.get(name):
        style += "border: 2px solid green; background-color: #123212;"

    with st.container():
        st.markdown(f"<div style='{style}'>", unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns([1, 2, 3, 2])

        with col1:
            if pic:
                st.markdown(f"<img src='{pic}' style='width:80px; height:80px; border-radius:50%; border:2px solid white; object-fit:cover;'>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='width:80px; height:80px; background:#555; border-radius:50%;'></div>", unsafe_allow_html=True)

        with col2:
            st.markdown(f"**{name}**")
            st.markdown(f"**Event**: {event}")
            st.markdown(f"**Gender**: {row.get('GENDER', '')}")
            st.markdown(f"**DOB**: {row.get('DOB', '')}")
            st.markdown(f"**Nationality**: {row.get('NATIONALITY', '')}")

        with col3:
            st.markdown(f"**Passport**: {row.get('PASSPORT', '')}")
            st.markdown(f"**Expires**: {row.get('PASSPORT EXPIRE DATE', '')}")
            if passport:
                st.markdown(f"[📄 View Passport]({passport})", unsafe_allow_html=True)
            if whatsapp:
                st.markdown(f"[📲 WhatsApp](https://wa.me/{whatsapp})", unsafe_allow_html=True)

        with col4:
            if st.session_state.checked.get(name):
                st.success("✔ Attendance recorded")
            else:
                if st.button(f"Mark Attendance - {name}"):
                    if not user_id.strip():
                        st.warning("⚠ Please enter your PS ID to register attendance.")
                    else:
                        st.session_state.checked[name] = True
                        log_attendance(gclient, name, user_id, tipo)
                        st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
