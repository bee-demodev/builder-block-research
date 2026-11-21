---
title: "Trade Review - NQ TTFM reversal short 02:00"
date: 2026-10-14
time: "02:00"
type: trade
strategy: ttfm
model: TTFM 1D / 1h / 5m
stack: 1D / 1h / 5m
symbol: NQ
source: backtest baseline
session: london
weekday: Wed
direction: short
path: reversal
stage: c4
trigger_kind: cisd
bias: bearish
entry: 30752.25
stop: 30891.5
risk: 139.25
target_r: 2.0
result_r: 1.998
r_1: 0.998
r_2: 1.998
r_3: 2.998
r_bias_close: 4.399
mfe_r: 12.677
mae_r: 0.786
outcome: win
criteria_failed: ["bias_poi_present", "bias_candle_index_ok", "rev_reward_at_least_2r"]
status: draft
confidence: unknown
verdict: ??
source_count: 1
journal: "[[2026-10-14__ttfm]]"
---

# NQ TTFM reversal short Wed 14 Oct 02:00

> [!info] Journaled automatically, not a live fill
> The companion's own rules replayed on TradingView bars (`results/backtest_tv/2026/baseline/NQ_1D-1h-5m.jsonl.gz`). Fill at the trigger candle's close; R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins. Fill the blanks marked `??` and set `status: reviewed`.

## Quick log

- **Model:** TTFM 1D / 1h / 5m, reversal at c4, trigger cisd; bias bearish; london session, Wed
- **Entry:** 30,752.25 at 02:00 (short)
- **Stop:** 30,891.50 (risk 139.25 points, 32% of ADR14)
- **Target:** 2R; structural target 30,476.00
- **Result:** +2.00 R (win); ladder 1R +1.00, 2R +2.00, 3R +3.00, held to the bias close +4.40
- **Excursion:** best +12.68 R, worst -0.79 R

## Thesis

The forming 1D candle turned at a key level (the previous 1D candle's high 30,906.00), the 1h closed below it, and the 5m confirmed the turn.

## Checklist (the engine's criteria)

- [x] enough bars loaded
- [x] the timeframe pairing is one he teaches
- [x] the bias candle closed directionally
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
- [ ] a higher-timeframe POI was in play (`bias_poi_present`)
- [ ] bias candle numbering fits (C2/C3) (`bias_candle_index_ok`)
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

- [[2026-10-14__ttfm]]
- [[TTRADES/concepts/entry-models|entry-models]]
- [[TTRADES/concepts/cisd|cisd]]
- [[TTRADES/concepts/candle-closures|candle-closures]]
- [[TTRADES/concepts/smt-and-psp|smt-and-psp]]
