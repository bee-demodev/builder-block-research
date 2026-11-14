# TTrades Phase B backtests: four pre-registered follow-ups

Written 2026-11-14. Pre-registration: [results/backtest_phase_b/PREREGISTERED.md](../results/backtest_phase_b/PREREGISTERED.md)
(commit 0c4f39c, committed before any run). Harness options: commit dd1e6e2 (`companion/tools/backtest.py`, tests in
`tests/companion/test_backtest_harness.py`). Scores: [results/backtest_phase_b/report/summary.md](../results/backtest_phase_b/report/summary.md)
and `test1.csv` … `test4.csv` next to it, produced by [scripts/phase_b_backtests.py](../scripts/phase_b_backtests.py).

Engine: the app's TTrades style at 05209b4 (Phase A in), baseline config. Data: TradingView 5m front-month stitch,
NQ ES GC YM RTY CL SI 6E, 2022-01-01 to 2026-11-13. Fill and costs as in
[ttrades_backtest_findings.md](ttrades_backtest_findings.md) (market at the next bar's open + 1 tick, stop + 1 tick,
$4.50 round turn). Every trigger counted once (first report); no one-position-at-a-time filter.

## Results at a glance

| # | Test | Pre-registered threshold | Result | Verdict |
|---|---|---|---|---|
| 1 | Weekly / monthly stacks, 35-day horizon (all triggers, stop ≥ 10% ADR) | per stack and exit: pooled mean > 0 with t ≥ 2 (symbol × bias-candle clusters), > 0 in ≥ 4 of 5 years (1M: 3 of 4), ≥ 5 of 8 symbols | Best cell 1W/1D/1h `r_bias_close` +0.049 R, t 1.0, 3/5 years. Others −0.079 to +0.023 R, t −1.3 to +0.5 | **FAIL** (6 of 6 cells) |
| 2a | Limit at plan entry, 3 entry bars, taken trades: filled-trade expectancy | > 0 with t ≥ 2, ≥ 4 of 5 years, ≥ 6 of 8 symbols | −0.030 R (n 3,768, t −1.2), 3/5 years, 2/8 symbols | **FAIL** |
| 2b | Limit vs market on the same taken triggers (unfilled = 0 R) | paired mean > 0 with t ≥ 2, ≥ 4 of 5 years | +0.013 R per trigger, t 1.3, 4/5 years | **FAIL** |
| 3 | Taken vs shadow, 1D/4h/15m, stage c4, test years 2024-26 | gap > 0 in each of 2024, 2025, 2026 and pooled t ≥ 2 | 2024 −0.234, 2025 +0.293, 2026 +0.049; pooled +0.036 R, t 0.6 | **FAIL** |
| 4 | Eligibility replay of the 13 quality checks | per check: affected-trigger mean change ≤ 0 with t ≤ −2.9 and ≥ 4 of 5 years ("helps"), mirror for "hurts" | 6 testable checks: mean change −0.121 to +0.206 R per affected trigger, |t| ≤ 1.2; 7 untestable (< 30 affected) | **No check helps or hurts** (0 of 13 pass either bar) |

No test supports an edge, and none was going to be claimed as one without forward data (every year here was seen
before in some form; see the pre-registration).

## Test 1: weekly and monthly stacks with a horizon of at least one bias candle

| Stack | Exit | n | Mean R | t | Years > 0 | Symbols > 0 | By year | Taken (n, mean) |
|---|---|---|---|---|---|---|---|---|
| 1W / 4h / 15m | 2R, 35 d | 4,390 | −0.031 | −1.3 | 1/5 | 3/8 | −0.106 / −0.012 / +0.038 / −0.027 / −0.052 | 518, −0.005 |
| 1W / 4h / 15m | bias close | 4,390 | +0.023 | 0.5 | 2/5 | 6/8 | −0.133 / −0.040 / +0.247 / +0.034 / −0.000 | 518, +0.244 |
| 1W / 1D / 1h | 2R, 35 d | 985 | +0.015 | 0.3 | 4/5 | 5/8 | −0.169 / +0.023 / +0.038 / +0.107 / +0.092 | 103, +0.090 |
| 1W / 1D / 1h | bias close | 985 | +0.049 | 1.0 | 3/5 | 5/8 | −0.078 / +0.019 / +0.087 / +0.227 / −0.022 | 103, −0.041 |
| 1M / 1D / 1h | 2R, 35 d | 538 | −0.022 | −0.4 | 1/4 | 3/8 | 2023-26: +0.059 / −0.093 / −0.049 / −0.020 | 57, +0.446 |
| 1M / 1D / 1h | bias close | 538 | −0.079 | −1.1 | 1/4 | 2/8 | +0.074 / −0.097 / −0.268 / −0.015 | 57, +0.178 |

