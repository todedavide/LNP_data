#!/usr/bin/env python3
"""
LNP Stats - Scraper e analisi statistiche pallacanestro LNP.

Uso:
    python main.py scrape              # Scarica nuove partite (incrementale)
    python main.py scrape --full       # Scarica tutto da zero
    python main.py report              # Genera report con tutti i dati
    python main.py report --campionato b_a   # Report solo girone A
"""

import argparse
import sys

import pandas as pd

from functions.config import CAMPIONATI, SIMILAR_TEAMS
from functions.scraper import run_scraping
from functions.analysis import (
    load_all_data,
    preprocess_data,
    compute_aggregated_stats,
    create_all_plots
)
from functions.report import generate_html_report, save_report
from functions.player_cards import compute_player_stats, generate_players_report


def cmd_scrape(args):
    """Esegue lo scraping delle partite."""
    incremental = not args.full

    if args.campionato:
        # Filtra solo il campionato specificato
        campionati = {k: v for k, v in CAMPIONATI.items()
                      if args.campionato in k or args.campionato in v.get('output_file', '')}
        if not campionati:
            print(f"Campionato '{args.campionato}' non trovato.")
            print(f"Disponibili: {list(CAMPIONATI.keys())}")
            return
    else:
        campionati = CAMPIONATI

    mode = "incrementale" if incremental else "completo"
    print(f"Modalità: {mode}")

    run_scraping(campionati, incremental=incremental)


def generate_single_report(campionato_filtro, open_browser=False):
    """Genera un singolo report per un campionato."""
    overall_df, report_suffix = load_all_data(campionato_filtro)
    if overall_df is None:
        return None

    print(f"  Record totali: {len(overall_df)}")

    # Preprocessa
    overall_df = preprocess_data(overall_df, similar_teams=SIMILAR_TEAMS)
    print(f"  Record dopo filtro: {len(overall_df)}")
    print(f"  Squadre: {overall_df['Team'].nunique()}, Giocatori: {overall_df['Giocatore'].nunique()}")

    # Calcola statistiche aggregate
    sum_df, median_df = compute_aggregated_stats(overall_df)

    # Crea grafici
    plots_with_captions, team_plots = create_all_plots(overall_df, sum_df, median_df)

    # Genera report
    title = f"LNP Stats Report {report_suffix.replace('_', ' ').upper()}"
    html_content = generate_html_report(plots_with_captions, team_plots, title=title)

    # Salva
    report_name = f"stats_LNP{report_suffix}.html"
    save_report(html_content, report_name, open_browser=open_browser)
    return report_name


def cmd_report(args):
    """Genera i report HTML per tutti i campionati."""
    reports_to_generate = [
        ('b_a', 'Serie B Girone A'),
        ('b_b', 'Serie B Girone B'),
        ('a2', 'Serie A2'),
    ]

    generated = []

    for camp_filter, camp_name in reports_to_generate:
        print(f"\n{'='*50}")
        print(f"Generando report: {camp_name}")
        print('='*50)
        result = generate_single_report(camp_filter, open_browser=False)
        if result:
            generated.append(result)

    # Report combinato Serie B (b_a + b_b)
    print(f"\n{'='*50}")
    print("Generando report: Serie B Combinata (Girone A + B)")
    print('='*50)

    # Carica entrambi i gironi
    df_a, _ = load_all_data('b_a')
    df_b, _ = load_all_data('b_b')

    if df_a is not None and df_b is not None:
        combined_df = pd.concat([df_a, df_b])
        combined_df['Campionato'] = 'b_combined'
        print(f"  Record totali: {len(combined_df)}")

        combined_df = preprocess_data(combined_df, similar_teams=SIMILAR_TEAMS)
        print(f"  Record dopo filtro: {len(combined_df)}")
        print(f"  Squadre: {combined_df['Team'].nunique()}, Giocatori: {combined_df['Giocatore'].nunique()}")

        sum_df, median_df = compute_aggregated_stats(combined_df)
        plots_with_captions, team_plots = create_all_plots(combined_df, sum_df, median_df)

        title = "LNP Stats Report SERIE B COMBINATA"
        html_content = generate_html_report(plots_with_captions, team_plots, title=title)
        save_report(html_content, "stats_LNP_b_combined.html", open_browser=False)
        generated.append("stats_LNP_b_combined.html")

    print(f"\n{'='*50}")
    print(f"Report generati: {len(generated)}")
    for r in generated:
        print(f"  - {r}")


