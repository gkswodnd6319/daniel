"""FX data layer — live rates + historical time series.

Live rates:   Finnhub (finnhub.io) — free key, real-time forex quotes.
Fallback:     ExchangeRate-API (open.er-api.com) — no key, daily updates.
History:      Frankfurter API (frankfurter.dev) — free, no key, ECB data.
"""

import os
import httpx
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

FINNHUB_KEY = os.getenv('FINNHUB_API_KEY', '')
FINNHUB_API = 'https://finnhub.io/api/v1'
FALLBACK_API = 'https://open.er-api.com/v6/latest'
HISTORY_API = 'https://api.frankfurter.dev/v1'

_cache = {}
_LIVE_TTL = 30       # Finnhub: refresh every 30 seconds
_HISTORY_TTL = 600   # historical: refresh every 10 minutes

# Finnhub uses OANDA pair format: "OANDA:BASE_QUOTE"
# For KRW base we fetch "OANDA:USD_KRW" and invert where needed.
# Not all KRW pairs exist directly — we fetch via USD cross rates.
_FINNHUB_DIRECT_PAIRS = {
    'USD': 'OANDA:USD_KRW',
    'EUR': 'OANDA:EUR_KRW',
    'GBP': 'OANDA:GBP_KRW',
    'JPY': 'OANDA:USD_JPY',   # cross via USD
    'CNY': 'OANDA:USD_CNH',   # offshore CNY
    'AUD': 'OANDA:AUD_USD',   # cross via USD
    'CAD': 'OANDA:USD_CAD',   # cross via USD
    'CHF': 'OANDA:USD_CHF',   # cross via USD
    'SGD': 'OANDA:USD_SGD',   # cross via USD
    'HKD': 'OANDA:USD_HKD',   # cross via USD
}

POPULAR_CURRENCIES = [
    'USD', 'EUR', 'JPY', 'GBP', 'CNY', 'AUD', 'CAD', 'CHF',
    'SGD', 'HKD', 'THB', 'SEK', 'NZD', 'MXN', 'INR', 'BRL',
]

CURRENCY_META = {
    'USD': ('United States Dollar', '$', '🇺🇸'),
    'EUR': ('Euro', '\u20ac', '🇪🇺'),
    'JPY': ('Japanese Yen', '\u00a5', '🇯🇵'),
    'GBP': ('British Pound', '\u00a3', '🇬🇧'),
    'CNY': ('Chinese Yuan', '\u00a5', '🇨🇳'),
    'AUD': ('Australian Dollar', 'A$', '🇦🇺'),
    'CAD': ('Canadian Dollar', 'C$', '🇨🇦'),
    'CHF': ('Swiss Franc', 'Fr', '🇨🇭'),
    'SGD': ('Singapore Dollar', 'S$', '🇸🇬'),
    'HKD': ('Hong Kong Dollar', 'HK$', '🇭🇰'),
    'THB': ('Thai Baht', '\u0e3f', '🇹🇭'),
    'SEK': ('Swedish Krona', 'kr', '🇸🇪'),
    'NZD': ('New Zealand Dollar', 'NZ$', '🇳🇿'),
    'MXN': ('Mexican Peso', 'Mex$', '🇲🇽'),
    'INR': ('Indian Rupee', '\u20b9', '🇮🇳'),
    'BRL': ('Brazilian Real', 'R$', '🇧🇷'),
    'KRW': ('South Korean Won', '\u20a9', '🇰🇷'),
    'PLN': ('Polish Zloty', 'z\u0142', '🇵🇱'),
    'TRY': ('Turkish Lira', '\u20ba', '🇹🇷'),
    'ZAR': ('South African Rand', 'R', '🇿🇦'),
    'NOK': ('Norwegian Krone', 'kr', '🇳🇴'),
    'DKK': ('Danish Krone', 'kr', '🇩🇰'),
    'CZK': ('Czech Koruna', 'K\u010d', '🇨🇿'),
    'HUF': ('Hungarian Forint', 'Ft', '🇭🇺'),
    'PHP': ('Philippine Peso', '\u20b1', '🇵🇭'),
    'IDR': ('Indonesian Rupiah', 'Rp', '🇮🇩'),
    'MYR': ('Malaysian Ringgit', 'RM', '🇲🇾'),
    'RON': ('Romanian Leu', 'lei', '🇷🇴'),
    'BGN': ('Bulgarian Lev', 'лв', '🇧🇬'),
    'ISK': ('Icelandic Krona', 'kr', '🇮🇸'),
}


