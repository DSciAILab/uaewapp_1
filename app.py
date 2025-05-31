# 🧩 Função modular para renderizar cada atleta com campos visuais, edição e detalhes
def renderizar_atleta(i, row, df):
    # 🔴 Definir cor de fundo e nome com base no corner
    corner = row.get("Corner", "").lower()
    cor_class = "corner-vermelho" if corner == "red" else "corner-azul"
    nome_class = "name-vermelho" if corner == "red" else "name-azul"

    # ⚠️ Verificar pendências
    tem_pendencia = any(str(row.get(status, "")).lower() == "required" for status in status_cols)
    icone_alerta = "⚠️ " if tem_pendencia else ""

    # 🧑 Nome e imagem do atleta
    nome_html = f"<div class='{nome_class}'>{icone_alerta}{row.get('Name', '')}</div>"
    img_html = f"<div class='circle-img'><img src='{row.get('Image', '')}'></div>" if row.get("Image") else ""

    # 🎯 Cabeçalho do atleta
    st.markdown(f"""
        <div class='header-container'>
            {img_html}{nome_html}
        </div>""", unsafe_allow_html=True)

    # 🧠 Estado de edição
    edit_key = f"edit_mode_{i}"
    if edit_key not in st.session_state:
        st.session_state[edit_key] = False

    # 🔍 Expander de detalhes
    with st.expander("Exibir detalhes", expanded=st.session_state[edit_key]):
        st.markdown(f"<div class='{cor_class}'>", unsafe_allow_html=True)

        # 🔖 Badges de status
        badges_html = "".join(gerar_badge(row.get(status, ""), status) for status in status_cols)
        st.markdown(f"<div class='status-line'>{badges_html}</div>", unsafe_allow_html=True)

        # 🥋 Fight Details – NOVA TABELA EM 2 LINHAS
        st.markdown("### 🥋 Fight Details")

        # Linha 1: Fight_Order, Corner, Event, Division
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("**Fight Order**")
            st.text(row.get("Fight_Order", "N/A"))
        with c2:
            st.markdown("**Corner**")
            st.text(row.get("Corner", "N/A"))
        with c3:
            st.markdown("**Event**")
            st.text(row.get("Event", "N/A"))
        with c4:
            st.markdown("**Division**")
            st.text(row.get("Division", "N/A"))

        # Linha 2: Opponent, Coach
        c5, c6 = st.columns(2)
        with c5:
            st.markdown("**Opponent**")
            st.text(row.get("Opponent", "N/A"))
        with c6:
            st.markdown("**Coach**")
            st.text(row.get("Coach", "N/A"))

        # 🌐 Botão de WhatsApp
        whatsapp = str(row.get("Whatsapp", "")).strip()
        if whatsapp:
            link = f"https://wa.me/{whatsapp.replace('+', '').replace(' ', '')}"
            st.markdown(f"<div class='wa-button'><a href='{link}' target='_blank'>📡 WhatsApp</a></div>", unsafe_allow_html=True)

        # ✏️ Botão de Edição / Salvar
        if st.button("Salvar" if st.session_state[edit_key] else "Editar", key=f"toggle_{i}"):
            if st.session_state[edit_key]:
                with st.spinner('Salvando alterações...'):
                    for campo in campos_editaveis:
                        novo_valor = st.session_state.get(f"{campo}_{i}", "")
                        if campo in df.columns:
                            col_index = df.columns.get_loc(campo)
                            salvar_valor(i, col_index, novo_valor)
                        else:
                            st.warning(f"Campo '{campo}' não encontrado.")
                st.success('Alterações salvas com sucesso!')
            st.session_state[edit_key] = not st.session_state[edit_key]
            st.rerun()

        # 📝 Campos editáveis em 2 colunas
        cols = st.columns(2)
        for idx, campo in enumerate(campos_editaveis):
            target_col = cols[idx % 2]
            target_col.text_input(
                campo,
                value=row.get(campo, ""),
                key=f"{campo}_{i}",
                disabled=not st.session_state[edit_key]
            )

        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<hr class='divisor'>", unsafe_allow_html=True)
