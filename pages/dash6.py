import streamlit as st
import pandas as pd
import math

# --- 1. Configuração da Página ---
st.set_page_config(
    page_title="Snowflake Table Catalog",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. Dados Fictícios (Baseados na Imagem) ---
def get_catalog_data():
    """Retorna uma lista de dicionários com dados fictícios para o catálogo."""
    data = [
        {"name": "TRIPS_FULL", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 49840000, "size_bytes": 2.42 * 1024**3, "columns": 18, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "TRIPS", "schema": "CITIBIKE.DEMO", "rows": 40720000, "size_bytes": 1.24 * 1024**3, "columns": 3, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2023-01-23"},
        {"name": "TRIPS", "schema": "CITIBIKE_DEV.DEMO", "rows": 6210000, "size_bytes": 191.69 * 1024**2, "columns": 3, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2023-01-23"},
        {"name": "RIDERS", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 100000, "size_bytes": 5.82 * 1024**2, "columns": 11, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "SPATIAL_DATA", "schema": "CITIBIKE.UTILS", "rows": 2110, "size_bytes": 664 * 1024, "columns": 2, "type": "BASE TABLE", "owner": "DEV_CITIBIKE", "created_on": "2022-11-29"},
        {"name": "SPATIAL_DATA", "schema": "CITIBIKE_DEV.UTILS", "rows": 2110, "size_bytes": 664 * 1024, "columns": 2, "type": "BASE TABLE", "owner": "DEV_CITIBIKE", "created_on": "2023-01-23"},
        {"name": "WEIGHT_WK", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 519, "size_bytes": 11.5 * 1024, "columns": 3, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "WEIGHT_ROUTE", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 200, "size_bytes": 6 * 1024, "columns": 5, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "WEIGHT_HOD", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 168, "size_bytes": 3.5 * 1024, "columns": 4, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "WEIGHT_BIRTHYEAR", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 65, "size_bytes": 2.5 * 1024, "columns": 3, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "WEIGHT_DOW", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 7, "size_bytes": 1.5 * 1024, "columns": 3, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "WEIGHT_GENDER", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 3, "size_bytes": 1.5 * 1024, "columns": 3, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "WEIGHT_PAYMENT", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 7, "size_bytes": 1.5 * 1024, "columns": 3, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "WEIGHT_MEMBERSHIP", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 7, "size_bytes": 1.5 * 1024, "columns": 3, "type": "BASE TABLE", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "TABLEAU_QUERY_HISTORY", "schema": "CITIBIKE.UTILS", "rows": 0, "size_bytes": 0, "columns": 42, "type": "VIEW", "owner": "DBA_CITIBIKE", "created_on": "2022-11-29"},
        {"name": "TRIPS_VW", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 0, "size_bytes": 0, "columns": 16, "type": "VIEW", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "TABLEAU_QUERY_HISTORY", "schema": "CITIBIKE_DEV.UTILS", "rows": 0, "size_bytes": 0, "columns": 42, "type": "VIEW", "owner": "DBA_CITIBIKE", "created_on": "2023-01-23"},
        {"name": "TRIPS", "schema": "CITIBIKE_V4_RESET.RESET", "rows": 0, "size_bytes": 0, "columns": 18, "type": "VIEW", "owner": "DBA_CITIBIKE", "created_on": "2022-01-21"},
        {"name": "TRIPS_VW", "schema": "CITIBIKE.DEMO", "rows": 0, "size_bytes": 0, "columns": 16, "type": "VIEW", "owner": "DBA_CITIBIKE", "created_on": "2023-01-24"},
    ]
    return data

# --- 3. Funções Auxiliares de Formatação ---
def format_number(num):
    """Formata números grandes em uma string compacta (K, M, B)."""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.2f}B"
    if num >= 1_000_000:
        return f"{num / 1_000_000:.2f}M"
    if num >= 1_000:
        return f"{num / 1_000:.2f}K"
    return str(num)

def format_bytes(size_bytes):
    """Formata bytes em uma string legível (KB, MB, GB)."""
    if size_bytes == 0:
        return "0.0 Bytes"
    size_name = ("Bytes", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"

# --- 4. Estilização CSS ---
st.markdown("""
<style>
    /* Estilo geral */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    /* Título principal */
    h1 {
        font-weight: 600;
        letter-spacing: -1px;
    }
    /* Seção de resumo superior (KPIs) */
    .summary-container {
        display: flex;
        justify-content: space-around;
        padding: 1.5rem 0;
        border-bottom: 1px solid #262730;
        margin-bottom: 2rem;
    }
    .summary-item {
        text-align: center;
    }
    .summary-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #E1E2E6;
        line-height: 1.2;
    }
    .summary-label {
        font-size: 0.9rem;
        color: #A0A3B1;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    /* Grade de cartões */
    .catalog-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 1.5rem;
    }
    /* Estilo individual do cartão */
    .catalog-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 8px;
        padding: 1.5rem;
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
    }
    .catalog-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
    }
    /* Cabeçalho do cartão */
    .card-header .name {
        font-size: 1.25rem;
        font-weight: 600;
        color: #C9D1D9;
        margin: 0;
    }
    .card-header .schema {
        font-size: 0.8rem;
        color: #8B949E;
        margin: 0 0 1.5rem 0;
    }
    /* Corpo do cartão (métricas) */
    .card-body {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .card-metric .value {
        font-size: 1.75rem;
        font-weight: 600;
        color: #F0F6FC;
        line-height: 1;
    }
    .card-metric .unit, .card-metric .label {
        font-size: 0.75rem;
        color: #8B949E;
        text-transform: uppercase;
    }
    /* Rodapé do cartão */
    .card-footer {
        font-size: 0.85rem;
        color: #8B949E;
    }
    .card-footer div {
        margin-bottom: 0.25rem;
    }
    .card-footer span {
        margin-left: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 5. Lógica Principal do App ---

# Carrega os dados
df = pd.DataFrame(get_catalog_data())

# Título do Dashboard
st.title("Snowflake Table Catalog")

# --- Seção de Resumo Superior ---
total_tables = df[df['type'] == 'BASE TABLE'].shape[0]
total_views = df[df['type'] == 'VIEW'].shape[0]
# Assumindo que não há visualizações materializadas nos dados fictícios
total_materialized_views = 0 
total_rows = df['rows'].sum()
total_size_bytes = df['size_bytes'].sum()

summary_html = f"""
<div class="summary-container">
    <div class="summary-item">
        <div class="summary-value">{total_tables}</div>
        <div class="summary-label">Tables</div>
    </div>
    <div class="summary-item">
        <div class="summary-value">{total_views}</div>
        <div class="summary-label">Views</div>
    </div>
    <div class="summary-item">
        <div class="summary-value">{total_materialized_views}</div>
        <div class="summary-label">Materialized Views</div>
    </div>
    <div class="summary-item">
        <div class="summary-value">{format_number(total_rows)}</div>
        <div class="summary-label">Rows</div>
    </div>
    <div class="summary-item">
        <div class="summary-value">{format_bytes(total_size_bytes)}</div>
        <div class="summary-label">Data Size</div>
    </div>
</div>
"""
st.markdown(summary_html, unsafe_allow_html=True)


# --- Grade de Cartões ---
cards_html = ""
for _, row in df.iterrows():
    # Formata os valores para exibição
    rows_formatted = format_number(row['rows'])
    size_formatted = format_bytes(row['size_bytes']).split() # Divide número e unidade (ex: ['2.42', 'GB'])
    
    card = f"""
    <div class="catalog-card">
        <div class="card-header">
            <p class="name">{row['name']}</p>
            <p class="schema">{row['schema']}</p>
        </div>
        <div class="card-body">
            <div class="card-metric">
                <div class="value">{rows_formatted}</div>
                <div class="label">Rows</div>
            </div>
            <div class="card-metric">
                <div class="value">{size_formatted[0]}</div>
                <div class="unit">{size_formatted[1]}</div>
            </div>
            <div class="card-metric">
                <div class="value">{row['columns']}</div>
                <div class="label">Columns</div>
            </div>
        </div>
        <div class="card-footer">
            <div>🗄️<span>Table Type: {row['type']}</span></div>
            <div>👤<span>Owner: {row['owner']}</span></div>
            <div>🗓️<span>Created On: {row['created_on']}</span></div>
        </div>
    </div>
    """
    cards_html += card

st.markdown(f"<div class='catalog-grid'>{cards_html}</div>", unsafe_allow_html=True)
