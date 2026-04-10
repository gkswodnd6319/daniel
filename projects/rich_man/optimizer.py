"""Brute-force parameter optimizer for intraday mean reversion strategy.

Run: python3 -m projects.rich_man.optimizer
Or:  python3 projects/rich_man/optimizer.py

Tests all parameter combinations over 7 months of hourly data (Bithumb)
and ranks by total P&L. Use results to set your backtest parameters.
"""

import sys
import os
import time

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from projects.rich_man.fx_data import fetch_intraday_history


def run_sim(prices, data, spread, ma_period, buy_dip, sell_gain, sl_pct,
            max_trades_day, max_vol, cooldown_hrs, seed=1_000_000):
    """Run a single mean reversion simulation. Returns (pnl, buys, sells, wins, losses)."""
    balance = seed
    units = 0.0
    cost_basis = 0.0
    realized = 0.0
    buys = 0
    sells = 0
    wins = 0
    losses = 0
    daily_trades = {}
    cooldown_until = 0

    for i in range(ma_period, len(data)):
        dt_str = data[i][0]
        price = prices[i]
        today = dt_str[:10]

        # Market hours: 09:00-15:00 KST, Mon-Fri only
        try:
            _hour = int(dt_str[11:13])
            _ymd = dt_str[:10].split('-')
            from datetime import date as _date
            _wd = _date(int(_ymd[0]), int(_ymd[1]), int(_ymd[2])).weekday()
            if _wd >= 5 or _hour < 9 or _hour >= 16:
                continue
        except (ValueError, IndexError):
            pass

        if i < cooldown_until:
            continue
        if max_trades_day and daily_trades.get(today, 0) >= max_trades_day:
            continue

        # Volatility check
        if max_vol and i >= 12:
            rets = []
            for j in range(i - 11, i + 1):
                if prices[j - 1]:
                    rets.append((prices[j] - prices[j - 1]) / prices[j - 1] * 100)
            if rets:
                mean_r = sum(rets) / len(rets)
                vol = (sum((r - mean_r) ** 2 for r in rets) / len(rets)) ** 0.5
                if vol > max_vol:
                    continue

        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)
        ma = sum(prices[i - ma_period:i]) / ma_period
        dev = (price - ma) / ma * 100

        if units == 0 and balance > 0 and dev <= -buy_dip:
            units = balance / ask
            cost_basis = balance
            balance = 0
            buys += 1
        elif units > 0:
            avg = cost_basis / units
            gain = (bid - avg) / avg * 100
            is_sl = False
            if gain >= sell_gain:
                pass
            elif sl_pct and gain <= -sl_pct:
                is_sl = True
            else:
                continue

            proceeds = units * bid
            profit = proceeds - cost_basis
            realized += profit
            sells += 1
            if profit > 0:
                wins += 1
            else:
                losses += 1
            daily_trades[today] = daily_trades.get(today, 0) + 1
            balance = proceeds
            units = 0
            cost_basis = 0
            if is_sl and cooldown_hrs:
                cooldown_until = i + cooldown_hrs

    final = balance + (units * prices[-1] if units else 0)
    pnl = final - seed
    return pnl, buys, sells, wins, losses