Years 2022-2026 (1M: 2023-2026). All triggers with displayed stop ≥ 10% of ADR14.

What the longer horizon changed (same triggers, 10 vs 35 days):

| Stack | 2R still open at 10 d → 35 d | Mean 2R 10 d → 35 d | Bias close 10 d → 35 d |
|---|---|---|---|
| 1W / 4h / 15m | 9.7% → 1.7% | −0.036 → −0.031 | +0.023 → +0.023 |
| 1W / 1D / 1h | 35.2% → 9.5% | −0.016 → +0.015 | +0.049 → +0.049 |
| 1M / 1D / 1h | 42.9% → 16.2% | −0.078 → −0.022 | −0.116 → −0.079 |

- The horizon was the problem the council named, and it is fixed: open 2R trades drop to 2-16%, and every
  bias-close exit now resolves (it already did for the weekly stacks: a weekly candle ends within 7 days).
- Resolving the trades moves the means by at most +0.06 R and **no stack becomes positive with any confidence**.
  1W/1D/1h, the best of them, is +0.015 R (2R) / +0.049 R (bias close) with t ≤ 1.
- The taken-only monthly numbers (+0.446 / +0.178 R) rest on 57 trades in four years; they were not scored and
  should not be read as a result.

**For the app:** keep 1W/4h/15m, 1W/1D/1h and 1M/1D/1h marked "not validated" (Phase A, A5). The earlier ranking of
these stacks was not an artefact of the 10-day horizon; with the horizon fixed they are still flat.

## Test 2: a limit order at the plan entry

Primary (taken trades on 1D/1h/5m and 1D/4h/15m, order valid for 3 entry bars, 10-day horizon):

| Window | Fill rate | Filled at the bar open | Filled-trade mean (H2a) | t | Years > 0 | Symbols > 0 | Limit − market per trigger (H2b) | t | Years > 0 |
|---|---|---|---|---|---|---|---|---|---|
| **3 bars (scored)** | 87.2% | 70% | **−0.030** | −1.2 | 3/5 | 2/8 | **+0.013** | 1.3 | 4/5 |
| 1 bar | 83.7% | 73% | −0.019 | −0.7 | 3/5 | 4/8 | +0.024 | 2.2 | 4/5 |
| 12 bars | 92.1% | 67% | −0.034 | −1.4 | 3/5 | 3/8 | +0.009 | 0.9 | 4/5 |

All triggers (taken + shadow), 3 bars: fill rate 77.5%, filled mean −0.062 R (t −6.8, negative in all 5 years and
on all 8 symbols), limit − market +0.002 R.

Why the two entries are so close: the plan's entry price is the trigger bar's close level, and the next bar opens at
a median 0.000 R from it (interquartile −0.017 to +0.029 R). So 61% of the time the order is marketable at once and
fills at that open (no entry tick), and the rest fill when price comes back within the window. The difference
from a market order is (a) one tick saved, and (b) the 13% of trades that never come back. Those are the winners:
the unfilled triggers make **+0.212 R** at market (2R hit rate 38%), the filled ones −0.076 R at market and −0.030 R
with the limit price. That is plain adverse selection: a limit order buys a better price on the trades that work
less often, and misses the ones that leave without it.

The 1-bar window's limit − market difference passes its numbers (+0.024 R, t 2.2, 4/5 years), but it was a
sensitivity row, not the registered window; it is reported, not counted. Per stack (3 bars): 1D/1h/5m limit
−0.034 vs market −0.062 R per trigger; 1D/4h/15m +0.005 vs +0.042 R (the limit is worse there). Weekly / monthly
stacks (35-day horizon, not scored): 1W/4h/15m +0.025 vs −0.001, 1W/1D/1h +0.129 vs +0.099, 1M/1D/1h +0.286 vs
+0.350 (n 63-620).

