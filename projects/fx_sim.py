"""FX Paper Trading Simulation — models 한국투자증권 FX environment.

Cost model:
  - Base spread: 0.25% (한투 standard for 해외주식 환전)
  - 우대율: configurable 0-100% (reduces spread)
  - Effective spread = base_spread * (1 - 우대율/100)
  - No additional commission
  - Bid = mid_rate * (1 - effective_spread/2)
  - Ask = mid_rate * (1 + effective_spread/2)
"""

from nicegui import ui, app
from datetime import datetime
from projects.fx_data import fetch_latest, fetch_upbit_crix, CURRENCY_META
from projects.fx_ws import fx_stream
from projects.fx_signals import compute_signals, backtest

BASE_SPREAD_PCT = 0.25  # 한투 standard
DEFAULT_BALANCE_KRW = 1_000_000  # ₩1M starting balance

TRADEABLE_CURRENCIES = ['USD', 'EUR', 'JPY', 'GBP', 'CNY', 'CAD', 'AUD', 'CHF']


def _get_storage():
    """Get or init simulation storage."""
    app.storage.general.setdefault('fx_sim', {
        'balance_krw': DEFAULT_BALANCE_KRW,
        'positions': {},       # currency -> {units, avg_cost_krw, total_spent_krw}
        'trades': [],          # [{id, type, currency, units, rate, cost_krw, spread_cost, timestamp}, ...]
        'settings': {
            'wudae_pct': 90,   # 우대율 default 90%
            'initial_balance': DEFAULT_BALANCE_KRW,
        },
    })
    return app.storage.general['fx_sim']


def _get_mid_rate(currency):
    """Get current mid-market rate (KRW per 1 unit).
    USD: live websocket price (~1-2s), others: Upbit CRIX (~30s).
    """
    # USD: prefer live websocket (USDT proxy)
    if currency == 'USD' and fx_stream.price:
        return fx_stream.price
    # Others: Upbit CRIX (서울외국환중개)
    crix = fetch_upbit_crix()
    if crix and currency in crix:
        return crix[currency].get('basePrice', 0)
    # Fallback
    data = fetch_latest('KRW')
    if data and 'rates' in data:
        rate = data['rates'].get(currency)
        if rate:
            return 1 / rate
    return 0


def _calc_spread(wudae_pct):
    """Calculate effective spread % given 우대율."""
    return BASE_SPREAD_PCT * (1 - wudae_pct / 100)


def _bid_ask(mid_rate, wudae_pct):
    """Return (bid, ask) prices given mid-rate and 우대율.
    Bid = price you get when SELLING foreign currency (lower).
    Ask = price you pay when BUYING foreign currency (higher).
    """
    spread = _calc_spread(wudae_pct)
    bid = mid_rate * (1 - spread / 200)
    ask = mid_rate * (1 + spread / 200)
    return bid, ask


