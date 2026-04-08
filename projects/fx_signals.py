"""FX Signal Engine — multi-factor scoring for USD/KRW opportunistic trades.

Combines technical indicators with macro context to produce actionable signals.
Designed for a hybrid DCA + opportunistic strategy.

Signal levels:
  STRONG_BUY  → Buy 2-3x DCA amount (rate deeply undervalued)
  BUY         → Buy 1.5x DCA amount (rate below fair value)
  HOLD        → DCA only (rate near fair value)
  TAKE_PROFIT → Sell some USD (rate above fair value)
  STRONG_SELL → Sell aggressively (rate deeply overvalued or BOK intervention risk)
"""

import logging
from datetime import datetime, timedelta
from projects.fx_data import fetch_history

logger = logging.getLogger(__name__)


def compute_signals(base='KRW', target='USD'):
    """Compute all signals for the given pair. Returns dict with full analysis."""
    history = fetch_history(base, target, days=180)
    if not history or len(history) < 30:
        return None

    # Convert to KRW per 1 USD
    rates = [(d, 1 / r) for d, r in history if r]
    if len(rates) < 30:
        return None

    dates = [r[0] for r in rates]
    prices = [r[1] for r in rates]
    current = prices[-1]

    # ── Technical Indicators ──
    ma20 = _sma(prices, 20)
    ma50 = _sma(prices, 50)
    ma20_val = ma20[-1] if ma20 else current
    ma50_val = ma50[-1] if ma50 else current

    # MA deviation: how far current price is from 20-day MA (%)
    ma20_dev = ((current - ma20_val) / ma20_val * 100) if ma20_val else 0

    # RSI (14-day)
    rsi = _rsi(prices, 14)

    # Bollinger Bands (20-day, 2 std)
    bb_upper, bb_mid, bb_lower = _bollinger(prices, 20, 2)

    # Rate of change (7-day)
    roc_7d = ((current - prices[-8]) / prices[-8] * 100) if len(prices) >= 8 else 0

    # Volatility (20-day rolling std of daily returns)
    volatility = _rolling_volatility(prices, 20)

    # 52-week high/low context
    high_52w = max(prices)
    low_52w = min(prices)
    range_52w = high_52w - low_52w
    position_in_range = ((current - low_52w) / range_52w * 100) if range_52w else 50

    # ── Multi-Factor Score ──
    # Score from -100 (strong sell) to +100 (strong buy)
    # Positive = buy USD opportunity, Negative = sell/take profit
    score = 0
    reasons = []

    # Factor 1: MA20 deviation (weight: 30)
    if ma20_dev < -1.5:
        score += 30
        reasons.append(f'Rate {abs(ma20_dev):.1f}% below 20-day MA — undervalued')
    elif ma20_dev < -1.0:
        score += 20
        reasons.append(f'Rate {abs(ma20_dev):.1f}% below 20-day MA')
    elif ma20_dev < -0.5:
        score += 10
        reasons.append(f'Rate slightly below 20-day MA')
    elif ma20_dev > 1.5:
        score -= 30
        reasons.append(f'Rate {ma20_dev:.1f}% above 20-day MA — overvalued')
    elif ma20_dev > 1.0:
        score -= 20
        reasons.append(f'Rate {ma20_dev:.1f}% above 20-day MA')
    elif ma20_dev > 0.5:
        score -= 10
        reasons.append(f'Rate slightly above 20-day MA')

    # Factor 2: RSI (weight: 25)
    if rsi < 25:
        score += 25
        reasons.append(f'RSI {rsi:.0f} — deeply oversold (KRW unusually strong)')
    elif rsi < 35:
        score += 15
        reasons.append(f'RSI {rsi:.0f} — oversold territory')
    elif rsi > 75:
        score -= 25
        reasons.append(f'RSI {rsi:.0f} — deeply overbought (KRW unusually weak)')
    elif rsi > 65:
        score -= 15
        reasons.append(f'RSI {rsi:.0f} — overbought territory')

    # Factor 3: Bollinger Band position (weight: 20)
    if current < bb_lower:
        score += 20
        reasons.append(f'Below lower Bollinger Band — statistically cheap')
    elif current > bb_upper:
        score -= 20
        reasons.append(f'Above upper Bollinger Band — statistically expensive')

    # Factor 4: 7-day rate of change (weight: 15)
    if roc_7d < -2.0:
        score += 15
        reasons.append(f'Sharp drop ({roc_7d:.1f}% in 7 days) — potential bounce')
    elif roc_7d < -1.0:
        score += 8
        reasons.append(f'Declining ({roc_7d:.1f}% in 7 days)')
    elif roc_7d > 2.0:
        score -= 15
        reasons.append(f'Sharp spike ({roc_7d:+.1f}% in 7 days) — potential pullback')
    elif roc_7d > 1.0:
        score -= 8
        reasons.append(f'Rising ({roc_7d:+.1f}% in 7 days)')

    # Factor 5: Position in 52-week range (weight: 10)
    if position_in_range < 20:
        score += 10
        reasons.append(f'Near 52-week low ({position_in_range:.0f}th percentile) — historically cheap')
    elif position_in_range > 80:
        score -= 10
        reasons.append(f'Near 52-week high ({position_in_range:.0f}th percentile) — historically expensive')

    # ── Signal Level ──
    if score >= 50:
        signal = 'STRONG_BUY'
    elif score >= 25:
        signal = 'BUY'
    elif score <= -50:
        signal = 'STRONG_SELL'
    elif score <= -25:
        signal = 'TAKE_PROFIT'
    else:
        signal = 'HOLD'

    return {
        'signal': signal,
        'score': score,
        'reasons': reasons,
        'current_rate': current,
        'ma20': ma20_val,
        'ma50': ma50_val,
        'ma20_dev_pct': ma20_dev,
        'rsi': rsi,
        'bb_upper': bb_upper,
        'bb_mid': bb_mid,
        'bb_lower': bb_lower,
        'roc_7d': roc_7d,
        'volatility': volatility,
        'high_52w': high_52w,
        'low_52w': low_52w,
        'position_in_range': position_in_range,
        # Chart data
        'dates': dates,
        'prices': prices,
        'ma20_series': ma20,
        'ma50_series': ma50,
    }


