"""
Generatori di contenuto per le singole pagine del sito.
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json

from .analysis import (
    load_all_data,
    preprocess_data,
    compute_aggregated_stats,
)
from .advanced_analysis import (
    compute_team_stats,
    compute_team_dependency,
    compute_shot_distribution,
    compute_consistency_metrics,
    compute_team_game_stats,
    compute_win_vs_loss_diff_by_team,
    compute_team_game_rules,
    compute_player_based_rules,
    compute_player_similarity,
    RADAR_STATS,
    TEAM_RADAR_STATS,
)
from .config import SIMILAR_TEAMS
from .official_standings import merge_standings, get_cache_info
from .pbp_analysis import (
    load_pbp_data,
    load_quarters_data,
    compute_clutch_stats,
    compute_closer_rankings,
    compute_clutch_responsibility,
    compute_q4_heroes,
    compute_quarter_distribution,
    compute_scoring_runs,
    compute_comeback_stats,
    compute_player_quarter_activity,
    compute_team_player_distribution,
)


# ============ HELPER ============

def plotly_to_html(fig):
    """Converte figura Plotly in HTML."""
    if fig is None:
        return '<p style="color: #666;">Dati insufficienti.</p>'
    return fig.to_html(full_html=False, include_plotlyjs=False)


def load_and_prepare_data(campionato_filter):
    """Carica e prepara i dati per un campionato."""
    overall_df, _ = load_all_data(campionato_filter)
    if overall_df is None:
        return None, None, None

    overall_df = preprocess_data(overall_df, similar_teams=SIMILAR_TEAMS)
    sum_df, median_df = compute_aggregated_stats(overall_df)

    return overall_df, sum_df, median_df


def get_camp_stats(campionato_filter):
    """Ottiene statistiche riassuntive per un campionato."""
    overall_df, sum_df, _ = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'games': 0, 'players': 0, 'teams': 0}

    n_games = overall_df.groupby(['Team', 'Opponent', 'Gap']).ngroups // 2
    return {
        'games': n_games,
        'players': overall_df['Giocatore'].nunique(),
        'teams': overall_df['Team'].nunique()
    }


# ============ PAGINE SQUADRE ============

def generate_squadre_classifiche(campionato_filter, camp_name):
    """Genera contenuto pagina Classifiche & Stats squadre."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Classifiche', 'page_title': 'Classifiche'}

    team_stats = compute_team_stats(overall_df)

    # Calcola statistiche per squadra includendo form e trend
    team_records = []
    for team in overall_df['Team'].unique():
        team_df = overall_df[overall_df['Team'] == team]

        # Raggruppa per partita (game_code identifica univocamente la partita)
        games = team_df.groupby(['game_code', 'Opponent', 'Gap']).agg({
            'PT': 'sum',
            'Result': 'first'
        }).reset_index().sort_values('game_code')

        wins = (games['Gap'] > 0).sum()
        losses = (games['Gap'] < 0).sum()
        gp = wins + losses

        # Punti segnati e subiti per partita
        pts_scored = games['PT'].mean() if len(games) > 0 else 0
        # Punti subiti = punti segnati - gap
        pts_allowed = (games['PT'] - games['Gap']).mean() if len(games) > 0 else 0

        # Form ultime 5 partite (ordinato per game_code = cronologico)
        last_5_results = games.tail(5)['Gap'].apply(lambda x: 'V' if x > 0 else 'S').tolist()
        form = ''.join(last_5_results)

        # Trend: confronta % vittorie ultime 5 vs tutte le precedenti
        if len(games) >= 6:  # Almeno 6 partite per avere confronto significativo
            last_5 = games.tail(5)
            previous = games.iloc[:-5]

            last_5_win_pct = (last_5['Gap'] > 0).mean() * 100
            prev_win_pct = (previous['Gap'] > 0).mean() * 100

            diff = last_5_win_pct - prev_win_pct
            if diff > 10:  # Miglioramento >10%
                trend = '↑'
                trend_color = '#22c55e'
            elif diff < -10:  # Peggioramento >10%
                trend = '↓'
                trend_color = '#ef4444'
            else:
                trend = '→'
                trend_color = '#666'
        else:
            trend = '–'
            trend_color = '#666'

        team_records.append({
            'Squadra': team,
            'GP': gp,
            'V': wins,
            'S': losses,
            'Punti': wins * 2,
            'Win%': round(wins / gp * 100, 1) if gp > 0 else 0,
            'Fatti': round(pts_scored, 1),
            'Subiti': round(pts_allowed, 1),
            'Diff': round(pts_scored - pts_allowed, 1),
            'Form': form,
            'Trend': trend,
            'TrendColor': trend_color
        })

    # Unisci con classifiche ufficiali LNP (se disponibili)
    team_records = merge_standings(team_records, campionato_filter)
    records_df = pd.DataFrame(team_records).sort_values('Punti', ascending=False)

    # Verifica se abbiamo dati ufficiali
    cache_info = get_cache_info()
    has_official = cache_info.get(campionato_filter) is not None

    # Tabella classifica ordinabile
    table_html = '''
    <style>
        .sortable-table th.sortable {
            cursor: pointer;
            user-select: none;
            position: relative;
        }
        .sortable-table th.sortable:hover {
            background: #3d379f;
        }
        .sortable-table th.sortable::after {
            content: '⇅';
            margin-left: 5px;
            opacity: 0.5;
            font-size: 0.8em;
        }
        .sortable-table th.sortable.asc::after {
            content: '↑';
            opacity: 1;
        }
        .sortable-table th.sortable.desc::after {
            content: '↓';
            opacity: 1;
        }
    </style>
    <div style="overflow-x: auto;">
    <table id="classifica-table" class="sortable-table" style="width: 100%; border-collapse: collapse; min-width: 800px;">
        <thead>
            <tr style="background: #302B8F; color: white;">
                <th style="padding: 10px 8px; text-align: center;">#</th>
                <th class="sortable" data-col="1" data-type="string" style="padding: 10px 8px; text-align: left;">Squadra</th>
                <th class="sortable" data-col="2" data-type="number" style="padding: 10px 8px; text-align: center;">Punti</th>
                <th class="sortable" data-col="3" data-type="number" style="padding: 10px 8px; text-align: center;">GP</th>
                <th class="sortable" data-col="4" data-type="number" style="padding: 10px 8px; text-align: center;">V</th>
                <th class="sortable" data-col="5" data-type="number" style="padding: 10px 8px; text-align: center;">S</th>
                <th class="sortable" data-col="6" data-type="number" style="padding: 10px 8px; text-align: center;">Fatti</th>
                <th class="sortable" data-col="7" data-type="number" style="padding: 10px 8px; text-align: center;">Subiti</th>
                <th class="sortable" data-col="8" data-type="number" style="padding: 10px 8px; text-align: center;">Diff</th>
                <th style="padding: 10px 8px; text-align: center;">Ultime 5</th>
                <th style="padding: 10px 8px; text-align: center;">Trend</th>
            </tr>
        </thead>
        <tbody>
    '''
    for i, (_, row) in enumerate(records_df.iterrows(), 1):
        bg = '#f9f9f9' if i % 2 == 0 else 'white'
        diff_color = '#22c55e' if row['Diff'] > 0 else '#ef4444' if row['Diff'] < 0 else '#666'

        # Form con colori
        form_html = ''
        for r in row['Form']:
            if r == 'V':
                form_html += '<span style="color: #22c55e; font-weight: bold;">V</span>'
            else:
                form_html += '<span style="color: #ef4444; font-weight: bold;">S</span>'

        table_html += f'''
            <tr style="background: {bg};">
                <td style="padding: 10px 8px; font-weight: bold; text-align: center;">{i}</td>
                <td style="padding: 10px 8px; font-weight: 600;">{row['Squadra']}</td>
                <td style="padding: 10px 8px; text-align: center; font-weight: bold; font-size: 1.1em;">{row['Punti']}</td>
                <td style="padding: 10px 8px; text-align: center;">{row['GP']}</td>
                <td style="padding: 10px 8px; text-align: center; color: #22c55e; font-weight: bold;">{row['V']}</td>
                <td style="padding: 10px 8px; text-align: center; color: #ef4444; font-weight: bold;">{row['S']}</td>
                <td style="padding: 10px 8px; text-align: center;">{row['Fatti']}</td>
                <td style="padding: 10px 8px; text-align: center;">{row['Subiti']}</td>
                <td style="padding: 10px 8px; text-align: center; color: {diff_color}; font-weight: bold;">{row['Diff']:+.1f}</td>
                <td style="padding: 10px 8px; text-align: center; font-family: monospace;">{form_html}</td>
                <td style="padding: 10px 8px; text-align: center; color: {row['TrendColor']}; font-size: 1.2em;">{row['Trend']}</td>
            </tr>
        '''
    table_html += '''</tbody></table></div>
    <script>
    (function() {
        const table = document.getElementById('classifica-table');
        const headers = table.querySelectorAll('th.sortable');
        let currentSort = {col: null, dir: 'asc'};

        headers.forEach(header => {
            header.addEventListener('click', () => {
                const col = parseInt(header.dataset.col);
                const type = header.dataset.type;
                const dir = (currentSort.col === col && currentSort.dir === 'asc') ? 'desc' : 'asc';

                // Rimuovi classi da tutte le colonne
                headers.forEach(h => h.classList.remove('asc', 'desc'));
                header.classList.add(dir);

                // Ordina righe
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));

                rows.sort((a, b) => {
                    let aVal = a.cells[col].textContent.trim();
                    let bVal = b.cells[col].textContent.trim();

                    if (type === 'number') {
                        aVal = parseFloat(aVal.replace(',', '.')) || 0;
                        bVal = parseFloat(bVal.replace(',', '.')) || 0;
                    }

                    if (dir === 'asc') {
                        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
                    } else {
                        return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
                    }
                });

                // Reinserisce righe ordinate e ricalcola zebra + posizione
                rows.forEach((row, idx) => {
                    row.style.background = idx % 2 === 0 ? 'white' : '#f9f9f9';
                    row.cells[0].textContent = idx + 1;
                    tbody.appendChild(row);
                });

                currentSort = {col, dir};
            });
        });
    })();
    </script>'''

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Classifica</h2>
        {table_html}
    </div>
    '''

    return {
        'content': content,
        'title': f'Classifiche - {camp_name}',
        'page_title': 'Classifiche & Stats',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Squadre / Classifiche'
    }


def generate_squadre_radar(campionato_filter, camp_name):
    """Genera contenuto pagina Radar Squadre."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Radar Squadre', 'page_title': 'Radar Squadre'}

    team_stats = compute_team_stats(overall_df)

    # Prepara dati per radar (normalizzati 0-100 dove 100 = max del campionato) e valori raw
    team_radar_data = {}
    team_raw_data = {}
    for _, row in team_stats.iterrows():
        values = []
        raw_values = {}
        for col, name in TEAM_RADAR_STATS:
            if col in row:
                val = row[col]
                raw_values[name] = round(float(val), 2) if pd.notna(val) else 0
                col_max = team_stats[col].max()
                if col_max > 0:
                    norm = (val / col_max) * 100
                else:
                    norm = 0
                values.append(round(norm, 1))
            else:
                values.append(0)
                raw_values[name] = 0
        team_radar_data[row['Team']] = values
        team_raw_data[row['Team']] = raw_values

    # Genera select + div per radar interattivo
    teams_json = json.dumps(team_radar_data)
    raw_json = json.dumps(team_raw_data)
    categories_json = json.dumps([name for _, name in TEAM_RADAR_STATS])

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Confronto Radar Squadre</h2>
        <div style="margin-bottom: 20px; display: flex; gap: 20px; flex-wrap: wrap;">
            <div>
                <label style="font-weight: 600;">Squadra 1:</label>
                <select id="team1" onchange="updateRadar()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd;">
                    {''.join(f'<option value="{t}">{t}</option>' for t in sorted(team_radar_data.keys()))}
                </select>
            </div>
            <div>
                <label style="font-weight: 600;">Squadra 2:</label>
                <select id="team2" onchange="updateRadar()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd;">
                    <option value="">-- Nessuna --</option>
                    {''.join(f'<option value="{t}">{t}</option>' for t in sorted(team_radar_data.keys()))}
                </select>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 350px; gap: 20px; align-items: start;">
            <div id="radar-chart"></div>
            <div id="comparison-table" style="background: #f9f9f9; border-radius: 8px; padding: 15px;"></div>
        </div>
    </div>

    <script>
        const teamData = {teams_json};
        const teamRaw = {raw_json};
        const categories = {categories_json};

        function updateRadar() {{
            const t1 = document.getElementById('team1').value;
            const t2 = document.getElementById('team2').value;

            const data = [];
            const colors = ['#302B8F', '#00F95B'];

            [t1, t2].forEach((team, i) => {{
                if (team && teamData[team]) {{
                    const vals = [...teamData[team]];
                    const cats = [...categories];
                    vals.push(vals[0]);
                    cats.push(cats[0]);

                    data.push({{
                        type: 'scatterpolar',
                        r: vals,
                        theta: cats,
                        fill: 'toself',
                        fillcolor: colors[i] + '33',
                        line: {{ color: colors[i], width: 2 }},
                        name: team
                    }});
                }}
            }});

            const layout = {{
                polar: {{
                    radialaxis: {{ visible: true, range: [0, 100] }}
                }},
                showlegend: true,
                height: 450,
                margin: {{ t: 30, b: 30 }}
            }};

            Plotly.newPlot('radar-chart', data, layout);

            // Update comparison table
            updateComparisonTable(t1, t2);
        }}

        function updateComparisonTable(t1, t2) {{
            const tableDiv = document.getElementById('comparison-table');

            if (!t2 || !teamRaw[t1] || !teamRaw[t2]) {{
                // Single team view
                if (teamRaw[t1]) {{
                    let html = '<h4 style="margin: 0 0 12px 0; color: #302B8F;">Valori Medi</h4>';
                    html += '<table style="width: 100%; font-size: 14px;">';
                    categories.forEach(cat => {{
                        const val = teamRaw[t1][cat];
                        html += `<tr><td style="padding: 6px 0;">${{cat}}</td><td style="text-align: right; font-weight: 600;">${{val}}</td></tr>`;
                    }});
                    html += '</table>';
                    tableDiv.innerHTML = html;
                }}
                return;
            }}

            // Two team comparison
            let html = '<h4 style="margin: 0 0 12px 0; color: #302B8F;">Confronto Valori</h4>';
            html += '<table style="width: 100%; font-size: 13px; border-collapse: collapse;">';
            html += '<thead><tr style="border-bottom: 2px solid #ddd;">';
            html += '<th style="text-align: left; padding: 6px 4px;">Stat</th>';
            html += '<th style="text-align: center; padding: 6px 4px; color: #302B8F;">🔵</th>';
            html += '<th style="text-align: center; padding: 6px 4px; color: #00F95B;">🟢</th>';
            html += '</tr></thead><tbody>';

            categories.forEach(cat => {{
                const v1 = teamRaw[t1][cat];
                const v2 = teamRaw[t2][cat];
                const better1 = v1 > v2;
                const better2 = v2 > v1;
                const c1 = better1 ? '#22c55e' : (better2 ? '#ef4444' : '#666');
                const c2 = better2 ? '#22c55e' : (better1 ? '#ef4444' : '#666');
                const w1 = better1 ? 'bold' : 'normal';
                const w2 = better2 ? 'bold' : 'normal';

                html += `<tr style="border-bottom: 1px solid #eee;">`;
                html += `<td style="padding: 6px 4px;">${{cat}}</td>`;
                html += `<td style="text-align: center; padding: 6px 4px; color: ${{c1}}; font-weight: ${{w1}};">${{v1}}</td>`;
                html += `<td style="text-align: center; padding: 6px 4px; color: ${{c2}}; font-weight: ${{w2}};">${{v2}}</td>`;
                html += `</tr>`;
            }});

            html += '</tbody></table>';
            tableDiv.innerHTML = html;
        }}

        updateRadar();
    </script>
    '''

    return {
        'content': content,
        'title': f'Radar Squadre - {camp_name}',
        'page_title': 'Radar Squadre',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Squadre / Radar'
    }


