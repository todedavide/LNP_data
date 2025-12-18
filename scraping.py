import time

import matplotlib.pyplot as plt
import numpy as np
from bs4 import BeautifulSoup
from selenium import webdriver
import pandas as pd
from datetime import timedelta, datetime
import pickle
import seaborn as sns
import plotly.express as px
import glob
import datapane as dp
import Levenshtein
from itertools import combinations
import re


def add_median_lines(df, labx, laby, fig):
    # calculate median values
    medianx = df[labx].median()
    mediany = df[laby].median()

    # add horizontal line
    fig.add_shape(type='line', x0=df[labx].min(), y0=mediany,
                  x1=df[labx].max(), y1=mediany,
                  line=dict(color='black', width=2, dash='dash'))

    # add vertical line
    fig.add_shape(type='line', x0=medianx, y0=df[laby].min(),
                  x1=medianx, y1=df[laby].max(),
                  line=dict(color='black', width=2, dash='dash'))
    return fig

def read_stats_table(cl='hstat'):
    stat = soup.find(class_=cl)
    table = stat.find('table')

    stats = pd.read_html(str(table))[0]

    stats = stats.iloc[0:-1]
    # Filter out columns that start with "Unnamed"
    stats = stats.filter(regex='^(?!Unnamed)')
    stats['Giocatore'] = stats['Giocatore'].str.replace('\xa0', ' ')
    to_minutes = lambda x: int(x.split(':')[0]) + int(x.split(':')[1]) / 60
    stats['MIN'] = stats['MIN'].str.replace('[^0-9:]+', '', regex=True)
    # Apply the lambda function to the "column" column
    stats['Minutes'] = stats['MIN'].apply(to_minutes)

    stats["pm_permin"] = stats['+/-'] / stats['Minutes']
    return stats


def find_similar_strings(strings, threshold=0.2):
    similarities = {}
    for a, b in combinations(strings, 2):
        set_a = set(a.split())
        set_b = set(b.split())
        common_words = set_a.intersection(set_b).intersection({"Pallacanestro", "Virtus", "Basket"})
        set_a = set_a - common_words
        set_b = set_b - common_words
        similarity = len(set_a.intersection(set_b)) / len(set_a.union(set_b))
        if similarity >= threshold:
            similarities[(a, b)] = similarity
    return list(set([tuple(sorted(pair)) for pair in similarities.keys()]))

# Create a function to compute the Levenshtein distance between two strings
def levenshtein_distance(s1, s2):
    return Levenshtein.distance(s1.lower(), s2.lower())

# Define a function to find potentially misspelled player names
def find_misspelled_names(df, threshold):
    misspelled_pairs = []
    for team in df['Team'].unique():
        team_df = df[df['Team'] == team]
        for i in range(len(team_df)):
            for j in range(i+1, len(team_df)):
                name1 = team_df.iloc[i]['Giocatore']
                name2 = team_df.iloc[j]['Giocatore']
                if levenshtein_distance(name1, name2)/len(name1) <= threshold:
                    misspelled_pairs.append((name1, name2))
    return misspelled_pairs


similar = [('Brianza Casa Basket 2022', 'Lissone Interni Brianza Casa Basket'),
          ('Virtus Kleb Ragusa', 'Virtus Ragusa'),
          ('Pallacanestro Ruvo di Puglia', 'Tecnoswitch Ruvo di Puglia'),
          ('Pall. Aurora Desio 94', 'Rimadesio Desio'),
          ('Pielle Livorno', 'Unicusano Pielle Livorno'),
          ('Pall. Viola Reggio Calabria', 'Pallacanestro Viola Reggio Calabria'),
          ('Libertas Livorno 1947', 'Maurelli Group Libertas Livorno'),
          ('UBP Petrarca Padova', 'Unione Basket Padova'),
          ('Fabo Herons Montecatini', 'Herons Basket Montecatini'),
          ('Agribertocchi Orzinuovi', 'Pallacanestro Orzinuovi'),
          ('Ble Decò Juvecaserta', 'Ble Juvecaserta'),
          ('Falconstar Monfalcone', 'Pontoni Monfalcone'),
          ('Ble Juvecaserta', 'Juvecaserta 2021'),
          ('Ble Decò Juvecaserta', 'Juvecaserta 2021')]

