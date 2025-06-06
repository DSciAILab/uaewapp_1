# pages/DashboardNovo.py
# ... (importações e constantes de abas/colunas como antes) ...

# --- Constantes de STATUS e EMOJI ATUALIZADAS ---
STATUS_TO_EMOJI = {
    "Done": "🟩",       
    "Requested": "🟧", 
    "---": "➖",        
    "Não Solicitado": "➖",
    "Pendente": "🟥",      # MODIFICADO para Pendente/Vazio
    "Não Registrado": "🟥" # MODIFICADO para Pendente/Vazio
}
DEFAULT_EMOJI = "🟥" # Emoji padrão se o status não for reconhecido agora é o vermelho

# NUM_TO_STATUS_VERBOSE não é mais usado para a legenda se os emojis são autoexplicativos,
# mas pode ser útil para o help text das colunas.
NUM_TO_STATUS_VERBOSE = { 
    # Se você ainda usa os números internamente e quer uma legenda para eles:
    0: f"Pendente ({STATUS_TO_EMOJI.get('Pendente', DEFAULT_EMOJI)})", 
    1: f"Não Solicitado ({STATUS_TO_EMOJI.get('---', DEFAULT_EMOJI)})", 
    2: f"Solicitado ({STATUS_TO_EMOJI.get('Requested', DEFAULT_EMOJI)})", 
    3: f"Concluído ({STATUS_TO_EMOJI.get('Done', DEFAULT_EMOJI)})"
}

# ... (Funções de conexão e carregamento de dados como antes) ...
# A função get_numeric_task_status continuará retornando números (0,1,2,3)
# A conversão para emoji será feita antes de popular o df_dashboard

# --- Início da Página Streamlit ---
# ... (título, auto-refresh, selectbox de tamanho da fonte e injeção de CSS como antes) ...

