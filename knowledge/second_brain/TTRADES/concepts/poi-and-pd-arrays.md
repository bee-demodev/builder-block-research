---
id: poi-and-pd-arrays
title: "Points of interest and PD arrays: FVG, IFVG, order blocks, breakers, gaps"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [POI, POIs, point of interest, points of interest, key level, important level, area of interest, HTF level, PD array, PDA, premium discount array, price delivery array, PDR rate, imbalance, FVG, fair value gap, gap, SIBI, BISI, CE, consequent encroachment, IFVG, inversion, inversion fair value gap, inverted FVG, order block, OB, opposing candle, opposing candles, continuation order block, propulsion block, mean threshold, main threshold, MT, breaker, breaker block, unicorn, volume imbalance, "volume in Don's", BPR, balanced price range, the box, mitigation block, NWOG, NDOG, opening gap, unbalanced price range, T-spot POI]
covers: [poi, pd-array, fvg, ce, ifvg, order-block, opposing-candle, mean-threshold, propulsion-block, continuation-order-block, breaker-block, unicorn, volume-imbalance, gap, bpr, mitigation-block, opening-gap, poi-respect, poi-invalidation]
sources: [the_only_trading_strategy_you_need_for_2026, livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq, understanding_fair_value_gaps_fvg_ict_concepts, order_blocks_simplified_ict_concepts, trade_continuations_using_order_blocks, how_to_actually_trade_inversion_fair_value_gaps_ifvg, candle_2_closure_foundation, candle_3_closure_ttrades_fractal_model, equilibrium_for_expansions, livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs, livestream_20260317_new_york_open_live_q_a_00izxpadr5a, breaker_blocks_simplified_ict_concepts, trade_continuations_using_breaker_blocks, inversion_fair_value_gaps_ifvg_ict_concepts, reversal_sequence_ttrs_how_to_blend_pd_arrays, my_favorite_reversal_pattern_orderblocks_ict_concepts, easy_daily_bias_mechanical_framework, livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha, livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c, livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq, higher_time_frame_points_of_interest_ict_concepts, livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4, why_your_continuations_fail_order_blocks_cisd_explained]
confidence: medium
chain_step: ["3 setup", "4 entry", "5 manage"]
timeframe_role: [htf, setup, entry]
requires: [swings-and-structure, liquidity, daily-bias]
feeds: [candle-closures, cisd, entry-models, risk-and-management]
---

# Points of interest and PD arrays

## Definition

