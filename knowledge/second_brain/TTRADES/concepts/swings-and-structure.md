---
id: swings-and-structure
title: "Swing points, protected swings and market structure"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [swing point, swing high, swing low, bullish swing point, bearish swing point, protected swing, protected high, protected low, protected swings, failure swing, failure swings, failed swing, relevant swing, relevant high, relevant low, valid separation, separation, market structure, market structure shift, MSS, market structure break, MSB, break of structure, BOS, short-term high, short-term low, STH, STL, intermediate-term high, intermediate-term low, ITH, ITL, long-term high, long-term low, LTH, LTL, advanced market structure, higher low, lower high, equal highs, equal lows, relative equal highs, stacked lows, stacked liquidity, trade away from, invalidation, trailing invalidation, structure trailing, low resistance liquidity, LRL, pivot machine gun, downclo candles]
covers: [swing-point, relevant-swing, failure-swing, valid-separation, protected-swing, swing-invalidation, market-structure, trend-definition, market-structure-shift, advanced-market-structure]
sources:
  - protected_swings_understanding_trend_and_invalidations
  - which_swing_highs_and_lows_matter_in_trading
  - a_simple_3_step_trading_model_full_breakdown
  - ict_advanced_market_structure_simplified
  - understanding_market_structure_for_trading
  - how_to_trade_expansion_phases_of_price
  - how_to_trade_retracement_phases_of_price
  - ttrades_top_down_chart_lessons_1
  - livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy
  - livestream_20260722_new_york_open_live_q_a_g1iidq3raky
  - livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq
  - livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims
  - livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi
  - livestream_20261103_new_york_open_live_q_a_tqokgrazwky
  - livestream_20260318_new_york_open_live_q_a_yud7tpe2ams
  - livestream_20260310_new_york_open_live_q_a_wm1s7uivq08
  - livestream_20260825_new_york_open_live_q_a_9h15zzvakpq
  - livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg
  - easy_daily_bias_mechanical_framework
  - cisd_validates_swing_points
  - market_structure_shift_vs_change_in_state_of_delivery_ict
  - intro_to_market_structure_shifts_fair_value_gaps_and_displacement_ict_concepts
  - livestream_20220814_stream_q_a_with_am_trades_ict_concepts_cruftskoveo
  - fractal_model_fundamentals
confidence: medium
chain_step: ["3 setup", "4 entry", "5 manage"]
timeframe_role: [any]
requires: [candle-closures, cisd, liquidity, poi-and-pd-arrays]
feeds: [entry-models, risk-and-management, daily-bias, fractal-model, ranges-and-eq]
---

# Swing points, protected swings and market structure

## Definition

