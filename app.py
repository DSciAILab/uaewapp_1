import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_autorefresh import st_autorefresh
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# 🔐 Conecta ao Google Sheets usando as credenciais do secrets
@st.cache_resource
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open("UAEW_App").worksheet("Sheet1")
    return sheet

# 🔄 Carrega os dados da planilha como DataFrame
@st.cache_data(ttl=300)
def load_data():
    sheet = connect_sheet()
    data = sheet.get_all_records()
    return pd.DataFrame(data), sheet

# 📂 Atualiza célula específica
def salvar_valor(sheet, row, col_index, valor):
    sheet.update_cell(row + 2, col_index + 1, valor)

# 📱 Melhoria visual para mobile
st.set_page_config(page_title="Controle de Atletas MMA", layout="wide")

# 🌙 Estilo escuro customizado
st.markdown("""
    <style>
    body { background-color: #0e1117; color: white; }
    .stApp { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

# 🔀 Navegação entre páginas
pagina = st.sidebar.selectbox("Selecione a visualização", ["Cards", "Datagrid"])

# 📦 Carregamento dos dados
df, sheet = load_data()

# 🎯 Página: Datagrid
if pagina == "Datagrid":
    st.title("📋 Visualização em Datagrid - UAE Warriors")

    # 🔽 Lista de países (resumida, pode expandir conforme necessário)
    paises = ["United Arab Emirates", "Brazil", "USA", "Russia", "France", "Japan", "Egypt", "India"]

    gb = GridOptionsBuilder.from_dataframe(df)

    campos_editaveis = ["Nationality", "Residence", "Hight", "Range", "Weight", "Coach", "Music 1", "Music 2", "Music 3"]
    for campo in campos_editaveis:
        if "Music" in campo:
            gb.configure_column(
                campo,
                editable=True,
                cellEditor="agTextCellEditor",
                tooltipField=campo,
                headerTooltip="Paste your YouTube link here"
            )
        elif campo == "Nationality":
            gb.configure_column(
                campo,
                editable=True,
                cellEditor="agSelectCellEditor",
                cellEditorParams={"values": paises},
                tooltipField=campo,
                headerTooltip="Select nationality"
            )
        else:
            gb.configure_column(
                campo,
                editable=True,
                tooltipField=campo,
                headerTooltip="Click to edit"
            )

    # ⚙️ Outras configurações visuais
    gb.configure_pagination(enabled=True)
    gb.configure_side_bar()
    gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=False)

    gridOptions = gb.build()

    # 🧩 Renderização
    response = AgGrid(
        df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.MANUAL,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        height=600,
        fit_columns_on_grid_load=True,
        theme="alpine"  # Visual limpo
    )

    edited_df = pd.DataFrame(response["data"])

    if st.button("💾 Salvar alterações no Google Sheets"):
        for i, row in edited_df.iterrows():
            for campo in campos_editaveis:
                try:
                    valor = row[campo]
                    col_index = df.columns.get_loc(campo)
                    salvar_valor(sheet, i, col_index, valor)
                except Exception as e:
                    st.error(f"Erro ao salvar linha {i}, coluna {campo}: {e}")
        st.success("Alterações salvas com sucesso!")
