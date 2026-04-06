"""Rich Man — FX Trading Dashboard.

Base currency: KRW (fixed for now).
Features:
  - Live rate cards with refresh button
  - Interactive price trend chart (Plotly)
  - Currency converter calculator
  - Rate alert watchlist
  - Toggleable advanced tools:
    - Multi-currency comparison chart
    - Volatility indicator
    - Position tracker (P&L)
    - Cost average calculator
"""

from nicegui import ui, app
from datetime import datetime
from projects.fx_data import (
    fetch_latest, fetch_history, fetch_multi_history, get_last_updated,
    get_currency_options, get_currency_label, CURRENCY_META,
    is_finnhub_active, _cache as _fx_cache,
)
from projects.fx_ws import fx_stream


def build_rich_man_tab():
    """FX trading dashboard — KRW base."""

    base = 'KRW'

    with ui.column().classes('w-full gap-4 p-4'):
        # ── Header ──
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-3'):
                ui.label('RICH MAN').classes('text-3xl font-extrabold').style(
                    'background: linear-gradient(135deg, #ffd740 0%, #ff9100 100%); '
                    '-webkit-background-clip: text; -webkit-text-fill-color: transparent;'
                )
                ui.badge('FX').props('color="amber" text-color="black"').classes('text-sm font-bold')

            # Status + refresh
            with ui.row().classes('items-center gap-2'):
                status_label = ui.label('').classes('mono text-xs text-gray-500')
                ws_dot = ui.icon('circle').classes('text-xs')

                def refresh_all():
                    keys_to_clear = [k for k in _fx_cache if k.startswith('live_')]
                    for k in keys_to_clear:
                        del _fx_cache[k]
                    _update_status()
                    render_cards()
                    convert()
                    render_watchlist()
                    ui.notify('Rates refreshed', type='positive')

                ui.button(icon='refresh', on_click=refresh_all).props(
                    'flat dense round color=amber'
                ).tooltip('Refresh rates')

        def _update_status():
            if fx_stream.connected:
                ws_dot.style('color: #00e676; font-size: 10px;')
                status_label.text = 'Streaming live'
            elif is_finnhub_active():
                ws_dot.style('color: #ff9100; font-size: 10px;')
                status_label.text = 'Connecting...'
            else:
                ws_dot.style('color: #555; font-size: 10px;')
                ts, ago, source = get_last_updated(base)
                if ts:
                    status_label.text = f'{source} | {ts}'
                else:
                    status_label.text = 'No data'

        with ui.row().classes('w-full items-center gap-2 -mt-2'):
            ui.label(f'Base: {CURRENCY_META[base][2]} {base} (Korean Won)').classes(
                'mono text-xs text-gray-500'
            )
            if is_finnhub_active():
                ui.badge('LIVE').props('color="green" text-color="white"').classes('text-xs')
                ui.label('Real-time via Finnhub websocket').classes('text-xs text-gray-600')
            else:
                ui.badge('DAILY').props('color="gray"').classes('text-xs')
                ui.label(
                    'Add FINNHUB_API_KEY to .env for real-time streaming'
                ).classes('text-xs text-gray-600')

        # ── Live Rate Cards ──
        # Each card has labels that update in-place (no re-render needed)
        highlight_currencies = ['USD', 'EUR', 'JPY', 'GBP', 'CNY', 'CAD']
        card_labels = {}  # currency -> {price_label, change_label, time_label}

        cards_container = ui.row().classes('w-full gap-3 flex-wrap')

        def render_cards():
            """Build card structure once, then update labels via websocket."""
            cards_container.clear()
            card_labels.clear()

            data = fetch_latest(base)
            _update_status()

            if not data or 'rates' not in data:
                with cards_container:
                    ui.label('Failed to load rates').classes('text-red-400')
                return

            rates = data['rates']

            with cards_container:
                for cur in highlight_currencies:
                    if cur not in rates:
                        continue
                    rate = rates[cur]
                    meta = CURRENCY_META.get(cur, ('', '', ''))
                    flag, symbol = meta[2], meta[1]
                    inverse = 1 / rate if rate else 0

                    with ui.card().classes('p-3').style(
                        'min-width: 155px; flex: 1; max-width: 200px; '
                        'background: #12121a; border: 1px solid #2a2a3a;'
                    ):
                        with ui.row().classes('items-center gap-2'):
                            ui.label(flag).classes('text-lg')
                            ui.label(cur).classes('font-bold text-sm')

                        price_lbl = ui.label(f'{symbol}{inverse:,.2f}').classes(
                            'font-extrabold text-xl mt-1'
                        ).style('color: #ffd740;')
                        ui.label(f'per 1 {cur}').classes('mono text-xs text-gray-500 -mt-1')

                        change_lbl = ui.label('').style(
                            'font-size: 12px; font-weight: 600;'
                        )
                        time_lbl = ui.label('').classes('mono text-xs text-gray-600')

                        card_labels[cur] = {
                            'price': price_lbl,
                            'change': change_lbl,
                            'time': time_lbl,
                            'symbol': symbol,
                            'prev_krw': inverse,  # track for change coloring
                        }

        render_cards()

        # ── Websocket live updates ──
        if is_finnhub_active():
            fx_stream.start()

            def _on_ws_tick(currency, krw_per_unit, ts_str):
                """Called from websocket thread — schedule UI update."""
                if currency in card_labels:
                    labels = card_labels[currency]
                    sym = labels['symbol']
                    prev = labels['prev_krw']

                    labels['price'].text = f'{sym}{krw_per_unit:,.2f}'
                    labels['time'].text = ts_str

                    if prev and prev != krw_per_unit:
                        diff = krw_per_unit - prev
                        diff_pct = (diff / prev) * 100
                        color = '#00e676' if diff <= 0 else '#ff1744'
                        arrow = '\u25b2' if diff > 0 else '\u25bc'
                        labels['change'].text = f'{arrow} {abs(diff_pct):.3f}%'
                        labels['change'].style(f'color: {color}; font-size: 12px; font-weight: 600;')

                        # Flash effect: briefly highlight the price
                        labels['price'].style(f'color: {color};')
                        labels['prev_krw'] = krw_per_unit

            fx_stream.on_tick(_on_ws_tick)

            # Timer to reset price color back to gold and update status
            def _reset_colors():
                for labels in card_labels.values():
                    labels['price'].style('color: #ffd740;')
                _update_status()

            ui.timer(2.0, _reset_colors)

        ui.separator()

        # ── Live Intraday Ticker (websocket only) ──
        if is_finnhub_active():
            _build_live_ticker(base, highlight_currencies)
            ui.separator()

        # ── Price Trend Chart ──
        _build_price_chart(base)

        ui.separator()

        # ── Currency Converter ──
        convert = _build_converter(base)

        ui.separator()

        # ── Rate Alerts ──
        render_watchlist = _build_watchlist(base)

        ui.separator()

        # ── Advanced Tools (toggleable) ──
        ui.label('ADVANCED TOOLS').classes('section-title')
        ui.label('Toggle tools to expand').classes('mono text-xs text-gray-500 mb-1')

        _build_toggle_section(
            'Multi-Currency Comparison',
            'compare',
            'Overlay multiple currencies on one chart to spot correlations',
            lambda: _build_multi_compare(base),
        )
        _build_toggle_section(
            'Volatility Indicator',
            'trending_up',
            'Rolling standard deviation to gauge currency stability',
            lambda: _build_volatility(base),
        )
        _build_toggle_section(
            'Position Tracker',
            'account_balance_wallet',
            'Log FX buys/sells and track profit & loss',
            lambda: _build_position_tracker(base),
        )
        _build_toggle_section(
            'Cost Average Calculator',
            'calculate',
            'Plan regular currency purchases with DCA strategy',
            lambda: _build_cost_avg(base),
        )