def generate_squadre_vittorie_sconfitte(campionato_filter, camp_name):
    """Genera contenuto pagina Vittorie vs Sconfitte."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Vittorie vs Sconfitte', 'page_title': 'Vittorie vs Sconfitte'}

    team_games = compute_team_game_stats(overall_df)
    team_diffs = compute_win_vs_loss_diff_by_team(team_games)

    # Prepara dati per JavaScript
    win_loss_js = {}
    for team, data in team_diffs.items():
        win_loss_js[team] = {
            'data': data['data'],
            'n_wins': int(data['n_wins']),
            'n_losses': int(data['n_losses']),
            'win_rate': round(float(data['win_rate']), 1)
        }

    data_json = json.dumps(win_loss_js)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Vittorie vs Sconfitte per Squadra</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Confronta le statistiche nelle partite vinte vs perse. Ordinate per influenza.
        </p>

        <div style="margin-bottom: 20px;">
            <label style="font-weight: 600;">Squadra:</label>
            <select id="team-select" onchange="showWinLoss()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd; min-width: 200px;">
                {''.join(f'<option value="{t}">{t}</option>' for t in sorted(team_diffs.keys()))}
            </select>
        </div>

        <div id="winloss-content"></div>
    </div>

    <script>
        const winLossData = {data_json};

        function showWinLoss() {{
            const team = document.getElementById('team-select').value;
            const contentDiv = document.getElementById('winloss-content');

            if (!winLossData[team]) {{
                contentDiv.innerHTML = '<p>Dati non disponibili.</p>';
                return;
            }}

            const data = winLossData[team];
            const labels = {{
                'PT': 'Punti', 'AS': 'Assist', 'RT': 'Rimbalzi', 'PR': 'Recuperi',
                'ST': 'Stoppate', '3PTM': 'Triple'
            }};

            // Raggruppa per statistica
            const statGroups = {{}};
            data.data.forEach(row => {{
                const stat = row['Statistica'];
                if (!statGroups[stat]) statGroups[stat] = {{ fatte: null, subite: null, maxInfluenza: 0 }};
                if (row['Tipo'] === 'Noi') statGroups[stat].fatte = row;
                else statGroups[stat].subite = row;
                statGroups[stat].maxInfluenza = Math.max(statGroups[stat].maxInfluenza, row['Influenza']);
            }});

            const sortedStats = Object.entries(statGroups).sort((a, b) => b[1].maxInfluenza - a[1].maxInfluenza);
            const allValues = data.data.flatMap(r => [r['Media Vittorie'], r['Media Sconfitte']]);
            const maxValue = Math.max(...allValues);

            let html = `<p style="margin-bottom: 15px;">
                <span style="color: #22c55e;">●</span> <strong>${{data.n_wins}} vittorie</strong> vs
                <span style="color: #ef4444;">●</span> <strong>${{data.n_losses}} sconfitte</strong>
                (Win rate: ${{data.win_rate}}%)
            </p>`;

            html += '<div style="display: flex; flex-direction: column; gap: 16px;">';

            sortedStats.forEach(([stat, group]) => {{
                const label = labels[stat] || stat;
                html += `<div style="background: white; border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px;">`;
                html += `<div style="text-align: center; margin-bottom: 12px; font-weight: 700; color: #302B8F; font-size: 16px;">${{label}}</div>`;
                html += `<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">`;

                ['fatte', 'subite'].forEach((tipo, idx) => {{
                    const rowData = tipo === 'fatte' ? group.fatte : group.subite;
                    const tipoColor = tipo === 'fatte' ? '#302B8F' : '#f97316';

                    if (!rowData) {{
                        html += `<div style="background: #f9f9f9; border-radius: 8px; padding: 12px; text-align: center; color: #999;">N/D</div>`;
                        return;
                    }}

                    const winVal = rowData['Media Vittorie'];
                    const lossVal = rowData['Media Sconfitte'];
                    const diffPct = rowData['Diff %'];
                    const diffAbs = rowData['Differenza'];
                    const isPositive = tipo === 'fatte' ? diffPct > 0 : diffPct < 0;
                    const diffColor = isPositive ? '#22c55e' : '#ef4444';
                    const winWidth = (winVal / maxValue) * 100;
                    const lossWidth = (lossVal / maxValue) * 100;

                    html += `<div style="background: #f9f9f9; border-radius: 8px; padding: 12px;">`;
                    html += `<div style="text-align: center; margin-bottom: 10px;">`;
                    html += `<span style="background: ${{tipoColor}}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px;">${{tipo}}</span>`;
                    html += `<div style="margin-top: 6px;">`;
                    html += `<span style="font-size: 20px; font-weight: bold; color: ${{diffColor}};">${{diffPct > 0 ? '+' : ''}}${{diffPct}}%</span>`;
                    html += `<span style="font-size: 13px; color: #666; margin-left: 6px;">(${{diffAbs > 0 ? '+' : ''}}${{diffAbs}})</span>`;
                    html += `</div></div>`;

                    html += `<div style="display: flex; flex-direction: column; gap: 4px;">`;
                    html += `<div style="display: flex; align-items: center; gap: 6px;">`;
                    html += `<div style="width: 16px; font-size: 10px; color: #22c55e; font-weight: bold;">V</div>`;
                    html += `<div style="flex: 1; background: #e5e5e5; border-radius: 3px; height: 18px; position: relative;">`;
                    html += `<div style="width: ${{winWidth}}%; background: #22c55e; height: 100%; border-radius: 3px;"></div>`;
                    html += `<span style="position: absolute; left: 6px; top: 50%; transform: translateY(-50%); font-size: 11px; font-weight: 600; color: #166534;">${{winVal}}</span>`;
                    html += `</div></div>`;

                    html += `<div style="display: flex; align-items: center; gap: 6px;">`;
                    html += `<div style="width: 16px; font-size: 10px; color: #ef4444; font-weight: bold;">S</div>`;
                    html += `<div style="flex: 1; background: #e5e5e5; border-radius: 3px; height: 18px; position: relative;">`;
                    html += `<div style="width: ${{lossWidth}}%; background: #ef4444; height: 100%; border-radius: 3px;"></div>`;
                    html += `<span style="position: absolute; left: 6px; top: 50%; transform: translateY(-50%); font-size: 11px; font-weight: 600; color: #991b1b;">${{lossVal}}</span>`;
                    html += `</div></div>`;
                    html += `</div></div>`;
                }});

                html += `</div></div>`;
            }});

            html += '</div>';
            contentDiv.innerHTML = html;
        }}

        showWinLoss();
    </script>
    '''

    return {
        'content': content,
        'title': f'Vittorie vs Sconfitte - {camp_name}',
        'page_title': 'Vittorie vs Sconfitte',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Squadre / Vittorie vs Sconfitte'
    }


def generate_squadre_casa_trasferta(campionato_filter, camp_name):
    """Genera contenuto pagina Casa vs Trasferta per squadre."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Casa vs Trasferta', 'page_title': 'Casa vs Trasferta'}

    # Verifica se is_home è disponibile
    if 'is_home' not in overall_df.columns:
        content = '''
        <div class="content-section">
            <h2 class="section-title">Casa vs Trasferta</h2>
            <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <h3 style="color: #b45309; margin: 0 0 10px 0;">⚠️ Dati non disponibili</h3>
                <p style="color: #92400e; margin: 0;">
                    I dati attuali non contengono l'informazione casa/trasferta.<br>
                    Esegui <code>python main.py scrape</code> per scaricare i dati aggiornati con questa informazione.
                </p>
            </div>
        </div>
        '''
        return {
            'content': content,
            'title': f'Casa vs Trasferta - {camp_name}',
            'page_title': 'Casa vs Trasferta',
            'subtitle': camp_name,
            'breadcrumb': f'{camp_name} / Squadre / Casa vs Trasferta'
        }

    # Aggrega statistiche per squadra e casa/trasferta
    stat_cols = ['PT', 'AS', 'RT', 'PR', 'ST']
    stat_cols = [c for c in stat_cols if c in overall_df.columns]

    # Prima aggrega a livello di partita (somma i punti di tutti i giocatori per partita)
    game_stats = overall_df.groupby(['Team', 'game_code', 'is_home', 'Gap']).agg({
        **{col: 'sum' for col in stat_cols}
    }).reset_index()

    # Poi aggrega per squadra e casa/trasferta
    team_home_away = game_stats.groupby(['Team', 'is_home']).agg({
        **{col: 'mean' for col in stat_cols},  # Media per partita
        'Gap': ['mean', 'count', lambda x: (x > 0).sum()]  # Gap medio, partite, vittorie
    }).reset_index()

    # Flatten column names
    team_home_away.columns = ['Team', 'is_home'] + stat_cols + ['Gap_pg', 'GP', 'Wins']

    # Arrotonda le medie
    for col in stat_cols:
        team_home_away[col] = team_home_away[col].round(1)

    team_home_away['Win_pct'] = (team_home_away['Wins'] / team_home_away['GP'] * 100).round(1)
    team_home_away['Gap_pg'] = team_home_away['Gap_pg'].round(1)

    # Prepara dati per JavaScript
    teams_data = {}
    for team in team_home_away['Team'].unique():
        team_data = team_home_away[team_home_away['Team'] == team]
        home_data = team_data[team_data['is_home'] == True]
        away_data = team_data[team_data['is_home'] == False]

        if len(home_data) == 0 or len(away_data) == 0:
            continue

        home_row = home_data.iloc[0]
        away_row = away_data.iloc[0]

        teams_data[team] = {
            'home': {
                'gp': int(home_row['GP']),
                'wins': int(home_row['Wins']),
                'win_pct': float(home_row['Win_pct']),
                'gap_pg': float(home_row['Gap_pg']),
                'stats': {col: float(home_row[col]) for col in stat_cols}
            },
            'away': {
                'gp': int(away_row['GP']),
                'wins': int(away_row['Wins']),
                'win_pct': float(away_row['Win_pct']),
                'gap_pg': float(away_row['Gap_pg']),
                'stats': {col: float(away_row[col]) for col in stat_cols}
            }
        }

    data_json = json.dumps(teams_data)
    stat_labels = {'PT': 'Punti', 'AS': 'Assist', 'RT': 'Rimbalzi', 'PR': 'Recuperi', 'ST': 'Stoppate'}

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Casa vs Trasferta</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Confronta le performance delle squadre in casa vs in trasferta.
        </p>

        <div style="margin-bottom: 20px;">
            <label style="font-weight: 600;">Squadra:</label>
            <select id="team-select" onchange="showHomeAway()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd; min-width: 200px;">
                {''.join(f'<option value="{t}">{t}</option>' for t in sorted(teams_data.keys()))}
            </select>
        </div>

        <div id="home-away-content"></div>
    </div>

    <script>
        const teamsData = {data_json};
        const statLabels = {json.dumps(stat_labels)};

        function showHomeAway() {{
            const team = document.getElementById('team-select').value;
            const contentDiv = document.getElementById('home-away-content');

            if (!teamsData[team]) {{
                contentDiv.innerHTML = '<p>Dati non disponibili.</p>';
                return;
            }}

            const data = teamsData[team];
            const home = data.home;
            const away = data.away;

            let html = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px;">
                    <div style="background: linear-gradient(135deg, #22c55e, #16a34a); color: white; padding: 20px; border-radius: 12px; text-align: center;">
                        <div style="font-size: 14px; opacity: 0.9;">🏠 CASA</div>
                        <div style="font-size: 32px; font-weight: 700;">${{home.wins}}/${{home.gp}}</div>
                        <div style="font-size: 18px;">${{home.win_pct}}% vittorie</div>
                        <div style="font-size: 14px; margin-top: 8px;">Media: ${{home.gap_pg > 0 ? '+' : ''}}${{home.gap_pg}} punti</div>
                    </div>
                    <div style="background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 20px; border-radius: 12px; text-align: center;">
                        <div style="font-size: 14px; opacity: 0.9;">✈️ TRASFERTA</div>
                        <div style="font-size: 32px; font-weight: 700;">${{away.wins}}/${{away.gp}}</div>
                        <div style="font-size: 18px;">${{away.win_pct}}% vittorie</div>
                        <div style="font-size: 14px; margin-top: 8px;">Media: ${{away.gap_pg > 0 ? '+' : ''}}${{away.gap_pg}} punti</div>
                    </div>
                </div>
            `;

            // Confronto statistiche
            html += '<h3 style="margin-bottom: 15px;">Statistiche per partita</h3>';
            html += '<div style="display: flex; flex-direction: column; gap: 12px;">';

            Object.keys(statLabels).forEach(stat => {{
                const homeVal = home.stats[stat] || 0;
                const awayVal = away.stats[stat] || 0;
                const maxVal = Math.max(homeVal, awayVal) * 1.1;
                const diff = homeVal - awayVal;
                const diffColor = diff > 0 ? '#22c55e' : (diff < 0 ? '#ef4444' : '#666');

                html += `
                    <div style="background: white; border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                            <span style="font-weight: 600;">${{statLabels[stat]}}</span>
                            <span style="color: ${{diffColor}}; font-weight: 600;">
                                ${{diff > 0 ? '+' : ''}}${{diff.toFixed(1)}}
                            </span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div>
                                <div style="font-size: 12px; color: #22c55e; margin-bottom: 3px;">Casa: ${{homeVal}}</div>
                                <div style="background: #e5e5e5; border-radius: 4px; height: 8px;">
                                    <div style="width: ${{(homeVal / maxVal) * 100}}%; background: #22c55e; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>
                            <div>
                                <div style="font-size: 12px; color: #ef4444; margin-bottom: 3px;">Trasferta: ${{awayVal}}</div>
                                <div style="background: #e5e5e5; border-radius: 4px; height: 8px;">
                                    <div style="width: ${{(awayVal / maxVal) * 100}}%; background: #ef4444; height: 100%; border-radius: 4px;"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }});

            html += '</div>';
            contentDiv.innerHTML = html;
        }}

        showHomeAway();
    </script>
    '''

    return {
        'content': content,
        'title': f'Casa vs Trasferta - {camp_name}',
        'page_title': 'Casa vs Trasferta',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Squadre / Casa vs Trasferta'
    }


# ============ PAGINE GIOCATORI ============

def generate_giocatori_statistiche(campionato_filter, camp_name):
    """Genera contenuto pagina Statistiche & Percentili giocatori."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Statistiche Giocatori', 'page_title': 'Statistiche Giocatori'}

    # Calcola GP (games played)
    gp = overall_df.groupby(['Giocatore', 'Team']).size().reset_index(name='GP')
    sum_df = sum_df.merge(gp, on=['Giocatore', 'Team'], how='left')

    # Calcola medie per partita
    sum_df['PT_pg'] = sum_df['PT'] / sum_df['GP']
    sum_df['AS_pg'] = sum_df['AS'] / sum_df['GP']
    sum_df['RT_pg'] = sum_df['RT'] / sum_df['GP']
    sum_df['PR_pg'] = sum_df['PR'] / sum_df['GP']
    sum_df['ST_pg'] = sum_df['ST'] / sum_df['GP']

    # Rimbalzi offensivi e difensivi
    if 'RO' in sum_df.columns and 'RD' in sum_df.columns:
        sum_df['RO_pg'] = sum_df['RO'] / sum_df['GP']
        sum_df['RD_pg'] = sum_df['RD'] / sum_df['GP']

    # Calcola statistiche per 40 minuti (durata partita italiana)
    sum_df['PT_pm'] = sum_df['PT'] / sum_df['Minutes'] * 40
    sum_df['AS_pm'] = sum_df['AS'] / sum_df['Minutes'] * 40
    sum_df['RT_pm'] = sum_df['RT'] / sum_df['Minutes'] * 40
    sum_df['PR_pm'] = sum_df['PR'] / sum_df['Minutes'] * 40
    sum_df['ST_pm'] = sum_df['ST'] / sum_df['Minutes'] * 40

    # Rimbalzi offensivi e difensivi per 40 min
    if 'RO' in sum_df.columns and 'RD' in sum_df.columns:
        sum_df['RO_pm'] = sum_df['RO'] / sum_df['Minutes'] * 40
        sum_df['RD_pm'] = sum_df['RD'] / sum_df['Minutes'] * 40

    # Usa VAL (valutazione ufficiale) se disponibile, altrimenti calcola EFF
    if 'VAL' in sum_df.columns:
        sum_df['EFF'] = sum_df['VAL']
        sum_df['EFF_pg'] = sum_df['VAL'] / sum_df['GP']
    elif 'PP' in sum_df.columns and 'FS' in sum_df.columns and 'FF' in sum_df.columns:
        sum_df['EFF'] = (sum_df['PT'] + sum_df['RT'] + sum_df['AS'] + sum_df['PR'] +
                         sum_df['ST'] + sum_df['FS']) - (sum_df['PP'] + sum_df['FF'])
        sum_df['EFF_pg'] = sum_df['EFF'] / sum_df['GP']
    else:
        sum_df['EFF'] = sum_df['PT'] + sum_df['RT'] + sum_df['AS'] + sum_df['PR'] + sum_df['ST']
        sum_df['EFF_pg'] = sum_df['EFF'] / sum_df['GP']

    # Parsing tiri e calcolo percentuali
    def parse_shots(df, col):
        """Estrae made e attempted da colonna tipo '4/7'."""
        made = []
        att = []
        for val in df[col]:
            if pd.isna(val) or val == '':
                made.append(0)
                att.append(0)
            else:
                parts = str(val).split('/')
                if len(parts) == 2:
                    made.append(int(parts[0]))
                    att.append(int(parts[1]))
                else:
                    made.append(0)
                    att.append(0)
        return made, att

    # Aggrega tiri per giocatore
    def aggregate_shots(overall_df, sum_df, col_name):
        """Somma made e attempted per ogni giocatore."""
        made_col = f'{col_name}_made'
        att_col = f'{col_name}_att'

        # Parse ogni riga del dataset completo
        shots_data = []
        for _, row in overall_df.iterrows():
            val = row[col_name]
            if pd.isna(val) or val == '':
                m, a = 0, 0
            else:
                parts = str(val).split('/')
                if len(parts) == 2:
                    m, a = int(parts[0]), int(parts[1])
                else:
                    m, a = 0, 0
            shots_data.append({'Giocatore': row['Giocatore'], 'Team': row['Team'], made_col: m, att_col: a})

        shots_df = pd.DataFrame(shots_data)
        shots_agg = shots_df.groupby(['Giocatore', 'Team']).agg({made_col: 'sum', att_col: 'sum'}).reset_index()
        return sum_df.merge(shots_agg, on=['Giocatore', 'Team'], how='left')

    # Aggrega tutti i tipi di tiro
    if '2PT' in overall_df.columns:
        sum_df = aggregate_shots(overall_df, sum_df, '2PT')
    if '3PT' in overall_df.columns:
        sum_df = aggregate_shots(overall_df, sum_df, '3PT')
    if 'TL' in overall_df.columns:
        sum_df = aggregate_shots(overall_df, sum_df, 'TL')

    # Calcola percentuali
    sum_df['2PT_pct'] = (sum_df['2PT_made'] / sum_df['2PT_att'] * 100).fillna(0).round(1)
    sum_df['3PT_pct'] = (sum_df['3PT_made'] / sum_df['3PT_att'] * 100).fillna(0).round(1)
    sum_df['TL_pct'] = (sum_df['TL_made'] / sum_df['TL_att'] * 100).fillna(0).round(1)

    # eFG% = (FGM + 0.5 * 3PM) / FGA
    sum_df['FG_made'] = sum_df['2PT_made'] + sum_df['3PT_made']
    sum_df['FG_att'] = sum_df['2PT_att'] + sum_df['3PT_att']
    sum_df['eFG_pct'] = ((sum_df['FG_made'] + 0.5 * sum_df['3PT_made']) / sum_df['FG_att'] * 100).fillna(0).round(1)

    # TS% = PTS / (2 * (FGA + 0.44 * FTA))
    sum_df['TS_pct'] = (sum_df['PT'] / (2 * (sum_df['FG_att'] + 0.44 * sum_df['TL_att'])) * 100).fillna(0).round(1)

    # Filtra giocatori con almeno 5 partite
    sum_df_filtered = sum_df[sum_df['GP'] >= 5].copy()

    # Prepara dati per JavaScript (colore unico per tutti)
    stats_config = [
        {'id': 'PT', 'name': 'Punti', 'desc': 'Punti segnati'},
        {'id': 'AS', 'name': 'Assist', 'desc': 'Passaggi decisivi per canestro'},
        {'id': 'RT', 'name': 'Rimbalzi', 'desc': 'Rimbalzi totali (offensivi + difensivi)', 'has_components': True},
        {'id': 'PR', 'name': 'Recuperi', 'desc': 'Palle recuperate'},
        {'id': 'ST', 'name': 'Stoppate', 'desc': 'Tiri avversari stoppati'},
        {'id': 'EFF', 'name': 'VAL', 'desc': 'Valutazione ufficiale LNP: (PT + RT + AS + PR + ST + FS) - (PP + FF + tiri sbagliati)'},
        {'id': '2PT_pct', 'name': '2PT%', 'is_pct': True, 'desc': 'Percentuale tiri da 2 punti (min. 30 tentativi)'},
        {'id': '3PT_pct', 'name': '3PT%', 'is_pct': True, 'desc': 'Percentuale tiri da 3 punti (min. 20 tentativi)'},
        {'id': 'TL_pct', 'name': 'TL%', 'is_pct': True, 'desc': 'Percentuale tiri liberi (min. 20 tentativi)'},
        {'id': 'eFG_pct', 'name': 'eFG%', 'is_pct': True, 'desc': 'Effective FG%: (FGM + 0.5 × 3PM) / FGA - pesa di più i tiri da 3 (min. 50 tentativi)'},
        {'id': 'TS_pct', 'name': 'TS%', 'is_pct': True, 'desc': 'True Shooting%: PTS / (2 × (FGA + 0.44 × FTA)) - efficienza complessiva al tiro includendo TL (min. 50 tentativi)'},
    ]
    main_color = '#302B8F'  # Colore principale TwinPlay

    # Prepara dati per ogni stat (top 20 assoluti, per partita, per 40 min)
    all_data = {}
    for stat in stats_config:
        stat_id = stat['id']
        is_pct = stat.get('is_pct', False)

        if is_pct:
            # Per le percentuali, filtro per minimo tentativi
            if '2PT' in stat_id:
                min_att_col = '2PT_att'
                min_att = 30
            elif '3PT' in stat_id:
                min_att_col = '3PT_att'
                min_att = 20
            elif 'TL' in stat_id:
                min_att_col = 'TL_att'
                min_att = 20
            else:  # eFG, TS
                min_att_col = 'FG_att'
                min_att = 50

            pct_filter = sum_df_filtered[sum_df_filtered[min_att_col] >= min_att].copy()
            if len(pct_filter) == 0:
                pct_filter = sum_df_filtered.nlargest(20, min_att_col)  # fallback

            # Per eFG e TS aggiungi le componenti
            if stat_id in ['eFG_pct', 'TS_pct']:
                cols_pct = ['Giocatore', 'Team', 'GP', stat_id, 'PT_pg', 'FG_made', 'FG_att', '2PT_pct', '3PT_pct', 'TL_pct']
            else:
                cols_pct = ['Giocatore', 'Team', 'GP', stat_id, 'PT_pg', 'FG_made', 'FG_att']

            top_pct = pct_filter.nlargest(20, stat_id)[[c for c in cols_pct if c in pct_filter.columns]].copy()
            pct_list = []
            for _, row in top_pct.iterrows():
                item = {
                    'giocatore': row['Giocatore'],
                    'team': row['Team'],
                    'gp': int(row['GP']),
                    'value': round(float(row[stat_id]), 1),
                    'pt': round(float(row['PT_pg']), 1),
                    'fg_made': int(row['FG_made']),
                    'fg_att': int(row['FG_att']),
                }
                # Aggiungi componenti per eFG e TS
                if stat_id in ['eFG_pct', 'TS_pct']:
                    item['pct_2pt'] = round(float(row['2PT_pct']), 1) if '2PT_pct' in row.index else 0
                    item['pct_3pt'] = round(float(row['3PT_pct']), 1) if '3PT_pct' in row.index else 0
                    item['pct_tl'] = round(float(row['TL_pct']), 1) if 'TL_pct' in row.index else 0
                pct_list.append(item)

            all_data[stat_id] = {'abs': pct_list}
            continue

        stat_pg = f"{stat_id}_pg"
        stat_pm = f"{stat_id}_pm" if stat_id not in ['EFF'] else None
        has_components = stat.get('has_components', False)

        # Top 20 assoluti
        cols_abs = ['Giocatore', 'Team', 'GP', 'Minutes', stat_id, 'PT', 'AS', 'RT']
        if has_components and stat_id == 'RT' and 'RO' in sum_df.columns and 'RD' in sum_df.columns:
            cols_abs += ['RO', 'RD']
        # Rimuovi duplicati mantenendo ordine
        cols_abs = list(dict.fromkeys(cols_abs))
        top_abs = sum_df.nlargest(20, stat_id)[[c for c in cols_abs if c in sum_df.columns]].copy()
        top_abs_list = []
        for _, row in top_abs.iterrows():
            item = {
                'giocatore': row['Giocatore'],
                'team': row['Team'],
                'gp': int(row['GP']),
                'min': int(row['Minutes']),
                'value': round(float(row[stat_id]), 1),
                'pt': round(float(row['PT']), 0),
                'as': round(float(row['AS']), 0),
                'rt': round(float(row['RT']), 0),
            }
            if has_components and stat_id == 'RT' and 'RO' in row.index and 'RD' in row.index:
                item['ro'] = round(float(row['RO']), 0)
                item['rd'] = round(float(row['RD']), 0)
            top_abs_list.append(item)

        # Top 20 per partita
        cols_pg = ['Giocatore', 'Team', 'GP', 'Minutes', stat_pg, 'PT_pg', 'AS_pg', 'RT_pg']
        if has_components and stat_id == 'RT' and 'RO_pg' in sum_df_filtered.columns:
            cols_pg += ['RO_pg', 'RD_pg']
        # Rimuovi duplicati mantenendo ordine
        cols_pg = list(dict.fromkeys(cols_pg))
        top_pg = sum_df_filtered.nlargest(20, stat_pg)[[c for c in cols_pg if c in sum_df_filtered.columns]].copy()
        top_pg_list = []
        for _, row in top_pg.iterrows():
            item = {
                'giocatore': row['Giocatore'],
                'team': row['Team'],
                'gp': int(row['GP']),
                'min': int(row['Minutes']),
                'value': round(float(row[stat_pg]), 2),
                'pt': round(float(row['PT_pg']), 1),
                'as': round(float(row['AS_pg']), 1),
                'rt': round(float(row['RT_pg']), 1),
            }
            if has_components and stat_id == 'RT' and 'RO_pg' in row.index:
                item['ro'] = round(float(row['RO_pg']), 1)
                item['rd'] = round(float(row['RD_pg']), 1)
            top_pg_list.append(item)

        all_data[stat_id] = {
            'abs': top_abs_list,
            'pg': top_pg_list
        }

        # Top 20 per 40 minuti (solo per stats base, non EFF)
        if stat_pm and stat_pm in sum_df_filtered.columns:
            min_filter = sum_df_filtered[sum_df_filtered['Minutes'] >= 100].copy()  # Min 100 minuti
            if len(min_filter) > 0:
                cols_pm = ['Giocatore', 'Team', 'GP', 'Minutes', stat_pm, 'PT_pm', 'AS_pm', 'RT_pm']
                if has_components and stat_id == 'RT' and 'RO_pm' in min_filter.columns:
                    cols_pm += ['RO_pm', 'RD_pm']
                # Rimuovi duplicati mantenendo ordine
                cols_pm = list(dict.fromkeys(cols_pm))
                top_pm = min_filter.nlargest(20, stat_pm)[[c for c in cols_pm if c in min_filter.columns]].copy()
                top_pm_list = []
                for _, row in top_pm.iterrows():
                    item = {
                        'giocatore': row['Giocatore'],
                        'team': row['Team'],
                        'gp': int(row['GP']),
                        'min': int(row['Minutes']),
                        'value': round(float(row[stat_pm]), 1),
                        'pt': round(float(row['PT_pm']), 1),
                        'as': round(float(row['AS_pm']), 1),
                        'rt': round(float(row['RT_pm']), 1),
                    }
                    if has_components and stat_id == 'RT' and 'RO_pm' in row.index:
                        item['ro'] = round(float(row['RO_pm']), 1)
                        item['rd'] = round(float(row['RD_pm']), 1)
                    top_pm_list.append(item)
                all_data[stat_id]['pm'] = top_pm_list

    data_json = json.dumps(all_data)
    config_json = json.dumps(stats_config)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Classifiche Giocatori</h2>

        <!-- Toggle Assoluti / Per Partita / Per 36 Min -->
        <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px; flex-wrap: wrap;">
            <div style="display: flex; background: #e5e5e5; border-radius: 8px; padding: 4px;">
                <button id="btn-abs" onclick="setMode('abs')" style="padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; background: #302B8F; color: white;">
                    Totali
                </button>
                <button id="btn-pg" onclick="setMode('pg')" style="padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; background: transparent; color: #666;">
                    Per Partita
                </button>
                <button id="btn-pm" onclick="setMode('pm')" style="padding: 8px 16px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; background: transparent; color: #666;">
                    Per 40 Min
                </button>
            </div>
            <span id="mode-note" style="color: #666; font-size: 13px;"></span>
        </div>

        <!-- Tab per categoria -->
        <div style="display: flex; gap: 8px; margin-bottom: 15px; flex-wrap: wrap;" id="stat-tabs">
        </div>

        <!-- Descrizione metrica corrente -->
        <div id="stat-description" style="background: #f0f4ff; border-left: 4px solid #302B8F; padding: 12px 16px; margin-bottom: 20px; border-radius: 0 8px 8px 0; font-size: 14px; color: #333;">
        </div>

        <!-- Contenuto dinamico -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; align-items: start;">
            <div id="table-container"></div>
            <div id="chart-container"></div>
        </div>
    </div>

    <script>
        const statsData = {data_json};
        const statsConfig = {config_json};
        const mainColor = '{main_color}';
        let currentMode = 'abs';
        let currentStat = 'PT';

        function initTabs() {{
            const tabsDiv = document.getElementById('stat-tabs');
            tabsDiv.innerHTML = statsConfig.map(s => `
                <button id="tab-${{s.id}}" onclick="setStat('${{s.id}}')"
                    style="padding: 10px 20px; border: 2px solid ${{mainColor}}; border-radius: 8px;
                           cursor: pointer; font-weight: 600; transition: all 0.2s;">
                    ${{s.name}}
                </button>
            `).join('');
            updateTabStyles();
        }}

        function updateTabStyles() {{
            statsConfig.forEach(s => {{
                const btn = document.getElementById('tab-' + s.id);
                if (s.id === currentStat) {{
                    btn.style.background = mainColor;
                    btn.style.color = 'white';
                }} else {{
                    btn.style.background = 'white';
                    btn.style.color = mainColor;
                }}
            }});
        }}

        function setMode(mode) {{
            // Se per 36 min non disponibile per questa stat, fallback a pg
            if (mode === 'pm' && !statsData[currentStat].pm) {{
                mode = 'pg';
            }}
            currentMode = mode;
            ['abs', 'pg', 'pm'].forEach(m => {{
                const btn = document.getElementById('btn-' + m);
                btn.style.background = mode === m ? mainColor : 'transparent';
                btn.style.color = mode === m ? 'white' : '#666';
            }});
            const notes = {{
                'abs': '',
                'pg': '(min. 5 partite)',
                'pm': '(min. 100 minuti, proiettato su 40 min)'
            }};
            document.getElementById('mode-note').textContent = notes[mode];
            render();
        }}

        function setStat(stat) {{
            currentStat = stat;
            updateTabStyles();
            updateDescription();
            // Se la modalità pm non è disponibile per questa stat, passa a pg
            if (currentMode === 'pm' && !statsData[stat].pm) {{
                setMode('pg');
                return;
            }}
            render();
        }}

        function updateDescription() {{
            const config = statsConfig.find(s => s.id === currentStat);
            const descDiv = document.getElementById('stat-description');
            descDiv.innerHTML = `<strong>${{config.name}}:</strong> ${{config.desc || ''}}`;
        }}

        function render() {{
            let data = statsData[currentStat][currentMode];
            // Fallback se dati non disponibili
            if (!data) {{
                data = statsData[currentStat].pg || statsData[currentStat].abs;
            }}
            if (!data) {{
                document.getElementById('table-container').innerHTML = '<p>Dati non disponibili per questa modalità.</p>';
                return;
            }}
            const config = statsConfig.find(s => s.id === currentStat);
            const suffixMap = {{ 'abs': '', 'pg': '/g', 'pm': '/40m' }};
            const suffix = suffixMap[currentMode] || '';
            const statLabel = config.name + suffix;
            const isPct = config.is_pct || false;
            const isCombined = currentStat === 'eFG_pct' || currentStat === 'TS_pct';
            const hasComponents = config.has_components || false;
            const isRT = currentStat === 'RT';

            // Tabella
            const showMin = currentMode === 'pm';
            let headerHtml = '';
            if (isPct) {{
                if (isCombined) {{
                    // Per eFG% e TS%, mostra anche le percentuali componenti
                    headerHtml = `
                        <th style="padding: 10px; text-align: left;">#</th>
                        <th style="padding: 10px; text-align: left;">Giocatore</th>
                        <th style="padding: 10px; text-align: center;">GP</th>
                        <th style="padding: 10px; text-align: center;">${{statLabel}}</th>
                        <th style="padding: 10px; text-align: center;">2PT%</th>
                        <th style="padding: 10px; text-align: center;">3PT%</th>
                        <th style="padding: 10px; text-align: center;">TL%</th>
                        <th style="padding: 10px; text-align: center;">FG</th>
                    `;
                }} else {{
                    // Per 2PT%, 3PT%, TL%
                    headerHtml = `
                        <th style="padding: 10px; text-align: left;">#</th>
                        <th style="padding: 10px; text-align: left;">Giocatore</th>
                        <th style="padding: 10px; text-align: center;">GP</th>
                        <th style="padding: 10px; text-align: center;">${{statLabel}}</th>
                        <th style="padding: 10px; text-align: center;">FG</th>
                        <th style="padding: 10px; text-align: center;">PT/g</th>
                    `;
                }}
            }} else if (hasComponents && isRT) {{
                // Per Rimbalzi, mostra RO e RD
                headerHtml = `
                    <th style="padding: 10px; text-align: left;">#</th>
                    <th style="padding: 10px; text-align: left;">Giocatore</th>
                    <th style="padding: 10px; text-align: center;">GP</th>
                    ${{showMin ? '<th style="padding: 10px; text-align: center;">MIN</th>' : ''}}
                    <th style="padding: 10px; text-align: center;">${{statLabel}}</th>
                    <th style="padding: 10px; text-align: center;">RO${{suffix}}</th>
                    <th style="padding: 10px; text-align: center;">RD${{suffix}}</th>
                    <th style="padding: 10px; text-align: center;">PT${{suffix}}</th>
                `;
            }} else {{
                headerHtml = `
                    <th style="padding: 10px; text-align: left;">#</th>
                    <th style="padding: 10px; text-align: left;">Giocatore</th>
                    <th style="padding: 10px; text-align: center;">GP</th>
                    ${{showMin ? '<th style="padding: 10px; text-align: center;">MIN</th>' : ''}}
                    <th style="padding: 10px; text-align: center;">${{statLabel}}</th>
                    <th style="padding: 10px; text-align: center;">PT${{suffix}}</th>
                    <th style="padding: 10px; text-align: center;">AS${{suffix}}</th>
                    <th style="padding: 10px; text-align: center;">RT${{suffix}}</th>
                `;
            }}

            let tableHtml = `
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                        <tr style="background: ${{mainColor}}; color: white;">
                            ${{headerHtml}}
                        </tr>
                    </thead>
                    <tbody>
            `;

            data.forEach((row, i) => {{
                const bg = i % 2 === 0 ? 'white' : '#f9f9f9';
                let rowHtml = '';
                if (isPct) {{
                    if (isCombined) {{
                        // Per eFG% e TS% mostra componenti
                        rowHtml = `
                            <td style="padding: 8px 10px; font-weight: bold;">${{i + 1}}</td>
                            <td style="padding: 8px 10px;">
                                <div style="font-weight: 600;">${{row.giocatore}}</div>
                                <div style="font-size: 12px; color: #666;">${{row.team}}</div>
                            </td>
                            <td style="padding: 8px 10px; text-align: center;">${{row.gp}}</td>
                            <td style="padding: 8px 10px; text-align: center; font-weight: bold; color: ${{mainColor}};">${{row.value}}%</td>
                            <td style="padding: 8px 10px; text-align: center;">${{row.pct_2pt || '-'}}%</td>
                            <td style="padding: 8px 10px; text-align: center;">${{row.pct_3pt || '-'}}%</td>
                            <td style="padding: 8px 10px; text-align: center;">${{row.pct_tl || '-'}}%</td>
                            <td style="padding: 8px 10px; text-align: center; font-size: 12px;">${{row.fg_made}}/${{row.fg_att}}</td>
                        `;
                    }} else {{
                        // Per 2PT%, 3PT%, TL%
                        rowHtml = `
                            <td style="padding: 8px 10px; font-weight: bold;">${{i + 1}}</td>
                            <td style="padding: 8px 10px;">
                                <div style="font-weight: 600;">${{row.giocatore}}</div>
                                <div style="font-size: 12px; color: #666;">${{row.team}}</div>
                            </td>
                            <td style="padding: 8px 10px; text-align: center;">${{row.gp}}</td>
                            <td style="padding: 8px 10px; text-align: center; font-weight: bold; color: ${{mainColor}};">${{row.value}}%</td>
                            <td style="padding: 8px 10px; text-align: center; font-size: 12px;">${{row.fg_made}}/${{row.fg_att}}</td>
                            <td style="padding: 8px 10px; text-align: center;">${{row.pt}}</td>
                        `;
                    }}
                }} else if (hasComponents && isRT) {{
                    // Per Rimbalzi, mostra RO e RD
                    rowHtml = `
                        <td style="padding: 8px 10px; font-weight: bold;">${{i + 1}}</td>
                        <td style="padding: 8px 10px;">
                            <div style="font-weight: 600;">${{row.giocatore}}</div>
                            <div style="font-size: 12px; color: #666;">${{row.team}}</div>
                        </td>
                        <td style="padding: 8px 10px; text-align: center;">${{row.gp}}</td>
                        ${{showMin ? `<td style="padding: 8px 10px; text-align: center;">${{row.min}}</td>` : ''}}
                        <td style="padding: 8px 10px; text-align: center; font-weight: bold; color: ${{mainColor}};">${{row.value}}</td>
                        <td style="padding: 8px 10px; text-align: center;">${{row.ro !== undefined ? row.ro : '-'}}</td>
                        <td style="padding: 8px 10px; text-align: center;">${{row.rd !== undefined ? row.rd : '-'}}</td>
                        <td style="padding: 8px 10px; text-align: center;">${{row.pt}}</td>
                    `;
                }} else {{
                    rowHtml = `
                        <td style="padding: 8px 10px; font-weight: bold;">${{i + 1}}</td>
                        <td style="padding: 8px 10px;">
                            <div style="font-weight: 600;">${{row.giocatore}}</div>
                            <div style="font-size: 12px; color: #666;">${{row.team}}</div>
                        </td>
                        <td style="padding: 8px 10px; text-align: center;">${{row.gp}}</td>
                        ${{showMin ? `<td style="padding: 8px 10px; text-align: center;">${{row.min}}</td>` : ''}}
                        <td style="padding: 8px 10px; text-align: center; font-weight: bold; color: ${{mainColor}};">${{row.value}}</td>
                        <td style="padding: 8px 10px; text-align: center;">${{row.pt}}</td>
                        <td style="padding: 8px 10px; text-align: center;">${{row.as}}</td>
                        <td style="padding: 8px 10px; text-align: center;">${{row.rt}}</td>
                    `;
                }}
                tableHtml += `<tr style="background: ${{bg}};">${{rowHtml}}</tr>`;
            }});

            tableHtml += '</tbody></table>';
            document.getElementById('table-container').innerHTML = tableHtml;

            // Grafico (top 10)
            const top10 = data.slice(0, 10).reverse();
            const chartData = [{{
                type: 'bar',
                orientation: 'h',
                x: top10.map(r => r.value),
                y: top10.map(r => r.giocatore),
                marker: {{ color: mainColor }},
                text: top10.map(r => r.value),
                textposition: 'outside',
                hovertemplate: '%{{y}}: %{{x}}<extra></extra>'
            }}];

            const layout = {{
                title: {{ text: 'Top 10 ' + statLabel, font: {{ size: 16 }} }},
                height: 400,
                margin: {{ l: 150, r: 50, t: 50, b: 40 }},
                xaxis: {{ title: statLabel }},
                yaxis: {{ automargin: true }}
            }};

            Plotly.newPlot('chart-container', chartData, layout, {{ responsive: true }});
        }}

        initTabs();
        updateDescription();
        render();
    </script>
    '''

    return {
        'content': content,
        'title': f'Statistiche Giocatori - {camp_name}',
        'page_title': 'Statistiche & Percentili',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Giocatori / Statistiche'
    }


