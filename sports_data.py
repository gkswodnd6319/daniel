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
#  LOL ESPORTS API (free, public key)
# ═══════════════════════════════════════════════════════════
LOL_ESPORTS_BASE = 'https://esports-api.lolesports.com/persisted/gw'
LOL_ESPORTS_KEY = '0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z'
LOL_ESPORTS_HEADERS = {'x-api-key': LOL_ESPORTS_KEY}

LCK_LEAGUE_ID = '98767991310872058'

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


def get_matches_by_league(league):
    """Get matches for a league. Uses live API for LCK and LoL International."""
    if league == 'LCK':
        matches = fetch_lck_schedule()
        if matches:
            return matches
        logger.warning('LCK API failed, falling back to demo data')
    elif league == 'LoL International':
        matches = fetch_lol_intl_schedule()
        if matches is not None:
            return matches
        logger.warning('LoL International API failed, falling back to demo data')

    count = LEAGUE_MATCH_COUNTS.get(league, 10)
    matches = _generate_league_matches(league, count)
    matches.sort(key=lambda m: m['date'])
    return matches


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


def fetch_lck_standings():
    """Fetch current LCK standings.
    Returns list of dicts: [{rank, name, code, image, wins, losses}, ...] sorted by rank.
    """
    try:
        tid, slug = _get_current_lck_tournament()
        if not tid:
            return []

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
                    'image': team.get('image', ''),
                    'wins': rec.get('wins', 0),
                    'losses': rec.get('losses', 0),
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

        cutoff = datetime.now() - timedelta(days=7)
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
        'home_image': team_a.get('image', ''),
        'away_image': team_b.get('image', ''),
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
                        'team1_image': t1.get('image', ''),
                        'team1_wins': r1.get('gameWins', 0),
                        'team1_outcome': r1.get('outcome', ''),
                        'team2_name': t2.get('name', 'TBD'),
                        'team2_code': t2.get('code', ''),
                        'team2_image': t2.get('image', ''),
                        'team2_wins': r2.get('gameWins', 0),
                        'team2_outcome': r2.get('outcome', ''),
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
