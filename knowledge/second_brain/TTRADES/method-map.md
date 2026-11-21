---
title: "TTrades method map"
type: ttrades-method-map
last_updated: 2026-11-21
status: "draft (not yet reviewed by Vik)"
---

# TTrades method map

Read this before any concept page. It puts the 15 pages in `concepts/` on one chain. Built 2026-11-21 from the pages' frontmatter, Definition, Engine notes and "How it changed" sections, [[conflicts]] (332 rows) and [[sources-index]] (183 sources: 2022 34, 2023 34, 2024 24, 2025 31, 2026 60, incl. 48 NY Open livestreams 2026-03-10 to 11-11).

**How to read it.** Teacher = TTrades (TTFM). A claim with `[[slug]] mm:ss` or a page link comes from a concept page as it stood on 2026-11-21 (not re-checked against transcripts; use `--quote` for that). **[inf]** marks this map's own synthesis. Ids such as `CISD-19` are rows in [[conflicts]]; `TD-nnn` are Vik's decisions in [[decisions]], which has no rows yet, so every conflict below is undecided. A later video does not replace an earlier one unless he says so; only the rows listed under "Explicit supersessions" do. Dates are recording dates, or upload dates where [[sources-index]] says "(upload)".

## The decision chain (2026)

Steps follow the pages' `chain_step` values. In short: closure, profile veto, continuation setup, CISD then next-continuation entry, protected-swing stop, fixed 2R, one trade a day ([[a_simple_3_step_trading_model_full_breakdown]] 11:48).