def optimize(seed=1_000_000, wudae_pct=90, sl_pct=0.3, start_date=None, end_date=None):
    """Run all parameter combos. Returns sorted list of results.
    Default: last 3 months (best balance of recency and data size).
    """
    if not start_date and not end_date:
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')

    print("Fetching hourly data from Bithumb...")
    data = fetch_intraday_history(interval='1h', start_date=start_date, end_date=end_date)
    if not data:
        print("No data available")
        return []

    print(f"{len(data)} candles ({data[0][0]} to {data[-1][0]})")

    prices = [d[1] for d in data]
    spread = 0.25 * (1 - wudae_pct / 100) / 100

    # Parameter grid
    param_grid = {
        'ma':       [3, 6, 12, 24, 48],
        'buy_dip':  [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50],
        'sell_gain': [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50],
        'max_trades': [0, 2, 3, 5],
        'max_vol':  [0, 0.2, 0.3, 0.5],
        'cooldown': [0, 3, 6, 12],
    }

    total = 1
    for v in param_grid.values():
        total *= len(v)

    print(f"\nRunning {total:,} simulations...")
    start = time.time()
    results = []
    count = 0

    for ma in param_grid['ma']:
        for bd in param_grid['buy_dip']:
            for sg in param_grid['sell_gain']:
                for mt in param_grid['max_trades']:
                    for mv in param_grid['max_vol']:
                        for cd in param_grid['cooldown']:
                            pnl, buys, sells, wins, losses = run_sim(
                                prices, data, spread, ma, bd, sg, sl_pct, mt, mv, cd, seed
                            )
                            if sells > 0:
                                results.append({
                                    'pnl': pnl,
                                    'ma': ma,
                                    'buy_dip': bd,
                                    'sell_gain': sg,
                                    'max_trades': mt,
                                    'max_vol': mv,
                                    'cooldown': cd,
                                    'buys': buys,
                                    'sells': sells,
                                    'wins': wins,
                                    'losses': losses,
                                    'win_rate': wins / (wins + losses) * 100 if wins + losses else 0,
                                })
                            count += 1

    elapsed = time.time() - start
    results.sort(key=lambda x: x['pnl'], reverse=True)

    print(f"Done in {elapsed:.1f}s ({count / elapsed:.0f} sims/sec)")
    print(f"Profitable combos: {len([r for r in results if r['pnl'] > 0])}/{len(results)}")

    return results


