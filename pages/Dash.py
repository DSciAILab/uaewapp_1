# --- NEW AND FINAL CSS FUNCTION ---
def get_dashboard_style(font_size_px):
    img_size = font_size_px * 3.5
    cell_padding = font_size_px * 0.5
    # Aumentando o multiplicador para a fonte do nome do atleta
    fighter_font_size = font_size_px * 2.0 

    return f"""
    <style>
        div[data-testid="stToolbar"] {{ visibility: hidden; height: 0%; position: fixed; }}
        div[data-testid="stDecoration"] {{ visibility: hidden; height: 0%; position: fixed; }}
        div[data-testid="stStatusWidget"] {{ visibility: hidden; height: 0%; position: fixed; }}
        #MainMenu {{ visibility: hidden; height: 0%; }}
        header {{ visibility: hidden; height: 0%; }}
        .block-container {{ padding-top: 1rem !important; padding-bottom: 0rem !important; }}
        
        .dashboard-container {{ font-family: 'Segoe UI', sans-serif; }}
        .dashboard-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background-color: #2a2a2e;
            color: #e1e1e1;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
            border-radius: 12px;
            overflow: hidden;
            table-layout: fixed;
        }}
        .dashboard-table th, .dashboard-table td {{
            border-right: 1px solid #4a4a50;
            border-bottom: 1px solid #4a4a50;
            padding: {cell_padding}px 8px;
            text-align: center;
            vertical-align: middle;
            word-break: break-word;
        }}
        .dashboard-table td {{ font-size: {font_size_px}px !important; }}
        .dashboard-table tr:hover td {{ background-color: #38383c; }}

        .dashboard-table th {{
            background-color: #1c1c1f;
            font-size: 1.5rem;
            font-weight: 600;
            white-space: normal;
        }}
        .blue-corner-header, .red-corner-header, .center-col-header {{
            font-size: 0.8rem !important;
            text-transform: uppercase;
        }}
        .blue-corner-header {{ background-color: #0d2e4e !important; }}
        .red-corner-header {{ background-color: #5a1d1d !important; }}
        .center-col-header {{ background-color: #111 !important; }}

        /* === MUDANÇAS APLICADAS === */
        
        /* 1. LARGURA E FONTE DO NOME AUMENTADAS */
        .fighter-name {{
            width: 45%;  /* Aumentado de 35% para 45% para dar mais espaço */
            font-weight: 700;
            font-size: {fighter_font_size}px !important; /* Fonte maior */
        }}
        .fighter-name-blue {{ text-align: right !important; padding-right: 15px !important; }}
        .fighter-name-red {{ text-align: left !important; padding-left: 15px !important; }}

        /* 2. COLUNAS DE TAREFAS "SUPRIMIDAS" (MUITO MAIS ESTREITAS) */
        .task-header, .status-cell {{
            width: 28px; /* Largura fixa e pequena para compactar as colunas */
        }}

        .photo-cell {{
            width: {img_size + 18}px;
        }}
        .center-info-cell {{
            width: 95px;
            background-color: #333;
            padding: 5px !important;
        }}
        
        /* 3. NOVAS CORES (VERDE MUSGO E AMARELO PASTEL) */
        .status-done {{ background-color: #556B2F; }} /* Verde Musgo */
        .status-requested {{ background-color: #F0E68C; }} /* Amarelo Pastel */

        /* === FIM DAS MUDANÇAS === */
        
        .fighter-img {{
            width: {img_size}px;
            height: {img_size}px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid #666;
        }}
        .fight-info-number {{ font-weight: bold; font-size: 1.2em; color: #fff; line-height: 1.2; }}
        .fight-info-event {{ font-style: italic; font-size: 0.8em; color: #ccc; line-height: 1; }}
        .fight-info-division {{ font-style: normal; font-size: 0.85em; color: #ddd; line-height: 1.2; }}

        .status-cell {{ cursor: help; }}
        .status-pending {{ background-color: #dc3545; }}
        .status-neutral {{ background-color: transparent; }}

        .summary-container {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 20px;
            margin-bottom: 20px;
        }}
    </style>
    """
