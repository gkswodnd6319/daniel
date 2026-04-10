"""Crypto Backtest — Mean reversion on Bithumb (BTC/KRW, USDT/KRW).

24/7 automated trading simulation.
Exchange: Bithumb (0.04% maker/taker fee)
Data: Bithumb hourly candles (5000 candles, ~7 months)
Safety locks: max trades/day, volatility filter, SL cooldown, daily loss limit, max drawdown
"""

import httpx
import logging
from collections import defaultdict
from nicegui import ui
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

BITHUMB_FEE = 0.0004  # 0.04% per trade
BITHUMB_CANDLE_API = 'https://api.bithumb.com/public/candlestick'

# Default params per pair (from optimization)
PAIR_DEFAULTS = {
    'USDT_KRW': {
        'label': 'USDT/KRW', 'ma': 48, 'dip': 0.05, 'gain': 0.40, 'sl': 0.3,
        'max_trades': 0, 'max_vol': 0.2, 'cooldown': 0,
        'daily_loss_limit': 1.0, 'max_drawdown': 5.0,
    },
    'BTC_KRW': {
        'label': 'BTC/KRW', 'ma': 6, 'dip': 0.5, 'gain': 1.5, 'sl': 5.0,
        'max_trades': 3, 'max_vol': 1.5, 'cooldown': 3,
        'daily_loss_limit': 3.0, 'max_drawdown': 10.0,
    },
}


