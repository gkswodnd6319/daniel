"""
═══════════════════════════════════════════════════════════════
  PERSONAL HUB — NiceGUI Dashboard

  Tabs:
    1. 🎯 Career      — Career goals tracker & roadmap
    2. 🚀 Projects    — Personal project workspace
    3. 🏟️ Matchday   — Live sports schedules (EPL, UCL, LCK, MLB, KBO)

  Run:
    pip install nicegui
    python main.py

  Then open http://localhost:8080
═══════════════════════════════════════════════════════════════
"""

from nicegui import ui, app
from datetime import datetime

from career_tab import build_career_tab
from projects import build_projects_tab

# ── Shared State (in-memory, swap for SQLite/JSON later) ────
app.storage.general.setdefault('career_goals', [
    {'id': 1, 'title': 'Learn NiceGUI deeply', 'category': 'skill', 'status': 'in_progress', 'deadline': '2026-05-01', 'notes': 'Build personal hub project'},
    {'id': 2, 'title': 'Get promoted to Senior DS', 'category': 'career', 'status': 'not_started', 'deadline': '2026-12-31', 'notes': ''},
    {'id': 3, 'title': 'Publish a side project', 'category': 'project', 'status': 'not_started', 'deadline': '2026-08-01', 'notes': 'Open source on GitHub'},
])

app.storage.general.setdefault('projects', [
    {'id': 1, 'name': 'Personal Hub App', 'description': 'NiceGUI-based personal dashboard', 'status': 'active', 'tech': 'Python, NiceGUI', 'created': '2026-04-01', 'tasks': [
        {'text': 'Set up NiceGUI project structure', 'done': True},
        {'text': 'Build sports schedule tab', 'done': False},
        {'text': 'Add career goals tracker', 'done': False},
        {'text': 'Deploy to Cloud Run', 'done': False},
    ]},
])

def setup_theme():
    """Apply theme and custom CSS — call inside each @ui.page function."""
    ui.dark_mode().enable()
    ui.add_head_html('''
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

        body { font-family: 'Outfit', sans-serif !important; }
        .mono { font-family: 'JetBrains Mono', monospace !important; }

        .q-tab { text-transform: none !important; font-weight: 600 !important; letter-spacing: 0 !important; }
        .q-card { border-radius: 12px !important; }

        .goal-card:hover { transform: translateY(-2px); transition: all 0.2s; }
        .project-card:hover { transform: translateY(-2px); transition: all 0.2s; }

        .status-badge {
            padding: 2px 10px; border-radius: 20px; font-size: 11px;
            font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
        }
        .badge-live { background: #ff1744; color: white; }
        .badge-scheduled { background: #00e676; color: #0a0a0f; }
        .badge-ft { background: #555570; color: #e8e8f0; }

        .league-pl { background: #3d195b; color: white; }
        .league-ucl { background: #071d6b; color: white; }
        .league-lck { background: #c89b3c; color: #0a0a0f; }
        .league-mlb { background: #002d72; color: white; }
        .league-kbo { background: #c8102e; color: white; }

        .section-title {
            font-size: 13px; font-weight: 600; color: #8888a0;
            font-family: 'JetBrains Mono', monospace;
            letter-spacing: 0.05em; text-transform: uppercase;
        }
    </style>
    ''')


# ═══════════════════════════════════════════════════════════
#  SPORTS — Sub-tabs per league
# ═══════════════════════════════════════════════════════════
SUB_TABS = [
    ('Premier League', '⚽ Premier League'),
    ('Champions League', '🏆 Champions League'),
    ('LCK', '🎮 LCK'),
    ('LoL International', '🌏 LoL International'),
    ('KBO', '⚾ KBO'),
    ('MLB', '⚾ MLB'),
]


