# TTrades backtest findings: where the setups have an edge that holds up

Written 2026-11-13 (revised the same day after the data-quality update). **Primary dataset: TradingView 5m front-month bars** (complete, volume-rolled, unadjusted), 5 stacks with 5m+ entries (1D/1h/5m, 1D/4h/15m, 1W/4h/15m, 1W/1D/1h, 1M/1D/1h), baseline config, 32,891 triggers (taken + shadow). Outcomes are walked on the 5m bars. R is net of costs (1 tick entry, 1 tick stop slippage, $4.50 round turn).

Protocol. Rules are searched on **D25** (NQ/ES/GC, 2025) only, and the same rule is then read on:
- **H24**: NQ/ES/GC 2024 (confirmation)
- **F26**: NQ/ES/GC 2026 to Nov 13 (forward, out of sample)
- **X**: YM/RTY/CL/SI/6E, all three years (cross-asset; never used for discovery)

Databento minutes miss 35–70% of NY-session minutes. They are kept only for the 1m/3m-entry stacks, in a separate **LOW CONFIDENCE** section.

Scripts: [scripts/enrich_backtest.py](../scripts/enrich_backtest.py) (features from bars closed by the check, asserted per row) and [scripts/research_backtest.py](../scripts/research_backtest.py). Tables: [results/backtest_tv/report/research.md](../results/backtest_tv/report/research.md) (primary) and [results/backtest/report/research.md](../results/backtest/report/research.md) (Databento 1m/3m, low confidence). Figures: `results/backtest_tv/report/figures/`.

## Bottom line

1. **No setup has an edge that survives the protocol.** Of 4,071 rules searched on 2025, **none** passes 2024 and 2026 together. The 50 best 2025 rules average −0.039R in 2024 and −0.094R in 2026. Every trigger together averages −0.002 / +0.009 / −0.061 / −0.044R per trade (D25 / H24 / F26 / X).
2. **The one rule that holds everywhere is a skip: stops under 4% of ADR14.** These trades make −0.27 / −0.21 / −0.21 / −0.32R in the four groups and lose on all 8 symbols. Above 4% ADR, stop size makes no reliable difference.
3. **The earlier "edge context" fails forward.** R\* (stop ≥ 10% ADR, ADR used ≥ 78%, overnight level behind the trade intact) came from the Databento study. On TradingView it makes +0.069 / +0.348R in 2025 / 2024 but **−0.113R in 2026** and **−0.048R on the other 5 symbols**. ADR used ≥ 78% alone fails the same way. On the 1m/3m Databento stacks it still reads +0.140 / +0.110, but that is low-confidence data with no forward test.
4. **The quality checks still add nothing.** Taken and shadow triggers are about the same in every group, and the gap changes sign between groups.
5. **Exits: holding to the bias-candle close is never worse than a fixed 2R** (by +0.004 to +0.083R across the four groups). 3R beats 2R in 3 of 4 groups. 1R, partials and break-even moves are no better than 2R. All of these differences are small; no exit turns the model profitable in 2026.
6. **9 of the teacher's top-10 claims are not supported.** One ("trade the body after a small wick") points the right way in all four groups but is not significant.

## Council caveats (round 1, 2026-11-13: Claude Opus 5.5 and GPT-6.1 Sol, read-only)

- Read every result as "for this implementation and execution model": market entry at the first report, structural
  stop, 10-day horizon. Discretionary or limit-order entries are not tested; "not supported" is not "disproved".
- **Quality checks:** "taken ≈ shadow" is not a causal test. 4,158-5,153 shadow rows sit below c4 (held by gates, not
  quality checks), and first-report dedupe misses later eligibility. On untouched 2022-23, 1D/4h/15m taken trades beat
  shadow by +0.13 R. Treat the effect of the checks as unmeasured.
- **Stop < 4% ADR:** about 58% of the loss is cost per R (gross about −0.13 R), so the threshold depends on the
  contract. Re-checked on the *displayed* risk the app would gate on: −0.315 / −0.224 / −0.124 R (2024 / 2025 / 2026,
  all symbols), with NQ/ES/GC 2026 the one positive cell (+0.122, n 89). The holdout could not test it (n 35).
- **Weekly / monthly stacks:** 34-42% of their trades are still open at the 10-day horizon, so their "bias close" exit is
  a 10-day mark-to-market. Their rankings here are not reliable.
