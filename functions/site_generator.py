"""
Generatore sito statico per LNP Stats.
Crea pagine HTML separate con sidebar di navigazione.
"""

import os
import json
import shutil
from datetime import datetime

# Directory
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DOCS_DIR = os.path.join(BASE_DIR, 'docs')
STATIC_SRC = os.path.join(BASE_DIR, 'static')
STATIC_DST = os.path.join(DOCS_DIR, 'static')


# ============ CONFIGURAZIONE NAVIGAZIONE ============

SITE_STRUCTURE = {
    'a2': {
        'name': 'Serie A2',
        'icon': '🏆',
        'sections': {
            'squadre': {
                'name': 'Squadre',
                'icon': '🏀',
                'pages': [
                    ('classifiche', 'Classifiche & Stats'),
                    ('radar', 'Radar Squadre'),
                    ('vittorie-sconfitte', 'Vittorie vs Sconfitte'),
                    ('casa-trasferta', 'Casa vs Trasferta'),
                    ('quando-vince', 'Quando Vince'),
                    ('andamento', 'Andamento & Parziali'),
                ]
            },
            'giocatori': {
                'name': 'Giocatori',
                'icon': '👤',
                'pages': [
                    ('statistiche', 'Statistiche & Percentili'),
                    ('radar', 'Radar Confronto'),
                    ('consistenza', 'Consistenza'),
                    ('simili', 'Giocatori Simili'),
                    ('forma', 'Forma Recente'),
                    ('casa-trasferta', 'Casa vs Trasferta'),
                    ('distribuzione-tiri', 'Distribuzione Tiri'),
                    ('impatto', 'Impatto'),
                    ('clustering', 'Clustering & Tipologie'),
                    ('dipendenza', 'Dipendenza Squadra'),
                    ('momenti-decisivi', 'Momenti Decisivi'),
                ]
            },
        }
    },
    'b': {
        'name': 'Serie B',
        'icon': '🅱️',
        'subsections': {
            'girone-a': 'Girone A',
            'girone-b': 'Girone B',
            'combinata': 'Combinata',
        },
        'sections': {
            'squadre': {
                'name': 'Squadre',
                'icon': '🏀',
                'pages': [
                    ('classifiche', 'Classifiche & Stats'),
                    ('radar', 'Radar Squadre'),
                    ('vittorie-sconfitte', 'Vittorie vs Sconfitte'),
                    ('casa-trasferta', 'Casa vs Trasferta'),
                    ('quando-vince', 'Quando Vince'),
                    ('andamento', 'Andamento & Parziali'),
                ]
            },
            'giocatori': {
                'name': 'Giocatori',
                'icon': '👤',
                'pages': [
                    ('statistiche', 'Statistiche & Percentili'),
                    ('radar', 'Radar Confronto'),
                    ('consistenza', 'Consistenza'),
                    ('simili', 'Giocatori Simili'),
                    ('forma', 'Forma Recente'),
                    ('casa-trasferta', 'Casa vs Trasferta'),
                    ('distribuzione-tiri', 'Distribuzione Tiri'),
                    ('impatto', 'Impatto'),
                    ('clustering', 'Clustering & Tipologie'),
                    ('dipendenza', 'Dipendenza Squadra'),
                    ('momenti-decisivi', 'Momenti Decisivi'),
                ]
            },
        }
    }
}


# ============ TEMPLATE HTML ============

