import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Fightcard", layout="wide")

# Estilo para centralizar imagens e tabelas
st.markdown("""
    <style>
        .fightcard-table {
            width: 100%;
            border-collapse: collapse;
        }
        .fightcard-table th, .fightcard-table td {
            border: 1px solid #444;
            padding: 10px;
            text-align: center;
            color: white;
        }
        .fightcard-header {
            background-color: #111;
            font-weight: bold;
            font-size: 1.2rem;
        }
        .fightcard-img {
            height: 100px;
            border-radius: 6px;
        }
        .blue { background-color: rgba(0, 123, 255, 0.15); }
        .red { background-color: rgba(255, 0, 0, 0.1); }
    </style>
""", unsafe_allow_html=True)

# Conexão com Google Sheets
@st.cache_resource
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open("UAEW_App").worksheet("Fightcard")

sheet = connect_sheet()

# Carregamento dos dados
@st.cache_data(ttl=30)
def load_data():
    df = pd.DataFrame(sheet.get_all_records())
    df.columns = df.columns.str.strip().str.replace(" ", "_").str.replace("-", "_")
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    return df

df = load_data()

# Agrupar por Evento e Ordem de Luta
agrupado = df.groupby(["Event", "FightOrder"])

st.title("📋 Fightcard Oficial")

# Renderizar os pares de lutadores lado a lado
for (evento, ordem), grupo in agrupado:
    if grupo.shape[0] != 2:
        continue  # pula se não houver dois lutadores na luta

    lutadores = grupo.sort_values(by="Corner", ascending=False)  # Azul primeiro, depois Vermelho

    azul = lutadores[lutadores["Corner"].str.lower() == "blue"].iloc[0]
    vermelho = lutadores[lutadores["Corner"].str.lower() == "red"].iloc[0]

    st.markdown(f"<h4 style='text-align:center; margin-top:30px;'>{evento} — Fight #{int(ordem)}</h4>", unsafe_allow_html=True)
    st.markdown(f"""
    <table class='fightcard-table'>
        <tr class='fightcard-header'>
            <td class='blue'>Picture</td>
            <td class='blue'>Fighter</td>
            <td class='blue'>Division</td>
            <td>VS</td>
            <td class='red'>Division</td>
            <td class='red'>Fighter</td>
            <td class='red'>Picture</td>
        </tr>
        <tr>
            <td class='blue'><img src="{azul.Picture}" class="fightcard-img"></td>
            <td class='blue'>{azul.Fighter}</td>
            <td class='blue'>{azul.Division}</td>
            <td><strong>X</strong></td>
            <td class='red'>{vermelho.Division}</td>
            <td class='red'>{vermelho.Fighter}</td>
            <td class='red'><img src="{vermelho.Picture}" class="fightcard-img"></td>
        </tr>
    </table>
    """, unsafe_allow_html=True)
