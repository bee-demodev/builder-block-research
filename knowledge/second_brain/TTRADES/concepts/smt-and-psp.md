---
id: smt-and-psp
title: "SMT divergence, PSP and relative strength"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [SMT, SMT divergence, smart money technique, smart money tool, divergence, crack in correlation, "Ken correlation", "Kraken correlation", "cracking correlation", PSP, precision swing point, "PHP", C2+PSP, C3+PSP, two-stage SMT, double SMT, reversal SMT, continuation SMT, structural SMT, SMT fill, inverse SMT, relative strength, relative weakness, asset strength, strongest asset, weakest asset, middle asset, leading asset, lagging asset, "which one is lying", triad, strength switch, fake SMT, SMT breaker, separation]
covers: [smt, psp, asset-strength, relative-strength, correlated-pairs, middle-asset, leading-lagging]
sources: [relative_strength_weakness_smt_divergence_full_guide, smt_divergence_ict_concepts, livestream_20260819_new_york_open_live_q_a_rvrk4mltjss, livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy, a_complete_trading_framework_universal_models_smt_swing_points_gxt, livestream_20261103_new_york_open_live_q_a_tqokgrazwky, livestream_20260325_new_york_open_live_q_a_aqny1yzvfys, the_best_relative_strength_indicator_for_es_nq_ict, smart_money_divergences_smt_ict_concepts, ttrades_top_down_chart_lessons_4, livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c, livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry, livestream_20260825_new_york_open_live_q_a_9h15zzvakpq, eurgbp_for_relative_strength_eu_vs_gu, livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds, a_simple_3_step_trading_model_full_breakdown, ttrades_fractal_model_trading_candle_4, trade_continuations_using_order_blocks, livestream_20260909_new_york_open_live_q_a_k7xvj2w3cp4, livestream_20261028_new_york_open_live_q_a_c4ti6kdxn0s, gxtradez_phases_of_price_profiles_for_expansion, livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]
confidence: medium
chain_step: ["3 setup", "4 entry", "asset selection"]
timeframe_role: [htf, setup, entry]
requires: [swings-and-structure, liquidity, daily-bias, fractal-model]
feeds: [cisd, entry-models, risk-and-management]
---

# SMT divergence, PSP and relative strength

## Definition

