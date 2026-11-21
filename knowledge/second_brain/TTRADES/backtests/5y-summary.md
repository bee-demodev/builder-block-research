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
`tv-5y-baseline`, `tv-5y-loop1`, `tv-5y-loop2`. Per-rule evidence: [[evidence]]; loop turns and readiness scores:
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

## 2. Baseline vs best, R per week

"Best" is the state the loop reached after turn 12, chosen on train only ([[loop-log]]):
`loop1` on 1D/4h/15m and 1W/1D/1h, `loop2` on 1D/1h/5m. `loop1` = `cont_setup_pick` wick_extreme
(TD-009) + `c4_after_double_expansion` skip (TD-008) + `stop_size_role` quality (TD-011); `loop2` adds
`htf_align_role` quality (TD-010). None of these is the engine default (all proposed, Vik decides).

| Period | Baseline mean R/wk | Best mean R/wk | Best median | Best weeks >= 5R | Best worst wk | Best max DD | Baseline trades/wk | Best trades/wk | Best R/trade |
|---|---|---|---|---|---|---|---|---|---|
| train 2021-11 to 2024 | -0.74 | **+0.17** | -0.07 | 6.7% | -6.5 | -31.6 | 14.65 | 5.33 | +0.032 |
| validate 2025 | +0.12 | **+0.86** | +0.96 | 7.5% | -6.1 | -16.0 | 13.15 | 5.13 | +0.168 |
| test 2026 | +0.34 | **+0.93** | +1.29 | 21.7% | -8.1 | -15.0 | 14.67 | 6.22 | +0.149 |
| all 5 years | -0.38 | +0.45 | +0.00 | 9.6% | -8.1 | -31.6 | 14.46 | 5.49 | +0.081 |

With one trade a day across the portfolio (PSY-1): best -0.09 / +0.51 / +0.56 R/wk (3 trades a
week, max DD -34 / -20 / -8), baseline -0.66 / +0.28 / +0.45.

Paired against the baseline, week by week: train +0.91 R/wk (t 2.40), 2025 +0.74 (t 1.22), 2026
+0.59 (t 1.01). Readiness card ([[loop-log]]): 4.5 / 8.0 / 6.7, out-of-sample score 6.7 and edge
4.9 out of 10: **not ready to trade** by the bar fixed before the loop (>= 8 and edge >= 7).

Best, per year (no cap):

| Year | Trades | /week | R/trade | Total R | Mean R/wk | Median | Worst wk | Max DD |
|---|---|---|---|---|---|---|---|---|
| 2021 (from 11-15) | 32 | 4.57 | +0.023 | +0.7 | +0.10 | -0.07 | -6.1 | -7.2 |
| 2022 | 275 | 5.19 | +0.066 | +18.2 | +0.34 | +0.00 | -6.4 | -19.8 |
| 2023 | 308 | 5.81 | -0.029 | -8.9 | -0.17 | -0.20 | -6.5 | -28.8 |
| 2024 | 259 | 4.89 | +0.070 | +18.1 | +0.34 | +0.00 | -6.2 | -23.6 |
| 2025 | 272 | 5.13 | +0.168 | +45.6 | +0.86 | +0.96 | -6.1 | -16.0 |
| 2026 (to 11-13) | 286 | 6.22 | +0.149 | +42.7 | +0.93 | +1.29 | -8.1 | -15.0 |

Best, per stack and per symbol (5 years, no cap):

| Stack | Trades | R/trade | Total R | Max DD |
|---|---|---|---|---|
| 1D / 1h / 5m (`loop2`) | 640 | +0.034 | +21.5 | -27.1 |
| 1D / 4h / 15m (`loop1`) | 694 | +0.132 | +91.9 | -23.6 |
| 1W / 1D / 1h (`loop1`) | 98 | +0.031 | +3.0 | -14.7 |

| Symbol | 6E | CL | ES | GC | NQ | RTY | SI | YM |
|---|---|---|---|---|---|---|---|---|
| Trades | 148 | 171 | 193 | 184 | 172 | 200 | 182 | 182 |
| R/trade | +0.072 | +0.124 | -0.155 | +0.141 | +0.083 | +0.226 | +0.192 | -0.032 |
| Total R | +10.6 | +21.2 | -30.0 | +25.9 | +14.3 | +45.2 | +35.0 | -5.8 |

ES (and YM) still lose; the teacher's own answer is to trade one index, the strongest or weakest
(livestream_20260428 1:04:47), which the engine cannot do yet (SMT / index strength, [[engine-gaps]]).

## 3. Every variant tried

Mean R per week, variant (baseline on the same stacks and cap). Full rows with citations: [[evidence]];
paired differences and keep decisions: [[loop-log]].

