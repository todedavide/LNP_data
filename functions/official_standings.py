"""
Modulo per scaricare e gestire classifiche ufficiali dal sito LNP.
Permette di usare dati ufficiali come fonte autoritativa per V/S/Punti.
"""

import os
import json
import time
from datetime import datetime
from bs4 import BeautifulSoup

# Directory per cache classifiche
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'official_cache')


def ensure_cache_dir():
    """Crea directory cache se non esiste."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(campionato):
    """Ritorna il path del file cache per un campionato."""
    return os.path.join(CACHE_DIR, f'standings_{campionato}.json')


def load_cached_standings(campionato):
    """
    Carica classifiche da cache.

    Returns:
        dict con standings e metadata, o None se cache non esiste
    """
    cache_path = get_cache_path(campionato)
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)
    return None


def save_standings_cache(campionato, standings_data):
    """Salva classifiche in cache."""
    ensure_cache_dir()
    cache_path = get_cache_path(campionato)

    cache_data = {
        'updated_at': datetime.now().isoformat(),
        'standings': standings_data
    }

    with open(cache_path, 'w') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


def scrape_serie_b_standings(driver):
    """
    Scrape classifiche Serie B dal sito ufficiale LNP.

    Returns:
        dict con {'girone_a': [...], 'girone_b': [...]}
    """
    url = "https://www.legapallacanestro.com/serie/4/classifica"
    driver.get(url)
    time.sleep(4)

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    results = {'girone_a': [], 'girone_b': []}

    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')

        for row in rows:
            cells = row.find_all(['td', 'th'])

            if len(cells) >= 8:
                cell_texts = [c.get_text(strip=True) for c in cells]

                if 'Pti' in cell_texts or 'PF' in cell_texts:
                    continue

                team_cell = cells[0]
                team_name = team_cell.get_text(strip=True)

                if not team_name or team_name.isdigit():
                    continue

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

                    if len(results['girone_a']) < 19:
                        results['girone_a'].append(data)
                    else:
                        results['girone_b'].append(data)

                except (ValueError, IndexError):
                    continue

    return results


def scrape_serie_b_girone_b_standings(driver):
    """
    Scrape classifica Serie B Girone B cliccando sul tab specifico.

    Returns:
        list di standings per girone B
    """
    from selenium.webdriver.common.by import By

    url = "https://www.legapallacanestro.com/serie/4/classifica"
    driver.get(url)
    time.sleep(3)

    # Clicca sul tab Girone B
    try:
        tab_b = driver.find_element(By.ID, "quicktabs-tab-campionato-selector-1")
        driver.execute_script("arguments[0].click();", tab_b)
        time.sleep(3)
    except Exception as e:
        print(f"Errore click tab Girone B: {e}")
        return []

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    results = []

    # Trova la tabella con l'header delle classifiche (Pti, G, V, P)
    tables = soup.find_all('table')

    standings_table = None
    for table in tables:
        rows = table.find_all('tr')
        for row in rows[:2]:  # Controlla solo prime 2 righe per header
            cells = row.find_all(['td', 'th'])
            texts = [c.get_text(strip=True) for c in cells]
            if 'Pti' in texts or ('G' in texts and 'V' in texts):
                standings_table = table
                break
        if standings_table:
            break

    if not standings_table:
        return []

    rows = standings_table.find_all('tr')

    for row in rows:
        cells = row.find_all(['td', 'th'])

        if len(cells) >= 5:
            cell_texts = [c.get_text(strip=True) for c in cells]

            # Salta header
            if 'Pti' in cell_texts or ('G' in cell_texts and 'V' in cell_texts):
                continue

            team_name = cells[0].get_text(strip=True)

            if not team_name or team_name.isdigit():
                continue

            # Limita a 19 squadre per girone
            if len(results) >= 19:
                break

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
                results.append(data)
            except (ValueError, IndexError):
                continue

    return results[:19]  # Assicura max 19 squadre


def scrape_serie_a2_standings(driver):
    """
    Scrape classifica Serie A2 dal sito ufficiale LNP.

    Returns:
        list di standings
    """
    # URL corretto per A2
    url = "https://www.legapallacanestro.com/serie-a2/classifica"
    driver.get(url)
    time.sleep(4)

    soup = BeautifulSoup(driver.page_source, 'html.parser')

    results = []

    # Trova tutte le tabelle
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')

        for row in rows:
            cells = row.find_all(['td', 'th'])

            # Header A2: ['', 'P', 'G', 'V', 'P', '%', ...]
            # Prima cella vuota, poi Pti, G, V, P(losses)
            if len(cells) >= 5:
                cell_texts = [c.get_text(strip=True) for c in cells]

                # Salta header (contiene 'G' o 'V' come header)
                if 'G' in cell_texts and 'V' in cell_texts and 'P' in cell_texts:
                    continue

                team_name = cells[0].get_text(strip=True)

                # Salta righe vuote o numeri
                if not team_name or team_name.isdigit():
                    continue

                # Salta se troppi caratteri
                if len(team_name) > 100:
                    continue

                try:
                    # Prova a parsare i dati
                    pts_str = cell_texts[1].strip()
                    gp_str = cell_texts[2].strip()

                    # Verifica che siano numeri validi
                    if not pts_str.isdigit() or not gp_str.isdigit():
                        continue

                    data = {
                        'team': team_name,
                        'pts': int(pts_str),
                        'gp': int(gp_str),
                        'wins': int(cell_texts[3]) if len(cell_texts) > 3 and cell_texts[3].isdigit() else 0,
                        'losses': int(cell_texts[4]) if len(cell_texts) > 4 and cell_texts[4].isdigit() else 0,
                        'pf': int(cell_texts[6]) if len(cell_texts) > 6 and cell_texts[6].isdigit() else 0,
                        'ps': int(cell_texts[7]) if len(cell_texts) > 7 and cell_texts[7].isdigit() else 0,
                    }

                    # Evita duplicati
                    if not any(r['team'] == team_name for r in results):
                        results.append(data)

                except (ValueError, IndexError):
                    continue

    return results


def refresh_all_standings():
    """
    Scarica tutte le classifiche ufficiali e le salva in cache.
    Richiede browser Selenium.

    Returns:
        dict con tutte le standings
    """
    import undetected_chromedriver as uc

    driver = uc.Chrome(headless=False)

    try:
        print("Scaricando classifiche ufficiali LNP...")

        # Serie B Girone A
        print("  - Serie B Girone A...")
        serie_b = scrape_serie_b_standings(driver)
        save_standings_cache('b_a', serie_b['girone_a'])
        print(f"    Salvate {len(serie_b['girone_a'])} squadre")

        # Serie B Girone B (richiede click su tab)
        print("  - Serie B Girone B...")
        girone_b = scrape_serie_b_girone_b_standings(driver)
        save_standings_cache('b_b', girone_b)
        print(f"    Salvate {len(girone_b)} squadre")

        # Serie A2
        print("  - Serie A2...")
        serie_a2 = scrape_serie_a2_standings(driver)
        save_standings_cache('a2', serie_a2)
        print(f"    Salvate {len(serie_a2)} squadre")

        print("Classifiche ufficiali aggiornate!")

        return {
            'b_a': serie_b['girone_a'],
            'b_b': girone_b,
            'a2': serie_a2
        }

    finally:
        driver.quit()


def normalize_team_name_for_match(name):
    """
    Normalizza nome squadra per matching tra fonti.
    Estrae parole chiave identificative.
    """
    name = name.lower().strip()

    # Mappatura diretta per casi problematici
    direct_mappings = {
        'bakery': 'bakery piacenza',
        'assigeco': 'ucc assigeco piacenza',
    }

    for key, val in direct_mappings.items():
        if key in name:
            return val

    # Parole chiave identificative
    keywords = [
        'montecatini', 'vigevano', 'orzinuovi', 'vendemiano', 'lumezzane',
        'desio', 'omegna', 'agrigento', 'fidenza', 'legnano',
        'treviglio', 'monferrato', 'vicenza', 'armerina', 'fiorenzuola',
        'orlando', 'livorno', 'avellino', 'fortitudo', 'casoria', 'nardò',
        'chiusi', 'latina', 'rieti', 'cento', 'forlì',
        'cantù', 'torino', 'udine', 'verona', 'cremona', 'rimini',
        'pesaro', 'scafati', 'mestre', 'ferrara', 'roseto', 'milano',
        'varese', 'trieste', 'pistoia', 'napoli', 'brindisi', 'sassari',
        'cagliari', 'pavia', 'teramo', 'mantova', 'bergamo', 'ancona',
        'civitanova', 'ravenna', 'jesi', 'fabriano', 'siena', 'arezzo',
        'ozzano', 'imola', 'san miniato', 'empoli', 'piombino',
        'faenza', 'cesena', 'senigallia', 'san severo', 'monopoli',
        'ruvo', 'corato', 'bisceglie', 'molfetta', 'taranto', 'cerignola',
        'salerno', 'battipaglia', 'torre del greco', 'portici', 'castellammare'
    ]

    for kw in keywords:
        if kw in name:
            return kw

    return name


def get_official_standings(campionato):
    """
    Ottiene classifiche ufficiali (da cache se disponibili).

    Args:
        campionato: 'b_a', 'b_b', 'a2'

    Returns:
        list di dict con standings, o None se non disponibili
    """
    cached = load_cached_standings(campionato)
    if cached:
        return cached.get('standings', [])
    return None


def merge_standings(calculated_standings, campionato):
    """
    Unisce le classifiche calcolate con quelle ufficiali.
    Usa i dati ufficiali per V/S/Punti quando disponibili.

    Args:
        calculated_standings: list di dict con standings calcolate
        campionato: 'b_a', 'b_b', 'a2'

    Returns:
        list di dict con standings corrette
    """
    official = get_official_standings(campionato)

    if not official:
        # Nessun dato ufficiale, usa calcolati
        return calculated_standings

    # Crea indice per matching veloce
    official_by_key = {}
    for team_data in official:
        key = normalize_team_name_for_match(team_data['team'])
        official_by_key[key] = team_data

    # Correggi standings calcolate
    corrected = []
    for calc_team in calculated_standings:
        team_name = calc_team['Squadra']
        key = normalize_team_name_for_match(team_name)

        # Cerca match
        off_data = official_by_key.get(key)

        if off_data:
            # Usa dati ufficiali per V/S/Punti
            calc_team = calc_team.copy()
            calc_team['V'] = off_data['wins']
            calc_team['S'] = off_data['losses']
            calc_team['GP'] = off_data['gp']
            calc_team['Punti'] = off_data['pts']

            # Ricalcola Win% con dati ufficiali
            if off_data['gp'] > 0:
                calc_team['Win%'] = round(off_data['wins'] / off_data['gp'] * 100, 1)

            # Marca come verificato
            calc_team['_verified'] = True
        else:
            calc_team = calc_team.copy()
            calc_team['_verified'] = False

        corrected.append(calc_team)

    # Riordina per punti (ufficiali)
    corrected.sort(key=lambda x: (-x['Punti'], -x.get('Win%', 0)))

    return corrected


def get_cache_info():
    """
    Ritorna info sulla cache delle classifiche.

    Returns:
        dict con info per ogni campionato
    """
    info = {}
    for camp in ['b_a', 'b_b', 'a2']:
        cached = load_cached_standings(camp)
        if cached:
            info[camp] = {
                'updated_at': cached.get('updated_at'),
                'teams': len(cached.get('standings', []))
            }
        else:
            info[camp] = None
    return info
