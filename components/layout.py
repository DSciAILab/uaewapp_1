# components/layout.py
from pathlib import Path
import streamlit as st

# Autenticação / header do usuário (seu módulo)
from auth import check_authentication, display_user_sidebar


# ==========
# ARRANJO DO SIDEBAR (seções e páginas)
# Usei tuplas de "candidatos de caminho" para tolerar nomes com espaço/underscore
# Ex.: ("pages/5_Blood_Test.py", "pages/5_Blood Test.py")
# ==========

SECTIONS = [
    (
        "Core",
        [
            (("app.py",),                    "🏠 Home"),
            (("pages/1_Login.py",),          "🔐 Login"),
            (("pages/3_Dashboard.py",),      "📊 Dashboard"),
        ],
        True,  # expanded
    ),
    (
        "Control Panel",
        [
            (("pages/2_Fightcard.py",),      "🥊 Fightcard"),
            (("pages/3_Dashboard.py",),      "📊 Dashboard"),
            (("pages/4_Arrival_List.py", "pages/_4_Arrival_List.py"), "🛬 Arrival List"),
        ],
        True,
    ),
    (
        "Event Ops",
        [
            (("pages/5_Blood_Test.py", "pages/5_Blood Test.py"),  "🩸 Blood Test"),
            (("pages/6_Stats.py",),                               "📈 Fighter Stats"),
            (("pages/7_Music.py", "pages/_7_Music.py", "pages/7_Music.py"), "🎵 Music"),
            (("pages/8_Photoshoot.py",),                          "📷 Photoshoot"),
            (("pages/9_Video.py",),                               "🎬 Video"),
            (("pages/10_Event_Check.py",),                        "🧭 Event Check"),
        ],
        True,
    ),
    (
        "Compliance & Medical",
        [
            (("pages/12_Medical_Team.py", "pages/12_Medical Team.py"), "🧑‍⚕️ Medical Team"),
        ],
        False,
    ),
]


# ==========
# Utilidades de layout
# ==========

def _hide_native_sidebar_nav():
    """Esconde o menu nativo de páginas do Streamlit (lista automática do diretório pages/)."""
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _page_link_if_exists(candidates: tuple[str, ...], label: str) -> bool:
    """
    Cria um st.page_link para o primeiro caminho que existir entre os candidatos.
    Retorna True se criou o link; False caso nenhum exista.
    """
    for rel in candidates:
        if Path(rel).exists():
            st.page_link(rel, label=label)
            return True
    return False


def render_sidebar():
    """
    Desenha o sidebar segmentado conforme SECTIONS,
    mantendo o header de usuário e ocultando o nav nativo.
    """
    _hide_native_sidebar_nav()

    with st.sidebar:
        # Header do usuário / logout (seu componente atual)
        display_user_sidebar()

        st.markdown("## app")

        for section_title, links, expanded in SECTIONS:
            with st.expander(section_title, expanded=expanded):
                for candidates, label in links:
                    _page_link_if_exists(candidates, label)

        st.divider()
        st.caption("Use os grupos para navegar 👆")

    # >>> FLAG IMPORTANTE <<<
    # Indica para o restante do app que o sidebar unificado já foi renderizado.
    # Use em outros módulos para evitar redesenhar o header (e duplicar keys).
    st.session_state["_unified_sidebar_rendered"] = True


def bootstrap_page(page_title: str, layout: str = "wide"):
    """
    Chame isto como PRIMEIRA linha em cada página (incluindo app.py).
    - Configura a página (set_page_config)
    - Valida autenticação (check_authentication)
    - Renderiza o sidebar segmentado (render_sidebar)
    """
    # Precisa ser a 1ª chamada de Streamlit na página:
    st.set_page_config(
        page_title=page_title,
        layout=layout,
        initial_sidebar_state="expanded",
    )

    # Autenticação
    check_authentication()

    # Sidebar unificado
    render_sidebar()    