def generate_giocatori_radar(campionato_filter, camp_name):
    """Genera contenuto pagina Radar Confronto giocatori."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Radar Giocatori', 'page_title': 'Radar Giocatori'}

    # Calcola GP (games played)
    gp = overall_df.groupby(['Giocatore', 'Team']).size().reset_index(name='GP')
    sum_df = sum_df.merge(gp, on=['Giocatore', 'Team'], how='left')

    # Calcola statistiche per partita
    sum_df = sum_df.copy()
    sum_df['PT_pergame'] = sum_df['PT'] / sum_df['GP']
    sum_df['AS_pergame'] = sum_df['AS'] / sum_df['GP']
    sum_df['RT_pergame'] = sum_df['RT'] / sum_df['GP']
    sum_df['PR_pergame'] = sum_df['PR'] / sum_df['GP']
    sum_df['ST_pergame'] = sum_df['ST'] / sum_df['GP']

    # Filtra giocatori con almeno 5 partite
    sum_df = sum_df[sum_df['GP'] >= 5].copy()

    # Prepara dati per radar (normalizzati 0-100 dove 100 = max del campionato)
    player_radar_data = {}
    player_raw_data = {}
    for _, row in sum_df.iterrows():
        player_key = f"{row['Giocatore']} ({row['Team']})"
        values = []
        raw_values = {}
        for col, name in RADAR_STATS:
            if col in row.index:
                val = row[col]
                raw_values[name] = round(float(val), 1) if pd.notna(val) else 0
                col_max = sum_df[col].max()
                if col_max > 0:
                    norm = (val / col_max) * 100
                else:
                    norm = 0
                values.append(round(norm, 1))
            else:
                values.append(0)
                raw_values[name] = 0
        player_radar_data[player_key] = values
        player_raw_data[player_key] = raw_values

    players_json = json.dumps(player_radar_data)
    raw_json = json.dumps(player_raw_data)
    categories_json = json.dumps([name for _, name in RADAR_STATS])

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Confronto Radar Giocatori</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Confronta il profilo statistico di due giocatori. Valori normalizzati (0-100) dove 100 = miglior giocatore del campionato.
        </p>
        <div style="margin-bottom: 20px; display: flex; gap: 20px; flex-wrap: wrap;">
            <div>
                <label style="font-weight: 600;">Giocatore 1:</label>
                <select id="player1" onchange="updatePlayerRadar()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd; min-width: 250px;">
                    {''.join(f'<option value="{p}">{p}</option>' for p in sorted(player_radar_data.keys()))}
                </select>
            </div>
            <div>
                <label style="font-weight: 600;">Giocatore 2:</label>
                <select id="player2" onchange="updatePlayerRadar()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd; min-width: 250px;">
                    <option value="">-- Nessuno --</option>
                    {''.join(f'<option value="{p}">{p}</option>' for p in sorted(player_radar_data.keys()))}
                </select>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 350px; gap: 20px; align-items: start;">
            <div id="player-radar-chart"></div>
            <div id="player-comparison-table" style="background: #f9f9f9; border-radius: 8px; padding: 15px;"></div>
        </div>
    </div>

    <script>
        const playerData = {players_json};
        const playerRaw = {raw_json};
        const playerCategories = {categories_json};

        function updatePlayerRadar() {{
            const p1 = document.getElementById('player1').value;
            const p2 = document.getElementById('player2').value;

            const data = [];
            const colors = ['#302B8F', '#00F95B'];

            [p1, p2].forEach((player, i) => {{
                if (player && playerData[player]) {{
                    const vals = [...playerData[player]];
                    const cats = [...playerCategories];
                    vals.push(vals[0]);
                    cats.push(cats[0]);

                    data.push({{
                        type: 'scatterpolar',
                        r: vals,
                        theta: cats,
                        fill: 'toself',
                        fillcolor: colors[i] + '33',
                        line: {{ color: colors[i], width: 2 }},
                        name: player
                    }});
                }}
            }});

            const layout = {{
                polar: {{
                    radialaxis: {{ visible: true, range: [0, 100] }}
                }},
                showlegend: true,
                height: 450,
                margin: {{ t: 30, b: 30 }}
            }};

            Plotly.newPlot('player-radar-chart', data, layout);
            updatePlayerComparisonTable(p1, p2);
        }}

        function updatePlayerComparisonTable(p1, p2) {{
            const tableDiv = document.getElementById('player-comparison-table');

            if (!p2 || !playerRaw[p1] || !playerRaw[p2]) {{
                if (playerRaw[p1]) {{
                    let html = '<h4 style="margin: 0 0 12px 0; color: #302B8F;">Valori per Partita</h4>';
                    html += '<table style="width: 100%; font-size: 14px;">';
                    playerCategories.forEach(cat => {{
                        const val = playerRaw[p1][cat];
                        html += `<tr><td style="padding: 6px 0;">${{cat}}</td><td style="text-align: right; font-weight: 600;">${{val}}</td></tr>`;
                    }});
                    html += '</table>';
                    tableDiv.innerHTML = html;
                }}
                return;
            }}

            let html = '<h4 style="margin: 0 0 12px 0;">Confronto Valori</h4>';
            html += '<table style="width: 100%; font-size: 13px;">';
            html += '<tr style="border-bottom: 1px solid #ddd;"><th style="text-align: left; padding: 6px 0;">Stat</th>';
            html += '<th style="text-align: right; color: #302B8F;">G1</th>';
            html += '<th style="text-align: right; color: #00a63e;">G2</th></tr>';

            playerCategories.forEach(cat => {{
                const v1 = playerRaw[p1][cat] || 0;
                const v2 = playerRaw[p2][cat] || 0;
                const better1 = v1 > v2;
                const c1 = better1 ? '#22c55e' : (v1 < v2 ? '#ef4444' : '#666');
                const c2 = !better1 ? '#22c55e' : (v1 > v2 ? '#ef4444' : '#666');

                html += `<tr><td style="padding: 6px 0;">${{cat}}</td>`;
                html += `<td style="text-align: right; color: ${{c1}}; font-weight: 600;">${{v1}}</td>`;
                html += `<td style="text-align: right; color: ${{c2}}; font-weight: 600;">${{v2}}</td></tr>`;
            }});
            html += '</table>';
            tableDiv.innerHTML = html;
        }}

        updatePlayerRadar();
    </script>
    '''

    return {
        'content': content,
        'title': f'Radar Giocatori - {camp_name}',
        'page_title': 'Radar Confronto',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Giocatori / Radar'
    }


def generate_giocatori_consistenza(campionato_filter, camp_name):
    """Genera contenuto pagina Consistenza giocatori."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Consistenza', 'page_title': 'Consistenza'}

    consistency_df = compute_consistency_metrics(overall_df, min_games=5)
    if consistency_df is None or len(consistency_df) == 0:
        return {'content': '<p>Dati insufficienti.</p>', 'title': 'Consistenza', 'page_title': 'Consistenza'}

    # Classifica per consistenza nei punti
    if 'PT_cv' not in consistency_df.columns:
        return {'content': '<p>Dati insufficienti.</p>', 'title': 'Consistenza', 'page_title': 'Consistenza'}

    # Filtra chi ha almeno 8 punti di media
    filtered = consistency_df[consistency_df['PT_mean'] >= 8].copy()
    if len(filtered) == 0:
        return {'content': '<p>Dati insufficienti.</p>', 'title': 'Consistenza', 'page_title': 'Consistenza'}

    # Calcola punteggio Affidabilità 0-100 (inverso del CV normalizzato)
    # CV basso = alta affidabilità
    max_cv = filtered['PT_cv'].max()
    min_cv = filtered['PT_cv'].min()
    if max_cv > min_cv:
        filtered['Affidabilita_raw'] = 100 - ((filtered['PT_cv'] - min_cv) / (max_cv - min_cv) * 100)
    else:
        filtered['Affidabilita_raw'] = 50

    # Aggiustamento Bayesiano per sample size: con poche partite il punteggio viene "tirato" verso 50
    # Formula: Aff_adj = 50 + (partite / (partite + k)) × (Aff_raw - 50)
    # k = parametro fisso (più alto = più conservativo)
    k = 10  # Con k=10: 10 partite → 50% credibilità, 20 partite → 67%, 30 → 75%
    if 'Partite' in filtered.columns:
        credibility = filtered['Partite'] / (filtered['Partite'] + k)
        filtered['Affidabilita'] = 50 + (filtered['Affidabilita_raw'] - 50) * credibility
    else:
        filtered['Affidabilita'] = filtered['Affidabilita_raw']

    filtered = filtered.sort_values('Affidabilita', ascending=False)

    # Prepara dati per JavaScript
    players_data = []
    for _, row in filtered.iterrows():
        players_data.append({
            'giocatore': row['Giocatore'],
            'team': row['Team'],
            'media': round(float(row['PT_mean']), 1),
            'affidabilita': round(float(row['Affidabilita']), 0),
            'partite': int(row['Partite']) if 'Partite' in row else 0
        })

    data_json = json.dumps(players_data)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Affidabilità Giocatori</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Il punteggio di <strong>Affidabilità</strong> (0-100) indica quanto un giocatore è costante nelle sue performance.
            <br>Punteggio alto = sai cosa aspettarti. Punteggio basso = performance imprevedibili.
            <br><span style="font-size: 13px;">Il punteggio è aggiustato per il numero di partite: con poche partite il valore viene "tirato" verso 50.</span>
        </p>

        <div style="display: flex; gap: 10px; margin-bottom: 20px;">
            <button id="btn-top" onclick="showView('top')" style="padding: 8px 16px; border: 2px solid #302B8F; border-radius: 6px; cursor: pointer; font-weight: 600; background: #302B8F; color: white;">
                Più Costanti
            </button>
            <button id="btn-bottom" onclick="showView('bottom')" style="padding: 8px 16px; border: 2px solid #302B8F; border-radius: 6px; cursor: pointer; font-weight: 600; background: white; color: #302B8F;">
                Più Variabili
            </button>
        </div>

        <div id="table-container"></div>
    </div>

    <script>
        const playersData = {data_json};
        let currentView = 'top';

        function showView(view) {{
            currentView = view;
            document.getElementById('btn-top').style.background = view === 'top' ? '#302B8F' : 'white';
            document.getElementById('btn-top').style.color = view === 'top' ? 'white' : '#302B8F';
            document.getElementById('btn-bottom').style.background = view === 'bottom' ? '#302B8F' : 'white';
            document.getElementById('btn-bottom').style.color = view === 'bottom' ? 'white' : '#302B8F';
            render();
        }}

        function render() {{
            const data = currentView === 'top' ? playersData.slice(0, 20) : playersData.slice(-20).reverse();

            let html = '<table style="width: 100%; border-collapse: collapse; font-size: 14px;">';
            html += '<thead><tr style="background: #302B8F; color: white;">';
            html += '<th style="padding: 10px; text-align: left;">#</th>';
            html += '<th style="padding: 10px; text-align: left;">Giocatore</th>';
            html += '<th style="padding: 10px; text-align: center;">Media PT</th>';
            html += '<th style="padding: 10px; text-align: center;">Partite</th>';
            html += '<th style="padding: 10px; text-align: center;">Affidabilità</th>';
            html += '</tr></thead><tbody>';

            data.forEach((row, i) => {{
                const bg = i % 2 === 0 ? 'white' : '#f9f9f9';
                const aff = row.affidabilita;
                const barColor = aff >= 70 ? '#22c55e' : aff >= 40 ? '#f59e0b' : '#ef4444';

                html += `<tr style="background: ${{bg}};">`;
                html += `<td style="padding: 10px; font-weight: bold;">${{i + 1}}</td>`;
                html += `<td style="padding: 10px;"><div style="font-weight: 600;">${{row.giocatore}}</div><div style="font-size: 12px; color: #666;">${{row.team}}</div></td>`;
                html += `<td style="padding: 10px; text-align: center; font-weight: 600;">${{row.media}}</td>`;
                html += `<td style="padding: 10px; text-align: center; color: #666;">${{row.partite}}</td>`;
                html += `<td style="padding: 10px; width: 150px;">`;
                html += `<div style="display: flex; align-items: center; gap: 8px;">`;
                html += `<div style="flex: 1; background: #e5e5e5; height: 10px; border-radius: 5px;">`;
                html += `<div style="width: ${{aff}}%; background: ${{barColor}}; height: 100%; border-radius: 5px;"></div>`;
                html += `</div>`;
                html += `<span style="font-weight: 600; width: 30px; text-align: right;">${{aff}}</span>`;
                html += `</div></td>`;
                html += `</tr>`;
            }});

            html += '</tbody></table>';
            document.getElementById('table-container').innerHTML = html;
        }}

        render();
    </script>
    '''

    return {
        'content': content,
        'title': f'Consistenza - {camp_name}',
        'page_title': 'Affidabilità',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Giocatori / Affidabilità'
    }


def generate_giocatori_simili(campionato_filter, camp_name):
    """Genera contenuto pagina Giocatori Simili."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Giocatori Simili', 'page_title': 'Giocatori Simili'}

    try:
        similarity_results = compute_player_similarity(sum_df, n_neighbors=5, min_minutes=100)
        if not similarity_results or len(similarity_results) == 0:
            return {'content': '<p>Dati insufficienti.</p>', 'title': 'Giocatori Simili', 'page_title': 'Giocatori Simili'}
    except Exception as e:
        return {'content': f'<p>Errore: {e}</p>', 'title': 'Giocatori Simili', 'page_title': 'Giocatori Simili'}

    # Prepara dati per JavaScript
    similarity_dict = {}
    for player_data in similarity_results:
        key = f"{player_data['Giocatore']} ({player_data['Team']})"
        profile = player_data.get('profile', {})
        similar = []
        for sim in player_data.get('similar', []):
            similar.append({
                'name': sim['name'],
                'team': sim['team'],
                'similarity': round(sim['similarity'] * 100, 0),
                'profile': sim.get('profile', {})
            })
        similarity_dict[key] = {
            'similar': similar,
            'profile': profile
        }

    similarity_json = json.dumps(similarity_dict)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Trova Giocatori Simili</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Seleziona un giocatore per vedere chi ha un profilo statistico simile.
        </p>

        <div style="margin-bottom: 20px;">
            <label style="font-weight: 600;">Giocatore:</label>
            <select id="player-select" onchange="showSimilar()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd; min-width: 300px;">
                {''.join(f'<option value="{p}">{p}</option>' for p in sorted(similarity_dict.keys()))}
            </select>
        </div>

        <div id="similar-content"></div>
    </div>

    <script>
        const similarityData = {similarity_json};

        function profileBar(label, pct) {{
            const color = pct >= 80 ? '#22c55e' : pct >= 50 ? '#302B8F' : '#94a3b8';
            return `<div style="display: flex; align-items: center; gap: 8px; margin: 4px 0;">
                <span style="width: 30px; font-size: 12px; color: #666;">${{label}}</span>
                <div style="flex: 1; background: #e5e5e5; height: 8px; border-radius: 4px;">
                    <div style="width: ${{pct}}%; background: ${{color}}; height: 100%; border-radius: 4px;"></div>
                </div>
                <span style="width: 30px; font-size: 12px; text-align: right;">${{pct}}</span>
            </div>`;
        }}

        function showSimilar() {{
            const player = document.getElementById('player-select').value;
            const contentDiv = document.getElementById('similar-content');

            if (!similarityData[player]) {{
                contentDiv.innerHTML = '<p>Dati non disponibili.</p>';
                return;
            }}

            const data = similarityData[player];
            const profile = data.profile || {{}};

            let html = '<div style="margin-bottom: 20px; background: #f9f9f9; padding: 15px; border-radius: 8px;">';
            html += '<strong style="display: block; margin-bottom: 10px;">Profilo (percentile rispetto al campionato):</strong>';
            ['PT', 'AS', 'RT', 'PR', 'ST'].forEach(stat => {{
                html += profileBar(stat, profile[stat] || 50);
            }});
            html += '</div>';

            html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">';

            data.similar.forEach((sim, i) => {{
                const simProfile = sim.profile || {{}};
                html += `<div style="background: white; border: 1px solid #e5e5e5; border-radius: 8px; padding: 15px;">`;
                html += `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">`;
                html += `<div><div style="font-weight: 600;">${{sim.name}}</div><div style="font-size: 13px; color: #666;">${{sim.team}}</div></div>`;
                html += `<div style="background: #302B8F; color: white; padding: 4px 12px; border-radius: 20px; font-weight: 600;">${{sim.similarity}}%</div>`;
                html += `</div>`;
                ['PT', 'AS', 'RT', 'PR', 'ST'].forEach(stat => {{
                    html += profileBar(stat, simProfile[stat] || 50);
                }});
                html += `</div>`;
            }});

            html += '</div>';
            contentDiv.innerHTML = html;
        }}

        showSimilar();
    </script>
    '''

    return {
        'content': content,
        'title': f'Giocatori Simili - {camp_name}',
        'page_title': 'Giocatori Simili',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Giocatori / Simili'
    }


