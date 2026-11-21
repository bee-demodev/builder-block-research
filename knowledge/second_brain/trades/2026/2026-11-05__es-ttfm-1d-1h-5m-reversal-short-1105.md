---
title: "Trade Review - ES TTFM reversal short 11:05"
date: 2026-11-05
time: "11:05"
type: trade
strategy: ttfm
model: TTFM 1D / 1h / 5m
stack: 1D / 1h / 5m
symbol: ES
source: backtest baseline
session: ny_lunch
weekday: Thu
direction: short
path: reversal
stage: c4
trigger_kind: cisd
bias: bullish
entry: 7446.0
stop: 7738.75
risk: 292.75
target_r: 2.0
result_r: -0.379
r_1: -0.379
r_2: -0.379
r_3: -0.379
r_bias_close: 0.317
mfe_r: 0.423
mae_r: 0.781
outcome: open
criteria_failed: ["bias_swing_intact", "bias_c2_not_expanded", "rev_reward_at_least_2r"]
status: draft
confidence: unknown
verdict: ??
source_count: 1
journal: "[[2026-11-05__ttfm]]"
---

# ES TTFM reversal short Thu 05 Nov 11:05

> [!info] Journaled automatically, not a live fill
> The companion's own rules replayed on TradingView bars (`results/backtest_tv/2026/baseline/ES_1D-1h-5m.jsonl.gz`). Fill at the trigger candle's close; R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins. Fill the blanks marked `??` and set `status: reviewed`.

## Quick log

- **Model:** TTFM 1D / 1h / 5m, reversal at c4, trigger cisd; bias bullish; ny_lunch session, Thu
- **Entry:** 7,446.00 at 11:05 (short)
- **Stop:** 7,738.75 (risk 292.75 points, 278% of ADR14)
- **Target:** 2R; structural target 7,303.75
- **Result:** -0.38 R (open); ladder 1R -0.38, 2R -0.38, 3R -0.38, held to the bias close +0.32
- **Excursion:** best +0.42 R, worst -0.78 R

## Thesis

The forming 1D candle turned at a key level (the unfilled 1D fair value gap 7,713.00–7,750.25), the 1h closed back below it, and the 5m confirmed the turn.

## Checklist (the engine's criteria)

- [x] enough bars loaded
- [x] the timeframe pairing is one he teaches
- [x] the bias candle closed directionally
- [x] a higher-timeframe POI was in play
- [x] CISD confirmed the bias
- [x] bias candle numbering fits (C2/C3)
- [x] a key level was reached
- [x] price expanded into the level
- [x] the opposing run was small
- [x] the reversal formed early in the candle
- [x] the level was reclaimed
- [x] reversal CISD confirmed
- [x] the reversal CISD was swift
- [x] an entry trigger printed
- [x] the reversal wick held
- [x] inside the session filter
- [ ] the bias swing held (`bias_swing_intact`)
- [ ] candle 2 had not already expanded (`bias_c2_not_expanded`)
- [ ] reward at least 2R (`rev_reward_at_least_2r`)

## What actually happened

??

## Mistakes

- ??

## What still looks valid

- ??

## Verdict

Verdict: ?? (valid_model_trade | rule_gap | engine_error | discretion_better). Would you have taken it: ??

## Teacher's rules that bear on it

- Delayed protraction is a New York reversal profile: New York reverses the direction of London's move toward the HTF draw on liquidity. ([[TTRADES/sources/afyz_trading_the_daily_ohlc_protraction_profiles|afyz_trading_the_daily_ohlc_protraction_profiles]] 05:00-05:33)
- Reversal closure: price sweeps the previous candle's low (high) but closes back inside the previous candle's range; anticipate the other direction. ([[TTRADES/sources/candle_2_closure_foundation|candle_2_closure_foundation]] 00:44)
- Build the CISD from the whole series of opposing candles, not a single insignificant candle; stop must cover at least 50% of the down-close candle, ideally ~75%. ([[TTRADES/sources/a_simple_3_step_trading_model_full_breakdown|a_simple_3_step_trading_model_full_breakdown]] 51:28)

## Linked

- [[2026-11-05__ttfm]]
- [[TTRADES/concepts/entry-models|entry-models]]
- [[TTRADES/concepts/cisd|cisd]]
- [[TTRADES/concepts/candle-closures|candle-closures]]
- [[TTRADES/concepts/smt-and-psp|smt-and-psp]]
