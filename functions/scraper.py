"""
Modulo per lo scraping delle statistiche LNP.
"""

import time
import pickle
import os
import re
from io import StringIO

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import undetected_chromedriver as uc


def read_play_by_play(soup):
    """
    Estrae il play-by-play completo dalla pagina.

    Returns:
        Lista di dizionari con: quarter, time, score_home, score_away,
        team, player, jersey, action_type
    """
    pbp_events = []

    # Trova tutti gli eventi del play-by-play
    events = soup.find_all('div', class_='filmlistnew', attrs={'q': True})

    for event in events:
        try:
            # Tempo e punteggio
            score_time = event.find(class_='filmlistnewscoretime')
            score_score = event.find(class_='filmlistnewscorescore')

            if not score_time or not score_score:
                continue

            time_text = score_time.get_text(strip=True)
            score_text = score_score.get_text(strip=True)

            # Estrai quarter dal testo (es. "Q4 09:59") - più affidabile dell'attributo q
            quarter_match = re.search(r'Q(\d)', time_text)
            quarter = quarter_match.group(1) if quarter_match else event.get('q', '0')

            # Estrai minuto dal formato "Q4 09:59"
            time_match = re.search(r'(\d{1,2}:\d{2})', time_text)
            game_time = time_match.group(1) if time_match else ''

            # Estrai punteggi dal formato "59-69"
            score_parts = score_text.split('-')
            score_home = int(score_parts[0]) if len(score_parts) == 2 else 0
            score_away = int(score_parts[1]) if len(score_parts) == 2 else 0

            # Squadra
            team_elem = event.find(class_='filmlistnewteam')
            team = team_elem.get_text(strip=True) if team_elem else ''

            # Numero maglia
            jersey_elem = event.find(class_='filmlistnewjersey')
            jersey = jersey_elem.get_text(strip=True) if jersey_elem else ''

            # Nome giocatore
            name_elem = event.find(class_='filmlistnewname')
            player = name_elem.get_text(strip=True) if name_elem else ''

            # Tipo di azione
            action_elem = event.find(class_='filmlistnewfilminfo')
            action_type = action_elem.get_text(strip=True) if action_elem else ''

            # Salta eventi vuoti (es. "Fine del tempo")
            if not player and 'Fine' in action_type:
                continue

            pbp_events.append({
                'quarter': int(quarter) if quarter.isdigit() else 0,
                'time': game_time,
                'score_home': score_home,
                'score_away': score_away,
                'team': team,
                'player': player,
                'jersey': jersey,
                'action_type': action_type
            })

        except Exception as e:
            continue

    return pbp_events


def read_quarter_scores(soup):
    """
    Estrae i punteggi parziali per ogni quarter.

    Returns:
        Dizionario con punteggi per quarter:
        {'home': {'q1': 17, 'q2': 15, ...}, 'away': {'q1': 25, ...}}
    """
    quarter_scores = {'home': {}, 'away': {}}

    # Trova riga squadra casa
    home_row = soup.find('tr', class_='hquarter')
    if home_row:
        for i in range(1, 6):
            cell = home_row.find(id=f'hp{i}')
            if cell:
                text = cell.get_text(strip=True)
                if text.isdigit():
                    quarter_name = f'q{i}' if i < 5 else 'ot'
                    quarter_scores['home'][quarter_name] = int(text)

    # Trova riga squadra ospite
    away_row = soup.find('tr', class_='aquarter')
    if away_row:
        for i in range(1, 6):
            cell = away_row.find(id=f'ap{i}')
            if cell:
                text = cell.get_text(strip=True)
                if text.isdigit():
                    quarter_name = f'q{i}' if i < 5 else 'ot'
                    quarter_scores['away'][quarter_name] = int(text)

    return quarter_scores


def read_stats_table(cl='hstat', soup=None):
    """Legge la tabella delle statistiche di una squadra."""
    stat = soup.find(class_=cl)
    if not stat:
        return None
    table = stat.find('table')
    if not table:
        return None

    stats = pd.read_html(StringIO(str(table)))[0]
    stats = stats.iloc[0:-1]
    stats = stats.filter(regex='^(?!Unnamed)')
    stats['Giocatore'] = stats['Giocatore'].str.replace('\xa0', ' ')

    to_minutes = lambda x: int(x.split(':')[0]) + int(x.split(':')[1]) / 60
    stats['MIN'] = stats['MIN'].str.replace('[^0-9:]+', '', regex=True)
    stats['Minutes'] = stats['MIN'].apply(to_minutes)
    stats["pm_permin"] = stats['+/-'] / stats['Minutes']

    return stats


