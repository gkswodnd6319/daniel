# Rich Man — User Manual

**Project Goal: 0.1% daily profit on seed money through USD/KRW mean reversion on 한국투자증권.**

## How to Use

1. Run `python3 main.py` → open `http://localhost:8080`
2. Go to **Projects** tab → **Rich Man** sub-tab
3. Left sidebar: **Dashboard** | **Backtest USD/KRW** | **Backtest Crypto** | **Paper Trade**

---

## Dashboard

### Rate Cards
Live KRW rates for USD, EUR, JPY, GBP, CNY, CAD. Data from 서울외국환중개 via Upbit CRIX.
- Green/red flash = USD card updating in real-time from websocket
- Change % = compared to previous day
- Hit **Refresh** (top right) to force re-fetch all rates

### Live Ticker
Real-time USD/KRW chart (actually USDT/KRW from Upbit websocket). Updates every 2 seconds without page reload.
- **Kimchi Premium** = gap between USDT price and official FX rate. Orange if > 0.5%.
- Green line = uptrend since chart start. Red = downtrend.

### Price Trend
Historical price chart with configurable currency and time range.
- Y-axis is tight (zoomed to data range) so movements are clearly visible
- High/Low annotations marked on chart
- Stats bar: current rate, period change, high, low, average

### Converter
Convert KRW to any currency at live rates. Updates instantly when you change amount or currency.

### Watchlist
Track currencies with target rates. Set alert direction (drops below / rises above). Green border = target hit.

### Advanced Tools (toggle switches)
- **Multi-Currency Comparison**: overlay 2+ currencies on one chart, normalized to 100
- **Volatility Indicator**: rolling standard deviation — shows if a currency is stable or volatile
- **Position Tracker**: log real FX buys/sells, track live P&L
- **Cost Average Calculator**: simulate regular purchases over a lookback period

---

## Paper Trade

### Signal Panel
Shows a live BUY/HOLD/SELL recommendation based on 5 technical factors:

| Factor | Weight | Buy Signal | Sell Signal |
|---|---|---|---|
| **MA20 Deviation** | 30/100 | Rate 1.5%+ below 20-day MA | Rate 1.5%+ above 20-day MA |
| **RSI (14-day)** | 25/100 | RSI below 25 (oversold) | RSI above 75 (overbought) |
| **Bollinger Bands** | 20/100 | Below lower band | Above upper band |
| **7-day Rate of Change** | 15/100 | Dropped 2%+ in 7 days | Spiked 2%+ in 7 days |
| **52-week Position** | 10/100 | Below 20th percentile | Above 80th percentile |

Score ranges: ≥50 = STRONG BUY, ≥25 = BUY, -25 to +25 = HOLD, ≤-25 = TAKE PROFIT, ≤-50 = STRONG SELL

### Strategy Guidelines
Permanent reference panel with rules for:
- DCA baseline (when and how much to buy)
- Opportunistic buying (what signals to look for)
- Taking profit (when to sell)
- Risk rules (max allocation, loss limits)
- Economic calendar (BOK, FOMC, NFP times in KST)

### Account Summary
Shows your paper trading account: total value, KRW balance, position value, P&L, 우대율, effective spread.

### 우대율 Slider
Adjusts the spread discount for paper trades. 90% = 0.025% effective spread per trade.

### Order Entry
Buy or sell USD (or other currencies) at live bid/ask prices. Quotes auto-refresh every 2 seconds for USD.
- **Ask** = price you pay when buying USD (higher)
- **Bid** = price you receive when selling USD (lower)
- Preview shows exact units and spread cost before execution

### Open Positions
Current USD holdings with average cost, current value, and unrealized P&L.

### Trade History
Full log of all paper trades with timestamp, type, rate, amount, and spread cost. Shows total accumulated spread costs.

---

## Backtest

### Parameters

| Parameter | Default | Description |
|---|---|---|
| **Capital Tier** | Custom | Presets: Tier 1 (₩10M), Tier 2 (₩50M), Tier 3 (₩100M). Auto-fills all fields. |
| **Seed Money** | ₩1,000,000 | Total KRW budget. Strategies stop buying when this is exhausted. |
| **DCA per Period** | ₩250,000 | How much KRW to buy each DCA interval. |
| **Interval** | Weekly | How often to buy: Weekly (7d), Bi-weekly (14d), Monthly (30d). |
| **Lookback** | 1 Month | Historical period to test: 1M, 3M, 6M, 1Y, or Custom Dates. |
| **Custom Dates** | — | Pick exact start/end dates. Appears when Lookback = "Custom Dates". |
| **Scalp %** | 0.50 | DCA+Scalp and Buy-Sell-Repeat: sell each lot when it's up this %. |
| **Take Profit %** | 2.00 | DCA and Signal DCA: sell entire position when avg gain hits this %. 0 = hold forever. |
| **Stop Loss %** | 3.00 | Sell entire position when avg loss hits this %. 0 = disabled. |
| **Max Wait (days)** | 5 | Buy-Sell-Repeat: if no buy signal after this many days, buy anyway. |
| **우대율 %** | 90 | Spread discount. 90 = 0.025% per trade. 100 = free. 0 = full 0.25% spread. |

