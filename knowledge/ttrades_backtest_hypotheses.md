# TTrades backtest hypotheses: the teacher's claims, made testable

Written 2026-11-13 to check the bar-by-bar backtest of the Trading Companion's TTFM rule engine (NQ / ES / GC, 2024 and 2025, nine stacks, variants `baseline`, `aggressive`, `conservative`, `latest_trigger`, `no_clean_wait`) against what TTrades teaches. Three parts: testable claims (1), what he draws versus what the app draws (2), and the ten claims that matter most for P&L (3). This is research only: no code or config was changed.

## 0. How to read this

**Citations.** Each claim has one verbatim quote and its file. Path prefixes:

| Prefix | Path |
|---|---|
| `TR/` | `knowledge/ttfm_video_corpus/transcripts/` (older videos and every `livestream_*` transcript) |
| `IN/` | `knowledge/ttfm_video_corpus/intake_2026-11-12/transcripts/` (2026 videos) |
| `P/` | `artifacts/ttrades/pages/` (his written posts) |
| `W/` | `knowledge/second_brain/wiki/playbooks/` (distilled notes; the quote is the transcript's, timestamp as the note gives it) |
| `LS/` | `knowledge/ttfm_video_corpus/livestream_synthesis/` (counts across 47–49 live streams) |

Transcripts are auto-captions, so the quotes keep caption errors. Every quote cited to a `TR/`, `IN/` or `P/` file was checked against that file's text for this document. Quotes cited through `W/` come from the wiki notes and were not re-checked; the same goes for the `LS/` synthesis wording, which is labelled where it is a paraphrase. **INFERRED** marks a reading of mine, not his words.

**App column.** It names the `rules.md` section or `config.json` key, the criterion key and its class: G = gate (kills the path), S = step, Q = quality (blocks `long`/`short` and keeps `watch`), A = advisory (shown only). NOT ENCODED means nothing in `companion/styles/ttrades/` checks it.

**Backtest facts that every test below depends on** (read in `companion/tools/backtest.py` and `scripts/analyze_backtest.py`):

- The fill is the open of the first minute bar after `check`, one tick worse. So every `net_*`, `first_*`, `mfe_r`, `mae_r` is measured from the **first report**, not from the trigger bar. `lag_min` is how stale that report was. `analyze_backtest.py` defines `fresh = lag_min <= 0`.
- `session`, `hour`, `minute`, `weekday` describe `check`, not the trigger bar. The rows also carry `trigger_open` / `trigger_close`, which let you bucket by trigger time instead.
- `bias_open` / `bias_close` are timestamps, not prices. `r_bias_close` is the R at the close of the bias candle ("trade the body" exit).
- `structural_targets` is `Verdict.targets`. With the default `target_mode = r_multiple` that is only the 2R price, **not** the structural levels. Tests that need the previous bias candle's high/low have to recompute them from bars or rerun with `target_mode = structural`.
- Gate failures leave no row, because a dead path has no trigger. Only Q failures produce shadow rows (`taken = false`, key in `blocking`). **A gate cannot be judged from these rows. You need a variant that turns the gate into a quality check.**
- `analyze_backtest.py` flattens `criteria` into `c:<key>` columns. "E" below means expectancy, the mean `net_2r`. "Win" means the share of resolved rows with `first_2r == "win"`. He quotes about 34% as the break-even win rate at 2R (`TR/livestream_20260729_..._xraklbjhw5k.txt`: "You need, what, a 34% win rate to break even"), so 34% plus costs is the bar every bucket has to clear.

**Standard test.** Split the rows, report n, E and Win per group with a bootstrap 95% interval, and run the same split on both years and all three symbols. A claim counts as "supported" only when the sign agrees in 2024 and 2025. With roughly 60 splits below, expect a few false positives at p < 0.05.

---

## 1. Testable claims

### A. Time of day, sessions, kill zones, day of week

**A1. New York AM is where index range is made.**
- Claim: for indices, most of the day's range comes in NY AM, so NY AM entries should reach targets more often. `P/kill_zones_explained_best_trading_sessions_for_entries.md:49`: "a large portion of the daily range is created during the New York AM session".
- App: NOT ENCODED as a filter. `kill_zones` holds 02:00–05:00 and 08:30–11:00 (config.json); `session_filter_ok` is A (`session_filter_role = advisory`).
- Test: taken rows on NQ and ES, group by `session`. Prediction: `ny_am` has the highest E and Win and the shortest `minutes_2r`. Use GC as a control (gold is not "indices").

**A2. Kill zones beat the rest of the clock.**
- Claim (2025 post): setups inside kill zones are higher probability. `P/kill_zones_explained_best_trading_sessions_for_entries.md:83`: "High probability setups tend to occur inside kill zones rather than outside of them."
- Counter-claim (2026): the clock doesn't matter, the HTF wick does. `IN/how_to_trade_london_using_ttrades_fractal_model.txt`: "I don't really care too much about kill zones". Repeated live: `TR/livestream_20260310_..._wm1s7uivq08.txt`: "I don't really care about kill zones. I'm just caring about the higher timeframe candle".
- App: `session_filter_ok`, A by default, Q when `session_filter_role = quality`; it applies only when the entry TF is under 60 min (`kill_zone_applies_below_minutes`).
- Test: taken rows with entry TF < 1h, split by `c:session_filter_ok`. If the 2026 stance is right, E is the same either way. This test decides whether to switch `session_filter_role` back to quality.

**A3. No New York PM, nothing after about 11:00.**
- Claim: he never trades NY PM; the range is made and the candle has no time left. `TR/livestream_20260506_..._eipm_d8rrsq.txt`: "I don't look at New York PM session ever." Window end: `TR/reversal_sequence_ttrs_how_to_blend_pd_arrays.txt`: "I'm going to focus on 8:30 to 11 for my trading".
- App: NOT ENCODED (the PM triggers stay `long`/`short`). The panel's session clock does say "His window closed at 11:00" (`companion/web/src/decision.ts` `checkpointText`).
- Test: `session in {ny_lunch, ny_pm, after_hours}` vs `ny_am`, intraday stacks only. Prediction: E is lower after 11:00.

**A4. Asia is only for two situations.**
- Claim: trade Asia only after a completed HTF reversal (an expansion day is expected) or when price opens near a draw. Otherwise skip it. `IN/how_to_trade_asia_using_ttrades_fractal_model.txt`: "Now there are only two times I really look to trade Asia".
- App: NOT ENCODED. Asia is also missing from `kill_zones`, so every Asia trigger reads "outside".
- Test: `session == "asia"`, split by path. Prediction: continuation rows (the expansion day already confirmed) beat reversal rows. Testing the "near a draw" half needs the distance to PDH/PDL at entry, which has to be recomputed from bars.

**A5. Before 9:30, 5-minute entries get swept; use 15m.**
- Claim: pre-market 5m entries "get swept out"; before 9:30 he wants a 15m structure. `W/ttfm-entry-timing-and-order-type.md` (rule 11, from `IN/let_the_wick_form_trade_the_body_stop_getting_stopped_out.txt` @09:10): "prior to 9:30, I want to use the 15-minute candle".
- App: NOT ENCODED. Only `reversal_entry_tf_confirm_window` (08:30–11:00, 1D bias, reversal path) touches the clock.
- Test: stack `1D / 1h / 5m`, split by `trigger_close` before or after 09:30 NY. Compare E and the `mae_r` distribution (more stop-outs before 9:30?). Then compare with `1D / 4h / 15m` rows in the same hours.

**A6. The 9:30 open itself and its first 3–5 minutes are not entries.**
- Claim: he waits out the 9:30 print and the first few minutes. Stated as a skip condition (`LS/s1_prep_session.md` §4 item 12, 2026-03-25 stream); this is the synthesis wording, not a verbatim quote: "The 9:30 open itself, and the first 3–5 minutes".
- App: NOT ENCODED.
- Test: `hour == 9 and minute in 30..35` vs the rest of `ny_am`. Prediction: lower E and a larger share of `minutes_to_stop` under 15.

**A7. 10:00 is a turning and exit point, because several HTF candles open there.**
- Claim: 10:00 matters because the 15m, 30m, 1h and 4h candles close and open together, not because of macros. `W/ttfm-exits-and-trade-management.md` (from `IN/using_time_based_exits_for_trading_expansions_ttfm.txt` @07:41): "That's why 10:00 a.m. is so important. Not because of macros, it's because multiple higher time frame candles are closing and opening."
- App: NOT ENCODED, apart from the panel clock (the 10:00 checkpoint).
- Test: for triggers between 09:30 and 10:00, compare E at 2R with the R at 10:00. The R at 10:00 is not a field, so it needs the minute bars (an extra simulation output, `r_at(10:00)`). Second test: do triggers checked at 10:00–10:15 beat those at 09:45–10:00?

**A8. The daily wick should form early (London or early NY).**
- Claim: on a daily bias the high or low of day should form "early New York or before New York"; entries are taken early in the day. `TR/wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt`: "we want to see this high day form early New York or before New York".
- App: `daily_wick_deadline = 11:00` feeds `rev_formed_early` (Q, reversal path only). On the continuation path NOT ENCODED.
- Test: reversal rows on 1D-bias stacks: shadow rows blocked only by `rev_formed_early` vs taken rows. Prediction: blocked rows have lower E. Continuation rows: bucket `hour` at check; prediction: E falls through the day.

**A9. Monday is traded only when Friday was a reversal.**
- Claim: Monday is usually an opposing run or a consolidation; he trades it only after a Friday reversal (Candle 2) day. `TR/livestream_20260803_..._nesscpmzwr0.txt`: "The only time I'll look to trade Mondays is when we have a reversal day on Friday". Also `TR/livestream_20260505_..._i2hhhhwdapq.txt`: "Usually Monday is an opposing run to the weekly range or some sort of consolidation."
- App: NOT ENCODED (no day-of-week logic).
- Test: `weekday == 0` vs Tue–Thu, all stacks. Prediction: Monday E is lower. Part two needs the bias case of Friday's daily candle (A = Candle 2 closure). The engine computes it in `bias.py` but the backtest does not export it. **Add a `bias_case` / `bias_candle_number` field.** On 1D-bias continuation rows, Monday with bias Candle 3 is exactly "Friday was a C2".

**A10. The week's high or low forms Monday–Tuesday, and Wednesday–Thursday expand.**
- Claim: in the classic expansion week the weekly extreme forms Mon/Tue and the following days carry the expansion. `P/weekly_profile_for_daily_bias_classic_expansion.md:30`: "Monday or Tuesday forms the high or low of the week".
- App: NOT ENCODED (`rules.md` 4.3: "Weekly profile ... not encoded").
- Test: continuation rows by `weekday`. Prediction: Wed/Thu best. Hit time of the weekly extreme needs weekly bars (extra).

**A11. Friday reversals come only after the objective is met; otherwise Friday "caps" the week.**
- Claim: `P/weekly_profile_tgif_setup.md:80`: "Friday reversals happen after objectives are met, not before."
- App: NOT ENCODED.
- Test: `weekday == 4` split by path. Prediction: Friday reversal rows are profitable only when the previous bias candle's high/low (the objective) was already taken. That flag is `c:cont_objective_open == False` on the continuation side; for reversal rows it has to be recomputed. Friday continuations should show lower `mfe_r` than Tue–Thu.

**A12. Avoid the first trading day of a new month.**
- Claim: `TR/livestream_20260803_..._nesscpmzwr0.txt`: "I don't like to do too much on the first day of the month just because you can get some weirder things occurring."
- App: NOT ENCODED.
- Test: derive `first_session_of_month` from `check`. Prediction: lower E. The sample is small (about 12 days a year), so treat any result as a weak hint.

### B. Setup type

**B1. Only Candle 3 and Candle 4 are traded as continuations; Candle 5+ is a new phase.**
- Claim: `TR/wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt`: "my fractal model only looks for candle 3 and four, because after that, you can get caught in a new phase of price".
- App: `bias_candle_index_ok` (G), `rules.md` 3.3 and 5.2 case D.
- Test: it is a gate, so no Candle 5 rows exist. Run a variant that lets case D through as Q, then compare. Within the taken rows, Candle 3 vs Candle 4 needs the exported `bias_candle_number` (see A9). Prediction: Candle 3 ≥ Candle 4.

**B2. Continuation (Candle 3/4) beats trading the reversal candle (Candle 2).**
- Claim: he prefers the continuation, and reversal days need more confirmation. `W/ttfm-smt-and-psp.md` (from `IN/how_to_use_smt_divergence_ttrades_fractal_model.txt` @05:15): "I prefer to look for a continuation in candle three". Older: `TR/trading_candle_3.txt`: "Don't try to trade candle twos that expand a ton".
- App: both paths fire `long`/`short`. The reversal path trades the in-candle CISD (`rules.md` 7). His official indicator labels that same event "Potential Candle 2", a heads-up rather than a model (`W/ttfm-indicator-full-guide.md` rule 2).
- Test: `path == "continuation"` vs `"reversal"` per stack, symbol and year. Prediction: continuation E > reversal E. **This is the single biggest structural split in the data** (see section 3).

**B3. A Candle 2 trade wants SMT with it.**
- Claim: `TR/easy_daily_bias_mechanical_framework.txt`: "If I'm going to be trading a candle too, I do prefer to have SMT paired with it".
- App: NOT ENCODED (`rules.md` Q23; single symbol per read).
- Test: needs a second symbol. NQ and ES are both in the run, so for each NQ reversal row, check from ES minute bars whether ES failed to take the same key level (reversal SMT). Prediction: reversal rows with SMT have higher E. **INFERRED feasibility**: the saved `data/databento/bars/{es,nq}_minute.csv` make this computable offline.

**B4. Wait for a continuation order block instead of entering on the first CISD (2026 rule) — or take either (playbook rule).**
- Claim A (2026): `TR/the_only_trading_strategy_you_need_for_2026.txt`: "we're not going to enter on that change in the state of delivery. We're going to wait for another continuation". Claim B (older): `TR/fractal_model_fundamentals.txt`: "look for a change in the state of delivery in candle 2. And with that, I can take any entry".
- App: `entry_mode_continuation` / `entry_mode_reversal` = `either` (trader answer, Q14); `entry_either_pick = first`.
- Test: `trigger_kind == "cisd"` vs `"order_block"` within `baseline`; then compare variants `aggressive`, `conservative`, `latest_trigger` per stack. Prediction (2026 rule): `conservative` has fewer trades and a higher E. Watch `risk` too: the order-block stop is tighter.

**B5. Take the first continuation; later ones are chasing.**
- Claim: `TR/trading_candle_3.txt`: "I like to trade that first continuation instead of the further continuations because I feel like I'm chasing".
- App: `entry_either_pick = first`, and `cont_entry_window_open` (Q) limits the trigger to setup Candle 3 (Candle 4 after a strong Candle 3).
- Test: `baseline` vs `latest_trigger`. Prediction: `first` wins on E, `latest` wins on `risk` (a smaller stop). Shadow rows blocked by `cont_entry_window_open` should have lower E than taken rows.

**B6. Candle 4 only after a strong Candle 3.**
- Claim: `TR/candle_2_closure_foundation.txt`: "If candle 3 closes below candle 2's low, we can look for candle 4 to continue lower as well".
- App: bias case B (`rules.md` 3.7, 5.2); setup entry window.
- Test: needs `bias_case` (A9). Prediction: case B (strong C3 → C4) is not worse than case A. Case C (a Candle 3 closure → C4) is the weakest.

**B7. Bias Candle 2 that already expanded: only the conservative entry.**
- Claim: `TR/trading_candle_3.txt`: "I'm going to demand a continuation on the lower time frame".
- App: `bias_c2_not_expanded` (A). When it is False, the CISD trigger is disallowed (`rules.md` 6, stage c1).
- Test: continuation rows split by `c:bias_c2_not_expanded`. Prediction: False rows (already expanded) have lower E even with the order-block entry.

**B8. The setup Candle 2 body should agree with the direction.**
- Claim: `TR/ttrades_scalping_model_simple_day_trading_strategy.txt`: "this alone I would not trust as a candle 2 closure as it is a bearish candle".
- App: `cont_setup_closure_body_aligned` (Q, `setup_body_alignment_required = true`).
- Test: shadow rows whose only block is `cont_setup_closure_body_aligned` vs taken rows. Prediction: blocked rows lose.

**B9. Failure to manipulate: no opposite CISD at the level means breakout, then trade the continuation.**
- Claim: `W/ttfm-daily-bias-invalidation-and-intraday-reversals.md` rule 21 (from `IN/how_to_trade_breakouts_failure_to_manipulate.txt`): "without that higher timeframe reason, you are just blindly trading breakouts".
- App: partly. The continuation path survives the previous high/low being taken (`objective_open_role = advisory`), but no breakout state exists.
- Test: continuation rows with `c:cont_objective_open == False` (the level was taken before the check) — their E vs rows with it True. Also see F1.

### C. Timeframe stacks

**C1. Daily bias is his main frame; the reversal path should not be framed from a bias below 4h.**
- Claim: `TR/easy_daily_bias_mechanical_framework.txt`: "I don't prefer to go below the 4hour time frame as it just becomes a bit more difficult".
- App: every stack runs both paths; nothing blocks reversals on a 1h bias.
- Test: reversal rows on `1h / 5m / 1m` and `1h / 15m / 1m` vs 4h-and-above bias stacks. Prediction: the 1h-bias reversal E is the worst.

**C2. Stated stacks beat unstated ones.**
- Claim: the stacks he names (`rules.md` 4.2). `1h / 5m / 1m` is not among them (5m:1m is not a pair he states). Flexibility: `TR/ttrades_swing_trading_model_simple_strategy.txt`: "You don't have to use this defined time frame alignment. If things are a bit messy, you can move up one time frame".
- App: `stack_pairing_stated` (A); `block_unstated_stacks = false`.
- Test: E for `1h / 5m / 1m` vs `1h / 15m / 1m` (the same bias and entry TF; only the setup TF differs). Prediction: the stated stack is better.

**C3. He alerts on and trades the Daily–Hourly and 4H–15m models.**
- Claim: he alerts on HTF models only (Daily-Hourly, 4H-15m). `W/ttfm-indicator-full-guide.md` rule 11: "I do not use the Early CISD alerts because I prefer to wait for alerts on the valid model formation".
- App: all nine stacks are equal.
- Test: rank the nine stacks by E, PF and max drawdown per year. Prediction: `1D / 1h / 5m`, `1D / 4h / 15m` and `4h / 15m / 1m` sit in the top half. **INFERRED**: no source ranks the stacks by expectancy.

**C4. The confirmation timeframe depends on the session (Asia 1h/4h, London 15m–30m/4h, NY 5m–15m/1h).**
- Claim: `W/ttfm-daily-bias-invalidation-and-intraday-reversals.md` rule 4 (from `IN/intraday_reversals_how_to_confirm_high_or_low_of_day_daily_profile.txt` @05:23): "I generally ... don't use hourly candle two closures earlier into the day".
- App: partial. `reversal_entry_tf_confirm_bias = ["1D"]` plus `reversal_entry_tf_confirm_window` (`rules.md` Q19).
- Test: within the 1D-bias stacks, cross `session` × setup TF (`1D/1h/5m`, `1D/30m/3m`, `1D/4h/15m`). Prediction: the 4h-setup stack wins in `asia` and `london`, and the 1h- and 30m-setup stacks win in `ny_am`.

**C5. Swing stacks (weekly or monthly bias) suit traders who can't watch the screen.**
- Claim: 9-5 traders use weekly bias → daily swing → 1D/1h model, checking at each hourly close. `W/ttfm-sessions-asia-london-ny.md` rule 22 (from `IN/how_to_trade_with_a_9_5_job_ttrades_fractal_model_explained.txt`).
- App: stacks `1W / 1D / 1h`, `1M / 1D / 1h`, `1W / 4h / 15m`.
- Test: E, trade count and `lag_min` tolerance. Prediction: E stays positive even for rows with `lag_min` up to 60. That is the point of the hourly check.

### D. Filters

**D1. ADR: continuation past PDH/PDL needs range left.**
- Claim: `P/how_to_use_average_daily_range_adr_with_pdh_pdl_no_more_fakeouts.md:63-65`: "You are not expecting continuation because PDH or PDL was taken. You are expecting it because there is still range available and a target left to reach." Late in the range: `IN/how_to_use_average_daily_range_adr_with_pdh_pdl_no_more_fakeouts.txt`: "That's when I'd want to wait for a new daily candle, so I have new range".
- App: NOT ENCODED (no ADR in the engine; `rules.md` Q36). The backtest records `adr14` only.
- Test: needs the forming day's range at `check` from bars: `adr_used = (day high so far − day low so far) / adr14`. Bucket it as <0.5, 0.5–0.78, >0.78 (his examples: 50% valid, 78% and 91% not). Prediction: E falls sharply above about 0.78. A rough first pass without extra data: bucket `risk_adr`. Large stops leave 2R outside the day's range, so prediction: E falls as `risk_adr` grows.

**D2. "Already hit the objective" ends the continuation.**
- Claim: `TR/why_your_continuations_fail_order_blocks_cisd_explained.txt` @03:20: "number three is a higher time frame target has already been taken". Live (21/49 streams per `LS/s1_prep_session.md`): `TR/livestream_20260722_..._g1iidq3raky.txt`: "Hit the target. Indices kind of done for today."
- App: `cont_objective_open_at_trigger` (Q, `objective_at_trigger_role`); `cont_objective_open` (A, `objective_open_role = advisory`).
- Test: (a) shadow rows blocked only by `cont_objective_open_at_trigger` vs taken rows. (b) Taken rows split by `c:cont_objective_open` (target taken between the trigger and the check). Prediction: both "taken" groups have lower E.

**D3. Equilibrium: the correct half of the previous candle must hold (upper half for longs).**
- Claim: `TR/equilibrium_for_expansions.txt`: "I'm looking for the upper half to respect for price to trade higher and the lower half to respect for price to trade lower". Soft form: `W/ttfm-daily-bias-invalidation-and-intraday-reversals.md` rule 13 (from `IN/trading_the_invalidation_of_daily_bias.txt` @09:31): "it's not an all or nothing thing".
- App: `cont_eq_respected` (G, zero tolerance `eq_tolerance_frac = 0`); `respect_level_mode = auto`.
- Test: it is a gate, so there are no failing rows. Run variants with `eq_tolerance_frac` 0.05 and 0.1 and compare E with the extra trades. A second variant can test the 2026 EQ selector (close side instead of wick size; `W/ttfm-ranges-adr-dealing-range-eq.md` rule 14), but that selector needs a code change before a variant can run it.

**D4. Premium/discount of the dealing range: no shorts at or below 25%.**
- Claim: `W/ttfm-ranges-adr-dealing-range-eq.md` rule 8 (from `IN/understanding_dealing_ranges_in_trading_get_better_risk_reward.txt` @11:08): "As I get to 25% of the range or lower, that is where I'm not really looking for shorts."
- App: NOT ENCODED.
- Test: needs the dealing range at entry: from the swing traded away from to the swing that made it, computed from bias- or setup-TF bars. Prediction: shorts in the bottom quarter and longs in the top quarter (the mirror is INFERRED) lose.

**D5. Small wick supports expansion; large wick does not.**
- Claim: `TR/ttrades_fractal_model_trading_candle_2.txt`: "Small wick supports expansion. Large wick doesn't support expansion".
- App: `rev_opposing_run_small` (Q; `wick_small_frac = 0.25`, `wick_large_frac = 0.5`, `wick_yardstick = avg_range`). Continuation path: NOT ENCODED for the forming candle; `cont_opened_against_bias_first` is A.
- Test: reversal shadow rows blocked by `rev_opposing_run_small` vs taken rows. For continuation rows, compute the forming bias candle's opposing run at `check` from bars and bucket it. Prediction: small wick → higher E and higher `r_bias_close`.

**D6. The wick should come first: open against the bias, then turn.**
- Claim: `TR/easy_daily_bias_mechanical_framework.txt`: "When price opens and makes a low first, that is bullish".
- App: `cont_opened_against_bias_first` (A).
- Test: continuation rows split by `c:cont_opened_against_bias_first`. Prediction: True has higher E. The test is free and the class can be promoted if it holds.

**D7. Swift CISD (1–3 candles) vs slow (consolidation).**
- Claim: `TR/why_your_continuations_fail_order_blocks_cisd_explained.txt`: "I prefer 1 2 maybe three. If it takes longer than that, a lot of times it's just taking too long". Live: more than about 20 minutes or two candles means consolidation (`LS/s1_prep_session.md` §4 item 13).
- App: `cisd_max_bars = 3`; `cont_entry_cisd_swift` (A), `cont_trigger_v_shape` (Q), `cont_not_inside_consolidation` (Q), `rev_cisd_swift` (Q); `wait_for_clean_continuation = true`.
- Test: shadow rows blocked by each key vs taken rows; then `baseline` vs `no_clean_wait`. Prediction: slow and consolidation rows lose. Earlier evidence: in the 2025 1D/1h/5m sweep these checks cut continuation trades from 27 to 6 (`rules.md` Q35–37). That sample is tiny; the multi-symbol, two-year run should confirm or refute it.

**D8. No continuation formed while running short-term highs or lows.**
- Claim: `TR/why_your_continuations_fail_order_blocks_cisd_explained.txt`: "the continuation forms at the same time that we are taking out highs in a range or a short-term target is taken".
- App: `cont_trigger_clear_of_liquidity` (Q).
- Test: shadow rows blocked by it vs taken rows.

**D9. Enter early in the HTF candle (first half; never after ¾).**
- Claim: `IN/when_to_take_entries_for_trading_expansions_time_range.txt`: "the best way to think about it is in the first half if you want to make it mechanical" and "We've already used 3/4 of this higher time frame candle, so there's not much time left".
- App: `cont_entry_early_in_candle` (Q, `entry_latest_candle_frac = 0.75`). Reversal path: NOT ENCODED.
- Test: for 1h-setup stacks, `minute` at check gives the position inside the setup candle directly. Bucket it 0–29, 30–44, 45–59. Prediction: E falls with each bucket, and 0.5 beats 0.75 as the cut-off. Apply the same buckets to reversal rows (unencoded). For 4h setups use `(hour − 18) mod 4`.

**D10. A stale signal is a different trade (late in the move).**
- Claim: enter "on the close". `TR/fractal_model_fundamentals.txt`: "enter short on the close, put my stop on this high, and then look for 2R". Live: chasing after the target or "at the lows after the move" is a skip (`LS/s1_prep_session.md` §4 item 11).
- App: NOT ENCODED (`rules.md` Q33: the verdict never expires).
- Test: bucket `lag_min` as 0, 1–15, 15–60 and >60, or use `fresh`. Prediction: E falls with lag. **This measures the gap between a live trader acting at the report and the engine's paper trigger.**

**D11. SMT and relative strength: trade the strongest long and the weakest short, never the laggard.**
- Claim: `TR/livestream_20260319_..._qv6ux_z8vra.txt`: "I just don't really trade the lagging asset, generally speaking, because it's just so much slower". SMT is confluence only: `W/ttfm-smt-and-psp.md` rule 3 (from `IN/how_to_use_smt_divergence_ttrades_fractal_model.txt` @07:31): "I do not care about that SMT because I'm not finding SMT and then applying a framework to it".
- App: NOT ENCODED.
- Test: on days when NQ and ES both have taken rows in the same direction, rank them by % change from the daily open at check (from bars). Prediction: longs on the stronger symbol and shorts on the weaker one have higher E. This needs a join across symbols plus bars. YM is not in the data.

**D12. High- vs low-resistance liquidity: target the untaken failure swings, stop behind the swept ones.**
- Claim: `P/high_resistance_vs_low_resistance_liquidity.md:61`: "Aim for Low Resistance Liquidity as take profit zones."
- App: NOT ENCODED (no relevant-vs-failure swing filter; `rules.md` Q12).
- Test: needs labels: is the first structural target a cluster of equal highs or lows (LRLR) or a single swept swing? From bars. Prediction: trades whose target is LRLR reach 2R (`first_2r == "win"`) more often.

**D13. Relevant swings only: a POI at a lesser level needs SMT.**
- Claim: `W/ttfm-swing-quality-cisd-ic-cisd.md` rule 17 (from `P/relevant_swings_which_swing_highs_and_lows_matter_in_trading.md`): "If it is too close, expect it to be taken. If it stands alone, respect it".
- App: NOT ENCODED (any 3-bar fractal in the lookback counts; `bias_poi_lookback_bars`).
- Test: needs the POI's separation from neighbouring swings (bars) and the POI type. Neither is a backtest field, so **export the POI kind (swing / FVG / order block) and its price**. Prediction: FVG POIs beat swing POIs, matching his POI order (`W/ttfm-liquidity-and-poi-selection.md` rule 7, from `P/the_only_points_of_interest_that_actually_matter_for_trading.md`: "If a Fair Value Gap exists between the protected swing and the current range, it becomes the point of interest.").

### E. Stops and targets

**E1. 2R is the minimum; never 1:1.**
- Claim: `TR/fractal_model_fundamentals.txt`: "For my system, I'm looking for a minimum of 2R". Live: `TR/livestream_20260604_..._c7nk7ypjhn4.txt`: "I don't trade a 1-to-1".
- App: `target_rr = 2.0`, `target_mode = r_multiple` (trader answer Q15; 1.0 selectable).
- Test: compare `net_1r`, `net_1.5r`, `net_2r` and `net_3r` E on the same rows. Prediction: 2R ≥ 1R. Check that the 2R Win clears 34% plus costs (`cost_r`).

**E2. The 2R must fit before the structural target, or use a limit or skip.**
- Claim: `W/ttfm-entry-timing-and-order-type.md` rule 13 (from `IN/market_order_vs_limit_order_when_to_use_each_in_trading.txt` @02:25): "Has price expanded too far away from the continuation or change in the state of delivery to provide 2R to the target?"
- App: `cont_reward_at_least_2r` / `rev_reward_at_least_2r` (A by default, `reward_check_role = advisory`; Q is the old rule).
- Test: taken rows split by `c:cont_reward_at_least_2r` / `c:rev_reward_at_least_2r`. Prediction: False rows have lower 2R Win, because price stalls at the structural level first. **High value: it is free, and it decides whether the trader's Q15 simplification costs money.**

**E3. Targets are HTF liquidity (Candle 1's high/low, then older untaken ones).**
- Claim: `TR/fractal_model_fundamentals.txt`: "if we're expecting price to continue to this previous day high, that's our target".
- App: structural levels are information only (`rules.md` 8.3). In the backtest `structural_targets` holds only the 2R price (see section 0).
- Test: recompute S1 (`B[-1]` high/low) in R per row. Compare `mfe_r ≥ S1_R` (structural reached) with `first_2r`. Or rerun with `target_mode = structural` as a new variant. Prediction: when S1 < 2R, a structural exit beats the 2R exit.

**E4. With a large wick, expect little beyond the level and target the open instead.**
- Claim: `TR/easy_daily_bias_mechanical_framework.txt`: "With a large wick, I'm not expecting much of a range beyond this level". `TR/wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt`: "we're just looking for it to reverse or return back to its opening price".
- App: S1-only on a large wick (`rules.md` 8.3, information); the exit is still 2R.
- Test: bucket the forming candle's opposing run (as in D5) and compare `mfe_r` medians. Prediction: large-wick rows have lower `mfe_r` and a lower 2R Win.

**E5. "Let the wick form, trade the body": hold to the bias candle's close.**
- Claim: `TR/trading_the_4_hour_power_of_three_ohlc_olhc.txt`: "I need to let the wick form and then look to trade the body". Time-based exit: `IN/how_to_trade_london_using_ttrades_fractal_model.txt`: "That's a time-based exit". He prefers it on the daily (`W/ttfm-exits-and-trade-management.md` rule 13).
- App: NOT ENCODED (the exit is a fixed 2R). The backtest records `r_bias_close` ("exp_body" in `analyze_backtest.py`).
- Test: E of `r_bias_close` vs `net_2r` per stack. Prediction: on 1D-bias stacks with a small wick and an early entry, `r_bias_close` ≥ `net_2r`; with a large wick it is worse (`W/ttfm-exits-and-trade-management.md` rule 14: the time exit "works pretty well" only while trending). The time exit at the **setup** candle close (09:45 / 10:00 live) needs a new field `r_setup_close`.

**E6. Partials only if the remainder still meets the model: "partials ruin a win rate".**
- Claim: `TR/livestream_20260803_..._nesscpmzwr0.txt`: "I only take partials when it still meets my requirement for a model because partials ruin a win rate."
- App: NOT ENCODED (one target).
- Test, from the fields: half off at 1R with the remainder on the original stop: `0.5 × 1 + 0.5 × (2 if first_2r == "win" else −1)` when `first_1r == "win"`, else −1, minus costs. Prediction: lower E than plain 2R. A partial with a break-even stop needs the path after 1R (did price revisit the entry before 2R?), so **add `mae_after_1r`**.

**E7. Stop on the protected swing; body stop only when the bodies sit beyond 50% of the opposing run.**
- Claim: `W/ttfm-stop-placement.md` rule 1 (from `IN/how_to_have_better_stop_losses_for_trading_ttfm.txt` @00:37): "generally speaking, I always put my stop loss on the swing point of a continuation or a protected swing".
- App: `rules.md` 8.2. Body stop: `body_stop_allowed`, `body_stop_min_body_frac = 0.6`, only when `reward_check_role = quality`, so never in the baseline.
- Test: the shape of `mae_r` for winners. If many winners reach `mae_r ≤ −0.8`, the stop is barely surviving and a buffer would matter ("give it a little bit of room", `TR/fractal_model_fundamentals.txt`). Also `minutes_to_stop` under 10 as the "swept immediately" rate per `trigger_kind`.

**E8. Trail only to new protected swings; break-even only when a new protected swing forms near the entry.**
- Claim: `W/ttfm-exits-and-trade-management.md` rule 16 (from `P/quit_moving_your_stop_loss_before_you_know_this_trailing_stop_loss.md`): "Our stop losses can only be trailed to new protected swings."
- App: `cont_newer_protected_low` (A, reported only; the stop does not move).
- Test: needs a path-dependent re-simulation with a trailing stop (minute bars plus the times of later protected swings). Not testable from the fields.

### F. Don't-trade conditions

**F1. Daily range or target already made → no continuation and no fade.**
- Claim (16 of 47 streams, `LS/s1_prep_session.md` §4 item 3): `TR/livestream_20260428_..._x4srguziqwk.txt`: "when it already hits that, that's when I kind of want to avoid it" (said of the ADR).
- App: partly. `cont_objective_open_at_trigger` (Q) covers the target; ADR is NOT ENCODED.
- Test: D1 and D2 combined. Rows where either the ADR is ≥ 78% used at check or the objective was taken. Prediction: E ≤ 0.

**F2. No bias → no trade.**
- Claim: `TR/fractal_model_fundamentals.txt`: "If I do not have a daily bias I do not drop down to the hourly time frame".
- App: the continuation needs `bias_closure_directional` (G). **The reversal path does not need a bias** (`rules.md` 5.4, 7.1), and its verdict can read `decision = short`, `bias = bullish` (Q32).
- Test: reversal rows split by `bias` (`neutral` / with / against `direction`). Prediction: reversal rows against a confirmed opposite bias (which he calls a retracement) and rows with no bias have the lowest E.

**F3. Inside day / consolidation / middle of the range.**
- Claim: `TR/next_day_model_fractal_way_to_get_bias_for_trading.txt`: "here we have an inside bar it does not give us any more information so we let another candle form". A double inside day is "consolidation by definition" (`LS/s1_prep_session.md` §2). No explicit rule for "low range days" was found beyond inside days and ADR (**INFERRED** that a low-range day is the inside-day case).
- App: case E (inside bar) → `neutral` on the bias TF. That only covers stacks whose bias is 1D; for other stacks the daily inside day is NOT ENCODED.
- Test: flag rows whose previous daily candle was inside the one before it (daily bars). Prediction: lower E on non-daily-bias stacks. Also bucket `adr14` by its own percentile, since low-volatility regimes give smaller targets relative to costs: prediction is that `cost_r` eats more of E.

**F4. News: no trading the CPI/NFP/FOMC release, nothing after FOMC.**
- Claim: `TR/livestream_20260605_..._x4xssv5cnqg.txt`: "CPI, NFP, FOMC. Don't trade the day, that current day prior to the news." `TR/livestream_20260729_..._xraklbjhw5k.txt`: "I never trade after FOMC. I just wait for the next day."
- App: NOT ENCODED (no calendar).
- Test: needs a 2024–2025 calendar of CPI, NFP and FOMC dates (public). Flag the rows that fall in the window around the release time (08:30 or 14:00) and the rows after an FOMC release. Prediction: FOMC-afternoon rows have the worst E and the widest `mae_r` spread.

**F5. Bank holidays and election days: low expectations.**
- Claim: conflicting. "I don't trade it" (2026-09-10) vs "can be clean" (`LS/s1_prep_session.md` §7 item 2). There is no clean verbatim; the synthesis flags the holiday half as context only.
- App: NOT ENCODED.
- Test: the CME holiday calendar and half days. Small sample, so it is only a hint.

**F6. After the first target is hit or the idea is invalidated: done for the day.**
- Claim: `TR/livestream_20260722_..._g1iidq3raky.txt`: "Hit the target. Indices kind of done for today."
- App: NOT ENCODED (each trigger stands alone).
- Test: order the taken rows per symbol and day. Compare the first trade of the day with later trades on the same day in the same direction, and with later trades after the first one resolved (win or loss). Prediction: later trades have lower E.

**F7. Three expansion days in a row → stand aside.**
- Claim: `TR/equilibrium_for_expansions.txt`: "at this point we have 3 days of expansion into lows this is where I'm going to avoid".
- App: implied by Candle 3/4 only (`rules.md` 5.4).
- Test: needs the count of consecutive expansion bias candles (bars). Prediction: Candle 4 rows after two big expansion days have lower E than Candle 3 rows (export `bias_candle_number`, A9).

---

## 2. Chart inventory: what TTrades shows vs what the app draws

Sources for his chart: the official indicator guide (`P/ttrades_fractal_model_indicator_full_guide.md`, mapped feature by feature in `W/ttfm-indicator-full-guide.md`), the older settings video (`TR/intro_to_ttrades_fractal_model_indicator_settings.txt`), and what he marks by hand in live streams (`LS/s1_prep_session.md` §1 and §6). App: `companion/styles/ttrades/style.py:99-129` (base levels) and `:185-215` (plan lines), `continuation.py:760-900`, `reversal.py:215-455`, `companion/web/src/components/Charts.tsx` (three panes, `ORDER = ['bias','setup','entry']`), `DecisionPanel.tsx` (verdict, steps, plan, session clock), `web/src/display.ts` (overlays: level names, zones, marker labels, risk/reward box).

| # | TTrades shows | Where it comes from | App draws now | Status |
|---|---|---|---|---|
| 1 | HTF candles beside the LTF chart (side panel) | indicator "HTF Candles" | Three separate panes: bias, setup, entry | partial |
| 2 | Vertical lines at HTF period opens | indicator "Vertical lines" | none (? INFERRED from the wiki's grep) | missing |
| 3 | Open of the current HTF candle on the LTF chart | indicator "HTF Open" | "Forming bias candle open" (`style.py:125`), bias TF only; no setup-candle open on the entry chart | partial |
| 4 | Previous HTF candle high/low (PDH/PDL) | indicator "L/H lines"; marked live | "Previous bias candle high/low", shown as PDH/PDL on 1D, shared on all panes (`style.py:110-117`) | present |
| 5 | Previous EQ (50% of the previous HTF candle) | indicator "Previous EQ" | "Previous bias candle equilibrium" (PD EQ) | present |
| 6 | 0.5 of the wick on large-wick candles | videos (`rules.md` 3.9) | "Respect level (wick midpoint)" (`continuation.py:766`) | present |
| 7 | T-spot box (where the next HTF wick should form) | indicator; settings video @11:14 | Respect level as a line only; no box | partial |
| 8 | C2 / C3 / C4 model labels, "C2 failed" / "XC2" | indicator; settings video @10:07; live | "Bias Candle N" marker (`C3`/`C4`, `continuation.py:785`) and "Setup closure (Candle 2/3 closure)"; no failed-C2 label, and none on the reversal path | partial |
| 9 | Candle 1 sweep line | indicator | Only the PDH/PDL lines; the sweep itself is not marked | partial |
| 10 | Bullish / bearish CISD lines | indicator | "Bias CISD", "Entry CISD", "Reversal CISD", plus the pending "Close above = CISD" level | present |
| 11 | Early CISD labelled "Potential Candle 2" | indicator (Early C2 CISD, his setting: on) | Reversal CISD drawn and traded, but not labelled as a potential (unconfirmed) model | partial |
| 12 | Protected-swing dots/lines for every continuation, greyed when invalidated | indicator "Protected Swings" | One "Protected low (stop swing)"; later protected swings only in the `cont_newer_protected_low` text; no grey-out | partial |
| 13 | Order block / opposing-candle zones | videos | "Bias order block", "Entry order block", "Reversal order block" zones | present |
| 14 | FVG and swing POIs | videos | "POI: fair value gap", "POI: swing low taken", key-level gap/swing | present |
| 15 | SMT lines and labels vs a correlated asset | indicator (his setting: on); live in 46/47 streams | none | missing |
| 16 | PSP label ("C2+PSP") | indicator (his setting: on) | none | missing |
| 17 | Formation liquidity: all untaken previous HTF highs/lows as targets | indicator; settings video @12:51 | "Structural level 1/2" (previous bias candle high/low and the next untaken bias swing), information only | partial |
| 18 | SD projections (−1, −2, −2.5, −4) | indicator (his setting: **off**) | none | missing (low priority) |
| 19 | Time-filter windows / session shading | indicator (his setting: **off**) | No shading. `session_filter_ok` in the checklist; next-checkpoint clock in the panel | partial |
| 20 | Info table: asset, timeframe, alignment, bias | indicator | Decision panel: verdict, bias/setup/entry chain, steps | present |
| 21 | Countdown to the HTF candle close | indicator info table | Panel clock counts to his fixed checkpoints (9:30, 9:45, 10:00, 10:30, 11:00), not to the bias/setup candle close | partial |
| 22 | One target line and one invalidation line | live, marked in 43/47 streams | "Entry", "Stop", "Target 1", risk/reward box (`style.py:191-205`) | present |
| 23 | Daily open (18:00), midnight, 08:30 and 09:30 opens | time-levels post; live | Daily open only when the bias is 1D (row 3) | partial |
| 24 | Session highs/lows: Asia, London, pre-open range | live target ladder | none | missing |
| 25 | Previous 4H high/low, previous week/month high/low | live target ladder | Only when that timeframe is the bias TF | partial |
| 26 | Three panes NQ / ES / YM, ranked strongest → weakest | live (18/47 narrated) | One symbol at a time | missing |
| 27 | ADR and the share of it used | live ("ADR judged by eye"); ADR video | none | missing |
| 28 | Dealing range, premium/discount | dealing-range video | none | missing |
| 29 | 4h candle grid (18, 22, 02, 06, 10, 14) with its O-L-H-C state | time-levels post | none unless the bias or setup TF is 4h | missing |
| 30 | Equal highs/lows / failure vs relevant swings (LRLR / HRLR) | posts; live | none | missing |
| 31 | News / event banner | live (CPI, NFP, FOMC) | none | missing |
| 32 | Day-type flags (inside day, Monday after a Friday reversal) | live | none | missing |
| 33 | Past models on the chart (history) | indicator "History" | Saved history can be stepped bar by bar; past models are not drawn together | partial |
| 34 | Alerts on model / protected swing | indicator (he alerts on Daily–Hourly and 4H–15m only) | On-screen flag only | missing |
| 35 | Breaker blocks / inversion FVG | posts (rarely used) | none (`rules.md` 3.13, Q26) | missing (low priority) |
| — | (app only) "At the POI", "Close above = CISD", step list, structural-level R distances | — | drawn / listed | app-only |

Biggest gaps, by how often he uses them: cross-asset SMT and relative strength (15, 26); the range-left context (ADR, session highs/lows, HTF targets beyond the previous candle: 17, 24, 25, 27); the "Potential Candle 2" labelling of in-candle reversals (11); and the HTF time structure (2, 21, 23, 29).

---

## 3. The ten claims that matter most for money, ranked

1. **B2: continuation beats the reversal candle.** The app trades every in-candle reversal CISD as a full model, while his own indicator calls it "Potential Candle 2" and he wants SMT with it. If reversal rows have negative E, cutting or tightening that path is the biggest single fix.
2. **D10: stale reports (`lag_min`).** Every outcome is measured from the first report, and earlier sweeps found 45 of 96 trades already +1R when first reported. If E collapses with lag, the live trader cannot earn the paper edge whatever the rules say.
3. **D1 / F1: range or target already used.** He gives this skip in 16 of 47 streams, and the engine has no ADR at all. Late-day continuations past PDH/PDL are the classic giveback.
4. **E2: 2R must fit before the structural target.** It is free to test (`c:*_reward_at_least_2r`) and it decides whether the trader's "just exit at 2R" answer is costing money.
5. **D9: early in the HTF candle.** This is his mechanical timing rule ("first half"). The test settles Q37 (0.5 vs 0.75) and applies to the reversal path, which has no timing check today.
6. **D7: swift CISD vs consolidation.** These checks cut 2025 continuation trades from 27 to 6 on one stack. The two-year, three-symbol run shows whether the cut keeps the winners or only shrinks the sample.
7. **A1 / A3 / A5: NY AM, no PM, no pre-9:30 5m.** Session buckets are free in the fields. They answer whether `session_filter_role` should go back to quality, and with which windows.
8. **E5: hold to the bias candle close vs fixed 2R.** `r_bias_close` is already recorded. If it beats `net_2r` on small-wick daily trades, the exit leaves money on the table; if it loses on large wicks, that confirms the "trade the body only after a small wick" rule.
9. **D2: objective already hit.** `cont_objective_open_at_trigger` blocks the most continuation checks of any quality rule (124 in the 2025 sweep, `rules.md` Q35–37). It needs proof that the blocked trades really lose.
10. **D11 / B3: relative strength and SMT across NQ/ES.** It is central to almost every live stream ("never the lagging asset") and absent from the app. Both symbols are in the data, so a cross-symbol join can test it before anyone builds it.

Extra fields that would unlock untestable claims, cheapest first: `bias_case` / `bias_candle_number` (A9, B1, B6, F7), POI kind and price (D13), `r_setup_close` and `r_at(10:00)` (A7, E5), `adr_used` at check (D1, F1), `mae_after_1r` (E6), structural S1/S2 in R (E2, E3).
