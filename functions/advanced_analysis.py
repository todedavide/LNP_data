"""
Modulo per analisi statistiche avanzate.

Include:
- Radar chart per confronto giocatori
- Radar chart per confronto squadre
- Metriche di consistenza (std, CV)
- Forma recente (ultime 5 partite vs media)
- Home vs Away
- Dipendenza squadra (concentrazione punti)
- Shot distribution (2PT vs 3PT)
- Correlazioni e Feature Importance
- Decision Tree
- Similarità giocatori
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors


# Statistiche per il radar chart giocatori (medie per partita)
RADAR_STATS = [
    ('PT_pergame', 'Punti'),
    ('AS_pergame', 'Assist'),
    ('RT_pergame', 'Rimbalzi'),
    ('PR_pergame', 'Recuperi'),
    ('ST_pergame', 'Stoppate'),
    ('True_shooting', 'Efficienza'),
]

# Statistiche per il radar chart squadre
TEAM_RADAR_STATS = [
    ('PT', 'Punti'),
    ('AS', 'Assist'),
    ('RT', 'Rimbalzi'),
    ('PR', 'Recuperi'),
    ('ST', 'Stoppate'),
    ('2PT_%', 'Tiro 2PT'),
    ('3PT_%', 'Tiro 3PT'),
]

# Statistiche per la consistenza
CONSISTENCY_STATS = [
    ('PT', 'Punti', 'pt'),
    ('AS', 'Assist', 'as'),
    ('RT', 'Rimbalzi', 'rt'),
    ('pm_permin', 'Plus/Minus per min', 'pm'),
]


def compute_consistency_metrics(overall_df, min_games=5):
    """
    Calcola metriche di consistenza per ogni giocatore.
    """
    results = []

    for (player, team), group in overall_df.groupby(['Giocatore', 'Team']):
        if len(group) < min_games:
            continue

        row = {
            'Giocatore': player,
            'Team': team,
            'Partite': len(group),
            'MinutiTot': group['Minutes'].sum(),
        }

        for stat_col, stat_name, stat_id in CONSISTENCY_STATS:
            if stat_col not in group.columns:
                continue

            values = group[stat_col].dropna()
            if len(values) < min_games:
                continue

            mean_val = values.mean()
            std_val = values.std()

            if stat_col == 'pm_permin' or mean_val == 0:
                cv = std_val * 100
            else:
                cv = (std_val / abs(mean_val) * 100)

            row[f'{stat_col}_mean'] = mean_val
            row[f'{stat_col}_std'] = std_val
            row[f'{stat_col}_cv'] = cv

        results.append(row)

    df = pd.DataFrame(results)

    for stat_col, stat_name, stat_id in CONSISTENCY_STATS:
        cv_col = f'{stat_col}_cv'
        if cv_col in df.columns:
            valid_cv = df[cv_col].dropna()
            if len(valid_cv) > 0:
                df[f'{stat_col}_consistency'] = df[cv_col].apply(
                    lambda x: 100 - stats.percentileofscore(valid_cv, x, kind='rank')
                    if pd.notna(x) else np.nan
                )

    return df


def compute_recent_form(overall_df, n_recent=5, min_games=8):
    """
    Calcola la forma recente: media ultime N partite vs media stagione.

    Returns:
        DataFrame con colonne: Giocatore, Team, PT_season, PT_recent, PT_diff, ...
    """
    results = []

    # Ordina per data se disponibile, altrimenti assume ordine cronologico
    if 'Data' in overall_df.columns:
        overall_df = overall_df.sort_values('Data')

    for (player, team), group in overall_df.groupby(['Giocatore', 'Team']):
        if len(group) < min_games:
            continue

        # Ultime n partite
        recent = group.tail(n_recent)

        row = {
            'Giocatore': player,
            'Team': team,
            'Partite': len(group),
        }

        # Statistiche da confrontare
        for stat in ['PT', 'AS', 'RT']:
            if stat not in group.columns:
                continue
            season_avg = group[stat].mean()
            recent_avg = recent[stat].mean()
            diff = recent_avg - season_avg
            diff_pct = (diff / season_avg * 100) if season_avg > 0 else 0

            row[f'{stat}_season'] = season_avg
            row[f'{stat}_recent'] = recent_avg
            row[f'{stat}_diff'] = diff
            row[f'{stat}_diff_pct'] = diff_pct

        results.append(row)

    return pd.DataFrame(results)


def create_form_chart(form_df, stat='PT', top_n=20):
    """
    Crea grafico della forma recente: chi è in crescita/calo.
    """
    diff_col = f'{stat}_diff'
    season_col = f'{stat}_season'
    recent_col = f'{stat}_recent'

    if diff_col not in form_df.columns:
        return None

    # Filtra giocatori con almeno 8 punti di media (evita rumore)
    df = form_df[form_df[season_col] >= 5].copy()

    # Prendi i più caldi e i più freddi
    hot = df.nlargest(top_n // 2, diff_col)
    cold = df.nsmallest(top_n // 2, diff_col)
    df = pd.concat([hot, cold]).drop_duplicates()
    df = df.sort_values(diff_col, ascending=True)

    # Colori: verde se positivo, rosso se negativo
    colors = ['#22c55e' if d > 0 else '#ef4444' for d in df[diff_col]]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df[diff_col],
        y=[f"{row['Giocatore']} ({row['Team'][:3]})" for _, row in df.iterrows()],
        orientation='h',
        marker_color=colors,
        text=[f"{d:+.1f}" for d in df[diff_col]],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Stagione: %{customdata[0]:.1f}<br>Ultime 5: %{customdata[1]:.1f}<br>Diff: %{x:+.1f}<extra></extra>',
        customdata=df[[season_col, recent_col]].values,
    ))

    fig.update_layout(
        height=max(400, len(df) * 25),
        xaxis_title='Differenza punti (ultime 5 vs stagione)',
        yaxis_title='',
        margin=dict(l=180, r=50, t=30, b=50),
        xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='gray'),
    )

    return fig


def compute_home_away_splits(overall_df, min_games=3):
    """
    Calcola differenze casa/trasferta per ogni giocatore.
    Usa Gap medio per partita come proxy: Gap positivo = casa, negativo = trasferta.
    """
    results = []

    # Prima calcola il Gap medio per partita (Team, Opponent, Gap)
    game_gaps = overall_df.groupby(['Team', 'Opponent', 'Gap']).size().reset_index()[['Team', 'Opponent', 'Gap']]

    # Crea un mapping partita -> location basato sul Gap
    # Se Gap > 0, probabilmente in casa. Se Gap < 0, probabilmente in trasferta.
    overall_df = overall_df.copy()
    overall_df['Location'] = overall_df['Gap'].apply(lambda x: 'H' if x > 0 else 'A')

    for (player, team), group in overall_df.groupby(['Giocatore', 'Team']):
        home = group[group['Location'] == 'H']
        away = group[group['Location'] == 'A']

        if len(home) < min_games or len(away) < min_games:
            continue

        row = {
            'Giocatore': player,
            'Team': team,
            'G_casa': len(home),
            'G_trasf': len(away),
        }

        for stat in ['PT', 'AS', 'RT', 'Minutes']:
            if stat not in group.columns:
                continue
            home_avg = home[stat].mean()
            away_avg = away[stat].mean()
            diff = home_avg - away_avg

            row[f'{stat}_casa'] = home_avg
            row[f'{stat}_trasf'] = away_avg
            row[f'{stat}_diff'] = diff

        results.append(row)

    return pd.DataFrame(results)


def create_home_away_chart(ha_df, stat='PT', top_n=25):
    """
    Crea grafico differenze casa/trasferta.
    """
    diff_col = f'{stat}_diff'
    casa_col = f'{stat}_casa'
    trasf_col = f'{stat}_trasf'

    if diff_col not in ha_df.columns or len(ha_df) == 0:
        return None

    # Ordina per differenza assoluta
    df = ha_df.copy()
    df['abs_diff'] = df[diff_col].abs()
    df = df.nlargest(top_n, 'abs_diff')
    df = df.sort_values(diff_col, ascending=True)

    # Colori
    colors = ['#302B8F' if d > 0 else '#f97316' for d in df[diff_col]]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df[diff_col],
        y=[f"{row['Giocatore']} ({row['Team'][:3]})" for _, row in df.iterrows()],
        orientation='h',
        marker_color=colors,
        text=[f"{d:+.1f}" for d in df[diff_col]],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Casa: %{customdata[0]:.1f}<br>Trasferta: %{customdata[1]:.1f}<br>Diff: %{x:+.1f}<extra></extra>',
        customdata=df[[casa_col, trasf_col]].values,
    ))

    fig.update_layout(
        height=max(400, len(df) * 22),
        xaxis_title=f'Differenza {stat} (Casa - Trasferta)',
        yaxis_title='',
        margin=dict(l=180, r=50, t=30, b=50),
        xaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor='gray'),
    )

    # Aggiungi annotazioni
    fig.add_annotation(
        x=df[diff_col].max() * 0.8, y=1.02, yref='paper',
        text="Meglio in casa", showarrow=False,
        font=dict(color='#302B8F', size=11)
    )
    fig.add_annotation(
        x=df[diff_col].min() * 0.8, y=1.02, yref='paper',
        text="Meglio in trasferta", showarrow=False,
        font=dict(color='#f97316', size=11)
    )

    return fig


def compute_team_dependency(overall_df, player_stats):
    """
    Calcola quanto ogni squadra dipende dai top scorer (punti e minuti).
    """
    results = []

    for team in overall_df['Team'].unique():
        team_players = player_stats[player_stats['Team'] == team].copy()
        if len(team_players) < 3:
            continue

        # === PUNTI ===
        team_by_pts = team_players.sort_values('PT', ascending=False)
        total_pts = team_by_pts['PT'].sum()
        if total_pts == 0:
            continue

        top1_pts = team_by_pts.iloc[0]['PT']
        top2_pts = team_by_pts.iloc[:2]['PT'].sum()
        top3_pts = team_by_pts.iloc[:3]['PT'].sum()

        # === MINUTI ===
        team_by_min = team_players.sort_values('Minutes', ascending=False)
        total_min = team_by_min['Minutes'].sum()

        top1_min = team_by_min.iloc[0]['Minutes']
        top2_min = team_by_min.iloc[:2]['Minutes'].sum()
        top3_min = team_by_min.iloc[:3]['Minutes'].sum()

        results.append({
            'Team': team,
            'Giocatori': len(team_players),
            # Punti
            'PT_totali': total_pts,
            'PT_Top1_nome': team_by_pts.iloc[0]['Giocatore'],
            'PT_Top2_nome': team_by_pts.iloc[1]['Giocatore'] if len(team_by_pts) >= 2 else '',
            'PT_Top3_nome': team_by_pts.iloc[2]['Giocatore'] if len(team_by_pts) >= 3 else '',
            'PT_Top1_pct': top1_pts / total_pts * 100,
            'PT_Top2_pct': top2_pts / total_pts * 100,
            'PT_Top3_pct': top3_pts / total_pts * 100,
            'PT_Altri_pct': (total_pts - top3_pts) / total_pts * 100,
            # Minuti
            'MIN_totali': total_min,
            'MIN_Top1_nome': team_by_min.iloc[0]['Giocatore'],
            'MIN_Top2_nome': team_by_min.iloc[1]['Giocatore'] if len(team_by_min) >= 2 else '',
            'MIN_Top3_nome': team_by_min.iloc[2]['Giocatore'] if len(team_by_min) >= 3 else '',
            'MIN_Top1_pct': top1_min / total_min * 100 if total_min > 0 else 0,
            'MIN_Top2_pct': top2_min / total_min * 100 if total_min > 0 else 0,
            'MIN_Top3_pct': top3_min / total_min * 100 if total_min > 0 else 0,
            'MIN_Altri_pct': (total_min - top3_min) / total_min * 100 if total_min > 0 else 0,
        })

    return pd.DataFrame(results)


def create_dependency_chart(dep_df, stat_type='PT'):
    """
    Crea grafico della dipendenza squadra dai top scorer.

    Args:
        dep_df: DataFrame con dati dipendenza
        stat_type: 'PT' per punti, 'MIN' per minuti
    """
    if len(dep_df) == 0:
        return None

    # Prefisso colonne
    prefix = stat_type
    top1_col = f'{prefix}_Top1_pct'
    top2_col = f'{prefix}_Top2_pct'
    top3_col = f'{prefix}_Top3_pct'
    altri_col = f'{prefix}_Altri_pct'
    top1_nome = f'{prefix}_Top1_nome'
    top2_nome = f'{prefix}_Top2_nome'
    top3_nome = f'{prefix}_Top3_nome'

    df = dep_df.sort_values(top1_col, ascending=True)

    fig = go.Figure()

    # Stacked bar: Top1, Top2-1, Top3-2, Altri
    fig.add_trace(go.Bar(
        y=df['Team'],
        x=df[top1_col],
        name='1°',
        orientation='h',
        marker_color='#302B8F',
        text=[f"{' '.join(row[top1_nome].split()[1:])}: {row[top1_col]:.0f}%" for _, row in df.iterrows()],
        textposition='inside',
        insidetextanchor='middle',
    ))

    fig.add_trace(go.Bar(
        y=df['Team'],
        x=df[top2_col] - df[top1_col],
        name='2°',
        orientation='h',
        marker_color='#00F95B',
        text=[f"{' '.join(row[top2_nome].split()[1:])}: {row[top2_col] - row[top1_col]:.0f}%" for _, row in df.iterrows()],
        textposition='inside',
        insidetextanchor='middle',
    ))

    fig.add_trace(go.Bar(
        y=df['Team'],
        x=df[top3_col] - df[top2_col],
        name='3°',
        orientation='h',
        marker_color='#60a5fa',
        text=[f"{' '.join(row[top3_nome].split()[1:])}: {row[top3_col] - row[top2_col]:.0f}%" for _, row in df.iterrows()],
        textposition='inside',
        insidetextanchor='middle',
    ))

    fig.add_trace(go.Bar(
        y=df['Team'],
        x=df[altri_col],
        name='Altri',
        orientation='h',
        marker_color='#d1d5db',
    ))

    stat_label = 'punti' if stat_type == 'PT' else 'minuti'
    fig.update_layout(
        barmode='stack',
        height=max(400, len(df) * 28),
        xaxis_title=f'% {stat_label} squadra',
        yaxis_title='',
        margin=dict(l=150, r=50, t=30, b=50),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        xaxis=dict(range=[0, 100], ticksuffix='%'),
    )

    return fig


def compute_team_stats(overall_df):
    """
    Calcola statistiche aggregate per squadra (per partita).
    """
    # Controlla quali colonne esistono
    agg_cols = {
        'PT': 'sum',
        'AS': 'sum',
        'RT': 'sum',
        'RO': 'sum',
        'RD': 'sum',
        'PR': 'sum',
        'ST': 'sum',
    }

    # Aggiungi colonne tiro se esistono
    if '2PTM' in overall_df.columns:
        agg_cols['2PTM'] = 'sum'
        agg_cols['2PTA'] = 'sum'
    if '3PTM' in overall_df.columns:
        agg_cols['3PTM'] = 'sum'
        agg_cols['3PTA'] = 'sum'
    if 'FTM' in overall_df.columns:
        agg_cols['FTM'] = 'sum'
        agg_cols['FTA'] = 'sum'

    # Raggruppa per squadra e partita, poi media
    team_game = overall_df.groupby(['Team', 'Opponent', 'Gap']).agg(agg_cols).reset_index()

    # Media per partita
    team_stats = team_game.groupby('Team').mean(numeric_only=True).reset_index()

    # Calcola percentuali
    if '2PTM' in team_stats.columns and '2PTA' in team_stats.columns:
        team_stats['2PT_%'] = team_stats['2PTM'] / team_stats['2PTA'] * 100
    if '3PTM' in team_stats.columns and '3PTA' in team_stats.columns:
        team_stats['3PT_%'] = team_stats['3PTM'] / team_stats['3PTA'] * 100
    if 'FTM' in team_stats.columns and 'FTA' in team_stats.columns:
        team_stats['FT_%'] = team_stats['FTM'] / team_stats['FTA'] * 100

    return team_stats


def create_team_radar_chart(team_stats, team_names, title="Confronto Squadre"):
    """
    Crea radar chart per confrontare squadre.
    """
    teams_df = team_stats[team_stats['Team'].isin(team_names)].copy()

    if len(teams_df) == 0:
        return None

    categories = [name for _, name in TEAM_RADAR_STATS]

    fig = go.Figure()
    colors = ['#302B8F', '#00F95B', '#f97316', '#ef4444']

    for i, (_, team) in enumerate(teams_df.iterrows()):
        values = []
        for stat_col, _ in TEAM_RADAR_STATS:
            if stat_col not in team_stats.columns:
                values.append(50)
                continue
            all_values = team_stats[stat_col].dropna()
            team_val = team[stat_col]
            if pd.isna(team_val):
                pct = 50
            else:
                pct = stats.percentileofscore(all_values, team_val, kind='rank')
            values.append(pct)

        values.append(values[0])
        cats = categories + [categories[0]]

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=cats,
            fill='toself',
            fillcolor=colors[i % len(colors)].replace('#', 'rgba(') + ', 0.2)' if colors[i].startswith('#') else colors[i],
            line=dict(color=colors[i], width=2),
            name=team['Team']
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickvals=[25, 50, 75, 100],
                ticktext=['25%', '50%', '75%', '100%']
            )
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        height=500,
    )

    return fig


def compute_shot_distribution(player_stats):
    """
    Calcola distribuzione tiri per giocatore (2PT, 3PT, FT).
    """
    df = player_stats.copy()

    # Controlla nomi colonne
    att_2pt = '2PTA' if '2PTA' in df.columns else '2PT_att'
    att_3pt = '3PTA' if '3PTA' in df.columns else '3PT_att'
    att_ft = 'FTA' if 'FTA' in df.columns else 'FT_att'
    made_2pt = '2PTM' if '2PTM' in df.columns else '2PT_made'
    made_3pt = '3PTM' if '3PTM' in df.columns else '3PT_made'
    made_ft = 'FTM' if 'FTM' in df.columns else 'FT_made'

    # Copia le colonne con nomi standard
    if att_2pt in df.columns:
        df['2PT_att'] = df[att_2pt]
        df['2PT_made'] = df[made_2pt]
        df['2PT_eff'] = np.where(df['2PT_att'] > 0, df['2PT_made'] / df['2PT_att'] * 100, 0)
        df['2PT_exp'] = df['2PT_eff'] / 100 * 2

    if att_3pt in df.columns:
        df['3PT_att'] = df[att_3pt]
        df['3PT_made'] = df[made_3pt]
        df['3PT_eff'] = np.where(df['3PT_att'] > 0, df['3PT_made'] / df['3PT_att'] * 100, 0)
        df['3PT_exp'] = df['3PT_eff'] / 100 * 3

    if att_ft in df.columns:
        df['FT_att'] = df[att_ft]
        df['FT_made'] = df[made_ft]
        df['FT_eff'] = np.where(df['FT_att'] > 0, df['FT_made'] / df['FT_att'] * 100, 0)

    return df


def create_shot_chart(shot_df, shot_type='3PT', min_att=15, top_n=40):
    """
    Crea scatter plot: efficienza (X) vs tiri/min (Y), size=volume.
    """
    att_col = f'{shot_type}_att'
    made_col = f'{shot_type}_made'
    eff_col = f'{shot_type}_eff'

    if att_col not in shot_df.columns or 'Minutes' not in shot_df.columns:
        return None

    # Filtra per tentativi minimi
    df = shot_df[shot_df[att_col] >= min_att].copy()
    if len(df) == 0:
        return None

    # Calcola tiri per minuto
    df['att_permin'] = df[att_col] / df['Minutes']

    df = df.nlargest(top_n, att_col)

    # Normalizza size per visualizzazione (range 8-30)
    min_att_val, max_att_val = df[att_col].min(), df[att_col].max()
    if max_att_val > min_att_val:
        df['marker_size'] = 8 + (df[att_col] - min_att_val) / (max_att_val - min_att_val) * 22
    else:
        df['marker_size'] = 15

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['att_permin'],
        y=df[eff_col],
        mode='markers',
        marker=dict(
            size=df['marker_size'],
            color=df[eff_col],
            colorscale='RdYlGn',
            showscale=True,
            colorbar=dict(title='Eff %'),
            line=dict(width=1, color='white'),
        ),
        text=df['Giocatore'],
        customdata=np.stack([df['Team'], df[made_col], df[att_col], df[eff_col], df['att_permin']], axis=-1),
        hovertemplate='<b>%{text}</b><br>' +
                      'Team: %{customdata[0]}<br>' +
                      'Realizzati: %{customdata[1]:.0f}/%{customdata[2]:.0f}<br>' +
                      'Efficienza: %{customdata[3]:.1f}%<br>' +
                      'Tiri/min: %{customdata[4]:.2f}<extra></extra>',
    ))

    # Linee di riferimento
    avg_eff = df[eff_col].mean()
    avg_permin = df['att_permin'].mean()

    fig.add_vline(x=avg_permin, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_hline(y=avg_eff, line_dash="dash", line_color="gray", opacity=0.5,
                  annotation_text=f"Media: {avg_eff:.1f}%", annotation_position="top right")

    # Labels
    shot_labels = {'2PT': 'Tiri da 2', '3PT': 'Tiri da 3', 'FT': 'Tiri Liberi'}

    fig.update_layout(
        height=450,
        xaxis_title=f'{shot_labels.get(shot_type, shot_type)} per minuto',
        yaxis_title='Efficienza (%)',
        margin=dict(t=30, b=50),
    )

    return fig


def create_consistency_plot(consistency_df, stat='PT', stat_name='Punti', top_n=25):
    """
    Crea un grafico della consistenza per una statistica.
    """
    consistency_col = f'{stat}_consistency'
    mean_col = f'{stat}_mean'

    if consistency_col not in consistency_df.columns or mean_col not in consistency_df.columns:
        return None

    df = consistency_df.dropna(subset=[consistency_col, mean_col]).copy()
    df = df.nlargest(top_n, mean_col)
    df = df.sort_values(consistency_col, ascending=True)

    colors = ['#22c55e' if score >= 70 else '#eab308' if score >= 40 else '#ef4444'
              for score in df[consistency_col]]

    # Testo: media | consistenza
    bar_text = [f"{row[mean_col]:.1f} avg | {row[consistency_col]:.0f} cons"
                for _, row in df.iterrows()]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df[consistency_col],
            y=df['Giocatore'],
            orientation='h',
            marker_color=colors,
            text=bar_text,
            textposition='outside',
            customdata=np.stack([df[mean_col], df[consistency_col]], axis=-1),
            hovertemplate='<b>%{y}</b><br>Media: %{customdata[0]:.1f}<br>Consistenza: %{customdata[1]:.0f}/100<extra></extra>'
        )
    )

    fig.update_layout(
        height=max(450, top_n * 22),
        showlegend=False,
        xaxis=dict(
            title='Punteggio Consistenza (0-100)',
            range=[0, 105],
            tickvals=[0, 25, 50, 75, 100],
        ),
        yaxis=dict(title=''),
        margin=dict(l=150, r=50, t=30, b=50),
    )

    return fig


# ========== CORRELAZIONI E ANALISI VITTORIA A LIVELLO SQUADRA ==========

def compute_team_game_stats(overall_df):
    """
    Aggrega statistiche a livello squadra per ogni partita.
    Include anche statistiche degli avversari.
    """
    # Parse tiri da colonne formato "made/attempted"
    df = overall_df.copy()

    def parse_shots(val):
        if pd.isna(val) or val == '':
            return 0, 0
        parts = str(val).split('/')
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except:
                return 0, 0
        return 0, 0

    # Crea colonne made/attempted se non esistono
    for shot_col, made_col, att_col in [('2PT', '2PTM', '2PTA'), ('3PT', '3PTM', '3PTA'), ('TL', 'FTM', 'FTA')]:
        if shot_col in df.columns and made_col not in df.columns:
            parsed = df[shot_col].apply(parse_shots)
            df[made_col] = parsed.apply(lambda x: x[0])
            df[att_col] = parsed.apply(lambda x: x[1])

    game_cols = ['Team', 'Opponent', 'Gap']
    stat_cols = ['PT', 'AS', 'RT', 'PR', 'ST', 'FF', '2PTM', '2PTA', '3PTM', '3PTA', 'FTM', 'FTA']
    stat_cols = [c for c in stat_cols if c in df.columns]

    # Aggrega per partita (squadra)
    agg_dict = {col: 'sum' for col in stat_cols}
    if 'Result' in df.columns:
        agg_dict['Result'] = 'first'

    team_games = df.groupby(game_cols).agg(agg_dict).reset_index()

    # Calcola percentuali
    if '2PTA' in team_games.columns and team_games['2PTA'].sum() > 0:
        team_games['2PT_%'] = (team_games['2PTM'] / team_games['2PTA'] * 100).fillna(0)
    if '3PTA' in team_games.columns and team_games['3PTA'].sum() > 0:
        team_games['3PT_%'] = (team_games['3PTM'] / team_games['3PTA'] * 100).fillna(0)
    if 'FTA' in team_games.columns and team_games['FTA'].sum() > 0:
        team_games['FT_%'] = (team_games['FTM'] / team_games['FTA'] * 100).fillna(0)

    if 'Result' in team_games.columns:
        team_games['Win'] = team_games['Result'].astype(int)
    else:
        team_games['Win'] = (team_games['Gap'] > 0).astype(int)

    # Aggiungi statistiche avversari (lookup inverso)
    # Per ogni partita Team vs Opponent, trova la riga Opponent vs Team
    opp_cols = ['Team', 'Opponent', 'Gap', 'PT', 'AS', 'RT', 'PR', 'ST']
    if '3PTM' in team_games.columns:
        opp_cols.append('3PTM')

    opp_stats = team_games[[c for c in opp_cols if c in team_games.columns]].copy()

    # Rinomina per merge inverso
    rename_map = {'Team': 'Opponent', 'Opponent': 'Team', 'Gap': 'Gap_opp',
                  'PT': 'OPP_PT', 'AS': 'OPP_AS', 'RT': 'OPP_RT', 'PR': 'OPP_PR', 'ST': 'OPP_ST'}
    if '3PTM' in opp_stats.columns:
        rename_map['3PTM'] = 'OPP_3PTM'
    opp_stats = opp_stats.rename(columns=rename_map)
    opp_stats['Gap_opp'] = -opp_stats['Gap_opp']  # Inverti il gap

    # Merge usando anche il Gap (che è stato invertito) per evitare duplicati
    team_games = team_games.merge(
        opp_stats,
        left_on=['Team', 'Opponent', 'Gap'],
        right_on=['Team', 'Opponent', 'Gap_opp'],
        how='left',
        suffixes=('', '_opp')
    )

    return team_games


def compute_win_correlations(team_games):
    """
    Calcola correlazioni delle statistiche squadra con la vittoria.
    """
    # Escludo Gap - ovvio che correli con vittoria
    corr_cols = ['PT', 'AS', 'RT', 'PR', 'ST', '2PT_%', '3PT_%', 'FT_%', '3PTM']
    corr_cols = [c for c in corr_cols if c in team_games.columns]

    correlations = {}
    for col in corr_cols:
        valid = team_games[[col, 'Win']].dropna()
        if len(valid) > 10:
            corr = valid[col].corr(valid['Win'])
            correlations[col] = corr

    return pd.DataFrame([
        {'Statistica': k, 'Correlazione': v}
        for k, v in sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)
    ])


def create_win_correlation_chart(corr_df):
    """
    Crea grafico delle correlazioni con la vittoria.
    """
    if corr_df is None or len(corr_df) == 0:
        return None

    labels = {
        'PT': 'Punti Squadra', 'AS': 'Assist Squadra', 'RT': 'Rimbalzi Squadra',
        'PR': 'Recuperi Squadra', 'ST': 'Stoppate Squadra', 'Gap': 'Margine Punti',
        '2PT_%': '% Tiro da 2', '3PT_%': '% Tiro da 3', 'FT_%': '% Tiri Liberi',
        '3PTM': 'Triple Segnate'
    }

    df = corr_df.copy()
    df['Label'] = df['Statistica'].map(lambda x: labels.get(x, x))
    df = df.sort_values('Correlazione', ascending=True)

    colors = ['#22c55e' if c > 0 else '#ef4444' for c in df['Correlazione']]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df['Correlazione'],
        y=df['Label'],
        orientation='h',
        marker_color=colors,
        text=[f'{v:+.2f}' for v in df['Correlazione']],
        textposition='outside',
    ))

    fig.add_vline(x=0, line_color="gray", line_width=2)

    fig.update_layout(
        height=max(300, len(df) * 35),
        xaxis_title='Correlazione con Vittoria',
        yaxis_title='',
        margin=dict(l=150, r=60, t=30, b=50),
        xaxis=dict(range=[-1, 1]),
    )

    return fig


def compute_win_vs_loss_diff_by_team(team_games):
    """
    Calcola differenze medie tra vittorie e sconfitte PER OGNI SQUADRA.
    Include statistiche proprie E degli avversari, ordinate per influenza.
    """
    # Statistiche proprie e avversari
    own_stats = ['PT', 'AS', 'RT', 'PR', 'ST', '3PTM']
    opp_stats = ['OPP_PT', 'OPP_AS', 'OPP_RT', 'OPP_PR', 'OPP_ST', 'OPP_3PTM']

    team_diffs = {}

    for team in team_games['Team'].unique():
        team_data = team_games[team_games['Team'] == team]
        wins = team_data[team_data['Win'] == 1]
        losses = team_data[team_data['Win'] == 0]

        if len(wins) < 2 or len(losses) < 2:
            continue

        results = []

        # Statistiche proprie
        for col in own_stats:
            if col not in team_data.columns:
                continue
            win_mean = wins[col].mean()
            loss_mean = losses[col].mean()
            if pd.isna(win_mean) or pd.isna(loss_mean):
                continue
            diff = win_mean - loss_mean
            diff_pct = (diff / loss_mean * 100) if loss_mean != 0 else 0

            results.append({
                'Statistica': col,
                'Tipo': 'Noi',
                'Media Vittorie': round(win_mean, 1),
                'Media Sconfitte': round(loss_mean, 1),
                'Differenza': round(diff, 1),
                'Diff %': round(diff_pct, 1),
                'Influenza': abs(diff_pct)  # Per ordinamento
            })

        # Statistiche avversari
        for col in opp_stats:
            if col not in team_data.columns:
                continue
            win_mean = wins[col].mean()
            loss_mean = losses[col].mean()
            if pd.isna(win_mean) or pd.isna(loss_mean):
                continue
            diff = win_mean - loss_mean
            diff_pct = (diff / loss_mean * 100) if loss_mean != 0 else 0

            results.append({
                'Statistica': col.replace('OPP_', ''),
                'Tipo': 'Avversari',
                'Media Vittorie': round(win_mean, 1),
                'Media Sconfitte': round(loss_mean, 1),
                'Differenza': round(diff, 1),
                'Diff %': round(diff_pct, 1),
                'Influenza': abs(diff_pct)
            })

        # Ordina per influenza (differenza % assoluta)
        results = sorted(results, key=lambda x: x['Influenza'], reverse=True)

        team_diffs[team] = {
            'data': results,
            'n_wins': len(wins),
            'n_losses': len(losses),
            'win_rate': round(len(wins) / len(team_data) * 100, 1)
        }

    return team_diffs


# ========== DECISION TREE PER SQUADRA (STATISTICHE DI SQUADRA) ==========

def compute_team_game_rules(team_games, min_games=10):
    """
    Per ogni squadra, trova quali STATISTICHE DI SQUADRA (nostre + avversari) predicono la vittoria.
    Es: "Vince quando segna >80pt" o "quando avversari fanno <10 assist"
    """
    team_rules = {}

    # Feature da usare: nostre + avversari
    own_features = ['PT', 'AS', 'RT', 'PR', 'ST', '3PTM']
    opp_features = ['OPP_PT', 'OPP_AS', 'OPP_RT', 'OPP_PR', 'OPP_ST', 'OPP_3PTM']

    for team in team_games['Team'].unique():
        team_data = team_games[team_games['Team'] == team].copy()

        n_games = len(team_data)
        if n_games < min_games:
            continue

        # Prepara features
        available_features = [f for f in own_features + opp_features if f in team_data.columns]
        X = team_data[available_features].fillna(0)
        y = team_data['Win'].astype(int)

        if len(y.unique()) < 2:  # Serve almeno una vittoria e una sconfitta
            continue

        # Train decision tree
        dt = DecisionTreeClassifier(max_depth=3, random_state=42, min_samples_leaf=3)
        try:
            dt.fit(X, y)
        except Exception:
            continue

        team_win_rate = y.mean()

        # Estrai regole
        rules = extract_team_stat_rules(dt, available_features, team_win_rate)

        if rules:
            team_rules[team] = {
                'rules': rules,
                'n_games': n_games,
                'win_rate': team_win_rate
            }

    return team_rules


def extract_team_stat_rules(tree, feature_names, team_win_rate):
    """
    Estrae regole con statistiche di squadra in formato COPPIA (≤ vs >).
    """
    tree_ = tree.tree_

    labels = {
        'PT': ('Punti', 'fatti'),
        'AS': ('Assist', 'fatti'),
        'RT': ('Rimbalzi', 'fatti'),
        'PR': ('Recuperi', 'fatti'),
        'ST': ('Stoppate', 'fatte'),
        '3PTM': ('Triple', 'fatte'),
        'OPP_PT': ('Punti', 'subiti'),
        'OPP_AS': ('Assist', 'subiti'),
        'OPP_RT': ('Rimbalzi', 'subiti'),
        'OPP_PR': ('Recuperi', 'subiti'),
        'OPP_ST': ('Stoppate', 'subite'),
        'OPP_3PTM': ('Triple', 'subite'),
    }

    paired_rules = []

    def extract_pairs(node, parent_conditions=None, depth=0):
        if depth > 1:
            return

        if tree_.feature[node] == -2:
            return

        fname = feature_names[tree_.feature[node]]
        threshold = tree_.threshold[node]
        stat_name, who = labels.get(fname, (fname, ''))

        left_node = tree_.children_left[node]
        right_node = tree_.children_right[node]

        def get_leaf_stats(n):
            if tree_.feature[n] == -2:
                samples = tree_.n_node_samples[n]
                value = tree_.value[n][0]
                win_prob = value[1] / sum(value) if sum(value) > 0 else 0
                return samples, win_prob
            else:
                l_samples, l_prob = get_leaf_stats(tree_.children_left[n])
                r_samples, r_prob = get_leaf_stats(tree_.children_right[n])
                total = l_samples + r_samples
                if total > 0:
                    avg_prob = (l_samples * l_prob + r_samples * r_prob) / total
                else:
                    avg_prob = 0
                return total, avg_prob

        left_samples, left_prob = get_leaf_stats(left_node)
        right_samples, right_prob = get_leaf_stats(right_node)

        diff = abs(left_prob - right_prob)

        if diff > 0.15 and left_samples >= 3 and right_samples >= 3:
            prefix = ""
            if parent_conditions:
                prefix = " E ".join(parent_conditions) + " → "

            paired_rules.append({
                'condition': f"{prefix}{stat_name} ({who})",
                'threshold': int(threshold),
                'stat': '',
                'who': who,
                'left_prob': left_prob,
                'left_samples': left_samples,
                'right_prob': right_prob,
                'right_samples': right_samples,
                'diff': diff
            })

        if parent_conditions is None:
            parent_conditions = []

        cond_text = f"{stat_name} ({who}) ≤{int(threshold)}"
        extract_pairs(left_node, parent_conditions + [cond_text], depth + 1)
        cond_text = f"{stat_name} ({who}) >{int(threshold)}"
        extract_pairs(right_node, parent_conditions + [cond_text], depth + 1)

    extract_pairs(0)

    # Ordina per differenza
    paired_rules = sorted(paired_rules, key=lambda x: x['diff'], reverse=True)[:5]

    return paired_rules


# ========== DECISION TREE PER GIOCATORI ==========

def compute_player_based_rules(overall_df, min_games=10):
    """
    Per ogni squadra, trova quali PERFORMANCE DEI GIOCATORI predicono la vittoria.
    Es: "Vince quando Rossi > 15 punti" o "quando Bianchi > 25 minuti"
    """
    team_rules = {}

    for team in overall_df['Team'].unique():
        team_data = overall_df[overall_df['Team'] == team].copy()

        # Trova partite uniche
        game_keys = team_data.groupby(['Opponent', 'Gap']).size().reset_index()[['Opponent', 'Gap']]
        n_games = len(game_keys)

        if n_games < min_games:
            continue

        # Prendi i top 5 giocatori per minuti
        player_minutes = team_data.groupby('Giocatore')['Minutes'].sum().sort_values(ascending=False)
        top_players = player_minutes.head(5).index.tolist()

        if len(top_players) < 3:
            continue

        # Pivot: una riga per partita, colonne = stats per giocatore
        game_stats = []
        for (opp, gap), game_df in team_data.groupby(['Opponent', 'Gap']):
            row = {'Opponent': opp, 'Gap': gap, 'Win': 1 if gap > 0 else 0}
            for player in top_players:
                p_data = game_df[game_df['Giocatore'] == player]
                if len(p_data) > 0:
                    row[f'{player}_PT'] = p_data['PT'].sum()
                    row[f'{player}_MIN'] = p_data['Minutes'].sum()
                else:
                    row[f'{player}_PT'] = 0
                    row[f'{player}_MIN'] = 0
            game_stats.append(row)

        game_df = pd.DataFrame(game_stats)

        if len(game_df) < min_games:
            continue

        # Features
        feature_cols = [c for c in game_df.columns if c.endswith('_PT') or c.endswith('_MIN')]
        X = game_df[feature_cols].fillna(0)
        y = game_df['Win']

        if len(y.unique()) < 2:
            continue

        # Decision tree
        dt = DecisionTreeClassifier(max_depth=3, random_state=42, min_samples_leaf=3)
        try:
            dt.fit(X, y)
        except Exception:
            continue

        team_win_rate = y.mean()

        # Estrai regole
        rules = extract_player_rules(dt, feature_cols, team_win_rate)

        if rules:
            team_rules[team] = {
                'rules': rules,
                'n_games': n_games,
                'win_rate': team_win_rate,
                'top_players': top_players
            }

    return team_rules


def extract_player_rules(tree, feature_names, team_win_rate):
    """
    Estrae regole con nomi giocatori in formato COPPIA (≤ vs >).
    """
    tree_ = tree.tree_

    paired_rules = []

    def extract_pairs(node, parent_conditions=None, depth=0):
        if depth > 1:
            return

        if tree_.feature[node] == -2:
            return

        fname = feature_names[tree_.feature[node]]
        threshold = tree_.threshold[node]

        # Parse nome: "Rossi Mario_PT" -> "Rossi Mario", "Punti"
        parts = fname.rsplit('_', 1)
        player_name = parts[0]
        stat_type = parts[1] if len(parts) > 1 else ''
        stat_label = 'punti' if stat_type == 'PT' else 'minuti' if stat_type == 'MIN' else stat_type

        # Usa nome completo
        short_name = player_name

        left_node = tree_.children_left[node]
        right_node = tree_.children_right[node]

        def get_leaf_stats(n):
            if tree_.feature[n] == -2:
                samples = tree_.n_node_samples[n]
                value = tree_.value[n][0]
                win_prob = value[1] / sum(value) if sum(value) > 0 else 0
                return samples, win_prob
            else:
                l_samples, l_prob = get_leaf_stats(tree_.children_left[n])
                r_samples, r_prob = get_leaf_stats(tree_.children_right[n])
                total = l_samples + r_samples
                if total > 0:
                    avg_prob = (l_samples * l_prob + r_samples * r_prob) / total
                else:
                    avg_prob = 0
                return total, avg_prob

        left_samples, left_prob = get_leaf_stats(left_node)
        right_samples, right_prob = get_leaf_stats(right_node)

        diff = abs(left_prob - right_prob)

        if diff > 0.15 and left_samples >= 3 and right_samples >= 3:
            prefix = ""
            if parent_conditions:
                prefix = " E ".join(parent_conditions) + " → "

            paired_rules.append({
                'condition': f"{prefix}{short_name}",
                'threshold': int(threshold),
                'stat': stat_label,
                'player': player_name,
                'left_prob': left_prob,
                'left_samples': left_samples,
                'right_prob': right_prob,
                'right_samples': right_samples,
                'diff': diff
            })

        if parent_conditions is None:
            parent_conditions = []

        cond_text = f"{short_name} ≤{int(threshold)} {stat_label}"
        extract_pairs(left_node, parent_conditions + [cond_text], depth + 1)
        cond_text = f"{short_name} >{int(threshold)} {stat_label}"
        extract_pairs(right_node, parent_conditions + [cond_text], depth + 1)

    extract_pairs(0)

    # Ordina per differenza
    paired_rules = sorted(paired_rules, key=lambda x: x['diff'], reverse=True)[:5]

    return paired_rules


# ========== SIMILARITÀ GIOCATORI ==========

SIMILARITY_STATS = ['PT', 'AS', 'RT', 'PR', 'ST', 'Minutes', '2PTM', '3PTM']


def compute_player_similarity(player_stats, n_neighbors=5, min_minutes=100):
    """
    Trova giocatori con profili statistici simili.
    Include anche il profilo statistico normalizzato per visualizzazione.
    """
    # Filtra giocatori con minuti sufficienti
    df = player_stats[player_stats['Minutes'] >= min_minutes].copy()

    if len(df) < n_neighbors + 1:
        return None

    # Seleziona features per similarità
    feature_cols = [c for c in SIMILARITY_STATS if c in df.columns]

    X = df[feature_cols].fillna(0).values

    # Normalizza
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Calcola percentili per profilo visivo
    profile_stats = ['PT', 'AS', 'RT', 'PR', 'ST']
    profile_stats = [s for s in profile_stats if s in df.columns]

    percentiles = {}
    for stat in profile_stats:
        vals = df[stat].values
        for i, v in enumerate(vals):
            pct = stats.percentileofscore(vals, v, kind='rank')
            if i not in percentiles:
                percentiles[i] = {}
            percentiles[i][stat] = round(pct, 0)

    # Nearest Neighbors
    nn = NearestNeighbors(n_neighbors=n_neighbors + 1, metric='cosine')
    nn.fit(X_scaled)

    distances, indices = nn.kneighbors(X_scaled)

    # Costruisci risultati
    results = []
    for i, row in df.reset_index(drop=True).iterrows():
        # Profilo del giocatore corrente
        player_profile = percentiles.get(i, {})

        similar_players = []
        for j, (dist, idx) in enumerate(zip(distances[i][1:], indices[i][1:])):  # Skip self
            similar_row = df.iloc[idx]
            similar_profile = percentiles.get(idx, {})

            similar_players.append({
                'name': similar_row['Giocatore'],
                'team': similar_row['Team'],
                'similarity': 1 - dist,
                'profile': similar_profile
            })

        results.append({
            'Giocatore': row['Giocatore'],
            'Team': row['Team'],
            'profile': player_profile,
            'similar': similar_players
        })

    return results


def generate_advanced_report(overall_df, player_stats, campionato):
    """
    Genera un report HTML con tutte le analisi avanzate.
    """
    import json

    # Calcola numero partite per giocatore da overall_df
    player_stats = player_stats.copy()
    game_counts = overall_df.groupby(['Giocatore', 'Team']).size().reset_index(name='Partite')
    player_stats = player_stats.merge(game_counts, on=['Giocatore', 'Team'], how='left')
    player_stats['Partite'] = player_stats['Partite'].fillna(1)  # fallback

    # Calcola medie per partita per radar giocatori
    for stat in ['PT', 'AS', 'RT', 'PR', 'ST']:
        if stat in player_stats.columns:
            player_stats[f'{stat}_pergame'] = player_stats[stat] / player_stats['Partite']

    # True shooting % (se non già presente)
    if 'True_shooting' not in player_stats.columns:
        if '2PTA' in player_stats.columns and '3PTA' in player_stats.columns and 'FTA' in player_stats.columns:
            tsa = player_stats['2PTA'] + player_stats['3PTA'] + 0.44 * player_stats['FTA']
            player_stats['True_shooting'] = np.where(tsa > 0, player_stats['PT'] / (2 * tsa), 0)

    # Calcola tutte le metriche
    consistency_df = compute_consistency_metrics(overall_df)
    form_df = compute_recent_form(overall_df)
    ha_df = compute_home_away_splits(overall_df)
    dep_df = compute_team_dependency(overall_df, player_stats)
    team_stats = compute_team_stats(overall_df)
    shot_df = compute_shot_distribution(player_stats)

    # Nuove analisi a livello squadra
    team_games = compute_team_game_stats(overall_df)
    team_win_loss_diffs = compute_win_vs_loss_diff_by_team(team_games)
    team_rules_stats = compute_team_game_rules(team_games)  # Statistiche di squadra
    team_rules_players = compute_player_based_rules(overall_df)  # Performance giocatori
    similarity_data = compute_player_similarity(player_stats)

    # Prepara HTML
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Analisi Avanzate - {campionato}</title>
    <link rel="icon" type="image/png" href="../static/favicon180x180.png">
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
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Roboto', sans-serif;
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            font-family: 'Poppins', sans-serif;
            color: var(--tp-secondary);
            text-align: center;
        }}
        h2 {{
            font-family: 'Poppins', sans-serif;
            color: var(--tp-secondary);
            border-bottom: 3px solid var(--tp-primary);
            padding-bottom: 8px;
            margin-top: 40px;
        }}
        .header-logo {{
            display: flex;
            justify-content: center;
            margin-bottom: 10px;
        }}
        .header-logo img {{
            height: 50px;
        }}
        .section {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section-desc {{
            color: #666;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .radar-selector {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .radar-selector label {{
            font-weight: bold;
            color: var(--tp-secondary);
        }}
        .radar-selector select {{
            padding: 8px 12px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
            margin: 0 10px;
        }}
        .radar-selector button {{
            padding: 8px 16px;
            background: var(--tp-secondary);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}
        .radar-selector button:hover {{
            background: var(--tp-dark);
        }}
        .consistency-legend {{
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            font-size: 13px;
        }}
        .consistency-legend span {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        .tab-container {{
            display: flex;
            gap: 5px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }}
        .tab-btn {{
            padding: 8px 16px;
            border: 2px solid var(--tp-secondary);
            background: white;
            color: var(--tp-secondary);
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
        }}
        .tab-btn:hover {{
            background: #f0f0f0;
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
        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        @media (max-width: 900px) {{
            .two-col {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="header-logo">
        <img src="../static/twinplay_one_row.svg" alt="TwinPlay">
    </div>
    <h1>Analisi Avanzate - {campionato}</h1>
'''

    # Ordina giocatori per squadra e poi per minuti
    sorted_players = player_stats.sort_values(['Team', 'Minutes'], ascending=[True, False])
    sorted_teams = sorted(team_stats['Team'].unique())

    # ========== 1. RADAR CHART GIOCATORI ==========
    html += '''
    <h2>1. Radar Chart - Confronto Giocatori</h2>
    <div class="section">
        <p class="section-desc">
            Confronta il profilo statistico di più giocatori. I valori sono normalizzati (0-100)
            dove 100 = massimo del campionato. Passa il mouse per vedere i valori reali (per partita).
        </p>
        <div class="radar-selector">
            <label>Seleziona giocatori:</label>
            <select id="player1">
'''

    current_team = None
    for _, row in sorted_players.iterrows():
        if row['Team'] != current_team:
            if current_team is not None:
                html += '                </optgroup>\n'
            current_team = row['Team']
            html += f'                <optgroup label="{current_team}">\n'
        html += f'                    <option value="{row["Giocatore"]}">{row["Giocatore"]}</option>\n'
    html += '                </optgroup>\n'

    html += '''
            </select>
            <select id="player2">
'''
    current_team = None
    for _, row in sorted_players.iterrows():
        if row['Team'] != current_team:
            if current_team is not None:
                html += '                </optgroup>\n'
            current_team = row['Team']
            html += f'                <optgroup label="{current_team}">\n'
        html += f'                    <option value="{row["Giocatore"]}">{row["Giocatore"]}</option>\n'
    html += '                </optgroup>\n'

    html += '''
            </select>
            <button onclick="updatePlayerRadar()">Confronta</button>
        </div>
        <div id="player-radar-chart"></div>
    </div>
'''

    # Prepara dati per radar chart giocatori (0-max normalization)
    # Prima calcola max per ogni statistica
    player_stat_max = {}
    for stat_col, stat_name in RADAR_STATS:
        if stat_col in player_stats.columns:
            vals = player_stats[stat_col].dropna()
            player_stat_max[stat_col] = vals.max()

    radar_data = {}
    for _, row in player_stats.iterrows():
        norm_values = []
        real_values = []
        for stat_col, _ in RADAR_STATS:
            if stat_col in player_stats.columns:
                val = row[stat_col]
                if pd.isna(val):
                    norm_values.append(0)
                    real_values.append(0)
                else:
                    # 0-max normalization (0-100)
                    max_v = player_stat_max[stat_col]
                    if max_v > 0:
                        norm = val / max_v * 100
                    else:
                        norm = 0
                    norm_values.append(round(norm, 1))
                    real_values.append(round(val, 3))
        radar_data[row['Giocatore']] = {
            'values': norm_values,
            'real': real_values,
            'team': row['Team']
        }

    # ========== 2. RADAR CHART SQUADRE ==========
    html += '''
    <h2>2. Radar Chart - Confronto Squadre</h2>
    <div class="section">
        <p class="section-desc">
            Confronta il profilo delle squadre. I valori sono normalizzati (0-100)
            dove 100 = massimo del campionato. Passa il mouse per vedere i valori reali.
        </p>
        <div class="radar-selector">
            <label>Seleziona squadre:</label>
            <select id="team1">
'''
    for team in sorted_teams:
        html += f'                <option value="{team}">{team}</option>\n'

    html += '''
            </select>
            <select id="team2">
'''
    for i, team in enumerate(sorted_teams):
        selected = ' selected' if i == 1 else ''
        html += f'                <option value="{team}"{selected}>{team}</option>\n'

    html += '''
            </select>
            <button onclick="updateTeamRadar()">Confronta</button>
        </div>
        <div id="team-radar-chart"></div>
    </div>
'''

    # Prepara dati per radar chart squadre (0-max normalization)
    team_stat_max = {}
    for stat_col, stat_name in TEAM_RADAR_STATS:
        if stat_col in team_stats.columns:
            vals = team_stats[stat_col].dropna()
            team_stat_max[stat_col] = vals.max()

    team_radar_data = {}
    for _, row in team_stats.iterrows():
        norm_values = []
        real_values = []
        for stat_col, _ in TEAM_RADAR_STATS:
            if stat_col in team_stats.columns:
                val = row[stat_col]
                if pd.isna(val):
                    norm_values.append(0)
                    real_values.append(0)
                else:
                    max_v = team_stat_max[stat_col]
                    if max_v > 0:
                        norm = val / max_v * 100
                    else:
                        norm = 0
                    norm_values.append(round(norm, 1))
                    real_values.append(round(val, 1))
        team_radar_data[row['Team']] = {
            'values': norm_values,
            'real': real_values
        }

    # ========== 3. FORMA RECENTE ==========
    html += '''
    <h2>3. Forma Recente - Chi è Hot/Cold</h2>
    <div class="section">
        <p class="section-desc">
            Confronto tra le <strong>ultime 5 partite</strong> e la media stagionale.
            Valori positivi (verde) = giocatore in crescita. Valori negativi (rosso) = giocatore in calo.
        </p>
'''
    form_fig = create_form_chart(form_df, 'PT', top_n=20)
    if form_fig:
        html += f'        {form_fig.to_html(full_html=False, include_plotlyjs=False)}\n'
    else:
        html += '        <p>Dati insufficienti.</p>\n'
    html += '    </div>\n'

    # ========== 4. HOME VS AWAY ==========
    html += '''
    <h2>4. Casa vs Trasferta</h2>
    <div class="section">
        <p class="section-desc">
            Differenza di rendimento tra partite in casa e in trasferta.
            <span style="color: #302B8F; font-weight: bold;">Blu</span> = meglio in casa,
            <span style="color: #f97316; font-weight: bold;">Arancione</span> = meglio in trasferta.
        </p>
'''
    ha_fig = create_home_away_chart(ha_df, 'PT', top_n=25)
    if ha_fig:
        html += f'        {ha_fig.to_html(full_html=False, include_plotlyjs=False)}\n'
    else:
        html += '        <p>Dati insufficienti (servono almeno 3 partite casa e 3 trasferta).</p>\n'
    html += '    </div>\n'

    # ========== 5. DIPENDENZA SQUADRA ==========
    html += '''
    <h2>5. Dipendenza Squadra</h2>
    <div class="section">
        <p class="section-desc">
            Quanto ogni squadra dipende dai propri top giocatori. Squadre con barra blu lunga =
            molto dipendenti da un singolo giocatore. Squadre bilanciate hanno barre più distribuite.
        </p>
        <div class="tab-container">
            <button class="tab-btn active" onclick="showTab('dep', 'pt', this)">Punti</button>
            <button class="tab-btn" onclick="showTab('dep', 'min', this)">Minuti</button>
        </div>
'''
    # Grafico punti
    dep_pt_fig = create_dependency_chart(dep_df, 'PT')
    html += '        <div id="dep-pt" class="tab-content active">\n'
    if dep_pt_fig:
        html += f'            {dep_pt_fig.to_html(full_html=False, include_plotlyjs=False)}\n'
    else:
        html += '            <p>Dati insufficienti.</p>\n'
    html += '        </div>\n'

    # Grafico minuti
    dep_min_fig = create_dependency_chart(dep_df, 'MIN')
    html += '        <div id="dep-min" class="tab-content">\n'
    if dep_min_fig:
        html += f'            {dep_min_fig.to_html(full_html=False, include_plotlyjs=False)}\n'
    else:
        html += '            <p>Dati insufficienti.</p>\n'
    html += '        </div>\n'

    html += '    </div>\n'

    # ========== 6. SHOT DISTRIBUTION ==========
    html += '''
    <h2>6. Distribuzione Tiri</h2>
    <div class="section">
        <p class="section-desc">
            Frequenza tiri/min (asse X) vs efficienza (asse Y). La dimensione indica il volume totale.
            <strong>In alto a destra</strong> = alta frequenza + alta efficienza.
        </p>
        <div class="tab-container">
            <button class="tab-btn active" onclick="showTab('shot', '3pt', this)">Tiri da 3</button>
            <button class="tab-btn" onclick="showTab('shot', '2pt', this)">Tiri da 2</button>
            <button class="tab-btn" onclick="showTab('shot', 'ft', this)">Tiri Liberi</button>
        </div>
'''
    # Grafico 3PT
    shot_3pt = create_shot_chart(shot_df, '3PT', min_att=15, top_n=40)
    html += '        <div id="shot-3pt" class="tab-content active">\n'
    if shot_3pt:
        html += f'            {shot_3pt.to_html(full_html=False, include_plotlyjs=False)}\n'
    else:
        html += '            <p>Dati insufficienti.</p>\n'
    html += '        </div>\n'

    # Grafico 2PT
    shot_2pt = create_shot_chart(shot_df, '2PT', min_att=20, top_n=40)
    html += '        <div id="shot-2pt" class="tab-content">\n'
    if shot_2pt:
        html += f'            {shot_2pt.to_html(full_html=False, include_plotlyjs=False)}\n'
    else:
        html += '            <p>Dati insufficienti.</p>\n'
    html += '        </div>\n'

    # Grafico FT
    shot_ft = create_shot_chart(shot_df, 'FT', min_att=15, top_n=40)
    html += '        <div id="shot-ft" class="tab-content">\n'
    if shot_ft:
        html += f'            {shot_ft.to_html(full_html=False, include_plotlyjs=False)}\n'
    else:
        html += '            <p>Dati insufficienti.</p>\n'
    html += '        </div>\n'

    html += '    </div>\n'

    # ========== 7. CONSISTENZA ==========
    html += '''
    <h2>7. Consistenza - Giocatori Affidabili</h2>
    <div class="section">
        <p class="section-desc">
            Il <strong>Punteggio di Consistenza</strong> (0-100) indica quanto un giocatore è regolare.
            100 = massima consistenza, 0 = alta variabilità. Mostra i top 25 per media.
        </p>
        <div class="consistency-legend">
            <span><div class="legend-dot" style="background: #22c55e"></div> Molto consistente (70+)</span>
            <span><div class="legend-dot" style="background: #eab308"></div> Moderato (40-69)</span>
            <span><div class="legend-dot" style="background: #ef4444"></div> Alta variabilità (&lt;40)</span>
        </div>
        <div class="tab-container">
            <button class="tab-btn active" onclick="showTab('cons', 'pt', this)">Punti</button>
            <button class="tab-btn" onclick="showTab('cons', 'as', this)">Assist</button>
            <button class="tab-btn" onclick="showTab('cons', 'rt', this)">Rimbalzi</button>
            <button class="tab-btn" onclick="showTab('cons', 'pm', this)">+/- per min</button>
        </div>
'''

    for stat_col, stat_name, stat_id in CONSISTENCY_STATS:
        consistency_fig = create_consistency_plot(consistency_df, stat_col, stat_name, top_n=25)
        active = ' active' if stat_id == 'pt' else ''
        if consistency_fig:
            html += f'        <div id="cons-{stat_id}" class="tab-content{active}">\n'
            html += f'            {consistency_fig.to_html(full_html=False, include_plotlyjs=False)}\n'
            html += '        </div>\n'

    html += '    </div>\n'

    # ========== 8. VITTORIE VS SCONFITTE PER SQUADRA ==========
    html += '''
    <h2>8. Vittorie vs Sconfitte per Squadra</h2>
    <div class="section">
        <p class="section-desc">
            Confronto delle medie statistiche nelle partite <span style="color:#22c55e">vinte</span>
            vs <span style="color:#ef4444">perse</span> per ogni squadra.
            Include statistiche <strong>proprie</strong> e degli <strong>avversari</strong>, ordinate per influenza.
        </p>
'''
    if team_win_loss_diffs:
        html += '''
        <div class="radar-selector">
            <label>Seleziona squadra:</label>
            <select id="winloss-team-select" onchange="showWinLossDiff()">
'''
        for team in sorted(team_win_loss_diffs.keys()):
            html += f'                <option value="{team}">{team}</option>\n'
        html += '''
            </select>
        </div>
        <div id="winloss-content"></div>
'''
    else:
        html += '        <p>Dati insufficienti.</p>\n'
    html += '    </div>\n'

    # ========== 9. REGOLE PER SQUADRA ==========
    html += '''
    <h2>9. Quando Vince Ogni Squadra</h2>
    <div class="section">
        <p class="section-desc">
            Analizza quali fattori predicono le vittorie di ogni squadra.
            Puoi scegliere tra <strong>statistiche di squadra</strong> (punti fatti/subiti, assist, ecc.)
            o <strong>performance individuali</strong> (quando un giocatore supera certe soglie).
        </p>
'''

    # Combina le squadre da entrambi i dataset
    all_teams = set(team_rules_stats.keys()) | set(team_rules_players.keys())

    if all_teams:
        html += '''
        <div class="radar-selector" style="display: flex; flex-wrap: wrap; gap: 15px; align-items: center;">
            <div>
                <label>Tipo analisi:</label>
                <select id="rules-type-select" onchange="showTeamRules()" style="min-width: 180px;">
                    <option value="stats">📊 Statistiche squadra</option>
                    <option value="players">👤 Performance giocatori</option>
                </select>
            </div>
            <div>
                <label>Squadra:</label>
                <select id="team-rules-select" onchange="showTeamRules()">
'''
        for team in sorted(all_teams):
            html += f'                <option value="{team}">{team}</option>\n'
        html += '''
                </select>
            </div>
        </div>
        <div id="team-rules-content"></div>
'''
    else:
        html += '        <p>Dati insufficienti (servono almeno 10 partite per squadra).</p>\n'

    html += '    </div>\n'

    # ========== 10. SIMILARITÀ GIOCATORI ==========
    html += '''
    <h2>10. Giocatori Simili</h2>
    <div class="section">
        <p class="section-desc">
            Trova giocatori con profili statistici simili. Utile per scouting e identificare
            potenziali sostituti. Basato su cosine similarity delle statistiche normalizzate.
        </p>
        <div class="radar-selector">
            <label>Seleziona giocatore:</label>
            <select id="similarity-player">
'''
    current_team = None
    for _, row in sorted_players.iterrows():
        if row['Team'] != current_team:
            if current_team is not None:
                html += '                </optgroup>\n'
            current_team = row['Team']
            html += f'                <optgroup label="{current_team}">\n'
        html += f'                    <option value="{row["Giocatore"]}">{row["Giocatore"]}</option>\n'
    html += '                </optgroup>\n'
    html += '''
            </select>
            <button onclick="showSimilarPlayers()">Trova Simili</button>
        </div>
        <div id="similarity-results"></div>
    </div>
'''

    # Prepara dati similarità per JavaScript (con profilo)
    similarity_js = {}
    if similarity_data:
        for item in similarity_data:
            # Converti profili in dict con int
            player_profile = {k: int(v) for k, v in item.get('profile', {}).items()}
            similar_clean = []
            for s in item['similar']:
                s_profile = {k: int(v) for k, v in s.get('profile', {}).items()}
                similar_clean.append({
                    'name': s['name'],
                    'team': s['team'],
                    'similarity': float(s['similarity']),
                    'profile': s_profile
                })
            similarity_js[item['Giocatore']] = {
                'team': item['Team'],
                'profile': player_profile,
                'similar': similar_clean
            }

    # Prepara dati team rules STATISTICHE per JavaScript
    team_rules_stats_js = {}
    for team, data in team_rules_stats.items():
        rules_clean = []
        for rule in data['rules']:
            rules_clean.append({
                'condition': rule['condition'],
                'threshold': int(rule['threshold']),
                'stat': rule.get('stat', ''),
                'who': rule.get('who', 'Noi'),
                'left_prob': float(rule['left_prob']),
                'left_samples': int(rule['left_samples']),
                'right_prob': float(rule['right_prob']),
                'right_samples': int(rule['right_samples']),
                'diff': float(rule['diff'])
            })
        team_rules_stats_js[team] = {
            'rules': rules_clean,
            'n_games': int(data['n_games']),
            'win_rate': round(float(data['win_rate']) * 100, 1)
        }

    # Prepara dati team rules GIOCATORI per JavaScript
    team_rules_players_js = {}
    for team, data in team_rules_players.items():
        rules_clean = []
        for rule in data['rules']:
            rules_clean.append({
                'condition': rule['condition'],
                'threshold': int(rule['threshold']),
                'stat': rule.get('stat', ''),
                'player': rule.get('player', ''),
                'left_prob': float(rule['left_prob']),
                'left_samples': int(rule['left_samples']),
                'right_prob': float(rule['right_prob']),
                'right_samples': int(rule['right_samples']),
                'diff': float(rule['diff'])
            })
        team_rules_players_js[team] = {
            'rules': rules_clean,
            'n_games': int(data['n_games']),
            'win_rate': round(float(data['win_rate']) * 100, 1),
            'top_players': data.get('top_players', [])
        }

    # Prepara dati win/loss diff per JavaScript
    win_loss_js = {}
    for team, data in team_win_loss_diffs.items():
        win_loss_js[team] = {
            'data': data['data'],
            'n_wins': int(data['n_wins']),
            'n_losses': int(data['n_losses']),
            'win_rate': float(data['win_rate'])
        }

    # JavaScript
    html += f'''
    <script>
        const playerRadarData = {json.dumps(radar_data)};
        const similarityData = {json.dumps(similarity_js)};
        const teamRulesStatsData = {json.dumps(team_rules_stats_js)};
        const teamRulesPlayersData = {json.dumps(team_rules_players_js)};
        const winLossData = {json.dumps(win_loss_js)};
        const teamRadarData = {json.dumps(team_radar_data)};
        const playerCategories = {json.dumps([name for _, name in RADAR_STATS])};
        const teamCategories = {json.dumps([name for _, name in TEAM_RADAR_STATS])};
        const profileStats = ['PT', 'AS', 'RT', 'PR', 'ST'];
        const profileLabels = {{'PT': 'Punti', 'AS': 'Assist', 'RT': 'Rimb', 'PR': 'Recup', 'ST': 'Stopp'}};

        function updatePlayerRadar() {{
            const p1 = document.getElementById('player1').value;
            const p2 = document.getElementById('player2').value;

            const data = [];
            const colors = ['#302B8F', '#00F95B'];

            [p1, p2].forEach((player, i) => {{
                if (playerRadarData[player]) {{
                    const vals = [...playerRadarData[player].values];
                    const realVals = [...playerRadarData[player].real];
                    const cats = [...playerCategories];

                    // Crea testo hover con valori reali
                    const hoverText = cats.map((cat, idx) => {{
                        const real = realVals[idx] || 0;
                        if (cat.includes('Efficienza')) {{
                            return cat + ': ' + (real * 100).toFixed(1) + '%';
                        }} else {{
                            return cat + ': ' + real.toFixed(1) + '/partita';
                        }}
                    }});

                    // Chiudi il poligono
                    vals.push(vals[0]);
                    cats.push(cats[0]);
                    hoverText.push(hoverText[0]);

                    data.push({{
                        type: 'scatterpolar',
                        r: vals,
                        theta: cats,
                        fill: 'toself',
                        fillcolor: colors[i] + '33',
                        line: {{ color: colors[i], width: 2 }},
                        name: player + ' (' + playerRadarData[player].team + ')',
                        text: hoverText,
                        hoverinfo: 'text+name'
                    }});
                }}
            }});

            const layout = {{
                polar: {{
                    radialaxis: {{
                        visible: true,
                        range: [0, 100],
                        tickvals: [0, 25, 50, 75, 100],
                        ticktext: ['0', '25', '50', '75', '100']
                    }}
                }},
                showlegend: true,
                legend: {{ orientation: 'h', y: -0.2 }},
                height: 500,
                margin: {{ t: 50 }}
            }};

            Plotly.newPlot('player-radar-chart', data, layout);
        }}

        function updateTeamRadar() {{
            const t1 = document.getElementById('team1').value;
            const t2 = document.getElementById('team2').value;

            const data = [];
            const colors = ['#302B8F', '#00F95B'];

            [t1, t2].forEach((team, i) => {{
                if (teamRadarData[team]) {{
                    const vals = [...teamRadarData[team].values];
                    const realVals = [...teamRadarData[team].real];
                    const cats = [...teamCategories];

                    // Crea testo hover con valori reali
                    const hoverText = cats.map((cat, idx) => {{
                        const real = realVals[idx] || 0;
                        if (cat.includes('Tiro')) {{
                            return cat + ': ' + real.toFixed(1) + '%';
                        }} else {{
                            return cat + ': ' + real.toFixed(1) + '/partita';
                        }}
                    }});

                    // Chiudi il poligono
                    vals.push(vals[0]);
                    cats.push(cats[0]);
                    hoverText.push(hoverText[0]);

                    data.push({{
                        type: 'scatterpolar',
                        r: vals,
                        theta: cats,
                        fill: 'toself',
                        fillcolor: colors[i] + '33',
                        line: {{ color: colors[i], width: 2 }},
                        name: team,
                        text: hoverText,
                        hoverinfo: 'text+name'
                    }});
                }}
            }});

            const layout = {{
                polar: {{
                    radialaxis: {{
                        visible: true,
                        range: [0, 100],
                        tickvals: [0, 25, 50, 75, 100],
                        ticktext: ['0', '25', '50', '75', '100']
                    }}
                }},
                showlegend: true,
                legend: {{ orientation: 'h', y: -0.2 }},
                height: 500,
                margin: {{ t: 50 }}
            }};

            Plotly.newPlot('team-radar-chart', data, layout);
        }}

        function showTab(prefix, tab, btn) {{
            document.querySelectorAll('[id^="' + prefix + '-"]').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => {{
                if (el.closest('.section') === btn.closest('.section')) {{
                    el.classList.remove('active');
                }}
            }});
            const tabEl = document.getElementById(prefix + '-' + tab);
            tabEl.classList.add('active');
            btn.classList.add('active');

            // Forza Plotly a ricalcolare le dimensioni
            setTimeout(() => {{
                window.dispatchEvent(new Event('resize'));
            }}, 50);
        }}

        function showSimilarPlayers() {{
            const player = document.getElementById('similarity-player').value;
            const resultsDiv = document.getElementById('similarity-results');

            if (!similarityData[player]) {{
                resultsDiv.innerHTML = '<p style="color: #666; padding: 15px;">Giocatore non trovato o minuti insufficienti.</p>';
                return;
            }}

            const data = similarityData[player];

            // Funzione per creare mini profilo visivo
            function createMiniProfile(profile) {{
                let html = '<div style="display: flex; gap: 4px; justify-content: center;">';
                profileStats.forEach(stat => {{
                    const pct = profile[stat] || 0;
                    // Colore basato su percentile
                    let color;
                    if (pct >= 80) color = '#22c55e';      // Top tier
                    else if (pct >= 60) color = '#84cc16'; // Good
                    else if (pct >= 40) color = '#eab308'; // Average
                    else if (pct >= 20) color = '#f97316'; // Below avg
                    else color = '#ef4444';                 // Low

                    html += `<div style="display: flex; flex-direction: column; align-items: center; min-width: 32px;" title="${{profileLabels[stat]}}: ${{pct}}° percentile">`;
                    html += `<div style="font-size: 9px; color: #999; margin-bottom: 2px;">${{profileLabels[stat]}}</div>`;
                    html += `<div style="width: 24px; height: 24px; border-radius: 4px; background: ${{color}}; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; color: white;">${{pct}}</div>`;
                    html += `</div>`;
                }});
                html += '</div>';
                return html;
            }}

            let html = '<div style="margin-top: 15px;">';

            // Prima mostra il profilo del giocatore selezionato
            html += `<div style="background: var(--tp-secondary); color: white; padding: 15px; border-radius: 8px; margin-bottom: 15px;">`;
            html += `<div style="font-weight: bold; margin-bottom: 10px;">📊 Profilo di ${{player}} (${{data.team}})</div>`;
            html += `<div style="display: flex; gap: 8px; justify-content: center;">`;
            profileStats.forEach(stat => {{
                const pct = data.profile[stat] || 0;
                html += `<div style="text-align: center; min-width: 50px;">`;
                html += `<div style="font-size: 11px; opacity: 0.8;">${{profileLabels[stat]}}</div>`;
                html += `<div style="font-size: 20px; font-weight: bold;">${{pct}}</div>`;
                html += `<div style="font-size: 10px; opacity: 0.7;">percentile</div>`;
                html += `</div>`;
            }});
            html += `</div></div>`;

            // Lista giocatori simili
            html += '<div style="display: flex; flex-direction: column; gap: 10px;">';

            data.similar.forEach((sim, i) => {{
                const simPercent = (sim.similarity * 100).toFixed(0);
                const barWidth = sim.similarity * 100;

                html += `<div style="background: white; border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px; display: grid; grid-template-columns: 1fr auto 180px; align-items: center; gap: 15px;">`;

                // Nome e squadra
                html += `<div>`;
                html += `<div style="font-weight: 600;">${{sim.name}}</div>`;
                html += `<div style="font-size: 12px; color: #666;">${{sim.team}}</div>`;
                html += `</div>`;

                // Profilo visivo
                html += createMiniProfile(sim.profile);

                // Similarità
                html += `<div style="display: flex; align-items: center; gap: 8px;">`;
                html += `<div style="flex: 1; background: #e5e5e5; border-radius: 4px; height: 8px; width: 80px;">`;
                html += `<div style="width: ${{barWidth}}%; background: var(--tp-primary); height: 100%; border-radius: 4px;"></div>`;
                html += `</div>`;
                html += `<span style="font-weight: bold; min-width: 45px;">${{simPercent}}%</span>`;
                html += `</div>`;

                html += `</div>`;
            }});

            html += '</div></div>';
            resultsDiv.innerHTML = html;
        }}

        function showTeamRules() {{
            const team = document.getElementById('team-rules-select').value;
            const ruleType = document.getElementById('rules-type-select').value;
            const contentDiv = document.getElementById('team-rules-content');

            // Seleziona il dataset giusto
            const dataSource = ruleType === 'stats' ? teamRulesStatsData : teamRulesPlayersData;

            if (!dataSource[team]) {{
                const otherSource = ruleType === 'stats' ? teamRulesPlayersData : teamRulesStatsData;
                if (otherSource[team]) {{
                    contentDiv.innerHTML = `<p style="color: #666; padding: 15px;">Nessuna regola "${{ruleType === 'stats' ? 'statistiche squadra' : 'giocatori'}}" per questa squadra. Prova l'altra modalità.</p>`;
                }} else {{
                    contentDiv.innerHTML = '<p style="color: #666; padding: 15px;">Nessuna regola trovata per questa squadra.</p>';
                }}
                return;
            }}

            const data = dataSource[team];
            let html = '<div style="margin-top: 15px;">';
            html += `<p style="margin-bottom: 15px;"><strong>${{data.n_games}} partite</strong> | Win rate: <strong>${{data.win_rate}}%</strong>`;

            // Per giocatori, mostra i top players
            if (ruleType === 'players' && data.top_players && data.top_players.length > 0) {{
                html += ` | Top 5: <span style="color: #666;">${{data.top_players.join(', ')}}</span>`;
            }}
            html += `</p>`;

            if (data.rules && data.rules.length > 0) {{
                html += '<div style="display: flex; flex-direction: column; gap: 15px;">';

                data.rules.forEach(rule => {{
                    const leftProb = (rule.left_prob * 100).toFixed(0);
                    const rightProb = (rule.right_prob * 100).toFixed(0);
                    const diffPct = (rule.diff * 100).toFixed(0);

                    // Colori basati su quale è meglio
                    const leftBetter = rule.left_prob > rule.right_prob;
                    const leftColor = leftBetter ? '#22c55e' : '#ef4444';
                    const rightColor = leftBetter ? '#ef4444' : '#22c55e';

                    // Titolo condizione con stat se presente
                    let conditionTitle = rule.condition;
                    if (rule.stat) {{
                        conditionTitle += ` (${{rule.stat}})`;
                    }}

                    html += `<div style="background: white; border: 1px solid #e5e5e5; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">`;

                    // Header con nome condizione
                    html += `<div style="font-weight: bold; margin-bottom: 12px; font-size: 15px; color: var(--tp-secondary); display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">`;
                    html += `<span>${{conditionTitle}}</span>`;
                    html += `<span style="font-size: 13px; color: #666; margin-left: auto;">Δ ${{diffPct}}%</span>`;
                    html += `</div>`;

                    // Due condizioni affiancate
                    html += `<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">`;

                    // Condizione ≤
                    const leftLabel = rule.stat ? `≤ ${{rule.threshold}} ${{rule.stat}}` : `≤ ${{rule.threshold}}`;
                    html += `<div style="background: ${{leftBetter ? '#dcfce7' : '#fee2e2'}}; padding: 12px; border-radius: 6px; text-align: center;">`;
                    html += `<div style="font-size: 13px; color: #666;">${{leftLabel}}</div>`;
                    html += `<div style="font-size: 24px; font-weight: bold; color: ${{leftColor}};">${{leftProb}}%</div>`;
                    html += `<div style="font-size: 12px; color: #666;">(${{rule.left_samples}} partite)</div>`;
                    html += `</div>`;

                    // Condizione >
                    const rightLabel = rule.stat ? `> ${{rule.threshold}} ${{rule.stat}}` : `> ${{rule.threshold}}`;
                    html += `<div style="background: ${{!leftBetter ? '#dcfce7' : '#fee2e2'}}; padding: 12px; border-radius: 6px; text-align: center;">`;
                    html += `<div style="font-size: 13px; color: #666;">${{rightLabel}}</div>`;
                    html += `<div style="font-size: 24px; font-weight: bold; color: ${{rightColor}};">${{rightProb}}%</div>`;
                    html += `<div style="font-size: 12px; color: #666;">(${{rule.right_samples}} partite)</div>`;
                    html += `</div>`;

                    html += `</div></div>`;
                }});

                html += '</div>';
            }} else {{
                html += '<p>Nessuna regola significativa trovata (differenza minima tra condizioni).</p>';
            }}

            html += '</div>';
            contentDiv.innerHTML = html;
        }}

        function showWinLossDiff() {{
            const team = document.getElementById('winloss-team-select').value;
            const contentDiv = document.getElementById('winloss-content');

            if (!winLossData[team]) {{
                contentDiv.innerHTML = '<p style="color: #666; padding: 15px;">Dati insufficienti per questa squadra.</p>';
                return;
            }}

            const data = winLossData[team];
            const labels = {{
                'PT': 'Punti', 'AS': 'Assist', 'RT': 'Rimbalzi', 'PR': 'Recuperi',
                'ST': 'Stoppate', '3PTM': 'Triple', '2PT_%': '% da 2', '3PT_%': '% da 3'
            }};

            // Raggruppa per statistica (fatte + subite insieme)
            const statGroups = {{}};
            data.data.forEach(row => {{
                const stat = row['Statistica'];
                if (!statGroups[stat]) {{
                    statGroups[stat] = {{ fatte: null, subite: null, maxInfluenza: 0 }};
                }}
                if (row['Tipo'] === 'Noi') {{
                    statGroups[stat].fatte = row;
                }} else {{
                    statGroups[stat].subite = row;
                }}
                statGroups[stat].maxInfluenza = Math.max(statGroups[stat].maxInfluenza, row['Influenza']);
            }});

            // Ordina per influenza massima
            const sortedStats = Object.entries(statGroups)
                .sort((a, b) => b[1].maxInfluenza - a[1].maxInfluenza);

            // Trova max per normalizzare le barre
            const allValues = data.data.flatMap(r => [r['Media Vittorie'], r['Media Sconfitte']]);
            const maxValue = Math.max(...allValues);

            let html = '<div style="margin-top: 15px;">';
            html += `<p style="margin-bottom: 15px;">
                <span style="color: #22c55e; font-weight: bold;">●</span> <strong>${{data.n_wins}} vittorie</strong>
                vs
                <span style="color: #ef4444; font-weight: bold;">●</span> <strong>${{data.n_losses}} sconfitte</strong>
                (Win rate: ${{data.win_rate}}%)
            </p>`;

            html += '<div style="display: flex; flex-direction: column; gap: 16px;">';

            sortedStats.forEach(([stat, group]) => {{
                const label = labels[stat] || stat;

                html += `<div style="background: white; border: 1px solid #e5e5e5; border-radius: 8px; padding: 16px;">`;

                // Titolo statistica
                html += `<div style="text-align: center; margin-bottom: 12px;">`;
                html += `<span style="font-weight: 700; color: var(--tp-secondary); font-size: 16px;">${{label}}</span>`;
                html += `</div>`;

                // Due colonne: fatte | subite
                html += `<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">`;

                // Helper per creare una colonna
                function createColumn(rowData, tipo, tipoColor) {{
                    if (!rowData) {{
                        return `<div style="background: #f9f9f9; border-radius: 8px; padding: 12px; text-align: center; color: #999;">N/D</div>`;
                    }}

                    const winVal = rowData['Media Vittorie'];
                    const lossVal = rowData['Media Sconfitte'];
                    const diffPct = rowData['Diff %'];
                    const diffAbs = rowData['Differenza'];
                    const diffSign = diffPct > 0 ? '+' : '';
                    const diffAbsSign = diffAbs > 0 ? '+' : '';

                    const winWidth = (winVal / maxValue) * 100;
                    const lossWidth = (lossVal / maxValue) * 100;

                    // Verde se positivo per fatte, verde se negativo per subite
                    const isPositive = tipo === 'fatte' ? diffPct > 0 : diffPct < 0;
                    const diffColor = isPositive ? '#22c55e' : '#ef4444';

                    let col = `<div style="background: #f9f9f9; border-radius: 8px; padding: 12px;">`;

                    // Header: tipo + variazione
                    col += `<div style="text-align: center; margin-bottom: 10px;">`;
                    col += `<span style="background: ${{tipoColor}}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">${{tipo}}</span>`;
                    col += `<div style="margin-top: 6px;">`;
                    col += `<span style="font-size: 20px; font-weight: bold; color: ${{diffColor}};">${{diffSign}}${{diffPct}}%</span>`;
                    col += `<span style="font-size: 13px; color: #666; margin-left: 6px;">(${{diffAbsSign}}${{diffAbs}})</span>`;
                    col += `</div></div>`;

                    // Barre
                    col += `<div style="display: flex; flex-direction: column; gap: 4px;">`;

                    // Vittorie
                    col += `<div style="display: flex; align-items: center; gap: 6px;">`;
                    col += `<div style="width: 16px; font-size: 10px; color: #22c55e; font-weight: bold;">V</div>`;
                    col += `<div style="flex: 1; background: #e5e5e5; border-radius: 3px; height: 18px; position: relative; overflow: hidden;">`;
                    col += `<div style="width: ${{winWidth}}%; background: #22c55e; height: 100%; border-radius: 3px;"></div>`;
                    col += `<span style="position: absolute; left: 6px; top: 50%; transform: translateY(-50%); font-size: 11px; font-weight: 600; color: #166534;">${{winVal}}</span>`;
                    col += `</div></div>`;

                    // Sconfitte
                    col += `<div style="display: flex; align-items: center; gap: 6px;">`;
                    col += `<div style="width: 16px; font-size: 10px; color: #ef4444; font-weight: bold;">S</div>`;
                    col += `<div style="flex: 1; background: #e5e5e5; border-radius: 3px; height: 18px; position: relative; overflow: hidden;">`;
                    col += `<div style="width: ${{lossWidth}}%; background: #ef4444; height: 100%; border-radius: 3px;"></div>`;
                    col += `<span style="position: absolute; left: 6px; top: 50%; transform: translateY(-50%); font-size: 11px; font-weight: 600; color: #991b1b;">${{lossVal}}</span>`;
                    col += `</div></div>`;

                    col += `</div></div>`;
                    return col;
                }}

                // Colonna FATTE (sinistra)
                html += createColumn(group.fatte, 'fatte', '#302B8F');

                // Colonna SUBITE (destra)
                html += createColumn(group.subite, 'subite', '#f97316');

                html += `</div></div>`;
            }});

            html += '</div></div>';
            contentDiv.innerHTML = html;
        }}

        // Inizializza
        updatePlayerRadar();
        updateTeamRadar();
        if (document.getElementById('team-rules-select')) {{
            showTeamRules();
        }}
        if (document.getElementById('winloss-team-select')) {{
            showWinLossDiff();
        }}
    </script>
</body>
</html>
'''

    return html


def save_advanced_report(overall_df, player_stats, campionato, output_dir='.'):
    """
    Salva il report HTML delle analisi avanzate.
    """
    import os

    html = generate_advanced_report(overall_df, player_stats, campionato)
    filename = os.path.join(output_dir, f'advanced_{campionato.lower().replace(" ", "_")}.html')

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Report avanzato salvato: {filename}")
    return filename