def backtest(base='KRW', target='USD', dca_amount=500_000, dca_interval_days=14,
             wudae_pct=90, base_spread_pct=0.25, scalp_target_pct=0.5,
             take_profit_pct=0, stop_loss_pct=0,
             lookback_days=365, seed_money=None):
    """Backtest 3 strategies over a configurable period.
    take_profit_pct: sell entire position when avg gain hits this %  (0 = disabled)
    stop_loss_pct:   sell entire position when avg loss hits this %  (0 = disabled)
    """
    history = fetch_history(base, target, days=lookback_days)
    if not history or len(history) < 20:
        return None

    rates = [(d, 1 / r) for d, r in history if r]
    if len(rates) < 20:
        return None

    spread = base_spread_pct * (1 - wudae_pct / 100) / 100
    cap = seed_money or float('inf')
    tp_sl = (take_profit_pct, stop_loss_pct)

    dca_result = _run_dca(rates, dca_amount, dca_interval_days, spread, cap, tp_sl)
    signal_result = _run_signal_dca(rates, dca_amount, dca_interval_days, spread, cap, tp_sl)
    scalp_result = _run_dca_scalp(rates, dca_amount, dca_interval_days, spread, scalp_target_pct, cap)
    cycle_result = _run_buy_sell_repeat(rates, spread, scalp_target_pct, sl_pct=stop_loss_pct, seed=cap)

    return {
        'dca': dca_result,
        'signal': signal_result,
        'scalp': scalp_result,
        'cycle': cycle_result,
        'seed_money': seed_money,
        'period': f'{rates[0][0]} to {rates[-1][0]}',
        'data_points': len(rates),
    }


def _finalize(total_spent, total_units, realized_pnl, prices_list, trades, sells=0):
    """Compute final results for a strategy."""
    final_rate = prices_list[-1]
    current_value = total_units * final_rate
    avg_cost = total_spent / total_units if total_units else 0
    unrealized = current_value - (total_units * avg_cost) if total_units else 0
    total_pnl = realized_pnl + unrealized
    # Capital base = total KRW ever spent on buys (including lots that were later sold)
    total_ever_bought = sum(t['amount'] for t in trades if t.get('type') == 'BUY')
    pnl_pct = (total_pnl / total_ever_bought * 100) if total_ever_bought else 0

    return {
        'total_spent': total_spent,
        'total_units': total_units,
        'avg_cost': avg_cost,
        'current_value': current_value,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized,
        'pnl': total_pnl,
        'pnl_pct': pnl_pct,
        'num_buys': len([t for t in trades if t.get('type') == 'BUY']),
        'num_sells': sells,
        'num_skipped': len([t for t in trades if t.get('type') == 'SKIP']),
        'trades': trades,
    }


