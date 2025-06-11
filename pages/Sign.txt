import streamlit as st
from streamlit_drawable_canvas import st_canvas

# Configuração do canvas
st.title("Escrita Manual / Canvas Interativo")

canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 0)",  # Cor do preenchimento
    stroke_width=3,                       # Espessura do traço
    stroke_color="#000000",              # Cor do traço
    background_color="#ffffff",          # Cor de fundo
    height=300,
    width=500,
    drawing_mode="freedraw",             # Modo livre de escrita
    key="canvas"
)

# Verifica se há desenho
if canvas_result.image_data is not None:
    st.image(canvas_result.image_data)