def build_sports_tab():
    """Sports tab with sub-tabs for each league."""
    from sports_data import get_matches_by_league

    with ui.column().classes('w-full gap-0'):
        with ui.tabs().classes('w-full').props(
            'dense active-color=green indicator-color=green no-caps'
        ) as league_tabs:
            tab_refs = {}
            for key, label in SUB_TABS:
                tab_refs[key] = ui.tab(key, label=label)

        with ui.tab_panels(league_tabs, value=tab_refs[SUB_TABS[0][0]]).classes('w-full'):
            for key, _ in SUB_TABS:
                with ui.tab_panel(tab_refs[key]):
                    if key == 'LCK':
                        _build_lck_panel(get_matches_by_league)
                    elif key == 'LoL International':
                        _build_lol_intl_panel(get_matches_by_league)
                    else:
                        _build_league_panel(key, get_matches_by_league)


def _build_lck_panel(get_matches_fn):
    """LCK panel with inner tabs: Match Schedule + Standings."""
    from sports_data import fetch_lck_standings

    with ui.tabs().props(
        'dense active-color=amber indicator-color=amber no-caps'
    ).classes('w-full') as lck_tabs:
        schedule_tab = ui.tab('lck_schedule', label='Match Schedule')
        standings_tab = ui.tab('lck_standings', label='Standings')

    with ui.tab_panels(lck_tabs, value=schedule_tab).classes('w-full'):
        with ui.tab_panel(schedule_tab):
            _build_league_panel('LCK', get_matches_fn)

        with ui.tab_panel(standings_tab):
            _build_standings_panel(fetch_lck_standings)


def _build_lol_intl_panel(get_matches_fn):
    """LoL International panel with inner tabs: Match Schedule + Bracket."""
    from sports_data import fetch_lol_intl_bracket

    with ui.tabs().props(
        'dense active-color=amber indicator-color=amber no-caps'
    ).classes('w-full') as intl_tabs:
        schedule_tab = ui.tab('intl_schedule', label='Match Schedule')
        bracket_tab = ui.tab('intl_bracket', label='Standings')

    with ui.tab_panels(intl_tabs, value=schedule_tab).classes('w-full'):
        with ui.tab_panel(schedule_tab):
            _build_league_panel('LoL International', get_matches_fn)

        with ui.tab_panel(bracket_tab):
            _build_bracket_panel(fetch_lol_intl_bracket)


def _build_bracket_panel(fetch_fn):
    """Render international tournament bracket stages."""
    container = ui.column().classes('w-full gap-4 p-4').style('max-width: 700px; margin: 0 auto;')

    def render():
        container.clear()
        stages, tournament_name = fetch_fn()

        if not stages:
            with container:
                ui.label('No tournament data available').classes('text-gray-500 text-center py-8')
            return

        with container:
            if tournament_name:
                ui.label(tournament_name).classes('text-xl font-extrabold')

            for stage in stages:
                ui.label(stage['name']).classes('section-title mt-4')

                for section in stage['sections']:
                    if section['name'] != stage['name']:
                        ui.label(section['name']).classes('text-sm font-bold text-gray-400 mt-2')

                    for match in section['matches']:
                        _build_bracket_match(match)

    render()
    ui.timer(120.0, render)


def _build_bracket_match(match):
    """Render a single bracket match."""
    is_completed = match['state'] == 'completed'
    is_live = match['state'] == 'inProgress'

    t1_win = match['team1_outcome'] == 'win'
    t2_win = match['team2_outcome'] == 'win'

    with ui.card().classes('w-full p-2'):
        with ui.element('div').style(
            'display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 8px;'
        ):
            # Team 1
            with ui.row().classes('items-center gap-2'):
                if match['team1_image']:
                    ui.image(match['team1_image']).style('width: 24px; height: 24px; border-radius: 4px;')
                t1_cls = 'font-bold' + (' text-green-400' if t1_win else (' text-gray-600' if t2_win else ''))
                ui.label(match['team1_code'] or match['team1_name']).classes(t1_cls)

            # Score
            if is_completed or is_live:
                score_text = f"{match['team1_wins']} : {match['team2_wins']}"
                cls = 'mono font-extrabold text-center'
                if is_live:
                    cls += ' text-red-400'
                ui.label(score_text).classes(cls)
            else:
                ui.label('vs').classes('mono text-xs text-gray-500 text-center')

            # Team 2
            with ui.row().classes('items-center gap-2 justify-end'):
                t2_cls = 'font-bold' + (' text-green-400' if t2_win else (' text-gray-600' if t1_win else ''))
                ui.label(match['team2_code'] or match['team2_name']).classes(t2_cls)
                if match['team2_image']:
                    ui.image(match['team2_image']).style('width: 24px; height: 24px; border-radius: 4px;')