def _build_live_ticker(base, currencies):
    """Live intraday mini-chart that updates every 2 seconds from websocket ticks."""
    ui.label('LIVE TICKER').classes('section-title')

    with ui.row().classes('w-full items-end gap-3'):
        ticker_currency = ui.select(
            options={c: f'{CURRENCY_META.get(c, ("","",""))[2]} {c}' for c in currencies},
            value='USD', label='Currency',
        ).props('dense outlined').classes('text-sm').style('min-width: 150px;')

    live_chart_container = ui.column().classes('w-full')
    live_price_label = ui.label('').classes('mono text-2xl font-extrabold').style('color: #ffd740;')
    live_time_label = ui.label('').classes('mono text-xs text-gray-500')

    def render_live_chart():
        live_chart_container.clear()
        cur = ticker_currency.value
        ticks = fx_stream.get_tick_history(cur, limit=120)

        if len(ticks) < 2:
            with live_chart_container:
                ui.label('Waiting for live ticks...').classes('text-gray-500 text-center py-4')
            return

        times = [t[0] for t in ticks]
        prices = [t[1] for t in ticks]

        # Update price display
        latest = prices[-1]
        meta = CURRENCY_META.get(cur, ('', '', ''))
        live_price_label.text = f'{meta[1]}{latest:,.2f} KRW'
        live_time_label.text = f'Last tick: {times[-1]} KST'

        import plotly.graph_objects as go
        fig = go.Figure()

        # Color line based on trend
        color = '#00e676' if prices[-1] >= prices[0] else '#ff1744'

        fig.add_trace(go.Scatter(
            x=times, y=prices,
            mode='lines',
            line=dict(color=color, width=2),
            fill='tozeroy',
            fillcolor=f'rgba({",".join(str(int(color[i:i+2], 16)) for i in (1,3,5))}, 0.06)',
            hovertemplate='%{x}<br>\u20a9%{y:,.2f}<extra></extra>',
        ))

        rate_min, rate_max = min(prices), max(prices)
        rate_range = rate_max - rate_min if rate_max != rate_min else rate_max * 0.001
        y_pad = rate_range * 0.15

        fig.update_layout(
            xaxis=dict(
                gridcolor='#1e1e2e', tickfont=dict(size=9, color='#555'),
                showgrid=False,
            ),
            yaxis=dict(
                gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666'),
                tickformat=',.2f', range=[rate_min - y_pad, rate_max + y_pad],
            ),
            plot_bgcolor='#0a0a0f', paper_bgcolor='#0a0a0f',
            font=dict(color='#e8e8f0', family='JetBrains Mono, monospace'),
            margin=dict(l=70, r=10, t=5, b=30),
            height=200, showlegend=False,
        )

        with live_chart_container:
            ui.plotly(fig).classes('w-full')

    ticker_currency.on_value_change(lambda _: render_live_chart())

    # Auto-refresh the chart every 2 seconds
    ui.timer(2.0, render_live_chart)
    render_live_chart()