### Mean Reversion Parameters

| Parameter | Default | Description |
|---|---|---|
| **Intraday (hourly)** | Off | Toggle: use hourly candles from Bithumb instead of daily. Enables multiple trades per day. |
| **MA Period** | 5-day / 24h | Moving average window. Daily: 5/7/9/20 days. Hourly: 3h/6h/12h/24h/48h/72h/120h/168h. |
| **Buy Dip %** | 0.50 | Buy when price drops this % below the MA. Lower = more frequent entries. |
| **Sell Gain %** | 0.30 | Sell when price rises this % above your buy price. Lower = quicker exits. |
| **Instant Buy** | Off | When ON, buys immediately after sell (no waiting for MA dip). Cycle: BUY → +x% → SELL → BUY → repeat. |
| **Fixed Seed** | Off | When ON, re-enters with original seed amount after each sell. Profits are banked, never risked. When OFF, compounds (reinvests full proceeds). |

### Intraday Risk Guards (visible when Intraday is on)

| Parameter | Default | Description |
|---|---|---|
| **Max Trades/Day** | 3 | Stop trading after N complete buy-sell cycles in one day. Prevents overtrading. 0 = unlimited. |
| **Max 12h Vol %** | 0.30 | Skip entry if the 12-hour rolling volatility exceeds this %. Avoids trading during wild swings. 0 = disabled. |
| **SL Cooldown (hrs)** | 6 | After a stop-loss hit, wait this many hours before re-entering. Prevents revenge trading. 0 = disabled. |

### 5 Strategies Compared

| Strategy | How It Works | Best In |
|---|---|---|
| **Pure DCA** | Buy fixed amount on schedule, hold. Sell only at TP/SL. | Trending markets |
| **Signal DCA** | Same as DCA but buys 2.5x on STRONG_BUY, 1.5x on BUY, skips overvalued. | Trending with dips |
| **DCA + Scalp** | Buy on schedule, sell each individual lot when it hits scalp %. | Choppy markets |
| **Buy-Sell-Repeat** | All-in on signal → sell at TP → re-buy with proceeds → repeat. Capital compounds. | Markets with clear swings |
| **Mean Reversion** | Buy when price dips below MA, sell when it bounces above buy price. | Ranging/oscillating markets |

### Backtest Output

- **Strategy cards**: invested amount, USD held, avg cost, value now, realized/unrealized P&L, tax estimate, after-tax P&L
- **Trade log** (expandable per strategy): date, type (BUY/SELL), signal, rate, units, KRW amount, profit
- **Cost breakdown table**: gross P&L, spread cost, estimated tax, net profit, net %
- **Winner ranking**: sorted by P&L % with after-tax amounts
- **Deploy info**: shows how many periods until seed money is fully deployed

### Monthly Breakdown
Each month runs independently with fresh seed money. Shows per-month P&L for all 5 strategies, totals, averages, and winner.

---

## Backtest Crypto (Bithumb)

Crypto mean reversion backtester for **BTC/KRW** and **USDT/KRW** on Bithumb. Trades 24/7 (no market hours restriction). Bithumb fee: 0.04% per trade (round-trip 0.08%).

**Note:** USDT/KRW 24/7 underperforms compared to USD/KRW via 한투 market hours — not recommended as a primary strategy.

### Toggle Options

| Toggle | Default | Description |
|---|---|---|
| **Instant Buy** | Off | When ON, buys immediately after sell (skip MA dip wait). Cycle: BUY → +x% → SELL → BUY → repeat. |
| **Fixed Seed** | Off | When ON, re-enters with original seed after each sell. Profits banked, never risked. When OFF, compounds. |

**Recommendation:** Use Fixed Seed ON for BTC. In backtests, Fixed Seed outperforms compound in both winning and losing months because after a loss it re-enters with full seed to catch the recovery, while compound re-enters with a shrunk balance.

