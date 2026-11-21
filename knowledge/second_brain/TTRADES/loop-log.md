---
title: "TTRADES: improvement loop log"
type: ttrades-loop-log
created: 2026-11-21
last_updated: 2026-11-21
---

# Improvement loop log

One entry per turn of the loop in [[ttrades-index]] ("The improvement loop"): one change, scored on
a fixed card, kept only when the **train** score improves, logged whether kept or not. The card is
`python -m companion.tools.ttfm_score` (rules in its docstring, fixed 2026-11-21 before any result
was scored):

- **edge**: t-statistic of the weekly R; 10 at t >= 3.
- **robustness**: share of years and of symbols with a positive total.
- **drawdown**: R per year over the max drawdown; 10 at >= 2.
- **teacher**: share of the teacher's own live trades (weekday New York sessions, 2026 only) the
  engine also took, same trading day, symbol and direction. Test period only, so it never steers a
  train choice.
- **coverage**: share of the [[engine-gaps]] rows whose switch has been tested.

Score = mean of the parts per period. **Ready to trade** = out-of-sample score (the worse of validate
2025 and test 2026) >= 8 **and** out-of-sample edge >= 7. Data: TradingView 5m, NQ ES YM RTY GC SI CL
6E, 2021-11-14 to 2026-11-13, costs included, no slippage, one position per symbol and stack, 2R target.

**Keep rule** (amended after turn 10, before anything was kept): the card's edge part is 0 for every
losing variant, so the card cannot rank one loser against another. A turn is kept when the paired
weekly-R difference on train (turn minus the current state, week by week) has t >= 1
(`ttfm_score --compare`). Validate and test differences are reported, never used to choose. The card
stays the readiness grade.

The latest kept turn is the current engine state; its line in the summary table is the headline.

## Summary

Turns 1-10 ran on the 1D/4h/15m and 1W/1D/1h stacks against the baseline on the same stacks, with
no trade cap and with one trade a day across the portfolio (PSY-1). Score = card score train /
validate / test (no cap). Δ = paired mean R/week difference against the baseline (t in brackets).

| Turn | Change (variant) | Card train / val / test | Δ train, no cap | Δ train, 1/day | Δ validate / test, no cap | Δ validate / test, 1/day | Kept | Teacher (test) | Ready |
|---|---|---|---|---|---|---|---|---|---|
| 0 | baseline, all three stacks | 2.1 / 3.9 / 4.5 | — | — | — | — | state | 4/13 | no |
| 0b | baseline, 4h + W stacks | 2.7 / 9.0 / 4.3 | — | — | — | — | state | 0/13 | no |
| 1 | enter on the next continuation, CISD-19 (`next_continuation`) | 2.7 / 8.5 / 4.5 | +0.087 (0.77) | +0.122 (1.22) | -0.237 / -0.018 | -0.009 / -0.061 | 1/day only; fails out of sample | 0/13 | no |
| 2 | EQ close is a soft invalidation (`eq_soft`) | 2.4 / 8.8 / 4.0 | -0.075 (-1.53) | -0.034 (-0.56) | +0.127 / -0.096 | +0.072 / -0.029 | no | 1/13 | no |
| 3 | daily-profile veto (`profile_veto`) | 2.9 / 8.6 / 4.1 | +0.020 (0.26) | +0.034 (0.46) | -0.292 / -0.057 | -0.206 / +0.048 | no | 0/13 | no |
| 4 | no reversals, ENT-6 (`no_reversals`) | 2.7 / 6.8 / 1.7 | +0.010 (0.06) | +0.064 (0.53) | -0.930 / -0.390 | -0.327 / -0.065 | no | 1/13 | no |
| 5 | kill zone 08:00-10:30 (`ny_window`) | 3.0 / 8.8 / 4.1 | +0.045 (0.26) | +0.091 (0.63) | -0.312 / -0.117 | +0.313 / +0.415 | no (out-of-sample gain with 1/day, but not chosen on train) | 0/13 | no |
| 6 | enter on the CISD only (`cont_cisd_entry`) | 2.6 / 8.8 / 4.2 | -0.018 (-0.31) | -0.060 (-1.12) | -0.150 / -0.013 | -0.084 / +0.004 | no | 0/13 | no |
| 7 | stop under 4% of ADR waits (`stop_gate`) | 2.9 / 8.8 / 4.6 | +0.038 (1.71) | +0.042 (1.34) | +0.030 / +0.025 | -0.014 / +0.003 | **yes** | 0/13 | no |
| 8 | protected swing breaks on a close (`swing_close_break`) | 2.7 / 9.0 / 4.0 | +0.005 (0.16) | +0.012 (1.00) | +0.000 / -0.022 | 0 / 0 | no (no effect) | 0/13 | no |
| 9 | skip Candle 4 after a double expansion, C4c (`no_double_expansion_c4`) | 2.6 / 9.0 / 4.7 | +0.070 (0.92) | +0.079 (1.17) | +0.038 / +0.054 | +0.008 / +0.004 | **yes** (1/day) | 0/13 | no |
| 10 | trade only the setup that made the wick, T1 (`wick_setup`) | 2.7 / 8.7 / 5.0 | +0.100 (2.85) | +0.091 (2.37) | -0.092 / +0.065 | +0.077 / +0.045 | **yes** | 0/13 | no |

