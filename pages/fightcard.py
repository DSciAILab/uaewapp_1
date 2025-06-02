import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

@st.cache_data
def load_data():
    # Substitua pelo seu próprio método de carregamento do Google Sheets
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-.../pub?output=csv"
    df = pd.read_csv(url)
    df.columns = df.columns.str.strip()
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    df["Corner"] = df["Corner"].str.strip().str.lower()
    return df

def render_fightcard_html(df):
    grouped = df.groupby(["Event", "FightOrder"], sort=False)

    html = "<style>\n"
    html += """
    .fightcard-table {
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 30px;
        font-family: Arial, sans-serif;
    }
    .fightcard-table td {
        padding: 10px;
        text-align: center;
        vertical-align: middle;
    }
    .fightcard-img {
        width: 100px;
        height: 100px;
        object-fit: cover;
        border-radius: 50%;
        border: 2px solid #ccc;
    }
    .blue {
        background-color: #d0e7ff;
        font-weight: bold;
    }
    .red {
        background-color: #ffd4d4;
        font-weight: bold;
    }
    .middle-cell {
        background-color: #f4f4f4;
        font-size: 14px;
        font-weight: bold;
    }
    .event-header {
        font-size: 20px;
        font-weight: bold;
        padding: 15px 0;
        text-align: left;
    }
    """
    html += "</style>\n"

    current_event = None
    html += "<table class='fightcard-table'>\n"
    html += "<tr><th colspan='5' class='event-header'></th></tr>"

    for (event, order), fighters in grouped:
        if event != current_event:
            html += f"<tr><td colspan='5' class='event-header'>{event}</td></tr>"
            html += """
            <tr>
                <th>Blue Corner</th><th>Fighter</th><th>Fight Info</th><th>Fighter</th><th>Red Corner</th>
            </tr>
            """
            current_event = event

        blue_row = fighters[fighters["Corner"] == "blue"]
        red_row = fighters[fighters["Corner"] == "red"]

        blue = blue_row.squeeze() if not blue_row.empty else {}
        red = red_row.squeeze() if not red_row.empty else {}

        blue_img = f"<img src='{blue.get('Picture', '')}' class='fightcard-img'>" if blue and blue.get("Picture") else ""
        red_img = f"<img src='{red.get('Picture', '')}' class='fightcard-img'>" if red and red.get("Picture") else ""

        blue_name = blue.get("Fighter", "") if blue else ""
        red_name = red.get("Fighter", "") if red else ""
        division = blue.get("Division", "") or red.get("Division", "") or ""
        fight_info = f"FIGHT #{int(order)}<br>{division}"

        html += f"""
        <tr>
            <td class='blue'>{blue_img}</td>
            <td class='blue'>{blue_name}</td>
            <td class='middle-cell'>{fight_info}</td>
            <td class='red'>{red_name}</td>
            <td class='red'>{red_img}</td>
        </tr>
        """

    html += "</table>"
    return html

# Página principal
df = load_data()
st.markdown("<h2 style='text-align:center;'>Fight Card</h2>", unsafe_allow_html=True)
html = render_fightcard_html(df)
st.markdown(html, unsafe_allow_html=True)
