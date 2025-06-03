import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Consulta de Atletas")

st.markdown("<h2 style='text-align:center; color:white;'>📋 Consulta de Atletas Ativos</h2>", unsafe_allow_html=True)

# 🔄 Cache de dados
@st.cache_data
def load_fighters():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)]
    df = df.sort_values(by=["EVENT", "NAME"])
    
    # Formatando datas
    for col in ["DOB", "PASSPORT EXPIRE DATE"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime('%d/%m/%Y')

    return df.reset_index(drop=True)

# Estado da presença
if "attendance" not in st.session_state:
    st.session_state.attendance = {}

# 🔎 ID do usuário
user_id = st.text_input("🔍 Digite o ID do usuário para consulta:", placeholder="Ex: 123456")

# Dropdown de ação
selected_action = st.selectbox("Selecionar Tipo:", ["Blood Test", "PhotoShoot"], index=0)

# Filtro por presença
status_filter = st.radio("Mostrar:", ["Restantes", "Feitos", "Todos"], horizontal=True)

# Carrega dados
df = load_fighters()

# Aplica filtro do slider
if status_filter == "Restantes":
    df = df[~df["NAME"].isin(st.session_state.attendance.keys())]
elif status_filter == "Feitos":
    df = df[df["NAME"].isin(st.session_state.attendance.keys())]

# Render HTML
html = """
<style>
    .athlete-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid #444;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .athlete-info {
        display: flex;
        align-items: center;
        gap: 20px;
    }
    .athlete-img {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        object-fit: cover;
        border: 2px solid white;
    }
    .athlete-name {
        font-size: 18px;
        font-weight: bold;
    }
    .registered {
        color: lightgreen;
        font-weight: bold;
        font-size: 14px;
        margin-left: 10px;
    }
    .athlete-table {
        width: 100%;
        margin-top: 10px;
        border-collapse: collapse;
        font-size: 14px;
    }
    .athlete-table td {
        padding: 4px 8px;
        border: 1px solid #333;
    }
</style>
"""

st.markdown(html, unsafe_allow_html=True)

for idx, row in df.iterrows():
    name = row["NAME"]
    event = row.get("EVENT", "")
    picture_url = row["PICTURE"] if "PICTURE" in row and pd.notna(row["PICTURE"]) else None
    picture_html = f"<img src='{picture_url}' class='athlete-img'>" if picture_url else "<div class='athlete-img' style='background:#999;'></div>"

    is_registered = name in st.session_state.attendance

    bg_color = "#1c3b1c" if is_registered else "#1c1c1c"
    registration_status = "<span class='registered'>Attendance registrada</span>" if is_registered else ""

    st.markdown(f"<div class='athlete-row' style='background-color:{bg_color};'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='athlete-info'>
            {picture_html}
            <div class='athlete-name'>{name} {registration_status}<br><span style='font-size:13px; font-weight:normal;'>Evento: {event}</span></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    cols = st.columns([1, 1, 1, 1, 1, 2])
    cols[0].markdown(f"**Gênero:** {row.get('GENDER', '')}")
    cols[1].markdown(f"**Nascimento:** {row.get('DOB', '')}")
    cols[2].markdown(f"**Nacionalidade:** {row.get('NATIONALITY', '')}")
    cols[3].markdown(f"**Passaporte:** {row.get('PASSPORT', '')}")
    cols[4].markdown(f"**Expira em:** {row.get('PASSPORT EXPIRE DATE', '')}")
    if isinstance(row.get("PASSPORT IMAGE"), str) and row["PASSPORT IMAGE"].startswith("http"):
        cols[5].markdown(f"[Ver Imagem]({row['PASSPORT IMAGE']})")
    else:
        cols[5].markdown("—")

    if not is_registered:
        if st.button(f"Registrar Presença: {name}", key=f"btn_{idx}"):
            st.session_state.attendance[name] = selected_action
            st.experimental_rerun()

    st.markdown("</div>", unsafe_allow_html=True)
