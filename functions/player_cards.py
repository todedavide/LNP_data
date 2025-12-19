"""
Modulo per la generazione di schede giocatore con percentili.
"""

import os
import numpy as np
import pandas as pd
from scipy import stats


# Statistiche da mostrare nelle schede
STATS_CONFIG = {
    # Statistiche totali
    'totals': [
        ('PT', 'Punti', 'higher'),
        ('AS', 'Assist', 'higher'),
        ('RT', 'Rimbalzi Tot.', 'higher'),
        ('RO', 'Rimb. Off.', 'higher'),
        ('RD', 'Rimb. Dif.', 'higher'),
        ('PR', 'Palle Rec.', 'higher'),
        ('PP', 'Palle Perse', 'lower'),
        ('ST', 'Stoppate', 'higher'),
        ('FS', 'Falli Subiti', 'higher'),
        ('FF', 'Falli Fatti', 'lower'),
        ('Minutes', 'Minuti', 'higher'),
    ],
    # Statistiche per minuto
    'per_minute': [
        ('PT_permin', 'Punti/min', 'higher'),
        ('AS_permin', 'Assist/min', 'higher'),
        ('RO_permin', 'Rimb.Off/min', 'higher'),
        ('RD_permin', 'Rimb.Dif/min', 'higher'),
        ('PR_permin', 'Palle Rec/min', 'higher'),
        ('ST_permin', 'Stoppate/min', 'higher'),
        ('3PTM_permin', 'Triple/min', 'higher'),
        ('FTA_permin', 'TL tent/min', 'higher'),
        ('FF_permin', 'Falli/min', 'lower'),
        ('FS_permin', 'Falli Sub/min', 'higher'),
    ],
    # Percentuali ed efficienza
    'efficiency': [
        ('True_shooting', 'True Shooting %', 'higher'),
        ('3PT_%', 'Tiro da 3 %', 'higher'),
        ('FT_%', 'Tiri Liberi %', 'higher'),
        ('AS_PP_ratio', 'Assist/PP', 'higher'),
        ('PR_PP_ratio', 'Pall.Rec/PP', 'higher'),
        ('FS_FF_ratio', 'Falli Sub/Fatti', 'higher'),
    ],
    # Plus/Minus
    'impact': [
        ('pm_permin', '+/- per min (mediana)', 'higher'),
        ('pm_permin_adj', '+/- Adjusted (mediana)', 'higher'),
    ]
}


def calculate_percentiles(df, stat_col, direction='higher'):
    """
    Calcola i percentili per una statistica usando scipy.stats.percentileofscore.

    Args:
        df: DataFrame con le statistiche
        stat_col: nome della colonna
        direction: 'higher' se valori alti sono migliori, 'lower' altrimenti

    Returns:
        Series con i percentili (0-100)
    """
    if stat_col not in df.columns:
        return pd.Series([np.nan] * len(df), index=df.index)

    values = df[stat_col]
    valid_mask = ~values.isna()
    valid_values = values[valid_mask].values

    percentiles = pd.Series(np.nan, index=df.index)

    if len(valid_values) > 0:
        # Calcola percentile per ogni valore usando scipy
        # kind='rank': percentile = (n valori <= x) / n * 100
        pct_scores = [
            stats.percentileofscore(valid_values, v, kind='rank')
            for v in valid_values
        ]

        if direction == 'lower':
            # Per stats dove minore è meglio, invertiamo
            pct_scores = [max(0, 100 - p) for p in pct_scores]

        percentiles[valid_mask] = pct_scores

    return percentiles