def print_results(results, top_n=20):
    """Print ranked results table."""
    if not results:
        print("No results")
        return

    print(f"\n{'Rank':>4} {'P&L':>12} {'MA':>4} {'Dip%':>5} {'Gain%':>6} {'MaxT':>5} {'Vol%':>5} {'Cool':>5} {'Buys':>5} {'Sells':>5} {'WR%':>5}")
    print("-" * 80)
    for i, r in enumerate(results[:top_n]):
        print(f"{i+1:>4} \u20a9{r['pnl']:>+10,.0f} {r['ma']:>3}h {r['buy_dip']:>4.2f} {r['sell_gain']:>5.2f} {r['max_trades']:>5} {r['max_vol']:>4.1f} {r['cooldown']:>5} {r['buys']:>5} {r['sells']:>5} {r['win_rate']:>4.0f}%")

    print(f"\nWorst 5:")
    for r in results[-5:]:
        print(f"      \u20a9{r['pnl']:>+10,.0f} {r['ma']:>3}h {r['buy_dip']:>4.2f} {r['sell_gain']:>5.2f} {r['max_trades']:>5} {r['max_vol']:>4.1f} {r['cooldown']:>5} {r['buys']:>5} {r['sells']:>5} {r['win_rate']:>4.0f}%")

    best = results[0]
    worst = results[-1]

    print(f"\n{'='*50}")
    print(f"GOLDEN PARAMETERS (highest P&L)")
    print(f"{'='*50}")
    print(f"  MA Period:       {best['ma']}h")
    print(f"  Buy Dip %:       {best['buy_dip']:.2f}%")
    print(f"  Sell Gain %:     {best['sell_gain']:.2f}%")
    print(f"  Max Trades/Day:  {best['max_trades']} (0=unlimited)")
    print(f"  Max 12h Vol %:   {best['max_vol']:.1f} (0=disabled)")
    print(f"  SL Cooldown:     {best['cooldown']}h (0=disabled)")
    print(f"  P&L:             \u20a9{best['pnl']:+,.0f} ({best['pnl']/10000:+.2f}%)")
    print(f"  Trades:          {best['buys']} buys, {best['sells']} sells")
    print(f"  Win Rate:        {best['win_rate']:.0f}%")

    # Pattern analysis
    print(f"\n{'='*50}")
    print(f"PATTERN ANALYSIS")
    print(f"{'='*50}")

    # What MA appears most in top 20?
    from collections import Counter
    top20 = results[:20]
    ma_counts = Counter(r['ma'] for r in top20)
    print(f"  Top 20 MA distribution: {dict(ma_counts)}")

    # Average parameters of top 20
    avg_bd = sum(r['buy_dip'] for r in top20) / 20
    avg_sg = sum(r['sell_gain'] for r in top20) / 20
    print(f"  Top 20 avg Buy Dip: {avg_bd:.2f}%, avg Sell Gain: {avg_sg:.2f}%")

    # Profitable vs unprofitable
    profitable = [r for r in results if r['pnl'] > 0]
    losing = [r for r in results if r['pnl'] <= 0]
    if profitable and losing:
        avg_p_wr = sum(r['win_rate'] for r in profitable) / len(profitable)
        avg_l_wr = sum(r['win_rate'] for r in losing) / len(losing)
        print(f"  Profitable combos avg WR: {avg_p_wr:.0f}%")
        print(f"  Losing combos avg WR:     {avg_l_wr:.0f}%")

    # When to hold cash (worst conditions)
    print(f"\n{'='*50}")
    print(f"DANGER ZONES (parameters that lose money)")
    print(f"{'='*50}")
    bottom20 = results[-20:]
    ma_bad = Counter(r['ma'] for r in bottom20)
    print(f"  Worst MA periods: {dict(ma_bad)}")
    avg_bad_bd = sum(r['buy_dip'] for r in bottom20) / 20
    avg_bad_sg = sum(r['sell_gain'] for r in bottom20) / 20
    print(f"  Worst avg Buy Dip: {avg_bad_bd:.2f}%, avg Sell Gain: {avg_bad_sg:.2f}%")
    print(f"  Pattern: Large buy dip + small sell gain + long MA = losses")
    print(f"  → Hold cash when market is trending strongly (no mean reversion)")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Optimize mean reversion parameters')
    parser.add_argument('--start', type=str, default=None, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, default=None, help='End date (YYYY-MM-DD)')
    parser.add_argument('--seed', type=int, default=1_000_000, help='Seed money in KRW (default: 1000000)')
    parser.add_argument('--wudae', type=int, default=90, help='우대율 %% (default: 90)')
    parser.add_argument('--sl', type=float, default=0.3, help='Stop loss %% (default: 0.3)')
    parser.add_argument('--top', type=int, default=20, help='Show top N results (default: 20)')
    args = parser.parse_args()

    print(f"Seed: \u20a9{args.seed:,} | 우대율: {args.wudae}% | SL: {args.sl}%")
    if args.start and args.end:
        print(f"Period: {args.start} to {args.end}")
    else:
        print("Period: all available data (~7 months)")

    results = optimize(
        seed=args.seed, wudae_pct=args.wudae, sl_pct=args.sl,
        start_date=args.start, end_date=args.end,
    )
    print_results(results, top_n=args.top)

    # Save best params to JSON for the UI to auto-load
    if results:
        import json
        best = results[0]
        params_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'optimal_params.json')
        output = {
            'ma_period': best['ma'],
            'buy_dip_pct': best['buy_dip'],
            'sell_gain_pct': best['sell_gain'],
            'max_trades_day': best['max_trades'],
            'max_vol_pct': best['max_vol'],
            'cooldown_hrs': best['cooldown'],
            'pnl': best['pnl'],
            'pnl_pct': round(best['pnl'] / args.seed * 100, 2),
            'win_rate': round(best['win_rate'], 1),
            'trades': best['sells'],
            'optimized_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'data_range': f"{args.start or 'all'} to {args.end or 'latest'}",
            'seed': args.seed,
            'wudae_pct': args.wudae,
        }
        with open(params_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved best params to {params_file}")
