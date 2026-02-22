# Atlas-AMT: Comprehensive Rebuild Plan
**Date:** 2026-02-06
**Author:** ATLAS
**Status:** APPROVED (Matt approved 2026-02-07)
**Last Updated:** 2026-02-07

---

## 1. Executive Summary

The HyperClaude AMT bot has lost **$96.71** (true net) across 404 fills since December 2025. The raw P&L of -$30.49 is dwarfed by **$64.00 in taker fees** (100% market orders) and $2.22 in funding. The bot has one profitable strategy (failed_auction at +$21.45) subsidizing catastrophic losses elsewhere.

**Root cause:** The LLM (Gemini Flash) is a rationalizer, not a filter. It can construct a plausible thesis for any market condition, leading to over-trading (3/day avg) with inflated confidence scores that trigger higher leverage on worse setups.

**The plan:** Keep the solid data infrastructure (driver, volume profiles, watchdog, exchange client). **Replace the 4-stage LLM pipeline with a deterministic rule-based decision engine.** Optionally retain an LLM (Claude via ATLAS) for daily market regime analysis only — never for execution decisions.

---

## 2. Current Architecture (What Exists)

```
Data Layer (KEEP)              Decision Layer (REPLACE)         Execution Layer (KEEP)
─────────────────              ────────────────────────         ─────────────────────
Hyperliquid WebSocket    →     Gemini Flash x4 calls      →    Hyperliquid Orders
  ├─ Tick buffer (24h)           ├─ Context Classify             ├─ Market orders (BAD)
  ├─ Volume profiles             ├─ Setup Identify               ├─ Watchdog stops
  ├─ CVD tracking                ├─ Entry Decision               └─ Position tracking
  └─ IB calculation              └─ Position Mgmt
                                                                
Coinbase OHLCV (HTF)    →     Vector DB (ChromaDB)
  ├─ Monthly profiles            ├─ Trade history
  ├─ Weekly profiles             ├─ Lessons
  ├─ Daily profiles              └─ Statistics
  └─ Idea generator
```

### What Works (Keep)
| Component | File | Why It's Good |
|-----------|------|---------------|
| Hyperliquid driver | `hyperliquid_driver.py` | Solid WebSocket, tick buffering, volume profile calc, watchdog |
| Exchange client | `hyperliquid_client.py` | Clean API wrapper, order placement, account queries |
| Idea generator | `idea_generator.py` | Good HTF analysis pipeline, DuckDB → profiles across 6 timeframes |
| Risk manager | `main.py` (RiskManager class) | Correct position sizing, circuit breaker, drawdown protection |
| Rules framework | `rules.json` | Comprehensive AMT rules — the theory is sound |
| Trade recorder | `main.py` (trade logging) | Good audit trail |

### What's Broken (Replace)
| Component | Problem | Impact |
|-----------|---------|--------|
| LLM Pipeline (4 stages) | Non-deterministic, rationalizes entries, inflates confidence | -$30.49 P&L |
| Market orders only | 100% taker, 0.045% per fill | -$64.00 fees |
| 5-min trigger cycle | 288 opportunities/day to over-trade | 86 trades in Jan |
| Dynamic leverage (LLM confidence) | Conf 9 = 10x leverage, but conf 9 has worst performance | Amplified losses |
| Value fade strategy | 0% win rate, -$25.78 | Biggest single drain |
| Vector DB | LLM doesn't meaningfully use the similarity results | Wasted complexity |

---

## 3. Performance Audit (Real Numbers)

### Account Summary
| Metric | Value |
|--------|-------|
| Current Equity | $203.67 |
| Starting Equity (est.) | ~$300 |
| Closed P&L | -$30.49 |
| Total Fees | -$64.00 |
| Funding P&L | -$2.22 |
| **True Net Loss** | **-$96.71 (~32% drawdown)** |

