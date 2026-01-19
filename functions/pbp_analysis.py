"""
Analisi Play-by-Play per LNP Stats.
Funzioni per estrarre statistiche avanzate dai dati PBP.
"""

import os
import pandas as pd
import numpy as np

from .config import SIMILAR_TEAMS

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


def normalize_team_names(df):
    """Normalizza i nomi delle squadre usando SIMILAR_TEAMS."""
    if df is None or df.empty:
        return df

    df = df.copy()

    # Trova colonne con nomi squadra
    team_columns = [col for col in df.columns if col.lower() in ['team', 'home', 'away', 'home_team', 'away_team']]

    for col in team_columns:
        if col in df.columns:
            for variant, standard in SIMILAR_TEAMS:
                df.loc[df[col] == variant, col] = standard

    return df


def fix_pbp_time_format(df):
    """
    Corregge il caso speciale 00:00 = 10:00 (fine quarto).

    Il tempo nel PBP è in formato count-up (tempo trascorso nel quarto),
    ma 00:00 è un caso speciale che significa 10:00 (fine quarto).
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    if 'time_seconds' in df.columns and 'quarter' in df.columns:
        # Caso speciale: 00:00 significa 10:00 (fine quarto)
        df.loc[df['time_seconds'] == 0, 'time_seconds'] = 600

        # Ricalcola total_seconds
        df['total_seconds'] = (df['quarter'] - 1) * 600 + df['time_seconds']

        # Ricalcola clutch (ultimi 2 min = da 8:00 a 10:00)
        if 'gap' in df.columns:
            df['clutch'] = (df['quarter'] == 4) & (df['time_seconds'] >= 480) & (df['gap'].abs() <= 5)

    return df


def load_pbp_data(campionato_filter=None):
    """
    Carica dati play-by-play per uno o più campionati.

    Args:
        campionato_filter: 'b_a', 'b_b', 'a2', 'b_combined', o None per tutti

    Returns:
        DataFrame con tutti gli eventi PBP
    """
    files_map = {
        'b_a': 'pbp_b_a.pkl',
        'b_b': 'pbp_b_b.pkl',
        'a2': 'pbp_a2.pkl',
    }

    if campionato_filter == 'b_combined':
        dfs = []
        for key in ['b_a', 'b_b']:
            path = os.path.join(DATA_DIR, files_map[key])
            if os.path.exists(path):
                dfs.append(pd.read_pickle(path))
        result = pd.concat(dfs, ignore_index=True) if dfs else None
        result = normalize_team_names(result)
        return fix_pbp_time_format(result)

    if campionato_filter and campionato_filter in files_map:
        path = os.path.join(DATA_DIR, files_map[campionato_filter])
        if os.path.exists(path):
            result = normalize_team_names(pd.read_pickle(path))
            return fix_pbp_time_format(result)
        return None

    # Tutti i campionati
    dfs = []
    for fname in files_map.values():
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            dfs.append(pd.read_pickle(path))
    result = pd.concat(dfs, ignore_index=True) if dfs else None
    result = normalize_team_names(result)
    return fix_pbp_time_format(result)


def load_quarters_data(campionato_filter=None):
    """
    Carica dati parziali per quarto.

    Args:
        campionato_filter: 'b_a', 'b_b', 'a2', 'b_combined', o None per tutti

    Returns:
        DataFrame con parziali per quarto per partita
    """
    files_map = {
        'b_a': 'quarters_b_a.pkl',
        'b_b': 'quarters_b_b.pkl',
        'a2': 'quarters_a2.pkl',
    }

    if campionato_filter == 'b_combined':
        dfs = []
        for key in ['b_a', 'b_b']:
            path = os.path.join(DATA_DIR, files_map[key])
            if os.path.exists(path):
                dfs.append(pd.read_pickle(path))
        result = pd.concat(dfs, ignore_index=True) if dfs else None
        return normalize_team_names(result)

    if campionato_filter and campionato_filter in files_map:
        path = os.path.join(DATA_DIR, files_map[campionato_filter])
        if os.path.exists(path):
            return normalize_team_names(pd.read_pickle(path))
        return None

    # Tutti i campionati
    dfs = []
    for fname in files_map.values():
        path = os.path.join(DATA_DIR, fname)
        if os.path.exists(path):
            dfs.append(pd.read_pickle(path))
    result = pd.concat(dfs, ignore_index=True) if dfs else None
    return normalize_team_names(result)


# ============ HELPER FUNCTIONS ============

def is_field_goal_attempt(action):
    """Verifica se l'azione è un tentativo di tiro da campo (no liberi)."""
    if pd.isna(action):
        return False
    action_lower = action.lower()
    return 'tiro' in action_lower and 'libero' not in action_lower


