"""
Modulo per analisi e visualizzazione delle mappe di tiro.
"""

import os
import pickle
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from collections import defaultdict
from scipy.ndimage import gaussian_filter

from .config import DATA_DIR, SIMILAR_TEAMS


def normalize_team_names(df):
    """Normalizza i nomi delle squadre usando SIMILAR_TEAMS."""
    if df is None or df.empty:
        return df

    df = df.copy()

    for col in ['home_team', 'away_team']:
        if col in df.columns:
            for variant, standard in SIMILAR_TEAMS:
                df.loc[df[col] == variant, col] = standard

    return df


def load_shots_data(campionato_filter=None):
    """
    Carica i dati dei tiri.

    Args:
        campionato_filter: 'a2', 'b_a', 'b_b' o None per tutti

    Returns:
        DataFrame con tutti i tiri (nomi squadre normalizzati)
    """
    shots_files = {
        'a2': os.path.join(DATA_DIR, 'shots_a2.pkl'),
        'b_a': os.path.join(DATA_DIR, 'shots_b_a.pkl'),
        'b_b': os.path.join(DATA_DIR, 'shots_b_b.pkl'),
    }

    if campionato_filter:
        files_to_load = {campionato_filter: shots_files.get(campionato_filter)}
    else:
        files_to_load = shots_files

    dfs = []
    for camp, filepath in files_to_load.items():
        if filepath and os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                df = pickle.load(f)
                dfs.append(df)

    if not dfs:
        return None

    result = pd.concat(dfs, ignore_index=True)
    return normalize_team_names(result)


# Court dimensions (scaled for plotting)
SCALE = 100 / 3
R_WIDTH = 15
R_LEN = 14
R_BASKET = 1.575
R_3P_DIST = 6.75
R_3P_CORNER = 6.6
R_3P_STRAIGHT_LEN = 2.99
R_AREA_WIDTH = 4.9
R_AREA_LEN = 5.8
R_RADIUS_AREA = 1.8

X_BORDER = R_WIDTH * SCALE / 2
Y_BASELINE = -R_BASKET * SCALE
Y_H_COURT_LINE = R_LEN * SCALE + Y_BASELINE
X_PAINT = R_AREA_WIDTH * SCALE / 2
Y_FT = R_AREA_LEN * SCALE + Y_BASELINE
RADIUS_FT = R_RADIUS_AREA * SCALE
THREE_PT_LINE_DIST = R_3P_DIST * SCALE
THREE_PT_LINE_CORNER = R_3P_CORNER * SCALE
THREE_PT_BREAK_Y = R_3P_STRAIGHT_LEN * SCALE + Y_BASELINE
ANGLE_3PT = 12 / 180 * np.pi


def ellipse_arc(x_center=0.0, y_center=0.0, a=10.5, b=10.5,
                start_angle=0.0, end_angle=2*np.pi, N=200, closed=False):
    """Generate SVG path for an elliptical arc."""
    t = np.linspace(start_angle, end_angle, N)
    x = x_center + a * np.cos(t)
    y = y_center + b * np.sin(t)
    path = f"M {x[0]}, {y[0]}"
    for k in range(1, len(t)):
        path += f"L{x[k]}, {y[k]}"
    if closed:
        path += " Z"
    return path