def build_simulation_tab():
    """Paper trading simulation UI."""
    sim = _get_storage()
    settings = sim['settings']

    with ui.column().classes('w-full gap-4 p-4'):
        # ── Header ──
        ui.label('PAPER TRADING').classes('text-3xl font-extrabold').style(
            'background: linear-gradient(135deg, #448aff 0%, #00e676 100%); '
            '-webkit-background-clip: text; -webkit-text-fill-color: transparent;'
        )
        ui.label('Simulated 한국투자증권 FX environment · No real money').classes(
            'mono text-xs text-gray-500 -mt-2'
        )

        # ── Signal Panel ──
        _build_signal_panel()

        ui.separator()

        # ── Account Summary ──
        summary_container = ui.column().classes('w-full gap-2')

        def render_summary():
            summary_container.clear()
            sim = _get_storage()
            balance = sim['balance_krw']
            positions = sim['positions']
            wudae = settings['wudae_pct']

            # Calculate total portfolio value
            total_position_value = 0
            unrealized_pnl = 0
            for cur, pos in positions.items():
                if pos['units'] <= 0:
                    continue
                mid = _get_mid_rate(cur)
                if mid:
                    current_value = pos['units'] * mid
                    total_position_value += current_value
                    unrealized_pnl += current_value - pos['total_spent_krw']

            total_value = balance + total_position_value
            initial = settings['initial_balance']
            total_pnl = total_value - initial
            total_pnl_pct = (total_pnl / initial * 100) if initial else 0
            pnl_color = '#00e676' if total_pnl >= 0 else '#ff1744'

            with summary_container:
                # Account cards
                with ui.row().classes('w-full gap-3 flex-wrap'):
                    _summary_card('Total Value', f'\u20a9{total_value:,.0f}', '#ffd740')
                    _summary_card('KRW Balance', f'\u20a9{balance:,.0f}', '#888')
                    _summary_card('Positions Value', f'\u20a9{total_position_value:,.0f}', '#448aff')
                    _summary_card(
                        'Total P&L',
                        f'{"+" if total_pnl >= 0 else ""}\u20a9{total_pnl:,.0f} ({total_pnl_pct:+.2f}%)',
                        pnl_color,
                    )
                    _summary_card('우대율', f'{wudae}%', '#00e676' if wudae >= 90 else '#ffd740')
                    _summary_card('Effective Spread', f'{_calc_spread(wudae):.3f}%', '#888')

        render_summary()

        ui.separator()

        # ── Settings ──
        with ui.row().classes('w-full items-end gap-3'):
            wudae_slider = ui.slider(
                min=0, max=100, step=5, value=settings['wudae_pct'],
            ).props('label-always color=amber').classes('flex-grow')
            wudae_label = ui.label(f"우대율: {settings['wudae_pct']}%").classes('mono text-sm font-bold').style('min-width: 100px;')

            def on_wudae_change(e):
                settings['wudae_pct'] = e.value
                sim['settings'] = settings
                app.storage.general['fx_sim'] = sim
                wudae_label.text = f"우대율: {e.value}%"
                render_summary()
                render_order_panel()

            wudae_slider.on_value_change(on_wudae_change)

        ui.separator()

        # ── Order Entry ──
        ui.label('PLACE ORDER').classes('section-title')

        order_container = ui.column().classes('w-full')

        def render_order_panel():
            order_container.clear()
            wudae = settings['wudae_pct']

            with order_container:
                with ui.card().classes('w-full p-4').style(
                    'background: #12121a; border: 1px solid #2a2a3a;'
                ):
                    with ui.row().classes('w-full items-end gap-3 flex-wrap'):
                        order_currency = ui.select(
                            options={c: f'{CURRENCY_META.get(c, ("","",""))[2]} {c}' for c in TRADEABLE_CURRENCIES},
                            value='USD', label='Currency',
                        ).props('dense outlined').classes('text-sm').style('min-width: 150px;')

                        order_type = ui.select(
                            options={'buy': 'BUY (KRW → FX)', 'sell': 'SELL (FX → KRW)'},
                            value='buy', label='Order Type',
                        ).props('dense outlined').classes('text-sm').style('min-width: 180px;')

                        order_amount = ui.number(
                            label='Amount (KRW to spend / FX units to sell)',
                            value=1000000, format='%.0f',
                        ).props('dense outlined').classes('flex-grow')

                    # Live quote display — persistent labels, no DOM rebuild
                    with ui.row().classes('w-full gap-4 mt-2'):
                        with ui.column().classes('gap-0'):
                            ui.label('Mid Rate').classes('mono text-xs text-gray-500')
                            mid_lbl = ui.label('--').classes('mono font-bold')
                        with ui.column().classes('gap-0'):
                            ui.label('Ask (buy)').classes('mono text-xs text-gray-500')
                            ask_lbl = ui.label('--').classes('mono font-bold').style('color: #ff1744;')
                        with ui.column().classes('gap-0'):
                            ui.label('Bid (sell)').classes('mono text-xs text-gray-500')
                            bid_lbl = ui.label('--').classes('mono font-bold').style('color: #00e676;')
                        with ui.column().classes('gap-0'):
                            ui.label('Spread').classes('mono text-xs text-gray-500')
                            spread_lbl = ui.label('--').classes('mono font-bold').style('color: #ffd740;')
                        preview_lbl = ui.label('').classes('mono text-sm text-gray-400 self-center')

                    def update_quote():
                        cur = order_currency.value
                        mid = _get_mid_rate(cur)
                        if not mid:
                            mid_lbl.text = 'N/A'
                            ask_lbl.text = 'N/A'
                            bid_lbl.text = 'N/A'
                            preview_lbl.text = ''
                            return

                        bid, ask = _bid_ask(mid, wudae)
                        mid_lbl.text = f'\u20a9{mid:,.2f}'
                        ask_lbl.text = f'\u20a9{ask:,.2f}'
                        bid_lbl.text = f'\u20a9{bid:,.2f}'
                        spread_lbl.text = f'{_calc_spread(wudae):.3f}%'

                        amount = order_amount.value or 0
                        if order_type.value == 'buy' and amount > 0:
                            units = amount / ask
                            cost = amount - (units * mid)
                            preview_lbl.text = f'\u2192 {units:,.2f} {cur} (spread: \u20a9{cost:,.0f})'
                        elif order_type.value == 'sell' and amount > 0:
                            proceeds = amount * bid
                            cost = (amount * mid) - proceeds
                            preview_lbl.text = f'\u2192 \u20a9{proceeds:,.0f} (spread: \u20a9{cost:,.0f})'
                        else:
                            preview_lbl.text = ''

                    for widget in [order_currency, order_type, order_amount]:
                        widget.on_value_change(lambda _: update_quote())
                    update_quote()

                    # Auto-refresh quotes: USD every 2s (websocket), others every 30s
                    def _auto_refresh_quote():
                        cur = order_currency.value
                        update_quote()
                        if cur == 'USD':
                            render_summary()

                    ui.timer(2.0, _auto_refresh_quote)

                    def execute_order():
                        sim = _get_storage()
                        cur = order_currency.value
                        mid = _get_mid_rate(cur)
                        if not mid:
                            ui.notify('Rate unavailable', type='negative')
                            return

                        bid, ask = _bid_ask(mid, settings['wudae_pct'])
                        amount = order_amount.value or 0
                        if amount <= 0:
                            ui.notify('Enter a valid amount', type='warning')
                            return

                        if order_type.value == 'buy':
                            # Buy foreign currency with KRW
                            cost_krw = amount
                            if cost_krw > sim['balance_krw']:
                                ui.notify(f'Insufficient KRW balance (\u20a9{sim["balance_krw"]:,.0f})', type='negative')
                                return

                            units = cost_krw / ask
                            spread_cost = cost_krw - (units * mid)

                            sim['balance_krw'] -= cost_krw
                            pos = sim['positions'].get(cur, {'units': 0, 'avg_cost_krw': 0, 'total_spent_krw': 0})
                            pos['units'] += units
                            pos['total_spent_krw'] += cost_krw
                            pos['avg_cost_krw'] = pos['total_spent_krw'] / pos['units'] if pos['units'] else 0
                            sim['positions'][cur] = pos

                            sim['trades'].append({
                                'id': len(sim['trades']) + 1,
                                'type': 'BUY',
                                'currency': cur,
                                'units': round(units, 4),
                                'rate': round(ask, 2),
                                'cost_krw': round(cost_krw, 0),
                                'spread_cost': round(spread_cost, 0),
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            })

                            app.storage.general['fx_sim'] = sim
                            ui.notify(f'Bought {units:,.2f} {cur} at \u20a9{ask:,.2f}', type='positive')

                        else:
                            # Sell foreign currency for KRW
                            units_to_sell = amount
                            pos = sim['positions'].get(cur, {'units': 0, 'avg_cost_krw': 0, 'total_spent_krw': 0})
                            if units_to_sell > pos['units']:
                                ui.notify(f'Insufficient {cur} (have {pos["units"]:,.2f})', type='negative')
                                return

                            proceeds = units_to_sell * bid
                            spread_cost = (units_to_sell * mid) - proceeds
                            cost_basis = (units_to_sell / pos['units']) * pos['total_spent_krw'] if pos['units'] else 0

                            sim['balance_krw'] += proceeds
                            pos['units'] -= units_to_sell
                            pos['total_spent_krw'] -= cost_basis
                            if pos['units'] <= 0.001:
                                pos = {'units': 0, 'avg_cost_krw': 0, 'total_spent_krw': 0}
                            else:
                                pos['avg_cost_krw'] = pos['total_spent_krw'] / pos['units']
                            sim['positions'][cur] = pos

                            sim['trades'].append({
                                'id': len(sim['trades']) + 1,
                                'type': 'SELL',
                                'currency': cur,
                                'units': round(units_to_sell, 4),
                                'rate': round(bid, 2),
                                'cost_krw': round(proceeds, 0),
                                'spread_cost': round(spread_cost, 0),
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            })

                            app.storage.general['fx_sim'] = sim
                            ui.notify(f'Sold {units_to_sell:,.2f} {cur} at \u20a9{bid:,.2f}', type='positive')

                        render_summary()
                        render_positions()
                        render_trades()
                        update_quote()

                    with ui.row().classes('w-full gap-2 mt-2'):
                        ui.button('Execute Order', icon='swap_horiz', on_click=execute_order).props(
                            'color=amber text-color=black'
                        )

        render_order_panel()

        ui.separator()

        # ── Open Positions ──
        ui.label('OPEN POSITIONS').classes('section-title')
        positions_container = ui.column().classes('w-full gap-2')

        def render_positions():
            positions_container.clear()
            sim = _get_storage()
            positions = sim['positions']
            has_positions = False

            with positions_container:
                for cur, pos in positions.items():
                    if pos['units'] <= 0.001:
                        continue
                    has_positions = True
                    mid = _get_mid_rate(cur)
                    current_value = pos['units'] * mid if mid else 0
                    pnl = current_value - pos['total_spent_krw']
                    pnl_pct = (pnl / pos['total_spent_krw'] * 100) if pos['total_spent_krw'] else 0
                    pnl_color = '#00e676' if pnl >= 0 else '#ff1744'
                    meta = CURRENCY_META.get(cur, ('', '', ''))

                    with ui.card().classes('w-full p-3').style(
                        'background: #12121a; border: 1px solid #2a2a3a;'
                    ):
                        with ui.row().classes('w-full items-center justify-between'):
                            with ui.column().classes('gap-0'):
                                ui.label(f'{meta[2]} {cur}').classes('font-bold')
                                ui.label(f'{pos["units"]:,.2f} units · Avg cost: \u20a9{pos["avg_cost_krw"]:,.2f}').classes(
                                    'mono text-xs text-gray-500'
                                )
                            with ui.column().classes('gap-0 items-end'):
                                ui.label(f'\u20a9{current_value:,.0f}').classes('font-bold').style('color: #ffd740;')
                                ui.label(
                                    f'{"+" if pnl >= 0 else ""}\u20a9{pnl:,.0f} ({pnl_pct:+.2f}%)'
                                ).style(f'color: {pnl_color}; font-weight: 600; font-size: 12px;')

                            if mid:
                                ui.label(f'Now: \u20a9{mid:,.2f}').classes('mono text-xs text-gray-500')

                if not has_positions:
                    ui.label('No open positions').classes('text-gray-500')

        render_positions()

        ui.separator()

        # ── Trade History ──
        ui.label('TRADE HISTORY').classes('section-title')
        trades_container = ui.column().classes('w-full gap-1')

        def render_trades():
            trades_container.clear()
            sim = _get_storage()
            trades = sim['trades']

            if not trades:
                with trades_container:
                    ui.label('No trades yet').classes('text-gray-500')
                return

            with trades_container:
                # Header
                with ui.row().classes('w-full px-2 py-1').style('border-bottom: 1px solid #2a2a3a;'):
                    for header, width in [('Time', '140px'), ('Type', '50px'), ('Currency', '60px'),
                                          ('Units', '80px'), ('Rate', '100px'), ('Amount', '110px'), ('Spread', '80px')]:
                        ui.label(header).classes('mono text-xs text-gray-500').style(f'width: {width};')

                for trade in reversed(trades[-50:]):  # last 50 trades
                    type_color = '#00e676' if trade['type'] == 'BUY' else '#ff1744'
                    with ui.row().classes('w-full px-2 py-1').style('border-bottom: 1px solid #1a1a2a;'):
                        ui.label(trade['timestamp']).classes('mono text-xs text-gray-400').style('width: 140px;')
                        ui.label(trade['type']).classes('mono text-xs font-bold').style(f'width: 50px; color: {type_color};')
                        ui.label(trade['currency']).classes('mono text-xs').style('width: 60px;')
                        ui.label(f'{trade["units"]:,.2f}').classes('mono text-xs').style('width: 80px;')
                        ui.label(f'\u20a9{trade["rate"]:,.2f}').classes('mono text-xs').style('width: 100px;')
                        ui.label(f'\u20a9{trade["cost_krw"]:,.0f}').classes('mono text-xs').style('width: 110px;')
                        ui.label(f'\u20a9{trade["spread_cost"]:,.0f}').classes('mono text-xs text-gray-500').style('width: 80px;')

                # Total spread costs
                total_spread = sum(t['spread_cost'] for t in trades)
                ui.label(f'Total spread costs: \u20a9{total_spread:,.0f}').classes(
                    'mono text-xs text-gray-500 mt-2'
                )

        render_trades()

        ui.separator()

        # ── Reset Account ──
        with ui.row().classes('w-full justify-between items-center'):
            reset_amount = ui.number(
                label='Starting balance (KRW)', value=settings['initial_balance'], format='%.0f',
            ).props('dense outlined').classes('').style('max-width: 200px;')

            def reset_account():
                new_balance = reset_amount.value or DEFAULT_BALANCE_KRW
                app.storage.general['fx_sim'] = {
                    'balance_krw': new_balance,
                    'positions': {},
                    'trades': [],
                    'settings': {
                        'wudae_pct': settings['wudae_pct'],
                        'initial_balance': new_balance,
                    },
                }
                ui.notify('Account reset', type='info')
                render_summary()
                render_positions()
                render_trades()

            ui.button('Reset Account', icon='restart_alt', on_click=reset_account).props(
                'flat color=red-4 size=sm'
            )


