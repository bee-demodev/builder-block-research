# TTrades engine failure audit: why it loses, what the chart must show

Written 2026-11-13. Research only: no `companion/` code or config was changed. Scope: stacks `1D / 1h / 5m` and `4h / 15m / 1m`, NQ and ES, baseline variant. Inputs are listed in the brief: `results/backtest/<year>/baseline/*.jsonl.gz` and `*.states.csv.gz`, `trades_full.pkl`, and `companion.engine.analyze` re-run at chosen moments. Claim IDs (A3, D10, …) refer to `knowledge/ttrades_backtest_hypotheses.md`; rule references point to `companion/styles/ttrades/rules.md`. Scripts are in the session scratchpad (`s1_days.py` … `s8_extra.py`); charts are in `results/backtest/report/cases/`.

**Data caveat (read first).** The cleaned minute feed holds only 66% (NQ) and 59% (ES) of the 450 NY-session minutes per day in 2025. The raw CSV stores one row per minute, and that row is often a spread or another contract, which cleaning then drops (NQ cleaning report: 36,099 spread rows and 71,743 other-contract rows out of 519,986). Every backtest bar is therefore built from partial minutes, so stops and targets can fall into the gaps. The gaps are visible in the 1m panes of the renders. Before anyone tunes rules on this data, re-download it per instrument.

## Summary

- **On big trend days the engine is absent, not wrong.** On the 50 largest NY-session days of 2025, the default stack took 4 trades in the move's direction and 4 against it; the 4h stack took 6 with and 3 against. It produced 163 with-move triggers and held every one of them at `watch`.
- **Losses come from when and how tight, not from which direction.** Going with the daily bias does not help. Off-window triggers, stops tighter than the entry timeframe's noise, order-block entries and same-day re-entries lose in both 2024 and 2025.
- **What the trader sees hides the worst problems.** 31% of `1D / 1h / 5m` "long/short" verdicts are first shown more than 15 minutes after their trigger. By then price has moved a median 1.74R. One verdict still read `long` after its own plan said `target_reached`.

## 1. Missed moves: 50 biggest NY days of 2025 (25 NQ, 25 ES), 2 stacks

Days are ranked by |NY open (08:30) − close (16:00)| / ADR14 and range from 0.81 to 3.66 ADR. For each day the states, the trigger rows and `analyze(..., direction=move)` at 10:00 and 11:30 were read. The per-day table is in the appendix and in `results/backtest/report/cases/missed_days.csv`.

**What the engine did (100 day×stack cases)**

| Result / root cause (code) | 1D/1h/5m | 4h/15m/1m | Rule that stopped it |
|---|---|---|---|
| Took the move and won (W+), counting days with at least one winning with-move trade | 2 | 4 | — |
| Took the move and lost (W−) | 1 | 1 | — |
| **Large-wick veto on the reversal (WICK)**: "the wick is not small, so it does not read as a reversal candle" | **24** | 5 | `rev_opposing_run_small` Q, 7 c1 (`rules.md:483`), `wick_small_frac` 0.25 |
| **No key level reached (NOLVL)**: the move started from a level the engine does not know (Asia/London high/low, an open) | 8 | 6 | 7.1, key levels = previous candle / swing / FVG only (Q29, `rules.md:788`) |
| **Bias "late", no POI behind the swing (LATE)** | 6 | 10 | case D, `bias_poi_present` / `bias_candle_index_ok` G (`rules.md:309, 364-366`) |
| **Candle 2 closure without a POI, so neutral (NOPOI)** | 4 | 5 | case G (`rules.md:312`) |
| **Continuation blocked because the HTF target was already taken (OBJ)** | 2 | 5 | `cont_objective_open_at_trigger` Q (`rules.md:431`, Q36) |
| Stuck waiting for a setup or entry step (WAIT); on the 4h stack the blocked shadows of these days are mostly OBJ | 0 | 12 | 6 c2–c4 |
| Drift or slow turn (DRIFT) | 3 | 1 | `rev_expansion_into_level`, `rev_cisd_swift` |
| EQ gate broke | 0 | 1 | `cont_eq_respected` G |
| …of these, days where it also **traded against** the move (F/) | 4 | 3 | the reversal path ignores the bias (Q32) |

