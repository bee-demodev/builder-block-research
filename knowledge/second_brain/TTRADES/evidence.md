---
title: "TTRADES: evidence ledger (backtested rules and switches)"
type: ttrades-evidence
created: 2026-11-21
last_updated: 2026-11-21
---

# Evidence ledger

One row per rule or switch that has been backtested. It records the engine's own results on
TradingView 5m bars (8 futures, 2021-11-14 to 2026-11-13, costs included, no slippage, one position
per symbol and stack, 2R target). This is evidence, not the teacher's words, and never a reason to
override the teacher without asking Vik. Concept cards (`tt_lookup <concept>`) show the rows for
their concept; `tt_lookup --evidence <word>` searches them.

Walk-forward: choose on train (2021-11-15 to 2024-12-31), confirm on validate (2025), forward-test on
test (2026-01-01 to 2026-11-13). Cells are mean R per week of the variant, with the baseline on the same
stacks and cap in brackets. **passes** = better than the baseline on train, and in both validate and
test. Generate a row with
`python -m companion.tools.weekly_r --runs <out> --variant <v> --compare baseline [--stacks ...] [--max-per-day 1 --day-scope portfolio]`.
The loop turns and readiness scores behind these rows are in [[loop-log]]; the full report is
`backtests/5y-summary.md`.

Stacks: "4h+W" = 1D/4h/15m and 1W/1D/1h; "all" adds 1D/1h/5m. Cap "1/day" = one fill a trading day
across the portfolio (PSY-1); "none" = one position per symbol and stack only.

## Ledger

| Rules | Concept | Switch | Variant | Stacks | Cap | Train | Validate | Test | Verdict | Run |
|---|---|---|---|---|---|---|---|---|---|---|
| CISD-19, ENT-1 | entry-models | entry_mode_continuation = conservative (wait for the next continuation) | next_continuation | 4h+W | none | -0.01 (base -0.10) | +0.91 (base +1.15) | +0.30 (base +0.32) | fails out of sample | tv-5y |
| CISD-19, ENT-1 | entry-models | entry_mode_continuation = conservative | next_continuation | 4h+W | 1/day | -0.04 (base -0.16) | +0.40 (base +0.41) | -0.13 (base -0.07) | fails out of sample | tv-5y |
| question 14 | entry-models | entry_mode_continuation = aggressive (enter on the CISD) | cont_cisd_entry | 4h+W | none | -0.11 (base -0.10) | +1.00 (base +1.15) | +0.30 (base +0.32) | fails on train | tv-5y |
| BIAS-1, RNG-3 | ranges-and-eq | eq_respect_role = advisory | eq_soft | 4h+W | none | -0.17 (base -0.10) | +1.28 (base +1.15) | +0.22 (base +0.32) | fails on train | tv-5y |
| BIAS-9, PROF-1 | profiles | profile_check_role = quality | profile_veto | 4h+W | none | -0.08 (base -0.10) | +0.86 (base +1.15) | +0.26 (base +0.32) | fails out of sample | tv-5y |
| ENT-6, ENT-7 | entry-models | trade_reversals = false | no_reversals | 4h+W | none | -0.09 (base -0.10) | +0.22 (base +1.15) | -0.07 (base +0.32) | fails out of sample | tv-5y |
| SES-1, SES-2 | sessions-and-time | kill_zones 08:00-10:30, session_filter_role = quality | ny_window | 4h+W | none | -0.05 (base -0.10) | +0.84 (base +1.15) | +0.20 (base +0.32) | fails out of sample | tv-5y |
| SES-1, SES-2, PSY-1 | sessions-and-time | kill_zones 08:00-10:30 + one trade a day | ny_window | 4h+W | 1/day | -0.07 (base -0.16) | +0.72 (base +0.41) | +0.35 (base -0.07) | passes (train gain under the loop's paired t of 1) | tv-5y |
| question 38 | risk-and-management | stop_size_role = quality (stop >= 4% of ADR) | stop_gate | 4h+W | none | -0.06 (base -0.10) | +1.18 (base +1.15) | +0.34 (base +0.32) | passes | tv-5y |
| SW-1 | swings-and-structure | protected_swing_break_on = close | swing_close_break | 4h+W | none | -0.09 (base -0.10) | +1.15 (base +1.15) | +0.29 (base +0.32) | fails out of sample (no effect) | tv-5y |
| CC-4, C4c | candle-closures | c4_after_double_expansion = skip | no_double_expansion_c4 | 4h+W | none | -0.03 (base -0.10) | +1.19 (base +1.15) | +0.37 (base +0.32) | passes | tv-5y |
| T1, CISD | cisd | cont_setup_pick = wick_extreme (one CISD a day forms the wick) | wick_setup | 4h+W | none | +0.00 (base -0.10) | +1.06 (base +1.15) | +0.38 (base +0.32) | fails out of sample | tv-5y |
| T1, CISD | cisd | cont_setup_pick = wick_extreme | wick_setup | 4h+W | 1/day | -0.07 (base -0.16) | +0.48 (base +0.41) | -0.02 (base -0.07) | passes | tv-5y |
| FM-1, FM-5 | fractal-model | stack choice (each stack alone) | baseline | each | none | 1D/1h/5m -0.64, 1D/4h/15m -0.07, 1W/1D/1h -0.02 | -1.03, +1.00, +0.15 | +0.02, +0.21, +0.11 | 1D/4h/15m and 1W/1D/1h beat 1D/1h/5m in every period | tv-5y |
| SES-22 | sessions-and-time | no fill on an FOMC statement day (post-run screen) | baseline + no_fomc_day | all | none | -0.58 (base -0.74) | -0.14 (base +0.12) | +0.42 (base +0.34) | fails out of sample (screen) | tv-5y |
| SMT, index strength | smt-and-psp | one of NQ / ES / YM per day and direction (post-run screen) | baseline + one_index | all | none | -0.42 (base -0.74) | +0.56 (base +0.12) | +0.14 (base +0.34) | fails out of sample (screen) | tv-5y |
