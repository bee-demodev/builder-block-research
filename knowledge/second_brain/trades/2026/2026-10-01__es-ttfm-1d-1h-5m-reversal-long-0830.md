---
title: "Trade Review - ES TTFM reversal long 08:30"
date: 2026-10-01
time: "08:30"
type: trade
strategy: ttfm
model: TTFM 1D / 1h / 5m
stack: 1D / 1h / 5m
symbol: ES
source: backtest baseline
session: ny_am
weekday: Thu
direction: long
path: reversal
stage: c4
trigger_kind: cisd
bias: neutral
entry: 7742.5
stop: 7705.0
risk: 37.5
target_r: 2.0
result_r: -1.009
r_1: -1.009
r_2: -1.009
r_3: -1.009
r_bias_close: -1.009
mfe_r: 0.167
mae_r: 0.867
outcome: loss
criteria_failed: ["bias_closure_directional", "bias_candle_index_ok"]
status: draft
confidence: unknown
verdict: ??
source_count: 1
journal: "[[2026-10-01__ttfm]]"
---

# ES TTFM reversal long Thu 01 Oct 08:30

> [!info] Journaled automatically, not a live fill
> The companion's own rules replayed on TradingView bars (`results/backtest_tv/2026/baseline/ES_1D-1h-5m.jsonl.gz`). Fill at the trigger candle's close; R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins. Fill the blanks marked `??` and set `status: reviewed`.

## Quick log

- **Model:** TTFM 1D / 1h / 5m, reversal at c4, trigger cisd; bias neutral; ny_am session, Thu
- **Entry:** 7,742.50 at 08:30 (long)
- **Stop:** 7,705.00 (risk 37.50 points, 47% of ADR14)
- **Target:** 2R; structural target 7,742.50
- **Result:** -1.01 R (loss); ladder 1R -1.01, 2R -1.01, 3R -1.01, held to the bias close -1.01
- **Excursion:** best +0.17 R, worst -0.87 R; stopped after 90 min

## Thesis

The forming 1D candle turned at a key level (the previous 1D candle's low 7,705.50), the 1h closed back above it, and the 5m confirmed the turn.

## Checklist (the engine's criteria)

- [x] enough bars loaded
- [x] the timeframe pairing is one he teaches
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
- [ ] the bias candle closed directionally (`bias_closure_directional`)
- [ ] bias candle numbering fits (C2/C3) (`bias_candle_index_ok`)

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

- [[2026-10-01__ttfm]]
- [[TTRADES/concepts/entry-models|entry-models]]
- [[TTRADES/concepts/cisd|cisd]]
- [[TTRADES/concepts/candle-closures|candle-closures]]
- [[TTRADES/concepts/smt-and-psp|smt-and-psp]]
