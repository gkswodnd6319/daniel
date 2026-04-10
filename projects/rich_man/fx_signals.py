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
from projects.rich_man.fx_data import fetch_history, fetch_intraday_history

logger = logging.getLogger(__name__)

CAPITAL_TIER_PRESETS = {
    'tier1_10m': {
        'label': 'Tier 1: ₩10M/month (Starter)',
        'seed_money': 10_000_000,
        'dca_amount': 2_500_000,
        'dca_interval_days': 7,
        'scalp_target_pct': 0.5,
        'take_profit_pct': 2.0,
        'stop_loss_pct': 3.0,
        'max_wait_days': 5,
        'wudae_pct': 90,
    },
    'tier2_50m': {
        'label': 'Tier 2: ₩50M/month (Core)',
        'seed_money': 50_000_000,
        'dca_amount': 12_500_000,
        'dca_interval_days': 7,
        'scalp_target_pct': 0.5,
        'take_profit_pct': 2.0,
        'stop_loss_pct': 3.0,
        'max_wait_days': 5,
        'wudae_pct': 90,
    },
    'tier3_100m': {
        'label': 'Tier 3: ₩100M/month (Advanced)',
        'seed_money': 100_000_000,
        'dca_amount': 20_000_000,
        'dca_interval_days': 7,
        'scalp_target_pct': 0.5,
        'take_profit_pct': 2.5,
        'stop_loss_pct': 3.0,
        'max_wait_days': 3,
        'wudae_pct': 95,
    },
}


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
             lookback_days=365, seed_money=None, max_wait_days=5,
             mr_ma_period=5, mr_buy_dip_pct=0.5, mr_sell_gain_pct=0.3,
             start_date=None, end_date=None, mr_intraday=False,
             mr_max_trades_day=0, mr_max_vol=0, mr_cooldown_sl=0, mr_instant_buy=False, mr_fixed_seed=False):
    """Backtest 5 strategies. Uses start_date/end_date if provided, else lookback_days."""
    # Fetch enough history to cover the range (plus buffer for MA calculation)
    if start_date and end_date:
        delta = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days
        history = fetch_history(base, target, days=delta + 60)
    else:
        history = fetch_history(base, target, days=lookback_days)
    if not history or len(history) < 20:
        return None

    rates = [(d, 1 / r) for d, r in history if r]
    if start_date and end_date:
        rates = [(d, r) for d, r in rates if start_date <= d <= end_date]
    if len(rates) < 5:
        return None

    spread = base_spread_pct * (1 - wudae_pct / 100) / 100
    cap = seed_money or float('inf')
    tp_sl = (take_profit_pct, stop_loss_pct)

    dca_result = _run_dca(rates, dca_amount, dca_interval_days, spread, cap, tp_sl)
    signal_result = _run_signal_dca(rates, dca_amount, dca_interval_days, spread, cap, tp_sl)
    scalp_result = _run_dca_scalp(rates, dca_amount, dca_interval_days, spread, scalp_target_pct, cap)
    cycle_result = _run_buy_sell_repeat(rates, spread, scalp_target_pct, sl_pct=stop_loss_pct, seed=cap, max_wait=max_wait_days)
    if mr_intraday:
        # Ensure intraday always has date bounds (from custom dates or lookback_days)
        mr_sd = start_date
        mr_ed = end_date
        if not mr_sd or not mr_ed:
            mr_ed = datetime.now().strftime('%Y-%m-%d')
            mr_sd = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        mr_result = _run_mean_reversion_intraday(
            spread, mr_ma_period, mr_buy_dip_pct, mr_sell_gain_pct, stop_loss_pct, cap,
            start_date=mr_sd, end_date=mr_ed,
            max_trades_per_day=mr_max_trades_day, max_volatility_pct=mr_max_vol,
            cooldown_after_sl=mr_cooldown_sl, instant_buy=mr_instant_buy, fixed_seed=mr_fixed_seed,
        )
    else:
        mr_result = _run_mean_reversion(rates, spread, mr_ma_period, mr_buy_dip_pct, mr_sell_gain_pct, stop_loss_pct, cap)

    return {
        'dca': dca_result,
        'signal': signal_result,
        'scalp': scalp_result,
        'cycle': cycle_result,
        'mr': mr_result,
        'seed_money': seed_money,
        'period': f'{rates[0][0]} to {rates[-1][0]}',
        'data_points': len(rates),
    }