### Strategy Breakdown
| Strategy | Trades | P&L | Win Rate | Verdict |
|----------|--------|-----|----------|---------|
| failed_auction | 31 | +$21.45 | 39% | **KEEP — only winner** |
| ib_breakdown | 6 | +$0.57 | 33% | Keep, needs tighter rules |
| momentum_continuation | 41 | -$6.27 | 32% | **REMOVE — over-traded, negative EV** |
| ib_breakout | 4 | -$5.96 | 50% | Insufficient data, pause |
| value_fade_80pct | 7 | -$25.78 | 0% | **KILL IMMEDIATELY** |

### Direction Breakdown
| Direction | Trades | P&L | Win Rate |
|-----------|--------|-----|----------|
| LONG | 33 | +$19.53 | 36% |
| SHORT | 32 | -$16.22 | 31% |

### Fee Impact
| Metric | Value |
|--------|-------|
| Total fills | 404 |
| Taker fills | 404 (100%) |
| Total fees | $64.00 |
| Avg fee per fill | $0.158 |
| Fee as % of losses | **68%** |
| If limit orders (est. 0.01% maker) | ~$14.20 (saving ~$50) |

---

## 4. New Architecture: Rule-Based Decision Engine

### Design Philosophy
1. **Deterministic:** Same inputs → same output, every time
2. **Backtestable:** Can replay historical data through the engine
3. **Auditable:** Every decision traced to specific rule triggers
4. **Fee-aware:** Limit orders by default, fee-adjusted targets
5. **Conservative:** Fewer, higher-quality trades

### Architecture

```
Data Layer (Existing)          Rule Engine (NEW)               Execution Layer (Improved)
─────────────────              ─────────────────               ──────────────────────────
Hyperliquid WebSocket    →     1. Regime Classifier      →     Limit Order Placement
  ├─ Tick buffer                  (boolean checks)              ├─ Post-only orders
  ├─ Volume profiles          2. Setup Scanner                  ├─ Trailing stops (formula)
  ├─ CVD tracking                (pattern matching)             ├─ Time stops
  └─ IB calculation           3. Entry Gate                     └─ Target exits
                                 (alignment scoring)
Coinbase OHLCV (HTF)    →    4. Position Manager          →   Watchdog (Existing)
  └─ Idea generator              (formulaic exits)              └─ Emergency stops
       (keep as-is)
                              5. Trade Filter
                                 (max frequency, fees)
                                                            
Daily Analysis (NEW)                                        Backtest Framework (NEW)
  └─ ATLAS/Claude brief                                       ├─ Historical replay
     (regime + bias only,                                     ├─ Strategy comparison
      NOT execution)                                          └─ Parameter optimization
```

### Stage 1: Regime Classifier (Replaces LLM Context Classification)
Pure boolean/numeric checks, no LLM:
```python
def classify_regime(market_data):
    regime = {
        'ib_extended_above': price > ib_high,
        'ib_extended_below': price < ib_low,
        'inside_ib': ib_low <= price <= ib_high,
        'cvd_bullish': cvd_delta > 0 and cvd_trend == 'rising',
        'cvd_bearish': cvd_delta < 0 and cvd_trend == 'falling',
        'above_poc': price > daily_poc,
        'above_vah': price > daily_vah,
        'below_val': price < daily_val,
        'volume_spike': current_volume > avg_volume * 2,
        'htf_bullish': monthly_bias == 'bullish' and weekly_bias == 'bullish',
        'htf_bearish': monthly_bias == 'bearish' and weekly_bias == 'bearish',
    }
    return regime
```

