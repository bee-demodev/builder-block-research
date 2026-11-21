---
title: "Trade Review - NQ TTFM continuation long 22:45"
date: 2026-10-19
time: "22:45"
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
trigger_kind: order_block
bias: bullish
entry: 29730.75
stop: 29711.25
risk: 19.5
target_r: 2.0
result_r: 1.988
r_1: 0.988
r_2: 1.988
r_3: -1.024
r_bias_close: -1.024
mfe_r: 2.769
mae_r: 0.103
outcome: win
criteria_failed: ["bias_c2_not_expanded", "cont_opened_against_bias_first", "session_filter_ok"]
status: draft
confidence: unknown
verdict: ??
source_count: 1
journal: "[[2026-10-19__ttfm]]"
---

# NQ TTFM continuation long Mon 19 Oct 22:45

> [!info] Journaled automatically, not a live fill
> The companion's own rules replayed on TradingView bars (`results/backtest_tv/2026/baseline/NQ_1D-1h-5m.jsonl.gz`). Fill at the trigger candle's close; R includes the backtest's cost model but no slippage; when one candle spans stop and target the stop wins. Fill the blanks marked `??` and set `status: reviewed`.

## Quick log

- **Model:** TTFM 1D / 1h / 5m, continuation at c4, trigger order_block; bias bullish; asia session, Mon
- **Entry:** 29,730.75 at 22:45 (long)
- **Stop:** 29,711.25 (risk 19.50 points, 4% of ADR14)
- **Target:** 2R; structural target 29,771.25
- **Result:** +1.99 R (win); ladder 1R +0.99, 2R +1.99, 3R -1.02, held to the bias close -1.02
- **Excursion:** best +2.77 R, worst -0.10 R; stopped after 70 min

## Thesis

1D bias is bullish (Candle 3 forming), the 1h pulled back to a point of interest, respected the previous 1D candle's equilibrium 29,604.75 and closed back up, and the 5m confirmed the turn. The trigger closed outside the kill zones (information only). The bias Candle 2 expanded, so the entry had to be a continuation order block.

## Checklist (the engine's criteria)

- [x] enough bars loaded
- [x] the timeframe pairing is one he teaches
- [x] the bias candle closed directionally
- [x] a higher-timeframe POI was in play
- [x] CISD confirmed the bias
- [x] bias candle numbering fits (C2/C3)
- [x] the bias swing held
- [x] the objective was still open
- [x] EQ was respected
- [x] price tagged the POI
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
- [x] reward at least 2R
- [ ] candle 2 had not already expanded (`bias_c2_not_expanded`)
- [ ] the candle opened against the bias first (wick formed) (`cont_opened_against_bias_first`)
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

- [[2026-10-19__ttfm]]
- [[TTRADES/concepts/entry-models|entry-models]]
- [[TTRADES/concepts/swings-and-structure|swings-and-structure]]
- [[TTRADES/concepts/candle-closures|candle-closures]]
- [[TTRADES/concepts/ranges-and-eq|ranges-and-eq]]