def generate_giocatori_forma(campionato_filter, camp_name):
    """Genera contenuto pagina Forma Recente - Chi è Hot/Cold."""
    import numpy as np
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Forma Recente', 'page_title': 'Forma Recente'}

    # Calcola medie stagionali e ultime 5 partite per ogni giocatore
    players_form = []

    for (player, team), group in overall_df.groupby(['Giocatore', 'Team']):
        if len(group) < 6:  # Almeno 6 partite per avere confronto significativo
            continue

        # Ordina per data/ordine cronologico (assumendo che l'ordine nel df sia cronologico)
        sorted_games = group.reset_index(drop=True)

        # Ultime 5 partite
        last_5 = sorted_games.tail(5)
        # Tutte le precedenti
        season = sorted_games

        # Calcola medie
        season_pt = season['PT'].mean()
        last5_pt = last_5['PT'].mean()
        season_as = season['AS'].mean()
        last5_as = last_5['AS'].mean()
        season_rt = season['RT'].mean()
        last5_rt = last_5['RT'].mean()

        # Differenze percentuali
        pt_diff = ((last5_pt - season_pt) / season_pt * 100) if season_pt > 0 else 0
        as_diff = ((last5_as - season_as) / season_as * 100) if season_as > 0 else 0
        rt_diff = ((last5_rt - season_rt) / season_rt * 100) if season_rt > 0 else 0

        # Score complessivo (media pesata delle differenze)
        form_score = (pt_diff * 0.5 + as_diff * 0.3 + rt_diff * 0.2)

        players_form.append({
            'name': player,
            'team': team,
            'gp': len(group),
            'season_pt': round(season_pt, 1),
            'last5_pt': round(last5_pt, 1),
            'pt_diff': round(pt_diff, 1),
            'season_as': round(season_as, 1),
            'last5_as': round(last5_as, 1),
            'as_diff': round(as_diff, 1),
            'season_rt': round(season_rt, 1),
            'last5_rt': round(last5_rt, 1),
            'rt_diff': round(rt_diff, 1),
            'form_score': round(form_score, 1)
        })

    if not players_form:
        return {'content': '<p>Dati insufficienti.</p>', 'title': 'Forma Recente', 'page_title': 'Forma Recente'}

    # Ordina per form_score
    hot_players = sorted(players_form, key=lambda x: x['form_score'], reverse=True)[:15]
    cold_players = sorted(players_form, key=lambda x: x['form_score'])[:15]

    hot_json = json.dumps(hot_players)
    cold_json = json.dumps(cold_players)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Forma Recente - Chi è Hot/Cold</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Confronto tra le ultime 5 partite e la media stagionale.
            <span style="color: #22c55e; font-weight: bold;">Valori positivi</span> = giocatore in crescita.
            <span style="color: #ef4444; font-weight: bold;">Valori negativi</span> = giocatore in calo.
        </p>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
            <!-- HOT Players -->
            <div>
                <h3 style="color: #22c55e; display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
                    <span style="font-size: 1.5em;">🔥</span> Giocatori HOT
                </h3>
                <div id="hot-container"></div>
            </div>

            <!-- COLD Players -->
            <div>
                <h3 style="color: #3b82f6; display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
                    <span style="font-size: 1.5em;">❄️</span> Giocatori COLD
                </h3>
                <div id="cold-container"></div>
            </div>
        </div>
    </div>

    <script>
        const hotPlayers = {hot_json};
        const coldPlayers = {cold_json};

        function renderPlayerCard(player, isHot) {{
            const color = isHot ? '#22c55e' : '#3b82f6';
            const arrow = isHot ? '↑' : '↓';

            function diffBadge(val) {{
                const c = val > 0 ? '#22c55e' : val < 0 ? '#ef4444' : '#666';
                const prefix = val > 0 ? '+' : '';
                return `<span style="color: ${{c}}; font-weight: 600;">${{prefix}}${{val}}%</span>`;
            }}

            return `
                <div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 4px solid ${{color}};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <div>
                            <div style="font-weight: 600;">${{player.name}}</div>
                            <div style="font-size: 12px; color: #666;">${{player.team}} | ${{player.gp}} partite</div>
                        </div>
                        <div style="background: ${{color}}; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold;">
                            ${{player.form_score > 0 ? '+' : ''}}${{player.form_score}}%
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; font-size: 13px;">
                        <div style="text-align: center; background: #f9f9f9; padding: 8px; border-radius: 6px;">
                            <div style="color: #666; font-size: 11px;">Punti</div>
                            <div><b>${{player.last5_pt}}</b> vs ${{player.season_pt}}</div>
                            ${{diffBadge(player.pt_diff)}}
                        </div>
                        <div style="text-align: center; background: #f9f9f9; padding: 8px; border-radius: 6px;">
                            <div style="color: #666; font-size: 11px;">Assist</div>
                            <div><b>${{player.last5_as}}</b> vs ${{player.season_as}}</div>
                            ${{diffBadge(player.as_diff)}}
                        </div>
                        <div style="text-align: center; background: #f9f9f9; padding: 8px; border-radius: 6px;">
                            <div style="color: #666; font-size: 11px;">Rimbalzi</div>
                            <div><b>${{player.last5_rt}}</b> vs ${{player.season_rt}}</div>
                            ${{diffBadge(player.rt_diff)}}
                        </div>
                    </div>
                </div>
            `;
        }}

        document.getElementById('hot-container').innerHTML = hotPlayers.map(p => renderPlayerCard(p, true)).join('');
        document.getElementById('cold-container').innerHTML = coldPlayers.map(p => renderPlayerCard(p, false)).join('');
    </script>
    '''

    return {
        'content': content,
        'title': f'Forma Recente - {camp_name}',
        'page_title': 'Forma Recente',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Giocatori / Forma'
    }


def generate_giocatori_casa_trasferta(campionato_filter, camp_name):
    """Genera contenuto pagina Casa vs Trasferta."""
    import numpy as np
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Casa vs Trasferta', 'page_title': 'Casa vs Trasferta'}

    # Verifica se abbiamo l'indicatore casa/trasferta
    if 'is_home' not in overall_df.columns:
        content = '''
        <div class="content-section">
            <h2 class="section-title">Casa vs Trasferta</h2>
            <div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <h3 style="color: #b45309; margin: 0 0 10px 0;">⚠️ Dati non disponibili</h3>
                <p style="color: #92400e; margin: 0;">
                    I dati attuali non contengono l'informazione casa/trasferta.<br>
                    Esegui <code>python main.py download</code> per scaricare i dati aggiornati con questa informazione.
                </p>
            </div>
        </div>
        '''
        return {
            'content': content,
            'title': f'Casa vs Trasferta - {camp_name}',
            'page_title': 'Casa vs Trasferta',
            'subtitle': camp_name,
            'breadcrumb': f'{camp_name} / Giocatori / Casa-Trasferta'
        }

    players_split = []

    for (player, team), group in overall_df.groupby(['Giocatore', 'Team']):
        home_games = group[group['is_home'] == True]
        away_games = group[group['is_home'] == False]

        # Almeno 3 partite in casa e 3 in trasferta
        if len(home_games) < 3 or len(away_games) < 3:
            continue

        # Statistiche casa
        home_pt = home_games['PT'].mean()
        home_as = home_games['AS'].mean()
        home_rt = home_games['RT'].mean()

        # Statistiche trasferta
        away_pt = away_games['PT'].mean()
        away_as = away_games['AS'].mean()
        away_rt = away_games['RT'].mean()

        # Differenze
        pt_diff = home_pt - away_pt
        as_diff = home_as - away_as
        rt_diff = home_rt - away_rt

        # Score complessivo
        home_advantage = (pt_diff * 0.5 + as_diff * 0.3 + rt_diff * 0.2)

        players_split.append({
            'name': player,
            'team': team,
            'gp_home': len(home_games),
            'gp_away': len(away_games),
            'home_pt': round(home_pt, 1),
            'away_pt': round(away_pt, 1),
            'pt_diff': round(pt_diff, 1),
            'home_as': round(home_as, 1),
            'away_as': round(away_as, 1),
            'as_diff': round(as_diff, 1),
            'home_rt': round(home_rt, 1),
            'away_rt': round(away_rt, 1),
            'rt_diff': round(rt_diff, 1),
            'home_advantage': round(home_advantage, 1)
        })

    if not players_split:
        return {'content': '<p>Dati insufficienti.</p>', 'title': 'Casa vs Trasferta', 'page_title': 'Casa vs Trasferta'}

    # Ordina per home advantage
    home_warriors = sorted(players_split, key=lambda x: x['home_advantage'], reverse=True)[:15]
    road_warriors = sorted(players_split, key=lambda x: x['home_advantage'])[:15]

    home_json = json.dumps(home_warriors)
    road_json = json.dumps(road_warriors)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Casa vs Trasferta</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Differenza di rendimento tra partite in casa e in trasferta.
            <span style="color: #3b82f6; font-weight: bold;">Blu</span> = meglio in casa,
            <span style="color: #f97316; font-weight: bold;">Arancione</span> = meglio in trasferta.
        </p>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
            <!-- Home Warriors -->
            <div>
                <h3 style="color: #3b82f6; display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
                    <span style="font-size: 1.5em;">🏠</span> Meglio in Casa
                </h3>
                <div id="home-container"></div>
            </div>

            <!-- Road Warriors -->
            <div>
                <h3 style="color: #f97316; display: flex; align-items: center; gap: 8px; margin-bottom: 15px;">
                    <span style="font-size: 1.5em;">🚗</span> Meglio in Trasferta
                </h3>
                <div id="road-container"></div>
            </div>
        </div>
    </div>

    <script>
        const homeWarriors = {home_json};
        const roadWarriors = {road_json};

        function renderSplitCard(player, isHome) {{
            const color = isHome ? '#3b82f6' : '#f97316';

            function diffBadge(val, reverse = false) {{
                const isGood = reverse ? val < 0 : val > 0;
                const c = val === 0 ? '#666' : (isGood ? '#22c55e' : '#ef4444');
                const prefix = val > 0 ? '+' : '';
                return `<span style="color: ${{c}}; font-weight: 600;">${{prefix}}${{val}}</span>`;
            }}

            return `
                <div style="background: white; border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 4px solid ${{color}};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <div>
                            <div style="font-weight: 600;">${{player.name}}</div>
                            <div style="font-size: 12px; color: #666;">${{player.team}} | 🏠 ${{player.gp_home}} / 🚗 ${{player.gp_away}}</div>
                        </div>
                        <div style="background: ${{color}}; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold;">
                            ${{player.home_advantage > 0 ? '+' : ''}}${{player.home_advantage}}
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; font-size: 13px;">
                        <div style="text-align: center; background: #f9f9f9; padding: 8px; border-radius: 6px;">
                            <div style="color: #666; font-size: 11px;">Punti</div>
                            <div><span style="color: #3b82f6;">${{player.home_pt}}</span> / <span style="color: #f97316;">${{player.away_pt}}</span></div>
                            ${{diffBadge(player.pt_diff, !isHome)}}
                        </div>
                        <div style="text-align: center; background: #f9f9f9; padding: 8px; border-radius: 6px;">
                            <div style="color: #666; font-size: 11px;">Assist</div>
                            <div><span style="color: #3b82f6;">${{player.home_as}}</span> / <span style="color: #f97316;">${{player.away_as}}</span></div>
                            ${{diffBadge(player.as_diff, !isHome)}}
                        </div>
                        <div style="text-align: center; background: #f9f9f9; padding: 8px; border-radius: 6px;">
                            <div style="color: #666; font-size: 11px;">Rimbalzi</div>
                            <div><span style="color: #3b82f6;">${{player.home_rt}}</span> / <span style="color: #f97316;">${{player.away_rt}}</span></div>
                            ${{diffBadge(player.rt_diff, !isHome)}}
                        </div>
                    </div>
                </div>
            `;
        }}

        document.getElementById('home-container').innerHTML = homeWarriors.map(p => renderSplitCard(p, true)).join('');
        document.getElementById('road-container').innerHTML = roadWarriors.map(p => renderSplitCard(p, false)).join('');
    </script>
    '''

    return {
        'content': content,
        'title': f'Casa vs Trasferta - {camp_name}',
        'page_title': 'Casa vs Trasferta',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Giocatori / Casa-Trasferta'
    }