**For the app:** nothing to change. The plan entry is close enough to the market at the report that the order type
moves expectancy by about one tick; neither entry is positive with any confidence. If the app ever offers a
limit-entry option, the cost of it (missed winners) should be shown next to the saved tick.

## Test 3: taken vs shadow on 1D/4h/15m, stage c4 rows

| Years | Taken n | Taken mean | Shadow n | Shadow mean | Gap | t |
|---|---|---|---|---|---|---|
| 2024 | 188 | −0.209 | 2,566 | +0.025 | **−0.234** | −2.3 |
| 2025 | 189 | +0.282 | 2,333 | −0.010 | +0.293 | 2.6 |
| 2026 | 197 | +0.067 | 2,147 | +0.018 | +0.049 | 0.4 |
| **2024-26 (scored)** | 574 | +0.048 | 7,046 | +0.011 | **+0.036** | **0.6** |
| 2022-23 (reference) | 357 | +0.032 | 4,828 | −0.048 | +0.081 | 1.0 |

Shadow = `watch` at stage c4 with at least one failing quality check. 494 c4 `watch` rows over 2022-2026 that were
held only by the played-out rule (Phase A) were excluded, as registered. With the hold-to-bias-close exit the
2024-26 gap is +0.034 R (t 0.5).

Cross-check on the earlier engine's files (a146893, `results/backtest_tv` and `results/backtest_tv_holdout`, same rows
restricted to c4): 2022-23 gap **+0.139 R** (t 2.0), which reproduces the +0.13 R holdout gap the hypothesis came
from; 2024-26 gap +0.002 R (2024 −0.247, 2025 +0.243, 2026 +0.013). The gap is a 2022 effect (+0.23 R) that does
not come back in the next four years.

**For the app:** the quality checks, taken together, still do not separate winners from losers at the first
report: keep them as the trader's checklist, not as evidence of an edge. Test 4 asks the same question per check.

## Test 4: eligibility replay of the quality checks

Baseline (1D/4h/15m, 8 symbols, 2022-2026): 15,968 triggers; 931 taken at the first report, **963 traded at some
check** (eligibility adds 32 triggers that became long / short later), +0.034 R per traded trade (2R) and
−0.032 R (bias close). Each row below is a full engine re-run with that one check made advisory. Affected =
triggers traded in only one of the two runs, or at a different check. d = R with the check off minus R with it on
(untraded = 0), so **d < 0 means the check helps**.

| Quality check | First reports it blocks (alone) | Affected | Mean d (2R) | t | Σd by year 2022 … 2026 | Mean d (bias close) | Change in R per traded trade (2R) | Verdict |
|---|---|---|---|---|---|---|---|---|
| `rev_expansion_into_level` | 6,027 (3,107) | 2,552 | −0.004 | −0.1 | −74.0 / +10.1 / +34.2 / +5.0 / +13.3 | +0.012 | −0.028 | no measurable effect |
| `rev_opposing_run_small` | 7,075 (2,287) | 2,248 | −0.024 | −0.8 | −4.8 / +23.5 / +1.1 / −26.0 / −48.5 | +0.001 | −0.041 | no measurable effect |
| `cont_objective_open_at_trigger` | 1,822 (804) | 801 | −0.041 | −0.8 | −36.2 / −19.3 / +3.5 / +4.9 / +14.1 | +0.067 | −0.034 | no measurable effect |
| `rev_cisd_swift` | 3,937 (717) | 492 | +0.014 | 0.2 | +13.7 / −4.2 / −11.7 / +9.9 / −0.8 | −0.024 | −0.007 | no measurable effect |
| `cont_setup_closure_body_aligned` | 641 (105) | 104 | −0.121 | −0.9 | +2.1 / −8.1 / +2.5 / +1.5 / −10.7 | +0.057 | −0.015 | no measurable effect |
| `cont_trigger_clear_of_liquidity` | 618 (81) | 80 | +0.206 | 1.2 | +3.5 / +4.6 / +2.0 / +3.6 / +2.8 | +0.044 | +0.013 | no measurable effect |
| `cont_entry_early_in_candle` | 158 (18) | 18 | −0.580 | −2.1 | −3.4 / −1.1 / −4.6 / −3.4 / +1.9 | −0.082 | −0.011 | untestable (< 30) |
| `cont_not_inside_consolidation` | 675 (6) | 6 | +0.434 | 0.7 | | −1.091 | +0.002 | untestable |
| `cont_trigger_v_shape` | 700 (3) | 3 | −0.023 | 0.0 | | −1.041 | −0.000 | untestable |
| `cont_protected_swing_intact` | 76 (4) | 0 | | | | | 0 | untestable |
| `cont_entry_window_open` | 31 (0) | 0 | | | | | 0 | untestable |
| `rev_formed_early` | 0 (0) | 0 | | | | | 0 | untestable |
| `rev_wick_intact` | 0 (0) | 0 | | | | | 0 | untestable |

