---
id: liquidity
title: "Liquidity, sweeps and draw on liquidity"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [liquidity, buy-side liquidity, sell-side liquidity, BSL, SSL, buyside, sellside, draw on liquidity, DOL, liquidity sweep, sweep, stop raid, stop hunt, stop run, liquidity grab, liquidity run, turtle soup, Judas swing, inducement, relative equal highs, relative equal lows, equal highs, equal lows, EQH, EQL, failure swing, failure swings, low resistance liquidity, LRL, LRLR, high resistance liquidity, HRL, HRLR, internal range liquidity, IRL, external range liquidity, ERL, formation liquidity, low hanging fruit, "drawn liquidity", "cell side"]
covers: [liquidity, buy-side-sell-side, draw-on-liquidity, liquidity-sweep, stop-raid, failure-to-displace, relative-equal-highs-lows, failure-swing, low-resistance-liquidity, high-resistance-liquidity, internal-external-liquidity, inducement, turtle-soup, formation-liquidity]
sources: [what_is_liquidity_ict_concepts, liquidity_buyside_sellside_ict_concepts, which_swing_highs_and_lows_matter_in_trading, high_resistance_vs_low_resistance_liquidity_ict_concepts, low_resistance_liquidity_run_ict_concepts, internal_external_liquidity_daily_bias_ict_concepts, niper_internal_external_liquidity_ict_daily_bias, internal_external_liquidity_model_ict_concepts, trading_irl_erl_with_order_blocks_ict_concepts, draw_on_liquidity_dol_ict_concepts, why_your_continuations_fail_order_blocks_cisd_explained, market_structure_shift_vs_liquidity_grab_ict_concepts, structure_shift_vs_liquidity_grab_ict_concepts, scalping_made_simple_building_a_scalping_model, a_ict_entry_checklist_ict_concepts, the_easiest_draw_on_liquidity_dol_daily_bias_ict, important_liquidity_levels_draw_on_liquidity_ict, how_to_trade_reversal_phases_of_price, ict_silver_bullet_strategy_no_daily_bias_with_backtest, livestream_20260331_new_york_open_live_q_a_0aygnc9czyc, livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc, livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry, intro_to_ttrades_fractal_model_indicator_settings, jokerszn_daily_orderflow_ict_daily_bias]
confidence: medium
chain_step: ["1 bias", "3 setup", "5 manage"]
timeframe_role: [any]
requires: [swings-and-structure]
feeds: [daily-bias, poi-and-pd-arrays, candle-closures, cisd, smt-and-psp, entry-models, risk-and-management]
---

# Liquidity, sweeps and draw on liquidity

## Definition

