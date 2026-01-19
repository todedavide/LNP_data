"""
Modulo per l'analisi dei dati e la generazione di grafici.
"""

import glob
import os
import pickle

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.colors as pc
import Levenshtein
from itertools import combinations

from .config import DATA_DIR


def get_team_color_map(teams):
    """Crea una mappa colori consistente per le squadre."""
    # Usa una palette ampia con colori distinguibili
    colors = (
        pc.qualitative.Plotly +
        pc.qualitative.D3 +
        pc.qualitative.Set1 +
        pc.qualitative.Set2 +
        pc.qualitative.Pastel1
    )
    sorted_teams = sorted(teams)
    return {team: colors[i % len(colors)] for i, team in enumerate(sorted_teams)}


def add_median_lines(df, labx, laby, fig):
    """Aggiunge linee mediane a un grafico."""
    medianx = df[labx].median()
    mediany = df[laby].median()

    fig.add_shape(type='line', x0=df[labx].min(), y0=mediany,
                  x1=df[labx].max(), y1=mediany,
                  line=dict(color='black', width=2, dash='dash'))

    fig.add_shape(type='line', x0=medianx, y0=df[laby].min(),
                  x1=medianx, y1=df[laby].max(),
                  line=dict(color='black', width=2, dash='dash'))
    return fig


def find_similar_strings(strings, threshold=0.2):
    """Trova stringhe simili in una lista."""
    similarities = {}
    for a, b in combinations(strings, 2):
        set_a = set(a.split())
        set_b = set(b.split())
        common_words = set_a.intersection(set_b).intersection({"Pallacanestro", "Virtus", "Basket"})
        set_a = set_a - common_words
        set_b = set_b - common_words
        if len(set_a.union(set_b)) > 0:
            similarity = len(set_a.intersection(set_b)) / len(set_a.union(set_b))
            if similarity >= threshold:
                similarities[(a, b)] = similarity
    return list(set([tuple(sorted(pair)) for pair in similarities.keys()]))


def levenshtein_distance(s1, s2):
    """Calcola la distanza di Levenshtein tra due stringhe."""
    return Levenshtein.distance(s1.lower(), s2.lower())


def find_misspelled_names(df, threshold):
    """Trova nomi di giocatori potenzialmente scritti male."""
    misspelled_pairs = []
    for team in df['Team'].unique():
        team_df = df[df['Team'] == team]
        for i in range(len(team_df)):
            for j in range(i + 1, len(team_df)):
                name1 = team_df.iloc[i]['Giocatore']
                name2 = team_df.iloc[j]['Giocatore']
                # Se le iniziali sono diverse, sono persone diverse (es. S. Bossi vs L. Bosso)
                if name1[0] != name2[0]:
                    continue
                if levenshtein_distance(name1, name2) / len(name1) <= threshold:
                    misspelled_pairs.append((name1, name2))
    return misspelled_pairs


def load_all_data(campionato_filtro=None):
    """
    Carica tutti i dati dai file pickle.

    Args:
        campionato_filtro: se specificato, filtra per campionato ('b_a', 'b_b', 'a2')

    Returns:
        DataFrame con tutti i dati, suffisso per il nome del report
    """
    stats_files = glob.glob(os.path.join(DATA_DIR, 'season_stats*.pkl'))
    if not stats_files:
        print("Nessun file di statistiche trovato. Esegui prima lo scraping.")
        return None, None

    dfs = []
    for file in stats_files:
        with open(file, 'rb') as f:
            df_temp = pickle.load(f)
            if 'Campionato' not in df_temp.columns:
                camp_name = os.path.basename(file).replace('season_stats_', '').replace('.pkl', '')
                if camp_name == 'season_stats':
                    camp_name = 'legacy'
                df_temp['Campionato'] = camp_name
            dfs.append(df_temp)

    overall_df = pd.concat(dfs)

    if campionato_filtro:
        overall_df = overall_df[overall_df['Campionato'] == campionato_filtro]
        report_suffix = f"_{campionato_filtro}"
        print(f"Filtrato per campionato: {campionato_filtro}")
    else:
        report_suffix = "_tutti"
        print(f"Campionati inclusi: {overall_df['Campionato'].unique().tolist()}")

    return overall_df, report_suffix


