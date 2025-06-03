import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Consulta de Atletas Ativos")
st.markdown("<h1 style='text-align:center;'>🎯 Consulta de Atletas Ativos</h1>", unsafe_allow_html=True)

@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df["INACTIVE"] = df["INACTIVE"].astype(str).str.lower() == "true"
    return df

df = load_data()

# Filtro: somente fighters ativos
filtered = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)].copy()
filtered = filtered.sort_values(by=["EVENT", "NAME"])

# Estilo CSS
st.markdown("""
    <style>
    .circle-img {
        width: 70px;
        height: 70px;
        border-radius: 50%;
        overflow: hidden;
        margin-right: 15px;
        display: inline-block;
        vertical-align: middle;
    }
    .circle-img img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .fighter-name {
        font-weight: bold;
        font-size: 1.2rem;
        display: inline-block;
        vertical-align: middle;
    }
    .info-table {
        border-collapse: collapse;
        width: 100%;
        margin-top: 10px;
    }
    .info-table td {
        padding: 6px 10px;
        border: 1px solid #555;
    }
    .info-table td.title {
        background-color: #222;
        font-weight: bold;
        color: white;
        width: 250px;
    }
    .box {
        border: 1px solid #333;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 25px;
        background-color: #1c1c1c;
    }
    </style>
""", unsafe_allow_html=True)

for _, row in filtered.iterrows():
    img_url = row.get("PICTURE", "")
    nome = row.get("NAME", "")
    st.markdown(f"<div class='box'>", unsafe_allow_html=True)

    # Nome + imagem
    st.markdown(f"""
        <div class='circle-img'><img src='{img_url}'></div>
        <span class='fighter-name'>{nome}</span>
    """, unsafe_allow_html=True)

    # Tabela com dados
    st.markdown(f"""
        <table class='info-table'>
            <tr><td class='title'>Gender</td><td>{row.get("GENDER", "—")}</td></tr>
            <tr><td class='title'>Date of Birth</td><td>{row.get("DOB", "—")}</td></tr>
            <tr><td class='title'>Nationality</td><td>{row.get("NATIONALITY", "—")}</td></tr>
            <tr><td class='title'>Passport</td><td>{row.get("PASSPORT", "—")}</td></tr>
            <tr><td class='title'>Passport Expire Date</td><td>{row.get("PASSPORT EXPIRE DATE", "—")}</td></tr>
            <tr><td class='title'>Passport Image</td><td><a href='{row.get("PASSPORT IMAGE", "#")}' target='_blank'>Visualizar</a></td></tr>
        </table>
    """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