def is_field_goal_made(action):
    """Verifica se l'azione è un tiro da campo segnato."""
    if pd.isna(action):
        return False
    action_lower = action.lower()
    return ('tiro realizzato' in action_lower or 'tiro segnato' in action_lower) and 'libero' not in action_lower


def is_three_point_attempt(action):
    """Verifica se l'azione è un tentativo da 3 punti."""
    if pd.isna(action):
        return False
    return '3 punti' in action.lower()


def is_three_point_made(action):
    """Verifica se l'azione è un tiro da 3 segnato."""
    if pd.isna(action):
        return False
    action_lower = action.lower()
    return 'tiro realizzato da 3 punti' in action_lower


def is_free_throw_attempt(action):
    """Verifica se l'azione è un tiro libero."""
    if pd.isna(action):
        return False
    return 'tiro libero' in action.lower()


def is_free_throw_made(action):
    """Verifica se l'azione è un tiro libero segnato."""
    if pd.isna(action):
        return False
    return 'tiro libero segnato' in action.lower()


# ============ MOMENTI DECISIVI ============

def compute_clutch_stats(pbp_df):
    """
    Calcola statistiche nei momenti clutch per giocatore.
    Clutch = ultimi 2 minuti di Q4 con gap <= 5 punti.

    Returns:
        DataFrame con stats complete incluse percentuali di tiro
    """
    if pbp_df is None or pbp_df.empty:
        return pd.DataFrame()

    # Filtra eventi clutch e rimuovi righe senza player valido
    clutch_df = pbp_df[(pbp_df['clutch'] == True) &
                       (pbp_df['player'].notna()) &
                       (pbp_df['player'] != '')].copy()

    if clutch_df.empty:
        return pd.DataFrame()

    # Aggiungi colonne per tipi di tiro
    clutch_df['is_fg_attempt'] = clutch_df['action_type'].apply(is_field_goal_attempt)
    clutch_df['is_fg_made'] = clutch_df['action_type'].apply(is_field_goal_made)
    clutch_df['is_3pt_attempt'] = clutch_df['action_type'].apply(is_three_point_attempt)
    clutch_df['is_3pt_made'] = clutch_df['action_type'].apply(is_three_point_made)
    clutch_df['is_ft_attempt'] = clutch_df['action_type'].apply(is_free_throw_attempt)
    clutch_df['is_ft_made'] = clutch_df['action_type'].apply(is_free_throw_made)

    # Aggrega per giocatore
    clutch_stats = clutch_df.groupby(['player', 'team']).agg({
        'points': 'sum',
        'game_code': 'nunique',
        'is_fg_attempt': 'sum',
        'is_fg_made': 'sum',
        'is_3pt_attempt': 'sum',
        'is_3pt_made': 'sum',
        'is_ft_attempt': 'sum',
        'is_ft_made': 'sum',
    }).reset_index()

    clutch_stats.columns = ['player', 'team', 'clutch_points', 'clutch_games',
                            'fg_attempts', 'fg_made', '3pt_attempts', '3pt_made',
                            'ft_attempts', 'ft_made']

    # Calcola percentuali
    clutch_stats['fg_pct'] = np.where(
        clutch_stats['fg_attempts'] > 0,
        (clutch_stats['fg_made'] / clutch_stats['fg_attempts'] * 100).round(1),
        0
    )
    clutch_stats['3pt_pct'] = np.where(
        clutch_stats['3pt_attempts'] > 0,
        (clutch_stats['3pt_made'] / clutch_stats['3pt_attempts'] * 100).round(1),
        0
    )
    clutch_stats['ft_pct'] = np.where(
        clutch_stats['ft_attempts'] > 0,
        (clutch_stats['ft_made'] / clutch_stats['ft_attempts'] * 100).round(1),
        0
    )

    # Calcola punti totali per confronto (solo player validi)
    valid_scoring = pbp_df[(pbp_df['points'] > 0) & (pbp_df['player'].notna()) & (pbp_df['player'] != '')]
    total_points = valid_scoring.groupby('player')['points'].sum()
    clutch_stats['total_points'] = clutch_stats['player'].map(total_points).fillna(0)

    # Percentuale punti in clutch
    clutch_stats['clutch_pct'] = np.where(
        clutch_stats['total_points'] > 0,
        (clutch_stats['clutch_points'] / clutch_stats['total_points'] * 100).round(1),
        0
    )

    # Media punti clutch per partita clutch
    clutch_stats['clutch_ppg'] = (
        clutch_stats['clutch_points'] / clutch_stats['clutch_games']
    ).round(2)

    # Tiri totali tentati (responsabilità)
    clutch_stats['total_shots'] = clutch_stats['fg_attempts'] + clutch_stats['ft_attempts']

    return clutch_stats.sort_values('clutch_points', ascending=False)


