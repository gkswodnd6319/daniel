"""Finnhub Websocket Manager — real-time FX price streaming.

Connects to wss://ws.finnhub.io, subscribes to FX pairs,
and pushes live ticks to registered callbacks.

Usage:
    from projects.fx_ws import fx_stream
    fx_stream.start()                    # connect + subscribe
    fx_stream.on_tick(my_callback)       # register callback(symbol, price, timestamp)
    fx_stream.get_price('USD')           # latest price for USD/KRW
    fx_stream.stop()                     # disconnect
"""

import os
import json
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

FINNHUB_KEY = os.getenv('FINNHUB_API_KEY', '')
WS_URL = f'wss://ws.finnhub.io?token={FINNHUB_KEY}'

# FX pairs to subscribe to — Finnhub OANDA format
# We track everything relative to KRW
SUBSCRIBE_PAIRS = {
    'USD': 'OANDA:USD_KRW',
    'EUR': 'OANDA:EUR_KRW',
    'GBP': 'OANDA:GBP_KRW',
    'JPY': 'OANDA:USD_JPY',     # cross: KRW/JPY = USD_KRW / USD_JPY
    'CNY': 'OANDA:USD_CNH',     # cross: KRW/CNY = USD_KRW / USD_CNH
    'CAD': 'OANDA:USD_CAD',     # cross: KRW/CAD = USD_KRW / USD_CAD
    'AUD': 'OANDA:AUD_USD',     # cross: KRW/AUD = USD_KRW * AUD_USD
    'CHF': 'OANDA:USD_CHF',     # cross: KRW/CHF = USD_KRW / USD_CHF
}

# Reverse map: OANDA symbol -> currency code
_SYMBOL_TO_CODE = {v: k for k, v in SUBSCRIBE_PAIRS.items()}

KST = timedelta(hours=9)


class FXStream:
    """Singleton websocket manager for Finnhub FX streaming."""

    def __init__(self):
        self._prices = {}           # currency -> {price, krw_per_unit, timestamp, raw_symbol}
        self._raw_prices = {}       # OANDA symbol -> latest price
        self._callbacks = []        # list of fn(currency, krw_per_unit, timestamp)
        self._tick_history = defaultdict(list)  # currency -> [(timestamp, krw_per_unit), ...]
        self._ws = None
        self._task = None
        self._loop = None
        self._thread = None
        self._connected = False
        self._should_run = False
        self._reconnect_count = 0
        self._max_history = 300     # keep last 300 ticks per currency (~5 min at 1/sec)

    @property
    def connected(self):
        return self._connected

    def on_tick(self, callback):
        """Register a callback: fn(currency, krw_per_unit, timestamp_str)."""
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        """Remove a previously registered callback."""
        self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def get_price(self, currency):
        """Get latest price data for a currency. Returns dict or None."""
        return self._prices.get(currency)

    def get_all_prices(self):
        """Get all latest prices. Returns dict of currency -> price data."""
        return dict(self._prices)

    def get_tick_history(self, currency, limit=60):
        """Get recent tick history for mini-chart. Returns [(ts_str, price), ...]."""
        history = self._tick_history.get(currency, [])
        return history[-limit:]

    def start(self):
        """Start the websocket connection in a background thread."""
        if not FINNHUB_KEY or FINNHUB_KEY == 'your_key_here':
            logger.warning('No Finnhub API key — websocket disabled')
            return

        if self._should_run:
            return  # already running

        self._should_run = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info('FX websocket stream starting...')

    def stop(self):
        """Stop the websocket connection."""
        self._should_run = False
        if self._loop and self._task:
            self._loop.call_soon_threadsafe(self._task.cancel)
        self._connected = False
        logger.info('FX websocket stream stopped')

    def _run_loop(self):
        """Run the async event loop in a dedicated thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self):
        """Connection loop with auto-reconnect."""
        import websockets

        while self._should_run:
            try:
                logger.info(f'Connecting to Finnhub websocket...')
                async with websockets.connect(WS_URL) as ws:
                    self._ws = ws
                    self._connected = True
                    self._reconnect_count = 0
                    logger.info('Finnhub websocket connected')

                    # Subscribe to all pairs
                    for symbol in SUBSCRIBE_PAIRS.values():
                        await ws.send(json.dumps({
                            'type': 'subscribe',
                            'symbol': symbol,
                        }))
                        logger.info(f'Subscribed to {symbol}')

                    # Listen for messages
                    async for msg in ws:
                        if not self._should_run:
                            break
                        self._handle_message(msg)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._reconnect_count += 1
                wait = min(30, 2 ** self._reconnect_count)
                logger.error(f'Websocket error: {e}. Reconnecting in {wait}s...')
                await asyncio.sleep(wait)

        self._connected = False

    def _handle_message(self, raw_msg):
        """Process incoming websocket message."""
        try:
            data = json.loads(raw_msg)
            if data.get('type') != 'trade':
                return

            for trade in data.get('data', []):
                symbol = trade.get('s', '')
                price = trade.get('p', 0)
                ts_ms = trade.get('t', 0)

                if not symbol or not price:
                    continue

                # Store raw price
                self._raw_prices[symbol] = price

                # Convert to KRW per 1 unit of target currency
                currency = _SYMBOL_TO_CODE.get(symbol)
                if not currency:
                    continue

                krw_per_unit = self._calculate_krw(currency, symbol, price)
                if not krw_per_unit:
                    continue

                # Timestamp in KST
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) + KST
                ts_str = ts.strftime('%H:%M:%S')

                # Update latest
                prev = self._prices.get(currency, {}).get('krw_per_unit', 0)
                self._prices[currency] = {
                    'price': price,
                    'krw_per_unit': krw_per_unit,
                    'prev': prev,
                    'timestamp': ts_str,
                    'raw_symbol': symbol,
                }

                # Append to history
                hist = self._tick_history[currency]
                hist.append((ts_str, krw_per_unit))
                if len(hist) > self._max_history:
                    self._tick_history[currency] = hist[-self._max_history:]

                # Fire callbacks
                for cb in self._callbacks:
                    try:
                        cb(currency, krw_per_unit, ts_str)
                    except Exception as e:
                        logger.error(f'Callback error: {e}')

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f'Message handling error: {e}')

    def _calculate_krw(self, currency, symbol, price):
        """Convert raw OANDA price to KRW per 1 unit of the target currency."""
        if currency in ('USD', 'EUR', 'GBP'):
            # Direct pair: OANDA:XXX_KRW — price IS KRW per 1 unit
            return price

        # Cross rates need USD_KRW
        usd_krw = self._raw_prices.get('OANDA:USD_KRW')
        if not usd_krw:
            return None

        if currency == 'AUD':
            # AUD_USD: KRW per 1 AUD = USD_KRW * AUD_USD
            return usd_krw * price
        else:
            # USD_XXX: KRW per 1 XXX = USD_KRW / USD_XXX
            return usd_krw / price if price else None


# Singleton instance
fx_stream = FXStream()