def _cached(key, fetch_fn, ttl):
    now = datetime.now().timestamp()
    if key in _cache:
        data, ts = _cache[key]
        if now - ts < ttl:
            return data
    data = fetch_fn()
    if data is not None:
        _cache[key] = (data, now)
    return data


def _finnhub_quote(symbol):
    """Fetch a single real-time quote from Finnhub."""
    if not FINNHUB_KEY or FINNHUB_KEY == 'your_key_here':
        return None
    try:
        resp = httpx.get(f'{FINNHUB_API}/quote', params={
            'symbol': symbol, 'token': FINNHUB_KEY,
        }, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get('c', 0) == 0:
            return None
        return data  # {c: current, h: high, l: low, o: open, pc: prev close, t: timestamp}
    except Exception as e:
        logger.error(f'Finnhub quote {symbol}: {e}')
        return None


def _finnhub_rates(base='KRW'):
    """Fetch all FX rates from Finnhub /forex/rates endpoint."""
    if not FINNHUB_KEY or FINNHUB_KEY == 'your_key_here':
        return None
    try:
        resp = httpx.get(f'{FINNHUB_API}/forex/rates', params={
            'base': base, 'token': FINNHUB_KEY,
        }, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get('quote', {})
    except Exception as e:
        logger.error(f'Finnhub rates: {e}')
        return None


def fetch_latest(base='KRW'):
    """Fetch live rates. Tries Finnhub first, falls back to ExchangeRate-API."""
    def _fetch():
        # Try Finnhub real-time rates
        finnhub_rates = _finnhub_rates(base)
        if finnhub_rates:
            return {
                'rates': finnhub_rates,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S KST'),
                'source': 'Finnhub (real-time)',
                'base': base,
            }

        # Fallback to ExchangeRate-API
        try:
            resp = httpx.get(f'{FALLBACK_API}/{base}', timeout=8)
            resp.raise_for_status()
            data = resp.json()
            if data.get('result') != 'success':
                return None
            return {
                'rates': data.get('rates', {}),
                'date': data.get('time_last_update_utc', '')[:25],
                'source': 'ExchangeRate-API (daily)',
                'base': base,
            }
        except Exception as e:
            logger.error(f'Failed to fetch live rates: {e}')
            return None
    return _cached(f'live_{base}', _fetch, ttl=_LIVE_TTL)


def fetch_quote_detail(target='USD', base='KRW'):
    """Fetch detailed quote (open/high/low/close/prev) for a single pair from Finnhub."""
    symbol = _FINNHUB_DIRECT_PAIRS.get(target)
    if not symbol:
        return None

    def _fetch():
        q = _finnhub_quote(symbol)
        if not q:
            return None
        # Determine how to convert to KRW per 1 target
        if target in ('USD', 'EUR', 'GBP'):
            # Direct KRW pairs: OANDA:USD_KRW -> value IS KRW per 1 target
            return {
                'current': q['c'], 'open': q['o'], 'high': q['h'],
                'low': q['l'], 'prev_close': q['pc'], 'timestamp': q.get('t', 0),
            }
        elif target == 'JPY':
            # USD_JPY: need USD_KRW / USD_JPY to get KRW per 1 JPY
            usd_krw = _finnhub_quote('OANDA:USD_KRW')
            if not usd_krw:
                return None
            return {
                'current': usd_krw['c'] / q['c'] if q['c'] else 0,
                'open': usd_krw['o'] / q['o'] if q['o'] else 0,
                'high': usd_krw['h'] / q['l'] if q['l'] else 0,  # high KRW/JPY when USD/JPY is low
                'low': usd_krw['l'] / q['h'] if q['h'] else 0,
                'prev_close': usd_krw['pc'] / q['pc'] if q['pc'] else 0,
                'timestamp': q.get('t', 0),
            }
        else:
            # Cross via USD: need USD_KRW quote too
            usd_krw = _finnhub_quote('OANDA:USD_KRW')
            if not usd_krw:
                return None
            # For USD_XXX pairs (CAD, CHF, SGD, HKD): KRW per 1 XXX = USD_KRW / USD_XXX
            # For XXX_USD pairs (AUD): KRW per 1 XXX = USD_KRW * XXX_USD
            if target == 'AUD':
                return {
                    'current': usd_krw['c'] * q['c'],
                    'open': usd_krw['o'] * q['o'],
                    'high': usd_krw['h'] * q['h'],
                    'low': usd_krw['l'] * q['l'],
                    'prev_close': usd_krw['pc'] * q['pc'],
                    'timestamp': q.get('t', 0),
                }
            elif target == 'CNY':
                # USD_CNH: KRW per 1 CNY = USD_KRW / USD_CNH
                return {
                    'current': usd_krw['c'] / q['c'] if q['c'] else 0,
                    'open': usd_krw['o'] / q['o'] if q['o'] else 0,
                    'high': usd_krw['h'] / q['l'] if q['l'] else 0,
                    'low': usd_krw['l'] / q['h'] if q['h'] else 0,
                    'prev_close': usd_krw['pc'] / q['pc'] if q['pc'] else 0,
                    'timestamp': q.get('t', 0),
                }
            else:
                # USD_XXX: KRW per 1 XXX = USD_KRW / USD_XXX
                return {
                    'current': usd_krw['c'] / q['c'] if q['c'] else 0,
                    'open': usd_krw['o'] / q['o'] if q['o'] else 0,
                    'high': usd_krw['h'] / q['l'] if q['l'] else 0,
                    'low': usd_krw['l'] / q['h'] if q['h'] else 0,
                    'prev_close': usd_krw['pc'] / q['pc'] if q['pc'] else 0,
                    'timestamp': q.get('t', 0),
                }
    return _cached(f'quote_{base}_{target}', _fetch, ttl=_LIVE_TTL)


def get_last_updated(base='KRW'):
    """Return (last_updated_str, seconds_ago, source) for the cached live data."""
    key = f'live_{base}'
    if key in _cache:
        data, ts = _cache[key]
        ago = int(datetime.now().timestamp() - ts)
        source = data.get('source', '') if data else ''
        return datetime.fromtimestamp(ts).strftime('%H:%M:%S KST'), ago, source
    return None, None, ''


def fetch_history(base='KRW', target='USD', days=90):
    """Fetch historical rates from Frankfurter API."""
    def _fetch():
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            resp = httpx.get(
                f'{HISTORY_API}/{start.strftime("%Y-%m-%d")}..{end.strftime("%Y-%m-%d")}',
                params={'base': base, 'symbols': target},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            rates = data.get('rates', {})
            return sorted(
                [(d, v[target]) for d, v in rates.items() if target in v],
                key=lambda x: x[0],
            )
        except Exception as e:
            logger.error(f'Failed to fetch history {base}/{target}: {e}')
            return None
    return _cached(f'history_{base}_{target}_{days}', _fetch, ttl=_HISTORY_TTL)


def fetch_multi_history(base='KRW', targets=None, days=90):
    """Fetch historical rates for base vs multiple targets."""
    if targets is None:
        targets = ['USD']
    def _fetch():
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            resp = httpx.get(
                f'{HISTORY_API}/{start.strftime("%Y-%m-%d")}..{end.strftime("%Y-%m-%d")}',
                params={'base': base, 'symbols': ','.join(targets)},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            rates = data.get('rates', {})
            result = {}
            for target in targets:
                result[target] = sorted(
                    [(d, v.get(target)) for d, v in rates.items() if v.get(target) is not None],
                    key=lambda x: x[0],
                )
            return result
        except Exception as e:
            logger.error(f'Failed to fetch multi history: {e}')
            return None
    key = f'multi_{base}_{"_".join(sorted(targets))}_{days}'
    return _cached(key, _fetch, ttl=_HISTORY_TTL)


def is_finnhub_active():
    """Check if Finnhub API key is configured and working."""
    return bool(FINNHUB_KEY and FINNHUB_KEY != 'your_key_here')


def warm_cache(base='KRW'):
    """Pre-fetch FX data in a background thread so the Rich Man tab loads instantly."""
    import threading

    def _warm():
        try:
            fetch_latest(base)
            for cur in ['USD', 'EUR', 'JPY', 'GBP', 'CNY', 'CAD']:
                fetch_history(base, cur, days=7)
            fetch_history(base, 'USD', days=90)
        except Exception as e:
            logger.error(f'FX warm_cache failed: {e}')

    threading.Thread(target=_warm, daemon=True).start()


def get_currency_label(code):
    """Return 'flag Code — Name' for display."""
    meta = CURRENCY_META.get(code)
    if meta:
        return f'{meta[2]} {code} — {meta[0]}'
    return code


def get_currency_options(exclude='KRW'):
    """Return dict of code -> display label for dropdown, excluding base."""
    options = {}
    for code in POPULAR_CURRENCIES:
        if code == exclude:
            continue
        options[code] = get_currency_label(code)
    return options