| Variant | Rule | Stacks | Train | Validate | Test | Outcome |
|---|---|---|---|---|---|---|
| next_continuation | CISD-19 | 4h+W | -0.01 (-0.10) | +0.91 (+1.15) | +0.30 (+0.32) | fails out of sample |
| eq_soft | BIAS-1 / RNG-3 | 4h+W | -0.17 (-0.10) | +1.28 (+1.15) | +0.22 (+0.32) | fails on train |
| profile_veto | BIAS-9 / PROF-1 | 4h+W | -0.08 (-0.10) | +0.86 (+1.15) | +0.26 (+0.32) | fails out of sample |
| no_reversals | ENT-6 | 4h+W | -0.09 (-0.10) | +0.22 (+1.15) | -0.07 (+0.32) | fails out of sample |
| ny_window | SES-1 | 4h+W | -0.05 (-0.10) | +0.84 (+1.15) | +0.20 (+0.32) | fails out of sample (passes with one trade a day, not chosen on train) |
| cont_cisd_entry | question 14 | 4h+W | -0.11 (-0.10) | +1.00 (+1.15) | +0.30 (+0.32) | fails on train |
| stop_gate | question 38 | 4h+W | -0.06 (-0.10) | +1.18 (+1.15) | +0.34 (+0.32) | kept |
| swing_close_break | SW-1 | 4h+W | -0.09 (-0.10) | +1.15 (+1.15) | +0.29 (+0.32) | no effect |
| no_double_expansion_c4 | C4c | 4h+W | -0.03 (-0.10) | +1.19 (+1.15) | +0.37 (+0.32) | kept |
| wick_setup | T1 | 4h+W | +0.00 (-0.10) | +1.06 (+1.15) | +0.38 (+0.32) | kept (train t 2.85) |
| loop1 | the three kept | 4h+W | +0.08 (-0.10) | +1.17 (+1.15) | +0.44 (+0.32) | kept: state |
| loop1_ny | loop1 + SES-1 | 4h+W | -0.06 (-0.10) | +0.73 (+1.15) | +0.22 (+0.32) | dropped |
| htf_align | FM-12 / BIAS-23 | 4h+W | +0.09 (-0.10) | +0.70 (+1.15) | +0.30 (+0.32) | fails out of sample |
| loop2 | loop1 + 4H check | 4h+W | +0.19 (loop1 +0.08) | +0.66 (+1.17) | +0.50 (+0.44) | dropped on these stacks (train t 0.89) |
| loop2 | loop1 + 4H check | 1D/1h/5m | +0.09 (-0.64) | -0.31 (-1.03) | +0.49 (+0.02) | kept |

Post-run screens on the baseline's trades (no engine change; quicker, approximate): FOMC-day skip,
one index per day, a 5-minute wait after 09:30, no New York PM, Candle 3 only, the 08:00-10:30 and
06:00-11:00 trigger windows, 1R / 1.5R / 3R targets, half off at 1R, hold to the bias close, the
09:30 timeframe hand-over. None improved train and both out-of-sample years; 2R remained the best
target on train.

## 4. The 5 R per week target

**Not reachable honestly with this engine.** The best state makes +0.86 (2025) and +0.93 (2026) R a
week out of sample, +0.17 on train; 5 R a week is 5-6 times the out-of-sample figure and about 30
times the train figure. No configuration tried came within reach, and fitting one to the target
would be fitting noise: the best state's weekly R has a standard deviation of 3.3 R (train,
2025) to 4.3 R (2026), four to twenty times its mean.

What would close the gap, with the numbers:

- **More books.** Out of sample the best state earns about 0.11 R a week per symbol (8 symbols,
  about 0.9 R). At that rate 5 R a week needs about 45 symbols with independent edges. The
  candidates are correlated (NQ / ES / YM / RTY, GC / SI) and ES and YM lose, so adding markets of the
  same kind adds less than that.
- **More trades at the same edge.** At +0.15 R a trade, 5 R a week needs about 33 trades a week; the
  engine takes 5-6. The baseline took 14 a week, but its extra trades were the losing ones.
- **Sizing.** R is the risk unit, so risking 5.5 times as much per trade turns 0.9 R into 5 "old" R a
  week. Drawdowns scale the same way: the out-of-sample max drawdown of 16 R becomes about 88 old R,
  the train drawdown of 32 R about 174 old R, on a train edge of t 0.67. That is leverage on an
  unproven edge, not a better system.
- **A different target.** What the evidence supports today: about +0.5 to +1 R a week out of sample
  (25-50 R a year at 5-6 trades a week), unproven on train. Raising it is the loop's job: the
  biggest open gaps are agreement with the teacher's own trades (2 of his 13 live 2026 trades), the
  bias CISD on the paired timeframe, the forming-wick check and SMT for reversals ([[engine-gaps]]).

## 5. Caveats

- No slippage; the harness's cost model only. Small stops are where costs bite (TD-011).
- One position per symbol and stack, but the three stacks of one symbol can be in the market together.
- 2022-2026 were looked at in earlier runs; the walk-forward guards the choice of switches, not
  the analyst's memory of those years.
- Period boundaries (2025-01-01, 2026-01-01) fall mid-week, so the boundary week is split between the
  two periods it straddles.
- The 5m data is a TradingView front-month stitch; rolls can leave artefacts.
- `tv-5y-*` notes in this folder count every taken trigger (no position holding), so their totals
  differ from the weekly-R tables here.
