---
id: cisd
title: "CISD and IC-CISD (change in the state of delivery)"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [CISD, change in state of delivery, change in the state of delivery, "change the state of delivery", IC-CISD, intra-candle CISD, intracandle CISD, in-candle CISD, early CISD, early C2 CISD, second CISD, opposing candles, series of opposing candles, series of down-close candles, series of up-close candles, order block formation, close through the series, MSS, market structure shift, market structure break, MSB, break of structure, BOS, displacement, shift in trend, "buy side of the curve", fake CISD, 0.5 of the CISD]
covers: [cisd, ic-cisd, early-cisd, opposing-candles, displacement, mss-legacy]
sources: [cisd_validates_swing_points, change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts, market_structure_shift_vs_change_in_state_of_delivery_ict, why_your_continuations_fail_order_blocks_cisd_explained, the_only_trading_strategy_you_need_for_2026, fractal_model_fundamentals, trading_irl_erl_with_order_blocks_ict_concepts, livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds, livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra, livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq, livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o, livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg, livestream_20260728_new_york_open_live_q_a_yngx9oaefui, trading_candle_3, intro_to_ttrades_fractal_model_indicator_settings, livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy, wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles, protected_swings_understanding_trend_and_invalidations, livestream_20260819_new_york_open_live_q_a_rvrk4mltjss, livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy, market_structure_shift_ict_concepts, structure_shift_vs_liquidity_grab_ict_concepts]
confidence: high
chain_step: ["3 setup", "4 entry"]
timeframe_role: [setup, entry]
requires: [liquidity, poi-and-pd-arrays, candle-closures, swings-and-structure]
feeds: [entry-models, risk-and-management, fractal-model, smt-and-psp]
---

# CISD and IC-CISD (change in the state of delivery)

## Definition

