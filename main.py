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
from sports_data import warm_cache as warm_sports_cache, _cache as _sports_cache
from projects.fx_data import warm_cache as warm_fx_cache, _cache as _fx_cache

# Clear stale caches from hot reload, then pre-fetch fresh data
_sports_cache.clear()
_fx_cache.clear()
warm_sports_cache()
warm_fx_cache()
from projects import build_projects_tab
from projects.rich_man import build_rich_man_tab

# ── Shared State (in-memory, swap for SQLite/JSON later) ────
app.storage.general.setdefault('career_goals', [
    {'id': 1, 'title': 'Learn NiceGUI deeply', 'category': 'skill', 'status': 'in_progress', 'deadline': '2026-05-01', 'notes': 'Build personal hub project'},
    {'id': 2, 'title': 'Get promoted to Senior DS', 'category': 'career', 'status': 'not_started', 'deadline': '2026-12-31', 'notes': ''},
    {'id': 3, 'title': 'Publish a side project', 'category': 'project', 'status': 'not_started', 'deadline': '2026-08-01', 'notes': 'Open source on GitHub'},
])

app.storage.general.setdefault('career_timeline', [])

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

        .fav-highlight {
            border-left: 3px solid #00e676 !important;
            background: rgba(0, 230, 118, 0.06) !important;
        }
        .fav-team-name { color: #00e676 !important; }
        .today-header {
            color: #00e676 !important;
            font-weight: 700 !important;
        }

        .bracket-round { min-width: 200px; }
        .bracket-match {
            border: 1px solid #2a2a3a; border-radius: 8px;
            padding: 6px 10px; margin: 4px 0;
        }
        .bracket-match.fav-highlight {
            border-color: #00e676 !important;
        }
        .bracket-team { display: flex; align-items: center; gap: 6px; padding: 2px 0; }
        .bracket-team.winner { color: #00e676; font-weight: 700; }
        .bracket-team.loser { color: #555; }
        .bracket-connector {
            border-left: 2px solid #2a2a3a;
            border-top: 2px solid #2a2a3a;
            border-bottom: 2px solid #2a2a3a;
            width: 20px; align-self: center;
        }
    </style>
    ''')


# ═══════════════════════════════════════════════════════════
#  SPORTS — Data-driven league configuration
# ═══════════════════════════════════════════════════════════

# Standings column definitions: (header, key, width, color_class)
_COLS_WL = [
    ('W', 'wins', '40px', 'font-bold text-green-400'),
    ('L', 'losses', '40px', 'text-red-400'),
    ('WR', '_wr', '50px', ''),
]
_COLS_KBO = [
    ('G', 'games', '35px', ''),
    ('W', 'wins', '35px', 'font-bold text-green-400'),
    ('L', 'losses', '35px', 'text-red-400'),
    ('D', 'draws', '35px', 'text-gray-400'),
    ('PCT', 'win_rate', '50px', ''),
    ('GB', 'gb', '45px', ''),
]
_COLS_PL = [
    ('G', 'games', '30px', ''),
    ('W', 'wins', '30px', 'font-bold text-green-400'),
    ('D', 'draws', '30px', 'text-gray-400'),
    ('L', 'losses', '30px', 'text-red-400'),
    ('GD', 'gd', '35px', ''),
    ('Pts', 'points', '35px', 'font-bold text-amber-400'),
]
_COLS_MLB = [
    ('W', 'wins', '40px', 'font-bold text-green-400'),
    ('L', 'losses', '40px', 'text-red-400'),
    ('PCT', 'win_rate', '50px', ''),
    ('GB', 'gb', '45px', ''),
]

LEAGUE_BADGE_CLASS = {
    'Premier League': 'league-pl',
    'Champions League': 'league-ucl',
    'LCK': 'league-lck',
    'LoL International': 'league-lck',
    'MLB': 'league-mlb',
    'KBO': 'league-kbo',
}

# Each league config: (tab_key, tab_label, standings_fn_name, standings_columns, bracket_fn_name, empty_msg)
LEAGUES = [
    {
        'key': 'Premier League', 'label': '⚽ Premier League',
        'standings_fn': 'fetch_pl_standings', 'standings_cols': _COLS_PL,
    },
    {
        'key': 'Champions League', 'label': '🏆 Champions League',
        'standings_fn': 'fetch_ucl_standings', 'standings_cols': _COLS_PL,
        'bracket_fn': 'fetch_ucl_bracket', 'bracket_label': 'Knockout Bracket',
    },
    {
        'key': 'LCK', 'label': '🎮 LCK',
        'standings_fn': 'fetch_lck_standings', 'standings_cols': _COLS_WL,
    },
    {
        'key': 'LoL International', 'label': '🌏 LoL International',
        'bracket_fn': 'fetch_lol_intl_bracket',
        'empty_msg': 'No International Tournament in the next 30 days',
    },
    {
        'key': 'KBO', 'label': '⚾ KBO',
        'standings_fn': 'fetch_kbo_standings', 'standings_cols': _COLS_KBO,
        'bracket_fn': 'fetch_kbo_postseason', 'bracket_label': 'Post-Season',
        'bracket_empty': 'No post-season games yet',
    },
    {
        'key': 'MLB', 'label': '⚾ MLB',
        'standings_fn': 'fetch_mlb_standings', 'standings_cols': _COLS_MLB,
        'standings_grouped': 'division',
        'bracket_fn': 'fetch_mlb_postseason', 'bracket_label': 'Post-Season',
        'bracket_empty': 'No post-season games yet',
    },
]

# Worlds sub-tabs config (nested inside the Worlds parent tab)
_COLS_WBC = [
    ('W', 'wins', '35px', 'font-bold text-green-400'),
    ('L', 'losses', '35px', 'text-red-400'),
    ('PCT', 'win_rate', '50px', ''),
]

WORLDS_TABS = [
    {
        'key': 'World Cup', 'label': '⚽ World Cup',
        'bracket_fn': 'fetch_worldcup_bracket', 'bracket_label': 'Knockout Bracket',
        'bracket_empty': 'No World Cup data available yet',
        'empty_msg': 'No World Cup matches scheduled yet',
    },
    {
        'key': 'WBC', 'label': '⚾ WBC',
        'standings_fn': 'fetch_wbc_standings', 'standings_cols': _COLS_WBC,
        'standings_grouped': 'pool',
        'bracket_fn': 'fetch_wbc_bracket', 'bracket_label': 'Knockout Bracket',
        'bracket_empty': 'No WBC knockout data yet',
    },
    {
        'key': 'Intl Others', 'label': '🌐 Others',
        'empty_msg': 'No international matches scheduled',
    },
]


def _build_league_from_config(cfg, fav, sports_data, get_matches_by_league, get_team_list):
    """Build a league panel from config dict — reusable for both LEAGUES and WORLDS_TABS."""
    key = cfg['key']
    _build_team_selector(key, get_team_list, fav)

    standings_fn = getattr(sports_data, cfg['standings_fn'], None) if 'standings_fn' in cfg else None
    bracket_fn = getattr(sports_data, cfg['bracket_fn'], None) if 'bracket_fn' in cfg else None

    inner_tabs_cfg = [('sched', 'Match Schedule')]
    if standings_fn:
        inner_tabs_cfg.append(('standings', 'Standings'))
    if bracket_fn:
        inner_tabs_cfg.append(('bracket', cfg.get('bracket_label', 'Standings')))

    if len(inner_tabs_cfg) > 1:
        with ui.tabs().props(
            'dense active-color=amber indicator-color=amber no-caps'
        ).classes('w-full') as inner_tabs:
            tab_map = {tid: ui.tab(f'{key}_{tid}', label=lbl) for tid, lbl in inner_tabs_cfg}

        inner_built = set()
        # Reverse map: full tab name -> short tid
        tab_name_to_tid = {f'{key}_{tid}': tid for tid, _ in inner_tabs_cfg}

        def build_inner(tab_name):
            tid = tab_name_to_tid.get(tab_name, tab_name)
            if tid in inner_built:
                return
            inner_built.add(tid)
            with inner_panels:
                with ui.tab_panel(tab_map[tid]):
                    if tid == 'sched':
                        _build_league_schedule(key, get_matches_by_league, fav, cfg.get('empty_msg'))
                    elif tid == 'standings' and standings_fn:
                        _build_standings_panel(standings_fn, fav, cfg['standings_cols'], cfg.get('standings_grouped'), cfg.get('standings_title'))
                    elif tid == 'bracket' and bracket_fn:
                        _build_bracket_panel(bracket_fn, fav, cfg.get('bracket_empty'))

        inner_panels = ui.tab_panels(inner_tabs, value=tab_map['sched'],
                                     on_change=lambda e, bld=build_inner: bld(e.value)).classes('w-full')
        build_inner(f'{key}_sched')
    else:
        _build_league_schedule(key, get_matches_by_league, fav, cfg.get('empty_msg'))


def _build_today_panel(get_matches_by_league, fav_teams):
    """Today's matches across all leagues, highlighting favorite teams."""
    container = ui.column().classes('w-full gap-2 p-4').style('max-width: 700px; margin: 0 auto;')

    def render():
        container.clear()
        today = datetime.now().strftime('%Y-%m-%d')
        all_today = []

        for cfg in LEAGUES:
            key = cfg['key']
            try:
                matches = get_matches_by_league(key)
                for m in matches:
                    if m.get('date', '')[:10] == today:
                        all_today.append(m)
            except Exception:
                pass

        fav_set = {cfg['key']: fav_teams[cfg['key']]['value'] for cfg in LEAGUES if fav_teams[cfg['key']]['value']}

        with container:
            ui.label(f"TODAY — {today}").classes('section-title mt-2 today-header')

            if not all_today:
                ui.label('No matches today').classes('text-gray-500 text-center py-8')
                return

            # My team's matches first
            my_matches = []
            other_matches = []
            for m in all_today:
                is_mine = any(
                    _is_fav(fav, m.get('home', '')) or _is_fav(fav, m.get('away', ''))
                    for fav in fav_set.values()
                )
                if is_mine:
                    my_matches.append(m)
                else:
                    other_matches.append(m)

            if my_matches:
                ui.label('MY TEAMS').classes('section-title mt-2')
                for m in sorted(my_matches, key=lambda x: x['date']):
                    fav = next((f for f in fav_set.values() if _is_fav(f, m.get('home', '')) or _is_fav(f, m.get('away', ''))), '')
                    _build_match_card(m, fav)

            if other_matches:
                ui.label('OTHER MATCHES').classes('section-title mt-4')
                for m in sorted(other_matches, key=lambda x: x['date']):
                    _build_match_card(m)

    render()
    # Register with all fav_teams so team selection re-renders
    for cfg in LEAGUES:
        fav_teams[cfg['key']]['renderers'].append(render)


def build_sports_tab():
    """Sports tab — builds all leagues from LEAGUES config + Worlds meta-tab."""
    import sports_data
    from sports_data import get_matches_by_league, get_team_list

    all_configs = LEAGUES + WORLDS_TABS
    fav_teams = {
        cfg['key']: {'value': app.storage.user.get(f"fav_{cfg['key']}", ''), 'renderers': []}
        for cfg in all_configs
    }

    with ui.column().classes('w-full gap-0'):
        with ui.tabs().classes('w-full').props(
            'dense active-color=green indicator-color=green no-caps'
        ) as league_tabs:
            tab_refs = {'Today': ui.tab('Today', label='📅 Today')}
            for cfg in LEAGUES:
                tab_refs[cfg['key']] = ui.tab(cfg['key'], label=cfg['label'])
            tab_refs['Worlds'] = ui.tab('Worlds', label='🌍 Worlds')

        built = set()

        def build_league(key):
            if key in built:
                return
            built.add(key)

            with tab_panels:
                with ui.tab_panel(tab_refs[key]):
                    if key == 'Today':
                        _build_today_panel(get_matches_by_league, fav_teams)
                    elif key == 'Worlds':
                        _build_worlds_panel(sports_data, get_matches_by_league, get_team_list, fav_teams)
                    else:
                        cfg = next(c for c in LEAGUES if c['key'] == key)
                        fav = fav_teams[key]
                        _build_league_from_config(cfg, fav, sports_data, get_matches_by_league, get_team_list)

        active_key = {'value': 'Today'}

        def on_tab_change(e):
            active_key['value'] = e.value
            build_league(e.value)

        tab_panels = ui.tab_panels(league_tabs, value=tab_refs['Today'],
                                   on_change=on_tab_change).classes('w-full')

        build_league('Today')

        # Single global refresh timer — only re-renders the active tab's panels
        def global_refresh():
            key = active_key['value']
            if key == 'Worlds':
                # Worlds has its own sub-tabs, refresh handled there
                return
            if key in fav_teams:
                for fn in fav_teams[key].get('renderers', []):
                    fn()

        ui.timer(300.0, global_refresh)


def _build_worlds_panel(sports_data, get_matches_by_league, get_team_list, fav_teams):
    """Build the Worlds meta-tab with sub-tabs: World Cup, WBC, Others."""
    with ui.tabs().props(
        'dense active-color=cyan indicator-color=cyan no-caps'
    ).classes('w-full') as worlds_tabs:
        wtab_refs = {cfg['key']: ui.tab(cfg['key'], label=cfg['label']) for cfg in WORLDS_TABS}

    worlds_built = set()

    def build_worlds_sub(key):
        if key in worlds_built:
            return
        worlds_built.add(key)
        cfg = next(c for c in WORLDS_TABS if c['key'] == key)
        fav = fav_teams[key]
        with worlds_panels:
            with ui.tab_panel(wtab_refs[key]):
                _build_league_from_config(cfg, fav, sports_data, get_matches_by_league, get_team_list)

    worlds_panels = ui.tab_panels(worlds_tabs, value=wtab_refs[WORLDS_TABS[0]['key']],
                                  on_change=lambda e: build_worlds_sub(e.value)).classes('w-full')

    build_worlds_sub(WORLDS_TABS[0]['key'])


# ── Helpers ────────────────────────────────────────────────

def _is_fav(fav, name):
    """Check if name matches favorite (either direction substring)."""
    if not fav or not name:
        return False
    return fav in name or name in fav


# ── Reusable UI components ────────────────────────────────

def _build_team_selector(league, get_team_list, fav_state):
    """Dropdown to pick favorite team. Triggers re-render on change."""
    teams = get_team_list(league)
    if not teams:
        return
    options = {'': 'None'} | {t: t for t in teams}

    # Reset stale stored value that no longer exists in options
    if fav_state['value'] and fav_state['value'] not in options:
        fav_state['value'] = ''
        app.storage.user[f'fav_{league}'] = ''

    def on_change(e):
        fav_state['value'] = e.value
        app.storage.user[f'fav_{league}'] = e.value
        for fn in fav_state['renderers']:
            fn()

    with ui.row().classes('w-full items-center gap-2 px-4 py-2').style('max-width: 700px; margin: 0 auto;'):
        ui.label('MY TEAM').classes('section-title')
        ui.select(options=options, value=fav_state['value'], on_change=on_change,
                  ).props('dense outlined').classes('text-sm').style('min-width: 180px')


def _register(fav_state, render_fn, container=None):
    """Run a render function and register it for fav-change re-renders."""
    if container:
        with container:
            ui.spinner('dots', size='lg').classes('mx-auto my-8')
    try:
        render_fn()
    except Exception:
        if container:
            container.clear()
            with container:
                ui.label('Failed to load data').classes('text-gray-500 text-center py-8')
    fav_state['renderers'].append(render_fn)


def _build_league_schedule(league, get_matches_fn, fav_state, empty_msg=None):
    """Match list with today pinned at top."""
    from itertools import groupby

    container = ui.column().classes('w-full gap-2 p-4').style('max-width: 700px; margin: 0 auto;')

    def render():
        container.clear()
        matches = get_matches_fn(league)
        fav = fav_state['value']
        today = datetime.now().strftime('%Y-%m-%d')

        if not matches:
            with container:
                ui.label(empty_msg or 'No matches found').classes('text-gray-500 text-center py-8')
            return

        matches.sort(key=lambda m: m['date'])
        today_matches = [m for m in matches if m['date'][:10] == today]
        past = [m for m in matches if m['date'][:10] < today]
        future = [m for m in matches if m['date'][:10] > today]
        # Limit: last 10 past + today + next 20 future
        capped = past[-10:] + today_matches + future[:20]

        with container:
            if today_matches:
                ui.label(f"TODAY — {today}").classes('section-title mt-2 today-header')
                for m in today_matches:
                    _build_match_card(m, fav)
            other = [m for m in capped if m['date'][:10] != today]
            for date_str, group in groupby(other, key=lambda m: m['date'][:10]):
                ui.label(date_str).classes('section-title mt-4')
                for m in group:
                    _build_match_card(m, fav)

    _register(fav_state, render, container)


def _build_standings_panel(fetch_fn, fav_state, columns, group_by=None, title=None):
    """Generic standings table driven by column definitions. Optional grouping."""
    container = ui.column().classes('w-full gap-0 p-4').style('max-width: 700px; margin: 0 auto;')

    def _render_header():
        with ui.row().classes('w-full items-center py-2 px-3').style('border-bottom: 1px solid #2a2a3a'):
            ui.label('#').classes('mono text-xs text-gray-500').style('width: 30px')
            ui.label('').style('width: 32px')
            ui.label('TEAM').classes('mono text-xs text-gray-500 flex-grow')
            for header, _, width, _ in columns:
                ui.label(header).classes('mono text-xs text-gray-500 text-center').style(f'width: {width}')

    def render():
        container.clear()
        standings = fetch_fn()
        fav = fav_state['value']
        if not standings:
            with container:
                ui.label('No standings data available').classes('text-gray-500 text-center py-8')
            return

        with container:
            auto_title = title or (standings[0].get('_title', '') if standings else '')
            if auto_title:
                ui.label(auto_title).classes('text-lg font-extrabold mb-2')
            if group_by:
                from itertools import groupby as igroupby
                for group_name, entries in igroupby(standings, key=lambda e: e.get(group_by, '')):
                    ui.label(group_name).classes('section-title mt-4 mb-1')
                    _render_header()
                    for entry in entries:
                        _render_standings_row(entry, fav, columns)
            else:
                _render_header()
                for entry in standings:
                    _render_standings_row(entry, fav, columns)

    def _render_standings_row(entry, fav, cols):
        is_fav = _is_fav(fav, entry['name'])
        row_cls = 'w-full items-center py-2 px-3' + (' fav-highlight' if is_fav else '')
        with ui.row().classes(row_cls).style('border-bottom: 1px solid #1a1a2a'):
            ui.label(str(entry['rank'])).classes('mono font-bold').style('width: 30px')
            if entry.get('image'):
                ui.image(entry['image']).style('width: 28px; height: 28px;').props('fit=contain')
            else:
                ui.icon('sports').classes('text-gray-600').style('width: 28px; font-size: 18px; text-align: center;')
            ui.label(entry['name']).classes(
                'font-bold flex-grow' + (' fav-team-name' if is_fav else ''))
            for _, key, width, color in cols:
                if key == '_wr':
                    total = entry['wins'] + entry['losses']
                    val = f"{entry['wins'] / total * 100:.0f}%" if total > 0 else '-'
                else:
                    val = str(entry.get(key, ''))
                ui.label(val).classes(f'mono text-center {color}'.strip()).style(f'width: {width}')

    _register(fav_state, render, container)


def _build_bracket_panel(fetch_fn, fav_state, empty_msg=None):
    """Tournament bracket — horizontal tree with rounds side by side."""
    container = ui.element('div').classes('w-full p-4').style('overflow-x: auto;')

    def render():
        container.clear()
        stages, tournament_name = fetch_fn()
        fav = fav_state['value']
        if not stages:
            with container:
                ui.label(empty_msg or 'No tournament data available').classes('text-gray-500 text-center py-8')
            return
        with container:
            if tournament_name:
                ui.label(tournament_name).classes('text-xl font-extrabold mb-4')
            # Horizontal bracket: each stage is a column
            with ui.row().classes('items-start gap-0').style('min-width: max-content;'):
                for i, stage in enumerate(stages):
                    all_matches = []
                    for sec in stage['sections']:
                        all_matches.extend(sec['matches'])
                    with ui.column().classes('bracket-round gap-0').style(
                        f'justify-content: space-around; min-height: {max(len(all_matches) * 80, 100)}px;'
                    ):
                        ui.label(stage['name']).classes('section-title text-center mb-2')
                        for match in all_matches:
                            _build_bracket_match(match, fav)
                    # Connector between rounds
                    if i < len(stages) - 1:
                        with ui.element('div').style(
                            f'width: 24px; align-self: center; '
                            f'border-top: 2px solid #2a2a3a;'
                        ):
                            pass

    _register(fav_state, render, container)


def _bracket_team_cls(is_fav, is_win, other_win):
    """CSS classes for a team in a bracket match."""
    cls = 'bracket-team'
    if is_fav:
        return cls + ' fav-team-name'
    if is_win:
        return cls + ' winner'
    if other_win:
        return cls + ' loser'
    return cls


def _build_bracket_match(match, fav=''):
    """Single bracket match card — compact vertical layout."""
    t1_win = match.get('team1_outcome') == 'win'
    t2_win = match.get('team2_outcome') == 'win'
    t1_fav = _is_fav(fav, match.get('team1_name', '')) or _is_fav(fav, match.get('team1_code', ''))
    t2_fav = _is_fav(fav, match.get('team2_name', '')) or _is_fav(fav, match.get('team2_code', ''))

    highlight = ' fav-highlight' if (t1_fav or t2_fav) else ''
    is_done = match.get('state') in ('completed', 'inProgress')

    with ui.element('div').classes(f'bracket-match{highlight}'):
        # Date line
        date = match.get('date', '')
        if date:
            ui.label(date + ' KST').classes('mono text-xs text-gray-500').style('margin-bottom: 2px;')
        elif match['state'] == 'unstarted':
            ui.label('TBD').classes('mono text-xs text-gray-600').style('margin-bottom: 2px;')
        # Team 1 row
        with ui.element('div').classes(_bracket_team_cls(t1_fav, t1_win, t2_win)):
            if match['team1_image']:
                ui.image(match['team1_image']).style('width: 20px; height: 20px;')
            ui.label(match['team1_code'] or match['team1_name']).classes('text-sm')
            if is_done:
                ui.label(str(match['team1_wins'])).classes('mono text-sm ml-auto font-bold')
        # Separator
        ui.element('div').style('border-top: 1px solid #2a2a3a; margin: 2px 0;')
        # Team 2 row
        with ui.element('div').classes(_bracket_team_cls(t2_fav, t2_win, t1_win)):
            if match['team2_image']:
                ui.image(match['team2_image']).style('width: 20px; height: 20px;')
            ui.label(match['team2_code'] or match['team2_name']).classes('text-sm')
            if is_done:
                ui.label(str(match['team2_wins'])).classes('mono text-sm ml-auto font-bold')


def _build_match_card(match, fav=''):
    """Single match card with favorite highlight."""
    league_cls = LEAGUE_BADGE_CLASS.get(match['league'], '')
    home_fav = _is_fav(fav, match['home'])
    away_fav = _is_fav(fav, match['away'])

    with ui.card().classes('w-full p-3' + (' fav-highlight' if (home_fav or away_fav) else '')):
        with ui.row().classes('w-full justify-between items-center'):
            with ui.row().classes('gap-2 items-center'):
                badge = match.get('league_short', '')
                ui.badge(badge).classes(f'{league_cls} text-xs')
                tournament = match.get('tournament', '')
                if tournament and tournament != badge:
                    ui.label(tournament).classes('mono text-xs text-gray-400')
            status = match.get('status', '')
            if status == 'LIVE':
                ui.label(f"🔴 LIVE {match.get('minute', '')}").classes('mono text-xs')
            elif status == 'SCHEDULED':
                ui.label(match.get('time', '')).classes('mono text-xs text-gray-500')
            elif status == 'PPD':
                ui.label('POSTPONED').classes('mono text-xs text-amber-400')
            elif status in ('SUSP', 'DELAY', 'CAN'):
                label_map = {'SUSP': 'SUSPENDED', 'DELAY': 'DELAYED', 'CAN': 'CANCELLED'}
                ui.label(label_map.get(status, status)).classes('mono text-xs text-amber-400')
            else:
                ui.label(status).classes('mono text-xs')

        with ui.element('div').classes('w-full py-2').style(
            'display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 8px;'
        ):
            _match_team_side(match, 'home', home_fav, align='start')

            if match.get('status') in ('LIVE', 'FT') and match.get('score_home') is not None:
                ui.label(f"{match['score_home']} : {match['score_away']}").classes('mono text-2xl font-extrabold text-center')
            else:
                ui.label('vs').classes('mono text-lg text-gray-600 text-center')

            _match_team_side(match, 'away', away_fav, align='end')

        if match.get('round'):
            ui.label(match['round']).classes('mono text-xs text-gray-600 text-center w-full')


def _team_logo(img):
    """Render a team logo, or a placeholder icon if missing."""
    if img:
        ui.image(img).classes('w-10 h-8').style('min-width: 40px;').props('fit=contain')
    else:
        ui.icon('sports').classes('text-gray-600').style('width: 40px; min-width: 40px; text-align: center; font-size: 20px;')


def _match_team_side(match, side, is_fav, align):
    """Render one side (home/away) of a match card."""
    name = match.get(side, 'TBD')
    img = match.get(f'{side}_image', '')
    rec = match.get(f'{side}_record', {})
    name_cls = 'font-bold' + (' fav-team-name' if is_fav else '')

    with ui.row().classes(f'items-center gap-2' + (f' justify-{align}' if align == 'end' else '')):
        if align == 'start':
            _team_logo(img)
        with ui.column().classes(f'items-{align} gap-0'):
            ui.label(name).classes(name_cls)
            if rec:
                ui.label(f"{rec.get('wins', 0)}W {rec.get('losses', 0)}L").classes('mono text-xs text-gray-500')
        if align == 'end':
            _team_logo(img)


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
            _build_projects_with_subs()

        with ui.tab_panel(sports_tab):
            build_sports_tab()


def _build_projects_with_subs():
    """Projects tab with sub-tabs: project list + Rich Man FX."""
    with ui.column().classes('w-full gap-0'):
        with ui.tabs().props(
            'dense active-color=amber indicator-color=amber no-caps'
        ).classes('w-full') as sub_tabs:
            list_tab = ui.tab('proj_list', label='🚀 Projects')
            richman_tab = ui.tab('richman', label='💰 Rich Man')

        with ui.tab_panels(sub_tabs, value=list_tab).classes('w-full'):
            with ui.tab_panel(list_tab):
                build_projects_tab()

            with ui.tab_panel(richman_tab):
                build_rich_man_tab()


# ═══════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════
ui.run(
    title='Personal Hub',
    port=8080,
    dark=True,
    storage_secret='personal-hub-secret-key-change-me',
)