def preprocess_data(overall_df, similar_teams=None, min_minutes=100):
    """
    Preprocessa i dati per l'analisi.

    Args:
        overall_df: DataFrame con i dati grezzi
        similar_teams: lista di tuple per normalizzare nomi squadre
        min_minutes: minuti minimi per includere un giocatore

    Returns:
        DataFrame preprocessato
    """
    overall_df = overall_df.copy()
    overall_df.reset_index(inplace=True, drop=True)

    # Parsing colonne tiro
    overall_df[['2PTM', '2PTA']] = overall_df['2PT'].str.split('/', expand=True).apply(pd.to_numeric)
    overall_df[['3PTM', '3PTA']] = overall_df['3PT'].str.split('/', expand=True).apply(pd.to_numeric)
    overall_df[['FTM', 'FTA']] = overall_df['TL'].str.split('/', expand=True).apply(pd.to_numeric)

    # Normalizza nomi squadre (usa sempre il secondo nome come standard)
    if similar_teams:
        for variant, standard in similar_teams:
            # Normalizza Team
            mask = overall_df["Team"] == variant
            if mask.any():
                overall_df.loc[mask, "Team"] = standard
            # Normalizza anche Opponent
            if "Opponent" in overall_df.columns:
                mask_opp = overall_df["Opponent"] == variant
                if mask_opp.any():
                    overall_df.loc[mask_opp, "Opponent"] = standard

    # Correggi nomi giocatori simili
    player_team_pairs = overall_df[['Giocatore', 'Team']].drop_duplicates()
    misspelled_pairs = find_misspelled_names(player_team_pairs, threshold=0.3)

    corrections = {}
    for name1, name2 in misspelled_pairs:
        team = overall_df.loc[overall_df['Giocatore'] == name1, 'Team'].iloc[0]
        name1_count = overall_df.loc[(overall_df['Giocatore'] == name1) & (overall_df['Team'] == team)].shape[0]
        name2_count = overall_df.loc[(overall_df['Giocatore'] == name2) & (overall_df['Team'] == team)].shape[0]
        if name1_count >= name2_count:
            corrections[name2] = name1
        else:
            corrections[name1] = name2

    overall_df['Giocatore'] = overall_df['Giocatore'].replace(corrections)

    # Filtra giocatori con minuti minimi
    player_minutes = overall_df.groupby(['Giocatore', 'Team'])['Minutes'].sum()
    selected_players = player_minutes[player_minutes > min_minutes].index
    overall_df = overall_df[overall_df.set_index(['Giocatore', 'Team']).index.isin(selected_players)]

    # Aggiungi colonne derivate
    overall_df['Result'] = overall_df['Gap'] > 0
    overall_df['Tight'] = np.abs(overall_df['Gap']) < 5
    overall_df.loc[np.abs(overall_df['pm_permin']) > 10, 'pm_permin'] = np.nan
    overall_df["pm_permin_adj"] = overall_df['pm_permin'] - overall_df['Gap_permin']

    return overall_df


def compute_aggregated_stats(overall_df):
    """
    Calcola statistiche aggregate per giocatore.

    Returns:
        sum_df: DataFrame con somme
        median_df: DataFrame con mediane
    """
    sum_df = overall_df.groupby(['Giocatore', 'Team']).sum(numeric_only=True)

    # Rapporti
    sum_df['AS_PP_ratio'] = sum_df['AS'] / sum_df['PP']
    sum_df['PR_PP_ratio'] = sum_df['PR'] / sum_df['PP']
    sum_df['FS_FF_ratio'] = sum_df['FS'] / sum_df['FF']
    sum_df['ST_FF_ratio'] = sum_df['ST'] / sum_df['FF']
    sum_df['AS_PP_perc'] = sum_df['AS'] / (sum_df['PP'] + sum_df['AS'])

    # Per minuto
    sum_df['AS_permin'] = sum_df['AS'] / sum_df['Minutes']
    sum_df['PT_permin'] = sum_df['PT'] / sum_df['Minutes']
    sum_df['RO_permin'] = sum_df['RO'] / sum_df['Minutes']
    sum_df['RD_permin'] = sum_df['RD'] / sum_df['Minutes']
    sum_df['PR_permin'] = sum_df['PR'] / sum_df['Minutes']
    sum_df['FS_permin'] = sum_df['FS'] / sum_df['Minutes']
    sum_df['FF_permin'] = sum_df['FF'] / sum_df['Minutes']
    sum_df['ST_permin'] = sum_df['ST'] / sum_df['Minutes']
    sum_df['3PTM_permin'] = sum_df['3PTM'] / sum_df['Minutes']
    sum_df['FTA_permin'] = sum_df['FTA'] / sum_df['Minutes']

    # Percentuali tiro
    sum_df['True_shooting'] = sum_df['PT'] / 2 / (sum_df['2PTA'] + sum_df['3PTA'] + 0.44 * sum_df['FTA'])
    sum_df['3PT_%'] = sum_df['3PTM'] / sum_df['3PTA']
    sum_df['FT_%'] = sum_df['FTM'] / sum_df['FTA']

    sum_df.reset_index(inplace=True)

    # Mediane
    median_df = overall_df.groupby(['Giocatore', 'Team']).agg({
        'pm_permin_adj': 'median',
        'Minutes': 'sum',
        'Gap_permin': 'median',
        'pm_permin': 'median'
    })
    median_df['pm_permin_adj_plusgap'] = median_df['pm_permin_adj'] + median_df['Gap_permin']
    median_df.sort_values(inplace=True, by='pm_permin_adj_plusgap')
    median_df.reset_index(inplace=True)

    return sum_df, median_df


