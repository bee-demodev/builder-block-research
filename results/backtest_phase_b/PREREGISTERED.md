# Phase B backtest follow-ups: pre-registration (written 2026-11-14, before any run)

Plan: [knowledge/ttrades_app_improvement_plan.md](../../knowledge/ttrades_app_improvement_plan.md), Phase B item 3.
Method and earlier results: [knowledge/ttrades_backtest_findings.md](../../knowledge/ttrades_backtest_findings.md) and
`results/backtest_tv/PREREGISTERED_2022_2023.md` (main checkout).

Nothing below has been run when this file is committed. The only run before it is a harness regression check
(NQ 1D/4h/15m 2025, a year the earlier study already used) that compares the old output fields; its new fields
(limit, eligibility) are not read before this commit.

## Common to all four tests

- **Engine**: the companion app's TTrades style at commit 05209b4 (Phase A included: stop-size check advisory by
  default; played-out triggers demoted to `watch`), baseline config, unless a test says otherwise.
- **Harness**: `companion/tools/backtest.py` with the Phase B options (`--max-days`, `--extra-horizons`,
  `--limit-windows`, `--eligibility`, `off-<check>` variants), committed with this file. With none of them set the
  harness gives the same fields as before.
- **Data**: TradingView 5m front-month stitch, unadjusted, `data/external/tradingview/<SYM>_5m.csv` (main checkout,
  first bar 2021-01-03, last 2026-11-13 13:20 NY). Symbols NQ ES GC YM RTY CL SI 6E. One job per calendar year;
  2026 runs to the end of the data. Outcomes are walked on the same 5m bars. No paid data.
- **Fill and cost model (market)**, unchanged from the findings: entry at the open of the first bar at or after the
  check, one tick worse; stop fill one tick worse; target is a limit (no slippage); $4.50 round turn per contract;
  a bar touching stop and target counts as the stop. R is net of costs. Open trades are marked to market at the
  horizon.
- **Row filters** (as `scripts/analyze_backtest.py`): drop rows with no fill data or a market fill beyond the stop;
  drop stops under two ticks.
- **Unit**: every trigger (first report), no one-position-at-a-time filter (as the 2022-2023 pre-registration).
- **t-statistics**: mean / clustered standard error, clusters = symbol x trading day (day starts 18:00 NY) unless a
  test names another cluster.
- **No edge is claimed from any of these tests.** Every year used here (2022-2026) has been looked at in some form by
  the earlier study or the 2022-2023 holdout (named per test). A PASS makes a rule a candidate for a forward test on
  data after 2026-11-13, nothing more. A test that cannot be run as written is reported as not run, not changed.

## Test 1: weekly and monthly stacks with a horizon of at least one bias candle

Why: in the findings, 34-42% of weekly / monthly trades were still open at the 10-day horizon, and a monthly bias
candle (up to 31 days) is cut short by it, so these stacks were not ranked reliably.

- Stacks: 1W / 4h / 15m, 1W / 1D / 1h, 1M / 1D / 1h. Years 2022-2026 for the weekly stacks; 2023-2026 for the monthly
  stack (it needs 23 closed monthly bars; the data starts 2021-01).
- Horizon: **35 calendar days** after the check for every outcome (>= one monthly bias candle, >= four weekly ones).
  The 10-day outcomes of the same triggers are kept (`h10_*`) to show what the longer horizon changes.
