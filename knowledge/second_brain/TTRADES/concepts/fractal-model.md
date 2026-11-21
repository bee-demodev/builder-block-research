---
id: fractal-model
title: "The TTrades Fractal Model (TTFM) and timeframe pairing"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [TTFM, TTrades Fractal Model, fractal model, the model, my model, timeframe pairing, timeframe alignment, fractal pair, X-Y model, daily-hourly fractal, 4H-15m model, top-down analysis, fractalize, favorite fractal model, scalping model, swing trading model, "TFM model", "4 Hour with the 15"]
covers: [fractal-model, timeframe-pairing, timeframe-alignment, top-down-alignment, fractalize, scalping-model, swing-trading-model, pattern-trading, auto-bias-pairing]
sources: [fractal_model_fundamentals, intro_to_ttrades_fractal_model_indicator_settings, timeframe_alignment_how_to_align_timeframes_for_expansion, trade_like_ttrades_top_down_analysis, cisd_validates_swing_points, candle_3_closure_ttrades_fractal_model, candle_2_closure_foundation, the_best_timeframe_for_ttrades_fractal_model_simple, ttrades_fractal_model_trading_candle_2, ttrades_scalping_model_simple_day_trading_strategy, ttrades_swing_trading_model_simple_strategy, higher_timeframe_analysis_for_trading_aligning_expansion_candles, easy_daily_bias_mechanical_framework, the_only_trading_strategy_you_need_for_2026, livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy, livestream_20260819_new_york_open_live_q_a_rvrk4mltjss, livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi, livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims, livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu, livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds, a_simple_3_step_trading_model_full_breakdown, internal_external_liquidity_model_ict_concepts, livestream_20220911_fractalizing_entries_q_a_with_ben_ict_concepts_yrmkkr4coju]
confidence: high
chain_step: ["0 framework", "1 bias", "3 setup", "4 entry"]
timeframe_role: [any]
requires: [candle-closures, cisd, swings-and-structure]
feeds: [daily-bias, profiles, entry-models, ttfm-indicator, sessions-and-time, risk-and-management]
---

# The TTrades Fractal Model (TTFM) and timeframe pairing

## Definition