scrape = False
if scrape:
    text_class = "filmlistnewfilminfo"
    time_class = "filmlistnewscoretime"
    score_class = "filmlistnewscorescore"
    driver = webdriver.Chrome()
    # game_codes = np.arange(2600, 2840)
    # game_codes = np.arange(1800, 2040)
    # game_codes = np.arange(2300, 2540) # girone c
    # game_codes = np.arange(1, 179) # girone b stagione 19/20
    # game_codes = np.arange(1, 56) # girone b1 stagione 20/21
    game_codes = np.arange(2100, 2339) # girone d

    all_df = []
    for code in game_codes:
        # url = 'https://netcasting3.webpont.com/?ita3_b_' + str(code)
        # url = 'https://netcasting3.webpont.com/?ita3_b1_' + str(code)
        # url = 'https://netcasting3.webpont.com/?ita3_a_' + str(code)
        # url = 'https://netcasting3.webpont.com/?ita3_c_' + str(code)
        url = 'https://netcasting3.webpont.com/?ita3_d_' + str(code)

        driver.get(url)
        # Wait for the content to load
        time.sleep(2)

        html = driver.page_source
        # Parse the HTML using BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        divs = soup.select('span.hscore-numbers div')
        try:
            hscore = int(''.join([div['rel'] for div in divs[0:3]]))
        except:
            continue
        divs = soup.select('span.ascore-numbers div')
        ascore = int(''.join([div['rel'] for div in divs[0:3]]))
        TTm = soup.find_all(class_="TTm")

        total_mins = 0
        for tm in TTm:
            if ":" not in tm.text:
                total_mins = max(total_mins, int(int(tm.text) / 5))
        teams = soup.find_all(class_="font-smoothing")
        home_team = teams[0].text
        away_team = teams[1].text

        if len(home_team) > 0 and total_mins >= 40:
            stats_home = read_stats_table(cl='hstat')
            stats_away = read_stats_table(cl='astat')

            stats_home['Team'] = home_team
            stats_home['Opponent'] = away_team
            stats_away['Team'] = away_team
            stats_away['Opponent'] = home_team

            stats_away['Gap'] = ascore - hscore
            stats_home['Gap'] = hscore - ascore
            stats_away['Gap_permin'] = (ascore - hscore) / total_mins
            stats_home['Gap_permin'] = (hscore - ascore) /total_mins

            game_stats = pd.concat([stats_home, stats_away])
            all_df.append(game_stats)
            a=0

    driver.quit()
    overall_df = pd.concat(all_df)
    overall_df["pm_permin_adj"] = overall_df['pm_permin'] - overall_df['Gap_permin']
    with open('season_stats_d.pkl', 'wb') as f:
        pickle.dump(overall_df, f)