**Latest (2025-2026, TTFM).** A *swing point* is a three-candle pivot: a bullish swing point is a candle whose low has a higher low on its left and on its right; a bearish one is a candle whose high has a lower high on both sides ([[which_swing_highs_and_lows_matter_in_trading]] 00:35, 00:45; [[ttrades_fractal_model_trading_candle_4]] 02:10). The whole model rests on one premise: price cannot reverse without forming a swing point ([[fractal_model_fundamentals]] 00:22; [[livestream_20261028_new_york_open_live_q_a_c4ti6kdxn0s]] 12:10). A *protected swing* is a high or low "expected to hold as the trend continues" ([[protected_swings_understanding_trend_and_invalidations]] 00:18). It forms when price sweeps a low or reaches into a gap / point of interest and then *closes* through the series of opposing candles that delivered price there, i.e. a CISD; that close confirms the swing ([[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 57:00; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:02:20). It is the invalidation and the stop of every trade ([[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 43:40). Not every swing counts: a *relevant swing* is the extreme of its cluster, has "valid separation" from the swing beside it and sits inside a lookback of three higher-timeframe candles ([[which_swing_highs_and_lows_matter_in_trading]] 01:12, 03:31). A *failure swing* is a swing too close to (or stacked beside) another, or a deep run back into a reversal point that did not take it out; it is liquidity to target, never a level to trade away from ([[a_simple_3_step_trading_model_full_breakdown]] 02:13; [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 1:10:50). Separation has no number, by the teacher's own statement ([[which_swing_highs_and_lows_matter_in_trading]] 12:21).

**2023-2024 (transition).** Market structure is taught as higher highs / higher lows and lower highs / lower lows; a higher high exists on the close beyond the old high, and the trend stays bullish while the relevant swing low holds ([[understanding_market_structure_for_trading]] 00:37, 03:27, 09:02). ICT's *advanced market structure* adds short-, intermediate- and long-term swings: an intermediate-term low is a short-term low with higher short-term lows on both sides, and it should not be violated while the leg continues ([[ict_advanced_market_structure_simplified]] 01:00, 08:24). A *market structure shift* (MSS) is a sweep followed by displacement and a close beyond the opposite swing ([[market_structure_shift_vs_change_in_state_of_delivery_ict]] 00:57). Late 2024 the protected swing appears with the indicator: once the CISD closes through, the high that made it is protected ([[intro_to_ttrades_fractal_model_indicator_settings]] 01:29).

**2022 (ICT-concepts streams).** Structure is "highs and lows: short-term, swing and relative equal highs/lows" ([[intro_to_market_structure_shifts_fair_value_gaps_and_displacement_ict_concepts]] 00:06). The MSS is a lower high (in a downtrend) broken with displacement, leaving an FVG ([[intro_to_market_structure_shifts_fair_value_gaps_and_displacement_ict_concepts]] 01:36). A structure break without displacement does not count ([[index_futures_weekly_recap_ict_concepts]] 10:27). He later says he dropped MSS / break of structure for the CISD because it is "simpler and mechanical" ([[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 45:00), and that protected swings simplify ICT's intermediate-term low ([[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 55:00).

## Rules

| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |
|---|---|---|---|
| **Swing points** | | | |
| 1 | A swing low is a candle whose low has a higher low immediately left and right; a swing high mirrors it (one candle each side, no other size rule). | high | [[which_swing_highs_and_lows_matter_in_trading]] 00:35, 00:45; [[liquidity_buyside_sellside_ict_concepts]] 00:39; [[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 38:50 |
| 2 | Price cannot reverse without a swing point, so every trade is framed off a swing (swing low to turn up, swing high to turn down). | high | [[fractal_model_fundamentals]] 00:22; [[ttrades_fractal_model_trading_candle_4]] 00:26; [[the_only_trading_strategy_you_need_for_2026]] 00:28; [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 25:50 |
| 3 | A swing is not confirmed until the candle on its right forms; a lower low only counts once a swing low is put in. | high | [[breaker_blocks_simplified_ict_concepts]] 01:04; [[ict_advanced_market_structure_simplified]] 02:47 |
| 4 | Swing points are both draws on liquidity (resting stops) and places to frame reversals. | high | [[liquidity_buyside_sellside_ict_concepts]] 00:10; [[ict_daily_bias_the_only_video_you_will_ever_need]] 07:28 |
| 5 | (2026) Every candle 2 is a swing point, but only a C2 or C3 closure at a POI is a swing worth framing; a plain swing high without that closure is ignored. | medium | [[livestream_20261006_new_york_open_live_q_a_rtomj8urfnw]] 43:40; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:02:20 |
| 6 | A swing point that price fails to displace through (closes back inside) frames a reversal back into the range. | medium | [[intraday_bias_simplified_ict_concepts]] 10:27 |
| **Relevant swings and separation** | | | |
| 7 | A swing with older highs (lows) still beyond it to its left is not relevant; walk out to the extreme of the cluster and use that one. | high | [[which_swing_highs_and_lows_matter_in_trading]] 01:12 |
| 8 | Only relevant swings are places to look for a reaction; there, watch whether price manipulates (sweep and close back) or breaks out (consolidates and continues). | high | [[which_swing_highs_and_lows_matter_in_trading]] 01:36 |
| 9 | A low that forms very close to the previous low lacks separation; do not expect a reversal from it without that previous low being taken. | high | [[which_swing_highs_and_lows_matter_in_trading]] 01:54; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 54:30 |
| 10 | Separation is judged visually, not by a percentage or point count; close-together swings count as one, well-separated ones are each a target. | high | [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 26:20; [[which_swing_highs_and_lows_matter_in_trading]] 12:21 |
| 11 | The most relevant low is the one with enough separation that it could have held while price ran the other low; if it breaks, move to the next low further left. | medium | [[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 04:00, 55:00 |
| 12 | Relevance lookback: use the highs and lows inside the current higher-timeframe candle and the two before it (daily chart → 3 months, hourly → 3 days). | high | [[which_swing_highs_and_lows_matter_in_trading]] 03:31 |
| 13 | (2026, 3-step model) Ignore daily highs/lows older than about 30 daily candles. | medium | [[a_simple_3_step_trading_model_full_breakdown]] 45:58 |
| 14 | Keep re-marking relevant swings as price moves: each new retracement makes a new relevant high or low. | high | [[which_swing_highs_and_lows_matter_in_trading]] 06:21 |
| 15 | A manipulation at a relevant swing is valid only with valid separation: its own extreme must not form a new failure swing against a daily high/low to its left. | medium | [[a_simple_3_step_trading_model_full_breakdown]] 04:40 |
| 16 | When nearby draws are taken and price keeps closing beyond, look left to older swing points. | medium | [[ict_daily_bias_the_only_video_you_will_ever_need]] 12:44 |
| **Failure swings** | | | |
| 17 | A failure swing is a set of lined-up (equal or stacked) highs or lows not yet taken; it is structure, not a candle pattern. | high | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 1:10:50; [[which_swing_highs_and_lows_matter_in_trading]] 08:17 |
| 18 | (2026) A deep run back into a reversal point that does not take it out makes a failure swing; treat that reversal as unestablished. | high | [[a_simple_3_step_trading_model_full_breakdown]] 02:13, 01:56 |
| 19 | (2023-2024, ICT) A failure swing / low-resistance liquidity is a swing followed by a lower high (higher low) that reversed without sweeping the first. | medium | [[low_resistance_liquidity_run_ict_concepts]] 01:07, 03:06; [[high_resistance_vs_low_resistance_liquidity_ict_concepts]] 00:02 |
| 20 | Never trade away from a failure swing or from equal / stacked lows; wait for the relevant (extreme) swing to be taken first. | high | [[a_simple_3_step_trading_model_full_breakdown]] 02:13; [[which_swing_highs_and_lows_matter_in_trading]] 05:05; [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 50:30; [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:00:40 |
| 21 | Failure swings are targets: they tend to be revisited and taken before the real move, and clusters of them are where stops get run. | high | [[ttrades_top_down_chart_lessons_1]] 04:22; [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 17:10; [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 29:00 |
| 22 | If the opposite-side swing is a failure swing, only take the direction toward the relevant swing (e.g. shorts only). | high | [[which_swing_highs_and_lows_matter_in_trading]] 06:05; [[ttrades_fractal_model_trading_candle_2]] 05:59 |
| 23 | Failure swings without SMT are not trusted; at lined-up highs he shorts only after the strongest asset sweeps them (or the weakest sweeps lows for longs). | medium | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 18:20; [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 1:07:40; [[livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg]] 10:30 |
| 24 | Do not short an asset with failure swings above it from the open; wait for a manipulation first. | medium | [[ttrades_top_down_chart_lessons_4]] 1:42; [[eurgbp_for_relative_strength_eu_vs_gu]] 4:26 |
| 25 | Equal highs sitting below a previous high are failure swings: expect a run toward the previous high and do not put a stop just above them. | medium | [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 29:40 |
| 26 | Draws on liquidity should ideally be failure swings, not protected swings; slightly swept equal lows are harder targets than clean failure swings. | medium | [[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 36:20, 31:40 |
| 27 | On low-expectation days target the failure swing to the right of the protected swing, or the current daily range low, not the protected swing itself (hard to reach). | medium | [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 43:40; [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 26:20; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 1:28:50 |
| 28 | Failure swings left by an expansion or a retracement are targets, not reversal points, until price shows it wants to expand away. | medium | [[gxtradez_phases_of_price_profiles_for_expansion]] 07:30 (guest); [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 24:47 (guest); [[how_to_trade_retracement_phases_of_price]] 1:18 |
| **Protected swing: formation** | | | |
| 29 | Type 1: a short-term low is swept, then price closes through the series of down-close candles that made the low; the low is now protected (mirror for highs). | high | [[protected_swings_understanding_trend_and_invalidations]] 00:40; [[livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg]] 31:40 |
| 30 | Type 2: price reaches into an FVG / POI and closes through the down-close candle(s) that went into it; the series can be a single candle. | high | [[equilibrium_for_expansions]] 03:43; [[how_to_trade_expansion_phases_of_price]] 01:47; [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 48:30 |
| 31 | No close through = no protected swing = no entry from it; a wick into the level does not qualify. | high | [[ttrades_top_down_chart_lessons_1]] 05:20; [[how_to_trade_expansion_phases_of_price]] 04:46; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 1:16:40; [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 37:20 |
| 32 | The protected swing is valid on the closing candle and prints on the next candle's open (indicator: dot plus line; never repaints). | high | [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 1:11:20; [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 04:20, 25:00 |
| 33 | Ignore insignificant small opposing candles inside a series; on a messy series use the cleaner leg. | medium | [[protected_swings_understanding_trend_and_invalidations]] 04:39, 10:10 |
| 34 | If there is no FVG or swept low to act as the important level, use 0.5 of the opposing candle as the level. | low | [[how_to_trade_consolidation_phases_of_price]] 06:47 |
| 35 | (2026) A swing is only a TTFM protected swing if the move away from it left an FVG; a continuation without one is less trustworthy. | low | [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 49:10 |
| 36 | A lethargic move back into the range after the sweep does not confirm a protected swing; a swing that takes a long time to form is a consolidation range. | medium | [[protected_swings_understanding_trend_and_invalidations]] 09:16; [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:28:00 |
| 37 | A shallow swing that barely sweeps (near-equal highs) is not trustworthy; the swing needs a real reach. | medium | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 24:00; [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 27:05 |
| 38 | With SMT (one index runs the low, the other does not), the low of the index that held is protected once price closes over. | medium | [[how_to_trade_consolidation_phases_of_price]] 02:26; [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 1:07:30 |
| 39 | You may anticipate a protected swing on a strong reaction (early entry inside the candle), but if that candle does not close over the level, scratch the trade. | medium | [[livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg]] 31:40, 55:00; [[protected_swings_understanding_trend_and_invalidations]] 08:30 |
| 40 | The ideal is a C2/C3 closure that creates the protected swing at the same time; a separate closure afterwards is acceptable. | high | [[candle_3_closure_ttrades_fractal_model]] 07:13; [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 47:00; [[ttrades_top_down_chart_lessons_3]] 02:34 |
| 41 | The lower-timeframe protected swing is what forms the higher-timeframe candle's wick; expect the move once it forms inside the HTF candle. | high | [[higher_timeframe_analysis_for_trading_aligning_expansion_candles]] 02:29; [[trading_the_4_hour_power_of_three_ohlc_olhc]] 03:01; [[cisd_validates_swing_points]] 9:38 |
| 42 | Positional entry: a protected swing formed before the new HTF candle opens may be traded at that open, but only with high bias confidence; otherwise let the HTF candle form its wick. | medium | [[livestream_20260915_new_york_open_live_q_a_hlwq1drjbzo]] 42:30; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 41:40; [[ttrades_scalping_model_simple_day_trading_strategy]] 10:24 |
| 43 | On the setup candle (e.g. 15m in a 1m-15m model) a swing formed just before the new candle opens is suspect; one formed at the open is tradable. | low | [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:00:40 |
| 44 | Do not trade the first swing low of a turn; wait for the higher low to form its wick, then trade it. | medium | [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 42:40; [[trade_continuations_using_order_blocks]] 00:47 |
| **Protected swing: holding and invalidation** | | | |
| 45 | While the trend continues the latest protected swing must not be taken; track each new protected swing as it forms (trailing invalidation). | high | [[how_to_trade_expansion_phases_of_price]] 03:06; [[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 14:00; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 16:30 |
| 46 | Violation of the protected swing ends the trend; back through the protected high of a bearish trend means chop, stop trading the idea. | high | [[how_to_trade_retracement_phases_of_price]] 7:02; [[ttrades_top_down_chart_lessons_1]] 14:25; [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 1:13:20 |
| 47 | If a continuation's protected swing is taken, the trend is weak / consolidating. | high | [[cisd_validates_swing_points]] 7:34 |
| 48 | A protected swing is protected only until price hits liquidity (the target or opposing extreme); after that it is often run once and then the trend continues. | high | [[easy_daily_bias_mechanical_framework]] 08:21; [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 18:20; [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 35:20; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 57:50 |
| 49 | Once the previous day low has been taken, the protected swing below it no longer counts; look to the next HTF target. | medium | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 04:40 |
| 50 | After a closure, price should hold about 0.5 of the leg (or of the candle closed over); only a lower-timeframe low in that area may be swept. | medium | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:08:20; [[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 40:20; [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 1:32:00 |
| 51 | A level that must be respected sees no closes beyond it; one close beyond is tolerated only if the next candle is bought back immediately; its low taken ends it. | medium | [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 1:02:30 |
| 52 | At a protected swing near the open of the next HTF candle expect only a small wick through; if it is disrespected, price runs it out before going the other way. | medium | [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 05:00 |
| 53 | A protected swing that holds stays valid even after a deep retrace into the leg; do not judge it on very low timeframes or with too-tight stops. | medium | [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 1:36:40 |
| 54 | A protected swing that later fails was not "false": it was valid mechanically and then failed (the indicator greys it out). | high | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 42:40, 25:00 |
| 55 | If the bias fails, the low (high) it relied on was not a swing point and becomes the draw on liquidity. | medium | [[livestream_20260910_new_york_open_live_q_a_wa9m30uhrm0]] 09:20 |
| **Trading from swings** | | | |
| 56 | Every trade needs a swing / protected swing to trade away from; it is the invalidation and the stop; with none, wait (next day if needed). | high | [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 43:40; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 27:30; [[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 10:15; [[the_phases_of_price_action_a_blueprint_for_market_movement]] 13:33 |
| 57 | Once a new protected swing forms, the stop may move to it. | medium | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 24:30 |
| 58 | If you missed the entry, wait for a retracement and a new continuation with a new protected swing; do not trade from the middle of a move or chase a breakout. | high | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 40:20; [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 08:20; [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 13:00; [[livestream_20260909_new_york_open_live_q_a_k7xvj2w3cp4]] 15:20 |
| 59 | Trade the continuation after the reversal from its protected swing, not the reversal extreme itself. | high | [[how_to_trade_reversal_phases_of_price]] 02:29; [[livestream_20260311_cpi_new_york_open_live_q_a_egv_gabtqks]] 1:36:40 |
| 60 | In a bearish idea he wants a new lower high and lower low, not the last high taken; no lower high means no trade. | high | [[ttrades_top_down_chart_lessons_3]] 01:12; [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 39:40; [[livestream_20260311_cpi_new_york_open_live_q_a_egv_gabtqks]] 1:18:50 |
| 61 | Protected swings on both sides with mixed candles is chop: no trade; let the day form (Asia, London) before picking a side. | medium | [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 06:55; [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 28:10 |
| 62 | Equal lows under a continuation are a red flag; a sweep of them is acceptable only if quick and aggressive both ways. | medium | [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 55:00 |
| 63 | The level to trade away from matters, not the timeframe; on stocks turn protected swings off and prefer higher timeframes. | low | [[livestream_20260311_cpi_new_york_open_live_q_a_egv_gabtqks]] 1:26:40; [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 47:30 |
| **Market structure (trend)** | | | |
| 64 | Price trends up only by higher highs and higher lows (down: lower highs and lower lows); after a higher high expect a higher low, then a close over the high. | high | [[understanding_market_structure_for_trading]] 00:37, 01:06, 03:27 |
| 65 | A higher high exists on the close beyond the old high, before its swing high has formed. | medium | [[understanding_market_structure_for_trading]] 03:27 |
| 66 | Minor highs/lows inside a leg get swept; judge the trend against the defining swing, which keeps the trend bullish while unbroken. | high | [[understanding_market_structure_for_trading]] 06:11, 09:02 |
| 67 | The easiest trend definition: a bullish trend keeps taking the previous day high, a bearish one the previous day low. | medium | [[the_easiest_draw_on_liquidity_dol_daily_bias_ict]] 00:34 |
| 68 | A trending market respects opposing candles: down-close candles support an uptrend, up-close candles cap a downtrend; mark them off the body. | high | [[trade_continuations_using_order_blocks]] 15:06; [[how_to_trade_expansion_phases_of_price]] 01:40; [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 17:30 |
| 69 | Do not read lower-timeframe structure without HTF context: get a daily C2 closure first and only mark structure in that direction. | medium | [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 1:02:10 |
| **Market structure shift and advanced structure (2022-2024)** | | | |
| 70 | (2022) An MSS is a short-term swing broken with displacement that leaves an FVG; without displacement it is a liquidity grab, not a shift. | high | [[intro_to_market_structure_shifts_fair_value_gaps_and_displacement_ict_concepts]] 01:36; [[index_futures_weekly_recap_ict_concepts]] 10:27; [[find_lower_time_frame_entries_using_bias_ict_concepts]] 06:23 |
| 71 | (2022-2023) At a POI, no short until swing lows are taken with displacement; displacement without a prior stop raid does not qualify. | high | [[index_futures_weekly_recap_ict_concepts]] 02:57; [[a_ict_entry_checklist_ict_concepts]] 07:19 |
| 72 | (2023) MSS sequence: swing formed, liquidity swept, displacement and a close beyond the opposite swing; it may give no entry if price never retraces. | high | [[market_structure_shift_vs_change_in_state_of_delivery_ict]] 00:57, 04:18; [[market_structure_shift_vs_liquidity_grab_ict_concepts]] 01:02 |
| 73 | (2022) Prefer a higher-timeframe low (not a tiny 1m low) being broken before calling displacement. | medium | [[structure_shift_vs_liquidity_grab_ict_concepts]] 01:35 |
| 74 | (2024, ICT) Intermediate-term low = a short-term low with higher short-term lows on each side; long-term low = the low off a reaction to an HTF level, validated once a short-term swing forms on its right. | medium | [[ict_advanced_market_structure_simplified]] 01:00, 01:25, 02:47 |
| 75 | (2024, ICT) A short-term high broken may be called a shift, but he prefers the intermediate-term high taken; once an intermediate-term low is confirmed it should not be violated. | medium | [[ict_advanced_market_structure_simplified]] 04:41, 08:24, 10:19 |
| 76 | (2024) Advanced-structure entry: long-term low, short-term low, intermediate-term low; enter at the short-term low to the right of the intermediate-term low. | low | [[niper_internal_external_liquidity_ict_daily_bias]] 21:00 (guest) |
| 77 | (2026) He does not use break of structure (wick); only the body-based CISD level counts, and the protected swing replaces waiting for ICT's intermediate-term low. | high | [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 38:40; [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 45:00; [[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 57:00 |

## Engine notes

- **Swing point.** `companion/styles/ttrades/rules.md` 3.1 computes a strict three-bar fractal (`low[i] < low[i-1]` and `low[i] < low[i+1]`), confirmed at the close of bar `i+1`; ties are not swings (proposal). This matches rule 1; the teacher never states a tie rule (inference).
- **No relevance or separation filter.** rules.md 3.1 and open question 12 accept any confirmed swing inside the lookback as a POI, so the engine accepts the failure swings and equal lows the teacher refuses to trade away from (rules 7-10, 20). The seed playbook proposed a `swing_relevance` switch (`knowledge/second_brain/wiki/playbooks/ttfm-swing-quality-cisd-ic-cisd.md`, candidate 1); nothing is decided (no TD row).
- **Lookback.** `swing_lookback_roles` = 3 candles of the next role up (source rule 12); `bias_poi_lookback_bars` = about 66 daily bars for a 1D bias (rules.md section 11). The 3-step model's "about 30 daily candles" (rule 13) is not used; see SW-3.
- **Protected swing.** rules.md 3.15: a bullish CISD whose leg reached a level creates the protected low; broken by the first later bar with `low < price`, i.e. by wick (`protected_swing_break_on = "wick"` in `config.json`, open question 24). The teacher forms it by close (rule 31) but never says whether a wick or a close breaks it, and once tolerates one close beyond (rule 51); see SW-1.
- **Missing teacher qualifiers (inference).** No test for "FVG left by the move away" (rule 35), for a slow-forming swing beyond `cisd_max_bars` other than the consolidation check (`cont_not_inside_consolidation`, rule 36), for the shallow-sweep distrust (rule 37), or for "protected only until liquidity is hit" (rule 48).
- **Positional swings.** Open question 20: protected swings formed before the bias candle opened are ignored; the teacher uses them for positional entries (rule 42) yet calls a setup-candle swing formed just before the open suspect (rule 43); see SW-8.
- **Trailing.** `cont_newer_protected_low` only reports a newer protected low and the R it would lock; the plan's stop does not move. The teacher moves the stop to the new protected swing (rule 57).
- **Series.** rules.md 3.11 counts every down-close bar in the run and does not ignore small interrupting candles (open question 9), unlike rule 33. The engine has no MSS / BOS; it is CISD-only, which matches the 2026 stance (rule 77).

## How it changed over time

- **2022 (ICT-concepts Q&A).** Structure is highs and lows plus relative equal highs/lows; the trigger is an MSS (swing broken with displacement and an FVG); a break without displacement is a stop raid ([[intro_to_market_structure_shifts_fair_value_gaps_and_displacement_ict_concepts]] 00:06, 01:36; [[index_futures_weekly_recap_ict_concepts]] 10:27). AM Trades (guest) teaches intermediate-term swings and wants bearish intermediate-term highs unviolated ([[livestream_20220814_stream_q_a_with_am_trades_ict_concepts_cruftskoveo]] 29:50). Trailing structure on the 1m "gets choppy" ([[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 49:00). The MSS by close, not wick, comes from the guest and the ICT slide ([[livestream_20220810_stream_q_a_with_trade_for_opportunity_ict_concepts_0bh_kkg2q6s]] 1:06:00).
- **2023.** MSS = sweep, displacement, close beyond structure ([[market_structure_shift_vs_liquidity_grab_ict_concepts]] 01:02); the close below an order-block series is treated as the MSS ([[my_favorite_reversal_pattern_orderblocks_ict_concepts]] 08:01), the bridge to the CISD. Failure swings appear as ICT low-resistance liquidity ([[low_resistance_liquidity_run_ict_concepts]] 01:07).
- **2024.** HH/HL market-structure basics ([[understanding_market_structure_for_trading]] 00:37) and ICT advanced market structure ([[ict_advanced_market_structure_simplified]] 01:00-12:56). Sunday sessions introduce trailing invalidation off each closed-through opposing candle ([[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 14:00). The indicator video names the protected high after a CISD ([[intro_to_ttrades_fractal_model_indicator_settings]] 01:29).
- **2025.** The protected-swing video gives two types (sweep, FVG reach) and the invalidation role ([[protected_swings_understanding_trend_and_invalidations]] 00:18, 00:40); the phases-of-price series ties the trend to the latest protected swing ([[how_to_trade_expansion_phases_of_price]] 03:06) and "no protected swing, no trade" ([[the_phases_of_price_action_a_blueprint_for_market_movement]] 13:33). Failure swings become "equal highs with no protective close" ([[ttrades_top_down_chart_lessons_1]] 04:22, 05:20).
- **2026.** Relevant swings, valid separation and the three-HTF-candle lookback ([[which_swing_highs_and_lows_matter_in_trading]] 00:35-12:21); the 3-step model's failure swing as an unestablished reversal and the ~30-day cut-off ([[a_simple_3_step_trading_model_full_breakdown]] 02:13, 45:58). The indicator update plots protected swings as non-repainting dots ([[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 04:20). Explicit supersession: "moved from market structure shift (2022) to CISD" ([[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 45:00), protected swings replace the intermediate-term low ([[livestream_20260722_new_york_open_live_q_a_g1iidq3raky]] 55:00, 57:00). Livestreams add the lifecycle (protected until the target is hit) and the SMT exception for failure swings.

## Examples

- Gold short: price sweeps a high and closes below, holds 0.5 of the leg, retraces into a small FVG and closes below again; entry on that close ([[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:08:20).
- Separation in points: NQ's two lows about 400 points apart make a better low to trade from than ES's lows sitting close together ([[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 04:00).
- ES's three equal highs are failure swings he will not short from, even with NQ's PDH sweep and SMT ([[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 28:20).
- Indicator demo: an early CISD candle fails to close over the level in its last seconds, so no protected low prints ([[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 37:20).
- YM low-expectation day: target the failure swing (~49,280) to the right of the protected low (~49,190), not the protected low ([[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 43:40).
- 2022 advanced structure: AM's ES 1H marks LTH, ITL and MSB under a consolidation, then ITH/STH on the retracement before the sell-off ([[livestream_20220814_stream_q_a_with_am_trades_ict_concepts_cruftskoveo]] 29:50).

## Conflicts and open questions

- SW-1: Is a protected swing broken by a wick or by a close? Engine uses wick.
- SW-2: Valid separation has no number; the engine has no separation filter at all.
- SW-3: Relevance lookback: three HTF candles (about 63 daily bars on a daily chart) vs "about 30 daily candles".
- SW-4: Four different failure-swing definitions across eras.
- SW-5: After a protected swing is taken: invalidation (trend over) vs "run it out, then continue".
- SW-6: Which 50% must hold after a closure (leg, candle closed over, range)?
- SW-7: Must the move away leave an FVG for a protected swing?
- SW-8: Protected swing formed before the HTF candle open: positional entry vs suspect; engine ignores them.
- SW-9: When is a protected swing "too slow" to form; no number.
- SW-10: "Shallow sweep" wanted vs distrusted.
- SW-11: Failure swings: never trade away vs acceptable with SMT.
- SW-12: Equal lows acceptable (2024) vs never (2026).
- SW-13: What "hits liquidity" ends protection?
- SW-14: Targets: failure swings preferred vs engine's nearest untaken swing.
- SW-15: Relevant swing = any fractal vs only a C2/C3 closure at a POI.
- SW-16: Small candles inside the series.
- SW-17: MSS on short-term vs intermediate-term swing (superseded by CISD).
- SW-18: MSS by displacement vs close vs BOS (superseded).
- SW-19: Intermediate-term low defined four ways (superseded by protected swing).
- SW-20: Anticipated protected swing vs "no close, no protected swing".
- SW-21: Discretionary discount of a mechanically valid close.
- SW-22: Tie rule for swing points / what counts as "equal".
- SW-23: Stop exactly on the protected swing vs "a little room".

See `_merge/swings-and-structure/conflicts-fragment.md` for sides and status.

## Related

- [[cisd]]: the close through the opposing series is what creates a protected swing.
- [[candle-closures]]: C2/C3 closures are the swings worth framing; ideal when the closure also makes the protected swing.
- [[fractal-model]]: candle 2 is the swing candle; the model rests on "no reversal without a swing point".
- [[liquidity]]: swing points and failure swings are the resting liquidity and the targets.
- [[poi-and-pd-arrays]]: the sweep or FVG reach that precedes a protected swing.
- [[smt-and-psp]]: SMT protects a low/high and is the exception that lets him trade near failure swings.
- [[ranges-and-eq]]: the 0.5 of the leg or candle a protected swing must hold; consolidation between protected swings.
- [[entry-models]]: continuation entries off new protected swings, positional entries.
- [[risk-and-management]]: stop on the protected swing, trailing to new ones, breakeven.
- [[daily-bias]]: bias invalidation when the swing it relied on breaks; daily profile lows.
- [[ttfm-indicator]]: protected-swing dots, grey-out on break, settings.

## Questions this page answers

- What exactly is a swing high / swing low in TTrades' model, and how many candles does it need?
- What makes a protected swing, and when does it become valid (close vs wick, which candle prints it)?
- What is the difference between a relevant swing and a failure swing, and how is separation judged?
- How far back should relevant swings be marked?
- Can I trade away from equal lows or failure swings? What about with SMT?
- When is a protected swing no longer protected, and what does it mean when it is taken?
- Should failure swings or protected swings be used as targets?
- Is a protected swing formed before the HTF candle open usable?
- What did MSS, BOS and intermediate-term lows mean in his 2022-2024 teaching, and what replaced them?
- How does the companion engine define swings and protected swings, and where does it differ from the teacher?
- What must price hold after a protected swing forms (0.5 of what)?
- Why does he refuse a trade when "there is no swing to trade away from"?