def generate_giocatori_distribuzione_tiri(campionato_filter, camp_name):
    """Genera contenuto pagina Distribuzione Tiri - scatterplot frequenza vs efficienza."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Distribuzione Tiri', 'page_title': 'Distribuzione Tiri'}

    # Calcola GP
    gp = overall_df.groupby(['Giocatore', 'Team']).size().reset_index(name='GP')
    sum_df = sum_df.merge(gp, on=['Giocatore', 'Team'], how='left')

    # Filtra giocatori con almeno 5 partite
    sum_df_filtered = sum_df[sum_df['GP'] >= 5].copy()

    # Parsing tiri made/attempted
    def parse_and_aggregate(df, col):
        """Aggrega made e attempted da colonna tipo '4/7'."""
        results = []
        for idx, group in df.groupby(['Giocatore', 'Team']):
            total_made = 0
            total_att = 0
            for val in group[col]:
                if pd.isna(val) or val == '':
                    continue
                parts = str(val).split('/')
                if len(parts) == 2:
                    try:
                        total_made += int(parts[0])
                        total_att += int(parts[1])
                    except:
                        pass
            results.append({
                'Giocatore': idx[0],
                'Team': idx[1],
                f'{col}_made': total_made,
                f'{col}_att': total_att
            })
        return pd.DataFrame(results)

    # Aggrega per ogni tipo di tiro
    shot_data = sum_df_filtered[['Giocatore', 'Team', 'GP', 'Minutes']].drop_duplicates()

    for col in ['2PT', '3PT', 'TL']:
        if col in overall_df.columns:
            agg = parse_and_aggregate(overall_df, col)
            shot_data = shot_data.merge(agg, on=['Giocatore', 'Team'], how='left')

    # Calcola percentuali e frequenze
    shot_data['Minutes'] = shot_data.apply(
        lambda r: sum_df_filtered[(sum_df_filtered['Giocatore'] == r['Giocatore']) &
                                  (sum_df_filtered['Team'] == r['Team'])]['Minutes'].values[0]
        if len(sum_df_filtered[(sum_df_filtered['Giocatore'] == r['Giocatore']) &
                               (sum_df_filtered['Team'] == r['Team'])]) > 0 else 0, axis=1)

    for col in ['2PT', '3PT', 'TL']:
        att_col = f'{col}_att'
        made_col = f'{col}_made'
        if att_col in shot_data.columns:
            shot_data[f'{col}_pct'] = (shot_data[made_col] / shot_data[att_col] * 100).fillna(0).round(1)
            shot_data[f'{col}_freq'] = (shot_data[att_col] / shot_data['Minutes']).fillna(0).round(3)

    # Prepara dati per ogni tipo di tiro
    shot_charts = {}
    for shot_type, min_att, label in [('3PT', 20, 'Tiri da 3'), ('2PT', 30, 'Tiri da 2'), ('TL', 15, 'Tiri Liberi')]:
        att_col = f'{shot_type}_att'
        pct_col = f'{shot_type}_pct'
        freq_col = f'{shot_type}_freq'
        made_col = f'{shot_type}_made'

        if att_col not in shot_data.columns:
            continue

        df = shot_data[shot_data[att_col] >= min_att].copy()
        if len(df) == 0:
            continue

        df = df.nlargest(40, att_col)

        players = []
        for _, row in df.iterrows():
            players.append({
                'name': row['Giocatore'],
                'team': row['Team'],
                'made': int(row[made_col]),
                'att': int(row[att_col]),
                'pct': float(row[pct_col]),
                'freq': float(row[freq_col]),
                'min': int(row['Minutes'])
            })

        avg_pct = df[pct_col].mean()
        avg_freq = df[freq_col].mean()

        shot_charts[shot_type] = {
            'players': players,
            'avg_pct': round(avg_pct, 1),
            'avg_freq': round(avg_freq, 3),
            'label': label
        }

    data_json = json.dumps(shot_charts)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Distribuzione Tiri</h2>
        <p style="color: #666; margin-bottom: 20px;">
            <strong>Frequenza tiri/min</strong> (asse X) vs <strong>Efficienza %</strong> (asse Y).
            La dimensione dei punti indica il volume totale di tiri.
            <br><strong>In alto a destra</strong> = alta frequenza + alta efficienza (ideale).
        </p>

        <div style="display: flex; gap: 8px; margin-bottom: 20px;">
            <button id="btn-3PT" onclick="showChart('3PT')" style="padding: 10px 20px; border: 2px solid #302B8F; border-radius: 8px; cursor: pointer; font-weight: 600; background: #302B8F; color: white;">Tiri da 3</button>
            <button id="btn-2PT" onclick="showChart('2PT')" style="padding: 10px 20px; border: 2px solid #302B8F; border-radius: 8px; cursor: pointer; font-weight: 600; background: white; color: #302B8F;">Tiri da 2</button>
            <button id="btn-TL" onclick="showChart('TL')" style="padding: 10px 20px; border: 2px solid #302B8F; border-radius: 8px; cursor: pointer; font-weight: 600; background: white; color: #302B8F;">Tiri Liberi</button>
        </div>

        <div id="chart-container" style="height: 500px;"></div>
    </div>

    <script>
        const shotData = {data_json};
        let currentType = '3PT';

        function showChart(type) {{
            currentType = type;
            // Update buttons
            ['3PT', '2PT', 'TL'].forEach(t => {{
                const btn = document.getElementById('btn-' + t);
                if (t === type) {{
                    btn.style.background = '#302B8F';
                    btn.style.color = 'white';
                }} else {{
                    btn.style.background = 'white';
                    btn.style.color = '#302B8F';
                }}
            }});

            renderChart();
        }}

        function renderChart() {{
            const data = shotData[currentType];
            if (!data) {{
                document.getElementById('chart-container').innerHTML = '<p>Dati non disponibili per questo tipo di tiro.</p>';
                return;
            }}

            const players = data.players;

            // Calcola size per marker
            const maxAtt = Math.max(...players.map(p => p.att));
            const minAtt = Math.min(...players.map(p => p.att));
            const sizes = players.map(p => 10 + (p.att - minAtt) / (maxAtt - minAtt + 1) * 25);

            const trace = {{
                type: 'scatter',
                mode: 'markers',
                x: players.map(p => p.freq),
                y: players.map(p => p.pct),
                text: players.map(p => p.name),
                customdata: players.map(p => [p.team, p.made, p.att, p.min]),
                hovertemplate: '<b>%{{text}}</b><br>' +
                    'Team: %{{customdata[0]}}<br>' +
                    'Realizzati: %{{customdata[1]}}/%{{customdata[2]}}<br>' +
                    'Efficienza: %{{y:.1f}}%<br>' +
                    'Frequenza: %{{x:.3f}} tiri/min<br>' +
                    '<extra></extra>',
                marker: {{
                    size: sizes,
                    color: players.map(p => p.pct),
                    colorscale: 'RdYlGn',
                    showscale: true,
                    colorbar: {{ title: 'Eff %' }},
                    line: {{ width: 1, color: 'white' }}
                }}
            }};

            const layout = {{
                height: 500,
                xaxis: {{
                    title: {{ text: data.label + ' per minuto', font: {{ size: 14 }} }},
                    gridcolor: '#e5e5e5',
                    range: [0, 0.5],
                    tickformat: '.2f'
                }},
                yaxis: {{
                    title: {{ text: 'Efficienza (%)', font: {{ size: 14 }} }},
                    gridcolor: '#e5e5e5',
                    range: [0, 100]
                }},
                shapes: [
                    {{ type: 'line', x0: data.avg_freq, x1: data.avg_freq, y0: 0, y1: 100, line: {{ dash: 'dash', color: 'gray', width: 1 }} }},
                    {{ type: 'line', x0: 0, x1: 0.5, y0: data.avg_pct, y1: data.avg_pct, line: {{ dash: 'dash', color: 'gray', width: 1 }} }}
                ],
                annotations: [
                    {{ x: 0.48, y: data.avg_pct + 3, text: 'Media: ' + data.avg_pct + '%', showarrow: false, font: {{ size: 11, color: 'gray' }} }}
                ],
                margin: {{ t: 20, b: 60, l: 70, r: 40 }}
            }};

            Plotly.newPlot('chart-container', [trace], layout, {{ responsive: true }});
        }}

        showChart('3PT');
    </script>
    '''

    return {
        'content': content,
        'title': f'Distribuzione Tiri - {camp_name}',
        'page_title': 'Distribuzione Tiri',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Giocatori / Distribuzione Tiri'
    }


def generate_giocatori_impatto(campionato_filter, camp_name):
    """Genera contenuto pagina Impatto - +/-, rapporti, metriche avanzate."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Impatto', 'page_title': 'Impatto'}

    # Calcola GP
    gp = overall_df.groupby(['Giocatore', 'Team']).size().reset_index(name='GP')
    sum_df = sum_df.merge(gp, on=['Giocatore', 'Team'], how='left')

    # Filtra giocatori con almeno 5 partite e minimo minuti
    sum_df = sum_df[sum_df['GP'] >= 5].copy()
    sum_df = sum_df[sum_df['Minutes'] >= 50].copy()

    if len(sum_df) < 10:
        return {'content': '<p>Dati insufficienti.</p>', 'title': 'Impatto', 'page_title': 'Impatto'}

    # Lista squadre per filtro
    teams = sorted(sum_df['Team'].unique().tolist())

    # Calcola metriche
    # Plus/Minus - calcola correttamente dal totale
    if '+/-' in sum_df.columns:
        sum_df['PM'] = sum_df['+/-']
        sum_df['PM_pg'] = (sum_df['PM'] / sum_df['GP']).round(2)
        # +/- per minuto = totale +/- / totale minuti
        sum_df['PM_pm'] = (sum_df['PM'] / sum_df['Minutes']).round(3)

    # Per l'adjusted, usa la mediana (già calcolata correttamente in median_df)
    if 'pm_permin_adj' in median_df.columns:
        # Rimuovi la colonna errata se esiste (è la somma, non la mediana)
        if 'pm_permin_adj' in sum_df.columns:
            sum_df = sum_df.drop(columns=['pm_permin_adj'])
        median_adj = median_df[['Giocatore', 'Team', 'pm_permin_adj']].copy()
        median_adj = median_adj.rename(columns={'pm_permin_adj': 'PM_adj'})
        sum_df = sum_df.merge(median_adj, on=['Giocatore', 'Team'], how='left')
        sum_df['PM_adj'] = sum_df['PM_adj'].round(3)

    # Rapporto AS/PP (Assist to Turnover)
    if 'AS' in sum_df.columns and 'PP' in sum_df.columns:
        sum_df['AS_TO'] = (sum_df['AS'] / sum_df['PP'].replace(0, 1)).round(2)

    # AS per minuto
    if 'AS' in sum_df.columns:
        sum_df['AS_pm'] = (sum_df['AS'] / sum_df['Minutes']).round(3)

    # RO vs RD
    if 'RO' in sum_df.columns and 'RD' in sum_df.columns:
        sum_df['RO_pct'] = (sum_df['RO'] / sum_df['RT'].replace(0, 1) * 100).round(1)

    # Prepara dati per le varie sezioni
    # 1. Tutti i dati +/- adjusted per tabella e grafico
    pm_data = []
    if 'PM_adj' in sum_df.columns:
        for _, row in sum_df.iterrows():
            pm_data.append({
                'name': row['Giocatore'],
                'team': row['Team'],
                'gp': int(row['GP']),
                'min': int(row['Minutes']),
                'pm': int(row.get('PM', 0)),
                'pm_pg': float(row.get('PM_pg', 0)),
                'pm_pm': float(row.get('PM_pm', 0)),
                'pm_adj': float(row['PM_adj'])
            })

    # 2. AS/TO ratio top
    asto_data = []
    if 'AS_TO' in sum_df.columns:
        min_as = sum_df['AS'].quantile(0.25)  # Almeno 25° percentile di assist
        asto_filter = sum_df[sum_df['AS'] >= min_as].nlargest(30, 'AS_TO')
        for _, row in asto_filter.iterrows():
            asto_data.append({
                'name': row['Giocatore'],
                'team': row['Team'],
                'as': int(row['AS']),
                'pp': int(row['PP']),
                'as_to': float(row['AS_TO']),
                'as_pm': float(row.get('AS_pm', 0))
            })

    # 3. Rimbalzi RO vs RD
    reb_data = []
    if 'RO' in sum_df.columns and 'RD' in sum_df.columns:
        min_rt = sum_df['RT'].quantile(0.5)  # Almeno 50° percentile rimbalzi
        reb_filter = sum_df[sum_df['RT'] >= min_rt].copy()
        for _, row in reb_filter.iterrows():
            reb_data.append({
                'name': row['Giocatore'],
                'team': row['Team'],
                'ro': int(row['RO']),
                'rd': int(row['RD']),
                'rt': int(row['RT']),
                'ro_pct': float(row['RO_pct']),
                'min': int(row['Minutes'])
            })

    data_json = json.dumps({
        'pm': pm_data,
        'asto': asto_data,
        'reb': reb_data,
        'teams': teams
    })

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Impatto Giocatori</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Metriche avanzate per valutare l'impatto dei giocatori sulla squadra.
        </p>

        <div style="display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap;">
            <button id="btn-pmraw" onclick="showSection('pmraw')" class="tab-active" style="padding: 10px 20px; border: 2px solid #302B8F; border-radius: 8px; cursor: pointer; font-weight: 600; background: #302B8F; color: white;">+/- per Minuto</button>
            <button id="btn-pm" onclick="showSection('pm')" style="padding: 10px 20px; border: 2px solid #302B8F; border-radius: 8px; cursor: pointer; font-weight: 600; background: white; color: #302B8F;">+/- Adjusted</button>
            <button id="btn-asto" onclick="showSection('asto')" style="padding: 10px 20px; border: 2px solid #302B8F; border-radius: 8px; cursor: pointer; font-weight: 600; background: white; color: #302B8F;">AS/TO Ratio</button>
            <button id="btn-reb" onclick="showSection('reb')" style="padding: 10px 20px; border: 2px solid #302B8F; border-radius: 8px; cursor: pointer; font-weight: 600; background: white; color: #302B8F;">RO vs RD</button>
        </div>

        <div id="content-container"></div>
    </div>

    <script>
        const impactData = {data_json};
        let currentSection = 'pmraw';
        let selectedTeam = 'all';

        function showSection(section) {{
            currentSection = section;
            ['pmraw', 'pm', 'asto', 'reb'].forEach(s => {{
                const btn = document.getElementById('btn-' + s);
                if (s === section) {{
                    btn.style.background = '#302B8F';
                    btn.style.color = 'white';
                }} else {{
                    btn.style.background = 'white';
                    btn.style.color = '#302B8F';
                }}
            }});
            renderSection();
        }}

        function renderSection() {{
            const container = document.getElementById('content-container');

            if (currentSection === 'pmraw') {{
                renderPMRaw(container);
            }} else if (currentSection === 'pm') {{
                renderPM(container);
            }} else if (currentSection === 'asto') {{
                renderASTO(container);
            }} else if (currentSection === 'reb') {{
                renderReb(container);
            }}
        }}

        function renderPMRaw(container) {{
            let data = impactData.pm;
            if (!data || data.length === 0) {{
                container.innerHTML = '<p>Dati non disponibili.</p>';
                return;
            }}

            // Ordina per pm_pm (raw) decrescente
            data = [...data].sort((a, b) => b.pm_pm - a.pm_pm);

            // Filtra per squadra se selezionata
            const filteredData = selectedTeam === 'all' ? data : data.filter(p => p.team === selectedTeam);

            // Dividi in positivi e negativi
            const positive = filteredData.filter(p => p.pm_pm > 0).slice(0, 15);
            const negative = [...filteredData].sort((a, b) => a.pm_pm - b.pm_pm).filter(p => p.pm_pm < 0).slice(0, 15);

            let html = `
                <!-- Spiegazione -->
                <div style="background: linear-gradient(135deg, #f0fff4 0%, #e8fff0 100%); border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 4px solid #22c55e;">
                    <h3 style="margin: 0 0 12px 0; color: #166534; font-size: 16px;">📊 +/- per Minuto (Raw)</h3>
                    <div style="color: #444; font-size: 14px; line-height: 1.6;">
                        <p style="margin: 0 0 10px 0;">
                            Il <strong>+/- (Plus/Minus)</strong> misura la differenza punti quando un giocatore è in campo.
                            Se la squadra segna 50 punti e ne subisce 45 mentre lui gioca → <strong>+/- = +5</strong>.
                        </p>
                        <p style="margin: 0 0 10px 0;">
                            Dividendo per i minuti giocati otteniamo un valore comparabile tra giocatori con minutaggi diversi.
                        </p>
                        <div style="background: white; border-radius: 8px; padding: 12px; margin-top: 12px;">
                            <strong style="color: #166534;">Formula:</strong><br>
                            <code style="font-size: 13px; color: #666;">+/- per min = Plus/Minus totale / Minuti giocati</code><br>
                            <span style="font-size: 12px; color: #888;">Valori tipici: da -0.5 a +0.5</span>
                        </div>
                    </div>
                </div>

                <!-- Filtro squadra -->
                <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 12px;">
                    <label style="font-weight: 600; color: #333;">Filtra per squadra:</label>
                    <select id="team-filter-pmraw" onchange="filterByTeam(this.value)" style="padding: 8px 16px; border: 2px solid #e5e5e5; border-radius: 8px; font-size: 14px; min-width: 200px;">
                        <option value="all">Tutte le squadre</option>
                        ${{impactData.teams.map(t => `<option value="${{t}}" ${{selectedTeam === t ? 'selected' : ''}}>${{t}}</option>`).join('')}}
                    </select>
                </div>

                <!-- Top e Flop -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 30px;">
                    <div>
                        <h3 style="color: #22c55e; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 24px;">🔥</span> Top +/- per Minuto
                        </h3>
                        ${{positive.length === 0 ? '<p style="color: #666;">Nessun giocatore con +/- positivo.</p>' : positive.map((p, i) => `
                            <div style="display: flex; align-items: center; gap: 10px; padding: 12px; background: ${{i % 2 === 0 ? 'white' : '#f9fdf9'}}; border-radius: 8px; margin-bottom: 6px; border-left: 4px solid #22c55e;">
                                <span style="width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: #22c55e; color: white; border-radius: 50%; font-weight: bold; font-size: 12px;">${{i + 1}}</span>
                                <div style="flex: 1;">
                                    <div style="font-weight: 600;">${{p.name}}</div>
                                    <div style="font-size: 12px; color: #666;">${{p.team}} · ${{p.gp}} partite · ${{p.min}} min</div>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-size: 20px; font-weight: bold; color: #22c55e;">+${{p.pm_pm.toFixed(2)}}</div>
                                    <div style="font-size: 11px; color: #666;">+/- totale: ${{p.pm > 0 ? '+' : ''}}${{p.pm}}</div>
                                </div>
                            </div>
                        `).join('')}}
                    </div>
                    <div>
                        <h3 style="color: #ef4444; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 24px;">❄️</span> Peggiori +/- per Minuto
                        </h3>
                        ${{negative.length === 0 ? '<p style="color: #666;">Nessun giocatore con +/- negativo.</p>' : negative.map((p, i) => `
                            <div style="display: flex; align-items: center; gap: 10px; padding: 12px; background: ${{i % 2 === 0 ? 'white' : '#fdf9f9'}}; border-radius: 8px; margin-bottom: 6px; border-left: 4px solid #ef4444;">
                                <span style="width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: #ef4444; color: white; border-radius: 50%; font-weight: bold; font-size: 12px;">${{i + 1}}</span>
                                <div style="flex: 1;">
                                    <div style="font-weight: 600;">${{p.name}}</div>
                                    <div style="font-size: 12px; color: #666;">${{p.team}} · ${{p.gp}} partite · ${{p.min}} min</div>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-size: 20px; font-weight: bold; color: #ef4444;">${{p.pm_pm.toFixed(2)}}</div>
                                    <div style="font-size: 11px; color: #666;">+/- totale: ${{p.pm > 0 ? '+' : ''}}${{p.pm}}</div>
                                </div>
                            </div>
                        `).join('')}}
                    </div>
                </div>
            `;
            container.innerHTML = html;
        }}

        function renderPM(container) {{
            let data = impactData.pm;
            if (!data || data.length === 0) {{
                container.innerHTML = '<p>Dati non disponibili.</p>';
                return;
            }}

            // Ordina per pm_adj decrescente
            data = [...data].sort((a, b) => b.pm_adj - a.pm_adj);

            // Filtra per squadra se selezionata
            const filteredData = selectedTeam === 'all' ? data : data.filter(p => p.team === selectedTeam);

            // Dividi in positivi e negativi
            const positive = filteredData.filter(p => p.pm_adj > 0).slice(0, 15);
            const negative = [...filteredData].sort((a, b) => a.pm_adj - b.pm_adj).filter(p => p.pm_adj < 0).slice(0, 15);

            let html = `
                <!-- Spiegazione dettagliata -->
                <div style="background: linear-gradient(135deg, #f0f4ff 0%, #e8f0ff 100%); border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 4px solid #302B8F;">
                    <h3 style="margin: 0 0 12px 0; color: #302B8F; font-size: 16px;">📊 Come si calcola il +/- Adjusted?</h3>
                    <div style="color: #444; font-size: 14px; line-height: 1.6;">
                        <p style="margin: 0 0 10px 0;">
                            Il <strong>+/- Adjusted</strong> corregge il +/- per minuto tenendo conto del <em>risultato della partita</em>.
                        </p>
                        <p style="margin: 0 0 10px 0;">
                            <strong>Problema del +/- normale:</strong> se la squadra vince di 20, tutti i giocatori avranno +/- positivo.
                            Ma chi ha contribuito <em>più</em> della media della squadra e chi <em>meno</em>?
                        </p>
                        <div style="background: white; border-radius: 8px; padding: 12px; margin-top: 12px;">
                            <strong style="color: #302B8F;">Formula:</strong><br>
                            <code style="font-size: 13px; color: #666;">+/- Adj = (+/- per minuto) - (Gap squadra per minuto)</code><br>
                            <span style="font-size: 12px; color: #888;">Valori tipici: da -0.3 (peggio della squadra) a +0.3 (meglio della squadra)</span>
                        </div>
                    </div>
                </div>

                <!-- Filtro squadra -->
                <div style="margin-bottom: 20px; display: flex; align-items: center; gap: 12px;">
                    <label style="font-weight: 600; color: #333;">Filtra per squadra:</label>
                    <select id="team-filter-pm" onchange="filterByTeam(this.value)" style="padding: 8px 16px; border: 2px solid #e5e5e5; border-radius: 8px; font-size: 14px; min-width: 200px;">
                        <option value="all">Tutte le squadre</option>
                        ${{impactData.teams.map(t => `<option value="${{t}}" ${{selectedTeam === t ? 'selected' : ''}}>${{t}}</option>`).join('')}}
                    </select>
                </div>

                <!-- Top e Flop -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 30px;">
                    <div>
                        <h3 style="color: #22c55e; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 24px;">🔥</span> Top Impatto Positivo
                        </h3>
                        ${{positive.length === 0 ? '<p style="color: #666;">Nessun giocatore con impatto positivo per questa selezione.</p>' : positive.map((p, i) => `
                            <div style="display: flex; align-items: center; gap: 10px; padding: 12px; background: ${{i % 2 === 0 ? 'white' : '#f9fdf9'}}; border-radius: 8px; margin-bottom: 6px; border-left: 4px solid #22c55e;">
                                <span style="width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: #22c55e; color: white; border-radius: 50%; font-weight: bold; font-size: 12px;">${{i + 1}}</span>
                                <div style="flex: 1;">
                                    <div style="font-weight: 600;">${{p.name}}</div>
                                    <div style="font-size: 12px; color: #666;">${{p.team}} · ${{p.gp}} partite · ${{p.min}} min</div>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-size: 20px; font-weight: bold; color: #22c55e;">+${{p.pm_adj.toFixed(2)}}</div>
                                    <div style="font-size: 11px; color: #666;">+/- totale: ${{p.pm > 0 ? '+' : ''}}${{p.pm}}</div>
                                </div>
                            </div>
                        `).join('')}}
                    </div>
                    <div>
                        <h3 style="color: #ef4444; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 24px;">❄️</span> Top Impatto Negativo
                        </h3>
                        ${{negative.length === 0 ? '<p style="color: #666;">Nessun giocatore con impatto negativo per questa selezione.</p>' : negative.map((p, i) => `
                            <div style="display: flex; align-items: center; gap: 10px; padding: 12px; background: ${{i % 2 === 0 ? 'white' : '#fdf9f9'}}; border-radius: 8px; margin-bottom: 6px; border-left: 4px solid #ef4444;">
                                <span style="width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: #ef4444; color: white; border-radius: 50%; font-weight: bold; font-size: 12px;">${{i + 1}}</span>
                                <div style="flex: 1;">
                                    <div style="font-weight: 600;">${{p.name}}</div>
                                    <div style="font-size: 12px; color: #666;">${{p.team}} · ${{p.gp}} partite · ${{p.min}} min</div>
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-size: 20px; font-weight: bold; color: #ef4444;">${{p.pm_adj.toFixed(2)}}</div>
                                    <div style="font-size: 11px; color: #666;">+/- totale: ${{p.pm > 0 ? '+' : ''}}${{p.pm}}</div>
                                </div>
                            </div>
                        `).join('')}}
                    </div>
                </div>

                <!-- Scatterplot -->
                <div style="background: white; border-radius: 12px; padding: 20px; border: 1px solid #e5e5e5;">
                    <h3 style="margin: 0 0 8px 0; color: #333;">Mappa Impatto: Minuti vs +/- Adjusted</h3>
                    <p style="margin: 0 0 15px 0; color: #666; font-size: 13px;">
                        🟢 Verde = impatto positivo | 🟡 Giallo = neutro | 🔴 Rosso = impatto negativo<br>
                        <strong>In alto a destra</strong> = tanti minuti + grande impatto positivo (giocatori chiave)
                    </p>
                    <div id="pm-scatter" style="height: 500px;"></div>
                </div>
            `;
            container.innerHTML = html;

            // Crea lo scatterplot
            renderPMScatter(filteredData);
        }}

        function filterByTeam(team) {{
            selectedTeam = team;
            renderSection();
        }}

        function renderPMScatter(data) {{
            if (!data || data.length === 0) return;

            // Calcola min/max per colorscale simmetrica
            const pmValues = data.map(p => p.pm_adj);
            const maxAbs = Math.max(Math.abs(Math.min(...pmValues)), Math.abs(Math.max(...pmValues)));

            const trace = {{
                type: 'scatter',
                mode: 'markers',
                x: data.map(p => p.min),
                y: data.map(p => p.pm_adj),
                text: data.map(p => p.name),
                marker: {{
                    size: 12,
                    color: data.map(p => p.pm_adj),
                    colorscale: [
                        [0, '#ef4444'],      // Rosso (negativo)
                        [0.35, '#fbbf24'],   // Giallo-arancio
                        [0.5, '#fde047'],    // Giallo (neutro)
                        [0.65, '#a3e635'],   // Verde chiaro
                        [1, '#22c55e']       // Verde (positivo)
                    ],
                    cmin: -maxAbs,
                    cmax: maxAbs,
                    showscale: true,
                    colorbar: {{
                        title: {{ text: '+/- Adj', font: {{ size: 12 }} }},
                        tickformat: '.3f'
                    }},
                    line: {{ width: 1, color: 'white' }}
                }},
                customdata: data.map(p => [p.team, p.gp, p.pm]),
                hovertemplate: '<b>%{{text}}</b><br>%{{customdata[0]}}<br>Minuti: %{{x}}<br>+/- Adj: %{{y:.4f}}<br>+/- Tot: %{{customdata[2]}}<br>Partite: %{{customdata[1]}}<extra></extra>'
            }};

            const layout = {{
                height: 500,
                xaxis: {{
                    title: {{ text: 'Minuti Totali Giocati', font: {{ size: 14 }} }},
                    gridcolor: '#e5e5e5',
                    zeroline: false
                }},
                yaxis: {{
                    title: {{ text: '+/- Adjusted (per minuto)', font: {{ size: 14 }} }},
                    gridcolor: '#e5e5e5',
                    zeroline: true,
                    zerolinecolor: '#999',
                    zerolinewidth: 2
                }},
                shapes: [
                    {{
                        type: 'line',
                        x0: 0,
                        x1: Math.max(...data.map(p => p.min)) * 1.05,
                        y0: 0,
                        y1: 0,
                        line: {{ dash: 'dash', color: '#666', width: 2 }}
                    }}
                ],
                margin: {{ t: 20, b: 60, l: 70, r: 20 }},
                plot_bgcolor: '#fafafa',
                paper_bgcolor: 'white'
            }};

            Plotly.newPlot('pm-scatter', [trace], layout, {{ responsive: true }});
        }}

        function renderASTO(container) {{
            const data = impactData.asto;
            if (!data || data.length === 0) {{
                container.innerHTML = '<p>Dati non disponibili.</p>';
                return;
            }}

            let html = `
                <div style="background: linear-gradient(135deg, #f0f4ff 0%, #e8f0ff 100%); border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 4px solid #302B8F;">
                    <h3 style="margin: 0 0 12px 0; color: #302B8F; font-size: 16px;">📊 Assist to Turnover Ratio (AS/TO)</h3>
                    <p style="margin: 0; color: #444; font-size: 14px; line-height: 1.6;">
                        Rapporto tra assist effettuati e palle perse. Un valore alto indica un giocatore
                        efficiente nella gestione del pallone, che crea più occasioni di quante ne sprechi.
                        <br><strong>Valori tipici:</strong> &lt;1 = negativo, 1-2 = buono, &gt;2 = eccellente
                    </p>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px;">
                    ${{data.map((p, i) => `
                        <div style="display: flex; align-items: center; gap: 12px; padding: 14px; background: white; border: 1px solid #e5e5e5; border-radius: 10px;">
                            <span style="width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; background: #302B8F; color: white; border-radius: 50%; font-weight: bold; font-size: 13px;">${{i + 1}}</span>
                            <div style="flex: 1;">
                                <div style="font-weight: 600;">${{p.name}}</div>
                                <div style="font-size: 12px; color: #666;">${{p.team}}</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 22px; font-weight: bold; color: ${{p.as_to >= 2 ? '#22c55e' : p.as_to >= 1 ? '#302B8F' : '#ef4444'}};">${{p.as_to.toFixed(2)}}</div>
                                <div style="font-size: 11px; color: #666;">${{p.as}} AS / ${{p.pp}} PP</div>
                                <div style="font-size: 10px; color: #999;">${{p.as_pm.toFixed(3)}} as/min</div>
                            </div>
                        </div>
                    `).join('')}}
                </div>
            `;
            container.innerHTML = html;
        }}

        function renderReb(container) {{
            const data = impactData.reb;
            if (!data || data.length === 0) {{
                container.innerHTML = '<p>Dati non disponibili.</p>';
                return;
            }}

            // Ordina per RO_pct (rimbalzisti offensivi)
            const sorted = [...data].sort((a, b) => b.ro_pct - a.ro_pct).slice(0, 30);

            let html = `
                <div style="background: linear-gradient(135deg, #f0f4ff 0%, #e8f0ff 100%); border-radius: 12px; padding: 20px; margin-bottom: 25px; border-left: 4px solid #302B8F;">
                    <h3 style="margin: 0 0 12px 0; color: #302B8F; font-size: 16px;">📊 Rimbalzi Offensivi vs Difensivi</h3>
                    <p style="margin: 0; color: #444; font-size: 14px; line-height: 1.6;">
                        Distribuzione tra rimbalzi offensivi (RO) e difensivi (RD).
                        Una % alta di RO indica un rimbalzista aggressivo che genera seconde opportunità.
                        <br><strong>% RO tipica:</strong> 20-30% per lunghi, 10-20% per esterni
                    </p>
                </div>
                <div id="reb-chart" style="height: 450px; margin-bottom: 20px;"></div>
                <h4 style="margin: 20px 0 12px 0;">Top Rimbalzisti Offensivi (% RO)</h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px;">
                    ${{sorted.slice(0, 20).map((p, i) => `
                        <div style="display: flex; align-items: center; gap: 8px; padding: 10px; background: ${{i % 2 === 0 ? 'white' : '#f9f9f9'}}; border-radius: 8px; border-left: 3px solid #f97316;">
                            <div style="flex: 1;">
                                <div style="font-weight: 600; font-size: 13px;">${{p.name}}</div>
                                <div style="font-size: 11px; color: #666;">${{p.team}}</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 16px; font-weight: bold;">${{p.ro}}/${{p.rd}}</div>
                                <div style="font-size: 12px; color: #f97316; font-weight: 600;">${{p.ro_pct}}% off</div>
                            </div>
                        </div>
                    `).join('')}}
                </div>
            `;
            container.innerHTML = html;

            // Crea scatter RO vs RD
            const trace = {{
                type: 'scatter',
                mode: 'markers+text',
                x: data.map(p => p.rd),
                y: data.map(p => p.ro),
                text: data.map(p => p.name.split(' ').pop()),
                textposition: 'top center',
                textfont: {{ size: 9 }},
                marker: {{
                    size: data.map(p => 8 + p.rt / 10),
                    color: data.map(p => p.ro_pct),
                    colorscale: 'YlOrRd',
                    showscale: true,
                    colorbar: {{ title: 'RO%' }}
                }},
                customdata: data.map(p => [p.name, p.team, p.rt]),
                hovertemplate: '<b>%{{customdata[0]}}</b><br>%{{customdata[1]}}<br>RD: %{{x}}, RO: %{{y}}<br>Tot: %{{customdata[2]}}<extra></extra>'
            }};

            const layout = {{
                height: 450,
                xaxis: {{ title: {{ text: 'Rimbalzi Difensivi', font: {{ size: 14 }} }}, gridcolor: '#e5e5e5' }},
                yaxis: {{ title: {{ text: 'Rimbalzi Offensivi', font: {{ size: 14 }} }}, gridcolor: '#e5e5e5' }},
                margin: {{ t: 20, b: 60, l: 60, r: 40 }},
                plot_bgcolor: '#fafafa'
            }};

            Plotly.newPlot('reb-chart', [trace], layout, {{ responsive: true }});
        }}

        showSection('pm');
    </script>
    '''

    return {
        'content': content,
        'title': f'Impatto Giocatori - {camp_name}',
        'page_title': 'Impatto',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Giocatori / Impatto'
    }


# ============ PAGINE ANALISI ============

def generate_analisi_clustering(campionato_filter, camp_name):
    """Genera contenuto pagina Clustering & Tipologie."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Clustering', 'page_title': 'Clustering'}

    from scipy import stats
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np

    # Calcola GP (games played)
    gp = overall_df.groupby(['Giocatore', 'Team']).size().reset_index(name='GP')
    sum_df = sum_df.merge(gp, on=['Giocatore', 'Team'], how='left')

    # Prepara dati - filtra giocatori con almeno 5 partite
    sum_df = sum_df[sum_df['GP'] >= 5].copy()
    if len(sum_df) < 10:
        return {'content': '<p>Dati insufficienti.</p>', 'title': 'Clustering', 'page_title': 'Clustering'}

    sum_df['PT_pergame'] = sum_df['PT'] / sum_df['GP']
    sum_df['AS_pergame'] = sum_df['AS'] / sum_df['GP']
    sum_df['RT_pergame'] = sum_df['RT'] / sum_df['GP']
    sum_df['PR_pergame'] = sum_df['PR'] / sum_df['GP']
    sum_df['ST_pergame'] = sum_df['ST'] / sum_df['GP']

    # Calcola percentili per ogni giocatore
    profile_stats = ['PT_pergame', 'AS_pergame', 'RT_pergame', 'PR_pergame', 'ST_pergame']
    for stat in profile_stats:
        sum_df[f'{stat}_pct'] = sum_df[stat].apply(
            lambda x: stats.percentileofscore(sum_df[stat], x, kind='rank')
        )

    # Definisci archetipi con profili percentili ideali
    # Ogni archetipo ha un vettore [PT, AS, RT, PR, ST]
    archetypes = {
        'Realizzatore': {
            'profile': [95, 50, 40, 40, 30],
            'color': '#302B8F',
            'desc': 'Primo riferimento offensivo, mette punti'
        },
        'Creatore': {
            'profile': [60, 95, 30, 50, 20],
            'color': '#00F95B',
            'desc': 'Crea occasioni per i compagni, alto volume di assist'
        },
        'Rimbalzista': {
            'profile': [50, 20, 95, 40, 70],
            'color': '#f97316',
            'desc': 'Domina a rimbalzo e protegge il ferro'
        },
        'Disruptor': {
            'profile': [30, 30, 50, 90, 60],
            'color': '#7c3aed',
            'desc': 'Rompe il gioco avversario, recuperi e pressione'
        },
        'Factotum': {
            'profile': [65, 65, 65, 55, 45],
            'color': '#06b6d4',
            'desc': 'Contributo solido in tutte le aree di gioco'
        }
    }

    # Per ogni giocatore, calcola similarità con ogni archetipo
    archetype_names = list(archetypes.keys())
    archetype_profiles = np.array([archetypes[a]['profile'] for a in archetype_names])

    players_data = []
    archetype_counts = {a: 0 for a in archetype_names}

    for _, row in sum_df.iterrows():
        player_profile = np.array([
            row['PT_pergame_pct'],
            row['AS_pergame_pct'],
            row['RT_pergame_pct'],
            row['PR_pergame_pct'],
            row['ST_pergame_pct']
        ]).reshape(1, -1)

        # Calcola similarità coseno con ogni archetipo
        similarities = cosine_similarity(player_profile, archetype_profiles)[0]
        best_match_idx = np.argmax(similarities)
        best_archetype = archetype_names[best_match_idx]
        match_score = similarities[best_match_idx]

        archetype_counts[best_archetype] += 1

        players_data.append({
            'name': row['Giocatore'],
            'team': row['Team'],
            'tipo': best_archetype,
            'match': round(match_score * 100),
            'color': archetypes[best_archetype]['color'],
            'profile': {
                'PT': int(round(row['PT_pergame_pct'])),
                'AS': int(round(row['AS_pergame_pct'])),
                'RT': int(round(row['RT_pergame_pct'])),
                'PR': int(round(row['PR_pergame_pct'])),
                'ST': int(round(row['ST_pergame_pct']))
            },
            'stats': {
                'PT': round(row['PT_pergame'], 1),
                'AS': round(row['AS_pergame'], 1),
                'RT': round(row['RT_pergame'], 1),
                'PR': round(row['PR_pergame'], 1),
                'ST': round(row['ST_pergame'], 1)
            }
        })

    players_json = json.dumps(players_data)

    # Prepara summary archetipi
    archetype_summary = []
    for name in archetype_names:
        arch_players = [p for p in players_data if p['tipo'] == name]
        if len(arch_players) > 0:
            avg_profile = {
                'PT': round(sum(p['profile']['PT'] for p in arch_players) / len(arch_players)),
                'AS': round(sum(p['profile']['AS'] for p in arch_players) / len(arch_players)),
                'RT': round(sum(p['profile']['RT'] for p in arch_players) / len(arch_players)),
                'PR': round(sum(p['profile']['PR'] for p in arch_players) / len(arch_players)),
                'ST': round(sum(p['profile']['ST'] for p in arch_players) / len(arch_players))
            }
        else:
            avg_profile = {'PT': 50, 'AS': 50, 'RT': 50, 'PR': 50, 'ST': 50}

        archetype_summary.append({
            'name': name,
            'color': archetypes[name]['color'],
            'desc': archetypes[name]['desc'],
            'ideal': archetypes[name]['profile'],
            'count': archetype_counts[name],
            'avg_profile': avg_profile
        })

    summary_json = json.dumps(archetype_summary)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Tipologie di Giocatori</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Ogni giocatore viene assegnato all'archetipo più simile al suo profilo statistico.
            La similarità è calcolata confrontando i percentili del giocatore con il profilo ideale di ogni archetipo.
        </p>

        <div id="archetype-cards" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-bottom: 30px;"></div>

        <div id="players-section" style="display: none;">
            <h3 id="archetype-title" style="margin-bottom: 15px;"></h3>
            <div id="players-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px;"></div>
        </div>
    </div>

    <script>
        const playersData = {players_json};
        const archetypeSummary = {summary_json};
        let selectedArchetype = null;

        function profileBar(label, pct, idealPct) {{
            const color = pct >= 80 ? '#22c55e' : pct >= 50 ? '#302B8F' : '#94a3b8';
            return `<div style="display: flex; align-items: center; gap: 8px; margin: 4px 0;">
                <span style="width: 30px; font-size: 12px; color: #666;">${{label}}</span>
                <div style="flex: 1; background: #e5e5e5; height: 8px; border-radius: 4px; position: relative;">
                    <div style="width: ${{pct}}%; background: ${{color}}; height: 100%; border-radius: 4px;"></div>
                    ${{idealPct !== undefined ? `<div style="position: absolute; left: ${{idealPct}}%; top: -2px; width: 2px; height: 12px; background: #000;"></div>` : ''}}
                </div>
                <span style="width: 30px; font-size: 12px; text-align: right;">${{pct}}</span>
            </div>`;
        }}

        function renderArchetypeCards() {{
            const container = document.getElementById('archetype-cards');
            let html = '';

            archetypeSummary.forEach(arch => {{
                const isSelected = selectedArchetype === arch.name;
                const border = isSelected ? `3px solid ${{arch.color}}` : '1px solid #e5e7eb';
                const shadow = isSelected ? 'box-shadow: 0 4px 12px rgba(0,0,0,0.15);' : '';

                html += `<div onclick="selectArchetype('${{arch.name}}')"
                    style="background: white; border: ${{border}}; border-radius: 12px; padding: 15px; cursor: pointer; transition: all 0.2s; ${{shadow}}">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <div style="width: 12px; height: 12px; border-radius: 50%; background: ${{arch.color}};"></div>
                        <div style="font-weight: 600;">${{arch.name}}</div>
                    </div>
                    <div style="font-size: 28px; font-weight: 700; color: ${{arch.color}};">${{arch.count}}</div>
                    <div style="font-size: 12px; color: #888; margin-top: 5px;">${{arch.desc}}</div>
                </div>`;
            }});

            container.innerHTML = html;
        }}

        function selectArchetype(name) {{
            selectedArchetype = name;
            renderArchetypeCards();
            showPlayers(name);
        }}

        function showPlayers(archName) {{
            const section = document.getElementById('players-section');
            const grid = document.getElementById('players-grid');
            const title = document.getElementById('archetype-title');

            const arch = archetypeSummary.find(a => a.name === archName);
            const players = playersData.filter(p => p.tipo === archName).sort((a, b) => b.match - a.match);

            title.innerHTML = `<span style="color: ${{arch.color}};">${{arch.name}}</span> - ${{players.length}} giocatori`;

            let html = '';

            // Mostra profilo ideale dell'archetipo
            html += `<div style="background: #f9f9f9; border: 2px dashed ${{arch.color}}; border-radius: 8px; padding: 15px; grid-column: 1 / -1;">
                <div style="font-weight: 600; margin-bottom: 10px;">Profilo ideale ${{arch.name}}</div>
                <div style="display: flex; gap: 20px; flex-wrap: wrap;">
                    <span>PT: ${{arch.ideal[0]}}</span>
                    <span>AS: ${{arch.ideal[1]}}</span>
                    <span>RT: ${{arch.ideal[2]}}</span>
                    <span>PR: ${{arch.ideal[3]}}</span>
                    <span>ST: ${{arch.ideal[4]}}</span>
                </div>
                <div style="font-size: 12px; color: #666; margin-top: 8px;">(la linea nera nelle barre indica il valore ideale)</div>
            </div>`;

            players.forEach(player => {{
                html += `<div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <div>
                            <div style="font-weight: 600;">${{player.name}}</div>
                            <div style="font-size: 13px; color: #666;">${{player.team}}</div>
                        </div>
                        <div style="background: ${{player.color}}; color: white; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600;">
                            ${{player.match}}% match
                        </div>
                    </div>
                    ${{profileBar('PT', player.profile.PT, arch.ideal[0])}}
                    ${{profileBar('AS', player.profile.AS, arch.ideal[1])}}
                    ${{profileBar('RT', player.profile.RT, arch.ideal[2])}}
                    ${{profileBar('PR', player.profile.PR, arch.ideal[3])}}
                    ${{profileBar('ST', player.profile.ST, arch.ideal[4])}}
                    <div style="margin-top: 10px; font-size: 11px; color: #888; text-align: center;">
                        ${{player.stats.PT}} pt | ${{player.stats.AS}} ast | ${{player.stats.RT}} reb /partita
                    </div>
                </div>`;
            }});

            grid.innerHTML = html;
            section.style.display = 'block';
        }}

        renderArchetypeCards();
        if (archetypeSummary.length > 0 && archetypeSummary[0].count > 0) {{
            // Seleziona il primo archetipo con giocatori
            const firstWithPlayers = archetypeSummary.find(a => a.count > 0);
            if (firstWithPlayers) selectArchetype(firstWithPlayers.name);
        }}
    </script>
    '''

    return {
        'content': content,
        'title': f'Tipologie - {camp_name}',
        'page_title': 'Tipologie Giocatori',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Analisi / Tipologie'
    }


