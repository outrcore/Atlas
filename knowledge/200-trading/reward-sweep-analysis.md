# Reward Sweep Full Analysis — Feb 20, 2026

## Setup
- 4 reward modes × 12 trials each (profit_bonus got 15 due to dual studies on GPU 3)
- Walk-forward validation, 5-12 folds per trial
- Pre-cached SNN predictions, forked shared data
- 4x RTX 4090 pod, ~10 hours runtime

## Results Summary

### Best Trial Per Mode (by composite score)

| Mode | Trial | Composite | Bps/Trade | Fills | Green Folds | BUT... |
|------|-------|-----------|-----------|-------|-------------|--------|
| **pnl_only** | T4 | +0.154 | +0.012 | 220 | 17% | Only 2/12 folds positive |
| **asymmetric** | T8 | +0.865 | +0.047 | 395 | 38% | First 2 folds carry all profit |
| **differential_sharpe** | T11 | +10.849 | +1.092 | 2228 | 30% | ⚠️ ONE fold = +12.14 bps (outlier!) |
| **profit_bonus** | T3 | +8.925 | +1.327 | 1127 | 40% | ⚠️ ONE fold = +13.30 bps (outlier!) |

### Best "Honest" Trials (no outlier dominance)

| Mode | Trial | Composite | Bps/Trade | Fills | Green Folds | Fold PnLs |
|------|-------|-----------|-----------|-------|-------------|-----------|
| **asymmetric** | T7 | +0.186 | +0.018 | 117 | **71%** | [0.138, -0.076, 0.055, 0.006, 0.020, -0.015, 0.0003] |
| **asymmetric** | T9 | +0.090 | +0.009 | 113 | **67%** | [-0.016, 0, 0.042, 0.007, 0.017, 0.0005] |
| **diff_sharpe** | T8 | +0.028 | +0.003 | 107 | **67%** | [0, 0.034, 0.001, 0.007, 0.001, -0.027] |
| **profit_bonus** | T1b | +0.177 | +0.010 | 333 | **67%** | [-0.056, 0.002, 0.063, 0.100, -0.064, 0.016] |

## Key Insights

### 1. Giant outlier folds are NOT real edge
The highest-scoring trials (diff_sharpe T11, profit_bonus T3/T5) all have ONE fold generating 4-13 bps that dominates the average. This is a single lucky trade on a big move — not reproducible.

### 2. The honest edge is ~0.01-0.02 bps/trade
Removing outlier folds, all 4 modes converge to roughly the same underlying performance: near-zero to slightly positive bps/trade. This is AT the noise floor.

### 3. No reward function stands out
All 4 modes produce similar honest results. Reward shaping isn't solving the fundamental signal quality issue. The bottleneck is the SNN prediction quality, not the execution optimization.

### 4. Asymmetric is marginally best
Trial 7 with 71% green folds and +0.018 bps is the most balanced result. The asymmetry_ratio of ~3.0 (penalizing losses 3x) + low lr + medium window produced the most consistent behavior.

### 5. Fill counts remain low
Even the best honest trials have 100-333 fills across all folds. The agent is being very selective but not generating enough volume for reliable statistics.

## Pod Cost
- ~$2.36/hr × ~10 hours = ~$24
- 2 GPU processes still running at time of analysis

## Verdict
**The RL execution layer cannot extract meaningful alpha from the current SNN signal.** The supervised SNN produces ~0.5-1 bps/trade raw signal, but after execution friction (limit order fills, timing, position management), the RL agent can barely break even.

## Possible Paths Forward
1. **STDP unsupervised training** — Paper proved this outperforms supervised (76.8% vs our ~52%). Architectural change
2. **Different market/timeframe** — BTC might not have enough microstructure signal for this approach
3. **Simpler execution** — Skip RL entirely, use SNN signal with fixed threshold and market orders
4. **Accept and deploy** — The asymmetric T7 config is marginally profitable. Paper trade it for validation
5. **Pivot to equities** — Resonance research shows S&P has much stronger signal than BTC
