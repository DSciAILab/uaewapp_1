# 📄 fightcard.py — UAE Warriors App
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 🎛️ Configuração da página
st.set_page_config(page_title="FightCard", layout="wide")

# 🔐 Autenticação e conexão com a aba Fightcard
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Fightcard")

sheet = connect_sheet()

# 🔄 Carregar dados
@st.cache_data(ttl=60)
def load_data():
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("\u00a0", "")
    df["Fight_Order"] = pd.to_numeric(df["Fight_Order"], errors="coerce")
    return df

df = load_data()

# 🎨 Estilo CSS para centralizar e exibir imagens
st.markdown("""
<style>
.card-table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
    background-color: #111;
    border: 1px solid #333;
    font-size: 0.9rem;
}
.card-table th, .card-table td {
    border: 1px solid #444;
    padding: 10px;
    text-align: center;
    vertical-align: middle;
    color: white;
}
.card-table img {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    object-fit: cover;
}
.card-table th {
    background-color: #222;
}
</style>
""", unsafe_allow_html=True)

# 👥 Agrupamento por evento e luta
grouped = df.groupby(["Event", "Fight_Order"])

st.title("🧾 FightCard - UAE Warriors")

for (event, fight_order), group in grouped:
    if len(group) != 2:
        continue  # ignorar entradas incompletas

    azul = group[group["Corner"].str.lower() == "blue"].iloc[0]
    vermelho = group[group["Corner"].str.lower() == "red"].iloc[0]

    st.markdown(f"### 🥊 {event} — Fight #{int(fight_order)}")

    table_html = f"""
    <table class="card-table">
        <tr>
            <th>Picture</th><th>Fighter</th><th>Division</th>
            <th>Picture</th><th>Fighter</th><th>Division</th>
        </tr>
        <tr>
            <td><img src="{azul['Picture']}" /></td>
            <td>{azul['Fighter']}</td>
            <td>{azul['Division']}</td>
            <td><img src="{vermelho['Picture']}" /></td>
            <td>{vermelho['Fighter']}</td>
            <td>{vermelho['Division']}</td>
        </tr>
    </table>
    """

    st.markdown(table_html, unsafe_allow_html=True)
