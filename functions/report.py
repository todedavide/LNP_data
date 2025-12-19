"""
Modulo per la generazione di report HTML con grafici Plotly.
"""

import webbrowser


def generate_html_report(plots_with_captions, dropdown_plots=None, title="LNP Stats Report", teams=None):
    """
    Genera un report HTML con grafici Plotly.

    Args:
        plots_with_captions: lista di tuple (fig, caption, title)
        dropdown_plots: lista di tuple (fig, label) per il dropdown squadre
        title: titolo del report
        teams: lista delle squadre per il filtro globale

    Returns:
        stringa HTML del report
    """
    # Estrai lista squadre se non fornita
    if teams is None and plots_with_captions:
        teams = []
        fig = plots_with_captions[0][0]
        for trace in fig.data:
            if hasattr(trace, 'name') and trace.name:
                teams.append(trace.name)
        teams = sorted(set(teams))

    html_parts = [f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <link rel="icon" type="image/png" href="static/favicon180x180.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Roboto:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        :root {{
            --tp-primary: #00F95B;
            --tp-secondary: #302B8F;
            --tp-dark: #18205E;
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Roboto', 'Segoe UI', sans-serif;
            max-width: 1600px;
            margin: 0 auto;
            padding: 10px;
            background: #f5f5f5;
        }}
        h1 {{
            font-family: 'Poppins', sans-serif;
            color: var(--tp-secondary);
            text-align: center;
            margin: 10px 0 20px 0;
        }}
        .header-logo {{
            display: flex;
            justify-content: center;
            margin-bottom: 10px;
        }}
        .header-logo img {{
            height: 50px;
        }}
        .filter-bar {{
            position: sticky;
            top: 0;
            background: white;
            padding: 12px 15px;
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            z-index: 1000;
        }}
        .filter-header {{
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 10px;
        }}
        .filter-header label {{
            font-weight: bold;
            color: #333;
        }}
        .filter-header .reset-btn {{
            padding: 6px 14px;
            background: var(--tp-secondary);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 13px;
        }}
        .filter-header .reset-btn:hover {{
            background: var(--tp-dark);
        }}
        .team-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .team-btn {{
            padding: 5px 10px;
            font-size: 12px;
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
        .plot-container {{
            background: white;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .plot-title {{
            font-family: 'Poppins', sans-serif;
            font-size: 16px;
            font-weight: 600;
            color: var(--tp-secondary);
            margin: 0 0 5px 10px;
        }}
        .caption {{
            color: #666;
            font-size: 13px;
            margin-top: 5px;
            padding: 8px 10px;
            background: #f9f9f9;
            border-left: 3px solid var(--tp-primary);
        }}
        .team-section {{
            background: white;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .team-section h2 {{
            font-family: 'Poppins', sans-serif;
            color: var(--tp-secondary);
            margin: 0 0 10px 10px;
            font-size: 18px;
        }}
        .team-plot {{
            display: none;
            margin-bottom: 10px;
        }}
        .team-plot.active {{
            display: block;
        }}
        .team-select-container {{
            margin: 0 0 10px 10px;
        }}
        .team-plots-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .team-plots-grid .team-plot.active {{
            flex: 1 1 calc(50% - 10px);
            min-width: 600px;
        }}
        .no-selection-msg {{
            color: #666;
            font-style: italic;
            padding: 20px;
            text-align: center;
            display: block;
        }}
        .no-selection-msg.hidden {{
            display: none;
        }}
    </style>
</head>
<body>
    <div class="header-logo">
        <img src="static/twinplay_one_row.svg" alt="TwinPlay">
    </div>
    <h1>{title}</h1>

    <div class="filter-bar">
        <div class="filter-header">
            <label>Filtra squadre:</label>
            <button class="reset-btn" onclick="resetFilter()">Mostra tutte</button>
        </div>
        <div class="team-buttons">
''']

    # Aggiungi pulsanti squadre
    if teams:
        for team in teams:
            html_parts.append(f'            <button class="team-btn" data-team="{team}" onclick="toggleTeam(this)">{team}</button>\n')

    html_parts.append('''        </div>
    </div>
''')

    # Grafici principali con caption e titolo
    for i, item in enumerate(plots_with_captions):
        if len(item) == 3:
            fig, caption, plot_title = item
        else:
            fig, caption = item
            plot_title = ""

        fig.update_layout(
            height=700,
            margin=dict(l=50, r=50, t=30, b=50)
        )
        plot_html = fig.to_html(full_html=False, include_plotlyjs=False)

        title_html = f'<div class="plot-title">{plot_title}</div>' if plot_title else ''
        html_parts.append(f'''
    <div class="plot-container filterable-plot">
        {title_html}
        {plot_html}
        <div class="caption">{caption}</div>
    </div>
''')

    # Sezione grafici per squadra
    if dropdown_plots:
        html_parts.append('''
    <div class="team-section">
        <h2>Dettaglio per Squadra</h2>
        <p class="no-selection-msg" id="no-team-msg">Seleziona una o più squadre dai pulsanti sopra per vedere il dettaglio giocatori</p>
        <div class="team-plots-grid">
''')

        for i, (fig, label) in enumerate(dropdown_plots):
            fig.update_layout(
                height=450,
                margin=dict(l=50, r=50, t=30, b=50),
                title=dict(text=label, font=dict(size=14))
            )
            plot_html = fig.to_html(full_html=False, include_plotlyjs=False)
            html_parts.append(f'''
            <div id="team-{i}" class="team-plot" data-team="{label}">
                {plot_html}
            </div>
''')

        html_parts.append('        </div>\n    </div>\n')

    html_parts.append('''
    <script>
        // Set per tenere traccia delle squadre selezionate
        let selectedTeams = new Set();

        function toggleTeam(btn) {
            const team = btn.dataset.team;

            if (selectedTeams.has(team)) {
                selectedTeams.delete(team);
                btn.classList.remove('active');
            } else {
                selectedTeams.add(team);
                btn.classList.add('active');
            }

            updateAllPlots();
            updateTeamDetailPlots();
        }

        function resetFilter() {
            selectedTeams.clear();
            document.querySelectorAll('.team-btn').forEach(btn => btn.classList.remove('active'));
            updateAllPlots();
            updateTeamDetailPlots();
        }

        function updateAllPlots() {
            // Filtra i grafici principali (scatter plots)
            const filterablePlots = document.querySelectorAll('.filterable-plot .plotly-graph-div');

            filterablePlots.forEach(plotDiv => {
                const plotData = plotDiv.data;
                if (!plotData) return;

                const visibility = plotData.map(trace => {
                    // Se nessuna squadra selezionata, mostra tutto
                    if (selectedTeams.size === 0) {
                        return true;
                    }
                    return selectedTeams.has(trace.name);
                });

                Plotly.restyle(plotDiv, {'visible': visibility});
            });
        }

        function updateTeamDetailPlots() {
            // Mostra/nascondi i grafici dettaglio per squadra
            const teamPlots = document.querySelectorAll('.team-plot');
            const noSelectionMsg = document.getElementById('no-team-msg');

            if (selectedTeams.size === 0) {
                // Nessuna selezione: nascondi tutti, mostra messaggio
                teamPlots.forEach(plot => plot.classList.remove('active'));
                if (noSelectionMsg) noSelectionMsg.classList.remove('hidden');
            } else {
                // Mostra solo le squadre selezionate
                if (noSelectionMsg) noSelectionMsg.classList.add('hidden');
                teamPlots.forEach(plot => {
                    const team = plot.dataset.team;
                    if (selectedTeams.has(team)) {
                        plot.classList.add('active');
                    } else {
                        plot.classList.remove('active');
                    }
                });
            }
        }
    </script>
</body>
</html>
''')

    return ''.join(html_parts)


def save_report(html_content, filename, open_browser=True):
    """
    Salva il report HTML su file e opzionalmente lo apre nel browser.

    Args:
        html_content: stringa HTML
        filename: nome del file di output
        open_browser: se True, apre il report nel browser
    """
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Report salvato: {filename}")

    if open_browser:
        webbrowser.open(filename)
