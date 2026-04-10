"""Paper Trade — auto-trading mean reversion with live websocket data.

Simulates a virtual 한국투자증권 account. Runs mean reversion automatically
using the Upbit KRW-USDT websocket. Buys/sells on its own based on
parameters from optimal_params.json.

All data persists across restarts via NiceGUI storage.
"""

import os
import json
from collections import deque

from nicegui import ui, app
from datetime import datetime
from projects.rich_man.fx_data import CURRENCY_META, fetch_upbit_crix
from projects.rich_man.fx_ws import fx_stream

# Load optimal params
_PARAMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'optimal_params.json')
_PARAMS = {}
if os.path.exists(_PARAMS_FILE):
    with open(_PARAMS_FILE) as f:
        _PARAMS = json.load(f)

# Defaults (golden params or from optimizer)
_DEF = {
    'ma_period': _PARAMS.get('ma_period', 6),
    'buy_dip_pct': _PARAMS.get('buy_dip_pct', 0.15),
    'sell_gain_pct': _PARAMS.get('sell_gain_pct', 0.50),
    'stop_loss_pct': 0.30,
    'max_trades_day': _PARAMS.get('max_trades_day', 0),
    'max_vol_pct': _PARAMS.get('max_vol_pct', 0.20),
    'cooldown_hrs': _PARAMS.get('cooldown_hrs', 3),
    'seed': 1_000_000,
    'wudae_pct': 90,
}

BASE_SPREAD_PCT = 0.25


def _new_account(name='Default', seed=None):
    """Create a fresh account dict."""
    s = seed or _DEF['seed']
    return {
        'name': name,
        'balance_krw': s,
        'units_usd': 0.0,
        'cost_basis': 0.0,
        'realized_pnl': 0.0,
        'trades': [],
        'daily_trades': {},
        'cooldown_until': '',
        'params': dict(_DEF),
        'running': False,
        'initial_balance': s,
    }


def _get_profiles():
    """Get all profiles. Returns dict of {name: account_data}."""
    app.storage.general.setdefault('paper_profiles', {
        'Default': _new_account('Default'),
    })
    app.storage.general.setdefault('paper_active_profile', 'Default')
    return app.storage.general['paper_profiles']


def _get_active_name():
    return app.storage.general.get('paper_active_profile', 'Default')


def _get_paper_storage():
    """Get active profile's storage."""
    profiles = _get_profiles()
    name = _get_active_name()
    if name not in profiles:
        profiles[name] = _new_account(name)
    return profiles[name]


def _save(store):
    profiles = _get_profiles()
    name = _get_active_name()
    profiles[name] = store
    app.storage.general['paper_profiles'] = profiles


