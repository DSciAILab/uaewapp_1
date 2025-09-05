from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import html

# ------------------------------------------------------------------------------
# Bootstrap da página (config/layout/sidebar centralizados)
# ------------------------------------------------------------------------------
bootstrap_page("Fightcard")  # <- PRIMEIRA LINHA DA PÁGINA

st.title("Fightcard")
st.markdown("<h1 style='text-align:center; color:white;'>FIGHT CARDS</h1>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# Carregamento de dados
# ------------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    url = (
        "https://docs.google.com/spreadsheets/d/1_JIQmKWytwwkmjTYoxVFoxayk8lCv75hrfqKlEjdh58/"
        "gviz/tq?tqx=out:csv&sheet=Fightcard"
    )
    df = pd.read_csv(url)
    # normalização leve
    df.columns = df.columns.str.strip()
    for col in ("FightOrder", "Corner", "Event", "Fighter", "Division", "Picture"):
        if col not in df.columns:
            df[col] = pd.NA
    df["FightOrder"] = pd.to_numeric(df["FightOrder"], errors="coerce")
    df["Corner"] = df["Corner"].astype(str).str.strip().str.lower()
    df["Event"] = df["Event"].astype(str).str.strip()
    df["Fighter"] = df["Fighter"].astype(str).str.strip()
    df["Division"] = df["Division"].astype(str).str.strip()
    df["Picture"] = df["Picture"].astype(str).str.strip()
    return df

# ------------------------------------------------------------------------------
# Renderização HTML
# ------------------------------------------------------------------------------
def _first_row_or_none(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty:
        return None
    return df.iloc[0]

def _img_tag(url: str, cls: str) -> str:
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return f"<img src='{html.escape(url, True)}' class='{cls}'>"
    return ""

def render_fightcard_html(df: pd.DataFrame) -> str:
    css = '''
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700&display=swap');
        body, .main { background-color: #0e1117; color: white; font-family: 'Barlow Condensed', sans-serif; }
        .fightcard-table { width: 100%; border-collapse: collapse; margin-bottom: 50px; table-layout: fixed; }
        .fightcard-table th, .fightcard-table td { padding: 12px; text-align: center; vertical-align: middle; font-size: 16px; color: white; border-bottom: 1px solid #444; }
        .fightcard-img { width: 100px; height: 100px; object-fit: cover; border-radius: 8px; }
        .blue { background-color: #0d2d51; font-weight: bold; }
        .red { background-color: #3b1214; font-weight: bold; }
        .middle-cell { background-color: #2f2f2f; font-weight: bold; font-size: 14px; }
        .event-header { background-color: #111; color: white; font-weight: bold; text-align: center; font-size: 20px; padding: 12px; }
        .fightcard-table th { background-color: #1c1c1c; text-transform: uppercase; letter-spacing: 1px; }
        @media screen and (max-width: 768px) {
            .fightcard-table td, .fightcard-table th { font-size: 13px; padding: 8px; }
            .fightcard-img { width: 60px; height: 60px; }
        }
    </style>
    '''

    if df is None or df.empty:
        return css + "<p>No fights available.</p>"

    html_out = css
    # Agrupa por evento
    for event, group in df.groupby("Event", dropna=False):
        event_label = html.escape(str(event) if pd.notna(event) else "Unknown Event")
        # Ordena por FightOrder crescente
        group_sorted = group.sort_values(["FightOrder"], ascending=[True])

        html_out += f"<div class='event-header'>{event_label}</div>"
        html_out += '''
        <table class='fightcard-table'>
            <thead>
                <tr>
                    <th colspan='2'>Blue Corner</th>
                    <th>Fight Details</th>
                    <th colspan='2'>Red Corner</th>
                </tr>
            </thead>
            <tbody>
        '''

        # Agrupa por FightOrder e cria linhas
        for fight_order, fight_df in group_sorted.groupby("FightOrder", dropna=False):
            blue_row = _first_row_or_none(fight_df[fight_df["Corner"] == "blue"])
            red_row  = _first_row_or_none(fight_df[fight_df["Corner"] == "red"])

            blue_name = html.escape(str(blue_row.get("Fighter", ""))) if isinstance(blue_row, pd.Series) else ""
            red_name  = html.escape(str(red_row.get("Fighter", "")))  if isinstance(red_row, pd.Series)  else ""
            blue_img  = _img_tag(blue_row.get("Picture", ""), "fightcard-img") if isinstance(blue_row, pd.Series) else ""
            red_img   = _img_tag(red_row.get("Picture", ""), "fightcard-img")  if isinstance(red_row, pd.Series)  else ""

            # Division: prioriza do blue; se vazio, usa do red
            division_src = blue_row if isinstance(blue_row, pd.Series) else red_row
            division = html.escape(str(division_src.get("Division", ""))) if isinstance(division_src, pd.Series) else ""

            try:
                fo_int = int(fight_order) if pd.notna(fight_order) else "–"
            except Exception:
                fo_int = "–"

            info = f"FIGHT #{fo_int}<br>{division}"

            html_out += f"""
            <tr>
                <td class='blue'>{blue_img}</td>
                <td class='blue'>{blue_name}</td>
                <td class='middle-cell'>{info}</td>
                <td class='red'>{red_name}</td>
                <td class='red'>{red_img}</td>
            </tr>
            """

        html_out += "</tbody></table>"

    return html_out

# ------------------------------------------------------------------------------
# Execução
# ------------------------------------------------------------------------------
df = load_data()

# Altura dinâmica aproximada: 130px por luta + cabeçalhos/espaços
num_fights = 0 if df.empty else df["FightOrder"].nunique(dropna=False)
estimated_height = max(800, int(130 * max(num_fights, 1)) + 300)

html_string = render_fightcard_html(df)
st.components.v1.html(html_string, height=estimated_height, scrolling=True)