**Bias at 09:30 against the day's move:** 1D: with 8, against 16, neutral 26. 4h: with 16, against 18, neutral 16. A wrong or absent bias is the normal state on these days, not the exception.

**Blocked with-move triggers on these days:** 58 on the 1D stack (48 had `rev_opposing_run_small` among their blockers) and 105 on the 4h stack (74 had `cont_objective_open_at_trigger`). They "won" 60% at 2R, but that figure is hindsight: the days were chosen because the move happened. The fair test is each veto across all days (2024–2025, NQ+ES, rows blocked by that check alone):

| Veto | Stack | Allowed trades E (n) | Blocked-only E (n) | Verdict |
|---|---|---|---|---|
| `cont_objective_open_at_trigger` | 1D/1h/5m | −0.150 (222) | −0.035 (439) | **blocks better trades than it keeps** |
| `cont_objective_open_at_trigger` | 4h/15m/1m | −0.149 (292) | −0.047 (740) | same, in both years |
| `rev_opposing_run_small` | 1D/1h/5m | +0.035 (361) | −0.041 (518) | weak; blocked rows are +0.14 in 2024 and −0.10 in 2025 |
| `rev_opposing_run_small` | 4h/15m/1m | −0.074 (805) | +0.059 (765) | **counter-productive** |
| `rev_cisd_swift` | 1D/1h/5m | +0.035 (361) | −0.149 (274) | **real filter** (−0.24 in 2024, −0.20 in 2025) |
| `rev_expansion_into_level` | 1D/1h/5m | +0.035 (361) | −0.081 (553) | mild filter |

**Root causes, in order:**
1. **Wick veto (29/100).** On trend days the daily candle often runs into PDH/PDL overnight. By NY that run is more than 25% of the average range, so the engine refuses the Candle 2 exactly where the expansion starts (`missed_2`: NQ 2025-02-27, −2.29 ADR). Across all days the veto earns nothing on 1D and costs money on 4h.
2. **Bias framework says "late" or "no POI" (25/100).** Case D and case G go neutral on the days when the trend is strongest, which is the "three expansion days" stand-aside working as designed (F7). Only a session-level reversal could still trade these days, and the engine has none.
3. **The key-level list is too short (14/100).** In `missed_1` (NQ 2025-10-08, +0.99 ADR) the low that launched the day was the Asia/London low cluster (≈25,027). The engine was waiting for a 1D gap 30.75 points lower and read `no_trade` and `watch` all morning.
4. **The objective veto (7 primary + most of the 12 WAIT cases on 4h).** On a trend day each previous 4h high is taken in turn, so every continuation after the first is vetoed. The population test above shows the veto removes the *better* continuations.
5. Fading the trend (7/100): the reversal path took the other side on 4 + 3 days and won 1 of 7.

## 2. Losers vs winners (taken trades at 2R)

Population: every resolved taken trade on the two stacks, NQ+ES, 2024–2025 (n = 1,561: 464 on 1D/1h/5m, 1,097 on 4h/15m/1m). Sample: 40 losers and 40 winners drawn at random (20 + 20 per stack, seed 7). Extra fields were recomputed from minute bars: ADR used at the check, room left to ADR in R, distance to the previous bias-candle level in R, the daily bias (from the 1D states) for 4h-stack trades, and session highs and lows.

**Medians in the sample (losers / winners):** stop 12.9% / 12.9% of ADR · ADR used 36% / 38% · room to ADR 6.2R / 6.5R · previous candle level 1.35R / 1.20R away · hour 08:30 / 09:30 · lag 0 / 0 min. The typical loser and the typical winner look the same on the chart. The differences live in the tails below.

