import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# CONFIGURAÇÃO
st.set_page_config(layout="wide", page_title="Consulta de Atletas")

# CAIXA DE TEXTO PARA PS ID
ps_id = st.text_input("Informe seu PS", "")

# DROPDOWN DO TOPO
tipo_selecionado = st.selectbox("Selecionar tipo:", ["Blood Test", "PhotoShoot"])

# SLIDER
filtro_attendance = st.radio("Visualizar:", ["Todos", "Restantes", "Feitos"], horizontal=True)

# CONEXÃO COM GOOGLE SHEETS
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client

client = connect_sheet()
sheet_df = client.open("UAEW_App").worksheet("df")
sheet_att = client.open("UAEW_App").worksheet("Attendance")

@st.cache_data(ttl=30)
def load_data():
    df = pd.DataFrame(sheet_df.get_all_records())
    df.columns = df.columns.str.strip().str.upper()
    df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"].astype(str).str.lower() != "true")]
    df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce").dt.strftime("%d/%m/%Y")
    df["PASSPORT EXPIRE DATE"] = pd.to_datetime(df["PASSPORT EXPIRE DATE"], errors="coerce").dt.strftime("%d/%m/%Y")
    df = df.sort_values(by=["EVENT", "NAME"])
    return df

df = load_data()

# FILTRO POR ATTENDANCE
if "attendance_log" not in st.session_state:
    st.session_state.attendance_log = {}

if filtro_attendance == "Feitos":
    df = df[df["NAME"].isin(st.session_state.attendance_log)]
elif filtro_attendance == "Restantes":
    df = df[~df["NAME"].isin(st.session_state.attendance_log)]

# VISUALIZAÇÃO DOS ATLETAS
for idx, row in df.iterrows():
    with st.container():
        col1, col2 = st.columns([1, 5])
        with col1:
            if row.get("PICTURE"):
                st.image(row["PICTURE"], width=80)
        with col2:
            nome = row["NAME"]
            registro = nome in st.session_state.attendance_log
            st.markdown(f"### {nome}")
            cols_info = st.columns(5)
            cols_info[0].markdown(f"**Gênero:** {row.get('GENDER', '')}")
            cols_info[1].markdown(f"**Nascimento:** {row.get('DOB', '')}")
            cols_info[2].markdown(f"**Nacionalidade:** {row.get('NATIONALITY', '')}")
            cols_info[3].markdown(f"**Passaporte:** {row.get('PASSPORT', '')}")
            cols_info[4].markdown(f"**Expira em:** {row.get('PASSPORT EXPIRE DATE', '')}")

            col_links = st.columns(2)
            mobile = str(row.get("MOBILE", "")).replace("+", "").replace(" ", "")
            if mobile:
                col_links[0].markdown(f"[📲 WhatsApp](https://wa.me/{mobile})")
            if row.get("PASSPORT IMAGE"):
                col_links[1].markdown(f"[🛂 Ver Passaporte]({row['PASSPORT IMAGE']})")

            # BOTÃO DE ATTENDANCE
            if not registro:
                if st.button(f"✅ Registrar Attendance", key=f"att_{idx}"):
                    if not ps_id:
                        st.warning("Informe seu PS para registrar.")
                    else:
                        now = datetime.now().strftime("%d/%m/%Y %H:%M")
                        sheet_att.append_row([nome, now, tipo_selecionado, ps_id])
                        st.session_state.attendance_log[nome] = True
                        st.success("Attendance registrada com sucesso!")
                        st.rerun()
            else:
                st.success("✅ Attendance registrada")
