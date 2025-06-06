# fighter_to_id_map não é mais necessário se usamos FC_ATHLETE_ID_COL

dash_data_list=[]
for order,group in df_fc_disp.sort_values(by=[FC_EVENT_COL,FC_ORDER_COL]).groupby([FC_EVENT_COL,FC_ORDER_COL]):
    ev,f_ord=order;bl_s=group[group[FC_CORNER_COL]=="blue"].squeeze(axis=0);rd_s=group[group[FC_CORNER_COL]=="red"].squeeze(axis=0)
    row_d={"Evento":ev,"Luta #":int(f_ord)if pd.notna(f_ord)else""}
    for corn_pref,ser_data in[("Azul",bl_s),("Vermelho",rd_s)]:
        f_name_fc=str(ser_data.get(FC_FIGHTER_COL,"N/A")).strip()if isinstance(ser_data,pd.Series)else"N/A"
        # --- USA O NOVO FC_ATHLETE_ID_COL ---
        athlete_id_from_fightcard = str(ser_data.get(FC_ATHLETE_ID_COL, "")).strip() if isinstance(ser_data, pd.Series) else ""
        
        pic_u=ser_data.get(FC_PICTURE_COL,"")if isinstance(ser_data,pd.Series)else""
        row_d[f"Foto {corn_pref}"]=pic_u if isinstance(pic_u,str)and pic_u.startswith("http")else None
        
        # --- Coluna Combinada: ID - Nome ---
        id_display = athlete_id_from_fightcard if athlete_id_from_fightcard else "N/D"
        row_d[f"Lutador {corn_pref}"]=f"{id_display} - {f_name_fc}"if f_name_fc!="N/A"else"N/A"
        
        if pd.notna(f_name_fc)and f_name_fc!="N/A" and athlete_id_from_fightcard: # Usa athlete_id_from_fightcard
            for tsk in all_tsks:
                emoji_stat = get_task_status_representation(athlete_id_from_fightcard,tsk,df_att) # Passa ID do fightcard
                row_d[f"{tsk} ({corn_pref})"]=emoji_stat
        else:
            for tsk in all_tsks:row_d[f"{tsk} ({corn_pref})"]=STATUS_TO_EMOJI.get("Pendente",DEFAULT_EMOJI)
    row_d["Divisão"]=bl_s.get(FC_DIVISION_COL,rd_s.get(FC_DIVISION_COL,"N/A"))if isinstance(bl_s,pd.Series)else(rd_s.get(FC_DIVISION_COL,"N/A")if isinstance(rd_s,pd.Series)else"N/A")
    dash_data_list.append(row_d)

if not dash_data_list:st.info(f"Nenhuma luta processada para '{sel_ev_opt}'.");st.stop()
df_dash=pd.DataFrame(dash_data_list)

col_conf_edit={ # Removidas colunas de ID separadas
    "Evento":st.column_config.TextColumn(width="small",disabled=True),"Luta #":st.column_config.NumberColumn(width="small",format="%d",disabled=True),
    "Foto Azul":st.column_config.ImageColumn("Foto(A)",width="small"),"Lutador Azul":st.column_config.TextColumn("Lutador(A) [ID - Nome]",width="large",disabled=True),
    "Divisão":st.column_config.TextColumn(width="medium",disabled=True),
    "Lutador Vermelho":st.column_config.TextColumn("Lutador(V) [ID - Nome]",width="large",disabled=True),"Foto Vermelho":st.column_config.ImageColumn("Foto(V)",width="small"),
}
col_ord_list=["Evento","Luta #","Foto Azul","Lutador Azul"] # Removidas colunas de ID separadas
for tsk_n_col in all_tsks:col_ord_list.append(f"{tsk_n_col} (Azul)")
col_ord_list.append("Divisão")
for tsk_n_col in all_tsks:col_ord_list.append(f"{tsk_n_col} (Vermelho)")
col_ord_list.extend(["Lutador Vermelho","Foto Vermelho"]) # Removidas colunas de ID separadas

leg_parts=[f"{emo}: {dsc}"for emo,dsc in EMOJI_LEGEND.items()if emo.strip()!=""]
help_txt_leg_disp=", ".join(leg_parts)
for tsk_n_col in all_tsks:
    col_conf_edit[f"{tsk_n_col} (Azul)"]=st.column_config.TextColumn(label=tsk_n_col,width="small",help=f"Status:{help_txt_leg_disp}",disabled=True)
    col_conf_edit[f"{tsk_n_col} (Vermelho)"]=st.column_config.TextColumn(label=tsk_n_col,width="small",help=f"Status:{help_txt_leg_disp}",disabled=True)

st.subheader(f"Detalhes das Lutas e Tarefas: {sel_ev_opt}")
st.markdown(f"**Legenda Status Tarefas:** {help_txt_leg_disp}")
tbl_h=(len(df_dash)+1)*45+10;tbl_h=max(400,min(tbl_h,1200))
st.data_editor(df_dash,column_config=col_conf_edit,column_order=col_ord_list,hide_index=True,use_container_width=True,num_rows="fixed",disabled=True,height=tbl_h)
st.markdown("---")

st.subheader(f"Estatísticas do Evento: {sel_ev_opt}")
if not df_dash.empty:
    tot_lutas_ev=df_dash["Luta #"].nunique();uniq_f_ev=set()
    for _,r in df_dash.iterrows(): # Usa a coluna combinada para extrair IDs para contagem de únicos
        if r["Lutador Azul"]!="N/A":uniq_f_ev.add(r["Lutador Azul"].split(" - ",1)[0].strip())
        if r["Lutador Vermelho"]!="N/A":uniq_f_ev.add(r["Lutador Vermelho"].split(" - ",1)[0].strip())
    tot_ath_uniq_ev=len(uniq_f_ev)
    done_c,req_c,not_sol_c,pend_c,tot_tsk_slots=0,0,0,0,0
    for tsk in all_tsks:
        for corn in["Azul","Vermelho"]:
            col_n=f"{tsk} ({corn})"
            if col_n in df_dash.columns:
                val_f_mask=df_dash[f"Lutador {corn}"]!="N/A";tsk_emo_ser=df_dash.loc[val_f_mask,col_n]
                tot_tsk_slots+=len(tsk_emo_ser)
                done_c+=(tsk_emo_ser==STATUS_TO_EMOJI["Done"]).sum();req_c+=(tsk_emo_ser==STATUS_TO_EMOJI["Requested"]).sum()
                not_sol_c+=(tsk_emo_ser==STATUS_TO_EMOJI["---"]).sum();pend_c+=(tsk_emo_ser==STATUS_TO_EMOJI["Pendente"]).sum()
    stat_cs=st.columns(5)
    stat_cs[0].metric("Lutas",tot_lutas_ev);stat_cs[1].metric("Atletas Únicos",tot_ath_uniq_ev)
    stat_cs[2].metric(f"Tarefas {STATUS_TO_EMOJI['Done']}",done_c,help=f"De {tot_tsk_slots} slots.")
    stat_cs[3].metric(f"Tarefas {STATUS_TO_EMOJI['Requested']}",req_c)
    stat_cs[4].metric(f"Tarefas {STATUS_TO_EMOJI['---']}",not_sol_c)
else:st.info("Nenhum dado para estatísticas do evento.")
st.markdown(f"--- \n *Dashboard atualizado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
