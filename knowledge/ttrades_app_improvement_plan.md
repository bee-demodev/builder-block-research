# Trading Companion: improvement plan from the 2026-11-13 backtest

v2, revised after council round 1 (Claude Opus 5.5: methodology 7, plan 6; GPT-6.1 Sol: methodology 6.5, plan 7).
Evidence: [ttrades_backtest_findings.md](ttrades_backtest_findings.md) (primary, TradingView 5m, 8 symbols, 2024 / 2025 /
2026 YTD), [PREREGISTERED_2022_2023.md](../results/backtest_tv/PREREGISTERED_2022_2023.md) (untouched 2022-2023),
[ttrades_failure_audit.md](ttrades_failure_audit.md), [ttrades_backtest_hypotheses.md](ttrades_backtest_hypotheses.md).

## What the data says

No demonstrated durable edge **for this implementation and execution model** (market entry at the first report, structural
stop, fixed 2R, 10-day horizon). Gross of costs the engine's triggers are a coin flip (−0.005 R over all triggers); costs
take ~0.03 R more. Nothing searched on 2025 held in 2024, 2026 and the other symbols. This does not test the trader's
discretion or limit-order entries: "not supported" teacher claims are not disproved claims.

The strongest warning: trades whose displayed stop (engine entry to stop) is under 4% of ADR14 lose in 5 of the 6
symbol-group × year cells with data (all 8 symbols pooled: −0.315 / −0.224 / −0.124 R, 2024 / 2025 / 2026; the app's taken
trades in that band −0.288 / −0.155 / −0.374). About 58% of that loss is cost per R, so it is partly arithmetic and
depends on the contract (micros cost ~2-3x more per point). The exception: NQ/ES/GC 2026 at +0.122 (n 89).

Separately, 31% of 1D/1h/5m verdicts reach the trader more than 15 minutes after the trigger, at a median 1.74 R from the
shown entry, and the verdict stays `long` / `short` after the trade has hit its target or stop.

## Phase A: build now (small, evidence-backed or plain bug fixes)

| # | Change | Why | Where |
|---|---|---|---|
| A1 | **Stop-size check** `stop_size_ok`: displayed risk / ADR14 ≥ `min_stop_adr_frac` (0.04). ADR14 = mean high−low of the last 14 closed 1D bars. Default role `quality`: the verdict stays `watch` ("stop is x% of ADR, under 4%: costs eat the trade") and the idea stays visible. Switchable to `gate` or `advisory`. | The strongest negative result, on the exact definition shipped (both reviewers asked for that check). `quality` rather than `gate` because 2026 core symbols were positive and the holdout could not test it. | `ttrades/context.py`, `checklist.py`, `style.py`, `config.py/json`, `rules.md` §8.2, §11 |
| A2 | **Stop size and cost on the plan**: stop as % of ADR, and cost per trade in R for a mini and a micro contract. One readout; no 10% band. | The trader sizes in micros (findings §3e); costs are most of the small-stop loss. | `types.PositionPlan` (+`risk_adr`, `cost_r_mini`, `cost_r_micro`), `plan.py`, `web/decision.ts`, `DecisionPanel.tsx` |
| A3 | **Signal lifecycle: forming / actionable / played out.** `planned` = forming. `triggered` is actionable only while the trigger is at most `actionable_entry_bars` (3) entry bars old and price is within `actionable_max_r` (0.5 R) of the entry; otherwise "late: price is x R from the entry". `outcome` `target_reached` / `stopped` demotes the decision to `watch` with "already played out". Age is counted in entry bars, so it scales with the timeframe. | Bug fix (Q33). Audit: 31% of verdicts are >15 min late, median 1.74 R away; a `long` survives its own `target_reached`. Sol's "potential vs actionable vs completed" ask. | `types.PositionPlan` (+`age_bars`, `stage_label`), `plan.py`, `style.py` §10.3, `rules.md` Q33, `DecisionPanel.tsx` |
| A4 | **Why a drawn trigger is blocked**: when the verdict is `watch` and a trigger exists, label the trigger on the chart with the failing checks in a few words. | Audit need #6; makes the quality checks transparent instead of changing them (their effect is not causally tested). | `style.py` markup `short`, `Charts.tsx` |
| A5 | **Stacks**: add 1D / 4h / 15m (stated by the teacher, least-bad stack, +0.090 R for taken trades on untouched 2022-23). Mark 1M/1D/1h, 1W/4h/15m and every 1m-entry stack "not validated" in the stack menu tooltip. Do not add 1W/1D/1h (failed its pre-registered test). | Honest stack choice. | `companion/config/stacks.json` (+`note`), `timeframes.py`, `TopBar.tsx` |
| A6 | **Intraday reference levels** as a toggle layer (default off): PDH / PDL, Asia (18:00-00:00) and London (02:00-05:00) high/low, midnight and 09:30 opens. `info` markup only; no rule reads them. | The teacher draws them; 14 of 100 missed big-day cases started from one. Context, not a filter. | `style.py` (markup), `DisplayMenu.tsx`, `Charts.tsx` |