def load_existing_data(output_file):
    """Carica dati esistenti se il file esiste."""
    if os.path.exists(output_file):
        with open(output_file, 'rb') as f:
            df = pickle.load(f)
            print(f"  Caricati {len(df)} record esistenti da {output_file}")
            return df
    return None


def get_scraped_games(existing_df):
    """Estrae i codici delle partite già scaricate."""
    if existing_df is None or 'game_code' not in existing_df.columns:
        return set()
    return set(existing_df['game_code'].unique())


def scrape_single_game(driver, url, code, config, extract_pbp=False):
    """
    Scarica i dati di una singola partita.

    Args:
        driver: istanza del browser
        url: URL della partita
        code: codice della partita
        config: configurazione del campionato
        extract_pbp: se True, estrae anche play-by-play e parziali

    Returns:
        Se extract_pbp=False: DataFrame con statistiche
        Se extract_pbp=True: (DataFrame stats, lista pbp, dict parziali)
    """
    driver.get(url)
    time.sleep(2)

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Punteggio
    divs = soup.select('span.hscore-numbers div')
    try:
        hscore = int(''.join([div['rel'] for div in divs[0:3]]))
    except:
        return None if not extract_pbp else (None, None, None)

    divs = soup.select('span.ascore-numbers div')
    ascore = int(''.join([div['rel'] for div in divs[0:3]]))

    # Minuti totali
    TTm = soup.find_all(class_="TTm")
    total_mins = 0
    for tm in TTm:
        if ":" not in tm.text:
            total_mins = max(total_mins, int(int(tm.text) / 5))

    # Squadre
    teams = soup.find_all(class_="font-smoothing")
    if len(teams) < 2:
        return None if not extract_pbp else (None, None, None)

    home_team = teams[0].text
    away_team = teams[1].text

    if len(home_team) == 0 or total_mins < 40:
        return None if not extract_pbp else (None, None, None)

    # Statistiche
    stats_home = read_stats_table(cl='hstat', soup=soup)
    stats_away = read_stats_table(cl='astat', soup=soup)

    if stats_home is None or stats_away is None:
        return None if not extract_pbp else (None, None, None)

    stats_home['Team'] = home_team
    stats_home['Opponent'] = away_team
    stats_away['Team'] = away_team
    stats_away['Opponent'] = home_team

    stats_away['Gap'] = ascore - hscore
    stats_home['Gap'] = hscore - ascore
    stats_away['Gap_permin'] = (ascore - hscore) / total_mins
    stats_home['Gap_permin'] = (hscore - ascore) / total_mins

    # Indicatore casa/trasferta
    stats_home['is_home'] = True
    stats_away['is_home'] = False

    game_stats = pd.concat([stats_home, stats_away])

    # Metadati per tracciare le partite
    campionato_name = os.path.basename(config['output_file']).replace('season_stats_', '').replace('.pkl', '')
    game_stats['Campionato'] = campionato_name
    game_stats['game_code'] = code
    game_stats['home_team'] = home_team
    game_stats['away_team'] = away_team
    game_stats['home_score'] = hscore
    game_stats['away_score'] = ascore

    if not extract_pbp:
        return game_stats

    # Estrai play-by-play e parziali
    pbp_events = read_play_by_play(soup)
    quarter_scores = read_quarter_scores(soup)

    # Aggiungi metadati al play-by-play
    for event in pbp_events:
        event['game_code'] = code
        event['campionato'] = campionato_name
        event['home_team'] = home_team
        event['away_team'] = away_team

    # Aggiungi metadati ai parziali
    quarter_scores['game_code'] = code
    quarter_scores['campionato'] = campionato_name
    quarter_scores['home_team'] = home_team
    quarter_scores['away_team'] = away_team

    return game_stats, pbp_events, quarter_scores