else:
    stats_file = glob.glob('season_stats*.pkl')
    dfs = []
    for file in stats_file:
        with open(file, 'rb') as f:
            dfs.append(pickle.load(f))
    overall_df = pd.concat(dfs)
    # with open('season_stats_a.pkl', 'rb') as f:
    #     overall_df = pickle.load(f)

    overall_df.reset_index(inplace=True, drop=True)
    overall_df[['2PTM', '2PTA']] = overall_df['2PT'].str.split('/', expand=True).apply(pd.to_numeric)
    overall_df[['3PTM', '3PTA']] = overall_df['3PT'].str.split('/', expand=True).apply(pd.to_numeric)
    overall_df[['FTM', 'FTA']] = overall_df['TL'].str.split('/', expand=True).apply(pd.to_numeric)

    # unique_teams = overall_df['Team'].unique()
    # # Example usage
    # similar_strings = find_similar_strings(unique_teams)

    # Replace similar strings with the most common value
    for a, b in similar:
        mask = (overall_df["Team"] == a) | (overall_df["Team"] == b)
        most_common_value = overall_df.loc[mask, "Team"].mode().values[0]
        overall_df.loc[mask, "Team"] = most_common_value

    player_team_pairs = overall_df[['Giocatore', 'Team']].drop_duplicates()

    misspelled_pairs = find_misspelled_names(player_team_pairs, threshold=0.3)
    # Create a dictionary to map misspelled names to corrected names
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

    # overall_df = overall_df[2669:]
    player_minutes = overall_df.groupby(['Giocatore', 'Team'])['Minutes'].sum()
    selected_players = player_minutes[player_minutes > 100].index
    # Filter overall_df based on selected_players
    overall_df = overall_df[overall_df.set_index(['Giocatore', 'Team']).index.isin(selected_players)]
    overall_df['Result'] = overall_df['Gap'] > 0
    overall_df['Tight'] = np.abs(overall_df['Gap']) < 5
    overall_df.loc[np.abs(overall_df['pm_permin']) > 10, 'pm_permin'] = np.nan
    overall_df["pm_permin_adj"] = overall_df['pm_permin'] - overall_df['Gap_permin']
    category_order = {'Tight': [False, True]}


    sum_df = overall_df.groupby(['Giocatore', 'Team']).sum()
    # permin_df = sum_df.div(sum_df['Minutes'], axis=0)
    sum_df['AS_PP_ratio'] = sum_df['AS'] / sum_df['PP']
    sum_df['PR_PP_ratio'] = sum_df['PR'] / sum_df['PP']
    sum_df['FS_FF_ratio'] = sum_df['FS'] / sum_df['FF']
    sum_df['ST_FF_ratio'] = sum_df['ST'] / sum_df['FF']

    sum_df['AS_PP_perc'] = sum_df['AS'] / (sum_df['PP'] + sum_df['AS'])
    sum_df['AS_permin'] = sum_df['AS'] / sum_df['Minutes']
    sum_df['PT_permin'] = sum_df['PT'] / sum_df['Minutes']
    sum_df['RO_permin'] = sum_df['RO'] / sum_df['Minutes']
    sum_df['RD_permin'] = sum_df['RD'] / sum_df['Minutes']
    sum_df['RD_permin'] = sum_df['RD'] / sum_df['Minutes']
    sum_df['PR_permin'] = sum_df['PR'] / sum_df['Minutes']
    sum_df['FS_permin'] = sum_df['FS'] / sum_df['Minutes']
    sum_df['FF_permin'] = sum_df['FF'] / sum_df['Minutes']
    sum_df['ST_permin'] = sum_df['ST'] / sum_df['Minutes']
    sum_df['True_shooting'] = sum_df['PT'] / 2 /(sum_df['2PTA'] + sum_df['3PTA'] + 0.44 * sum_df['FTA'])
    sum_df['3PT_%'] = sum_df['3PTM'] / sum_df['3PTA']
    sum_df['FT_%'] = sum_df['FTM'] / sum_df['FTA']
    sum_df['FTA_permin'] = sum_df['FTA'] / sum_df['Minutes']

    sum_df['3PTM_permin'] = sum_df['3PTM'] / sum_df['Minutes']
    median = overall_df.groupby(['Giocatore','Team']).agg({'pm_permin_adj': 'median',
                                                  'Minutes': 'sum',
                                                  'Gap_permin': 'median',
                                                  'pm_permin': 'median'})

    median['pm_permin_adj_plusgap'] = median['pm_permin_adj'] + median['Gap_permin']
    median.sort_values(inplace=True, by='pm_permin_adj_plusgap')
    median_tight = overall_df.loc[overall_df['Tight']].groupby(['Giocatore','Team']).agg({'pm_permin_adj': 'median',
                                                                                 'Minutes': 'sum'})

    median_tight.sort_values(inplace=True, by='pm_permin_adj')

    # agg_funcs = {'Team': lambda x: x.mode().iloc[0]}
    # sum_df['Team'] = overall_df.groupby(['Giocatore','Team']).agg(agg_funcs)
    # permin_df['Team'] = sum_df['Team']
    # median_tight['Team'] = sum_df['Team']
    # median['Team'] = sum_df['Team']

    sum_df.reset_index(inplace=True)
    # permin_df.reset_index(inplace=True)
    median_tight.reset_index(inplace=True)
    median.reset_index(inplace=True)

    box_list = []
    scatter_list = []
    for team in overall_df['Team'].unique():
        team_data = overall_df[overall_df['Team'] == team]
        median_team = median[median['Team'] == team]
        groups = team_data.groupby('Giocatore')
        fig = px.box(team_data, x='Giocatore', y='pm_permin_adj', color='Tight', points="all",
                     hover_data={'Opponent': ':.s', 'Gap': ':.0'}, category_orders=category_order)
        box_list.append(dp.Plot(fig, label=re.sub(r'[^a-zA-Z]', '', team)))
        fig = px.scatter(team_data, x='pm_permin_adj', y='Gap', size='Minutes', color='Giocatore', hover_name='Opponent')
        fig = add_median_lines(team_data, 'pm_permin_adj', 'Gap', fig)
        scatter_list.append(dp.Plot(fig, label=re.sub(r'[^a-zA-Z]', '', team)))

    fig_dict = {}
    fig = px.scatter(median, x='pm_permin_adj', y='pm_permin', size='Minutes', color='Team',  hover_name='Giocatore')
    fig = add_median_lines(median, 'pm_permin_adj', 'pm_permin', fig)
    fig_dict['pm_permin_adj/pm_permin'] = fig
    # fig.show()


    fig = px.scatter(sum_df, x='AS_permin', y='AS_PP_ratio', size='AS', color='Team',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'AS_permin', 'AS_PP_ratio', fig)
    fig_dict['AS_permin/AS_PP_ratio'] = fig

    # fig.show()

    fig = px.scatter(sum_df, x='AS_permin', y='PT_permin', color='Team',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'AS_permin', 'PT_permin', fig)
    fig_dict['AS_permin/PT_permin'] = fig

    # fig.show()

    fig = px.scatter(sum_df, x='RD_permin', y='RO_permin', size='RT', color='Team',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'RD_permin', 'RO_permin', fig)
    fig_dict['RD_permin/RO_permin'] = fig

    # fig.show()

    fig = px.scatter(sum_df, x='AS_PP_ratio', y='True_shooting', color='Team', size='PT',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'AS_PP_ratio', 'True_shooting', fig)
    fig.update_layout(yaxis_tickformat='.0%')
    fig_dict['AS_PP_ratio/True_shooting'] = fig

    # fig.show()

    fig = px.scatter(sum_df, x='PT_permin', y='True_shooting', color='Team', size='PT',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'PT_permin', 'True_shooting', fig)
    fig.update_layout(yaxis_tickformat='.0%')
    fig_dict['PT_permin/True_shooting'] = fig

    # fig.show()

    fig = px.scatter(sum_df, x='3PTM_permin', y='3PT_%', color='Team', size='3PTM',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, '3PTM_permin', '3PT_%', fig)
    fig.update_layout(yaxis_tickformat='.0%')
    fig_dict['3PTM_permin/3PT_%'] = fig

    # fig.show()

    fig = px.scatter(sum_df, x='FTA_permin', y='FT_%', color='Team', size='FTA',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'FTA_permin', 'FT_%', fig)
    fig.update_layout(yaxis_tickformat='.0%')
    fig_dict['FTA_permin/FT_%'] = fig

    fig = px.scatter(sum_df, x='PR_permin', y='PR_PP_ratio', color='Team', size='PR',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'PR_permin', 'PR_PP_ratio', fig)
    fig_dict['PR_permin/PR_PP_ratio'] = fig

    fig = px.scatter(sum_df, x='FS_permin', y='FS_FF_ratio', color='Team', size='FS',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'FS_permin', 'FS_FF_ratio', fig)
    fig_dict['FS_permin/FS_FF_ratio'] = fig

    fig = px.scatter(sum_df, x='ST_permin', y='ST_FF_ratio', color='Team', size='ST',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'ST_permin', 'ST_FF_ratio', fig)
    fig_dict['ST_permin/ST_FF_ratio'] = fig

    fig = px.scatter(sum_df, x='FF_permin', y='FF', color='Team', size='Minutes',  hover_name='Giocatore')
    fig = add_median_lines(sum_df, 'FF_permin', 'FF', fig)
    fig_dict['FF_permin/FF'] = fig

    # fig.show()
    report = dp.View(
        dp.Plot(fig_dict['pm_permin_adj/pm_permin'], caption='+/- al minuto vs +/- al minuto corretto per punteggio della partita. '
                                                             'In alto giocatori che fanno bene con dipendenza anche dal risultato di squadra, '
                                                             'a destra giocatori che fanno meglio del risultato di squadra'),
        dp.Plot(fig_dict['AS_permin/AS_PP_ratio'], caption='Efficienza negli assist: assist al minuto vs rapporto assist palle perse'),
        dp.Plot(fig_dict['AS_permin/PT_permin'], caption='Efficienza temporale in attacco: assist al minuto vs punti al minuto'),
        dp.Plot(fig_dict['RD_permin/RO_permin'], caption='Efficienza temporale a rimbalzo: rimbalzi difensivi al minuto vs rimbalzi offensivi al minuto'),
        dp.Plot(fig_dict['AS_PP_ratio/True_shooting'], caption='Efficienza sugli errori: rapporto assist-PP vs True shooting percentage'),
        dp.Plot(fig_dict['PT_permin/True_shooting'], caption='Efficienza al tiro: punti al minuto vs True shooting percentage'),
        dp.Plot(fig_dict['3PTM_permin/3PT_%'], caption='Efficienza al tiro da 3 punti: Tiri realizzati al minuto vs 3PT  percentage'),
        dp.Plot(fig_dict['FTA_permin/FT_%'], caption='Efficienza nei tiri liberi: Tiri tentati al minuto vs FT percentage'),
        dp.Plot(fig_dict['PR_permin/PR_PP_ratio'],
                caption='Efficienza palloni recuperati: PR al minuto vs Rapporto PR/PP'),
        dp.Plot(fig_dict['FS_permin/FS_FF_ratio'], caption="Falli subiti al minuto vs rapporto subiti-fatti"),
    dp.Plot(fig_dict['ST_permin/ST_FF_ratio'], caption="Stoppate al minuto vs rapporto stoppate-falli fatti"),
    dp.Plot(fig_dict['FF_permin/FF'], caption="Falli al minuto vs falli"),
    dp.Select(blocks=box_list, type=dp.SelectType.DROPDOWN),
    # dp.Select(blocks=scatter_list, type=dp.SelectType.DROPDOWN)

    )
    dp.save_report(report, path="serieB_stats.html", open=True,
                   formatting=dp.Formatting(accent_color='#2c1fe0',
                                            font=dp.FontChoice.SERIF,
                                            width=dp.Width.FULL))

    a = 0
        # plt.savefig(f'{team}.jpg')
