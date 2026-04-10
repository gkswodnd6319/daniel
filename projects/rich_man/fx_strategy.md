# USD/KRW Mean Reversion Strategy

> **Disclaimer:** Simulation-based strategy, not financial advice. Past performance ≠ future results. Consult a 세무사 before trading real money.

---

## Strategy Summary

**Goal: 0.1% daily profit on seed money (₩1,000 per ₩1M, ₩10,000 per ₩10M)**

**Platform:** 한국투자증권 (사전환전, 90% 우대율)
**Method:** Instant buy → sell at +0.40% → repeat. Fixed seed (profits banked, never risked).
**Hours:** 09:00-15:30 KST weekdays only. Max 2 trades/day.

---

## Golden Parameters (한투, instant buy, fixed seed, market hours)

| Parameter | Value | Reasoning |
|---|---|---|
| **Sell Gain %** | +0.40% | Moderate exit — takes profit before bounce exhausts |
| **Stop Loss %** | -0.50% | Wider SL avoids noise-triggered exits on intraday hourly data |
| **Max Trades/Day** | 2 | Limits overtrading while allowing multiple cycles per day |
| **SL Cooldown** | 3h | Prevents revenge trading after a stop-loss hit |
| **Instant Buy** | ON | Buys immediately after sell — skip MA dip wait |
| **Fixed Seed** | ON | Re-enters with original seed amount; profits banked, never risked |

**Important:** Re-optimize every month using `python3 projects/rich_man/optimizer.py`. Market regimes shift — old params may underperform in new conditions.

---

## How It Works

```
Every hour (09:00-15:30 KST, Mon-Fri only):

  IF no position AND under max trades/day limit:
     → BUY all-in at ask price (instant buy after sell, no MA dip wait)

  IF holding AND gain ≥ +0.40%:
     → SELL at bid price (take profit)
     → Bank profits, re-enter with original seed (fixed seed)

  IF holding AND loss ≥ -0.50%:
     → SELL at bid price (stop loss)
     → Wait 3 hours before next entry (SL cooldown)

  Cycle: BUY → +0.40% → SELL → BUY immediately → repeat
  Max 2 complete buy-sell cycles per day
```

**Toggle options (both ON for golden params):**
- **Instant Buy (ON):** Buys immediately after sell instead of waiting for the next MA dip. Cycle: BUY → wait for +x% → SELL → BUY immediately → repeat.
- **Fixed Seed (ON):** Re-enters with the original seed amount after each sell. Profits are banked and never risked. When OFF, compounds by reinvesting full proceeds.

---

## Cost Model (한국투자증권)

| Cost | Amount | Notes |
|---|---|---|
| **Spread** | 0.025% per trade | 0.25% base × (1 - 90% 우대) |
| **Round-trip** | 0.05% | Buy + sell |
| **Commission** | ₩0 | 한투 사전환전 has no commission |
| **Tax** | 22% on gains > ₩2.5M/year | 양도소득세. Annualized. |

At 0.40% sell target, the net per cycle after spread: ~0.40% gross - 0.05% round-trip spread = **~0.35% net**.

---

## Profit Projections (Mean Reversion)

Based on 3-month optimizer results (~1.9%/month average):

| Seed Money | Monthly Est. | Annual Est. | Annual Tax | Annual Net |
|---|---|---|---|---|
| ₩1,000,000 | ₩19,000 | ₩228,000 | ₩0 (under exemption) | **₩228,000** |
| ₩10,000,000 | ₩190,000 | ₩2,280,000 | ₩0 (under exemption) | **₩2,280,000** |
| ₩50,000,000 | ₩950,000 | ₩11,400,000 | ₩1,958,000 | **₩9,442,000** |
| ₩100,000,000 | ₩1,900,000 | ₩22,800,000 | ₩4,466,000 | **₩18,334,000** |

**Caution:** These are based on 3-month backtest (~1.9%/month). Real results will vary. Expect -2% to +6% monthly range. March 2026 alone showed +5%, but April started negative.

---

## When to Trade (Conditions Favor Mean Reversion)

- Market is **ranging/oscillating** — rate bounces between levels
- **12h volatility < 0.20%** — small predictable swings
- **6h MA is flat** — no strong trend
- **Seoul market hours (09:00-15:30 KST)** — tightest spreads
- **Mid-week (Tue-Thu)** — less gap risk than Mon/Fri

## When to Hold Cash (Do NOT Trade)

- **Strong directional trend** — rate drops/rises steadily without bouncing
- **12h volatility > 0.30%** — swings overshoot stop-loss
- **48h MA also declining/rising** — the "dip" is actually a trend
- **Post-news (FOMC, BOK, NFP)** — momentum, not mean reversion
- **Weekend** — lower liquidity, wider spreads
- **3 consecutive stop-losses** — regime has shifted, stop for the day

---

## Monthly Optimization Workflow

Re-optimize at the start of each month. The optimizer now defaults to a **3-month lookback window**:

```bash
# Default: 3-month window (recommended)
python3 projects/rich_man/optimizer.py

# Optionally compare a specific month to see if conditions shifted
python3 projects/rich_man/optimizer.py --start 2026-03-01 --end 2026-03-31
```

The 3-month window balances recency with statistical significance. Update backtest parameters in the Paper Trade UI with the top result. If all combos are losing, **do not trade mean reversion** — hold cash or switch to DCA.

---

## Danger Patterns (From Optimizer)

| Pattern | Result | Why |
|---|---|---|
| 48h MA + tight sell (0.05-0.10%) | Worst losses (-₩85K) | Slow MA misses trend changes, tiny wins can't offset losses |
| Large dip (0.40%+) + any sell | Few trades, capital sits idle | Entry too strict, misses most opportunities |
| No volatility filter + any params | Higher losses | Trades during wild swings get stopped out |

---

## Risk Rules

- Never put more than 30% of savings into FX
- Keep 3 months expenses in KRW untouched
- Max single trade: 10% of FX allocation
- If monthly P&L hits -5%: stop all trading, review strategy
- If 3 consecutive trades lose: stop for the day
- Don't trade 1 hour before/after FOMC, NFP, BOK decisions