def _build_standings_panel(fetch_fn):
    """Render a standings table."""
    container = ui.column().classes('w-full gap-0 p-4').style('max-width: 700px; margin: 0 auto;')

    def render():
        container.clear()
        standings = fetch_fn()
        if not standings:
            with container:
                ui.label('No standings data available').classes('text-gray-500 text-center py-8')
            return

        with container:
            # Header row
            with ui.row().classes('w-full items-center py-2 px-3').style(
                'border-bottom: 1px solid #2a2a3a'
            ):
                ui.label('#').classes('mono text-xs text-gray-500').style('width: 30px')
                ui.label('').style('width: 32px')  # logo space
                ui.label('TEAM').classes('mono text-xs text-gray-500 flex-grow')
                ui.label('W').classes('mono text-xs text-gray-500 text-center').style('width: 40px')
                ui.label('L').classes('mono text-xs text-gray-500 text-center').style('width: 40px')
                ui.label('WR').classes('mono text-xs text-gray-500 text-center').style('width: 50px')

            for entry in standings:
                wins = entry['wins']
                losses = entry['losses']
                total = wins + losses
                wr = f"{wins / total * 100:.0f}%" if total > 0 else '-'

                with ui.row().classes('w-full items-center py-2 px-3').style(
                    'border-bottom: 1px solid #1a1a2a'
                ):
                    ui.label(str(entry['rank'])).classes('mono font-bold').style('width: 30px')
                    if entry.get('image'):
                        ui.image(entry['image']).style('width: 28px; height: 28px')
                    else:
                        ui.label('').style('width: 28px')
                    ui.label(entry['name']).classes('font-bold flex-grow')
                    ui.label(str(wins)).classes('mono text-center font-bold text-green-400').style('width: 40px')
                    ui.label(str(losses)).classes('mono text-center text-red-400').style('width: 40px')
                    ui.label(wr).classes('mono text-center').style('width: 50px')

    render()
    ui.timer(120.0, render)


def _build_league_panel(league, get_matches_fn):
    """Build match list for a single league sub-tab."""
    from itertools import groupby

    matches_container = ui.column().classes('w-full gap-2 p-4').style('max-width: 700px; margin: 0 auto;')

    def render():
        matches_container.clear()
        matches = get_matches_fn(league)

        if not matches:
            with matches_container:
                if league == 'LoL International':
                    ui.label('No International Tournament in the next 30 days').classes('text-gray-500 text-center py-8')
                else:
                    ui.label('No matches found').classes('text-gray-500 text-center py-8')
            return

        matches.sort(key=lambda m: m['date'])
        for date_str, group in groupby(matches, key=lambda m: m['date'][:10]):
            with matches_container:
                ui.label(date_str).classes('section-title mt-4')
                for match in group:
                    _build_match_card(match)

    render()
    ui.timer(60.0, render)


