# Phase B pre-registered tests (written 2026-11-14, before any of these numbers were computed)

Engine: `ttrades-backtest` at 05209b4 (Phase A defaults). Data: TradingView 5m front-month stitch,
NQ ES GC YM RTY CL SI 6E. R is net of costs (commission $4.50 round turn on a mini, one tick of stop slippage).
Clustered t: by symbol x trading day.

## Data groups

- **U21 (untouched):** a new run, 2021-08-01 to 2022-01-01 (the 5m data starts 2021-01-03; August leaves 200+ days
  of history for a weekly bias). Stacks 1D/1h/5m, 1D/4h/15m, 1W/1D/1h; variants `baseline` and `quality_off`
  (every quality check made advisory, so every entry-ready trigger is taken). No analysis has read 2021.
- **P:** baseline 2022-2023 (1D/4h/15m and 1W/1D/1h, plus `quality_off`) and 2024-01-01 to 2026-11-14
  (1D/1h/5m, 1D/4h/15m, 1W/4h/15m, 1W/1D/1h). 1M/1D/1h is left out everywhere.
- Amended before any run (2026-11-14): every group is **re-run on the current engine** into `results/phase_b/`, not
  read from `results/backtest_tv*`. Those older runs predate Phase A and count played-out triggers as taken, which
  would bias T1 (a limit on a played-out trigger is cancelled) and T3 (the two sides would differ in that rule).

## T1. Limit order at the plan's entry instead of a market fill at the first report

Never computed on any year, so U21 and every year of P are out of sample for it.

Population: the app's taken triggers (`taken`, not skipped, risk known), every stack above.
Order: placed at the check that first reports the trigger; buy (sell) limit at `plan_entry`, stop `plan_stop`.
- If the first 5m bar at or after the check opens at or beyond the entry in the trade's favour (long: open <= entry)
  and still short of the stop, fill at that open (a marketable limit). If it opens at or beyond the stop: no trade.
- Otherwise fill at `plan_entry` on the first bar that trades through it by one tick (long: low <= entry - tick).
- Cancelled, no trade, if before the fill price reaches the 2R target measured from the plan entry, or the stop, or
  the forming bias candle closes, or 10 days pass.
- After the fill: 2R target and stop from the fill. On the fill bar the stop counts, the target does not (it starts
  on the next bar). A bar touching both is a stop. Stop fill one tick worse; no entry slippage. Open at 10 days:
  marked to the last close.

Metric: net R per signal (no fill = 0) for the limit, against `net_2r` (market) on the same signals.
**PASS** if all three hold: (a) mean(limit - market) per signal > 0 pooled, clustered t >= 2; (b) positive in at
least 5 of the 6 year groups (U21, 2022, 2023, 2024, 2025, 2026); (c) positive on at least 6 of 8 symbols.
Reported but not part of the pass: fill rate, mean R per fill, and whether the limit's own mean is > 0.

## T2. Exit: bias-candle close and 3R against a fixed 2R

Exits were already compared on 2022-2026, so only U21 tests them. Taken triggers on the 1D-bias stacks
(1D/1h/5m, 1D/4h/15m), market entry. **PASS** for each exit separately if mean(`r_bias_close` - `net_2r`) (or
`net_3r` - `net_2r`) > 0 on U21 and positive on at least 5 of 8 symbols. Expected to be weak (small n).

## T3. Do the quality checks help? (replay with the checks off)

Triggers keyed by (symbol, stack, trigger bar open, direction). Kept = taken in both `baseline` and `quality_off`;
removed = taken in `quality_off` only. Each row's own outcome (`net_2r`) is used. Groups: U21 (all three stacks)
and 2022-2023 (1D/4h/15m and 1W/1D/1h; `quality_off` run added for this test).
**PASS (the checks help)** if mean(kept) - mean(removed) > 0 in U21 and in 2022-2023, and mean(removed) < 0 in both.
**FAIL** otherwise; then the app should present the quality checks as information, not as blockers (a proposal,
not applied without the trader's say).

## T4. Re-test of the best-measured setup (H4) on U21

Taken, `trigger_kind == "cisd"`, `risk_adr >= 0.10`, stacks 1D/4h/15m and 1W/1D/1h, market entry, 2R.
**PASS** if mean `net_2r` > 0 on U21 (pooled over the 8 symbols) and positive on at least 5 of 8 symbols.

Nothing here is changed after the runs start. Results are appended below with the date.

## Run incident (2026-11-14, before scoring)

The first run reused worker processes, and the `quality_off` patch stayed active in a worker after its job, so 83
of 152 baseline outputs were produced with the quality checks off (detected because no row of those files lists a
quality check as blocking). A first scoring pass was run on that mix before the leak was noticed; its numbers are
discarded. The 83 files were moved to `results/phase_b/_contaminated/` and re-run with one job per process and a guard
that refuses a baseline job if the patch is present. The tests and pass rules above are unchanged.