def compute_clutch_responsibility(pbp_df, min_games=3):
    """
    Classifica chi si prende più responsabilità nei momenti clutch.
    Basato su tiri tentati, non solo segnati.

    Returns:
        DataFrame ordinato per tiri tentati in clutch
    """
    clutch_stats = compute_clutch_stats(pbp_df)

    if clutch_stats.empty:
        return pd.DataFrame()

    # Filtra per minimo partite
    responsibility = clutch_stats[clutch_stats['clutch_games'] >= min_games].copy()

    if responsibility.empty:
        return pd.DataFrame()

    # Calcola tiri per partita
    responsibility['shots_per_game'] = (
        responsibility['total_shots'] / responsibility['clutch_games']
    ).round(2)

    # Calcola TS% (True Shooting %)
    # TS% = PTS / (2 * (FGA + 0.44 * FTA))
    responsibility['ts_pct'] = np.where(
        (responsibility['fg_attempts'] + 0.44 * responsibility['ft_attempts']) > 0,
        (responsibility['clutch_points'] /
         (2 * (responsibility['fg_attempts'] + 0.44 * responsibility['ft_attempts'])) * 100).round(1),
        0
    )

    return responsibility.sort_values('total_shots', ascending=False)


def compute_closer_rankings(pbp_df, min_clutch_games=3):
    """
    Classifica i "closer" - giocatori che segnano di più nei momenti decisivi.

    Args:
        pbp_df: DataFrame PBP
        min_clutch_games: Minimo partite clutch per essere incluso

    Returns:
        DataFrame con ranking dei closer
    """
    clutch_stats = compute_clutch_stats(pbp_df)

    if clutch_stats.empty:
        return pd.DataFrame()

    # Filtra per minimo partite
    closers = clutch_stats[clutch_stats['clutch_games'] >= min_clutch_games].copy()

    # Calcola un "closer score" combinato
    # Peso: punti totali clutch + bonus per efficienza (ppg)
    closers['closer_score'] = (
        closers['clutch_points'] * 0.7 +
        closers['clutch_ppg'] * closers['clutch_games'] * 0.3
    ).round(1)

    return closers.sort_values('closer_score', ascending=False)


def compute_q4_heroes(pbp_df, min_games=5):
    """
    Trova i giocatori che performano meglio nel 4° quarto rispetto al resto.

    Returns:
        DataFrame con: player, team, q4_points, q4_ppg, other_ppg, q4_boost
    """
    if pbp_df is None or pbp_df.empty:
        return pd.DataFrame()

    # Filtra righe con player valido
    valid_df = pbp_df[(pbp_df['player'].notna()) & (pbp_df['player'] != '')]

    # Punti nel Q4
    q4_df = valid_df[(valid_df['quarter'] == 4) & (valid_df['points'] > 0)]
    q4_stats = q4_df.groupby(['player', 'team']).agg({
        'points': 'sum',
        'game_code': 'nunique'
    }).reset_index()
    q4_stats.columns = ['player', 'team', 'q4_points', 'q4_games']

    # Punti nei quarti 1-3
    other_df = valid_df[(valid_df['quarter'] < 4) & (valid_df['points'] > 0)]
    other_stats = other_df.groupby('player').agg({
        'points': 'sum',
        'game_code': 'nunique'
    }).reset_index()
    other_stats.columns = ['player', 'other_points', 'other_games']

    # Merge
    heroes = q4_stats.merge(other_stats, on='player', how='inner')

    # Filtra per minimo partite
    heroes = heroes[heroes['q4_games'] >= min_games]

    if heroes.empty:
        return pd.DataFrame()

    # Calcola PPG
    heroes['q4_ppg'] = (heroes['q4_points'] / heroes['q4_games']).round(2)
    heroes['other_ppg'] = (heroes['other_points'] / heroes['other_games']).round(2)

    # Q4 boost: quanto migliora nel Q4 (in percentuale)
    heroes['q4_boost'] = (
        (heroes['q4_ppg'] - heroes['other_ppg']) / heroes['other_ppg'] * 100
    ).round(1)

    # Solo chi migliora almeno un po'
    heroes = heroes[heroes['q4_boost'] > -50]  # Escludi outlier negativi

    return heroes.sort_values('q4_boost', ascending=False)