| Flag | Losers in sample (/40) | Winners in sample (/40) | Population n | E flagged | E rest | Same sign 2024 & 2025? |
|---|---|---|---|---|---|---|
| Outside his windows (5m entry: not 09:30–11:00; 1m entry: not 02–05 or 08:30–11:00) | 32 | 29 | 1,040 | **−0.141** | +0.011 | yes (−0.18 / −0.10) |
| Stop below the entry TF's noise (<10% ADR on 5m, <4% on 1m) | 11 | 6 | 333 | **−0.282** | −0.038 | yes (−0.41 / −0.15) |
| Continuation order-block trigger | 7 | 6 | 212 | **−0.232** | −0.068 | yes (−0.31 / −0.15) |
| Gave back +1R, then stopped | 12 | — | 24% of losers | — | — | — |
| Stopped within 30 min | 9 | — | 28% of losers | — | — | — |
| Continuation path | 17 | 13 | 479 | −0.160 | −0.060 | 2024 only |
| No daily bias | 17 | 7 | 571 | −0.075 | −0.099 | no |
| Against the daily bias | 6 | 17 | 443 | −0.041 | −0.110 | no (against is *better*) |
| Range spent (≥78% ADR or <2R left) | 9 | 5 | 285 | −0.034 | −0.103 | no |
| Previous candle level inside 2R | 25 | 24 | 857 | −0.091 | −0.090 | no |
| Stop just past an Asia/London/PD level | — | — | 807 | −0.07 | −0.11 | no |

**Time of day, fresh triggers only (lag 0):** on 1D/1h/5m, 09:30–13:30 has E **+0.29** (n 41, win 44%), before 09:30 **−0.23** (n 143) and from 13:30 on (including Asia at 18:00+) **−0.21** (n 96). The stack fires 92 trades in the 18:00–24:00 Asia hours (E −0.24, negative in both years). On 4h/15m/1m, 13:30–16:00 is **−0.26** (n 172, both years), against +0.05 for 09:30–13:30.

### The 5 failure modes

| # | Failure mode | Count (evidence) | Rule / missing rule | Corpus |
|---|---|---|---|---|
| 1 | **Wrong clock.** 5m entries before 09:30 and overnight; 1m entries in NY PM | 1,040 of 1,561 taken trades (67%), E −0.14 vs +0.01; 32/40 sample losers | `session_filter_ok` is advisory (9.1, `rules.md:613`, Q18); no pre-9:30 rule for 5m (A5); no PM rule (A3) | A3: "I don't look at New York PM session ever." A5: "prior to 9:30, I want to use the 15-minute candle". C4: Asia/London confirm on 1h/4h |
| 2 | **Stop too tight for the entry timeframe** | 333 trades, E −0.28; 11/40 vs 6/40; 28% of all losers are stopped within 30 min | `stop_buffer = 0`, no minimum stop (8.2, `rules.md:549`) | E7: "give it a little bit of room to sweep if it wants to" |
| 3 | **Continuation order-block entry** (median stop 3–4% ADR) | 212 trades, E −0.23 vs −0.07, both years | OB trigger, `entry_mode = either` (6 c4, `rules.md:413-421`, Q14/Q28) | B4: the 2026 rule *prefers* the OB ("wait for another continuation"). The data says the opposite |
| 4 | **Re-entering the same day.** 2nd, 3rd trade, or after a loss | 40% of losers are the 2nd+ trade of that stack-day; after a same-day loser E −0.18 (n 417); 3rd+ trade −0.17 (1D) / −0.19 (4h) | NOT ENCODED (each trigger stands alone) | F6: "Hit the target. Indices kind of done for today." |
| 5 | **Gave back +1R.** No management after the trade moves | 24% of losers reached +1R first (12/40 in the sample); median loser MFE 0.44R | Fixed 2R exit only (8.3); `cont_newer_protected_low` is reported but never moves the stop (A) | E8: "Our stop losses can only be trailed to new protected swings." E6: partials only when the rest still meets the model |

Checked and **not** failure modes in this data: trading against the daily bias, ADR already spent, the structural level sitting inside 2R (`*_reward_at_least_2r`, E2), and stops sitting on session liquidity. `cont_opened_against_bias_first` on 4h continuations is the reverse of D6 (True −0.28, False −0.03). Stale reports are not a loss cause in the backtest (stale rows E +0.03), because the backtest refills at the later price. They are a display problem (section 3).

## 3. Rendered cases (`results/backtest/report/cases/`)