### Stage 2: Setup Scanner (Replaces LLM Setup Identification)
Pattern matching against codified AMT rules:
```python
SETUP_RULES = {
    'failed_auction': {
        'conditions': [
            'price_broke_prior_high_or_low',      # Boolean
            'rejection_candle_present',             # Boolean (wick > 2x body)
            'cvd_divergence_present',               # Boolean (price up, CVD down or vice versa)
            'back_inside_value_area',               # Boolean
        ],
        'min_conditions': 3,                        # At least 3 of 4 must be true
        'direction': 'counter_to_failed_break',     # If broke high and failed → SHORT, etc.
        'trade_type': 'mean_reversion',
    },
    'ib_breakdown': {
        'conditions': [
            'price_below_ib_low',                   # Boolean
            'ib_width_normal',                       # Boolean (not too wide/narrow)
            'cvd_confirming_direction',              # Boolean
            'htf_alignment_bearish',                 # Boolean (at least 2 HTF bearish)
            'no_nearby_support',                     # Boolean (no daily/weekly VAL within 0.3%)
        ],
        'min_conditions': 4,
        'direction': 'SHORT',
        'trade_type': 'trend_following',
    },
    # ... ib_breakout (mirror of breakdown)
}
```

### Stage 3: Entry Gate (Replaces LLM Entry Decision)
Mechanical scoring — no interpretation:
```python
def calculate_confidence(setup, market_data, htf_ideas):
    score = 0
    
    # Timeframe alignment (max 10 points, from rules.json weights)
    if monthly_aligned: score += 3
    if weekly_aligned: score += 2
    if daily_aligned: score += 2
    if h4_aligned: score += 1
    if h1_aligned: score += 1
    if m15_aligned: score += 1
    
    # Deductions
    if conflicting_timeframe: score -= 1  # Per conflict
    if high_volatility and mean_reversion: score -= 1
    if against_macro_trend: score -= 2
    
    return max(0, min(10, score))

# Hard rules (non-negotiable)
ENTRY_GATES = {
    'min_confidence': 6,
    'max_trades_per_day': 1,            # Down from ~3/day
    'min_risk_reward': 2.0,             # Minimum 2:1 R:R
    'cooldown_after_loss_minutes': 60,  # No revenge trading
    'no_trade_window': ['15:55', '16:10'],  # Session close
    'require_htf_alignment': 2,         # At least 2 higher TFs agree
    'cvd_delta_threshold': 100,         # Hard CVD filter for mean reversion
}
```

### Stage 4: Position Manager (Replaces LLM Position Management)
Formulaic exits — no LLM re-evaluation:
```python
EXIT_RULES = {
    'trend_following': {
        'initial_stop': 'entry - (ATR * 1.5)',        # or structural level
        'trail_activation': '1.0%',                     # Start trailing at 1% profit
        'trail_distance': 'ATR * 1.0',                 # Trail by 1 ATR
        'target_1': 'next_structural_level',            # VAH/VAL/POC/PDH/PDL
        'target_2': 'next_value_area_extreme',          # Extended target
        'time_stop': '4 hours',                         # Max hold time
        'breakeven_at': '0.5%',                         # Move stop to breakeven at 0.5%
    },
    'mean_reversion': {
        'initial_stop': 'beyond_failed_level + buffer', # Beyond the level that failed
        'trail_activation': '0.8%',
        'trail_distance': 'ATR * 0.75',
        'target': 'opposite_value_area_extreme',        # POC or opposite VA extreme
        'time_stop': '2 hours',                         # Mean reversion = shorter duration
        'breakeven_at': '0.4%',
    },
}
```

### Stage 5: Trade Filter (NEW — doesn't exist in current system)
Pre-execution sanity checks:
```python
TRADE_FILTERS = {
    'min_expected_profit_after_fees': 0.3,  # % — must clear fees + slippage
    'max_daily_trades': 1,
    'max_daily_loss': -4.0,                  # % — circuit breaker (existing)
    'require_volume_confirmation': True,      # No entries on low volume
    'min_distance_to_stop': 0.2,             # % — stop can't be too tight
}
```