# ============ ANDAMENTO PARTITE ============

def compute_quarter_distribution(quarters_df):
    """
    Calcola distribuzione punti per quarto per squadra.

    Returns:
        DataFrame con: team, q1_avg, q2_avg, q3_avg, q4_avg,
                       best_quarter, worst_quarter, q4_vs_q1
    """
    if quarters_df is None or quarters_df.empty:
        return pd.DataFrame()

    # Espandi i dati
    rows = []
    for _, game in quarters_df.iterrows():
        # Home team
        home_quarters = game['home']
        rows.append({
            'team': game['home_team'],
            'q1': home_quarters.get('q1', 0),
            'q2': home_quarters.get('q2', 0),
            'q3': home_quarters.get('q3', 0),
            'q4': home_quarters.get('q4', 0),
            'game_code': game['game_code']
        })
        # Away team
        away_quarters = game['away']
        rows.append({
            'team': game['away_team'],
            'q1': away_quarters.get('q1', 0),
            'q2': away_quarters.get('q2', 0),
            'q3': away_quarters.get('q3', 0),
            'q4': away_quarters.get('q4', 0),
            'game_code': game['game_code']
        })

    games_df = pd.DataFrame(rows)

    # Aggrega per squadra
    team_quarters = games_df.groupby('team').agg({
        'q1': 'mean',
        'q2': 'mean',
        'q3': 'mean',
        'q4': 'mean',
        'game_code': 'count'
    }).reset_index()

    team_quarters.columns = ['team', 'q1_avg', 'q2_avg', 'q3_avg', 'q4_avg', 'games']

    # Round
    for col in ['q1_avg', 'q2_avg', 'q3_avg', 'q4_avg']:
        team_quarters[col] = team_quarters[col].round(1)

    # Best e worst quarter
    quarter_cols = ['q1_avg', 'q2_avg', 'q3_avg', 'q4_avg']
    quarter_names = ['Q1', 'Q2', 'Q3', 'Q4']

    team_quarters['best_quarter'] = team_quarters[quarter_cols].idxmax(axis=1).map(
        dict(zip(quarter_cols, quarter_names))
    )
    team_quarters['worst_quarter'] = team_quarters[quarter_cols].idxmin(axis=1).map(
        dict(zip(quarter_cols, quarter_names))
    )

    # Q4 vs Q1: squadre che finiscono forte vs partono forte
    team_quarters['q4_vs_q1'] = (team_quarters['q4_avg'] - team_quarters['q1_avg']).round(1)

    return team_quarters.sort_values('q4_avg', ascending=False)


