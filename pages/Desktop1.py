import streamlit as st
import pandas as pd

# --- 1. Configuração da Página ---
# Otimiza para telas FHD usando o layout "wide"
st.set_page_config(
    page_title="Otimização de Tabela FHD",
    layout="wide"
)

# --- 2. Título da Aplicação ---
# O espaço vertical foi otimizado, sem elementos extras entre o título e a tabela.
st.title("Tabela de Lutas Otimizada")

# --- 3. Criação de Dados de Exemplo ---
# Simulando os dados que você teria em seu aplicativo.
data = {
    'FIGHTER': ['Alexandre "The Great" Pantoja', 'Israel "The Last Stylebender" Adesanya', 'Sean "Suga" O\'Malley', 'Islam Makhachev', 'Jon "Bones" Jones', 'Zhang "Magnum" Weili'],
    'EVENT': ['UFC 301', 'UFC 293', 'UFC 299', 'UFC 294', 'UFC 285', 'UFC 292'],
    'DIVISION': ['Flyweight', 'Middleweight', 'Bantamweight', 'Lightweight', 'Heavyweight', 'Strawweight'],
    'FIGHT': ['Main Event', 'Main Event', 'Co-Main Event', 'Main Event', 'Main Event', 'Co-Main Event'],
    'STATUS': ['Venceu', 'Perdeu', 'Venceu', 'Venceu', 'Venceu', 'Venceu'],
    'OPPONENT': ['Steve Erceg', 'Sean Strickland', 'Marlon Vera', 'Alexander Volkanovski', 'Ciryl Gane', 'Amanda Lemos']
}
df = pd.DataFrame(data)


# --- 4. Transformação dos Dados (Otimização de Colunas) ---

# Função para formatar a nova coluna consolidada usando HTML/Markdown para melhor visualização.
def formatar_detalhes_luta(row):
    return f"""
    **Evento:** {row['EVENT']}<br>
    **Divisão:** {row['DIVISION']}<br>
    **Luta:** {row['FIGHT']}
    """

# Cria a nova coluna 'fight_details' aplicando a função acima.
df['fight_details'] = df.apply(formatar_detalhes_luta, axis=1)

# Seleciona e reordena as colunas que serão exibidas. As colunas originais são omitidas.
df_display = df[['FIGHTER', 'fight_details', 'OPPONENT', 'STATUS']]


# --- 5. Exibição da Tabela Otimizada ---

st.write("Visualização da tabela com colunas otimizadas:")

# Usa st.dataframe com column_config para personalizar a exibição
st.dataframe(
    df_display,
    # Oculta o índice da tabela
    hide_index=True,
    # Usa todo o container (e a largura da página)
    use_container_width=True,
    # Configuração avançada das colunas
    column_config={
        # Configura a coluna FIGHTER
        "FIGHTER": st.column_config.TextColumn(
            "Lutador",  # Define um novo rótulo mais amigável
            width="large",  # Aumenta a largura desta coluna em relação às outras
            help="Nome do lutador principal."
        ),
        # Configura a nova coluna consolidada
        "fight_details": st.column_config.TextColumn(
            "Detalhes da Luta",
            help="Informações consolidadas sobre o evento e a luta."
        ),
        # Configura as colunas restantes com rótulos amigáveis
        "OPPONENT": st.column_config.TextColumn(
            "Oponente"
        ),
        "STATUS": st.column_config.TextColumn(
            "Resultado"
        )
    }
)