**Latest (2026).** A CISD is "the order-block formation that appears when trend changes": price reaches an important level (sweeps a low/high or taps an FVG), then closes through the series of candles that delivered it there ([[cisd_validates_swing_points]] 0:18, 0:32). Procedure: find the extreme, find the series of candles that made it, check for a close through that series ([[cisd_validates_swing_points]] 1:53; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 53:20). The level is the series' opening price, measured with bodies, not wicks. A remaining wick beyond the body does not matter ([[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 38:40), and neither does how much of the closing body gets through ([[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 28:20). It needs a new extreme made by a series of candles ([[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 1:10:20). The ideal is a V-shaped turn in 1-3 candles; a slow close-through is consolidation ([[cisd_validates_swing_points]] 8:23-8:32; [[why_your_continuations_fail_order_blocks_cisd_explained]] 09:55). A CISD only means something paired with a higher-timeframe Candle 2 / Candle 3 closure: "every candle 2 closure needs a CISD on the lower timeframe" ([[the_best_timeframe_for_ttrades_fractal_model_simple]] 02:03; [[cisd_validates_swing_points]] 1:11). There is "only one CISD per day and it forms the daily wick"; later same-direction formations are continuations ([[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 16:30, 22:20). **IC-CISD** (intra-candle CISD, "I created it", 2024) is the CISD inside the forming HTF candle, off a POI, that forms that candle's wick ([[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 46:40; [[livestream_20260616_new_york_open_live_q_a_tjuolmjncmy]] 15:20, 24:40).

**2024-2025.** The same object runs through every playbook as the lower-timeframe confirmation of the HTF swing and the protected swing ([[intro_to_ttrades_fractal_model_indicator_settings]] 01:12; [[fractal_model_fundamentals]] 01:53-02:11; [[trade_like_ttrades_top_down_analysis]] 03:41). In October 2024 he insists the series is "never a single candle" ([[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 11:50). In 2025 he says "the series can be a single candle" ([[protected_swings_understanding_trend_and_invalidations]] 04:10; [[fractal_model_fundamentals]] 08:19). If price makes a new extreme first, the reference moves to the new series ([[trading_irl_erl_with_order_blocks_ict_concepts]] 04:18).

**2023.** The CISD video defines it inside ICT language: after price runs into an HTF PD array, a close beyond the opening price of the first candle of the opposite-colour series validates those candles as an order block ([[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 00:37-01:06). It comes before, or on the same candle as, the market structure shift. It gives an earlier entry but more losers ([[market_structure_shift_vs_change_in_state_of_delivery_ict]] 01:26, 04:18, 05:23).

**2022.** There is no CISD yet. The trend change is a market structure shift: an energetic, displacing break of a short-term swing that leaves an FVG. A break without displacement is a liquidity grab ([[reversal_or_pullback_using_market_structure_to_determine_trend_ict_concepts]] 03:08-03:41; [[structure_shift_vs_liquidity_grab_ict_concepts]] 00:07). He later says explicitly that he "moved from market structure shift (2022) to CISD" ([[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 45:00 Q&A; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 48:00 Q&A).

## Rules

| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |
|---|---|---|---|
| **The object** | | | |
| 1 | CISD = price reaches an important level (sweep of a high/low or tap of an FVG) and then closes through the series of candles that delivered it there. | stated | [[cisd_validates_swing_points]] 0:32; [[timeframe_alignment_how_to_align_timeframes_for_expansion]] 04:00 |
| 2 | The CISD is the order-block formation at a trend change; the series it closes through is the order block. | stated | [[cisd_validates_swing_points]] 0:18; [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 00:57; [[order_blocks_simplified_ict_concepts]] 05:37 |
| 3 | Procedure: find the extreme, find the series of candles that made it, ask whether price closed through it. | stated | [[cisd_validates_swing_points]] 1:53; [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 48:40; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 53:20 |
| 4 | Bullish CISD = close over the down-close series that made the low; bearish = close below the up-close series that made the high. | stated | [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 00:37; [[fractal_model_fundamentals]] 08:19 |
| 5 | The level is the opening price of the series; with several candles use the open of the first candle of the series. | stated | [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 01:06; [[trading_irl_erl_with_order_blocks_ict_concepts]] 10:41 |
| 6 | Measure body to body: a close of the body through the level is the CISD; a wick still beyond it does not matter, and how much of the body closes through does not matter. | stated | [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 38:40; [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 28:20 |
| 7 | A CISD needs a new low (high) made by a series of candles; a reaction without a new extreme is not a CISD, whatever its size. | stated | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 1:10:20 |
| 8 | The series that counts is the one that made the extreme; closing through other candles (e.g. a consolidation high) is not a CISD. | stated | [[trading_candle_3]] 23:22; [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 02:06; [[how_to_trade_reversal_phases_of_price]] 14:10 |
| 9 | (2025-2026 videos) The series can be a single candle when only one candle delivered into the level. | stated | [[protected_swings_understanding_trend_and_invalidations]] 04:10; [[cisd_validates_swing_points]] 4:30; [[why_your_continuations_fail_order_blocks_cisd_explained]] 06:06 |
| 10 | (2024, 2026 streams) Always use the series, never a single (insignificant) candle, so the CISD stays mechanical. | stated | [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 11:50; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:05:20; [[a_simple_3_step_trading_model_full_breakdown]] 51:28 |
| 11 | Leave out a candle that does not form a swing, or a tiny consolidation candle; use the actual structural point. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 12:58; [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 20:40 |
| 12 | If the move has no clean series, treat the whole move (large down-close candle plus continuation) as the series; if the LTF is messy, go up one timeframe for a clean series. | stated | [[trading_irl_erl_with_order_blocks_ict_concepts]] 07:16; [[ict_daily_profile_london_reversal_new_york_continuation]] 05:06 |
| 13 | If price makes a new extreme before the close-through, re-anchor on the new candles that made it. | stated | [[trading_irl_erl_with_order_blocks_ict_concepts]] 04:18; [[timeframe_alignment_how_to_align_timeframes_for_expansion]] 05:35; [[ict_daily_profile_new_york_reversal]] 02:11 |
| 14 | Read the CISD from both the previous candle's and the current candle's price action; do not box off the prior candle. | stated | [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 35:50 |
| 15 | A lower-timeframe CISD can be a close back over the HTF candle's opening price that flips that candle's colour. | stated | [[livestream_20260909_new_york_open_live_q_a_k7xvj2w3cp4]] 51:10 |
| 16 | A very aggressive up-down shape on the LTF can count as the CISD on structure; otherwise use the later close. | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:00:20 |
| **Quality** | | | |
| 17 | The ideal CISD is a V-shaped reversal from the sweep. | stated | [[cisd_validates_swing_points]] 8:32; [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 30:40 |
| 18 | Speed: the close-through should take 1, 2, maybe 3 candles; longer usually means it is taking too long. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 09:55; [[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 09:30 |
| 19 | If the retracement leg was large, allow a few more candles and still call it V-shaped. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 16:42 |
| 20 | If the HTF candle consolidated for about half its duration before closing over, treat it as consolidation, not a CISD. | stated | [[cisd_validates_swing_points]] 8:23 |
| 21 | A CISD that takes too long is a consolidation range; its eventual close-over is a sweep of the range high, and price goes to the other side. | stated | [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 50:10; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 14:40; [[trading_candle_3]] 23:22 |
| 22 | If price struggles repeatedly to close over the level and the close that finally gets over sweeps a short-term high, expect failure and a run to the opposite low. | stated | [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 43:20; [[why_your_continuations_fail_order_blocks_cisd_explained]] 00:51 |
| 23 | A CISD that forms only after several failed attempts and wicks is lower quality; prefer the T-spot gap entry for the continuation. | stated | [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 57:00 |
| 24 | A CISD does not need volatility, but do not use a CISD inside consolidation, one not paired with a swing point, or one against your bias. | stated | [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 33:00 |
| 25 | For a valid move off a low he still wants actual displacement / an expansive candle, not choppy candles. | stated | [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 46:20; [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 40:20 (note) |
| 26 | A mechanical close back below is not enough when the price action is slow and shallow; use discernment. | stated | [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 29:40 |
| 27 | Find the swing point first, then look for the CISD; ignore CISDs inside a range that are not at a relevant level. | stated | [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:15:20; [[ttrades_fractal_model_trading_candle_2]] 08:59 |
| 28 | (2024) A London CISD that formed without an HTF level being reached is fake; it builds equal lows/highs for New York to run. | stated | [[ict_daily_profile_new_york_reversal]] 03:43 (definition) |
| **Pairing with the HTF closure** | | | |
| 29 | Every Candle 2 closure needs a CISD on the lower timeframe; a C2/C3 closure without a CISD is not a setup. | stated | [[the_best_timeframe_for_ttrades_fractal_model_simple]] 02:03; [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 16:30; [[candle_2_closure_foundation]] 07:44 |
| 30 | Without the LTF CISD do not treat the HTF closure as a trend shift; an LTF CISD with no HTF closure behind it is ignored too. | stated | [[cisd_validates_swing_points]] 1:11, 2:04 |
| 31 | Confirm the HTF bias one pairing down (1D -> 1h): a CISD from the high/low that made the reversal; entries need both the daily closure and the hourly CISD. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 01:12; [[fractal_model_fundamentals]] 01:53, 02:11; [[next_day_model_fractal_way_to_get_bias_for_trading]] 08:21 |
| 32 | The daily Candle 2 used for a swing trade must also show a CISD before looking for the model next day. | stated | [[ttrades_swing_trading_model_simple_strategy]] 01:37 |
| 33 | A sweep of the previous candle's high/low is confirmed as the wick only with a CISD; a sweep without it is not traded. | stated | [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 03:25, 07:15; [[easy_daily_bias_mechanical_framework]] 01:33 |
| 34 | A sweep low into an FVG is not trusted until a CISD closes through; while price has not closed over the down-close candles, the move is still bearish. | stated | [[trade_continuations_using_breaker_blocks]] 07:22; [[protected_swings_understanding_trend_and_invalidations]] 02:00; [[ttrades_fractal_model_trading_candle_4]] 09:21 |
| 35 | A strong candle close alone is not enough; require a CISD. | stated | [[the_phases_of_price_action_a_blueprint_for_market_movement]] 08:57 |
| 36 | A lower-timeframe CISD (15m/30m) still needs the 4H candle to support expansion (small wick or a formed reversal). | stated | [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 16:00 |
| 37 | Confirm the high/low of day with either a session-timeframe CISD (Asia H1; London H1/M30, rarely M15; New York M15/M5) or an H4/H1 Candle 2 closure at a relevant POI. | stated | [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 09:20; [[livestream_20260910_new_york_open_live_q_a_wa9m30uhrm0]] 04:40 |
| 38 | On a reversal day the New York confirming CISD is usually a 15m CISD; H1 CISD confirmation is for C2/C3-closure trades. A reversal off the low needs at least a 5m (or 3m) CISD. | stated | [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 1:01:50; [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 13:10 |
| 39 | In the scalping model a 5m CISD confirming the 1h is ideal but not required. | stated | [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 50:00 |
| 40 | There is only one CISD per day and it forms the daily wick; if London made it, New York is a continuation. | stated | [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 16:30 |
| 41 | After the CISD, later same-direction order blocks or protected swings are continuations, not new CISDs; one CISD per swing. | stated | [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 22:20; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 1:02:30; [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 29:40 (Q&A) |
| 42 | For a Candle 4 after a Candle 3 closure, one CISD from the swing point (in C2) is enough; not one in both C2 and C3. | stated | [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 45:00 |
| 43 | A daily CISD against the trend is not enough; he wants a continuation to form first. A bullish CISD by itself does not mean a low has formed. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 29:50; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 10:00; [[livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg]] 17:10 |
| **IC-CISD and early CISD** | | | |
| 44 | IC-CISD = the CISD inside the forming HTF candle that forms its wick; it must be off a POI (high, low or FVG); with no FVG or high/low, use the CISD itself. | stated | [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 46:40; [[livestream_20260616_new_york_open_live_q_a_tjuolmjncmy]] 24:40 |
| 45 | What sets his CISD apart from the standard fractal is location: it forms at the wick of the higher-timeframe candle. | stated | [[livestream_20260616_new_york_open_live_q_a_tjuolmjncmy]] 15:20 |
| 46 | IC-CISD entry: let the HTF candle open and make its opposing run into a POI, wait for the close through the series into it (protected swing), enter in the bias direction with the stop on that swing. | stated | [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 1:03:00; [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 40:20; [[livestream_20260729_new_york_open_live_q_a_xraklbjhw5k]] 33:40 |
| 47 | On a C2 closure, to keep trending inside the HTF candle price must respect the EQ and print an IC-CISD on the entry timeframe; without it there is no setup. | stated | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 45:40 |
| 48 | For Candle 3 entries he prefers an IC-CISD (highest win-rate part of the model); positional FVG/OB entries are an alternative. | stated | [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 51:20; [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 41:20 (Q&A) |
| 49 | Early C2 CISD (indicator, off by default) shows the CISD dotted before the HTF candle closes and solid on the closure; he prefers the confirmed continuation and takes the early CISD only with very strong bias. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 11:40, 1:08:50; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 46:10 |
| **Entry, stop, level after the CISD** | | | |
| 50 | (2026 strategy) Check the CISD (it confirms the swing point) but do not enter on it; wait for another continuation. | stated | [[the_only_trading_strategy_you_need_for_2026]] 02:46; [[how_to_trade_consolidation_phases_of_price]] 03:30 |
| 51 | Inside an HTF reversal candle there are two entry types: the first CISD that confirms the wick (reversal entry) and a later continuation order block. | stated | [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 13:00; [[ttrades_fractal_model_trading_candle_2]] 02:42 |
| 52 | Only trade the first CISD as a reversal when bias conviction is very good; he normally waits for the second CISD (the continuation). | stated | [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 51:00; [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 48:40 |
| 53 | No retest is needed: enter when price closes through the level; never market-enter before the candle closes. | stated | [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 26:00; [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 20:00; [[next_day_model_fractal_way_to_get_bias_for_trading]] 15:42 |
| 54 | When retesting a CISD level he prefers price to sweep the previous candle's low first rather than close straight over (a direct close leaves LTF failure swings). | stated | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 1:10:30 |
| 55 | The CISD extreme is the protected swing and the stop; if it is taken the idea is invalid, and trading the failure is a separate invalidation trade. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 01:29; [[trading_candle_3]] 04:29; [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 58:25 |
| 56 | A return from a CISD level also creates a protected swing if it happens in a POI. | stated | [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 48:40 |
| 57 | After the sweep, 0.5 of the CISD (50% of its candles' bodies) must hold; a close back over it is a bad sign / conflicts with the read. | stated | [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 54:10; [[ttrades_top_down_chart_lessons_1]] 03:52; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 1:12:05 (note) |
| 58 | Stop must cover at least 50% of the down-close candle, ideally about 75%. | stated | [[a_simple_3_step_trading_model_full_breakdown]] 51:28 |
| 59 | Skip the CISD when its level sits at (or its close would reach) your short-term target; avoid setups where opposing liquidity sits at the CISD price. | stated | [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 22:20; [[trading_candle_3]] 22:25; [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 34:40 |
| 60 | When the CISD level is too far for the RR: drop one timeframe for a closer CISD, use the HTF closure (e.g. 4H) or a new continuation, or enter off the swing on the closure with the stop below 50% of the candle. | stated | [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 20:50; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 18:40; [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 52:00 |
| 61 | Mechanically the trend has not shifted until price closes through the CISD level, even when you trade without it. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 18:40; [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 19:00 |
| 62 | If price reaches the level but cannot produce a CISD and comes back in, it usually makes a new extreme; wait for that one with its own CISD. | stated | [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 1:15:30; [[ict_daily_profile_new_york_reversal]] 02:11 |
| 63 | After the first target, a CISD the other way warns the continuation may be wrong; failing to form one is a continuation sign. | stated | [[livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg]] 38:00 |
| 64 | Projections: after the CISD the manipulation leg runs from the extreme to the swing that made it; draw no projections before the CISD. | stated | [[targets_using_projections_the_fractal_model]] 01:01, 07:51 |
| 65 | Prefer CISD over IFVG as the entry; in an LTF reversal the inversion comes first, then the CISD. | stated | [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 24:30; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 54:00 |
| **Legacy (MSS era) and CISD vs MSS** | | | |
| 66 | (2022) A structure break counts only with displacement (energetic, large-range candles that leave an FVG); without it, it is a liquidity grab. | stated | [[reversal_or_pullback_using_market_structure_to_determine_trend_ict_concepts]] 03:08, 03:41; [[livestream_20220923_stream_q_a_giveaway_winners_announced_am_traders_0yzqr8hpyeu]] 23:40 |
| 67 | (2022-2023) Displacement = large, full-bodied candles closing at their extremes, through structure; spotted by the FVGs it leaves. | stated | [[structure_shift_vs_liquidity_grab_ict_concepts]] 00:07; [[market_structure_shift_ict_concepts]] 00:10, 00:39 |
| 68 | (2023) CISD comes before or with the MSS: earlier entry, but it can lose where the MSS never confirms. | stated | [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 01:26, 04:18, 05:23 |
| 69 | (2023) Three ways order flow changes: inversion (close through an FVG), CISD (close through the opposing series), MSS (close through the swing). | stated | [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 06:11-06:42 |
| 70 | Use CISD instead of BOS/MSS/CHoCH; a CISD is not the same thing as an MSS. | stated | [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 48:40; [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 1:49:10 |
| 71 | [guest AM Trades] A weekly reversal needs an HTF PD array, the right day of week, then a 1H CISD; a breaker can serve as an alternative CISD. | stated | [[livestream_20230730_live_q_a_with_am_trades_weekly_profile_wgyde_h84cs]] 14:10, 15:30 |
| 72 | With SMT, use the traded index's own down-close series as the opposing candle even though it made no new low; a CISD is not required on both correlated assets. | stated | [[ttrades_top_down_chart_lessons_4]] 4:38; [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 2:14:40 |

## Engine notes

- rules.md §3.11 computes the CISD as the teacher's procedure (rule 3): the anchor at the extreme of the leg, the maximal run of opposite-close bars ending there, level = **highest open** in the run, confirmation = first later close beyond it, re-anchor on a new extreme (rule 13), and the leg must have reached a level (rule 1). Inference: "highest open" equals the teacher's "open of the first candle" (rule 5) for an unbroken down-close run without gaps; they can differ after a gap or a doji.
- §3.11 folds dojis and small candles into the run and states it "does not ignore small candles" (open question 9). That contradicts rules 11 and 12 (leave out non-swing and consolidation candles; use the whole move when there is no clean series).
- Speed: `cisd_max_bars = 3` from rule 18. `cont_entry_cisd_swift` has been advisory since 2026-11-12; a slow entry CISD instead opens the entry range of `cont_not_inside_consolidation`, which matches rule 21. `rev_cisd_swift` stays quality. Rule 19 (more bars after a large leg) and rule 20 (half the HTF candle) are not modelled. No displacement or size test exists (Q10), in line with rules 6 and 24 and against rule 25.
- Pairing: bias case H (closure plus POI, no setup-timeframe CISD) is `watch`, and the entry CISD must be anchored inside the setup swing candle (§5.3, §6 c3). This matches rules 29-31. The engine has no "one CISD per day" rule (rule 40) and no CISD-vs-target distance test (rule 59).
- Entry: `entry_mode = either` (trader answer Q14) accepts the CISD trigger or a continuation order block. That sits between rule 50 (2026: never enter on it) and rules 51-53 (either / close entry). Q28 notes that `either` almost always fires on the CISD (144 of 149 in the 2025 sweep), so the engine leans to the entry the 2026 strategy video rejects. Inference.
- IC-CISD: the continuation path already works as an IC-CISD at two levels (setup-timeframe closure inside `B[0]`, then an entry CISD), and `cont_entry_early_in_candle` (0.75) bounds lateness. The reversal path's CISD may confirm on `E` only for a 1D bias in New York (§7 c3; Q19). Rules 37-38 give a session table (Asia H1, London H1/M30, NY M15/M5) that a fixed three-role stack cannot follow.
- Protected swing = CISD anchor, broken by any trade-through (§3.15; Q24). This matches rule 55. The 0.5-of-CISD hold level (rule 57) has a close cousin in the order-block mean threshold (§3.12), but only as a POI test, not as an invalidation of the idea.
- No TD decision covers CISD; `decisions.md` has no rows yet.

## How it changed over time

- **2022 (MSS era).** Trend change = market structure shift with displacement that leaves an FVG; a wick-only or lethargic break is a liquidity grab; BOS vs MSS labels "mean basically the same thing" ([[what_is_displacement_ict_concepts]] 00:39; [[livestream_20220810_stream_q_a_with_trade_for_opportunity_ict_concepts_0bh_kkg2q6s]] 19:20; [[livestream_20220923_stream_q_a_giveaway_winners_announced_am_traders_0yzqr8hpyeu]] 23:40). The rough analogue is the 2022 order-block use of the series and its opening price ([[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 28:45 note).
- **2023.** MSS video (full-bodied displacement, close over structure, then a PD array) ([[market_structure_shift_ict_concepts]] 02:07-07:23). AM Trades brings CISD onto his stream in July ([[livestream_20230730_live_q_a_with_am_trades_weekly_profile_wgyde_h84cs]] 14:40), and TTrades says he "definitely prefers" it over MSS (50:10). The CISD video in November sets the definition: the series into an HTF PD array, the first candle's open, an order-block formation ([[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 00:10-01:06). In December he lays out CISD vs MSS ([[market_structure_shift_vs_change_in_state_of_delivery_ict]] 00:57-06:42).
- **2024.** The daily-profile videos use CISD (London 2-5 a.m.; NY at the PDL; fake CISD), still sometimes "CISD or MSS" interchangeably ([[ict_daily_profile_london_reversal_new_york_continuation]] 01:43 note, 02:46; [[ict_daily_profile_new_york_reversal]] 01:43-03:43). In October: series only, close through the opening price, "never a single candle"; the CISD/order block is "the only entry confirmation" ([[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 11:50, 26:40). In November the indicator confirms the HTF bias one pairing down with a CISD ([[intro_to_ttrades_fractal_model_indicator_settings]] 01:12).
- **2025.** CISD is a step in every playbook: C2 confirmation, protected swing, entry ([[fractal_model_fundamentals]] 02:11, 09:05; [[trading_candle_3]] 01:39). The series may be one candle ([[protected_swings_understanding_trend_and_invalidations]] 04:10). Slow CISD = consolidation ([[trading_candle_3]] 23:22). Skip a CISD at the target ([[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 22:20). The indicator gets its early-CISD mode ([[ttrades_fractal_model_trading_candle_2]] 04:41 definition).
- **2026.** The CISD validates swing points (V-shape, consolidation test) ([[cisd_validates_swing_points]] 0:18-8:32). Why continuations fail (1-3 candles) ([[why_your_continuations_fail_order_blocks_cisd_explained]] 09:55). The 2026 strategy video: confirm with the CISD but enter on the next continuation ([[the_only_trading_strategy_you_need_for_2026]] 02:46). The streams add IC-CISD as his named concept ([[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 46:40), one CISD per day ([[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 16:30), session confirmation timeframes ([[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 09:20), "no volatility requirement" ([[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 33:00), body-only ([[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 38:40), and "never a single candle" again ([[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:05:20). The MSS-to-CISD change is explicit: "He moved from market structure shift (2022) to CISD" ([[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 45:00).

## Examples

- 5m next-day model: the CISD level is the series that made the high; enter on the close through it, stop on the high, 2R ([[next_day_model_fractal_way_to_get_bias_for_trading]] 15:42).
- NQ news day: lows run at 8:30 after a consolidation; the close through the single down-close candle that took the low is the LTF CISD ([[ttrades_fractal_model_trading_candle_4]] 05:22).
- Hourly CISD after a consolidation: a sweep of the consolidation high, a close through the up-close series that made it, so the daily high is in from 06:00 ([[livestream_20260910_new_york_open_live_q_a_wa9m30uhrm0]] 04:40-05:00).
- Rejected CISD: a viewer's 1m "CISD" at an OTE at 9:35; no new low was made, so it is not a CISD ([[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 1:10:20).
- Gold IC-CISD: the down-closed candles into the POI, then a close over them; that swing is the invalidation ([[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 1:03:00).
- Slow CISD: two candles down, six up without reclaiming; not V-shaped, so consolidation ([[why_your_continuations_fail_order_blocks_cisd_explained]] 09:55).

## Conflicts and open questions

- CISD-1: Can the series be a single candle (2025-2026 videos) or never (2024, 2026 streams)?
- CISD-2: Level = open of the first candle of the series vs "close below the last up-close candle"; engine uses the highest open.
- CISD-3: Which candles are in the series (skip non-swing / consolidation candles, whole move, previous candle, HTF open).
- CISD-4: Displacement / size: required (2023 wording, 2026 "actual displacement", FVG) vs "no volatility needed", "body size does not matter".
- CISD-5: Speed limit: 1-3 candles vs more after a large leg vs half the HTF candle.
- CISD-6: Enter on the CISD vs wait for the continuation (and retest or not).
- CISD-7: CISD vs MSS (superseded: MSS dropped after 2022).
- CISD-8: "One CISD per day" vs "wait for the second CISD".
- CISD-9: Confirmation timeframe per session and per pairing.
- CISD-10: Is the LTF CISD mandatory (every C2) or replaceable (4H closure, "ideal not required")?
- CISD-11: CISD level too close to / too far from target: no number; several alternatives.
- CISD-12: New extreme required vs IC-CISD off an FVG / SMT without new low.
- CISD-13: "Important level" for a CISD undefined.
- CISD-14: Does a single CISD flip the trend (2023, 2025) or need a continuation (2026)?
- CISD-15: 0.5 of the CISD: bodies vs range; hold level vs stop coverage.
- CISD-16: Engine series selection (highest open, dojis folded in) vs teacher's structural series.
- CISD-17: Engine has no "no CISD inside consolidation / not at a swing point" filter beyond the entry range.
- CISD-18: Engine's fixed stack vs the teacher's session-dependent confirmation timeframe.
- CISD-19: Engine `entry_mode = either` fires on the CISD almost always; 2026 strategy says do not enter on it.
- CISD-20: Speech slips (indicator intro "down close candle that made that high"; same candle as bullish and bearish C2).
- CISD-21: Ideal Formation and the IC-CISD education video (seed playbook) are not in this corpus.

## Related

- [[candle-closures]]: the HTF C2/C3 closure the CISD must confirm.
- [[fractal-model]]: valid model = HTF closure + LTF CISD inside that candle.
- [[liquidity]]: the sweep or tap that the series delivers into.
- [[poi-and-pd-arrays]]: order block = the series closed through; FVG as the CISD's POI; IFVG vs CISD.
- [[swings-and-structure]]: protected swing is the CISD extreme; MSS/BOS legacy terms.
- [[entry-models]]: CISD entry vs continuation order block; IC-CISD entry.
- [[risk-and-management]]: stop on the protected swing / bodies; 0.5 of the CISD; projections.
- [[sessions-and-time]]: session-dependent CISD timeframe; one CISD per day forms the daily wick.
- [[ranges-and-eq]]: slow CISD = consolidation range; T-spot.
- [[smt-and-psp]]: SMT is confirmed by a CISD.
- [[ttfm-indicator]]: CISD lines, early C2 CISD setting.

## Questions this page answers

- What exactly is a CISD and how do I find its level?
- Which candles make up the "series", and can it be one candle?
- Is a wick through the level enough, or does it need a body close?
- How fast must a CISD be, and when is it just consolidation?
- Does a CISD need displacement or an FVG?
- Does every Candle 2 / Candle 3 closure need a lower-timeframe CISD, and on which timeframe?
- What is an IC-CISD and how do I enter with it?
- Should I enter on the CISD or wait for the continuation?
- What is the difference between CISD and market structure shift, and when did TTrades switch?
- What do I do when the CISD level is at my target or too far away?
- What is "one CISD per day"?
- How does the companion engine compute the CISD, and where does it differ from the teacher?
