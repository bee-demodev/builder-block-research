---
title: "TTrades Fractal Model + Inversion (Intraday Strategy)"
type: ttrades-source
slug: ttrades_fractal_model_inversion_intraday_strategy
source: youtube
youtube_id: 4jU547ocod4
youtube_url: https://www.youtube.com/watch?v=4jU547ocod4
partition: educational_youtube
duration_min: 18
recorded: unknown
format: lesson
speakers: [ttrades]
instruments: [NQ, ES]
timeframes: [1D, 4h, 1h, 15m, 5m, 1m]
concepts: [fractal-model, ifvg, timeframe-pairing, cisd, entry, stop-placement, targets, trade-management, candle-2, consolidation, smt, ttfm-indicator, time-of-day]
transcript: "[[../../ttfm_video_corpus/transcripts/ttrades_fractal_model_inversion_intraday_strategy.txt]]"
page: "none"
confidence: high
---

# TTrades Fractal Model + Inversion (Intraday Strategy)

## TL;DR
Entry refinement inside the TTFM hourly/5m model: once the hourly candle shows a sweep and close back in (candle 2 closure) and the 5m CISD aligns, the indicator prints a T-spot (where the HTF wick should form); inside the T-spot, drop to 1m and wait for an inversion (close through an FVG / series of candles) to get on side with risk at the wick. Targets are 2R or HTF targets; optional time-based exit at the end of the hourly expansion candle (e.g. 11:00). The same structure scales: daily/hourly model with a 15m inversion. Uses his TTrades indicator with settings locked to hourly and 5m.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | The fractal model's goal is to anticipate one HTF candle's OHLC / OLHC for bias, then use the LTF for entry. | fractal-model | stated | 00:31 | "my whole goal is to anticipate one candle's open high low close or open low high close" |
| 2 | A sweep of the prior candle and a close back inside lets you anticipate the next candle to expand the other way. | candle-2 | stated | 00:45 | "with the sweep of this first candle and the closure back in then I can anticipate this candle to continue lower" |
| 3 | Pair hourly with 5m and wait until both are aligned in the same direction (5m closes through the series of opposite-close candles). | timeframe-pairing | stated | 00:58 | "I will wait until those time frames are aligned in the same direction" |
| 4 | The T-spot is the area where the HTF wick is expected to form; look for LTF entries there, at a PD array / POI. | fractal-model | stated | 01:14 | "the t-spot is the area in which I expect this higher time frame Wick to form" |
| 5 | Inside the T-spot, use a 1m inversion to get on side with risk at the wick, then trade the HTF expansion. | ifvg | stated | 01:44 | "I will look in that t-spot for a 1 minute inversion which allows me to get on side with my risk on this High" |
| 6 | With a conflicted bias (bullish structure but previous day high taken and reversing), use the daily profile to decide. | daily-profile | stated | 02:28 | "with a conflicted bias we can go ahead and use the daily profile to see what is going on" |
| 7 | Failure swings are generally a good target to trade back to. | targets | stated | 02:44 | "we are just creating failure swings right which generally are a great Target to trade back to" |
| 8 | When the range is already large, do not expect a large wick and further expansion; target liquidity around the daily open instead. | targets | stated | 02:52 | "when we have a large range already we're not really expecting price to form a large Wick" |
| 9 | Do not take the 5m model until the 5m closes through the series of opposite candles that swept the level. | cisd | stated | 03:20 | "we have not closed through this series of down Clos candles that swept out the low" |
| 10 | If the HTF candle still lacks a wick when the T-spot prints, expect a retrace into the T-spot to put in the wick before expansion. | fractal-model | stated | 03:36 | "we lack a higher time frame Wick we can then anticipate price to retrace down to put in a higher time frame Wick" |
| 11 | Lock the indicator settings to hourly and 5m so the model stays the same when dropping to 1m. | ttfm-indicator | stated | 03:57 | "have them locked to the hourly and 5 minutes so I can drop down to the lower time frames" |
| 12 | The inversion requires a candle close over the level; wait for it. | ifvg | stated | 04:13 | "do we have an inversion out of this t-spot well we would need a close over this level" |
| 13 | Prefer the stop at the swing low rather than waiting for another close; target 2R or hold for HTF targets. | stop-placement | stated | 04:30 | "I prefer to put my stop at the swing low right instead of waiting for another close above" |
| 14 | Once the inversion closes, expect the wick to hold, giving invalidation for the whole HTF candle. | trade-management | stated | 05:11 | "once closed over I'm anticipating this Wick to hold which gives me an invalidation throughout the duration of this higher time frame candle" |
| 15 | Expansion candles usually close at their high or low, so a time-based exit at the HTF close (e.g. 11:00) is valid for runners. | trade-management | stated | 05:18 | "expansion candles they usually close in the high or the low" |
| 16 | No inversion and no sweep / relevant POI yet means wait. | entry | demonstrated | 06:39 | "we also have not swept out any lows or hit a relevant point of Interest" |
| 17 | Enter on the inversion close or on its retest; prefer the retest when the target is a nearby short-term high (to get 2R). | entry | stated | 07:08 | "I can choose to look for an entry on the close or on the retest" |
| 18 | Repeated failure to displace out of a range (e.g. three drives at the previous day low) marks it as a consolidation; trade from its high/low. | consolidation | stated | 08:32 | "see how we continue to fail to displace out of this range" |
| 19 | In a consolidation, want a run of a high before trading lower (protected high). | consolidation | stated | 11:13 | "if we have a consolidation we want to see a run of a high before trading that lower" |
| 20 | SMT (ES takes highs, NQ does not) shows weakness and gives another chance to get on side with an inversion. | smt | stated | 11:29 | "ES was taking these highs while NQ wasn't which shows its weakness" |
| 21 | If the wick/invalidation already formed before the new HTF open (inversion into the open, 0.5 of the 5m range held), enter at the open with stop on that low. | entry | stated | 13:46 | "when I have an invalidation very close to the opening price that's when I can go ahead and look for an entry off the open" |
| 22 | If price trades below that low after the open, it is consolidating, not expanding. | expansion | stated | 14:37 | "if it goes open low below this low then it's already just consolidating" |
| 23 | Later entry on a further CISD / order block needs a stop at least on the body and more range for 2R. | stop-placement | stated | 15:10 | "I need my stop at least on the body down here" |
| 24 | The model is fractal: daily/hourly model with a 15m inversion works the same way. | timeframe-pairing | stated | 15:35 | "let's talk about a daily and hourly model and then using a 15-minute inversion" |
| 25 | A large T-spot makes a positional entry poor risk-to-reward; wait for price to come back into it. | risk | stated | 16:09 | "it is a bit large right so this is not something where I want to take a positional entry" |
| 26 | Do not trade if price runs all the way to the target highs before coming back; the target must stay open. | targets | stated | 16:33 | "I wouldn't want to trade this if it trades all the way to the highs and then back in" |
| 27 | Inversions are not pattern trading; take them only in context (toward the target after a sweep). | ifvg | stated | 16:54 | "this isn't just pattern trading right I don't want to just take this cuz we have inversion forming in here" |