def compute_player_stats(overall_df, sum_df, median_df):
    """
    Calcola tutte le statistiche e percentili per ogni giocatore.

    Returns:
        DataFrame con statistiche e percentili per ogni giocatore
    """
    # Unisci sum_df e median_df
    player_stats = sum_df.copy()

    # Aggiungi colonne da median_df (merge unico)
    median_cols_to_add = ['pm_permin', 'pm_permin_adj']
    cols_to_merge = ['Giocatore', 'Team'] + [c for c in median_cols_to_add if c in median_df.columns]
    player_stats = player_stats.merge(
        median_df[cols_to_merge],
        on=['Giocatore', 'Team'],
        how='left',
        suffixes=('_sum', '')
    )

    # Se ci sono duplicati, usa la versione senza suffisso
    for col in median_cols_to_add:
        if f'{col}_sum' in player_stats.columns:
            player_stats[col] = player_stats[col].fillna(player_stats[f'{col}_sum'])
            player_stats.drop(columns=[f'{col}_sum'], inplace=True)

    # Aggiungi campionato
    camp_map = overall_df.groupby(['Giocatore', 'Team'])['Campionato'].first()
    player_stats = player_stats.merge(
        camp_map.reset_index(),
        on=['Giocatore', 'Team'],
        how='left'
    )

    # Calcola numero partite
    games_played = overall_df.groupby(['Giocatore', 'Team']).size()
    player_stats = player_stats.merge(
        games_played.reset_index(name='Partite'),
        on=['Giocatore', 'Team'],
        how='left'
    )

    # Calcola percentili per ogni statistica
    all_stats = []
    for category, stats in STATS_CONFIG.items():
        all_stats.extend(stats)

    for stat_col, stat_name, direction in all_stats:
        pct_col = f'{stat_col}_pct'
        player_stats[pct_col] = calculate_percentiles(player_stats, stat_col, direction)

    return player_stats


def get_percentile_color(pct):
    """Restituisce un colore basato sul percentile."""
    if pd.isna(pct):
        return '#999'
    if pct >= 90:
        return '#22c55e'  # Verde brillante
    elif pct >= 75:
        return '#84cc16'  # Verde lime
    elif pct >= 50:
        return '#eab308'  # Giallo
    elif pct >= 25:
        return '#f97316'  # Arancione
    else:
        return '#ef4444'  # Rosso


def get_percentile_label(pct):
    """Restituisce un'etichetta per il percentile."""
    if pd.isna(pct):
        return 'N/D'
    if pct >= 90:
        return 'Elite'
    elif pct >= 75:
        return 'Ottimo'
    elif pct >= 50:
        return 'Buono'
    elif pct >= 25:
        return 'Medio'
    else:
        return 'Basso'


def format_stat_value(value, stat_col):
    """Formatta il valore della statistica."""
    if pd.isna(value):
        return 'N/D'

    # Percentuali
    if stat_col in ['True_shooting', '3PT_%', 'FT_%']:
        return f'{value*100:.1f}%'

    # Per minuto (3 decimali)
    if '_permin' in stat_col:
        return f'{value:.3f}'

    # Rapporti (2 decimali)
    if '_ratio' in stat_col:
        return f'{value:.2f}'

    # Interi
    if stat_col in ['PT', 'AS', 'RT', 'RO', 'RD', 'PR', 'PP', 'ST', 'FS', 'FF', 'Minutes', 'Partite']:
        return f'{int(value)}'

    return f'{value:.2f}'


def generate_player_card_html(player_row):
    """Genera l'HTML per una singola scheda giocatore."""
    name = player_row['Giocatore']
    team = player_row['Team']
    camp = player_row.get('Campionato', 'N/D')
    games = player_row.get('Partite', 0)
    minutes = player_row.get('Minutes', 0)

    html = f'''
    <div class="player-card" id="player-{name.replace(' ', '-').replace("'", "")}">
        <div class="player-header">
            <h3>{name}</h3>
            <div class="player-team">{team}</div>
            <div class="player-meta">{camp.upper()} | {int(games)} partite | {int(minutes)} minuti</div>
        </div>
        <div class="stats-grid">
    '''

    # Sezioni statistiche
    sections = [
        ('Totali Stagione', 'totals'),
        ('Per Minuto', 'per_minute'),
        ('Efficienza', 'efficiency'),
        ('Impatto', 'impact'),
    ]

    for section_title, section_key in sections:
        html += f'''
            <div class="stats-section">
                <h4>{section_title}</h4>
                <div class="stats-list">
        '''

        for stat_col, stat_name, direction in STATS_CONFIG[section_key]:
            value = player_row.get(stat_col, np.nan)
            pct = player_row.get(f'{stat_col}_pct', np.nan)
            color = get_percentile_color(pct)
            pct_display = f'{round(pct)}' if not pd.isna(pct) else '-'

            html += f'''
                    <div class="stat-row">
                        <span class="stat-name">{stat_name}</span>
                        <span class="stat-value">{format_stat_value(value, stat_col)}</span>
                        <span class="stat-pct" style="background-color: {color}">{pct_display}</span>
                    </div>
            '''

        html += '''
                </div>
            </div>
        '''

    html += '''
        </div>
    </div>
    '''

    return html


