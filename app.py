import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh

# 🔐 Conecta ao Google Sheets usando as credenciais do secrets
@st.cache_resource
def connect_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client

# 🔄 Carrega os dados da planilha como DataFrame
@st.cache_data(ttl=300)
def load_data(sheet_name):
    client = connect_client()
    sheet = client.open("UAEW_App").worksheet(sheet_name)
    data = sheet.get_all_records()
    return pd.DataFrame(data), sheet

# 📂 Atualiza célula específica
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# ⚙️ Configuração da interface
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")

# 🌙 Estilo escuro
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

# 🔐 Tela de login
st.sidebar.title("🔐 Login")
username = st.sidebar.text_input("Usuário")
password = st.sidebar.text_input("Senha", type="password")

if username and password:
    df_users, _ = load_data("Login")
    user_row = df_users[(df_users["USER"] == username) & (df_users["PASSWORD"] == password)]

    if not user_row.empty and str(user_row.iloc[0]["PERMISSION"]).upper() == "TRUE":
        st.sidebar.success(f"Bem-vindo, {username}!")

        # 📦 Carregamento dos dados principais
        df, sheet = load_data("Sheet1")

        st.title("🎯 Cards - UAE Warriors")

        for i, row in df.iterrows():
            with st.expander(f"🧍‍♂️ Atleta: {row['NAME']}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    row["Nationality"] = st.text_input("Nationality", value=row["Nationality"], key=f"nat_{i}")
                    row["Residence"] = st.text_input("Residence", value=row["Residence"], key=f"res_{i}")
                    row["Hight"] = st.text_input("Hight", value=row["Hight"], key=f"hgt_{i}")

                with col2:
                    row["Range"] = st.text_input("Range", value=row["Range"], key=f"rng_{i}")
                    row["Weight"] = st.text_input("Weight", value=row["Weight"], key=f"wgt_{i}")
                    row["Coach"] = st.text_input("Coach", value=row["Coach"], key=f"cch_{i}")

                with col3:
                    row["Music 1"] = st.text_input("Music 1", value=row["Music 1"], key=f"msc1_{i}")
                    row["Music 2"] = st.text_input("Music 2", value=row["Music 2"], key=f"msc2_{i}")
                    row["Music 3"] = st.text_input("Music 3", value=row["Music 3"], key=f"msc3_{i}")

                if st.button("Salvar", key=f"save_{i}"):
                    for campo in [
                        "Nationality", "Residence", "Hight", "Range", "Weight",
                        "Coach", "Music 1", "Music 2", "Music 3"
                    ]:
                        try:
                            valor = row[campo]
                            col_index = df.columns.get_loc(campo)
                            salvar_valor(sheet, i, col_index, valor)
                        except Exception as e:
                            st.error(f"Erro ao salvar linha {i}, campo {campo}: {e}")
                    st.success("Dados salvos com sucesso!")

    else:
        st.sidebar.error("Usuário ou senha incorretos ou sem permissão.")
else:
    st.warning("Por favor, faça login para acessar o aplicativo.")
