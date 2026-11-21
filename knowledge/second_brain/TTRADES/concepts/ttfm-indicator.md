---
id: ttfm-indicator
title: "The TTFM indicator and charting tools"
type: ttrades-concept
created: 2026-11-21
last_updated: 2026-11-21
aliases: [TTFM indicator, TTrades fractal model indicator, TTFM Pro, "TTFM [Pro+]", fractal model indicator, his indicator, indicator.ttrades.com, T-spot, t-pot, te-spot, tpot, gray box, green box, XC2, C2+PSP, auto bias, Auto Bias 1, Auto Bias 2, early C2, early CISD, show early C2 CISD, formation liquidity, candle 1 sweep, candle equilibrium, HTF candles, power of three indicator, PO3, HTF PO3, offset 17, indicator template, quiz template, "two degrees", "from 2 degrees"]
covers: [ttfm-indicator, t-spot, indicator-labels, indicator-settings, auto-bias, early-cisd-setting, formation-liquidity, htf-candle-overlay, indicator-templates, indicator-alerts, charting-tools, data-feeds]
sources: [intro_to_ttrades_fractal_model_indicator_settings, livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy, livestream_20260826_ttrades_mnq_cup_afternoon_session_h1zqwwqdhka, livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry, livestream_20260819_new_york_open_live_q_a_rvrk4mltjss, livestream_20260727_new_york_open_live_q_a_je7cd9hjube, livestream_20260728_new_york_open_live_q_a_yngx9oaefui, livestream_20260313_new_york_open_live_q_a_bmkromkeunu, livestream_20260825_new_york_open_live_q_a_9h15zzvakpq, livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c, livestream_20260318_new_york_open_live_q_a_yud7tpe2ams, livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi, livestream_20260923_new_york_open_live_q_a_kbjaggkxdei, livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg, livestream_20261007_new_york_open_live_q_a_mflp3acpzc0, cisd_validates_swing_points, candle_2_closure_foundation, easy_daily_bias_mechanical_framework, ttrades_fractal_model_trading_candle_2, wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles, livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc, livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]
confidence: medium
chain_step: ["1 bias", "3 setup", "4 entry", "5 manage"]
timeframe_role: [any]
requires: [fractal-model, candle-closures, cisd, swings-and-structure, ranges-and-eq, smt-and-psp]
feeds: [entry-models, risk-and-management, psychology-and-process]
---

# The TTFM indicator and charting tools

## Definition