def create_all_plots(overall_df, sum_df, median_df):
    """
    Crea tutti i grafici per il report.

    Returns:
        plots_with_captions: lista di tuple (fig, caption, title)
        team_plots: lista di tuple (fig, label) per dropdown squadre
    """
    # Mappa colori consistente per tutte le squadre
    all_teams = overall_df['Team'].unique()
    color_map = get_team_color_map(all_teams)

    category_order = {'Tight': [False, True]}

    # Grafici per squadra (dropdown)
    team_plots = []
    for team in sorted(overall_df['Team'].unique()):
        team_data = overall_df[overall_df['Team'] == team]
        fig = px.box(team_data, x='Giocatore', y='pm_permin_adj', color='Tight', points="all",
                     hover_data={'Opponent': True, 'Gap': True}, category_orders=category_order)
        team_plots.append((fig, team))

    # Grafici principali: (fig, caption, title)
    plots = []

    # 1. +/- adjusted vs +/-
    fig = px.scatter(median_df, x='pm_permin_adj', y='pm_permin', size='Minutes',
                     color='Team', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(median_df, 'pm_permin_adj', 'pm_permin', fig)
    plots.append((fig,
                  'In alto giocatori che fanno bene con dipendenza anche dal risultato di squadra, '
                  'a destra giocatori che fanno meglio del risultato di squadra',
                  '+/- Adjusted vs +/- Raw'))

    # 2. Assist
    fig = px.scatter(sum_df, x='AS_permin', y='AS_PP_ratio', size='AS',
                     color='Team', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'AS_permin', 'AS_PP_ratio', fig)
    plots.append((fig,
                  'Assist al minuto vs rapporto assist/palle perse',
                  'Efficienza Assist'))

    # 3. Assist vs Punti
    fig = px.scatter(sum_df, x='AS_permin', y='PT_permin', color='Team',
                     hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'AS_permin', 'PT_permin', fig)
    plots.append((fig,
                  'Assist al minuto vs punti al minuto',
                  'Produzione Offensiva'))

    # 4. Rimbalzi
    fig = px.scatter(sum_df, x='RD_permin', y='RO_permin', size='RT',
                     color='Team', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'RD_permin', 'RO_permin', fig)
    plots.append((fig,
                  'Rimbalzi difensivi al minuto vs rimbalzi offensivi al minuto',
                  'Efficienza a Rimbalzo'))

    # 5. True shooting vs AS/PP
    fig = px.scatter(sum_df, x='AS_PP_ratio', y='True_shooting', color='Team',
                     size='PT', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'AS_PP_ratio', 'True_shooting', fig)
    fig.update_layout(yaxis_tickformat='.0%')
    plots.append((fig,
                  'Rapporto assist-PP vs True shooting percentage',
                  'Efficienza sugli Errori'))

    # 6. True shooting vs PT/min
    fig = px.scatter(sum_df, x='PT_permin', y='True_shooting', color='Team',
                     size='PT', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'PT_permin', 'True_shooting', fig)
    fig.update_layout(yaxis_tickformat='.0%')
    plots.append((fig,
                  'Punti al minuto vs True shooting percentage',
                  'Efficienza al Tiro'))

    # 7. 3PT
    fig = px.scatter(sum_df, x='3PTM_permin', y='3PT_%', color='Team',
                     size='3PTM', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, '3PTM_permin', '3PT_%', fig)
    fig.update_layout(yaxis_tickformat='.0%')
    plots.append((fig,
                  'Triple realizzate al minuto vs percentuale da 3',
                  'Tiro da 3 Punti'))

    # 8. Free throws
    fig = px.scatter(sum_df, x='FTA_permin', y='FT_%', color='Team',
                     size='FTA', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'FTA_permin', 'FT_%', fig)
    fig.update_layout(yaxis_tickformat='.0%')
    plots.append((fig,
                  'Tiri liberi tentati al minuto vs percentuale ai liberi',
                  'Tiri Liberi'))

    # 9. Palloni recuperati
    fig = px.scatter(sum_df, x='PR_permin', y='PR_PP_ratio', color='Team',
                     size='PR', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'PR_permin', 'PR_PP_ratio', fig)
    plots.append((fig,
                  'Palloni recuperati al minuto vs rapporto PR/PP',
                  'Palloni Recuperati'))

    # 10. Falli subiti
    fig = px.scatter(sum_df, x='FS_permin', y='FS_FF_ratio', color='Team',
                     size='FS', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'FS_permin', 'FS_FF_ratio', fig)
    plots.append((fig,
                  'Falli subiti al minuto vs rapporto falli subiti/fatti',
                  'Falli Subiti'))

    # 11. Stoppate
    fig = px.scatter(sum_df, x='ST_permin', y='ST_FF_ratio', color='Team',
                     size='ST', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'ST_permin', 'ST_FF_ratio', fig)
    plots.append((fig,
                  'Stoppate al minuto vs rapporto stoppate/falli fatti',
                  'Stoppate'))

    # 12. Falli fatti
    fig = px.scatter(sum_df, x='FF_permin', y='FF', color='Team',
                     size='Minutes', hover_name='Giocatore', color_discrete_map=color_map)
    fig = add_median_lines(sum_df, 'FF_permin', 'FF', fig)
    plots.append((fig,
                  'Falli fatti al minuto vs totale falli',
                  'Falli Fatti'))

    return plots, team_plots
