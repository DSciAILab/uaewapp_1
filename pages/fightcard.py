import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Fightcard", layout="wide")

# Estilo básico
st.markdown("""
<style>
.fightcard-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}
.fightcard-table td {
    border: 1px solid #555;
    padding: 8px;
    text-align: center;
    vertical-align: middle;
}
.fighter-img {
    width: 100px;
    height: 100px;
    border-radius: 8px;
    object-fit: cover;
}
.fightorder-row {
    background-color: #222;
    font-weight: bold;
    color: #fff;
}
</style>
""", unsafe_allow_html=True)

# 🔐 Conexão segura com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Fightcard")

sheet = connect_sheet()

# 📥 Carregar dados da aba Fightcard
@st.cache_data(ttl=60)
def load_data():
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "")
    df["Fight_Order"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    return df

df = load_data()

# 🔁 Agrupar por evento e ordem de luta
grouped = df.groupby(["Event", "Fight_Order"])

st.title("🥊 Fightcard Visual")

for (event, fight_order), group in grouped:
    if group.shape[0] != 2:
        st.warning(f"{event} - Fight {fight_order}: precisa ter 2 lutadores.")
        continue

    azul = group[group["Corner"].str.lower() == "blue"]
    vermelho = group[group["Corner"].str.lower() == "red"]

    if azul.empty or vermelho.empty:
        st.warning(f"{event} - Fight {fight_order}: corner azul ou vermelho ausente.")
        continue

    fighter_azul = azul.iloc[0]
    fighter_vermelho = vermelho.iloc[0]

    table_html = f"""
    <table class='fightcard-table'>
        <tr class='fightorder-row'>
            <td colspan='3'>Event: {event} | Fight {fight_order}</td>
        </tr>
        <tr>
            <td><img src="{fighter_azul['Picture']}" class='fighter-img'></td>
            <td></td>
            <td><img src="{fighter_vermelho['Picture']}" class='fighter-img'></td>
        </tr>
        <tr>
            <td>{fighter_azul['Fighter']}</td>
            <td>VS</td>
            <td>{fighter_vermelho['Fighter']}</td>
        </tr>
        <tr>
            <td>{fighter_azul['Division']}</td>
            <td></td>
            <td>{fighter_vermelho['Division']}</td>
        </tr>
    </table>
    """

    st.markdown(table_html, unsafe_allow_html=True)