### Pair Selection
Select BTC/KRW or USDT/KRW. Parameters auto-fill with optimized defaults for each pair.

### Strategy Modes

**Fixed Mode:** Static thresholds (same as USD/KRW mean reversion). Set exact MA, buy dip %, sell gain %, stop loss %.

**Adaptive Mode (recommended for BTC):** Thresholds scale dynamically with 24h rolling volatility.
- Buy Dip = max(0.05%, vol x dip_multiplier)
- Sell Gain = max(0.05%, vol x gain_multiplier)
- Stop Loss = max(0.5%, vol x SL_multiplier)

When volatility is high, thresholds widen automatically to avoid false entries. When volatility is low, thresholds tighten to capture small swings.

### BTC/KRW Optimal Parameters (Adaptive)

| Parameter | Value | Meaning |
|---|---|---|
| MA Period | 24h | Short-term trend baseline |
| Buy Dip multiplier | 1.0x | Enter when price dips 1x the current 24h volatility below MA |
| Sell Gain multiplier | 1.5x | Exit when price bounces 1.5x the current volatility above cost |
| Stop Loss multiplier | 5.0x | Cut loss at 5x volatility — wide enough to avoid noise |

### Safety Locks

| Lock | Default (BTC) | Description |
|---|---|---|
| Max Trades/Day | 3 | Prevents overtrading in choppy markets |
| Max 12h Vol % | 1.5% | Skip entry during extreme volatility |
| SL Cooldown | 3h | Wait after stop-loss before re-entering |
| Daily Loss Limit | 3.0% | Stop trading if daily losses exceed this |
| Max Drawdown | 10.0% | Pause trading when portfolio drops this % from peak |
| DD Pause (hrs) | 48 | How long to pause after drawdown trigger (0 = permanent halt) |

**Max drawdown is a temporary pause**, not a permanent halt. After the pause expires, the peak resets to the current portfolio value and trading resumes. This allows recovery from drawdowns without manual intervention.

---

## Paper Trade

### Trading Engine

Auto-executes mean reversion trades using live Upbit KRW-USDT websocket ticks. Supports profiles for different parameter sets.

- **Market hours toggle:** When enabled, only trades during 09:00-15:30 KST (Mon-Fri)
- **Start/Stop buttons:** Control auto-trading execution

### Emergency Kill Switch

Automatically stops trading and sells the entire position if a sudden crash is detected.

| Setting | Default | Description |
|---|---|---|
| Kill if drop % | 1.5% | Price drop threshold |
| Within (min) | 30 | Time window to measure the drop |
| Enabled | On | Toggle the kill switch on/off |

When triggered: immediately stops the trading engine, sells any open position at market, and displays a warning. This protects against flash crashes and black swan events.

### Account Summary
Shows your paper trading account: total value, KRW balance, position value, P&L, 우대율, effective spread.

### Trade History
Full log of all auto-executed trades with timestamp, type, rate, amount, signal, and P&L.

---

## Key Formulas

**Effective spread** = 0.25% × (1 - 우대율/100)
- At 90% 우대: 0.025% per trade, 0.05% round-trip

**Ask price** (you pay when buying) = mid rate × (1 + spread/200)
**Bid price** (you receive when selling) = mid rate × (1 - spread/200)

**Tax** = 22% on annual gains exceeding ₩2.5M (양도소득세)
- Annualized from backtest period: if you made ₩100K in 30 days, annual projection = ₩1.2M → under exemption → ₩0 tax

**Mean reversion entry** = price deviation from MA ≤ -buy_dip_%
**Mean reversion exit** = (bid - buy_price) / buy_price × 100 ≥ sell_gain_%

---

## Parameter Optimizer

The optimizer defaults to a **3-month lookback window** for finding optimal parameters.

```bash
# Default: 3-month window (recommended)
python3 projects/rich_man/optimizer.py

# Specific month (for monthly re-optimization)
python3 projects/rich_man/optimizer.py --start 2026-03-01 --end 2026-03-31

# Custom seed money and 우대율
python3 projects/rich_man/optimizer.py --seed 10000000 --wudae 95

# All options
python3 projects/rich_man/optimizer.py --start 2026-03-01 --end 2026-03-31 --seed 10000000 --wudae 95 --sl 0.5 --top 30
```

Options: `--start`, `--end` (date range), `--seed` (KRW, default 1M), `--wudae` (%, default 90), `--sl` (stop loss %, default 0.3), `--top` (show top N, default 20).

Tests 20,480 parameter combinations. Takes ~3 minutes. Shows top 20 results ranked by P&L.

### Monthly Optimization Workflow