def draw_court(fig, line_color="#333333", lines_above=False):
    """Draw basketball court on a Plotly figure."""
    line_width = 3
    layer = "above" if lines_above else "below"

    fig.update_xaxes(range=[-X_BORDER - 20, X_BORDER + 20])
    fig.update_yaxes(range=[Y_BASELINE - 40, Y_H_COURT_LINE + 20])

    shapes = [
        dict(type="rect", x0=-X_BORDER, y0=Y_BASELINE, x1=X_BORDER, y1=Y_H_COURT_LINE,
             line=dict(color=line_color, width=line_width), layer=layer),
        dict(type="rect", x0=-X_PAINT, y0=Y_BASELINE, x1=X_PAINT, y1=Y_FT,
             line=dict(color=line_color, width=line_width), layer=layer),
        dict(type="path", path=ellipse_arc(x_center=0, y_center=Y_FT, a=RADIUS_FT, b=RADIUS_FT,
             start_angle=0, end_angle=np.pi),
             line=dict(color=line_color, width=line_width), layer=layer),
        dict(type="rect", x0=-2, y0=-7.25, x1=2, y1=-12.5,
             line=dict(color="#ec7607", width=line_width), fillcolor="#ec7607"),
        dict(type="circle", x0=-7.5, y0=-7.5, x1=7.5, y1=7.5,
             line=dict(color="#ec7607", width=line_width)),
        dict(type="line", x0=-30, y0=-12.5, x1=30, y1=-12.5,
             line=dict(color="#ec7607", width=line_width)),
        dict(type="path", path=ellipse_arc(a=40, b=40, start_angle=0, end_angle=np.pi),
             line=dict(color=line_color, width=line_width), layer=layer),
        dict(type="path", path=ellipse_arc(a=THREE_PT_LINE_DIST, b=THREE_PT_LINE_DIST,
             start_angle=ANGLE_3PT, end_angle=np.pi - ANGLE_3PT),
             line=dict(color=line_color, width=line_width), layer=layer),
        dict(type="line", x0=-THREE_PT_LINE_CORNER, y0=Y_BASELINE, x1=-THREE_PT_LINE_CORNER, y1=THREE_PT_BREAK_Y,
             line=dict(color=line_color, width=line_width), layer=layer),
        dict(type="line", x0=THREE_PT_LINE_CORNER, y0=Y_BASELINE, x1=THREE_PT_LINE_CORNER, y1=THREE_PT_BREAK_Y,
             line=dict(color=line_color, width=line_width), layer=layer),
        dict(type="path", path=ellipse_arc(y_center=Y_H_COURT_LINE, a=RADIUS_FT, b=RADIUS_FT,
             start_angle=0, end_angle=-np.pi),
             line=dict(color=line_color, width=line_width), layer=layer),
    ]

    fig.update_layout(
        height=550,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis=dict(scaleanchor="x", scaleratio=1, showgrid=False, zeroline=False, showline=False,
                   ticks="", showticklabels=False, fixedrange=True),
        xaxis=dict(showgrid=False, zeroline=False, showline=False,
                   ticks="", showticklabels=False, fixedrange=True),
    )

    for shape in shapes:
        fig.add_shape(shape)

    return fig


def convert_canvas_to_court(x_canvas, y_canvas, is_home, quarter=1):
    """
    Converte le coordinate canvas (360x240) in coordinate campo per la visualizzazione.

    I team cambiano campo a metà gara:
    - Q1-Q2: home tira verso x=0, away verso x=360
    - Q3+: home tira verso x=360, away verso x=0

    I tiri fuori dalla metà campo vengono speculari al canestro corretto.
    """
    canvas_width = 360
    canvas_height = 240
    half_court_len_m = 14
    court_width_m = 15

    # Determina se home tira verso x=0 (primo tempo) o x=360 (secondo tempo)
    home_attacks_left = quarter <= 2

    # Determina la direzione del tiro
    if is_home:
        attacks_left = home_attacks_left
    else:
        attacks_left = not home_attacks_left

    # Calcola distanza dal canestro target
    if attacks_left:
        # Target = x=0
        dist_from_basket_pix = x_canvas
        lateral_m = (y_canvas - canvas_height/2) / (canvas_height/2) * (court_width_m / 2)
    else:
        # Target = x=360
        dist_from_basket_pix = canvas_width - x_canvas
        lateral_m = -(y_canvas - canvas_height/2) / (canvas_height/2) * (court_width_m / 2)

    # Se il tiro è oltre metà campo, specchia al canestro
    if dist_from_basket_pix > canvas_width / 2:
        dist_from_basket_pix = canvas_width - dist_from_basket_pix

    # Converti pixel in metri (metà campo = 180 pixel = 14 metri)
    dist_from_basket_m = dist_from_basket_pix / (canvas_width / 2) * half_court_len_m

    x_plot = lateral_m * SCALE
    y_plot = dist_from_basket_m * SCALE + Y_BASELINE

    return x_plot, y_plot