def _fetch_candles(pair='BTC_KRW', interval='1h', start_date=None, end_date=None):
    """Fetch hourly candles from Bithumb for any pair."""
    try:
        resp = httpx.get(f'{BITHUMB_CANDLE_API}/{pair}/{interval}', timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('status') != '0000':
            return None
        result = []
        for c in data.get('data', []):
            ts = datetime.fromtimestamp(c[0] / 1000) + timedelta(hours=9)
            result.append((ts.strftime('%Y-%m-%d %H:%M'), float(c[2])))  # close
        result.sort(key=lambda x: x[0])
        if start_date or end_date:
            sd = start_date or '0000'
            ed = (end_date + ' 23:59') if end_date else '9999'
            result = [(d, p) for d, p in result if sd <= d <= ed]
        return result
    except Exception as e:
        logger.error(f'Bithumb candle fetch {pair}: {e}')
        return None


def _run_crypto_mr(pair='BTC_KRW', seed=1_000_000, ma_period=6, buy_dip_pct=0.5,
                   sell_gain_pct=1.5, sl_pct=5.0, max_trades_day=3, max_vol_pct=1.5,
                   cooldown_hrs=3, daily_loss_limit_pct=3.0, max_drawdown_pct=10.0,
                   dd_pause_hrs=48, start_date=None, end_date=None, instant_buy=False,
                   fixed_seed=False):
    """Mean reversion backtest for any crypto pair on Bithumb. 24/7, all safety locks.
    dd_pause_hrs: hours to pause after max drawdown (0 = permanent halt).
    """
    data = _fetch_candles(pair, '1h', start_date, end_date)
    if not data or len(data) < ma_period + 5:
        return _empty()

    balance = seed
    banked_profit = 0.0  # profits set aside when fixed_seed=True
    peak_balance = seed
    units = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0
    trades = []
    prices = [d[1] for d in data]
    buy_count = 0
    sell_count = 0
    daily_pnl = defaultdict(float)
    daily_trades_count = defaultdict(int)
    cooldown_until = 0
    dd_pause_until = 0
    dd_count = 0
    halt_reason = ''

    for i in range(ma_period, len(data)):
        dt_str, price = data[i]
        today = dt_str[:10]

        # Drawdown pause check
        if i < dd_pause_until:
            continue

        # Max drawdown check (from peak balance)
        current_total = balance + (units * price if units else 0)
        if current_total > peak_balance:
            peak_balance = current_total
        drawdown = (peak_balance - current_total) / peak_balance * 100
        if max_drawdown_pct and drawdown >= max_drawdown_pct:
            dd_count += 1
            halt_reason = f'Drawdown {drawdown:.1f}% (#{dd_count})'
            trades.append({
                'date': dt_str, 'type': 'PAUSE', 'signal': f'{halt_reason} — pausing {dd_pause_hrs}h',
                'amount': 0, 'units': 0, 'rate': price,
            })
            if dd_pause_hrs > 0:
                dd_pause_until = i + dd_pause_hrs
                # Reset peak after pause so it can trade the recovery
                peak_balance = current_total
            else:
                dd_pause_until = len(data)  # permanent halt
            continue

        # Daily loss limit check
        if daily_loss_limit_pct and daily_pnl[today] <= -(seed * daily_loss_limit_pct / 100):
            continue

        # Cooldown check
        if i < cooldown_until:
            continue

        # Max trades/day check
        if max_trades_day and daily_trades_count[today] >= max_trades_day:
            continue

        # Volatility check (12h rolling)
        if max_vol_pct and i >= 12:
            rets = [(prices[j] - prices[j-1]) / prices[j-1] * 100
                    for j in range(i-11, i+1) if prices[j-1]]
            if rets:
                mean_r = sum(rets) / len(rets)
                vol = (sum((r - mean_r)**2 for r in rets) / len(rets)) ** 0.5
                if vol > max_vol_pct:
                    continue

        bid = price * (1 - BITHUMB_FEE)
        ask = price * (1 + BITHUMB_FEE)
        ma = sum(prices[i - ma_period:i]) / ma_period
        dev = (price - ma) / ma * 100

        # BUY
        if units == 0 and balance > 0:
            if instant_buy or dev <= -buy_dip_pct:
                units = balance / ask
                cost_basis = balance
                balance = 0
                buy_count += 1
                trades.append({
                    'date': dt_str, 'type': 'BUY',
                    'signal': f'MA{ma_period}h dev {dev:+.2f}%',
                    'amount': cost_basis, 'units': units, 'rate': price,
                })

        # SELL
        elif units > 0:
            avg_cost = cost_basis / units
            gain = (bid - avg_cost) / avg_cost * 100
            is_sl = False
            sell_signal = None

            if gain >= sell_gain_pct:
                sell_signal = f'TP +{gain:.2f}%'
            elif sl_pct and gain <= -sl_pct:
                sell_signal = f'SL {gain:.2f}%'
                is_sl = True

            if sell_signal:
                proceeds = units * bid
                profit = proceeds - cost_basis
                realized_pnl += profit
                daily_pnl[today] += profit
                daily_trades_count[today] += 1
                sell_count += 1
                trades.append({
                    'date': dt_str, 'type': 'SELL', 'signal': sell_signal,
                    'amount': proceeds, 'units': units, 'rate': price,
                    'profit': profit,
                })
                if fixed_seed:
                    banked_profit += proceeds - seed
                    balance = seed
                else:
                    balance = proceeds
                units = 0
                cost_basis = 0
                if is_sl and cooldown_hrs:
                    cooldown_until = i + cooldown_hrs

    current_value = units * prices[-1] if units else 0
    unrealized = current_value - cost_basis if units else 0
    total_pnl = realized_pnl + unrealized + banked_profit
    pnl_pct = (total_pnl / seed * 100) if seed else 0
    total_bought = sum(t['amount'] for t in trades if t.get('type') == 'BUY')
    total_sold = sum(t['amount'] for t in trades if t.get('type') == 'SELL')
    total_fees = (total_bought + total_sold) * BITHUMB_FEE
    wins = sum(1 for t in trades if t.get('profit', 0) > 0)

    return {
        'total_invested': total_bought,
        'banked_profit': banked_profit,
        'total_units': units,
        'avg_cost': cost_basis / units if units else 0,
        'current_value': current_value,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized,
        'pnl': total_pnl,
        'pnl_pct': pnl_pct,
        'num_buys': buy_count,
        'num_sells': sell_count,
        'num_wins': wins,
        'win_rate': (wins / sell_count * 100) if sell_count else 0,
        'trades': trades,
        'final_balance': balance + current_value,
        'total_fees': total_fees,
        'halted': dd_pause_hrs == 0 and dd_count > 0,
        'halt_reason': halt_reason,
        'dd_pauses': dd_count,
    }


def _empty():
    return {
        'total_invested': 0, 'total_units': 0, 'avg_cost': 0, 'current_value': 0,
        'realized_pnl': 0, 'unrealized_pnl': 0, 'pnl': 0, 'pnl_pct': 0,
        'num_buys': 0, 'num_sells': 0, 'num_wins': 0, 'win_rate': 0,
        'trades': [], 'final_balance': 0, 'total_fees': 0,
        'halted': False, 'halt_reason': '',
    }


def _run_crypto_adaptive(pair='BTC_KRW', seed=1_000_000, ma_period=24,
                         dip_mult=1.0, gain_mult=1.5, sl_mult=5.0,
                         max_trades_day=3, max_vol_pct=0, cooldown_hrs=3,
                         daily_loss_limit_pct=3.0, max_drawdown_pct=10.0, dd_pause_hrs=48,
                         instant_buy=False, fixed_seed=False,
                         start_date=None, end_date=None):
    """Adaptive mean reversion — thresholds scale with 24h rolling volatility."""
    data = _fetch_candles(pair, '1h', start_date, end_date)
    if not data or len(data) < max(ma_period, 24) + 5:
        return _empty()

    balance = seed
    banked_profit = 0.0
    peak_balance = seed
    units = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0
    trades = []
    prices = [d[1] for d in data]
    buy_count = 0
    sell_count = 0
    daily_pnl = defaultdict(float)
    daily_trades_count = defaultdict(int)
    cooldown_until = 0
    dd_pause_until = 0
    dd_count = 0
    halt_reason = ''

    for i in range(max(ma_period, 24), len(data)):
        dt_str, price = data[i]
        today = dt_str[:10]

        if i < dd_pause_until:
            continue

        # Max drawdown
        current_total = balance + (units * price if units else 0)
        if current_total > peak_balance:
            peak_balance = current_total
        drawdown = (peak_balance - current_total) / peak_balance * 100
        if max_drawdown_pct and drawdown >= max_drawdown_pct:
            dd_count += 1
            halt_reason = f'Drawdown {drawdown:.1f}% (#{dd_count})'
            trades.append({'date': dt_str, 'type': 'PAUSE', 'signal': f'{halt_reason} — pausing {dd_pause_hrs}h',
                           'amount': 0, 'units': 0, 'rate': price})
            if dd_pause_hrs > 0:
                dd_pause_until = i + dd_pause_hrs
                peak_balance = current_total
            else:
                dd_pause_until = len(data)
            continue

        if daily_loss_limit_pct and daily_pnl[today] <= -(seed * daily_loss_limit_pct / 100):
            continue
        if i < cooldown_until:
            continue
        if max_trades_day and daily_trades_count[today] >= max_trades_day:
            continue

        # 24h rolling volatility
        rets = [(prices[j] - prices[j-1]) / prices[j-1] * 100
                for j in range(i-23, i+1) if prices[j-1]]
        mean_r = sum(rets) / len(rets) if rets else 0
        vol = (sum((r - mean_r)**2 for r in rets) / len(rets))**0.5 if rets else 0.1

        if max_vol_pct and vol > max_vol_pct:
            continue

        # Adaptive thresholds
        buy_dip = max(0.05, vol * dip_mult)
        sell_gain = max(0.05, vol * gain_mult)
        sl_pct = max(0.5, vol * sl_mult)

        bid = price * (1 - BITHUMB_FEE)
        ask = price * (1 + BITHUMB_FEE)
        ma = sum(prices[i - ma_period:i]) / ma_period
        dev = (price - ma) / ma * 100

        if units == 0 and balance > 0:
            if instant_buy or dev <= -buy_dip:
                units = balance / ask
                cost_basis = balance
                balance = 0
                buy_count += 1
                trades.append({
                    'date': dt_str, 'type': 'BUY',
                    'signal': f'MA{ma_period}h dev {dev:+.2f}% (dip>{buy_dip:.2f}%, vol={vol:.2f}%)',
                    'amount': cost_basis, 'units': units, 'rate': price,
                })

        elif units > 0:
            avg_cost = cost_basis / units
            gain = (bid - avg_cost) / avg_cost * 100
            is_sl = False
            sell_signal = None

            if gain >= sell_gain:
                sell_signal = f'TP +{gain:.2f}% (target>{sell_gain:.2f}%)'
            elif gain <= -sl_pct:
                sell_signal = f'SL {gain:.2f}% (limit>{sl_pct:.2f}%)'
                is_sl = True

            if sell_signal:
                proceeds = units * bid
                profit = proceeds - cost_basis
                realized_pnl += profit
                daily_pnl[today] += profit
                daily_trades_count[today] += 1
                sell_count += 1
                trades.append({
                    'date': dt_str, 'type': 'SELL', 'signal': sell_signal,
                    'amount': proceeds, 'units': units, 'rate': price,
                    'profit': profit,
                })
                if fixed_seed:
                    banked_profit += proceeds - seed
                    balance = seed
                else:
                    balance = proceeds
                units = 0
                cost_basis = 0
                if is_sl and cooldown_hrs:
                    cooldown_until = i + cooldown_hrs

    current_value = units * prices[-1] if units else 0
    unrealized = current_value - cost_basis if units else 0
    total_pnl = realized_pnl + unrealized + banked_profit
    pnl_pct = (total_pnl / seed * 100) if seed else 0
    total_bought = sum(t['amount'] for t in trades if t.get('type') == 'BUY')
    total_sold = sum(t['amount'] for t in trades if t.get('type') == 'SELL')
    total_fees = (total_bought + total_sold) * BITHUMB_FEE
    wins = sum(1 for t in trades if t.get('profit', 0) > 0)

    return {
        'total_invested': total_bought,
        'banked_profit': banked_profit,
        'total_units': units,
        'avg_cost': cost_basis / units if units else 0,
        'current_value': current_value,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized,
        'pnl': total_pnl,
        'pnl_pct': pnl_pct,
        'num_buys': buy_count,
        'num_sells': sell_count,
        'num_wins': wins,
        'win_rate': (wins / sell_count * 100) if sell_count else 0,
        'trades': trades,
        'final_balance': balance + current_value,
        'total_fees': total_fees,
        'halted': dd_pause_hrs == 0 and dd_count > 0,
        'halt_reason': halt_reason,
        'dd_pauses': dd_count,
    }


def build_crypto_backtest_tab():
    """Crypto backtest — BTC/KRW and USDT/KRW mean reversion on Bithumb, 24/7."""

    with ui.column().classes('w-full gap-4 p-4'):
        ui.label('BACKTEST — Crypto (Bithumb)').classes('text-3xl font-extrabold').style(
            'background: linear-gradient(135deg, #00bcd4 0%, #e040fb 100%); '
            '-webkit-background-clip: text; -webkit-text-fill-color: transparent;'
        )
        with ui.row().classes('gap-2 -mt-2'):
            ui.badge('24/7').props('color="cyan" text-color="black"').classes('text-xs')
            ui.badge('Bithumb 0.04%').props('color="dark" text-color="cyan"').classes('text-xs')
            ui.badge('Automated').props('color="dark" text-color="white"').classes('text-xs')

        # Pair selector
        with ui.row().classes('w-full items-end gap-3 flex-wrap'):
            pair_select = ui.select(
                options={'BTC_KRW': 'BTC/KRW', 'USDT_KRW': 'USDT/KRW'},
                value='BTC_KRW', label='Pair',
            ).props('dense outlined').style('min-width: 150px;')
            cr_seed = ui.number(label='Seed (KRW)', value=1_000_000, format='%.0f').props('dense outlined').style('max-width: 150px;')

        # Mode: fixed or adaptive
        ui.label('STRATEGY PARAMS').classes('mono text-xs text-gray-500 mt-1')
        with ui.row().classes('w-full items-center gap-3'):
            cr_instant = ui.switch('Instant Buy (buy immediately, sell at +x%)', value=False).props('dense color=green')
            cr_fixed_seed = ui.switch('Fixed Seed (don\'t reinvest profits)', value=False).props('dense color=amber')
            cr_adaptive = ui.switch('Adaptive (auto-scale to volatility)', value=True).props('dense color=cyan')
            cr_vol_info = ui.label('').classes('mono text-xs text-gray-500')

        # Fixed params
        fixed_row = ui.row().classes('w-full items-end gap-3 flex-wrap')
        fixed_row.set_visibility(False)
        with fixed_row:
            cr_ma = ui.number(label='MA (hours)', value=6, format='%.0f').props('dense outlined').style('max-width: 90px;')
            cr_dip = ui.number(label='Buy Dip %', value=0.5, step=0.05, format='%.2f').props('dense outlined').style('max-width: 90px;')
            cr_gain = ui.number(label='Sell Gain %', value=1.5, step=0.05, format='%.2f').props('dense outlined').style('max-width: 90px;')
            cr_sl = ui.number(label='Stop Loss %', value=5.0, step=0.5, format='%.1f').props('dense outlined').style('max-width: 90px;')

        # Adaptive params (multipliers of 24h volatility)
        adapt_row = ui.row().classes('w-full items-end gap-3 flex-wrap')
        with adapt_row:
            cr_ma_adapt = ui.number(label='MA (hours)', value=24, format='%.0f').props('dense outlined').style('max-width: 90px;')
            cr_dip_mult = ui.number(label='Buy Dip ×vol', value=1.0, step=0.5, format='%.1f').props('dense outlined').style('max-width: 100px;')
            cr_gain_mult = ui.number(label='Sell Gain ×vol', value=1.5, step=0.5, format='%.1f').props('dense outlined').style('max-width: 100px;')
            cr_sl_mult = ui.number(label='Stop Loss ×vol', value=5.0, step=1.0, format='%.1f').props('dense outlined').style('max-width: 100px;')

        def _on_mode_toggle(e):
            fixed_row.set_visibility(not e.value)
            adapt_row.set_visibility(e.value)

        cr_adaptive.on_value_change(_on_mode_toggle)

        ui.label('SAFETY LOCKS').classes('mono text-xs text-gray-500 mt-1')
        with ui.row().classes('w-full items-end gap-3 flex-wrap'):
            cr_max_t = ui.number(label='Max Trades/Day', value=3, format='%.0f').props('dense outlined').style('max-width: 110px;')
            cr_vol = ui.number(label='Max 12h Vol %', value=1.5, step=0.1, format='%.1f').props('dense outlined').style('max-width: 100px;')
            cr_cool = ui.number(label='SL Cooldown (hrs)', value=3, format='%.0f').props('dense outlined').style('max-width: 110px;')
            cr_daily_loss = ui.number(label='Daily Loss Limit %', value=3.0, step=0.5, format='%.1f').props('dense outlined').style('max-width: 120px;')
            cr_max_dd = ui.number(label='Max Drawdown %', value=10.0, step=1.0, format='%.1f').props('dense outlined').style('max-width: 120px;')
            cr_dd_pause = ui.number(label='DD Pause (hrs)', value=48, format='%.0f').props('dense outlined').style('max-width: 110px;')
            ui.label('0 = permanent halt').classes('mono text-xs text-gray-600 self-center')

        # Auto-fill params when pair changes
        def on_pair_change(e):
            defaults = PAIR_DEFAULTS.get(e.value, {})
            cr_ma.value = defaults.get('ma', 6)
            cr_dip.value = defaults.get('dip', 0.5)
            cr_gain.value = defaults.get('gain', 1.5)
            cr_sl.value = defaults.get('sl', 5.0)
            cr_max_t.value = defaults.get('max_trades', 3)
            cr_vol.value = defaults.get('max_vol', 1.5)
            cr_cool.value = defaults.get('cooldown', 3)
            cr_daily_loss.value = defaults.get('daily_loss_limit', 3.0)
            cr_max_dd.value = defaults.get('max_drawdown', 10.0)

        pair_select.on_value_change(on_pair_change)

        # Date range
        with ui.row().classes('w-full items-end gap-3'):
            cr_lookback = ui.select(
                options={'30': '1 Month', '90': '3 Months', '180': '6 Months'},
                value='30', label='Lookback',
            ).props('dense outlined').style('max-width: 130px;')
            cr_custom = ui.switch('Custom Dates').props('dense color=cyan')

        date_row = ui.row().classes('w-full items-end gap-3')
        date_row.set_visibility(False)
        with date_row:
            with ui.input('Start').style('max-width: 150px;').props('dense outlined') as cr_start:
                with cr_start.add_slot('append'):
                    ui.icon('edit_calendar').on('click', lambda: sm.open()).classes('cursor-pointer')
                with ui.menu() as sm:
                    ui.date(on_change=lambda e: (cr_start.set_value(e.value), sm.close()))
            with ui.input('End').style('max-width: 150px;').props('dense outlined') as cr_end:
                with cr_end.add_slot('append'):
                    ui.icon('edit_calendar').on('click', lambda: em.open()).classes('cursor-pointer')
                with ui.menu() as em:
                    ui.date(on_change=lambda e: (cr_end.set_value(e.value), em.close()))

        cr_custom.on_value_change(lambda e: (date_row.set_visibility(e.value), cr_lookback.set_visibility(not e.value)))

        result_container = ui.column().classes('w-full gap-2')

        def run_backtest():
            result_container.clear()

            use_custom = cr_custom.value
            sd = cr_start.value if use_custom else None
            ed = cr_end.value if use_custom else None
            if not sd or not ed:
                ed = datetime.now().strftime('%Y-%m-%d')
                sd = (datetime.now() - timedelta(days=int(cr_lookback.value))).strftime('%Y-%m-%d')

            if use_custom and (not cr_start.value or not cr_end.value):
                with result_container:
                    ui.label('Select both dates').classes('text-amber-400')
                return

            if cr_adaptive.value:
                result = _run_crypto_adaptive(
                    pair=pair_select.value,
                    seed=cr_seed.value or 1_000_000,
                    ma_period=int(cr_ma_adapt.value or 24),
                    dip_mult=cr_dip_mult.value or 1.0,
                    gain_mult=cr_gain_mult.value or 1.5,
                    sl_mult=cr_sl_mult.value or 5.0,
                    max_trades_day=int(cr_max_t.value or 0),
                    max_vol_pct=cr_vol.value or 0,
                    cooldown_hrs=int(cr_cool.value or 0),
                    daily_loss_limit_pct=cr_daily_loss.value or 0,
                    max_drawdown_pct=cr_max_dd.value or 0,
                    dd_pause_hrs=int(cr_dd_pause.value or 0),
                    instant_buy=cr_instant.value,
                    fixed_seed=cr_fixed_seed.value,
                    start_date=sd, end_date=ed,
                )
            else:
                result = _run_crypto_mr(
                    pair=pair_select.value,
                    seed=cr_seed.value or 1_000_000,
                    ma_period=int(cr_ma.value or 6),
                    buy_dip_pct=cr_dip.value or 0.5,
                    sell_gain_pct=cr_gain.value or 1.5,
                    sl_pct=cr_sl.value or 5.0,
                    max_trades_day=int(cr_max_t.value or 0),
                    max_vol_pct=cr_vol.value or 0,
                    cooldown_hrs=int(cr_cool.value or 0),
                    daily_loss_limit_pct=cr_daily_loss.value or 0,
                    max_drawdown_pct=cr_max_dd.value or 0,
                    dd_pause_hrs=int(cr_dd_pause.value or 0),
                    instant_buy=cr_instant.value,
                    fixed_seed=cr_fixed_seed.value,
                    start_date=sd, end_date=ed,
                )

            seed = cr_seed.value or 1_000_000
            pair_label = PAIR_DEFAULTS.get(pair_select.value, {}).get('label', pair_select.value)
            pnl_color = '#00e676' if result['pnl'] >= 0 else '#ff1744'

            # Show adaptive info
            if cr_adaptive.value:
                candles = _fetch_candles(pair_select.value, '1h', sd, ed)
                if candles and len(candles) > 24:
                    recent_prices = [c[1] for c in candles[-24:]]
                    rets = [(recent_prices[j]-recent_prices[j-1])/recent_prices[j-1]*100 for j in range(1, len(recent_prices))]
                    mean_r = sum(rets)/len(rets)
                    last_vol = (sum((r-mean_r)**2 for r in rets)/len(rets))**0.5
                    dm = cr_dip_mult.value or 1.0
                    gm = cr_gain_mult.value or 1.5
                    sm = cr_sl_mult.value or 5.0
                    cr_vol_info.text = (
                        f'Latest 24h vol: {last_vol:.3f}% → '
                        f'Buy dip: {max(0.05, last_vol*dm):.2f}% | '
                        f'Sell gain: {max(0.05, last_vol*gm):.2f}% | '
                        f'SL: {max(0.5, last_vol*sm):.2f}%'
                    )
                else:
                    cr_vol_info.text = ''
            else:
                cr_vol_info.text = 'Fixed mode — params don\'t adjust to volatility'

            # Tax estimate (가상자산 과세)
            lb = (datetime.strptime(ed, '%Y-%m-%d') - datetime.strptime(sd, '%Y-%m-%d')).days or 30
            annual_pnl = result['pnl'] * (365 / lb) if lb else 0
            tax = max(0, annual_pnl - 2_500_000) * 0.22 * (lb / 365) if annual_pnl > 2_500_000 else 0
            net = result['pnl'] - tax

            with result_container:
                ui.label(f'Period: {sd} to {ed} · {pair_label}').classes('mono text-xs text-gray-500')

                # Price trend chart with buy/sell markers
                candle_data = _fetch_candles(pair_select.value, '1h', sd, ed)
                if candle_data and len(candle_data) > 5:
                    import plotly.graph_objects as go
                    chart_dates = [d[0] for d in candle_data]
                    chart_prices = [d[1] for d in candle_data]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=chart_dates, y=chart_prices, mode='lines', name=pair_label,
                        line=dict(color='#ffd740', width=1.5),
                        hovertemplate='%{x}<br>\u20a9%{y:,.0f}<extra></extra>',
                    ))

                    # Mark buys and sells
                    buy_trades = [t for t in result['trades'] if t['type'] == 'BUY']
                    sell_trades = [t for t in result['trades'] if t['type'] == 'SELL']
                    if buy_trades:
                        fig.add_trace(go.Scatter(
                            x=[t['date'] for t in buy_trades],
                            y=[t['rate'] for t in buy_trades],
                            mode='markers', name='BUY',
                            marker=dict(color='#00e676', size=8, symbol='triangle-up'),
                            hovertemplate='BUY %{x}<br>\u20a9%{y:,.0f}<extra></extra>',
                        ))
                    if sell_trades:
                        sell_colors = ['#00e676' if t.get('profit', 0) >= 0 else '#ff1744' for t in sell_trades]
                        fig.add_trace(go.Scatter(
                            x=[t['date'] for t in sell_trades],
                            y=[t['rate'] for t in sell_trades],
                            mode='markers', name='SELL',
                            marker=dict(color=sell_colors, size=8, symbol='triangle-down'),
                            hovertemplate='SELL %{x}<br>\u20a9%{y:,.0f}<extra></extra>',
                        ))

                    p_min, p_max = min(chart_prices), max(chart_prices)
                    pad = (p_max - p_min) * 0.1
                    fig.update_layout(
                        xaxis=dict(gridcolor='#1e1e2e', tickfont=dict(size=9, color='#555')),
                        yaxis=dict(gridcolor='#1e1e2e', tickfont=dict(size=10, color='#666'),
                                   tickformat=',.0f', range=[p_min - pad, p_max + pad]),
                        plot_bgcolor='#0a0a0f', paper_bgcolor='#0a0a0f',
                        font=dict(color='#e8e8f0', family='Outfit, sans-serif'),
                        margin=dict(l=80, r=10, t=10, b=30),
                        height=280, legend=dict(orientation='h', y=1.1, font=dict(size=10)),
                        hovermode='x unified',
                    )
                    ui.plotly(fig).classes('w-full')

                dd_pauses = result.get('dd_pauses', 0)
                if result['halted']:
                    ui.label(f'HALTED: {result["halt_reason"]}').classes('font-bold').style('color: #ff1744;')
                elif dd_pauses:
                    ui.label(f'Drawdown triggered {dd_pauses}x — paused and resumed each time').classes('font-bold').style('color: #ff9100;')

                with ui.card().classes('w-full p-4').style('background: #1a1a2a; border: 1px solid #2a2a3a;'):
                    ui.label(f'{pair_label} Mean Reversion (24/7 Bithumb)').classes('font-bold').style('color: #00bcd4;')

                    with ui.row().classes('w-full gap-4 flex-wrap mt-2'):
                        for label, val, color in [
                            ('Seed', f'\u20a9{seed:,.0f}', '#888'),
                            ('Cycles', f'{result["num_sells"]}', '#00bcd4'),
                            ('Win Rate', f'{result["num_wins"]}/{result["num_sells"]} ({result["win_rate"]:.0f}%)', '#888'),
                            ('Gross P&L', f'\u20a9{result["pnl"]:+,.0f} ({result["pnl_pct"]:+.2f}%)', pnl_color),
                            ('Bithumb Fees', f'-\u20a9{result["total_fees"]:,.0f}', '#ff9100'),
                            ('Est. Tax', f'-\u20a9{tax:,.0f}' if tax else '\u20a90 (under exemption)', '#ff9100'),
                            ('Net Profit', f'\u20a9{net:+,.0f}', '#00e676' if net >= 0 else '#ff1744'),
                            ('Final Balance', f'\u20a9{result["final_balance"]:,.0f}', '#ffd740'),
                        ]:
                            with ui.column().classes('gap-0'):
                                ui.label(label).classes('mono text-xs text-gray-500')
                                ui.label(val).style(f'color: {color}; font-weight: 700;')

                # Safety locks report
                with ui.card().classes('w-full p-3 mt-2').style('background: #1a1a2a; border: 1px solid #2a2a3a;'):
                    ui.label('SAFETY LOCKS STATUS').classes('mono text-xs text-gray-500')
                    locks = [
                        ('Max Trades/Day', f'{int(cr_max_t.value or 0)}', 'Limits cycles per day'),
                        ('Max 12h Volatility', f'{cr_vol.value or 0:.1f}%', 'Skips volatile hours'),
                        ('SL Cooldown', f'{int(cr_cool.value or 0)}h', 'Pause after stop-loss'),
                        ('Daily Loss Limit', f'{cr_daily_loss.value or 0:.1f}%', 'Stop trading if daily loss exceeds'),
                        ('Max Drawdown', f'{cr_max_dd.value or 0:.1f}%', f'Pause {int(cr_dd_pause.value or 0)}h then resume (0h = permanent halt)'),
                    ]
                    for name, val, desc in locks:
                        active = val not in ('0', '0.0%', '0h')
                        color = '#00e676' if active else '#555'
                        ui.label(f'  {"●" if active else "○"} {name}: {val} — {desc}').classes('mono text-xs').style(f'color: {color};')

                    if result['halted']:
                        ui.label(f'  ⚠ HALTED: {result["halt_reason"]}').classes('mono text-xs font-bold').style('color: #ff1744;')

                # Trade log
                active_trades = [t for t in result['trades'] if t['type'] in ('BUY', 'SELL', 'HALT', 'PAUSE')]
                if active_trades:
                    with ui.expansion(text=f'{len(active_trades)} trades').props(
                        'dense header-class="text-sm font-bold"'
                    ).classes('w-full mt-2').style('color: #00bcd4;'):
                        with ui.row().classes('w-full px-2 py-1').style('border-bottom: 1px solid #2a2a3a;'):
                            for h, w in [('Time', '140px'), ('Type', '45px'), ('Rate', '110px'),
                                         ('Units', '90px'), ('KRW', '110px'), ('P&L', '100px'), ('Signal', '160px')]:
                                ui.label(h).classes('mono text-xs text-gray-500').style(f'width: {w};')
                        for t in active_trades:
                            tc = {'BUY': '#00e676', 'SELL': '#ff1744', 'HALT': '#ff9100', 'PAUSE': '#ff9100'}.get(t['type'], '#888')
                            with ui.row().classes('w-full px-2 py-1').style('border-bottom: 1px solid #1a1a2a;'):
                                ui.label(t['date']).classes('mono text-xs text-gray-400').style('width: 140px;')
                                ui.label(t['type']).classes('mono text-xs font-bold').style(f'width: 45px; color: {tc};')
                                ui.label(f'\u20a9{t["rate"]:,.0f}').classes('mono text-xs').style('width: 110px;')
                                ui.label(f'{t.get("units",0):,.4f}').classes('mono text-xs').style('width: 90px;')
                                ui.label(f'\u20a9{t["amount"]:,.0f}').classes('mono text-xs').style('width: 110px;')
                                p = t.get('profit')
                                if p is not None:
                                    ui.label(f'\u20a9{p:+,.0f}').classes('mono text-xs').style(
                                        f'width: 100px; color: {"#00e676" if p >= 0 else "#ff1744"};')
                                else:
                                    ui.label('\u2014').classes('mono text-xs text-gray-600').style('width: 100px;')
                                ui.label(t.get('signal', '')).classes('mono text-xs text-gray-500').style('width: 160px;')

                ui.label(
                    f'Bithumb fee: 0.04% per trade (maker/taker). '
                    f'Round-trip: 0.08%. All fees included in P&L. '
                    f'Tax: 가상자산 과세 22% on gains > \u20a92.5M/year.'
                ).classes('mono text-xs text-gray-600 mt-2')

        def reset_crypto():
            defaults = PAIR_DEFAULTS.get(pair_select.value, PAIR_DEFAULTS['BTC_KRW'])
            cr_seed.value = 1_000_000
            cr_ma.value = defaults['ma']
            cr_dip.value = defaults['dip']
            cr_gain.value = defaults['gain']
            cr_sl.value = defaults['sl']
            cr_max_t.value = defaults['max_trades']
            cr_vol.value = defaults['max_vol']
            cr_cool.value = defaults['cooldown']
            cr_daily_loss.value = defaults['daily_loss_limit']
            cr_max_dd.value = defaults['max_drawdown']
            cr_dd_pause.value = 48
            cr_instant.value = False
            cr_fixed_seed.value = False
            cr_lookback.value = '30'
            cr_custom.value = False
            cr_start.value = ''
            cr_end.value = ''
            date_row.set_visibility(False)
            cr_lookback.set_visibility(True)
            result_container.clear()

        with ui.row().classes('gap-2 mt-2'):
            ui.button('Run Crypto Backtest', icon='play_arrow', on_click=run_backtest).props(
                'color=cyan text-color=black'
            )
            ui.button('Reset', icon='restart_alt', on_click=reset_crypto).props(
                'flat dense color=red-4'
            )
