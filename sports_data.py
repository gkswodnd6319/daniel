"""
Sports data provider — demo data for now, swap with real APIs later.

APIs you can plug in:
  - Football: https://www.api-football.com  (free: 100 req/day)
  - LoL Esports: https://lolesports.com (unofficial community APIs)
  - MLB: https://statsapi.mlb.com (free, no key needed)
  - KBO: Manual / scraping (no official public API)
"""

import random
import httpx
import logging
from datetime import datetime, timedelta
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  Simple time-based cache for API calls
# ═══════════════════════════════════════════════════════════
_cache = {}
_CACHE_TTL = 300  # 5 minutes


def _cached(key, fetch_fn):
    """Return cached result if fresh, otherwise call fetch_fn and cache it."""
    now = datetime.now().timestamp()
    if key in _cache:
        data, ts = _cache[key]
        if now - ts < _CACHE_TTL:
            return data
    data = fetch_fn()
    _cache[key] = (data, now)
    return data


def _cache_fn(fn):
    """Decorator: cache function results by function name for _CACHE_TTL seconds."""
    def wrapper(*args, **kwargs):
        return _cached(fn.__name__, lambda: fn(*args, **kwargs))
    wrapper.__name__ = fn.__name__
    return wrapper


def warm_cache():
    """Pre-fetch all league data into cache. Call on app startup."""
    import threading

    def _warm():
        for league in _LEAGUE_FETCH:
            try:
                get_matches_by_league(league)
            except Exception:
                pass
        # Pre-warm standings and brackets
        for fn_name in [
            'fetch_pl_standings', 'fetch_ucl_standings', 'fetch_ucl_bracket',
            'fetch_lck_standings', 'fetch_lol_intl_bracket',
            'fetch_kbo_standings', 'fetch_mlb_standings',
            'fetch_wbc_standings', 'fetch_wbc_bracket',
        ]:
            try:
                globals()[fn_name]()
            except Exception:
                pass
        logger.info('Cache warmed for all leagues')

    threading.Thread(target=_warm, daemon=True).start()


# ═══════════════════════════════════════════════════════════
#  LOL ESPORTS API (free, public key)
# ═══════════════════════════════════════════════════════════
LOL_ESPORTS_BASE = 'https://esports-api.lolesports.com/persisted/gw'
LOL_ESPORTS_KEY = '0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z'
LOL_ESPORTS_HEADERS = {'x-api-key': LOL_ESPORTS_KEY}

LCK_LEAGUE_ID = '98767991310872058'

# ═══════════════════════════════════════════════════════════
#  KBO API (official koreabaseball.com)
# ═══════════════════════════════════════════════════════════
KBO_API_BASE = 'https://www.koreabaseball.com/ws/Main.asmx'

# ═══════════════════════════════════════════════════════════
#  MLB API (statsapi.mlb.com — free, no auth)
# ═══════════════════════════════════════════════════════════
MLB_API_BASE = 'https://statsapi.mlb.com/api/v1'

# ═══════════════════════════════════════════════════════════
#  Premier League API (premierleague.com Pulse — free, no auth)
# ═══════════════════════════════════════════════════════════
PL_API_BASE = 'https://footballapi.pulselive.com/football'
PL_HEADERS = {'Origin': 'https://www.premierleague.com'}
PL_COMP_SEASON = '777'  # 2025/26

_KBO_LOGO_BASE = 'https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/eng/resources/images/ebl/regular/2026'

# Map team name fragments (Korean short, English, full) -> logo code
_KBO_LOGO_CODES = {
    'LG': 'LG', 'KT': 'KT', 'SSG': 'SK', 'NC': 'NC', 'KIA': 'HT',
    '두산': 'OB', 'DOOSAN': 'OB',
    '롯데': 'LT', 'LOTTE': 'LT',
    '삼성': 'SS', 'SAMSUNG': 'SS',
    '한화': 'HH', 'HANWHA': 'HH',
    '키움': 'WO', 'KIWOOM': 'WO',
}
KBO_TEAM_LOGOS = {k: f'{_KBO_LOGO_BASE}/ebl_s_{v}.png' for k, v in _KBO_LOGO_CODES.items()}

# Map AWAY_ID/HOME_ID to display names
KBO_TEAM_ID_TO_NAME = {
    'LG': 'LG 트윈스', 'HT': 'KIA 타이거즈', 'SS': '삼성 라이온즈',
    'OB': '두산 베어스', 'LT': '롯데 자이언츠', 'SK': 'SSG 랜더스',
    'WO': '키움 히어로즈', 'NC': 'NC 다이노스', 'KT': 'KT 위즈',
    'HH': '한화 이글스',
}

LOL_INTL_LEAGUES = {
    'First Stand': '113464388705111224',
    'MSI': '98767991325878492',
    'Worlds': '98767975604431411',
}


# ═══════════════════════════════════════════════════════════
#  TEAM ROSTERS
# ═══════════════════════════════════════════════════════════

TEAMS = {
    'Premier League': [
        'Arsenal', 'Liverpool', 'Man City', 'Chelsea', 'Man United',
        'Tottenham', 'Newcastle', 'Aston Villa', 'Brighton', 'West Ham',
        'Bournemouth', 'Fulham', 'Crystal Palace', 'Wolves', 'Everton',
        'Brentford', "Nott'm Forest", 'Leicester', 'Ipswich', 'Southampton',
    ],
    'Champions League': [
        'Real Madrid', 'Barcelona', 'Bayern Munich', 'PSG', 'Inter Milan',
        'Dortmund', 'Atletico Madrid', 'Arsenal', 'Liverpool', 'Man City',
        'Juventus', 'AC Milan', 'Benfica', 'Porto', 'Napoli', 'Leverkusen',
    ],
    'LCK': [
        'T1', 'Gen.G', 'Hanwha Life', 'DRX', 'KT Rolster',
        'Dplus KIA', 'BNK FearX', 'OKSavingsBank', 'Kwangdong Freecs', 'Nongshim RedForce',
    ],
    'LoL International': [
        'T1', 'Gen.G', 'Hanwha Life', 'BLG', 'Top Esports',
        'Weibo Gaming', 'G2 Esports', 'Fnatic', 'Team Liquid', 'Cloud9',
        'PSG Talon', 'GAM Esports',
    ],
    'MLB': [
        'NY Yankees', 'LA Dodgers', 'Houston Astros', 'Atlanta Braves',
        'Philadelphia Phillies', 'San Diego Padres', 'Texas Rangers',
        'Baltimore Orioles', 'Minnesota Twins', 'Arizona D-backs',
        'Chicago Cubs', 'Boston Red Sox', 'Tampa Bay Rays', 'Seattle Mariners',
        'NY Mets', 'SF Giants',
    ],
    'KBO': [
        '삼성 라이온즈', 'LG 트윈스', 'KT 위즈', 'SSG 랜더스', '키움 히어로즈',
        '두산 베어스', 'NC 다이노스', '롯데 자이언츠', '한화 이글스', 'KIA 타이거즈',
    ],
}

LEAGUE_SHORT = {
    'Premier League': 'PL',
    'Champions League': 'UCL',
    'LCK': 'LCK',
    'LoL International': 'LOL INTL',
    'MLB': 'MLB',
    'KBO': 'KBO',
}

LEAGUE_FILTERS = {
    'all': {'label': 'All', 'color': '#00e676'},
    'Premier League': {'label': 'EPL', 'color': '#3d195b'},
    'Champions League': {'label': 'UCL', 'color': '#071d6b'},
    'LCK': {'label': 'LCK', 'color': '#c89b3c'},
    'LoL International': {'label': 'LOL INTL', 'color': '#1a78c2'},
    'MLB': {'label': 'MLB', 'color': '#002d72'},
    'KBO': {'label': 'KBO', 'color': '#c8102e'},
}


# ═══════════════════════════════════════════════════════════
#  DEMO DATA GENERATOR
# ═══════════════════════════════════════════════════════════

def _https(url):
    """Upgrade http:// URLs to https:// to avoid mixed content blocks."""
    if url and url.startswith('http://'):
        return 'https://' + url[7:]
    return url or ''