def compute_scoring_runs(pbp_df, min_run=8):
    """
    Identifica i "run" (parziali) significativi nelle partite.
    Un run è una sequenza di punti consecutivi di una squadra.
    Deduce i punti dalla sequenza di punteggio, non dal testo delle azioni.

    Args:
        pbp_df: DataFrame PBP
        min_run: Minimo punti per considerare un run significativo

    Returns:
        DataFrame con: team, runs_made, runs_allowed, best_run,
                       avg_run_made, avg_run_allowed
    """
    if pbp_df is None or pbp_df.empty:
        return pd.DataFrame()

    runs_data = []

    # Analizza partita per partita
    for game_code in pbp_df['game_code'].unique():
        game_df = pbp_df[pbp_df['game_code'] == game_code].copy()
        game_df = game_df.sort_values('total_seconds')

        home_team = game_df['home_team'].iloc[0]
        away_team = game_df['away_team'].iloc[0]

        # Estrai sequenza unica di punteggi (rimuovi duplicati consecutivi)
        prev_home, prev_away = 0, 0
        score_changes = []

        for _, event in game_df.iterrows():
            curr_home = event['score_home']
            curr_away = event['score_away']

            # Salta se punteggio non cambiato o diminuito (dati corrotti)
            if curr_home == prev_home and curr_away == prev_away:
                continue
            if curr_home < prev_home or curr_away < prev_away:
                continue

            # Determina chi ha segnato dalla differenza di punteggio
            home_pts = curr_home - prev_home
            away_pts = curr_away - prev_away

            if home_pts > 0 and away_pts == 0:
                score_changes.append(('home', home_pts))
            elif away_pts > 0 and home_pts == 0:
                score_changes.append(('away', away_pts))
            # Se entrambi cambiano, potrebbero essere eventi multipli - ignora

            prev_home, prev_away = curr_home, curr_away

        # Trova i run dalla sequenza di cambi punteggio
        current_run_team = None
        current_run_points = 0

        for team_type, pts in score_changes:
            scoring_team = home_team if team_type == 'home' else away_team

            if scoring_team == current_run_team:
                current_run_points += pts
            else:
                # Salva il run precedente se significativo
                if current_run_points >= min_run and current_run_team:
                    other_team = away_team if current_run_team == home_team else home_team
                    runs_data.append({
                        'team': current_run_team,
                        'opponent': other_team,
                        'run_points': current_run_points,
                        'game_code': game_code
                    })

                # Inizia nuovo run
                current_run_team = scoring_team
                current_run_points = pts

        # Salva l'ultimo run
        if current_run_points >= min_run and current_run_team:
            other_team = away_team if current_run_team == home_team else home_team
            runs_data.append({
                'team': current_run_team,
                'opponent': other_team,
                'run_points': current_run_points,
                'game_code': game_code
            })

    if not runs_data:
        return pd.DataFrame()

    runs_df = pd.DataFrame(runs_data)

    # Statistiche per squadra - run fatti
    runs_made = runs_df.groupby('team').agg({
        'run_points': ['count', 'max', 'mean']
    }).reset_index()
    runs_made.columns = ['team', 'runs_made', 'best_run', 'avg_run_made']

    # Run subiti
    runs_allowed = runs_df.groupby('opponent').agg({
        'run_points': ['count', 'max', 'mean']
    }).reset_index()
    runs_allowed.columns = ['team', 'runs_allowed', 'worst_run_allowed', 'avg_run_allowed']

    # Merge
    team_runs = runs_made.merge(runs_allowed, on='team', how='outer').fillna(0)

    # Round
    team_runs['avg_run_made'] = team_runs['avg_run_made'].round(1)
    team_runs['avg_run_allowed'] = team_runs['avg_run_allowed'].round(1)
    team_runs['runs_made'] = team_runs['runs_made'].astype(int)
    team_runs['runs_allowed'] = team_runs['runs_allowed'].astype(int)
    team_runs['best_run'] = team_runs['best_run'].astype(int)
    team_runs['worst_run_allowed'] = team_runs['worst_run_allowed'].astype(int)

    # Run differential
    team_runs['run_diff'] = team_runs['runs_made'] - team_runs['runs_allowed']

    return team_runs.sort_values('run_diff', ascending=False)


