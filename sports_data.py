"""
Sports data provider — demo data for now, swap with real APIs later.

APIs you can plug in:
  - Football: https://www.api-football.com  (free: 100 req/day)
  - LoL Esports: https://lolesports.com (unofficial community APIs)
  - MLB: https://statsapi.mlb.com (free, no key needed)
  - KBO: Manual / scraping (no official public API)
"""

import random
from datetime import datetime, timedelta


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
    'MLB': 'MLB',
    'KBO': 'KBO',
}

LEAGUE_FILTERS = {
    'all': {'label': 'All', 'color': '#00e676'},
    'Premier League': {'label': 'EPL', 'color': '#3d195b'},
    'Champions League': {'label': 'UCL', 'color': '#071d6b'},
    'LCK': {'label': 'LCK', 'color': '#c89b3c'},
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
    is_esports = league in ('LCK',)
    
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


def get_all_matches():
    """Get all demo matches across all leagues."""
    all_matches = []
    counts = {
        'Premier League': 16,
        'Champions League': 10,
        'LCK': 14,
        'MLB': 18,
        'KBO': 14,
    }
    for league, count in counts.items():
        all_matches.extend(_generate_league_matches(league, count))
    
    all_matches.sort(key=lambda m: m['date'])
    return all_matches


# ═══════════════════════════════════════════════════════════
#  TODO: Real API integrations
# ═══════════════════════════════════════════════════════════
#
# async def fetch_football_api(league_id):
#     """Fetch from api-football.com (free tier: 100 req/day)."""
#     import httpx
#     async with httpx.AsyncClient() as client:
#         resp = await client.get(
#             'https://v3.football.api-sports.io/fixtures',
#             headers={'x-apisports-key': 'YOUR_KEY'},
#             params={'league': league_id, 'season': 2025, 'next': 10},
#         )
#         return resp.json()
#
# async def fetch_mlb_schedule():
#     """MLB Stats API — free, no auth needed."""
#     import httpx
#     today = datetime.now().strftime('%Y-%m-%d')
#     async with httpx.AsyncClient() as client:
#         resp = await client.get(
#             f'https://statsapi.mlb.com/api/v1/schedule?date={today}&sportId=1'
#         )
#         return resp.json()
