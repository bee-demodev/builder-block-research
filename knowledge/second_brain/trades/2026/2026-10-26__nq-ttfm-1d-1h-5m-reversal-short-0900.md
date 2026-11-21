---
title: "Trade Review - NQ TTFM reversal short 09:00"
date: 2026-10-26
time: "09:00"
type: trade
strategy: ttfm
model: TTFM 1D / 1h / 5m
stack: 1D / 1h / 5m
symbol: NQ
source: backtest baseline
session: ny_am
weekday: Mon
direction: short
path: reversal
stage: c4
trigger_kind: cisd
bias: bullish
entry: 29283.0
stop: 29354.0
risk: 71.0
target_r: 2.0
result_r: -1.007
r_1: 0.997
r_2: -1.007
r_3: -1.007
r_bias_close: -1.007
mfe_r: 1.658
mae_r: 0.754
outcome: loss
criteria_failed: ["bias_c2_not_expanded"]
status: draft
confidence: unknown
verdict: ??
source_count: 1
journal: "[[2026-10-26__ttfm]]"
---

# NQ TTFM reversal short Mon 26 Oct 09:00

> [!info] Journaled automatically, not a live fill
> The companion's own rules replayed on TradingView bars (`results/backtest_tv/2026/baseline/NQ_1D-1h-5m.jsonl.gz`). Fill at the trigger candle's close; R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins. Fill the blanks marked `??` and set `status: reviewed`.

## Quick log

- **Model:** TTFM 1D / 1h / 5m, reversal at c4, trigger cisd; bias bullish; ny_am session, Mon
- **Entry:** 29,283.00 at 09:00 (short)
- **Stop:** 29,354.00 (risk 71.00 points, 13% of ADR14)
- **Target:** 2R; structural target 29,190.50
- **Result:** -1.01 R (loss); ladder 1R +1.00, 2R -1.01, 3R -1.01, held to the bias close -1.01
- **Excursion:** best +1.66 R, worst -0.75 R; stopped after 75 min

## Thesis

The forming 1D candle turned at a key level (the previous 1D candle's high 29,326.00), the 1h closed back below it, and the 5m confirmed the turn.

## Checklist (the engine's criteria)

- [x] enough bars loaded
- [x] the timeframe pairing is one he teaches
- [x] the bias candle closed directionally
- [x] a higher-timeframe POI was in play
- [x] CISD confirmed the bias
- [x] bias candle numbering fits (C2/C3)
- [x] the bias swing held
- [x] a key level was reached
- [x] price expanded into the level
- [x] the opposing run was small
- [x] the reversal formed early in the candle
- [x] the level was reclaimed
- [x] reversal CISD confirmed
- [x] the reversal CISD was swift
- [x] an entry trigger printed
- [x] the reversal wick held
- [x] reward at least 2R
- [x] inside the session filter
- [ ] candle 2 had not already expanded (`bias_c2_not_expanded`)

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

- [[2026-10-26__ttfm]]
- [[TTRADES/concepts/entry-models|entry-models]]
- [[TTRADES/concepts/cisd|cisd]]
- [[TTRADES/concepts/candle-closures|candle-closures]]
- [[TTRADES/concepts/smt-and-psp|smt-and-psp]]