def get_base_template():
    """Ritorna il template HTML base con sidebar e CSS TwinPlay."""
    return '''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - LNP Stats</title>
    <link rel="icon" type="image/png" href="{root_path}static/favicon180x180.png">
    <link rel="stylesheet" href="{root_path}static/twinplay_brand.css">
    <script src="https://cdn.plot.ly/plotly-3.3.1.min.js"></script>
    <style>
        :root {{
            --sidebar-width: 280px;
            --header-height: 64px;
        }}

        body {{
            margin: 0;
            padding: 0;
        }}

        /* Header */
        .site-header {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: var(--header-height);
            background: var(--tp-gradient-primary);
            color: white;
            display: flex;
            align-items: center;
            padding: 0 var(--tp-spacing-lg);
            z-index: 1000;
            box-shadow: var(--tp-shadow-md);
        }}

        .header-logo {{
            display: flex;
            align-items: center;
            gap: var(--tp-spacing-md);
        }}

        .header-logo img {{
            height: 36px;
        }}

        .header-logo a {{
            color: white;
            text-decoration: none;
            font-family: var(--tp-font-primary);
            font-weight: 700;
            font-size: 1.25rem;
        }}

        .header-breadcrumb {{
            margin-left: var(--tp-spacing-xl);
            opacity: 0.8;
            font-size: 0.875rem;
        }}

        .menu-toggle {{
            display: none;
            background: none;
            border: none;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
            margin-right: var(--tp-spacing-md);
        }}

        /* Sidebar */
        .sidebar {{
            position: fixed;
            top: var(--header-height);
            left: 0;
            width: var(--sidebar-width);
            height: calc(100vh - var(--header-height));
            background: white;
            border-right: 1px solid #e0e0e0;
            overflow-y: auto;
            z-index: 999;
            transition: transform 0.3s ease;
        }}

        .sidebar-section {{
            border-bottom: 1px solid var(--tp-light);
        }}

        .sidebar-section-header {{
            padding: var(--tp-spacing-md) var(--tp-spacing-lg);
            font-family: var(--tp-font-primary);
            font-weight: 600;
            color: var(--tp-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: var(--tp-spacing-sm);
            transition: background 0.2s;
        }}

        .sidebar-section-header:hover {{
            background: var(--tp-light);
        }}

        .sidebar-section-header .arrow {{
            margin-left: auto;
            transition: transform 0.2s;
            font-size: 0.75rem;
        }}

        .sidebar-section.expanded .arrow {{
            transform: rotate(90deg);
        }}

        .sidebar-subsection {{
            display: none;
            background: var(--tp-light);
        }}

        .sidebar-section.expanded .sidebar-subsection {{
            display: block;
        }}

        .sidebar-category {{
            padding: var(--tp-spacing-sm) var(--tp-spacing-lg);
            padding-left: var(--tp-spacing-lg);
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--tp-gray);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: var(--tp-spacing-sm);
        }}

        .sidebar-link {{
            display: block;
            padding: var(--tp-spacing-sm) var(--tp-spacing-lg);
            padding-left: calc(var(--tp-spacing-lg) + 10px);
            color: var(--tp-dark);
            text-decoration: none;
            font-size: 0.875rem;
            transition: all 0.2s;
            border-left: 3px solid transparent;
        }}

        .sidebar-link:hover {{
            background: white;
            border-left-color: var(--tp-primary);
        }}

        .sidebar-link.active {{
            background: white;
            border-left-color: var(--tp-primary);
            color: var(--tp-secondary);
            font-weight: 600;
        }}

        .sidebar-home-btn {{
            display: block;
            padding: var(--tp-spacing-md) var(--tp-spacing-lg);
            color: var(--tp-gray);
            text-decoration: none;
            font-size: 0.875rem;
            border-bottom: 1px solid var(--tp-light);
            transition: all 0.2s;
        }}

        .sidebar-home-btn:hover {{
            background: var(--tp-light);
            color: var(--tp-secondary);
        }}

        .sidebar-competition {{
            padding: var(--tp-spacing-md) var(--tp-spacing-lg);
            background: var(--tp-gradient-primary);
            color: white;
            font-family: var(--tp-font-primary);
            font-weight: 600;
            font-size: 0.95rem;
            margin-bottom: var(--tp-spacing-sm);
        }}

        .sidebar:empty + .main {{
            margin-left: 0;
        }}

        /* Main content */
        .main {{
            margin-left: var(--sidebar-width);
            margin-top: var(--header-height);
            padding: var(--tp-spacing-xl);
            min-height: calc(100vh - var(--header-height));
            background: var(--tp-light);
        }}

        .page-title {{
            font-family: var(--tp-font-primary);
            font-size: 1.75rem;
            color: var(--tp-secondary);
            margin-bottom: var(--tp-spacing-xs);
        }}

        .page-subtitle {{
            color: var(--tp-gray);
            margin-bottom: var(--tp-spacing-xl);
        }}

        .content-section {{
            background: white;
            border-radius: var(--tp-radius-lg);
            padding: var(--tp-spacing-lg);
            margin-bottom: var(--tp-spacing-lg);
            box-shadow: var(--tp-shadow-sm);
        }}

        .section-title {{
            font-family: var(--tp-font-primary);
            font-size: 1.25rem;
            color: var(--tp-secondary);
            margin-bottom: var(--tp-spacing-lg);
            padding-bottom: var(--tp-spacing-sm);
            border-bottom: 2px solid var(--tp-light);
        }}

        /* Responsive */
        @media (max-width: 1024px) {{
            .sidebar {{
                transform: translateX(-100%);
            }}

            .sidebar.open {{
                transform: translateX(0);
            }}

            .main {{
                margin-left: 0;
            }}

            .menu-toggle {{
                display: block;
            }}
        }}

        /* Stats cards */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: var(--tp-spacing-lg);
            margin-bottom: var(--tp-spacing-xl);
        }}

        .stat-card {{
            background: var(--tp-gradient-primary);
            color: white;
            padding: var(--tp-spacing-lg);
            border-radius: var(--tp-radius-lg);
            text-align: center;
        }}

        .stat-card.accent {{
            background: var(--tp-gradient-accent);
            color: var(--tp-dark);
        }}

        .stat-card.orange {{
            background: linear-gradient(135deg, #ea580c, #f97316);
        }}

        .stat-value {{
            font-family: var(--tp-font-primary);
            font-size: 2.5rem;
            font-weight: 700;
        }}

        .stat-label {{
            font-size: 0.875rem;
            opacity: 0.9;
            margin-top: var(--tp-spacing-xs);
        }}

        /* Plotly responsive */
        .js-plotly-plot {{
            width: 100% !important;
        }}

        /* Footer */
        .site-footer {{
            text-align: center;
            padding: var(--tp-spacing-lg);
            color: var(--tp-gray);
            font-size: 0.8rem;
        }}

        .site-footer img {{
            height: 24px;
            margin-bottom: var(--tp-spacing-sm);
            opacity: 0.7;
        }}
    </style>
</head>
<body>
    <header class="site-header">
        <button class="menu-toggle" onclick="toggleSidebar()">☰</button>
        <div class="header-logo">
            <img src="{root_path}static/twinplay_one_row.svg" alt="TwinPlay">
            <a href="{root_path}index.html">LNP Stats</a>
        </div>
        <div class="header-breadcrumb">{breadcrumb}</div>
    </header>

    <nav class="sidebar" id="sidebar">
        {sidebar_html}
    </nav>

    <main class="main">
        <h1 class="page-title">{page_title}</h1>
        <p class="page-subtitle">{page_subtitle}</p>

        {content}

        <div class="site-footer">
            <img src="{root_path}static/twinplay_one_row.svg" alt="TwinPlay">
            <div>Ultimo aggiornamento: {last_update}</div>
            <div>Generato con LNP Stats</div>
        </div>
    </main>

    <script>
        function toggleSidebar() {{
            document.getElementById('sidebar').classList.toggle('open');
        }}

        // Espandi sezione corrente
        document.querySelectorAll('.sidebar-section-header').forEach(header => {{
            header.addEventListener('click', () => {{
                header.parentElement.classList.toggle('expanded');
            }});
        }});

        // Espandi automaticamente la sezione attiva
        const activeLink = document.querySelector('.sidebar-link.active');
        if (activeLink) {{
            let parent = activeLink.closest('.sidebar-section');
            if (parent) parent.classList.add('expanded');
        }}
    </script>
</body>
</html>'''


