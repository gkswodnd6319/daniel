"""Real-time FX streaming via Upbit WebSocket.

Upbit streams KRW-USDT trades 24/7 — USDT tracks USD within ~0.3%.
No API key required. Sub-second tick updates.

Usage:
    from projects.fx_ws import fx_stream
    fx_stream.start()
    fx_stream.on_tick(my_callback)       # fn(price, timestamp_str)
    fx_stream.get_price()                # latest KRW/USDT price
    fx_stream.get_tick_history(limit=60) # recent ticks for charting
"""

import json
import asyncio
import logging
import threading
from datetime import datetime, timezone, timedelta
from collections import deque

logger = logging.getLogger(__name__)

WS_URL = 'wss://api.upbit.com/websocket/v1'
SUBSCRIBE_MSG = json.dumps([
    {'ticket': 'richman-fx'},
    {'type': 'ticker', 'codes': ['KRW-USDT']},
])

KST = timedelta(hours=9)


class FXStream:
    """Singleton websocket manager — streams KRW-USDT from Upbit."""

    def __init__(self):
        self._price = 0.0             # latest KRW per 1 USDT
        self._prev_price = 0.0
        self._timestamp = ''          # HH:MM:SS KST
        self._tick_history = deque(maxlen=600)  # (ts_str, price) — ~10 min at 1/sec
        self._callbacks = []
        self._connected = False
        self._should_run = False
        self._thread = None
        self._loop = None
        self._reconnect_count = 0

    @property
    def connected(self):
        return self._connected

    @property
    def price(self):
        return self._price

    @property
    def prev_price(self):
        return self._prev_price

    @property
    def timestamp(self):
        return self._timestamp

    def on_tick(self, callback):
        """Register callback: fn(price, timestamp_str)."""
        self._callbacks.append(callback)

    def remove_callback(self, callback):
        self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def get_price(self):
        """Get latest KRW/USDT price."""
        return self._price

    def get_tick_history(self, limit=120):
        """Get recent ticks for charting. Returns list of (ts_str, price)."""
        hist = list(self._tick_history)
        return hist[-limit:]

    def start(self):
        """Start websocket in background thread."""
        if self._should_run:
            return
        self._should_run = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info('Upbit FX websocket starting...')

    def stop(self):
        self._should_run = False
        self._connected = False

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self):
        import websockets

        while self._should_run:
            try:
                async with websockets.connect(WS_URL, ping_interval=30) as ws:
                    self._connected = True
                    self._reconnect_count = 0
                    logger.info('Upbit websocket connected')

                    await ws.send(SUBSCRIBE_MSG)

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
                logger.warning(f'Upbit WS error: {e}. Reconnecting in {wait}s...')
                await asyncio.sleep(wait)

        self._connected = False

    def _handle_message(self, raw_msg):
        try:
            if isinstance(raw_msg, bytes):
                data = json.loads(raw_msg.decode('utf-8'))
            else:
                data = json.loads(raw_msg)

            price = data.get('trade_price')
            ts_ms = data.get('trade_timestamp') or data.get('timestamp')
            if not price:
                return

            # Timestamp in KST
            if ts_ms:
                ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc) + KST
                ts_str = ts.strftime('%H:%M:%S')
            else:
                ts_str = datetime.now().strftime('%H:%M:%S')

            self._prev_price = self._price
            self._price = float(price)
            self._timestamp = ts_str

            self._tick_history.append((ts_str, self._price))

            for cb in self._callbacks:
                try:
                    cb(self._price, ts_str)
                except Exception as e:
                    logger.error(f'Tick callback error: {e}')

        except Exception as e:
            logger.error(f'Message parse error: {e}')


# Singleton
fx_stream = FXStream()
