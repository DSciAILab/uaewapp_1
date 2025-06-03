import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(layout="wide", page_title="Consulta Atletas")

# --- Autenticação Google Sheets ---
@st.cache_resource
def authenticate_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name("gs_credentials.json", scope)
    gc = gspread.authorize(credentials)
    return gc

gc = authenticate_gsheet()
sheet = gc.open_by_url("https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/edit")
ws_df = sheet.worksheet("df")
df = pd.DataFrame(ws_df.get_all_records())

# --- Formatando datas ---
def format_date(date_str):
    try:
        return pd.to_datetime(date_str).strftime("%d/%m/%Y")
    except:
        return ""

df["DOB"] = df["DOB"].apply(format_date)
df["PASSPORT EXPIRE DATE"] = df["PASSPORT EXPIRE DATE"].apply(format_date)

# --- Filtros iniciais ---
st.markdown("<h2 style='text-align:center; color:white;'>Consulta de Atletas Ativos</h2>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([2, 2, 2])

with col1:
    selected_type = st.selectbox("Selecionar tipo:", ["Blood Test", "PhotoShoot"])

with col2:
    user_id = st.text_input("Insira seu ID (PS)", placeholder="Ex: PS-123")

with col3:
    filter_slider = st.radio("Mostrar:", ["Restantes", "Feitos", "Todos"], horizontal=True)

# --- Filtrar lutadores ativos ---
df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == "FALSE")]
df = df.sort_values(by=["EVENT", "NAME"])

# --- Sessão de estado local ---
if "attendance" not in st.session_state:
    st.session_state.attendance = {}

# --- Layout por lutador ---
for idx, row in df.iterrows():
    fighter_key = f"{row['NAME']}_{selected_type}"
    attendance_done = st.session_state.attendance.get(fighter_key, False)

    if filter_slider == "Feitos" and not attendance_done:
        continue
    if filter_slider == "Restantes" and attendance_done:
        continue

    with st.container():
        st.markdown("<hr style='border-top: 1px solid gray;'>", unsafe_allow_html=True)

        col1, col2 = st.columns([1, 5])

        with col1:
            if row["PICTURE"]:
                st.image(row["PICTURE"], width=80, caption="", use_column_width=False)
            else:
                st.markdown("<div style='width:80px; height:80px; border-radius:50%; background:#ccc;'></div>", unsafe_allow_html=True)

        with col2:
            name_line = f"### {row['NAME']}"
            if attendance_done:
                name_line += " ✅ *Attendance registrada*"
            st.markdown(name_line)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**Evento:** {row['EVENT']}")
                st.markdown(f"**Gênero:** {row['GENDER']}")
                st.markdown(f"**Nascimento:** {row['DOB']}")
                st.markdown(f"**Passaporte:** {row['PASSPORT']}")
                if row["PASSPORT IMAGE"]:
                    st.markdown(f"[📎 Ver Passaporte]({row['PASSPORT IMAGE']})", unsafe_allow_html=True)

            with col_b:
                st.markdown(f"**Nacionalidade:** {row['NATIONALITY']}")
                st.markdown(f"**Expira:** {row['PASSPORT EXPIRE DATE']}")
                if row.get("MOBILE"):
                    number = row["MOBILE"].replace(" ", "").replace("+", "")
                    st.markdown(f"[📱 Enviar WhatsApp](https://wa.me/{number})", unsafe_allow_html=True)

            # --- Botão de presença ---
            if not attendance_done:
                if st.button(f"Registrar presença - {row['NAME']}", key=fighter_key):
                    if not user_id:
                        st.warning("⚠️ Informe seu PS (ID) antes de registrar a presença.")
                    else:
                        st.session_state.attendance[fighter_key] = True

                        # Gravação na aba "Attendance"
                        ws_attendance = sheet.worksheet("Attendance")
                        last_row = len(ws_attendance.get_all_values()) + 1
                        today = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                        ws_attendance.append_row([row["NAME"], today, selected_type, user_id])

                        st.success("✅ Presença registrada com sucesso.")