def generate_table_html(player_stats):
    """Genera l'HTML per la vista tabella."""
    # Colonne da mostrare nella tabella
    table_cols = [
        ('Giocatore', 'Giocatore', 'text'),
        ('Team', 'Squadra', 'text'),
        ('Partite', 'G', 'int'),
        ('Minutes', 'Min', 'int'),
        ('PT', 'PT', 'int'),
        ('AS', 'AS', 'int'),
        ('RT', 'RT', 'int'),
        ('RO', 'RO', 'int'),
        ('RD', 'RD', 'int'),
        ('PR', 'PR', 'int'),
        ('PP', 'PP', 'int'),
        ('ST', 'ST', 'int'),
        ('FS', 'FS', 'int'),
        ('FF', 'FF', 'int'),
        ('PT_permin', 'PT/m', 'float3'),
        ('AS_permin', 'AS/m', 'float3'),
        ('RD_permin', 'RD/m', 'float3'),
        ('PR_permin', 'PR/m', 'float3'),
        ('True_shooting', 'TS%', 'pct'),
        ('3PT_%', '3P%', 'pct'),
        ('FT_%', 'FT%', 'pct'),
        ('AS_PP_ratio', 'AS/PP', 'float2'),
        ('pm_permin', '+/-', 'float3'),
        ('pm_permin_adj', '+/-Adj', 'float3'),
    ]

    html = '<table id="stats-table"><thead><tr>'
    for col, label, _ in table_cols:
        html += f'<th data-col="{col}" onclick="sortTable(\'{col}\')">{label}</th>'
    html += '</tr></thead><tbody>'

    for _, row in player_stats.iterrows():
        html += '<tr>'
        for col, _, fmt in table_cols:
            val = row.get(col, np.nan)
            pct = row.get(f'{col}_pct', None)

            # Formatta valore
            if pd.isna(val):
                cell_val = '-'
            elif fmt == 'int':
                cell_val = str(int(val))
            elif fmt == 'float2':
                cell_val = f'{val:.2f}'
            elif fmt == 'float3':
                cell_val = f'{val:.3f}'
            elif fmt == 'pct':
                cell_val = f'{val*100:.1f}%'
            else:
                cell_val = str(val)

            # Formatta percentile
            if pct is not None and not pd.isna(pct):
                pct_val = f'{round(pct)}'
                pct_sort = pct
            else:
                pct_val = '-'
                pct_sort = -1

            # Colore percentile per colonne numeriche
            color = ''
            if pct is not None and not pd.isna(pct) and fmt != 'text':
                color = get_percentile_color(pct)

            # Valore ordinamento
            sort_val = val if not pd.isna(val) else -9999
            if fmt == 'text':
                sort_val = val if val else ''

            # Aggiungi attributi per toggle valori/percentili
            data_attrs = f'data-sort="{sort_val}" data-val="{cell_val}" data-pct="{pct_val}" data-pct-sort="{pct_sort}"'
            if color:
                data_attrs += f' data-color="{color}"'
            style = f' style="background-color: {color}20"' if color else ''

            html += f'<td {data_attrs}{style}>{cell_val}</td>'
        html += '</tr>'

    html += '</tbody></table>'
    return html