- **H4 "pass"** is the pre-registered sign test, not significance (about 9% of null hypotheses pass it; 2023 t ≈ 0.4).
- Measured and small: fills beyond the stop dropped (0.8% of rows), both-touched bars counted as stops (bias ≤ +0.01 R
  overall, ≤ +0.09 R on small stops), duplicate triggers (33 of 39,801).

## 1. Findings ranked by robustness

One position at a time per symbol and stack. "E 2R" = mean net R with a 2R target. ct = t-statistic clustered by symbol × trading day. S = stop ≥ 10% of ADR14. Order: D25 / H24 / F26 / X.

| # | Rule | n | E 2R | ct | PF | Holds? |
|---|---|---|---|---|---|---|
| 1 | **Skip** stop < 4% ADR | 138 / 150 / 85 / 695 | **−0.241 / −0.231 / −0.185 / −0.331** | −1.8 / −2.0 / −1.3 / −6.2 | 0.70 / 0.71 / 0.76 / 0.62 | **Yes**: all 4 groups and all 8 symbols (NQ −0.09 … 6E −0.59) |
| 2 | Watch: S + 1D/4h/15m + check 11:00–13:30 NY | 66 / 91 / 64 / 429 (all triggers) | +0.231 / +0.346 / +0.178 / +0.099 | 1.3 / 2.2 / 1.0 / 1.5 | | Positive in all 4 groups and on 7 of 8 symbols (CL −0.10). **Found after looking at all four groups** (1 of 15 stack × window cells), so it is not out of sample. Treat it as a hypothesis. |
| 3 | Skip-ish: checks 02:00–05:00 NY (all triggers) | 246 / 253 / 213 / 1542 | −0.060 / −0.007 / −0.181 / −0.059 | −0.7 / −0.1 / −2.1 / −1.6 | | Negative in all 4 groups and on 7 of 8 symbols, but small. Same caveat as #2. |
| — | Taken by the app today | 315 / 380 / 329 / 1829 | +0.026 / −0.100 / +0.050 / +0.011 | 0.3 / −1.3 / 0.6 / 0.3 | 1.04 / 0.86 / 1.08 / 1.02 | No edge |
| — | All triggers | 1461 / 1533 / 1264 / 6845 | +0.033 / −0.019 / −0.019 / −0.045 | 0.8 / −0.5 / −0.4 / −2.2 | 1.05 / 0.97 / 0.97 / 0.93 | No edge |
| — | S (stop ≥ 10% ADR) | 1297 / 1355 / 1141 / 6169 | +0.054 / +0.006 / −0.018 / −0.033 | 1.2 / 0.1 / −0.4 / −1.6 | 1.09 / 1.01 / 0.97 / 0.95 | No |
| — | S + taken | 245 / 282 / 259 / 1409 | +0.050 / −0.029 / +0.077 / +0.057 | 0.5 / −0.3 / 0.8 / 1.4 | 1.08 / 0.96 / 1.12 / 1.09 | No (H24 negative) |
| — | R\*: S + ADR used ≥ 78% + ON level behind intact | 248 / 254 / 238 / 1404 | +0.069 / +0.348 / **−0.113** / **−0.048** | 0.7 / 3.1 / −1.1 / −1.1 | 1.12 / 1.73 / 0.83 / 0.92 | **No, fails forward** |
| — | S + ADR used ≥ 78% | 522 / 456 / 514 / 2482 | +0.081 / +0.120 / **−0.093** / −0.031 | 1.2 / 1.5 / −1.2 / −0.9 | | **No, fails forward** |
| — | S + reversal | 1139 / 1190 / 992 / 5440 | +0.079 / −0.036 / −0.008 / −0.024 | | | No |
| — | S + continuation | 452 / 440 / 368 / 2366 | −0.035 / +0.135 / −0.082 / −0.045 | | | No |
| — | FOMC day (all triggers) | 114 / 95 / 109 / 624 | −0.042 / +0.002 / −0.072 / +0.036 | | | No. NQ/ES lose (−0.15 / −0.09); GC, RTY and SI make money. |
| — | Continuation with stop < 10% ADR | 399 / 353 / 335 / 2031 | −0.023 / −0.049 / +0.016 / −0.183 | | | No on NQ/ES/GC; yes on the other 5 symbols (−0.18) |