def convert_shots_to_court_coords(shots_df):
    """
    Converte tutte le coordinate dei tiri in coordinate campo.

    Returns:
        Tuple (x_coords, y_coords, outcomes) - liste di coordinate e esiti
    """
    x_coords = []
    y_coords = []
    outcomes = []

    for _, shot in shots_df.iterrows():
        if shot['x'] == 0:  # Skip invalid
            continue
        quarter = shot.get('quarter', 1)
        x_plot, y_plot = convert_canvas_to_court(shot['x'], shot['y'], shot['is_home'], quarter)
        x_coords.append(x_plot)
        y_coords.append(y_plot)
        outcomes.append(1 if shot['made'] else 0)

    return x_coords, y_coords, outcomes


def compute_hexbins(x_coords, y_coords, outcomes, gridsize=15, min_threshold=0.001):
    """
    Compute hexagonal binning for shot data.

    Returns dict with:
        - x, y: hexagon centers (scaled coordinates)
        - accs_by_hex: accuracy per hexagon
        - freq_by_hex: frequency per hexagon
    """
    import matplotlib.pyplot as plt

    x_arr = np.array(x_coords)
    y_arr = np.array(y_coords)
    outcomes_arr = np.array(outcomes)

    if len(x_arr) == 0:
        return {"x": [], "y": [], "accs_by_hex": [], "freq_by_hex": []}

    # Create hexbin to get the grid structure
    fig_temp, ax_temp = plt.subplots()
    hexbin_obj = ax_temp.hexbin(
        x_arr, y_arr, C=outcomes_arr,
        gridsize=gridsize, reduce_C_function=np.sum, mincnt=1,
    )

    offsets = hexbin_obj.get_offsets()

    # Calculate which bin each shot belongs to
    bin_data = defaultdict(lambda: {"outcomes": [], "count": 0})

    for i in range(len(x_arr)):
        x, y = x_arr[i], y_arr[i]
        outcome = outcomes_arr[i]

        distances = np.sqrt((offsets[:, 0] - x) ** 2 + (offsets[:, 1] - y) ** 2)
        nearest_idx = np.argmin(distances)

        bin_data[nearest_idx]["outcomes"].append(outcome)
        bin_data[nearest_idx]["count"] += 1

    plt.close(fig_temp)

    total_shots = len(x_coords)
    x_centers, y_centers, accuracies, frequencies = [], [], [], []

    for bin_idx, data in bin_data.items():
        if bin_idx < len(offsets):
            x_center = offsets[bin_idx, 0]
            y_center = offsets[bin_idx, 1]

            if (x_center >= -X_BORDER and x_center <= X_BORDER and
                y_center >= Y_BASELINE and y_center <= Y_H_COURT_LINE):

                freq = data["count"] / total_shots
                if freq >= min_threshold:
                    x_centers.append(x_center)
                    y_centers.append(y_center)
                    accuracies.append(np.mean(data["outcomes"]))
                    frequencies.append(freq)

    return {
        "x": x_centers,
        "y": y_centers,
        "accs_by_hex": accuracies,
        "freq_by_hex": frequencies,
    }


