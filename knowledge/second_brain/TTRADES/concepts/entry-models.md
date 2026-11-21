---
id: entry-models
title: "Entry models: reversal and continuation entries, triggers, order type, the playbooks"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [entry model, entry models, setup, setups, playbook, entry function, entry trigger, continuation entry, reversal entry, positional entry, aggressive entry, retest entry, phases of price, phases of price delivery, expansion met with expansion, V-shaped reversal, 2022 model, 2022 mentorship model, model 1, model 3, OTE entry, unicorn, unicorn model, box setup, inducement model, IDM, reversal sequence, TTRS, smart money reversal, SMR, MMXM, market maker buy model, market maker sell model, next day model, twitter model, chasing, "I model"]
covers: [entry-models, reversal-entry, continuation-entry, continuation-order-block-entry, positional-entry, entry-order-type, missed-entry-and-chasing, phases-of-price, reversal-sequence, ict-2022-model, ote-entry, inducement-model, box-setup, unicorn-model, mmxm-models, range-deviation-trade]
sources: [why_your_continuations_fail_order_blocks_cisd_explained, the_only_trading_strategy_you_need_for_2026, trade_continuations_using_order_blocks, reversal_sequence_ttrs_how_to_blend_pd_arrays, how_to_trade_reversal_phases_of_price, trading_candle_3, the_phases_of_price_action_a_blueprint_for_market_movement, easy_daily_bias_mechanical_framework, the_best_timeframe_for_ttrades_fractal_model_simple, a_simple_3_step_trading_model_full_breakdown, trading_the_4_hour_power_of_three_ohlc_olhc, trade_like_ttrades_top_down_analysis, protected_swings_understanding_trend_and_invalidations, wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles, ttrades_scalping_model_simple_day_trading_strategy, livestream_20260313_new_york_open_live_q_a_bmkromkeunu, livestream_20260325_new_york_open_live_q_a_aqny1yzvfys, livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c, livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o, a_ict_entry_checklist_ict_concepts, ote_optimal_trade_entry_ict_concepts, livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4, breaker_blocks_simplified_ict_concepts, market_structure_shift_vs_change_in_state_of_delivery_ict]
confidence: medium
chain_step: ["3 setup", "4 entry"]
timeframe_role: [setup, entry]
requires: [daily-bias, fractal-model, candle-closures, cisd, swings-and-structure, poi-and-pd-arrays, liquidity]
feeds: [risk-and-management]
---

# Entry models

## Definition

