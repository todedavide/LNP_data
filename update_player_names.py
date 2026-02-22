#!/usr/bin/env python3
"""
Script per aggiornare i nomi giocatori nei dati shots esistenti.
Visita ogni partita e aggiunge player_name senza riscaricare tutto.
"""

import pickle
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from functions.scraper import read_player_names


def create_driver():
    """Crea driver Chrome con opzioni anti-bot."""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(options=options)


def update_shots_with_player_names(shots_file, url_prefix):
    """
    Aggiorna i dati shots con i nomi giocatori.
    """
    if not os.path.exists(shots_file):
        print(f"File non trovato: {shots_file}")
        return

    with open(shots_file, 'rb') as f:
        shots_df = pickle.load(f)

    print(f"Caricati {len(shots_df)} tiri da {shots_file}")

    # Controlla se player_name esiste già
    if 'player_name' not in shots_df.columns:
        shots_df['player_name'] = ''

    # Conta quanti già hanno il nome
    filled = shots_df['player_name'].notna() & (shots_df['player_name'] != '')
    print(f"  {filled.sum()} tiri hanno già player_name")

    # Trova partite uniche
    game_codes = sorted(shots_df['game_code'].unique())
    print(f"Partite da processare: {len(game_codes)}")

    driver = create_driver()

    try:
        updated_count = 0

        for i, game_code in enumerate(game_codes):
            url = f"https://netcasting3.webpont.com/?{url_prefix}{game_code}"

            print(f"[{i+1}/{len(game_codes)}] Partita {game_code}...", end=' ', flush=True)

            try:
                driver.get(url)
                time.sleep(2.5)

                player_names = read_player_names(driver)

                if player_names:
                    mask = shots_df['game_code'] == game_code
                    updates = 0
                    for idx in shots_df[mask].index:
                        player_code = shots_df.loc[idx, 'player_code']
                        if player_code in player_names:
                            shots_df.loc[idx, 'player_name'] = player_names[player_code]
                            updates += 1

                    print(f"{len(player_names)} giocatori, {updates} tiri aggiornati")
                    updated_count += updates
                else:
                    print("nessun giocatore trovato")

            except Exception as e:
                print(f"errore: {e}")

            # Salva ogni 20 partite
            if (i + 1) % 20 == 0:
                with open(shots_file, 'wb') as f:
                    pickle.dump(shots_df, f)
                print(f"  [Checkpoint salvato]")

        # Salva finale
        with open(shots_file, 'wb') as f:
            pickle.dump(shots_df, f)

        print(f"\nCompletato! {updated_count} tiri aggiornati con nomi giocatori")

    finally:
        driver.quit()


def main():
    from functions.config import CAMPIONATI

    print("=" * 50)
    print("AGGIORNAMENTO NOMI GIOCATORI")
    print("=" * 50)

    for nome, config in CAMPIONATI.items():
        if not config['enabled']:
            continue

        output_file = config['output_file']
        output_dir = os.path.dirname(output_file)
        base_name = os.path.basename(output_file).replace('season_stats_', '').replace('.pkl', '')
        shots_file = os.path.join(output_dir, f"shots_{base_name}.pkl")
        url_prefix = config['url_prefix']

        print(f"\n{'='*50}")
        print(f"Campionato: {nome}")
        print(f"{'='*50}")

        update_shots_with_player_names(shots_file, url_prefix)


if __name__ == '__main__':
    main()