plt.show()
a = 0
# texts = soup.find_all(class_=text_class)
# minutes = soup.find_all(class_=time_class)
# scores = soup.find_all(class_=score_class)
#
# # Find all elements with a class that contains the word "starter" in their class name
# starter_classes = soup.select("[class*=starter]")
#
# # Print the resulting element tags
# for element in starter_classes:
#     second_cell = element.find_all('td')[1]
#     print(second_cell.text)
#
# l = []
# for t, m, s in zip(texts, minutes, scores):
#     l.append([t.text.replace("\xa0", " "), m.text, s.text])
#
# column_names = ['Text', 'Q & Time', 'Score']
# df = pd.DataFrame(l, columns=column_names)
#
# df[['Home score', 'Away score']] = df['Score'].str.split('-', expand=True)
# df['Home score'] = pd.to_numeric(df['Home score'])
# df['Away score'] = pd.to_numeric(df['Away score'])
# df['Score Gap'] = df['Home score'] - df['Away score']
# df[['Quarter', 'Time']] = df['Q & Time'].str.split(' ', expand=True)
# df['Quarter'] = pd.to_numeric(df['Quarter'].str.replace('Q', ''))
# df['Time'] = pd.to_datetime(df['Time'], format='%M:%S')
# df['Time'] = df.apply(lambda row: row['Time'] + timedelta(minutes=(row['Quarter'] - 1)*10), axis=1)
# df = df.iloc[::-1]
#
# incorrect_times = (df['Time'].dt.minute == 0) & (df['Time'].dt.second == 0) & (df['Time'].shift() != pd.Timestamp.min) & (df['Quarter'] == df['Quarter'].shift())
#
# # Replace incorrect Times with 10:00
# df.loc[incorrect_times, 'Time'] = df.loc[incorrect_times, 'Time'] + pd.Timedelta(minutes=10)
#
#
#
# # Calculate the differences between each value and the previous value
# differences = df['Home Score'].diff()
#
# # Calculate the median and standard deviation of the differences
# median_diff = differences.median()
# std_diff = differences.std()
#
# # Identify any differences that are significantly larger or smaller than the typical difference
# outliers = df.loc[(differences > median_diff + 2*std_diff) | (differences < median_diff - 2*std_diff)]