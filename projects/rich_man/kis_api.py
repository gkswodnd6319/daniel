"""한국투자증권 Open API — FX rate history and account data.

Requires APP_KEY and APP_SECRET from https://apiportal.koreainvestment.com
Set in .env:
  KIS_APP_KEY=your_key
  KIS_APP_SECRET=your_secret
  KIS_ACCOUNT_TYPE=paper  (or "real")

Endpoints used:
  - OAuth token: /oauth2/tokenP
  - FX daily chart: /uapi/overseas-price/v1/quotations/inquire-daily-chartprice
"""

import os
import httpx
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

APP_KEY = os.getenv('KIS_APP_KEY', '')
APP_SECRET = os.getenv('KIS_APP_SECRET', '')
ACCOUNT_TYPE = os.getenv('KIS_ACCOUNT_TYPE', 'paper')

BASE_URL = 'https://openapi.koreainvestment.com:9443' if ACCOUNT_TYPE == 'real' else 'https://openapivts.koreainvestment.com:29443'

_token_cache = {'token': '', 'expires': 0}


def is_configured():
    """Check if KIS API keys are set."""
    return bool(APP_KEY and APP_SECRET)


def _get_token():
    """Get OAuth access token. Cached until expiry."""
    now = datetime.now().timestamp()
    if _token_cache['token'] and now < _token_cache['expires']:
        return _token_cache['token']

    if not is_configured():
        return None

    try:
        resp = httpx.post(f'{BASE_URL}/oauth2/tokenP', json={
            'grant_type': 'client_credentials',
            'appkey': APP_KEY,
            'appsecret': APP_SECRET,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        token = data.get('access_token', '')
        # Token valid for ~24 hours, cache for 23 hours
        _token_cache['token'] = token
        _token_cache['expires'] = now + 23 * 3600
        logger.info('KIS API token acquired')
        return token
    except Exception as e:
        logger.error(f'KIS token error: {e}')
        return None


def _headers(tr_id):
    """Build request headers with auth token."""
    token = _get_token()
    if not token:
        return None
    return {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {token}',
        'appkey': APP_KEY,
        'appsecret': APP_SECRET,
        'tr_id': tr_id,
    }


def fetch_fx_daily_history(days=90):
    """Fetch daily USD/KRW rates from 한투 API.
    Returns list of (date_str, close_price) sorted by date, or None if not configured.
    """
    if not is_configured():
        return None

    headers = _headers('FHKST03030100')
    if not headers:
        return None

    end = datetime.now()
    start = end - timedelta(days=days)

    try:
        resp = httpx.get(f'{BASE_URL}/uapi/overseas-price/v1/quotations/inquire-daily-chartprice',
            headers=headers,
            params={
                'fid_cond_mrkt_div_code': 'X',   # X = exchange rates
                'fid_input_iscd': 'FX@KRW',       # USD/KRW
                'fid_input_date_1': start.strftime('%Y%m%d'),
                'fid_input_date_2': end.strftime('%Y%m%d'),
                'fid_period_div_code': 'D',        # D=daily, W=weekly, M=monthly
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        output2 = data.get('output2', [])
        if not output2:
            logger.warning(f'KIS FX: no data returned')
            return None

        result = []
        for item in output2:
            date_str = item.get('stck_bsop_date', '')  # YYYYMMDD
            close = item.get('ovrs_nmix_prpr', '') or item.get('stck_clpr', '')
            if date_str and close:
                formatted_date = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'
                result.append((formatted_date, float(close)))

        result.sort(key=lambda x: x[0])
        logger.info(f'KIS FX: {len(result)} daily rates fetched')
        return result

    except Exception as e:
        logger.error(f'KIS FX history error: {e}')
        return None


def fetch_fx_latest():
    """Fetch the most recent USD/KRW rate from 한투.
    Returns (date_str, rate) or None.
    """
    history = fetch_fx_daily_history(days=7)
    if history:
        return history[-1]
    return None