**Latest (2026).** SMT is "between correlated assets a difference in structure" at the same swing: at a low, the asset that makes the higher low is the stronger, the one that makes the lower low the weaker; mirrored at highs ([[relative_strength_weakness_smt_divergence_full_guide]] 00:41-01:11). Live he reduces it to "one asset's previous candle high/low was taken out and the other's wasn't" ([[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 46:40). It only counts at a relevant swing or level ([[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 10:40), it is confluence to a model that already exists ([[livestream_20260331_new_york_open_live_q_a_0aygnc9czyc]] 52:20), and it is confirmed by a CISD ([[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 38:40). He says it is needed for reversals and for trading away from unswept highs/lows, not for continuations ([[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:09:50; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 11:40). **PSP** (precision swing point) is the same higher-timeframe candle closing bullish on one asset and bearish on its correlated asset ([[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 34:40). His indicator prints it as "C2+PSP" / "C3+PSP", but he says he does not really use it ([[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 59:20). **Relative strength** is the larger use in 2026: rank the correlated assets, go long the strongest and short the weakest, never trade the lagging asset, and use the middle asset (usually ES) when strength keeps flipping ([[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 1:03:40; [[livestream_20260604_new_york_open_live_q_a_c7nk7ypjhn4]] 22:30).

**2025.** SMT becomes the stated exception that lets a level count as run without a sweep: order blocks, breakers, protected swings, consolidation lows and Candle 4 framing all accept "the correlated asset ran it" in place of a sweep ([[trade_continuations_using_order_blocks]] 01:58; [[protected_swings_understanding_trend_and_invalidations]] 00:55; [[how_to_trade_consolidation_phases_of_price]] 02:05). The guest GXT adds the triad, PSP, two-stage SMT/PSP and SMT fill ([[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 07:17-11:51). These are guest vocabulary; the teacher later puts PSP in his indicator.

**2023-2024.** Relative strength is read from swing points, candle closures and candle size ([[the_best_relative_strength_indicator_for_es_nq_ict]] 00:56). SMT is "a confluence to a reversal used to confirm a pre-existing idea or HTF level, not the reason" ([[smt_divergence_ict_concepts]] 02:37). In late 2024 it is "optional confluence" that "needs a CISD to confirm it" and "is never the source of bias" ([[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 45:20; [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 47:40).

**2022.** He calls it "divergence" ([[ict_index_futures_weekly_recap_week_of_5_16_22]] 03:30): ES and NQ disagree at a swing, which "only signals a possible reversal" ([[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 08:00). Short the weaker index and long the stronger ([[smart_money_divergences_smt_ict_concepts]] 02:09), or take whichever index has the cleaner setup ([[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 20:50).

## Rules

| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |
|---|---|---|---|
| **Definition and pairs** | | | |
| 1 | SMT = correlated assets that should share structure disagree at the same swing: one takes the high (low), the other makes a lower high (higher low). | stated | [[smart_money_divergences_smt_ict_concepts]] 00:36, 01:06; [[smt_divergence_ict_concepts]] 01:05; [[relative_strength_weakness_smt_divergence_full_guide]] 01:11 |
| 2 | Only compare assets that should move together (ES/NQ/YM, EU/GU, gold futures vs gold in other currencies). | stated | [[smt_divergence_ict_concepts]] 00:38; [[relative_strength_weakness_smt_divergence_full_guide]] 03:49 |
| 3 | For an inversely correlated pair (EURUSD vs DXY), expect mirrored structure; an inverse SMT is a higher high on one with a higher low (not lower low) on the other. | stated | [[smt_divergence_ict_concepts]] 12:18, 12:48 |
| 4 | Index SMT uses NQ, ES and YM together (the indicator's automatic pairs for NQ are ES and YM); mini contracts only, never micros. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 15:00; [[livestream_20260909_new_york_open_live_q_a_k7xvj2w3cp4]] 42:00; [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 29:05 |
| 5 | Gold SMT: GC with XAUEUR and XAUGBP intraday; silver as well, preferred on the higher timeframe. | stated | [[livestream_20261006_new_york_open_live_q_a_rtomj8urfnw]] 24:00; [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 37:50 |
| 6 | FX pairs: GBP with EUR, NZD with AUD, JPY alone, CAD alone; RTY is its own asset; USD pairs (e.g. USDCAD) use only DXY. | stated | [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 1:49:10; [[livestream_20260311_cpi_new_york_open_live_q_a_egv_gabtqks]] 47:20; [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 58:00 |
| 7 | (2026) Do not use the dollar to decide index trades; the DXY/index correlation "barely exists lately". | stated | [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 52:20; [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 41:10 |
| 8 | A one-asset FVG entry is also an SMT: one asset trades into (fills) the gap, the other does not reach it. | stated | [[smt_divergence_ict_concepts]] 15:30-16:25; [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 08:05 (guest) |
| 9 | An HTF wick low taken on one asset but not the other is a lower-timeframe SMT visible from the HTF chart. | demonstrated | [[smt_divergence_ict_concepts]] 03:38-04:34 |
| 10 | SMT works on any timeframe ("it is fractal"), and SMTs on several timeframes that agree reinforce the same strong/weak read. | stated | [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 44:40 (Q&A); [[relative_strength_weakness_smt_divergence_full_guide]] 09:40 |
| 11 | SMT can be read before the higher-timeframe candle closes. | stated | [[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 58:00 |
| **Where it counts** | | | |
| 12 | Ignore SMTs that are not at an HTF level or idea; they appear everywhere. Look for them at session highs/lows, previous-day highs/lows and HTF levels. | stated | [[smt_divergence_ict_concepts]] 04:34; [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 22:40 |
| 13 | The divergent asset must run out a relevant swing, not a minor one; prefer SMT off the external range high over an internal equal high. | stated | [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 10:40; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 43:00; [[ap_use_market_structure_fibonacci_levels_for_sniper_entries]] 33:13 (guest) |
| 14 | Ignore SMT inside consolidation; SMT is overused. | stated | [[livestream_20261028_new_york_open_live_q_a_c4ti6kdxn0s]] 31:40 |
| 15 | Equal highs/lows taken by only one asset (the other left them perfectly equal) are not trusted as SMT. | stated | [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 11:40; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 20:00; [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:14:00 |
| 16 | A 1m SMT is not enough to frame an idea; fading an extended overnight move needs a higher-timeframe swing-point SMT. | stated | [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 27:30; [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 11:00 |
| 17 | In-model SMT is looked for only after the C2/C3 closure; a structural SMT (between a swing and a key level such as PDL, outside the model's swing point) can be used before the model closes. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 36:20 |
| 18 | The indicator marks only reversal SMT (forms with the reversal, shown on the CISD) and continuation SMT (forms later, prints when the correlated asset takes the level); both together = double SMT. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 34:20; [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 1:10:20 |
| 19 | Swing-point SMT can sit between Candle 1 and Candle 2 (trade the Candle 3 continuation) or between Candle 2 and Candle 3 on a Candle 2 closure; extra confluence = SMT between C1's and C2's highs. | stated | [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 09:44 (guest); [[how_to_actually_trade_inversion_fair_value_gaps_ifvg]] 02:16 |
| **Role: confluence, not a model** | | | |
| 20 | Have the bias and the model first; SMT only confirms. Never build a trade around an SMT alone; remove it and the setup should still stand. | stated | [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 10:50; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 29:25; [[livestream_20260901_new_york_open_live_q_a_uw55tuk_ngy]] 50:50 |
| 21 | SMT never sets bias; on a bullish day a bearish SMT is ignored. | stated | [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 47:40; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 29:25 |
| 22 | SMT needs a CISD (or displacement in the expected direction) to confirm it; a small SMT without CISD is not a reversal signal. | stated | [[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 47:40; [[nickdoesfutures_unicorn_model_experiences_with_ict]] 14:51 (guest); [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 40:20; [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 54:05 |
| 23 | SMT alone means nothing; a reversal must still form in the area, and structure must align (no failure swings to trade away from). | stated | [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 25:00; [[livestream_20260721_new_york_open_live_q_a_m8xcjkoubhu]] 1:09:10 |
| 24 | PSP and SMT matter only when there is a valid fractal model; without one they are not confluence. | stated | [[livestream_20260803_new_york_open_live_q_a_nesscpmzwr0]] 59:30 |
| 25 | SMT is not required to take a trade; TTFM can be traded without SMT. | stated | [[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 45:20; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 1:11:40; [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 19:10 |
| 26 | SMT is required for reversals but not for continuations. | stated | [[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:09:50 |
| 27 | Do not short against unswept highs (or long against unswept lows) unless a correlated asset took its level; without SMT there is no counter-profile trade. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 11:40, 22:30; [[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 07:20; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 58:00 |
| 28 | Without SMT at a range extreme (HTF or LTF) he is not interested in the reversal from it. | stated | [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 18:50 |
| 29 | When trading a Candle 2 (reversal candle) he prefers SMT paired with it. | stated | [[easy_daily_bias_mechanical_framework]] 14:41 |
| 30 | If you trade reversals at all, demand more confirmation (e.g. double SMT). | stated | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 1:08:10 |
| 31 | For a reversal, a real sweep of the high is preferred over SMT. | stated | [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 1:48:50 |
| 32 | (2024) Once the SMT extreme forms at the expected reversal, expect it not to be touched; if the lagging asset later takes the same level, the SMT is cancelled. | stated | [[smt_divergence_ict_concepts]] 03:09, 05:38 |
| **SMT in place of a sweep** | | | |
| 33 | An opposing candle without a sweep or FVG tag still counts as an order block if the correlated asset swept (SMT). | stated | [[trade_continuations_using_order_blocks]] 01:58; [[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 16:40 |
| 34 | With SMT the low need not be taken: the up-close candles act as the breaker (the other asset formed the true breaker); this is more discretionary. | stated | [[trade_continuations_using_breaker_blocks]] 01:56-02:18 |
| 35 | With SMT the stronger asset need not make a new low: its old low becomes the protected low once price closes over the down-close series that formed the failure swing. | stated | [[protected_swings_understanding_trend_and_invalidations]] 00:55; [[ttrades_fractal_model_trading_candle_4]] 04:03; [[a_simple_3_step_trading_model_full_breakdown]] 39:58 |
| 36 | The only exception to needing a run of the range high/low (consolidation, retracement) is SMT: if the correlated asset ran it, treat it as run. | stated | [[how_to_trade_consolidation_phases_of_price]] 02:05; [[how_to_trade_retracement_phases_of_price]] 13:10 |
| 37 | A failure swing on one index with SMT on the correlated index is a tradeable manipulation, not a failure swing; without SMT you cannot trade away from an untaken failure swing. | stated | [[a_simple_3_step_trading_model_full_breakdown]] 09:54 (AM Trades); [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 16:52; [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 18:20 (Q&A) |
| 38 | A Candle 2 closure printed only on the correlated asset can frame the trade on the stronger asset. | stated | [[a_simple_3_step_trading_model_full_breakdown]] 41:29; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 50:40 |
| 39 | With SMT, the opposing candles at a high become a trustworthy stop reference; equal highs without SMT are not. | stated | [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 30:50 |
| 40 | Before price reaches the relevant high, treat a pullback as a retracement; do not anticipate a reversal there unless there is SMT. | stated | [[which_swing_highs_and_lows_matter_in_trading]] 09:07 |
| 41 | (2024) Step 1 of the reversal sequence (purge) is not needed when SMT is present. | stated | [[reversal_sequence_ttrs_how_to_blend_pd_arrays]] 05:28 |
| **Relative strength: measuring it** | | | |
| 42 | Judge relative strength with three tools: SMT, structure/separation, candle closures (his order varies, see SMT-6). | stated | [[relative_strength_weakness_smt_divergence_full_guide]] 00:26; [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 26:40; [[livestream_20260319_new_york_open_live_q_a_qv6ux_z8vra]] 20:50 |
| 43 | Without SMT (both made higher lows), compare separation from the prior extreme: more separation = stronger; use separation when neither asset has taken the reference low yet. | stated | [[relative_strength_weakness_smt_divergence_full_guide]] 02:11, 13:46 |
| 44 | Closures: the asset closing through its series (CISD) or over its previous candle is stronger than one closing a doji back inside; a big bearish closure is weaker than a bullish one. | stated | [[relative_strength_weakness_smt_divergence_full_guide]] 03:02; [[the_best_relative_strength_indicator_for_es_nq_ict]] 07:52 |
| 45 | Daily read: close vs open, who took the previous-day high, strongest close vs largest wick; largest wick / weakest close = weakest. | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 25:30 |
| 46 | Intraday read: the most recent hourly closures, the 4H candle vs its open (above = strong), or opposing 4H closures. | stated | [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 1:08:10; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 06:40; [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:15:20 |
| 47 | The index closest to (or through) its previous-day low is the weakest; a bullish reversal candle is weaker than a bullish expansion candle. | stated | [[ttrades_top_down_chart_lessons_4]] 0:53, 1:09 |
| 48 | Relative strength rotates (in consolidation, after a target is hit, at a higher low); re-rank after each move. | stated | [[relative_strength_weakness_smt_divergence_full_guide]] 11:13; [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 25:00; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 12:40 |
| 49 | Relative strength is a filter inside an HTF framework; never trade an asset only because it looks stronger. Bias first, then model, then the asset. | stated | [[relative_strength_weakness_smt_divergence_full_guide]] 15:26; [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 1:15:20 |
| **Relative strength: picking the asset** | | | |
| 50 | Long the strongest asset and short the weakest; never long the weakest or short the strongest. | stated | [[smart_money_divergences_smt_ict_concepts]] 02:09; [[relative_strength_weakness_smt_divergence_full_guide]] 00:20; [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 40:20 |
| 51 | Never trade the lagging asset hoping it will follow; prefer the leading asset or the middle one. | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 33:20; [[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 1:03:40; [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 13:00 |
| 52 | Leading/lagging = relative strength by direction: the weakest leads down, the strongest leads up. | stated | [[livestream_20261027_new_york_open_live_q_a_bjzpiunp8gc]] 32:50; [[livestream_20260909_new_york_open_live_q_a_k7xvj2w3cp4]] 21:00 |
| 53 | When strength keeps flipping between NQ and YM, or you cannot read it, trade ES, the middle asset. | stated | [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 25:20; [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 33:20; [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 39:30 |
| 54 | When one index trends up and another down, avoid the middle asset; it will chop. | stated | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 02:50 |
| 55 | Skip the strongest asset when it has already expanded over its highs; trade the middle asset that still has liquidity left (most range to target). | stated | [[ttrades_top_down_chart_lessons_4]] 2:27, 2:44; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 37:05 |
| 56 | Pick the asset closest to its target / draw (bearish day: the one nearest its PDL). | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 17:00; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 09:25 |
| 57 | Use YM mainly as a relative-strength and levels gauge; trade it only in the bias direction. | stated | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 20:40; [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 56:20 |
| 58 | FX: read the dollar first, then pair a weak currency against a strong one; with no clear weak vs strong there is no trade. EURGBP bullish = EUR stronger. | stated | [[livestream_20260325_new_york_open_live_q_a_aqny1yzvfys]] 06:30; [[eurgbp_for_relative_strength_eu_vs_gu]] 1:04-1:30 |
| **Relative strength: timing across assets** | | | |
| 59 | To long the strongest, wait for the weakest (or middle) asset to sweep a relevant low and reverse; that reversal is the SMT and the timing. | stated | [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 14:40; [[livestream_20260916_new_york_open_live_q_a_9yvbe_20hdg]] 11:30; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 07:05 |
| 60 | To short the weakest, the strongest asset must sweep/reverse off its level first; if the strongest will not reverse, you are probably wrong. | stated | [[livestream_20260311_cpi_new_york_open_live_q_a_egv_gabtqks]] 1:12:30; [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 37:00, 52:40; [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 15:45 |
| 61 | When the indices diverge, one is "lying" and will come back into alignment; wait for 5m/15m closures to see which. If both are lying, expect consolidation; if you cannot tell, it is chop. | stated | [[livestream_20261006_new_york_open_live_q_a_rtomj8urfnw]] 13:40; [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 54:50; [[livestream_20260826_ttrades_mnq_cup_afternoon_session_h1zqwwqdhka]] 14:00 |
| 62 | If the weakest asset continues through its low (fails to manipulate), the others usually follow to their equivalent lows; do not expect the follower to reverse first. | stated | [[livestream_20260729_new_york_open_live_q_a_xraklbjhw5k]] 41:20; [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 1:15:20; [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 10:10 |
| 63 | If the leading asset continues through its level, expect the next asset to reach its own equivalent level (trade the middle asset's catch-up, only around 09:30-10:00). | stated | [[livestream_20260605_new_york_open_live_q_a_x4xssv5cnqg]] 37:00; [[livestream_20260729_new_york_open_live_q_a_xraklbjhw5k]] 53:20, 1:01:20 |
| 64 | Ideal short open: the strongest index sweeps its high and reacts, the weakest pushes through its low, the middle one continues. | demonstrated | [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 14:50 |
| 65 | When the setup depends on another index's reversal, let that index's 15m candle close before acting on the traded index. | stated | [[ttrades_top_down_chart_lessons_4]] 3:21 |
| 66 | SMT formed before 10:00 is enough; the 09:30 SMT scalp (stop under the 09:30 low) is possible but sketchy and not his trade. | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 1:14:40; [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 33:40; [[livestream_20260909_new_york_open_live_q_a_k7xvj2w3cp4]] 18:30 (Q&A) |
| 67 | If the trade is too far from the level the strongest asset reversed from, skip it (no number given). | stated | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 37:00 |
| **Targets and management** | | | |
| 68 | A target can come from another asset: take profit on NQ when ES hits its level, because that creates SMT and price often leaves the level. | stated | [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 22:40; [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 42:40; [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 1:05:20 |
| 69 | The POI for the strongest index to reverse is the other indices reaching their targets. | stated | [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 29:20 |
| 70 | Once one asset has printed several expansion candles (or hit its target), it consolidates while the laggard catches up. | stated | [[livestream_20261020_new_york_open_live_q_a_vzhkq3c8xbi]] 43:20; [[livestream_20260910_new_york_open_live_q_a_wa9m30uhrm0]] 04:00 |
| 71 | On the 15m after an expansion, an index that has not made a new low while yours has (SMT) marks a potential bottom; expect the trailed protected swing to be hit. | demonstrated | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 33:20 |
| **PSP and guest extensions** | | | |
| 72 | PSP: the same HTF candle closes bullish on one asset and bearish on its correlated asset; indicator can compute it on Candle 1, Candle 2 or both and labels only "C2+PSP" on the chart. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 15:30, 34:40; [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 10:42 (guest, credits Trader Day) |
| 73 | (2026) He does not teach or really use PSP because he mostly trades continuations; at most extra confluence. | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 1:19:20; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 59:20; [[livestream_20261028_new_york_open_live_q_a_c4ti6kdxn0s]] 42:40 (Q&A) |
| 74 | [guest GXT] Pair SMT within a triad: DXY/EURUSD/GBPUSD, NQ/ES/YM, GC/XAUEUR/XAUGBP, CL/RB/HO. | stated | [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 07:17 |
| 75 | [guest GXT] Two-stage SMT (C1-C2 SMT then C2-C3 SMT) and two-stage PSP (SMT + PSP in either order) are strong reversal signatures; best = SMT at the key level, then PSP, then a crack at a swing point. | stated | [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 10:12, 11:16, 14:25 |
| 76 | [guest GXT] Continuation PSP: during expansion, one asset closes a retracement as a PSP and the other runs its extreme; any PSP against the open draw after the high/low of day is in is continuation, never reversal. | stated | [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 11:51, 27:54 |
| 77 | [guest GxTradez] A divergence is a fake SMT when the strongest asset fails to reverse; the lagging asset will then take the level. Expect a strength switch at most SMTs. | stated | [[gxtradez_phases_of_price_profiles_for_expansion]] 36:37, 39:19 |

## Engine notes

- The companion is single-symbol and SMT/PSP are not implemented. rules.md Q23 lists the three uses it loses: accepting order blocks without a sweep, preferring Candle 2 trades with SMT, picking the weaker symbol ([[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 15:00 for his pair config; rules.md §12 Q23).
- rules.md §3.12 says the SMT exception to order-block validity "is not implemented" (rule 33). The same gap applies to breakers (rule 34), protected swings without a new low (rule 35) and range runs (rule 36). rules.md §3.2/§3.15 build protected swings only from this symbol's own taken level. Inference: the engine rejects setups he takes on the non-sweeping asset.
- rules.md §7 stage c4 records "If I'm going to be trading a candle two, I do prefer to have SMT paired with it" as uncodable (rule 29). Inference: the 2026 rules 26-28 (SMT required for reversals and for trading away from unswept highs) are stronger than a preference, so the engine's reversal path (§7.1, a key level plus a CISD only) is more permissive than the 2026 teacher.
- rules.md §3.1 / Q12 accept any confirmed swing as a POI and do not filter failure swings. The teacher uses SMT as the thing that turns a failure swing into a tradeable one (rule 37). Inference: Q12 and Q23 interact; a failure-swing filter without SMT would reject the very setups SMT is meant to rescue.
- The engine's reversal key levels (previous candle, swing, FVG; rules.md §7.1) match where he wants SMT (PDH/PDL, HTF levels; rule 12), so a future SMT check could reuse `reversal_key_levels` (inference).
- Nothing in rules.md ranks symbols. Relative strength (rules 42-58) would be a new advisory layer. It needs at least two, ideally three, symbols, with daily, 4H and hourly closures (inference).
- No TD decision covers SMT; `decisions.md` has no rows yet.

## How it changed over time

- **2022 (ICT-concepts streams).** Named "divergence", ES vs NQ on the 15m; trade the weaker index short / stronger long, or the cleaner one; "only signals a possible reversal" ([[ict_index_futures_weekly_recap_week_of_5_16_22]] 03:30; [[livestream_20220724_stream_q_a_ict_concepts__ekue_pwime]] 31:20; [[livestream_20220807_stream_q_a_ict_concepts_h_xtsfk8np4]] 08:00, 20:50). Guest Ben: secondary confluence only ([[livestream_20220911_fractalizing_entries_q_a_with_ben_ict_concepts_yrmkkr4coju]] 45:40).
- **2023.** Relative-strength video adds closures and candle size, and calls an ES/NQ correlation flip "an SMT without an SMT" ([[the_best_relative_strength_indicator_for_es_nq_ict]] 00:56, 11:38). A 4h SMT supports the short bias ([[draw_on_liquidity_example_1_18_23_ict_concepts]] 00:36). Guests: AM Trades defaults to NQ and switches to ES on clear relative weakness ([[livestream_20230730_live_q_a_with_am_trades_weekly_profile_wgyde_h84cs]] 36:40); Rauf adds YM as the third leg and DXY first ([[livestream_20230924_live_with_day_trading_rauf_preparing_for_a_new_week_qftfd09vv3e]] 20:30).
- **2024.** The SMT video sets the frame: correlated only, confluence to an HTF idea, ignore SMTs away from levels, cancelled if the laggard takes the level, inverse and FVG variants ([[smt_divergence_ict_concepts]] 00:38-16:25). Late-2024 streams: optional, needs CISD, never bias ([[livestream_20241006_ttrades_sunday_session_live_q_a_r7yw6ou1lds]] 47:40). It is his "favourite reversal confluence" ([[reversal_sequence_ttrs_how_to_blend_pd_arrays]] 04:28).
- **2025.** SMT becomes the standard sweep substitute in the continuation playbooks ([[trade_continuations_using_order_blocks]] 01:58; [[trade_continuations_using_breaker_blocks]] 01:56; [[protected_swings_understanding_trend_and_invalidations]] 00:55; [[ttrades_fractal_model_trading_candle_4]] 12:25). Guests GXT and GxTradez introduce PSP, the triad, two-stage signatures, fake SMT and strength switch ([[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 07:17-14:25; [[gxtradez_phases_of_price_profiles_for_expansion]] 36:37). The top-down lessons formalise the middle asset ([[ttrades_top_down_chart_lessons_4]] 2:44).
- **2026.** The relative-strength full guide (SMT, separation, closures) ([[relative_strength_weakness_smt_divergence_full_guide]] 00:26). The New York Open streams make asset selection the main use: strongest/weakest, never the laggard, ES when unclear, "which one is lying" ([[livestream_20260428_new_york_open_live_q_a_x4srguziqwk]] 1:03:40; [[livestream_20261006_new_york_open_live_q_a_rtomj8urfnw]] 13:40). The indicator gets SMT and PSP ([[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 15:00-34:40). He also rejects SMT "hunting" more and more: no SMT in consolidation, none on equal highs, no 1m SMT, none without a model ([[livestream_20261028_new_york_open_live_q_a_c4ti6kdxn0s]] 31:40; [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 27:30). He also hardens it into a requirement for reversals ([[livestream_20261103_new_york_open_live_q_a_tqokgrazwky]] 1:09:50). He never says "I used to..." about SMT, so the 2024 "optional" and the 2026 "required for reversals" stand side by side (SMT-1).

## Examples

- NQ held higher lows while ES made lower lows; long the diverging NQ with the stop below its lows; invalid once those lows are taken ([[index_futures_weekly_recap_ict_concepts]] 07:10-07:17).
- 15m ES long: NQ swept a low and tapped an FVG, ES did neither; ES closes over its down-close series, protected low, 2R hit ([[a_simple_3_step_trading_model_full_breakdown]] 39:01-40:33).
- Bearish day: NQ took the PDH, ES/YM did not; SMT plus a bearish closure was enough to short, executed on ES to avoid whipsaw ([[livestream_20260603_new_york_open_live_q_a_u4j_fzd_fjk]] 26:20, 34:50).
- ES live scalp: NQ weakest took its PDL and reversed; YM had already expanded over its highs, so the long went on ES, the middle asset ([[ttrades_top_down_chart_lessons_4]] 0:35-2:58).
- Gold long out of a range only after silver ran the range low while gold held ([[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 33:20).
- EURUSD vs GBPUSD: EURGBP bearish, EURUSD the bearish daily close, so short EURUSD; EUR broke its low at 8:00, GBP at 9:00 ([[eurgbp_for_relative_strength_eu_vs_gu]] 10:34, 11:25).

## Conflicts and open questions

- SMT-1: Is SMT optional (2024, 2026 streams) or required for reversals / trading away from unswept highs (2026)?
- SMT-2: Which correlated timeframe and which signals rank strength, and in what order, when they disagree.
- SMT-3: What a "relevant" swing/level is for SMT to count (PDH/PDL, session, external vs internal).
- SMT-4: Middle asset (ES): default to trade vs avoid when indices trend apart.
- SMT-5: Which asset to trade after an SMT: weaker/diverging, cleaner, the one that swept, or the strongest/weakest by direction.
- SMT-6: Order of the three strength tools differs between videos.
- SMT-7: SMT cancelled when the laggard takes the level vs the laggard catching up as the trigger (guest).
- SMT-8: Sweep preferred over SMT vs SMT as favourite reversal confluence.
- SMT-9: Equal highs/lows with SMT: not trusted vs accepted once swept.
- SMT-10: SMT timeframe floor (any TF vs no 1m vs HTF swing-point for fades).
- SMT-11: SMT confirmed by CISD vs SMT + candle closure enough.
- SMT-12: PSP definition and status (guest/indicator vs "does not use").
- SMT-13: YM ignored (2024) vs default third leg (2025-2026).
- SMT-14: DXY for indices (guests 2023-24) vs ignored (2026).
- SMT-15: Silver for gold SMT: valid vs "not correlated enough".
- SMT-16: Guest "market cannot reverse without SMT" and "strength switch at most SMTs" vs teacher.
- SMT-17: "Too far away" and SMT timing windows (09:30 vs before 10:00) have no numbers.
- SMT-18: Engine has no sweep substitute (order block, breaker, protected swing, range run).
- SMT-19: Engine reversal path needs no SMT; 2026 teacher requires it for reversals.
- SMT-20: Failure-swing filter (Q12) and SMT rescue must be designed together.
- SMT-21: Mishearings ("Ken/Kraken correlation", "PHP", "GBV CAD", "SS(MT)").
- SMT-22: Speech vs chart (RTY gap SMT labelled "continuation PSP"; 2022 bearish speech, long trade).
- SMT-23: Reversal/continuation SMT split and the PSP "different colour, same structure" wording come from the 2026 SMT/PSP videos that are not in this corpus (seed playbook only).

## Related

- [[liquidity]]: SMT is a sweep on one asset and a failure to sweep on the other; it substitutes for a sweep.
- [[swings-and-structure]]: relevant vs failure swings, protected swings; SMT rescues failure swings.
- [[cisd]]: SMT is confirmed by a CISD; the reversal SMT is shown on the CISD.
- [[candle-closures]]: Candle 2 with SMT preferred; PSP is a closure-colour difference.
- [[fractal-model]]: in-model SMT after the C2/C3 closure.
- [[daily-bias]]: SMT never sets bias; bias first.
- [[entry-models]]: which asset to execute on; middle-asset catch-up trade.
- [[risk-and-management]]: SMT-backed opposing candles as stop; cross-asset targets.
- [[ttfm-indicator]]: SMT/PSP settings, automatic pairs, C2+PSP labels.
- [[sessions-and-time]]: 09:30 SMT, catch-up window 09:30-10:00.
- [[ranges-and-eq]]: no SMT inside consolidation; range extremes need SMT.

## Questions this page answers

- What is an SMT divergence and which assets does TTrades pair for it?
- Is SMT required for a TTFM trade, or only for reversals?
- Which index should I trade (NQ, ES or YM) once I have a bias?
- What is the "middle asset" and when should I trade or avoid it?
- What does "the lagging asset" or "which one is lying" mean?
- What is a PSP and does TTrades use it?
- When can SMT replace a sweep for an order block, breaker or protected swing?
- Which SMTs should be ignored (consolidation, equal highs, 1m, away from levels)?
- How do I rank relative strength without an SMT (separation, closures)?
- What is the difference between reversal, continuation, double and structural SMT?
- Does TTrades use DXY for index trades?
- What does the companion engine do with SMT today?
