# BTC/KRW Adaptive Mean Reversion Strategy

> **Disclaimer:** Simulation-based strategy, not financial advice. Past performance does not equal future results. Consult a 세무사 before trading real money.

---

## Strategy Summary

**Goal: Secondary income stream. Higher risk/reward supplement to the USD/KRW 0.1%/day core strategy.**

**Exchange:** Bithumb (maker/taker 0.04%)
**Method:** Adaptive volatility-based mean reversion on hourly BTC/KRW data
**Logic:** Buy when price dips below short-term MA by a threshold that scales with current volatility. Sell when it bounces back by a larger scaled threshold. 24/7 trading.
**Note:** USDT/KRW 24/7 trading underperforms 한투 USD/KRW market hours. BTC is the only crypto pair worth trading.

---

## Adaptive Volatility-Based Mean Reversion Explained

Unlike fixed-threshold strategies (e.g., "buy at -0.05% below MA"), adaptive mode dynamically adjusts entry/exit thresholds based on the **24-hour rolling volatility** of the asset.

**How it works each hour:**
1. Calculate 24h rolling volatility (standard deviation of hourly returns)
2. Multiply volatility by configured multipliers to get thresholds:
   - `buy_dip = max(0.05%, vol x dip_multiplier)`
   - `sell_gain = max(0.05%, vol x gain_multiplier)`
   - `stop_loss = max(0.5%, vol x sl_multiplier)`
3. Calculate MA deviation: `(price - MA) / MA x 100%`
4. If no position and deviation <= -buy_dip: **BUY** all-in at ask
5. If holding and gain >= sell_gain: **SELL** at bid (take profit)
6. If holding and loss >= stop_loss: **SELL** at bid (stop loss)

**Why adaptive works for BTC:**
- BTC volatility swings from 0.3% (calm) to 5%+ (news events) within hours
- Fixed thresholds either miss opportunities (too wide) or get whipsawed (too tight)
- Adaptive mode widens thresholds during high vol (avoid false entries) and tightens during low vol (capture small swings)

---

## BTC Optimal Multipliers

| Parameter | Value | What It Means |
|---|---|---|
| **MA Period** | 24h | Short-term trend baseline. 24h captures intraday cycles without lagging. |
| **Buy Dip x** | 1.0x | Enter when price dips 1x the current volatility below MA. If vol=1%, buy at -1% deviation. Conservative — waits for a real dip relative to current conditions. |
| **Sell Gain x** | 1.5x | Exit when price bounces 1.5x the current volatility above cost. Asymmetric (1.5x gain vs 1.0x entry) ensures winners are larger than typical entries. |
| **Stop Loss x** | 5.0x | Cut loss at 5x volatility. Very wide — avoids noise-triggered exits. Only fires on genuine trend breakdowns. At vol=1%, SL = -5%. |

**Asymmetry is key:** The 1.0x:1.5x entry-to-exit ratio means you need ~40% win rate to break even (after fees). The 5.0x SL means losses are rare but large when they occur.

---

## Instant Buy and Fixed Seed Toggles

Two toggle options available in both Fixed and Adaptive mode:

**Instant Buy (OFF by default):** When ON, buys immediately after sell instead of waiting for the next MA dip. Cycle: BUY → wait for +x% → SELL → BUY immediately → repeat. Useful in trending-up markets where waiting for a dip means missing the move.

**Fixed Seed (OFF by default):** When ON, re-enters with the original seed amount after each sell. Profits are banked and never risked. When OFF (default), compounds by reinvesting full proceeds into the next buy.

### Fixed Seed vs Compound: BTC/KRW Backtest Results (1.5% gain target)

| Scenario | Fixed Seed | Compound | Winner |
|---|---|---|---|
| Winning month (March) | **+4.1%** | +3.6% | Fixed Seed |
| Losing 3 months (Jan-Mar) | **-19.3%** | -20.0% | Fixed Seed (nearly tied) |

**Why Fixed Seed wins:** After a losing trade, compound mode re-enters with a shrunk balance (losses reduce the next buy). Fixed Seed re-enters with the full original amount, catching the recovery at full size. This asymmetry means Fixed Seed outperforms in both winning and losing periods.

**Recommendation: Use Fixed Seed ON for BTC mean reversion.** It is both safer (profits banked) and actually performs better due to the recovery asymmetry.

---

## Cost Model (Bithumb)

| Cost | Amount | Notes |
|---|---|---|
| **Fee** | 0.04% per trade | Bithumb maker/taker flat fee |
| **Round-trip** | 0.08% | Buy + sell |
| **Slippage** | ~0.01-0.05% | Depends on order size and BTC liquidity |
| **Tax** | 가상자산 과세 (see below) | Crypto-specific tax rules |

Bithumb's 0.04% fee is cheaper than Upbit (0.05%). At adaptive thresholds, a typical cycle nets 1-3% gross minus 0.08% fees = ~0.9-2.9% net per cycle.

---

## 24/7 Trading: Advantages and Risks