0. **Framework / gate.** There is one fractal model on any pair: an HTF C2/C3 closure at a POI, an LTF CISD inside it, then trade the next HTF candle's body. No bias, no trade; a model without HTF bias is "pattern trading". [[fractal-model]], [[psychology-and-process]], [[ttfm-indicator]]. Key: [[intro_to_ttrades_fractal_model_indicator_settings]] 00:28-01:37; [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 52:30.
1. **Daily closure = bias.** Read the previous daily close against the candle before it. A C2 (sweep, close back inside) gives a reversal bias; a C3 (close beyond C2's body/open, C2's extreme untaken) or a close beyond PDH/PDL gives a continuation bias. His easiest version is a daily C2/C3 + H1 CISD. There are two named invalidations: EQ invalidated, or a reversal off PDH/PDL. [[daily-bias]], [[candle-closures]], [[cisd]], [[ranges-and-eq]]. Key: [[the_only_trading_strategy_you_need_for_2026]] 00:57-01:37; [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 1:02:10. Open: `POI-1`, `BIAS-1`.
2. **Daily profile = veto.** Bias, then profile, then entry. A bullish day must "open, make some sort of low, then trade higher", read on the 4H/1H. A bias without a confirming profile is not traded, and on reversal days the bias follows the profile, not the closure. His A+ profile is London reversal into NY continuation. [[profiles]], [[sessions-and-time]]. Key: [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 1:36:40; [[livestream_20261006_new_york_open_live_q_a_rtomj8urfnw]] 25:50. Open: `BIAS-9`, `PROF-1`.
3. **Setup: continuation first.** Price reaches a POI (an FVG or a swept short-term low/high) in the previous candle's respected half. Trade C3/C4, never C5 by default. The 2026 toolkit is highs/lows, FVGs, CISD, EQ and OHLC. In the 2026 streams he does not trade reversals; reversals need SMT. Never trade away from a failure swing. Choose the asset by relative strength (strongest long, weakest short, never the laggard). [[entry-models]], [[poi-and-pd-arrays]], [[liquidity]], [[swings-and-structure]], [[smt-and-psp]]. Key: [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 50:10; [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:09:50. **[inf]** "No reversals" means nothing against the daily bias: an intraday reversal in the bias direction is "a continuation" ([[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 14:10). Open: `ENT-6`, `SMT-1`, `LIQ-2`.
4. **Entry: confirm with the CISD, enter on the next continuation.** A CISD is a body close through the series that delivered price to the level, ideally a V in 1-3 candles; a slow close-through is consolidation. There is one CISD per day, and it forms the daily wick. The 2026 strategy video says to check the CISD, not enter on it, and to enter on the close of the next continuation order block; he takes the first CISD only with very strong bias. Enter early in the HTF candle, after its wick, at about 08:00-10:30 NY. [[cisd]], [[entry-models]], [[sessions-and-time]]. Key: [[the_only_trading_strategy_you_need_for_2026]] 02:46; [[why_your_continuations_fail_order_blocks_cisd_explained]] 09:55. Open: `CISD-19`, `CISD-2`, `ENT-4`.
5. **Manage.**
   - Stop exactly on the protected swing, no buffer.
   - At least 2R, and a fixed 2R set-and-forget for anyone who cuts winners.
   - Break-even only when a return to entry would itself be invalidation.
   - One trade a day.
   - Size from the drawdown.
   - No entry after the target is hit or the daily range is made.
   - Time exits at 09:45/10:00 are allowed.

   [[risk-and-management]], [[psychology-and-process]]. Key: [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 13:24; [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 47:20. Open: `RISK-4`, `SW-1`, `PSY-1`.

## Timeframe pairings

**Pairs and stacks.**
- Pairs: W-4H, D-1H, 4H-15m, 1H-5m, 30m-3m, 15m-1m, plus M-D ([[timeframe_alignment_how_to_align_timeframes_for_expansion]] 02:13).
- Closure-to-CISD: daily C2 to H1 CISD, 4H to 15m, H1 to 5m ([[candle_2_closure_foundation]] 09:10).
- A stack has three roles, bias / structure / entry, and bias is the structure timeframe's own higher pair ([[timeframe_alignment_how_to_align_timeframes_for_expansion]] 02:27). The third timeframe is optional ([[trade_like_ttrades_top_down_analysis]] 12:41).
- The indicator uses one pair; Auto Bias 1/2 needs a valid model one or two pairs up ([[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 07:30).

| Era | Preferred stack | Source |
|---|---|---|
| 2022 | 15m/5m/1m, 15s/30s refinement, "domino" structure shifts | [[livestream_20220810_stream_q_a_with_trade_for_opportunity_ict_concepts_0bh_kkg2q6s]] 53:50 |
| 2023 | Daily, then an LTF POI, then an LTF entry | [[top_down_analysis_daily_bias_to_entries_ict_concepts]] 01:53 |
| 2024 | D/1H/5m, execute on the 5m | [[internal_external_liquidity_model_ict_concepts]] 15:31; [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 37:50 |
| 2025 | D/1H/5m; 4H-15m for the 4H power of three | [[trade_like_ttrades_top_down_analysis]] 02:30; [[trading_the_4_hour_power_of_three_ohlc_olhc]] 04:48 |
| 2026 | Videos: "favourite" D/4H/15m. Streams: D-1H bias + 4H-15m execution; D-H1 if only one; weekly-4H not used | [[the_best_timeframe_for_ttrades_fractal_model_simple]] 00:14; [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 10:00; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 14:00; [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 37:40 |

**What the higher timeframe must show first.**
- A daily bias: "without a daily bias I do not drop to the hourly" ([[fractal_model_fundamentals]] 01:10).
- A structure-timeframe CISD in the bias direction ([[timeframe_alignment_how_to_align_timeframes_for_expansion]] 01:10).
- HTF candles that support expansion (small wick; daily and 4H aligned) ([[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:09:10); a large wick means only a return to its open is expected ([[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 05:00).
- Preferably the HTF candle closed in your direction ([[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 48:30).
- No reversal framing below the 4H ([[easy_daily_bias_mechanical_framework]] 12:24).

**Session confirmation timeframes.**
- CISD for the high/low of day: Asia H1/30m, London H1/30m (rarely 15m), New York 15m/5m ([[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 09:20).
- Pairs by session: Asia D-H1 or H4-M15, London H4-M15 or H1-M5, NY AM H4-M15, H1-M5 or M30-M3 ([[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 36:00).
- Before 9:30, 15m (H4/M15 or 7H to 15m); after 9:30, H1-M5 or M30-M3 ([[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 1:26:20).
- Move up a timeframe when stopped before the move ([[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 55:40).
- Refine down when there is no 2R ([[ttrades_top_down_chart_lessons_2]] 06:21).

Open: `FM-1`, `FM-2`, `FM-5`, `FM-6`, `FM-9`, `FM-19`, `CISD-9`.

## Eras

- **2022: ICT concepts, MSS, order blocks (34 sources).** Bias came from the 4H/1H used as "the daily", and "don't focus on determining bias" ([[intraday_bias_ict_concepts]] 00:00; [[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 28:10). The trigger was an MSS with displacement and an FVG; a break without displacement was a liquidity grab ([[reversal_or_pullback_using_market_structure_to_determine_trend_ict_concepts]] 03:08-03:41). The entry was ICT's 2022 model (liquidity run, MSS, FVG in discount/premium, OTE 0.62-0.79) ([[livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4]] 34:10; [[ote_optimal_trade_entry_ict_concepts]] 00:34). POIs were the full ICT menu: highs/lows, FVGs, OBs, breakers, OTE, BPR ([[higher_time_frame_points_of_interest_ict_concepts]] 00:36). Time meant the NY AM kill zone 8:30-11:00 and the midnight open ([[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 33:10). He dropped Strat triggers ([[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 44:00).
- **2023: ICT definitions, CISD arrives (34 sources).** Definition videos covered OHLC/OLHC ([[open_high_low_close_ohlc_olhc_ict_concepts]] 00:03), draw on liquidity as daily bias ([[ict_daily_bias_the_only_video_you_will_ever_need]] 00:10) and the kill-zone table ([[important_liquidity_levels_draw_on_liquidity_ict]] 06:33), plus OTE 0.705, the unicorn and the IFVG ([[optimal_trade_entry_ote_ict_concepts]] 11:17; [[breaker_block_fvg_entry_model_ict_concepts]] 02:02). **Added:** the CISD. AM Trades brings it in July and he "definitely prefers" it ([[livestream_20230730_live_q_a_with_am_trades_weekly_profile_wgyde_h84cs]] 14:40, 50:10). The November video defines it as a close beyond the opposite series' opening price at an HTF PD array ([[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 00:37-01:06); the December video gives CISD vs MSS ([[market_structure_shift_vs_change_in_state_of_delivery_ict]] 00:57-06:42). The 2R floor becomes explicit ([[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 03:11).
- **2024: daily profiles, Sunday sessions, indicator (24 sources).** London reversal / NY continuation and NY reversal profiles ([[ict_daily_profile_london_reversal_new_york_continuation]] 00:50; [[ict_daily_profile_new_york_reversal]] 00:57). The Sunday sessions bring the 18:00 open instead of midnight (`SES-13`); "don't trade reversal days, trade the next day's continuation"; the CISD as "the only entry confirmation", "never a single candle"; SMT as optional and never the bias ([[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 27:10, 21:00, 26:40, 11:50, 47:40). The next day model becomes closure-based ([[next_day_model_fractal_way_to_get_bias_for_trading]] 02:44). The TTFM indicator (2024-11-29) prints C2/C3/C4, the CISD one pairing down and the protected high, with "enter on the close, stop on the high, 2R" ([[intro_to_ttrades_fractal_model_indicator_settings]] 01:12-02:07).
- **2025: the TTFM playbook (31 sources).**
  - Pair list ([[timeframe_alignment_how_to_align_timeframes_for_expansion]] 02:13).
  - EQ "opposite to ICT": wick to wick, respected half ([[equilibrium_for_expansions]] 00:55).
  - Continuations with OBs and breakers ([[trade_continuations_using_order_blocks]] 00:18; [[trade_continuations_using_breaker_blocks]] 14:32).
  - The protected swing as the invalidation ([[protected_swings_understanding_trend_and_invalidations]] 14:05).
  - Numbering, "no daily bias, no hourly", the one-candle series ([[fractal_model_fundamentals]] 00:46, 01:10, 08:19).
  - Phases of price ([[how_to_trade_reversal_phases_of_price]] 00:33).
  - The session CISD timeframe ([[ttrades_fractal_model_trading_candle_2]] 10:15).
  - C2/C3 as "the only two formations" ([[candle_3_closure_ttrades_fractal_model]] 10:31).
  - Only the 18:00 open ([[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 08:30).
  - No reversal framing below the 4H ([[easy_daily_bias_mechanical_framework]] 12:24).
  - SMT as a sweep substitute ([[trade_continuations_using_order_blocks]] 01:58).
  - Time exits at the HTF close ([[ttrades_fractal_model_inversion_intraday_strategy]] 05:18).
- **2026: education videos plus New York Open streams (60 sources).**
  - Videos: enter on the next continuation, not the CISD ([[the_only_trading_strategy_you_need_for_2026]] 02:46); D/4H/15m ([[the_best_timeframe_for_ttrades_fractal_model_simple]] 00:14); why continuations fail ([[why_your_continuations_fail_order_blocks_cisd_explained]] 00:34); relevant vs failure swings ([[which_swing_highs_and_lows_matter_in_trading]] 01:12); the 3-step model, joint with AM Trades ([[a_simple_3_step_trading_model_full_breakdown]] 11:48).
  - Streams add: bias, profile, entry ([[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 36:30); no weekly bias ([[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 1:18:20); "kill zones don't matter" ([[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 18:40); IC-CISD ([[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 46:40); one CISD and one trade a day ([[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 16:30, 47:20); SMT for reversals ([[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:09:50); the indicator update with protected swings, PSP and Auto Bias ([[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 04:20).
  - Dropped with no "I used to", so these stay open: OTE (`ENT-15`), kill zones (`SES-12`), the midnight open (`SES-13`, `CC-14`), and SMT's change from optional to required for reversals (`SMT-1`).

### Explicit supersessions (the only ones)
| Change | Said in | Conflict rows |
|---|---|---|
| MSS replaced by CISD: "moved from market structure shift (2022) to CISD" | [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 45:00; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 48:00 | `CISD-7`, `SW-17`, `SW-18` |
| C3 tightened: the first course counted a C3 on EQ disrespect, now it needs the stricter close | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 22:00 | `CC-18` |
| Premium/discount and breakers removed from the model | [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:24:50 | `POI-4`, `POI-8` |
| Also marked in [[conflicts]]: protected swings replace the intermediate-term low; the old silver-bullet and box-setup videos retired | [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 55:00; [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 59:20; [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 21:00 | `SW-19`, `FM-20` |

## Teacher vs engine (companion)

Engine = `companion/styles/ttrades/rules.md`, as summarised in each page's Engine notes.

| Gap | Teacher (2026) | Engine | Page | Conflicts |
|---|---|---|---|---|
| Entry trigger | Confirm with the CISD, enter on the next continuation ([[the_only_trading_strategy_you_need_for_2026]] 02:46) | `entry_mode = either` fires on the CISD in 144 of 149 trades (2025 sweep, Q28) | [[cisd]], [[entry-models]] | `CISD-19`, `ENT-11` |
| EQ respect | One H1 close beyond EQ is a soft invalidation that cuts targets; taps and shallow wicks are allowed | `cont_eq_respected` is a gate with `eq_tolerance_frac = 0` | [[ranges-and-eq]], [[daily-bias]] | `RNG-2`, `RNG-3`, `BIAS-1` |
| Daily profile | The second filter; on reversal days the bias follows it | No profile criterion (Q26); `Verdict.bias` stays closure-based (Q32) | [[profiles]] | `BIAS-9`, `PROF-1`, `BIAS-14` |
| Time | NY only, about 08:00-10:30; 8:30/9:30/10:00 used as gates; time exits at 9:45/10:00 | `kill_zones` 02:00-05:00 / 08:30-11:00, advisory; `daily_wick_deadline = 11:00`; no time-based exit | [[sessions-and-time]] | `SES-1`, `SES-2`, `SES-5`, `SES-6`, `FM-15` |
| Reversals | Not traded in the 2026 streams; need SMT | Reversal path weighted equal to continuation; ties go to continuation (Q34); key level + CISD only | [[entry-models]], [[smt-and-psp]] | `ENT-6`, `ENT-7`, `SMT-19` |
| Order blocks as POI | "Rarely uses HTF OBs"; POIs are FVGs and highs/lows | 3.14(c) accepts an order block as a POI | [[poi-and-pd-arrays]] | `POI-6` |
| POI requirement | No POI needed for a continuation inside the daily range, ideal but not required on the daily, profile can replace it | `bias_poi_present` and `cont_poi_tagged` are gates | [[poi-and-pd-arrays]], [[profiles]] | `POI-1`, `BIAS-4`, `PROF-5` |
| SMT and relative strength | Rank indices, trade the strongest/weakest; SMT stands in for a sweep | Single-symbol; no SMT, no ranking (Q23) | [[smt-and-psp]] | `FM-17`, `SMT-2`, `SMT-18`, `SMT-20` |
| Trade count | One idea, one trade a day | No cap; re-evaluates at every check and can flip side the same day | [[psychology-and-process]] | `PSY-1`, `PSY-6`, `RISK-23` |
| Exit | Fixed 2R default, plus HTF liquidity targets, runners, BE rule, time exits | One target at `target_rr = 2.0`; no BE or trailing | [[risk-and-management]] | `RISK-4`, `LIQ-10` |
| Stack | Two timeframes are enough; entry on the structure timeframe is allowed; the pair changes by session | Three fixed roles per run; triggers only on `E` | [[fractal-model]] | `FM-6`, `FM-7`, `CISD-18`, `SES-9` |
| Swings | Relevance and separation decide; never trade away from a failure swing | Any three-bar swing is a POI (Q12); protected swing broken by a wick | [[swings-and-structure]], [[liquidity]] | `LIQ-2`, `SW-2`, `SW-1` |

Where the engine matches him: closed bars only, stop on the protected swing with no buffer, no bias no trade, fixed 2R ([[psychology-and-process]], [[risk-and-management]] Engine notes).

## Undecided blockers (ask Vik first)

All are `open`; [[decisions]] has no TD rows yet. These are ordered by how much of the chain each one blocks **[inf]**.

1. `CISD-19`: enter on the CISD close or on the next continuation order block?
2. `BIAS-9` / `PROF-1`: does the daily profile veto the closure bias, and which one sets the direction on a reversal day?
3. `ENT-6`: are reversals (and reversal days) traded at all, or continuation only?
4. `SMT-1` / `SMT-19`: is SMT required for reversals? (A single-symbol engine cannot check it.)
5. `POI-1` / `BIAS-4`: is an HTF POI required for every C2/C3 closure?
6. `BIAS-1` / `RNG-2`: EQ tolerance. How far past EQ, on which timeframe, and reclaimed within how many bars?
7. `RNG-1` / `BIAS-7`: which 0.5 is EQ: whole candle, wick, or bodies?
8. `CISD-2` / `CISD-3`: CISD level (first candle's open vs highest open) and which candles make up the series.
9. `SW-1`: is a protected swing broken by a wick or by a close?
10. `CC-1` / `CC-2`: the numbers for small vs large wick, and how early the wick must form.
11. `SES-1` / `SES-2`: NY window end (10:30 vs 11:00) and the "early in the candle" deadline.
12. `RISK-4` / `SES-5`: fixed 2R, or hold for the HTF target / time exit?
13. `PSY-1` / `PSY-6`: one trade and one direction per day in backtests and live?
14. `FM-1` / `FM-2`: default stack (D/1H/5m vs D-1H + 4H-15m) and which pair gives bias to a setup pair.
15. `LIQ-2` / `SW-2`: a mechanical rule for a relevant swing vs a failure swing (valid separation).

## Guests

The channel hosts other traders. Their rules are flagged `[guest]` or "(guest X)" on the concept pages and are not TTrades' teaching, even when he presents them.

| Guest | Source (date) | What they teach that is not TTFM |
|---|---|---|
| GxTradez / GXT (Garrett, same person) | [[gxtradez_phases_of_price_profiles_for_expansion]] (2025-04-18); [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] (2025-10-05) | Phases of price where consolidation never leads to reversal (`RNG-17`); a 4H session profile; 10:30 wick deadline (`SES-2`); universal models; the three-market triad; PSP and two-stage SMT/PSP ([[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 07:17-14:25); C3 close over C2's high (`CC-3`); no C2 needed (`CC-21`) |
| AM Trades | [[livestream_20220814_stream_q_a_with_am_trades_ict_concepts_cruftskoveo]]; [[livestream_20230730_live_q_a_with_am_trades_weekly_profile_wgyde_h84cs]]; [[a_simple_3_step_trading_model_full_breakdown]] (2026-06-20) | Weekly profile = HTF PD array + day of week + 1H CISD, no Mondays (23:20); weekly bias + MMXM narrative (08:50); NQ default, ES on weakness (36:40); 7h daily profiles (20:22), which TTrades says he does "Not really" use (`PROF-10`, `SES-20`); 50% close-to-swing profile invalidation (`RNG-22`). He also brought the CISD to the channel in 2023 |
| AP ("AP Trades") | [[ap_use_market_structure_fibonacci_levels_for_sniper_entries]] (2025-03-13) | Not an ICT trader; credits DTFX; market structure + Fibonacci, blind limit at 0.7475 after a valid flip |
| Ash Trades | [[ash_trades_the_journey_to_profitability_the_unicorn_model]] (2024-01-19) | Unicorn model; resting orders with no BE, trail or trims, one trade a day (1:19:38, 1:24:12); stop after a win (1:23:06, `PSY-15`) |
| Jokerszn | [[jokerszn_daily_orderflow_ict_daily_bias]] (2024-02-18) | Daily order flow: bias from daily closes, never wicks (22:12); expansion/retracement/consolidation profiles; bias neutral after the target until price shows intent |
| $niper / Sniper (Matt) | [[livestream_20220821_8_14_22_mmxm_live_with_niper_ict_concepts_umlwrlxd_v8]]; [[niper_internal_external_liquidity_ict_daily_bias]] (2024-04-18) | IRL/ERL alternation with an MSS on the paired lower timeframe (ICT vocabulary, no candle numbers); 2R partials with 20% runners (36:20); mentored by the MMXM Trader |
| MMXM Trader | [[next_day_model_the_mmxm_trader_ict_concepts]] (2023-05-09); [[the_twitter_model_the_mmxm_trader_ict_concepts]] (2024-06-07) | Third-party models TTrades walks through: next day model (skip Mondays, NY only, 15m) and Twitter model (PDH/PDL raid, 15m MSS + SMT, correct side of the midnight open) |
| OTE Trader (Tom) | [[the_ote_trader_i_turned_profitable_with_this_stage_of_ict_s_mmxm_models]] (2024-09-14) | Forex: 4h/1h/15m alignment; skips the smart money reversal and trades the following re-accumulation leg; kill zones only below the hourly; NY focus when Asia already trends |
| DTR (Day Trading Realtor) | [[dtr_c2u_blending_the_fractal_model_unicorn_model_no_daily_bias]] (2025-02-15) | C2U: enters inside C2 on a 5m unicorn formed within 10-12 candles, no daily bias (02:13, 18:46; `FM-14`); uses AM Trades' 7h profile and ADR |
| Others | NickDoesFutures ([[nickdoesfutures_unicorn_model_experiences_with_ict]]; 2026-06-17 co-host), AFYZ ([[afyz_trading_the_daily_ohlc_protraction_profiles]]), Rauf, TFO, HolyAngelBruv, Ben, Alex (2022-2023 streams) | Nick: limit at the breaker edge; AFYZ: protraction profiles (`SES-24`); TFO: 1% risk, at most three trades a day ([[livestream_20220810_stream_q_a_with_trade_for_opportunity_ict_concepts_0bh_kkg2q6s]] 39:00); Rauf: YM as third leg |

In co-hosted livestreams, check who is speaking before you cite a line as the teacher's (e.g. `RISK-20`, "speaker possibly Nick").

## How to use this brain

`python knowledge/second_brain/TTRADES/_pipeline/tt_lookup.py` (it rebuilds the index when a note is newer):

| Command | Returns |
|---|---|
| `--map` | This file. Read it first |
| `"<concept>"` (e.g. `cisd`, `"candle 2"`) | Concept card: chain step, definition, conflicts, decisions |
| `"<concept>" --rules [--grep WORD]` | Plus the merged, cited rules table |
| `--search "wick into a key level"` | The teacher's rules first, then transcript and page evidence |
| `--quote <slug> 12:34` | The transcript around a cited time (ground truth) |
| `--rule <slug>#3`, `--conflict CISD-2`, `--sources [concept]` | One per-video rule, one conflict in full, source notes newest first |
| `--trades session=asia path=reversal [outcome=loss] [symbol=NQ] [from=..] [to=..]` | Journal trades that match, with win rate and R |
| `--day 2026-11-03` | One journal day: its trades and note path |
| `--backtest <id> [SYMBOL]` | One registered backtest run |

**Three voices rule** (`.claude/skills/ttrades-intent/SKILL.md`). Keep three things apart:
1. The teacher's words, and named guests' words marked as guests.
2. Vik's decisions (TD-nnn).
3. Your own inference, marked.

Also from that skill: never fill a gap with general ICT/SMC knowledge; a later video overrides an earlier one only when he says so; never code against an open conflict row without asking Vik; TCM (`TCM-CORE/`) is a different teacher, so never mix the brains.

Workflow: place the task on the chain, open that step's pages, pull `--rules`, check the step's conflict ids, and verify quoted times with `--quote`.