## Definitions
- **T-spot**: indicator-printed zone where the HTF candle's wick is expected to form; entries are sought inside it (01:14).
- **Inversion (1m)**: a close through an opposing FVG / level inside the T-spot, used as the entry trigger (01:44, 04:13).
- **Time-based exit**: closing runners at the end of the HTF expansion candle (e.g. 11:00 for the 10:00 hourly) (05:24).
- **Positional entry**: entry before price returns to the T-spot, stop beyond the whole structure (16:12).

## Procedure / checklist
1. Hourly: sweep of the previous candle and close back inside (candle 2 closure) (00:45, 03:06).
2. 5m: wait for CISD, close through the series of opposite-close candles; now aligned; indicator prints the T-spot (03:20).
3. Find a PD array / POI in the T-spot (01:24).
4. Drop to 1m (settings locked to 1h/5m); wait for a sweep / POI and an inversion close (04:08).
5. Enter on close or retest; stop at the swing extreme; target 2R, HTF target, or time-based exit at the hourly close (04:30, 05:24).
6. Variant: if invalidation is already formed before the new hourly open, enter at the open (13:46).
7. Same steps on daily/1h with a 15m inversion (15:35).

## Worked examples
### Example 1: hourly/5m bearish off previous day high (02:12-05:45)
- Bullish structure but previous day high and a swing high swept; hourly reversal, up-close candles respected in a downtrend; failure swings below as target; large range, so target liquidity near the daily open.
- Hourly closure; 5m waits for close through down-close candles; HTF lacks a wick so expect a retrace into the T-spot. 1m: hourly lower wick forms, inversion close, stop at the swing, 2R hit and trades through failure swings; time-based exit at 11:00 shown.