Each png shows the bias, setup and entry panes. Coloured lines are `Verdict.markup` from `analyze` at the moment shown; orange dotted lines are audit overlays the app does not draw. Faded candles come after `as_of`, and the forming candle is drawn only from minutes before `as_of`.

| File | What the engine shows | What a trader would need and does not get |
|---|---|---|
| `missed_1_NQ_2025-10-08_long.png` | 1D: PDH, PDL, PD EQ, open only. `no_trade`, "nearest key level is a 1D gap 30.75 below". | The Asia and London lows (≈25,027) that were swept at 08:30, the 09:30 open, the ADR used (76% by 10:30), and a separate reason for the neutral bias: an outside day (case F). Nothing on the setup or entry pane shows why there is no trade. |
| `missed_2_NQ_2025-02-27_short.png` | `watch` at c4. A CISD and "Trigger" marker are drawn at 07:50, but no plan is told. | A label on the trigger itself ("blocked: wick 133.5 pts = 39% of the 1D average range; small ≤ 25%"), a wick meter on the forming 1D candle, and "range used 118% of ADR at 10:00". The day then fell another 1.2 ADR, so range used was information, not a stop sign. |
| `loser_1_NQ_2025-09-08_short_ob.png` | `short`, OB entry 23,769, stop 23,781.5 (3.7% ADR), 07:25. | A stop-size warning, a pre-NY clock warning ("5m entry 2 h before the open"), and the Asia/London highs drawn at the stop: the stop was exactly the London high (23,781.5), 7 points under the Asia high (23,788.5); price ran to 23,874 by 10:30. |
| `loser_2_NQ_2025-03-13_short_pm.png` | `short` at 15:15, 4h Candle 4, stop 10.6% ADR. | "NY PM, 45 min to the cash close", "92% ADR used", a countdown to the 4h close (18:00), and the session low just under the target. Price reached +1.87R (19,206) and turned 28 points above the 13:00–15:00 low (19,178.25), with the 19,198 target between them. |
| `stale_1_NQ_2025-08-06_long.png` | `long` at 09:40 with entry 23,070.75. Its trigger bar is **18:25 the evening before**, `plan.outcome = target_reached` at 21:40, last close +3.56R. | A "missed: target already reached" state instead of `long`, and the trigger's age. The backtest scored this as a +2R winner by refilling at 23,159.75. |
| `winner_1_NQ_2025-11-25_long.png` | Fresh 1D Candle 4 continuation at 11:00 off a 1h FVG and the 1D EQ, stop 21% ADR, target above PDH. | Almost everything needed is drawn. Missing: the session levels sitting between entry and target, and the ADR left (54% used). |
| `winner_2_ES_2025-07-25_long.png` | 4h reversal at the previous 4h low at 10:30, stop 12% ADR. | The confluence with the London low (6,401) and the 10:00 4h open is not drawn. The 1m pane shows the data gaps. |

## 4. Chart needs, prioritized

The web UI files are `companion/web/src/components/DecisionPanel.tsx` (verdict, plan, `SessionClock`) and `Charts.tsx` (three panes; `display.ts` handles overlays). The existing "Stale" badge (`store.ts:156` `isStale`) means the *data link* is stale, not the signal. `PlanBlock` already prints "Last close +xR" but does not warn.