def generate_players_report(player_stats, campionato, output_dir='.'):
    """
    Genera il report HTML con schede giocatori e tabella per un campionato.

    Args:
        player_stats: DataFrame con le statistiche
        campionato: nome del campionato per il titolo
        output_dir: directory di output
    """
    # Ordina per squadra e poi per minuti giocati
    player_stats = player_stats.sort_values(['Team', 'Minutes'], ascending=[True, False])

    # Raggruppa per squadra
    teams = player_stats['Team'].unique()

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Giocatori - {campionato}</title>
    <link rel="icon" type="image/png" href="static/favicon180x180.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Roboto:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --tp-primary: #00F95B;
            --tp-secondary: #302B8F;
            --tp-dark: #18205E;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Roboto', 'Segoe UI', sans-serif;
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            font-family: 'Poppins', sans-serif;
            color: var(--tp-secondary);
            text-align: center;
            margin-bottom: 10px;
        }}
        .header-logo {{
            display: flex;
            justify-content: center;
            margin-bottom: 10px;
        }}
        .header-logo img {{
            height: 50px;
        }}
        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 15px;
        }}

        /* Tabs */
        .tabs {{
            display: flex;
            gap: 5px;
            margin-bottom: 15px;
            justify-content: center;
        }}
        .tab-btn {{
            font-family: 'Poppins', sans-serif;
            padding: 10px 25px;
            border: none;
            background: #ddd;
            cursor: pointer;
            border-radius: 6px 6px 0 0;
            font-size: 14px;
            font-weight: 600;
        }}
        .tab-btn.active {{
            background: var(--tp-secondary);
            color: white;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}

        /* Filter bar */
        .filter-bar {{
            position: sticky;
            top: 0;
            background: white;
            padding: 12px 15px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            z-index: 1000;
        }}
        .filter-section {{
            margin-bottom: 10px;
        }}
        .filter-section:last-child {{
            margin-bottom: 0;
        }}
        .filter-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }}
        .filter-header label {{
            font-weight: bold;
            color: #333;
        }}
        .filter-header .reset-btn {{
            padding: 4px 12px;
            background: var(--tp-secondary);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        .filter-header .reset-btn:hover {{
            background: var(--tp-dark);
        }}
        .team-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }}
        .team-btn {{
            padding: 4px 8px;
            font-size: 11px;
            border: 2px solid #ccc;
            border-radius: 4px;
            background: white;
            cursor: pointer;
            transition: all 0.15s ease;
            color: #666;
        }}
        .team-btn:hover {{
            border-color: var(--tp-primary);
            color: var(--tp-secondary);
        }}
        .team-btn.active {{
            background: var(--tp-primary);
            border-color: var(--tp-primary);
            color: var(--tp-secondary);
            font-weight: 500;
        }}
        .player-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            max-height: 100px;
            overflow-y: auto;
        }}
        .player-btn {{
            padding: 3px 6px;
            font-size: 10px;
            border: 1px solid #ddd;
            border-radius: 3px;
            background: #f9f9f9;
            cursor: pointer;
            transition: all 0.15s ease;
            color: #555;
        }}
        .player-btn:hover {{
            border-color: var(--tp-secondary);
            color: var(--tp-secondary);
        }}
        .player-btn.active {{
            background: var(--tp-secondary);
            border-color: var(--tp-secondary);
            color: white;
        }}
        .search-box {{
            padding: 6px 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 12px;
            width: 200px;
        }}
        .toggle-container {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-left: auto;
            background: #f0f0f0;
            padding: 6px 12px;
            border-radius: 20px;
        }}
        .toggle-label {{
            font-size: 12px;
            color: #666;
            cursor: pointer;
        }}
        .toggle-label.active {{
            color: var(--tp-secondary);
            font-weight: bold;
        }}
        .toggle-switch {{
            width: 44px;
            height: 24px;
            background: var(--tp-secondary);
            border-radius: 12px;
            position: relative;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .toggle-switch::after {{
            content: '';
            position: absolute;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            top: 2px;
            left: 2px;
            transition: transform 0.2s;
        }}
        .toggle-switch.percentile {{
            background: var(--tp-primary);
        }}
        .toggle-switch.percentile::after {{
            transform: translateX(20px);
        }}

        /* Cards */
        .team-section {{
            margin-bottom: 30px;
        }}
        .team-section h2 {{
            font-family: 'Poppins', sans-serif;
            color: var(--tp-secondary);
            border-bottom: 2px solid var(--tp-primary);
            padding-bottom: 5px;
            margin-bottom: 15px;
        }}
        .players-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 15px;
        }}
        .player-card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .player-header {{
            background: linear-gradient(135deg, var(--tp-secondary), var(--tp-dark));
            color: white;
            padding: 12px 15px;
        }}
        .player-header h3 {{
            font-family: 'Poppins', sans-serif;
            margin: 0 0 3px 0;
            font-size: 16px;
        }}
        .player-team {{
            font-size: 13px;
            opacity: 0.9;
        }}
        .player-meta {{
            font-size: 11px;
            opacity: 0.7;
            margin-top: 3px;
        }}
        .stats-grid {{
            padding: 10px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        .stats-section {{
            background: #f9f9f9;
            border-radius: 6px;
            padding: 8px;
        }}
        .stats-section h4 {{
            font-family: 'Poppins', sans-serif;
            margin: 0 0 8px 0;
            font-size: 12px;
            color: var(--tp-secondary);
            text-transform: uppercase;
        }}
        .stats-list {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .stat-row {{
            display: flex;
            align-items: center;
            font-size: 11px;
            gap: 5px;
        }}
        .stat-name {{
            flex: 1;
            color: #555;
        }}
        .stat-value {{
            font-weight: bold;
            min-width: 45px;
            text-align: right;
        }}
        .stat-pct {{
            min-width: 28px;
            text-align: center;
            padding: 2px 4px;
            border-radius: 3px;
            color: white;
            font-weight: bold;
            font-size: 10px;
        }}

        /* Table */
        .table-container {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-x: auto;
        }}
        #stats-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        #stats-table th {{
            font-family: 'Poppins', sans-serif;
            background: var(--tp-secondary);
            color: white;
            padding: 8px 6px;
            text-align: left;
            cursor: pointer;
            white-space: nowrap;
            position: sticky;
            top: 0;
        }}
        #stats-table th:hover {{
            background: var(--tp-dark);
        }}
        #stats-table th.sorted-asc::after {{
            content: ' ▲';
        }}
        #stats-table th.sorted-desc::after {{
            content: ' ▼';
        }}
        #stats-table td {{
            padding: 6px;
            border-bottom: 1px solid #eee;
        }}
        #stats-table tr:hover {{
            background: #f0f0ff;
        }}
        #stats-table td:first-child {{
            font-weight: bold;
        }}

        /* Legend */
        .legend {{
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
        }}
        .legend-color {{
            width: 20px;
            height: 14px;
            border-radius: 3px;
        }}
        .hidden {{
            display: none !important;
        }}
    </style>