### Stage 6: Session Awareness (NEW)
Adjusts behavior based on time-of-day liquidity:
```python
SESSION_PROFILES = {
    'us_open': {
        'hours': ['09:30', '11:30'],        # EST
        'volume_expectation': 'HIGH',
        'confidence_modifier': 0,            # Normal rules
        'stop_multiplier': 1.0,
        'size_multiplier': 1.0,
    },
    'us_afternoon': {
        'hours': ['11:30', '16:00'],
        'volume_expectation': 'NORMAL',
        'confidence_modifier': 0,
        'stop_multiplier': 1.0,
        'size_multiplier': 1.0,
    },
    'overnight_low_vol': {
        'hours': ['00:00', '07:00'],
        'volume_expectation': 'LOW',
        'confidence_modifier': +1,           # Need MORE confidence to trade
        'stop_multiplier': 1.3,              # Wider stops (wicks)
        'size_multiplier': 0.7,              # Smaller size
    },
    'eu_session': {
        'hours': ['07:00', '09:30'],
        'volume_expectation': 'MODERATE',
        'confidence_modifier': 0,
        'stop_multiplier': 1.1,
        'size_multiplier': 0.9,
    },
}
```
Session info is logged with every trade for performance analysis by time-of-day.

### Directional Bias (from Daily Brief)
Instead of hard-disabling longs or shorts, the daily analysis sets a bias score:
```python
# Bias score from -3 (strong bearish) to +3 (strong bullish)
# Applied as confidence modifier:
#   bias = +2 (bullish) → longs get +1 confidence, shorts get -1
#   bias = -2 (bearish) → shorts get +1 confidence, longs get -1
# Nothing is fully disabled — just tilted toward the regime
def apply_directional_bias(confidence, direction, bias_score):
    if direction == 'LONG':
        return confidence + (bias_score // 2)  # Positive bias helps longs
    else:
        return confidence - (bias_score // 2)  # Positive bias hurts shorts
```

---

## 5. Limit Order Execution (Fee Fix)

### Current Problem
- 404/404 fills are taker (market) orders = 0.045% per fill
- $64 in fees on $142K volume
- Fees are 2x the actual trading losses

### Solution: Post-Only Limit Orders
```python
def place_limit_entry(direction, target_price, size):
    """Place post-only limit order at favorable price."""
    if direction == 'LONG':
        # Place limit at bid or slightly below
        limit_price = best_bid - tick_size
    elif direction == 'SHORT':
        # Place limit at ask or slightly above
        limit_price = best_ask + tick_size
    
    order = client.place_order(
        coin='BTC',
        is_buy=(direction == 'LONG'),
        sz=size,
        limit_px=limit_price,
        order_type={'limit': {'tif': 'Gtc'}},  # Good til cancelled
        reduce_only=False,
    )
    
    # Cancel if not filled within 30 seconds (market moved)
    schedule_cancel(order.id, timeout=30)
```

### Expected Impact
| Order Type | Fee Rate | On $142K Volume | Savings |
|------------|----------|-----------------|---------|
| Taker (current) | 0.045% | $64.00 | — |
| Maker (limit) | 0.01% | $14.20 | **$49.80** |
| Post-only + rebate | -0.002% | -$2.84 (rebate!) | **$66.84** |

**Note:** Hyperliquid maker rebates depend on tier. At minimum we save $50/period. At best we get paid to provide liquidity.

---

## 6. Leverage Policy (Fixed)

### Current Problem
LLM confidence 9 → 10x leverage → biggest losses (-$14.01 at conf 9)

### New Policy: Fixed Conservative Leverage
| Confidence | Old Leverage | New Leverage | Rationale |
|------------|-------------|-------------|-----------|
| 6 | 3x | 3x | Minimum threshold |
| 7 | 5x | 3x | Reduced — was losing tier |
| 8 | 5x | 5x | Standard |
| 9 | 10x | 5x | **Capped** — was worst tier |
| 10 | 10x | 5x | **Capped** — never 10x |

**Max leverage: 5x, period.** No exceptions. With a $200 account, 10x leverage on a bad entry is account-threatening.

---

## 7. Strategy Whitelist