| # | Show / compute / warn | Evidence (this audit) | Corpus | Effort |
|---|---|---|---|---|
| 1 | **Signal age and "move already happened".** Trigger time and minutes since; price distance from the entry in R. When `plan.outcome` is `target_reached` or `stopped`, demote `long`/`short` to "missed" or "done" on the panel and the chart. | 31% of 1D-stack verdicts are first shown >15 min late, median 1.74R gone, 59% >1R; `stale_1` reads `long` after `target_reached` | D10; rules Q33 (`rules.md:792`) | S (UI only: `plan.since`, `outcome` and `r_now` already exist) |
| 2 | **His trading windows on the chart.** Shade London 02–05 and NY 08:30–11:00, mark 09:30. Put an "outside his window" banner on the verdict, plus "5m entry before 09:30" and "NY PM". | Failure mode 1: 67% of trades, E −0.14 vs +0.01; fresh 1D-stack 09:30–13:30 +0.29 vs −0.23 / −0.21 outside | A1–A5, inventory #19 | S |
| 3 | **Stop-size warning** in % ADR next to the stop, with a minimum per entry TF (≈10% ADR for 5m, ≈4% for 1m) and an OB-entry flag. | Failure modes 2–3: 333 trades at E −0.28; OB entries −0.23 | E7; rules 8.2 | S (needs ADR, item 4) |
| 4 | **ADR and range used.** ADR14, today's range so far as a % of it, and projection lines (day low + ADR, day high − ADR). Show it as information, not as a gate. | `missed_2` hit 118% at 10:00 and went 1.2 ADR further; "range spent" did not separate losers (E −0.03 vs −0.10) | D1, F1 (16/47 streams); inventory #27; rules Q36 | M (engine has no ADR; the backtest's `daily_range` can be reused) |
| 5 | **Session liquidity on every pane.** Asia H/L, London H/L, midnight / 08:30 / 09:30 opens, PDH/PDL on the intraday panes. Then let the reversal path use them as key levels. | NOLVL 14/100 missed cases; `missed_1` launched from the Asia/London low 30.75 points above the engine's nearest level | inventory #23, #24; rules Q29 | M (draw) + M (engine key levels) |
| 6 | **Why a drawn trigger is blocked, on the trigger.** A label such as "watch: wick 39% of avg range (small ≤ 25%)", plus a wick meter on the forming bias candle with the small/large thresholds, so a blocked c4 reads as a "Potential Candle 2". | WICK 29/100 and OBJ 7/100 primary causes; triggers are drawn at c4 with no plan (`missed_2`); both vetoes fail the population test | D5, B2; inventory #11 | S–M |
| 7 | **Same-day trade log and a "done for today" warning.** Trades taken today on this stack and their results; warn after a loss or after the target is hit. | Failure mode 4: 40% of losers are the 2nd+ trade of the day; after a loss E −0.18 | F6 | S (UI state) |
| 8 | **HTF candle separators and countdowns** to the bias and setup closes, with the "¾ of the candle used" mark. | `loser_2` entered with 45 min of NY left; the 4h stack loses after 13:30 (−0.26) | A7, D9; inventory #2, #21, #29 | S |
| 9 | **Management cue at +1R**: draw the newer protected swing (`cont_newer_protected_low` already computes it) and the R it would lock. | Failure mode 5: 24% of losers were +1R first | E8, E6 | M |
| 10 | **NQ/ES relative strength and SMT pane.** Not tested here. | Rules Q23 | D11, B3; 46/47 streams | L |

Rules-side follow-ups, for the trader to decide (not changed here): demote `cont_objective_open_at_trigger` to advisory (it blocks the better continuations in both years and both stacks); re-test `rev_opposing_run_small` with `wick_small_frac` 0.35–0.5 or the body yardstick; keep `rev_cisd_swift`; run variants with `session_filter_role = quality` plus a 09:30 start for 5m entries, a minimum stop, and one trade per stack-day.

## Appendix: the 50 days

Codes: W+ took the move and won; W− took it and lost; F/ also traded against the move; other codes as in section 1. Bias is the stack's bias at 09:30.