</head>
<body>
    <div class="header-logo">
        <img src="static/twinplay_one_row.svg" alt="TwinPlay">
    </div>
    <h1>Giocatori - {campionato}</h1>
    <p class="subtitle">Percentili calcolati rispetto a tutti i giocatori del campionato (min. 100 minuti)</p>

    <div class="tabs">
        <button class="tab-btn active" onclick="showTab('cards')">Schede</button>
        <button class="tab-btn" onclick="showTab('table')">Tabella</button>
    </div>

    <div class="legend">
        <div class="legend-item"><div class="legend-color" style="background: #22c55e"></div> 90+ Elite</div>
        <div class="legend-item"><div class="legend-color" style="background: #84cc16"></div> 75-89 Ottimo</div>
        <div class="legend-item"><div class="legend-color" style="background: #eab308"></div> 50-74 Buono</div>
        <div class="legend-item"><div class="legend-color" style="background: #f97316"></div> 25-49 Medio</div>
        <div class="legend-item"><div class="legend-color" style="background: #ef4444"></div> 0-24 Basso</div>
    </div>

    <!-- TAB SCHEDE -->
    <div id="tab-cards" class="tab-content active">
        <div class="filter-bar">
            <div class="filter-section">
                <div class="filter-header">
                    <label>Squadre:</label>
                    <button class="reset-btn" onclick="resetTeamFilter('cards')">Reset</button>
                </div>
                <div class="team-buttons" id="cards-team-buttons">
'''

    for team in sorted(teams):
        html += f'                    <button class="team-btn" data-team="{team}" onclick="toggleTeamFilter(this, \'cards\')">{team}</button>\n'

    html += '''
                </div>
            </div>
            <div class="filter-section">
                <div class="filter-header">
                    <label>Giocatori:</label>
                    <button class="reset-btn" onclick="resetPlayerFilter('cards')">Reset</button>
                    <input type="text" class="search-box" id="cards-search" placeholder="Cerca..." oninput="filterPlayerButtons('cards')">
                </div>
                <div class="player-buttons" id="cards-player-buttons">
'''

    # Aggiungi pulsanti giocatori con team associato
    player_team_map = player_stats[['Giocatore', 'Team']].drop_duplicates().sort_values('Giocatore')
    for _, row in player_team_map.iterrows():
        player, team = row['Giocatore'], row['Team']
        html += f'                    <button class="player-btn" data-player="{player}" data-team="{team}" onclick="togglePlayerFilter(this, \'cards\')">{player}</button>\n'

    html += '''
                </div>
            </div>
        </div>
'''

    # Genera schede per squadra
    for team in sorted(teams):
        team_players = player_stats[player_stats['Team'] == team]

        html += f'''
        <div class="team-section" data-team="{team}">
            <h2>{team}</h2>
            <div class="players-grid">