### Phase 1 (Launch): Conservative
Only strategies with proven positive expectancy:
| Strategy | Status | Rationale |
|----------|--------|-----------|
| **failed_auction** | ✅ ENABLED | +$21.45, 39% WR — only proven winner |
| ib_breakdown | ✅ ENABLED (tight rules) | +$0.57, needs more data |
| ib_breakout | ⏸️ PAUSED | Only 4 trades, insufficient data |
| momentum_continuation | ❌ DISABLED | -$6.27, 32% WR, over-traded |
| value_fade_80pct | ❌ DISABLED | -$25.78, 0% WR — catastrophic |

### Phase 2 (After Backtest): Re-evaluate
Once the backtest framework exists, test disabled strategies against historical data. Re-enable only if backtested positive EV with >100 trade sample.

---

## 8. Backtest Framework (NEW)

### Why This Is Critical
The current system has **zero ability to test changes without live money.** Every logic change since December has been tested live. This is gambling, not trading.

### Architecture
```python
class Backtester:
    """Replay historical data through the rule engine."""
    
    def __init__(self, rule_engine, start_date, end_date):
        self.engine = rule_engine
        self.data = load_historical_ticks(start_date, end_date)
        self.trades = []
        self.equity_curve = [STARTING_EQUITY]
    
    def run(self):
        for candle in self.data:
            signal = self.engine.evaluate(candle)
            if signal.action in ('BUY', 'SELL'):
                self.open_trade(signal)
            self.manage_open_trades(candle)
        return self.generate_report()
    
    def generate_report(self):
        return {
            'total_pnl': sum(t.pnl for t in self.trades),
            'win_rate': wins / total,
            'profit_factor': gross_wins / abs(gross_losses),
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'trades_per_day': len(self.trades) / days,
            'fee_adjusted_pnl': total_pnl - total_fees,
        }
```

### Data Sources
- **Tick data:** Already buffered by `hyperliquid_driver.py` (24h rolling)
- **Historical OHLCV:** Already pulled from Coinbase via `idea_generator.py`
- **Storage:** Save tick buffers daily to parquet files on DigitalOcean Spaces (already set up)

### Validation Rules
- Minimum 100 trades before going live with any strategy
- Must show positive EV after fees
- Must show < 10% max drawdown
- Out-of-sample testing (train on month 1, test on month 2)

---

## 9. Daily Analysis (ATLAS Market Brief)

### How It Works
Once per day at **6:30 AM EST**, a cron job on the trading server pulls current market data (Hyperliquid + Coinbase APIs — price, volume profiles, key levels across all timeframes). It sends this data to ATLAS via webhook. ATLAS analyzes it and produces two outputs:

1. **Engine Config (JSON)** — pushed back to the trading server, sets parameters for the rule engine
2. **Matt's Daily Brief** — sent to Matt via Telegram with key levels, regime analysis, and what to watch for

### Engine Config Example
```json
{
    "date": "2026-02-07",
    "macro_regime": "BEARISH",
    "directional_bias": {
        "score": -2,
        "long_confidence_modifier": -1,
        "short_confidence_modifier": +1
    },
    "key_levels": {
        "monthly_vah": 102500, "monthly_poc": 98200, "monthly_val": 94800,
        "weekly_vah": 97500, "weekly_poc": 96200, "weekly_val": 95100,
        "daily_vah": 96800, "daily_poc": 96100, "daily_val": 95400,
        "pdh": 97200, "pdl": 95000
    },
    "session_awareness": {
        "high_volume_hours": ["09:30-11:30", "14:00-16:00"],
        "low_volume_hours": ["00:00-07:00"],
        "low_volume_rules": {
            "min_confidence_boost": 1,
            "stop_multiplier": 1.3,
            "position_size_multiplier": 0.7
        }
    },
    "volatility_expectation": "ELEVATED",
    "strategy_permissions": {
        "failed_auction": true,
        "ib_breakdown": true,
        "ib_breakout": false,
        "momentum_continuation": false,
        "value_fade_80pct": false
    }
}
```

