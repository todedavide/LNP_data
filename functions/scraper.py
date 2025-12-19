"""
Modulo per lo scraping delle statistiche LNP.
"""

import time
import pickle
import os
from io import StringIO

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
import undetected_chromedriver as uc


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


def scrape_single_game(driver, url, code, config):
    """Scarica i dati di una singola partita."""
    driver.get(url)
    time.sleep(2)

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Punteggio
    divs = soup.select('span.hscore-numbers div')
    try:
        hscore = int(''.join([div['rel'] for div in divs[0:3]]))
    except:
        return None

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
        return None

    home_team = teams[0].text
    away_team = teams[1].text

    if len(home_team) == 0 or total_mins < 40:
        return None

    # Statistiche
    stats_home = read_stats_table(cl='hstat', soup=soup)
    stats_away = read_stats_table(cl='astat', soup=soup)

    if stats_home is None or stats_away is None:
        return None

    stats_home['Team'] = home_team
    stats_home['Opponent'] = away_team
    stats_away['Team'] = away_team
    stats_away['Opponent'] = home_team

    stats_away['Gap'] = ascore - hscore
    stats_home['Gap'] = hscore - ascore
    stats_away['Gap_permin'] = (ascore - hscore) / total_mins
    stats_home['Gap_permin'] = (hscore - ascore) / total_mins

    game_stats = pd.concat([stats_home, stats_away])

    # Metadati per tracciare le partite
    campionato_name = config['output_file'].replace('season_stats_', '').replace('.pkl', '')
    game_stats['Campionato'] = campionato_name
    game_stats['game_code'] = code
    game_stats['home_team'] = home_team
    game_stats['away_team'] = away_team
    game_stats['home_score'] = hscore
    game_stats['away_score'] = ascore

    return game_stats


def scrape_campionato(config, driver, incremental=True):
    """
    Scarica le statistiche per un singolo campionato/girone.

    Args:
        config: dizionario con la configurazione del campionato
        driver: istanza del browser
        incremental: se True, scarica solo le partite nuove

    Returns:
        DataFrame con tutte le statistiche (vecchie + nuove)
    """
    output_file = config['output_file']
    url_prefix = config['url_prefix']
    game_codes = np.arange(config['start_code'], config['end_code'] + 1)

    print(f"\nScraping {output_file} - {len(game_codes)} partite potenziali...")

    # Carica dati esistenti
    existing_df = load_existing_data(output_file) if incremental else None
    scraped_codes = get_scraped_games(existing_df)

    if scraped_codes:
        print(f"  Partite già scaricate: {len(scraped_codes)}")

    new_games = []
    skipped = 0

    for code in game_codes:
        # Skip se già scaricata (modalità incrementale)
        if incremental and code in scraped_codes:
            skipped += 1
            continue

        url = f'https://netcasting3.webpont.com/?{url_prefix}{code}'
        game_data = scrape_single_game(driver, url, code, config)

        if game_data is not None:
            new_games.append(game_data)
            home = game_data['home_team'].iloc[0]
            away = game_data['away_team'].iloc[0]
            hs = game_data['home_score'].iloc[0]
            aws = game_data['away_score'].iloc[0]
            print(f"  {code}: {home} {hs}-{aws} {away}")

            if len(new_games) % 20 == 0:
                print(f"  ... scaricate {len(new_games)} nuove partite")

    if skipped > 0:
        print(f"  Saltate {skipped} partite già presenti")

    # Combina vecchi e nuovi dati
    if new_games:
        new_df = pd.concat(new_games)
        new_df["pm_permin_adj"] = new_df['pm_permin'] - new_df['Gap_permin']

        if existing_df is not None:
            overall_df = pd.concat([existing_df, new_df])
            # Rimuovi eventuali duplicati
            overall_df = overall_df.drop_duplicates(
                subset=['game_code', 'Giocatore', 'Team'],
                keep='last'
            )
        else:
            overall_df = new_df

        # Salva
        with open(output_file, 'wb') as f:
            pickle.dump(overall_df, f)
        print(f"  Salvate {len(new_games)} nuove partite -> totale {len(overall_df)} record")

        return overall_df

    elif existing_df is not None:
        print(f"  Nessuna nuova partita, dati esistenti invariati")
        return existing_df

    return None


def create_driver():
    """Crea un'istanza del browser."""
    print("Avvio browser...")
    return uc.Chrome(headless=False)


def run_scraping(campionati, incremental=True):
    """
    Esegue lo scraping per tutti i campionati abilitati.

    Args:
        campionati: dizionario con la configurazione dei campionati
        incremental: se True, scarica solo le partite nuove
    """
    driver = create_driver()

    try:
        for nome, config in campionati.items():
            if config['enabled']:
                print(f"\n{'='*50}")
                print(f"Campionato: {nome}")
                print(f"{'='*50}")
                scrape_campionato(config, driver, incremental=incremental)
    finally:
        driver.quit()
        print("\nScraping completato!")
