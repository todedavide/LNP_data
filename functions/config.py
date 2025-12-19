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
        'end_code': 154,  # Aggiorna man mano che si giocano partite
        'output_file': os.path.join(DATA_DIR, 'season_stats_b_a.pkl'),
        'enabled': True
    },
    'serie_b_girone_b': {
        'url_prefix': 'ita3_b_',
        'start_code': 1,
        'end_code': 154,
        'output_file': os.path.join(DATA_DIR, 'season_stats_b_b.pkl'),
        'enabled': True
    },
    'serie_a2': {
        'url_prefix': 'ita2_',
        'start_code': 1,
        'end_code': 200,
        'output_file': os.path.join(DATA_DIR, 'season_stats_a2.pkl'),
        'enabled': True
    },
}

# Mappatura nomi squadre simili (da aggiornare ogni stagione)
# Formato: (nome_variante, nome_variante) - verrà usato il più comune
SIMILAR_TEAMS = [
    # Aggiungi qui nuove mappature quando trovi squadre con nomi diversi
    # Es: ('Nome Vecchio', 'Nome Nuovo'),
]