**2026 (current).** The TTrades Fractal Model indicator (TTFM, sold as "TTFM Pro" / "TTFM [Pro+]", TradingView only, at indicator.ttrades.com) marks his model mechanically on one higher/lower timeframe pair. It draws the HTF candles to the right of the chart, the candle 2 / 3 / 4 labels, the CISD line, protected swings, the T-spot box, candle EQ, candle 1 sweep, formation liquidity (targets) and SMT/PSP [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 1:02:10, [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 04:20-15:30. A setup prints only if it qualifies as a fractal setup: a candle closure plus a CISD [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 22:20. The rest of the logic (T-spot, EQ) prints only once both are met [[cisd_validates_swing_points]] 5:18. It gives no buy/sell signals, stops or targets and has no win rate. It "only marks out his model", and a printed model is not automatically one to take [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 42:40, [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 26:00 (qa). The **T-spot** is the box inside the next HTF candle where he expects the HTF wick to form before price trades away. Gray is for a bearish wick (a high), green for a bullish wick (a low to be held) [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 39:40, [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 32:30 (qa). An **X** prefix (XC2) marks a model that formed and then failed. The indicator does not repaint, so failed models and taken protected swings stay on the chart, grayed or crossed [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 45:20 (qa), [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 42:40 (qa). He says the indicator is not needed: he marked everything by hand for about a year, and the tool only saves effort [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 32:10 (qa).

**2024-2025 (first release).** The indicator was introduced in a settings walkthrough [[intro_to_ttrades_fractal_model_indicator_settings]] 03:17-13:55. At that point validity used a colour code: gray C2 = valid through candle 4, red = failed in the first candle after, orange = failed in the second. There were time filters (kill zones) applied to whole HTF candles, and projections drawn from the CISD bodies [[intro_to_ttrades_fractal_model_indicator_settings]] 06:50, 07:58, 11:44. 2025 videos call the T-spot the zone "where the higher-timeframe candle's wick should form" [[how_to_trade_retracement_phases_of_price]] 5:28. In some examples it is "just the equilibrium" [[easy_daily_bias_mechanical_framework]] 06:07. An "early CISD" mode prints the CISD one candle earlier [[ttrades_fractal_model_trading_candle_2]] 04:41.

**2022-2023 (before TTFM).** No own indicator. He used third-party tools: an ATR trailing stop and an ICT sessions indicator [[livestream_20220821_8_14_22_mmxm_live_with_niper_ict_concepts_umlwrlxd_v8]] 32:30 (qa), later "no indicators, sometimes volume" [[livestream_20230204_live_q_a_review_with_am_trades_xcvqikdea9w]] 59:30 (qa). He also used a Power of Three (PO3 Pro+) HTF-candle overlay and an edited ICT Killzones & Pivots indicator [[livestream_20230924_live_with_day_trading_rauf_preparing_for_a_new_week_qftfd09vv3e]] 37:00 (qa), and an ES/NQ ratio chart for relative strength [[the_best_relative_strength_indicator_for_es_nq_ict]] 04:22. A 2023 scalping video already says defined rules "can be coded into an indicator" [[scalping_made_simple_building_a_scalping_model]] 04:26.

## Rules

| # | Rule (operational, one sentence) | Conf. | Source (slug, time) |
|---|---|---|---|
| **What it is and is not** | | | |
| 1 | The indicator marks candle closures, CISD, SMT, EQ and targets on top of a power-of-three HTF candle tool. | stated | [[livestream_20260617_new_york_open_live_q_a_with_nickdoesfutures_tdiwwmrwf2k]] 1:02:10 (qa); [[candle_2_closure_foundation]] 09:19 |
| 2 | A setup prints only when it qualifies as a fractal setup: a HTF candle closure plus a CISD. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 22:20 |
| 3 | The remaining logic (T-spot, EQ) prints only once both requirements are met. | stated | [[cisd_validates_swing_points]] 5:18 |
| 4 | It gives no entries, signals, stops or targets and has no win rate; results depend on execution, R:R and sizing. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 42:40; [[livestream_20260401_new_york_open_live_q_a_wbwoimdxt2c]] 26:00 (qa); [[livestream_20261028_new_york_open_live_q_a_c4ti6kdxn0s]] 34:00 (qa) |
| 5 | A printed model is not a trade: set the HTF bias first, then use the indicator on the lower timeframe to chart the structure. | stated | [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 31:30 (qa); [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 1:01:20 |
| 6 | Do not pattern-trade the indicator: every pattern must align with the HTF bias / draw. | stated | [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 2:17:30 (qa); [[livestream_20260317_new_york_open_live_q_a_00izxpadr5a]] 35:00 (qa) |
| 7 | You do not need the indicator to trade the model; he marked C2, wick 0.5 and targets by hand for about a year. | stated | [[livestream_20260318_new_york_open_live_q_a_yud7tpe2ams]] 32:10 (qa); [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 35:30 (qa) |
| 8 | The indicator is kept deliberately clean: no C1-C4 labels on the HTF candles and no HTF FVGs; C1 is not marked (it is just liquidity). | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 1:13:20, 52:50 |
| 9 | Phases of price will not be coded into it. | stated | [[livestream_20260910_new_york_open_live_q_a_wa9m30uhrm0]] 28:20 (qa) |
| **Labels and drawings** | | | |
| 10 | Labels run C2, then C3, and C4 for continuation when the closure is good; the model is fractal on every timeframe. | stated | [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 1:23:30 (qa); [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 21:30 (qa) |
| 11 | XC2 = a C2 closure that formed and was then taken out; failed models stay on the chart because it never repaints. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 45:20 (qa); [[livestream_20261111_new_york_open_live_q_a_mk9qoez3qzi]] 42:40 (qa) |
| 12 | (2024) Validity colours: gray C2 = valid through candle 4; red = failed in the first candle after; orange = failed in the second. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 06:50 |
| 13 | T-spot = the zone inside the next HTF candle where the HTF wick should form; for a short, price trades into the gray box, forms a high, then trades lower. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 03:17; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 13:20 (qa) |
| 14 | T-spot colours: gray for continuations lower (a high), green for continuations higher (a low to be held). | stated | [[livestream_20260313_new_york_open_live_q_a_bmkromkeunu]] 32:30 (qa); [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 39:40 |
| 15 | The T-spot prints in the third and fourth candle, not after that. | stated | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 21:40 (qa) |
| 16 | In replay the T-spot prints one minute into the candle with an FVG in it, then the continuation prints on its own. | demonstrated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 1:08:20 (qa) |
| 17 | The T-spot area is 0.5 of the wick (marked by the indicator) together with a CISD; that is where the 15m wick should form for a continuation. | stated | [[livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg]] 27:40 (qa) |
| 18 | For continuation lower, price should hold / not close over the T-spot area; a close over the hold level turns it red as an early warning. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 18:23, 15:53 |
| 19 | The gray boxes are also where he decides what counts as a small wick. | stated | [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 1:20:50 (qa) |
| 20 | Protected swings form on the closure through, print on the next candle's open as a dot plus a line, and keep forming as price continues (trail-stop use). | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 04:20 |
| 21 | Protected swings never repaint: a taken one turns gray and a new line forms. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 25:00 |
| 22 | With an early CISD the low becomes protected only if the candle actually closes over the level. | demonstrated | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 37:20 |
| 23 | A 3m swing with no FVG is not shown as protected; you may still choose to treat it as protected. | stated | [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 49:10 (qa) |
| 24 | Continuation labels show only for continuations that form in an FVG, and only for a limited time after the model; late ones are not marked. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 43:40, 27:20 |
| 25 | Candle 1 sweep = line at the candle 1 extreme swept by the HTF closure; candle EQ = midpoint of the HTF candle, drawn on HTF and LTF. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 10:29, 11:05 |
| 26 | Formation liquidity = the untaken previous candle / previous day low (bearish) or high (bullish) the setup should draw to; taken lows are not marked. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 13:04 |
| 27 | Projections are standard-deviation targets drawn from the CISD bodies (or wicks); defaults -1, -2, -2.5...; off by default and he keeps them off. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 11:44; [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 46:40; [[targets_using_projections_the_fractal_model]] 08:14 |
| 28 | Vertical open/close lines separating each HTF candle are "very important" to his analysis. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 09:41 |
| 29 | SMT is drawn automatically, only at the model's own spots: a reversal SMT on the CISD and a continuation SMT that prints live; discretionary SMTs are not marked. | stated | [[livestream_20260728_new_york_open_live_q_a_yngx9oaefui]] 58:00, 1:10:20 (qa); [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 34:20 |
| 30 | PSP (HTF candle closes opposite colours on correlated assets) shows as "C2+PSP"; it is in the indicator because people asked, and he does not really use it. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 15:30, 34:40; [[livestream_20261028_new_york_open_live_q_a_c4ti6kdxn0s]] 42:40 (qa) |
| 31 | An OB line printed by the indicator is also an OB once price closes over it. | stated | [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 25:00 (qa) |
| **Settings** | | | |
| 32 | His settings are default except "show early C2 / early CISD" turned on (and the colour). | stated | [[livestream_20260902_new_york_open_live_q_a_grc5fvb5tdg]] 10:30 (qa); [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 28:40 (qa); [[livestream_20260429_new_york_open_live_q_a_n3ml_r0x30o]] 28:40 (qa) |
| 33 | Early C2 CISD (off by default) shows the CISD before the HTF close as a dotted line that turns solid on the closure; continuations also show dotted first. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 11:40; [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 46:10 (qa) |
| 34 | Early C2 is off by default because learners should not trade C2; with it off nothing prints until the HTF candle closes. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 25:40, 04:00; [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 1:52:40 (qa) |
| 35 | Fractal: Automatic picks the HTF from the chart timeframe (1H -> daily, 15m -> 4H, 5m -> 1H); a fixed pair stays the same on any chart; Custom allows pairs such as 7H-15m. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 06:20, 49:10; [[intro_to_ttrades_fractal_model_indicator_settings]] 04:11 |
| 36 | Very low timeframes: 30s entries pair with 10m (not 3m), 15s with 5m. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 49:10 |
| 37 | A model shows nothing on a chart timeframe above its LTF; keep warnings on to see why. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 05:07 |
| 38 | Lock the fractal (e.g. hourly-5m) so the model stays the same when dropping to 1m. | stated | [[ttrades_fractal_model_inversion_intraday_strategy]] 03:57; [[livestream_20260506_new_york_open_live_q_a_eipm_d8rrsq]] 32:10 (qa) |
| 39 | Bias filter: Neutral shows both sides, Bullish/Bearish one side, Auto Bias 1 only setups aligned with the model one fractal up, Auto Bias 2 two fractals up. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 07:30; [[intro_to_ttrades_fractal_model_indicator_settings]] 07:06 |
| 40 | He leaves bias on Neutral to see all swings and decide himself; the table's "Bias: Neutral" shows the setting, not a market read. | stated | [[livestream_20260826_ttrades_mnq_cup_afternoon_session_h1zqwwqdhka]] 44:00 (qa); [[livestream_20260610_new_york_open_live_q_a_w7fu3rx5ims]] 1:19:40 |
| 41 | When Auto Bias 1 and 2 disagree, decide your own bias instead of letting the indicator decide. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 1:04:40 |
| 42 | HTF candles: count 4 (minimum, his model needs it), size small/medium/large, offset to place two copies side by side. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 08:20 |
| 43 | Two HTF sets: copy/paste the indicator, lock the copy to the daily, offset 17, and remove its model (C2/C3/C4). | demonstrated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 09:20, 1:00:50 (qa); [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 20:20 (qa) |
| 44 | History = how many past models stay on the chart; 0 while trading, 1 in his template. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 05:55 |
| 45 | (2024) Time filters (up to 3 kill zones) snap to whole HTF candles and apply only at or below the "Apply below" timeframe. | stated | [[intro_to_ttrades_fractal_model_indicator_settings]] 07:58, 12:33 |
| 46 | (2026) A session filter can restrict printed setups (e.g. New York only); he no longer uses kill zones. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 16:00; [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 1:02:50 (qa) |
| 47 | SMT pairs: Automatic (NQ vs ES and YM) or Custom with an optional second pair and an Inverse flag (e.g. dollar vs euro). | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 15:00; [[livestream_20261006_new_york_open_live_q_a_rtomj8urfnw]] 23:50 (qa) |
| 48 | On stocks turn protected swings off (messy) and prefer higher timeframes. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 47:30 |
| 49 | Calculation bars sets how far back the script computes; about 2,000, lower if slow. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 16:20 |
| **Templates, alerts, workflow** | | | |
| 50 | Save indicator templates (his "all", "clean", "daily-4H-15m"); templates do not update with the script and must be re-saved after an update. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 02:50, 25:00 (qa); [[livestream_20260505_new_york_open_live_q_a_i2hhhhwdapq]] 1:03:20 (qa) |
| 51 | Create the alert on the entry timeframe of the pair (hourly chart for daily closures, 15m for 4H) and add it to the whole watchlist. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 26:20; [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 11:00 (qa) |
| 52 | Use the indicator's alerts instead of scanning every pair, then check the most interesting ones. | stated | [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 46:30 (qa) |
| 53 | Learning: make a "quiz" template with all fractals off, mark C2, CISD, T-spot and C1 high yourself, then switch to the normal template to check. | stated | [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 43:20 (qa); [[livestream_20260825_new_york_open_live_q_a_9h15zzvakpq]] 1:16:40 (qa) |
| 54 | Learners trade only C3/C4 after a valid model prints; C2 comes later. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 53:10 |
| 55 | He prefers the confirmed continuation to an early CISD and takes early CISDs only with very strong bias. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 1:08:50 |
| 56 | A counter-HTF LTF setup printing inside a HTF setup tends to fail right away. | demonstrated | [[intro_to_ttrades_fractal_model_indicator_settings]] 15:31 |
| 57 | When the indicator shows nothing because there was no sweep, SMT can still let you treat the candle as a C2 / reversal candle. | stated | [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 50:40 (qa) |
| **Charting environment** | | | |
| 58 | Use the 18:00 daily open (data-feed open), not true day open or midnight; the indicator uses the feed's open automatically. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 1:30:10; [[livestream_20260310_new_york_open_live_q_a_wm1s7uivq08]] 46:30 (qa) |
| 59 | Chart futures with back-adjust (B-ADJ) on, so rollover jumps are not read as gaps. | stated | [[livestream_20260923_new_york_open_live_q_a_kbjaggkxdei]] 23:30 (qa); [[livestream_20260915_new_york_open_live_q_a_hlwq1drjbzo]] 1:02:50 |
| 60 | Read daily candles on the futures chart, not ETFs/CFDs whose daily candles gap. | stated | [[livestream_20230730_live_q_a_with_am_trades_weekly_profile_wgyde_h84cs]] 09:40 |
| 61 | Gold triad: use the Forex.com feed for XAU crosses because it opens at 18:00 like GC. | stated (guest) | [[a_complete_trading_framework_universal_models_smt_swing_points_gxt]] 15:58 |
| 62 | ADR is eyeballed from the last few daily candles, not from an indicator that outlier days skew. | stated | [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 25:50; [[livestream_20260804_new_york_open_live_q_a_m0wtbdue7gs]] 17:20 (qa) |
| 63 | TradingView only (works on the free plan, CFDs, any timeframe); not available on NinjaTrader, which he suggests for faster execution. | stated | [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 1:09:10 (qa); [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 20:50 (qa); [[livestream_20260826_ttrades_mnq_cup_morning_session_es_r3bydyry]] 1:26:10 (qa) |
| 64 | (2023) A ratio chart ES/NQ shows relative strength: rising = ES stronger; it cannot be bar-replayed. | stated | [[the_best_relative_strength_indicator_for_es_nq_ict]] 04:22, 06:02 |
| 65 | (2024) He used Power of Three Pro (paid, third party) for multiple HTF candles plus an EQ-of-previous-day indicator. | stated | [[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 11:40 (qa) |

## Engine notes

- **Pair versus stack.** The indicator's model is always one HTF/LTF pair (rule 35), with alignment to a higher model as an optional Auto Bias filter (rule 39). The companion requires a three-role stack (bias / setup / entry) and checks it against the pairings in rules.md 4.2. That is stricter than the indicator's Neutral default and closest to Auto Bias 2 on 1D/1h/5m (inference; seed `wiki/playbooks/ttfm-indicator-full-guide.md`).
- **Bias.** In the indicator, bias is a user filter, not a computed state (rule 40). The companion computes `bias.side` from bias-timeframe closures (rules.md 5), so its "bias" has no counterpart in the indicator (inference).
- **Early CISD.** The indicator prints an in-candle CISD dotted, as a heads-up, and confirms the model only on the close (rules 33-34). He trades early CISDs only with very strong bias (rule 55). The companion's reversal path (rules.md 7) enters off a CISD inside the forming bias candle, which the official tool ranks below a closed-candle model (teacher-vs-engine, IND-3).
- **T-spot.** The companion equates the T-spot with the correct half of the previous candle, citing "just the equilibrium" (rules.md 3.9; [[easy_daily_bias_mechanical_framework]] 06:07). The teacher also describes it as 0.5 of the wick plus a CISD, printed only in candles 3 and 4 with an FVG inside (rules 15-17). The box bounds are never given (IND-1).
- **Kill zones / time filter.** The companion's `kill_zones` (02:00-05:00, 08:30-11:00) and "applies below 1h" mirror the 2024 indicator time filter, whose "Apply below" works the same way (rule 45). In 2026 he no longer uses kill zones (rule 46), and the companion's default `session_filter_role` only reports (rules.md 9.1, 10.4).
- **Projections.** rules.md 8.3 lists projections (-1, -2, -2.5, -4, -4.5) as optional confluence, not used for decisions. That matches his own projections-off setting (rule 27).
- **Not in the engine.** SMT/PSP (single-symbol engine, rules.md open question 23), alert plumbing, multi-model history, HTF candle overlay and the full formation-liquidity set. The companion also returns an entry, stop and targets (rules.md 8), which the teacher says his indicator deliberately does not (rule 4).
- **Repainting.** The indicator never repaints: failed models stay as XC2 and taken protected swings go gray (rules 11, 21). The companion resets a failed path to `none` / `watch` (rules.md 9.2-9.3). Keeping failed models visible for review would match the teacher (inference).

## How it changed over time

- **2022**: no own tool. Auto-plotted levels in an early video [[simple_options_day_trading_strategy_auto_plotted_levels_and_ict_entries]] 00:07. An ATR trailing stop and ICT sessions indicator [[livestream_20220821_8_14_22_mmxm_live_with_niper_ict_concepts_umlwrlxd_v8]] 32:30 (qa). 15-second entries on TradingView/NinjaTrader [[ict_trade_example_15_second_entry]] 00:24.
- **2023**: "no indicators, sometimes volume" [[livestream_20230204_live_q_a_review_with_am_trades_xcvqikdea9w]] 59:30 (qa). Scalping rules coded as an indicator (sweep, displacement, OTE swing) [[scalping_made_simple_building_a_scalping_model]] 04:56. ES/NQ ratio [[the_best_relative_strength_indicator_for_es_nq_ict]] 04:22. PO3 Pro+ and an edited ICT Killzones & Pivots [[livestream_20230924_live_with_day_trading_rauf_preparing_for_a_new_week_qftfd09vv3e]] 37:00 (qa).
- **2024**: midnight open via the ICT kill zones & pivots indicator [[the_twitter_model_the_mmxm_trader_ict_concepts]] 04:22. PO3 Pro plus a previous-day EQ indicator [[livestream_20240929_ttrades_sunday_session_live_q_a_u8bnmaih_ha]] 11:40 (qa). In November the TTFM indicator launches with C2/C3/C4 labels, gray/red/orange validity, T-spot, projections, time filters and formation liquidity [[intro_to_ttrades_fractal_model_indicator_settings]] 03:17-13:55.
- **2025**: fractal locking [[ttrades_fractal_model_inversion_intraday_strategy]] 03:57. Early CISD mode [[ttrades_fractal_model_trading_candle_2]] 04:41. The T-spot becomes his teaching vocabulary [[wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles]] 09:21, [[how_to_trade_retracement_phases_of_price]] 5:28. Auto projections toggle [[targets_using_projections_the_fractal_model]] 08:14. Alerts replace scanning [[livestream_20251007_candle_2_confirmations_live_lesson_q_a_uzpgxvypvgc]] 46:30 (qa).
- **2026**: Pro+ update adds protected swings (dot + line, no repaint) and PSP, the bias filter with Auto Bias 1/2, custom fractals and a session filter; projections stay off [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 04:20-46:40. The XC2 failed label [[livestream_20260819_new_york_open_live_q_a_rvrk4mltjss]] 45:20 (qa). Repeated warnings not to pattern-trade it [[livestream_20261007_new_york_open_live_q_a_mflp3acpzc0]] 31:30 (qa). Not on NinjaTrader [[livestream_20261104_new_york_open_live_q_a_j8u9ch8gkdc]] 20:50 (qa).

## Examples

- Daily C2 with an hourly CISD on an FX pair. Replayed with the indicator: the C2 label, projections and T-spot print, and the next day is a bearish continuation to the lows [[intro_to_ttrades_fractal_model_indicator_settings]] 02:59.
- Two stacked copies: a 5m T-spot inside the hourly T-spot. A bullish 5m setup inside it fails right away because it opposes the HTF, and a close over the hold level turns red as the warning [[intro_to_ttrades_fractal_model_indicator_settings]] 14:12-16:09.
- NQ walkthrough. A C2 shows with a dotted CISD (early) and SMT on the HTF candles. After the closure it marks the CISD, protected swing and T-spot. Entry on the intra-candle CISD, stop on the swing, 2R [[livestream_20260727_new_york_open_live_q_a_je7cd9hjube]] 38:30 (qa).
- Gold 1H with protected swings on both sides of price: he lets Asia/London form before choosing a side [[livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy]] 28:10.
- The indicator marked nothing at a 9 AM NQ entry because the high was not swept. SMT at equal highs still made it a C2 reversal [[livestream_20260821_new_york_open_live_q_a_4rnc3qxxc20]] 50:40 (qa).
- A Discord member's oil swing trade: when the indicator printed the entry-candle CISD off a daily swing, that was the trade, held to the low [[livestream_20261110_new_york_open_live_q_a_cp1nyqa_t5c]] 16:50 (qa).

## Conflicts and open questions

See [[conflicts]] (fragment `_merge/ttfm-indicator/conflicts-fragment.md`).

- **IND-1**: T-spot geometry: the correct half / EQ, 0.5 of the wick, the overlap of two 0.5s, or a box whose bounds are never stated.
- **IND-2**: T-spot timing: only in candles 3-4, the next candle's wick, or open-ended until an hourly close past it.
- **IND-3**: Early / in-candle CISD: a heads-up in the indicator versus an entry in the companion's reversal path.
- **IND-4**: What "failed" means for XC2 and gray protected swings: a wick or a close through.
- **IND-5**: A protected swing without an FVG is not marked, against "type 1" protected swings formed after a sweep.
- **IND-6**: How long after the model a continuation is still marked (no cutoff given).
- **IND-7**: Indicator bias (user filter / Auto Bias ladder) versus a computed bias in the companion.
- **IND-8**: Two-timeframe pair versus three-role stack.
- **IND-9 to IND-18**: kill zones vs session filter, projections, formation-liquidity choice, colour meanings across versions, EQ range, SMT spots, daily open per feed, the "two degrees" collaborator name, continuations only in an FVG (see POI-23), PSP as a headline feature he does not use.

## Related

- [[fractal-model]]: the model the indicator draws; HTF/LTF pairs and alignment.
- [[candle-closures]]: C2/C3/C4 labels and the closure rules behind them.
- [[cisd]]: CISD line, early CISD and the confirmation the indicator requires.
- [[swings-and-structure]]: protected swings (dot + line) and relevant swings.
- [[ranges-and-eq]]: candle EQ and the T-spot as a half of the candle.
- [[smt-and-psp]]: automatic SMT and PSP marks.
- [[liquidity]]: formation liquidity and target marks.
- [[sessions-and-time]]: time filters, session filter, 18:00 open, vertical HTF lines.
- [[poi-and-pd-arrays]]: continuations marked only inside FVGs; no HTF FVGs drawn.
- [[psychology-and-process]]: no pattern trading, quiz templates, "an indicator is not an algo".

## Questions this page answers

- What does the TTFM indicator draw, and what does it not do?
- What is the T-spot, and what do the gray and green boxes mean?
- What does XC2 (or a red/orange C2) mean?
- Which settings does TTrades use (early CISD, bias, fractal, history)?
- What are Auto Bias 1 and Auto Bias 2?
- How do I put two sets of HTF candles on one chart?
- Why is the indicator not showing a setup or a protected swing?
- How should alerts be set for a daily-hourly or 4H-15m model?
- Can the indicator be pattern-traded, and does it have a win rate?
- Does the indicator work on NinjaTrader, CFDs, stocks or the free TradingView plan?
- Which daily open and futures data settings should the chart use?
- How does the companion's engine differ from the indicator's model?
