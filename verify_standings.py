"""
Script per verificare la classifica confrontando i dati scraping vs sito ufficiale LNP.
"""

import time
import pandas as pd
import os
import re
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def create_driver():
    """Crea istanza del browser."""
    return uc.Chrome(headless=False)


def scrape_lnp_standings(driver):
    """
    Scrape classifica dal sito ufficiale LNP.

    Returns:
        Dict con {'girone_a': DataFrame, 'girone_b': DataFrame}
    """
    url = "https://www.legapallacanestro.com/serie/4/classifica"
    driver.get(url)
    time.sleep(4)  # Attendi caricamento JavaScript

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Trova tutte le tabelle
    tables = soup.find_all('table')

    results = {'girone_a': [], 'girone_b': []}
    current_girone = 'girone_a'

    for table in tables:
        rows = table.find_all('tr')

        for row in rows:
            cells = row.find_all(['td', 'th'])

            if len(cells) >= 8:
                # Estrai testo da ogni cella
                cell_texts = [c.get_text(strip=True) for c in cells]

                # Controlla se è header
                if 'Pti' in cell_texts or 'PF' in cell_texts:
                    continue

                # Prima cella è il nome squadra
                team_cell = cells[0]
                team_name = team_cell.get_text(strip=True)

                # Salta righe vuote
                if not team_name or team_name.isdigit():
                    continue

                # Le celle successive sono: Pti, G, V, P, %, PF, PS, Diff, ...
                try:
                    data = {
                        'team': team_name,
                        'pts': int(cell_texts[1]) if cell_texts[1].isdigit() else 0,
                        'gp': int(cell_texts[2]) if cell_texts[2].isdigit() else 0,
                        'wins': int(cell_texts[3]) if cell_texts[3].isdigit() else 0,
                        'losses': int(cell_texts[4]) if cell_texts[4].isdigit() else 0,
                        'pf': int(cell_texts[6]) if len(cell_texts) > 6 and cell_texts[6].isdigit() else 0,
                        'ps': int(cell_texts[7]) if len(cell_texts) > 7 and cell_texts[7].isdigit() else 0,
                    }

                    # Determina girone basandosi sul contesto
                    if len(results['girone_a']) < 19:
                        results['girone_a'].append(data)
                    else:
                        results['girone_b'].append(data)

                except (ValueError, IndexError) as e:
                    continue

    return {
        'girone_a': pd.DataFrame(results['girone_a']),
        'girone_b': pd.DataFrame(results['girone_b'])
    }


def get_our_standings(campionato='b_a'):
    """Ottiene la nostra classifica calcolata."""
    from functions.analysis import preprocess_data
    from functions.config import SIMILAR_TEAMS

    file_map = {
        'b_a': 'season_stats_b_a.pkl',
        'b_b': 'season_stats_b_b.pkl',
        'a2': 'season_stats_a2.pkl',
    }

    path = os.path.join(DATA_DIR, file_map[campionato])
    if not os.path.exists(path):
        return None

    overall_df = pd.read_pickle(path)
    overall_df = preprocess_data(overall_df, similar_teams=SIMILAR_TEAMS)

    # Calcola classifica
    standings = []
    for team in overall_df['Team'].unique():
        team_df = overall_df[overall_df['Team'] == team]
        games = team_df.groupby(['game_code', 'Opponent', 'Gap']).first().reset_index()

        wins = (games['Gap'] > 0).sum()
        losses = (games['Gap'] < 0).sum()
        gp = wins + losses

        # Calcola punti fatti e subiti
        pf = team_df.groupby('game_code')['PT'].sum().sum()
        # PS più complesso - usa i dati delle partite
        pts_scored_per_game = team_df.groupby('game_code')['PT'].sum()
        gap_per_game = team_df.groupby('game_code')['Gap'].first()
        ps = (pts_scored_per_game - gap_per_game).sum()

        standings.append({
            'team': team,
            'gp': gp,
            'wins': wins,
            'losses': losses,
            'pts': wins * 2,
            'pf': int(pf),
            'ps': int(ps),
        })

    return pd.DataFrame(standings).sort_values('pts', ascending=False)


def normalize_team_name(name):
    """Normalizza nome squadra per confronto."""
    # Rimuovi prefissi sponsor comuni
    name = name.lower().strip()
    # Estrai parole chiave
    keywords = ['montecatini', 'vigevano', 'orzinuovi', 'vendemiano', 'lumezzane',
                'desio', 'omegna', 'agrigento', 'piacenza', 'fidenza', 'legnano',
                'treviglio', 'monferrato', 'vicenza', 'armerina', 'fiorenzuola',
                'orlando', 'livorno', 'avellino', 'fortitudo', 'casoria', 'nardò',
                'chiusi', 'latina', 'rieti', 'vigevano', 'cento', 'forlì',
                'cantù', 'torino', 'udine', 'verona', 'cremona', 'rimini',
                'pesaro', 'piacenza']

    for kw in keywords:
        if kw in name:
            return kw

    return name