### Matt's Daily Brief Example
```
BTC Daily Brief — Feb 7, 2026

Macro: BEARISH — monthly POC migrating lower, weekly value 
dropping. BTC rejected 97.5K twice this week.

Key Levels:
  Resistance: 97,500 (weekly VAH) → 98,200 (monthly POC)
  Support: 95,100 (weekly VAL) → 94,800 (monthly VAL)
  POC: 96,100 (daily) — watch for acceptance above/below

Today's Bias: SHORT-favored (+1 confidence on shorts)
Watch For: Failed auction at 95K if it breaks and reclaims.
  IB breakdown below 95,100 with CVD confirmation.
Session: Low vol overnight was choppy. Expect real move 
  after 9:30 AM.
```

### Why This Works
- Runs once/day, not 288 times
- Sets parameters, doesn't execute trades
- ATLAS has broader context (macro sentiment, cross-market awareness)
- Daily regime analysis is an LLM strength (synthesis, not split-second decisions)
- Matt gets a briefing he can follow along with during the trading day

---

## 10. Implementation Plan

### Phase 0: Immediate Fixes (Day 1) — NO CODE CHANGES NEEDED
| Task | Time | Impact |
|------|------|--------|
| Disable value_fade_80pct in rules.json | 5 min | Saves ~$25/period |
| Disable momentum_continuation | 5 min | Saves ~$6/period |
| Cap leverage at 5x in config | 5 min | Reduces tail risk ~40% |
| Set max 1 trade/day in config | 5 min | Reduces fee burn ~60% |

### Phase 1: Limit Orders (Days 1-2)
| Task | Time | Impact |
|------|------|--------|
| Modify `place_hyperliquid_order()` for limit orders | 2 hrs | ~$50 fee savings |
| Add post-only flag | 30 min | Guarantee maker status |
| Add order timeout/cancel logic | 1 hr | Handle unfilled orders |
| Test on small position | 1 hr | Verify execution |

### Phase 2: Rule Engine Core (Days 3-5)
| Task | Time | Impact |
|------|------|--------|
| Build `rule_engine.py` — Regime Classifier | 3 hrs | Replaces LLM Stage 1 |
| Build `rule_engine.py` — Setup Scanner | 4 hrs | Replaces LLM Stage 2 |
| Build `rule_engine.py` — Entry Gate | 3 hrs | Replaces LLM Stage 3 |
| Build `rule_engine.py` — Position Manager | 4 hrs | Replaces LLM Stage 4 |
| Build `rule_engine.py` — Trade Filter | 2 hrs | New safety layer |
| Wire into `main.py`, bypass LLM pipeline | 2 hrs | Integration |

### Phase 3: Backtest Framework (Days 5-7)
| Task | Time | Impact |
|------|------|--------|
| Build `backtester.py` | 4 hrs | Historical replay |
| Historical data export (tick → parquet) | 2 hrs | Data storage |
| Backtest failed_auction strategy | 1 hr | Validate before live |
| Backtest ib_breakdown strategy | 1 hr | Validate |
| Parameter optimization | 2 hrs | Tune thresholds |

### Phase 4: Paper Trading on Testnet (Days 7-10)
| Task | Time | Impact |
|------|------|--------|
| Switch `use_testnet: true` in hl_config.json | 5 min | Real market data, fake money |
| Run full system live on Hyperliquid testnet | 3-5 days | End-to-end validation |
| Log every signal, fill, and P&L | — | Real execution testing |
| Validate limit order fills, timing, slippage | — | Execution quality check |
| Fix any edge cases found | ongoing | Stability |

### Phase 5: Go Live (Day 10+)
| Task | Time | Impact |
|------|------|--------|
| Switch `use_testnet: false` | 5 min | Back to mainnet |
| Deploy rule engine to production | 1 hr | Replace LLM pipeline |
| Start with minimum position size | — | Conservative ramp |
| Daily ATLAS brief → Matt via Telegram | automatic | Market context + levels |
| Daily review of trades | 15 min/day | Ongoing monitoring |
| Weekly parameter review | 1 hr/week | Continuous improvement |

---

## 11. Success Metrics