No check reaches the registered bar (|t| ≥ 2.9 with 4 of 5 years the same sign): **no check is shown to help or
to hurt.** Six are testable and all six are "no measurable effect"; seven are untestable on this stack.

What the replay does show:

- **The checks that matter in volume are near-neutral filters.** `rev_expansion_into_level`,
  `rev_opposing_run_small` and `cont_objective_open_at_trigger` each hold back 800-2,500 trades that, taken, make
  about 0 R (−0.003 to −0.041 R each). Switching any of them off adds those near-zero trades and lowers the R per
  traded trade by 0.03-0.04 (from +0.034); it does not change total R in a way the data can tell from noise, and
  the yearly sums change sign.
- **Two hints, below the bar:** `cont_trigger_clear_of_liquidity` holds back 80 trades that make +0.206 R each,
  positive in all 5 years (t 1.2): if anything this check costs R. `cont_entry_early_in_candle` holds back 18 trades
  at −0.58 R, 4 of 5 years negative (t −2.1): if anything it helps, but on 18 trades. Both need more data
  (1D/1h/5m, or forward) before anyone acts on them.
- **Why seven are untestable:** `rev_formed_early` and `rev_wick_intact` never fail at a report on 1D/4h/15m;
  `cont_entry_window_open` never fails alone; `cont_trigger_v_shape` and `cont_not_inside_consolidation` almost
  never block because the clean-continuation wait already skips such triggers; `cont_protected_swing_intact` blocks 4
  triggers alone, and with it off they still stay at `watch` because a taken stop swing means the trade has played
  out (the Phase A rule), so the check is redundant with that rule.
- The switch itself was verified: no variant row lists the switched-off check in `blocking`, and only the decision
  changes (no trigger was removed in any variant; 3 were re-timed in one).

**For the app:** keep the quality checks as the trader's checklist and keep explaining why a trigger is blocked
(A4), but do not present any single check as an evidence-backed filter. The data does not support adding weight to
any of them, nor removing one; `cont_trigger_clear_of_liquidity` and `cont_entry_early_in_candle` are the two to
re-test on 1D/1h/5m or in the decision journal.

## What could not be run as registered

All four tests ran as registered. Limits of scope that were stated in the pre-registration, not changed after:

- Test 4 covers 1D/4h/15m only (1D/1h/5m would have needed about 13 × 40 × 25 CPU-minutes). On this stack seven of
  the 13 checks have fewer than 30 affected triggers, so they are "untestable" here, not "no effect".
- The monthly stack starts in 2023 (it needs 23 closed monthly bars; the data starts 2021-01).
- The "played-out only" exclusion count in Test 3 (494) is over 2022-2026, not per year.

## Method notes

- Harness changes (all opt-in; checked to leave the old output unchanged: NQ 1D/4h/15m 2025, 398 rows identical
  with and without the options, outcomes identical to the earlier study's file):
  `--max-days`, `--extra-horizons`, `--limit-windows`, `--eligibility`, and `off-<check>` variants that make one
  quality check advisory for the run only (the app's config and behaviour do not change).
- Run time: another backtest session shared the machine for the first two hours (22 workers), so the core grid
  hit the 2-hour background limit after 31 of 80 jobs and was relaunched; finished jobs are kept, so nothing was
  re-run or lost.
- Multiple comparisons: tests 1 and 2 score 6 + 2 cells; test 4 13 checks with a Bonferroni-style |t| ≥ 2.9 bar.