def _build_toggle_section(title, icon, description, builder_fn):
    """Toggle section — switch to show/hide, lazy-loads content on first toggle."""
    built = {'done': False}

    with ui.card().classes('w-full p-0').style(
        'background: #12121a; border: 1px solid #2a2a3a;'
    ):
        with ui.row().classes('w-full items-center justify-between px-4 py-2'):
            with ui.row().classes('items-center gap-2'):
                ui.icon(icon).style('color: #ffd740; font-size: 20px;')
                with ui.column().classes('gap-0'):
                    ui.label(title).classes('font-bold text-sm').style('color: #ffd740;')
                    ui.label(description).classes('text-xs text-gray-500')

            toggle = ui.switch(value=False).props('color=amber')

        content = ui.column().classes('w-full gap-3 px-4 pb-4')
        content.set_visibility(False)

    def on_toggle(e):
        content.set_visibility(e.value)
        if e.value and not built['done']:
            built['done'] = True
            with content:
                builder_fn()

    toggle.on_value_change(on_toggle)


def _build_price_chart(base):
    """Interactive price trend chart with currency selector and time range."""
    ui.label('PRICE TREND').classes('section-title')

    with ui.row().classes('w-full items-end gap-3 flex-wrap'):
        currency_select = ui.select(
            options=get_currency_options(exclude=base),
            value='USD',
            label='Currency',
        ).props('dense outlined').classes('text-sm').style('min-width: 220px;')

        range_select = ui.select(
            options={'30': '1 Month', '90': '3 Months', '180': '6 Months', '365': '1 Year'},
            value='90',
            label='Time Range',
        ).props('dense outlined').classes('text-sm').style('min-width: 140px;')

    chart_container = ui.column().classes('w-full')
    stats_container = ui.row().classes('w-full gap-4 flex-wrap')

    def render_chart():
        chart_container.clear()
        stats_container.clear()

        target = currency_select.value
        days = int(range_select.value)
        history = fetch_history(base, target, days=days)

        if not history:
            with chart_container:
                ui.label('No data available').classes('text-gray-500 text-center py-8')
            return

        dates = [h[0] for h in history]
        rates = [1 / h[1] if h[1] else 0 for h in history]

        import plotly.graph_objects as go

        fig = go.Figure()

        # Tight y-axis: pad 10% above/below the data range so changes are visible
        rate_min, rate_max = min(rates), max(rates)
        rate_range = rate_max - rate_min if rate_max != rate_min else rate_max * 0.01
        y_pad = rate_range * 0.15
        y_lo = rate_min - y_pad
        y_hi = rate_max + y_pad

        fig.add_trace(go.Scatter(
            x=dates, y=rates,
            mode='lines',
            fill='tonexty',
            line=dict(color='#ffd740', width=2),
            fillcolor='rgba(255, 215, 64, 0.06)',
            hovertemplate='%{x}<br>\u20a9%{y:,.2f}<extra></extra>',
        ))

        # Invisible trace at y_lo for the fill baseline
        fig.add_trace(go.Scatter(
            x=dates, y=[y_lo] * len(dates),
            mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip',
        ))
        # Re-order: baseline first, then data (fill='tonexty' fills to the previous trace)
        fig.data = (fig.data[1], fig.data[0])

        if rates:
            max_idx = rates.index(rate_max)
            min_idx = rates.index(rate_min)
            for idx, label, color in [(max_idx, 'High', '#ff1744'), (min_idx, 'Low', '#00e676')]:
                fig.add_annotation(
                    x=dates[idx], y=rates[idx],
                    text=f'{label}: \u20a9{rates[idx]:,.2f}',
                    showarrow=True, arrowhead=2, arrowcolor=color,
                    font=dict(size=10, color=color),
                    bgcolor='#0a0a0f', bordercolor=color,
                )

        fig.update_layout(
            xaxis=dict(gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666')),
            yaxis=dict(
                gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666'),
                tickformat=',.0f',
                range=[y_lo, y_hi],
                title=dict(text=f'KRW per 1 {target}', font=dict(size=11, color='#888')),
            ),
            plot_bgcolor='#0a0a0f',
            paper_bgcolor='#0a0a0f',
            font=dict(color='#e8e8f0', family='Outfit, sans-serif'),
            margin=dict(l=70, r=20, t=10, b=40),
            height=350,
            showlegend=False,
            hovermode='x unified',
        )

        with chart_container:
            ui.plotly(fig).classes('w-full')

        # Stats summary
        if len(rates) >= 2:
            current = rates[-1]
            period_start = rates[0]
            high, low = max(rates), min(rates)
            avg = sum(rates) / len(rates)
            change = current - period_start
            change_pct = (change / period_start * 100) if period_start else 0

            stats = [
                ('Current', f'\u20a9{current:,.2f}', '#ffd740'),
                ('Change', f'{"+" if change >= 0 else ""}\u20a9{change:,.2f} ({change_pct:+.2f}%)',
                 '#ff1744' if change > 0 else '#00e676'),
                ('High', f'\u20a9{high:,.2f}', '#ff1744'),
                ('Low', f'\u20a9{low:,.2f}', '#00e676'),
                ('Average', f'\u20a9{avg:,.2f}', '#888'),
            ]
            with stats_container:
                for label, value, color in stats:
                    with ui.column().classes('gap-0'):
                        ui.label(label).classes('mono text-xs text-gray-500')
                        ui.label(value).style(f'color: {color}; font-weight: 700; font-size: 14px;')

    currency_select.on_value_change(lambda _: render_chart())
    range_select.on_value_change(lambda _: render_chart())
    render_chart()


def _build_converter(base):
    """Quick currency converter calculator. Returns convert() for external refresh."""
    ui.label('CONVERTER').classes('section-title')

    with ui.card().classes('w-full p-4').style('background: #12121a; border: 1px solid #2a2a3a;'):
        with ui.row().classes('w-full items-end gap-3'):
            amount_input = ui.number(
                label=f'Amount ({base})', value=1000000, format='%.0f',
            ).props('dense outlined').classes('flex-grow')

            target_select = ui.select(
                options=get_currency_options(exclude=base),
                value='USD',
                label='To',
            ).props('dense outlined').classes('text-sm').style('min-width: 200px;')

        result_label = ui.label('').classes('text-2xl font-extrabold mt-2').style('color: #ffd740;')
        rate_label = ui.label('').classes('mono text-xs text-gray-500')

        def convert():
            data = fetch_latest(base)
            if not data or 'rates' not in data:
                result_label.text = 'Rate unavailable'
                return

            target = target_select.value
            rate = data['rates'].get(target)
            if not rate:
                result_label.text = f'{target} not available'
                return

            amount = amount_input.value or 0
            converted = amount * rate
            meta = CURRENCY_META.get(target, ('', '', ''))
            result_label.text = f'{meta[1]}{converted:,.2f} {target}'
            inverse = 1 / rate if rate else 0
            rate_label.text = (
                f'1 {target} = \u20a9{inverse:,.2f} | '
                f'1 {base} = {rate:.6f} {target} | '
                f'Updated: {data.get("date", "")}'
            )

        amount_input.on_value_change(lambda _: convert())
        target_select.on_value_change(lambda _: convert())
        convert()

    return convert


def _build_watchlist(base):
    """Rate alert watchlist. Returns render_watchlist() for external refresh."""
    ui.label('WATCHLIST').classes('section-title')
    ui.label('Track currencies and set target rates').classes('mono text-xs text-gray-500 mb-2')

    app.storage.general.setdefault('fx_watchlist', [
        {'currency': 'USD', 'target_rate': 1400.0, 'direction': 'below'},
        {'currency': 'JPY', 'target_rate': 9.5, 'direction': 'below'},
    ])

    watchlist_container = ui.column().classes('w-full gap-2')

    def render_watchlist():
        watchlist_container.clear()
        items = app.storage.general.get('fx_watchlist', [])
        data = fetch_latest(base)
        rates = data.get('rates', {}) if data else {}

        if not items:
            with watchlist_container:
                ui.label('No items in watchlist').classes('text-gray-500')
            return

        with watchlist_container:
            for item in items:
                cur = item['currency']
                target_rate = item.get('target_rate', 0)
                direction = item.get('direction', 'below')
                rate = rates.get(cur)
                current_krw = (1 / rate) if rate else 0

                triggered = False
                if current_krw and target_rate:
                    if direction == 'below' and current_krw <= target_rate:
                        triggered = True
                    elif direction == 'above' and current_krw >= target_rate:
                        triggered = True

                meta = CURRENCY_META.get(cur, ('', '', ''))
                border_color = '#00e676' if triggered else '#2a2a3a'

                with ui.card().classes('w-full p-3').style(
                    f'background: #12121a; border: 1px solid {border_color};'
                ):
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.row().classes('items-center gap-3'):
                            ui.label(f'{meta[2]} {cur}').classes('font-bold')
                            if current_krw:
                                ui.label(f'\u20a9{current_krw:,.2f}').classes(
                                    'mono font-bold'
                                ).style('color: #ffd740;')
                            else:
                                ui.label('N/A').classes('text-gray-500')

                        with ui.row().classes('items-center gap-2'):
                            dir_icon = 'trending_down' if direction == 'below' else 'trending_up'
                            dir_color = '#00e676' if direction == 'below' else '#ff1744'
                            ui.icon(dir_icon).style(f'color: {dir_color}; font-size: 18px;')
                            ui.label(f'\u20a9{target_rate:,.2f}').classes('mono text-sm')

                            if triggered:
                                ui.badge('HIT').props('color="green" text-color="black"').classes('text-xs')

                            ui.button(
                                icon='close',
                                on_click=lambda c=cur: remove_watchlist(c),
                            ).props('flat dense round size=xs color=gray')

    def remove_watchlist(currency):
        ui.notify(f'Removed {currency}', type='info')
        items = app.storage.general.get('fx_watchlist', [])
        items = [i for i in items if i['currency'] != currency]
        app.storage.general['fx_watchlist'] = items
        render_watchlist()

    render_watchlist()

    # Add form
    with ui.card().classes('w-full p-3 mt-2').style('background: #12121a; border: 1px solid #2a2a3a;'):
        with ui.row().classes('w-full items-end gap-3'):
            watch_currency = ui.select(
                options=get_currency_options(exclude=base),
                value='EUR', label='Currency',
            ).props('dense outlined').classes('text-sm').style('min-width: 200px;')

            watch_target = ui.number(
                label='Target rate (KRW per 1 unit)', value=1300.0, format='%.2f',
            ).props('dense outlined').classes('flex-grow')

            watch_direction = ui.select(
                options={'below': 'Drops below', 'above': 'Rises above'},
                value='below', label='Alert when',
            ).props('dense outlined').classes('text-sm').style('min-width: 150px;')

        def add_to_watchlist():
            items = app.storage.general.get('fx_watchlist', [])
            items = [i for i in items if i['currency'] != watch_currency.value]
            items.append({
                'currency': watch_currency.value,
                'target_rate': watch_target.value or 0,
                'direction': watch_direction.value,
            })
            app.storage.general['fx_watchlist'] = items
            ui.notify(f'Added {watch_currency.value} to watchlist', type='positive')
            render_watchlist()

        ui.button('Add to Watchlist', icon='add_alert', on_click=add_to_watchlist).props(
            'color=amber text-color=black'
        )

    return render_watchlist


# ═══════════════════════════════════════════════════════════
#  ADVANCED TOGGLEABLE TOOLS
# ═══════════════════════════════════════════════════════════

def _build_multi_compare(base):
    """Overlay multiple currencies on one normalized chart."""
    with ui.row().classes('w-full items-end gap-3 flex-wrap'):
        cur_options = get_currency_options(exclude=base)
        multi_select = ui.select(
            options=cur_options,
            value=['USD', 'EUR', 'JPY'],
            label='Currencies',
            multiple=True,
        ).props('dense outlined use-chips').classes('text-sm').style('min-width: 300px;')

        range_select = ui.select(
            options={'30': '1M', '90': '3M', '180': '6M', '365': '1Y'},
            value='90', label='Range',
        ).props('dense outlined').classes('text-sm')

    chart_container = ui.column().classes('w-full')

    def render():
        chart_container.clear()
        targets = multi_select.value or ['USD']
        days = int(range_select.value)
        data = fetch_multi_history(base, targets, days)
        if not data:
            with chart_container:
                ui.label('No data').classes('text-gray-500')
            return

        import plotly.graph_objects as go
        colors = ['#ffd740', '#00e676', '#448aff', '#e040fb', '#ff9100', '#00bcd4', '#ff1744']
        fig = go.Figure()

        for i, target in enumerate(targets):
            series = data.get(target, [])
            if not series:
                continue
            dates = [s[0] for s in series]
            # Normalize to 100 at start for comparison
            base_val = 1 / series[0][1] if series[0][1] else 1
            values = [(1 / s[1] / base_val * 100) if s[1] else 100 for s in series]

            fig.add_trace(go.Scatter(
                x=dates, y=values,
                mode='lines', name=target,
                line=dict(color=colors[i % len(colors)], width=2),
                hovertemplate=f'{target}: %{{y:.1f}}<extra></extra>',
            ))

        fig.update_layout(
            yaxis=dict(
                title=dict(text='Indexed (100 = start)', font=dict(size=11, color='#888')),
                gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666'),
            ),
            xaxis=dict(gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666')),
            plot_bgcolor='#0a0a0f', paper_bgcolor='#0a0a0f',
            font=dict(color='#e8e8f0', family='Outfit, sans-serif'),
            margin=dict(l=60, r=20, t=10, b=40),
            height=300,
            legend=dict(orientation='h', y=1.1),
            hovermode='x unified',
        )

        with chart_container:
            ui.plotly(fig).classes('w-full')

    multi_select.on_value_change(lambda _: render())
    range_select.on_value_change(lambda _: render())
    render()


def _build_volatility(base):
    """Rolling standard deviation chart to measure currency stability."""
    with ui.row().classes('w-full items-end gap-3'):
        vol_currency = ui.select(
            options=get_currency_options(exclude=base),
            value='USD', label='Currency',
        ).props('dense outlined').classes('text-sm').style('min-width: 220px;')

        vol_window = ui.select(
            options={'5': '5-day', '10': '10-day', '20': '20-day'},
            value='10', label='Rolling Window',
        ).props('dense outlined').classes('text-sm')

    chart_container = ui.column().classes('w-full')

    def render():
        chart_container.clear()
        target = vol_currency.value
        history = fetch_history(base, target, days=180)
        if not history or len(history) < 10:
            with chart_container:
                ui.label('Not enough data').classes('text-gray-500')
            return

        rates = [1 / h[1] if h[1] else 0 for h in history]
        dates = [h[0] for h in history]
        window = int(vol_window.value)

        # Calculate daily returns
        returns = [(rates[i] - rates[i - 1]) / rates[i - 1] * 100
                   for i in range(1, len(rates)) if rates[i - 1]]

        # Rolling std dev
        rolling_vol = []
        roll_dates = []
        for i in range(window, len(returns)):
            chunk = returns[i - window:i]
            mean = sum(chunk) / len(chunk)
            variance = sum((x - mean) ** 2 for x in chunk) / len(chunk)
            rolling_vol.append(variance ** 0.5)
            roll_dates.append(dates[i + 1])  # +1 because returns starts from index 1

        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=roll_dates, y=rolling_vol,
            mode='lines', fill='tozeroy',
            line=dict(color='#e040fb', width=2),
            fillcolor='rgba(224, 64, 251, 0.08)',
            hovertemplate='%{x}<br>Volatility: %{y:.3f}%<extra></extra>',
        ))

        fig.update_layout(
            yaxis=dict(
                title=dict(text='Daily Volatility (%)', font=dict(size=11, color='#888')),
                gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666'),
            ),
            xaxis=dict(gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666')),
            plot_bgcolor='#0a0a0f', paper_bgcolor='#0a0a0f',
            font=dict(color='#e8e8f0', family='Outfit, sans-serif'),
            margin=dict(l=60, r=20, t=10, b=40),
            height=250, showlegend=False,
        )

        with chart_container:
            ui.plotly(fig).classes('w-full')

        # Interpretation
        if rolling_vol:
            current_vol = rolling_vol[-1]
            avg_vol = sum(rolling_vol) / len(rolling_vol)
            with chart_container:
                level = 'LOW' if current_vol < avg_vol * 0.8 else ('HIGH' if current_vol > avg_vol * 1.2 else 'NORMAL')
                color = '#00e676' if level == 'LOW' else ('#ff1744' if level == 'HIGH' else '#ffd740')
                ui.label(
                    f'Current {window}-day volatility: {current_vol:.3f}% '
                    f'(avg: {avg_vol:.3f}%) — {level}'
                ).style(f'color: {color}; font-weight: 600; font-size: 13px;')

    vol_currency.on_value_change(lambda _: render())
    vol_window.on_value_change(lambda _: render())
    render()


def _build_position_tracker(base):
    """Log FX trades and track P&L."""
    app.storage.general.setdefault('fx_positions', [])

    positions_container = ui.column().classes('w-full gap-2')

    def render_positions():
        positions_container.clear()
        positions = app.storage.general.get('fx_positions', [])
        data = fetch_latest(base)
        rates = data.get('rates', {}) if data else {}

        if not positions:
            with positions_container:
                ui.label('No positions yet. Add your first trade below.').classes('text-gray-500')
            return

        total_pnl = 0
        with positions_container:
            for pos in positions:
                cur = pos['currency']
                amount_krw = pos['amount_krw']
                bought_rate = pos['rate']  # KRW per 1 unit at buy time
                amount_fx = amount_krw / bought_rate if bought_rate else 0

                current_rate_raw = rates.get(cur)
                current_krw_per_unit = (1 / current_rate_raw) if current_rate_raw else 0
                current_value = amount_fx * current_krw_per_unit
                pnl = current_value - amount_krw
                pnl_pct = (pnl / amount_krw * 100) if amount_krw else 0
                total_pnl += pnl

                meta = CURRENCY_META.get(cur, ('', '', ''))
                pnl_color = '#00e676' if pnl >= 0 else '#ff1744'

                with ui.card().classes('w-full p-3').style(
                    'background: #12121a; border: 1px solid #2a2a3a;'
                ):
                    with ui.row().classes('w-full items-center justify-between'):
                        with ui.column().classes('gap-0'):
                            ui.label(f'{meta[2]} {cur} — {pos.get("note", "")}').classes('font-bold text-sm')
                            ui.label(
                                f'Bought \u20a9{amount_krw:,.0f} at \u20a9{bought_rate:,.2f}/{cur} '
                                f'({pos["date"]})'
                            ).classes('mono text-xs text-gray-500')

                        with ui.column().classes('items-end gap-0'):
                            ui.label(f'\u20a9{current_value:,.0f}').classes('font-bold').style('color: #ffd740;')
                            ui.label(
                                f'{"+" if pnl >= 0 else ""}\u20a9{pnl:,.0f} ({pnl_pct:+.2f}%)'
                            ).style(f'color: {pnl_color}; font-weight: 600; font-size: 12px;')

                        ui.button(
                            icon='close', on_click=lambda p=pos: remove_position(p),
                        ).props('flat dense round size=xs color=gray')

            # Total P&L
            total_color = '#00e676' if total_pnl >= 0 else '#ff1744'
            with ui.row().classes('w-full justify-end mt-2'):
                ui.label(
                    f'Total P&L: {"+" if total_pnl >= 0 else ""}\u20a9{total_pnl:,.0f}'
                ).style(f'color: {total_color}; font-weight: 700; font-size: 16px;')

    def remove_position(pos):
        ui.notify('Position removed', type='info')
        positions = app.storage.general.get('fx_positions', [])
        positions = [p for p in positions if p['id'] != pos['id']]
        app.storage.general['fx_positions'] = positions
        render_positions()

    render_positions()

    # Add position form
    with ui.card().classes('w-full p-3 mt-2').style('background: #12121a; border: 1px solid #2a2a3a;'):
        ui.label('Add Position').classes('font-bold text-sm mb-1')
        with ui.row().classes('w-full items-end gap-3 flex-wrap'):
            pos_currency = ui.select(
                options=get_currency_options(exclude=base),
                value='USD', label='Currency',
            ).props('dense outlined').classes('text-sm').style('min-width: 180px;')

            pos_amount = ui.number(
                label='Amount (KRW)', value=1000000, format='%.0f',
            ).props('dense outlined').classes('flex-grow')

            pos_rate = ui.number(
                label='Buy rate (KRW per 1 unit)', value=1450.0, format='%.2f',
            ).props('dense outlined').classes('flex-grow')

            pos_note = ui.input(label='Note', placeholder='e.g. Hana Bank').props('dense outlined').classes('flex-grow')

        def add_position():
            positions = app.storage.general.get('fx_positions', [])
            new_id = max([p['id'] for p in positions], default=0) + 1
            positions.append({
                'id': new_id,
                'currency': pos_currency.value,
                'amount_krw': pos_amount.value or 0,
                'rate': pos_rate.value or 0,
                'note': pos_note.value or '',
                'date': datetime.now().strftime('%Y-%m-%d'),
            })
            app.storage.general['fx_positions'] = positions
            pos_note.value = ''
            ui.notify('Position added', type='positive')
            render_positions()

        ui.button('Add Position', icon='add', on_click=add_position).props('color=amber text-color=black')


def _build_cost_avg(base):
    """Dollar-cost averaging calculator for regular FX purchases."""
    ui.label('Simulate regular currency purchases to see the average cost effect.').classes(
        'text-xs text-gray-400 mb-2'
    )

    with ui.row().classes('w-full items-end gap-3 flex-wrap'):
        dca_currency = ui.select(
            options=get_currency_options(exclude=base),
            value='USD', label='Currency',
        ).props('dense outlined').classes('text-sm').style('min-width: 200px;')

        dca_amount = ui.number(
            label=f'Amount per purchase ({base})', value=500000, format='%.0f',
        ).props('dense outlined').classes('flex-grow')

        dca_freq = ui.select(
            options={'7': 'Weekly', '14': 'Bi-weekly', '30': 'Monthly'},
            value='30', label='Frequency',
        ).props('dense outlined').classes('text-sm')

        dca_period = ui.select(
            options={'90': '3 Months', '180': '6 Months', '365': '1 Year'},
            value='180', label='Lookback',
        ).props('dense outlined').classes('text-sm')

    result_container = ui.column().classes('w-full gap-2')

    def calculate():
        result_container.clear()
        target = dca_currency.value
        days = int(dca_period.value)
        freq = int(dca_freq.value)
        amount = dca_amount.value or 0

        history = fetch_history(base, target, days=days)
        if not history or len(history) < 5:
            with result_container:
                ui.label('Not enough data').classes('text-gray-500')
            return

        # Simulate purchases at regular intervals
        dates_available = {h[0]: h[1] for h in history}
        all_dates = sorted(dates_available.keys())

        purchases = []
        for i in range(0, len(all_dates), freq):
            d = all_dates[i]
            rate = dates_available[d]
            krw_per_unit = 1 / rate if rate else 0
            units = amount / krw_per_unit if krw_per_unit else 0
            purchases.append({'date': d, 'krw_per_unit': krw_per_unit, 'units': units, 'spent': amount})

        if not purchases:
            return

        total_spent = sum(p['spent'] for p in purchases)
        total_units = sum(p['units'] for p in purchases)
        avg_cost = total_spent / total_units if total_units else 0

        # Current value
        latest_rate = 1 / history[-1][1] if history[-1][1] else 0
        current_value = total_units * latest_rate
        pnl = current_value - total_spent
        pnl_pct = (pnl / total_spent * 100) if total_spent else 0
        pnl_color = '#00e676' if pnl >= 0 else '#ff1744'

        with result_container:
            with ui.row().classes('w-full gap-4 flex-wrap'):
                for label, value, color in [
                    ('Purchases', f'{len(purchases)}', '#888'),
                    ('Total Invested', f'\u20a9{total_spent:,.0f}', '#888'),
                    (f'Total {target}', f'{total_units:,.2f}', '#ffd740'),
                    ('Avg Cost', f'\u20a9{avg_cost:,.2f}', '#ffd740'),
                    ('Current Rate', f'\u20a9{latest_rate:,.2f}', '#888'),
                    ('Current Value', f'\u20a9{current_value:,.0f}', '#ffd740'),
                    ('P&L', f'{"+" if pnl >= 0 else ""}\u20a9{pnl:,.0f} ({pnl_pct:+.1f}%)', pnl_color),
                ]:
                    with ui.column().classes('gap-0'):
                        ui.label(label).classes('mono text-xs text-gray-500')
                        ui.label(value).style(f'color: {color}; font-weight: 700;')

            # Show purchase history
            if len(purchases) <= 20:
                with ui.row().classes('w-full flex-wrap gap-1 mt-2'):
                    for p in purchases:
                        with ui.element('div').style(
                            'background: #1a1a2a; border-radius: 4px; padding: 2px 6px;'
                        ):
                            ui.label(
                                f'{p["date"]}: \u20a9{p["krw_per_unit"]:,.0f}'
                            ).classes('mono text-xs text-gray-400')

    for widget in [dca_currency, dca_amount, dca_freq, dca_period]:
        widget.on_value_change(lambda _: calculate())
    calculate()