Latest (2025-2026): an entry model is a swing formation, taken at a point of interest, that agrees with an idea you already hold: "have an idea (bias) and find a swing formation that aligns with it" ([[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 20:10). There are two families. A **reversal entry** trades the swing while it forms: expansion into a relevant high/low met by an opposing expansion (V-shape) and a close through the series of opposing candles (CISD) ([[how_to_trade_reversal_phases_of_price]] 08:30). A **continuation entry** trades after the swing is confirmed: price reaches into a POI (an FVG or a swept short-term low), then closes back through the series of opposing candles in one to three candles, which leaves a new protected swing; he enters on that close, stops on the protected swing and targets 2R ([[the_only_trading_strategy_you_need_for_2026]] 02:57, 03:11; [[why_your_continuations_fail_order_blocks_cisd_explained]] 00:34, 09:55). He prefers continuations and, in 2026 livestreams, says he does not trade reversals at all ([[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 50:10; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:04:20). The 2026 toolkit is only highs/lows, FVGs, CISD, EQ and candle (OHLC) logic, with SMT as confluence ([[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 05:50; [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 45:40).

2025 framing: the same entries are read as **phases of price** at a level: expansion, retracement, consolidation, reversal. A reversal is "expansion met with expansion"; a continuation signature is expansion-retracement-expansion or expansion-consolidation-manipulation-expansion ([[how_to_trade_reversal_phases_of_price]] 00:33, 00:42; [[the_phases_of_price_action_a_blueprint_for_market_movement]] 01:13).

2023-2024: entries were PD-array blends. The **reversal sequence** runs purge (turtle soup) → inversion → CISD / order-block formation → FVG and/or breaker; the later the entry, the more confirmation and the worse the price ([[reversal_sequence_ttrs_how_to_blend_pd_arrays]] 05:23, 06:19). CISD and OB retests replaced MSS entries ([[market_structure_shift_vs_change_in_state_of_delivery_ict]] 03:49, 08:21); the unicorn (breaker + overlapping FVG) was taught as a model ([[breaker_block_fvg_entry_model_ict_concepts]] 02:02).

2022: "entry model" meant ICT's 2022 mentorship model as a labelled diagram: liquidity run at the open or a HTF POI, a 5m/1m market structure shift with displacement, then a retracement into the FVG in discount (longs) or premium (shorts), often refined with OTE (0.62-0.79), inducement or a box setup ([[livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4]] 34:10; [[build_an_entry_model_ict_concepts]] 01:47; [[ote_optimal_trade_entry_ict_concepts]] 00:34). Early 2022 videos used Strat candle triggers off plotted levels ([[simple_day_trading_strategy_intro]] 01:03).

## Rules

| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |
|---|---|---|---|
| **Where an entry model is allowed** | | | |
| 1 | Never enter just because price reached a POI; wait there for a lower-timeframe model (displacement, closure, CISD). | stated | [[find_lower_time_frame_entries_using_bias_ict_concepts]] 01:58; [[higher_time_frame_points_of_interest_ict_concepts]] 04:17; [[lower_time_frame_entries_using_htf_poi_ict_concepts]] 01:34; [[cisd_validates_swing_points]] 9:21 |
| 2 | Look for the lower-timeframe model only at a HTF POI or relevant high/low, not all the time; trade against the trend only after such a level is hit. | stated | [[higher_time_frame_points_of_interest_ict_concepts]] 00:52; [[how_to_trade_reversal_phases_of_price]] 10:57 |
| 3 | A formation that prints is not a trade: the structure and HTF bias must also align, and concepts must be combined into one defined, labelled model. | stated | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 29:40; [[livestream_20260616_new_york_open_live_q_a_tjuolmjncmy]] 33:10; [[build_an_entry_model_ict_concepts]] 01:47; [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 42:40 |
| 4 | The model is: hold a bias, then find a swing formation that aligns with it. | stated | [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 20:10 |
| 5 | (2026) Use only highs/lows, FVGs, CISD, EQ and OHLC logic (SMT as confluence); no OTE, breakers, rejection blocks, Fib, silver bullet, kill zones, BOS/MSS. | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 05:50; [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 45:40; [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 41:15; [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 15:00 |
| 6 | No raid, no trade: the setup needs a sweep of liquidity or a reach into a POI first; a close through opposing candles that tagged neither is not a continuation. | stated | [[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 15:40; [[ttrades_fractal_model_inversion_intraday_strategy]] 06:39; [[trade_continuations_using_order_blocks]] 14:04; [[why_your_continuations_fail_order_blocks_cisd_explained]] 10:49 |
| 7 | No trade when the structure cannot be read; skip consolidating or choppy markets even when a mechanical setup prints. | stated | [[ict_silver_bullet_strategy_no_daily_bias_with_backtest]] 20:27; [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 29:40; [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 18:40 |
| **Reading the phase of price at the level** | | | |
| 8 | (2024-2026) A reversal is expansion met with expansion: an expansion into the level answered straight away by an opposing expansion (V-shape). | stated | [[fractal_model_fundamentals]] 07:35; [[how_to_trade_reversal_phases_of_price]] 00:33; [[the_phases_of_price_action_a_blueprint_for_market_movement]] 01:13; [[ttrades_top_down_chart_lessons_1]] 00:37 |
| 9 | Continuation signatures are expansion → retracement → expansion and expansion → consolidation → manipulation → expansion. | stated | [[how_to_trade_reversal_phases_of_price]] 00:42; [[the_phases_of_price_action_a_blueprint_for_market_movement]] 00:42; [[how_to_trade_retracement_phases_of_price]] 3:54 |
| 10 | A fast move back against an expansion is a reversal; a slow, shallow move back is a retracement (continuation). | stated | [[how_to_trade_retracement_phases_of_price]] 2:47; [[ttrades_top_down_chart_lessons_3]] 00:54; [[market_structure_shift_vs_liquidity_grab_ict_concepts]] 04:35 |
| 11 | Ideal reversal structure: expansion that sweeps lows, displacement back in, and a close over the series of down-close candles (V-shape + CISD). | stated | [[how_to_trade_reversal_phases_of_price]] 08:30; [[ttrades_fractal_model_trading_candle_2]] 13:27; [[gxtradez_phases_of_price_profiles_for_expansion]] 09:03 [guest] |
| 12 | Do not call a reversal before displacement (full-bodied candles) prints the other way; a nice close without a CISD is not a reversal. | stated | [[market_structure_shift_vs_liquidity_grab_ict_concepts]] 05:50; [[the_phases_of_price_action_a_blueprint_for_market_movement]] 08:57; [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 30:40 |
| 13 | Expect reversals only at relevant highs/lows (previous day high/low, relevant swings), never mid-range on the way to the target. | stated | [[the_phases_of_price_action_a_blueprint_for_market_movement]] 12:47; [[easy_daily_bias_mechanical_framework]] 00:30; [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 45:00 |
| 14 | When a reversal and a retracement-then-continuation are both alive, do nothing until price shows its phase (the next 1-3 closures at the level). | demonstrated | [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 32:10; [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 24:00 |
| 15 | A reversal very close to the high, or one that consolidates at the level, is untrusted: wait for a V-shape plus a continuation, or treat the consolidation's extreme as the new reversal point. | stated | [[the_only_trading_strategy_you_need_for_2026]] 05:31; [[gxtradez_phases_of_price_profiles_for_expansion]] 09:30 [guest]; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 14:10 |
| 16 | After a sweep, require immediate aggressive displacement; a mere retracement means continuation in the sweep's direction. | stated | [[ict_silver_bullet_strategy_no_daily_bias_with_backtest]] 15:55; [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 47:40 |
| **Reversal entries** | | | |
| 17 | (2025-2026) Frame reversals off the previous day's high or low; target the range EQ first, then the opposite extreme. | stated | [[easy_daily_bias_mechanical_framework]] 00:30, 00:37; [[how_to_trade_consolidation_phases_of_price]] 12:20 |
| 18 | Trade the reversal candle itself only with a shallow wick and an LTF CISD; with a large wick, let it close and trade the next candle (candle 3). | stated | [[easy_daily_bias_mechanical_framework]] 01:12; [[trading_candle_3]] 00:58, 01:08; [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 05:40 |
| 19 | Do not enter late in a candle after a long reversal formation; wait for the next HTF candle to open. | stated | [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 21:40; [[gxtradez_phases_of_price_profiles_for_expansion]] 1:01:20 [guest] |
| 20 | Do not trust a reversal from a low with no valid separation from the previous low until the nearby low is taken. | stated | [[which_swing_highs_and_lows_matter_in_trading]] 02:01, 08:49; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 54:30 |
| 21 | Highest-conviction reversal: a daily candle closure reversal, a CISD and expansion met with expansion at the same time. | demonstrated | [[the_phases_of_price_action_a_blueprint_for_market_movement]] 10:46 |
| 22 | (2024-2026) He mostly skips reversal days and reversal trades; he waits for the reversal to print and trades the next day's continuation. | stated | [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 21:00; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 50:10; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 25:20; [[ttrades_top_down_chart_lessons_2]] 01:09 |
| **Continuation entries** | | | |
| 23 | A continuation needs a reversal first (purge + CISD / protected swing); missing the reversal entry is not missing the move. | stated | [[trade_continuations_using_order_blocks]] 00:18, 00:30; [[protected_swings_understanding_trend_and_invalidations]] 16:00 |
| 24 | Continuation order block = a sweep of a short-term low or a reach into an FVG, then a close through the series of opposing candles that went into the POI. | stated | [[the_only_trading_strategy_you_need_for_2026]] 02:57; [[the_best_timeframe_for_ttrades_fractal_model_simple]] 09:14; [[why_your_continuations_fail_order_blocks_cisd_explained]] 00:34 |
| 25 | The close through must be quick and V-shaped (1, 2, maybe 3 candles); slower means consolidation, and the later close over is a manipulation of that range. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 01:25, 09:55; [[trading_candle_3]] 19:32 |
| 26 | Do not buy the FVG touch; an FVG reach without a close over the opposing candles is not a continuation. | stated | [[how_to_trade_retracement_phases_of_price]] 9:16; [[the_only_trading_strategy_you_need_for_2026]] 10:52 |
| 27 | Each new protected swing in a trend is another continuation entry; repeat after each new sweep. | stated | [[protected_swings_understanding_trend_and_invalidations]] 06:11, 13:52; [[trading_irl_erl_with_order_blocks_ict_concepts]] 10:56 |
| 28 | Continuation entries are higher probability than the reversal entry: trade the 1st or 2nd stage of distribution, not the low-risk sell. | stated | [[trade_continuations_using_order_blocks]] 06:03; [[the_ote_trader_i_turned_profitable_with_this_stage_of_ict_s_mmxm_models]] 02:18 [guest] |
| 29 | Prefer the first continuation in candle 3; later ones feel like chasing. | stated | [[trading_candle_3]] 34:39 |
| 30 | Preferred: HTF continuation traded with an LTF continuation; on a weak or expanded HTF setup demand an LTF continuation; an LTF reversal is allowed only with a strong HTF bias. | stated | [[trading_candle_3]] 10:46, 17:23, 25:31 |
| 31 | If the continuation's close also takes out range highs or a short-term target, wait for another continuation; prefer continuations taken before short-term targets go. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 02:16, 16:18; [[trade_continuations_using_order_blocks]] 15:01 |
| 32 | Stop looking for continuations once a HTF objective is hit or after 1-3 HTF expansion candles. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 03:38, 28:54; [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 08:26 |
| 33 | In expansion, do not wait for discount; skip deep retracements (OTE depth), because expansions do not retrace deeply. | stated | [[how_to_trade_expansion_phases_of_price]] 01:32; [[ttrades_fractal_model_trading_candle_4]] 10:02; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 1:01:40 |
| 34 | Let the HTF wick form, then trade the body; frame entries while the HTF wick is forming, confirmed by an intraday CISD. | stated | [[trading_the_4_hour_power_of_three_ohlc_olhc]] 03:57; [[why_your_continuations_fail_order_blocks_cisd_explained]] 28:00; [[easy_daily_bias_mechanical_framework]] 02:04 |
| 35 | (2026 3-step model) Every entry waits for the 8:00 candle's wick, then trades the body; for a NY reversal, take the continuation after it. | stated | [[a_simple_3_step_trading_model_full_breakdown]] 32:33, 34:20 |
| 36 | (2026 3-step model) On a continuation day the new day's low (bull) must form beyond 50% of the previous daily candle (close to opposing extreme); a run through it kills the day. | stated | [[a_simple_3_step_trading_model_full_breakdown]] 15:12, 15:47 |
| **Trigger and order type** | | | |
| 37 | Default trigger: market entry on the close through (fills near the next open), stop on the protected swing, target 2R. | stated | [[the_only_trading_strategy_you_need_for_2026]] 03:11; [[the_best_timeframe_for_ttrades_fractal_model_simple]] 05:44; [[why_your_continuations_fail_order_blocks_cisd_explained]] 12:06; [[ttrades_scalping_model_simple_day_trading_strategy]] 04:36; [[intro_to_ttrades_fractal_model_indicator_settings]] 02:07 |
| 38 | Prefer the close over waiting for a retest, since the retest may never come ("I'd rather be late than early"). | stated | [[trade_like_ttrades_top_down_analysis]] 09:54; [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 33:50; [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:24:10; [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 26:00 |
| 39 | When the close is too far from the stop to give the R wanted (e.g. 2R to the high), use a retest/limit; around 1R a market entry is fine. | stated | [[trading_irl_erl_with_order_blocks_ict_concepts]] 07:47; [[trade_continuations_using_order_blocks]] 10:12; [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 32:00; [[ttrades_fractal_model_inversion_intraday_strategy]] 07:08 |
| 40 | If the closure candle is so large that the stop is far away, do not enter on it; wait for a new continuation with its own protected swing. | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:24:10; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 28:00 |
| 41 | Right after price took nearby highs, prefer the retest over the close (expect a retracement); a stop on full-bodied candles' bodies is allowed. | stated | [[the_only_trading_strategy_you_need_for_2026]] 11:17 |
| 42 | In the breaker and scalping videos, close versus retest is the trader's choice: being in the trade versus better R:R and the risk of no fill. | stated | [[trade_continuations_using_breaker_blocks]] 01:43; [[breaker_blocks_simplified_ict_concepts]] 06:43; [[ttrades_scalping_model_simple_day_trading_strategy]] 04:47 |
| 43 | He enters with market orders, not stop orders. | stated | [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 41:10 |
| 44 | Do not rest limits inside FVGs (they get run through); let a reaction validate a new order block, then enter with a defined stop. | stated | [[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 48:20 |
| 45 | Positional entry: with the model complete and a protected swing formed before the new HTF candle opens, enter at that open, stop on that swing, 2R; only with high bias confidence. | stated | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 41:40; [[livestream_20260915_new_york_open_live_q_a_hlwq1drjbzo]] 42:30; [[trading_the_4_hour_power_of_three_ohlc_olhc]] 13:31; [[ttrades_fractal_model_inversion_intraday_strategy]] 13:46 |
| 46 | A high-confidence positional entry may skip the reversal entry, stop above 0.5 of the wick; a large T-spot makes it poor R:R, so wait for price to return. | stated | [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 1:32:20; [[ttrades_fractal_model_inversion_intraday_strategy]] 16:09 |
| 47 | On a very aggressive reversal at the open of a new HTF candle, enter at the open (little retracement expected), target 2R. | stated | [[trading_the_4_hour_power_of_three_ohlc_olhc]] 20:00 |
| 48 | Mean-threshold / CE entries raise R:R but risk no fill; use them when the order block is a large series or the OB retest gives about 1R. | stated | [[order_blocks_simplified_ict_concepts]] 04:29, 09:46; [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 03:49; [[inversion_fair_value_gaps_ifvg_ict_concepts]] 03:48 |
| 49 | Do not enter where you cannot partial before or at the short-term targets with good R:R; wait for a retracement into the range. | stated | [[ttrades_top_down_chart_lessons_2]] 05:38; [[ttrades_swing_trading_model_simple_strategy]] 11:59 |
| **Missed entries, chasing, too late** | | | |
| 50 | A missed entry is fine: take a later continuation off a new protected swing while the HTF target is open and 2R is available, otherwise let it go. | stated | [[trading_the_4_hour_power_of_three_ohlc_olhc]] 09:17; [[trade_like_ttrades_top_down_analysis]] 13:33; [[ttrades_top_down_chart_lessons_2]] 09:14 |
| 51 | Do not chase: once price ran far, sits at the day's extreme, or the HTF candle already expanded, skip ("I want to short before the expansion, not after"). | stated | [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 27:40; [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 16:20; [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 07:20 |
| 52 | Late in the HTF candle is too late (e.g. an NQ short at 09:50); wait for the next HTF open (10:00) and a fresh continuation; the first ~10 minutes of a new HTF candle is where to look. | stated | [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 57:20; [[trading_the_4_hour_power_of_three_ohlc_olhc]] 10:16; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 1:18:40 |
| 53 | No candle-5 continuation: the model trades C3, C4 and sometimes C2; after three expansion candles a new phase can start. | stated | [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 1:09:20; [[livestream_20260616_new_york_open_live_q_a_tjuolmjncmy]] 15:40; [[ttrades_fractal_model_trading_candle_2]] 12:44 |
| 54 | Avoid entering right after an expansion: a consolidation or another new phase usually follows. | stated | [[how_to_trade_expansion_phases_of_price]] 08:49; [[livestream_20260915_new_york_open_live_q_a_hlwq1drjbzo]] 36:10; [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 06:40 |
| 55 | Do not enter right next to obvious lows/highs (expect them to be taken); equal highs at your short level are a red flag; never short below lows. | stated | [[trade_like_ttrades_top_down_analysis]] 14:30; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 42:50, 27:10 |
| 56 | Once the target level is hit, the idea is complete. | stated | [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 18:40 |
| **Consolidations and ranges** | | | |
| 57 | Do not trade the breakout of a consolidation; trade a continuation off the breakout or a new manipulation (sweep) of a range extreme. | stated | [[ttrades_top_down_chart_lessons_1]] 11:51; [[why_your_continuations_fail_order_blocks_cisd_explained]] 08:17, 11:28 |
| 58 | Ignore closures inside a consolidation; trade from the range extremes back in, never the middle or the POC. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 09:18; [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 16:00; [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 42:30 |
| 59 | Consolidation at a HTF objective: wait for its high/low to be run, then a CISD, then trade the other way; with an open draw and no level hit, expect continuation instead. | stated | [[how_to_trade_consolidation_phases_of_price]] 03:57, 03:00 |
| 60 | (2026) Range trade, a separate strategy from his expansion model: one side swept while the opposite extreme holds, then a 15m/30m swing, target the other side. | stated | [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 10:00, 07:00 |
| **ICT-era models (2022-2024, historical)** | | | |
| 61 | (2022) 2022 mentorship model: liquidity run at the open or a HTF POI, 5m/1m MSS with displacement, retrace into the FVG in discount (long) / premium (short), stop on the swing. | stated | [[livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4]] 34:10; [[what_is_liquidity_ict_concepts]] 03:13; [[ict_index_futures_weekly_recap_week_of_5_16_22]] 02:14; [[intro_to_market_structure_shifts_fair_value_gaps_and_displacement_ict_concepts]] 02:37 |
| 62 | (2022) Refine the FVG entry with its 0.5, an aligned OB/breaker open, or a smaller-timeframe imbalance (1m, 15s). | stated | [[improve_your_trade_entries_within_fair_value_gaps_fvg]] 00:06; [[index_futures_weekly_recap_ict_concepts]] 02:10; [[ict_trade_example_15_second_entry]] 00:24 |
| 63 | (2022-2023) OTE: fib on the displacement leg from the wicks; 0.5 splits premium/discount, 0.62-0.79 is the zone, 0.705 preferred, 0.62 if you must be in; never long above 0.5. | stated | [[ote_optimal_trade_entry_ict_concepts]] 00:34; [[livestream_20220828_ict_orderflow_q_a_with_holyangelbruv_8z2abzljunu]] 30:40; [[optimal_trade_entry_ote_ict_concepts]] 00:37, 11:17; [[a_ict_entry_checklist_ict_concepts]] 02:05 |
| 64 | (2022) Inducement model: run external liquidity, break structure, run internal range liquidity (the first FVG buyers' stops), then the real move. | stated | [[intro_to_the_inducement_model_ict_concepts]] 00:06, 00:34; [[livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4]] 13:40 |
| 65 | (2022-2023) Box setup: consolidation, aggressive move out, aggressive move back in, retest of the deviation, expansion; the confirmed version waits for an OB formation on the retest. | stated | [[livestream_20230112_back_testing_live_session_fx_replay_8r6pxpeldiu]] 35:00; [[livestream_20230204_live_q_a_review_with_am_trades_xcvqikdea9w]] 55:40; [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 12:54 |
| 66 | (2023) Blend one to three concepts (e.g. FVG nested in an OB inside the OTE, aligned with a box setup) and pick the entry by trading R:R against fill chance. | stated | [[a_ict_entry_checklist_ict_concepts]] 01:09, 03:04, 03:32 |
| 67 | (2023-2024) CISD/OB entry: after the close through the opening price, sell the OB retest with the stop on the high; with poor R:R use an FVG or the OB's mean threshold. | stated | [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 03:49; [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 02:39; [[order_blocks_simplified_ict_concepts]] 01:54 |
| 68 | (2023) Inversion and CISD trigger earlier than MSS and get you in before the expansion, at the cost of losers MSS would have filtered. | stated | [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 08:21, 04:50 |
| 69 | (2023-2025) Unicorn: breaker with an overlapping same-direction FVG from the displacement through it; enter at the FVG's start or the breaker inside it; an hourly unicorn can be entered directly. | stated | [[breaker_block_fvg_entry_model_ict_concepts]] 02:02; [[breaker_blocks_simplified_ict_concepts]] 03:53, 04:49, 11:21; [[ash_trades_the_journey_to_profitability_the_unicorn_model]] 1:17:52 [guest] |
| 70 | (2025) Continuation breaker: let the reversal form, let a short-term swing be run and a breaker form in the new trend, then enter on its close or retest; never the breaker at the reversal. | stated | [[trade_continuations_using_breaker_blocks]] 01:43, 04:05, 06:38 |
| 71 | (2023-2024) Third-party MMXM models he presented: next day model (15m, NY only) and Twitter model (PDH/PDL raid, 15m MSS + SMT, correct side of midnight open). | stated | [[next_day_model_the_mmxm_trader_ict_concepts]] 04:39; [[the_twitter_model_the_mmxm_trader_ict_concepts]] 00:02, 00:39 |
| 72 | [guest] Variants not core TTFM: DTR unicorns only if formed in ~10-12 candles; AP blind limit at 0.7475 after a valid flip; Nick limit at the breaker edge on M5/M1. | stated (guest) | [[dtr_c2u_blending_the_fractal_model_unicorn_model_no_daily_bias]] 04:48; [[ap_use_market_structure_fibonacci_levels_for_sniper_entries]] 10:42; [[nickdoesfutures_unicorn_model_experiences_with_ict]] 19:24, 22:12 |

## Engine notes

- The companion has the teacher's two families as two checklists: a continuation path (bias Candle 3/4, POI in the correct half, setup closure, entry CISD, trigger) and a reversal path (key level reached, reclaim, CISD at the level) (`companion/styles/ttrades/rules.md` §1, §6, §7). Inference: the teacher's 2026 position (rule 22) is that he does not trade reversals, but the engine weighs both paths equally and on a tie picks continuation (§10.1 item 4, its open question 34).
- Trigger: `entry_mode = either` (CISD trigger or continuation order block, whichever confirms first) is a trader answer (rules.md §6 c4, its question 14). The 2026 video says "check the CISD but do not enter on it; wait for another continuation" ([[the_only_trading_strategy_you_need_for_2026]] 02:46), while 2025 says entering on the CISD close is his preference ([[trade_like_ttrades_top_down_analysis]] 09:54). By construction `either` fires on the CISD almost always (144 of 149 in the engine's 2025 sweep, rules.md question 28).
- Order type: the engine always enters at market on the trigger close and computes the 2R limit price only when `reward_check_role = quality` (rules.md §8.1). The teacher switches to a limit or waits for a new continuation when the market price no longer gives the R wanted (rules 39-40); the engine's `entry_either_pick = first` can keep reporting a stale first trigger (rules.md question 28).
- Continuation quality checks map to the teacher's "why continuations fail" reasons: `cont_trigger_v_shape` / `cisd_max_bars = 3` (rule 25, "1, 2, maybe 3"), `cont_trigger_clear_of_liquidity` (rule 31), `cont_objective_open_at_trigger` (rule 32), `cont_not_inside_consolidation` (rule 58) (rules.md §6 c4). The teacher also allows a few more candles for the reclaim after a large retracement leg ([[why_your_continuations_fail_order_blocks_cisd_explained]] 16:42); the engine has no such allowance (inference).
- Entry window: setup Candle 3, plus Candle 4 after a strong Candle 3, and `entry_latest_candle_frac = 0.75` (rules.md §6 c4). The 0.75 comes from a 2026-10-24 video outside this corpus (rules.md §6 sources); within the corpus the teacher gives no fraction, only "late in the candle" and "first ~10 minutes of a new HTF candle" (rules 19, 52).
- Positional entries (rule 45) are not implemented: the engine ignores swings formed before the forming bias candle (rules.md question 20).
- Not encoded at all: SMT and relative strength for picking the instrument, the "do nothing while two paths are alive" rule (rule 14), the no-chase rules beyond "played out" (rules 51-55; rules.md §10.3 question 33), skipping consolidating markets (rule 7), and the separate range strategy (rule 60). None of the 2022-2024 ICT models (rules 61-71) are encoded, which matches the teacher dropping them (rule 5).

## How it changed over time

- **2022 (ICT Q&A era).** Strat candle triggers off auto-plotted levels in January ([[simple_day_trading_strategy_intro]] 01:03), then ICT's 2022 mentorship model: liquidity run, MSS, FVG in discount/premium ([[what_is_liquidity_ict_concepts]] 03:13; [[livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4]] 34:10). Refinements: OTE ([[ote_optimal_trade_entry_ict_concepts]] 00:34), inducement ([[intro_to_the_inducement_model_ict_concepts]] 00:06), 15-second entries ([[ict_trade_example_15_second_entry]] 00:24), labelled model diagrams ([[build_an_entry_model_ict_concepts]] 01:47). He dropped the Strat because it made him chase ([[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 44:00).
- **2023.** Entry checklist blends 1-3 concepts ([[a_ict_entry_checklist_ict_concepts]] 01:09); OTE refined to 0.705 ([[optimal_trade_entry_ote_ict_concepts]] 11:17); unicorn taught ([[breaker_block_fvg_entry_model_ict_concepts]] 02:02); CISD and IFVG replace MSS as the trigger, entered on the OB retest ([[market_structure_shift_vs_change_in_state_of_delivery_ict]] 03:49, 08:21; [[inversion_fair_value_gaps_ifvg_ict_concepts]] 02:16). Guest MMXM models (next day model, AM Trades weekly profiles).
- **2024.** Continuations after a smart money reversal on OBs ([[order_blocks_simplified_ict_concepts]] 06:52), guest unicorn and MMXM interviews, the indicator's "enter on the close through, stop on the high, 2R" ([[intro_to_ttrades_fractal_model_indicator_settings]] 02:07), and the reversal sequence with its stated preference for later, continuation entries ([[reversal_sequence_ttrs_how_to_blend_pd_arrays]] 05:08, 06:19). Reversal days skipped on purpose ([[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 21:00).
- **2025.** Continuation entries with OBs and breakers ([[trade_continuations_using_order_blocks]] 00:18; [[trade_continuations_using_breaker_blocks]] 06:38); the phases-of-price series ([[how_to_trade_reversal_phases_of_price]] 00:33); candle 2 / candle 3 entries and wick size ([[trading_candle_3]] 34:39; [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 21:40); positional entries at the HTF open ([[trading_the_4_hour_power_of_three_ohlc_olhc]] 13:31).
- **2026.** "Do not enter on the CISD; wait for another continuation" ([[the_only_trading_strategy_you_need_for_2026]] 02:46); the three reasons continuations fail ([[why_your_continuations_fail_order_blocks_cisd_explained]] 00:34, 02:16, 03:38); the 3-step model trading the 8:00 candle's body ([[a_simple_3_step_trading_model_full_breakdown]] 32:33). New York Open streams: minimal toolkit, no OTE, no breakers, no reversals, no chasing, market on the close ([[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 05:50; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 50:10, 1:01:40; [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:24:10). None of these is an explicit "I used to... now I..." retraction, so the ICT-era rules stay recorded as history, not as superseded.

## Examples

- 2022 short: low taken, 5m MSS down, retrace into FVG/OB, sell, stop on the highs, hold for the day's target. [[ict_index_futures_weekly_recap_week_of_5_16_22]] 02:14
- 2023 CISD order-block short: close below the opening price, retest of the OB, stop on the high, target the London lows. [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 02:39
- 2024 guest unicorn: limit at the start of the breaker, stop beyond the breaker, 2R, only in the opening times. [[ash_trades_the_journey_to_profitability_the_unicorn_model]] 1:17:52
- 2025 candle 3 retry: first close-over fails, a new low forms a new protected swing, enter on the open after the close through the down-close series, stop on the protected low, 2R. [[trading_candle_3]] 04:21
- 2026 favourite stack 1D → 4h → 15m: down-close candles into an FVG with a sweep of a low, close over them, market on the new open, stop on the protected low, 2R or HTF objectives. [[the_best_timeframe_for_ttrades_fractal_model_simple]] 05:44
- 2026 live refusal: a new NQ short at 09:50 is a chase; wait for 10:00 for a fresh continuation. [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 57:20

## Conflicts and open questions

- ENT-1: Enter on the entry CISD, or wait for a continuation order block?
- ENT-2: Market on the close versus retest/limit: the R threshold that flips the choice has no number.
- ENT-3: First continuation only, or later continuations (C4, re-entries)?
- ENT-4: How late in the HTF candle is too late?
- ENT-5: Positional entry before the wick forms versus "let the wick form".
- ENT-6: Does he trade reversals and reversal days or not?
- ENT-7: Two paths alive: engine picks by stage, teacher waits or follows the HTF.
- ENT-8: V-shape / displacement has no size and only a soft candle count.
- ENT-9: Relevant level and valid separation have no threshold.
- ENT-10: What confirms a reversal: CISD, inversion, or V-shape alone?
- ENT-11: Stale first trigger versus a fresh continuation.
- ENT-12: Continuation after the HTF target is taken: skip, or allowed while range is left?
- ENT-13: Strong versus weak HTF bias (gates LTF reversal entries) is undefined.
- ENT-14: Expansion-day count before no more continuations: after 3 or after the 4th?
- ENT-15: OTE entries 2022-2023 versus "no OTE" 2026.
- ENT-16: Breakers / unicorn as entries versus "I don't use breakers".
- ENT-17: Kill zones and midnight open as entry filters versus "not used".
- ENT-18: Entry on the break of a high versus the close-through.
- ENT-19: Indicator-video speech slip: "down close candle that made that high".
- ENT-20: Guest models as variants, not TTFM.
- ENT-21: 2R exit versus 2R to the structural target when choosing the order type.
- ENT-22: Which POI qualifies a continuation when a protected swing exists going into the open.
- ENT-23: 2022 inducement model: the inducement FVG entry vs the real one.
- ENT-24: Unicorn "beginning of the breaker" is not a defined price.
- ENT-25: Twitter model's MSS loosened to inversion or CISD.

## Related

- [[fractal-model]]: the candle 1-4 frame the entries sit in.
- [[candle-closures]]: C2 / C3 closures that set up the reversal and continuation entries.
- [[cisd]]: the close through the series of opposing candles that is the trigger.
- [[swings-and-structure]]: protected swings, relevant swings, failure swings, separation.
- [[poi-and-pd-arrays]]: FVGs, order blocks, breakers, OTE: where entries are framed.
- [[liquidity]]: sweeps and short-term highs/lows that a continuation must or must not take.
- [[daily-bias]]: the idea the entry must align with.
- [[profiles]]: daily, 7h and weekly profiles that say reversal day versus continuation day.
- [[ranges-and-eq]]: EQ/50% respect, range trades, ADR and range left.
- [[sessions-and-time]]: 8:00 / 9:30 / 10:00 candles, early-in-candle timing.
- [[smt-and-psp]]: relative strength to choose the instrument; SMT as reversal confluence.
- [[risk-and-management]]: stop on the protected swing, 2R, partials, trailing.
- [[ttfm-indicator]]: what the indicator prints (C2/C3/C4, T-spot) and that it gives no signals.

## Questions this page answers

- Does TTrades enter on the CISD itself or wait for a continuation order block?
- When does he use a market order, a limit/retest, or skip the trade?
- What is a continuation entry, and what makes it fail?
- What is a reversal entry in TTFM, and does he still trade reversals in 2026?
- What is a positional entry and when is it allowed?
- How does he decide that an entry is too late or a chase?
- What are the phases of price and how do they pick reversal versus continuation?
- Which ICT-era entry models (2022 model, OTE, inducement, box setup, unicorn) did he teach, and which does he still use?
- What should happen when both a reversal and a continuation are possible?
- Is a missed entry recoverable, and how?
- Where does the companion's entry logic differ from the teacher?