### Minimum Viable (must hit before staying live):
- Win rate > 40% (up from 34%)
- Profit factor > 1.2 (up from 0.88)
- Max 1-2 trades per day (down from ~3)
- Fees < 30% of gross profit (down from >200%)
- No single strategy with 0% win rate

### Target (3-month goal):
- Win rate > 50%
- Profit factor > 1.5
- Monthly return > 5% (after fees)
- Max drawdown < 10%
- Sharpe ratio > 1.0

### Stretch:
- Positive P&L every month
- Automated daily briefs from ATLAS
- Expand to ETH/SOL with same rule engine
- Graduate to larger position sizes

---

## 12. Risk Controls (Non-Negotiable)

These rules are hardcoded and cannot be overridden:

1. **Max 5x leverage** — no exceptions
2. **Max 1 trade per day** (increase to 2 only after 30 days of profitability)
3. **4% daily drawdown circuit breaker** — shuts down for the session
4. **2% max risk per trade** — position sized to stop loss
5. **No trading during IB formation** (first 60 min of RTH)
6. **Minimum 2:1 reward-to-risk** — won't enter if target < 2x stop distance
7. **Limit orders only** — no market orders except emergency watchdog exits
8. **60-minute cooldown after a loss** — no revenge trading
9. **Strategy whitelist enforced** — only backtested strategies can execute
10. **Kill switch** — manual override to disable all trading instantly

---

## 13. Matt's Decisions (Resolved)

1. **Account size:** $203 current equity. More capital if the system proves itself. All sizing is percentage-based — scales automatically with equity. No fixed-value optimization.
2. **Trading hours:** 24/7 with **session awareness layer**. Tighter rules during low-volume overnight hours (higher confidence threshold, wider stops, smaller size). Session tracked on every trade for performance analysis.
3. **Directional bias:** No strategies fully disabled. **Bias score system** tilts confidence toward the current macro regime. Bearish macro → shorts get confidence bonus, longs get penalty. Both directions always available for strong setups.
4. **Gemini costs:** Negligible. Eliminated entirely with rule engine.
5. **Timeline:** Backtest first → testnet paper trading 3-5 days → go live. No artificial urgency but move fast.
6. **Multi-asset:** Yes, once BTC is profitable. Rule engine designed to be asset-agnostic — adding ETH/SOL is config, not code.
7. **Daily brief:** ATLAS sends Matt a Telegram brief alongside the engine config. Key levels, regime, bias, what to watch for.

---

*This plan prioritizes capital preservation and provable edge before scaling. The AMT theory is sound — the implementation just needs to match the discipline the theory demands.*

---

## 14. Infrastructure: Dev/Prod Split (Added 2026-02-07)

### Development (RunPod GPU — this server)
- **Path:** `/workspace/projects/HyperClaude-AMT-Atlas/`
- **Purpose:** All development, backtesting, rule engine iteration, dashboard
- **Advantages:** GPU compute, ATLAS direct access, fast iteration, all tools installed
- **Data:** DO Spaces parquet via DuckDB + local cache
- **RunPod:** On-Demand Non-interruptible, IP stable unless manually shut down
- **Storage:** 20GB container + 100GB cloud (expandable)

### Production (DigitalOcean — YOUR_SERVER_IP)  
- **Path:** `/root/amt-bot/`
- **Purpose:** Live trading only (when ready)
- **Advantages:** Static IP, always-on, isolated from dev
- **Deploy:** Push tested code from dev → prod via git or scp
- **Access:** `ssh root@YOUR_SERVER_IP`

### Data Storage (DigitalOcean Spaces — keep)
- **Bucket:** `market-data-bucket`
- **Purpose:** Historical candle data archive, cheap S3 storage
- **Access:** DuckDB with DO Spaces credentials
- **Cost:** ~$5/mo

### Workflow
1. Develop & test on RunPod (rule engine, backtester, dashboard)
2. When ready for live: deploy clean build to DO production
3. ATLAS monitors both environments
4. Daily brief: generated on RunPod, config pushed to prod server