def scrape_campionato(config, driver, incremental=True, include_pbp=True):
    """
    Scarica le statistiche per un singolo campionato/girone.

    Args:
        config: dizionario con la configurazione del campionato
        driver: istanza del browser
        incremental: se True, scarica solo le partite nuove
        include_pbp: se True, scarica anche play-by-play e parziali

    Returns:
        DataFrame con tutte le statistiche (vecchie + nuove)
    """
    output_file = config['output_file']
    url_prefix = config['url_prefix']
    start_code = config['start_code']
    end_code = config.get('end_code')  # Può essere None

    # File per pbp e parziali
    output_dir = os.path.dirname(output_file)
    base_name = os.path.basename(output_file).replace('season_stats_', '').replace('.pkl', '')
    pbp_file = os.path.join(output_dir, f"pbp_{base_name}.pkl")
    quarters_file = os.path.join(output_dir, f"quarters_{base_name}.pkl")

    if end_code:
        print(f"\nScraping {base_name} - partite {start_code}-{end_code}...")
    else:
        print(f"\nScraping {base_name} - da partita {start_code} (auto-stop dopo 5 vuote)...")

    if include_pbp:
        print(f"  (include play-by-play e parziali)")

    # Carica dati esistenti
    existing_df = load_existing_data(output_file) if incremental else None
    scraped_codes = get_scraped_games(existing_df)

    existing_pbp = load_existing_pbp(pbp_file) if (incremental and include_pbp) else None
    existing_quarters = load_existing_quarters(quarters_file) if (incremental and include_pbp) else None

    if scraped_codes:
        print(f"  Partite già scaricate: {len(scraped_codes)}")
        if end_code is None:
            max_scraped = max(scraped_codes)
            print(f"  Ultimo game_code: {max_scraped}")

    new_games = []
    new_pbp_events = []
    new_quarters_list = []
    skipped = 0
    empty_streak = 0  # Contatore pagine vuote consecutive (solo dopo max scraped)
    max_empty = 5     # Stop dopo 5 pagine vuote consecutive

    code = start_code
    while True:
        # Condizione di uscita con end_code definito
        if end_code is not None and code > end_code:
            break

        # Condizione di uscita con end_code None (5 pagine vuote consecutive OLTRE l'ultimo scraped)
        if end_code is None and empty_streak >= max_empty:
            print(f"  Stop: {max_empty} pagine vuote consecutive")
            break

        # Skip se già scaricata (modalità incrementale)
        if incremental and code in scraped_codes:
            skipped += 1
            empty_streak = 0  # Reset: siamo ancora nella zona con partite
            code += 1
            continue

        url = f'https://netcasting3.webpont.com/?{url_prefix}{code}'

        if include_pbp:
            result = scrape_single_game(driver, url, code, config, extract_pbp=True)
            if result[0] is not None:
                game_data, pbp_events, quarter_scores = result
                new_pbp_events.extend(pbp_events)
                new_quarters_list.append(quarter_scores)
            else:
                game_data = None
        else:
            game_data = scrape_single_game(driver, url, code, config, extract_pbp=False)

        if game_data is not None:
            new_games.append(game_data)
            home = game_data['home_team'].iloc[0]
            away = game_data['away_team'].iloc[0]
            hs = game_data['home_score'].iloc[0]
            aws = game_data['away_score'].iloc[0]
            n_pbp = len(pbp_events) if include_pbp else 0
            pbp_info = f" ({n_pbp} eventi)" if include_pbp else ""
            print(f"  {code}: {home} {hs}-{aws} {away}{pbp_info}")

            empty_streak = 0  # Reset contatore pagine vuote

            if len(new_games) % 20 == 0:
                print(f"  ... scaricate {len(new_games)} nuove partite")
        else:
            # Pagina vuota - NON viene aggiunta a scraped_codes
            empty_streak += 1
            if end_code is None and empty_streak <= max_empty:
                print(f"  {code}: vuota ({empty_streak}/{max_empty})")

        code += 1

    if skipped > 0:
        print(f"  Saltate {skipped} partite già presenti")

    # Combina vecchi e nuovi dati - STATISTICHE
    if new_games:
        new_df = pd.concat(new_games)
        new_df["pm_permin_adj"] = new_df['pm_permin'] - new_df['Gap_permin']

        if existing_df is not None:
            overall_df = pd.concat([existing_df, new_df])
            overall_df = overall_df.drop_duplicates(
                subset=['game_code', 'Giocatore', 'Team'],
                keep='last'
            )
        else:
            overall_df = new_df

        with open(output_file, 'wb') as f:
            pickle.dump(overall_df, f)
        print(f"  Salvate {len(new_games)} nuove partite -> totale {len(overall_df)} record")

        # Salva PBP e parziali
        if include_pbp and new_pbp_events:
            new_pbp_df = pd.DataFrame(new_pbp_events)
            new_quarters_df = pd.DataFrame(new_quarters_list)

            if existing_pbp is not None and not existing_pbp.empty:
                all_pbp_df = pd.concat([existing_pbp, new_pbp_df], ignore_index=True)
            else:
                all_pbp_df = new_pbp_df

            if existing_quarters is not None and not existing_quarters.empty:
                all_quarters_df = pd.concat([existing_quarters, new_quarters_df], ignore_index=True)
            else:
                all_quarters_df = new_quarters_df

            # Rimuovi duplicati e arricchisci
            all_pbp_df = all_pbp_df.drop_duplicates(
                subset=['game_code', 'quarter', 'time', 'player', 'action_type'],
                keep='last'
            )
            all_quarters_df = all_quarters_df.drop_duplicates(subset=['game_code'], keep='last')
            all_pbp_df = enrich_pbp_dataframe(all_pbp_df)

            with open(pbp_file, 'wb') as f:
                pickle.dump(all_pbp_df, f)
            with open(quarters_file, 'wb') as f:
                pickle.dump(all_quarters_df, f)

            print(f"  Play-by-play: {len(all_pbp_df)} eventi totali")
            print(f"  Parziali: {len(all_quarters_df)} partite")

        return overall_df

    elif existing_df is not None:
        print(f"  Nessuna nuova partita, dati esistenti invariati")
        return existing_df

    return None