def _filter_by_date_window(matches, days_back=2, days_ahead=7):
    """Filter and sort matches to a date window around today."""
    now = datetime.now()
    cutoff_past = (now - timedelta(days=days_back)).strftime('%Y-%m-%d')
    cutoff_future = (now + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
    filtered = [m for m in matches if cutoff_past <= m.get('date', '')[:10] <= cutoff_future]
    filtered.sort(key=lambda m: m['date'])
    return filtered


def _pick_two(team_list):
    shuffled = random.sample(team_list, 2)
    return shuffled[0], shuffled[1]


def _generate_league_matches(league, count=12):
    """Generate realistic demo matches for a league."""
    now = datetime.now()
    start = now - timedelta(days=4)
    teams = TEAMS[league]
    matches = []
    
    is_baseball = league in ('MLB', 'KBO')
    is_esports = league in ('LCK', 'LoL International')
    
    for i in range(count):
        home, away = _pick_two(teams)
        match_dt = start + timedelta(
            days=i // 3,
            hours=random.choice([14, 16, 18, 19, 20, 21] if not is_baseball else [14, 18, 18, 19]),
            minutes=random.choice([0, 30]),
        )
        
        is_past = match_dt < now
        is_live = (
            not is_past 
            and abs((match_dt - now).total_seconds()) < 7200 
            and random.random() > 0.6
        )
        
        if is_past or is_live:
            if is_baseball:
                s1, s2 = random.randint(0, 12), random.randint(0, 12)
            else:
                s1, s2 = random.randint(0, 4), random.randint(0, 4)
        else:
            s1, s2 = None, None
        
        status = 'LIVE' if is_live else ('FT' if is_past else 'SCHEDULED')
        
        minute = None
        if is_live:
            if is_baseball:
                minute = f"{random.randint(1, 9)}회"
            elif is_esports:
                minute = f"Game {random.randint(1, 3)}"
            else:
                minute = f"{random.randint(1, 90)}'"
        
        round_label = ''
        if is_esports:
            round_label = f"Week {i // 5 + 1} · Bo3"
        elif is_baseball:
            round_label = f"Game {i + 1}"
        else:
            round_label = f"Matchday {i // 8 + 1}"
        
        matches.append({
            'id': f'{league}-{i}',
            'league': league,
            'league_short': LEAGUE_SHORT[league],
            'home': home,
            'away': away,
            'date': match_dt.strftime('%Y-%m-%d %H:%M'),
            'time': match_dt.strftime('%H:%M'),
            'status': status,
            'score_home': s1,
            'score_away': s2,
            'minute': minute,
            'round': round_label,
        })
    
    return matches


LEAGUE_MATCH_COUNTS = {
    'Premier League': 16,
    'Champions League': 10,
    'LCK': 14,
    'LoL International': 10,
    'MLB': 18,
    'KBO': 14,
}


def get_team_list(league):
    """Return team names from cached data where available, static list as fallback."""
    # Only use cached data — never trigger a fresh API call just for team names
    cache_key = f'matches_{league}'
    if cache_key in _cache:
        matches, _ = _cache[cache_key]
        if matches:
            names = {m['home'] for m in matches} | {m['away'] for m in matches}
            names.discard('TBD')
            if names:
                return sorted(names)
    return TEAMS.get(league, [])


_LEAGUE_FETCH = {
    'Premier League': 'fetch_pl_schedule',
    'Champions League': 'fetch_ucl_schedule',
    'World Cup': 'fetch_worldcup_schedule',
    'WBC': 'fetch_wbc_schedule',
    'LCK': 'fetch_lck_schedule',
    'LoL International': 'fetch_lol_intl_schedule',
    'KBO': 'fetch_kbo_schedule',
    'MLB': 'fetch_mlb_schedule',
}


def get_matches_by_league(league):
    """Get matches for a league. Cached for 60s to avoid redundant API calls."""
    fn_name = _LEAGUE_FETCH.get(league)
    if fn_name:
        def _fetch():
            fn = globals()[fn_name]
            result = fn()
            return result if result else None
        matches = _cached(f'matches_{league}', _fetch)
        if matches:
            return matches

    # Only fall back to demo data for leagues that have teams defined
    if league in TEAMS:
        count = LEAGUE_MATCH_COUNTS.get(league, 10)
        matches = _generate_league_matches(league, count)
        matches.sort(key=lambda m: m['date'])
        return matches

    return []


def get_all_matches():
    """Get all demo matches across all leagues."""
    all_matches = []
    for league, count in LEAGUE_MATCH_COUNTS.items():
        all_matches.extend(_generate_league_matches(league, count))

    all_matches.sort(key=lambda m: m['date'])
    return all_matches


# ═══════════════════════════════════════════════════════════
#  LIVE API: LCK (LoL Esports)
# ═══════════════════════════════════════════════════════════

def _fetch_lck_tournaments():
    """Fetch LCK tournament list and return as date-range lookup.
    Returns list of (start_date, end_date, display_name) sorted by start_date desc.
    """
    try:
        resp = httpx.get(
            f'{LOL_ESPORTS_BASE}/getTournamentsForLeague',
            headers=LOL_ESPORTS_HEADERS,
            params={'hl': 'en-US', 'leagueId': LCK_LEAGUE_ID},
            timeout=10,
        )
        resp.raise_for_status()
        tournaments = resp.json()['data']['leagues'][0]['tournaments']
        result = []
        for t in tournaments:
            slug = t.get('slug', '')
            start = t.get('startDate', '')
            end = t.get('endDate', '')
            # Pretty name from slug: "lck_split_2_2026" -> "LCK Split 2 2026"
            name = slug.replace('_', ' ').upper()
            for keyword, label in [
                ('SPLIT 1', 'LCK Spring'),
                ('SPLIT 2', 'LCK Summer'),
                ('SPLIT 3', 'LCK Fall'),
                ('CUP', 'LCK Cup'),
                ('REGIONAL', 'LCK Regional Qualifier'),
                ('SPRING', 'LCK Spring'),
                ('SUMMER', 'LCK Summer'),
            ]:
                if keyword in name:
                    year = slug.split('_')[-1] if slug[-4:].isdigit() else ''
                    name = f"{label} {year}".strip()
                    break
            result.append((start, end, name))
        return result
    except Exception as e:
        logger.error(f'Failed to fetch LCK tournaments: {e}')
        return []


def _resolve_tournament(date_str, tournaments):
    """Find which tournament a match date falls into."""
    d = date_str[:10]  # 'YYYY-MM-DD'
    for start, end, name in tournaments:
        if start <= d <= end:
            return name
    return ''


def _get_current_lck_tournament():
    """Return (tournament_id, display_name) for the current/most recent LCK tournament."""
    try:
        resp = httpx.get(
            f'{LOL_ESPORTS_BASE}/getTournamentsForLeague',
            headers=LOL_ESPORTS_HEADERS,
            params={'hl': 'en-US', 'leagueId': LCK_LEAGUE_ID},
            timeout=10,
        )
        resp.raise_for_status()
        tournaments = resp.json()['data']['leagues'][0]['tournaments']
        today = datetime.now().strftime('%Y-%m-%d')
        # Find the tournament whose date range covers today, or the most recent one
        for t in tournaments:
            if t['startDate'] <= today <= t['endDate']:
                return t['id'], t['slug']
        # Fallback: most recent past tournament
        for t in tournaments:
            if t['endDate'] < today:
                return t['id'], t['slug']
        return tournaments[0]['id'], tournaments[0]['slug']
    except Exception as e:
        logger.error(f'Failed to get current LCK tournament: {e}')
        return None, ''


@_cache_fn
def fetch_lck_standings():
    """Fetch current LCK standings.
    Returns list of dicts: [{rank, name, code, image, wins, losses}, ...] sorted by rank.
    """
    try:
        tid, slug = _get_current_lck_tournament()
        if not tid:
            return []

        # Resolve slug to display name
        tournaments = _fetch_lck_tournaments()
        title = ''
        for start, end, name in tournaments:
            if name and slug and slug.replace('_', ' ').lower() in name.lower().replace(' ', ' '):
                title = name
                break
        if not title:
            title = _resolve_tournament(datetime.now().strftime('%Y-%m-%d'), tournaments)

        resp = httpx.get(
            f'{LOL_ESPORTS_BASE}/getStandings',
            headers=LOL_ESPORTS_HEADERS,
            params={'hl': 'en-US', 'tournamentId': tid},
            timeout=10,
        )
        resp.raise_for_status()
        stages = resp.json()['data']['standings'][0]['stages']
        if not stages:
            return []

        section = stages[0]['sections'][0]
        rankings = section.get('rankings', [])
        result = []
        for r in rankings:
            for team in r.get('teams', []):
                rec = team.get('record', {})
                result.append({
                    'rank': r['ordinal'],
                    'name': team.get('name', ''),
                    'code': team.get('code', ''),
                    'image': _https(team.get('image', '')),
                    'wins': rec.get('wins', 0),
                    'losses': rec.get('losses', 0),
                    '_title': title,
                })
        return result
    except Exception as e:
        logger.error(f'Failed to fetch LCK standings: {e}')
        return []


def fetch_lck_schedule():
    """Fetch real LCK schedule from the LoL Esports API.
    Only returns matches from 7 days ago onwards.
    Returns list of match dicts in our standard format, or [] on failure.
    """
    try:
        tournaments = _fetch_lck_tournaments()

        resp = httpx.get(
            f'{LOL_ESPORTS_BASE}/getSchedule',
            headers=LOL_ESPORTS_HEADERS,
            params={'hl': 'en-US', 'leagueId': LCK_LEAGUE_ID},
            timeout=10,
        )
        resp.raise_for_status()
        events = resp.json()['data']['schedule']['events']

        cutoff = datetime.now() - timedelta(days=2)
        matches = []
        for e in events:
            if e.get('type') != 'match':
                continue
            parsed = _parse_lol_event(e, tournaments)
            # Filter: only from 7 days ago onwards
            try:
                match_dt = datetime.strptime(parsed['date'], '%Y-%m-%d %H:%M')
                if match_dt < cutoff:
                    continue
            except ValueError:
                pass
            matches.append(parsed)
        return matches
    except Exception as e:
        logger.error(f'Failed to fetch LCK schedule: {e}')
        return []


def _parse_lol_event(event, tournaments=None, league_name='LCK', league_short='LCK'):
    """Convert a LoL Esports API event into our standard match dict."""
    match = event.get('match', {})
    teams = match.get('teams', [{}, {}])
    team_a = teams[0] if len(teams) > 0 else {}
    team_b = teams[1] if len(teams) > 1 else {}

    # Parse time
    start_str = event.get('startTime', '')
    try:
        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        # Convert UTC to KST (UTC+9) for display
        start_local = start_dt + timedelta(hours=9)
        date_str = start_local.strftime('%Y-%m-%d %H:%M')
        time_str = start_local.strftime('%H:%M')
    except (ValueError, AttributeError):
        date_str = start_str[:16] if start_str else ''
        time_str = ''

    # Resolve tournament category
    tournament = ''
    if tournaments:
        tournament = _resolve_tournament(date_str, tournaments)

    # Map API state to our status
    state = event.get('state', '')
    status_map = {
        'completed': 'FT',
        'inProgress': 'LIVE',
        'unstarted': 'SCHEDULED',
    }
    status = status_map.get(state, 'SCHEDULED')

    # Scores (game wins in a Bo3/Bo5)
    score_a = team_a.get('result', {}).get('gameWins')
    score_b = team_b.get('result', {}).get('gameWins')

    # Strategy info
    strategy = match.get('strategy', {})
    bo_count = strategy.get('count', 3)
    block_name = event.get('blockName', '')
    # For international matches, show tournament in round; for LCK show week
    if league_name == 'LoL International' and tournament:
        round_label = f"{block_name} · Bo{bo_count}" if block_name else f"Bo{bo_count}"
    else:
        round_label = f"{block_name} · Bo{bo_count}" if block_name else f"Bo{bo_count}"

    # Live indicator
    minute = None
    if status == 'LIVE':
        minute = f"Game {(score_a or 0) + (score_b or 0) + 1}"

    return {
        'id': match.get('id', ''),
        'league': league_name,
        'league_short': league_short,
        'tournament': tournament,
        'home': team_a.get('name', 'TBD'),
        'away': team_b.get('name', 'TBD'),
        'home_code': team_a.get('code', ''),
        'away_code': team_b.get('code', ''),
        'home_image': _https(team_a.get('image', '')),
        'away_image': _https(team_b.get('image', '')),
        'home_record': team_a.get('record', {}),
        'away_record': team_b.get('record', {}),
        'date': date_str,
        'time': time_str,
        'status': status,
        'score_home': score_a,
        'score_away': score_b,
        'minute': minute,
        'round': round_label,
    }


# ═══════════════════════════════════════════════════════════
#  LIVE API: LoL International (First Stand, MSI, Worlds)
# ═══════════════════════════════════════════════════════════

def _fetch_tournaments_for_league(league_id):
    """Fetch tournament list for a given league ID.
    Returns list of dicts with id, slug, name, startDate, endDate.
    """
    try:
        resp = httpx.get(
            f'{LOL_ESPORTS_BASE}/getTournamentsForLeague',
            headers=LOL_ESPORTS_HEADERS,
            params={'hl': 'en-US', 'leagueId': league_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()['data']['leagues'][0]['tournaments']
    except Exception as e:
        logger.error(f'Failed to fetch tournaments for {league_id}: {e}')
        return []


def _pretty_intl_name(slug):
    """Convert slug to display name: 'msi_2026' -> 'MSI 2026'."""
    parts = slug.replace('_', ' ').split()
    name_parts = []
    for p in parts:
        if p.isdigit():
            name_parts.append(p)
        else:
            name_parts.append(p.upper() if len(p) <= 4 else p.title())
    return ' '.join(name_parts)


def fetch_lol_intl_schedule():
    """Fetch schedule across all LoL international leagues.
    Returns matches from 7 days ago to 30 days ahead.
    Returns [] if no matches in that window (with a flag), or None on API failure.
    """
    now = datetime.now()
    cutoff_past = now - timedelta(days=7)
    cutoff_future = now + timedelta(days=30)

    all_matches = []
    for league_name, league_id in LOL_INTL_LEAGUES.items():
        try:
            # Build tournament date lookup
            raw_tournaments = _fetch_tournaments_for_league(league_id)
            tournaments = []
            for t in raw_tournaments:
                pretty = _pretty_intl_name(t['slug'])
                tournaments.append((t['startDate'], t['endDate'], pretty))

            resp = httpx.get(
                f'{LOL_ESPORTS_BASE}/getSchedule',
                headers=LOL_ESPORTS_HEADERS,
                params={'hl': 'en-US', 'leagueId': league_id},
                timeout=10,
            )
            resp.raise_for_status()
            events = resp.json()['data']['schedule']['events']

            for e in events:
                if e.get('type') != 'match':
                    continue
                parsed = _parse_lol_event(
                    e, tournaments,
                    league_name='LoL International',
                    league_short=league_name,
                )
                try:
                    match_dt = datetime.strptime(parsed['date'], '%Y-%m-%d %H:%M')
                    if match_dt < cutoff_past or match_dt > cutoff_future:
                        continue
                except ValueError:
                    continue
                all_matches.append(parsed)
        except Exception as e:
            logger.error(f'Failed to fetch {league_name} schedule: {e}')

    all_matches.sort(key=lambda m: m['date'])
    return all_matches


def _get_current_intl_tournament():
    """Find the current or most recent international tournament.
    Returns (tournament_id, display_name, league_name) or (None, '', '').
    """
    today = datetime.now().strftime('%Y-%m-%d')
    near_future = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    best = None
    for league_name, league_id in LOL_INTL_LEAGUES.items():
        raw = _fetch_tournaments_for_league(league_id)
        for t in raw:
            # Currently running
            if t['startDate'] <= today <= t['endDate']:
                return t['id'], _pretty_intl_name(t['slug']), league_name
            # Upcoming within 30 days
            if today < t['startDate'] <= near_future:
                if best is None or t['startDate'] < best[1]:
                    best = (t['id'], t['startDate'], _pretty_intl_name(t['slug']), league_name)
            # Most recently finished
            if t['endDate'] < today:
                if best is None:
                    best = (t['id'], t['endDate'], _pretty_intl_name(t['slug']), league_name)

    if best:
        return best[0], best[2], best[3]
    return None, '', ''


@_cache_fn
def fetch_lol_intl_bracket():
    """Fetch bracket/stage data for the current international tournament.
    Returns list of stages: [{name, sections: [{name, matches: [{state, team1, team2, ...}]}]}]
    """
    try:
        tid, display_name, league_name = _get_current_intl_tournament()
        if not tid:
            return [], ''

        resp = httpx.get(
            f'{LOL_ESPORTS_BASE}/getStandings',
            headers=LOL_ESPORTS_HEADERS,
            params={'hl': 'en-US', 'tournamentId': tid},
            timeout=10,
        )
        resp.raise_for_status()
        raw_stages = resp.json()['data']['standings'][0]['stages']

        stages = []
        for stage in raw_stages:
            sections = []
            for sec in stage.get('sections', []):
                matches = []
                for m in sec.get('matches', []):
                    teams = m.get('teams', [])
                    t1 = teams[0] if teams else {}
                    t2 = teams[1] if len(teams) > 1 else {}
                    r1 = t1.get('result', {})
                    r2 = t2.get('result', {})
                    matches.append({
                        'state': m.get('state', ''),
                        'team1_name': t1.get('name', 'TBD'),
                        'team1_code': t1.get('code', ''),
                        'team1_image': _https(t1.get('image', '')),
                        'team1_wins': r1.get('gameWins', 0),
                        'team1_outcome': r1.get('outcome', ''),
                        'team2_name': t2.get('name', 'TBD'),
                        'team2_code': t2.get('code', ''),
                        'team2_image': _https(t2.get('image', '')),
                        'team2_wins': r2.get('gameWins', 0),
                        'team2_outcome': r2.get('outcome', ''),
                        'date': '',
                    })
                sections.append({
                    'name': sec.get('name', ''),
                    'matches': matches,
                })
            stages.append({
                'name': stage.get('name', ''),
                'sections': sections,
            })
        return stages, display_name
    except Exception as e:
        logger.error(f'Failed to fetch LoL international bracket: {e}')
        return [], ''


# ═══════════════════════════════════════════════════════════
#  LIVE API: KBO (koreabaseball.com)
# ═══════════════════════════════════════════════════════════

def _get_kbo_logo(team_name):
    """Get logo URL for a KBO team by display name."""
    for key, url in KBO_TEAM_LOGOS.items():
        if key in team_name:
            return url
    return ''


def fetch_kbo_schedule():
    """Fetch KBO schedule: -2 days to +7 days.
    Returns list of match dicts in our standard format, or [] on failure.
    """
    now = datetime.now()
    matches = []
    try:
        for day_offset in range(-2, 8):
            dt = now + timedelta(days=day_offset)
            date_str = dt.strftime('%Y%m%d')
            resp = httpx.post(
                f'{KBO_API_BASE}/GetKboGameList',
                data={'leId': '1', 'srId': '0', 'date': date_str},
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            games = resp.json().get('game', [])
            for g in games:
                matches.append(_parse_kbo_game(g))
        matches.sort(key=lambda m: m['date'])
        return matches
    except Exception as e:
        logger.error(f'Failed to fetch KBO schedule: {e}')
        return []


def _parse_kbo_game(game):
    """Convert a KBO API game object into our standard match dict."""
    state = game.get('GAME_STATE_SC', '1')
    is_final = game.get('GAME_RESULT_CK') == 1
    if is_final:
        status = 'FT'
    elif state == '2':
        status = 'LIVE'
    else:
        status = 'SCHEDULED'

    cancel = game.get('CANCEL_SC_ID', '0')
    if cancel != '0':
        status = 'CANCELLED'

    away_name = game.get('AWAY_NM', '')
    home_name = game.get('HOME_NM', '')
    game_date = game.get('G_DT', '')
    game_time = game.get('G_TM', '')

    date_formatted = f"{game_date[:4]}-{game_date[4:6]}-{game_date[6:8]} {game_time}" if len(game_date) == 8 else game_date

    score_away = game.get('T_SCORE_CN', '0')
    score_home = game.get('B_SCORE_CN', '0')

    minute = None
    if status == 'LIVE':
        inn = game.get('GAME_INN_NO', '')
        tb = game.get('GAME_TB_SC_NM', '')
        minute = f"{inn}회 {tb}" if inn else ''

    stadium = game.get('S_NM', '')
    series_game = game.get('VS_GAME_CN', '')
    round_label = f"{stadium} · Game {series_game}/3" if series_game else stadium

    return {
        'id': game.get('G_ID', ''),
        'league': 'KBO',
        'league_short': 'KBO',
        'tournament': f"KBO {game.get('SEASON_ID', '')}",
        'home': home_name,
        'away': away_name,
        'home_code': game.get('HOME_ID', ''),
        'away_code': game.get('AWAY_ID', ''),
        'home_image': _get_kbo_logo(home_name),
        'away_image': _get_kbo_logo(away_name),
        'home_record': {},
        'away_record': {},
        'date': date_formatted,
        'time': game_time,
        'status': status,
        'score_home': int(score_home) if status in ('FT', 'LIVE') else None,
        'score_away': int(score_away) if status in ('FT', 'LIVE') else None,
        'minute': minute,
        'round': round_label,
    }


@_cache_fn
def fetch_kbo_standings():
    """Fetch current KBO standings by scraping eng.koreabaseball.com.
    Returns list of dicts sorted by rank.
    """
    import re
    try:
        resp = httpx.get(
            'https://eng.koreabaseball.com/Standings/TeamStandings.aspx',
            timeout=10,
        )
        resp.raise_for_status()
        html = resp.text

        # First table contains the standings
        table_match = re.search(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
        if not table_match:
            return []

        # Parse rows (skip header row)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_match.group(1), re.DOTALL)
        standings = []
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) < 8:
                continue
            clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            # Columns: RK, TEAM, GAMES, W, L, D, PCT, GB, STREAK, HOME, AWAY
            name = clean[1]
            standings.append({
                'rank': int(clean[0]) if clean[0].isdigit() else len(standings) + 1,
                'name': name,
                'code': name,
                'image': _get_kbo_logo(name),
                'wins': int(clean[3]) if clean[3].isdigit() else 0,
                'losses': int(clean[4]) if clean[4].isdigit() else 0,
                'draws': int(clean[5]) if clean[5].isdigit() else 0,
                'games': int(clean[2]) if clean[2].isdigit() else 0,
                'win_rate': clean[6],
                'gb': clean[7],
            })
        return standings
    except Exception as e:
        logger.error(f'Failed to fetch KBO standings: {e}')
        return []


# KBO postseason round mapping: srId -> (round name, series length)
_KBO_POSTSEASON_ROUNDS = [
    ('4', 'Wild Card', 2),
    ('3', 'Semi-Playoff', 5),
    ('5', 'Playoff', 5),
    ('7', 'Korean Series', 7),
]


def fetch_kbo_postseason():
    """Fetch KBO postseason bracket for the current year.
    Returns (stages, title) in the same format as fetch_lol_intl_bracket.
    """
    year = datetime.now().year
    # Postseason is Oct-Nov — skip expensive scan if before September
    if datetime.now().month < 9:
        return [], ''

    def _fetch():
        return _fetch_kbo_postseason_inner(year)
    return _cached('kbo_postseason', _fetch)


def _fetch_kbo_postseason_inner(year):
    stages = []
    try:
        for sr_id, round_name, best_of in _KBO_POSTSEASON_ROUNDS:
            matches = _fetch_kbo_postseason_round(sr_id, year)
            if not matches:
                continue

            # Group into series by matchup
            series = {}
            for g in matches:
                key = tuple(sorted([g['AWAY_NM'], g['HOME_NM']]))
                series.setdefault(key, []).append(g)

            section_matches = []
            for (t1, t2), games in series.items():
                t1_wins = sum(1 for g in games if g.get('GAME_RESULT_CK') == 1 and (
                    (g['HOME_NM'] == t1 and int(g['B_SCORE_CN']) > int(g['T_SCORE_CN'])) or
                    (g['AWAY_NM'] == t1 and int(g['T_SCORE_CN']) > int(g['B_SCORE_CN']))
                ))
                t2_wins = sum(1 for g in games if g.get('GAME_RESULT_CK') == 1 and (
                    (g['HOME_NM'] == t2 and int(g['B_SCORE_CN']) > int(g['T_SCORE_CN'])) or
                    (g['AWAY_NM'] == t2 and int(g['T_SCORE_CN']) > int(g['B_SCORE_CN']))
                ))
                all_done = all(g.get('GAME_RESULT_CK') == 1 for g in games)
                t1_outcome = 'win' if t1_wins > t2_wins and all_done else ''
                t2_outcome = 'win' if t2_wins > t1_wins and all_done else ''

                # Extract dates from games
                gdates = []
                for g in games:
                    gd = g.get('G_DT', '')
                    gt = g.get('G_TM', '')
                    if len(gd) == 8:
                        gdates.append(f"{gd[4:6]}/{gd[6:8]} {gt}")
                date_str = gdates[0] + (' ~ ' + gdates[-1] if len(gdates) > 1 else '') if gdates else ''

                section_matches.append({
                    'state': 'completed' if all_done else 'inProgress',
                    'team1_name': t1, 'team1_code': t1,
                    'team1_image': _get_kbo_logo(t1),
                    'team1_wins': t1_wins,
                    'team1_outcome': t1_outcome,
                    'team2_name': t2, 'team2_code': t2,
                    'team2_image': _get_kbo_logo(t2),
                    'team2_wins': t2_wins,
                    'team2_outcome': t2_outcome,
                    'date': date_str,
                })

            stages.append({
                'name': f"{round_name} (Best of {best_of})",
                'sections': [{'name': round_name, 'matches': section_matches}],
            })

        title = f"KBO {year} Post-Season" if stages else ''
        return stages, title
    except Exception as e:
        logger.error(f'Failed to fetch KBO postseason: {e}')
        return [], ''


def _fetch_kbo_postseason_round(sr_id, year):
    """Fetch all games for a specific postseason round by scanning Oct-Nov."""
    all_games = []
    start = datetime(year, 10, 1)
    for day_offset in range(60):
        dt = start + timedelta(days=day_offset)
        resp = httpx.post(
            f'{KBO_API_BASE}/GetKboGameList',
            data={'leId': '1', 'srId': sr_id, 'date': dt.strftime('%Y%m%d')},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10,
        )
        if resp.status_code != 200:
            continue
        games = resp.json().get('game', [])
        all_games.extend(games)
    return all_games


# ═══════════════════════════════════════════════════════════
#  LIVE API: Champions League (premierleague.com Pulse, comp=2)
# ═══════════════════════════════════════════════════════════

# UCL knockout gameweek ranges
_UCL_KO_ROUNDS = [
    (9, 10, 'Playoff Round'),
    (11, 12, 'Round of 16'),
    (13, 14, 'Quarter-Finals'),
    (15, 16, 'Semi-Finals'),
    (17, 17, 'Final'),
]


def _get_ucl_season_id():
    try:
        data = _pl_api('competitions/2/compseasons', {'page': 0, 'pageSize': 1})
        return str(int(data['content'][0]['id']))
    except Exception:
        return '813'


def fetch_ucl_schedule():
    """Fetch UCL schedule: -7 days to +14 days (football is weekly)."""
    try:
        season = _get_ucl_season_id()
        completed = _pl_api('fixtures', {
            'comps': '2', 'compSeasons': season, 'altIds': 'true',
            'page': 0, 'pageSize': 10, 'sort': 'desc', 'statuses': 'C',
        }).get('content', [])
        upcoming = _pl_api('fixtures', {
            'comps': '2', 'compSeasons': season, 'altIds': 'true',
            'page': 0, 'pageSize': 15, 'sort': 'asc', 'statuses': 'U,L',
        }).get('content', [])
        matches = [_parse_pl_fixture(f, league='Champions League', league_short='UCL') for f in completed + upcoming]
        matches = _filter_by_date_window(matches, days_back=7, days_ahead=14)
        return matches
    except Exception as e:
        logger.error(f'Failed to fetch UCL schedule: {e}')
        return []


@_cache_fn
def fetch_ucl_standings():
    """Fetch UCL league phase standings."""
    try:
        season = _get_ucl_season_id()
        data = _pl_api('standings', {'compSeasons': season, 'altIds': 'true'})
        tables = data.get('tables', [])
        if not tables:
            return []
        standings = []
        for entry in tables[0].get('entries', []):
            t = entry.get('team', {})
            o = entry.get('overall', {})
            standings.append({
                'rank': entry.get('position', 0),
                'name': t.get('shortName', ''),
                'code': t.get('club', {}).get('abbr', ''),
                'image': _pl_logo(t.get('altIds', {}).get('opta', '')),
                'games': o.get('played', 0),
                'wins': o.get('won', 0),
                'draws': o.get('drawn', 0),
                'losses': o.get('lost', 0),
                'gd': o.get('goalsDifference', 0),
                'points': o.get('points', 0),
            })
        return standings
    except Exception as e:
        logger.error(f'Failed to fetch UCL standings: {e}')
        return []


@_cache_fn
def fetch_ucl_bracket():
    """Fetch UCL knockout bracket as stages for bracket visual."""
    try:
        season = _get_ucl_season_id()
        resp = _pl_api('fixtures', {
            'comps': '2', 'compSeasons': season, 'altIds': 'true',
            'page': 0, 'pageSize': 200, 'sort': 'asc', 'statuses': 'C,U,L',
        })
        fixtures = resp.get('content', [])
        ko_fixtures = [f for f in fixtures
                       if f.get('gameweek', {}).get('competitionPhase', {}).get('type') == 'K']

        stages = []
        for gw_start, gw_end, round_name in _UCL_KO_ROUNDS:
            round_fixes = [f for f in ko_fixtures
                           if gw_start <= int(f.get('gameweek', {}).get('gameweek', 0)) <= gw_end]
            if not round_fixes:
                continue

            # Group into ties (same two teams)
            ties = {}
            for f in round_fixes:
                t = f['teams']
                names = tuple(sorted([t[0]['team']['shortName'], t[1]['team']['shortName']]))
                ties.setdefault(names, []).append(f)

            section_matches = []
            for (t1_name, t2_name), legs in ties.items():
                t1_agg, t2_agg = 0, 0
                all_done = True
                t1_opta = t2_opta = ''
                leg_dates = []
                for leg in legs:
                    t = leg['teams']
                    home_name = t[0]['team']['shortName']
                    # Collect dates
                    millis = leg.get('kickoff', {}).get('millis')
                    if millis:
                        kst = datetime(1970, 1, 1) + timedelta(milliseconds=millis) + timedelta(hours=9)
                        leg_dates.append(kst.strftime('%m/%d %H:%M'))
                    if leg['status'] != 'C':
                        all_done = False
                        continue
                    s0, s1 = int(t[0].get('score', 0)), int(t[1].get('score', 0))
                    if home_name == t1_name:
                        t1_agg += s0; t2_agg += s1
                    else:
                        t1_agg += s1; t2_agg += s0
                    if t[0]['team']['shortName'] == t1_name:
                        t1_opta = t[0]['team'].get('altIds', {}).get('opta', '')
                        t2_opta = t[1]['team'].get('altIds', {}).get('opta', '')
                    else:
                        t1_opta = t[1]['team'].get('altIds', {}).get('opta', '')
                        t2_opta = t[0]['team'].get('altIds', {}).get('opta', '')

                section_matches.append({
                    'state': 'completed' if all_done else ('inProgress' if any(l['status'] == 'L' for l in legs) else 'unstarted'),
                    'team1_name': t1_name, 'team1_code': t1_name,
                    'team1_image': _pl_logo(t1_opta),
                    'team1_wins': t1_agg,
                    'team1_outcome': 'win' if all_done and t1_agg > t2_agg else '',
                    'team2_name': t2_name, 'team2_code': t2_name,
                    'team2_image': _pl_logo(t2_opta),
                    'team2_wins': t2_agg,
                    'team2_outcome': 'win' if all_done and t2_agg > t1_agg else '',
                    'date': ' / '.join(leg_dates) if leg_dates else '',
                })

            stages.append({
                'name': round_name,
                'sections': [{'name': round_name, 'matches': section_matches}],
            })

        return stages, 'UEFA Champions League 2025/26' if stages else ''
    except Exception as e:
        logger.error(f'Failed to fetch UCL bracket: {e}')
        return [], ''


# ═══════════════════════════════════════════════════════════
#  LIVE API: FIFA World Cup (worldcupjson.net — updates for each tournament)
# ═══════════════════════════════════════════════════════════

WORLDCUP_API = 'https://worldcupjson.net'


def fetch_worldcup_schedule():
    """Fetch World Cup match schedule. Returns [] if no current tournament."""
    try:
        resp = httpx.get(f'{WORLDCUP_API}/matches/current', timeout=10)
        if resp.status_code != 200:
            return []
        matches = resp.json()
        if not matches:
            # Check if all-matches data is from the current year
            resp = httpx.get(f'{WORLDCUP_API}/matches', timeout=10)
            raw = resp.json() if resp.status_code == 200 else []
            year = datetime.now().year
            matches = [m for m in raw if str(year) in m.get('datetime', '')]
        if not matches:
            return []
        return [_parse_worldcup_match(m) for m in matches]
    except Exception as e:
        logger.error(f'Failed to fetch World Cup schedule: {e}')
        return []


def _parse_worldcup_match(m):
    """Convert worldcupjson match to standard format."""
    home = m.get('home_team', {})
    away = m.get('away_team', {})
    status_map = {'completed': 'FT', 'in_progress': 'LIVE', 'future_scheduled': 'SCHEDULED'}
    status = status_map.get(m.get('status', ''), 'SCHEDULED')

    dt_str = m.get('datetime', '')
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        kst = dt + timedelta(hours=9)
        date_str = kst.strftime('%Y-%m-%d %H:%M')
        time_str = kst.strftime('%H:%M')
    except (ValueError, AttributeError):
        date_str = dt_str[:16]
        time_str = ''

    return {
        'id': str(m.get('id', '')),
        'league': 'World Cup',
        'league_short': 'WC',
        'tournament': m.get('stage_name', 'World Cup'),
        'home': home.get('name', 'TBD'),
        'away': away.get('name', 'TBD'),
        'home_code': home.get('country', ''),
        'away_code': away.get('country', ''),
        'home_image': '',
        'away_image': '',
        'home_record': {},
        'away_record': {},
        'date': date_str,
        'time': time_str,
        'status': status,
        'score_home': home.get('goals') if status in ('FT', 'LIVE') else None,
        'score_away': away.get('goals') if status in ('FT', 'LIVE') else None,
        'minute': '' if status != 'LIVE' else 'LIVE',
        'round': m.get('venue', ''),
    }


@_cache_fn
def fetch_worldcup_bracket():
    """Fetch World Cup knockout bracket. Returns (stages, title)."""
    try:
        resp = httpx.get(f'{WORLDCUP_API}/matches', timeout=10)
        if resp.status_code != 200 or not resp.json():
            return [], ''
        year = datetime.now().year
        matches = [m for m in resp.json() if str(year) in m.get('datetime', '')]
        if not matches:
            return [], ''
        ko_matches = [m for m in matches if m.get('stage_name', '').lower() not in ('first stage', 'group stage', '')]
        if not ko_matches:
            return [], ''

        # Group by stage
        stage_map = {}
        for m in ko_matches:
            stage = m.get('stage_name', 'Knockout')
            stage_map.setdefault(stage, []).append(m)

        stages = []
        for stage_name, games in stage_map.items():
            section_matches = []
            for g in games:
                home = g.get('home_team', {})
                away = g.get('away_team', {})
                is_done = g.get('status') == 'completed'
                h_goals = home.get('goals', 0) or 0
                a_goals = away.get('goals', 0) or 0
                section_matches.append({
                    'state': 'completed' if is_done else 'unstarted',
                    'team1_name': home.get('name', 'TBD'), 'team1_code': home.get('country', ''),
                    'team1_image': '', 'team1_wins': h_goals,
                    'team1_outcome': 'win' if is_done and (h_goals > a_goals or (h_goals == a_goals and home.get('penalties', 0) > away.get('penalties', 0))) else '',
                    'team2_name': away.get('name', 'TBD'), 'team2_code': away.get('country', ''),
                    'team2_image': '', 'team2_wins': a_goals,
                    'team2_outcome': 'win' if is_done and (a_goals > h_goals or (a_goals == h_goals and away.get('penalties', 0) > home.get('penalties', 0))) else '',
                    'date': _parse_worldcup_match(g)['date'][:11] if g.get('datetime') else '',
                })
            stages.append({
                'name': stage_name,
                'sections': [{'name': stage_name, 'matches': section_matches}],
            })

        return stages, 'FIFA World Cup 2026'
    except Exception as e:
        logger.error(f'Failed to fetch World Cup bracket: {e}')
        return [], ''


# ═══════════════════════════════════════════════════════════
#  LIVE API: WBC (statsapi.mlb.com, sportId=51)
# ═══════════════════════════════════════════════════════════

def _parse_wbc_game(game):
    """Convert MLB API game to standard match dict for WBC."""
    away = game['teams']['away']
    home = game['teams']['home']
    away_team = away.get('team', {})
    home_team = home.get('team', {})

    status_map = {'Final': 'FT', 'Game Over': 'FT', 'Completed Early': 'FT', 'In Progress': 'LIVE'}
    detailed = game.get('status', {}).get('detailedState', '')
    status = status_map.get(detailed, 'SCHEDULED')

    gd = game.get('gameDate', '')
    try:
        dt = datetime.fromisoformat(gd.replace('Z', '+00:00')) + timedelta(hours=9)
        date_str = dt.strftime('%Y-%m-%d %H:%M')
        time_str = dt.strftime('%H:%M')
    except (ValueError, AttributeError):
        date_str = gd[:16]
        time_str = ''

    sd = game.get('seriesDescription', '')
    round_label = sd.replace('World Baseball Classic ', '') if sd else ''

    return {
        'id': str(game.get('gamePk', '')),
        'league': 'WBC',
        'league_short': 'WBC',
        'tournament': round_label,
        'home': home_team.get('name', 'TBD'),
        'away': away_team.get('name', 'TBD'),
        'home_code': home_team.get('abbreviation', ''),
        'away_code': away_team.get('abbreviation', ''),
        'home_image': _mlb_logo(home_team.get('id', '')),
        'away_image': _mlb_logo(away_team.get('id', '')),
        'home_record': {},
        'away_record': {},
        'date': date_str,
        'time': time_str,
        'status': status,
        'score_home': home.get('score') if status in ('FT', 'LIVE') else None,
        'score_away': away.get('score') if status in ('FT', 'LIVE') else None,
        'minute': '' if status != 'LIVE' else 'LIVE',
        'round': round_label,
    }


def fetch_wbc_schedule():
    """Fetch WBC schedule for the current year."""
    year = datetime.now().year
    try:
        resp = httpx.get(f'{MLB_API_BASE}/schedule', params={
            'sportId': 51, 'startDate': f'{year}-03-01', 'endDate': f'{year}-04-15',
            'hydrate': 'team',
        }, timeout=8)
        resp.raise_for_status()
        matches = []
        for d in resp.json().get('dates', []):
            for g in d.get('games', []):
                matches.append(_parse_wbc_game(g))
        matches.sort(key=lambda m: m['date'])
        return matches if matches else []
    except Exception as e:
        logger.error(f'Failed to fetch WBC schedule: {e}')
        return []


@_cache_fn
def fetch_wbc_standings():
    """Fetch WBC pool play standings by computing W/L from pool play games."""
    year = datetime.now().year
    try:
        resp = httpx.get(f'{MLB_API_BASE}/schedule', params={
            'sportId': 51, 'startDate': f'{year}-03-01', 'endDate': f'{year}-04-15',
            'hydrate': 'team',
        }, timeout=8)
        resp.raise_for_status()

        # Collect pool play games only
        pool_games = []
        for d in resp.json().get('dates', []):
            for g in d.get('games', []):
                sd = g.get('seriesDescription', '')
                if 'Pool Play' in sd:
                    pool_games.append(g)

        if not pool_games:
            return []

        # Build team records grouped by pool
        teams = {}
        for g in pool_games:
            if g['status']['detailedState'] not in ('Final', 'Game Over', 'Completed Early'):
                continue
            away = g['teams']['away']
            home = g['teams']['home']
            a_score = away.get('score', 0) or 0
            h_score = home.get('score', 0) or 0
            # Determine pool from seriesDescription: "World Baseball Classic Pool Play"
            # We need to figure out pools — group by which teams play each other
            for side, score, opp_score in [(away, a_score, h_score), (home, h_score, a_score)]:
                name = side['team']['name']
                tid = side['team'].get('id', '')
                if name not in teams:
                    teams[name] = {'name': name, 'id': tid, 'wins': 0, 'losses': 0, 'opponents': set()}
                if score > opp_score:
                    teams[name]['wins'] += 1
                else:
                    teams[name]['losses'] += 1
                opp_name = home['team']['name'] if side is away else away['team']['name']
                teams[name]['opponents'].add(opp_name)

        # Determine pools by opponent clusters
        pools = {}
        assigned = set()
        pool_letter = ord('A')
        for name, data in sorted(teams.items(), key=lambda x: -x[1]['wins']):
            if name in assigned:
                continue
            cluster = {name} | data['opponents']
            pool_name = f"Pool {chr(pool_letter)}"
            pool_letter += 1
            for t in cluster:
                if t in teams and t not in assigned:
                    assigned.add(t)
                    pools.setdefault(pool_name, []).append(t)

        # Build standings list
        standings = []
        for pool_name in sorted(pools.keys()):
            pool_teams = pools[pool_name]
            pool_data = sorted([teams[t] for t in pool_teams if t in teams],
                               key=lambda x: (-x['wins'], x['losses']))
            for rank, t in enumerate(pool_data, 1):
                total = t['wins'] + t['losses']
                standings.append({
                    'rank': rank,
                    'name': t['name'],
                    'code': t['name'],
                    'image': _mlb_logo(t['id']),
                    'pool': pool_name,
                    'wins': t['wins'],
                    'losses': t['losses'],
                    'win_rate': f"{t['wins'] / total:.3f}" if total > 0 else '-',
                })
        return standings
    except Exception as e:
        logger.error(f'Failed to fetch WBC standings: {e}')
        return []


@_cache_fn
def fetch_wbc_bracket():
    """Fetch WBC knockout bracket."""
    year = datetime.now().year
    try:
        resp = httpx.get(f'{MLB_API_BASE}/schedule', params={
            'sportId': 51, 'startDate': f'{year}-03-01', 'endDate': f'{year}-04-15',
            'hydrate': 'team',
        }, timeout=8)
        resp.raise_for_status()

        ko_rounds = {}
        for d in resp.json().get('dates', []):
            for g in d.get('games', []):
                sd = g.get('seriesDescription', '')
                if 'Pool Play' in sd or 'Exhibition' in sd or not sd:
                    continue
                round_name = sd.replace('World Baseball Classic ', '')
                ko_rounds.setdefault(round_name, []).append(g)

        if not ko_rounds:
            return [], ''

        round_order = ['Quarterfinals', 'Semifinals', 'Finals']
        stages = []
        for rname in round_order:
            games = ko_rounds.get(rname, [])
            if not games:
                continue
            section_matches = []
            for g in games:
                away = g['teams']['away']
                home = g['teams']['home']
                is_done = g['status']['detailedState'] in ('Final', 'Game Over', 'Completed Early')
                a_score = away.get('score', 0) or 0
                h_score = home.get('score', 0) or 0
                gd = g.get('gameDate', '')
                try:
                    dt = datetime.fromisoformat(gd.replace('Z', '+00:00')) + timedelta(hours=9)
                    date_str = dt.strftime('%m/%d %H:%M')
                except (ValueError, AttributeError):
                    date_str = ''

                section_matches.append({
                    'state': 'completed' if is_done else 'unstarted',
                    'team1_name': home.get('team', {}).get('name', 'TBD'),
                    'team1_code': home.get('team', {}).get('abbreviation', ''),
                    'team1_image': _mlb_logo(home.get('team', {}).get('id', '')),
                    'team1_wins': h_score,
                    'team1_outcome': 'win' if is_done and h_score > a_score else '',
                    'team2_name': away.get('team', {}).get('name', 'TBD'),
                    'team2_code': away.get('team', {}).get('abbreviation', ''),
                    'team2_image': _mlb_logo(away.get('team', {}).get('id', '')),
                    'team2_wins': a_score,
                    'team2_outcome': 'win' if is_done and a_score > h_score else '',
                    'date': date_str,
                })
            stages.append({
                'name': rname,
                'sections': [{'name': rname, 'matches': section_matches}],
            })

        return stages, f'WBC {year}' if stages else ''
    except Exception as e:
        logger.error(f'Failed to fetch WBC bracket: {e}')
        return [], ''


# ═══════════════════════════════════════════════════════════
#  LIVE API: Premier League (premierleague.com Pulse)
# ═══════════════════════════════════════════════════════════

def _pl_logo(opta_id):
    """Use opta altId (e.g. 't3') for reliable badge URLs."""
    if not opta_id:
        return ''
    return f'https://resources.premierleague.com/premierleague/badges/50/{opta_id}.png'


def _pl_api(endpoint, params=None):
    """Helper for PL Pulse API calls."""
    resp = httpx.get(f'{PL_API_BASE}/{endpoint}', params=params or {},
                     headers=PL_HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _get_pl_season_id():
    """Get current PL season ID dynamically."""
    try:
        data = _pl_api('competitions/1/compseasons', {'page': 0, 'pageSize': 1})
        return str(int(data['content'][0]['id']))
    except Exception:
        return PL_COMP_SEASON


def _parse_pl_fixture(f, league='Premier League', league_short='PL'):
    """Convert PL Pulse fixture into standard match dict."""
    teams = f.get('teams', [{}, {}])
    t1 = teams[0] if teams else {}
    t2 = teams[1] if len(teams) > 1 else {}
    t1_team = t1.get('team', {})
    t2_team = t2.get('team', {})

    status_map = {'C': 'FT', 'L': 'LIVE', 'U': 'SCHEDULED'}
    status = status_map.get(f.get('status', ''), 'SCHEDULED')

    ko = f.get('kickoff', {})
    millis = ko.get('millis')
    if millis:
        # millis is UTC epoch -> convert to KST (UTC+9)
        utc_dt = datetime(1970, 1, 1) + timedelta(milliseconds=millis)
        kst_dt = utc_dt + timedelta(hours=9)
        date_str = kst_dt.strftime('%Y-%m-%d %H:%M')
        time_str = kst_dt.strftime('%H:%M')
    else:
        date_str = ''
        time_str = ''

    gw = f.get('gameweek', {}).get('gameweek', '')
    round_label = f"Matchday {int(gw)}" if gw else ''

    score_home = int(t1.get('score', 0)) if status in ('FT', 'LIVE') else None
    score_away = int(t2.get('score', 0)) if status in ('FT', 'LIVE') else None

    minute = None
    if status == 'LIVE':
        clock = f.get('clock', {})
        minute = f"{clock.get('label', '')}'" if clock.get('label') else ''

    return {
        'id': str(int(f.get('id', 0))),
        'league': league,
        'league_short': league_short,
        'tournament': f"Premier League {int(gw)}" if gw else 'Premier League',
        'home': t1_team.get('shortName', 'TBD'),
        'away': t2_team.get('shortName', 'TBD'),
        'home_code': t1_team.get('club', {}).get('abbr', ''),
        'away_code': t2_team.get('club', {}).get('abbr', ''),
        'home_image': _pl_logo(t1_team.get('altIds', {}).get('opta', '')),
        'away_image': _pl_logo(t2_team.get('altIds', {}).get('opta', '')),
        'home_record': {},
        'away_record': {},
        'date': date_str,
        'time': time_str,
        'status': status,
        'score_home': score_home,
        'score_away': score_away,
        'minute': minute,
        'round': round_label,
    }


def fetch_pl_schedule():
    """Fetch PL schedule: -7 days to +14 days (football is weekly)."""
    try:
        season = _get_pl_season_id()
        completed = _pl_api('fixtures', {
            'comps': '1', 'compSeasons': season, 'altIds': 'true',
            'page': 0, 'pageSize': 10, 'sort': 'desc', 'statuses': 'C',
        }).get('content', [])
        upcoming = _pl_api('fixtures', {
            'comps': '1', 'compSeasons': season, 'altIds': 'true',
            'page': 0, 'pageSize': 15, 'sort': 'asc', 'statuses': 'U,L',
        }).get('content', [])

        matches = [_parse_pl_fixture(f) for f in completed + upcoming]
        matches = _filter_by_date_window(matches, days_back=7, days_ahead=14)
        return matches
    except Exception as e:
        logger.error(f'Failed to fetch PL schedule: {e}')
        return []


@_cache_fn
def fetch_pl_standings():
    """Fetch current PL standings."""
    try:
        season = _get_pl_season_id()
        data = _pl_api('standings', {'compSeasons': season, 'altIds': 'true'})
        tables = data.get('tables', [])
        if not tables:
            return []

        standings = []
        for entry in tables[0].get('entries', []):
            t = entry.get('team', {})
            o = entry.get('overall', {})
            standings.append({
                'rank': entry.get('position', 0),
                'name': t.get('shortName', ''),
                'code': t.get('club', {}).get('abbr', ''),
                'image': _pl_logo(t.get('altIds', {}).get('opta', '')),
                'games': o.get('played', 0),
                'wins': o.get('won', 0),
                'draws': o.get('drawn', 0),
                'losses': o.get('lost', 0),
                'gd': o.get('goalsDifference', 0),
                'points': entry.get('overall', {}).get('points', 0),
            })
        return standings
    except Exception as e:
        logger.error(f'Failed to fetch PL standings: {e}')
        return []


# ═══════════════════════════════════════════════════════════
#  LIVE API: MLB (statsapi.mlb.com)
# ═══════════════════════════════════════════════════════════

def _mlb_logo(team_id):
    return f'https://www.mlbstatic.com/team-logos/{team_id}.svg'


def _parse_mlb_game(game):
    """Convert MLB API game object into our standard match dict."""
    away = game['teams']['away']
    home = game['teams']['home']
    away_team = away.get('team', {})
    home_team = home.get('team', {})

    status_map = {
        'Final': 'FT', 'Game Over': 'FT', 'Completed Early': 'FT',
        'In Progress': 'LIVE', 'Live': 'LIVE',
    }
    detailed = game.get('status', {}).get('detailedState', '')
    status = status_map.get(detailed, 'SCHEDULED')

    game_date = game.get('gameDate', '')
    try:
        dt = datetime.fromisoformat(game_date.replace('Z', '+00:00'))
        # Convert UTC to KST (UTC+9)
        dt_local = dt + timedelta(hours=9)
        date_str = dt_local.strftime('%Y-%m-%d %H:%M')
        time_str = dt_local.strftime('%H:%M')
    except (ValueError, AttributeError):
        date_str = game_date[:16]
        time_str = ''

    minute = None
    if status == 'LIVE':
        ls = game.get('linescore', {})
        inn = ls.get('currentInning', '')
        half = ls.get('inningHalf', '')
        minute = f"{half} {inn}" if inn else ''

    venue = game.get('venue', {}).get('name', '')
    series_game = game.get('seriesGameNumber', '')
    games_in_series = game.get('gamesInSeries', '')
    round_label = venue
    if series_game and games_in_series:
        round_label = f"{venue} · Game {series_game}/{games_in_series}"

    return {
        'id': str(game.get('gamePk', '')),
        'league': 'MLB',
        'league_short': 'MLB',
        'tournament': game.get('seriesDescription', ''),
        'home': home_team.get('name', 'TBD'),
        'away': away_team.get('name', 'TBD'),
        'home_code': home_team.get('abbreviation', ''),
        'away_code': away_team.get('abbreviation', ''),
        'home_image': _mlb_logo(home_team.get('id', '')),
        'away_image': _mlb_logo(away_team.get('id', '')),
        'home_record': {},
        'away_record': {},
        'date': date_str,
        'time': time_str,
        'status': status,
        'score_home': home.get('score') if status in ('FT', 'LIVE') else None,
        'score_away': away.get('score') if status in ('FT', 'LIVE') else None,
        'minute': minute,
        'round': round_label,
    }


def fetch_mlb_schedule():
    """Fetch MLB schedule: today, -2 days, +3 days."""
    now = datetime.now()
    start = (now - timedelta(days=2)).strftime('%Y-%m-%d')
    end = (now + timedelta(days=3)).strftime('%Y-%m-%d')
    try:
        resp = httpx.get(f'{MLB_API_BASE}/schedule', params={
            'sportId': 1, 'startDate': start, 'endDate': end,
            'hydrate': 'team,linescore',
        }, timeout=8)
        resp.raise_for_status()
        matches = []
        for date_entry in resp.json().get('dates', []):
            for game in date_entry.get('games', []):
                matches.append(_parse_mlb_game(game))
        matches.sort(key=lambda m: m['date'])
        return matches
    except Exception as e:
        logger.error(f'Failed to fetch MLB schedule: {e}')
        return []


@_cache_fn
def fetch_mlb_standings():
    """Fetch current MLB standings by division."""
    try:
        year = datetime.now().year
        resp = httpx.get(f'{MLB_API_BASE}/standings', params={
            'leagueId': '103,104', 'season': year,
            'standingsTypes': 'regularSeason', 'hydrate': 'division,team',
        }, timeout=10)
        resp.raise_for_status()
        standings = []
        for div in resp.json().get('records', []):
            div_name = div.get('division', {}).get('name', '')
            for tr in div.get('teamRecords', []):
                t = tr.get('team', {})
                standings.append({
                    'rank': int(tr.get('divisionRank', 0)),
                    'name': t.get('name', ''),
                    'code': t.get('abbreviation', ''),
                    'image': _mlb_logo(t.get('id', '')),
                    'division': div_name,
                    'wins': tr.get('wins', 0),
                    'losses': tr.get('losses', 0),
                    'win_rate': tr.get('winningPercentage', ''),
                    'gb': tr.get('divisionGamesBack', '-'),
                    'games': tr.get('wins', 0) + tr.get('losses', 0),
                })
        return standings
    except Exception as e:
        logger.error(f'Failed to fetch MLB standings: {e}')
        return []


def fetch_mlb_postseason():
    """Fetch MLB postseason bracket for the current year."""
    year = datetime.now().year
    if datetime.now().month < 9:
        return [], ''
    try:
        resp = httpx.get(f'{MLB_API_BASE}/schedule', params={
            'sportId': 1, 'season': year, 'gameType': 'W,D,L,F',
            'startDate': f'{year}-10-01', 'endDate': f'{year}-11-15',
            'hydrate': 'team,seriesStatus',
        }, timeout=8)
        resp.raise_for_status()

        # Group games by series description
        series_map = {}
        for date_entry in resp.json().get('dates', []):
            for game in date_entry.get('games', []):
                sd = game.get('seriesDescription', 'Postseason')
                series_map.setdefault(sd, []).append(game)

        if not series_map:
            return [], ''

        # Order: Wild Card -> Division -> Championship -> World Series
        round_order = ['Wild Card', 'Division', 'Championship', 'World Series']
        stages = []
        for round_key in round_order:
            matching = {k: v for k, v in series_map.items() if round_key.lower() in k.lower()}
            for series_name, games in matching.items():
                # Group by matchup
                matchups = {}
                for g in games:
                    away_name = g['teams']['away']['team']['name']
                    home_name = g['teams']['home']['team']['name']
                    key = tuple(sorted([away_name, home_name]))
                    matchups.setdefault(key, []).append(g)

                section_matches = []
                for (t1, t2), mgames in matchups.items():
                    t1_wins = sum(1 for g in mgames if g['status']['detailedState'] in ('Final', 'Game Over')
                                  and ((g['teams']['home']['team']['name'] == t1 and g['teams']['home'].get('score', 0) > g['teams']['away'].get('score', 0))
                                       or (g['teams']['away']['team']['name'] == t1 and g['teams']['away'].get('score', 0) > g['teams']['home'].get('score', 0))))
                    t2_wins = sum(1 for g in mgames if g['status']['detailedState'] in ('Final', 'Game Over')
                                  and ((g['teams']['home']['team']['name'] == t2 and g['teams']['home'].get('score', 0) > g['teams']['away'].get('score', 0))
                                       or (g['teams']['away']['team']['name'] == t2 and g['teams']['away'].get('score', 0) > g['teams']['home'].get('score', 0))))
                    all_done = all(g['status']['detailedState'] in ('Final', 'Game Over') for g in mgames)

                    # Get team IDs for logos
                    sample = mgames[0]
                    t1_id = sample['teams']['away']['team']['id'] if sample['teams']['away']['team']['name'] == t1 else sample['teams']['home']['team']['id']
                    t2_id = sample['teams']['away']['team']['id'] if sample['teams']['away']['team']['name'] == t2 else sample['teams']['home']['team']['id']

                    # Extract dates (KST)
                    gdates = []
                    for g in mgames:
                        gd = g.get('gameDate', '')
                        try:
                            dt = datetime.fromisoformat(gd.replace('Z', '+00:00')) + timedelta(hours=9)
                            gdates.append(dt.strftime('%m/%d %H:%M'))
                        except (ValueError, AttributeError):
                            pass
                    date_str = gdates[0] + (' ~ ' + gdates[-1] if len(gdates) > 1 else '') if gdates else ''

                    section_matches.append({
                        'state': 'completed' if all_done else 'inProgress',
                        'team1_name': t1, 'team1_code': t1,
                        'team1_image': _mlb_logo(t1_id),
                        'team1_wins': t1_wins,
                        'team1_outcome': 'win' if t1_wins > t2_wins and all_done else '',
                        'team2_name': t2, 'team2_code': t2,
                        'team2_image': _mlb_logo(t2_id),
                        'team2_wins': t2_wins,
                        'team2_outcome': 'win' if t2_wins > t1_wins and all_done else '',
                        'date': date_str,
                    })

                stages.append({
                    'name': series_name,
                    'sections': [{'name': series_name, 'matches': section_matches}],
                })

        title = f"MLB {year} Post-Season" if stages else ''
        return stages, title
    except Exception as e:
        logger.error(f'Failed to fetch MLB postseason: {e}')
        return [], ''
