# TTrades Fractal Model (TTFM) — companion rules

Status: draft for trader review; revised 2026-11-12 after the trader answered open questions 1, 2, 14, 15, 16 and 18 (section 12). Written from the transcripts in `knowledge/ttfm_video_corpus/transcripts/` and the pages in `artifacts/ttrades/pages/`. Nothing here comes from memory of the method.

How to read this document:

- **Source rule** means TTrades states it. Each one carries a citation in the form `[src: file — "verbatim quote"]`. Transcript quotes are auto-captions and are copied as they appear, including caption errors ("wretch" = "reached", "candle to closure" = "candle 2 closure", "downclo" = "down close").
- **Proposal** means the source is silent or qualitative and a default was chosen so code can run. Every proposal is repeated in section 12 (open questions).
- **Trader answer** means the trader this companion is built for decided it (spoken, transcribed, quoted in section 12). Where the answer left room, the reading used is marked as a reading and the behaviour is a `config.json` switch.
- **Not specified in source** means no number or rule was found in the files read.
- All rules are written for the bullish case unless stated. The bearish case is the exact mirror (swap high/low, above/below, up-close/down-close).
- Stage names `c1`..`c4` (lower case) are the stages in `data/fractal_state_machine.json`. "Candle 1".."Candle 4" (capitalised) are TTrades' candle numbers. They are different things; section 2.3 explains the collision.

---

## 1. The model in one page

1. Price cannot turn without a swing point. Number the swing: Candle 2 is the swing candle, Candle 1 is before it, Candle 3 and Candle 4 follow. `[src: fractal_model_fundamentals.txt — "price cannot reverse without a swing point"]` `[src: fractal_model_fundamentals.txt — "Candle 2 will always be the swing low or swing high"]`
2. Three timeframes, three jobs: bias, structure (called "setup" here), entry. `[src: timeframe_alignment_how_to_align_timeframes_for_expansion.txt — "a higher time frame for bias a middle time frame for structure and a lower time frame for entry"]`
3. Bias comes from how the last bias-timeframe candle closed against the candle before it, at a point of interest, confirmed by a change in state of delivery (CISD) one timeframe down. No bias, no trade. `[src: fractal_model_fundamentals.txt — "If I do not have a daily bias I do not drop down to the hourly time frame"]`
4. With a bias, wait for the new bias candle to form its wick against the bias, in the correct half of the previous bias candle, at a point of interest. Then trade the body. `[src: trading_the_4_hour_power_of_three_ohlc_olhc.txt — "I need to let the wick form and then look to trade the body"]`
5. The wick is recognised by repeating the same pattern one level down: a Candle 2 or Candle 3 closure on the setup timeframe, confirmed by a CISD on the entry timeframe, then (preferred) a continuation order block on the entry timeframe.
6. Stop goes on the protected swing. The exit is a fixed multiple of the risk (trader answer: 2R by default, 1R selectable). Higher-timeframe liquidity levels are reported as information. `[src: fractal_model_fundamentals.txt — "For my system, I'm looking for a minimum of 2R"]`
7. Only Candle 3 and Candle 4 are traded as continuations. `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "my fractal model only looks for candle 3 and four, because after that, you can get caught in a new phase of price"]`

Two paths come out of this, and TTrades names them himself: `[src: easy_daily_bias_mechanical_framework.txt — "I'm either going to be looking for a reversal or for a continuation"]`