'''

        for _, player in team_players.iterrows():
            html += generate_player_card_html(player)

        html += '''
            </div>
        </div>
'''

    html += '''
    </div>

    <!-- TAB TABELLA -->
    <div id="tab-table" class="tab-content">
        <div class="filter-bar">
            <div class="filter-section">
                <div class="filter-header">
                    <label>Squadre:</label>
                    <button class="reset-btn" onclick="resetTeamFilter('table')">Reset</button>
                </div>
                <div class="team-buttons" id="table-team-buttons">
'''

    for team in sorted(teams):
        html += f'                    <button class="team-btn" data-team="{team}" onclick="toggleTeamFilter(this, \'table\')">{team}</button>\n'

    html += '''
                </div>
            </div>
            <div class="filter-section">
                <div class="filter-header">
                    <label>Giocatori:</label>
                    <button class="reset-btn" onclick="resetPlayerFilter('table')">Reset</button>
                    <input type="text" class="search-box" id="table-search" placeholder="Cerca..." oninput="filterPlayerButtons('table')">
                </div>
                <div class="player-buttons" id="table-player-buttons">
'''

    for _, row in player_team_map.iterrows():
        player, team = row['Giocatore'], row['Team']
        html += f'                    <button class="player-btn" data-player="{player}" data-team="{team}" onclick="togglePlayerFilter(this, \'table\')">{player}</button>\n'

    html += '''
                </div>
            </div>
            <div class="filter-section" style="display: flex; align-items: center;">
                <div class="toggle-container">
                    <span class="toggle-label active" id="label-values" onclick="setTableMode('values')">Valori</span>
                    <div class="toggle-switch" id="table-toggle" onclick="toggleTableMode()"></div>
                    <span class="toggle-label" id="label-percentile" onclick="setTableMode('percentile')">Percentili</span>
                </div>
            </div>
        </div>
        <div class="table-container">