- Population: all triggers with displayed risk / ADR14 >= 0.10 (the findings' stack ranking filter). Taken-only is
  reported, not scored.
- Hypotheses, per stack (6 cells):
  - **H1a**: mean `net_2r` (2R target, 35-day horizon) > 0.
  - **H1b**: mean `r_bias_close` (held to the close of the bias candle the trade belongs to) > 0.
- **PASS** for a cell only if all three hold: pooled mean > 0 with t >= 2.0 (clusters: symbol x bias candle, because
  trades on one bias candle overlap); > 0 in at least 4 of 5 years (monthly: 3 of 4); > 0 on at least 5 of 8
  symbols (pooled over years). Otherwise FAIL.
- Also reported: share of rows still `open` for 2R at 10 and at 35 days; share with an unresolved `r_bias_close`
  (should be ~0 at 35 days).
- Prior looks: all three stacks 2024-2026 at a 10-day horizon (findings §3a); 1W / 1D / 1h 2022-2023 with
  risk_adr >= 0.10 (holdout H2, FAIL). 1W / 4h / 15m and 1M / 1D / 1h 2022-2023 were not looked at.

## Test 2: limit order at the plan entry instead of a market entry at the first report

- Order: at the first check that reports the trigger, a limit at the plan's entry price (`plan_entry`, the trigger
  level the app shows), valid for **W = 3 entry-timeframe bars** (15 min on 1D/1h/5m, 45 min on 1D/4h/15m; the
  same 3 bars as the app's `actionable_entry_bars`), then cancelled.
- Fill (`Simulator.run_limit`): a bar that opens at or beyond the entry fills at its open (the better price); else
  the order fills at the entry on the first bar that trades through it by one tick (touching is not enough). On the
  fill bar the stop counts but a target does not (only the bar's close counts in favour). A bar opening beyond the
  stop before a fill: `gap_beyond_stop`, excluded and counted. R = |fill - stop|. Costs: commission and one tick of
  stop slippage; no entry slippage. 10-day horizon as in the findings.
- Stacks: 1D / 1h / 5m and 1D / 4h / 15m (the 5m+ entry stacks the app offers as stated stacks). Years 2022-2026,
  8 symbols. Weekly / monthly stacks get the same fields (35-day horizon) and are reported, not scored.
- Population (primary): triggers **taken** at the first report (the app said long / short). All triggers reported.
- Hypotheses:
  - **H2a (edge)**: mean `lim3_net_2r` over filled limit trades > 0. PASS only if pooled t >= 2.0, > 0 in at least
    4 of 5 years and on at least 6 of 8 symbols.
  - **H2b (better than the market entry)**: per taken trigger, limit outcome (unfilled = 0 R) minus market `net_2r`
    of the same trigger: pooled mean > 0 with t >= 2.0 (paired, symbol x day clusters) and > 0 in at least 4 of
    5 years.
- Also reported: fill rate, share filled at the open, W = 1 and W = 12 bars, and all triggers.
- Prior looks: market entries on all these triggers (findings, holdout); never a limit entry.

## Test 3: taken vs shadow on 1D / 4h / 15m, stage c4 only

Why: on untouched 2022-2023, 1D / 4h / 15m taken trades beat shadow by +0.13 R, but many shadow rows sit below c4
(held by steps or gates, not by quality checks).

- Stack 1D / 4h / 15m, 8 symbols. **Test years 2024, 2025, 2026** (2022-2023 produced the hypothesis; reported for
  reference only).
- Rows: first reports with `stage == "c4"`. Taken = decision long / short. Shadow = decision `watch` with at least one
  failing quality check (`blocking` not empty). Watch rows with nothing in `blocking` (held only by the played-out
  rule) are excluded and counted.
- Metric: gap = mean `net_2r` (taken) - mean `net_2r` (shadow).
- **PASS** only if the gap is > 0 in each of 2024, 2025 and 2026, and the pooled 2024-2026 gap has t >= 2.0, with
  t = gap / sqrt(se_taken^2 + se_shadow^2), each se clustered by symbol x trading day.
- Also reported: the same on the earlier engine's files (commit a146893, `results/backtest_tv`, which have the same
  `stage` and `blocking` fields), and `r_bias_close`.
- Prior looks: taken vs shadow over all rows, 2024-2026 (findings: no gap). The c4 restriction has not been scored.

## Test 4: eligibility replay of the quality checks (causal)

For each quality check, switch it off (made advisory for the run: computed, never blocking) and re-run the engine;
compare the trades the app would have given with and without it. Unlike the first-report comparison this catches
triggers that become eligible later in their life.

- Checks: the 13 quality checks of the default config: `cont_setup_closure_body_aligned`, `cont_entry_window_open`,
  `cont_protected_swing_intact`, `cont_trigger_clear_of_liquidity`, `cont_trigger_v_shape`,
  `cont_not_inside_consolidation`, `cont_objective_open_at_trigger`, `cont_entry_early_in_candle`,
  `rev_expansion_into_level`, `rev_opposing_run_small`, `rev_formed_early`, `rev_cisd_swift`, `rev_wick_intact`.
  The clean-continuation wait (`wait_for_clean_continuation`, a separate setting) stays on; its effect was measured
  as the `no_clean_wait` variant in the findings.
- Stack 1D / 4h / 15m only, 8 symbols, 2022-2026. (1D / 1h / 5m would need ~13 x 40 x 25 CPU-minutes; out of budget.)
- Trade definition (`--eligibility`): a trigger is traded at the **first check that reports it long / short**, market
  entry there (same fill and cost model), 2R target, 10-day horizon.
- Matching: triggers are matched across runs by (symbol, direction, path, trigger bar, plan entry, plan stop). Per
  trigger, o = `elig_net_2r` if traded, else 0. d = o(check off) - o(baseline). **Affected** triggers: traded in only
  one run, or traded at a different check.
- Metric per check: mean d over affected triggers (R per affected trigger; negative = the check keeps out trades
  that lose, i.e. it helps).
- Verdict per check (13 checks, so a Bonferroni-style bar |t| >= 2.9; clusters symbol x trading day of the trigger's
  first report):
  - **helps**: mean d < 0, t <= -2.9, and the summed d < 0 in at least 4 of 5 years;
  - **hurts**: mean d > 0, t >= 2.9, and the summed d > 0 in at least 4 of 5 years;
  - **no measurable effect**: otherwise; **untestable**: fewer than 30 affected triggers.
- Also reported: added / removed / re-timed counts, the mean outcome of the added trades vs the baseline's traded
  trades, the change in R per traded trade, and the same with `r_bias_close`.
- Prior looks: first-report "held only by this check" comparisons (findings §3d, D7 / D9 rows). No causal re-run.

## Runs (in this order; at most 16 worker processes; each background job under 2 hours)

1. `core`: 1D/1h/5m and 1D/4h/15m, 2022-2026, `--limit-windows 1 3 12 --eligibility` (tests 2, 3, 4 baseline).
2. `htf`: 1W/4h/15m, 1W/1D/1h (2022-2026), 1M/1D/1h (2023-2026), `--max-days 35 --extra-horizons 10
   --limit-windows 1 3 12 --eligibility` (test 1).
3. `checks_off`: the 13 `off-<check>` variants on 1D/4h/15m, 2022-2026, `--eligibility`, in two batches (test 4).

Analysis: `scripts/phase_b_backtests.py`; outputs in `results/backtest_phase_b/report/`; write-up in
`knowledge/ttrades_phase_b_backtests.md`.