def _summary_card(label, value, color):
    with ui.card().classes('p-3').style(
        'min-width: 140px; flex: 1; background: #12121a; border: 1px solid #2a2a3a;'
    ):
        ui.label(label).classes('mono text-xs text-gray-500')
        ui.label(value).style(f'color: {color}; font-weight: 700; font-size: 15px;')


def _build_signal_panel():
    """Signal panel with live recommendation, technical chart, guidelines, and backtest."""

    SIGNAL_CONFIG = {
        'STRONG_BUY':  {'label': 'STRONG BUY',  'color': '#00e676', 'icon': 'keyboard_double_arrow_up',   'action': 'Buy 2-3x your DCA amount'},
        'BUY':         {'label': 'BUY',          'color': '#66bb6a', 'icon': 'arrow_upward',               'action': 'Buy 1.5x your DCA amount'},
        'HOLD':        {'label': 'HOLD (DCA)',   'color': '#ffd740', 'icon': 'pause',                      'action': 'Stick to normal DCA schedule'},
        'TAKE_PROFIT': {'label': 'TAKE PROFIT',  'color': '#ff9100', 'icon': 'arrow_downward',             'action': 'Sell some USD holdings'},
        'STRONG_SELL': {'label': 'STRONG SELL',   'color': '#ff1744', 'icon': 'keyboard_double_arrow_down', 'action': 'Sell aggressively'},
    }

    with ui.card().classes('w-full p-4').style('background: #12121a; border: 1px solid #2a2a3a;'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('SIGNAL').classes('section-title')
            refresh_btn = ui.button(icon='refresh', on_click=lambda: render_signal()).props('flat dense round color=amber')

        signal_container = ui.column().classes('w-full gap-2')

        def render_signal():
            signal_container.clear()
            signals = compute_signals()
            if not signals:
                with signal_container:
                    ui.label('Insufficient data for signals').classes('text-gray-500')
                return

            cfg = SIGNAL_CONFIG.get(signals['signal'], SIGNAL_CONFIG['HOLD'])

            with signal_container:
                # Big signal display
                with ui.row().classes('w-full items-center gap-4'):
                    ui.icon(cfg['icon']).style(f'color: {cfg["color"]}; font-size: 48px;')
                    with ui.column().classes('gap-0'):
                        ui.label(cfg['label']).style(
                            f'color: {cfg["color"]}; font-size: 28px; font-weight: 800;'
                        )
                        ui.label(cfg['action']).classes('mono text-sm text-gray-400')
                        ui.label(f'Score: {signals["score"]}/100').classes('mono text-xs text-gray-500')

                # Indicator cards
                with ui.row().classes('w-full gap-2 flex-wrap mt-2'):
                    _indicator_card('Rate', f'\u20a9{signals["current_rate"]:,.2f}', '#ffd740')
                    _indicator_card('20-day MA', f'\u20a9{signals["ma20"]:,.2f}', '#888')
                    _indicator_card('MA Deviation', f'{signals["ma20_dev_pct"]:+.2f}%',
                                    '#00e676' if signals['ma20_dev_pct'] < -0.5 else '#ff1744' if signals['ma20_dev_pct'] > 0.5 else '#888')
                    _indicator_card('RSI (14)', f'{signals["rsi"]:.0f}',
                                    '#00e676' if signals['rsi'] < 35 else '#ff1744' if signals['rsi'] > 65 else '#888')
                    _indicator_card('7d Change', f'{signals["roc_7d"]:+.2f}%',
                                    '#00e676' if signals['roc_7d'] < -1 else '#ff1744' if signals['roc_7d'] > 1 else '#888')
                    _indicator_card('Volatility', f'{signals["volatility"]:.3f}%', '#888')
                    _indicator_card('52w Position', f'{signals["position_in_range"]:.0f}th %ile',
                                    '#00e676' if signals['position_in_range'] < 30 else '#ff1744' if signals['position_in_range'] > 70 else '#888')

                # Reasons
                if signals['reasons']:
                    with ui.column().classes('gap-1 mt-2'):
                        ui.label('Why this signal:').classes('mono text-xs text-gray-500')
                        for reason in signals['reasons']:
                            ui.label(f'  \u2022 {reason}').classes('text-sm text-gray-400')

                # Mini chart with MA and Bollinger Bands
                _build_signal_chart(signals)

        render_signal()

    # ── Guidelines ──
    with ui.card().classes('w-full p-4 mt-2').style('background: #12121a; border: 1px solid #2a2a3a;'):
        ui.label('STRATEGY GUIDELINES').classes('section-title')

        guidelines = [
            ('DCA Baseline', '#ffd740', [
                'Set a fixed KRW amount and interval (e.g. \u20a9500,000 every 2 weeks)',
                'Execute regardless of signals — this is your foundation',
                'Never skip DCA. The whole point is removing emotion from timing.',
            ]),
            ('When to Buy More (Opportunistic)', '#00e676', [
                'BUY signal → increase DCA by 50% (e.g. \u20a9750,000 instead of \u20a9500,000)',
                'STRONG BUY signal → increase DCA by 150-200% (e.g. \u20a91,000,000-1,250,000)',
                'Best entries: rate 1%+ below 20-day MA AND RSI below 35',
                'Key events to watch: after a sharp weekly drop (>1.5%), post-BOK dovish surprise, KRW flash strength',
            ]),
            ('When to Take Profit', '#ff9100', [
                'TAKE PROFIT signal → sell 20-30% of your USD position',
                'STRONG SELL signal → sell 40-50% of position',
                'Best exits: rate 1.5%+ above 20-day MA AND RSI above 70',
                'Watch for: BOK verbal intervention warnings ("excessive volatility"), rate approaching 52-week high',
            ]),
            ('Risk Rules', '#ff1744', [
                'Never put more than 30% of your savings into FX',
                'Keep at least 3 months expenses in KRW — never trade that',
                'Max single trade: 10% of your FX allocation',
                'If your total P&L hits -5%, pause and review your strategy',
                'Don\u2019t trade 1 hour before/after FOMC, NFP, or BOK decisions',
            ]),
            ('Economic Calendar (KST)', '#448aff', [
                'BOK Rate Decision (8x/year, 10:00 KST) — biggest KRW mover',
                'Korean Export Data (1st of month, 09:00 KST) — early trade balance signal',
                'US NFP (1st Friday, 22:30/23:30 KST) — biggest USD mover',
                'US CPI (mid-month, 22:30/23:30 KST) — Fed policy signal',
                'FOMC Decision (8x/year, 03:00 KST next day) — direct USD impact',
            ]),
        ]

        for title, color, items in guidelines:
            with ui.column().classes('gap-1 mt-3'):
                ui.label(title).style(f'color: {color}; font-weight: 700; font-size: 13px;')
                for item in items:
                    ui.label(f'  \u2022 {item}').classes('text-sm text-gray-400')

    # ── Backtest ──
    with ui.card().classes('w-full p-4 mt-2').style('background: #12121a; border: 1px solid #2a2a3a;'):
        ui.label('BACKTEST — 3 Strategies Compared').classes('section-title')
        ui.label('Customize parameters and compare performance over the past year').classes(
            'mono text-xs text-gray-500 mb-1'
        )

        with ui.row().classes('w-full items-end gap-3 flex-wrap'):
            bt_seed = ui.number(
                label='Seed Money (KRW)', value=1_000_000, format='%.0f',
            ).props('dense outlined').style('max-width: 160px;')
            bt_dca_amount = ui.number(
                label='DCA per Period (KRW)', value=250_000, format='%.0f',
            ).props('dense outlined').style('max-width: 160px;')
            bt_interval = ui.select(
                options={'7': 'Weekly', '14': 'Bi-weekly', '30': 'Monthly'},
                value='7', label='Interval',
            ).props('dense outlined').style('max-width: 120px;')
            bt_lookback = ui.select(
                options={'30': '1 Month', '90': '3 Months', '180': '6 Months', '365': '1 Year'},
                value='90', label='Lookback',
            ).props('dense outlined').style('max-width: 120px;')
            bt_scalp_target = ui.number(
                label='Scalp %', value=0.5, format='%.1f',
            ).props('dense outlined').style('max-width: 90px;')
            bt_take_profit = ui.number(
                label='Take Profit %', value=2.0, format='%.1f',
            ).props('dense outlined').style('max-width: 100px;')
            bt_stop_loss = ui.number(
                label='Stop Loss %', value=3.0, format='%.1f',
            ).props('dense outlined').style('max-width: 100px;')
            bt_wudae = ui.number(
                label='우대율 %', value=90, format='%.0f',
            ).props('dense outlined').style('max-width: 90px;')
            ui.button('Run', icon='play_arrow', on_click=lambda: render_backtest()).props(
                'color=amber text-color=black dense'
            )

        # Summary line: deployment schedule + warnings
        deploy_label = ui.label('').classes('mono text-xs mt-1')

        def _update_deploy_info():
            seed = bt_seed.value or 0
            dca = bt_dca_amount.value or 0
            interval = int(bt_interval.value)
            interval_names = {'7': 'weeks', '14': 'bi-weeks', '30': 'months'}
            unit = interval_names.get(bt_interval.value, 'periods')

            if dca <= 0 or seed <= 0:
                deploy_label.text = ''
                return

            if dca > seed:
                deploy_label.text = f'DCA amount (\u20a9{dca:,.0f}) exceeds seed (\u20a9{seed:,.0f}) — will buy \u20a9{seed:,.0f} on first period only'
                deploy_label.style('color: #ff9100;')
                return

            num_buys = int(seed // dca)
            remainder = seed % dca
            total_periods = num_buys
            remainder_text = f' + \u20a9{remainder:,.0f} partial buy' if remainder > 0 else ''

            deploy_label.text = (
                f'\u20a9{seed:,.0f} \u00f7 \u20a9{dca:,.0f} = {num_buys} buys{remainder_text} '
                f'\u2192 fully deployed in {total_periods} {unit}'
            )
            deploy_label.style('color: #888;')

        for w in [bt_seed, bt_dca_amount, bt_interval]:
            w.on_value_change(lambda _: _update_deploy_info())
        _update_deploy_info()

        backtest_container = ui.column().classes('w-full gap-2 mt-2')

        def render_backtest():
            backtest_container.clear()
            result = backtest(
                dca_amount=bt_dca_amount.value or 250_000,
                dca_interval_days=int(bt_interval.value),
                scalp_target_pct=bt_scalp_target.value or 0.5,
                take_profit_pct=bt_take_profit.value or 0,
                stop_loss_pct=bt_stop_loss.value or 0,
                lookback_days=int(bt_lookback.value),
                seed_money=bt_seed.value or None,
                wudae_pct=bt_wudae.value or 90,
            )
            if not result:
                with backtest_container:
                    ui.label('Insufficient historical data for backtest').classes('text-gray-500')
                return

            dca = result['dca']
            sig = result['signal']
            sclp = result['scalp']
            cyc = result['cycle']

            with backtest_container:
                seed_text = f' · Seed: \u20a9{result["seed_money"]:,.0f}' if result.get('seed_money') else ''
                ui.label(f'Period: {result["period"]} · {result["data_points"]} data points{seed_text}').classes('mono text-xs text-gray-500')

                with ui.row().classes('w-full gap-3 mt-2 flex-wrap'):
                    # Pure DCA
                    with ui.card().classes('flex-1 p-3').style('background: #1a1a2a; border: 1px solid #2a2a3a; min-width: 200px;'):
                        ui.label('Pure DCA').classes('font-bold text-sm').style('color: #ffd740;')
                        ui.label('Buy fixed amount, hold forever').classes('text-xs text-gray-600 mb-1')
                        _bt_stat('Invested', f'\u20a9{dca["total_spent"]:,.0f}')
                        _bt_stat('USD Held', f'${dca["total_units"]:,.2f}')
                        _bt_stat('Avg Cost', f'\u20a9{dca["avg_cost"]:,.2f}')
                        _bt_stat('Value Now', f'\u20a9{dca["current_value"]:,.0f}')
                        pnl_color = '#00e676' if dca['pnl'] >= 0 else '#ff1744'
                        _bt_stat('Total P&L', f'{"+" if dca["pnl"] >= 0 else ""}\u20a9{dca["pnl"]:,.0f} ({dca["pnl_pct"]:+.2f}%)', pnl_color)
                        _render_tax_estimate(dca['pnl'], int(bt_lookback.value))
                        _bt_stat('Buys', str(dca['num_buys']))

                    # Signal DCA
                    with ui.card().classes('flex-1 p-3').style('background: #1a1a2a; border: 1px solid #2a2a3a; min-width: 200px;'):
                        ui.label('Signal-Enhanced DCA').classes('font-bold text-sm').style('color: #00e676;')
                        ui.label('Adjust buy size by signal, skip overvalued').classes('text-xs text-gray-600 mb-1')
                        _bt_stat('Invested', f'\u20a9{sig["total_spent"]:,.0f}')
                        _bt_stat('USD Held', f'${sig["total_units"]:,.2f}')
                        _bt_stat('Avg Cost', f'\u20a9{sig["avg_cost"]:,.2f}')
                        _bt_stat('Value Now', f'\u20a9{sig["current_value"]:,.0f}')
                        pnl_color = '#00e676' if sig['pnl'] >= 0 else '#ff1744'
                        _bt_stat('Total P&L', f'{"+" if sig["pnl"] >= 0 else ""}\u20a9{sig["pnl"]:,.0f} ({sig["pnl_pct"]:+.2f}%)', pnl_color)
                        _render_tax_estimate(sig['pnl'], int(bt_lookback.value))
                        _bt_stat('Buys', f'{sig["num_buys"]}')
                        _bt_stat('Skipped', f'{sig["num_skipped"]}')

                    # DCA + Scalp
                    with ui.card().classes('flex-1 p-3').style('background: #1a1a2a; border: 1px solid #2a2a3a; min-width: 200px;'):
                        ui.label('DCA + Scalp').classes('font-bold text-sm').style('color: #e040fb;')
                        ui.label('DCA baseline + sell lots at 0.5% profit').classes('text-xs text-gray-600 mb-1')
                        _bt_stat('Invested', f'\u20a9{sclp["total_spent"]:,.0f}')
                        _bt_stat('USD Held', f'${sclp["total_units"]:,.2f}')
                        _bt_stat('Avg Cost', f'\u20a9{sclp["avg_cost"]:,.2f}' if sclp['total_units'] else 'N/A')
                        _bt_stat('Value Now', f'\u20a9{sclp["current_value"]:,.0f}')
                        _bt_stat('Realized P&L', f'{"+" if sclp["realized_pnl"] >= 0 else ""}\u20a9{sclp["realized_pnl"]:,.0f}',
                                 '#00e676' if sclp['realized_pnl'] >= 0 else '#ff1744')
                        _bt_stat('Unrealized P&L', f'{"+" if sclp["unrealized_pnl"] >= 0 else ""}\u20a9{sclp["unrealized_pnl"]:,.0f}',
                                 '#00e676' if sclp['unrealized_pnl'] >= 0 else '#ff1744')
                        pnl_color = '#00e676' if sclp['pnl'] >= 0 else '#ff1744'
                        _bt_stat('Total P&L', f'{"+" if sclp["pnl"] >= 0 else ""}\u20a9{sclp["pnl"]:,.0f} ({sclp["pnl_pct"]:+.2f}%)', pnl_color)
                        _render_tax_estimate(sclp['pnl'], int(bt_lookback.value))
                        _bt_stat('Buys / Sells', f'{sclp["num_buys"]} / {sclp["num_sells"]}')

                    # Buy-Sell-Repeat
                    with ui.card().classes('flex-1 p-3').style('background: #1a1a2a; border: 1px solid #2a2a3a; min-width: 200px;'):
                        ui.label('Buy-Sell-Repeat').classes('font-bold text-sm').style('color: #00bcd4;')
                        ui.label('All-in \u2192 sell at TP \u2192 re-buy \u2192 repeat').classes('text-xs text-gray-600 mb-1')
                        _bt_stat('Seed', f'\u20a9{result.get("seed_money", 0) or 0:,.0f}')
                        _bt_stat('Cycles', f'{cyc["num_cycles"]} complete')
                        _bt_stat('USD Held', f'${cyc["total_units"]:,.2f}')
                        _bt_stat('Final Balance', f'\u20a9{cyc.get("final_balance", 0):,.0f}')
                        _bt_stat('Realized P&L', f'{"+" if cyc["realized_pnl"] >= 0 else ""}\u20a9{cyc["realized_pnl"]:,.0f}',
                                 '#00e676' if cyc['realized_pnl'] >= 0 else '#ff1744')
                        _bt_stat('Unrealized P&L', f'{"+" if cyc["unrealized_pnl"] >= 0 else ""}\u20a9{cyc["unrealized_pnl"]:,.0f}',
                                 '#00e676' if cyc['unrealized_pnl'] >= 0 else '#ff1744')
                        pnl_color = '#00e676' if cyc['pnl'] >= 0 else '#ff1744'
                        _bt_stat('Total P&L', f'{"+" if cyc["pnl"] >= 0 else ""}\u20a9{cyc["pnl"]:,.0f} ({cyc["pnl_pct"]:+.2f}%)', pnl_color)
                        _render_tax_estimate(cyc['pnl'], int(bt_lookback.value))
                        _bt_stat('Buys / Sells', f'{cyc["num_buys"]} / {cyc["num_sells"]}')

                # Trade logs per strategy
                ui.label('TRADE LOG').classes('section-title mt-4')
                for name, data, color in [
                    ('Pure DCA', dca, '#ffd740'),
                    ('Signal DCA', sig, '#00e676'),
                    ('DCA + Scalp', sclp, '#e040fb'),
                    ('Buy-Sell-Repeat', cyc, '#00bcd4'),
                ]:
                    active_trades = [t for t in data['trades'] if t.get('type') in ('BUY', 'SELL')]
                    if not active_trades:
                        continue
                    with ui.expansion(text=f'{name} — {len(active_trades)} trades').props(
                        'dense header-class="text-sm font-bold"'
                    ).classes('w-full').style(f'color: {color};'):
                        # Header
                        with ui.row().classes('w-full px-2 py-1').style('border-bottom: 1px solid #2a2a3a;'):
                            for h, w in [('Date', '90px'), ('Type', '45px'), ('Signal', '90px'),
                                         ('Rate', '100px'), ('Units', '80px'), ('KRW', '110px'), ('P&L', '100px')]:
                                ui.label(h).classes('mono text-xs text-gray-500').style(f'width: {w};')
                        for t in active_trades:
                            is_sell = t['type'] == 'SELL'
                            type_color = '#ff1744' if is_sell else '#00e676'
                            with ui.row().classes('w-full px-2 py-1').style('border-bottom: 1px solid #1a1a2a;'):
                                ui.label(t['date']).classes('mono text-xs text-gray-400').style('width: 90px;')
                                ui.label(t['type']).classes('mono text-xs font-bold').style(f'width: 45px; color: {type_color};')
                                ui.label(t.get('signal', '')).classes('mono text-xs text-gray-400').style('width: 90px;')
                                ui.label(f'\u20a9{t["rate"]:,.2f}').classes('mono text-xs').style('width: 100px;')
                                ui.label(f'{t["units"]:,.2f}').classes('mono text-xs').style('width: 80px;')
                                ui.label(f'\u20a9{t["amount"]:,.0f}').classes('mono text-xs').style('width: 110px;')
                                profit = t.get('profit')
                                if profit is not None:
                                    p_color = '#00e676' if profit >= 0 else '#ff1744'
                                    ui.label(f'\u20a9{profit:+,.0f}').classes('mono text-xs').style(f'width: 100px; color: {p_color};')
                                else:
                                    ui.label('—').classes('mono text-xs text-gray-600').style('width: 100px;')

                # Winner summary (after-tax)
                dca_net = _after_tax_pnl(dca['pnl'], int(bt_lookback.value))
                sig_net = _after_tax_pnl(sig['pnl'], int(bt_lookback.value))
                sclp_net = _after_tax_pnl(sclp['pnl'], int(bt_lookback.value))
                cyc_net = _after_tax_pnl(cyc['pnl'], int(bt_lookback.value))

                results_ranked = sorted([
                    ('Pure DCA', dca['pnl_pct'], dca_net, '#ffd740'),
                    ('Signal DCA', sig['pnl_pct'], sig_net, '#00e676'),
                    ('DCA + Scalp', sclp['pnl_pct'], sclp_net, '#e040fb'),
                    ('Buy-Sell-Repeat', cyc['pnl_pct'], cyc_net, '#00bcd4'),
                ], key=lambda x: x[1], reverse=True)

                with ui.row().classes('w-full items-center gap-2 mt-3'):
                    ui.icon('emoji_events').style(f'color: {results_ranked[0][3]}; font-size: 24px;')
                    ui.label(f'Winner: {results_ranked[0][0]} ({results_ranked[0][1]:+.2f}%)').style(
                        f'color: {results_ranked[0][3]}; font-weight: 700;'
                    )

                with ui.column().classes('gap-0 mt-1'):
                    for i, (name, pnl_pct, net, color) in enumerate(results_ranked):
                        ui.label(
                            f'  {i+1}. {name}: {pnl_pct:+.2f}% (after tax: \u20a9{net:+,.0f})'
                        ).classes('mono text-sm').style(f'color: {color};')

                ui.label(
                    'Tax estimate: 22% on gains over \u20a92.5M/year (양도소득세). '
                    'Annualized from lookback period. Consult a 세무사 for your actual situation.'
                ).classes('mono text-xs text-gray-600 mt-2')

        render_backtest()


def _annualized_gain(pnl, lookback_days):
    """Project gain to annual based on lookback period."""
    if lookback_days <= 0:
        return pnl
    return pnl * (365 / lookback_days)


def _tax_estimate(pnl, lookback_days):
    """Estimate Korean 양도소득세 on FX gains.
    22% (20% tax + 2% local) on annual gains exceeding ₩2.5M exemption.
    """
    if pnl <= 0:
        return 0
    annual = _annualized_gain(pnl, lookback_days)
    taxable = max(0, annual - 2_500_000)
    tax_annual = taxable * 0.22
    # Scale back to the lookback period
    return tax_annual * (lookback_days / 365)


def _after_tax_pnl(pnl, lookback_days):
    """P&L after estimated tax."""
    return pnl - _tax_estimate(pnl, lookback_days)


def _render_tax_estimate(pnl, lookback_days):
    """Render tax estimate row in backtest card."""
    tax = _tax_estimate(pnl, lookback_days)
    net = pnl - tax
    if pnl <= 0:
        _bt_stat('Est. Tax', '\u20a90 (no gain)', '#888')
        _bt_stat('After Tax', f'\u20a9{pnl:+,.0f}', '#ff1744' if pnl < 0 else '#888')
    elif tax == 0:
        _bt_stat('Est. Tax', '\u20a90 (under \u20a92.5M exemption)', '#888')
        _bt_stat('After Tax', f'\u20a9{net:+,.0f}', '#00e676')
    else:
        _bt_stat('Est. Tax (22%)', f'-\u20a9{tax:,.0f}', '#ff9100')
        _bt_stat('After Tax', f'\u20a9{net:+,.0f}', '#00e676' if net > 0 else '#ff1744')


def _indicator_card(label, value, color):
    with ui.element('div').style(
        'background: #0a0a0f; border: 1px solid #2a2a3a; border-radius: 6px; padding: 6px 10px;'
    ):
        ui.label(label).classes('mono text-xs text-gray-600')
        ui.label(value).style(f'color: {color}; font-weight: 700; font-size: 13px;')


def _bt_stat(label, value, color='#ccc'):
    with ui.row().classes('w-full justify-between'):
        ui.label(label).classes('mono text-xs text-gray-500')
        ui.label(value).classes('mono text-xs').style(f'color: {color}; font-weight: 600;')


def _build_signal_chart(signals):
    """Mini chart with price, MA20, MA50, and Bollinger Bands."""
    import plotly.graph_objects as go

    dates = signals['dates'][-90:]
    prices = signals['prices'][-90:]
    ma20 = signals['ma20_series'][-90:]
    ma50 = signals['ma50_series'][-90:]

    fig = go.Figure()

    # Bollinger band fill
    bb_u, bb_m, bb_l = signals['bb_upper'], signals['bb_mid'], signals['bb_lower']
    # Approximate bands for the visible range using latest values
    fig.add_trace(go.Scatter(x=dates, y=[bb_u] * len(dates), mode='lines',
                             line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=dates, y=[bb_l] * len(dates), mode='lines',
                             line=dict(width=0), fill='tonexty',
                             fillcolor='rgba(68, 138, 255, 0.06)', showlegend=False, hoverinfo='skip'))

    # Price
    fig.add_trace(go.Scatter(x=dates, y=prices, mode='lines', name='USD/KRW',
                             line=dict(color='#ffd740', width=2),
                             hovertemplate='%{x}<br>\u20a9%{y:,.2f}<extra></extra>'))
    # MA20
    fig.add_trace(go.Scatter(x=dates, y=ma20, mode='lines', name='MA20',
                             line=dict(color='#448aff', width=1, dash='dot')))
    # MA50
    if len(ma50) == len(dates):
        fig.add_trace(go.Scatter(x=dates, y=ma50, mode='lines', name='MA50',
                                 line=dict(color='#e040fb', width=1, dash='dot')))

    rate_min = min(prices)
    rate_max = max(prices)
    pad = (rate_max - rate_min) * 0.1

    fig.update_layout(
        xaxis=dict(gridcolor='#1e1e2e', tickfont=dict(size=9, color='#555')),
        yaxis=dict(gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666'),
                   tickformat=',.0f', range=[rate_min - pad, rate_max + pad]),
        plot_bgcolor='#0a0a0f', paper_bgcolor='#0a0a0f',
        font=dict(color='#e8e8f0', family='Outfit, sans-serif'),
        margin=dict(l=60, r=10, t=10, b=30),
        height=250, legend=dict(orientation='h', y=1.1, font=dict(size=10)),
        hovermode='x unified',
    )
    ui.plotly(fig).classes('w-full')