**Built 2026-11-13** (uncommitted on `ttrades-backtest`). Change from the table: A1 `stop_size_role` defaults to
`advisory` (trader: "ADR is not that big of a deal"); `quality` stays a config switch. A6 levels are read from the
entry timeframe (the series a live feed keeps current), so a 1h entry has no 09:30 open. Confirmation backtest
(`scripts/compare_phase_a.py`, TradingView data, NQ and ES 1D/1h/5m 2025, old engine vs new, defaults): identical
trigger sets (876 NQ, 799 ES); the only changes are 18 NQ and 21 ES taken trades demoted to `watch` as played out
(first reported a median 798 / 465 minutes after the trigger, mean −0.41 / −0.38 R). Taken-trade expectancy moves
−0.127 → −0.063 R (NQ) and −0.247 → −0.209 R (ES): still negative, and in-sample; no edge is claimed.

Settled, no change: the entry-mode default. On TradingView data (NQ ES GC YM RTY, 1D/1h/5m, 1D/4h/15m, 1W/4h/15m,
2024-25) taken trades are baseline −0.099 / +0.001, CISD-only (`aggressive`) −0.086 / +0.007, `no_clean_wait`
−0.081 / +0.014 R: within 0.02 R in every year, stack and symbol.

Cut from v1: the "best-measured setup" tag (a sign-test pass is not significance; it described a pooled two-stack
population), the separate ADR-used readout (folded into A2), kill-zone shading (no evidence; the 02:00-05:00 result was
found after looking), the 10% stop warning band (rested on low-confidence Databento data), the 1W/1D/1h stack.

## Phase B step 1: pre-registered tests (2026-11-14)

Rules written first in [PREREGISTERED_PHASE_B.md](../results/phase_b/PREREGISTERED_PHASE_B.md); results in
[report.md](../results/phase_b/report.md). Every year re-run on the current engine (played-out trades no longer count
as taken: 114 of 290 taken 1D/4h/15m trades in 2022 were first reported a median 750 minutes after their target or stop
had traded). Aug-Dec 2021 was untouched. A worker-process leak in the first run was caught and re-run before scoring
(logged in the pre-registration). 8 symbols, 3,750 taken trades.

| Test | Result | Verdict |
|---|---|---|
| T1 limit at the plan entry vs market at the first report | -0.001 R per signal (t -0.07), up 2 of 6 years, fill rate ~92% | FAIL: no difference |
| T2 exits on 2021 (1D-bias stacks) | bias close -0.088 R and 3R -0.060 R against 2R | FAIL: 2R stays |
| T3 replay with the quality checks off | checks helped in 2022-23 (+0.058 R), hurt in 2021 (-0.088 R) | FAIL: effect unproven |
| T4 best-measured setup (CISD, stop >= 10% ADR, 1D/4h/15m + 1W/1D/1h) on 2021 | +0.060 R, n 73, 4 of 8 symbols | FAIL (needed 5 of 8) |

Descriptive, all years, taken trades net of costs: all -0.033 R (t -1.3); **1D/1h/5m -0.075 R (t -2.4), negative in
every year tested and on 5 of 8 symbols** (gross -0.02 R: costs plus a slight negative; continuation -0.12 R);
1D/4h/15m +0.042 R (t 0.9, up 4 of 6 years); 1W/4h/15m 0.000; 1W/1D/1h +0.054 (n 119); **stops under 4% of ADR
-0.309 R (t -3.7, every year negative)**.

Built from it: the plan panel shows the dollars one contract risks, and a grade with its record from
`companion/config/evidence.json` (written by `scripts/phase_b_evidence.py`): "Small stop", "No edge measured" with the
stack's record and its exits, or "Not backtested". The best-measured grade is suppressed because its re-test failed.
Stack-menu notes carry the same numbers.

## Phase B: next session (the trader's discretion is the only place an edge can still be)

- **Decision journal** (both reviewers' top missing item): log every verdict the trader saw (including `watch` triggers),
  a take / skip button with a reason, and the outcome from the plan; show running expectancy per stack against the engine
  baseline. This is the only way to measure whether the trader's discretion adds what the rules alone do not.
- **Evidence line per stack** (descriptive only: "2022-26, n …, ~0 R/trade net"), once the journal can sit next to it.
- *Built (items 1 and 2, 2026-11-14):* `companion/core/journal.py` logs each trigger once (live checks that follow
  the latest bars; long, short or watch with a triggered plan) to `journal.jsonl` in the state folder, fills the outcome
  from later checks (+R at the target, -1R stopped, open triggers stay open), and takes the `journal` wire command for
  "Took it" / "Skipped" with a reason. The left panel shows the call, taken / skipped / all-trigger average R per stack
  (before costs, closed only, "too few" under 20) and the stack's `note`. Not yet tested on a live session.
- **Backtest follow-ups, pre-registered first**: (1) 1W / 1M stacks with a horizon of at least one bias candle;
  (2) a limit-at-plan-entry variant; (3) taken vs shadow on 1D/4h/15m restricted to c4 rows (holdout gap +0.13 R);
  (4) eligibility replay of the quality checks (a causal test, not the first-report comparison).

## Verification for Phase A

Python: `.venv/Scripts/python -m pytest tests/companion -q`, plus new tests: A1 boundary at exactly 4%, ADR14 from closed
1D bars only, role switching; A3 each lifecycle state, age in entry bars, `target_reached` and `stopped` demote. Web:
`npm run check` and `npm test` in `companion/web`. Backtest: re-run NQ and ES 1D/1h/5m 2025 on TradingView data and
confirm that the only taken trades that change are the sub-4% and played-out ones. Then a fresh council round on the diff.