def create_hexbin_chart(hexbin_data, title="Hexbin Shot Chart"):
    """Create Plotly hexbin visualization."""
    if not hexbin_data["x"]:
        return None

    xlocs = hexbin_data["x"]
    ylocs = hexbin_data["y"]
    accs = hexbin_data["accs_by_hex"]
    freqs = np.array(hexbin_data["freq_by_hex"])

    max_freq = 0.03
    freqs_capped = np.array([min(max_freq, f) for f in freqs])

    hexbin_text = [
        f"<i>Precisione:</i> {round(accs[i] * 100, 1)}%<BR>"
        f"<i>Frequenza:</i> {round(freqs[i] * 100, 2)}%"
        for i in range(len(freqs))
    ]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=xlocs, y=ylocs,
        mode="markers",
        marker=dict(
            size=freqs_capped,
            sizemode="area",
            sizeref=1.0 * max(freqs_capped) / (15**2) if len(freqs_capped) > 0 else 1,
            sizemin=2.5,
            color=accs,
            colorscale="RdYlGn",
            opacity=0.9,
            showscale=False,
            cmin=0, cmax=1,
            line=dict(width=1, color="#333333"),
            symbol="hexagon",
        ),
        text=hexbin_text,
        hoverinfo="text",
        showlegend=False,
    ))

    draw_court(fig)

    # Legend
    legend_y = Y_BASELINE - 60
    legend_x_left = -X_BORDER + 20

    for i, (color, label) in enumerate([
        ("rgb(215, 48, 39)", "Bassa"),
        ("rgb(254, 224, 139)", "Media"),
        ("rgb(26, 152, 80)", "Alta"),
    ]):
        fig.add_trace(go.Scatter(
            x=[legend_x_left + i * 60], y=[legend_y],
            mode="markers",
            marker=dict(size=20, color=color, opacity=0.9, symbol="hexagon",
                       line=dict(width=2, color="#333333")),
            showlegend=False, hoverinfo="skip",
        ))
        fig.add_annotation(
            x=legend_x_left + i * 60, y=legend_y - 20,
            text=f"<b>{label}</b>", showarrow=False,
            font=dict(size=11, color="#4d4d4d"), xanchor="center",
        )

    fig.add_annotation(
        x=legend_x_left + 60, y=legend_y + 20,
        text="<b>Precisione</b>", showarrow=False,
        font=dict(size=10, color="#4d4d4d"), xanchor="center",
    )

    fig.update_layout(title=dict(text=title, x=0.5, font=dict(size=16)))

    return fig


def compute_heatmap_data(x_coords, y_coords, bins=100, sigma=4):
    """
    Compute 2D histogram for heatmap visualization with Gaussian smoothing.
    """
    x_arr = np.array(x_coords)
    y_arr = np.array(y_coords)

    if len(x_arr) == 0:
        return None

    x_range = [-X_BORDER, X_BORDER]
    y_range = [Y_BASELINE, Y_H_COURT_LINE]

    volume, xedges, yedges = np.histogram2d(
        x_arr, y_arr, bins=bins, range=[x_range, y_range]
    )

    volume_smooth = gaussian_filter(volume, sigma=sigma, mode="constant", cval=0.0)

    return {
        "volume": volume_smooth.T,
        "xedges": xedges,
        "yedges": yedges,
    }


def create_heatmap_chart(heatmap_data, title="Heatmap Tiri"):
    """Create Plotly heatmap visualization."""
    if heatmap_data is None:
        return None

    z_data = heatmap_data["volume"]
    xedges = heatmap_data["xedges"]
    yedges = heatmap_data["yedges"]

    z_min = np.nanmin(z_data)
    z_max = np.nanmax(z_data)

    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        x=xedges, y=yedges, z=z_data,
        colorscale="Hot",
        zsmooth=False,
        showscale=True,
        opacity=1.0,
        colorbar=dict(
            title=dict(text="<B>Volume</B>", side="top", font=dict(size=11, color="#4d4d4d")),
            orientation="h", thickness=15, len=0.6,
            x=0.5, xanchor="center", y=0.02, yanchor="bottom",
            tickvals=[z_min, z_max], ticktext=["Basso", "Alto"],
            tickfont=dict(size=10, color="#4d4d4d"),
        ),
        hoverinfo="skip",
    ))

    draw_court(fig, line_color="#ffffff", lines_above=True)
    fig.update_layout(title=dict(text=title, x=0.5, font=dict(size=16)))

    return fig


def get_team_games(shots_df, team):
    """
    Ottiene la lista delle partite di una squadra.

    Returns:
        Lista di dict con game_code, opponent, home_score, away_score
    """
    team_shots = shots_df[
        (shots_df['home_team'] == team) | (shots_df['away_team'] == team)
    ]

    games = []
    for game_code in team_shots['game_code'].unique():
        game_shots = team_shots[team_shots['game_code'] == game_code].iloc[0]
        home = game_shots['home_team']
        away = game_shots['away_team']

        if home == team:
            opponent = away
            is_home = True
        else:
            opponent = home
            is_home = False

        games.append({
            'game_code': game_code,
            'opponent': opponent,
            'is_home': is_home,
            'label': f"{'vs' if is_home else '@'} {opponent}"
        })

    return sorted(games, key=lambda x: x['game_code'])
