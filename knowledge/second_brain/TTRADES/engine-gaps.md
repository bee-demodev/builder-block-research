---
title: "TTRADES: where the companion engine differs from the teacher"
type: ttrades-engine-gaps
created: 2026-11-21
last_updated: 2026-11-21
---

# Where the engine differs from the teacher

Research for the 5-year backtest (2026-11-21). Each gap gives the teacher's rule with a
transcript-checked citation (`--quote <slug> mm:ss` ran on every one; `@mm:ss` is where the words
actually sit when the brain's stamp is off), where the engine differs (file:line on branch
`ttfm-5y-backtest`), and the switch that would close it. Status: **tested** = a backtest variant
exists and its result is in [[evidence]]; **built** = the switch exists but has not been run;
**open** = no switch yet. Three voices stay apart: the teacher's words, Vik's decisions
([[decisions]]), and this page's inference (marked "my reading" or "my number").

Every switch defaults to the engine's current behaviour. None becomes a default without Vik
(proposed rows in [[decisions]]).

## Bias and the higher timeframe

| Gap | Teacher (verified) | Engine | Switch | Status |
|---|---|---|---|---|
| No check that the 4H candle supports expansion (FM-12, BIAS-23) | "you're trading against the 4-hour candle, which is a lot harder" (livestream_20260310 04:25-06:08); "when true expansion occurs, it's when these timeframes are kind of all aligned together" (livestream_20260313 1:09:08) | bias reads only the last closed bias candle (bias.py:115-160); no 4H read on 1D/1h/5m | `htf_align_tf` null / "4h" + role; my number: reuse `closed_wick_large_frac` 0.5 | open |
| Bias CISD read on the setup timeframe, not his paired one | "if I'm on the daily, I'm going to use the hourly for a change in the state of delivery" (candle_2_closure_foundation 09:10) | `_swing_cisd` uses the setup frame (bias.py:100-112): on 1D/4h/15m that is a 4H CISD | `bias_cisd_tf` "setup" / "paired" | open |
| Every closure needs a POI (BIAS-4 / POI-1) | "I need a point of interest to frame a candle closure" (candle_2_closure_foundation 06:09) vs 2026 bias from the close alone (the_only_trading_strategy_you_need_for_2026 00:57) | `bias_poi_present` is a gate (continuation.py:477-494) | `bias_poi_role` gate / advisory | open |
| Candle 4 after C2 and C3 both expanded (C4c) | "When to avoid trading candle 4? Well, generally when candle 2 and candle 3 both expand." (livestream_20260317_new_york_open_live_q_a_00izxpadr5a 50:05) | Candle 4 traded like Candle 3 | `c4_after_double_expansion` trade / skip (proposed TD-008) | tested |

## Timeframe pairing

| Gap | Teacher (verified) | Engine | Switch | Status |
|---|---|---|---|---|
| 2026 default is D-H1 bias, 4H-15m execution | "best off with using daily and hourly fractal for bias and then using the H4 and 15 model ... a lot of people go to too low of timeframes and you get chopped up" (livestream_20260721 09:12) | one fixed stack per run; 1D/1h/5m is the app default | stack choice (run selection), proposed TD-007 | tested (per stack in [[evidence]]) |
| No 5m before the open | "pre-open, right, I'm not going below a 15-minute chart" (livestream_20260721 44:23) | 5m triggers at any hour | post-run screen: 1D/4h/15m before 09:30, 1D/1h/5m after | tested (screen) |
| No weekly bias in 2026 (FM-3, BIAS-15) | "I don't have a weekly bias" (livestream_20260325 78:12) | 1W/1D/1h is one of the run stacks | stack choice | tested |

## Protected swings

| Gap | Teacher (verified) | Engine | Switch | Status |
|---|---|---|---|---|
| A wick through the swing kills the bias (SW-1) | close-based reading at livestream_20260610 1:02:54 is about a level, not clearly a protected swing (partial) | `protected_swing_break_on` = "wick" (primitives.py:201-207) | existing key, value "close" (variant `swing_close_break`) | tested |
| No relevance / failure-swing filter (SW-2, LIQ-2) | "I don't have a mechanical reason to say, hey, this is valid separation" (which_swing_highs_and_lows_matter_in_trading 12:21) | any untaken 3-bar swing is a POI (primitives.py:379-386) | `relevant_swing_sep_frac`; my number 0.25 avg range | open |

## Candle 2 / 3 / 4 execution