def backtest_monthly(base='KRW', target='USD', dca_amount=250_000, dca_interval_days=7,
                     wudae_pct=90, base_spread_pct=0.25, scalp_target_pct=0.5,
                     take_profit_pct=2.0, stop_loss_pct=3.0,
                     lookback_days=90, seed_money=1_000_000, max_wait_days=5,
                     mr_ma_period=5, mr_buy_dip_pct=0.5, mr_sell_gain_pct=0.3,
                     start_date=None, end_date=None, mr_intraday=False,
                     mr_max_trades_day=0, mr_max_vol=0, mr_cooldown_sl=0, mr_instant_buy=False, mr_fixed_seed=False):
    """Run backtest per-month: each month starts fresh with the seed money."""
    if start_date and end_date:
        delta = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.strptime(start_date, '%Y-%m-%d')).days
        history = fetch_history(base, target, days=delta + 60)
    else:
        history = fetch_history(base, target, days=lookback_days)
    if not history or len(history) < 20:
        return None

    rates = [(d, 1 / r) for d, r in history if r]
    if start_date and end_date:
        rates = [(d, r) for d, r in rates if start_date <= d <= end_date]
    if len(rates) < 5:
        return None

    spread = base_spread_pct * (1 - wudae_pct / 100) / 100
    cap = seed_money or float('inf')
    tp_sl = (take_profit_pct, stop_loss_pct)

    # Group rates by month
    from itertools import groupby
    months = []
    for month_key, group in groupby(rates, key=lambda r: r[0][:7]):
        month_rates = list(group)
        if len(month_rates) >= 5:  # need at least 5 trading days
            months.append((month_key, month_rates))

    if not months:
        return None

    monthly_results = []
    for month_key, month_rates in months:
        prices = [r[1] for r in month_rates]
        dca_r = _run_dca(month_rates, dca_amount, dca_interval_days, spread, cap, tp_sl)
        sig_r = _run_signal_dca(month_rates, dca_amount, dca_interval_days, spread, cap, tp_sl)
        sclp_r = _run_dca_scalp(month_rates, dca_amount, dca_interval_days, spread, scalp_target_pct, cap)
        cyc_r = _run_buy_sell_repeat(month_rates, spread, scalp_target_pct, sl_pct=stop_loss_pct, seed=cap, max_wait=max_wait_days)
        if mr_intraday:
            mr_r = _run_mean_reversion_intraday(
                spread, mr_ma_period, mr_buy_dip_pct, mr_sell_gain_pct, stop_loss_pct, cap,
                start_date=month_rates[0][0], end_date=month_rates[-1][0],
                max_trades_per_day=mr_max_trades_day, max_volatility_pct=mr_max_vol,
                cooldown_after_sl=mr_cooldown_sl, instant_buy=mr_instant_buy,
            )
        else:
            mr_r = _run_mean_reversion(month_rates, spread, mr_ma_period, mr_buy_dip_pct, mr_sell_gain_pct, stop_loss_pct, cap)

        monthly_results.append({
            'month': month_key,
            'days': len(month_rates),
            'open_rate': prices[0],
            'close_rate': prices[-1],
            'rate_change_pct': (prices[-1] - prices[0]) / prices[0] * 100,
            'dca': dca_r,
            'signal': sig_r,
            'scalp': sclp_r,
            'cycle': cyc_r,
            'mr': mr_r,
        })

    # Totals across months
    totals = {}
    for key in ['dca', 'signal', 'scalp', 'cycle', 'mr']:
        total_pnl = sum(m[key]['pnl'] for m in monthly_results)
        total_realized = sum(m[key].get('realized_pnl', 0) for m in monthly_results)
        total_buys = sum(m[key]['num_buys'] for m in monthly_results)
        total_sells = sum(m[key].get('num_sells', 0) for m in monthly_results)
        totals[key] = {
            'pnl': total_pnl,
            'pnl_pct': (total_pnl / cap * 100) if cap and cap != float('inf') else 0,
            'realized_pnl': total_realized,
            'num_buys': total_buys,
            'num_sells': total_sells,
            'avg_monthly_pnl': total_pnl / len(monthly_results) if monthly_results else 0,
        }

    return {
        'months': monthly_results,
        'totals': totals,
        'seed_money': seed_money,
        'num_months': len(monthly_results),
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
        'total_invested': total_ever_bought,
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


def _run_buy_sell_repeat(rates, spread, tp_pct, sl_pct=0, seed=1_000_000, max_wait=5):
    """Smart Buy-Sell-Repeat:
    WAITING: check signals daily. Buy when dip detected OR after max_wait days.
    HOLDING: sell at TP%, overvalued signal, or SL%. Recycle proceeds. Repeat.
    """
    balance = seed
    units = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0
    trades = []
    prices = [r[1] for r in rates]
    buy_count = 0
    sell_count = 0
    days_waiting = 0

    for i in range(len(rates)):
        date, price = rates[i]
        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)

        # ── WAITING state: looking for entry ──
        if units == 0 and balance > 0:
            window = prices[:i + 1]
            ma20_val = sum(window[-20:]) / 20 if len(window) >= 20 else price
            ma20_dev = (price - ma20_val) / ma20_val * 100
            rsi_val = _rsi(window, 14)

            # Entry signals
            strong_entry = ma20_dev < -1.5 and rsi_val < 35
            normal_entry = ma20_dev < -0.5 or rsi_val < 40
            forced_entry = days_waiting >= max_wait

            if strong_entry:
                signal = f'STRONG_BUY (MA {ma20_dev:+.1f}%, RSI {rsi_val:.0f})'
            elif normal_entry:
                signal = f'BUY (MA {ma20_dev:+.1f}%, RSI {rsi_val:.0f})'
            elif forced_entry:
                signal = f'MAX_WAIT ({max_wait}d)'
            else:
                days_waiting += 1
                trades.append({
                    'date': date, 'type': 'SKIP', 'signal': f'WAIT d{days_waiting} (MA {ma20_dev:+.1f}%, RSI {rsi_val:.0f})',
                    'amount': 0, 'units': 0, 'rate': price,
                })
                continue

            # Execute buy
            units = balance / ask
            cost_basis = balance
            buy_count += 1
            trades.append({
                'date': date, 'type': 'BUY', 'signal': signal,
                'amount': balance, 'units': units, 'rate': price,
            })
            balance = 0
            days_waiting = 0
            continue

        # ── HOLDING state: looking for exit ──
        if units > 0:
            avg_cost = cost_basis / units
            gain_pct = (bid - avg_cost) / avg_cost * 100

            window = prices[:i + 1]
            ma20_val = sum(window[-20:]) / 20 if len(window) >= 20 else price
            ma20_dev = (price - ma20_val) / ma20_val * 100
            rsi_val = _rsi(window, 14)

            # Exit signals (checked in priority order)
            sell_signal = None
            if tp_pct and gain_pct >= tp_pct:
                sell_signal = f'TP +{gain_pct:.1f}%'
            elif sl_pct and gain_pct <= -sl_pct:
                sell_signal = f'SL {gain_pct:.1f}%'
            elif ma20_dev > 1.5 and rsi_val > 70 and gain_pct > 0:
                sell_signal = f'OVERBOUGHT (MA +{ma20_dev:.1f}%, RSI {rsi_val:.0f}, +{gain_pct:.1f}%)'

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
                balance = proceeds
                units = 0
                cost_basis = 0
                days_waiting = 0

    current_value = units * prices[-1] if units else 0
    unrealized = current_value - cost_basis if units else 0
    total_pnl = realized_pnl + unrealized
    pnl_pct = (total_pnl / seed * 100) if seed else 0

    total_ever_bought = sum(t['amount'] for t in trades if t.get('type') == 'BUY')
    return {
        'total_spent': cost_basis,
        'total_invested': total_ever_bought,
        'total_units': units,
        'avg_cost': cost_basis / units if units else 0,
        'current_value': current_value,
        'realized_pnl': realized_pnl,
        'unrealized_pnl': unrealized,
        'pnl': total_pnl,
        'pnl_pct': pnl_pct,
        'num_buys': buy_count,
        'num_sells': sell_count,
        'num_skipped': len([t for t in trades if t['type'] == 'SKIP']),
        'trades': trades,
        'final_balance': balance + current_value,
        'num_cycles': sell_count,
    }