def generate_analisi_dipendenza(campionato_filter, camp_name):
    """Genera contenuto pagina Dipendenza Squadra."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Dipendenza', 'page_title': 'Dipendenza'}

    try:
        dep_df = compute_team_dependency(overall_df, sum_df)
        if dep_df is None or len(dep_df) == 0:
            return {'content': '<p>Dati insufficienti.</p>', 'title': 'Dipendenza', 'page_title': 'Dipendenza'}
    except Exception as e:
        return {'content': f'<p>Errore: {e}</p>', 'title': 'Dipendenza', 'page_title': 'Dipendenza'}

    # Prepara dati dettaglio per ogni squadra (tutti i giocatori)
    team_players_data = {}
    for team in sum_df['Team'].unique():
        team_data = sum_df[sum_df['Team'] == team].copy()
        if len(team_data) == 0:
            continue

        total_pts = team_data['PT'].sum()
        total_min = team_data['Minutes'].sum() if 'Minutes' in team_data.columns else 0

        players = []
        for _, row in team_data.sort_values('PT', ascending=False).iterrows():
            players.append({
                'name': row['Giocatore'],
                'pt': int(row['PT']),
                'pt_pct': round(row['PT'] / total_pts * 100, 1) if total_pts > 0 else 0,
                'min': int(row['Minutes']) if 'Minutes' in row else 0,
                'min_pct': round(row['Minutes'] / total_min * 100, 1) if total_min > 0 else 0
            })
        team_players_data[team] = players

    team_players_json = json.dumps(team_players_data, default=str)

    # Prepara dati per JavaScript
    dep_data = dep_df.to_dict('records')
    dep_json = json.dumps(dep_data, default=str)
    teams = sorted(dep_df['Team'].unique().tolist())

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Dipendenza dai Top Scorer</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Quanto ogni squadra dipende dai propri top 3 giocatori per punti e minuti.
            Un'alta concentrazione può essere un rischio in caso di infortunio.
        </p>

        <div style="margin-bottom: 20px; display: flex; gap: 20px; flex-wrap: wrap; align-items: center;">
            <div>
                <label style="font-weight: 600;">Statistica:</label>
                <select id="stat-type" onchange="updateChart()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd;">
                    <option value="PT">Punti</option>
                    <option value="MIN">Minuti</option>
                </select>
            </div>
        </div>

        <div id="dep-chart" style="min-height: 500px;"></div>

        <div style="margin-top: 30px;">
            <h3 style="margin-bottom: 15px;">Dettaglio per Squadra</h3>
            <select id="team-select" onchange="updateDetail()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd; min-width: 200px;">
                {''.join(f'<option value="{t}">{t}</option>' for t in teams)}
            </select>
            <div id="team-detail" style="margin-top: 15px;"></div>
        </div>
    </div>

    <script>
        const depData = {dep_json};
        const teamPlayers = {team_players_json};

        function updateChart() {{
            const statType = document.getElementById('stat-type').value;
            const prefix = statType;

            // Sort by top1 percentage
            const sorted = [...depData].sort((a, b) => a[prefix + '_Top1_pct'] - b[prefix + '_Top1_pct']);

            const teams = sorted.map(d => d.Team);
            const top1 = sorted.map(d => d[prefix + '_Top1_pct']);
            const top2Diff = sorted.map(d => d[prefix + '_Top2_pct'] - d[prefix + '_Top1_pct']);
            const top3Diff = sorted.map(d => d[prefix + '_Top3_pct'] - d[prefix + '_Top2_pct']);
            const altri = sorted.map(d => d[prefix + '_Altri_pct']);

            const traces = [
                {{
                    y: teams, x: top1, name: '1° scorer',
                    type: 'bar', orientation: 'h',
                    marker: {{ color: '#302B8F' }},
                    text: sorted.map(d => d[prefix + '_Top1_nome'].split(' ').pop() + ': ' + d[prefix + '_Top1_pct'].toFixed(0) + '%'),
                    textposition: 'inside', insidetextanchor: 'middle'
                }},
                {{
                    y: teams, x: top2Diff, name: '2° scorer',
                    type: 'bar', orientation: 'h',
                    marker: {{ color: '#00F95B' }},
                    text: sorted.map(d => d[prefix + '_Top2_nome'].split(' ').pop() + ': ' + (d[prefix + '_Top2_pct'] - d[prefix + '_Top1_pct']).toFixed(0) + '%'),
                    textposition: 'inside', insidetextanchor: 'middle'
                }},
                {{
                    y: teams, x: top3Diff, name: '3° scorer',
                    type: 'bar', orientation: 'h',
                    marker: {{ color: '#fbbf24' }},
                    text: sorted.map(d => d[prefix + '_Top3_nome'].split(' ').pop() + ': ' + (d[prefix + '_Top3_pct'] - d[prefix + '_Top2_pct']).toFixed(0) + '%'),
                    textposition: 'inside', insidetextanchor: 'middle'
                }},
                {{
                    y: teams, x: altri, name: 'Altri',
                    type: 'bar', orientation: 'h',
                    marker: {{ color: '#e5e7eb' }},
                    text: sorted.map(d => 'Altri: ' + d[prefix + '_Altri_pct'].toFixed(0) + '%'),
                    textposition: 'inside', insidetextanchor: 'middle'
                }}
            ];

            const layout = {{
                barmode: 'stack',
                height: Math.max(400, teams.length * 35),
                margin: {{ l: 150, r: 30, t: 30, b: 50 }},
                xaxis: {{ title: 'Percentuale %', range: [0, 100] }},
                legend: {{ orientation: 'h', y: -0.1 }}
            }};

            Plotly.newPlot('dep-chart', traces, layout, {{ responsive: true }});
        }}

        function updateDetail() {{
            const team = document.getElementById('team-select').value;
            const players = teamPlayers[team];
            if (!players) return;

            let html = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px;">';

            // Punti - tutti i giocatori
            html += '<div style="background: #f9f9f9; padding: 15px; border-radius: 8px;">';
            html += '<h4 style="margin-bottom: 15px; color: #302B8F;">Distribuzione Punti</h4>';
            players.forEach((p, i) => {{
                const barColor = i < 3 ? '#302B8F' : '#94a3b8';
                html += `<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <span style="width: 120px; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${{p.name}}</span>
                    <div style="flex: 1; background: #e5e7eb; height: 20px; border-radius: 4px; position: relative;">
                        <div style="width: ${{p.pt_pct}}%; background: ${{barColor}}; height: 100%; border-radius: 4px;"></div>
                    </div>
                    <span style="width: 50px; font-size: 12px; text-align: right;">${{p.pt_pct}}%</span>
                    <span style="width: 40px; font-size: 11px; color: #888; text-align: right;">${{p.pt}}</span>
                </div>`;
            }});
            html += '</div>';

            // Minuti - tutti i giocatori (ordinati per minuti)
            const playersByMin = [...players].sort((a, b) => b.min - a.min);
            html += '<div style="background: #f9f9f9; padding: 15px; border-radius: 8px;">';
            html += '<h4 style="margin-bottom: 15px; color: #302B8F;">Distribuzione Minuti</h4>';
            playersByMin.forEach((p, i) => {{
                const barColor = i < 3 ? '#302B8F' : '#94a3b8';
                html += `<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                    <span style="width: 120px; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${{p.name}}</span>
                    <div style="flex: 1; background: #e5e7eb; height: 20px; border-radius: 4px; position: relative;">
                        <div style="width: ${{p.min_pct}}%; background: ${{barColor}}; height: 100%; border-radius: 4px;"></div>
                    </div>
                    <span style="width: 50px; font-size: 12px; text-align: right;">${{p.min_pct}}%</span>
                    <span style="width: 40px; font-size: 11px; color: #888; text-align: right;">${{p.min}}</span>
                </div>`;
            }});
            html += '</div>';

            html += '</div>';
            document.getElementById('team-detail').innerHTML = html;
        }}

        updateChart();
        updateDetail();
    </script>
    '''

    return {
        'content': content,
        'title': f'Dipendenza - {camp_name}',
        'page_title': 'Dipendenza Squadra',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Analisi / Dipendenza'
    }


def generate_analisi_quando_vince(campionato_filter, camp_name):
    """Genera contenuto pagina Quando Vince."""
    overall_df, sum_df, median_df = load_and_prepare_data(campionato_filter)
    if overall_df is None:
        return {'content': '<p>Dati non disponibili.</p>', 'title': 'Quando Vince', 'page_title': 'Quando Vince'}

    try:
        team_games = compute_team_game_stats(overall_df)
        team_rules = compute_team_game_rules(team_games, min_games=8)
        player_rules = compute_player_based_rules(overall_df, min_games=8)
    except Exception as e:
        return {'content': f'<p>Errore: {e}</p>', 'title': 'Quando Vince', 'page_title': 'Quando Vince'}

    # Combina squadre da entrambi i tipi di regole
    all_teams = set(team_rules.keys()) | set(player_rules.keys())
    if not all_teams:
        return {'content': '<p>Dati insufficienti.</p>', 'title': 'Quando Vince', 'page_title': 'Quando Vince'}

    # Prepara dati per JavaScript
    all_rules = {
        'team': {team: data for team, data in team_rules.items()},
        'player': {team: data for team, data in player_rules.items()},
    }
    rules_json = json.dumps(all_rules, default=str)

    teams = sorted(all_teams)

    content = f'''
    <div class="content-section">
        <h2 class="section-title">Quando Vince Ogni Squadra</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Quali condizioni statistiche caratterizzano le vittorie di ogni squadra?
            Confronto tra situazioni sopra/sotto soglia.
        </p>

        <div style="margin-bottom: 20px; display: flex; gap: 20px; flex-wrap: wrap;">
            <div>
                <label style="font-weight: 600;">Squadra:</label>
                <select id="rule-team" onchange="showRules()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd; min-width: 200px;">
                    {''.join(f'<option value="{t}">{t}</option>' for t in teams)}
                </select>
            </div>
            <div>
                <label style="font-weight: 600;">Tipo analisi:</label>
                <select id="rule-type" onchange="showRules()" style="padding: 8px; border-radius: 6px; border: 1px solid #ddd;">
                    <option value="team">Stats squadra (fatti/subiti)</option>
                    <option value="player">Performance giocatori</option>
                </select>
            </div>
        </div>

        <div id="rules-content"></div>
    </div>

    <script>
        const rulesData = {rules_json};

        function showRules() {{
            const team = document.getElementById('rule-team').value;
            const type = document.getElementById('rule-type').value;
            const contentDiv = document.getElementById('rules-content');

            const data = rulesData[type][team];
            if (!data || !data.rules || data.rules.length === 0) {{
                contentDiv.innerHTML = '<p style="color: #666;">Dati insufficienti per questa squadra.</p>';
                return;
            }}

            const winRate = (data.win_rate * 100).toFixed(1);
            const nGames = data.n_games;

            let html = `<div style="margin-bottom: 20px; background: #f9f9f9; padding: 15px; border-radius: 8px;">`;
            html += `<strong>Win Rate generale:</strong> ${{winRate}}% (${{nGames}} partite)`;
            html += `</div>`;

            html += '<div style="display: grid; gap: 20px;">';

            data.rules.forEach((rule, i) => {{
                const condition = rule.condition || '';
                const threshold = rule.threshold || 0;
                const stat = rule.stat || '';  // "punti" o "minuti"
                const leftProb = (rule.left_prob * 100).toFixed(0);
                const rightProb = (rule.right_prob * 100).toFixed(0);
                const leftSamples = rule.left_samples || 0;
                const rightSamples = rule.right_samples || 0;

                // Determina quale lato è migliore
                const leftBetter = rule.left_prob > rule.right_prob;

                // Titolo con stat type se disponibile
                const titleText = stat ? `${{condition}} - ${{threshold}} ${{stat}}` : `${{condition}} - Soglia: ${{threshold}}`;

                html += `<div style="background: white; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden;">`;
                html += `<div style="background: #302B8F; color: white; padding: 12px 15px; font-weight: 600;">`;
                html += titleText;
                html += `</div>`;

                html += `<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0;">`;

                // Lato sinistro (≤ threshold)
                const leftBg = leftBetter ? '#dcfce7' : '#fee2e2';
                const leftBorder = leftBetter ? '#22c55e' : '#ef4444';
                const statSuffix = stat ? ` ${{stat}}` : '';
                html += `<div style="padding: 15px; background: ${{leftBg}}; border-right: 1px solid #e5e7eb;">`;
                html += `<div style="font-size: 14px; color: #666; margin-bottom: 5px;">≤ ${{threshold}}${{statSuffix}}</div>`;
                html += `<div style="font-size: 28px; font-weight: 700; color: ${{leftBorder}};">${{leftProb}}%</div>`;
                html += `<div style="font-size: 12px; color: #888;">vittorie (${{leftSamples}} partite)</div>`;
                html += `</div>`;

                // Lato destro (> threshold)
                const rightBg = !leftBetter ? '#dcfce7' : '#fee2e2';
                const rightBorder = !leftBetter ? '#22c55e' : '#ef4444';
                html += `<div style="padding: 15px; background: ${{rightBg}};">`;
                html += `<div style="font-size: 14px; color: #666; margin-bottom: 5px;">> ${{threshold}}${{statSuffix}}</div>`;
                html += `<div style="font-size: 28px; font-weight: 700; color: ${{rightBorder}};">${{rightProb}}%</div>`;
                html += `<div style="font-size: 12px; color: #888;">vittorie (${{rightSamples}} partite)</div>`;
                html += `</div>`;

                html += `</div></div>`;
            }});

            html += '</div>';
            contentDiv.innerHTML = html;
        }}

        showRules();
    </script>
    '''

    return {
        'content': content,
        'title': f'Quando Vince - {camp_name}',
        'page_title': 'Quando Vince',
        'subtitle': camp_name,
        'breadcrumb': f'{camp_name} / Analisi / Quando Vince'
    }


# ============ PAGINE PARTITE (PBP) ============

def generate_partite_momenti_decisivi(campionato_filter, camp_name):
    """Genera pagina Momenti Decisivi con clutch stats, closer rankings, Q4 heroes."""
    pbp_df = load_pbp_data(campionato_filter)

    if pbp_df is None or pbp_df.empty:
        return {
            'content': '<p>Dati play-by-play non disponibili.</p>',
            'title': f'Momenti Decisivi - {camp_name}',
            'page_title': 'Momenti Decisivi',
            'subtitle': camp_name,
            'breadcrumb': f'{camp_name} / Partite / Momenti Decisivi'
        }

    # Calcola statistiche
    clutch_stats = compute_clutch_stats(pbp_df)
    closer_rankings = compute_closer_rankings(pbp_df, min_clutch_games=3)
    responsibility = compute_clutch_responsibility(pbp_df, min_games=3)
    q4_heroes = compute_q4_heroes(pbp_df, min_games=5)

    content = '''
    <div class="content-section">
        <h2 class="section-title">Cos'sono i Momenti Decisivi?</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Analizziamo le performance nei <strong>momenti clutch</strong>: ultimi 2 minuti del 4° quarto
            quando il punteggio è entro i 5 punti. Chi segna quando conta davvero?
        </p>
    </div>
    '''

    # CLOSER RANKINGS
    if not closer_rankings.empty:
        top_closers = closer_rankings.head(15)

        # Grafico a barre orizzontali
        fig = go.Figure()

        fig.add_trace(go.Bar(
            y=top_closers['player'],
            x=top_closers['clutch_points'],
            orientation='h',
            marker=dict(
                color=top_closers['clutch_ppg'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title='PPG Clutch')
            ),
            text=[f"{p} pts ({g} partite)" for p, g in zip(top_closers['clutch_points'], top_closers['clutch_games'])],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Punti clutch: %{x}<br>PPG: %{customdata:.2f}<extra></extra>',
            customdata=top_closers['clutch_ppg']
        ))

        fig.update_layout(
            title='Top Closer - Chi Segna nei Momenti Decisivi',
            xaxis_title='Punti Totali in Clutch',
            yaxis=dict(autorange='reversed'),
            height=500,
            margin=dict(l=150, r=100)
        )

        content += f'''
        <div class="content-section">
            <h2 class="section-title">🎯 Top Closer</h2>
            <p style="color: #666; margin-bottom: 15px;">
                Giocatori che segnano di più nei momenti clutch (ultimi 2 min, gap ≤5).
            </p>
            {plotly_to_html(fig)}
        </div>
        '''

        # Tabella dettagliata
        table_html = '''
        <table class="stats-table" style="width: 100%; border-collapse: collapse; margin-top: 20px;">
            <thead>
                <tr style="background: #302B8F; color: white;">
                    <th style="padding: 12px; text-align: left;">Giocatore</th>
                    <th style="padding: 12px; text-align: left;">Squadra</th>
                    <th style="padding: 12px; text-align: center;">Punti</th>
                    <th style="padding: 12px; text-align: center;">Partite</th>
                    <th style="padding: 12px; text-align: center;">PPG</th>
                    <th style="padding: 12px; text-align: center;">FG%</th>
                    <th style="padding: 12px; text-align: center;">3PT%</th>
                    <th style="padding: 12px; text-align: center;">FT%</th>
                </tr>
            </thead>
            <tbody>
        '''

        for i, row in top_closers.iterrows():
            bg = '#f8f8f8' if i % 2 == 0 else 'white'
            fg_pct = f"{row['fg_pct']:.0f}%" if row.get('fg_attempts', 0) > 0 else '-'
            three_pct = f"{row['3pt_pct']:.0f}%" if row.get('3pt_attempts', 0) > 0 else '-'
            ft_pct = f"{row['ft_pct']:.0f}%" if row.get('ft_attempts', 0) > 0 else '-'
            table_html += f'''
                <tr style="background: {bg};">
                    <td style="padding: 10px; font-weight: 600;">{row['player']}</td>
                    <td style="padding: 10px;">{row['team']}</td>
                    <td style="padding: 10px; text-align: center; font-weight: 700; color: #302B8F;">{int(row['clutch_points'])}</td>
                    <td style="padding: 10px; text-align: center;">{int(row['clutch_games'])}</td>
                    <td style="padding: 10px; text-align: center;">{row['clutch_ppg']:.1f}</td>
                    <td style="padding: 10px; text-align: center;">{fg_pct}</td>
                    <td style="padding: 10px; text-align: center;">{three_pct}</td>
                    <td style="padding: 10px; text-align: center;">{ft_pct}</td>
                </tr>
            '''

        table_html += '</tbody></table>'

        content += f'''
        <div class="content-section">
            <h2 class="section-title">📊 Statistiche Clutch Complete</h2>
            {table_html}
        </div>
        '''

    # RESPONSABILITÀ - Chi si prende più tiri
    if not responsibility.empty:
        top_resp = responsibility.head(15)

        fig_resp = go.Figure()

        fig_resp.add_trace(go.Bar(
            y=top_resp['player'],
            x=top_resp['total_shots'],
            orientation='h',
            marker=dict(
                color=top_resp['ts_pct'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title='TS%')
            ),
            text=[f"{s} tiri ({g} partite)" for s, g in zip(top_resp['total_shots'], top_resp['clutch_games'])],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Tiri totali: %{x}<br>TS%: %{customdata:.1f}%<extra></extra>',
            customdata=top_resp['ts_pct']
        ))

        fig_resp.update_layout(
            title='Chi Si Prende la Responsabilità nei Momenti Decisivi',
            xaxis_title='Tiri Totali in Clutch (FG + FT)',
            yaxis=dict(autorange='reversed'),
            height=500,
            margin=dict(l=150, r=100)
        )

        resp_table = '''
        <table class="stats-table" style="width: 100%; border-collapse: collapse; margin-top: 20px;">
            <thead>
                <tr style="background: #302B8F; color: white;">
                    <th style="padding: 12px; text-align: left;">Giocatore</th>
                    <th style="padding: 12px; text-align: left;">Squadra</th>
                    <th style="padding: 12px; text-align: center;">Tiri</th>
                    <th style="padding: 12px; text-align: center;">Tiri/G</th>
                    <th style="padding: 12px; text-align: center;">Punti</th>
                    <th style="padding: 12px; text-align: center;">TS%</th>
                    <th style="padding: 12px; text-align: center;">FG%</th>
                </tr>
            </thead>
            <tbody>
        '''

        for i, row in top_resp.iterrows():
            bg = '#f8f8f8' if i % 2 == 0 else 'white'
            ts_color = '#22c55e' if row['ts_pct'] >= 50 else ('#fbbf24' if row['ts_pct'] >= 40 else '#ef4444')
            resp_table += f'''
                <tr style="background: {bg};">
                    <td style="padding: 10px; font-weight: 600;">{row['player']}</td>
                    <td style="padding: 10px;">{row['team']}</td>
                    <td style="padding: 10px; text-align: center; font-weight: 700; color: #302B8F;">{int(row['total_shots'])}</td>
                    <td style="padding: 10px; text-align: center;">{row['shots_per_game']:.1f}</td>
                    <td style="padding: 10px; text-align: center;">{int(row['clutch_points'])}</td>
                    <td style="padding: 10px; text-align: center; color: {ts_color}; font-weight: 600;">{row['ts_pct']:.1f}%</td>
                    <td style="padding: 10px; text-align: center;">{row['fg_pct']:.0f}%</td>
                </tr>
            '''

        resp_table += '</tbody></table>'

        content += f'''
        <div class="content-section">
            <h2 class="section-title">💪 Responsabilità nei Momenti Chiave</h2>
            <p style="color: #666; margin-bottom: 15px;">
                Chi si prende più tiri nei momenti clutch? TS% (True Shooting) misura l'efficienza complessiva.
            </p>
            {plotly_to_html(fig_resp)}
            {resp_table}
        </div>
        '''

    # Q4 HEROES
    if not q4_heroes.empty:
        # Filtra solo chi migliora significativamente
        heroes_positive = q4_heroes[q4_heroes['q4_boost'] > 0].head(15)

        if not heroes_positive.empty:
            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=heroes_positive['player'],
                y=heroes_positive['q4_boost'],
                marker=dict(
                    color=heroes_positive['q4_boost'],
                    colorscale=[[0, '#fbbf24'], [0.5, '#22c55e'], [1, '#059669']],
                ),
                text=[f"+{b:.0f}%" for b in heroes_positive['q4_boost']],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Boost Q4: +%{y:.1f}%<br>Q4 PPG: %{customdata[0]:.1f}<br>Q1-Q3 PPG: %{customdata[1]:.1f}<extra></extra>',
                customdata=list(zip(heroes_positive['q4_ppg'], heroes_positive['other_ppg']))
            ))

            fig.update_layout(
                title='4° Quarto Heroes - Chi Migliora nel Finale',
                yaxis_title='Boost Performance (%)',
                xaxis_tickangle=-45,
                height=450,
                margin=dict(b=120)
            )

            content += f'''
            <div class="content-section">
                <h2 class="section-title">🦸 4° Quarto Heroes</h2>
                <p style="color: #666; margin-bottom: 15px;">
                    Giocatori che aumentano la loro produzione nel 4° quarto rispetto ai primi tre.
                    Il boost indica la % di miglioramento dei punti per partita.
                </p>
                {plotly_to_html(fig)}
            </div>
            '''

            # Confronto Q4 vs Q1-Q3
            comparison_data = heroes_positive.head(10)

            fig2 = go.Figure()

            fig2.add_trace(go.Bar(
                name='Q1-Q3 PPG',
                x=comparison_data['player'],
                y=comparison_data['other_ppg'],
                marker_color='#94a3b8'
            ))

            fig2.add_trace(go.Bar(
                name='Q4 PPG',
                x=comparison_data['player'],
                y=comparison_data['q4_ppg'],
                marker_color='#22c55e'
            ))

            fig2.update_layout(
                title='Confronto Performance: Q4 vs Q1-Q3',
                yaxis_title='Punti per Partita',
                barmode='group',
                xaxis_tickangle=-45,
                height=400,
                margin=dict(b=120)
            )

            content += f'''
            <div class="content-section">
                <h2 class="section-title">📈 Confronto Q4 vs Resto Partita</h2>
                {plotly_to_html(fig2)}
            </div>
            '''

    return {
        'content': content,
        'title': f'Momenti Decisivi - {camp_name}',
        'page_title': 'Momenti Decisivi',
        'subtitle': f'{camp_name} - Clutch Stats & Q4 Heroes',
        'breadcrumb': f'{camp_name} / Partite / Momenti Decisivi'
    }


def generate_partite_andamento(campionato_filter, camp_name):
    """Genera pagina Andamento & Parziali con distribuzione quarti, run analysis, comeback."""
    pbp_df = load_pbp_data(campionato_filter)
    quarters_df = load_quarters_data(campionato_filter)

    if (pbp_df is None or pbp_df.empty) and (quarters_df is None or quarters_df.empty):
        return {
            'content': '<p>Dati play-by-play non disponibili.</p>',
            'title': f'Andamento & Parziali - {camp_name}',
            'page_title': 'Andamento & Parziali',
            'subtitle': camp_name,
            'breadcrumb': f'{camp_name} / Partite / Andamento'
        }

    content = '''
    <div class="content-section">
        <h2 class="section-title">Analisi Andamento Partite</h2>
        <p style="color: #666; margin-bottom: 20px;">
            Come si sviluppano le partite? Quali squadre partono forte, quali finiscono in crescendo,
            e chi riesce a rimontare dai grandi svantaggi?
        </p>
    </div>
    '''

    # DISTRIBUZIONE PUNTI PER QUARTO
    if quarters_df is not None and not quarters_df.empty:
        quarter_dist = compute_quarter_distribution(quarters_df)

        if not quarter_dist.empty:
            # Heatmap distribuzione quarti
            teams = quarter_dist['team'].tolist()
            q1 = quarter_dist['q1_avg'].tolist()
            q2 = quarter_dist['q2_avg'].tolist()
            q3 = quarter_dist['q3_avg'].tolist()
            q4 = quarter_dist['q4_avg'].tolist()

            fig = go.Figure(data=go.Heatmap(
                z=[q1, q2, q3, q4],
                x=teams,
                y=['Q1', 'Q2', 'Q3', 'Q4'],
                colorscale='RdYlGn',
                text=[[f'{v:.1f}' for v in q1],
                      [f'{v:.1f}' for v in q2],
                      [f'{v:.1f}' for v in q3],
                      [f'{v:.1f}' for v in q4]],
                texttemplate='%{text}',
                textfont={"size": 10},
                hovertemplate='%{x}<br>%{y}: %{z:.1f} pts<extra></extra>'
            ))

            fig.update_layout(
                title='Punti Medi per Quarto per Squadra',
                xaxis_tickangle=-45,
                height=350,
                margin=dict(b=120)
            )

            content += f'''
            <div class="content-section">
                <h2 class="section-title">📊 Distribuzione Punti per Quarto</h2>
                {plotly_to_html(fig)}
            </div>
            '''

            # Chi parte forte vs chi finisce forte
            quarter_dist_sorted = quarter_dist.sort_values('q4_vs_q1', ascending=False)

            fig2 = go.Figure()

            colors = ['#22c55e' if x > 0 else '#ef4444' for x in quarter_dist_sorted['q4_vs_q1']]

            fig2.add_trace(go.Bar(
                x=quarter_dist_sorted['team'],
                y=quarter_dist_sorted['q4_vs_q1'],
                marker_color=colors,
                text=[f"+{v:.1f}" if v > 0 else f"{v:.1f}" for v in quarter_dist_sorted['q4_vs_q1']],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Q4 vs Q1: %{y:.1f} pts<extra></extra>'
            ))

            fig2.add_hline(y=0, line_dash="dash", line_color="gray")

            fig2.update_layout(
                title='Q4 vs Q1: Chi Finisce Forte (+) vs Chi Parte Forte (-)',
                yaxis_title='Differenza Punti (Q4 - Q1)',
                xaxis_tickangle=-45,
                height=400,
                margin=dict(b=120)
            )

            content += f'''
            <div class="content-section">
                <h2 class="section-title">🏁 Partenze vs Chiusure</h2>
                <p style="color: #666; margin-bottom: 15px;">
                    Valori positivi = squadre che migliorano nel finale. Valori negativi = squadre che partono forte.
                </p>
                {plotly_to_html(fig2)}
            </div>
            '''

    # SCORING RUNS
    if pbp_df is not None and not pbp_df.empty:
        runs = compute_scoring_runs(pbp_df, min_run=8)

        if not runs.empty:
            fig = go.Figure()

            fig.add_trace(go.Bar(
                name='Run Fatti',
                x=runs['team'],
                y=runs['runs_made'],
                marker_color='#22c55e',
                text=runs['runs_made'],
                textposition='auto'
            ))

            fig.add_trace(go.Bar(
                name='Run Subiti',
                x=runs['team'],
                y=runs['runs_allowed'],
                marker_color='#ef4444',
                text=runs['runs_allowed'],
                textposition='auto'
            ))

            fig.update_layout(
                title='Parziali Significativi (8+ punti consecutivi)',
                yaxis_title='Numero di Run',
                barmode='group',
                xaxis_tickangle=-45,
                height=450,
                margin=dict(b=120)
            )

            content += f'''
            <div class="content-section">
                <h2 class="section-title">🔥 Parziali & Run</h2>
                <p style="color: #666; margin-bottom: 15px;">
                    Un "run" è una sequenza di 8+ punti consecutivi senza che l'avversario segni.
                    Verde = run fatti, Rosso = run subiti.
                </p>
                {plotly_to_html(fig)}
            </div>
            '''

            # Tabella migliori run
            top_runs = runs.head(10)
            table_html = '''
            <table class="stats-table" style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background: #302B8F; color: white;">
                        <th style="padding: 12px; text-align: left;">Squadra</th>
                        <th style="padding: 12px; text-align: center;">Run Fatti</th>
                        <th style="padding: 12px; text-align: center;">Miglior Run</th>
                        <th style="padding: 12px; text-align: center;">Run Subiti</th>
                        <th style="padding: 12px; text-align: center;">Peggior Subito</th>
                        <th style="padding: 12px; text-align: center;">Differenziale</th>
                    </tr>
                </thead>
                <tbody>
            '''

            for i, row in top_runs.iterrows():
                bg = '#f8f8f8' if i % 2 == 0 else 'white'
                diff_color = '#22c55e' if row['run_diff'] > 0 else '#ef4444' if row['run_diff'] < 0 else '#666'
                table_html += f'''
                    <tr style="background: {bg};">
                        <td style="padding: 10px; font-weight: 600;">{row['team']}</td>
                        <td style="padding: 10px; text-align: center;">{int(row['runs_made'])}</td>
                        <td style="padding: 10px; text-align: center; color: #22c55e; font-weight: 700;">{int(row['best_run'])}-0</td>
                        <td style="padding: 10px; text-align: center;">{int(row['runs_allowed'])}</td>
                        <td style="padding: 10px; text-align: center; color: #ef4444;">0-{int(row['worst_run_allowed'])}</td>
                        <td style="padding: 10px; text-align: center; font-weight: 700; color: {diff_color};">{int(row['run_diff']):+d}</td>
                    </tr>
                '''

            table_html += '</tbody></table>'

            content += f'''
            <div class="content-section">
                <h2 class="section-title">📋 Dettaglio Parziali</h2>
                {table_html}
            </div>
            '''

        # COMEBACK KINGS
        comebacks = compute_comeback_stats(pbp_df, min_deficit=10)

        if not comebacks.empty:
            fig = go.Figure()

            fig.add_trace(go.Bar(
                name='Rimonte Riuscite',
                x=comebacks['team'],
                y=comebacks['comeback_wins'],
                marker_color='#22c55e',
                text=comebacks['comeback_wins'],
                textposition='auto'
            ))

            fig.add_trace(go.Bar(
                name='Vantaggi Sprecati',
                x=comebacks['team'],
                y=comebacks['blown_leads'],
                marker_color='#ef4444',
                text=comebacks['blown_leads'],
                textposition='auto'
            ))

            fig.update_layout(
                title='Rimonte da -10+ Punti',
                yaxis_title='Numero di Partite',
                barmode='group',
                xaxis_tickangle=-45,
                height=450,
                margin=dict(b=120)
            )

            content += f'''
            <div class="content-section">
                <h2 class="section-title">👑 Comeback Kings</h2>
                <p style="color: #666; margin-bottom: 15px;">
                    Squadre che riescono a rimontare da -10 o più punti di svantaggio,
                    e squadre che si fanno rimontare dopo essere state avanti di 10+.
                </p>
                {plotly_to_html(fig)}
            </div>
            '''

            # Tabella dettaglio
            table_html = '''
            <table class="stats-table" style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background: #302B8F; color: white;">
                        <th style="padding: 12px; text-align: left;">Squadra</th>
                        <th style="padding: 12px; text-align: center;">Rimonte</th>
                        <th style="padding: 12px; text-align: center;">Rimonte Vinte</th>
                        <th style="padding: 12px; text-align: center;">Max Deficit</th>
                        <th style="padding: 12px; text-align: center;">Vantaggi Persi</th>
                    </tr>
                </thead>
                <tbody>
            '''

            for i, row in comebacks.head(15).iterrows():
                bg = '#f8f8f8' if i % 2 == 0 else 'white'
                table_html += f'''
                    <tr style="background: {bg};">
                        <td style="padding: 10px; font-weight: 600;">{row['team']}</td>
                        <td style="padding: 10px; text-align: center;">{int(row['comebacks'])}</td>
                        <td style="padding: 10px; text-align: center; color: #22c55e; font-weight: 700;">{int(row['comeback_wins'])}</td>
                        <td style="padding: 10px; text-align: center;">-{int(row['max_deficit'])}</td>
                        <td style="padding: 10px; text-align: center; color: #ef4444;">{int(row['blown_leads'])}</td>
                    </tr>
                '''

            table_html += '</tbody></table>'

            content += f'''
            <div class="content-section">
                <h2 class="section-title">📋 Dettaglio Rimonte</h2>
                {table_html}
            </div>
            '''

    # DISTRIBUZIONE GIOCATORI PER QUARTO
    if pbp_df is not None and not pbp_df.empty:
        player_activity = compute_player_quarter_activity(pbp_df)

        if not player_activity.empty:
            # Filtra giocatori significativi
            significant_players = player_activity[player_activity['total_events'] >= 30].copy()

            if not significant_players.empty:
                # Grafico: Top 20 giocatori per Q4 share (chi gioca di più nel finale)
                q4_specialists = significant_players.nlargest(20, 'q4_share')

                fig_q4 = go.Figure()

                fig_q4.add_trace(go.Bar(
                    y=q4_specialists['player'],
                    x=q4_specialists['q4_share'],
                    orientation='h',
                    marker=dict(
                        color=q4_specialists['q4_share'],
                        colorscale='Blues',
                    ),
                    text=[f"{v:.1f}%" for v in q4_specialists['q4_share']],
                    textposition='outside',
                    hovertemplate='<b>%{y}</b><br>Q4 Share: %{x:.1f}%<br>Team: %{customdata}<extra></extra>',
                    customdata=q4_specialists['team']
                ))

                fig_q4.update_layout(
                    title='Chi Gioca di Più nel 4° Quarto (% eventi in Q4)',
                    xaxis_title='% Eventi in Q4',
                    yaxis=dict(autorange='reversed'),
                    height=550,
                    margin=dict(l=150, r=80)
                )

                content += f'''
                <div class="content-section">
                    <h2 class="section-title">⏱️ Distribuzione per Quarto</h2>
                    <p style="color: #666; margin-bottom: 15px;">
                        Analisi dell'attività dei giocatori nei vari quarti. La % indica quanta parte
                        della loro attività avviene nel 4° quarto (un proxy per i minuti giocati).
                    </p>
                    {plotly_to_html(fig_q4)}
                </div>
                '''

                # Stacked bar per distribuzione completa (top 15 per eventi totali)
                top_players = significant_players.nlargest(15, 'total_events')

                fig_dist = go.Figure()

                for q, col, color in [
                    ('Q1', 'q1_events', '#94a3b8'),
                    ('Q2', 'q2_events', '#64748b'),
                    ('Q3', 'q3_events', '#475569'),
                    ('Q4', 'q4_events', '#302B8F')
                ]:
                    fig_dist.add_trace(go.Bar(
                        name=q,
                        y=top_players['player'],
                        x=top_players[col],
                        orientation='h',
                        marker_color=color,
                        hovertemplate=f'<b>%{{y}}</b><br>{q}: %{{x}} eventi<extra></extra>'
                    ))

                fig_dist.update_layout(
                    title='Distribuzione Eventi per Quarto (Top 15 giocatori)',
                    xaxis_title='Numero Eventi',
                    barmode='stack',
                    yaxis=dict(autorange='reversed'),
                    height=500,
                    margin=dict(l=150, r=50),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )


    return {
        'content': content,
        'title': f'Andamento & Parziali - {camp_name}',
        'page_title': 'Andamento & Parziali',
        'subtitle': f'{camp_name} - Quarti, Run, Rimonte',
        'breadcrumb': f'{camp_name} / Partite / Andamento'
    }


# ============ MAPPING CAMPIONATI ============

CAMP_MAPPING = {
    'a2': ('a2', 'Serie A2'),
    'b/girone-a': ('b_a', 'Serie B - Girone A'),
    'b/girone-b': ('b_b', 'Serie B - Girone B'),
    # 'b/combinata': ('b_combined', 'Serie B - Combinata'),  # TODO: gestire separatamente
}


def generate_all_pages():
    """Genera tutte le pagine del sito."""
    pages = {}

    # Per ogni campionato
    for path_prefix, (camp_filter, camp_name) in CAMP_MAPPING.items():
        print(f"Generando pagine per: {camp_name}")

        try:
            # Squadre
            pages[f'{path_prefix}/squadre/classifiche.html'] = generate_squadre_classifiche(camp_filter, camp_name)
            pages[f'{path_prefix}/squadre/radar.html'] = generate_squadre_radar(camp_filter, camp_name)
            pages[f'{path_prefix}/squadre/vittorie-sconfitte.html'] = generate_squadre_vittorie_sconfitte(camp_filter, camp_name)
            pages[f'{path_prefix}/squadre/casa-trasferta.html'] = generate_squadre_casa_trasferta(camp_filter, camp_name)

            # Giocatori
            pages[f'{path_prefix}/giocatori/statistiche.html'] = generate_giocatori_statistiche(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/radar.html'] = generate_giocatori_radar(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/consistenza.html'] = generate_giocatori_consistenza(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/simili.html'] = generate_giocatori_simili(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/forma.html'] = generate_giocatori_forma(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/casa-trasferta.html'] = generate_giocatori_casa_trasferta(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/distribuzione-tiri.html'] = generate_giocatori_distribuzione_tiri(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/impatto.html'] = generate_giocatori_impatto(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/clustering.html'] = generate_analisi_clustering(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/dipendenza.html'] = generate_analisi_dipendenza(camp_filter, camp_name)
            pages[f'{path_prefix}/giocatori/momenti-decisivi.html'] = generate_partite_momenti_decisivi(camp_filter, camp_name)

            # Pagine squadra aggiuntive
            pages[f'{path_prefix}/squadre/quando-vince.html'] = generate_analisi_quando_vince(camp_filter, camp_name)
            pages[f'{path_prefix}/squadre/andamento.html'] = generate_partite_andamento(camp_filter, camp_name)

        except Exception as e:
            print(f"  Errore per {camp_name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    return pages


def get_site_stats():
    """Calcola statistiche riassuntive per la homepage."""
    stats = {
        'total_games': 0,
        'total_players': 0,
        'total_teams': 0,
        'a2_teams': 0,
        'a2_players': 0,
        'ba_teams': 0,
        'ba_players': 0,
        'bb_teams': 0,
        'bb_players': 0,
    }

    for camp, prefix in [('a2', 'a2'), ('b_a', 'ba'), ('b_b', 'bb')]:
        camp_stats = get_camp_stats(camp)
        stats[f'{prefix}_teams'] = camp_stats['teams']
        stats[f'{prefix}_players'] = camp_stats['players']
        stats['total_games'] += camp_stats['games']
        stats['total_players'] += camp_stats['players']
        stats['total_teams'] += camp_stats['teams']

    return stats
