---
title: "Trade Review - NQ TTFM reversal short 23:15"
date: 2026-10-26
time: "23:15"
type: trade
strategy: ttfm
model: TTFM 1D / 1h / 5m
stack: 1D / 1h / 5m
symbol: NQ
source: backtest baseline
session: asia
weekday: Mon
direction: short
path: reversal
stage: c4
trigger_kind: cisd
bias: bullish
entry: 29416.5
stop: 29589.5
risk: 173.0
target_r: 2.0
result_r: -1.003
r_1: -1.003
r_2: -1.003
r_3: -1.003
r_bias_close: -1.003
mfe_r: 0.743
mae_r: 0.691
outcome: loss
criteria_failed: ["rev_reward_at_least_2r", "session_filter_ok"]
status: draft
confidence: unknown
verdict: ??
source_count: 1
journal: "[[2026-10-26__ttfm]]"
---

# NQ TTFM reversal short Mon 26 Oct 23:15

> [!info] Journaled automatically, not a live fill
> The companion's own rules replayed on TradingView bars (`results/backtest_tv/2026/baseline/NQ_1D-1h-5m.jsonl.gz`). Fill at the trigger candle's close; R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins. Fill the blanks marked `??` and set `status: reviewed`.

## Quick log

- **Model:** TTFM 1D / 1h / 5m, reversal at c4, trigger cisd; bias bullish; asia session, Mon
- **Entry:** 29,416.50 at 23:15 (short)
- **Stop:** 29,589.50 (risk 173.00 points, 30% of ADR14)
- **Target:** 2R; structural target 29,099.00
- **Result:** -1.00 R (loss); ladder 1R -1.00, 2R -1.00, 3R -1.00, held to the bias close -1.00
- **Excursion:** best +0.74 R, worst -0.69 R; stopped after 450 min

## Thesis

The forming 1D candle turned at a key level (the previous 1D candle's high 29,572.00), the 1h closed back below it, and the 5m confirmed the turn. The trigger closed outside the kill zones (information only).

## Checklist (the engine's criteria)

- [x] enough bars loaded
- [x] the timeframe pairing is one he teaches
- [x] the bias candle closed directionally
- [x] a higher-timeframe POI was in play
- [x] CISD confirmed the bias
- [x] bias candle numbering fits (C2/C3)
- [x] the bias swing held
- [x] candle 2 had not already expanded
- [x] a key level was reached
- [x] price expanded into the level
- [x] the opposing run was small
- [x] the reversal formed early in the candle
- [x] the level was reclaimed
- [x] reversal CISD confirmed
- [x] the reversal CISD was swift
- [x] an entry trigger printed
- [x] the reversal wick held
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

- [[2026-10-26__ttfm]]
- [[TTRADES/concepts/entry-models|entry-models]]
- [[TTRADES/concepts/cisd|cisd]]
- [[TTRADES/concepts/candle-closures|candle-closures]]
- [[TTRADES/concepts/smt-and-psp|smt-and-psp]]