### Example 2: NQ 10:00 long from consolidation low (05:45-08:17)
- Consolidation range low taken, hourly sweep and close back inside; expect 10:00 (new 4h candle) higher. 5m already aligned, T-spot printed. 1m: no inversion or sweep at first; then low swept with an inversion, close over; entry on retest, stop on the low, 2R; just misses TP then hits. Trade window 10:00-11:00.

### Example 3: previous day low three drives, 10:00 hourly (08:17-10:31)
- Consolidation into the new day, previous day low swept twice (three drives), equal highs above; expect the 10:00 hourly to trade higher. 5m closure through down-close candles; 1m T-spot already formed the wick; first inversion missed (waiting for 5m), second inversion: limit on retest, stop below low, 2R or to 11:00. Not filled; price expands and closes at the high: a missed trade.

### Example 4: bearish hourly with ES/NQ SMT (10:31-12:31)
- Hourly sweep and close back in, CISD, T-spot. 1m: no clean inversion; price consolidates without running a high. SMT: ES takes highs, NQ does not; bullish FVG inverted; entry on close or retest, stop on the high, 2R hit; continuation lower; hourly expansion candle closes near lows (~10:00 noted).

### Example 5: reversal off previous day low, entry at the open (12:31-15:30)
- Downtrend, previous day low swept, close through the down-close candles; failure swings above. 5m confirmation; a second closure out of the CISD retest / FVG; 0.5 of the range should hold. Invalidation is close to the opening price, so on 1m, with an inversion going into the open, enter at the new HTF open with stop on the low; move higher. Alternative later entry on a CISD / order block with stop on the body; 2R after a retracement.

### Example 6: daily/hourly model with 15m inversion (15:30-17:40)
- Daily: equal highs as target, sweep and close; expect expansion. Hourly T-spot is large, so no positional entry; wait for a return while highs stay untouched. 15m: bearish FVG inverted after lows taken; entry, then a second inversion entered on retest for 2R; both hit 2R.

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:11 | Intro: 1m inversion inside the hourly/5m model, uses his indicator |
| 00:31 | Recap: OHLC bias, alignment, T-spot, 1m inversion |
| 02:12 | Example 1: bearish off previous day high, time-based exit |
| 05:45 | Example 2: NQ 10:00 long |
| 08:17 | Example 3: three drives, missed fill |
| 10:31 | Example 4: SMT ES vs NQ |
| 12:31 | Example 5: entry at the HTF open |
| 15:30 | Example 6: daily/hourly with 15m inversion |
| 17:40 | Outro |

## Mistakes and warnings
- Entering before the 5m alignment close (03:20).
- Taking an inversion as pattern trading without context (16:54).
- Positional entries when the T-spot is large (poor R:R) (16:09).
- Retest entries can miss the fill entirely (10:16).

## Conflicts and open questions
- "Inversion" is used for both FVG inversions and closes through a level; the exact level type is not fixed (04:13 vs 11:41).
- At 11:39 he says "do we have a bullish fair value gap" in a bearish trade that is inverted; consistent with IFVG (bullish FVG closed through becomes bearish).
- Time-based exit times (11:00, 10:00) depend on which hourly candle is traded; no general rule beyond "end of the expansion candle".
- 0.5 of the 5m range (13:38) as hold level is from his wick video; range endpoints not specified.

## Glossary additions
- `T-spot`: TTFM indicator zone where the HTF wick should form.
- `time-based exit`: exit at the close of the HTF expansion candle.
- Mishearings: "to r" = 2R.