**2026 (current).** A point of interest (POI) is the place a trade has to come out of: "a trade must come out of a point of interest, normally a high or a fair value gap" [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 47:40. In the 3-step material POIs "are always an FVG or a low" for longs and "an FVG or a high" for shorts, looked for inside the previous day's range [[the_only_trading_strategy_you_need_for_2026]] 01:51-02:09. In the live Q&As he narrows it to "fair value gaps, highs and lows" [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 21:30, plus the CISD; he does not use breakers and rarely uses HTF order blocks [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 51:30, though another stream lists "FVGs, highs, lows and order blocks only" [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 38:50. A **fair value gap** is a three-candle pattern where the wicks of candle 1 and candle 3 do not overlap [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 00:22. An **IFVG** is an FVG that is not respected and is swiftly closed over, so resistance becomes support and vice versa [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 00:38. An **order block / opposing candle** is the single candle or series of opposite-close candles that ran into a POI and was then closed through. That close is the CISD, and any later one in the trend direction is a *continuation order block* [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 1:02:30. A POI is only a *location*. He does not trade it blindly: he waits for a reaction or a swing to form there [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 1:14:30, [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 33:10.

**2022 (ICT-concepts era).** "Imbalance" means an FVG or an order block left by displacement [[simple_options_day_trading_strategy_auto_plotted_levels_and_ict_entries]] 03:50. "PD arrays" (premium/discount arrays) are the full ICT menu: highs/lows, equal highs/lows, FVGs, order blocks, FVG fills, OTE, internal range liquidity [[higher_time_frame_points_of_interest_ict_concepts]] 00:36-00:52, and BPRs [[build_an_entry_model_ict_concepts]] 04:11. He prefers FVGs to order blocks and uses order blocks to narrow an FVG entry; breakers are rare [[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 22:50, 45:20. Premium arrays give sells and discount arrays give buys [[livestream_20220814_stream_q_a_with_am_trades_ict_concepts_cruftskoveo]] 14:10 (guest).

**2023-2024 (TTFM takes shape).** Teaching videos pin down the objects. The FVG gets SIBI/BISI, CE, close-based respect, inversion, volume imbalance and gap [[understanding_fair_value_gaps_fvg_ict_concepts]] 00:10-08:50. The order block must form "into an important level", with a sweep, displacement and a close beyond the opening price of the up/down-close series [[order_blocks_simplified_ict_concepts]] 00:38-01:23. The breaker is the high-low-higher high-lower low structure [[breaker_blocks_simplified_ict_concepts]] 00:10-02:43. From late 2023 the order-block close-through *is* the CISD [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 00:57, and a **propulsion block** is an order block formed off another one [[inversion_fair_value_gaps_ifvg_ict_concepts]] 06:38.

**2025.** POIs become the frame for every candle 2 / candle 3 closure: "both closure types always require a higher-timeframe key level" [[candle_3_closure_ttrades_fractal_model]] 10:38. A continuation order block counts only if its run tagged an FVG or swept a swing [[trade_continuations_using_order_blocks]] 14:04. "PDA" is glossed as "price delivery array, generally an FVG" [[how_to_trade_retracement_phases_of_price]] 2:07.

## Rules

| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |
|---|---|---|---|
| **What counts as a POI** | | | |
| 1 | (2026) Bullish POIs are an FVG or a low, bearish POIs an FVG or a high; look for them inside the previous day's range. | stated | [[the_only_trading_strategy_you_need_for_2026]] 01:51, 02:01 |
| 2 | (2026) The only POIs he uses are FVGs, highs and lows (plus CISD); no breakers, rarely HTF order blocks, no rejection blocks. | stated | [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 21:30; [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 51:30; [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 11:30 (qa) |
| 3 | (2026) The model's tools are FVGs, highs, lows and order blocks only: no OTE, GEX, IFVG-as-strategy, double purge or quarter SMT. | stated | [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 38:50 |
| 4 | (2026) A trade must come out of a POI, normally a high or an FVG; it need not be a higher-timeframe FVG. | stated | [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 47:40 |
| 5 | (2025) Frame a C2 with bias and a HTF POI (FVGs, highs/lows); opposing candles count as a POI only after a protected swing ("more advanced"). | stated | [[candle_2_closure_foundation]] 01:39, 06:22 |
| 6 | A POI can come from a much higher timeframe, e.g. an old monthly high. | demonstrated | [[candle_2_closure_foundation]] 05:18 |
| 7 | (2026) A HTF CISD can serve as a POI only when it makes sense in context. | stated | [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 47:30 |
| 8 | (2026) With nothing to the left (all-time highs), use an average-daily-range estimate as the POI and keep trading the candles in front of you. | stated | [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 14:40 |
| 9 | (2026) On an inside day use only three POIs: previous day high, previous day EQ, previous day low. | stated | [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 04:20 |
| 10 | (2026) Wick POIs only on doji or hammer/shooting-star candles, not generic rejection blocks. | stated | [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 32:50 |
| 11 | (2026) Mark relevant highs and lows, not every session high/low; a London high may carry no relevance. | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 46:00 |
| 12 | (2026) He does not use the first presented FVG; use the 9:30 open instead if you want that idea. | stated | [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 18:40 (qa); [[livestream_20260915_new_york_open_live_q_a_hlwq1drjbzo]] 27:00 |
| 13 | (2022) HTF POIs: highs/lows (equal, session, daily), FVGs, order blocks, FVG fills, OTE of a range and internal range liquidity. | stated | [[higher_time_frame_points_of_interest_ict_concepts]] 00:36, 00:52 |
| 14 | (2022) OTE (0.62-0.79) is only a zone in which to look for an FVG/order block; the exact fib level does not matter. | stated | [[livestream_20220923_stream_q_a_giveaway_winners_announced_am_traders_0yzqr8hpyeu]] 07:50 |
| **Fair value gap: geometry** | | | |
| 15 | An FVG is three candles where candle 1's and candle 3's wicks do not overlap; any overlap means no FVG, and no minimum size is given. | stated | [[understanding_fair_value_gaps_fvg_ict_concepts]] 00:10, 01:10; [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 00:22 |
| 16 | Bullish FVG: candle 1's high does not overlap candle 3's low (BISI); bearish: candle 1's low does not overlap candle 3's high (SIBI). | stated | [[breaker_block_fvg_entry_model_ict_concepts]] 00:37; [[understanding_fair_value_gaps_fvg_ict_concepts]] 02:37 |
| 17 | Consecutive overlapping candle triples can each form their own FVG; when several sit in one leg treat them as one zone. | stated | [[understanding_fair_value_gaps_fvg_ict_concepts]] 02:08; [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 05:13 |
| 18 | Consequent encroachment (CE) = 50% of the FVG (also of a wick); it is an alternative entry or reference to the near edge. | stated | [[understanding_fair_value_gaps_fvg_ict_concepts]] 03:37; [[intraday_bias_simplified_ict_concepts]] 23:50 |
| 19 | Volume imbalance = close-to-open gap between two candles whose wicks still overlap; a gap = no trading at all between two candles. | stated | [[understanding_fair_value_gaps_fvg_ict_concepts]] 08:50 |
| 20 | (2026) For gap targets use only the portion of the gap with no volume, not the whole gap. | stated | [[livestream_20260729_new_york_open_live_q_a_xraklbjhw5k]] 06:00 |
| 21 | (2026) An unbalanced price range (previous high and low do not overlap, price only moved one way) is a continuation target; HTF levels are imbalances where a high does not overlap a low. | stated | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 05:40; [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 1:14:30 |
| **Fair value gap: respect and failure** | | | |
| 22 | Respect = price reaches into the FVG, closes back out and continues; judge it by bodies, wicks may dig deeper. | stated | [[understanding_fair_value_gaps_fvg_ict_concepts]] 04:09; [[how_to_trade_retracement_phases_of_price]] 3:32; [[order_blocks_simplified_ict_concepts]] 06:38 |
| 23 | A close over the CE warns that the FVG is not respected; a full close through it invalidates it. | stated | [[understanding_fair_value_gaps_fvg_ict_concepts]] 04:36, 05:04 |
| 24 | A bullish PD array should not close below its mean threshold and should react from its upper half (bearish: mirror). | stated (guest) | [[jokerszn_daily_orderflow_ict_daily_bias]] 17:12 |
| 25 | (2026) Expansions retrace shallowly, ideally only into the lower half of the gap; a retracement bought back through the gap is a V-shape reversal. | stated | [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 29:10, 32:30 |
| 26 | An FVG that is not respected (traded through) points to continuation through it and to the next opposite old high/low as the draw. | stated | [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 23:00; [[market_structure_shift_vs_liquidity_grab_ict_concepts]] 02:28 |
| 27 | Unrespected FVGs are dropped: do not guess which one below/above EQ will react, wait for a swing / new protected swing to form there. | stated | [[easy_daily_bias_mechanical_framework]] 05:11; [[livestream_20220923_stream_q_a_giveaway_winners_announced_am_traders_0yzqr8hpyeu]] 15:00 |
| 28 | (2026) A POI closed through (e.g. a 1H FVG closed below while sweeping, not bought back aggressively) is not traded away from; keep the HTF bias but wait for a sweep. | stated | [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 1:32:40 |
| 29 | (2026) One mechanical close back through a daily FVG is not enough when the approach was slow and shallow; require aggressive price action and a CISD. | stated | [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 29:40 |
| 30 | (2026) A LTF FVG at a low is just that low: a reaction off it without a close below is a LTF low swept to go higher; require a close on your entry timeframe. | stated | [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 48:20 |
| **Inversion (IFVG)** | | | |
| 31 | An inversion is an FVG closed through; on return it acts from the other side, often at its CE, and need not follow straight away. | stated | [[understanding_fair_value_gaps_fvg_ict_concepts]] 05:32, 06:03, 08:16 |
| 32 | The inversion needs a body close over the whole gap (the whole cluster when FVGs are stacked); a close past the CE is only a hint. | stated | [[inversion_fair_value_gaps_ifvg_ict_concepts]] 05:34; [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 06:42; [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 05:13 |
| 33 | Trade inversions only in context (toward the target after a sweep, inside a HTF expansion candle with a small wick), never as a stand-alone pattern. | stated | [[ttrades_fractal_model_inversion_intraday_strategy]] 16:54; [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 01:07, 12:08 |
| 34 | An inversion can stand in for the CISD in continuations, notably when the candle range is extremely large. | stated | [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 07:33; [[why_your_continuations_fail_order_blocks_cisd_explained]] 18:36 |
| 35 | (2026) The order of reversal is inversion first, then CISD; trade IFVGs together with HTF candles. | stated | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 54:00; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 38:20 |
| 36 | (2026) He often watches a post-sweep IFVG get ripped through and does not read it as automatically bearish. | stated | [[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 13:50 |
| **Order block / opposing candles** | | | |
| 37 | Bearish OB: into an important level, sweep buy-side, displace and close below the opening price of the up-close candle(s); the retrace into it is resistance (bullish: mirror). | stated | [[order_blocks_simplified_ict_concepts]] 00:38, 01:05 |
| 38 | Without a higher-timeframe PD array / important level the pattern is not an order block. | stated | [[order_blocks_simplified_ict_concepts]] 01:23, 11:37 |
| 39 | (2025) A continuation order block needs its run to tag an FVG or sweep a swing, then a close through the opposing series; a close-through without either is not valid. | stated | [[trade_continuations_using_order_blocks]] 01:20, 14:04; [[the_only_trading_strategy_you_need_for_2026]] 02:57 |
| 40 | The opening price of the series is the OB's reference level; a close beyond it validates the block. | stated | [[my_favorite_reversal_pattern_orderblocks_ict_concepts]] 01:36; [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 03:40 |
| 41 | For a series, wait for a close over the open of the lowest-body down-close candle (bullish case). | demonstrated | [[order_blocks_simplified_ict_concepts]] 08:45 |
| 42 | Mean threshold = 50% of the OB bodies (body low to body high); a respected bullish OB does not close below it. | stated | [[order_blocks_simplified_ict_concepts]] 04:03, 04:29; [[breaker_block_fvg_entry_model_ict_concepts]] 06:34 |
| 43 | Wicks may pierce the OB on the retest; bodies must respect it. | stated | [[my_favorite_reversal_pattern_orderblocks_ict_concepts]] 05:21; [[livestream_20230112_back_testing_live_session_fx_replay_8r6pxpeldiu]] 11:00 |
| 44 | After a close over a series of down-close candles he does not expect that low to be touched again. | stated | [[the_twitter_model_the_mmxm_trader_ict_concepts]] 05:47; [[intro_to_ttrades_fractal_model_indicator_settings]] 17:06 |
| 45 | (2024) A CISD through a series of opposing candles is the same thing as an order block; use a higher timeframe (30m) if the 15m is messy. | stated | [[ict_daily_profile_new_york_reversal]] 06:11 |
| 46 | (2026) A CISD is the order block that changes the trend; any later same-direction OB or protected swing is a continuation OB. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 1:02:30 (qa) |
| 47 | Propulsion block = an order block formed off an earlier order block; it should hold and not close past its threshold. | stated | [[timeframe_alignment_how_to_align_timeframes_for_expansion]] 09:02; [[trade_like_ttrades_top_down_analysis]] 17:23 |
| 48 | Do not trust an order block sitting inside a consolidation; use the range high/low as the POI and look for a sweep or SMT. | stated | [[equilibrium_for_expansions]] 13:28 |
| 49 | A mitigated OB / CISD level can be reused only while the draw on liquidity is untaken. | stated | [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 09:10 |
| 50 | (2022) Order block = last opposite-close candle (or its body) before the move; with a clean series use the whole series and its opening price. | stated | [[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 22:50; [[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 28:45 (qa) |
| 51 | (2022) A high-probability order block has an FVG beyond it; enter the FVG and let the OB support price. | stated | [[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 24:40; [[livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4]] 37:10 |
| 52 | (2022) Mark daily blocks from wick to open (most sensitive part); a 4h block from body to wick of the up-close series. | stated | [[top_down_analysis_ict_concepts]] 01:56, 02:27 |
| **Breaker, unicorn, BPR, other ICT arrays** | | | |
| 53 | Bearish breaker: high, low, higher high, lower low; the down-close candles from that high to the low are resistance (bullish: low, high, lower low, higher high; up-close candles are support). | stated | [[trade_continuations_using_breaker_blocks]] 00:31, 00:49; [[breaker_blocks_simplified_ict_concepts]] 00:39, 02:43 |
| 54 | No lower low after the higher high (bearish) means no breaker. | stated | [[breaker_blocks_simplified_ict_concepts]] 02:43 |
| 55 | A breaker is marked as the whole candle series including wicks, by bodies when wicks are messy; an OB is marked only at its opening price. | stated | [[breaker_blocks_simplified_ict_concepts]] 07:09; [[trade_continuations_using_breaker_blocks]] 04:36 |
| 56 | Unicorn = breaker block paired with an FVG from the displacement through it; it stays valid while bodies do not close past the breaker's mean threshold. | stated | [[breaker_block_fvg_entry_model_ict_concepts]] 00:10, 06:34 |
| 57 | (2025) Breakers are an equally valid continuation tool, but he prefers order blocks as simpler. | stated | [[trade_continuations_using_breaker_blocks]] 14:32 |
| 58 | (2026) He does not use breaker blocks; he removed breakers, advanced market structure and premium/discount from his model. | stated | [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 1:04:30; [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:24:50 (qa) |
| 59 | (2022) BPR = overlap of opposing FVGs after an aggressive move met by an aggressive opposite move; for a bullish BPR enter the smaller gap. | stated | [[build_an_entry_model_ict_concepts]] 04:11, 04:43 |
| 60 | Old FVGs or OBs from the opposite side of the curve can support price later (mitigation / reaccumulation). | stated | [[inversion_fair_value_gaps_ifvg_ict_concepts]] 08:13; [[cpi_gold_trade_review_ict_market_maker_sell_model_mmxm]] 03:30 |
| 61 | Volume imbalances count as an important level only when paired with a retest of another opposing candle. | stated | [[trade_continuations_using_order_blocks]] 16:29 |
| **Using POIs: context, location, waiting** | | | |
| 62 | (2025) Use C2/C3 closures only at a HTF key level; a closure that just misses the POI, or a sweep that fails to take the relevant high/low, is not valid. | stated | [[candle_2_closure_foundation]] 01:30, 06:04; [[candle_3_closure_ttrades_fractal_model]] 06:07, 10:38 |
| 63 | (2026) A C2 for a continuation inside the daily range does not need a POI; a C2 for a reversal must be at one (he teaches "yes, POI" for simplicity). | stated | [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 09:00 |
| 64 | (2026) The daily is the one timeframe where a POI before the closure is ideal but not required, given other context (monthly turning, aggressive closure). | stated | [[livestream_20260729_new_york_open_live_q_a_xraklbjhw5k]] 24:30 |
| 65 | (2026) A model generally needs a POI, more so on the hourly (~24 candles a day) than on the 4H (six); in the daily-4H-15m model he prefers it on both daily and 4H. | stated | [[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 20:30, 16:40 |
| 66 | (2025) Match the PD array to the respected half of the previous candle, e.g. a bullish FVG in the upper half above a protected low; skip it if not respected and move to the next. | stated | [[equilibrium_for_expansions]] 01:53, 04:05 |
| 67 | (2022-2023) Do not short from an FVG in discount or long from one in premium; drop a timeframe for one in the correct zone. | stated | [[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 20:20; [[a_ict_entry_checklist_ict_concepts]] 09:27 (note) |
| 68 | Never take a bias off a single pattern or a random FVG; always have a HTF draw on liquidity. | stated | [[livestream_20260616_new_york_open_live_q_a_tjuolmjncmy]] 28:10; [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 20:30 |
| 69 | Do not trade away from a market that failed to reach a relevant level, however good the pattern; if price leaves the levels untouched there is nothing to trade. | stated | [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 30:20; [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 1:02:00 |
| 70 | Do not pick a distant HTF gap and trade from it blindly; trade current price action and reference nearby POIs. | stated | [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 1:05:45 |
| 71 | No limit orders inside FVGs or blind retests: wait for the reaction to form a swing / new order block there, then enter with that stop. | stated | [[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 48:20; [[livestream_20260311_cpi_new_york_open_live_q_a_egv_gabtqks]] 38:00; [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 33:10 |
| 72 | A pullback that does not reach a POI is not a continuation, even with SMT on a correlated asset. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 10:49 |
| 73 | (2026) Refine a HTF POI downward: it must form a 1m/3m swing (a LTF continuation) there, otherwise the idea fails. | stated | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 16:00; [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 47:20 |
| 74 | (2026) If the bias-direction move leaves no gap on the entry timeframe, step down one timeframe at a time until a gap appears. | demonstrated | [[livestream_20261006_new_york_open_live_q_a_rtomj8urfnw]] 18:30 |
| 75 | (2026) If stops keep getting hit before target, look for a HTF FVG at the stop: move up a timeframe and wait for price to reach into it. | stated | [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 27:20; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:15:00 |
| 76 | (2026) A FVG counts as a high on a lower timeframe; do not trade away from it while a nearby high is left untaken. | stated | [[which_swing_highs_and_lows_matter_in_trading]] 08:36; [[livestream_20220923_stream_q_a_giveaway_winners_announced_am_traders_0yzqr8hpyeu]] 1:01:40 |
| 77 | (2026) After C2 + SMT + CISD trade away from the FVG first; if no continuation forms there, the sweep of the low (or T-spot) becomes the POI. | stated | [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 1:03:00 |
| 78 | Imbalances (FVGs, gaps) are also targets and front-run levels, especially when they line up with liquidity. | stated | [[price_targets_ict_concepts]] 00:39; [[livestream_20260826_ttrades_mnq_cup_afternoon_session_h1zqwwqdhka]] 1:18:30 |

## Engine notes

- **FVG** (companion rules.md 3.10): wick-to-wick three-bar gap, `confirmed_at` = close of bar 3, tagged when a later bar trades in, `filled_at` = first *close* through the far side, then dropped. This matches rules 15, 23 and 27. `fvg_min_size = 0` is a proposal (the teacher gives no minimum). The CE warning (rule 23) and the "only the no-volume part" rule (rule 20) are not encoded (inference).
- **POI test** (3.14): a bar reached a POI if it took an untaken swing on its own timeframe, traded into an unfilled same-direction FVG confirmed before the bar opened, or traded into a valid order block and closed at or above its mean threshold. The teacher's 2026 list (FVG, high/low) is covered by (a) and (b). Using order blocks as POIs (c) goes beyond the 2026 livestreams, which say he rarely uses HTF OBs (rule 2), but matches [[candle_2_closure_foundation]] 06:22 and [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 38:50.
- **Order block zone** (3.12): `top = highest open in the series`, `bottom = lowest close`, MT = midpoint. Its validity needs a sweep or FVG tag (rule 39). The SMT exception is not implemented. This zone is an engine choice: the teacher marks only the opening price (rule 55) or 50% of the bodies (rule 42) (inference).
- **Location**: continuation POIs must sit in the respected half of the previous bias candle (6 c2 `cont_poi_tagged`: FVG `top > respect_level`). That follows rule 66, not the 2022 discount rule 67. The companion calls the lower-half reading in `daily_bias_c123_map.json` reversed (3.9).
- **Closure gating**: `bias_poi_present` makes the POI a gate for cases A/C, and case G (closure with no POI) is neutral. That follows rule 62. The 2026 relaxations (rules 63-64: continuation inside the daily range or a daily closure needs no POI) are not encoded (teacher-vs-engine, POI-1).
- **POI closed through** (9.3): the engine drops that POI, goes back to c1 and keeps looking while `respect_level` holds. The teacher's alternative of keeping the bias and shrinking the target is deliberately left out (companion open question 17; rule 28 supports "keep the bias, drop the POI").
- **Not used by the checklist**: breakers (3.13, matches rule 58) and inversion FVGs (3.10), plus BPR, volume imbalance and opening gaps (not defined). Reversal key levels are previous candle / swing / unfilled FVG with a 10% `reversal_level_tolerance_frac` "near" band, a proposal. The teacher says a closure that just misses the POI is invalid (rule 62; POI-11).
- **Lookback**: POI swings use the "three higher-timeframe candles" rule (3.1). `bias_poi_lookback_bars` converts it to bar counts, and the 12-bar figure for a monthly bias is invented (companion open question 13). The teacher also uses an ~8-trading-day-old daily gap and an old monthly high (POI-10).

## How it changed over time

- **2022**: ICT menu. POIs are highs/lows, FVGs, OBs, breakers, OTE, BPR and IRL [[higher_time_frame_points_of_interest_ict_concepts]] 00:36. FVG preferred and OB used to refine [[livestream_20220821_8_14_22_mmxm_live_with_niper_ict_concepts_umlwrlxd_v8]] 32:30. Entry at the FVG 0.5 [[improve_your_trade_entries_within_fair_value_gaps_fvg]] 00:06. Premium/discount filter [[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 20:20. Breakers "rarely" used [[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 18:00 (qa).
- **2023**: definition videos. FVG respect, CE, inversion, VI and gap [[understanding_fair_value_gaps_fvg_ict_concepts]] 00:10. OB as a close beyond the opening price at an important level [[my_favorite_reversal_pattern_orderblocks_ict_concepts]] 01:36, [[order_blocks_simplified_ict_concepts]] 00:38. Breaker / unicorn [[breaker_block_fvg_entry_model_ict_concepts]] 00:10. IFVG video [[inversion_fair_value_gaps_ifvg_ict_concepts]] 00:57. CISD = OB validation [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 03:40.
- **2024**: OB and CISD merge into one event [[ict_daily_profile_new_york_reversal]] 06:11. Propulsion blocks [[high_resistance_vs_low_resistance_liquidity_ict_concepts]] 10:24. "Don't place limits inside FVGs; wait for a new order block" [[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 48:20. The breaker is taught again as a structure [[reversal_sequence_ttrs_how_to_blend_pd_arrays]] 02:57.
- **2025**: POIs frame closures. Continuation OBs need an FVG tag or a sweep [[trade_continuations_using_order_blocks]] 14:04. Breaker continuations are "equally valid" but OBs preferred [[trade_continuations_using_breaker_blocks]] 14:32. Respected-half matching [[equilibrium_for_expansions]] 01:53. Closures need a HTF key level [[candle_3_closure_ttrades_fractal_model]] 10:38. He "does not really use IFVGs" [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 1:49:10 (qa).
- **2026**: reduced to FVG + highs/lows (+ CISD) [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 21:30. He explicitly removed breakers and premium/discount [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:24:50 (qa) and "does not use breaker blocks" [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 1:04:30. An IFVG teaching video [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 00:38, while streams say "doesn't trade IFVGs" [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 54:30 (qa) and later "inversion first, then CISD" [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 54:00. POI requirement relaxed for continuations and the daily [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 09:00. Emphasis on waiting for a swing at the POI [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 33:10.

## Examples

- NQ 1H FVG closed below while sweeping and not bought back aggressively. He drops it as a POI and keeps the daily bullish bias, but frames no long until a sweep [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 1:32:40.
- At the 10:00 new 4H candle he uses a 15m FVG as the POI, refines it to the 5m swing low it coincides with, then the 3m 0.5; price should not take that LTF low [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 47:20.
- Gold reached into a daily gap. A 3m gap at 244 inside the 15m gap 263-242 still counts as "inside the gap", and he waits for hourly displacement out of it [[livestream_20260826_ttrades_mnq_cup_afternoon_session_h1zqwwqdhka]] 42:30, 1:16:10.
- A retest of a fresh order block forms another opposing candle into an important level, which gives a second entry, and that swing then holds [[trade_continuations_using_order_blocks]] 08:06.
- Inversion with a series of FVGs: using the whole cluster as the CISD level saved a loss when price failed to close through both [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 10:06.
- (2023) A daily up-close series that took the previous day low and closed below became the hourly OB POI. The New York move above the daily open closed back in and displaced lower, targeting PDL [[top_down_analysis_daily_bias_to_entries_ict_concepts]] 03:13, 06:25.

## Conflicts and open questions

See [[conflicts]] (fragment `_merge/poi-and-pd-arrays/conflicts-fragment.md`).

- **POI-1**: Is a POI required for every closure, or only for reversals and sub-daily timeframes?
- **POI-2**: When does an FVG stop counting: a close past the CE, a close past the far edge, or a slow close?
- **POI-3**: How near is "reached"? A closure that just misses is invalid, but "inside the HTF gap" is loose, and the engine has a 10% band.
- **POI-4**: Which half: the TTFM respected half (bullish POI in the upper half) or ICT discount. He removed premium/discount in 2026.
- **POI-5**: Order block zone and mean-threshold geometry (open only, wick-to-open, body-to-wick, open-to-lowest-close).
- **POI-6**: Are HTF order blocks POIs? Taught in 2023-2025, rarely used in 2026, and the engine uses them.
- **POI-7**: IFVGs: a 2026 teaching video and a reversal step versus "doesn't trade IFVGs".
- **POI-8**: Breakers: taught through 2025, explicitly removed in 2026.
- **POI-9**: Gap versus FVG versus volume imbalance, and which part of a gap counts.
- **POI-10**: How far back a POI may sit (three HTF candles, ~8 trading days, an old monthly high).
- **POI-11**: A POI closed through: drop the bias, drop only the POI, or expect continuation through it.
- **POI-12 to POI-24**: limits at the POI, propulsion block definition, OB validity without a sweep (SMT), first-presented FVG, wick POIs, BPR meanings, unicorn overlap, breaker wording, opening gaps, FVGs as reversal points, FVG size, continuation POI by the indicator, location inside the previous day's range.

## Related

- [[liquidity]]: highs/lows are both POIs and targets; POIs are where liquidity is taken before the move.
- [[swings-and-structure]]: a POI matters only once a swing forms there; protected swings form "out of an FVG".
- [[candle-closures]]: C2/C3 closures are framed at a HTF POI.
- [[cisd]]: the order block close-through is the CISD; continuation OBs need a POI.
- [[ranges-and-eq]]: the respected half / EQ decides which POI is valid.
- [[entry-models]]: continuation order block and inversion entries.
- [[smt-and-psp]]: SMT can stand in for a sweep when validating an OB.
- [[risk-and-management]]: stops at the protected swing, HTF FVGs at the stop, gap targets.
- [[daily-bias]]: a HTF draw is required before any POI is used.
- [[ttfm-indicator]]: T-spot box and continuation labels drawn only in FVGs.

## Questions this page answers

- What counts as a point of interest in TTrades' current model?
- How is a fair value gap defined, and what makes it respected or invalidated?
- When is an FVG inverted (CE close or full close)?
- Does TTrades trade IFVGs or breaker blocks today?
- How is an order block / opposing candle validated, and where is its mean threshold?
- What is a propulsion block and a continuation order block?
- Does a candle 2 closure always need a POI?
- Which half of the previous candle should the POI sit in?
- Should I enter with a limit at the POI or wait?
- What do I do when the POI is closed through?
- How far back can a POI be, and what if there is nothing to the left?
- What is the difference between a gap, an FVG and a volume imbalance?