def get_competition_from_path(path):
    """Estrae il campionato dal path della pagina."""
    if path.startswith('a2/'):
        return 'a2'
    elif path.startswith('b/girone-a/'):
        return 'b_girone_a'
    elif path.startswith('b/girone-b/'):
        return 'b_girone_b'
    elif path.startswith('b/combinata/'):
        return 'b_combinata'
    return None


def get_competition_info(competition):
    """Ritorna info sul campionato per la sidebar."""
    info = {
        'a2': {'name': 'Serie A2', 'path_prefix': 'a2'},
        'b_girone_a': {'name': 'Serie B - Girone A', 'path_prefix': 'b/girone-a'},
        'b_girone_b': {'name': 'Serie B - Girone B', 'path_prefix': 'b/girone-b'},
        'b_combinata': {'name': 'Serie B - Combinata', 'path_prefix': 'b/combinata'},
    }
    return info.get(competition, {})


def generate_sidebar_html(active_path='', competition=None):
    """Genera l'HTML della sidebar per il campionato corrente."""

    # Se siamo in homepage, sidebar vuota
    if not competition:
        return ''

    comp_info = get_competition_info(competition)
    if not comp_info:
        return ''

    # Usa le sections di A2 o B (stessa struttura)
    if competition == 'a2':
        sections = SITE_STRUCTURE['a2']['sections']
    else:
        sections = SITE_STRUCTURE['b']['sections']

    path_prefix = comp_info['path_prefix']

    html = f'''
    <a href="{{root}}index.html" class="sidebar-home-btn">
        ← Cambia campionato
    </a>
    <div class="sidebar-competition">
        {comp_info['name']}
    </div>
    '''

    for section_id, section in sections.items():
        html += f'<div class="sidebar-category">{section["name"]}</div>'
        for page_id, page_name in section['pages']:
            path = f'{path_prefix}/{section_id}/{page_id}.html'
            active = 'active' if path == active_path else ''
            html += f'<a href="{{root}}{path}" class="sidebar-link {active}">{page_name}</a>'

    return html


