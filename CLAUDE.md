
# Personal Hub — NiceGUI Dashboard

A personal dashboard built with NiceGUI (Python). Run `python3 main.py` → open `http://localhost:8080`.

## Tabs

**Career** (`career_tab.py`) — Two sub-tabs:
- Goals Tracker: kanban-style career goals with status, deadlines, categories
- Career Path: upload resume PDF or paste text → auto-parses career history into a timeline chart. Supports Korean (YYYY.MM ~ Present), English, and numeric date formats. Manual add/edit/delete.

**Projects** (`projects/tab.py` + `projects/rich_man/`) — Two sub-tabs:
- Projects: personal project list with task checklists and progress bars
- Rich Man: FX + crypto trading dashboard. Goal: 0.1% daily profit via USD/KRW mean reversion. (see `projects/rich_man/CLAUDE.md`)

**Sports** (`sports_data.py`, built in `main.py`) — Live schedules and standings:
- Premier League, Champions League, LCK, LoL International, KBO, MLB
- World Cup, WBC, Others under Worlds meta-tab
- Favorite team highlighting, bracket views, standings tables
- All times displayed in KST (UTC+9)

## Tech

- **Framework:** NiceGUI 3.9+ (Python web UI)
- **Data sources (all free, no API keys):**
  - Sports: football-data.org, LoL Esports, MLB statsapi
  - FX live: Upbit CRIX (서울외국환중개), Upbit WebSocket (KRW-USDT real-time)
  - FX history: Frankfurter (daily, ECB), Bithumb candles (hourly, ~7 months)
  - Crypto: Bithumb candle API (BTC/KRW, USDT/KRW, 0.04% fee)
  - Fallback: ExchangeRate-API (166 currencies, daily)
- **Storage:** NiceGUI `app.storage.general` (JSON file in `.nicegui/`)
- **Charts:** Plotly (in-place updates for live ticker to avoid flicker)
- **Real-time:** Upbit WebSocket for live KRW-USDT price streaming (sub-second ticks)

## Structure

```
main.py              Entry point, theme, sports tab, page layout
career_tab.py        Career goals + resume parser + timeline chart
sports_data.py       All sports API fetching, caching, parsing
system_prompt.md     Coding guidelines (follow when making changes)
requirements.txt     Dependencies (nicegui, pdfplumber, plotly, python-dotenv, websockets)
projects/
  tab.py             Projects list tab
  rich_man/          FX trading project
    CLAUDE.md        Rich Man specific docs
    rich_man.py      Main entry, left sidebar (Dashboard / Backtest USD / Backtest Crypto / Paper Trade)
    fx_data.py       Data layer — Upbit CRIX, Bithumb candles, Frankfurter, ExchangeRate-API
    fx_ws.py         WebSocket streaming (Upbit KRW-USDT, 24/7)
    fx_signals.py    Signal engine + 5 backtest strategies + tier presets
    fx_sim.py        USD/KRW backtest UI, monthly breakdown, cost breakdown
    crypto_sim.py    Crypto backtest (BTC/KRW, USDT/KRW on Bithumb, adaptive mean reversion)
    fx_paper.py      Paper trading UI — auto-trading, kill switch, profiles
    optimizer.py     Brute-force parameter optimizer (20,480 combos)
    kis_api.py       한투 API client (future live trading, needs keys)
    instructions.md  User manual
    research.md      Comprehensive FX trading guide for Korean traders
    fx_platforms.md  Platform cost comparison (한투, Hana, Toss, Wise, etc.)
    fx_strategy.md   USD/KRW capital tier strategy playbook
    crypto_strategy.md  BTC/KRW adaptive mean reversion strategy
    deployment.md    Oracle Cloud free tier deployment guide
```

## Conventions

- Follow `system_prompt.md` for all code changes
- All displayed times must be KST (UTC+9)
- Dark theme throughout, Outfit + JetBrains Mono fonts
- Prefer config-driven patterns, DRY code
- No unnecessary dependencies
- Plotly charts: use `title=dict(text=..., font=...)` not deprecated `titlefont`
- Plotly in NiceGUI: use in-place `chart.update()` for live data, not DOM rebuild (causes flicker)
- FX costs modeled: spread (0.25% base, adjustable 우대율), tax (22% >₩2.5M/year), no commission on 한투 사전환전
- Backtest strategies (USD): Pure DCA, Signal DCA, DCA+Scalp, Buy-Sell-Repeat, Mean Reversion (daily + intraday hourly)
- Backtest strategies (Crypto): Mean Reversion (fixed or adaptive volatility-based) on Bithumb
- Fixed Seed recommended for BTC mean reversion (outperforms compound; profits banked, never risked)
- Golden params USD/KRW (한투, instant buy, fixed seed, market hours): Sell +0.40%, SL -0.50%, Max 2/day, Cooldown 3h
- Golden params BTC/KRW (adaptive): 24h MA, 1.0x dip, 1.5x gain, 5.0x SL multipliers
- USDT/KRW 24/7 underperforms vs 한투 market hours — not recommended
- Paper trade kill switch: auto-stop + sell if price drops X% within Y minutes (default: 1.5%/30min)
