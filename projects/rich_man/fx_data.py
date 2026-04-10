"""FX data layer — live rates + historical time series.

Live rates:   Upbit CRIX API (서울외국환중개 data, free, no key, updates during KRW market hours).
Real-time:    Upbit WebSocket KRW-USDT (free, no key, 24/7 sub-second ticks).
Fallback:     ExchangeRate-API (open.er-api.com) — no key, daily updates, 166 currencies.
History:      Frankfurter API (frankfurter.dev) — free, no key, ECB data.
Intraday:     Bithumb candle API — free, no key, 5000 hourly candles (~7 months).
"""

import httpx
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

UPBIT_CRIX_API = 'https://crix-api-cdn.upbit.com/v1/forex/recent'
FALLBACK_API = 'https://open.er-api.com/v6/latest'
HISTORY_API = 'https://api.frankfurter.dev/v1'

_cache = {}
_LIVE_TTL = 30       # Upbit CRIX: refresh every 30 seconds
_HISTORY_TTL = 600   # historical: refresh every 10 minutes

# Upbit CRIX currency codes
UPBIT_CODES = {
    'USD': 'FRX.KRWUSD', 'EUR': 'FRX.KRWEUR', 'JPY': 'FRX.KRWJPY',
    'GBP': 'FRX.KRWGBP', 'CNY': 'FRX.KRWCNY', 'CAD': 'FRX.KRWCAD',
    'AUD': 'FRX.KRWAUD', 'CHF': 'FRX.KRWCHF',
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


def fetch_upbit_crix():
    """Fetch live KRW FX rates from Upbit CRIX (서울외국환중개 data).
    Returns dict of currency -> {basePrice, openingPrice, highPrice, lowPrice,
    changePrice, signedChangePrice, signedChangeRate, high52wPrice, low52wPrice, ...}
    """
    def _fetch():
        try:
            codes = ','.join(UPBIT_CODES.values())
            resp = httpx.get(UPBIT_CRIX_API, params={'codes': codes}, timeout=5)
            resp.raise_for_status()
            result = {}
            for item in resp.json():
                cur_code = item.get('currencyCode', '')
                if cur_code:
                    result[cur_code] = item
            return result
        except Exception as e:
            logger.error(f'Upbit CRIX fetch failed: {e}')
            return None
    return _cached('upbit_crix', _fetch, ttl=_LIVE_TTL)


def fetch_latest(base='KRW'):
    """Fetch live rates. Tries Upbit CRIX first, falls back to ExchangeRate-API.
    Returns dict with 'rates' (currency -> rate as fraction of KRW), 'date', 'source'.
    """
    def _fetch():
        # Try Upbit CRIX (official 서울외국환중개 rates)
        crix = fetch_upbit_crix()
        if crix:
            rates = {}
            for cur, data in crix.items():
                bp = data.get('basePrice', 0)
                if bp:
                    rates[cur] = 1 / bp  # convert KRW-per-unit to unit-per-KRW
            if rates:
                return {
                    'rates': rates,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S KST'),
                    'source': 'Upbit CRIX (서울외국환중개)',
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
            logger.error(f'Fallback rates fetch failed: {e}')
            return None
    return _cached(f'live_{base}', _fetch, ttl=_LIVE_TTL)


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
    """Fetch daily historical rates. Tries 한투 API first (real USD/KRW), falls back to Frankfurter (ECB)."""
    def _fetch():
        # Try 한투 API for real USD/KRW data
        if target == 'USD':
            from projects.rich_man.kis_api import is_configured, fetch_fx_daily_history
            if is_configured():
                kis_data = fetch_fx_daily_history(days=days)
                if kis_data:
                    # Convert from KRW-per-USD to USD-per-KRW (same as Frankfurter format)
                    return [(d, 1 / p) for d, p in kis_data if p]

        # Fallback: Frankfurter (ECB data)
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


BITHUMB_CANDLE_API = 'https://api.bithumb.com/public/candlestick/USDT_KRW'


def fetch_intraday_history(interval='1h', start_date=None, end_date=None):
    """Fetch hourly KRW-USDT candles from Bithumb. Returns [(datetime_str, close_price), ...].
    interval: '1h' (default), '30m', '10m'
    """
    def _fetch():
        try:
            resp = httpx.get(f'{BITHUMB_CANDLE_API}/{interval}', timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('status') != '0000':
                logger.error(f'Bithumb candle error: {data}')
                return None
            candles = data.get('data', [])
            result = []
            for c in candles:
                ts_ms = c[0]
                close = float(c[2])
                # Convert to KST datetime string
                dt = datetime.fromtimestamp(ts_ms / 1000) + timedelta(hours=9)
                result.append((dt.strftime('%Y-%m-%d %H:%M'), close))
            result.sort(key=lambda x: x[0])
            return result
        except Exception as e:
            logger.error(f'Bithumb candle fetch failed: {e}')
            return None

    data = _cached(f'intraday_{interval}', _fetch, ttl=_HISTORY_TTL)
    if not data:
        return None

    # Filter by date range if provided
    if start_date or end_date:
        sd = start_date or '0000'
        ed = (end_date + ' 23:59') if end_date else '9999'
        data = [(d, p) for d, p in data if sd <= d <= ed]

    return data


def warm_cache(base='KRW'):
    """Pre-fetch FX data in a background thread."""
    import threading

    def _warm():
        try:
            fetch_upbit_crix()
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
