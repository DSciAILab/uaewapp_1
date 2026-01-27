from components.layout import bootstrap_page
import streamlit as st
import pandas as pd
import html

# ------------------------------------------------------------------------------
# Bootstrap da página (config/layout/sidebar centralizados)
# ------------------------------------------------------------------------------
bootstrap_page("Fight Cards")  # <- PRIMEIRA LINHA DA PÁGINA

st.markdown("<h1 style='text-align: center; margin-bottom: 40px;'>Fight Cards</h1>", unsafe_allow_html=True)

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
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        :root {
            --fc-bg-color: #0e1117;
            --fc-card-bg: #1e1e1e;
            --fc-blue-bg: linear-gradient(135deg, #0d2d51 0%, #164070 100%);
            --fc-red-bg: linear-gradient(135deg, #3b1214 0%, #601d21 100%);
            --fc-text-color: #ffffff;
            --fc-border-radius: 12px;
            --fc-gap: 16px;
        }

        body, .main { 
            background-color: var(--fc-bg-color); 
            color: var(--fc-text-color); 
            font-family: 'Outfit', sans-serif; 
        }

        .event-container {
            margin-bottom: 60px;
            max-width: 1200px; /* Limita a largura em telas grandes (1920px) */
            margin-left: auto;
            margin-right: auto;
        }

        .event-header {
            background: linear-gradient(90deg, #111, #222, #111);
            color: #ccc;
            text-transform: uppercase;
            letter-spacing: 2px;
            font-weight: 800;
            text-align: center;
            font-size: 24px;
            padding: 20px;
            border-radius: var(--fc-border-radius);
            margin-bottom: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            border: 1px solid #333;
        }

        .match-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background-color: var(--fc-card-bg);
            border-radius: var(--fc-border-radius);
            margin-bottom: var(--fc-gap);
            padding: 0;
            overflow: hidden;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            border: 1px solid #333;
            height: 140px; /* Fixed height for consistency on desktop */
            position: relative;
        }

        /* --- CORNER STYLES --- */
        .corner {
            flex: 1;
            display: flex;
            align-items: center;
            padding: 10px;
            height: 100%;
            position: relative;
        }
        
        .corner.blue {
            background: var(--fc-blue-bg);
            justify-content: flex-start;
            text-align: right; /* Alinha texto para a direita */
            flex-direction: row-reverse; /* Flip: Text | Img */
        }
        
        .corner.red {
            background: var(--fc-red-bg);
            justify-content: flex-end; /* Image on right */
            text-align: left; /* Alinha texto para a esquerda (perto do VS) */
            flex-direction: row-reverse; /* Flip order: Name | Img */
        }

        .fighter-img {
            width: 110px;
            height: 110px;
            object-fit: cover;
            border-radius: 50%;
            border: 3px solid rgba(255,255,255,0.2);
            box-shadow: 0 4px 8px rgba(0,0,0,0.4);
            flex-shrink: 0;
            z-index: 2;
        }
        
        .fighter-info {
            padding: 0 20px;
            z-index: 1;
            flex-grow: 1;
        }

        .fighter-name {
            font-size: 26px;
            font-weight: 800;
            line-height: 1.1;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        
        .placeholder-text {
            color: rgba(255,255,255,0.3);
            font-style: italic;
            font-weight: 300;
        }

        /* --- MIDDLE INFO --- */
        .match-info {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            width: 140px;
            height: 100%;
            background-color: #1a1a1a;
            color: #888;
            font-weight: 600;
            text-align: center;
            border-left: 1px solid #333;
            border-right: 1px solid #333;
            flex-shrink: 0;
            position: relative;
            z-index: 3;
        }

        .vs-badge {
            font-size: 24px;
            font-weight: 900;
            color: #fff;
            margin-bottom: 8px;
            font-style: italic;
        }

        .fight-order {
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #aaa;
            margin-bottom: 4px;
        }
        
        .division-badge {
            padding: 4px 10px;
            background-color: #333;
            border-radius: 12px;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #ddd;
        }

        /* --- MOBILE RESPONSIVENESS --- */
        @media screen and (max-width: 768px) {
            .event-header {
                font-size: 18px;
                padding: 15px;
                margin-bottom: 16px;
            }

            .match-card {
                flex-direction: column;
                height: auto;
                padding: 0;
            }

            .match-info {
                width: 100%;
                height: 40px; /* Slim bar */
                flex-direction: row;
                gap: 15px;
                border: none;
                border-top: 1px solid #333;
                border-bottom: 1px solid #333;
                order: 2; /* Info in middle */
                padding: 5px;
            }
            
            .vs-badge { font-size: 16px; margin: 0; }
            .fight-order { font-size: 11px; margin: 0; }
            .division-badge { font-size: 9px; padding: 2px 8px; }

            .corner {
                width: 100%;
                height: auto;
                padding: 15px;
            }
            
            .corner.blue {
                order: 1; /* Top */
                background: linear-gradient(180deg, #0d2d51 0%, #0a1f3a 100%);
            }
            
            .corner.red {
                order: 3; /* Bottom */
                flex-direction: row; /* Normal order on mobile too for consistency? No, let's keep img left for both or standard */
                justify-content: flex-start;
                text-align: left;
                background: linear-gradient(180deg, #3b1214 0%, #2a0d0e 100%);
            }
            
            /* On mobile, standard order: Img | Info */
            .corner.red {
                 flex-direction: row; 
            }

            .fighter-img {
                width: 70px;
                height: 70px;
                margin-right: 15px;
                margin-left: 0;
            }
            
            .fighter-info {
                padding: 0;
            }

            .fighter-name {
                font-size: 20px;
            }
        }
    </style>
    '''

    if df is None or df.empty:
        return css + "<div style='text-align:center; padding:50px; color:#666;'>No fights loaded.</div>"

    html_out = css
    
    # Iterate Events
    for event, group in df.groupby("Event", dropna=False):
        event_label = html.escape(str(event) if pd.notna(event) else "Event")
        group_sorted = group.sort_values(["FightOrder"], ascending=[True])

        html_out += f"<div class='event-container'><div class='event-header'>{event_label}</div>"

        # Iterate Fights
        for fight_order, fight_df in group_sorted.groupby("FightOrder", dropna=False):
            blue_row = _first_row_or_none(fight_df[fight_df["Corner"] == "blue"])
            red_row  = _first_row_or_none(fight_df[fight_df["Corner"] == "red"])

            # Extract Data
            b_name = html.escape(str(blue_row.get("Fighter", "TBA"))) if isinstance(blue_row, pd.Series) else "TBA"
            r_name = html.escape(str(red_row.get("Fighter", "TBA")))  if isinstance(red_row, pd.Series)  else "TBA"
            
            b_img_url = blue_row.get("Picture", "") if isinstance(blue_row, pd.Series) else ""
            r_img_url = red_row.get("Picture", "")  if isinstance(red_row, pd.Series)  else ""
            
            b_img = _img_tag(b_img_url, "fighter-img") if b_img_url else "<div class='fighter-img' style='background:#ccc;'></div>"
            r_img = _img_tag(r_img_url, "fighter-img") if r_img_url else "<div class='fighter-img' style='background:#ccc;'></div>"

            # Division logic
            div_src = blue_row if isinstance(blue_row, pd.Series) else red_row
            division = html.escape(str(div_src.get("Division", ""))) if isinstance(div_src, pd.Series) else ""

            # Fight Order safe int
            try:
                fo_int = int(fight_order) if pd.notna(fight_order) else 0
            except:
                fo_int = 0
            
            order_display = f"FIGHT {fo_int}" if fo_int > 0 else "PRELIM"

            html_out += f"""
            <div class='match-card'>
                <!-- BLUE CORNER -->
                <div class='corner blue'>
                    {b_img}
                    <div class='fighter-info'>
                        <div class='fighter-name'>{b_name}</div>
                    </div>
                </div>

                <!-- INFO CENTER -->
                <div class='match-info'>
                    <div class='fight-order'>{order_display}</div>
                    <div class='vs-badge'>VS</div>
                    {f"<div class='division-badge'>{division}</div>" if division else ""}
                </div>

                <!-- RED CORNER -->
                <div class='corner red'>
                    <div class='fighter-info'>
                        <div class='fighter-name'>{r_name}</div>
                    </div>
                    {r_img}
                </div>
            </div>
            """
        
        html_out += "</div>" # Close event-container

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
