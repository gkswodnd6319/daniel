# Rich Man — FX + Crypto Trading Dashboard & Simulator

## Purpose

**Ultimate Goal: 0.1% daily profit on seed money through USD/KRW mean reversion.**

| Seed | Daily Target | Monthly | Annual (after tax) |
|---|---|---|---|
| ₩1M | ₩1,000 | ₩22,000 | ₩264,000 |
| ₩10M | ₩10,000 | ₩220,000 | ₩2,609,200 |
| ₩50M | ₩50,000 | ₩1,100,000 | ₩10,846,000 |
| ₩100M | ₩100,000 | ₩2,200,000 | ₩21,142,000 |

Personal USD/KRW and BTC/KRW trading tool built for a Korean resident. Start with paper trading, validate the strategy, then go live on 한국투자증권 (FX) and optionally Bithumb (crypto).

## What It Does

**Left sidebar:** Dashboard | Backtest USD/KRW | Backtest Crypto | Paper Trade

**Dashboard** — real-time FX monitoring:
- Live rate cards (6 currencies), real-time USD/KRW ticker via Upbit websocket
- Kimchi premium, historical charts, converter, watchlist, advanced tools

**Backtest USD/KRW** — 5 strategies (Pure DCA, Signal DCA, DCA+Scalp, Buy-Sell-Repeat, Mean Reversion):
- Intraday hourly from Bithumb (5000 candles, ~7 months)
- Market hours filter (09:00-15:30 KST)
- Optimizer defaults to 3-month window, 20,480 parameter combos
- Golden params: Sell +0.40%, SL -0.50%, Max 2/day, Cooldown 3h, market hours only
- Toggles: Instant Buy (skip MA dip wait after sell), Fixed Seed (re-enter with original seed, bank profits)

**Backtest Crypto** — BTC/KRW and USDT/KRW on Bithumb:
- Fixed or adaptive mean reversion (thresholds scale with 24h rolling volatility)
- BTC optimal: adaptive, 24h MA, 1.0x dip, 1.5x gain, 5.0x SL multipliers
- Bithumb fee: 0.04% per trade (round-trip 0.08%)
- 24/7 trading, no market hours restriction
- Toggles: Instant Buy (skip MA dip wait after sell), Fixed Seed (re-enter with original seed, bank profits)
- Fixed Seed recommended for BTC — outperforms compound in both winning and losing months
- USDT/KRW 24/7 underperforms vs USD/KRW via 한투 market hours — not recommended
- Safety locks: max trades/day, vol filter, SL cooldown, daily loss limit, max drawdown pause

**Paper Trade** — auto-trading with live websocket:
- Virtual 한투 account with profiles, market hours toggle (09:00-15:30 KST)
- Emergency kill switch: auto-stops + sells if price drops X% within Y min (default: 1.5%/30min)
- Max drawdown = temporary pause (default 48h), resets peak and resumes

## Data Sources (all free, no API keys)

| Source | Data | Update |
|---|---|---|
| Upbit CRIX | Official KRW rates (8 currencies) | ~30s during market hours |
| Upbit WebSocket | KRW-USDT real-time | Sub-second, 24/7 |
| Bithumb candles | Hourly BTC/KRW, USDT/KRW (5000 candles) | ~10 min cache |
| Frankfurter | Daily historical (ECB) | Daily |
| ExchangeRate-API | 166 currencies fallback | Daily |

## File Structure

| File | Role |
|---|---|
| `rich_man.py` | Main entry, left sidebar (Dashboard / Backtest USD / Backtest Crypto / Paper Trade) |
| `fx_data.py` | Data layer — Upbit CRIX, Bithumb candles, Frankfurter, ExchangeRate-API |
| `fx_ws.py` | Upbit websocket manager — real-time KRW-USDT streaming |
| `fx_signals.py` | Signal engine + backtester (5 strategies) + tier presets |
| `fx_sim.py` | USD/KRW backtest UI, monthly breakdown, cost breakdown |
| `crypto_sim.py` | Crypto backtest — BTC/KRW, USDT/KRW on Bithumb (fixed + adaptive) |
| `fx_paper.py` | Paper trading UI — auto-trading, kill switch, profiles |
| `optimizer.py` | Brute-force parameter optimizer (20,480 combos) |
| `kis_api.py` | 한투 API client (future live trading) |
| `research.md` | FX trading guide for Korean traders |
| `fx_platforms.md` | Platform cost comparison |
| `fx_strategy.md` | USD/KRW strategy playbook |
| `crypto_strategy.md` | BTC/KRW adaptive strategy |
| `instructions.md` | User manual |
| `deployment.md` | Oracle Cloud free tier deployment guide |

## Current Status

Backtesting and paper trading functional for both USD/KRW and BTC/KRW. Primary strategies: **intraday mean reversion** (USD, market hours) and **adaptive volatility-based mean reversion** (BTC, 24/7).

**Plan:** Start with ₩1M seed on USD/KRW via 한국투자증권 (instant buy + fixed seed). Deploy paper trade to Oracle Cloud for 24/7 simulation. Collect seed money through USD/KRW, potentially add BTC later.
