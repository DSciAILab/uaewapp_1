def render_dashboard_html_content(df_fc, df_att, tasks_all, id_ca, name_ca):
    html_str = "" # O CSS é injetado pela função local_css()

    grouped_events = df_fc.groupby("Event", sort=False)

    for ev_name, ev_group in grouped_events:
        # Linha de Cabeçalho do Evento fora da tabela de lutas
        html_str += f"<table class='dashboard-table event-table'><tr><td class='event-header-row' colspan='7'>{html.escape(str(ev_name))}</td></tr></table>"
        
        html_str += "<table class='dashboard-table'>"
        html_str += """
        <thead>
            <tr>
                <th>Foto</th>
                <th>Lutador Azul <br/> Info Geral</th>
                <th>Tarefas (Azul)</th>
                <th>Detalhes da Luta</th>
                <th>Tarefas (Vermelho)</th>
                <th>Lutador Vermelho <br/> Info Geral</th>
                <th>Foto</th>
            </tr>
        </thead>
        <tbody>
        """
        fights = ev_group.sort_values(by="FightOrder").groupby("FightOrder")

        for f_order, f_df in fights:
            blue = f_df[f_df["Corner"] == "blue"].squeeze(axis=0) # axis=0 se for DataFrame de uma linha
            red = f_df[f_df["Corner"] == "red"].squeeze(axis=0)

            b_name = html.escape(str(blue.get("Fighter", ""))) if isinstance(blue, pd.Series) else ""
            r_name = html.escape(str(red.get("Fighter", ""))) if isinstance(red, pd.Series) else ""
            
            # Info Geral - Placeholder - você definirá o que vai aqui
            b_info_geral = html.escape(str(blue.get("Nationality", ""))) if isinstance(blue,pd.Series) else "" # Exemplo
            r_info_geral = html.escape(str(red.get("Nationality", ""))) if isinstance(red,pd.Series) else ""   # Exemplo

            b_img = f"<img src='{html.escape(str(blue.get('Picture','')),True)}' class='fighter-img'>" if isinstance(blue,pd.Series)and blue.get("Picture")and isinstance(blue.get("Picture"),str)and blue.get("Picture").startswith("http")else"<div class='fighter-img' style='background-color:#222; display:inline-block;'></div>"
            r_img = f"<img src='{html.escape(str(red.get('Picture','')),True)}' class='fighter-img'>" if isinstance(red,pd.Series)and red.get("Picture")and isinstance(red.get("Picture"),str)and red.get("Picture").startswith("http")else"<div class='fighter-img' style='background-color:#222; display:inline-block;'></div>"
            
            b_tasks_h = "<div class='task-grid'>"
            if b_name:
                for task_i in tasks_all:
                    stat_v = get_task_status_for_athlete(b_name, task_i, df_att, id_ca, name_ca, is_id=False)
                    stat_cls = "status-pending" # Default
                    if stat_v == "Done": stat_cls = "status-done"
                    elif stat_v == "Requested": stat_cls = "status-requested"
                    elif stat_v in ["---", "Não Solicitado"]: stat_cls = "status-not-requested" # Verde Claro
                    b_tasks_h += f"<div class='task-item'><span class='task-status-indicator {stat_cls}'></span><span class='task-name'>{html.escape(task_i)}</span></div>"
            b_tasks_h += "</div>"
            
            r_tasks_h = "<div class='task-grid'>"
            if r_name:
                for task_i in tasks_all:
                    stat_v = get_task_status_for_athlete(r_name, task_i, df_att, id_ca, name_ca, is_id=False)
                    stat_cls = "status-pending" # Default
                    if stat_v == "Done": stat_cls = "status-done"
                    elif stat_v == "Requested": stat_cls = "status-requested"
                    elif stat_v in ["---", "Não Solicitado"]: stat_cls = "status-not-requested" # Verde Claro
                    r_tasks_h += f"<div class='task-item'><span class='task-status-indicator {stat_cls}'></span><span class='task-name'>{html.escape(task_i)}</span></div>"
            r_tasks_h += "</div>"
            
            div_val = html.escape(str(blue.get("Division","")if isinstance(blue,pd.Series)else(red.get("Division","")if isinstance(red,pd.Series)else"")))
            f_info = f"FIGHT #{int(f_order)}<br>{div_val}"

            html_str += f"""
            <tr>
                <td class='fighter-cell blue-corner-bg'>{b_img}</td>
                <td class='blue-corner-bg'>
                    <span class='fighter-name'>{b_name}</span>
                    <span class='fighter-info-general'>{b_info_geral}</span>
                </td>
                <td class='tasks-cell blue-corner-bg'>{b_tasks_h if b_name else ""}</td>
                <td class='fight-details-cell'>{f_info}</td>
                <td class='tasks-cell red-corner-bg'>{r_tasks_h if r_name else ""}</td>
                <td class='red-corner-bg'>
                    <span class='fighter-name'>{r_name}</span>
                    <span class='fighter-info-general'>{r_info_geral}</span>
                </td>
                <td class='fighter-cell red-corner-bg'>{r_img}</td>
            </tr>
            """
        html_str += "</tbody></table>"
    return html_str