def cmd_players(args):
    """Genera le schede giocatori con percentili."""
    campionati = [
        ('b_a', 'Serie B Girone A'),
        ('b_b', 'Serie B Girone B'),
        ('a2', 'Serie A2'),
    ]

    generated = []

    for camp_filter, camp_name in campionati:
        print(f"\n{'='*50}")
        print(f"Generando schede: {camp_name}")
        print('='*50)

        overall_df, _ = load_all_data(camp_filter)
        if overall_df is None:
            continue

        overall_df = preprocess_data(overall_df, similar_teams=SIMILAR_TEAMS)
        sum_df, median_df = compute_aggregated_stats(overall_df)

        print(f"  Giocatori: {len(sum_df)}")

        player_stats = compute_player_stats(overall_df, sum_df, median_df)
        filename = generate_players_report(player_stats, camp_name)
        generated.append(filename)

    # Schede per Serie B combinata
    print(f"\n{'='*50}")
    print("Generando schede: Serie B Combinata")
    print('='*50)

    df_a, _ = load_all_data('b_a')
    df_b, _ = load_all_data('b_b')

    if df_a is not None and df_b is not None:
        combined_df = pd.concat([df_a, df_b])
        combined_df['Campionato'] = 'b_combined'

        combined_df = preprocess_data(combined_df, similar_teams=SIMILAR_TEAMS)
        sum_df, median_df = compute_aggregated_stats(combined_df)

        print(f"  Giocatori: {len(sum_df)}")

        player_stats = compute_player_stats(combined_df, sum_df, median_df)
        filename = generate_players_report(player_stats, 'Serie B Combinata')
        generated.append(filename)

    print(f"\n{'='*50}")
    print(f"Schede generate: {len(generated)}")
    for f in generated:
        print(f"  - {f}")


def cmd_info(args):
    """Mostra informazioni sui dati disponibili."""
    overall_df, _ = load_all_data()
    if overall_df is None:
        return

    print("\n" + "=" * 50)
    print("RIEPILOGO DATI")
    print("=" * 50)

    for camp in sorted(overall_df['Campionato'].unique()):
        camp_df = overall_df[overall_df['Campionato'] == camp]

        # Calcola numero partite
        if 'game_code' in camp_df.columns:
            n_games = camp_df['game_code'].nunique()
        else:
            # Fallback: conta combinazioni uniche Team-Opponent-Gap
            n_games = camp_df.groupby(['Team', 'Opponent', 'Gap']).ngroups // 2

        n_teams = camp_df['Team'].nunique()
        n_players = camp_df['Giocatore'].nunique()

        print(f"\n{camp.upper()}:")
        print(f"  Partite:   ~{n_games}")
        print(f"  Squadre:   {n_teams}")
        print(f"  Giocatori: {n_players}")
        print(f"  Record:    {len(camp_df)}")


def main():
    parser = argparse.ArgumentParser(
        description='LNP Stats - Scraper e analisi statistiche pallacanestro',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python main.py scrape                    # Scarica nuove partite
  python main.py scrape --full             # Riscarica tutto
  python main.py scrape --campionato b_a   # Solo Serie B Girone A
  python main.py report                    # Genera tutti i report (b_a, b_b, a2, b_combined)
  python main.py players                   # Genera schede giocatori
  python main.py info                      # Info sui dati disponibili
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Comandi disponibili')

    # Comando scrape
    scrape_parser = subparsers.add_parser('scrape', help='Scarica statistiche partite')
    scrape_parser.add_argument('--full', action='store_true',
                               help='Scarica tutto da zero (ignora dati esistenti)')
    scrape_parser.add_argument('--campionato', '-c', type=str,
                               help='Scarica solo un campionato (es: b_a, b_b, a2)')

    # Comando report
    subparsers.add_parser('report', help='Genera tutti i report HTML (b_a, b_b, a2, b_combined)')

    # Comando players
    subparsers.add_parser('players', help='Genera schede giocatori con percentili')

    # Comando info
    subparsers.add_parser('info', help='Mostra info sui dati disponibili')

    args = parser.parse_args()

    if args.command == 'scrape':
        cmd_scrape(args)
    elif args.command == 'report':
        cmd_report(args)
    elif args.command == 'players':
        cmd_players(args)
    elif args.command == 'info':
        cmd_info(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