1. At the **start of each month**, run optimizer (defaults to 3-month window):
   ```bash
   python3 projects/rich_man/optimizer.py
   ```
2. Note the **top result** (MA, Buy Dip, Sell Gain, Max Trades, Vol, Cooldown)
3. Update the **Paper Trade backtest** parameters with these values
4. If **all combos lost money** → do NOT trade mean reversion. Hold cash or switch to DCA.
5. Run backtest with new params to verify before live trading
6. Optionally compare against a specific month to see if recent conditions changed:
   ```bash
   python3 projects/rich_man/optimizer.py --start 2026-03-01 --end 2026-03-31
   ```

### Golden Parameters — USD/KRW (한투, instant buy, fixed seed, market hours)

| Parameter | Optimal Value | Why |
|---|---|---|
| Sell Gain % | **+0.40%** | Moderate exit — takes profit before bounce exhausts |
| Stop Loss % | **-0.50%** | Wider SL avoids noise-triggered exits on intraday data |
| Max Trades/Day | **2** | Limits overtrading while allowing multiple cycles |
| SL Cooldown | **3h** | Prevents revenge trading after a stop-loss hit |
| Instant Buy | **ON** | Buys immediately after sell — no waiting for MA dip |
| Fixed Seed | **ON** | Re-enters with original seed; profits banked, never risked |

### Golden Parameters — BTC/KRW (adaptive, 24/7)

| Parameter | Optimal Value | Why |
|---|---|---|
| Mode | **Adaptive** | Auto-scales to BTC's volatile nature |
| MA Period | **24h** | Short-term trend baseline for crypto |
| Buy Dip multiplier | **1.0x** | Enter at 1x current 24h volatility below MA |
| Sell Gain multiplier | **1.5x** | Exit at 1.5x volatility above cost — asymmetric win:loss |
| Stop Loss multiplier | **5.0x** | Wide SL avoids noise-triggered exits on BTC |

**Note:** Market regimes shift — always re-optimize monthly. Old params may underperform in new conditions.

---

## When to Trade (Push Parameters)

Mean reversion works best when:
- **Market is ranging/oscillating** — rate bounces between levels without a clear direction
- **Low volatility** (12h vol < 0.2%) — small predictable swings
- **6h MA is flat** — no strong trend in either direction
- **During Seoul market hours (09:00-15:30 KST)** — tighter spreads, more liquidity
- **Mid-week (Tue-Thu)** — Monday/Friday tend to have gap risk and position squaring

**When you see these conditions:** Use the golden parameters (instant buy, fixed seed, +0.40% gain, -0.50% SL, max 2/day, 3h cooldown). Multiple cycles per day will compound.

## When to Hold Cash (Do NOT Trade)

Mean reversion loses money when:
- **Strong directional trend** — rate drops steadily without bouncing (e.g., Apr 2026: -3% in a week)
- **High volatility** (12h vol > 0.3%) — big swings overshoot your stop-loss
- **48h MA is also declining** — the dip isn't a dip, it's a trend
- **After a major news event** — FOMC, BOK surprise, geopolitical shock creates momentum, not mean reversion
- **Large buy dip + small sell gain combos** — the optimizer showed these consistently lose money
- **Weekend (Sat-Sun)** — lower liquidity, wider spreads on crypto markets

**When you see these conditions:** Do NOT enter mean reversion trades. Hold cash. Consider DCA if you're bullish long-term, or wait for the trend to exhaust and volatility to drop.

### Danger Pattern (from optimizer worst results)
- **48h MA + buy dip 0.25% + sell gain 0.05-0.10%** → worst losses (-₩85K)
- Long MA means slow to detect trend changes
- Tight sell gain means you exit too early on winners but hold losers too long
- This combo has 64% win rate but tiny wins and large losses = net negative

---

## Tips

- **Start with paper trading** for at least 1 month before using real money
- **Intraday mean reversion** reveals many more opportunities than daily data
- **Instant buy + fixed seed** is the recommended mode for USD/KRW — faster cycling, profits banked
- **Re-optimize monthly** — run `optimizer.py` to recalibrate. Market regimes change.
- **Use risk guards** (volatility cap 0.2%, SL cooldown 3h) to avoid overtrading
- **The dominant cost is tax, not spread** — at 90% 우대, spread is nearly free
- **Don't trade during FOMC, NFP, BOK announcements** — volatility is unpredictable
- **DCA strategies beat mean reversion in trending markets** — check the signal panel first
- **If 3 consecutive trades lose, stop for the day** — the market regime has likely shifted
