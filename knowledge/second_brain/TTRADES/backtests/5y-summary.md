---
title: "TTFM 5-year backtest and walk-forward tuning (2021-11 to 2026-11)"
type: ttrades-backtest-report
created: 2026-11-21
---

# TTFM 5-year backtest: R per week, walk-forward tuning, the 5 R/week target

The companion's TTrades engine (`companion/styles/ttrades/`) through the bar-by-bar harness
(`companion/tools/backtest.py grid`) on the TradingView 5m front-month stitch: NQ ES YM RTY GC SI CL
6E, 2021-11-14 to 2026-11-13, stacks 1D/1h/5m, 1D/4h/15m and 1W/1D/1h. Costs as the harness models
them, no slippage. Trades taken as a trader would: one position at a time per symbol and stack, 2R
target, an open trade held to the 10-day horizon (`companion/tools/weekly_r.py`). R per week counts
every Monday-Sunday week (trading days, 18:00 New York roll), so an idle week is 0 R.

Walk-forward: **train** 2021-11-15 to 2024-12-31 (164 weeks, choose here), **validate** 2025 (53
weeks, confirm), **test** 2026-01-01 to 2026-11-13 (46 weeks, forward test). 2022-2026 had been
looked at in earlier runs (`results/backtest_tv`, `results/backtest_tv_holdout`), so validate and
test are not virgin data; the walk-forward guards against tuning on them, not against that history.

Raw runs: `results/backtest_tv_5y/<year>/<variant>/` in the main checkout (untracked). Registered:
`tv-5y-baseline`, `tv-5y-loop1`. Per-rule evidence: [[evidence]]; loop turns and readiness scores:
[[loop-log]]; engine-vs-teacher gaps: [[engine-gaps]].

## 1. Baseline (the engine's defaults)

All three stacks, no trade cap.

| Period | Weeks | Trades | /week | R/trade | Win % | Total R | Mean R/wk | Median | Weeks >= 5R | Worst wk | Max DD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 164 | 2402 | 14.65 | -0.051 | 34% | -121.5 | -0.74 | -1.20 | 16.5% | -14.4 | -149.8 |
| validate | 53 | 697 | 13.15 | +0.009 | 36% | +6.5 | +0.12 | -0.22 | 20.8% | -12.5 | -34.3 |
| test | 46 | 675 | 14.67 | +0.023 | 36% | +15.6 | +0.34 | +0.24 | 23.9% | -12.5 | -28.4 |
| all | 261 | 3774 | 14.46 | -0.026 | 34% | -99.4 | -0.38 | -0.65 | 18.8% | -14.4 | -149.8 |

"Weeks >= 5R" is not a sign of an edge here: with 14 trades a week at about 35% wins, weekly R
swings from -14 to +15, so a fifth of the weeks clear 5 R while the mean is negative.

Per year:

| Year | Weeks | Trades | /week | R/trade | Total R | Mean R/wk | Median | Weeks >= 5R | Worst wk | Max DD |
|---|---|---|---|---|---|---|---|---|---|---|
| 2021 (from 11-15) | 7 | 84 | 12.00 | -0.032 | -2.7 | -0.38 | -0.46 | 14.3% | -6.7 | -12.4 |
| 2022 | 53 | 727 | 13.72 | -0.031 | -22.2 | -0.42 | -0.30 | 11.3% | -9.2 | -60.8 |
| 2023 | 53 | 797 | 15.04 | -0.099 | -78.7 | -1.49 | -2.20 | 18.9% | -12.7 | -82.7 |
| 2024 | 53 | 794 | 14.98 | -0.023 | -17.9 | -0.34 | -1.25 | 18.9% | -14.4 | -50.1 |
| 2025 | 53 | 697 | 13.15 | +0.009 | +6.5 | +0.12 | -0.22 | 20.8% | -12.5 | -34.3 |
| 2026 (to 11-13) | 46 | 675 | 14.67 | +0.023 | +15.6 | +0.34 | +0.24 | 23.9% | -12.5 | -28.4 |

Per stack (whole 5 years):

| Stack | Trades | /week | R/trade | Win % | Total R | Mean R/wk | Max DD |
|---|---|---|---|---|---|---|---|
| 1D / 1h / 5m | 2856 | 10.94 | -0.056 | 33% | -159.0 | -0.61 | -173.8 |
| 1D / 4h / 15m | 811 | 3.11 | +0.063 | 37% | +50.8 | +0.19 | -39.3 |
| 1W / 1D / 1h | 107 | 0.41 | +0.082 | 48% | +8.8 | +0.03 | -13.0 |

Per symbol (whole 5 years):

| Symbol | Trades | R/trade | Total R | Max DD |
|---|---|---|---|---|
| 6E | 428 | -0.058 | -24.8 | -40.7 |
| CL | 456 | +0.018 | +8.0 | -36.4 |
| ES | 504 | -0.145 | -72.9 | -89.6 |
| GC | 430 | +0.065 | +28.1 | -24.4 |
| NQ | 468 | +0.002 | +1.1 | -36.9 |
| RTY | 521 | +0.029 | +15.0 | -26.9 |
| SI | 472 | +0.017 | +8.0 | -42.5 |
| YM | 495 | -0.125 | -61.8 | -78.0 |

What the baseline rows say (screens over its own trades, R per trade train / validate / test):

- Continuation trades lose (-0.109 / -0.045 / -0.021); reversals do not (+0.002 / +0.051 / +0.054).
- Continuations triggered on the order block lose in every period (-0.266 / -0.189 / -0.122); on the
  CISD they do not (+0.011 / +0.096 / +0.059).
- Stops under 4% of the ADR lose in every period (-0.494 / -0.297 / -0.444, continuation): costs.
- Continuations outside the kill zones lose (-0.178 / -0.162 / -0.067); Asia continuations most.

<!-- sections 2-5 are written when loop turn 11 is in -->