**Latest (2025-2026).** The fractal model is TTrades' one model: a higher-timeframe (HTF) candle forms a swing point with a candle 2 or candle 3 closure at a point of interest, a change in the state of delivery (CISD) inside that HTF candle on the paired lower timeframe (LTF) validates the swing, and he then trades the following HTF candle's body (open-high-low-close / open-low-high-close) with LTF continuations ([[intro_to_ttrades_fractal_model_indicator_settings]] 00:28-01:37; [[cisd_validates_swing_points]] 00:54; [[ttrades_fractal_model_inversion_intraday_strategy]] 00:31). Its foundation is that "price cannot reverse without a swing point" ([[fractal_model_fundamentals]] 00:22). Candle 2 and candle 3 closures are "the only two formations in his model", and closures plus equilibrium (the HTF wick location) plus an LTF CISD or continuation order block "is the entire model" ([[candle_3_closure_ttrades_fractal_model]] 10:31, 11:34). It is called fractal because the identical logic runs on any timeframe pair, from monthly-daily down to 5m-15s, and on any asset ([[intro_to_ttrades_fractal_model_indicator_settings]] 04:11; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 46:20; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 55:00). Top-down use stacks three roles: a higher timeframe for bias, a middle one for structure (swing point / setup), a lower one for entry ([[timeframe_alignment_how_to_align_timeframes_for_expansion]] 00:31); the 2026 streams restate it as "daily bias, intraday reversal, aligned fractal model", normally three or four timeframes ([[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:16:00). A fractal model without HTF bias is "pattern trading" and is rejected ([[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 52:30).

**2026 indicator wording.** Pairs are written "X-Y Model" (e.g. "15m-4H Model"), the countdown runs to the close of the higher (Y) candle, and "Auto Bias 1/2" shows a model only when the pair one or two fractals up also has a valid model ([[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 15:10 (visual); [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 07:30).

**2024 (launch).** The name appears with the TTFM indicator (uploaded 2024-11-29): HTF sweep and close back inside, LTF CISD, trade the next HTF candle; the indicator's Automatic mode picks the pair from the chart timeframe ([[intro_to_ttrades_fractal_model_indicator_settings]] 00:28-04:29). In the 2024 Sunday streams he already calls his model "fractal" because it is the same on every timeframe, with daily and hourly preferred ([[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 17:30). He says it began as daily + hourly only and was generalised later ([[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 22:40, Q&A).

**2022-2023 (ICT era).** "Fractal" meant that ICT setups (liquidity run, displacement, FVG entry; MMXM) repeat on every timeframe, and pairing meant an HTF POI with an LTF entry model, usually a 15m/5m/1m stack with structure shifts that "domino" upward ([[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 20:50, 35:10; [[livestream_20220810_stream_q_a_with_trade_for_opportunity_ict_concepts_0bh_kkg2q6s]] 53:50). There were no candle numbers or closure rules yet.

## Rules

| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |
|---|---|---|---|
| **Core model** | | | |
| 1 | The model rests on swing points: price cannot reverse without one, so every trade is framed off an HTF swing high/low. | stated | [[fractal_model_fundamentals]] 00:22; [[intro_to_ttrades_fractal_model_indicator_settings]] 00:28; [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 41:10 |
| 2 | Sequence: HTF closure (sweep of the prior candle's extreme, close back inside), LTF CISD confirming the swing, then trade the following HTF candle's OHLC/OLHC in that direction. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 00:48-01:37; [[ttrades_fractal_model_inversion_intraday_strategy]] 00:31 |
| 3 | A valid fractal model = HTF candle 2 or candle 3 closure plus an LTF CISD inside that HTF candle on the paired timeframe. | stated | [[cisd_validates_swing_points]] 00:54; [[cisd_validates_swing_points]] 09:52 |
| 4 | C2 and C3 closures are the only two formations; closures + EQ (HTF wick location) + LTF CISD or continuation order block is the whole model. | stated | [[candle_3_closure_ttrades_fractal_model]] 10:31, 11:34 |
| 5 | Use closures with POIs and context; do not pattern-trade the model. | stated | [[candle_3_closure_ttrades_fractal_model]] 10:11; [[easy_daily_bias_mechanical_framework]] 09:00 |
| 6 | No daily bias, no drop to the hourly: the bias timeframe must give a direction before lower timeframes are read. | stated | [[fractal_model_fundamentals]] 01:10; [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 16:00; [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 55:40 (Q&A) |
| 7 | The fractal model does not try to catch the low; it lets the HTF low (wick) form and trades the continuation. | stated | [[how_to_trade_consolidation_phases_of_price]] 11:34; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 55:30 (Q&A) |
| 8 | Frame entries while the HTF wick is forming, in the T-spot (where the HTF wick is expected), not random continuations. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 28:00; [[ttrades_fractal_model_inversion_intraday_strategy]] 01:14 |
| 9 | If the HTF candle has no wick yet when the T-spot prints, expect a retrace into the T-spot to put the wick in before expansion. | stated | [[ttrades_fractal_model_inversion_intraday_strategy]] 03:36 |
| 10 | If the HTF candle has already expanded, let the next HTF candle form its wick and trade away from that. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 26:12 |
| 11 | The model only trades candle 3 and candle 4; if the candle-2 reversal is missed, trade the C3/C4 continuations. | stated | [[ttrades_fractal_model_trading_candle_2]] 17:58; [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 22:00 |
| 12 | A counter-HTF LTF setup that prints inside an HTF setup tends to fail immediately. | demonstrated | [[intro_to_ttrades_fractal_model_indicator_settings]] 15:31 |
| 13 | A mechanically valid C3/CISD continuation is not a trade without HTF backing and agreement with the day's context. | stated | [[livestream_20260729_new_york_open_live_q_a_xraklbjhw5k]] 28:30; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 17:20 |
| 14 | A trade needs daily bias, structure and the daily profile aligned; a swept-and-reclaimed hourly low alone is not enough. | stated | [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 42:10 |
| **Timeframe roles** | | | |
| 15 | Three roles: higher timeframe for bias, middle for structure (swing point / setup), lower for entry. | stated | [[timeframe_alignment_how_to_align_timeframes_for_expansion]] 00:31; [[trade_like_ttrades_top_down_analysis]] 02:30 |
| 16 | The structure timeframe shows the CISD forming the HTF wick and supplies POIs for the LTF. | stated | [[trade_like_ttrades_top_down_analysis]] 02:02 |
| 17 | No entries until the structure timeframe shifts (CISD/MSS) in the bias direction; then wait for a structure POI and align the entry timeframe. | stated | [[timeframe_alignment_how_to_align_timeframes_for_expansion]] 01:10, 10:06, 10:59 |
| 18 | Bias is aligned the same way as structure: the bias timeframe is the structure timeframe's own higher pair (5m entry -> 1h -> daily; 1m -> 15m -> 4H). | stated | [[timeframe_alignment_how_to_align_timeframes_for_expansion]] 02:27 |
| 19 | The third timeframe is optional: executing on the structure timeframe (e.g. hourly close, stop on the low, 2R) is valid when risk is manageable. | stated | [[trade_like_ttrades_top_down_analysis]] 12:41; [[ttrades_fractal_model_trading_candle_4]] 12:45; [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 59:20 (Q&A) |
| 20 | (2026) A C2 closure after the intraday reversal is a continuation and can be entered directly on the 1H (about 2R); refining lower is optional. | stated | [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 14:10; [[trade_continuations_using_breaker_blocks]] 11:52 |
| 21 | The trade logic always comes from the daily chart; lower timeframes only execute it; for intraday nothing above the daily matters. | stated | [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 17:15; [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 39:50 |
| 22 | An HTF opinion matters only at the horizon you hold: a monthly view is irrelevant to a 3m trade held 30 minutes. | stated | [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 1:27:00 |
| **Pairings** | | | |
| 23 | Two-timeframe pairs: W-4H, D-1H, 4H-15m, 1H-5m, 30m-3m, 15m-1m; M-D for monthly closures. | stated | [[timeframe_alignment_how_to_align_timeframes_for_expansion]] 02:13; [[cisd_validates_swing_points]] 04:51; [[trade_continuations_using_order_blocks]] 06:38 |
| 24 | Closure-to-CISD pairs: daily C2 -> hourly CISD, 4H -> 15m, hourly C2 -> 5m; a monthly wick is confirmed by a daily CISD. | stated | [[candle_2_closure_foundation]] 09:10; [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 1:00:00 |
| 25 | Indicator Automatic mode: 1H chart -> daily, 15m -> 4H, 5m -> 1H; a fixed pair stays the same on any chart; Custom allows any pair (e.g. 7H-15m). | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 06:20, 49:10 |
| 26 | Seconds pairs on the indicator: 30s pairs with 10m (not 3m), 15s with 5m. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 49:10 |
| 27 | Three-timeframe stacks named: 1D/1H/5m, 1D/4H/15m ("favorite"), 4H/15m/1m, 1D/30m/3m, 1H/15m/1m (scalp), W/D/1H and M/W/4H (swing), M/D/1H. | stated | [[fractal_model_fundamentals]] 02:52; [[the_best_timeframe_for_ttrades_fractal_model_simple]] 00:14; [[timeframe_alignment_how_to_align_timeframes_for_expansion]] 02:27; [[ttrades_fractal_model_trading_candle_4]] 06:00; [[ttrades_scalping_model_simple_day_trading_strategy]] 01:30; [[ttrades_swing_trading_model_simple_strategy]] 02:10; [[the_only_trading_strategy_you_need_for_2026]] 09:59 |
| 28 | (2026) Default for most traders: daily + hourly fractal for bias, 4H-15m model for execution. | stated | [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 10:00; [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 18:20 |
| 29 | (2026) 4H-15m is his current favourite pairing and the one to learn first (a mentee's 4 months of gold: 48 trades, 63% win rate, 63R at 2R targets). | stated | [[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 44:10; [[livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg]] 42:00; [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 1:35:00 |
| 30 | If limited to one alignment: daily + hourly fractal (e.g. daily C3 closure, 1H fractal, 1H IC-CISD). | stated | [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 14:00 |
| 31 | Use the highest pairing that makes sense (4H-15m or 1H-5m); lower timeframes chop people up even when direction is right. | stated | [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 32:40; [[livestream_20261006_new_york_open_live_q_a_rtomj8urfnw]] 16:00 |
| 32 | He does not like framing reversals / candle 2s below the 4H; focus reversal candles on the daily or 4H. | stated | [[easy_daily_bias_mechanical_framework]] 12:24 |
| **Alignment** | | | |
| 33 | Only trade LTF setups in the direction of the HTF expansion candle; never a bullish LTF setup inside an expected bearish HTF candle. | stated | [[trade_like_ttrades_top_down_analysis]] 00:48, 01:16; [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 07:00 |
| 34 | Timeframe alignment = find a low (high) all timeframes should form, then trade a fractal model in line with all of them. | stated | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 36:00; [[higher_timeframe_analysis_for_trading_aligning_expansion_candles]] 06:49 |
| 35 | True expansion comes when the daily and 4H candles both support expansion in one direction; daily + 4H aligned is enough to trade the 15m. | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:09:10; [[higher_timeframe_analysis_for_trading_aligning_expansion_candles]] 01:33 |
| 36 | Easiest expansion: candle 3s aligned on several timeframes (daily C3 + 4H C3 + 15m protected swing; or daily C3 + a 4H C2 that gives a 15m C3). | stated | [[the_best_timeframe_for_ttrades_fractal_model_simple]] 03:03, 10:22; [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 09:00; [[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 31:40 |
| 37 | A candle with a small wick supports expansion, a large wick does not; when an HTF candle does not support expansion, expect a move only back to its open and wait for its close. | stated | [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 05:00; [[ttrades_top_down_chart_lessons_4]] 03:58 |
| 38 | Measure the opposing run on the HTF candle of the pair (the 1h candle when executing on 5m): open to the extreme against your bias. | stated | [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 03:15 |
| 39 | Trading against the current 4H candle is fighting every timeframe; prefer the continuation; an LTF reversal against the 4H is a clue for correlated assets, not a trade. | stated | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 16:55; [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 28:40; [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 1:16:40 |
| 40 | If the 4H/1H/15m candles oppose your idea, wait for a small wick on the next candle (e.g. 10:00) instead of fighting them; require a continuation before any reversal entry against unaligned HTF candles. | stated | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 32:40; [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 14:10 |
| 41 | If the daily is aligned but the 15m structure is against you, wait for the 15m to switch; trading before that means you are just wrong. | stated | [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 48:40; [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 04:20 |
| 42 | An LTF reversal does not by itself cancel the HTF idea; a move can be an LTF reversal and an HTF continuation at once; frame it by the HTF. | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 28:40; [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 51:40 |
| 43 | Wait for the HTF candle (e.g. the 5m above a 15s model) to close in your direction before the LTF model is valid; he prefers the HTF close, not only the LTF one. | stated | [[livestream_20260826_ttrades_mnq_cup_afternoon_session_h1zqwwqdhka]] 54:00; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 48:30 |
| 44 | Don't go to lower timeframes until there is HTF context (e.g. wait for the 10:00 4H, see the C3 closure, then go to 1H and 5m). | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:13:40; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 33:40 |
| 45 | With indices pointing opposite ways and no HTF bias preferring one, expect consolidation and stand aside. | stated | [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:08:20 |
| 46 | Indicator Auto Bias 1 shows a model only if the next pair up also has a valid model (H1-M5 needs H4-M15); Auto Bias 2 needs a valid model two pairs up (D-H1). | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 07:30; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 59:10 |
| **Moving between timeframes** | | | |
| 47 | If a timeframe is messy, move up one (30m->1h, 1h->4h); don't force a rigid alignment. | stated | [[ttrades_swing_trading_model_simple_strategy]] 11:18; [[internal_external_liquidity_model_ict_concepts]] 08:50; [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 54:10 |
| 48 | Right on bias but stopped before the move: move up one entry timeframe (H1-M5 becomes H1-M15); do not just widen the stop. | stated | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 55:40; [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 57:50; [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 49:10 |
| 49 | If the entry-timeframe continuation does not give 2R to the target, refine down (5m -> 3m -> rarely 1m). | stated | [[ttrades_top_down_chart_lessons_2]] 06:21; [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 27:30; [[livestream_20260915_new_york_open_live_q_a_hlwq1drjbzo]] 27:00 |
| 50 | If waiting for the structure-timeframe CISD/close would put entry at the target or miss the move, drop one timeframe (15m -> 5m) for the closure. | stated | [[ttrades_fractal_model_trading_candle_2]] 10:27; [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 20:00; [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 37:00 |
| 51 | If the daily gives no clear closure, drop to the 4H (a 4H reversal candle lets the next 4H expand); if the 1H gives no C2, use the 30m. | stated | [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 1:15:30; [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 43:20; [[ttrades_top_down_chart_lessons_1]] 02:02, 07:20 |
| 52 | Don't drop to very low timeframes without a reason, when choppy after the move, or out of fear of missing it; the higher timeframe stops you being stopped out. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 10:15; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 27:20; [[livestream_20260910_new_york_open_live_q_a_wa9m30uhrm0]] 21:10 |
| 53 | Fractalize: on a lower pair, treat the LTF candle exactly like a daily one (previous candle's high instead of PDH, 0.5 respected, low not taken). | stated | [[ttrades_top_down_chart_lessons_2]] 08:21; [[easy_daily_bias_mechanical_framework]] 11:13 |
| **Session and asset** | | | |
| 54 | Confirmation timeframe for a daily C2 by session: Asia 1h/30m; London 1h/30m/15m; New York 1h/30m if present, often lower because NY reversals are fast. | stated | [[ttrades_fractal_model_trading_candle_2]] 10:15; [[easy_daily_bias_mechanical_framework]] 06:53 |
| 55 | (2026) Session pairings: Asia D-H1 or H4-M15; London H4-M15 (preferred, after the Asia range is taken) or H1-M5; New York AM H4-M15, H1-M5 or M30-M3. | stated | [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 36:00; [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:39:30; [[livestream_20260729_new_york_open_live_q_a_xraklbjhw5k]] 18:20 |
| 56 | Before 9:30 stay on the 15m (H4/M15 or 7H->15m); near/after 9:30 use an LTF aligned model (1H-5m or 30m-3m); before 10:00 an open trade needs a 30m/3m fractal because the hourly closes at 10:00. | stated | [[a_simple_3_step_trading_model_full_breakdown]] 34:41; [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 1:26:20; [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 14:10; [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 44:10 |
| 57 | Pre-open continuation entries go on the 15m, not the 5m (the 5m chops you out). | stated | [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 39:00 |
| 58 | 4H-15m: stay with the bias for the whole 06:00-10:00 4H candle; the LTF expansion should finish before 10:00 (time-box it). | stated | [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 24:00 |
| 59 | Pick the setup timeframe from when you expect expansion (wanting the 10:00 move meant 15m with 1m entries, not 30m/1H). | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 58:30 |
| 60 | Lifestyle pairings: 9-to-5 traders D-H1 (check hourly) or a 4H model; swing = the model on a higher pair (D-H1 positional; M-D for stocks); beginner = simple 4H-15m. | stated | [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:39:30; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 42:10; [[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 36:20 |
| 61 | Positional swing trades use daily and hourly, not weekly and 4H; he does not use a weekly-4H model. | stated | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 55:40; [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 37:40 |
| 62 | Currencies: never below the 15m intraday, prefer 4H-15m or the hourly; crypto: higher stacks (D-H4-15m, D-H1) because LTFs sweep both sides. | stated | [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:09:15; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 1:13:50; [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 16:00 |
| 63 | (2026) Preferred entry timeframes 5m and 15m; avoid below 3m, 1m only when needed; do not trade seconds timeframes. | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 51:20; [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 33:50; [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 48:30 |
| 64 | Scalping model: align with the hourly candle instead of the daily; find the 15m swing point (C2 closure) that forms the hourly wick; 1m continuations inside it; only when hourly and 15m continue the same way. | stated | [[ttrades_scalping_model_simple_day_trading_strategy]] 00:25, 00:56, 01:30; [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 41:40 |
| 65 | Relative strength picks the asset (on the execution timeframe); the bias can come from one index and the trade from another. | stated | [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 1:12:10; [[eurgbp_for_relative_strength_eu_vs_gu]] 07:39 |
| **Earlier-era stacks (context)** | | | |
| 66 | (2022) Intraday stack 15m/5m/1m: liquidity run on 15m, shift with FVG on 5m, entry in an FVG on 1m; enter on 1m or even 15s only at an HTF POI. | stated | [[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 20:50; [[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 48:50 |
| 67 | (2022) Don't look at lower timeframes until an HTF reason exists; daily and hourly for bias, hourly/15m for POIs, 5m-1m for entry. | stated | [[livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4]] 30:20, 45:20 |
| 68 | (2022, guest Ben) Separate the sponsorship timeframe (idea and target) from the execution timeframe; the sponsor sets the target. | stated | [[livestream_20220911_fractalizing_entries_q_a_with_ben_ict_concepts_yrmkkr4coju]] 18:00, 16:40 |
| 69 | (2023) For a 1m entry use a 4H/1h draw; for 5m, a daily/4H draw; entering on the 1h, look to weekly/monthly. | stated | [[ict_son_s_model_higher_time_frames]] 00:34, 05:07; [[draw_on_liquidity_dol_ict_concepts]] 00:06 |
| 70 | (2024) Preferred pairing daily / hour / 5m because it aligns with the daily candle's formation and the economic calendar. | stated | [[internal_external_liquidity_model_ict_concepts]] 15:31; [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 17:30 |

## Engine notes

- The companion's three roles `stack.bias / stack.setup / stack.entry` and "the same pairing links bias to setup and setup to entry" follow rules 15 and 18 ([[timeframe_alignment_how_to_align_timeframes_for_expansion]] 00:31, 02:27; `companion/styles/ttrades/rules.md` 4.1).
- The engine's pairing and stack tables (rules.md 4.2) list the pairs of rules 23 and 27. A stack outside them (e.g. 1D/15m/1m) still runs and is flagged by the advisory `stack_pairing_stated` (rules.md 4.2, open question 22). The 2026 Auto Bias ladder (rule 46) and the 7H-15m and 30s-10m pairs (rules 25-26) are not in the engine's tables (inference).
- The engine always requires three roles; the teacher allows two (rules 19-20, D-H1 alone, entry on the structure timeframe). The engine cannot enter on `S` (inference from rules.md 2.1 and 6).
- No bias, no trade (engine 5.4) matches rule 6. The engine does not encode "pattern trading" beyond requiring bias (inference).
- Session-dependent confirmation timeframe (rule 54) is approximated: for a daily bias only, the reversal CISD may be read on `E` instead of `S` in the New York window (rules.md 4.3; open question 19). The 2026 session pairings (rules 55-58) and the "move up / refine down" rules (47-52) are not implemented: the stack is fixed per run (inference).
- The engine generalises PDH/PDL/EQ/daily open to `B[-1]` / `B[0]` (rules.md 4.3), which is rule 53 (fractalize) in TTrades' own words ([[easy_daily_bias_mechanical_framework]] 11:13).
- Multi-timeframe expansion alignment (rules 35-37, daily + 4H both supporting expansion) has no criterion: only the bias candle and the setup candle are read (inference). Relative strength / cross-asset bias (rule 65) is out of scope for a single-symbol engine (rules.md open question 23).
- The engine's 4.2 note "prefers not to frame reversals from a bias timeframe below 4h" cites rule 32; the engine does not block such stacks (inference).

## How it changed over time

- **2022 (ICT-concepts Q&A streams).** "Fractal" = ICT setups repeating across timeframes; 15m/5m/1m stacks with 15s/30s refinement, dominoing structure shifts, HTF POI then LTF confirmation ([[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 35:10; [[livestream_20220810_stream_q_a_with_trade_for_opportunity_ict_concepts_0bh_kkg2q6s]] 53:50). Guests add sponsorship vs execution timeframes and "trading inside every HTF candle at once" ([[livestream_20220911_fractalizing_entries_q_a_with_ben_ict_concepts_yrmkkr4coju]] 58:40). Top-down depth follows the entry timeframe ([[top_down_analysis_ict_concepts]] 00:06).
- **2023.** Daily -> lower TF POI -> lower TF entry chain ([[top_down_analysis_daily_bias_to_entries_ict_concepts]] 01:53); next-4H-candle OLHC traded on the 5m ([[open_high_low_close_ohlc_olhc_ict_concepts]] 03:10); CISD on the hourly after a daily FVG ([[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 04:51); "concepts are fractal: weekly the same as 5-minute" ([[intraday_bias_simplified_ict_concepts]] 24:24).
- **2024.** Preferred pairing daily/hour/5m ([[internal_external_liquidity_model_ict_concepts]] 15:31); Sunday streams call the model fractal and identical on every timeframe ([[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 44:40); execute on the 5m, rarely lower ([[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 37:50); daily wick -> hourly, hourly wick -> 5m ([[master_candlestick_wicks_the_key_to_catching_reversals]] 02:45); TTFM indicator launch with Automatic pairing and the Overlap trick ([[intro_to_ttrades_fractal_model_indicator_settings]] 04:11, 14:12).
- **2025.** Timeframe alignment video fixes the pair list and the bias-from-structure's-pair rule ([[timeframe_alignment_how_to_align_timeframes_for_expansion]] 02:13, 02:27); top-down roles D/1H/5m ([[trade_like_ttrades_top_down_analysis]] 02:30); 4H-15m for the 4H power of three ([[trading_the_4_hour_power_of_three_ohlc_olhc]] 04:48); session-dependent confirmation timeframe ([[ttrades_fractal_model_trading_candle_2]] 10:15); C2/C3 closures declared the only formations ([[candle_3_closure_ttrades_fractal_model]] 10:31); no reversal framing below 4H ([[easy_daily_bias_mechanical_framework]] 12:24).
- **2026 (education-centre videos).** Favourite D/4H/15m ([[the_best_timeframe_for_ttrades_fractal_model_simple]] 00:14); scalping model H1/15m/1m and swing model W/D/1H, M/W/4H ([[ttrades_scalping_model_simple_day_trading_strategy]] 00:25; [[ttrades_swing_trading_model_simple_strategy]] 02:10); 3-step model with 7H->15m pre-open ([[a_simple_3_step_trading_model_full_breakdown]] 34:41).
- **2026 (New York Open Live streams).** "I really like the 4-hour 15 model currently" ([[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 44:10), the default becomes D-H1 bias + 4H-15m execution ([[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 10:00); seconds charts rejected ([[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 48:30); weekly-4H model not used ([[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 37:40); Auto Bias 1/2 alignment in the indicator ([[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 07:30); "daily bias, intraday reversal, aligned fractal model" ([[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:16:00). He explicitly retires the old silver-bullet and box-setup videos in favour of the model ([[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 59:20; [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 21:00).

## Examples

- NQ 1D -> 1h -> 5m, 17 Jan 2025: daily sweep of PDH into an FVG with a bearish close, hourly CISD, 5m entry; stopped because the POI was not respected and candle 3 went the wrong way first ([[fractal_model_fundamentals]] 04:34-07:15).
- Gold 1D -> 1h -> 5m: daily lows swept with a bullish closure, hourly sweep + one-candle CISD, 5m close over the down-close series, stop on the protected low, 2R hit ([[fractal_model_fundamentals]] 07:18-10:45).
- Indicator Overlap: an HTF T-spot refined by a 5m T-spot from a second indicator copy; a counter-HTF 5m setup inside it fails at once ([[intro_to_ttrades_fractal_model_indicator_settings]] 14:12-15:40).
- Oil quiz: anticipate the hourly candle lower, align a 15m swing point, enter on a 1m candle 3 closure; not the 5m because it would likely give no CISD ([[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 52:30).
- Gold daily + hourly: daily C3 closure, hourly fractal model with an IC-CISD, so lower until 10:00; stop on the high ([[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 14:00).
- 10:00 expansion: 4H expanded, 10:00 candle, 15m swing point, 1m fractal model; the LTF setup only valid because of the HTF path ([[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 30:30).

## Conflicts and open questions

See [[conflicts]] and `_merge/fractal-model/conflicts-fragment.md`.

- FM-1 Default pairing: D-1H vs 4H-15m vs D/4H/15m vs D/1H/5m.
- FM-2 Bias timeframe for a given setup: structure's own pair (5m -> 1H -> D) vs Auto Bias ladder (H1-M5 -> H4-M15 -> D-H1).
- FM-3 Weekly-4H: listed and taught for swings vs "I don't use the weekly 4-hour model".
- FM-4 Lowest entry timeframe: 1m/15s (2022, 2026 15s model) vs "not below 5m/3m", "no seconds".
- FM-5 Pre-9:30 setup pair: 7H->15m vs H4/M15; session-dependent switching vs a fixed stack.
- FM-6 Three timeframes required (engine) vs two allowed (teacher).
- FM-7 Entering on the structure timeframe is allowed by the teacher, impossible in the engine.
- FM-8 When to drop a timeframe for the closure vs wait for the HTF close.
- FM-9 Stopped out: move up vs no 2R: refine down; no rule which wins.
- FM-10 Reversal framing below 4H discouraged vs taught 1H C2 -> 5m and 15m C2 scalps.
- FM-11 Indicator Bias field reads Neutral while he is directional.
- FM-12 "Supports expansion" across daily/4H/1H has no engine definition.
- FM-13 Bias timeframe for a 30m setup is not in the pair list.
- FM-14 DTR C2U enters inside C2; TTFM waits for the closure.
- FM-15 Kill zones "don't matter" vs time filters and kill-zone models.
- FM-16 FX/crypto timeframe floors vary between streams.
- FM-17 Relative-strength asset choice vs single-symbol engine.
- FM-18 CRT relation stated three ways.
- FM-19 Daily-profile read timeframe (1H vs 4H/1H vs any).
- FM-20 ICT-era stacks vs TTFM pairs; only the silver-bullet and box-setup videos are explicitly retired.

## Related

- [[candle-closures]]: C2/C3/C4 closures are the formations the model is built from.
- [[cisd]]: the LTF confirmation inside the HTF candle.
- [[swings-and-structure]]: swing points and protected swings the model trades away from.
- [[daily-bias]]: the bias timeframe's job; "no bias, no hourly".
- [[profiles]]: daily/weekly profile = middle-timeframe structure of the HTF candle.
- [[ranges-and-eq]]: EQ / T-spot where the HTF wick should form.
- [[entry-models]]: continuation order blocks, IFVG, breakers used on the entry timeframe.
- [[sessions-and-time]]: session-dependent pairings, 9:30/10:00 timing.
- [[ttfm-indicator]]: Automatic/fixed/custom fractal, Auto Bias, X-Y Model table.
- [[smt-and-psp]]: SMT as confirmation at the HTF level.
- [[risk-and-management]]: 2R, moving timeframe instead of widening stops.

## Questions this page answers

- What is the TTrades fractal model in one sentence, and why is it called fractal?
- Which timeframe pairs does TTrades use (W-4H, D-1H, 4H-15m, 1H-5m, 30m-3m, 15m-1m)?
- Which pairing does he prefer in 2026, and which did he prefer in 2024?
- Do I need three timeframes, or is daily-hourly alone enough?
- Can I enter on the hourly without refining to the 5m?
- Which timeframe confirms a daily / 4H / hourly / monthly candle 2?
- What is timeframe alignment and when are timeframes "aligned"?
- When should I move up a timeframe and when should I refine down?
- Which pairing for London, New York pre-open and after 9:30?
- How do Auto Bias 1 and Auto Bias 2 relate to timeframe pairs?
- Why is an LTF setup without HTF bias rejected ("pattern trading")?
- What pairings suit forex, crypto, stocks and swing trading?