def generate_page(title, page_title, subtitle, content, breadcrumb, active_path, depth=0):
    """Genera una pagina HTML completa."""
    root_path = '../' * depth

    # Determina il campionato dal path
    competition = get_competition_from_path(active_path)

    sidebar = generate_sidebar_html(active_path, competition)
    sidebar = sidebar.replace('{root}', root_path)

    template = get_base_template()

    return template.format(
        title=title,
        root_path=root_path,
        breadcrumb=breadcrumb,
        sidebar_html=sidebar,
        page_title=page_title,
        page_subtitle=subtitle,
        content=content,
        last_update=datetime.now().strftime('%d/%m/%Y %H:%M')
    )


def ensure_dir(path):
    """Crea directory se non esiste."""
    os.makedirs(path, exist_ok=True)


# ============ HOMEPAGE ============

def generate_homepage(stats):
    """Genera la homepage pulita con solo i 3 campionati."""
    content = '''
    <style>
        .home-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}

        .home-subtitle {{
            color: var(--tp-gray);
            margin-bottom: 40px;
            text-align: center;
            font-size: 1.1rem;
        }}

        .competitions-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 25px;
            width: 100%;
            max-width: 1100px;
        }}

        @media (max-width: 900px) {{
            .competitions-grid {{
                grid-template-columns: 1fr;
                max-width: 400px;
            }}
        }}

        .competition-card {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            background: linear-gradient(135deg, #302B8F 0%, #18205E 100%);
            color: white;
            padding: 50px 30px;
            border-radius: var(--tp-radius-xl);
            transition: all 0.25s ease;
            box-shadow: 0 4px 20px rgba(48, 43, 143, 0.3);
            min-height: 180px;
        }}

        .competition-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 30px rgba(48, 43, 143, 0.4);
        }}

        .competition-name {{
            font-family: var(--tp-font-primary);
            font-size: 1.4rem;
            font-weight: 600;
            margin-bottom: 8px;
            text-align: center;
        }}

        .competition-stats {{
            opacity: 0.85;
            font-size: 0.95rem;
        }}
    </style>

    <div class="home-container">
        <p class="home-subtitle">Seleziona un campionato</p>

        <div class="competitions-grid">
            <a href="a2/squadre/classifiche.html" class="competition-card">
                <div class="competition-name">Serie A2</div>
                <div class="competition-stats">{a2_teams} squadre</div>
            </a>

            <a href="b/girone-a/squadre/classifiche.html" class="competition-card">
                <div class="competition-name">Serie B - Girone A</div>
                <div class="competition-stats">{ba_teams} squadre</div>
            </a>

            <a href="b/girone-b/squadre/classifiche.html" class="competition-card">
                <div class="competition-name">Serie B - Girone B</div>
                <div class="competition-stats">{bb_teams} squadre</div>
            </a>
        </div>
    </div>
    '''.format(**stats)

    # Homepage speciale senza sidebar
    return generate_homepage_html(content)