def _run_dca(rates, base_amount, interval_days, spread, cap=float('inf'), tp_sl=(0, 0)):
    """Pure DCA: buy on schedule, sell on take-profit/stop-loss."""
    total_spent = 0
    total_units = 0
    total_cost_basis = 0  # tracks total KRW spent on currently-held units
    realized_pnl = 0
    trades = []
    prices = [r[1] for r in rates]
    sell_count = 0
    next_buy = 0
    tp_pct, sl_pct = tp_sl

    for i in range(len(rates)):
        date, price = rates[i]
        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)

        # Buy on schedule if under cap
        if i >= next_buy and total_spent < cap:
            amount = min(base_amount, cap - total_spent)
            units = amount / ask
            total_spent += amount
            total_units += units
            total_cost_basis += amount
            trades.append({'date': date, 'type': 'BUY', 'signal': 'DCA', 'amount': amount, 'units': units, 'rate': price})
            next_buy = i + interval_days

        # Check take-profit / stop-loss on entire position
        if total_units > 0 and (tp_pct or sl_pct):
            avg_cost = total_cost_basis / total_units
            gain_pct = (bid - avg_cost) / avg_cost * 100

            sell_signal = None
            if tp_pct and gain_pct >= tp_pct:
                sell_signal = f'TP +{gain_pct:.1f}%'
            elif sl_pct and gain_pct <= -sl_pct:
                sell_signal = f'SL {gain_pct:.1f}%'

            if sell_signal:
                proceeds = total_units * bid
                profit = proceeds - total_cost_basis
                realized_pnl += profit
                sell_count += 1
                trades.append({
                    'date': date, 'type': 'SELL', 'signal': sell_signal,
                    'amount': proceeds, 'units': total_units, 'rate': price, 'profit': profit,
                })
                total_units = 0
                total_cost_basis = 0

    return _finalize(total_cost_basis, total_units, realized_pnl, prices, trades, sells=sell_count)


def _run_signal_dca(rates, base_amount, interval_days, spread, cap=float('inf'), tp_sl=(0, 0)):
    """Signal DCA: adjust buy amount by signal, sell on take-profit/stop-loss."""
    total_spent = 0
    total_units = 0
    total_cost_basis = 0
    realized_pnl = 0
    trades = []
    prices = [r[1] for r in rates]
    sell_count = 0
    next_buy = 0
    tp_pct, sl_pct = tp_sl

    for i in range(len(rates)):
        date, price = rates[i]
        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)

        # Buy on schedule
        if i >= next_buy and total_spent < cap:
            window = prices[:i + 1]
            ma20_val = sum(window[-20:]) / 20 if len(window) >= 20 else price
            ma20_dev = (price - ma20_val) / ma20_val * 100
            rsi = _rsi(window, 14)

            if ma20_dev < -1.5 and rsi < 35:
                multiplier, signal = 2.5, 'STRONG_BUY'
            elif ma20_dev < -0.5 or rsi < 40:
                multiplier, signal = 1.5, 'BUY'
            elif ma20_dev > 1.5 or rsi > 70:
                multiplier, signal = 0, 'SKIP'
            else:
                multiplier, signal = 1.0, 'HOLD'

            amount = base_amount * multiplier
            if amount <= 0:
                trades.append({'date': date, 'type': 'SKIP', 'signal': signal, 'amount': 0, 'units': 0, 'rate': price})
            else:
                amount = min(amount, cap - total_spent)
                units = amount / ask
                total_spent += amount
                total_units += units
                total_cost_basis += amount
                trades.append({'date': date, 'type': 'BUY', 'signal': signal, 'amount': amount, 'units': units, 'rate': price})

            next_buy = i + interval_days

        # Check take-profit / stop-loss
        if total_units > 0 and (tp_pct or sl_pct):
            avg_cost = total_cost_basis / total_units
            gain_pct = (bid - avg_cost) / avg_cost * 100

            sell_signal = None
            if tp_pct and gain_pct >= tp_pct:
                sell_signal = f'TP +{gain_pct:.1f}%'
            elif sl_pct and gain_pct <= -sl_pct:
                sell_signal = f'SL {gain_pct:.1f}%'

            if sell_signal:
                proceeds = total_units * bid
                profit = proceeds - total_cost_basis
                realized_pnl += profit
                sell_count += 1
                trades.append({
                    'date': date, 'type': 'SELL', 'signal': sell_signal,
                    'amount': proceeds, 'units': total_units, 'rate': price, 'profit': profit,
                })
                total_units = 0
                total_cost_basis = 0

    return _finalize(total_cost_basis, total_units, realized_pnl, prices, trades, sells=sell_count)