def build_paper_trade_tab():
    """Auto-trading paper trade UI."""
    store = _get_paper_storage()
    params = store['params']
    spread = BASE_SPREAD_PCT * (1 - params.get('wudae_pct', 90) / 100) / 100

    # Pre-load MA history from Bithumb so trading starts immediately
    price_history = deque(maxlen=200)
    from projects.rich_man.fx_data import fetch_intraday_history
    _preload = fetch_intraday_history(interval='1h')
    if _preload:
        ma_needed = params.get('ma_period', 6)
        for _, p in _preload[-(ma_needed + 10):]:
            price_history.append(p)

    with ui.column().classes('w-full gap-4 p-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between'):
            with ui.column().classes('gap-0'):
                ui.label('PAPER TRADE').classes('text-3xl font-extrabold').style(
                    'background: linear-gradient(135deg, #00e676 0%, #448aff 100%); '
                    '-webkit-background-clip: text; -webkit-text-fill-color: transparent;'
                )
                ui.label('Auto-trading mean reversion · Virtual 한국투자증권 account').classes(
                    'mono text-xs text-gray-500'
                )

            # Profile selector
            with ui.row().classes('items-end gap-2'):
                profiles = _get_profiles()
                profile_select = ui.select(
                    options=list(profiles.keys()),
                    value=_get_active_name(),
                    label='Profile',
                ).props('dense outlined').style('min-width: 150px;')

                new_name_input = ui.input(placeholder='New profile').props('dense outlined').style('max-width: 120px;')

                def add_profile():
                    name = new_name_input.value.strip()
                    if not name:
                        ui.notify('Enter a profile name', type='warning')
                        return
                    profiles = _get_profiles()
                    if name in profiles:
                        ui.notify('Profile already exists', type='warning')
                        return
                    profiles[name] = _new_account(name)
                    app.storage.general['paper_profiles'] = profiles
                    profile_select.options = list(profiles.keys())
                    profile_select.value = name
                    profile_select.update()
                    new_name_input.value = ''
                    ui.notify(f'Profile "{name}" created', type='positive')

                ui.button(icon='add', on_click=add_profile).props('dense flat color=green')

                def switch_profile(e):
                    app.storage.general['paper_active_profile'] = e.value
                    ui.notify(f'Switched to "{e.value}" — reload page to apply', type='info')

                profile_select.on_value_change(switch_profile)

                def delete_profile():
                    name = _get_active_name()
                    if name == 'Default':
                        ui.notify('Cannot delete Default profile', type='warning')
                        return
                    profiles = _get_profiles()
                    del profiles[name]
                    app.storage.general['paper_profiles'] = profiles
                    app.storage.general['paper_active_profile'] = 'Default'
                    ui.notify(f'Deleted "{name}" — reload page', type='info')

                ui.button(icon='delete', on_click=delete_profile).props('dense flat color=red-4')

        # ── Account Summary ──
        with ui.row().classes('w-full gap-3 flex-wrap'):
            balance_card = _card('KRW Balance', '', '#888')
            position_card = _card('USD Position', '', '#448aff')
            value_card = _card('Total Value', '', '#ffd740')
            pnl_card = _card('Total P&L', '', '#888')
            status_card = _card('Status', 'STOPPED', '#ff1744')

        # ── Controls ──
        with ui.card().classes('w-full p-4').style('background: #12121a; border: 1px solid #2a2a3a;'):
            with ui.row().classes('w-full items-center justify-between'):
                ui.label('TRADING ENGINE').classes('section-title')
                with ui.row().classes('gap-2 items-center'):
                    market_hours_only = ui.switch('Market hours only (09:00-15:30 KST)', value=True).props(
                        'dense color=amber'
                    )
                    start_btn = ui.button('Start', icon='play_arrow', on_click=lambda: start_trading()).props(
                        'color=green dense'
                    )
                    stop_btn = ui.button('Stop', icon='stop', on_click=lambda: stop_trading()).props(
                        'color=red dense'
                    )

            # Emergency kill switch
            ui.label('EMERGENCY KILL SWITCH').classes('mono text-xs text-gray-500 mt-3')
            with ui.row().classes('w-full items-end gap-3 flex-wrap'):
                kill_drop_pct = ui.number(label='Kill if drop %', value=1.5, step=0.1, format='%.1f').props(
                    'dense outlined').style('max-width: 110px;')
                kill_window_min = ui.number(label='Within (min)', value=30, format='%.0f').props(
                    'dense outlined').style('max-width: 100px;')
                kill_enabled = ui.switch('Enabled', value=True).props('dense color=red')
                ui.label('Auto-stops + sells position if price crashes').classes('mono text-xs text-gray-600 self-center')

            kill_status = ui.label('').classes('mono text-xs')

            # Parameters display
            opt_date = _PARAMS.get('optimized_at', 'manual')
            ui.label(f'Parameters from optimizer ({opt_date})').classes('mono text-xs text-gray-500 mt-2')

            with ui.row().classes('w-full gap-3 flex-wrap'):
                _param_chip(f'MA: {params.get("ma_period", 6)}h')
                _param_chip(f'Buy Dip: {params.get("buy_dip_pct", 0.15):.2f}%')
                _param_chip(f'Sell Gain: {params.get("sell_gain_pct", 0.50):.2f}%')
                _param_chip(f'SL: {params.get("stop_loss_pct", 0.30):.2f}%')
                _param_chip(f'Max Vol: {params.get("max_vol_pct", 0.20):.2f}%')
                _param_chip(f'Cooldown: {params.get("cooldown_hrs", 3)}h')
                _param_chip(f'우대율: {params.get("wudae_pct", 90)}%')

            # Live signal display
            with ui.row().classes('w-full items-center gap-4 mt-2'):
                signal_icon = ui.icon('hourglass_empty').style('font-size: 28px; color: #888;')
                signal_label = ui.label('Waiting for data...').classes('mono text-sm')
                price_label = ui.label('').classes('mono text-sm text-gray-500')
                ma_label = ui.label('').classes('mono text-xs text-gray-600')

        ui.separator()

        # ── Live Trade Feed ──
        ui.label('LIVE TRADES').classes('section-title')
        feed_container = ui.column().classes('w-full gap-1').style('max-height: 400px; overflow-y: auto;')

        # ── Trade History ──
        ui.separator()
        ui.label('TRADE HISTORY').classes('section-title')
        history_container = ui.column().classes('w-full gap-1')

        # ── Account Controls ──
        ui.separator()
        with ui.row().classes('w-full items-end gap-3'):
            seed_input = ui.number(
                label='Seed Money (KRW)', value=store['initial_balance'], format='%.0f',
            ).props('dense outlined').style('max-width: 200px;')

            def reset_account():
                new_seed = seed_input.value or _DEF['seed']
                store = _get_paper_storage()
                store['balance_krw'] = new_seed
                store['units_usd'] = 0.0
                store['cost_basis'] = 0.0
                store['realized_pnl'] = 0.0
                store['trades'] = []
                store['daily_trades'] = {}
                store['cooldown_until'] = ''
                store['running'] = False
                store['initial_balance'] = new_seed
                _save(store)
                update_summary()
                render_history()
                feed_container.clear()
                ui.notify('Account reset', type='info')

            ui.button('Reset Account', icon='restart_alt', on_click=reset_account).props('flat color=red-4 size=sm')

        # ── Update functions ──
        def update_summary():
            store = _get_paper_storage()
            balance = store['balance_krw']
            units = store['units_usd']
            cost = store['cost_basis']
            realized = store['realized_pnl']
            initial = store['initial_balance']

            # Get current price for valuation
            current_price = fx_stream.price or 0
            position_value = units * current_price
            total_value = balance + position_value
            unrealized = position_value - cost if units > 0 else 0
            total_pnl = realized + unrealized
            pnl_pct = (total_pnl / initial * 100) if initial else 0

            balance_card['value'].text = f'\u20a9{balance:,.0f}'
            if units > 0:
                position_card['value'].text = f'${units:,.2f} (\u20a9{position_value:,.0f})'
                position_card['value'].style('color: #448aff;')
            else:
                position_card['value'].text = 'No position'
                position_card['value'].style('color: #888;')
            value_card['value'].text = f'\u20a9{total_value:,.0f}'

            pnl_color = '#00e676' if total_pnl >= 0 else '#ff1744'
            pnl_card['value'].text = f'\u20a9{total_pnl:+,.0f} ({pnl_pct:+.2f}%)'
            pnl_card['value'].style(f'color: {pnl_color};')

            is_running = store.get('running', False)
            status_card['value'].text = 'RUNNING' if is_running else 'STOPPED'
            status_card['value'].style(f'color: {"#00e676" if is_running else "#ff1744"};')

        def render_history():
            history_container.clear()
            store = _get_paper_storage()
            trades = store.get('trades', [])
            if not trades:
                with history_container:
                    ui.label('No trades yet').classes('text-gray-500')
                return

            with history_container:
                with ui.row().classes('w-full px-2 py-1').style('border-bottom: 1px solid #2a2a3a;'):
                    for h, w in [('Time', '150px'), ('Type', '50px'), ('Rate', '90px'),
                                 ('Units', '80px'), ('KRW', '100px'), ('P&L', '100px'), ('Signal', '150px')]:
                        ui.label(h).classes('mono text-xs text-gray-500').style(f'width: {w};')

                for trade in reversed(trades[-100:]):
                    type_color = '#00e676' if trade['type'] == 'BUY' else '#ff1744'
                    with ui.row().classes('w-full px-2 py-1').style('border-bottom: 1px solid #1a1a2a;'):
                        ui.label(trade['time']).classes('mono text-xs text-gray-400').style('width: 150px;')
                        ui.label(trade['type']).classes('mono text-xs font-bold').style(f'width: 50px; color: {type_color};')
                        ui.label(f'\u20a9{trade["rate"]:,.2f}').classes('mono text-xs').style('width: 90px;')
                        ui.label(f'{trade["units"]:,.2f}').classes('mono text-xs').style('width: 80px;')
                        ui.label(f'\u20a9{trade["amount"]:,.0f}').classes('mono text-xs').style('width: 100px;')
                        profit = trade.get('profit')
                        if profit is not None:
                            p_color = '#00e676' if profit >= 0 else '#ff1744'
                            ui.label(f'\u20a9{profit:+,.0f}').classes('mono text-xs').style(f'width: 100px; color: {p_color};')
                        else:
                            ui.label('\u2014').classes('mono text-xs text-gray-600').style('width: 100px;')
                        ui.label(trade.get('signal', '')).classes('mono text-xs text-gray-500').style('width: 150px;')

        def add_feed_entry(text, color='#888'):
            """Add a line to the live trade feed."""
            now = datetime.now().strftime('%H:%M:%S')
            with feed_container:
                ui.label(f'{now} {text}').classes('mono text-xs').style(f'color: {color};')

        # ── Trading Engine ──
        def start_trading():
            store = _get_paper_storage()
            store['running'] = True
            _save(store)
            update_summary()
            add_feed_entry('Trading engine started', '#00e676')
            ui.notify('Trading started', type='positive')

        def stop_trading():
            store = _get_paper_storage()
            store['running'] = False
            _save(store)
            update_summary()
            add_feed_entry('Trading engine stopped', '#ff1744')
            ui.notify('Trading stopped', type='warning')

        def trading_tick(price, ts_str):
            """Called every websocket tick. Runs the mean reversion logic."""
            store = _get_paper_storage()
            if not store.get('running', False):
                return

            # Market hours check: only trade 09:00-15:30 KST weekdays
            now = datetime.now()
            if market_hours_only.value:
                weekday = now.weekday()  # 0=Mon, 6=Sun
                hour_min = now.hour * 100 + now.minute
                if weekday >= 5:  # Saturday/Sunday
                    signal_icon.style('color: #555; font-size: 28px;')
                    signal_label.text = 'Market closed (weekend)'
                    return
                if hour_min < 900 or hour_min > 1530:
                    signal_icon.style('color: #555; font-size: 28px;')
                    signal_label.text = f'Market closed (open 09:00-15:30 KST)'
                    return

            price_history.append(price)

            # Emergency kill switch: detect flash crash
            if kill_enabled.value and len(price_history) >= 2:
                window = int(kill_window_min.value or 30)
                # Each tick is ~1-2 seconds, but price_history is populated once per tick
                # Use the last N entries where N approximates the window
                lookback = min(len(price_history), window * 30)  # ~30 ticks per minute
                if lookback >= 2:
                    window_prices = list(price_history)[-lookback:]
                    peak_in_window = max(window_prices)
                    drop_pct = (peak_in_window - price) / peak_in_window * 100
                    threshold = kill_drop_pct.value or 1.5

                    if drop_pct >= threshold:
                        # EMERGENCY: force sell if holding, then stop
                        store = _get_paper_storage()
                        units = store['units_usd']
                        if units > 0:
                            bid = price * (1 - spread / 2)
                            proceeds = units * bid
                            profit = proceeds - store['cost_basis']
                            store['balance_krw'] = proceeds
                            store['units_usd'] = 0.0
                            store['cost_basis'] = 0.0
                            store['realized_pnl'] = store.get('realized_pnl', 0) + profit
                            store['trades'].append({
                                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'type': 'SELL', 'rate': price,
                                'units': round(units, 4), 'amount': round(proceeds, 0),
                                'profit': round(profit, 0),
                                'signal': f'EMERGENCY SELL — crash {drop_pct:.1f}% in {window}min',
                            })
                            add_feed_entry(
                                f'EMERGENCY SELL ${units:,.2f} @ \u20a9{price:,.0f} — crash {drop_pct:.1f}%',
                                '#ff1744',
                            )

                        store['running'] = False
                        _save(store)

                        signal_icon.style('color: #ff1744; font-size: 28px;')
                        signal_label.text = f'KILLED — {drop_pct:.1f}% crash detected in {window}min'
                        kill_status.text = f'Triggered at {datetime.now().strftime("%H:%M:%S")} — price dropped {drop_pct:.1f}%'
                        kill_status.style('color: #ff1744;')
                        add_feed_entry(
                            f'KILL SWITCH — {drop_pct:.1f}% crash in {window}min. Trading stopped.',
                            '#ff1744',
                        )
                        update_summary()
                        render_history()
                        return

            ma_period = params.get('ma_period', 6)

            if len(price_history) < ma_period:
                return

            # Update signal display
            ma_val = sum(list(price_history)[-ma_period:]) / ma_period
            dev = (price - ma_val) / ma_val * 100
            price_label.text = f'\u20a9{price:,.0f}'
            ma_label.text = f'MA{ma_period}h: \u20a9{ma_val:,.2f} | Dev: {dev:+.3f}%'

            today = datetime.now().strftime('%Y-%m-%d')
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            bid = price * (1 - spread / 2)
            ask = price * (1 + spread / 2)

            # Cooldown check
            cooldown = store.get('cooldown_until', '')
            if cooldown and now_str < cooldown:
                signal_icon.style('color: #ff9100; font-size: 28px;')
                signal_label.text = f'Cooldown until {cooldown[11:19]}'
                return

            # Max trades/day check
            max_t = params.get('max_trades_day', 0)
            daily_count = store.get('daily_trades', {}).get(today, 0)
            if max_t and daily_count >= max_t:
                signal_icon.style('color: #888; font-size: 28px;')
                signal_label.text = f'Max trades reached ({daily_count}/{max_t})'
                return

            # Volatility check
            max_vol = params.get('max_vol_pct', 0)
            if max_vol and len(price_history) >= 12:
                recent = list(price_history)[-12:]
                rets = [(recent[i] - recent[i-1]) / recent[i-1] * 100 for i in range(1, len(recent))]
                if rets:
                    mean_r = sum(rets) / len(rets)
                    vol = (sum((r - mean_r) ** 2 for r in rets) / len(rets)) ** 0.5
                    if vol > max_vol:
                        signal_icon.style('color: #ff9100; font-size: 28px;')
                        signal_label.text = f'Vol too high ({vol:.3f}% > {max_vol}%)'
                        return

            units = store['units_usd']
            balance = store['balance_krw']
            cost_basis = store['cost_basis']

            # WAITING: buy on dip
            if units == 0 and balance > 0:
                buy_dip = params.get('buy_dip_pct', 0.15)
                if dev <= -buy_dip:
                    new_units = balance / ask
                    store['units_usd'] = new_units
                    store['cost_basis'] = balance
                    store['balance_krw'] = 0
                    signal_text = f'MA{ma_period}h dev {dev:+.3f}%'

                    store['trades'].append({
                        'time': now_str, 'type': 'BUY', 'rate': price,
                        'units': round(new_units, 4), 'amount': round(balance, 0),
                        'signal': signal_text,
                    })
                    _save(store)

                    signal_icon.style('color: #00e676; font-size: 28px;')
                    signal_label.text = f'BOUGHT ${new_units:,.2f} at \u20a9{price:,.2f}'
                    add_feed_entry(f'BUY ${new_units:,.2f} @ \u20a9{price:,.2f} ({signal_text})', '#00e676')
                    update_summary()
                    render_history()
                else:
                    signal_icon.style('color: #ffd740; font-size: 28px;')
                    signal_label.text = f'Waiting for dip (dev: {dev:+.3f}%, need ≤ -{buy_dip}%)'

            # HOLDING: sell on gain or stop-loss
            elif units > 0:
                avg_cost = cost_basis / units
                gain = (bid - avg_cost) / avg_cost * 100

                sell_gain = params.get('sell_gain_pct', 0.50)
                sl_pct = params.get('stop_loss_pct', 0.30)

                sell_signal = None
                is_sl = False
                if gain >= sell_gain:
                    sell_signal = f'TP +{gain:.3f}%'
                elif sl_pct and gain <= -sl_pct:
                    sell_signal = f'SL {gain:.3f}%'
                    is_sl = True

                if sell_signal:
                    proceeds = units * bid
                    profit = proceeds - cost_basis

                    store['balance_krw'] = proceeds
                    store['units_usd'] = 0.0
                    store['cost_basis'] = 0.0
                    store['realized_pnl'] = store.get('realized_pnl', 0) + profit

                    daily_trades = store.get('daily_trades', {})
                    daily_trades[today] = daily_trades.get(today, 0) + 1
                    store['daily_trades'] = daily_trades

                    if is_sl:
                        cooldown_hrs = params.get('cooldown_hrs', 3)
                        if cooldown_hrs:
                            from datetime import timedelta
                            cool_until = datetime.now() + timedelta(hours=cooldown_hrs)
                            store['cooldown_until'] = cool_until.strftime('%Y-%m-%d %H:%M:%S')

                    store['trades'].append({
                        'time': now_str, 'type': 'SELL', 'rate': price,
                        'units': round(units, 4), 'amount': round(proceeds, 0),
                        'profit': round(profit, 0), 'signal': sell_signal,
                    })
                    _save(store)

                    p_color = '#00e676' if profit >= 0 else '#ff1744'
                    signal_icon.style(f'color: {p_color}; font-size: 28px;')
                    signal_label.text = f'SOLD ${units:,.2f} at \u20a9{price:,.2f} ({sell_signal})'
                    add_feed_entry(
                        f'SELL ${units:,.2f} @ \u20a9{price:,.2f} {sell_signal} P&L: \u20a9{profit:+,.0f}',
                        p_color,
                    )
                    update_summary()
                    render_history()
                else:
                    signal_icon.style('color: #448aff; font-size: 28px;')
                    signal_label.text = f'Holding ${units:,.2f} | gain: {gain:+.3f}% (TP: +{sell_gain}% / SL: -{sl_pct}%)'

        # Register websocket callback
        fx_stream.start()
        fx_stream.on_tick(trading_tick)

        # Periodic summary update (every 2s)
        ui.timer(2.0, update_summary)

        # Initial render
        update_summary()
        render_history()

        # Auto-start if was running before restart
        if store.get('running', False):
            add_feed_entry('Resumed from previous session', '#ffd740')


def _card(label, initial_value, color):
    """Account summary card. Returns dict with 'value' label for updating."""
    with ui.card().classes('p-3').style(
        'min-width: 140px; flex: 1; background: #12121a; border: 1px solid #2a2a3a;'
    ):
        ui.label(label).classes('mono text-xs text-gray-500')
        value_label = ui.label(initial_value).style(f'color: {color}; font-weight: 700; font-size: 15px;')
    return {'value': value_label}


def _param_chip(text):
    ui.badge(text).props('color="dark" text-color="amber"').classes('text-xs')
