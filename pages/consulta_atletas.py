import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="Consulta de Atletas", layout="wide")

# Conectar ao Google Sheets
@st.cache_resource
def connect_gsheet(sheet_name, tab_name):
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    worksheet = client.open(sheet_name).worksheet(tab_name)
    return worksheet

# Carregar dados dos atletas
@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)]
    df["EVENT"] = df["EVENT"].fillna("Z")
    df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce").dt.strftime("%d/%m/%Y")
    df["PASSPORT EXPIRE DATE"] = pd.to_datetime(df["PASSPORT EXPIRE DATE"], errors="coerce").dt.strftime("%d/%m/%Y")
    return df.sort_values(by=["EVENT", "NAME"])

# Registrar log
def registrar_log(nome, tipo, user_id):
    sheet = connect_gsheet("UAEW_App", "Attendance")
    data_registro = datetime.now().strftime("%d/%m/%Y %H:%M")
    nova_linha = [nome, data_registro, tipo, user_id]
    sheet.append_row(nova_linha, value_input_option="USER_ENTERED")

# Interface
st.markdown("<h1 style='font-size: 38px; margin-bottom: 10px;'>Consulta de Atletas</h1>", unsafe_allow_html=True)
user_id = st.text_input("Informe seu PS (ID de usuário)", max_chars=15)
tipo = st.selectbox("Tipo de verificação", ["Blood Test", "PhotoShoot"])
status_view = st.radio("Filtro", ["Todos", "Feitos", "Restantes"], horizontal=True)

df = load_data()

if "presencas" not in st.session_state:
    st.session_state["presencas"] = {}

for i, row in df.iterrows():
    presenca_id = f"{row['NAME']}_{tipo}"
    presenca_registrada = st.session_state["presencas"].get(presenca_id, False)

    if status_view == "Feitos" and not presenca_registrada:
        continue
    if status_view == "Restantes" and presenca_registrada:
        continue

    whatsapp = f"<tr><td style='padding: 6px;'><b>📱 WhatsApp:</b></td><td style='padding: 6px;'><a href='https://wa.me/{str(row['MOBILE'])}' target='_blank'>{str(row['MOBILE'])}</a></td></tr>" if pd.notna(row["MOBILE"]) else ""
    passaporte_img = f"<tr><td style='padding: 6px;'><b>📄</b></td><td style='padding: 6px;'><a href='{row['PASSPORT IMAGE']}' target='_blank'>Ver Passaporte</a></td></tr>" if pd.notna(row["PASSPORT IMAGE"]) else ""

    html = f"""
    <div style='background-color:{"#143d14" if presenca_registrada else "#1e1e1e"}; padding:20px; border-radius:12px; margin-bottom:20px;'>
        <div style='text-align:center;'>
            <img src='{row["IMAGE"]}' style='width:100px; height:100px; border-radius:50%; border:2px solid white; object-fit:cover;'><br>
            <h3 style='margin-top:10px; margin-bottom:5px;'>{row["NAME"]}</h3>
            <p style='margin:0; font-size:14px;'>Evento: <b>{row["EVENT"]}</b></p>
        </div>
        <table style='width:100%; font-size:14px; margin-top:20px;'>
            <tr><td style='padding: 6px;'><b>Gênero:</b></td><td style='padding: 6px;'>{row["GENDER"]}</td></tr>
            <tr><td style='padding: 6px;'><b>Nascimento:</b></td><td style='padding: 6px;'>{row["DOB"]}</td></tr>
            <tr><td style='padding: 6px;'><b>Nacionalidade:</b></td><td style='padding: 6px;'>{row["NATIONALITY"]}</td></tr>
            <tr><td style='padding: 6px;'><b>Passaporte:</b></td><td style='padding: 6px;'>{row["PASSPORT"]}</td></tr>
            <tr><td style='padding: 6px;'><b>Expira em:</b></td><td style='padding: 6px;'>{row["PASSPORT EXPIRE DATE"]}</td></tr>
            {whatsapp}
            {passaporte_img}
        </table>
    """

    if presenca_registrada:
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        continue

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    if st.button(f"Registrar presença de {row['NAME']}", key=f"attend_{i}"):
        if not user_id.strip():
            st.warning("⚠️ Informe seu PS antes de registrar a presença.")
        else:
            st.session_state["presencas"][presenca_id] = True
            registrar_log(row["NAME"], tipo, user_id)
            st.rerun()
