# HyperClaude AMT Bot — Full Audit Report
**Date:** 2026-02-06  
**Auditor:** Atlas (automated)  
**Period:** 2025-12-04 to 2026-01-23  
**Status:** BOT IS OFF (last trade Jan 23)

---

## Executive Summary

The AMT bot lost **$14.01** across 96 closed trades with a **34.4% win rate**. While the total dollar loss appears small, this masks severe structural problems: the bot is over-trading, the LLM is rationalizing entries, and the one profitable strategy (failed_auction at +$21.45) is subsidizing catastrophic losses from value_fade (-$25.78) and momentum_continuation (-$6.27). The architecture is over-engineered — 4 LLM calls per decision cycle is expensive, slow, and introduces non-determinism at every stage. **Recommendation: Rebuild the decision engine as rule-based, keep the data pipeline and execution layer.**

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│  Hyperliquid WebSocket (BTC trades)                  │
│  hyperliquid_driver.py                               │
│  ├── Tick buffer (24h rolling)                       │
│  ├── Volume profile calculation (POC/VAH/VAL)        │
│  ├── CVD tracking                                    │
│  ├── WATCHDOG (tick-by-tick stop monitoring)          │
│  └── Trigger: every 5m → main.py (EXECUTE=TRUE)      │
│         every 15m/1h/4h → main.py (CONTEXT ONLY)     │
└──────────────────┬───────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────┐
│  main.py — FastAPI Server                            │
│  ├── State management (market_state.json)            │
│  ├── Risk manager (position sizing, circuit breaker) │
│  ├── Trade execution (Hyperliquid orders)            │
│  └── Calls LLM Pipeline ▼                           │
└──────────────────┬───────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────┐
│  LLM Pipeline (4 Gemini API calls per cycle)         │
│  Stage 1: Context Classification (gemini-3-flash)    │
│  Stage 2: Setup Identification (gemini-3-flash)      │
│  Stage 3: Entry Decision (gemini-3-flash)            │
│  Stage 4: Position Management (gemini-3-flash)       │
└──────────────────┬───────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────┐
│  idea_generator.py (HTF context)                     │
│  ├── DuckDB → DigitalOcean Spaces (parquet)          │
│  ├── Monthly/Weekly/Daily/4H/1H/15m profiles         │
│  └── Composite thesis (direction + confidence)       │
└──────────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────┐
│  vector_db/ — ChromaDB                               │
│  ├── Trade history (similarity search)               │
│  ├── Lessons (exit management advice)                │
│  └── Statistics (pattern win rates)                  │
└──────────────────────────────────────────────────────┘
```

---

## Trade Performance Breakdown

### Overall
| Metric | Value |
|--------|-------|
| Total Closed Trades | 96 |
| Total P&L | **-$14.01** |
| Win Rate | 34.4% (33W / 63L) |
| Avg Win | $3.14 |
| Avg Loss | -$1.87 |
| Profit Factor | 0.88 |
| Largest Win | $28.80 |
| Largest Loss | -$6.86 |

### By Strategy (ranked by P&L)
| Strategy | Trades | P&L | Win Rate |
|----------|--------|-----|----------|
| **value_fade_80pct** | 7 | **-$25.78** | **0%** |
| momentum_continuation | 41 | -$6.27 | 32% |
| ib_breakout | 4 | -$5.96 | 50% |
| ib_breakdown | 6 | +$0.57 | 33% |
| unknown | 7 | +$1.98 | 57% |
| **failed_auction** | 31 | **+$21.45** | 39% |

### By Confidence Score
| Confidence | Trades | P&L | Win Rate |
|------------|--------|-----|----------|
| 3 | 12 | +$4.08 | 50% |
| 4 | 4 | +$1.35 | 50% |
| 5 | 2 | -$0.02 | 50% |
| 6 | 4 | -$4.02 | 0% |
| **7** | **31** | **-$6.43** | **29%** |
| 8 | 34 | +$5.03 | 35% |
| **9** | **9** | **-$14.01** | **33%** |

### By Month
| Month | Trades | P&L | Win Rate |
|-------|--------|-----|----------|
| 2025-12 | 10 | +$1.72 | 50% |
| 2026-01 | 86 | -$15.74 | 33% |

### By Direction (inferred)
| Direction | Trades | P&L | Win Rate |
|-----------|--------|-----|----------|
| LONG | 33 | +$19.53 | 36% |
| SHORT | 32 | -$16.22 | 31% |

### Watchdog Exits
- Count: 30 (31% of all exits!)
- Total P&L: +$2.67 (marginally positive — stops are set appropriately)

---

## Top 5 Problems (Ranked by P&L Impact)

### 1. Value Fade Strategy is Catastrophic (-$25.78, 0% win rate)
**Impact:** Single largest P&L drain. 7 trades, all losers.
**Root Cause:** The 80% rule requires very specific conditions (open outside value, re-entry confirmation). The LLM is applying it too liberally — entering value fades without proper confirmation of re-entry. The strategy works in textbooks but requires precision timing the bot doesn't have.
**Fix:** Disable value_fade entirely, or implement strict rule-based entry criteria (require 2+ closes inside VA after opening outside).

### 2. Confidence Score is Inversely Correlated with Performance
**Impact:** Confidence 9 trades lost -$14.01 (worst tier). Confidence 7 lost -$6.43.
**Root Cause:** The LLM inflates confidence when it has a compelling narrative. Higher confidence → higher leverage → bigger losses. The LLM is essentially a rationalizer — given enough market data, it can always construct a plausible thesis. At confidence 9, the bot uses 10x leverage and 2% risk, turning small price moves into outsized losses.
**Fix:** Cap leverage at 5x regardless of confidence. Better: remove LLM confidence scoring entirely and use purely rule-based confidence (count of aligned timeframes).

### 3. Massive Over-Trading (86 trades in January = ~3/day)
**Impact:** Death by a thousand cuts. Fees and slippage compound.
**Root Cause:** The 5-minute trigger fires 288 times/day. Each time, the LLM runs 4 stages and can find a "setup" in almost any market condition. The context classifier is too permissive — it marks markets as "actionable" far too often. With a 34% win rate, every trade costs on average.
**Fix:** Reduce triggers to 15-minute. Add hard rule: max 1 trade per day. Require 3+ timeframe alignment before any entry.

### 4. LLM Non-Determinism Causes Inconsistent Exits (-$3.41 worst exit)
**Impact:** Position management (Stage 4) exits profitable trades too early and holds losers.
**Root Cause:** Every 5 minutes, the LLM re-evaluates the position. It has no memory of prior evaluations — each call is independent. It can exit at 0.5% profit because "IB reclaimed" even though the thesis is still valid. The prompts try to prevent this with extensive guidance (see POSITION_MANAGEMENT_PROMPT), but the LLM still makes inconsistent calls.
**Fix:** Rule-based exit management. Trailing stops by formula, not LLM judgment. Exit only on: stop hit, target hit, time stop.

### 5. Short Trades Underperform (-$16.22 vs +$19.53 long)
**Impact:** Shorts are a consistent drag.
**Root Cause:** BTC has had a bullish bias in this period. The bot shorts aggressively on IB breakdowns and momentum continuation, but BTC dip-buys recover. The LLM doesn't adequately weight the macro trend.
**Fix:** Require higher confidence threshold for shorts (8+ vs 6+ for longs) when monthly/weekly bias is bullish. Or: disable shorts entirely until macro turns bearish.

---

## Decision Architecture Review

### How the LLM Pipeline Works
1. **Context Classification** — Gemini Flash classifies market regime (trend/normal/rotational), bias, actionability. ~10s timeout.
2. **Setup Identification** — Scans for AMT setups (IB breakdown, failed auction, etc.). Returns confidence 1-10.
3. **Entry Decision** — Validates setup, checks CVD, queries vector DB for similar trades. Returns BUY/SELL/PASS.
4. **Position Management** — While in position, every 5m re-evaluates whether to HOLD/TRAIL/EXIT/WIDEN.

### Critical Flaws in This Architecture
- **4 LLM calls per 5-minute candle** = ~$2-5/day in API costs, 20-40s latency per cycle
- **LLM is a rationalizer, not a filter.** Given enough data, Gemini will find a pattern. The prompts are 500+ words each with extensive guidance, but the LLM still produces inconsistent outputs.
- **No backtest capability.** Every change requires live trading to validate. There's no way to replay historical data through the pipeline.
- **Temperature 0.0-0.1 doesn't guarantee determinism.** Same inputs can produce different outputs across calls.

### Watchdog
The watchdog is well-implemented. It monitors price tick-by-tick via WebSocket and triggers emergency closes when stops are hit. It's correctly handling both long and short positions. The +$2.67 net from watchdog exits confirms stops are placed reasonably.

### Vector DB
Contains trade history, lessons, and statistics. The similarity search for past trades is a good idea but poorly utilized — the LLM doesn't meaningfully incorporate the results. The pattern statistics show 50% win rates across the board, which suggests insufficient data for meaningful pattern recognition.

### Rules.json
Comprehensive and well-thought-out AMT rules. The problem isn't the rules — it's that the LLM doesn't reliably follow them. The rules specify "minimum confidence 6/10" but the LLM inflates confidence. The rules say "let winners run" but the LLM exits early.

---

## Research Findings

### LLM-Based Trading: Industry Consensus
- LLMs are **non-deterministic** — same inputs produce different outputs, unacceptable for trading
- LLMs **hallucinate** plausible but wrong strategies, especially under uncertainty
- LLMs **herd** on similar patterns from shared training data
- LLM latency (seconds) is unsuitable for intraday execution
- Rule-based systems are **deterministic, auditable, backtestable** — superior for execution

### Best Practice for AMT Systems
- Volume profile levels should be computed mechanically, not interpreted by LLM
- Entry/exit rules should be codified as if-then logic with precise thresholds
- CVD confirmation should be a boolean check, not an LLM judgment call
- Position sizing should be pure math (risk % / stop distance), which the bot already does correctly

### When LLMs Add Value in Trading
- **Research and analysis** — generating trade ideas, summarizing market conditions
- **Not execution** — the actual buy/sell/exit decisions should be rule-based
- The current architecture uses LLM for both analysis AND execution, which is wrong

---

## Recommendation: Fix or Rebuild?

### Verdict: **Partial Rebuild**

Keep:
- ✅ `hyperliquid_driver.py` — WebSocket data, watchdog, volume profiles. Working well.
- ✅ `hyperliquid_client.py` — Exchange integration. Working.
- ✅ `idea_generator.py` — HTF analysis. Good data pipeline.
- ✅ Risk management in `main.py` — Position sizing, circuit breaker, cooldowns. Solid.
- ✅ `rules.json` — Good AMT framework.

Rebuild:
- ❌ **Replace entire LLM pipeline with rule-based decision engine**
  - Context: IB extension check (boolean), CVD sign check (boolean), HTF alignment count
  - Setup: Pattern match against rules.json criteria mechanically
  - Entry: Confidence = count of aligned factors, not LLM score
  - Exit: Trailing stop by formula, target by level, time stop at session close
- ❌ **Kill value_fade strategy** until backtested
- ❌ **Reduce trade frequency** — max 1-2 trades/day, 15m minimum trigger

### Prioritized Fix Plan

| Priority | Fix | Expected Impact | Effort |
|----------|-----|-----------------|--------|
| 1 | Disable value_fade_80pct | +$25.78/period saved | 5 min |
| 2 | Cap leverage at 5x max | Reduce tail losses ~40% | 5 min |
| 3 | Replace LLM entry with rule-based | Deterministic, backtestable | 2-3 days |
| 4 | Replace LLM position mgmt with formulaic trailing | Consistent exits | 1 day |
| 5 | Add max 1 trade/day limit | Reduce over-trading | 30 min |
| 6 | Require 3+ TF alignment for entry | Higher quality trades | 1 hour |
| 7 | Build backtest framework | Validate before going live | 3-5 days |
| 8 | Higher short threshold when macro bullish | Reduce short losses | 1 hour |

### Optional: Keep LLM for Analysis Only
Use Gemini to generate a daily market brief (regime, key levels, bias) that informs the rule-based engine's parameters. This leverages LLM strengths (synthesis) without its weaknesses (execution consistency).

---

## Research: LLM Model Comparison for Trading

### Which LLM is Best for Trading Decisions?

| Model | Finance Ranking | Cost (per 1M tokens) | Strengths | Weaknesses |
|-------|----------------|---------------------|-----------|------------|
| **GPT-5** | #1 in finance evals | $75/M | Best pattern recognition, earnings/commentary | Extremely expensive, no real-time market access |
| **Claude Opus 4.1** | Near-top, efficient | $3-15/M | "Thinking" mode for reasoning, cost-effective | Unranked on some finance benchmarks |
| **Gemini 3 Pro** ← current | Strong general, lower finance-specific | $2/M | Multimodal (charts), cheap | Lower finance-specific accuracy |
| **DeepSeek R1** | Unranked in finance | $0.55/M | Math/reasoning specialist | No finance benchmark data |
| **Llama 4** | No finance benchmark wins | Free (self-hosted) | 10M context, fine-tunable | Requires infrastructure, no out-of-box finance skill |

**Key finding:** GPT-5 leads finance benchmarks but costs 37x more than Gemini. Claude offers the best cost/accuracy tradeoff. However, **no LLM matches human expert accuracy for live trading decisions** — in a 407-task finance comparison, all LLMs scored below expert humans, with particularly weak forecasting and risk assessment.

**Verdict for HyperClaude:** Switching from Gemini to GPT-5 or Claude would marginally improve analysis quality but would NOT fix the core problem. The issue isn't model quality — it's using an LLM as the decision-maker at all. A better Gemini prompt would yield similar results to switching models.

### Should LLMs Make Trade Decisions? (Hybrid Architecture Research)

**Industry consensus: No. LLMs should analyze, rules should execute.**

The recommended hybrid architecture from multiple sources:

```
┌─────────────────────────┐     ┌──────────────────────────┐
│   LLM LAYER (Analysis)  │     │  RULES ENGINE (Execution) │
│                         │     │                          │
│ • Market regime detect  │────▶│ • If regime=trend AND    │
│ • Sentiment parsing     │     │   IB_extended AND        │
│ • News impact scoring   │     │   CVD_aligned:           │
│ • Daily market brief    │     │     → ENTER (formula)    │
│                         │     │ • Trail stop = f(price)  │
│ Runs: 1x/hour or daily  │     │ • Max 1 trade/day       │
│ Output: JSON parameters │     │ • Position size = math   │
└─────────────────────────┘     └──────────────────────────┘
```

**Why this works:**
- LLMs handle **qualitative context** (regime, sentiment) — their strength
- Rules handle **execution** (entry, exit, sizing) — deterministic, backtestable
- LLM runs infrequently (hourly/daily) → low cost, low latency impact
- Rules run every candle → fast, consistent, auditable
- The LLM's output is **parameters to a rules engine**, not trade decisions

**Why pure-LLM fails (HyperClaude's current approach):**
- 4 LLM calls per 5-minute candle = latency + non-determinism at every decision point
- LLM "finds" setups in any market condition (rationalizer, not filter)
- No backtesting possible — can't replay LLM decisions deterministically
- Inconsistent exits destroy edge even when entries are good

**Cited evidence:**
- Multi-agent CoT trading systems outperform baselines by ~3% returns, but use LLM for analysis only, not execution [arxiv:2601.08641]
- Platforms like Hummingbot succeed with rule-based bots enhanced by analysis, not pure LLM decisions
- Production AI trading systems use guardrails and rules engines as the trust layer

### Open-Source LLM Trading Systems

**No successful open-source LLM trading system has published live performance metrics.** All are research/experimental:

| Project | Architecture | Status |
|---------|-------------|--------|
| **QuantEvolve** (Autonomous-Agents) | Multi-agent evolutionary strategy discovery | Research — no live P&L published |
| **FinGPT** (AI4Finance) | Financial LLM benchmark/fine-tuning | Benchmark tool, not a trading system |
| **FinRL** (AI4Finance) | Reinforcement learning for trading | RL-based, not LLM-based execution |
| **LLM-TradeBot** (GitHub) | LLM signals → rules execution | Early-stage, no results |
| **REITs Trading Framework** (arxiv) | 4 analysis agents → prediction → decision | Tested on Chinese REITs only, low-volatility |

**Key insight:** The most promising architectures (QuantEvolve, REITs framework) all use **multi-agent analysis feeding into deterministic decision layers**. None use a single LLM to make buy/sell decisions directly.

### Revised Recommendation

Based on this research, the audit recommendation is strengthened:

1. **Keep Gemini** — switching models won't fix the architecture problem, and Gemini is cost-effective
2. **Demote Gemini to analysis-only** — run 1x per hour to classify market regime and output parameters
3. **Build a deterministic rules engine** for all entry/exit/sizing decisions
4. **LLM output format:** `{"regime": "trend_day", "bias": "BULLISH", "key_levels": [...], "confidence_factors": 4}` — fed as parameters to the rules engine
5. **This matches what every successful system does** — LLM for brains, rules for hands

---

## Appendix: Account Size Context

With ~$100 equity (inferred from trade sizes of 0.004 BTC at ~$90k = ~$360 notional at 3-5x leverage), the -$14 loss represents ~14% drawdown. This is significant for the account size and confirms the bot should not be trading live until the decision engine is rebuilt and backtested.