| Gap | Teacher (verified) | Engine | Switch | Status |
|---|---|---|---|---|
| The latest setup is traded, not the one that formed the wick (T1) | "you really only have one change in the state of delivery per day. That forms the daily wick." (livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq rule 5, @16:24) | `max(intact, key=closing)` (continuation.py, setup pick) | `cont_setup_pick` latest / wick_extreme (proposed TD-009) | tested |
| Enter on the CISD vs the next continuation (CISD-19) | "we're not going to enter on that change in the state of delivery. We're going to wait for another continuation" (the_only_trading_strategy_you_need_for_2026 02:46) | `entry_mode_continuation` "either" (question 14) | existing key: "conservative" (variant `next_continuation`) / "aggressive" (`cont_cisd_entry`) | tested |
| Forming candle has already spent its time or range (T3, T4) | "if this is already expanded ... why would I really care" (livestream_20260610 @56:03) | continuation never classifies the forming wick | `cont_forming_wick_role`; my number 0.5 | open |
| 4H setup closure at any hour (T2) | "a candle 2 closure during London ... anticipate 6 a.m. and 10:00 a.m. to expand higher" (the_best_timeframe_for_ttrades_fractal_model_simple 01:42) | no time rule on the setup closure | screen on trigger hour | tested (screen, no stable effect) |

## Sessions, SMT and news

| Gap | Teacher (verified) | Engine | Switch | Status |
|---|---|---|---|---|
| Window about 08:00-10:30 New York (SES-1) | "I just like to capture the move from 8 normally to 10-ish ... Sometimes 10.30" (livestream_20260728 @36:35) | kill zones 02:00-05:00 and 08:30-11:00, advisory (question 18); only for entry timeframes under 60m | existing keys (variant `ny_window`) | tested |
| Kill zones do not matter once the HTF wick formed (SES-12) | "I'm not going to wait for the kill zone if price forms its wick" (livestream_20260916 42:00) | — | conflict with SES-1 stays open | — |
| No New York PM | "I don't look at New York PM session ever." (livestream_20260506 @1:44:08) | PM triggers taken | screen | tested (screen, no effect) |
| SMT needed for reversals, not continuations | "If you're trading a reversal, Sure, require it. If I'm trading a continuation ... I don't require it." (livestream_20261103 1:09:50) | no SMT; one symbol per evaluation (rules.md question 23) | `smt_role` off / reversal_required; pairs NQ:[ES,YM], GC:[SI] | open |
| One index at a time, the strongest / weakest by the hourly close | "previous hourly candle close versus this one ... YM is clearly weaker" (livestream_20260428 @1:04:47) | NQ, ES and YM all trade the same idea | `index_selection`; screen keeps the first fill per day and direction | tested (screen) |
| No trade right before CPI / NFP / FOMC; trade the day after FOMC | "FOMC, NFP, CPI. Don't trade right before it." (livestream_20260910 18:40); "I'd like to trade the day after FOMC" (livestream_20261028 @28:17) | no news calendar in the repo before this work | `no_fomc_day` screen (FOMC dates from the Fed calendar in companion/tools/weekly_r.py); CPI / NFP need a dated list | tested (FOMC screen) |
| Mondays only after a Friday reversal | "The only time I'll look to trade Mondays is when we have a reversal day on Friday." (livestream_20260803 @12:37) | Mondays traded | `monday_rule`; needs daily bars | open |
| One trade a day (PSY-1) | "Best way to go about that is max one trade a day" (livestream_20261110 17:44) | engine is stateless | harness option `--max-per-day 1` (proposed TD-006) | tested |

## Citations in the brain that did not hold up

Checked with `--quote` on 2026-11-21; do not rely on these:

- `livestream_20260617 1:02:10`: about options, not "C2/C3 + H1 CISD".
- `livestream_20260726 1:26:20`: about the daily open, not "15m before 9:30".
- `livestream_20261110 16:55`: about swing trading D/H1, not "fighting every timeframe".
- `livestream_20260902 38:00`: does not support BIAS-23 side A.
- `livestream_20260310 18:40` (kill zones): the words sit elsewhere in that stream.
- `livestream_20260617 26:50` (FOMC chop): unverified.
- `livestream_20260311 47:20` ("RTY is its own asset"): unverified.
- method-map stamps livestream_20260401 1:36:40, 1:08:20 and livestream_20260722 20:50 do not say what is claimed.

## What next (the loop)

Each open row is a candidate for the next turn of the loop: add the switch (default unchanged),
run it on train, then validate and test, and file the result in [[evidence]]. Order by expected
impact: 4H alignment, bias CISD on the paired timeframe, forming-wick check, SMT for reversals.