**Latest (2025-2026).** Liquidity is the stops resting beyond swing highs and lows: "the market can only reverse with a swing point; a swing high/low is liquidity", and the important ones are the previous day high and low ([[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 24:50 qa). In TTFM liquidity does two jobs. As a **target**, the draw on liquidity is the failure swings: stacked or lined-up highs/lows not yet taken, which price runs easily ([[which_swing_highs_and_lows_matter_in_trading]] 08:17; [[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 36:20 qa; [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 1:10:50). As a **place to trade from**, only a relevant swing (the extreme of its cluster, with separation, inside a three-higher-timeframe-candle lookback) that gets swept and reversed in a V-shape counts ([[which_swing_highs_and_lows_matter_in_trading]] 01:12-03:29; [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 40:00). A sweep is "literally just a liquidity sweep" whatever it is called (turtle soup, inducement) ([[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 1:20:30 qa; [[livestream_20260311_cpi_new_york_open_live_q_a_egv_gabtqks]] 11:00 qa). The 2026 rule pair: trade toward failure swings, and keep high-resistance (already swept) liquidity on your stop side ([[protected_swings_understanding_trend_and_invalidations]] 14:45; [[which_swing_highs_and_lows_matter_in_trading]] 08:17).

**2023-2024 (ICT vocabulary, TTFM forming).** Buy-side liquidity = buy stops above swing highs, sell-side = sell stops below swing lows, with relatively equal highs/lows and old highs/lows as the obvious pools ([[liquidity_buyside_sellside_ict_concepts]] 01:07-05:00). Draws were split into external range liquidity (ERL: swing highs/lows) and internal range liquidity (IRL: FVGs), and price was said to alternate between them ([[internal_external_liquidity_daily_bias_ict_concepts]] 00:10-00:58; guest Niper: [[niper_internal_external_liquidity_ict_daily_bias]] 02:17). Low-resistance liquidity (LRL, failure swings) vs high-resistance liquidity (HRL, swept swings) named the target side and the stop side ([[low_resistance_liquidity_run_ict_concepts]] 00:37-01:07; [[high_resistance_vs_low_resistance_liquidity_ict_concepts]] 00:37-01:34). A liquidity grab was a failure to displace: reach over a level and close back in ([[market_structure_shift_vs_liquidity_grab_ict_concepts]] 01:02).

**2022 (ICT-concepts).** Liquidity = resting stops at the most obvious highs and lows; after one pool is taken, look for the setup the other way, toward the opposite pool or equal highs/lows ([[what_is_liquidity_ict_concepts]] 00:06-01:36). The 2022 mentorship model was liquidity grab, structure break with displacement, FVG; a run without displacement was a liquidity grab, not a shift ([[build_an_entry_model_ict_concepts]] 02:46; [[structure_shift_vs_liquidity_grab_ict_concepts]] 00:34).

## Rules

| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |
|---|---|---|---|
| **What liquidity is** | | | |
| 1 | Liquidity is resting stops at the most obvious highs and lows: buy-side above highs (shorts' stops), sell-side below lows (longs' stops). | stated | [[what_is_liquidity_ict_concepts]] 00:06-00:35; [[liquidity_buyside_sellside_ict_concepts]] 01:07; [[intro_to_market_structure_shifts_fair_value_gaps_and_displacement_ict_concepts]] 00:33 |
| 2 | Focus on the obvious highs and lows on the outside of the range: swing highs/lows, short-term highs/lows, relatively equal highs/lows, old highs/lows. | stated | [[ict_daily_bias]] 00:38; [[liquidity_buyside_sellside_ict_concepts]] 03:10-05:00 |
| 3 | Relatively equal highs/lows are two or more swing points close together (near-equal, not a perfect double top); treat them together as one pool and as a target. | stated | [[liquidity_buyside_sellside_ict_concepts]] 04:30; [[index_futures_weekly_recap_ict_concepts]] 04:16; [[price_targets_ict_concepts]] 01:46 |
| 4 | Once a high is taken it is no longer liquidity; the next swing high becomes the buy-side. | demonstrated | [[liquidity_buyside_sellside_ict_concepts]] 02:03 |
| 5 | The previous day, week and month highs/lows are always relevant liquidity levels; previous candle high/low = buy-side/sell-side. | stated | [[how_to_trade_reversal_phases_of_price]] 02:50; [[important_liquidity_levels_draw_on_liquidity_ict]] 00:38, 01:58; [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 24:50 (qa) |
| 6 | Session highs and lows (Asia, London, overnight) can be used as a draw and to frame a reversal. | stated | [[important_liquidity_levels_draw_on_liquidity_ict]] 06:33; [[liquidity_buyside_sellside_ict_concepts]] 08:34 |
| 7 | A higher-timeframe candle with no wick is an unestablished low: treat it as liquidity, not a level to trust. | stated | [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 07:30 |
| **Draw on liquidity (where price goes)** | | | |
| 8 | Unless price consolidates, expect it to reach for the previous candle's high, low, or both; ask which is more likely; the side it is moving toward is the likelier draw. | stated | [[ict_daily_bias_the_only_video_you_will_ever_need]] 00:38; [[intraday_bias_simplified_ict_concepts]] 00:36; [[the_easiest_draw_on_liquidity_dol_daily_bias_ict]] 00:10 |
| 9 | Decide where price is likely to reach on the HTF first, then use lower timeframes for entry and risk toward it. | stated | [[draw_on_liquidity_dol_ict_concepts]] 00:35 |
| 10 | (2023-2024) External draws are old/equal highs and lows; internal draws are FVGs (and order blocks, occasionally volume imbalances/gaps). | stated | [[draw_on_liquidity_dol_ict_concepts]] 00:35-01:02; [[internal_external_liquidity_daily_bias_ict_concepts]] 00:10-00:39; [[trading_irl_erl_with_order_blocks_ict_concepts]] 00:28-00:43 |
| 11 | Price only reaches for old highs/lows or rebalances an FVG; after ERL is taken it seeks IRL, after IRL it reaches for ERL. | stated | [[internal_external_liquidity_daily_bias_ict_concepts]] 00:39-00:58; [[niper_internal_external_liquidity_ict_daily_bias]] 02:17 (guest); [[trading_irl_erl_with_order_blocks_ict_concepts]] 00:55 |
| 12 | After a sweep of external liquidity that fails to displace through, expect a reach back to internal liquidity; once the FVG is respected, expect external next. | stated | [[internal_external_liquidity_model_ict_concepts]] 01:28; [[internal_external_liquidity_daily_bias_ict_concepts]] 01:28; [[inversion_fair_value_gaps_ifvg_ict_concepts]] 03:20 |
| 13 | IRL/ERL is fractal: a lower-timeframe swing closed through is itself ERL, so expect a retrace into a lower-timeframe FVG; it works on any timeframe. | stated | [[niper_internal_external_liquidity_ict_daily_bias]] 05:57 (guest); [[internal_external_liquidity_daily_bias_ict_concepts]] 10:04 |
| 14 | External liquidity on a zoomed-in range becomes internal when zoomed out; do not get caught up in labels. | stated | [[choosing_dealing_ranges_displacement_ranges_ict_concepts]] 00:33 |
| 15 | A daily close through equal highs (instead of a sweep that fails to close) makes the next higher draw likely. | stated (guest) | [[jokerszn_daily_orderflow_ict_daily_bias]] 03:03 |
| 16 | Several unswept previous-day highs above price make a short low probability; the resting buy-side may be run first. | stated (guest) | [[jokerszn_daily_orderflow_ict_daily_bias]] 38:06 |
| 17 | Always anchor an idea to a higher-timeframe draw on liquidity; never take a bias off a random FVG. | stated | [[livestream_20260616_new_york_open_live_q_a_tjuolmjncmy]] 28:10 |
| 18 | When the planned targets are done and there is no new draw on liquidity, do nothing. | stated | [[livestream_20260616_new_york_open_live_q_a_tjuolmjncmy]] 43:00 |
| 19 | If the daily move already happened before the open, either skip or trade only toward a remaining open draw (on the asset whose draw is still open), with lowered expectations. | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 16:40; [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 1:09:10 (note) |
| 20 | A reused order block is valid only while the draw is still untaken; after the objective is hit, re-entries get stopped. | stated | [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 09:10 (note) |
| **Failure swings, LRL and HRL** | | | |
| 21 | Low-resistance liquidity is a failure swing: a high/low not swept by the next leg (lower high beside a prior high, stacked higher lows), so liquidity still rests there. | stated | [[low_resistance_liquidity_run_ict_concepts]] 00:37; [[high_resistance_vs_low_resistance_liquidity_ict_concepts]] 00:37; [[cpi_gold_trade_review_ict_market_maker_sell_model_mmxm]] 01:38; [[ict_son_s_model_higher_time_frames]] 04:01 |
| 22 | High-resistance liquidity is a swing that was just swept (higher high / lower low) before the reversal; HRL lows are harder to break and are not targeted directly. | stated | [[high_resistance_vs_low_resistance_liquidity_ict_concepts]] 01:07; [[low_resistance_liquidity_run_ict_concepts]] 06:24 |
| 23 | A daily sweep becomes HRL once the next day closes back inside; use 0.5 of its wick as support. | demonstrated | [[high_resistance_vs_low_resistance_liquidity_ict_concepts]] 04:54; [[trade_like_ttrades_top_down_analysis]] 02:48-02:59 |
| 24 | Trade toward failure swings and keep HRL (swept swings, no failure swings) on the stop side. | stated | [[protected_swings_understanding_trend_and_invalidations]] 14:45; [[which_swing_highs_and_lows_matter_in_trading]] 08:17; [[cpi_gold_trade_review_ict_market_maker_sell_model_mmxm]] 01:45 |
| 25 | (2026) A failure swing is a set of lined-up highs/lows not yet taken out; it is structure, not a candle pattern. | stated | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 1:10:50; [[why_your_continuations_fail_order_blocks_cisd_explained]] 03:23 (def) |
| 26 | Never trade away from a failure swing or from equal/stacked lows; wait for the relevant (extreme) low to be taken. | stated | [[a_simple_3_step_trading_model_full_breakdown]] 2:13; [[which_swing_highs_and_lows_matter_in_trading]] 05:05; [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 50:30; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 07:10 |
| 27 | A reversal off a random high that leaves failure swings above is not trusted, even if the structure looks good. | stated | [[how_to_trade_reversal_phases_of_price]] 03:47; [[ttrades_top_down_chart_lessons_2]] 03:06-03:16; [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 1:22:10 |
| 28 | Equal highs right at the swing you would short from are a red flag; never put the stop just above them. | stated | [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 42:50; [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 29:40; [[livestream_20260826_ttrades_mnq_cup_afternoon_session_h1zqwwqdhka]] 47:00 |
| 29 | Clusters of failure swings are what gets run out (stop-outs before the move); target the relevant swing, not the failure swings next to it. | stated | [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 17:10; [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 31:20 |
| 30 | Equal highs / failure swings make the cleanest targets; on a weak-conviction day target the first failure swing (~1.5R). | stated | [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 16:00; [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:07:50, 1:12:50; [[ttrades_top_down_chart_lessons_4]] 0:27 |
| 31 | Lots of LRL ahead (lined-up session highs/lows, previous-day lows) is what makes the move after the CISD aggressive. | stated | [[ict_daily_profile_new_york_reversal]] 03:12; [[internal_external_liquidity_model_ict_concepts]] 07:50 |
| 32 | When overnight highs are already taken there is no LRL left: favour the daily open; the R:R is poor. | stated | [[ttrades_fractal_model_trading_candle_2]] 11:27 |
| 33 | A slightly swept previous-day low (equal lows nicked) is not a failure swing and loses target quality. | stated | [[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 31:40 (note) |
| **What counts as a sweep** | | | |
| 34 | A sweep (liquidity grab) is a failure to displace: price reaches over a level and closes back in; a sweep that does not close over the high is the better one. | stated | [[market_structure_shift_vs_liquidity_grab_ict_concepts]] 01:02; [[market_structure_shift_ict_concepts]] 03:33; [[structure_shift_vs_liquidity_grab_ict_concepts]] 00:34 |
| 35 | A stop hunt needs an aggressive move out of the range and an aggressive move back in; moving beyond an old low without returning is invalid and makes a new level to watch. | stated | [[scalping_made_simple_building_a_scalping_model]] 01:28, 01:57, 03:14 |
| 36 | A one-tick run below a low, or equal highs touched without running, is not a sweep. | stated | [[a_ict_entry_checklist_ict_concepts]] 07:19; [[ict_silver_bullet_strategy_no_daily_bias_with_backtest]] 09:57 |
| 37 | Very shallow sweeps (without displacement, FVGs, or a real reach) are low quality and do not make a trustworthy protected swing. | stated | [[ict_silver_bullet_strategy_no_daily_bias_with_backtest]] 26:37; [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 24:00; [[ict_advanced_market_structure_simplified]] 05:14 |
| 38 | He wants a clear swing swept, not a small one, and prefers a shallow sweep over a deep one. | stated | [[order_blocks_simplified_ict_concepts]] 04:56; [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 47:30 |
| 39 | A real sweep gives a V-shape reaction; a lethargic reaction is just part of a consolidation. | stated | [[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 40:00; [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 1:04:20 |
| 40 | A turtle soup over PDH without the close through the opposing candles (CISD) is not confirmed and can fail. | demonstrated | [[protected_swings_understanding_trend_and_invalidations]] 03:50; [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 36:40 |
| 41 | Mechanically, frame a daily reversal (candle 2) by requiring a sweep of the previous day's low (high); a daily close back inside a swept prior-month low makes a candle 2. | stated | [[livestream_20260729_new_york_open_live_q_a_xraklbjhw5k]] 06:00; [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 14:45 |
| 42 | An asset can print a C2 closure without sweeping its own extreme when the SMT partner swept it. | stated | [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 48:40 |
| 43 | If a low is taken without displacement below it (no close below, no FVG), expect price to go for the high. | stated | [[livestream_20230112_back_testing_live_session_fx_replay_8r6pxpeldiu]] 1:08:10; [[lower_time_frame_entries_using_htf_poi_ict_concepts]] 05:27; [[structure_shift_vs_liquidity_grab_ict_concepts]] 01:35 |
| 44 | A continuation through a swept high (instead of a reversal) is an expected phase-of-price outcome, not a failed sweep. | stated | [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 1:21:40 |
| 45 | A very aggressive move lower that leaves the highs unswept is usually fake; expect it to go higher. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 24:30 |
| **Sweeps in the trade sequence** | | | |
| 46 | When bullish, wait for lows to be taken (a stop raid opposite the draw) before the long that targets the highs; no sweep, no trade. | stated | [[index_futures_weekly_recap_ict_concepts]] 01:18; [[ict_index_futures_weekly_recap_week_of_5_16_22]] 01:05; [[ict_son_s_model_higher_time_frames]] 01:29; [[a_ict_entry_checklist_ict_concepts]] 00:10 |
| 47 | Without a lower-timeframe liquidity raid before the move he is not interested; he generally wants an LTF sweep inside the entry model. | stated | [[a_ict_entry_checklist_ict_concepts]] 08:23; [[change_in_state_of_delivery_cisd_orderblock_formation_ict_concepts]] 02:06; [[ict_silver_bullet_strategy_no_daily_bias_with_backtest]] 15:55 |
| 48 | To frame longs you need a sweep of a relevant low or an SMT at it; to short off highs you need a sweep of the high or SMT (a correlated asset taking its high). | stated | [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 1:32:40; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 11:40, 22:30 |
| 49 | For a reversal, prefer a sweep of the high over SMT. | stated | [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 1:48:50 |
| 50 | A sweep at the NY open is only wanted when no protected swing exists going into the open; with one, he does not want a sweep. | stated | [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 15:30 (qa) |
| 51 | Do not use a sweep of a low whose break would invalidate the HTF idea (e.g. a daily low expected to hold); use an FVG instead. | stated | [[trading_irl_erl_with_order_blocks_ict_concepts]] 06:38 |
| 52 | Sweeps of short-term highs/lows are often the manipulation that builds the higher-timeframe wick. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 14:10; [[gxtradez_phases_of_price_profiles_for_expansion]] 06:49 (guest) |
| 53 | When a continuation closure also takes range highs or significant buy/sell-side liquidity, that is where the opposite setup forms: wait for an extra continuation after the sweep. | stated | [[why_your_continuations_fail_order_blocks_cisd_explained]] 02:16, 13:36; [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 29:40 |
| 54 | Continuations fail when you enter after the short-term lows are already swept; enter early in the continuation. | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 24:10 |
| 55 | A protected swing is only protected until price hits liquidity; after significant liquidity is taken it can be re-swept before the trend continues. | stated | [[easy_daily_bias_mechanical_framework]] 08:21-08:35; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 57:50 |
| 56 | Do not trade a reversal away from the draw until those highs/lows are taken; do not trade away from a level after price already reached the opposing liquidity. | stated | [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 13:45; [[candle_3_closure_ttrades_fractal_model]] 06:47 |
| 57 | A C2 that expanded is tradable for C3 only while short-term liquidity remains open; if C2 already reached the draw, skip C3. | stated | [[trading_candle_3]] 08:57 |
| **Consolidations and ranges** | | | |
| 58 | Bullish out of a consolidation: want the range low run, then trade higher (accumulation, manipulation, distribution); bearish mirror. | stated | [[how_to_trade_consolidation_phases_of_price]] 01:39; [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 32:40 |
| 59 | When there are no lows/highs you can trust, trade it as a range: a sweep of the range high targets the range low (or the middle first). | stated | [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 22:40; [[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 06:40 |
| 60 | A closure out of a consolidation is often a liquidity sweep the other way; need one side swept and then a break of the other. | stated | [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 1:13:20 (note) |
| 61 | A broadening formation is a range swept on both sides during consolidation, before expansion away. | stated | [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 1:36:40 (qa) |
| **Lookback and marking** | | | |
| 62 | (2026) Swings count as relevant only inside a lookback of three higher-timeframe candles, the current one included (daily chart -> three months, hourly -> three days). | stated | [[which_swing_highs_and_lows_matter_in_trading]] 03:29, 10:32; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 1:12:20 (qa) |
| 63 | (2023, 2026 stream) For daily liquidity, look back three days and mark those highs and lows. | stated | [[the_easiest_draw_on_liquidity_dol_daily_bias_ict]] 04:29; [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 24:50 (note) |
| 64 | A low formed very close to the previous low lacks valid separation; do not trust a reversal from it until the nearby low is taken (no mechanical separation rule). | stated | [[which_swing_highs_and_lows_matter_in_trading]] 02:01, 08:49, 11:15 |
| 65 | Mark liquidity on the 15m (or hourly) at the 8:30 open by looking left, not on the 1m. | stated | [[index_futures_weekly_recap_ict_concepts]] 00:58; [[livestream_20220731_stream_q_a_ict_concepts_qgirecy2nz4]] 21:40 (note); [[livestream_20220904_q_a_live_with_alex_s_options_ict_strat_v8p6lniisvc]] 55:00 (qa) |
| 66 | The indicator's formation liquidity marks the untaken previous candle / previous day extreme the setup should draw to; taken levels are not marked. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 13:04-13:27 |
| **Older-era rules (kept for history)** | | | |
| 67 | (2022) Plot only previous week high/low, previous day high/low/close and the current day open. | stated | [[simple_day_trading_strategy_triple_s]] 00:29 |
| 68 | (2022) First check which liquidity was taken last: after sell-side expect distribution higher, after buy-side lower. | stated | [[ict_daily_bias]] 00:07 |
| 69 | (2022) Inducement = internal range liquidity (stops of early FVG longs, induced equal lows) run before the real move. | stated | [[intro_to_the_inducement_model_ict_concepts]] 01:35-02:34 |
| 70 | (2023) Silver Bullet: wait for a stop raid of one side of the 9 AM hourly range inside the window, then trade to the opposite side. | stated | [[ict_silver_bullet_strategy_no_daily_bias_with_backtest]] 00:38-01:37 |
| 71 | (2024, guest) Order pairing: the market raids sell stops below an old low then pairs them with buy stops above the range high; this defines the draw. | stated | [[the_ote_trader_i_turned_profitable_with_this_stage_of_ict_s_mmxm_models]] 04:09 |

## Engine notes

- **Sweep vs level taken.** `rules.md` 3.2 separates "level taken" (`bar.low < level`, no close) from "sweep" (taken and closed back within `sweep_reclaim_max_bars`, proposal 0 on the bias timeframe, 3 on setup/entry). The teacher adds quality conditions the engine does not test: not one tick (rule 36), not shallow (rule 37), a V-shape reaction (rule 39), and a relevant swing (rules 26, 64) (inference; `companion/styles/ttrades/rules.md` 3.2).
- **Swings and relevance.** 3.1 defines a swing with one bar each side and strict inequality, and does not filter failure swings or separation (open question 12). The teacher's core 2026 point (never trade away from a failure swing, rule 26) is therefore not encoded; a POI of kind (a) is any untaken swing inside the lookback (3.14).
- **Lookback.** 3.1 applies the three-higher-timeframe-candle rule (rule 62); `bias_poi_lookback_bars` is 1D -> 3 months (~66 bars), his own numbers for the daily. The 2023 / Sep-2026 "three days" read for daily liquidity (rule 63) is not used (section 11).
- **Liquidity as target is information only.** Exits are a fixed R multiple (`target_rr` 2.0); structural levels S1 (previous bias candle extreme) and S2 (nearest untaken bias-timeframe swing) are drawn and reported in R but never the exit (8.3). No IRL->ERL target logic and no "draw already reached" gate other than the advisory `cont_objective_open` (rules 11-12, 18-20; inference).
- **Reversal key levels** are previous bias candle extreme, untaken bias swings and unfilled bias FVGs, reached within 10% of average range (7.1, open question 29). Session highs/lows (rule 6) are drawn as `session` markup only (10.6).
- **Sweep during the trigger.** `cont_trigger_clear_of_liquidity` (quality) blocks a continuation trigger that formed while running short-term highs, matching rule 53 (6 stage c4). The re-sweep caveat of rule 55 is listed as a downgrade (9.3).
- **Not modelled:** SMT as a sweep substitute (rules 42, 48; open question 23), HRL/LRL classification of the stop side (rule 24), equal-high red flags at the stop (rule 28), the indicator's formation liquidity (rule 66).

## How it changed over time

- **2022.** Liquidity = obvious stops; the 2022 mentorship model (liquidity grab, displacement shift, FVG) and inducement ([[what_is_liquidity_ict_concepts]] 00:06; [[intro_to_the_inducement_model_ict_concepts]] 02:34; [[build_an_entry_model_ict_concepts]] 02:46). Fixed plotted levels in the "Triple S" videos ([[simple_day_trading_strategy_triple_s]] 00:29).
- **2023.** BSL/SSL, relatively equal vs old highs/lows ([[liquidity_buyside_sellside_ict_concepts]] 01:07-05:00); draw on liquidity as daily bias ([[the_easiest_draw_on_liquidity_dol_daily_bias_ict]] 00:10); LRL/HRL introduced ([[low_resistance_liquidity_run_ict_concepts]] 00:37); IRL/ERL ([[internal_external_liquidity_daily_bias_ict_concepts]] 00:10); stop-hunt validity tests ([[scalping_made_simple_building_a_scalping_model]] 01:28).
- **2024.** IRL/ERL repeated by guests (Niper, Joker) and in his own model videos ([[niper_internal_external_liquidity_ict_daily_bias]] 01:56; [[trading_irl_erl_with_order_blocks_ict_concepts]] 00:55); LRL/HRL re-taught as target vs stop side ([[high_resistance_vs_low_resistance_liquidity_ict_concepts]] 00:37-01:34); formation liquidity in the TTFM indicator ([[intro_to_ttrades_fractal_model_indicator_settings]] 13:04).
- **2025.** The vocabulary moves to "failure swings" vs "protected swings": trade toward failure swings, stop on protected swings ([[protected_swings_understanding_trend_and_invalidations]] 14:45); relevant swings, previous day/week extremes ([[how_to_trade_reversal_phases_of_price]] 02:50).
- **2026.** "Which swing highs and lows matter": relevant swings, three-HTF-candle lookback, valid separation without a number ([[which_swing_highs_and_lows_matter_in_trading]] 01:12-11:15); sweeps judged by V-shape and SMT; "turtle soup is literally just a liquidity sweep" ([[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 1:20:30 qa); continuations that sweep liquidity fail ([[why_your_continuations_fail_order_blocks_cisd_explained]] 13:36).

## Examples

- PDH taken but no daily close over it: order flow turns bearish toward sell-side ([[low_resistance_liquidity_run_ict_concepts]] 04:56).
- Daily PDL sweep that closes above 50% of its wick becomes HRL; next day targets the lined-up highs / FVG ([[high_resistance_vs_low_resistance_liquidity_ict_concepts]] 04:54, 07:26).
- Silver Bullet: 9 AM hourly range raided inside the window, entry the other way to the opposite side ([[ict_silver_bullet_strategy_no_daily_bias_with_backtest]] 01:37).
- ES already swept its draw, YM had not: he trades YM, whose target is still open ([[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 1:09:10).
- YM equal highs left as failure swings make the target for the move down ([[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 36:20).
- Equal highs below a previous high on ES are failure swings to be run toward the previous high, so no stop just above them ([[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 29:40).

## Conflicts and open questions

From [[_merge/liquidity/conflicts-fragment]]:

- **LIQ-1** Sweep validity has no number: how far beyond, how fast back, wick vs close.
- **LIQ-2** Relevant swing separation and failure-swing detection have no rule.
- **LIQ-3** Lookback: three HTF candles (daily -> 3 months) vs three days on the daily.
- **LIQ-4** Same-bar close back vs a later CISD as the sweep confirmation.
- **LIQ-5** Equal highs: target, red flag at the stop, or "not counted" when only touched.
- **LIQ-6** Which pool is the draw when several are open (nearest, LRL, PDH/PDL, HTF)?
- **LIQ-7** IRL/ERL alternation (2023-2024) vs the 2026 failure-swing framing.
- **LIQ-8** Is a sweep required before every entry, or not when a protected swing exists?
- **LIQ-9** SMT as a substitute for a sweep vs "prefer the sweep over SMT".
- **LIQ-10** Liquidity target vs fixed 2R exit.
- **LIQ-11** Close through a level: breakout continuation or failed sweep / consolidation?
- **LIQ-12** Shallow sweep preferred (2026) vs "a shallow sweep is sketchy / low quality".
- **LIQ-13** Session highs/lows as key levels: teacher yes, engine reversal levels no.
- **LIQ-14** Is HRL a target or stop side only?
- **LIQ-15** "Liquidity sweep around EQ" vs EQ as an invalidation line.
- **LIQ-16** Niper 02:17 misspeak on IRL/ERL direction.
- **LIQ-17** Formation liquidity: previous candle or previous day when both are untaken.
- **LIQ-18** Inducement / turtle soup / stop hunt / liquidity grab: one concept or several.
- **LIQ-19** When a protected swing stops being protected after liquidity is hit (re-sweep rule).
- **LIQ-20** Displacement test (2022) vs CISD close-through (TTFM) for telling a sweep from a shift.

## Related

- [[swings-and-structure]]: swing points, relevant vs failure swings, protected swings.
- [[daily-bias]]: draw on liquidity as the 2023 bias; PDH/PDL closures as the 2025-2026 bias.
- [[poi-and-pd-arrays]]: FVG as internal liquidity and as POI; swept swing as POI kind (a).
- [[candle-closures]]: the sweep-and-close-back that makes a candle 2.
- [[cisd]]: the close through the series that confirms a sweep.
- [[smt-and-psp]]: SMT as the cross-asset form of a sweep.
- [[ranges-and-eq]]: consolidation ranges, sweeps around EQ, broadening formations.
- [[risk-and-management]]: failure swings as targets, HRL as the stop side.
- [[ttfm-indicator]]: formation liquidity lines, previous-candle high/low marks.

## Questions this page answers

- What is buy-side and sell-side liquidity in TTrades' terms?
- What counts as a valid liquidity sweep, and what does not (one tick, touched equal highs, shallow)?
- What is a failure swing and why does he never trade away from one?
- What are low-resistance and high-resistance liquidity and how are they used for targets and stops?
- How does internal vs external range liquidity work, and is it still part of TTFM?
- How far back should I look for relevant highs and lows?
- Do I need a sweep before every entry?
- Can SMT replace a sweep?
- What is the draw on liquidity when several levels are open?
- Is turtle soup or inducement different from a liquidity sweep?
- Why does a continuation that sweeps highs often fail?
- What does the companion engine do with liquidity, and what does it leave out?