| sym | day | NY move (ADR) | 1D bias | 1D/1h/5m | 4h bias | 4h/15m/1m |
|---|---|---|---|---|---|---|
| NQ | 2025-01-07 | −0.84 | bull | W+ | bull | F/DRIFT |
| NQ | 2025-01-15 | +1.06 | bear | F/DRIFT | bull | WAIT |
| NQ | 2025-02-21 | −1.73 | neut | F/WICK | bull | WAIT |
| NQ | 2025-02-24 | −1.17 | neut | F/NOPOI | neut | WAIT |
| NQ | 2025-02-25 | −0.93 | bear | LATE | bear | NOPOI |
| NQ | 2025-02-27 | −2.29 | neut | WICK | bull | NOPOI |
| NQ | 2025-03-03 | −1.67 | neut | WICK | neut | W− |
| NQ | 2025-03-28 | −0.94 | bear | LATE | neut | NOLVL |
| NQ | 2025-04-02 | +1.00 | bull | F/WICK | bear | NOPOI |
| NQ | 2025-04-04 | −1.26 | bear | OBJ | neut | LATE |
| NQ | 2025-04-09 | +3.57 | bear | WICK | bull | NOPOI |
| NQ | 2025-05-19 | +0.88 | neut | WICK | bear | OBJ |
| NQ | 2025-07-31 | −2.03 | bull | WICK | neut | LATE |
| NQ | 2025-08-01 | −0.87 | neut | NOPOI | bear | LATE |
| NQ | 2025-08-04 | +0.86 | bear | NOLVL | bull | OBJ |
| NQ | 2025-08-06 | +0.93 | bear | W+ | neut | WICK |
| NQ | 2025-08-19 | −0.93 | neut | NOLVL | neut | LATE |
| NQ | 2025-08-22 | +0.96 | neut | WICK | bull | WAIT |
| NQ | 2025-10-01 | +0.88 | neut | WICK | bear | WAIT |
| NQ | 2025-10-08 | +0.99 | neut | NOLVL | neut | LATE |
| NQ | 2025-10-10 | −3.34 | neut | WICK | bear | NOLVL |
| NQ | 2025-11-06 | −1.37 | neut | NOLVL | neut | WAIT |
| NQ | 2025-11-13 | −1.11 | neut | NOPOI | bear | F/EQ |
| NQ | 2025-11-14 | +0.84 | bear | WICK | bear | NOLVL |
| NQ | 2025-11-20 | −2.05 | bull | WICK | bear | W+ |
| ES | 2025-01-10 | −0.86 | neut | W− | neut | F/WAIT |
| ES | 2025-02-13 | +0.91 | neut | OBJ | bear | OBJ |
| ES | 2025-02-21 | −1.81 | neut | NOLVL | bull | WAIT |
| ES | 2025-02-24 | −1.01 | bear | LATE | neut | WAIT |
| ES | 2025-03-28 | −0.94 | bear | LATE | neut | LATE |
| ES | 2025-03-31 | +0.97 | bear | WICK | bear | WICK |
| ES | 2025-04-02 | +1.08 | bull | LATE | bear | NOLVL |
| ES | 2025-04-08 | −1.58 | neut | WICK | bear | W+ |
| ES | 2025-04-09 | +3.66 | bear | WICK | bull | NOLVL |
| ES | 2025-05-21 | −0.85 | neut | NOPOI | bear | WICK |
| ES | 2025-07-15 | −1.01 | bull | WICK | bull | WAIT |
| ES | 2025-07-31 | −1.73 | bull | WICK | neut | LATE |
| ES | 2025-08-01 | −0.82 | neut | NOLVL | bear | LATE |
| ES | 2025-08-04 | +0.90 | bear | DRIFT | bull | OBJ |
| ES | 2025-08-22 | +1.15 | neut | WICK | bull | WAIT |
| ES | 2025-09-15 | +1.26 | neut | NOLVL | neut | WAIT |
| ES | 2025-09-22 | +0.81 | bull | LATE | bear | LATE |
| ES | 2025-10-01 | +0.88 | neut | WICK | bear | OBJ |
| ES | 2025-10-10 | −3.58 | neut | WICK | bear | NOLVL |
| ES | 2025-10-16 | −0.85 | neut | WICK | bull | WICK |
| ES | 2025-11-06 | −1.19 | bull | NOLVL | bull | NOPOI |
| ES | 2025-11-13 | −1.29 | neut | DRIFT | neut | LATE |
| ES | 2025-11-14 | +0.84 | bear | WICK | bear | WICK |
| ES | 2025-11-20 | −2.07 | neut | WICK | neut | W+ |
| ES | 2025-12-17 | −1.48 | bull | WICK | bull | W+ |

Method notes: the cause code comes from the `analyze(direction=move)` step and its detail at 11:30 NY, or from the trades when a with-move trade was taken. Sessions use NY time; the "trading day" opens at 18:00. All E figures are net of costs at a fixed 2R, measured from the first report, as `backtest.py` defines them.