**Multiple comparisons.** 77 conditions gave 4,071 rules scored on D25 at n ≥ 100: every condition, every pair, and every pair on top of the stop filter. On top of that came about 80 hand cuts: 15 stack × window cells, 21 claim comparisons, 9 exits, 8 stop thresholds and 15 named rules.

| Check | Result |
|---|---|
| Spearman of D25 vs H24 / F26 / X mean R across rules | 0.01 / −0.14 / 0.19 |
| Top 20 / 50 / 200 by D25 t: mean E in H24 | −0.046 / −0.039 / −0.004 |
| Same, in F26 | −0.111 / −0.094 / −0.097 |
| Same, in X | +0.002 / −0.008 / −0.015 |
| D25 t ≥ 2.5 | 88 rules → 4 have H24 t ≥ 2 → 0 also positive in F26 |
| D25 t ≤ −2.5 | 60 rules → 6 have H24 t ≤ −2 → 4 also negative in F26 |
| Stack × window cells keeping one sign across D25/H24/F26 | 4 of 15. Chance gives about 4. |

![equity](../results/backtest_tv/report/figures/equity_core.png)

## 2. Headline numbers re-derived, and where TradingView and Databento differ

On the same stacks (5m+ entries), symbols and years, the two sources agree in aggregate, even though individual triggers often differ (20 of ~45 matched in the coordinator's 4-week check). Mean net R, 2025 / 2024:

| Cut | TradingView | Databento | Difference |
|---|---|---|---|
| Taken | −0.010 / −0.098 | −0.044 / −0.016 | Same story (no edge); the year that looks worst flips |
| All triggers | −0.002 / +0.009 | −0.034 / +0.010 | Close |
| Stop < 4% ADR | −0.267 / −0.208 | −0.196 / −0.331 | Same |
| Stop ≥ 10% ADR | +0.009 / +0.042 | −0.014 / +0.066 | Close |
| Continuation | −0.016 / +0.040 | −0.079 / −0.013 | **TradingView: continuation is not worse** |
| Reversal | +0.003 / −0.003 | −0.015 / +0.019 | Close |
| R\* | −0.006 / +0.195 | −0.017 / +0.206 | Same, so its 2026 failure is not a data artefact |
| 09:30–11:00 | +0.040 / +0.005 | +0.078 / +0.039 | Close |

**How the earlier (Databento, all stacks) headlines change:**

| Headline | Databento study | TradingView (primary) |
|---|---|---|
| Taken-trade expectancy | −0.074R (8,636 trades, mostly 1m/3m stacks) | −0.010 / −0.098 / −0.006 / −0.015 per trigger. Still no edge, and less negative because these stacks have wider stops. |
| Stop-size effect | Monotone, with a "break-even above 10% ADR" plateau | Only < 4% ADR is clearly bad (−0.2 to −0.3R). Above that it is flat and negative in 2026 at every threshold (−0.058 at ≥ 10%). On these stacks 96% of stops are already ≥ 4% ADR (median 21–44% ADR on intraday stacks). |
| Continuation vs reversal | Continuation clearly worse (−0.12 vs −0.01) | No consistent gap: continuation −0.016 / +0.040 / −0.049 / −0.098 vs reversal +0.003 / −0.003 / −0.065 / −0.021. The Databento gap came from small-stop 1m/3m continuation entries. |
| Quality filters | Taken ≈ shadow | Same: taken −0.010 / −0.098 / −0.006 / −0.015 vs shadow −0.001 / +0.021 / −0.068 / −0.048 |
| Time windows | No stable window | Same. 09:30–11:00: +0.040 / +0.005 / −0.140 / +0.009. 05:00–08:30: +0.071 / −0.051 / −0.071 / −0.034. Only 02:00–05:00 is negative in all four groups. |
| R\* context | +0.106 / +0.153, replicated | Fails 2026 and the other 5 symbols |
| Best exit | Fixed 2R; bias close ≈ 0 | Bias close ≥ 2R in every group; 2R ≥ 1R in 3 of 4 |

## 3. Direct answers

### (a) Best and worst stacks (stop ≥ 10% ADR, all triggers, D25 / H24 / F26 / X)

| Stack | n (D25) | E 2R | Read |
|---|---|---|---|
| 1D / 4h / 15m | 1066 | +0.013 / +0.065 / −0.043 / +0.014 | Best of a flat set; 3 of 4 positive |
| 1D / 1h / 5m | 1876 | +0.013 / +0.023 / −0.065 / −0.031 | Flat |
| 1W / 4h / 15m | 259 | −0.064 / +0.074 / −0.022 / −0.025 | Flat to slightly negative |
| 1W / 1D / 1h | 61 | +0.094 / +0.078 / −0.163 / +0.057 | Too few in the core years |
| 1M / 1D / 1h | 57 | +0.039 / −0.047 / −0.235 / −0.142 | Worst, small n |

No stack has a durable edge. 1D/4h/15m is the least bad and holds the only watch-list cell (11:00–13:30, finding #2).

### (b) Time windows (NY clock)

There is no stable window: the stack × window counts match chance. All triggers, D25 / H24 / F26 / X:

| Window | E 2R |
|---|---|
| 18:00–02:00 | −0.033 / +0.014 / +0.022 / −0.083 |
| **02:00–05:00** | **−0.060 / −0.007 / −0.181 / −0.059** (skip-ish) |
| 05:00–08:30 | +0.071 / −0.051 / −0.071 / −0.034 |
| 08:30–09:30 | −0.210 / +0.140 / −0.170 / −0.037 |
| 09:30–11:00 | +0.040 / +0.005 / −0.140 / +0.009 |
| 11:00–13:30 | +0.073 / +0.041 / −0.016 / −0.044 |
| 13:30–16:00 | −0.165 / +0.085 / +0.009 / −0.077 |

On 1D/4h/15m only, 11:00–13:30 with stop ≥ 10% ADR is +0.231 / +0.346 / +0.178 / +0.099 (watch list, #2).

### (c) Exit: 2R vs 1R vs partials vs bias-candle close

Same trades (stop ≥ 10% ADR), D25 / H24 / F26 / X:

| Exit | All stop-filtered trades | Fills before 11:00 |
|---|---|---|
| 1R target | +0.005 / −0.001 / −0.044 / −0.025 | +0.020 / −0.006 / −0.039 / −0.024 |
| 2R target | +0.009 / +0.042 / −0.058 / −0.016 | +0.027 / +0.041 / −0.063 / −0.009 |
| 3R target | +0.047 / +0.075 / −0.059 / +0.001 | +0.077 / +0.065 / −0.072 / +0.012 |
| Half at 1R, rest 2R, stop to entry | +0.003 / +0.005 / −0.046 / −0.025 | +0.016 / +0.006 / −0.049 / −0.022 |
| 2R, stop to entry at +1R | +0.000 / +0.011 / −0.047 / −0.026 | +0.012 / +0.017 / −0.058 / −0.021 |
| **Hold to bias-candle close** | **+0.092 / +0.046 / −0.036 / +0.009** | +0.111 / +0.069 / −0.030 / +0.013 |
| Time exit 16:00 | | +0.075 / +0.046 / −0.036 / +0.000 |

- **Bias close minus 2R** is positive in every group: +0.083 / +0.004 / +0.018 / +0.025 (ct 2.2 / 0.1 / 0.6 / 1.7). That makes it the default exit for these HTF stacks; it agrees with "let the wick form, trade the body".
- **3R minus 2R** is +0.039 / +0.033 / −0.001 / +0.017 (ct 2.0 / 1.7 / 0.0 / 2.0).
- **Partials and break-even moves** don't beat a plain 2R. 48% of trades that reach +1R come back to the entry before 2R, yet 63–66% still reach 2R.
- No exit makes 2026 positive.

![exits](../results/backtest_tv/report/figures/exits.png)

### (d) The teacher's top-10 claims (`knowledge/ttrades_backtest_hypotheses.md` §3)

Mean net R, A vs B, D25 / H24 / F26 / X. A claim is supported only if A beats B in every group.

| # | Claim | A vs B | Verdict |
|---|---|---|---|
| 1 | B2 continuation beats reversal | −0.016 vs +0.003 / +0.040 vs −0.003 / −0.049 vs −0.065 / −0.098 vs −0.021 | Not supported (mixed) |
| 2 | D10 stale reports lose (lag 0 vs > 15 min) | −0.019 vs +0.076 / +0.033 vs −0.018 / −0.038 vs −0.083 / −0.059 vs −0.009 | Not supported |
| 3 | D1/F1 no trade once the range is used (< 78% vs ≥ 78%, stop filter) | −0.015 vs +0.062 / +0.022 vs +0.102 / −0.027 vs −0.127 / −0.014 vs −0.022 | Not supported (flips in 2026) |
| 4 | E2 2R fits before structure (stop filter) | +0.066 vs −0.015 / −0.073 vs +0.081 / −0.079 vs −0.053 / +0.030 vs −0.031 | Not supported |
| 5 | D9 first half of the setup candle (stop filter) | −0.032 vs +0.084 / +0.032 vs +0.061 / −0.037 vs −0.099 / −0.026 vs +0.005 | Not supported |
| 6 | D7 swift CISD (taken vs held only by `rev_cisd_swift`) | −0.010 vs −0.133 / −0.098 vs −0.139 / −0.006 vs −0.047 / −0.015 vs −0.003 | Not supported. Points the right way on the core symbols, but on all reversal triggers swift vs not swift is mixed (+0.020 vs −0.029, −0.012 vs +0.016, −0.069 vs −0.056, −0.017 vs −0.031). `cont_trigger_v_shape` / `cont_not_inside_consolidation` hold back ≤ 18 triggers: untestable. |
| 7 | A1/A3/A5 NY AM best, nothing after 11:00, no 5m before 09:30 | A1 (index futures): +0.096 vs −0.041 / +0.081 vs +0.035 / −0.150 vs −0.037 / +0.004 vs +0.012 | Not supported. A1 fails in 2026; A3 and A5 are mixed. |
| 8 | E5 trade the body after a small wick (hold to close vs 2R, 1D bias) | +0.010 vs −0.002 / +0.084 vs +0.020 / +0.072 vs −0.006 / +0.008 vs −0.015 | **Points the right way in all 4 groups**, not significant (difference ct 0.3 / 1.2 / 1.4 / 1.0). Absolute R ≈ 0. |
| 9 | D2 objective already hit (taken vs held only by the objective check) | −0.010 vs −0.001 / −0.098 vs +0.128 / −0.006 vs −0.039 / −0.015 vs −0.066 | Not supported |
| 10 | D11 trade the stronger of the pair; B3 reversals want SMT | stronger vs weaker: +0.016 vs +0.002 / +0.018 vs +0.066 / −0.106 vs −0.007 / −0.020 vs +0.030. SMT vs none: −0.087 vs +0.026 / … | Not supported |

Pairs for relative strength and SMT on TradingView: NQ/ES, YM→ES, RTY→ES, GC/SI. SMT is defined in the enrich script's docstring. Still untested (no exported field): bias case / candle number (B1, B6, F7), POI kind (D13), trailing stop (E8).

### (e) Minimum stop and stop sizing

| Minimum stop (fraction of ADR14) | E 2R, all triggers above it (D25 / H24 / F26 / X) |
|---|---|
| none | −0.002 / +0.009 / −0.061 / −0.044 |
| 0.04 | +0.008 / +0.018 / −0.057 / −0.034 |
| 0.10 | +0.009 / +0.042 / −0.058 / −0.016 |
| 0.20 | +0.030 / +0.046 / −0.084 / −0.012 |
| 0.30 | +0.050 / +0.089 / −0.082 / −0.006 |

- **Block stops under 0.04 × ADR14.** This is the only threshold supported in every group and on every symbol. Costs there are 0.15–0.25R per trade, and the stop sits inside the bar noise.
- **Warn under 0.10 × ADR14.** The Databento 1m/3m stacks lose below it: −0.14 / −0.25R under 4%, and about −0.05R at 7–10% (low confidence). On the TradingView stacks, 4–10% is mixed.
- **Skip, don't widen.** In the Databento test, moving sub-10% stops out to 10% ADR still lost (−0.080 / −0.020).
- **Sizing:** a fixed dollar risk per trade, contracts = floor(risk$ / (stop points × $ per point)). Use micros so the dollar risk stays constant as stops vary from 4% to 40% of ADR. Show `cost_r` and warn above 0.04.

![stop size](../results/backtest_tv/report/figures/stop_size.png)

## 4. What to take and what to skip

**Take:** nothing has a demonstrated edge. Treat the companion as a discretionary aid. If you trade its signals, the least-bad way the data supports:
- Stop at least 4% of ADR14, preferably 10%.
- Exit at the bias-candle close, or at 3R, rather than 1R or partials.
- Expect about 0R per trade before your own discretion; 2026 to date was −0.02 to −0.06R.

**Skip:**
- Stops under 4% of ADR14: −0.19 to −0.33R, everywhere.
- Continuation triggers with stops under 10% ADR on CL, SI, 6E and YM (−0.18R). Neutral on NQ/ES/GC.
- Optionally, 02:00–05:00 NY checks: negative in all four groups, but small and found after the fact.

**Watch list (needs a fresh test before anyone trades it):**
- 1D/4h/15m triggers checked 11:00–13:30 NY with stop ≥ 10% ADR: +0.23 / +0.35 / +0.18 / +0.10R.
- Holding to the bias-candle close after a small daily wick.

The TradingView bars go back to 2021, so a 2021–2023 grid on 1D/4h/15m (8 symbols) would be an untouched test of both.

## 5. What the app must compute or show

| Field / indicator | Definition (as computed in `enrich_backtest.py`) | Use |
|---|---|---|
| `adr14` | Mean of the last 14 completed trading-day ranges (day = 18:00–18:00 NY), known at the day's open | Base unit |
| `stop_adr` | \|entry − stop\| / adr14 | **Block below 0.04**; warn below 0.10; show it on every plan |
| `cost_r` | (tick + commission / $ per point) / \|entry − stop\| | Show it; warn above 0.04 |
| Position size | floor(risk$ / (stop points × $ per point)), micros by default | Plan panel |
| Bias-candle close time | Close of the forming bias candle | Default exit option ("trade the body") next to 2R / 3R. Remove the partial and break-even prompts. |
| `adr_used` | (today's high − low so far) / adr14 | Show as context only: the edge it suggested did not hold forward |
| Overnight high / low (18:00–09:30), PDH/PDL position, SMT / relative strength vs partner | As in the enrich script | Informational only. None of them separated winners from losers across groups. |
| Quality checks | As today | Keep advisory. They don't separate winners from losers. |
| Edge statistics | Running per-stack expectancy from the app's own journal, in the four-group format above | The only way to learn whether the watch-list items hold up. Show sample size next to every number. |

## 6. LOW CONFIDENCE: Databento 1m/3m-entry stacks (1h/5m/1m, 1h/15m/1m, 4h/15m/1m, 1D/30m/3m)

The cleaned Databento minutes keep 64.8% (NQ), 57.5% (ES) and 29.3% (GC) of 2025 NY-session minutes. 2024–2025 only, NQ/ES/GC. Full tables: [results/backtest/report/research.md](../results/backtest/report/research.md).

| Rule (one at a time) | n 25 / 24 | E 2R 25 / 24 | ct 25 / 24 |
|---|---|---|---|
| All triggers | 9244 / 8715 | −0.025 / −0.070 | −1.5 / −3.9 |
| Taken | 3134 / 3082 | +0.003 / −0.115 | 0.1 / −4.1 |
| Skip stop < 4% ADR | 4668 / 4164 | −0.138 / −0.251 | −5.8 / −9.8 |
| Skip continuation, stop < 10% ADR | 4622 / 4418 | −0.135 / −0.173 | −5.5 / −7.4 |
| Skip FOMC day | 444 / 466 | −0.155 / −0.171 | −2.0 / −2.0 |
| R\* (S + ADR used ≥ 78% + ON level behind intact) | 1025 / 1059 | +0.140 / +0.110 | 2.5 / 2.0 |

Read these as hypotheses for a rerun on complete 1m data, not as findings. R\* replicated across 2025 and 2024 here, but the same rule failed 2026 and the cross-asset test on the TradingView stacks. The 2025 rule search on these stacks had the same pattern as before: the top 50 averaged +0.001R in 2024, while 682 of 896 strong 2025 losers lost again in 2024. The stop-size and small-stop continuation skips are consistent with the TradingView result (#1).

Variants (footnote; Databento GC only, 2025, 1m-entry stacks): aggressive ≈ baseline (−0.034 vs −0.037 on 1h/5m/1m). Conservative is much worse (−0.20 / −0.22R, median stop 3% ADR). Variants will be rerun on TradingView data.

## 7. Caveats

- One position at a time is per symbol and stack; positions on different stacks of the same symbol can overlap.
- The TradingView backtest walks outcomes on 5m bars. A bar that reaches both the stop and the target counts as a stop, which slightly understates targets hit inside a bar.
- FOMC 2026 dates and the late-2025 CPI/NFP dates were typed from the public release calendars and not checked against an official source. They only affect the FOMC and news rows.
- The watch-list items (#2, #3, E5) were picked after seeing all four groups. Their 2026 and cross-asset numbers are not out-of-sample evidence.
