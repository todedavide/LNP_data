"""
Configurazione campionati LNP.
Modifica questi parametri per scegliere cosa scaricare.
"""

import os

# Directory per i dati
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

CAMPIONATI = {
    'serie_b_girone_a': {
        'url_prefix': 'ita3_a_',
        'start_code': 1,
        'end_code': None,  # Auto-stop dopo 5 pagine vuote consecutive
        'output_file': os.path.join(DATA_DIR, 'season_stats_b_a.pkl'),
        'enabled': True
    },
    'serie_b_girone_b': {
        'url_prefix': 'ita3_b_',
        'start_code': 1,
        'end_code': None,  # Auto-stop dopo 5 pagine vuote consecutive
        'output_file': os.path.join(DATA_DIR, 'season_stats_b_b.pkl'),
        'enabled': True
    },
    'serie_a2': {
        'url_prefix': 'ita2_',
        'start_code': 1,
        'end_code': None,  # Auto-stop dopo 5 pagine vuote consecutive
        'output_file': os.path.join(DATA_DIR, 'season_stats_a2.pkl'),
        'enabled': True
    },
}

# Mappatura nomi squadre simili (da aggiornare ogni stagione)
# Formato: (nome_variante, nome_standard) - il secondo nome è quello che verrà usato
SIMILAR_TEAMS = [
    # Livorno
    ('Libertas Livorno 1947', 'Libertas Livorno'),
    ('Bi.Emme Service Libertas Livorno', 'Libertas Livorno'),
    # Avellino
    ('Gruppo Lombardi Avellino Basket', 'Avellino Basket'),
    ('Unicusano Avellino Basket', 'Avellino Basket'),
    # Fortitudo Bologna
    ('Flats Service Fortitudo Bologna', 'Fortitudo Bologna'),
    # PSA Casoria
    ('Malvin PSA Basket Casoria', 'PSA Basket Casoria'),
]