def compute_comeback_stats(pbp_df, min_deficit=10, comeback_threshold=2):
    """
    Trova le squadre che rimontano da grandi deficit.

    Una "rimonta" = da -min_deficit o peggio, tornare almeno a -comeback_threshold
    Una "rimonta riuscita" = rimonta che finisce con vittoria

    Args:
        pbp_df: DataFrame PBP
        min_deficit: Minimo svantaggio da cui partire (default 10)
        comeback_threshold: Scarto massimo per considerare rimonta completata (default 2)

    Returns:
        tuple: (DataFrame aggregato, DataFrame dettagli partite)
    """
    if pbp_df is None or pbp_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    comeback_data = []
    blown_lead_data = []

    # Analizza partita per partita
    for game_code in pbp_df['game_code'].unique():
        game_df = pbp_df[pbp_df['game_code'] == game_code].copy()

        if game_df.empty or 'gap' not in game_df.columns:
            continue

        # Ordina per tempo E punteggio totale per gestire eventi con stesso timestamp
        game_df['total_score'] = game_df['score_home'] + game_df['score_away']
        game_df = game_df.sort_values(['total_seconds', 'total_score'])

        # Rimuovi eventi anomali dove il punteggio diminuisce
        valid_mask = [True]  # Primo evento sempre valido
        prev_home = game_df.iloc[0]['score_home']
        prev_away = game_df.iloc[0]['score_away']

        for i in range(1, len(game_df)):
            row = game_df.iloc[i]
            # Valido se il punteggio non diminuisce (tolleranza per errori minori)
            if row['score_home'] >= prev_home - 1 and row['score_away'] >= prev_away - 1:
                valid_mask.append(True)
                prev_home = row['score_home']
                prev_away = row['score_away']
            else:
                valid_mask.append(False)

        game_df = game_df[valid_mask]

        if game_df.empty:
            continue

        home_team = game_df['home_team'].iloc[0]
        away_team = game_df['away_team'].iloc[0]

        # Gap e punteggio finale
        final_gap = game_df.iloc[-1]['gap'] if len(game_df) > 0 else 0
        final_home = 0
        final_away = 0
        if 'score_home' in game_df.columns and 'score_away' in game_df.columns:
            final_home = int(game_df.iloc[-1]['score_home'])
            final_away = int(game_df.iloc[-1]['score_away'])
            final_gap = final_home - final_away

        home_won = final_gap > 0

        # Traccia rimonte per HOME team
        home_max_deficit = 0
        home_max_deficit_time = 0
        home_max_deficit_quarter = 0
        home_came_back = False

        for _, event in game_df.iterrows():
            gap = event['gap']
            if gap < -min_deficit:
                if abs(gap) > home_max_deficit:
                    home_max_deficit = abs(gap)
                    home_max_deficit_time = event.get('total_seconds', 0)
                    home_max_deficit_quarter = event.get('quarter', 0)
            if home_max_deficit >= min_deficit and gap >= -comeback_threshold:
                home_came_back = True
                break

        if home_max_deficit >= min_deficit and home_came_back:
            # Trova il massimo vantaggio/minimo svantaggio DOPO il momento del deficit
            best_gap_after = -home_max_deficit  # Inizia dal peggior punto
            best_gap_after_time = home_max_deficit_time
            best_gap_after_quarter = home_max_deficit_quarter
            passed_deficit = False

            for _, event in game_df.iterrows():
                gap = event['gap']
                # Segnala quando superiamo il momento del max deficit
                if event.get('total_seconds', 0) >= home_max_deficit_time:
                    passed_deficit = True
                # Cerca il miglior gap solo DOPO il momento del deficit
                if passed_deficit and gap > best_gap_after:
                    best_gap_after = gap
                    best_gap_after_time = event.get('total_seconds', 0)
                    best_gap_after_quarter = event.get('quarter', 0)

            # Converti tempi in minuti:secondi
            mins = int(home_max_deficit_time // 60)
            secs = int(home_max_deficit_time % 60)
            best_mins = int(best_gap_after_time // 60)
            best_secs = int(best_gap_after_time % 60)

            comeback_data.append({
                'team': home_team,
                'opponent': away_team,
                'deficit': home_max_deficit,
                'deficit_time': f"{mins}:{secs:02d}",
                'deficit_quarter': int(home_max_deficit_quarter),
                'best_after': best_gap_after,  # Positivo = in vantaggio
                'best_after_time': f"{best_mins}:{best_secs:02d}",
                'best_after_quarter': int(best_gap_after_quarter),
                'final_score': f"{final_home}-{final_away}",
                'won': home_won,
                'game_code': game_code
            })
            # Dettaglio blown lead (prospettiva away team che subisce rimonta)
            blown_lead_data.append({
                'team': away_team,
                'opponent': home_team,
                'max_lead': home_max_deficit,
                'max_lead_time': f"{mins}:{secs:02d}",
                'max_lead_quarter': int(home_max_deficit_quarter),
                'worst_after': -best_gap_after,  # Negativo = in svantaggio
                'worst_after_time': f"{best_mins}:{best_secs:02d}",
                'worst_after_quarter': int(best_gap_after_quarter),
                'final_score': f"{final_away}-{final_home}",
                'lost': home_won,  # away team perde se home vince
                'game_code': game_code
            })

        # Traccia rimonte per AWAY team
        away_max_deficit = 0
        away_max_deficit_time = 0
        away_max_deficit_quarter = 0
        away_came_back = False

        for _, event in game_df.iterrows():
            gap = event['gap']
            if gap > min_deficit:
                if gap > away_max_deficit:
                    away_max_deficit = gap
                    away_max_deficit_time = event.get('total_seconds', 0)
                    away_max_deficit_quarter = event.get('quarter', 0)
            if away_max_deficit >= min_deficit and gap <= comeback_threshold:
                away_came_back = True
                break

        if away_max_deficit >= min_deficit and away_came_back:
            # Trova il massimo vantaggio DOPO il momento del deficit per away
            best_gap_after = away_max_deficit  # Inizia dal peggior punto (positivo per away = sotto)
            best_gap_after_time = away_max_deficit_time
            best_gap_after_quarter = away_max_deficit_quarter
            passed_deficit = False

            for _, event in game_df.iterrows():
                gap = event['gap']
                # Segnala quando superiamo il momento del max deficit
                if event.get('total_seconds', 0) >= away_max_deficit_time:
                    passed_deficit = True
                # Per away, gap negativo = away avanti, quindi cerchiamo il gap più basso
                if passed_deficit and gap < best_gap_after:
                    best_gap_after = gap
                    best_gap_after_time = event.get('total_seconds', 0)
                    best_gap_after_quarter = event.get('quarter', 0)

            mins = int(away_max_deficit_time // 60)
            secs = int(away_max_deficit_time % 60)
            best_mins = int(best_gap_after_time // 60)
            best_secs = int(best_gap_after_time % 60)

            # Per away: best_after negativo = in vantaggio, lo invertiamo per coerenza
            comeback_data.append({
                'team': away_team,
                'opponent': home_team,
                'deficit': away_max_deficit,
                'deficit_time': f"{mins}:{secs:02d}",
                'deficit_quarter': int(away_max_deficit_quarter),
                'best_after': -best_gap_after,  # Inverti: positivo = in vantaggio
                'best_after_time': f"{best_mins}:{best_secs:02d}",
                'best_after_quarter': int(best_gap_after_quarter),
                'final_score': f"{final_away}-{final_home}",
                'won': not home_won,
                'game_code': game_code
            })
            # Dettaglio blown lead (prospettiva home team che subisce rimonta)
            blown_lead_data.append({
                'team': home_team,
                'opponent': away_team,
                'max_lead': away_max_deficit,
                'max_lead_time': f"{mins}:{secs:02d}",
                'max_lead_quarter': int(away_max_deficit_quarter),
                'worst_after': best_gap_after,  # gap positivo = home sotto
                'worst_after_time': f"{best_mins}:{best_secs:02d}",
                'worst_after_quarter': int(best_gap_after_quarter),
                'final_score': f"{final_home}-{final_away}",
                'lost': not home_won,  # home team perde se home non vince
                'game_code': game_code
            })

    if not comeback_data:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    comeback_df = pd.DataFrame(comeback_data)
    details_df = comeback_df.copy()  # Dettagli singole partite rimonte

    # Dettagli blown leads
    blown_details_df = pd.DataFrame(blown_lead_data) if blown_lead_data else pd.DataFrame()

    # Statistiche aggregate per squadra
    comebacks = comeback_df.groupby('team').agg({
        'deficit': ['count', 'max', 'mean'],
        'won': 'sum'
    }).reset_index()
    comebacks.columns = ['team', 'comebacks', 'max_deficit', 'avg_deficit', 'comeback_wins']

    # Blown leads aggregate
    if blown_lead_data:
        blown_df = pd.DataFrame(blown_lead_data)
        blown = blown_df.groupby('team').agg({
            'max_lead': ['count', 'max'],
            'lost': 'sum'
        }).reset_index()
        blown.columns = ['team', 'blown_leads', 'worst_blown', 'blown_losses']
        comebacks = comebacks.merge(blown, on='team', how='outer').fillna(0)
    else:
        comebacks['blown_leads'] = 0
        comebacks['worst_blown'] = 0
        comebacks['blown_losses'] = 0

    comebacks['avg_deficit'] = comebacks['avg_deficit'].round(1)
    comebacks['comebacks'] = comebacks['comebacks'].astype(int)
    comebacks['comeback_wins'] = comebacks['comeback_wins'].astype(int)
    comebacks['blown_leads'] = comebacks['blown_leads'].astype(int)
    comebacks['max_deficit'] = comebacks['max_deficit'].astype(int)
    comebacks['worst_blown'] = comebacks['worst_blown'].astype(int)
    comebacks['blown_losses'] = comebacks['blown_losses'].astype(int)

    comebacks['comeback_score'] = (
        comebacks['comeback_wins'] * 2 +
        comebacks['comebacks'] -
        comebacks['blown_losses'] * 2 -
        comebacks['blown_leads']
    )

    return comebacks.sort_values('comeback_score', ascending=False), details_df, blown_details_df


def get_pbp_summary(campionato_filter):
    """
    Ottiene statistiche riassuntive PBP per un campionato.
    """
    pbp_df = load_pbp_data(campionato_filter)
    quarters_df = load_quarters_data(campionato_filter)

    if pbp_df is None:
        return {
            'total_events': 0,
            'total_games': 0,
            'clutch_events': 0,
            'total_points_scored': 0
        }

    return {
        'total_events': len(pbp_df),
        'total_games': pbp_df['game_code'].nunique(),
        'clutch_events': pbp_df['clutch'].sum(),
        'total_points_scored': pbp_df['points'].sum()
    }


def compute_player_quarter_activity(pbp_df):
    """
    Calcola l'attività dei giocatori per quarto basata sugli eventi PBP.
    Proxy per i minuti giocati basato sul numero di eventi.

    Returns:
        DataFrame con: player, team, q1_events, q2_events, q3_events, q4_events,
                       total_events, q4_share (% eventi in Q4)
    """
    if pbp_df is None or pbp_df.empty:
        return pd.DataFrame()

    # Filtra righe con player valido
    valid_df = pbp_df[(pbp_df['player'].notna()) & (pbp_df['player'] != '')]

    # Conta eventi per giocatore per quarto
    activity = valid_df.groupby(['player', 'team', 'quarter']).size().unstack(fill_value=0)
    activity = activity.reset_index()

    # Rinomina colonne
    quarter_cols = {1: 'q1_events', 2: 'q2_events', 3: 'q3_events', 4: 'q4_events'}
    for q, col_name in quarter_cols.items():
        if q not in activity.columns:
            activity[col_name] = 0
        else:
            activity = activity.rename(columns={q: col_name})

    # Assicura che tutte le colonne esistano
    for col in ['q1_events', 'q2_events', 'q3_events', 'q4_events']:
        if col not in activity.columns:
            activity[col] = 0

    # Calcola totale e percentuale Q4
    activity['total_events'] = (
        activity['q1_events'] + activity['q2_events'] +
        activity['q3_events'] + activity['q4_events']
    )

    activity['q4_share'] = np.where(
        activity['total_events'] > 0,
        (activity['q4_events'] / activity['total_events'] * 100).round(1),
        0
    )

    return activity.sort_values('total_events', ascending=False)


def compute_team_player_distribution(pbp_df, min_events=20):
    """
    Calcola la distribuzione degli eventi tra i giocatori per squadra per quarto.

    Returns:
        Dict con {team: DataFrame con distribuzione giocatori per quarto}
    """
    if pbp_df is None or pbp_df.empty:
        return {}

    activity = compute_player_quarter_activity(pbp_df)

    # Filtra giocatori con almeno min_events
    activity = activity[activity['total_events'] >= min_events]

    team_distributions = {}

    for team in activity['team'].unique():
        team_df = activity[activity['team'] == team].copy()

        # Calcola percentuale sul totale squadra per quarto
        for col in ['q1_events', 'q2_events', 'q3_events', 'q4_events']:
            total = team_df[col].sum()
            if total > 0:
                team_df[col.replace('_events', '_pct')] = (team_df[col] / total * 100).round(1)
            else:
                team_df[col.replace('_events', '_pct')] = 0

        team_distributions[team] = team_df.sort_values('total_events', ascending=False)

    return team_distributions