'''

    # Genera tabella
    html += generate_table_html(player_stats)

    html += '''
        </div>
    </div>

    <script>
        // Stato filtri per ogni tab
        const filters = {
            cards: { teams: new Set(), players: new Set() },
            table: { teams: new Set(), players: new Set() }
        };
        let currentSort = { col: null, asc: true };
        let tableMode = 'values'; // 'values' o 'percentile'

        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('tab-' + tabName).classList.add('active');
            event.target.classList.add('active');
        }

        function toggleTeamFilter(btn, tab) {
            const team = btn.dataset.team;
            if (filters[tab].teams.has(team)) {
                filters[tab].teams.delete(team);
                btn.classList.remove('active');
            } else {
                filters[tab].teams.add(team);
                btn.classList.add('active');
            }
            filterPlayerButtons(tab);
            applyFilters(tab);
        }

        function togglePlayerFilter(btn, tab) {
            const player = btn.dataset.player;
            if (filters[tab].players.has(player)) {
                filters[tab].players.delete(player);
                btn.classList.remove('active');
            } else {
                filters[tab].players.add(player);
                btn.classList.add('active');
            }
            applyFilters(tab);
        }

        function resetTeamFilter(tab) {
            filters[tab].teams.clear();
            document.querySelectorAll(`#${tab}-team-buttons .team-btn`).forEach(btn => btn.classList.remove('active'));
            filterPlayerButtons(tab);
            applyFilters(tab);
        }

        function resetPlayerFilter(tab) {
            filters[tab].players.clear();
            document.querySelectorAll(`#${tab}-player-buttons .player-btn`).forEach(btn => btn.classList.remove('active'));
            document.getElementById(`${tab}-search`).value = '';
            filterPlayerButtons(tab);
            applyFilters(tab);
        }

        function filterPlayerButtons(tab) {
            const search = document.getElementById(`${tab}-search`).value.toLowerCase();
            const selectedTeams = filters[tab].teams;
            const hasTeamFilter = selectedTeams.size > 0;

            document.querySelectorAll(`#${tab}-player-buttons .player-btn`).forEach(btn => {
                const name = btn.dataset.player.toLowerCase();
                const team = btn.dataset.team;

                const matchesSearch = !search || name.includes(search);
                const matchesTeam = !hasTeamFilter || selectedTeams.has(team);

                btn.style.display = (matchesSearch && matchesTeam) ? '' : 'none';

                // Se il giocatore era selezionato ma ora è nascosto, deselezionalo
                if (btn.style.display === 'none' && filters[tab].players.has(btn.dataset.player)) {
                    filters[tab].players.delete(btn.dataset.player);
                    btn.classList.remove('active');
                }
            });
        }

        function applyFilters(tab) {
            if (tab === 'cards') {
                applyCardsFilter();
            } else {
                applyTableFilter();
            }
        }

        function applyCardsFilter() {
            const { teams, players } = filters.cards;
            const hasTeamFilter = teams.size > 0;
            const hasPlayerFilter = players.size > 0;

            document.querySelectorAll('.team-section').forEach(section => {
                const team = section.dataset.team;
                const teamMatch = !hasTeamFilter || teams.has(team);

                if (!teamMatch) {
                    section.classList.add('hidden');
                } else {
                    section.classList.remove('hidden');

                    section.querySelectorAll('.player-card').forEach(card => {
                        const name = card.querySelector('h3').textContent;
                        const playerMatch = !hasPlayerFilter || players.has(name);
                        card.classList.toggle('hidden', !playerMatch);
                    });
                }
            });
        }

        function applyTableFilter() {
            const { teams, players } = filters.table;
            const hasTeamFilter = teams.size > 0;
            const hasPlayerFilter = players.size > 0;

            document.querySelectorAll('#stats-table tbody tr').forEach(row => {
                const name = row.cells[0].textContent;
                const team = row.cells[1].textContent;
                const teamMatch = !hasTeamFilter || teams.has(team);
                const playerMatch = !hasPlayerFilter || players.has(name);

                row.classList.toggle('hidden', !(teamMatch && playerMatch));
            });
        }

        function sortTable(col) {
            const table = document.getElementById('stats-table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const headers = table.querySelectorAll('th');
            const colIndex = Array.from(headers).findIndex(h => h.dataset.col === col);

            if (currentSort.col === col) {
                currentSort.asc = !currentSort.asc;
            } else {
                currentSort.col = col;
                currentSort.asc = false;
            }

            headers.forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
            headers[colIndex].classList.add(currentSort.asc ? 'sorted-asc' : 'sorted-desc');

            rows.sort((a, b) => {
                // Usa il valore di ordinamento corretto in base alla modalità
                const sortAttr = tableMode === 'percentile' ? 'pctSort' : 'sort';
                let aVal = a.cells[colIndex].dataset[sortAttr] || a.cells[colIndex].dataset.sort;
                let bVal = b.cells[colIndex].dataset[sortAttr] || b.cells[colIndex].dataset.sort;

                const aNum = parseFloat(aVal);
                const bNum = parseFloat(bVal);

                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return currentSort.asc ? aNum - bNum : bNum - aNum;
                }

                return currentSort.asc
                    ? aVal.localeCompare(bVal)
                    : bVal.localeCompare(aVal);
            });

            rows.forEach(row => tbody.appendChild(row));
        }

        function toggleTableMode() {
            setTableMode(tableMode === 'values' ? 'percentile' : 'values');
        }

        function setTableMode(mode) {
            tableMode = mode;
            const toggle = document.getElementById('table-toggle');
            const labelValues = document.getElementById('label-values');
            const labelPercentile = document.getElementById('label-percentile');

            if (mode === 'percentile') {
                toggle.classList.add('percentile');
                labelValues.classList.remove('active');
                labelPercentile.classList.add('active');
            } else {
                toggle.classList.remove('percentile');
                labelValues.classList.add('active');
                labelPercentile.classList.remove('active');
            }

            // Aggiorna contenuto celle
            document.querySelectorAll('#stats-table tbody td').forEach(cell => {
                const val = cell.dataset.val;
                const pct = cell.dataset.pct;
                const color = cell.dataset.color;

                if (mode === 'percentile' && pct && pct !== '-') {
                    cell.textContent = pct;
                    if (color) {
                        cell.style.backgroundColor = color + '40';
                    }
                } else {
                    cell.textContent = val;
                    if (color) {
                        cell.style.backgroundColor = color + '20';
                    }
                }
            });
        }
    </script>
</body>
</html>
'''

    # Salva file
    filename = os.path.join(output_dir, f'players_{campionato.lower().replace(" ", "_")}.html')
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Schede giocatori salvate: {filename}")
    return filename
