---
title: "Trade Review - NQ TTFM continuation long 20:00"
date: 2026-10-26
time: "20:00"
type: trade
strategy: ttfm
model: TTFM 1D / 1h / 5m
stack: 1D / 1h / 5m
symbol: NQ
source: backtest baseline
session: asia
weekday: Mon
direction: long
path: continuation
stage: c4
trigger_kind: cisd
bias: bullish
entry: 29536.75
stop: 29412.25
risk: 124.5
target_r: 2.0
result_r: -1.004
r_1: -1.004
r_2: -1.004
r_3: -1.004
r_bias_close: -1.004
mfe_r: 0.424
mae_r: 0.974
outcome: loss
criteria_failed: ["cont_reward_at_least_2r", "session_filter_ok"]
status: draft
confidence: unknown
verdict: ??
source_count: 1
journal: "[[2026-10-26__ttfm]]"
---

# NQ TTFM continuation long Mon 26 Oct 20:00

> [!info] Journaled automatically, not a live fill
> The companion's own rules replayed on TradingView bars (`results/backtest_tv/2026/baseline/NQ_1D-1h-5m.jsonl.gz`). Fill at the trigger candle's close; R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins. Fill the blanks marked `??` and set `status: reviewed`.

## Quick log

- **Model:** TTFM 1D / 1h / 5m, continuation at c4, trigger cisd; bias bullish; asia session, Mon
- **Entry:** 29,536.75 at 20:00 (long)
- **Stop:** 29,412.25 (risk 124.50 points, 22% of ADR14)
- **Target:** 2R; structural target 29,787.25
- **Result:** -1.00 R (loss); ladder 1R -1.00, 2R -1.00, 3R -1.00, held to the bias close -1.00
- **Excursion:** best +0.42 R, worst -0.97 R; stopped after 190 min

## Thesis

1D bias is bullish (Candle 4 forming), the 1h pulled back to a point of interest, respected the previous 1D candle's equilibrium 29,298.12 and closed back up, and the 5m confirmed the turn. The trigger closed outside the kill zones (information only).

## Checklist (the engine's criteria)

- [x] enough bars loaded
- [x] the timeframe pairing is one he teaches
- [x] the bias candle closed directionally
- [x] a higher-timeframe POI was in play
- [x] CISD confirmed the bias
- [x] bias candle numbering fits (C2/C3)
- [x] the bias swing held
- [x] the objective was still open
- [x] candle 2 had not already expanded
- [x] EQ was respected
- [x] price tagged the POI
- [x] the candle opened against the bias first (wick formed)
- [x] the setup candle closed (C2 closure)
- [x] the setup closure's body is with the bias
- [x] entry CISD confirmed
- [x] the entry CISD was swift
- [x] the entry window was open
- [x] an entry trigger printed
- [x] the protected swing held
- [x] the trigger was clear of opposing liquidity
- [x] the trigger was V-shaped
- [x] not inside a consolidation
- [x] the objective was still open at the trigger
- [x] the entry came early in the candle
- [ ] reward at least 2R (`cont_reward_at_least_2r`)
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

- For a continuation day, anchor a 50% fib on the previous daily candle from its close to its opposing extreme (low if bullish, high if bearish); the new day's low (bull) / high (bear) should form beyond that 50% in the trade direction. ([[TTRADES/sources/a_simple_3_step_trading_model_full_breakdown|a_simple_3_step_trading_model_full_breakdown]] 15:12)
- A run through the 50% invalidation makes a large wick / potential failure swing and makes the continuation day uninteresting. ([[TTRADES/sources/a_simple_3_step_trading_model_full_breakdown|a_simple_3_step_trading_model_full_breakdown]] 15:47)
- If a continuation forms and its protected swing is then taken, the trend is weak / consolidating. ([[TTRADES/sources/cisd_validates_swing_points|cisd_validates_swing_points]] 7:34)

## Linked

- [[2026-10-26__ttfm]]
- [[TTRADES/concepts/entry-models|entry-models]]
- [[TTRADES/concepts/swings-and-structure|swings-and-structure]]
- [[TTRADES/concepts/candle-closures|candle-closures]]
- [[TTRADES/concepts/ranges-and-eq|ranges-and-eq]]