def compare_standings(official_df, our_df, girone_name):
    """Confronta le due classifiche."""
    print(f"\n{'='*70}")
    print(f"CONFRONTO {girone_name.upper()}")
    print("="*70)

    discrepancies = []
    matched = 0

    for _, off_row in official_df.iterrows():
        off_team = off_row['team']
        off_key = normalize_team_name(off_team)
        off_pts = off_row['pts']
        off_gp = off_row['gp']
        off_wins = off_row['wins']
        off_losses = off_row['losses']

        # Cerca match nei nostri dati
        found = False
        for _, our_row in our_df.iterrows():
            our_key = normalize_team_name(our_row['team'])

            if off_key == our_key or off_key in our_key or our_key in off_key:
                our_team = our_row['team']
                our_pts = our_row['pts']
                our_gp = our_row['gp']
                our_wins = our_row['wins']
                our_losses = our_row['losses']

                found = True

                if our_pts != off_pts or our_gp != off_gp:
                    discrepancies.append({
                        'team_off': off_team,
                        'team_our': our_team,
                        'off_pts': off_pts,
                        'our_pts': our_pts,
                        'diff_pts': our_pts - off_pts,
                        'off_gp': off_gp,
                        'our_gp': our_gp,
                        'diff_gp': our_gp - off_gp,
                    })
                    print(f"❌ {off_team[:40]}")
                    print(f"   Uffic.: {off_gp:2d}G {off_wins:2d}V {off_losses:2d}S = {off_pts:2d} pts")
                    print(f"   Nostri: {our_gp:2d}G {our_wins:2d}V {our_losses:2d}S = {our_pts:2d} pts")
                    diff_pts = our_pts - off_pts
                    diff_gp = our_gp - off_gp
                    print(f"   Diff:   {diff_gp:+d} partite, {diff_pts:+d} punti")
                else:
                    matched += 1
                    print(f"✓  {off_team[:40]}: {off_pts} pts OK")
                break

        if not found:
            print(f"?  {off_team[:40]}: non trovato nei nostri dati")

    print(f"\n--- Riepilogo ---")
    print(f"Corrispondenti: {matched}")
    print(f"Discrepanze: {len(discrepancies)}")

    return discrepancies


def main():
    print("="*70)
    print("VERIFICA CLASSIFICA LNP - Serie B")
    print("="*70)

    driver = create_driver()

    try:
        # Scrape classifica ufficiale
        print("\n📥 Scraping classifica ufficiale LNP...")
        official = scrape_lnp_standings(driver)

        print(f"\n--- Girone A: {len(official['girone_a'])} squadre ---")
        if not official['girone_a'].empty:
            print(official['girone_a'][['team', 'pts', 'gp', 'wins', 'losses']].to_string(index=False))

        print(f"\n--- Girone B: {len(official['girone_b'])} squadre ---")
        if not official['girone_b'].empty:
            print(official['girone_b'][['team', 'pts', 'gp', 'wins', 'losses']].to_string(index=False))

        # Ottieni nostre classifiche
        print("\n📊 Calcolo nostre classifiche...")

        our_a = get_our_standings('b_a')
        our_b = get_our_standings('b_b')

        if our_a is not None:
            print(f"Girone A: {len(our_a)} squadre nei nostri dati")
        if our_b is not None:
            print(f"Girone B: {len(our_b)} squadre nei nostri dati")

        # Confronta
        all_discrepancies = []

        if not official['girone_a'].empty and our_a is not None:
            disc_a = compare_standings(official['girone_a'], our_a, "Girone A")
            all_discrepancies.extend(disc_a)

        if not official['girone_b'].empty and our_b is not None:
            disc_b = compare_standings(official['girone_b'], our_b, "Girone B")
            all_discrepancies.extend(disc_b)

        # Riepilogo finale
        print("\n" + "="*70)
        print("RIEPILOGO FINALE")
        print("="*70)

        if all_discrepancies:
            print(f"\n⚠️  Trovate {len(all_discrepancies)} discrepanze totali:")
            for d in all_discrepancies:
                print(f"   - {d['team_off']}: {d['diff_pts']:+d} pts ({d['diff_gp']:+d} partite)")
        else:
            print("\n✓ Tutte le classifiche corrispondono!")

    finally:
        driver.quit()


if __name__ == '__main__':
    main()