def _run_dca_scalp(rates, base_amount, interval_days, spread, target_pct, cap=float('inf')):
    """DCA + Scalp: buy on DCA schedule (up to cap), sell lots at target_pct% profit."""
    lots = []
    total_spent = 0
    realized_pnl = 0
    trades = []
    prices = [r[1] for r in rates]
    sell_count = 0

    next_buy = 0
    for i in range(len(rates)):
        date, price = rates[i]
        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)

        # Buy on schedule if under cap
        if i >= next_buy and total_spent < cap:
            amount = min(base_amount, cap - total_spent)
            units = amount / ask
            lots.append({'date': date, 'units': units, 'cost_per_unit': ask, 'cost_krw': amount})
            total_spent += amount
            trades.append({'date': date, 'type': 'BUY', 'signal': 'DCA', 'amount': amount, 'units': units, 'rate': price})
            next_buy = i + interval_days

        # Check each lot for profit target
        remaining_lots = []
        for lot in lots:
            gain_pct = (bid - lot['cost_per_unit']) / lot['cost_per_unit'] * 100
            if gain_pct >= target_pct:
                # Sell this lot
                proceeds = lot['units'] * bid
                profit = proceeds - lot['cost_krw']
                realized_pnl += profit
                sell_count += 1
                trades.append({
                    'date': date, 'type': 'SELL', 'signal': f'+{gain_pct:.1f}%',
                    'amount': proceeds, 'units': lot['units'], 'rate': price,
                    'profit': profit,
                })
            else:
                remaining_lots.append(lot)
        lots = remaining_lots

    # Remaining units
    total_units = sum(lot['units'] for lot in lots)
    remaining_cost = sum(lot['cost_krw'] for lot in lots)

    return _finalize(remaining_cost, total_units, realized_pnl, prices, trades, sells=sell_count)


def _run_buy_sell_repeat(rates, spread, tp_pct, sl_pct=0, seed=1_000_000):
    """Buy-Sell-Repeat: go all-in → sell at TP% → re-buy with proceeds → repeat.
    Capital compounds with each successful cycle. Stop-loss exits and re-enters next day.
    """
    balance = seed       # KRW available
    units = 0.0          # USD held
    cost_basis = 0.0     # KRW spent on current position
    realized_pnl = 0.0
    trades = []
    prices = [r[1] for r in rates]
    buy_count = 0
    sell_count = 0

    for i in range(len(rates)):
        date, price = rates[i]
        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)

        # If no position, buy all-in
        if units == 0 and balance > 0:
            units = balance / ask
            cost_basis = balance
            buy_count += 1
            trades.append({
                'date': date, 'type': 'BUY', 'signal': 'ALL-IN',
                'amount': balance, 'units': units, 'rate': price,
            })
            balance = 0

        # If holding, check TP / SL
        if units > 0:
            avg_cost = cost_basis / units
            gain_pct = (bid - avg_cost) / avg_cost * 100

            sell_signal = None
            if tp_pct and gain_pct >= tp_pct:
                sell_signal = f'TP +{gain_pct:.1f}%'
            elif sl_pct and gain_pct <= -sl_pct:
                sell_signal = f'SL {gain_pct:.1f}%'

            if sell_signal:
                proceeds = units * bid
                profit = proceeds - cost_basis
                realized_pnl += profit
                sell_count += 1
                trades.append({
                    'date': date, 'type': 'SELL', 'signal': sell_signal,
                    'amount': proceeds, 'units': units, 'rate': price,
                    'profit': profit,
                })
                balance = proceeds  # recycle capital for next cycle
                units = 0
                cost_basis = 0

    # If still holding at end, count as unrealized
    total_ever_bought = sum(t['amount'] for t in trades if t['type'] == 'BUY')
    current_value = units * prices[-1] if units else 0
    unrealized = current_value - cost_basis if units else 0
    total_pnl = realized_pnl + unrealized
    pnl_pct = (total_pnl / seed * 100) if seed else 0

    return {
        'total_spent': cost_basis,  # currently invested
        'total_units': units,
        'avg_cost': cost_basis / units if units else 0,
        'current_value': current_value,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized,
        'pnl': total_pnl,
        'pnl_pct': pnl_pct,
        'num_buys': buy_count,
        'num_sells': sell_count,
        'num_skipped': 0,
        'trades': trades,
        'final_balance': balance + current_value,
        'num_cycles': sell_count,
    }


# ── Technical indicator helpers ──

def _sma(data, period):
    """Simple moving average. Returns list same length as data (NaN-padded as 0)."""
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(data[i])
        else:
            result.append(sum(data[i - period + 1:i + 1]) / period)
    return result


def _rsi(data, period=14):
    """Relative Strength Index. Returns single value for latest."""
    if len(data) < period + 1:
        return 50  # neutral default

    changes = [data[i] - data[i - 1] for i in range(1, len(data))]
    gains = [max(0, c) for c in changes]
    losses = [max(0, -c) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _bollinger(data, period=20, num_std=2):
    """Bollinger Bands. Returns (upper, mid, lower) for latest value."""
    if len(data) < period:
        return data[-1], data[-1], data[-1]

    window = data[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = variance ** 0.5
    return mid + num_std * std, mid, mid - num_std * std


def _rolling_volatility(data, period=20):
    """Rolling annualized volatility (% daily std dev)."""
    if len(data) < period + 1:
        return 0
    returns = [(data[i] - data[i - 1]) / data[i - 1] * 100 for i in range(-period, 0)]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return variance ** 0.5
