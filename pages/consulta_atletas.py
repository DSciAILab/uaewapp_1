import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(layout="wide", page_title="Fighters Attendance")

st.markdown("<h2 style='text-align:center; color:white;'>🧾 FIGHTERS ATTENDANCE</h2>", unsafe_allow_html=True)

@st.cache_data
def load_data():
    url = "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/gviz/tq?tqx=out:csv&sheet=df"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df = df[(df["ROLE"] == "1 - Fighter") & (df["INACTIVE"] == False)]
    df["EVENT"] = df["EVENT"].fillna("Unknown")
    df["DOB"] = pd.to_datetime(df["DOB"], errors="coerce").dt.strftime('%d/%m/%Y')
    df["PASSPORT EXPIRE DATE"] = pd.to_datetime(df["PASSPORT EXPIRE DATE"], errors="coerce").dt.strftime('%d/%m/%Y')
    df = df.sort_values(by=["EVENT", "NAME"])
    return df.reset_index(drop=True)

df = load_data()

# Interface de filtro
col1, col2 = st.columns([3, 2])
with col1:
    selected_type = st.selectbox("🔽 Select Type", ["Blood Test", "PhotoShoot"])

with col2:
    filter_status = st.radio("🔄 Filter By", ["Todos", "Feitos", "Restantes"], horizontal=True)

# Sessão de presença temporária
if "attendance" not in st.session_state:
    st.session_state.attendance = {}

# Campo de ID (ainda não usado funcionalmente, mas visível)
user_id = st.text_input("🔑 Enter Your ID", "")

# Renderizar os lutadores
for idx, row in df.iterrows():
    fighter_id = str(row["ID"])
    is_present = st.session_state.attendance.get(fighter_id, False)

    # Filtragem por slider
    if filter_status == "Feitos" and not is_present:
        continue
    if filter_status == "Restantes" and is_present:
        continue

    row_color = "#1f5121" if is_present else "#0e1117"

    with st.container():
        st.markdown(f"""
            <div style='background:{row_color}; padding:15px; border-radius:10px; margin-bottom:10px; color:white;'>
                <div style='display:flex; align-items:center; gap:20px;'>
                    <img src='{row["PICTURE"]}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid white;'>
                    <div style='flex-grow:1;'>
                        <h4 style='margin:0;'>{row["NAME"]} {"✅ Attendance registrada" if is_present else ""}</h4>
                        <p style='margin:0; font-size:13px;'>Event: {row["EVENT"]}</p>
                    </div>
                    <form action='/{selected_type}/{fighter_id}' method='post'>
                        <button type='submit' name='attendance' style='padding:8px 16px; background:#4CAF50; color:white; border:none; border-radius:6px; cursor:pointer;'>Attendance</button>
                    </form>
                </div>
                <hr style='border:1px solid #444;'>
                <table style='width:100%; color:white; font-size:14px;'>
                    <tr><td><b>Gender:</b></td><td>{row["GENDER"]}</td></tr>
                    <tr><td><b>DOB:</b></td><td>{row["DOB"]}</td></tr>
                    <tr><td><b>Nationality:</b></td><td>{row["NATIONALITY"]}</td></tr>
                    <tr><td><b>Passport:</b></td><td>{row["PASSPORT"]}</td></tr>
                    <tr><td><b>Expiry:</b></td><td>{row["PASSPORT EXPIRE DATE"]}</td></tr>
                    <tr><td><b>Passport Image:</b></td><td><a href="{row["PASSPORT IMAGE"]}" target="_blank">📎 View</a></td></tr>
                </table>
            </div>
        """, unsafe_allow_html=True)

        # Botão funcional
        if st.button(f"Registrar presença para {row['NAME']}", key=f"btn_{fighter_id}"):
            st.session_state.attendance[fighter_id] = True
            st.experimental_rerun()