def _run_mean_reversion(rates, spread, ma_period=5, buy_dip_pct=0.5, sell_gain_pct=0.3,
                        sl_pct=0, seed=1_000_000):
    """Mean Reversion: buy when price dips X% below MA, sell when up Y% from buy price.
    buy_dip_pct: how far below MA to trigger buy (e.g. 0.5 = -0.5%)
    sell_gain_pct: profit target from buy price (e.g. 0.3 = +0.3%)
    Costs applied via spread on both buy (ask) and sell (bid).
    """
    balance = seed
    units = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0
    trades = []
    prices = [r[1] for r in rates]
    buy_count = 0
    sell_count = 0

    for i in range(ma_period, len(rates)):
        date, price = rates[i]
        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)

        ma = sum(prices[i - ma_period:i]) / ma_period
        dev = (price - ma) / ma * 100

        # WAITING: buy when price dips below MA by buy_dip_pct
        if units == 0 and balance > 0:
            if dev <= -buy_dip_pct:
                units = balance / ask
                cost_basis = balance
                balance = 0
                buy_count += 1
                trades.append({
                    'date': date, 'type': 'BUY',
                    'signal': f'MA{ma_period} dev {dev:+.2f}%',
                    'amount': cost_basis, 'units': units, 'rate': price,
                })

        # HOLDING: sell when up sell_gain_pct from buy, or stop-loss
        elif units > 0:
            avg_cost = cost_basis / units
            gain = (bid - avg_cost) / avg_cost * 100

            sell_signal = None
            if gain >= sell_gain_pct:
                sell_signal = f'TP +{gain:.2f}%'
            elif sl_pct and gain <= -sl_pct:
                sell_signal = f'SL {gain:.2f}%'

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
                balance = proceeds
                units = 0
                cost_basis = 0

    current_value = units * prices[-1] if units else 0
    unrealized = current_value - cost_basis if units else 0
    total_pnl = realized_pnl + unrealized
    pnl_pct = (total_pnl / seed * 100) if seed else 0

    total_ever_bought = sum(t['amount'] for t in trades if t.get('type') == 'BUY')
    return {
        'total_spent': cost_basis,
        'total_invested': total_ever_bought,
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


def _run_mean_reversion_intraday(spread, ma_period=24, buy_dip_pct=0.5, sell_gain_pct=0.3,
                                 sl_pct=0, seed=1_000_000, start_date=None, end_date=None,
                                 max_trades_per_day=0, max_volatility_pct=0, cooldown_after_sl=0,
                                 market_hours_only=True, instant_buy=False, fixed_seed=False):
    """Mean Reversion on hourly candles — multiple trades per day possible.
    market_hours_only: if True, only trade 09:00-15:00 KST Mon-Fri (한투 market hours).
    MA still uses all hours for calculation, but trades only execute during market hours.
    """
    data = fetch_intraday_history(interval='1h', start_date=start_date, end_date=end_date)
    if not data or len(data) < ma_period + 5:
        return _empty_result(seed)

    balance = seed
    units = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0
    trades = []
    prices = [d[1] for d in data]
    buy_count = 0
    sell_count = 0
    banked_profit = 0.0

    # Tracking state
    daily_trades = {}
    cooldown_until = 0

    for i in range(ma_period, len(data)):
        dt_str, price = data[i]
        today = dt_str[:10]
        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)

        # Market hours filter: 09:00-15:00 KST, Mon-Fri
        if market_hours_only:
            try:
                dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
                if dt.weekday() >= 5:  # Sat/Sun
                    continue
                if dt.hour < 9 or dt.hour >= 16:  # before 09:00 or 16:00+
                    continue
            except ValueError:
                pass

        # Cooldown check
        if i < cooldown_until:
            continue

        # Max trades per day check
        if max_trades_per_day and daily_trades.get(today, 0) >= max_trades_per_day:
            continue

        # Volatility check: skip if 12h rolling std dev of returns is too high
        if max_volatility_pct and i >= 12:
            returns_12h = [(prices[j] - prices[j-1]) / prices[j-1] * 100
                           for j in range(i-11, i+1) if prices[j-1]]
            if returns_12h:
                mean_r = sum(returns_12h) / len(returns_12h)
                vol = (sum((r - mean_r) ** 2 for r in returns_12h) / len(returns_12h)) ** 0.5
                if vol > max_volatility_pct:
                    continue

        ma = sum(prices[i - ma_period:i]) / ma_period
        dev = (price - ma) / ma * 100

        # WAITING: buy on dip (or instantly if instant_buy)
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

        # HOLDING: sell on gain or stop-loss
        elif units > 0:
            avg_cost = cost_basis / units
            gain = (bid - avg_cost) / avg_cost * 100

            sell_signal = None
            is_sl = False
            if gain >= sell_gain_pct:
                sell_signal = f'TP +{gain:.2f}%'
            elif sl_pct and gain <= -sl_pct:
                sell_signal = f'SL {gain:.2f}%'
                is_sl = True

            if sell_signal:
                proceeds = units * bid
                profit = proceeds - cost_basis
                realized_pnl += profit
                sell_count += 1
                daily_trades[today] = daily_trades.get(today, 0) + 1
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

                if is_sl and cooldown_after_sl:
                    cooldown_until = i + cooldown_after_sl

    current_value = units * prices[-1] if units else 0
    unrealized = current_value - cost_basis if units else 0
    total_pnl = realized_pnl + unrealized + banked_profit
    pnl_pct = (total_pnl / seed * 100) if seed else 0
    total_ever_bought = sum(t['amount'] for t in trades if t.get('type') == 'BUY')

    return {
        'total_spent': cost_basis,
        'total_invested': total_ever_bought,
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


def run_usdt_backtest(seed=1_000_000, ma_period=6, buy_dip_pct=0.15, sell_gain_pct=0.50,
                      sl_pct=0.3, max_trades_per_day=0, max_volatility_pct=0.2,
                      cooldown_after_sl=3, start_date=None, end_date=None):
    """USDT/KRW backtest on Upbit. 24/7 trading, 0.05% fee per trade.
    Returns same structure as _run_mean_reversion_intraday for comparison.
    """
    UPBIT_FEE = 0.0005  # 0.05% per trade

    data = fetch_intraday_history(interval='1h', start_date=start_date, end_date=end_date)
    if not data or len(data) < ma_period + 5:
        return _empty_result(seed)

    balance = seed
    units = 0.0
    cost_basis = 0.0
    realized_pnl = 0.0
    trades = []
    prices = [d[1] for d in data]
    buy_count = 0
    sell_count = 0
    daily_trades = {}
    cooldown_until = 0

    for i in range(ma_period, len(data)):
        dt_str, price = data[i]
        today = dt_str[:10]

        # No market hours filter — USDT trades 24/7

        if i < cooldown_until:
            continue
        if max_trades_per_day and daily_trades.get(today, 0) >= max_trades_per_day:
            continue

        # Volatility check
        if max_volatility_pct and i >= 12:
            rets = [(prices[j] - prices[j-1]) / prices[j-1] * 100
                    for j in range(i-11, i+1) if prices[j-1]]
            if rets:
                mean_r = sum(rets) / len(rets)
                vol = (sum((r - mean_r)**2 for r in rets) / len(rets)) ** 0.5
                if vol > max_volatility_pct:
                    continue

        # Upbit cost: 0.05% fee applied on both buy and sell
        buy_price = price * (1 + UPBIT_FEE)   # you pay more
        sell_price = price * (1 - UPBIT_FEE)   # you receive less

        ma = sum(prices[i - ma_period:i]) / ma_period
        dev = (price - ma) / ma * 100

        if units == 0 and balance > 0:
            if dev <= -buy_dip_pct:
                units = balance / buy_price
                cost_basis = balance
                balance = 0
                buy_count += 1
                trades.append({
                    'date': dt_str, 'type': 'BUY',
                    'signal': f'MA{ma_period}h dev {dev:+.2f}%',
                    'amount': cost_basis, 'units': units, 'rate': price,
                })

        elif units > 0:
            avg_cost = cost_basis / units
            gain = (sell_price - avg_cost) / avg_cost * 100
            is_sl = False
            sell_signal = None

            if gain >= sell_gain_pct:
                sell_signal = f'TP +{gain:.2f}%'
            elif sl_pct and gain <= -sl_pct:
                sell_signal = f'SL {gain:.2f}%'
                is_sl = True

            if sell_signal:
                proceeds = units * sell_price
                profit = proceeds - cost_basis
                realized_pnl += profit
                sell_count += 1
                daily_trades[today] = daily_trades.get(today, 0) + 1
                trades.append({
                    'date': dt_str, 'type': 'SELL', 'signal': sell_signal,
                    'amount': proceeds, 'units': units, 'rate': price,
                    'profit': profit,
                })
                balance = proceeds
                units = 0
                cost_basis = 0
                if is_sl and cooldown_after_sl:
                    cooldown_until = i + cooldown_after_sl

    current_value = units * prices[-1] if units else 0
    unrealized = current_value - cost_basis if units else 0
    total_pnl = realized_pnl + unrealized
    pnl_pct = (total_pnl / seed * 100) if seed else 0
    total_ever_bought = sum(t['amount'] for t in trades if t.get('type') == 'BUY')

    return {
        'total_spent': cost_basis,
        'total_invested': total_ever_bought,
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


def _empty_result(seed=0):
    """Return an empty result dict when no data is available."""
    return {
        'total_spent': 0, 'total_invested': 0, 'total_units': 0,
        'avg_cost': 0, 'current_value': 0, 'realized_pnl': 0,
        'unrealized_pnl': 0, 'pnl': 0, 'pnl_pct': 0,
        'num_buys': 0, 'num_sells': 0, 'num_skipped': 0,
        'trades': [], 'final_balance': seed, 'num_cycles': 0,
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