def _build_match_card(match):
    """Render a single match card."""
    league_class = {
        'Premier League': 'league-pl',
        'Champions League': 'league-ucl',
        'LCK': 'league-lck',
        'LoL International': 'league-lck',
        'MLB': 'league-mlb',
        'KBO': 'league-kbo',
    }.get(match['league'], '')

    with ui.card().classes('w-full p-3'):
        # Top row: league badge + tournament + status
        with ui.row().classes('w-full justify-between items-center'):
            with ui.row().classes('gap-2 items-center'):
                ui.badge(match['league_short']).classes(f'{league_class} text-xs')
                tournament = match.get('tournament', '')
                if tournament:
                    ui.label(tournament).classes('mono text-xs text-gray-400')

            status_text = match['status']
            if match['status'] == 'LIVE':
                status_text = f"🔴 LIVE {match.get('minute', '')}"
            elif match['status'] == 'SCHEDULED':
                status_text = match['time']
            ui.label(status_text).classes('mono text-xs')

        # Teams + Score — use CSS grid for proper alignment
        with ui.element('div').classes('w-full py-2').style(
            'display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 8px;'
        ):
            # Home team (left-aligned)
            with ui.row().classes('items-center gap-2'):
                home_img = match.get('home_image', '')
                if home_img:
                    ui.image(home_img).style('width: 32px; height: 32px; border-radius: 4px;')
                with ui.column().classes('items-start gap-0'):
                    ui.label(match['home']).classes('font-bold')
                    home_rec = match.get('home_record', {})
                    if home_rec:
                        ui.label(f"{home_rec.get('wins', 0)}W {home_rec.get('losses', 0)}L").classes('mono text-xs text-gray-500')

            # Score (centered)
            if match['status'] in ('LIVE', 'FT'):
                ui.label(f"{match['score_home']} : {match['score_away']}").classes('mono text-2xl font-extrabold text-center')
            else:
                ui.label(match['time']).classes('mono text-lg text-gray-500 text-center')

            # Away team (right-aligned)
            with ui.row().classes('items-center gap-2 justify-end'):
                with ui.column().classes('items-end gap-0'):
                    ui.label(match['away']).classes('font-bold')
                    away_rec = match.get('away_record', {})
                    if away_rec:
                        ui.label(f"{away_rec.get('wins', 0)}W {away_rec.get('losses', 0)}L").classes('mono text-xs text-gray-500')
                away_img = match.get('away_image', '')
                if away_img:
                    ui.image(away_img).style('width: 32px; height: 32px; border-radius: 4px;')

        ui.label(match.get('round', '')).classes('mono text-xs text-gray-600 text-center w-full')


# ═══════════════════════════════════════════════════════════
#  MAIN PAGE LAYOUT
# ═══════════════════════════════════════════════════════════
@ui.page('/')
def main_page():
    setup_theme()
    # Header
    with ui.header().classes('items-center justify-between').style(
        'background: linear-gradient(135deg, #0a0a0f 0%, #12121a 100%); '
        'border-bottom: 1px solid #2a2a3a;'
    ):
        ui.label('PERSONAL HUB').classes('text-xl font-extrabold tracking-tight').style(
            'background: linear-gradient(135deg, #e8e8f0 20%, #00e676 100%); '
            '-webkit-background-clip: text; -webkit-text-fill-color: transparent;'
        )

        ui.label(datetime.now().strftime('%a, %b %d %Y')).classes('mono text-xs text-gray-500')

    # Tab navigation
    with ui.tabs().classes('w-full').props('dense active-color=green indicator-color=green') as tabs:
        career_tab = ui.tab('career', label='🎯 Career', icon=None)
        projects_tab = ui.tab('projects', label='🚀 Projects', icon=None)
        sports_tab = ui.tab('sports', label='🏟️ Sports', icon=None)

    # Tab panels
    with ui.tab_panels(tabs, value=career_tab).classes('w-full flex-grow'):
        with ui.tab_panel(career_tab):
            build_career_tab()

        with ui.tab_panel(projects_tab):
            build_projects_tab()

        with ui.tab_panel(sports_tab):
            build_sports_tab()


# ═══════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════
ui.run(
    title='Personal Hub',
    port=8080,
    dark=True,
    storage_secret='personal-hub-secret-key-change-me',
)
