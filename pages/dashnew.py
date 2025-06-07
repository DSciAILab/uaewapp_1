# pages/DashboardNovo.py

# Trecho principal alterado do script: adicionar zoom via slider e aplicar ao CSS

import streamlit as st

# Sidebar com slider de zoom
font_scale = st.sidebar.slider("🔍 Zoom da Interface", 0.8, 2.0, 1.0, 0.05)

# CSS para estilização da tabela e imagens com escala
custom_css = f"""
<style>
.dashboard-container {{ font-family: 'Segoe UI', sans-serif; transform: scale({font_scale}); transform-origin: top left; }}
.dashboard-table {{ width: 100%; border-collapse: separate; border-spacing: 0; background-color: #2a2a2e; color: #e1e1e1; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); border-radius: 12px; overflow: hidden; }}
.dashboard-table th, .dashboard-table td {{ border-right: 1px solid #4a4a50; border-bottom: 1px solid #4a4a50; padding: {12 * font_scale}px {8 * font_scale}px; text-align: center; vertical-align: middle; min-width: 40px; }}
.dashboard-table th {{ background-color: #1c1c1f; font-size: {0.8 * font_scale}rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; white-space: normal; word-break: break-word; }}
.blue-corner-header {{ background-color: #0d2e4e !important; border-color: #1a4a75 !important; }}
.red-corner-header {{ background-color: #5a1d1d !important; border-color: #8b3d3d !important; }}
.center-col-header {{ background-color: #111 !important; }}
.dashboard-table td {{ font-size: {0.95 * font_scale}rem; }}
.dashboard-table tr:hover td {{ background-color: #38383c; }}
.fighter-img {{ width: {55 * font_scale}px; height: {55 * font_scale}px; border-radius: 50%; object-fit: cover; border: 2px solid #666; }}
.fighter-name {{ font-weight: 600; min-width: {180 * font_scale}px; }}
.fighter-name-blue {{ text-align: right !important; padding-right: 15px !important; }}
.fighter-name-red {{ text-align: left !important; padding-left: 15px !important; }}
.fight-number-cell {{ font-weight: bold; font-size: {1.2 * font_scale}em; background-color: #333; }}
.event-cell {{ font-style: italic; background-color: #333; font-size: {0.85 * font_scale}em; color: #ccc; }}
.division-cell {{ font-style: italic; background-color: #333; }}
.status-cell {{ cursor: help; }}
.status-done {{ background-color: #28a745; }}
.status-requested {{ background-color: #ffc107; }}
.status-pending {{ background-color: #dc3545; }}
.status-neutral {{ background-color: transparent; }}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# CSS adicional para zoom nos componentes do Streamlit
st.markdown(f"""
<style>
.main > div {{ transform: scale({font_scale}); transform-origin: top left; }}
h1, h2, h3, h4, h5, h6, .stMarkdown p, .stMarkdown span {{ font-size: {1.0 * font_scale}rem !important; }}
.stMetricValue, .stMetricLabel {{ font-size: {1.0 * font_scale}rem !important; }}
.stButton > button {{ font-size: {0.9 * font_scale}rem !important; }}
.stSelectbox label, .stSlider label {{ font-size: {0.9 * font_scale}rem !important; }}
.stMarkdown, .stSubheader {{ font-size: {1.0 * font_scale}rem !important; }}
</style>
""", unsafe_allow_html=True)

# A partir daqui, o restante do dashboard permanece como está (load data, render html, etc.)
