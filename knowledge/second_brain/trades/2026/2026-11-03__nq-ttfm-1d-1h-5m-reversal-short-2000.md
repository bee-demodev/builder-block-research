---
title: "Trade Review - NQ TTFM reversal short 20:00"
date: 2026-11-03
time: "20:00"
type: trade
strategy: ttfm
model: TTFM 1D / 1h / 5m
stack: 1D / 1h / 5m
symbol: NQ
source: backtest baseline
session: asia
weekday: Tue
direction: short
path: reversal
stage: c4
trigger_kind: cisd
bias: neutral
entry: 28149.25
stop: 28512.0
risk: 362.75
target_r: 2.0
result_r: -1.001
r_1: 0.999
r_2: -1.001
r_3: -1.001
r_bias_close: -1.001
mfe_r: 1.471
mae_r: 0.923
outcome: loss
criteria_failed: ["bias_poi_present", "bias_c2_not_expanded", "rev_reward_at_least_2r", "session_filter_ok"]
status: draft
confidence: unknown
verdict: ??
source_count: 1
journal: "[[2026-11-03__ttfm]]"
---

# NQ TTFM reversal short Tue 03 Nov 20:00

> [!info] Journaled automatically, not a live fill
> The companion's own rules replayed on TradingView bars (`results/backtest_tv/2026/baseline/NQ_1D-1h-5m.jsonl.gz`). Fill at the trigger candle's close; R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins. Fill the blanks marked `??` and set `status: reviewed`.

## Quick log

- **Model:** TTFM 1D / 1h / 5m, reversal at c4, trigger cisd; bias neutral; asia session, Tue
- **Entry:** 28,149.25 at 20:00 (short)
- **Stop:** 28,512.00 (risk 362.75 points, 57% of ADR14)
- **Target:** 2R; structural target 27,425.25
- **Result:** -1.00 R (loss); ladder 1R +1.00, 2R -1.00, 3R -1.00, held to the bias close -1.00
- **Excursion:** best +1.47 R, worst -0.92 R; stopped after 545 min

## Thesis

The forming 1D candle turned at a key level (the previous 1D candle's high 28,449.50), the 1h closed back below it, and the 5m confirmed the turn. The trigger closed outside the kill zones (information only).

## Checklist (the engine's criteria)

- [x] enough bars loaded
- [x] the timeframe pairing is one he teaches
- [x] the bias candle closed directionally
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
- [ ] a higher-timeframe POI was in play (`bias_poi_present`)
- [ ] candle 2 had not already expanded (`bias_c2_not_expanded`)
- [ ] reward at least 2R (`rev_reward_at_least_2r`)
- [ ] inside the session filter (`session_filter_ok`)

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

- [[2026-11-03__ttfm]]
- [[TTRADES/concepts/entry-models|entry-models]]
- [[TTRADES/concepts/cisd|cisd]]
- [[TTRADES/concepts/candle-closures|candle-closures]]
- [[TTRADES/concepts/smt-and-psp|smt-and-psp]]