def get_chrome_version():
    """Rileva la versione major di Chrome installata."""
    import subprocess
    try:
        # Linux
        result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            # "Google Chrome 144.0.7559.132" -> 144
            version_str = result.stdout.strip().split()[-1]
            return int(version_str.split('.')[0])
    except FileNotFoundError:
        pass

    try:
        # Alternative path
        result = subprocess.run(['chromium-browser', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version_str = result.stdout.strip().split()[-1]
            return int(version_str.split('.')[0])
    except FileNotFoundError:
        pass

    return None  # Lascia che uc gestisca


def create_driver():
    """Crea un'istanza del browser."""
    # Usa headless mode se variabile HEADLESS=1 (per GitHub Actions)
    headless = os.environ.get('HEADLESS', '0') == '1'
    chrome_version = get_chrome_version()

    print(f"Avvio browser... {'(headless)' if headless else '(GUI)'}", end='')
    if chrome_version:
        print(f" [Chrome {chrome_version}]")
    else:
        print()

    return uc.Chrome(headless=headless, version_main=chrome_version)


def load_existing_pbp(output_file):
    """Carica play-by-play esistente se il file esiste."""
    if os.path.exists(output_file):
        with open(output_file, 'rb') as f:
            data = pickle.load(f)
            print(f"  Caricati {len(data)} eventi play-by-play da {output_file}")
            return data
    return None


def load_existing_quarters(output_file):
    """Carica parziali esistenti se il file esiste."""
    if os.path.exists(output_file):
        with open(output_file, 'rb') as f:
            data = pickle.load(f)
            print(f"  Caricati {len(data)} parziali da {output_file}")
            return data
    return None


def get_scraped_pbp_games(existing_df):
    """Estrae i codici delle partite con play-by-play già scaricato."""
    if existing_df is None or 'game_code' not in existing_df.columns:
        return set()
    return set(existing_df['game_code'].unique())


def enrich_pbp_dataframe(df):
    """
    Aggiunge colonne derivate utili per le analisi.

    Colonne aggiunte:
    - time_seconds: secondi rimanenti nel quarto
    - total_seconds: secondi totali dall'inizio partita
    - gap: differenza punteggio (home - away)
    - is_score: True se l'azione è un punto segnato
    - points: punti segnati (0, 1, 2, 3)
    - is_home_action: True se l'azione è della squadra di casa
    - clutch: True se ultimi 2 min e gap <= 5
    """
    if df.empty:
        return df

    df = df.copy()

    # Tempo in secondi (rimanenti nel quarto)
    def time_to_seconds(t):
        if pd.isna(t) or t == '':
            return 0
        try:
            parts = str(t).split(':')
            return int(parts[0]) * 60 + int(parts[1])
        except:
            return 0

    df['time_seconds'] = df['time'].apply(time_to_seconds)

    # Caso speciale: 00:00 nel sito significa 10:00 (fine quarto)
    # Tutti gli altri tempi sono in formato count-up normale
    df.loc[df['time_seconds'] == 0, 'time_seconds'] = 600

    # Secondi totali dall'inizio partita
    df['total_seconds'] = (df['quarter'] - 1) * 600 + df['time_seconds']

    # Gap punteggio (positivo = vantaggio casa)
    df['gap'] = df['score_home'] - df['score_away']

    # Identifica azioni di punteggio dal testo (per riferimento)
    score_actions = [
        'Tiro realizzato', 'Tiro libero realizzato', 'Tripla realizzata',
        'realizzato', r'\d\)'  # pattern nei testi es. "(2)", "(3)"
    ]
    df['is_score'] = df['action_type'].str.contains('|'.join(score_actions), case=False, na=False, regex=True)

    # Azione della squadra di casa
    df['is_home_action'] = df['team'] == df['home_team']

    # Calcola punti dalla variazione del punteggio (più affidabile del parsing testo)
    # Per ogni partita, calcola la differenza di punteggio rispetto all'evento precedente
    df = df.sort_values(['game_code', 'total_seconds', 'score_home', 'score_away'])

    df['prev_score_home'] = df.groupby('game_code')['score_home'].shift(1).fillna(0).astype(int)
    df['prev_score_away'] = df.groupby('game_code')['score_away'].shift(1).fillna(0).astype(int)

    df['home_pts_change'] = (df['score_home'] - df['prev_score_home']).clip(lower=0)
    df['away_pts_change'] = (df['score_away'] - df['prev_score_away']).clip(lower=0)

    # Punti segnati: assegna i punti in base a chi ha effettivamente segnato
    # (non in base a chi sta facendo l'azione, che potrebbe essere un timeout/cambio)
    df['points'] = df['home_pts_change'] + df['away_pts_change']

    # Indica se i punti sono stati segnati da home o away
    df['points_by_home'] = df['home_pts_change'] > 0

    # Rimuovi colonne temporanee
    df = df.drop(columns=['prev_score_home', 'prev_score_away', 'home_pts_change', 'away_pts_change'])

    # Situazione clutch: ultimi 2 minuti di Q4 o overtime (da 8:00 a 10:00) e gap <= 5
    df['clutch'] = (df['quarter'] >= 4) & (df['time_seconds'] >= 480) & (df['gap'].abs() <= 5)

    return df


def scrape_campionato_pbp(config, driver, incremental=True):
    """
    Scarica play-by-play e parziali per un singolo campionato.

    Args:
        config: dizionario con la configurazione del campionato
        driver: istanza del browser
        incremental: se True, scarica solo le partite nuove

    Returns:
        Tuple (DataFrame pbp, DataFrame parziali)
    """
    # Estrai directory e nome base dal file di output esistente
    output_dir = os.path.dirname(config['output_file'])
    base_name = os.path.basename(config['output_file']).replace('season_stats_', '').replace('.pkl', '')
    pbp_file = os.path.join(output_dir, f"pbp_{base_name}.pkl")
    quarters_file = os.path.join(output_dir, f"quarters_{base_name}.pkl")
    url_prefix = config['url_prefix']
    game_codes = np.arange(config['start_code'], config['end_code'] + 1)

    print(f"\nScraping Play-by-Play {base_name} - {len(game_codes)} partite potenziali...")

    # Carica dati esistenti
    existing_pbp = load_existing_pbp(pbp_file) if incremental else None
    existing_quarters = load_existing_quarters(quarters_file) if incremental else None
    scraped_codes = get_scraped_pbp_games(existing_pbp)

    if scraped_codes:
        print(f"  Partite già scaricate: {len(scraped_codes)}")

    new_pbp_events = []
    new_quarters_list = []
    skipped = 0

    for code in game_codes:
        # Skip se già scaricata (modalità incrementale)
        if incremental and code in scraped_codes:
            skipped += 1
            continue

        url = f'https://netcasting3.webpont.com/?{url_prefix}{code}'
        result = scrape_single_game(driver, url, code, config, extract_pbp=True)

        if result[0] is not None:
            game_stats, pbp_events, quarter_scores = result
            home = game_stats['home_team'].iloc[0]
            away = game_stats['away_team'].iloc[0]
            hs = game_stats['home_score'].iloc[0]
            aws = game_stats['away_score'].iloc[0]

            new_pbp_events.extend(pbp_events)
            new_quarters_list.append(quarter_scores)

            print(f"  {code}: {home} {hs}-{aws} {away} ({len(pbp_events)} eventi)")

            if len(new_quarters_list) % 20 == 0:
                print(f"  ... scaricate {len(new_quarters_list)} nuove partite")

    if skipped > 0:
        print(f"  Saltate {skipped} partite già presenti")

    # Combina vecchi e nuovi dati
    if new_pbp_events:
        # Crea DataFrame dai nuovi eventi
        new_pbp_df = pd.DataFrame(new_pbp_events)
        new_quarters_df = pd.DataFrame(new_quarters_list)

        # Combina con esistenti
        if existing_pbp is not None and not existing_pbp.empty:
            all_pbp_df = pd.concat([existing_pbp, new_pbp_df], ignore_index=True)
        else:
            all_pbp_df = new_pbp_df

        if existing_quarters is not None and not existing_quarters.empty:
            all_quarters_df = pd.concat([existing_quarters, new_quarters_df], ignore_index=True)
        else:
            all_quarters_df = new_quarters_df

        # Rimuovi duplicati
        all_pbp_df = all_pbp_df.drop_duplicates(
            subset=['game_code', 'quarter', 'time', 'player', 'action_type'],
            keep='last'
        )
        all_quarters_df = all_quarters_df.drop_duplicates(subset=['game_code'], keep='last')

        # Arricchisci con colonne derivate
        all_pbp_df = enrich_pbp_dataframe(all_pbp_df)

        # Salva
        with open(pbp_file, 'wb') as f:
            pickle.dump(all_pbp_df, f)
        with open(quarters_file, 'wb') as f:
            pickle.dump(all_quarters_df, f)

        n_games = all_pbp_df['game_code'].nunique()
        print(f"  Salvati {len(new_pbp_events)} nuovi eventi -> totale {len(all_pbp_df)} eventi, {n_games} partite")
        print(f"  Salvati {len(new_quarters_list)} nuovi parziali -> totale {len(all_quarters_df)} partite")

        return all_pbp_df, all_quarters_df

    elif existing_pbp is not None:
        print(f"  Nessuna nuova partita, dati esistenti invariati")
        return existing_pbp, existing_quarters

    return pd.DataFrame(), pd.DataFrame()


def run_scraping_pbp(campionati, incremental=True):
    """
    Esegue lo scraping del play-by-play per tutti i campionati abilitati.

    Args:
        campionati: dizionario con la configurazione dei campionati
        incremental: se True, scarica solo le partite nuove
    """
    driver = create_driver()

    try:
        for nome, config in campionati.items():
            if config['enabled']:
                print(f"\n{'='*50}")
                print(f"Play-by-Play: {nome}")
                print(f"{'='*50}")
                scrape_campionato_pbp(config, driver, incremental=incremental)
    finally:
        driver.quit()
        print("\nScraping Play-by-Play completato!")


def run_scraping(campionati, incremental=True, include_pbp=True):
    """
    Esegue lo scraping per tutti i campionati abilitati.

    Args:
        campionati: dizionario con la configurazione dei campionati
        incremental: se True, scarica solo le partite nuove
        include_pbp: se True, scarica anche play-by-play e parziali
    """
    driver = create_driver()

    try:
        for nome, config in campionati.items():
            if config['enabled']:
                print(f"\n{'='*50}")
                print(f"Campionato: {nome}")
                print(f"{'='*50}")
                scrape_campionato(config, driver, incremental=incremental, include_pbp=include_pbp)
    finally:
        driver.quit()
        print("\nScraping completato!")