**Advantages:**
- No market hours restriction — captures overnight and weekend swings
- More trading opportunities than FX (which is limited to 09:00-15:30 KST)
- BTC volatility provides larger per-cycle returns than USD/KRW
- Weekend volatility can be profitable during ranging conditions

**Risks:**
- No circuit breakers — BTC can drop 10%+ in hours (flash crash risk)
- Weekend liquidity is lower — wider effective spreads
- News events happen 24/7 (US regulatory announcements, hack events)
- Must have kill switch and drawdown pause active at all times
- Harder to monitor continuously — automation is essential

---

## Safety Locks

| Lock | BTC Default | Description |
|---|---|---|
| **Max Trades/Day** | 3 | Prevents overtrading. BTC cycles are longer than FX. |
| **Max 12h Vol %** | 1.5% | Skip entry during extreme volatility. BTC baseline vol is higher than FX. |
| **SL Cooldown (hrs)** | 3 | Wait 3 hours after a stop-loss before re-entering. Prevents revenge trading. |
| **Daily Loss Limit** | 3.0% | Stop all trading if daily losses hit 3% of seed. |
| **Max Drawdown** | 10.0% | Temporary pause when portfolio drops 10% from peak. |
| **DD Pause (hrs)** | 48 | Pause 48 hours after drawdown trigger. Resets peak balance and resumes. 0 = permanent halt. |
| **Kill Switch** | 1.5% in 30min | Paper trade only. Auto-stops + sells if price crashes. Protects against flash crashes. |

**Max drawdown pause behavior:** When drawdown threshold is hit, trading pauses for the configured hours. After the pause, the peak balance resets to the current portfolio value and trading resumes. This prevents premature permanent stops while still protecting against sustained declines.

---

## When to Trade BTC (Conditions Favor Mean Reversion)

- **Market is ranging** — BTC oscillating within a band without clear breakout
- **Low-to-mid volatility** (24h vol 0.5-2.0%) — enough movement for profit, not enough for whipsaws
- **24h MA is flat** — no strong directional trend
- **After a consolidation period** — BTC settled post-news, choppy sideways action
- **Weekend if ranging** — lower volume but predictable oscillations

## When to Hold Cash (Do NOT Trade BTC)

- **Strong trend** — BTC dropping/rising 5%+ in 24h without bouncing
- **High volatility** (24h vol > 3%) — thresholds widen so far that no trades trigger, or SL gets hit frequently
- **After major news events** — ETF decisions, exchange hacks, regulatory announcements create momentum, not reversion
- **During liquidation cascades** — large leveraged positions unwinding cause one-directional moves
- **When funding rates are extreme** — indicates crowded positioning, trend likely to continue
- **3 consecutive stop-losses** — regime has shifted, stop for the day

---

## Monthly Profit Projections (Adaptive Mean Reversion)

Based on backtested ~1.5%/month average (conservative estimate for BTC adaptive):

| Seed Money | Monthly Est. | Annual Est. | Annual Tax | Annual Net |
|---|---|---|---|---|
| ₩1,000,000 | ₩15,000 | ₩180,000 | ₩0 | **₩180,000** |
| ₩10,000,000 | ₩150,000 | ₩1,800,000 | ₩0 | **₩1,800,000** |
| ₩100,000,000 | ₩1,500,000 | ₩18,000,000 | ₩3,410,000 | **₩14,590,000** |

**Caution:** BTC is more volatile than USD/KRW. Expect -5% to +10% monthly range. The adaptive mode helps, but large drawdowns are possible. Start with 1M seed and scale up only after 3+ months of positive results.

---

## Tax: 가상자산 과세

Korean crypto tax rules (가상자산 과세):
- **Tax rate:** 22% (소득세 20% + 지방소득세 2%) on annual gains exceeding ₩2,500,000
- **Exemption:** First ₩2,500,000 of annual crypto gains is tax-free
- **Cost basis:** 이동평균법 (moving average method) required
- **Reporting:** Annual tax filing (5월 종합소득세 신고)
- **Implementation status:** Check current legislation as crypto tax has been delayed multiple times. Consult a 세무사 for the latest.

Tax calculation: `tax = max(0, (annual_gain - 2,500,000)) x 0.22`

At ₩10M seed earning ₩1.8M/year: under ₩2.5M exemption, **₩0 tax**.
At ₩100M seed earning ₩18M/year: `(18,000,000 - 2,500,000) x 0.22 = ₩3,410,000 tax`.

---

## Risk Rules

- **Use Fixed Seed ON** — safer and better-performing than compound for BTC
- Never put more than 20% of total savings into crypto (higher risk than FX)
- Keep 6 months expenses in KRW untouched
- Max single trade: 100% of crypto allocation (all-in per mean reversion design)
- If monthly P&L hits -10%: stop all trading, review strategy
- If 3 consecutive trades lose: stop for the day
- Always keep kill switch enabled during paper/live trading
- Do not increase seed size after a winning streak — wait 3+ months of consistent results