- **Continuation path**: the forming bias candle is Candle 3 or Candle 4 of a bias-timeframe swing. Trade with the bias, out of the correct half of the previous bias candle.
- **Reversal path**: the forming bias candle is itself becoming a Candle 2. It expands out to, or near, a key level (the previous bias candle's high or low, an untaken bias-timeframe swing, an unfilled bias-timeframe fair value gap), prints a change in state of delivery there with a small wick, and is traded away from the level.

---

## 2. Conventions

### 2.1 Roles and bars

| Symbol | Meaning |
|---|---|
| `B` | bars on the **bias** timeframe (`stack.bias`) |
| `S` | bars on the **setup** timeframe (`stack.setup`) |
| `E` | bars on the **entry** timeframe (`stack.entry`) |
| `X[-1]` | the last bar of frame `X` that is closed at `as_of` |
| `X[-2]` | the bar before that |
| `X[0]` | the bar of frame `X` that is still forming at `as_of` |

`companion/types.py` forbids reading a bar that is not closed. So `B[0]` and `S[0]` are never read from their own frames. They are **synthesised** from closed `E` bars whose open time is at or after the forming candle's open time: `open` = first E open, `high`/`low` = running extremes, "time of high/low" = open time of the E bar that made it. The forming candle's open time is `B[-1].open_time + duration` adjusted to the next actual E bar (sessions, weekends and holidays make durations irregular; use the frame's own index, do not assume a fixed clock).

"Previous bias candle" always means `B[-1]`. With a daily bias that is "previous day"; TTrades' PDH / PDL / EQ are `B[-1].high`, `B[-1].low` and its midpoint.

### 2.2 Candle direction words

- up-close candle: `close > open`. down-close candle: `close < open`.
- A candle with `close == open` (doji): not specified in source. **Proposal:** treat it as belonging to whichever run it sits inside (it neither starts nor ends a series).

### 2.3 Stage names versus candle numbers

`data/fractal_state_machine.json` uses `c1..c4` as progress stages of a setup and fixes `c4_is_entry_ready_structure: true`. TTrades' Candle 1..4 are positions in a swing. This document keeps both and maps them like this:

| Stage | Continuation path | Reversal path |
|---|---|---|
| `none` | no confirmed bias, or path invalidated | no key level reached |
| `c1` | bias established on the bias timeframe | forming bias candle has expanded to, or near, a key level |
| `c2` | an aligned setup-timeframe POI is tagged in the correct half | setup timeframe has closed back on the trade's side of that key level |
| `c3` | setup-timeframe Candle 2/3 closure plus entry-timeframe CISD | CISD confirms the wick |
| `c4` | entry trigger formed; entry-ready structure | entry trigger formed; entry-ready structure |

---

## 3. Primitive definitions

Each primitive lists: definition, how to compute it, parameters, and what is or is not in the source. Parameters are collected in section 11.

### 3.1 Swing high / swing low

- **Source rule.** `[src: which_swing_highs_and_lows_matter_in_trading.txt — "A bullish swing point is a candle that has a low and then a higher low to its right and to its left"]`
- **Compute.** Swing low at bar `i` when `low[i] < low[i-1]` and `low[i] < low[i+1]`. Swing high mirrored. `Swing.time` = bar `i` open time; `Swing.confirmed_at` = close time of bar `i+1`.
- **Parameters.** None in source (one bar each side). Equal lows: not specified. **Proposal:** strict inequality; ties are not swings.
- **Relevant versus failure swings.** TTrades only trusts "relevant" swings (the extreme of a cluster, with "valid separation" from neighbours) and says there is no rule for separation: `[src: which_swing_highs_and_lows_matter_in_trading.txt — "I don't have a mechanical reason to say, hey, this is valid separation"]`. This document does not filter by separation (open question 12).
- **Lookback (source rule).** `[src: which_swing_highs_and_lows_matter_in_trading.txt — "it's always going to be that same look back period of three higher time frame candles, including the current one"]`. For swings on `S`, "higher timeframe" is `B`: use S swings with `time >= B[-2].open_time`. For swings on `E`, use E swings with `time >= S[-2].open_time`. For swings on `B` the next timeframe up is outside the stack; see `bias_poi_lookback_bars` in section 11.

### 3.2 Level taken, and liquidity sweep

Two events are needed and the source uses "sweep" loosely for both.

- **Level taken**: a bar trades beyond a level. For a low: `bar.low < level`. No close condition.
- **Sweep** (matches `types.Sweep`: "traded beyond a prior swing and closed back inside it"): a low is taken at bar `i` and a bar `j` with `i <= j <= i + sweep_reclaim_max_bars` closes back above the level. `Sweep.time` = bar `i`, `extreme` = lowest low from `i` to `j`, `confirmed_at` = close time of bar `j`.
- **Source.** The single-bar form is TTrades' reversal closure (3.4). On lower timeframes he does not require the same bar to close back; the CISD is the confirmation. `[src: protected_swings_understanding_trend_and_invalidations.txt — "be ran out or swept and then close through the series of downclo candles that made the low"]`
- **Parameters.** `sweep_reclaim_max_bars`: not specified in source. **Proposal:** 0 on `B` (same bar, because the bias closure rules are single-candle), 3 on `S` and `E`.

### 3.3 Candle numbering

- **Source rule.** `[src: fractal_model_fundamentals.txt — "candle one will always be the candle before candle 2"]` `[src: fractal_model_fundamentals.txt — "candle 4 is always a continuation if that trend is correct"]`
- Candle 2 = the swing candle. Candle 3 = next candle. Candle 4 = the one after. Numbering applies on every role timeframe.
- Beyond Candle 4 the model stops looking for continuations. `[src: ttrades_fractal_model_trading_candle_2.txt — "within my model I cannot look long after my fourth day"]` `[src: candle_2_closure_foundation.txt — "once you get into candle five and six, that's where you can get caught in a new phase of price"]`

### 3.4 Closure types (one candle against the candle before it)

For candle `k` against candle `k-1`:

| Closure | Bullish condition | Source |
|---|---|---|
| **Reversal closure** | `low[k] < low[k-1]` and `close[k] > low[k-1]` | `[src: candle_2_closure_foundation.txt — "we need price to take out its previous candle's high and then close back below it in a bearish scenario"]` |
| **Continuation closure** | `close[k] > high[k-1]` | `[src: candle_2_closure_foundation.txt — "When price closes below the previous candle's low, I can anticipate a continuation lower"]` |
| **Inside bar** | `high[k] <= high[k-1]` and `low[k] >= low[k-1]` | `[src: next_day_model_fractal_way_to_get_bias_for_trading.txt — "here we have an inside bar it does not give us any more information so we let another candle form"]` |
| **Outside bar closing inside** | takes both `high[k-1]` and `low[k-1]`, closes between them | source only calls it weaker: `[src: equilibrium_for_expansions.txt — "this is less ideal as it has taken both sides of the range"]` |

Notes:

- A candle that takes the low and closes above the previous **high** is both a reversal closure and a continuation closure in the same direction; treat it as bullish (he calls an engulfing candle "very bullish").
- **Proposal:** an outside bar that closes inside the previous range is ambiguous and gives no direction.
- A candle that takes only the high and closes back inside is a bearish reversal closure even if its body is green. See body alignment in 3.5.

### 3.5 Candle 2 closure

- **Definition (source rule).** A reversal closure (3.4) that happens at a point of interest. `[src: candle_2_closure_foundation.txt — "I need a point of interest to frame a candle closure"]`
- **Compute.** Candle `k` is a bullish Candle 2 closure when (a) `low[k] < low[k-1]` and `close[k] > low[k-1]`, and (b) candle `k` reached a POI for its timeframe (3.14).
- **Taking only Candle 1's low is not a POI.** In the Candle 2 video a swing that meets (a) is rejected because it did not reach an older low: `[src: candle_2_closure_foundation.txt — "do we have a point of interest? No, we fail to sweep out this low"]`
- **Body alignment (quality, source).** He repeatedly distrusts a bullish Candle 2 closure whose body is bearish: `[src: fractal_model_fundamentals.txt — "Yes, it closed back inside its previous range, but this is a bearish candle"]` `[src: ttrades_scalping_model_simple_day_trading_strategy.txt — "this alone I would not trust as a candle 2 closure as it is a bearish candle"]`. No threshold given. **Proposal:** quality check `close[k] > open[k]`.
- **Must be confirmed by CISD** one timeframe down (3.11). `[src: cisd_validates_swing_points.txt — "I'm not going to be looking for that as a valid shift in trend"]`

### 3.6 Candle 3 closure

- **Definition (source rule).** Used when the candle at the key level did **not** make a reversal closure. Candle 3 then must hold Candle 2's extreme and close beyond Candle 2's body. `[src: candle_3_closure_ttrades_fractal_model.txt — "price does not sweep out the high or the low but then closes over the body of candle 2"]` `[src: candle_3_closure_ttrades_fractal_model.txt — "candle 3 does not take out the high of candle 2, but closes below the body of candle 2"]`
- **Compute (bullish).** Candle `k` reached a POI and is not a bullish reversal closure. Candle `k+1` has `low[k+1] >= low[k]` and `close[k+1] > max(open[k], close[k])`.
- **Which body edge.** One transcript says "the opening price": `[src: cisd_validates_swing_points.txt — "candle 3 closes below the opening price in candle 2"]`. The two wordings agree when a bearish-case Candle 2 is an up-close candle and disagree when it is not. **Proposal:** use the far body edge (`max(open, close)` bullish, `min(open, close)` bearish), which satisfies both.
- If candle `k+1` does take `low[k]` and closes back above it, it is simply a Candle 2 closure with `k+1` as the swing candle.
- A Candle 3 closure sets up **Candle 4** as the expansion candle. `[src: candle_3_closure_ttrades_fractal_model.txt — "This is where I can then expect candle 4 to continue higher"]`
- Engulf threshold (how far past the body): not specified in source. **Proposal:** any close beyond the edge.

### 3.7 Strong Candle 3 (permission for Candle 4)

- **Source rule.** After a Candle 2 closure, Candle 4 is only expected if Candle 3 closes beyond Candle 2's extreme. `[src: candle_2_closure_foundation.txt — "If candle 3 closes below candle 2's low, we can look for candle 4 to continue lower as well"]` `[src: the_best_timeframe_for_ttrades_fractal_model_simple.txt — "10 a.m. is dependent on 6 a.m. with a strong closure"]`
- **Compute (bullish).** `close[C3] > high[C2]`.

### 3.8 Wick size: small versus large, expansion versus reversal candle

- **Source definitions (qualitative).** `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "it has a small wick on both sides and a large body"]` `[src: ttrades_fractal_model_trading_candle_2.txt — "Small wick supports expansion. Large wick doesn't support expansion"]`
- **Opposing run** is the wick that matters for a forming candle: `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "from the opening price to that high or the move opposite my bias"]`. For a bullish expectation: `opposing_run = open(X[0]) - low_so_far(X[0])`.
- **Threshold: none is given.** The nearest things to a number in the source are relative statements: `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "Yes, we have a small wick relative to the daily range"]` `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "We use almost half the time and quite a bit of range on this move up"]`. An earlier draft spec in this repo (`results/indicator_specs/daily_bias_framework.json`) lists the same threshold as an open question.
- **Timing is part of "small".** The wick must form early. `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "We want to see that early into the candle"]` For a daily candle: `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "we want to see this high day form early New York or before New York"]`
- **Forming candle — default yardstick `wick_yardstick = avg_range` (trader answer to question 2: "yeah, that works").** With `avg_range` = mean of `high - low` over the last `avg_range_bars` closed candles of that timeframe:
  - `small` when `opposing_run <= wick_small_frac * avg_range` **and** the extreme was made early (see `wick_time_frac_max` / `daily_wick_deadline` in section 11);
  - `large` when `opposing_run >= wick_large_frac * avg_range` **or** the extreme was made late;
  - otherwise `unclassified`, treated as not small.
- **Forming candle — alternative yardstick `wick_yardstick = body`.** The trader added: "A small wick is kind of relative to how big the body is, and a large wick is relative to how big the body is — I think that's what he was referencing." Selectable, not the default. `body = abs(last - open)` of the forming candle, where `last` is the latest closed entry-timeframe close. `small` when `opposing_run <= wick_body_small_frac * body` and early; `large` when `opposing_run >= wick_body_large_frac * body` or late; a zero body with any opposing run is `large`. **Proposal:** `wick_body_small_frac = 0.5`, `wick_body_large_frac = 1.0` (a wick as long as the body). Note what this yardstick does: just after a reversal's turn the body is still small, so the wick reads `large` until price has travelled away from the level (open question 31). It applies to the forming candle only; the closed-candle test below is unchanged.
- **Proposal — closed candle** (used to decide which midpoint to respect, 3.9). For a bullish Candle 2: `wick = min(open, close) - low`. `large` when `wick >= closed_wick_large_frac * (high - low)`.
- **What each class means (source rules).**
  - Small wick: the candle can be traded for expansion in the same candle. `[src: easy_daily_bias_mechanical_framework.txt — "a shallow wick supports expansion lower"]`
  - Large wick: do not trade that candle for expansion; wait for the next one, or cut the target to the candle's open. `[src: easy_daily_bias_mechanical_framework.txt — "If we have a large wick, then we're going to want to wait for candle three or the following candle"]` `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "we're just looking for it to reverse or return back to its opening price"]`

### 3.9 Equilibrium (EQ) and the wick midpoint

- **EQ is wick to wick (source rule).** `[src: equilibrium_for_expansions.txt — "I'm always going to measure the candles from Wick High to Wick low"]` `EQ = (B[-1].high + B[-1].low) / 2`.
- **Which half (source rule; opposite of classic premium/discount).** `[src: equilibrium_for_expansions.txt — "I'm looking for the upper half to respect for price to trade higher and the lower half to respect for price to trade lower"]`
- **Correction to an earlier draft.** `results/rulepacks/daily_bias_c123_map.json` defines the bullish POI as the *lower* half of the previous day. That is the reverse of the source and must not be used.
- **"Respect" is judged on setup-timeframe closes (source rule).** `[src: easy_daily_bias_mechanical_framework.txt — "it's not ideal to have closures on the hourly chart below that"]` Price need not touch EQ: `[src: easy_daily_bias_mechanical_framework.txt — "price can form its high below that level. It doesn't need to go up and touch it"]`
- **Wick midpoint (source rule).** For a reversal candle with a large wick he uses half of the wick instead of half of the candle. `[src: master_candlestick_wicks_the_key_to_catching_reversals.txt — "marking out 0.5 of this Wick from the body to the low or the body to the high"]` `[src: equilibrium_for_expansions.txt — "it doesn't really make sense to use the EQ of the whole candle"]` Bullish: `wick_mid = (min(open, close) + low) / 2` of `B[-1]`.
- **Which one to use is not fully mechanical in the source.** In one example with a long lower wick he deliberately uses the whole candle: `[src: trading_candle_3.txt — "that's why I'm going to look for 0.5 of this daily candles range because it makes sense with this candle type"]`
- **Proposal — `respect_level`.** If `B[-1]` is a Candle 2 closure with a `large` closed wick (3.8): `respect_level = wick_mid`. Otherwise (Candle 2 that expanded, strong Candle 3, Candle 3 closure): `respect_level = EQ`. Both levels are always reported in the criterion detail.
- **Tolerance.** He sometimes allows a little more: `[src: equilibrium_for_expansions.txt — "I will allow it to trade a little bit higher than I normally would because of the structure"]`. No number. **Proposal:** `eq_tolerance_frac = 0`.
- **"T-spot".** His indicator's name for the zone where the next candle's wick is expected to form; in the simple case it is the correct half. `[src: easy_daily_bias_mechanical_framework.txt — "the T-spot marked up which in this case is just the equilibrium"]`

### 3.10 Fair value gap (FVG)

- **Source rule.** `[src: reversal_sequence_ttrs_how_to_blend_pd_arrays.txt — "three Candlestick pattern in which the high of the third candle does not overlap the low of the first candle"]` `[src: how_to_actually_trade_inversion_fair_value_gaps_ifvg.txt — "the wick of candle one and the wick of candle three do not overlap leaving a gap"]`
- **Compute.** Bullish FVG over bars `i-1, i, i+1` when `low[i+1] > high[i-1]`. `bottom = high[i-1]`, `top = low[i+1]`, `time` = bar `i`, `confirmed_at` = close of bar `i+1`. Bearish: `high[i+1] < low[i-1]`, `top = low[i-1]`, `bottom = high[i+1]`.
- **Tagged**: a later bar trades into the zone (bullish: `bar.low <= top`) while it is unfilled.
- **Filled / not respected** (`filled_at`): first bar that **closes** through the far side (bullish: `close < bottom`). He then drops it: `[src: easy_daily_bias_mechanical_framework.txt — "we don't respect this fair value gap. So I can simply remove it"]`
- **Minimum size.** Not specified in source (he uses "a tiny little fair value Gap"). **Proposal:** `fvg_min_size = 0`.
- **Inversion FVG.** A filled FVG used as support/resistance from the other side. Defined in the source; not used by this checklist.

### 3.11 Change in state of delivery (CISD)

- **Source rule.** `[src: cisd_validates_swing_points.txt — "closing through the series of candles that wretch into that important level"]` It is the same event as an order block forming: `[src: cisd_validates_swing_points.txt — "The change in the state of delivery is the order block formation that forms when trend changes"]`
- **Bodies, not wicks (source rule).** `[src: equilibrium_for_expansions.txt — "I'm not going to use the bodies like I do for the change in the state of delivery or order blocks"]` The level is an opening price: `[src: trade_continuations_using_breaker_blocks.txt — "did we close through the opening price in that we did so we have a change in the state of delivery"]`
- **Compute (bullish CISD).**
  1. **Anchor**: bar `i` holding the lowest low of the leg into the level.
  2. **Series**: the maximal run of consecutive down-close bars ending at bar `i`. If bar `i` is itself up-close, the run ends at bar `i-1`. He often has a one-candle series: `[src: fractal_model_fundamentals.txt — "find the series of down close candles. This case, it's one"]`
  3. **Level**: the highest `open` in the series (the open of its first candle unless there are gaps). This is `Cisd.level`.
  4. **Confirmation**: first bar `j > i` with `close[j] > level`. `Cisd.time` = bar `j`, `confirmed_at` = close of bar `j`.
  5. **Re-anchor**: if any bar before `j` makes a lower low than `low[i]`, discard and start again from the new low. `[src: trading_candle_3.txt — "we make a new low. We're going to then track that new low"]`
  6. **Leg must have reached a level** to count: took a prior swing low / previous higher-role candle low, or traded into a bullish FVG (3.14).
- **No series found** (bars `i` and `i-1` are both up-close): not specified in source. **Proposal:** use `max(open[i], close[i])` as the level.
- **Which candles belong to the series is sometimes discretionary.** `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt — "when we have this candle that doesn't form a swing, generally I ignore it"]` The computation above does not ignore small candles (open question 9).
- **Speed (source rule, with a number).** `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt — "I prefer 1 2 maybe three. If it takes longer than that, a lot of times it's just taking too long"]` `bars_to_confirm = j - i`; "swift" when `<= cisd_max_bars` (default 3, from that quote). A slow close-through is read as consolidation: `[src: cisd_validates_swing_points.txt — "If it consolidates for half of the candle and then closes over, it's usually just a consolidation"]`
- **Scope (source rule).** A CISD only matters inside a qualifying higher-timeframe candle closure. `[src: cisd_validates_swing_points.txt — "it does not mean anything to me unless it is paired with a higher time frame candle closure"]`

### 3.12 Order block / opposing candle, mean threshold, propulsion block

- **Source rule.** `[src: reversal_sequence_ttrs_how_to_blend_pd_arrays.txt — "I take the series of up closed candles into that point of interest when it is then closed below"]`
- **Compute.** The series from 3.11 step 2, once the CISD confirms. Bullish order block zone: `top = level` (highest open in the series), `bottom = lowest close in the series`. "Opposing candle(s)" is the same object.
- **Validity (source rule).** The run into the block must have swept a high/low or reached into an FVG. `[src: trade_continuations_using_order_blocks.txt — "I needed to reach into a fair value Gap or sweep out a high"]` The one exception he gives is SMT divergence with a correlated asset, which cannot be computed from one symbol's bars and is **not implemented**.
- **Mean threshold** = midpoint of the zone (`(top + bottom) / 2`). Price should hold it. `[src: fractal_model_fundamentals.txt — "I don't want to see price trade above 50% of these opposing candles"]`
- **Propulsion block**: an order block formed while retesting an earlier one. `[src: timeframe_alignment_how_to_align_timeframes_for_expansion.txt — "this is now a propulsion block because it is an order block formed off of another order block"]`
- **Continuation order block**: an order block that forms *after* the reversal CISD, in the direction of the new trend. This is his preferred entry (section 7).

### 3.13 Breaker block

- **Source rule.** `[src: trade_continuations_using_breaker_blocks.txt — "a breaker block is a Candlestick pattern in which we have a high low higher high and lower Low"]` Bearish breaker = the down-close candles between that high and that low; bullish = the up-close candles between the low and the high of a low / high / lower low / higher high sequence.
- **Use.** Optional alternative entry in continuations. He prefers order blocks: `[src: trade_continuations_using_breaker_blocks.txt — "although I prefer to just use order blocks as I find them more simple and easy"]`
- **This checklist does not use breakers.** Defined here so the term is unambiguous.

### 3.14 Point of interest (POI)

- **Source rule.** `[src: the_only_trading_strategy_you_need_for_2026.txt — "points of interest are always going to be either a fair value gap or a low in a bullish scenario"]` Order blocks / opposing candles are also used, described as more advanced: `[src: candle_2_closure_foundation.txt — "I can use these opposing candles as the point of interest"]`
- **A bar "reached a POI" (bullish) when any of:**
  - (a) it took a confirmed, previously untaken swing low on its own timeframe inside the lookback (3.1);
  - (b) it traded into an unfilled bullish FVG on its own timeframe that was confirmed before the bar opened;
  - (c) it traded into a valid bullish order block zone (3.12) and closed at or above that block's mean threshold.
- **Location.** For the continuation path the POI must sit in the correct half (section 6). `[src: fractal_model_fundamentals.txt — "I want to see them in the upper half or lower half of the previous day's range and then at a point of interest"]`
- **Mapping to `poi_type` in the state machine:** (a) `liquidity_target_zone`; (b) and (c) `reaction_zone`; the correct half itself `equilibrium_zone`; a protected swing used as the reference `protected_swing_zone`.

### 3.15 Protected swing

- **Source rule.** `[src: protected_swings_understanding_trend_and_invalidations.txt — "A protected swing is a high or low in which I'm expecting to hold as the trend continues"]` Two types: after a sweep, or out of an FVG. `[src: protected_swings_understanding_trend_and_invalidations.txt — "the other type of protected swing is one formed out of a fair value gap"]`
- **Compute.** A bullish CISD (3.11) whose leg reached a level creates a protected low: `price = low[i]` (the anchor), `time` = bar `i`, `confirmed_at` = `Cisd.confirmed_at`.
- **Broken** (`broken_at`): first later bar with `low < price`. Not specified whether a wick or a close breaks it; stops are placed on the swing, so **proposal:** any trade-through.
- **Caveat (source rule).** `[src: easy_daily_bias_mechanical_framework.txt — "this swing is only protected until it hits liquidity"]`
- **Use.** Stop placement and invalidation (section 7), and the continuation entry itself: `[src: protected_swings_understanding_trend_and_invalidations.txt — "I am mainly focused on a new invalidation forming"]`

---

## 4. Timeframe alignment

### 4.1 The three roles

| Role | Field | Job (source wording) |
|---|---|---|
| bias | `stack.bias` | direction; whose high/low/EQ frame the trade |
| setup | `stack.setup` | "structure": confirms the bias swing with a CISD, hosts the POI and the Candle 2/3 closure that forms the bias candle's wick |
| entry | `stack.entry` | CISD and continuation order block that confirm the setup candle's wick; stop placement |

The same pairing links bias to setup and setup to entry. `[src: timeframe_alignment_how_to_align_timeframes_for_expansion.txt — "I align my bias the same way as I would align my structure"]`

### 4.2 Pairings TTrades states

**Two-timeframe pairings (higher : lower):**

| Higher | Lower | Citation |
|---|---|---|
| 1W | 4h | `[src: timeframe_alignment_how_to_align_timeframes_for_expansion.txt — "I pair the weekly with the 4 Hour the daily with the 1 hour the 4 Hour with the 15"]` |
| 1D | 1h | same quote |
| 4h | 15m | same quote |
| 1h | 5m | `[src: timeframe_alignment_how_to_align_timeframes_for_expansion.txt — "the 1 hour with the five the 30 minute with the 3 minute and the 15minute with the 1 minute"]` |
| 30m | 3m | same quote |
| 15m | 1m | same quote |
| 1M | 1D | `[src: cisd_validates_swing_points.txt — "we need to go down to the daily time frame to see if we have a change in the state of delivery"]` (said of a monthly candle) |

**Three-timeframe stacks (bias / setup / entry):**

| Stack | Citation |
|---|---|
| 1D / 1h / 5m | `[src: fractal_model_fundamentals.txt — "the hourly and 5-minute model aligned with the daily chart"]` |
| 1W / 4h / 15m | `[src: trade_like_ttrades_top_down_analysis.txt — "let's analyze the weekly 4H hour and 15-minute time frame"]` |
| 4h / 15m / 1m | `[src: timeframe_alignment_how_to_align_timeframes_for_expansion.txt — "I'd use the 4H hour for bias the 15-minute with structure and the 1 minute for entry"]` |
| 1D / 4h / 15m | `[src: the_best_timeframe_for_ttrades_fractal_model_simple.txt — "the daily for bias and then using the 4 hour for a swing point and the 15-minute time frame for entry"]` |
| 1D / 30m / 3m | `[src: ttrades_fractal_model_trading_candle_4.txt — "our 3 minute our 30 minute and our daily is all aligned in One Direction"]` |
| 1W / 1D / 1h | `[src: ttrades_swing_trading_model_simple_strategy.txt — "using this on the weekly, the daily, and the hourly for entries"]` |
| 1M / 1W / 4h | `[src: ttrades_swing_trading_model_simple_strategy.txt — "monthly, weekly, and then 4hour for entries"]` |
| 1M / 1D / 1h | `[src: the_only_trading_strategy_you_need_for_2026.txt — "I'm using the monthly, daily, and then hourly"]` |
| 1h / 15m / 1m | `[src: ttrades_scalping_model_simple_day_trading_strategy.txt — "trading the body of the hourly candle using a 15-minute and 1 minute fractal model"]` |

Further statements that affect stack choice:

- Stacks are a preference, not a law. `[src: ttrades_swing_trading_model_simple_strategy.txt — "You don't have to use this defined time frame alignment. If things are a bit messy, you can move up one time frame"]`
- Two timeframes can be enough. `[src: trade_like_ttrades_top_down_analysis.txt — "I don't need three time frames"]`
- He prefers not to frame reversals from a bias timeframe below 4h. `[src: easy_daily_bias_mechanical_framework.txt — "I don't prefer to go below the 4hour time frame as it just becomes a bit more difficult"]`
- For expansion alignment he wants at least two higher candles lined up. `[src: higher_timeframe_analysis_for_trading_aligning_expansion_candles.txt — "if this was a daily candle and a 4-hour candle, then that would be enough for me to trade a 15-minute time frame"]`

Notes on the stacks: 1D / 4h / 15m and 1W / 1D / 1h use a bias-to-setup step that is not in the two-timeframe pairing list (the list would give 1D : 1h and 1W : 4h). He teaches both, so both are accepted. A stack not in the table above (for example 1D / 15m / 1m) is **not stated in the source**; the checklist still runs and reports it through the advisory criterion `stack_pairing_stated`.

### 4.3 Rules tied to a specific timeframe, and how they generalise

| Source rule (as taught on the daily) | Generalised rule used here | Whose generalisation |
|---|---|---|
| Previous day high / low (PDH / PDL) | `B[-1].high` / `B[-1].low` | **TTrades.** `[src: easy_daily_bias_mechanical_framework.txt — "instead of previous day high, it's going to be a previous candle's high"]` |
| Previous day EQ | wick-to-wick midpoint of `B[-1]` | **TTrades.** `[src: equilibrium_for_expansions.txt — "is it also fractal right just like my fractal model used on any time frame it's the same with this concept"]` |
| Daily open ("back towards the daily open") | open of `B[0]` | **TTrades.** `[src: ttrades_fractal_model_trading_candle_2.txt — "back towards the daily open or the higher time frame open"]` |
| Daily bias from daily closes | bias from `B[-1]` against `B[-2]` | **TTrades** ("next candle model"). `[src: next_day_model_fractal_way_to_get_bias_for_trading.txt — "simply using the previous candle to anticipate the next"]` |
| Look back 3 days / 3 months for relevant swings | 3 candles of the next role up, including the current | **TTrades** (3.1 quote) |
| "High of day should form early New York or before" | the forming bias candle's wick must form early in that candle | **Mine.** For a daily bias the deadline is a clock time; for other bias timeframes a fraction of the candle. See `daily_wick_deadline`, `wick_time_frac_max`. |
| Kill zones (London, New York AM) | apply only when the entry timeframe is below 1h | **Mine**, from his remark that kill zones are for intraday. `[src: reversal_sequence_ttrs_how_to_blend_pd_arrays.txt — "trade inaday which is what I include to be below the hourly chart"]` His indicator's time filter is likewise limited: `[src: intro_to_ttrades_fractal_model_indicator_settings.txt — "this time filter will only apply on the 30 minute time frame or below"]` |
| Time levels 8:30, 9:30, 10:00 New York | advisory only; reported, never gating | **Mine.** They are daily-profile events and mean nothing for a weekly or monthly bias. |
| Session decides the confirmation timeframe (Asia: 1h/30m; London: 1h/30m/15m; New York: also 5m) | daily bias only: the reversal-path CISD may be read on `E` instead of `S` once inside the New York window | **Mine.** Source: `[src: ttrades_fractal_model_trading_candle_2.txt — "in Asia, I'm almost specifically only going to use the hourly or 30 minute"]` `[src: ttrades_fractal_model_trading_candle_2.txt — "Once I get into London, I'll use the hourly, 30 minute, or 15"]` |
| Weekly profile (Tuesday low, Wednesday/Thursday expand) | not encoded; it is the same Candle 2 / Candle 3 / Candle 4 logic with a weekly bias | **Mine** |
| 4h candle opens (he names 6 a.m. and 10 a.m. New York for futures) | taken from the data's own 4h index | **Mine** |
| 2R minimum | unchanged on every stack | n/a |

---

## 5. Bias rules (bias timeframe)

Bias is read once per closed bias candle and does not change while `B[0]` forms. It can be *invalidated* intra-candle (section 8).

### 5.1 Raw closure read

Classify `B[-1]` against `B[-2]` with 3.4, and check `B[-1]` against `B[-2]`/`B[-3]` for a Candle 3 closure (3.6).

`[src: fractal_model_fundamentals.txt — "if price closes below its previous day low, I'm expecting a continuation lower"]`
`[src: fractal_model_fundamentals.txt — "If price fails to close below its previous day low, I'm expecting a reversal and for price to be bullish"]`

### 5.2 Bias cases

| Case | What `B[-1]` is | Extra requirement | `Verdict.bias` | `B[0]` is |
|---|---|---|---|---|
| A | Candle 2 closure (3.5) | POI reached by `B[-1]`; CISD on `S` inside `B[-1]` | direction of the closure | Candle 3 |
| B | strong Candle 3 (3.7) after a case-A Candle 2 at `B[-2]` | case-A requirements held for `B[-2]` | same direction | Candle 4 |
| C | completes a Candle 3 closure (3.6) with swing candle `B[-2]` | POI reached by `B[-2]`; CISD on `S` inside `B[-2]`..`B[-1]` | direction of the closure | Candle 4 |
| D | continuation closure that fits neither B nor C | — | direction of the close, flagged **late** | Candle 5 or later, or no identifiable swing |
| E | inside bar | — | `neutral` | — |
| F | outside bar closing inside | — | `neutral` (proposal) | — |
| G | reversal closure with no POI | — | `neutral` | — |
| H | fits A or C by closure, but the CISD on `S` has not printed yet | — | `neutral` until the CISD prints, then as A/C | Candle 3 / 4 |
| I | bullish Candle 3 closure and bearish reversal closure at the same time (or the mirror) | — | `neutral` (proposal) | — |

Source support:

- A: `[src: candle_2_closure_foundation.txt — "you want to find those candle closures first, then see if they have a point of interest, and then that gives you bias"]`
- A, C (CISD requirement): `[src: fractal_model_fundamentals.txt — "Once I have both the closure and the change in the state of delivery, then I can look for entries"]`
- H (CISD may arrive after the close): `[src: targets_using_projections_the_fractal_model.txt — "We have yet to form a change in the state of delivery. So we need to wait for that"]`
- D (late): `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt — "I don't look for continuations after we've already hit a higher time frame objective or had multiple candles of expansion"]`
- G: `[src: candle_3_closure_ttrades_fractal_model.txt — "if we do not have a point of interest or a valid closure, I'm not just going to choose random swing points"]`
- Preference for case A with a reversal-shaped Candle 2: `[src: trading_candle_3.txt — "Don't try to trade candle twos that expand a ton"]`

### 5.3 The bias-swing CISD

For cases A and C, find on `S` the lowest low inside the swing candle (bullish) and apply 3.11 using S bars. The CISD must confirm at or before `as_of`. It creates the **bias protected swing** (the swing candle's low) and the **bias order block** (an S-timeframe zone that is itself a POI for section 6).

`[src: fractal_model_fundamentals.txt — "the swing point on the daily and make sure we have a change in the state of delivery there"]`

### 5.4 When there is no trade from bias

- Cases E, F, G, I (`Verdict.bias == neutral`): continuation path is `none`, decision `no_trade` unless the reversal path is alive.
- Case H: the closure and POI are there but the CISD is not. The continuation path is alive at stage `none` and the decision is `watch` until the CISD prints or the swing breaks.
- Case D: bias is reported, but the continuation path is blocked by `bias_candle_index_ok`.
- The bias swing's extreme is traded through (section 8).
- The previous bias candle's high/low was already taken, or `B[0]` has already expanded. `[src: equilibrium_for_expansions.txt — "wait for the next daily closure as this range has already expanded"]` Since the trader's answer to question 16 this is reported (`cont_objective_open`) but does not end the path unless `objective_open_role = gate`.
- Three or more expansion candles in a row: stand aside for continuations. `[src: equilibrium_for_expansions.txt — "at this point we have 3 days of expansion into lows this is where I'm going to avoid"]` With Candle 3 / Candle 4 only, the checklist already stops after two expansion candles past the swing, so this never binds separately.

The reversal path (section 7) does not need a confirmed bias. It needs price at or near a key level instead.

---

## 6. Continuation path — ordered checklist

Direction = the closure direction from section 5.2 (the same as `Verdict.bias` once the bias CISD has printed). Written for bullish.

Criterion classes, used in the decision mapping (section 10):

- **G (gate)**: `False` kills the path until the next bias candle.
- **S (step)**: `False` means "has not happened yet".
- **Q (quality)**: `False` blocks entry-ready but keeps the path alive.
- **A (advisory)**: reported, never changes the decision.

`passed = None` always means the inputs needed were not available; the "cannot evaluate" column says when.

### Stage c1 — bias established

| Key | Label | TF | Class | Pass condition | Cannot evaluate when |
|---|---|---|---|---|---|
| `data_sufficient` | Enough history on all three timeframes | all | G | `B` has at least `max(avg_range_bars, bias_poi_lookback_bars) + 3` closed bars; `S` covers from `B[-3]` open; `E` covers from `B[-1]` open | never (returns `False`) |
| `stack_pairing_stated` | Stack is one TTrades teaches | all | A | `(bias, setup, entry)` is in the 4.2 stack table, or both adjacent pairs are in the pairing table | never |
| `bias_closure_directional` | Bias candle closed with a direction | B | G | section 5.2 case A, B, C or D applies by closure alone | fewer than 3 closed `B` bars |
| `bias_poi_present` | Bias swing formed at a point of interest | B | G | the swing candle (A: `B[-1]`; B, C: `B[-2]`) reached a POI per 3.14 (a) or (b) using `B` swings/FVGs within `bias_poi_lookback_bars`. Case D: `False` | not enough `B` history for the lookback |
| `bias_cisd_confirmed` | Lower timeframe confirms the bias swing | S | S | bullish CISD on `S` anchored at the swing candle's low, confirmed `<= as_of` (5.3) | `S` bars do not cover the swing candle |
| `bias_candle_index_ok` | Forming bias candle is Candle 3 or Candle 4 | B | G | case A (Candle 3), B or C (Candle 4). Case D: `False` | `bias_closure_directional` is `None` |
| `bias_swing_intact` | Bias swing has not been broken | B (via E) | G | no bar since the swing candle has traded below the swing candle's low | — |
| `cont_objective_open` | Previous bias candle's high (the structural level) is not yet taken | B (via E) | A by default; G when `objective_open_role = gate` | `B[0].high_so_far <= B[-1].high` | no closed `E` bar in `B[0]` yet → `None` |
| `bias_c2_not_expanded` | Bias Candle 2 was a reversal candle, not an expansion | B | A | case A and the closed-candle wick of `B[-1]` is `large` (3.8). Cases B, C: `True` | — |

Sources: gates above are cited in sections 3 and 5. `cont_objective_open`: `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt — "when we hit a higher time frame target, that is when we can form a new phase of price"]`. It was a gate until the trader's answer to questions 15 and 16 ("that just depends on the RR ... if it's a one-to-one or one-to-two ratio for the trade, the user should exit"): the exit is now a multiple of the risk, not that level, so the level being taken no longer ends the path. In the real-data sweep before the change this gate failed in 277 of 420 continuation checks. `bias_c2_not_expanded`: when it fails he still trades but only with the conservative entry: `[src: trading_candle_3.txt — "I'm going to demand a continuation on the lower time frame"]`; in that case the entry CISD is not accepted as a trigger, whatever `entry_mode` says, and only a continuation order block counts.

### Stage c2 — aligned setup POI tagged in the correct half

| Key | Label | TF | Class | Pass condition | Cannot evaluate when |
|---|---|---|---|---|---|
| `cont_eq_respected` | Correct half of the previous bias candle is holding | S | G | no closed `S` bar inside `B[0]` has `close < respect_level - eq_tolerance_frac * (B[-1].high - B[-1].low)` (3.9) | no closed `S` bar in `B[0]` yet → `None` |
| `cont_poi_tagged` | Price has reached a setup-timeframe point of interest | S | S | some closed `S` bar inside `B[0]` reached a POI per 3.14: (a) took an untaken `S` swing low with `time >= B[-2].open_time`; or (b) traded into an unfilled bullish `S` FVG whose `top > respect_level`; or (c) traded into the bias order block (5.3) and closed at or above its mean threshold | no closed `S` bar in `B[0]` |
| `cont_opened_against_bias_first` | Bias candle moved against the bias first | B (via E) | A | in `B[0]`, time of `low_so_far` is earlier than time of `high_so_far`, and `low_so_far < open` | no closed `E` bar in `B[0]` |

Sources:

- `cont_eq_respected` failing flips his expectation, hence a gate: `[src: equilibrium_for_expansions.txt — "if these do not respect I then can flip my bias and anticipate the low of the range being taken"]`
- `cont_poi_tagged` (a): `[src: fractal_model_fundamentals.txt — "what I'm going to use now is those intraday lows"]`; (c): `[src: timeframe_alignment_how_to_align_timeframes_for_expansion.txt — "price retraces into a fair value Gap retesting the change in the state of delivery"]`
- He does not pick which POI will hold in advance: `[src: easy_daily_bias_mechanical_framework.txt — "I'm going to wait for a swing to form in that area or a new protected swing"]`
- `cont_opened_against_bias_first`: `[src: easy_daily_bias_mechanical_framework.txt — "When price opens and makes a low first, that is bullish"]`; he blamed a losing example on the opposite: `[src: fractal_model_fundamentals.txt — "This expansion candle or what we are anticipating to expand lower opened and went lower first"]`. Advisory because he calls the preferred order "most ideal", not required.

### Stage c3 — confirmation

The **setup swing candle** is the `S` bar that tagged the POI. The **active setup** is the most recent qualifying closure inside `B[0]`.

| Key | Label | TF | Class | Pass condition | Cannot evaluate when |
|---|---|---|---|---|---|
| `cont_setup_closure` | Setup timeframe printed a Candle 2 or Candle 3 closure at the POI | S | S | a bar that satisfied `cont_poi_tagged` is a bullish reversal closure (3.4), **or** it is not, and the next `S` bar completes a Candle 3 closure (3.6). The closing candle must also satisfy `cont_eq_respected` | `cont_poi_tagged` is not `True` → `False`, not `None` |
| `cont_setup_closure_body_aligned` | Closing candle's body agrees with the direction | S | Q | Candle 2 closure: `close > open` on the swing candle. Candle 3 closure: `True` | no active setup → `None` |
| `cont_entry_cisd_confirmed` | Entry timeframe confirms the setup swing | E | S | bullish CISD on `E` anchored at the lowest low inside the setup swing candle (for a Candle 3 closure: inside Candle 2..Candle 3), confirmed `<= as_of` | `E` bars do not cover the setup swing candle |
| `cont_entry_cisd_swift` | That confirmation was a quick, V-shaped turn | E | A | `bars_to_confirm <= cisd_max_bars` for the CISD above. Advisory since 2026-11-12: a slow turn no longer blocks by itself; it makes the entry range of `cont_not_inside_consolidation`, which decides | no CISD yet → `None` |

Sources:

- `cont_setup_closure`: `[src: the_only_trading_strategy_you_need_for_2026.txt — "have either a candle 2 or a candle 3 closure"]`; these are the only two formations: `[src: candle_3_closure_ttrades_fractal_model.txt — "these are the only two formations that I look for within my model"]`
- `cont_entry_cisd_confirmed`: `[src: fractal_model_fundamentals.txt — "No, we have not yet closed over that. So I have to wait for that to occur before I can take an entry"]`
- `cont_entry_cisd_swift`: 3.11 speed quote.
- `cont_entry_cisd_swift` as the start of a consolidation: see `cont_not_inside_consolidation` (stage c4).

### Stage c4 — entry-ready structure

**Entry window.** After a setup Candle 2 closure: setup Candle 3, plus setup Candle 4 if Candle 3 was strong (3.7). After a setup Candle 3 closure: setup Candle 4 only. `[src: trading_candle_3.txt — "I like to trade that first continuation instead of the further continuations because I feel like I'm chasing"]`

**Entry trigger.** Two kinds of trigger exist:

- **CISD trigger** (the "aggressive" entry): the entry CISD itself. Trigger time = later of (CISD confirmation, close of the setup closing candle). Not available when the bias Candle 2 expanded (`bias_c2_not_expanded` is `False`).
- **Order-block trigger** (the "conservative" entry): a **continuation order block** on `E` inside the entry window. After the entry CISD, price pulls back without breaking the protected low, reaches an `E` POI per 3.14 (takes an `E` swing low formed after the protected low, or trades into an unfilled bullish `E` FVG, or retests the entry CISD's order block), then closes through the series of down-close candles of that pullback (3.11). The trigger bar is the bar that closes through. It creates a **new protected low** at the pullback's low.

`entry_mode` selects which count (trader answer to question 14: "both can reach you at the same time — you're going to grab a CISD or a continuation order block"):

- `either` (default): both kinds count. The trigger reported is the first to confirm among those whose stop swing is untaken (`entry_either_pick = first`); the detail says which kind fired and how many other live triggers exist. With `entry_either_pick = latest` the most recent live trigger is reported instead.
- `aggressive`: the CISD trigger only (the order-block trigger when the bias Candle 2 expanded).
- `conservative`: order-block triggers only; the latest live one is reported, as before.

By construction the order block forms after the entry CISD, so in `either` mode the CISD trigger always confirms first when it is available; the order block is the first trigger only when the CISD trigger is not available (expanded bias Candle 2). See open question 28.

| Key | Label | TF | Class | Pass condition | Cannot evaluate when |
|---|---|---|---|---|---|
| `cont_entry_window_open` | Still inside setup Candle 3 (or allowed Candle 4) | S | Q | `as_of` falls inside the entry window of the active setup | no active setup → `None` |
| `cont_entry_trigger` | Entry trigger has formed | E | S | per `entry_mode` above, trigger bar closed `<= as_of` and inside the entry window; the detail names the kind that fired | no entry CISD yet → `False` |
| `cont_protected_swing_intact` | Stop swing has not been taken | E | Q | no `E` bar since the trigger has `low <` the stop swing; and the setup swing candle's low is untaken | no trigger → `None` |
| `cont_trigger_clear_of_liquidity` | Trigger did not form while running short-term highs | E | Q | the trigger bar's `high` is not above any confirmed `E` swing high formed since the setup swing candle opened | no trigger → `None` |
| `cont_trigger_v_shape` | Trigger closed through in a quick V | E | Q | the chosen trigger's own close-through came `<= cisd_max_bars` bars after its low. A slow one is consolidation, not continuation: with `wait_for_clean_continuation` the engine reports the next clean trigger instead, and this check fails only when none has formed | no trigger → `None` |
| `cont_not_inside_consolidation` | Trigger is not an internal move inside a consolidation | E | Q | **Entry range.** When the entry CISD closed through slowly (`bars_to_confirm > cisd_max_bars`), price was consolidating: range low = the entry CISD's low, range high = the highest high from the bar before its down-close series (the top of the leg) up to the bar before the close-through. That close-through is a sweep of the range high, not a continuation. Passes when there is no entry range, or when the trigger is a new continuation (order-block trigger) whose pullback began after a close above the range high (breakout). Fails for the slow CISD trigger itself and for any continuation that formed inside the range. A sweep of the range low takes the setup swing low, so it ends this setup; the next setup closure is the manipulation entry | no trigger → `None` |
| `cont_objective_open_at_trigger` | Higher-timeframe target (previous bias candle's high) was still open at the trigger | B, E | Q by default; A when `objective_at_trigger_role = advisory` | no `E` bar of the forming bias candle, up to and including the trigger bar, traded above `B[-1].high`. Judged at the trigger, so the target being reached after entry never demotes the trade | no trigger → `None` |
| `cont_entry_early_in_candle` | Trigger closed early enough in its setup candle | S | Q | the trigger closes at most `entry_latest_candle_frac` (0.75) into the setup candle open at that moment. A trigger closing exactly at a setup candle's close belongs to the next candle (0%) | no trigger → `None` |
| `cont_newer_protected_low` | Newer protected low since the entry (stop can trail) | E | A | a later continuation order block (same definition as the order-block trigger) left a higher, untaken protected low; the detail gives it and the R it would lock | none yet → `None` |
| `cont_reward_at_least_2r` | Structural level (previous bias candle's high) is at least 2R away | E, B | A by default; Q when `reward_check_role = quality` | `(S1 - entry) >= min_rr * (entry - stop)` with the values from section 8, where S1 is the structural level `B[-1].high`. The detail gives the exit price and where S1 (and S2) sit in R. Only as Q: if it fails on the wick stop and the body stop is allowed (8.2), re-test with the body stop | no trigger → `None` |
| `session_filter_ok` | Inside a kill zone (information) | E | A by default; Q when `session_filter_role = quality` | section 9.1 | — |

Sources:

- Order-block trigger: `[src: the_only_trading_strategy_you_need_for_2026.txt — "we're not going to enter on that change in the state of delivery. We're going to wait for another continuation"]`
- CISD trigger: `[src: fractal_model_fundamentals.txt — "look for a change in the state of delivery in candle 2. And with that, I can take any entry"]`
- The continuation must form the higher-timeframe wick: `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt — "Frame your entries when it is forming the higher time frame wick"]`
- `cont_trigger_clear_of_liquidity`: `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt — "the continuation forms at the same time that we are taking out highs in a range or a short-term target is taken"]`; his response is to wait for another continuation.
- A trigger needs a POI, or it is not counted: `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt — "I would consider personally no because we don't reach into a point of interest"]`
- Trigger choice (`wait_for_clean_continuation`, default on): the trigger reported is the first that is clean, meaning `cont_trigger_v_shape`, `cont_trigger_clear_of_liquidity` and `cont_not_inside_consolidation` would all pass. When the first trigger is not clean and a later clean one exists, the later one is reported. Source: "when you take out short-term highs or lows and you're still seeking a continuation, you want to wait for a continuation move off of those levels" (@23:32).
- `cont_trigger_v_shape` and `cont_not_inside_consolidation`: `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt]`. @01:00: "When price doesn't get that nice V-shaped recovery and close over the series of down-close candles ... this is actually a consolidation. And this closure through ... is actually a manipulation of this consolidation range". @06:30: "It's actually just sweeping out the high in the consolidation range". @07:00–07:30: "this isn't a retracement anymore. This is a consolidation and then we'd be focused on the highs and the lows of the range ... you're not interested in closures over this level or any closures over down-close candles in here". @08:30: "Two candles down and we have six candles up ... That is not fast or V-shaped". @09:00: "That's just internal to the range". @11:01: "we either want to see a manipulation of the low or a breakout of the high. So, we're not going to trade the breakout unless we have a continuation". @21:30: "I'm either going to wait for a manipulation of that consolidation or a breakout".
- `cont_objective_open_at_trigger`: `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt @03:20 — "number three is a higher time frame target has already been taken"; @03:40 — "when we hit a higher time frame target, that is when we can form a new phase of price"]`. This differs from the reading of question 16 that made `cont_objective_open` advisory: that check asks whether the target is taken *now*, this one whether it was taken *before the entry*.
- `cont_entry_early_in_candle`: `[src: when_to_take_entries_for_trading_expansions_time_range — "first half if you want to make it mechanical"; with three quarters of the candle gone, wait for the next one]` (see `knowledge/second_brain/wiki/playbooks/ttfm-entry-timing-and-order-type.md`).
- `cont_newer_protected_low`: protected-swings blog — "each subsequent reach into an important level and close below an up-close candle series creates new protected highs. These become stepping stones for continuation entries"; "Refine your stop loss by finding closer protected swings following the CISD". Reported only; the stop the plan uses does not move.

---

## 7. Reversal path — ordered checklist

This is "trading Candle 2" on the bias timeframe: `B[0]` expands out to a key level and turns there. `[src: easy_daily_bias_mechanical_framework.txt — "I'm always going to frame that reversal off of previous day's high or previous day's low"]`

Direction is set by the side of the level: a key level **above** price reached by `B[0]`'s high → **bearish**; a key level **below** reached by its low → **bullish**. Written below for the **bearish** case, because that is how the source usually presents it.

### 7.1 Reversal context: expansion out to, or near, a key level

TTrades insists the pattern alone is not enough: `[src: easy_daily_bias_mechanical_framework.txt — "I'm not just going to pattern trade this. I want to actually align it with a bias"]`, and names a higher-timeframe key level as the place: `[src: candle_2_closure_foundation.txt — "we want this to occur at a higher time frame key level"]`.

**Trader answer (question 1).** An earlier draft accepted "three continuation closes in a row" as context. The trader rejected it: "No, that's not the correct definition. It's the expansion — expansion out — then the change in state of delivery is the close below the sequence of up-close candles, or [above the] down-close candles, at or near a key level." The run-of-closes condition is removed entirely; there is no switch for it. Context is now:

1. **A key level.** For now, the levels the rules already know, on the bias timeframe (`reversal_key_levels`):
   - `previous_candle`: `B[-1].high`;
   - `swing`: a confirmed `B` swing high inside `bias_poi_lookback_bars` that no later closed `B` bar has traded above;
   - `fvg`: an unfilled bearish `B` fair value gap (3.10) inside the same lookback; its edge is the gap's bottom.
2. **At or near.** `B[0]` has *reached* a level when `B[0].high_so_far` traded through it (a gap: into it), or came within `reversal_level_tolerance_frac * avg_range` of it. **Proposal:** `reversal_level_tolerance_frac = 0.10`. With a tolerance above 0 the level need not be traded through; with 0 it must be. Which level is reported: if any level was traded through, the furthest one traded through; otherwise the nearest one approached. The detail names it and says by how much price traded through it or fell short of it, and lists other levels reached.
3. **Expansion out.** The trader did not define it further. **Proposal** (`rev_expansion_into_level`, `reversal_expansion_test = directional_run`): on the setup timeframe, take the unbroken run of up-close candles that ends at the candle holding `B[0].high_so_far` (or at the candle before it when that candle closed down). This is the series a CISD at the high has to close below (3.11). The move is a directional run when the run has at least `reversal_expansion_min_bars` candles (default 1) **and** the distance from the lowest open in the run to the high is at least `reversal_expansion_min_travel_frac` (default 1.0) times the average range of the last `avg_range_bars` closed setup candles. The setup candle still forming is built from closed `E` bars so the read does not wait for it. With `reversal_expansion_test = off`, reaching the level is sufficient and the measurement is shown as advisory. See open question 30.
4. **Confirmation** is the CISD of stage c3: a close below the run of up-close candles into the high. Because the CISD is anchored at `B[0].high_so_far` and that high is at or near the key level, the CISD is "at or near the key level" by construction. How far past a level the high may run and still count as "at" it is not limited (open question 29).

When a confirmed bias (section 5) points the other way he treats the move as a retracement, not a reversal: `[src: easy_daily_bias_mechanical_framework.txt — "Since I am still bullish, I still want to anticipate this to be a retracement to then trade it higher"]`. This is **not** encoded: the reversal path does not look at `Verdict.bias`.

`Verdict.bias` keeps the section 5 value on the reversal path. A reversal verdict can therefore read `decision = short`, `bias = bullish`. The trader's answer did not address this half of question 1 (now open question 32).

### Stage c1 — key level reached

| Key | Label | TF | Class | Pass condition | Cannot evaluate when |
|---|---|---|---|---|---|
| `data_sufficient` | as section 6 | all | G | as section 6 | — |
| `rev_key_level_reached` | Forming bias candle has expanded to, or near, a key level | B (via E) | S | 7.1 items 1 and 2 | no closed `E` bar in `B[0]` → `None` |
| `rev_expansion_into_level` | The move into the level was a directional run, not a drift | S (via E) | Q; A when `reversal_expansion_test = off` | 7.1 item 3 | fewer than two closed `S` bars → `None` |
| `rev_opposing_run_small` | The wick so far is small | B (via E) | Q | forming-candle classification of `B[0]` is `small` (3.8), with `opposing_run = B[0].high_so_far - B[0].open` | `avg_range` not computable → `None` |
| `rev_formed_early` | The wick formed early in the bias candle | B (via E) | Q | time of `B[0].high_so_far` is before the deadline (`daily_wick_deadline` for a 1D bias, else `wick_time_frac_max` of the candle's duration) | bias candle duration unknown → `None` |

`rev_key_level_reached` replaces the earlier `rev_level_taken` ("has run the previous bias candle's high") and `rev_context_present` (a gate). The reversal path has no gate of its own any more: it is alive whenever `rev_key_level_reached` is `True`. Setting `reversal_key_levels = ["previous_candle"]` and `reversal_level_tolerance_frac = 0` gives the old `rev_level_taken` test back.

Sources: `[src: easy_daily_bias_mechanical_framework.txt — "I can look to trade the reversal if it has a small enough wick"]`; large or late wick → wait for the next candle: `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "if I have a large wick that doesn't support expansion, I'm just going to wait for a new higher time frame candle"]` `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "Does it make sense to enter this late into a candle? No"]`

### Stage c2 — reclaim

| Key | Label | TF | Class | Pass condition | Cannot evaluate when |
|---|---|---|---|---|---|
| `rev_reclaim` | Setup timeframe has closed back below the key level | S | S | a closed `S` bar that closed after `B[0].high_so_far` was made has `close <` the reported key level (a gap: `close <=` the gap's top, its far edge) | no such bar → `False` |

Source: `[src: fractal_model_fundamentals.txt — "the hourly wretched above its previous candle's high into a point of interest and close back in"]`. When the level was only approached, every later setup close is on the trade's side of it, so the first setup bar to close after the high passes this step. The reversal POI required by the state machine is the key level itself (`poi_type = liquidity_target_zone`, or `reaction_zone` for a gap).

### Stage c3 — CISD at the level

| Key | Label | TF | Class | Pass condition | Cannot evaluate when |
|---|---|---|---|---|---|
| `rev_cisd_confirmed` | Change in state of delivery at the level: a close through the run of up-close candles | S (or E, see below) | S | bearish CISD (3.11) anchored at `B[0].high_so_far`, confirmed `<= as_of`, and no higher high since | confirmation frame does not cover `B[0]` → `None` |
| `rev_cisd_swift` | The turn was quick | same | Q | `bars_to_confirm <= cisd_max_bars` | no CISD → `None` |

Confirmation timeframe: `S` by default. With a 1D bias and `as_of` inside the New York AM window, `E` is also accepted (4.3). Source: `[src: easy_daily_bias_mechanical_framework.txt — "have a change in the state of delivery, which confirms that wick high"]`; without it there is no trade: `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "Without that change in the state of delivery there, we cannot confirm this wick high"]`

### Stage c4 — entry-ready structure

Entry trigger, by `entry_mode` (the same three modes as section 6; default `either`):

- **CISD trigger**: the bar that confirmed `rev_cisd_confirmed`.
- **Order-block trigger**: a bearish continuation order block on `E` after that CISD, built exactly as in section 6 (pullback up that does not take the wick high, reaches an `E` POI, closes through its series of up-close candles).

Source for both: `[src: ttrades_fractal_model_trading_candle_2.txt — "Then I can look to trade this reversal lower or look for the continuation that follows"]`

| Key | Label | TF | Class | Pass condition | Cannot evaluate when |
|---|---|---|---|---|---|
| `rev_entry_trigger` | Entry trigger has formed | E | S | per `entry_mode`, trigger bar closed `<= as_of`, inside `B[0]`; the detail names the kind that fired | no CISD → `False` |
| `rev_wick_intact` | The reversal high has not been taken again | B (via E) | Q | no `E` bar after the CISD has `high >` the CISD anchor high | no CISD → `None` |
| `rev_reward_at_least_2r` | Structural level (previous bias candle's equilibrium) is at least 2R away | E, B | A by default; Q when `reward_check_role = quality` | `(entry - S1) >= min_rr * (stop - entry)` with section 8 values, S1 = EQ of `B[-1]` | no trigger → `None` |
| `session_filter_ok` | Inside a kill zone (information) | E | A by default; Q when `session_filter_role = quality` | section 9.1 | — |

If `rev_wick_intact` fails, the path drops back to `c1` and re-anchors on the new high (the opposing run is now larger, so `rev_opposing_run_small` is re-tested).

He adds a preference that cannot be coded from one symbol: `[src: easy_daily_bias_mechanical_framework.txt — "If I'm going to be trading a candle too, I do prefer to have SMT paired with it"]`

---

## 8. Entry, stop, targets

### 8.1 Entry price

- **Default:** the close of the trigger bar on `E` (in practice, the next bar's open). `[src: fractal_model_fundamentals.txt — "enter short on the close, put my stop on this high, and then look for 2R"]`
- **Retest (limit) alternative:** a limit at the trigger order block's level (`Cisd.level`). `[src: fractal_model_fundamentals.txt — "I could look to take an entry on the retest, my stop on the low, and then look for 2 R"]` He uses it when the market entry gives less than 2R. Which to use is his discretion; the checklist reports market entry in `Verdict.entry`. When `reward_check_role = quality` or `target_mode = structural` and `*_reward_at_least_2r` fails, the criterion detail gives the limit price that would give exactly `min_rr` to the structural level S1: long `(S1 + min_rr * stop) / (1 + min_rr)`, short the mirror.

### 8.2 Stop (invalidation)

| Path / mode | Stop |
|---|---|
| Continuation, order-block trigger | low of the trigger's pullback = the new protected low |
| Continuation, CISD trigger | protected low from the entry CISD = low of the setup swing candle |
| Reversal, CISD trigger | `B[0].high_so_far` at the CISD = the wick high |
| Reversal, order-block trigger | high of the trigger's pullback = the new protected high |

The stop follows the kind of trigger that fired, whatever `entry_mode` selected it.

- Source: `[src: fractal_model_fundamentals.txt — "I'd put my stop on a protected low, which is this low out of a fair value gap"]` and `pages/stop_loss_mastery_using_protected_swings_for_precise_invalidations.md`: "Default: Stop at the protected low."
- **Body stop (source rule, conditional).** The stop may move to the body of the swing candle to reach 2R, only when the opposing candles are full-bodied. `[src: the_only_trading_strategy_you_need_for_2026.txt — "put my stop on the bodies because they are nice and fullbodied candles"]` and the same page: "Only use candle body invalidation if there are big bulking opposing candles." "Full-bodied" has no number. **Proposal:** allowed when every candle in the trigger series has `abs(close - open) >= body_stop_min_body_frac * (high - low)`; body stop = lowest body edge of the series. The verdict must say when the body stop is in use. The body stop exists only to reach the minimum reward to the structural level, so it is considered only when that check blocks (`reward_check_role = quality`). With the default advisory check the stop always rests on the protected swing.
- **Buffer beyond the swing:** `[src: fractal_model_fundamentals.txt — "maybe I'll just give it a little bit of room to sweep if it wants to"]`. No amount given. **Proposal:** `stop_buffer = 0`.
- `Verdict.invalidation` text: "trade through {stop} ({what it is})", plus the path-level invalidations from section 9.2.

### 8.3 Targets

**Trader answer (questions 15 and 16).** "That just depends on the RR ... usually you go for a one to two ... keep it simple for right now: if it's a one-to-one or one-to-two ratio for the trade, the user should exit."

**The exit (`target_mode = r_multiple`, default).** `Verdict.targets = (X,)` with `X = entry + target_rr * (entry - stop)` for a long and the mirror for a short. `target_rr` defaults to 2.0; the trader also named 1.0. There is no second target.

**Structural levels (information).** They are still computed, given in R terms in the `*_reward_at_least_2r` detail and drawn as markup ("Structural level 1 / 2"). They do not block and they are not the exit.

Continuation (bullish):

| Level | Price | Source |
|---|---|---|
| S1 | `B[-1].high` | `[src: fractal_model_fundamentals.txt — "if we're expecting price to continue to this previous day high, that's our target"]` |
| S2 | nearest untaken `B` swing high above S1 within `bias_poi_lookback_bars`; none → omit | `[src: easy_daily_bias_mechanical_framework.txt — "we trade into these previous highs on the left here"]` |

How far past S1 to expect depends on the forming bias candle's wick: `[src: easy_daily_bias_mechanical_framework.txt — "With a large wick, I'm not expecting much of a range beyond this level"]`. Rule used: if `B[0]`'s opposing run is `large` (3.8), S1 only.

Reversal (bearish, small wick):

| Level | Price | Source |
|---|---|---|
| S1 | EQ of `B[-1]` | `[src: easy_daily_bias_mechanical_framework.txt — "looking for that EQ or to the previous day's low"]` |
| S2 | `B[-1].low` | same quote |

These two are defined off the previous bias candle. When the key level reached is a swing or a gap, or was only approached, S1 can sit on the wrong side of the entry; the detail then says it is not beyond the entry (open question 29).

**Reversal with a large wick** (not entry-ready under this checklist, listed for completeness): target the open of `B[0]`, then the current low of `B[0]`. `[src: ttrades_fractal_model_trading_candle_2.txt — "I have to adjust my targets looking back towards that opening price and the current candle's low"]`

**Old behaviour (`target_mode = structural`).** `Verdict.targets = (S1, S2)`, S2 omitted when it does not exist. Together with `reward_check_role = quality` this is the rule as it stood before the answer: the verdict stays `watch` until S1 is at least `min_rr` away. Source for the 2R minimum: `[src: fractal_model_fundamentals.txt — "take a lower time frame entry and just use a higher time frame target"]`.

**Projections (optional confluence, not used for decisions).** Fibonacci extension of the bias Candle 2's manipulation leg on `S`, levels −1, −2, −2.5, −4, −4.5. `[src: targets_using_projections_the_fractal_model.txt — "I'm generally looking for price to reach to the -2 or -2.5"]` With a large leg: `[src: targets_using_projections_the_fractal_model.txt — "I'm then going to use the -1 as my target"]` They are confluence only: `[src: targets_using_projections_the_fractal_model.txt — "I personally use them as a confluence to existing liquidity targets"]`. The leg's start ("the high that made that low") is chosen by eye in the source, so projections are not computed.

---

## 9. Session filters, invalidation and downgrade rules

### 9.1 Session and time-of-day filters

All times are New York local (`America/New_York`). TTrades says "Eastern Standard Time" and "EST" throughout; this document assumes he means New York clock time year-round.

**Kill zones stated in the sources — they do not agree with each other:**

| Window | Times | Source |
|---|---|---|
| London | 02:00–05:00 | `[src: reversal_sequence_ttrs_how_to_blend_pd_arrays.txt — "looking between 2 to 5 a.m. and all times are an Eastern Standard Time"]` |
| New York AM | 08:30–11:00 | `[src: reversal_sequence_ttrs_how_to_blend_pd_arrays.txt — "I'm going to focus on 8:30 to 11 for my trading"]` |
| New York AM | 08:30–12:00 | `[src: ict_daily_profile_london_reversal_new_york_continuation.txt — "generally I'm looking at 8:30 to 12 I kind of extend this out to 12 personally"]` |
| New York (indicator demo) | 08:00–11:30 | `[src: intro_to_ttrades_fractal_model_indicator_settings.txt — "let's say I'm only interested in price in the New York session between 8 to 11:30"]` |
| Asia | 20:00–00:00 | written page only: `pages/london_reversal_and_new_york_continuation_daily_profile.md`: "Asia session: 20:00 EST – 00:00 EST". Not a window he trades entries in. |
| New York PM | no times given | named on a slide, never defined |

**Time levels:** 08:30, 09:30, 10:00. `[src: ict_daily_profile_new_york_reversal.txt — "what times am I looking at 8:30 9:30 10"]` 10:00 matters because it opens a 4h candle on futures.

**Macros:** he does not use them. `[src: wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles.txt — "And that's why macros don't even make sense, right?"]` No macro windows are defined anywhere in the files read. No macro filter is implemented.

**`session_filter_ok` (proposal built from the above):**

- If `stack.entry` is 1h or higher: `True` (kill zones are for intraday; 4.3).
- Otherwise: `True` when the trigger bar's close time is inside any window in `kill_zones`. Default `kill_zones = [("02:00", "05:00"), ("08:30", "11:00")]`.
- Before a trigger exists, evaluate on `as_of` so the trader can see whether a trigger now would be inside a window.

**Effect on the decision (trader answer to question 18).** "Let's not worry about the trading window right now, as long as I can recognize the state." The criterion is still computed and shown, but its class is advisory by default (`session_filter_role = advisory`): a trigger outside the kill zones still gives `long` / `short`, and the summary says it is outside. `session_filter_role = quality` restores the old rule (outside a window keeps the verdict at `watch`). Which windows to use is still not settled; it stopped mattering for the decision.

**Early-session rule (source, advisory):** in Asia / early in the day he stays on higher timeframes. `[src: easy_daily_bias_mechanical_framework.txt — "this is when I prefer not to go down to the lower time frames and I like to execute on the higher time frames"]` Not gated separately; the kill-zone criterion flags Asia for intraday stacks.

### 9.2 Invalidation (path returns to `none`)

| Condition | Applies to | Criterion | Source |
|---|---|---|---|
| Bias swing extreme traded through | continuation | `bias_swing_intact` | `[src: cisd_validates_swing_points.txt — "We take out that protected swing. That means this trend is not looking that great"]` |
| Setup timeframe closes through the respect level (EQ / wick midpoint) on the wrong side | continuation | `cont_eq_respected` | 3.9 flip quote |
| Previous bias candle's high/low already taken in `B[0]` | continuation, only when `objective_open_role = gate` (not the default) | `cont_objective_open` | section 6 quote |
| Forming candle is Candle 5 or later | continuation | `bias_candle_index_ok` | 3.3 quotes |
| No key level reached | reversal | `rev_key_level_reached` (a step: the path is simply not alive) | 7.1 |
| New bias candle opens | both | all state is rebuilt from section 5 | — |

### 9.3 Downgrades and resets (path stays alive, decision is `watch`)

| Condition | Effect | Source |
|---|---|---|
| A tagged POI is closed through (FVG filled, order block mean threshold lost) without breaking `respect_level` | drop that POI; back to `c1`; look for the next POI | `[src: easy_daily_bias_mechanical_framework.txt — "we don't respect this fair value gap. So I can simply remove it"]` |
| Setup closure exists but entry CISD never prints and the setup swing low is taken | discard setup; back to `c1`/`c2` | `[src: fractal_model_fundamentals.txt — "I need to wait for a sweep and then a continuation entry"]` |
| Protected swing taken after trigger (trade stopped) | discard setup; idea survives if gates still pass | `[src: trading_candle_3.txt — "the idea isn't invalidated. I just need to have a new setup"]` |
| Entry window expired without a trigger | discard setup; back to `c2` | section 6 entry window |
| CISD was slow (`> cisd_max_bars`) | treat as consolidation; wait for a sweep of the small range and a new, swift CISD | `[src: why_your_continuations_fail_order_blocks_cisd_explained.txt — "It fails. Now, why does it fail? Well, when you take a look, this is actually a consolidation"]` |
| Trigger formed while taking short-term highs/lows | wait for another continuation | section 6 quote |
| Bias Candle 2 expanded (small wick, big body) | conservative entry only | section 6 quote |
| Forming bias candle's wick is large or late (reversal path) | no entry this candle; after it closes, section 5 may give a Candle 2 closure and the continuation path takes over | 7 c1 quotes |
| Protected swing's objective already hit | stop trusting older protected swings | `[src: easy_daily_bias_mechanical_framework.txt — "this swing is only protected until it hits liquidity"]` |

One source alternative is deliberately not encoded: when a POI is closed through he may keep the bias and shrink the target instead of standing down. `[src: fractal_model_fundamentals.txt — "I can either invalidate my bias and not continue to look short"]` That choice is discretionary (open question 17).

---

## 10. Decision mapping

### 10.1 Path selection

1. Evaluate section 5. Evaluate both checklists.
2. The **continuation** path is alive when all its G criteria are `True`.
3. The **reversal** path is alive when `rev_key_level_reached` is `True` (it has no G criteria of its own; the shared ones apply). It is evaluated for both directions; the direction reported is the one that is alive, then the one at the higher stage, then the one whose extreme is more recent.
4. Both paths alive at once is now common: the continuation no longer ends when `B[-1].high` trades, and a reversal is alive whenever price is at or near any key level. **Proposal:** if both are alive, report the one at the higher stage; on a tie, continuation (open question 34).
5. Neither alive: `path_family = "none"`, `stage = "none"`.

### 10.2 Stage

`stage` = the highest stage `cN` for which every **S** criterion of stages `c1..cN` is `True` on the selected path (G criteria are already `True` by 10.1). If no stage qualifies but the path is alive, `stage = "none"` with decision `watch`.

### 10.3 Decision

| Condition | `decision` |
|---|---|
| `data_sufficient` is `False` | `no_trade` |
| No path alive (`path_family = "none"`) | `no_trade` |
| Any G criterion on the selected path is `None` | `no_trade` (summary says what could not be evaluated) |
| Path alive, `stage < c4` | `watch` |
| `stage = c4`, any Q criterion `False` or `None` | `watch` |
| `stage = c4`, all Q criteria `True`, direction bullish | `long` |
| `stage = c4`, all Q criteria `True`, direction bearish | `short` |

A criteria never change the decision. By default that now includes `session_filter_ok`, `cont_objective_open` and `*_reward_at_least_2r` (sections 6, 7, 9.1); each can be switched back to its old class in `config.json`. `entry`, `stop`, `targets` are filled only for `long` / `short`, and for `watch` at `c4` when the only failing Q is `*_reward_at_least_2r` or `session_filter_ok` (possible only when those are switched back to Q).

A `long` / `short` verdict describes a trigger that has formed and whose stop is untaken. It does not check whether price has since travelled to the exit; the entry is the trigger bar's close, which can be well before `as_of` (open question 33).

### 10.4 Mapping to `entry_rules.default_entry_ready_constraints`

| State-machine constraint | Satisfied by |
|---|---|
| `fractal_stage must equal c4` | 10.2 |
| `setup_quality must equal good_setup` | every Q criterion `True` (`bad_setup` when stage is `c4` and a Q fails; `no_setup` below `c4`) |
| `htf_bias must be directional and aligned` | continuation: `Verdict.bias` equals the trade direction. Reversal: `rev_key_level_reached` (the trade direction may oppose `Verdict.bias`; see open question 32) |
| `poi_type must not equal none` / `poi_validity must be true` | continuation: `cont_poi_tagged` and `cont_eq_respected`. Reversal: `rev_key_level_reached` and `rev_reclaim` |
| `ltf_confirmation_present must be true` | `cont_entry_cisd_confirmed` / `rev_cisd_confirmed` |
| `invalidation_state must not equal broken` | `bias_swing_intact` and `cont_protected_swing_intact` / `rev_wick_intact` (`at_risk` is not defined by the source; unused) |
| `kill_zone_alignment must not equal misaligned` | `session_filter_ok` (`neutral` when the entry timeframe is 1h or higher). Enforced only when `session_filter_role = quality`; by default the companion reports it and does not enforce it |

### 10.5 Top-down read (output only)

`Verdict.read`, `Verdict.why` and `Verdict.waiting_for` (`read.py`) restate the result for the trader: one line per role, bias first, for the selected path only, with a status (confirmed / waiting / failed / not applicable). They change no rule and no decision. Candle numbers in them are the trader's (3.3), never the stage names of 2.3: the bias line says which candle of the bias swing is forming (Candle 3 or 4 on the continuation path, Candle 2 on the reversal path); the setup line counts from the setup swing candle on the continuation path and gives no number on the reversal path, where the rules define none. A quality criterion that is `False` marks its timeframe's line failed as soon as it is known, although it only blocks at `c4` (10.3).

### 10.6 Side asked for, steps and position plan (output only)

**Side asked for.** `evaluate(..., direction=None | "long" | "short")`. `None` is 10.1 unchanged. With a side, only that side's paths compete in 10.1: the continuation when the bias closure points that way (`bias.side`), and the reversal evaluated for that side; the stage and the decision then follow 10.2 and 10.3 as written. Nothing else changes: every criterion passes or fails exactly as it does without a side, except that the reversal checklist reported is the asked side's and `session_filter_ok` is judged on the selected path's trigger, as always. No path alive on that side gives `no_trade` with `path_family = "none"`; the read and the steps then name what would open a route, which is always the reversal: the nearest key level of 7.1 the forming bias candle has not reached, with its price and distance. `Verdict.requested` carries the side, `Verdict.idea` the side of the idea told (`""` when none), and `Verdict.auto_note` one line when 10.1 without a side would have told the other direction.

**Steps** (`Verdict.steps`, `plan.py`). The selected path's **S** criteria in order, bias timeframe first, each `done`, `next`, `later` or `blocked`:

| Path | Steps (criterion that makes each one `done`) |
|---|---|
| continuation | bias swing confirmed (`bias_cisd_confirmed`); pullback to a POI (`cont_poi_tagged`); setup closure (`cont_setup_closure`); entry (`cont_entry_trigger`). When only a continuation order block may be entered (mode `conservative`, or the bias Candle 2 expanded) the entry CISD (`cont_entry_cisd_confirmed`) is its own step before the entry |
| reversal | key level reached (`rev_key_level_reached`); reclaim (`rev_reclaim`); entry (`rev_entry_trigger`), with the CISD (`rev_cisd_confirmed`) as its own step before it in mode `conservative` |

The first step that has not happened is `next`, and it alone carries the exact condition and, where the rules wait on one price, that price: the bias-swing CISD level, the nearest setup POI (or the bias order block's mean threshold once the forming setup candle is inside it), the Candle 3 body edge, the key level's hold price, the CISD level, the top of the entry order block. A **Q** criterion that is `False` marks the last finished step of its timeframe's line `blocked` (as 10.5 marks that line failed); at `c4` with a failing Q nothing is `next`. A setup closure whose entry window passed without a trigger puts the setup closure back as `next`. With no path alive the steps are where the read stops (`blocked`) followed by the reversal route(s): `next` for a side asked for, `later` for both sides without one.

**Position plan** (`Verdict.plan`).

- *triggered*: the trade plan of section 8 for the selected trigger. Told for `long` / `short`, and for `watch` at `c4` when the only failing Q are `*_reward_at_least_2r`, `session_filter_ok`, `cont_entry_window_open` or `cont_protected_swing_intact` (the trigger was a valid entry when it formed). `outcome` scans the closed entry bars after the trigger bar: `stopped` at the first bar that trades through the stop, `target_reached` at the first bar that reaches `targets[0]`, the stop winning a bar that does both; otherwise `open`. `r_now` = (last close - entry) / risk.
- *planned*: nothing has triggered and the CISD entry is allowed. Entry = the level the trigger has to close through (continuation: the entry CISD level of the active setup closure; reversal: the nearest pending CISD level), stop = the current structural extreme (setup swing low; reversal wick low) minus `stop_buffer`, target = entry + `target_rr` x risk (or the structural first level in `target_mode = structural`). The real entry will be the trigger bar's close, beyond that level, and all three move if price makes a new extreme first. A trigger that exists below `c4` (a reversal that turned before its reclaim) is told as planned with its own levels.
- no plan when those levels cannot be computed: no setup closure or key level yet, only an order-block entry is allowed, the entry window has passed, or no path is alive.

None of this answers open question 33. The decision stays `long` / `short` after the exit has traded; the plan's `outcome` and `r_now` only make that visible, and the window words the suggestion from them.

---

## 11. Parameters

| Parameter | Default | Basis |
|---|---|---|
| `target_rr` | 2.0 | **Trader answer** (questions 15, 16): the exit multiple; 1.0 is the other value named |
| `target_mode` | `r_multiple` | **Trader answer**; `structural` is the old rule |
| `min_rr` | 2.0 | **Source** ("minimum of 2R"); now the threshold of the advisory structural check |
| `reward_check_role` | `advisory` | **Reading of the trader answer** (questions 15, 16); `quality` is the old rule |
| `objective_open_role` | `advisory` | **Reading of the trader answer** (question 16); `gate` is the old rule |
| `session_filter_role` | `advisory` | **Trader answer** (question 18); `quality` is the old rule |
| `cisd_max_bars` | 3 | **Source** ("1 2 maybe three") |
| `wait_for_clean_continuation` | `true` | **Source** ("wait for a continuation move off of those levels"); `false` is the old trigger choice |
| `objective_at_trigger_role` | `quality` | **Source** (reason three, "higher time frame target has already been taken"); `advisory` reports only (question 36) |
| `entry_latest_candle_frac` | 0.75 | **Source** (2026-10-24 video); 0.5 is the strict "first half"; 1.0 switches it off (question 37) |
| `swing_lookback_roles` | 3 candles of the next role up, including current | **Source** |
| `kill_zones` | 02:00–05:00, 08:30–11:00 New York | **Source**, but sources conflict on the New York end time (11:00 / 11:30 / 12:00) |
| `entry_mode_continuation`, `entry_mode_reversal` | `either` | **Trader answer** (question 14); `conservative` and `aggressive` remain selectable |
| `entry_either_pick` | `first` | Proposal (open question 28) |
| `sweep_reclaim_max_bars` | 0 on `B`; 3 on `S`, `E` | Proposal |
| `avg_range_bars` | 20 | Proposal |
| `wick_yardstick` | `avg_range` | **Trader answer** (question 2): keep it; `body` is the alternative he described |
| `wick_small_frac` | 0.25 of `avg_range` | Proposal accepted by the trader ("yeah, that works") |
| `wick_large_frac` | 0.50 of `avg_range` | Proposal accepted by the trader — loosely anchored to "almost half" |
| `wick_body_small_frac` | 0.5 of the candle's body | Proposal (only with `wick_yardstick = body`; open question 31) |
| `wick_body_large_frac` | 1.0 of the candle's body | Proposal (only with `wick_yardstick = body`; open question 31) |
| `closed_wick_large_frac` | 0.50 of the candle's range | Proposal |
| `wick_time_frac_max` | 0.50 of the candle's duration (non-daily bias) | Proposal — anchored to "almost half the time" being too much |
| `daily_wick_deadline` | 11:00 New York (1D bias) | Proposal — from "early New York or before New York" |
| `eq_tolerance_frac` | 0 | Proposal |
| `fvg_min_size` | 0 | Proposal |
| `bias_poi_lookback_bars` | by bias timeframe: 1h → 3 days of bars; 4h → 3 weeks; 1D → 3 months (about 66 bars); 1W → 3 months (13 bars); 1M → 12 bars | 1h–1W: his three-candle rule applied through his pairings, bar counts are my arithmetic. 1M: proposal (nothing pairs above monthly) |
| `reversal_key_levels` | previous candle, swing, fvg | **Trader answer** (question 1) says "a key level"; which levels count is my reading |
| `reversal_level_tolerance_frac` | 0.10 of `avg_range` | Proposal for "at or near" (open question 29) |
| `reversal_expansion_test` | `directional_run` | Proposal for "expansion out" (open question 30) |
| `reversal_expansion_min_bars` | 1 | Proposal (open question 30) |
| `reversal_expansion_min_travel_frac` | 1.0 of the average setup-timeframe range | Proposal (open question 30) |
| `body_stop_min_body_frac` | 0.6 | Proposal |
| `stop_buffer` | 0 | Proposal |

---

## 12. Open questions for the trader

Questions 1, 2, 14, 15, 16 and 18 were answered by the trader on 2026-11-12 (spoken, transcribed). Each keeps its number and shows the original question, the trader's words and the rule that resulted. The reading of each answer is mine; where it left room the behaviour is a `config.json` switch. Questions 28 to 34 are new: they were raised by implementing the answers.

1. **ANSWERED (first half). What makes a reversal tradable, and what is "bias" on a reversal day?** I had chosen: three continuation closes in a row, or the sweep also reaching a bias-timeframe swing/FVG. *Trader:* "No, that's not the correct definition. It's the expansion — expansion out — then the change in state of delivery is the close below the sequence of up-close candles, or [above the] down-close candles, at or near a key level." *Rule now (7.1):* the run-of-closes condition is removed with no switch. Context = the forming bias candle has reached, or come near, a key level (previous bias candle's high/low, untaken bias-timeframe swing, unfilled bias-timeframe fair value gap); confirmation = a CISD anchored at that extreme. `rev_level_taken` and `rev_context_present` became `rev_key_level_reached`; `rev_expansion_into_level` is new. What "near", "expansion out" and "key level" mean precisely is in questions 29 and 30. The second half (what `Verdict.bias` should read on a reversal) was not answered: question 32.
2. **ANSWERED. Small versus large wick has no number in the source.** I proposed small ≤ 25% and large ≥ 50% of the 20-candle average range of that timeframe, measured as the opposing run from the candle's open. *Trader:* "Yeah, that works. A small wick is kind of relative to how big the body is, and a large wick is relative to how big the body is — I think that's what he was referencing." *Rule now (3.8):* the default is unchanged (`wick_yardstick = avg_range`). The body-relative reading is available as `wick_yardstick = body` with its own thresholds, which are proposals (question 31).
3. **"Early in the candle" has no number, and is session-based for the daily.** I proposed: daily wick must be in by 11:00 New York; other bias timeframes within the first half of the candle. The daily futures candle is already about two-thirds elapsed at 09:30, so one fraction cannot serve both. Confirm or replace.
4. **EQ or wick midpoint?** He uses half of the wick for large-wick reversal candles and half of the whole candle otherwise, but in at least one large-wick example he chose the whole candle "because it makes sense with this candle type". I switch on a closed-wick ≥ 50% of range test. Is a single fixed choice preferable?
5. **How strict is "respect"?** I fail the continuation on any setup-timeframe close beyond the level, with zero tolerance. He sometimes allows "a little bit" more for structure. Do you want a tolerance band?
6. **Candle 3 closure body edge.** "Closes over the body of candle 2" versus "closes below the opening price in candle 2". I used the far body edge, which satisfies both. Confirm.
7. **Outside bars and conflicting reads.** A bias candle that takes both sides and closes inside, or one that is a bullish Candle 3 closure and a bearish reversal closure at once: I return neutral. He only says "less ideal" / "I will wait for another candle".
8. **Inside bar = neutral.** After an inside bar he waits for another candle. I therefore drop to neutral even if the prior bias was strong. Should the earlier bias carry instead?
9. **Which candles make up "the series" for CISD.** I use the unbroken run of opposite-close candles ending at the extreme and the highest open among them. He sometimes ignores small candles or uses a whole up-down-up leg. Dojis are folded into the run. Acceptable?
10. **Does a CISD need displacement?** He wants a "V-shape". I only test speed (≤ 3 bars, his number). No size or body requirement is given. Should one be added?
11. **Is the body-direction check on a setup Candle 2 closure a hard requirement?** He distrusts bearish-bodied bullish closures and doji closes but the formal definition does not exclude them. I made it a quality check (blocks entry-ready, keeps watching).
12. **Relevant versus failure swings.** He says there is no mechanical rule for "valid separation". I accept any confirmed swing inside the lookback as a POI, which will accept swings he would reject. Do you want a minimum separation (and in what unit)?
13. **Bias-timeframe POI lookback.** His rule is three candles of the next timeframe up; that timeframe is outside a three-role stack. I converted it to bar counts and invented 12 bars for a monthly bias.
14. **ANSWERED. Entry mode default.** The playbook video allows entry on the entry-timeframe CISD; the 2026 video says to wait for a continuation order block. I had defaulted to the conservative rule for both paths. *Trader:* "Both can reach you at the same time — you're going to grab a CISD or a continuation order block." *Rule now (6 and 7, stage c4):* `entry_mode = either` is the default on both paths: whichever trigger confirms first counts, and the detail says which fired. `aggressive` and `conservative` stay selectable. A consequence I did not expect is in question 28.
15. **ANSWERED. 2R versus structural targets.** I gated on the structural first target being at least 2R away and output the structural levels as targets. *Trader:* "That just depends on the RR ... usually you go for a one to two ... keep it simple for right now: if it's a one-to-one or one-to-two ratio for the trade, the user should exit." *Rule now (8.3):* `Verdict.targets[0]` = entry ± `target_rr` × risk, default 2.0, 1.0 selectable; no second target. The structural levels are reported in R terms and drawn, as information. `*_reward_at_least_2r` is advisory (`reward_check_role`); `target_mode = structural` with `reward_check_role = quality` is the old rule.
16. **ANSWERED (by the same words as 15). Continuation after the first target is hit.** I ended the continuation path once `B[0]` traded through the previous bias candle's high/low. *Rule now (6, stage c1):* that level is no longer the target, so `cont_objective_open` is advisory and the path stays alive after it trades (`objective_open_role = gate` restores the old rule). This is my inference from the answer to 15, not something the trader said about this gate directly.
17. **POI closed through.** He gives two options: drop the bias, or keep it and cut the target. I drop the POI and keep looking for another one while the respect level holds. Confirm.
18. **ANSWERED (deferred). Kill-zone end time and which sessions.** Sources give 11:00, 11:30 and 12:00 for New York AM. *Trader:* "Let's not worry about the trading window right now, as long as I can recognize the state." *Rule now (9.1):* `session_filter_ok` is computed and shown but advisory (`session_filter_role`); a trigger outside the windows still gives `long` / `short`. Which windows are right is still undecided and will matter again if the filter is switched back on.
19. **Session-dependent confirmation timeframe.** For a daily bias he confirms on 1h/30m in Asia and London and drops to 15m/5m in New York. A fixed three-role stack cannot switch timeframes. I allow the reversal CISD on the entry timeframe during New York for a daily bias only. Is that enough?
20. **Setup swing must be inside the forming bias candle.** I ignore protected swings formed before the bias candle opened, though he occasionally enters "positionally" at the open off one. Should those count?
21. **Entry window.** I allow the trigger only in setup Candle 3 (plus Candle 4 after a strong Candle 3). He takes later continuations at times ("another continuation") while calling it chasing. Keep it strict?
22. **Stacks whose pairings he never states** (for example 1D / 15m / 1m, or 1W / 1D / 5m). I let them run and flag them with an advisory criterion. Should unstated stacks be blocked?
23. **SMT divergence is left out entirely.** He uses it to accept order blocks without a sweep, to prefer Candle 2 trades, and to pick the weaker of two correlated symbols. It needs a second symbol's bars. Is a single-symbol companion acceptable, knowing it will reject some setups he would take?
24. **Protected swing broken by wick or by close?** Not stated. I use any trade-through, consistent with a stop resting on the swing.
25. **"Body stop" eligibility.** "Big bulking opposing candles" has no number; I used body ≥ 60% of range for every candle in the series.
26. **Breakers, inversion FVGs, projections, daily profiles (London reversal / New York reversal / seek and destroy) and the weekly profile are defined in the source but not used by the checklist.** Tell me if any should become criteria.
27. **"EST".** I read every stated time as New York clock time including during daylight saving.
28. **"Either" mode: first or latest trigger, and is it just the CISD entry?** As the two triggers are defined, the continuation order block can only form after the entry CISD. So "whichever confirms first" is always the CISD entry when that entry is allowed, and `either` behaves like `aggressive` with one exception: when the bias Candle 2 expanded the CISD entry is not allowed and the order block is the first trigger. In the 2025 sweep 144 of 149 long/short checks on 1D / 1h / 5m fired on the CISD. I report the first live trigger and keep reporting it at later checks (`entry_either_pick = first`), which means the entry price can be stale and the stop wide; `latest` reports the newest live trigger instead (fresher price, tighter stop). Which do you want? And should the order block be preferred once it exists?
29. **"At or near a key level": how near, which levels, and how far past?** I accept a level as reached when price traded through it or came within 10% of the 20-candle average bias-timeframe range (`reversal_level_tolerance_frac`, a proposal). Key levels are the previous bias candle's high/low, untaken bias-timeframe swings and unfilled bias-timeframe gaps; nothing else (no session highs/lows, opens, order blocks, higher timeframes outside the stack). There is no limit on how far past a level price may run and still count as "at" it. When several levels are reached I report the furthest one traded through, else the nearest one approached, and the reclaim step is judged against that one. The structural levels of a reversal (equilibrium and far side of the previous bias candle) are still defined off the previous candle even when the key level is a swing or a gap. In the 2025 sweep on 1D / 1h / 5m, 17 of 30 long reversal trades came from a level that was approached but not traded through, against 4 of 39 shorts. Confirm or change each of these.
30. **"Expansion out" — what I chose.** You did not define it. I test the setup-timeframe candles leading into the extreme: the unbroken run of candles closing toward the level that ends at the extreme (the same series the CISD closes through) must have at least 1 candle and must have travelled at least 1.0 times the average setup-timeframe range (20 candles) from its first open to the extreme. It is a quality check (`rev_expansion_into_level`): failing it keeps the verdict at `watch`. `reversal_expansion_test = off` makes reaching the level sufficient. It failed in 192 of the 672 reversal checks that reached stage c4 on 1D / 1h / 5m. Is a run of candles the right picture of "expansion", and is one average candle of travel the right size?
31. **Body-relative wick thresholds.** With `wick_yardstick = body` I propose small ≤ 0.5 × body and large ≥ 1.0 × body, where body is the forming candle's `abs(last - open)`. Right after a reversal turns the body is tiny, so this yardstick calls nearly every reversal wick large until price has moved away. Is that the intent, or should the body be the previous closed candle's?
32. **What should `Verdict.bias` read on a reversal?** Unanswered half of question 1. It keeps the closure-based value, so a reversal short can show `bias = bullish`. The reversal path also ignores a confirmed opposite bias, although TTrades treats that case as a retracement.
33. **A verdict stays `long` / `short` after the move has happened.** The entry is the trigger bar's close. Nothing switches the verdict off once price has reached the exit, and a reversal trigger has no entry window. In the 2025 sweep on 1D / 1h / 5m the median time between the trigger and the first check that reported it was 85 minutes, and in 45 of 96 trades price had already traded 1R in favour by that first check. Should a verdict expire (after N entry bars, or once the exit price has traded), and should the entry shown be the current price?
34. **Two paths alive at once.** Now that the continuation survives the previous high/low being taken and a reversal is alive near any key level, both are often alive together, sometimes in opposite directions. I report the path at the higher stage and prefer the continuation on a tie. Is that the order you want?

Questions 35 to 37 come from the entry rules added on 2026-11-12 (protected swings, and consolidations read the way "Why Your Continuations Fail" reads them). In the 2025 sweep on 1D / 1h / 5m they cut continuation trades from 27 to 6. At 2R, measured from the first check that reported each trade, the continuation trades went from 8 wins / 16 losses to 3 / 3. `cont_objective_open_at_trigger` failed at 124 checks, `cont_trigger_v_shape` at 44 and `cont_not_inside_consolidation` at 38. Reversal trades are unchanged.

35. **Is a slow close-through the whole definition of a consolidation?** I follow the video: an entry CISD that needs more than `cisd_max_bars` bars turns the pullback into a range (low = its low, high = the top of the leg), and only a breakout plus a new continuation, or a sweep of the low (a new setup), gets out of it. The video also calls a pullback that "cannot close above this level" a consolidation before any close-through (@07:00); the engine has no trigger then anyway. Two things I chose: the range high is the leg's top (the bar before the down-close series), and the breakout is any close above it after the slow close-through. Right?
36. **Higher-timeframe target taken before entry: block or inform?** The source (reason three) says don't take the continuation. Question 16's reading kept the path alive after the previous high is taken. Both now hold: the path stays alive (`cont_objective_open` advisory), but a trigger formed after the target was taken is `watch` (`cont_objective_open_at_trigger` quality). The source on ADR says a continuation past the previous high can still work while range is left (`knowledge/second_brain/wiki/playbooks/ttfm-ranges-adr-dealing-range-eq.md`). Keep it as quality until an ADR check exists?
37. **How late in the candle is too late?** 0.75 (the source's "three quarters, wait for the next candle") is the default. The source also says "first half if you want to make it mechanical". Which one?

---

## 13. Sources

Transcripts read in full (all TTrades' own videos): `fractal_model_fundamentals`, `equilibrium_for_expansions`, `easy_daily_bias_mechanical_framework`, `candle_2_closure_foundation`, `trading_candle_3`, `cisd_validates_swing_points`, `candle_3_closure_ttrades_fractal_model`, `wick_size_matters_the_key_to_understanding_reversal_and_expansion_candles`, `master_candlestick_wicks_the_key_to_catching_reversals`, `the_best_timeframe_for_ttrades_fractal_model_simple`, `protected_swings_understanding_trend_and_invalidations`, `timeframe_alignment_how_to_align_timeframes_for_expansion`, `intro_to_ttrades_fractal_model_indicator_settings`, `ttrades_fractal_model_trading_candle_2`, `ttrades_fractal_model_trading_candle_4`, `trade_continuations_using_order_blocks`, `trade_continuations_using_breaker_blocks`, `why_your_continuations_fail_order_blocks_cisd_explained`, `targets_using_projections_the_fractal_model`, `which_swing_highs_and_lows_matter_in_trading`, `the_only_trading_strategy_you_need_for_2026`, `ttrades_scalping_model_simple_day_trading_strategy`, `ttrades_swing_trading_model_simple_strategy`, `higher_timeframe_analysis_for_trading_aligning_expansion_candles`.

Read in part or searched for specific rules: `trade_like_ttrades_top_down_analysis` (first half), `next_day_model_fractal_way_to_get_bias_for_trading` (first half), `reversal_sequence_ttrs_how_to_blend_pd_arrays` (first third), `trading_the_4_hour_power_of_three_ohlc_olhc` (opening), `ict_daily_profile_new_york_reversal`, `ict_daily_profile_london_reversal_new_york_continuation`, `how_to_actually_trade_inversion_fair_value_gaps_ifvg`, `ttrades_fractal_model_inversion_intraday_strategy` (time and session passages only).

Not used: third-party interviews and recaps in the folder (`ap_...`, `gxtradez_...`, `nickdoesfutures_...`, `afyz_...`, `dtr_c2u_...`, `the_ote_trader_...`, `a_simple_3_step_...`, `a_complete_trading_framework_...`), trade reviews and weekly recaps, the four "phases of price" videos, and the SMT video. The 63 files under 1 KB (most named `*_ict_concepts.txt`) and contain generated topic labels, not transcripts; they were not used.

Pages read in `artifacts/ttrades/pages/`: `stop_loss_mastery_using_protected_swings_for_precise_invalidations`, `understanding_wick_sizes_reversals_and_expansion_candles_in_price_action`, `easy_daily_bias_a_mechanical_trading_framework`; others searched for numbers and session times only.

Repo drafts checked against the transcripts: `knowledge/ttfm_video_corpus/indicator_alignment_notes.md` (consistent with the transcripts), `results/indicator_specs/*.json` (acceptance checks reused where the transcripts support them: wick-to-wick EQ, no entry-ready before bias + POI + closure, Candle 3 closure only when Candle 2 did not qualify, bar-close confirmation), `results/rulepacks/daily_bias_c123_map.json` (its bullish/bearish POI halves are reversed relative to the source; see 3.9).