| 11 | turns 7 + 9 + 10 together (`loop1`) | **3.2** / 9.0 / 5.5 | +0.174 (2.03) | +0.195 (2.29) | +0.023 / +0.119 | +0.125 / +0.049 | **yes: new state** | 0/13 | no |
| 11b | `loop1` + kill zone 08:00-10:30 (`loop1_ny`) | 3.0 / 8.8 / 4.3 | +0.034 (0.19) | +0.074 (0.52) | -0.421 / -0.094 | +0.221 / +0.437 | no | 0/13 | no |

Turn 11 is the first combination: the three kept switches beat the baseline on train under both
caps and in both out-of-sample years. Its train card (3.2) is the best so far, but the train edge is
still t 0.43: the state is better, not yet an edge.

Turn 12 (4H alignment, `htf_align_role` = quality; FM-12 / BIAS-23). Screened first on the
baseline's own trades (keep only trades whose last closed 4H candle closed their way without a
rejection wick): on 1D/1h/5m, train +0.74 R/wk (t 2.35), 2025 +0.48, 2026 +0.70; on 1D/4h/15m and
1W/1D/1h, train +0.12 (t 1.32), 2025 -0.38, 2026 +0.02. On `loop1`'s 4h + W trades: train t 0.76,
2025 -0.39. So the 4H check is the missing layer on the 1h / 5m stack (his D-1H bias with a lower
entry), and mostly redundant where the setup timeframe is the 4H. Engine runs: `htf_align` and
`loop2` (= `loop1` + the 4H check) on 4h + W, `loop2` on 1D/1h/5m.

| Turn | Change (variant) | Stacks | Card train / val / test | Δ train vs state, no cap | Δ train vs state, 1/day | Δ validate / test, no cap | Δ validate / test, 1/day | Kept | Teacher (test) | Ready |
|---|---|---|---|---|---|---|---|---|---|---|
| 12a | 4H check alone vs baseline (`htf_align`) | 4h+W | 3.7 / 8.7 / 4.8 | +0.185 (1.48) | — | -0.444 / -0.013 | — | superseded by 12b | 0/13 | no |
| 12b | `loop1` + 4H check (`loop2`) vs `loop1` | 4h+W | 5.1 / 8.6 / 6.3 | +0.109 (0.89) | +0.093 (0.88) | -0.513 / +0.070 | -0.238 / +0.433 | **no** (t under 1) | 0/13 | no |
| 12c | `loop2` vs baseline (no `loop1` run on this stack) | 1D/1h/5m | 3.5 / 1.9 / 6.1 | +0.738 (2.05) | +0.523 (2.15) | +0.715 / +0.469 | +0.034 / +0.226 | **yes** | 2/13 | no |

**State after turn 12**: `loop1` on 1D/4h/15m and 1W/1D/1h, `loop2` (= `loop1` + the 4H check) on
1D/1h/5m. The 4H check is kept where the setup timeframe is below the 4H and not where it is the
4H, which is how the teacher pairs them (D-1H bias, the 4H between bias and a lower entry). Against
the baseline on all three stacks: train +0.91 R/wk (t 2.40), 2025 +0.74, 2026 +0.59.

| State | Cap | Card train / val / test | Mean R/wk train / val / test | Trades/wk | Max DD (R) train / val / test | Teacher (test) | OOS score, edge | Ready |
|---|---|---|---|---|---|---|---|---|
| baseline, all stacks | none | 2.2 / 4.0 / 4.6 | -0.74 / +0.12 / +0.34 | 14.5 | -150 / -34 / -28 | 4/13 | 4.0, 0.6 | no |
| after turn 12 | none | **4.5 / 8.0 / 6.7** | +0.17 / +0.86 / +0.93 | 5.5 | -32 / -16 / -15 | 2/13 | 6.7, 4.9 | no |
| after turn 12 | 1/day | 2.7 / 6.9 / 6.3 | -0.09 / +0.51 / +0.56 | 3.0 | -34 / -20 / -8 | 1/13 | 6.3, 4.9 | no |
| `loop2` on all stacks (not chosen: train t 0.89 on 4h+W) | none | 5.1 / 5.7 / 6.6 | +0.28 / +0.35 / +1.00 | 4.5 | -39 / -21 / -15 | 2/13 | 5.7, 2.9 | no |

Grade after turn 12: **6.7 / 10** out of sample (edge 4.9 / 10). Not ready to trade: the train edge
is t 0.67, the out-of-sample edges t 1.87 (2025) and 1.48 (2026), and the engine agrees with only 2
of the teacher's 13 own trades in 2026. Next turns, by expected gain: teacher agreement (why it misses
his NQ / ES shorts: bias CISD on the paired timeframe, the forming-wick check), then SMT for
reversals. Each turn now costs 1-2 hours of grid time; the harness speed-up (next PR) is what makes
more turns cheap.