def generate_homepage_html(content):
    """Genera l'HTML della homepage senza sidebar."""
    return '''<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LNP Stats</title>
    <link rel="icon" type="image/png" href="static/favicon180x180.png">
    <link rel="stylesheet" href="static/twinplay_brand.css">
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            height: 100%;
            overflow: hidden;
        }}

        body {{
            display: flex;
            flex-direction: column;
            background: var(--tp-light);
        }}

        .home-header {{
            background: var(--tp-gradient-primary);
            color: white;
            padding: 15px 30px;
            display: flex;
            align-items: center;
            gap: 15px;
            flex-shrink: 0;
        }}

        .home-header img {{
            height: 28px;
        }}

        .home-header span {{
            font-family: var(--tp-font-primary);
            font-weight: 700;
            font-size: 1.1rem;
        }}

        .home-main {{
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}

        .home-footer {{
            text-align: center;
            padding: 15px;
            color: var(--tp-gray);
            font-size: 0.75rem;
            flex-shrink: 0;
        }}

        .home-footer img {{
            height: 20px;
            opacity: 0.6;
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <header class="home-header">
        <img src="static/twinplay_one_row.svg" alt="TwinPlay">
        <span>LNP Stats</span>
    </header>

    <main class="home-main">
        {content}
    </main>

    <footer class="home-footer">
        <img src="static/twinplay_one_row.svg" alt="TwinPlay"><br>
        Ultimo aggiornamento: {last_update}
    </footer>
</body>
</html>'''.format(content=content, last_update=datetime.now().strftime('%d/%m/%Y %H:%M'))


# ============ GENERATORE PRINCIPALE ============

def generate_site(data_stats, page_contents):
    """
    Genera l'intero sito.

    Args:
        data_stats: dict con statistiche riassuntive
        page_contents: dict con contenuti delle pagine {path: content_html}
    """
    ensure_dir(DOCS_DIR)

    # Homepage
    homepage = generate_homepage(data_stats)
    with open(os.path.join(DOCS_DIR, 'index.html'), 'w') as f:
        f.write(homepage)
    print(f"Generato: docs/index.html")

    # Pagine contenuto
    for path, page_data in page_contents.items():
        full_path = os.path.join(DOCS_DIR, path)
        ensure_dir(os.path.dirname(full_path))

        depth = path.count('/')

        page_html = generate_page(
            title=page_data['title'],
            page_title=page_data['page_title'],
            subtitle=page_data.get('subtitle', ''),
            content=page_data['content'],
            breadcrumb=page_data.get('breadcrumb', ''),
            active_path=path,
            depth=depth
        )

        with open(full_path, 'w') as f:
            f.write(page_html)
        print(f"Generato: docs/{path}")

    # Copia file statici
    copy_static_files()

    print(f"\nSito generato in: {DOCS_DIR}/")
    print(f"Totale pagine: {len(page_contents) + 1}")


def copy_static_files():
    """Copia i file statici (CSS, immagini, loghi) in docs/static/."""
    if os.path.exists(STATIC_DST):
        shutil.rmtree(STATIC_DST)

    if os.path.exists(STATIC_SRC):
        shutil.copytree(STATIC_SRC, STATIC_DST)
        print(f"Copiati file statici in: docs/static/")