# --- Preparar Dados para a Tabela do Dashboard (MODIFICADO ONDE OS EMOJIS SÃO INSERIDOS) ---
# ... (carregamento de df_fightcard, df_attendance, all_tasks, df_athletes_info) ...
# ... (lógica do seletor de evento) ...
# ... (lógica do fighter_to_id_map) ...

    dashboard_data_list = []
    for order, group in df_fightcard_display.sort_values(by=[FC_EVENT_COL, FC_ORDER_COL]).groupby([FC_EVENT_COL, FC_ORDER_COL]):
        event, fight_order = order
        blue_s = group[group[FC_CORNER_COL] == "blue"].squeeze(axis=0); red_s = group[group[FC_CORNER_COL] == "red"].squeeze(axis=0)
        row_data = {"Evento": event, "Luta #": int(fight_order) if pd.notna(fight_order) else ""}

        for corner_prefix, series_data in [("Azul", blue_s), ("Vermelho", red_s)]:
            fighter_name_fc = str(series_data.get(FC_FIGHTER_COL, "N/A")).strip() if isinstance(series_data, pd.Series) else "N/A"
            athlete_id_from_map = fighter_to_id_map.get(fighter_name_fc, None) 
            pic_url = series_data.get(FC_PICTURE_COL, "") if isinstance(series_data, pd.Series) else ""
            
            row_data[f"Foto {corner_prefix}"] = pic_url if isinstance(pic_url, str) and pic_url.startswith("http") else None
            
            fighter_id_display = athlete_id_from_map if athlete_id_from_map else "N/D"
            # --- Coluna Combinada: ID - Nome ---
            row_data[f"Lutador {corner_prefix}"] = f"{fighter_id_display} - {fighter_name_fc}" if fighter_name_fc != "N/A" else "N/A"
            # Removida a coluna separada de ID para o df_dashboard, já que está combinada
            
            identifier_for_status = athlete_id_from_map 
            if pd.notna(fighter_name_fc) and fighter_name_fc != "N/A":
                for task in all_tasks:
                    status_text_representation = DEFAULT_EMOJI # Default se ID não encontrado
                    if identifier_for_status: 
                        # get_numeric_task_status ainda retorna o número (0,1,2,3)
                        numeric_status = get_numeric_task_status(identifier_for_status, task, df_attendance)
                        # Agora mapeamos o número para o emoji desejado
                        if numeric_status == 3: status_text_representation = STATUS_TO_EMOJI["Done"]
                        elif numeric_status == 2: status_text_representation = STATUS_TO_EMOJI["Requested"]
                        elif numeric_status == 1: status_text_representation = STATUS_TO_EMOJI["---"]
                        else: status_text_representation = STATUS_TO_EMOJI["Pendente"] # status 0 ou não mapeado
                    row_data[f"{task} ({corner_prefix})"] = status_text_representation
            else:
                for task in all_tasks: row_data[f"{task} ({corner_prefix})"] = STATUS_TO_EMOJI["Pendente"] 
        row_data["Divisão"] = blue_s.get(FC_DIVISION_COL, red_s.get(FC_DIVISION_COL, "N/A")) if isinstance(blue_s, pd.Series) else (red_s.get(FC_DIVISION_COL, "N/A") if isinstance(red_s, pd.Series) else "N/A")
        dashboard_data_list.append(row_data)

    if not dashboard_data_list: st.info(f"Nenhuma luta processada para '{selected_event_option}'."); st.stop()
    df_dashboard = pd.DataFrame(dashboard_data_list)

    # --- Configuração das Colunas para st.data_editor ---
    column_config_editor = {
        "Evento": st.column_config.TextColumn(width="small", disabled=True),
        "Luta #": st.column_config.NumberColumn(width="small", format="%d", disabled=True),
        "Foto Azul": st.column_config.ImageColumn("Foto (A)", width="small"),
        "Lutador Azul": st.column_config.TextColumn("Lutador (A) [ID - Nome]", width="large", disabled=True), # Label atualizado
        "Divisão": st.column_config.TextColumn(width="medium", disabled=True),
        "Lutador Vermelho": st.column_config.TextColumn("Lutador (V) [ID - Nome]", width="large", disabled=True), # Label atualizado
        "Foto Vermelho": st.column_config.ImageColumn("Foto (V)", width="small"),
    }
    # Ordem das colunas na tabela - REMOVIDAS colunas de ID separadas
    column_order_list = ["Evento", "Luta #", "Foto Azul", "Lutador Azul"]
    for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Azul)")
    column_order_list.append("Divisão")
    for task_name_col in all_tasks: column_order_list.append(f"{task_name_col} (Vermelho)")
    column_order_list.extend(["Lutador Vermelho", "Foto Vermelho"])
    
    # Legenda com emojis
    legend_parts_disp = [f"{emoji}: {desc.split(' (')[0]}" for desc, emoji_list_val in STATUS_TO_EMOJI.items() for emoji in ([emoji_list_val] if not isinstance(emoji_list_val, list) else emoji_list_val) if emoji.strip() != ""] # Só mostra emojis válidos
    # Remove duplicados da legenda (caso haja)
    seen_emojis = set()
    unique_legend_parts = []
    for part in legend_parts_disp:
        emoji_char = part.split(':')[0].strip()
        if emoji_char not in seen_emojis:
            unique_legend_parts.append(part)
            seen_emojis.add(emoji_char)
    help_text_general_legend_disp = ", ".join(unique_legend_parts)


    for task_name_col in all_tasks:
        # Colunas de tarefa agora são TextColumn para exibir emojis
        column_config_editor[f"{task_name_col} (Azul)"] = st.column_config.TextColumn(
            label=task_name_col, width="small", help=f"Status: {help_text_general_legend_disp}", disabled=True
        )
        column_config_editor[f"{task_name_col} (Vermelho)"] = st.column_config.TextColumn(
            label=task_name_col, width="small", help=f"Status: {help_text_general_legend_disp}", disabled=True
        )

    # --- Exibição da Tabela Principal ---
    st.subheader(f"Detalhes das Lutas e Tarefas: {selected_event_option}")
    st.markdown(f"**Legenda Status Tarefas:** {help_text_general_legend_disp}")
    
    table_height = (len(df_dashboard) + 1) * 45 + 10; table_height = max(400, min(table_height, 1200)) 
    st.data_editor(
        df_dashboard,
        column_config=column_config_editor,
        column_order=column_order_list,
        hide_index=True,
        use_container_width=True, 
        num_rows="fixed",
        disabled=True, 
        height=table_height
    )
    st.markdown("---")

    # --- Estatísticas do Evento Selecionado ---
    st.subheader(f"Estatísticas do Evento: {selected_event_option}")
    if not df_dashboard.empty:
        total_lutas_evento = df_dashboard["Luta #"].nunique()
        # Ajusta contagem de atletas únicos para a nova coluna combinada
        unique_fighters_event = set()
        for _, row in df_dashboard.iterrows():
            if row["Lutador Azul"] != "N/A": unique_fighters_event.add(row["Lutador Azul"])
            if row["Lutador Vermelho"] != "N/A": unique_fighters_event.add(row["Lutador Vermelho"])
        total_atletas_unicos_ev = len(unique_fighters_event)

        # Contagem de tarefas por emoji para as estatísticas
        done_emoji = STATUS_TO_EMOJI["Done"]
        req_emoji = STATUS_TO_EMOJI["Requested"]
        not_sol_emoji = STATUS_TO_EMOJI["---"] # Ou "Não Solicitado"
        pend_emoji = STATUS_TO_EMOJI["Pendente"]

        done_count = 0; req_count = 0; not_sol_count = 0; total_task_slots = 0

        for task in all_tasks:
            for corner in ["Azul", "Vermelho"]:
                col_name = f"{task} ({corner})"
                if col_name in df_dashboard.columns:
                    valid_fighter_mask = df_dashboard[f"Lutador {corner}"] != "N/A"
                    task_emojis_series = df_dashboard.loc[valid_fighter_mask, col_name]
                    
                    total_task_slots += len(task_emojis_series) # Cada célula é um slot
                    done_count += (task_emojis_series == done_emoji).sum()
                    req_count += (task_emojis_series == req_emoji).sum()
                    not_sol_count += (task_emojis_series == not_sol_emoji).sum()
        
        stat_cols = st.columns(5)
        stat_cols[0].metric("Lutas", total_lutas_evento)
        stat_cols[1].metric("Atletas Únicos", total_atletas_unicos_ev)
        stat_cols[2].metric(f"Tarefas {done_emoji} (Done)", done_count, help=f"De {total_task_slots} slots de tarefa considerados.")
        stat_cols[3].metric(f"Tarefas {req_emoji} (Requested)", req_count)
        stat_cols[4].metric(f"Tarefas {not_sol_emoji} (---)", not_sol_count)
    else: 
        st.info("Nenhum dado para estatísticas do evento.")
    st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
