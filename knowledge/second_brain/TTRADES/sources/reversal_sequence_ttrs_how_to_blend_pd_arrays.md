---
title: "Reversal Sequence (TTRS) - How To Blend PD Arrays"
type: ttrades-source
slug: reversal_sequence_ttrs_how_to_blend_pd_arrays
source: youtube
youtube_id: wik00c9_2nk
youtube_url: https://www.youtube.com/watch?v=wik00c9_2nk
partition: educational_youtube
duration_min: 17
recorded: unknown
format: lesson
speakers: [ttrades]
instruments: []
timeframes: [1D, 1h, 15m, 5m]
concepts: [reversal, liquidity-sweep, ifvg, cisd, order-block, breaker, fvg, premium-discount, smt, consolidation, daily-profile, time-of-day, entry]
transcript: "[[../../ttfm_video_corpus/transcripts/reversal_sequence_ttrs_how_to_blend_pd_arrays.txt]]"
page: "none"
confidence: high
---

# Reversal Sequence (TTRS) - How To Blend PD Arrays

## TL;DR
An older ICT-era lesson on building an entry model. TTrades sets kill zones (NY AM 8:30-11:00 for indices, London 2:00-5:00 ET), defines the PD arrays (FVG, inversion, order block, breaker, OTE) and confluences (premium/discount, SMT), then gives the "order of a reversal": (1) purge of a low / turtle soup, or SMT instead; (2) inversion of the FVG that made the leg; (3) CISD / order block formation; (4-5) FVG and/or breaker block. Each later step adds confirmation but enters further from the extreme. He advises picking one PD array (his is the CISD / order block) rather than watching all of them. Pre-dates the formal TTFM candle 2/3 framing but CISD is already the core.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | Intraday (below the hourly) trade only within kill zones: NY AM 8:30-11:00 for indices, London 2:00-5:00, Eastern time. | time-of-day | stated | 00:45 | "I personally focus on the New York am session for indices so I'm going to focus on 8:30 to 11 for my trading" |
| 2 | Choose your execution timeframe by temperament: impatient lower, patient higher; he executes on 5m because it aligns with the daily profile. | timeframe-pairing | stated | 00:59 | "impatient people want to be on a lower time frame while patient people are generally better suited for a higher time frame" |
| 3 | Master one PD array rather than every concept. | entry | stated | 01:28 | "instead focus on one of these Concepts and master that" |
| 4 | FVG: three-candle pattern where candle 3's high does not overlap candle 1's low (or candle 3's low does not overlap candle 1's high); the gap is a POI. | fvg | stated | 01:55 | "it is a three Candlestick pattern in which the high of the third candle does not overlap the low of the first candle" |
| 5 | Inversion: an FVG that is closed over and then used as support (bullish) or resistance (bearish). | ifvg | stated | 02:18 | "that is when a fair value Gap gets closed over and then is used as support to trade higher or resistance to trade lower" |
| 6 | Order block (his focus): at a POI, take the series of up-close candles into it; when closed below, expect that high to hold and the block to act as resistance. | order-block | stated | 02:34 | "I take the series of up closed candles into that point of interest when it is then closed below" |
| 7 | Bearish breaker: high, low, higher high, lower low; mark the down-close candles between that high and low as resistance; bullish mirror uses up-close candles. | breaker | stated | 02:57 | "it is where we have a high a low a higher high and a lower low" |
| 8 | OTE: Fib the impulse leg high to low and look for a lower high around the 70.5% retracement to trade back toward the low. | retracement | stated | 03:27 | "using the Fibonacci retracements and specifically the 705 area" |
| 9 | Confluence: look for your chosen PD array in discount for lows and premium for highs (0.5 of the range). | premium-discount | stated | 04:03 | "when we use premium in discount or A5 FIB of a range I can then look for either a fair value Gap or an order block" |
| 10 | SMT (correlated assets with different structure: one higher low, one lower low) is his favourite reversal confluence. | smt | stated | 04:28 | "one asset made a higher low while the other one made a lower low" |
| 11 | Order of a reversal: purge of a low / turtle soup, then inversion, then CISD / order block formation, then FVG and/or breaker. | reversal | stated | 05:23 | "this is generally how reversals form is we first have a purge of a low or a turtle soup" |
| 12 | Step 1 (purge) is not needed when SMT is present. | smt | stated | 05:28 | "we will not have this if we have smt" |
| 13 | Step 3: CISD / order block formation = close through the series of down-close candles that purged the low. | cisd | stated | 05:43 | "once we close through this series of down closed candles that Purge that low" |
| 14 | The further down the sequence, the more confirmation, but the later the entry; you trade confirmation for price. | entry | stated | 06:19 | "the further down this list the more confirmation there is that it has formed a reversal" |
| 15 | He prefers trading continuations, i.e. later in the sequence. | continuation | stated | 05:08 | "I personally prefer to trade continuations so later into the move" |
| 16 | A consolidation (failure to displace out of either side) is a range whose high and low are manipulation candidates. | consolidation | stated | 07:01 | "you can see we have failed to displace out of either side of this range and we are consolidating" |
| 17 | Remove all drawings except your chosen PD array to read reversals clearly. | entry | stated | 10:27 | "go ahead and remove all the other drawings except for that one" |
| 18 | In a bullish daily profile with Asia highs and London consolidation, expect London/equal highs taken, needing a low manipulation or SMT first. | daily-profile | stated | 11:30 | "we want to see either a manipulation of a low or an smt to form and confirm this reversal" |
| 19 | When steps overlap (inversion, CISD, breaker, FVG in one area), they act as confluence; he still focuses on the CISD and the order block's mean threshold. | order-block | demonstrated | 12:41 | "what I would be focusing on here is just the change in the state of delivery and then the main threshold of this order block" |
| 20 | In a retracement against expected continuation, wait for either a close below the up-close candles (validating the high) or a sweep of the high, whichever comes first. | cisd | stated | 14:20 | "I either want to see a close below these up close candles here to validate this high or for this High to get swept out" |
| 21 | If the breaker is not clean, use the whole leg as the breaker zone. | breaker | demonstrated | 15:47 | "this one isn't very clear so generally on this I would just use this whole leg up" |

## Definitions
- **Kill zones**: NY AM 8:30-11:00 (indices), London 2:00-5:00, ET (00:28).
- **FVG**: 3-candle non-overlap of candle 1 and candle 3 extremes (01:55).
- **Inversion**: FVG closed through, reused as opposite support/resistance (02:18).
- **Order block**: series of same-colour candles into a POI that gets closed through; expected to hold (02:29).
- **Breaker block**: high-low-higher high-lower low (bearish); down-close candles between high and low (02:57).
- **OTE**: Fib of impulse leg, 70.5% area (03:27).
- **Turtle soup / purge**: sweep of a low (or high) as step 1 of a reversal (05:23).
- **Propulsion block**: named at 16:07 as a new block forming in the retracement; not defined here.

## Procedure / checklist
1. Bias and daily profile (draw on liquidity, session context) (10:41-11:30).
2. In the kill zone, watch the expected manipulation side (or SMT) (00:45).
3. Track the reversal order: purge / SMT, inversion, CISD / OB, FVG / breaker (05:23-06:31).
4. Enter at the step that matches your chosen PD array; later = more confirmation, worse price (06:19).

## Worked examples
### Example 1: consolidation low purge, sequence demo (06:51-10:38)
- Consolidation, mark high/low; low taken = turtle soup (little confirmation). FVG of the down leg closed over = inversion entry. Single down-close candle that made the low closed over = CISD entry. FVG and breaker (low-high-lower low-higher high) form; retracement into the FVG, consolidation, then expansion through the other side of the range. Instrument not named.

### Example 2: bullish daily, 5m/LTF top-down (10:41-13:39)
- Daily: consolidation low manipulated, close back inside, expansion higher; draw = high. Daily profile: Asia high with failure swings, London consolidation; expect London / equal highs taken after a low manipulation or SMT.
- Purge of the low = turtle soup; next candle forms an FVG usable as inversion; at the same time CISD and breaker form; FVG forms; all overlap. He focuses on the CISD and order block mean threshold; reaction and move higher toward Asia highs.

### Example 3: bearish daily, 1h to 15m (13:39-16:42)
- Daily: high swept, close back in, continuation lower; target lows and FVGs to the left; hourly shows resting lows.
- 15m: no low taken, retracement / consolidation into London; sweep of the high = turtle soup; inversion of the FVG that made the high; CISD / order block; then breaker (whole leg used) and FVG overlap; retrace into FVG/breaker, respects CISD, new propulsion block, then takes the low.

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:11 | Intro: building an entry model |
| 00:28 | Kill zones and execution timeframe |
| 01:28 | Concepts: FVG, inversion, order block, breaker, OTE |
| 03:49 | Confluences: premium/discount, SMT |
| 04:50 | Order of a reversal (5 steps) |
| 06:51 | Example 1: sequence demo |
| 09:57 | Why focus on one PD array |
| 10:41 | Example 2: bullish top-down |
| 13:39 | Example 3: bearish top-down |
| 16:42 | Outro |

## Mistakes and warnings
- Trying to master every concept at once (01:30).
- Watching every PD array at once leads to overwhelm; simplify (09:57-10:38).
- Entering at the turtle soup has very little confirmation (07:33).

## Conflicts and open questions
- Order block defined via "series of up closed candles into that point of interest" then closed below (bearish); this matches TTrades' CISD definition, so here order block formation = CISD (05:43). A rule engine should treat them as the same event in this source.
- Breaker definition at 02:57 says "high, low, higher high, lower low" for bearish then marks "down close candles in between that high and that low"; ICT convention normally uses the up-close candles of the swing high; in Example 1 (bullish) he marks up-close candles "from this low to this high". Direction/colour wording is not fully consistent.
- Steps 4 and 5 (FVG vs breaker) "blend together" with no fixed order (05:51).
- "Main threshold" (12:45) presumably = mean threshold (50% of the order block); not defined.
- "Propulsion block" (16:07) is used without definition.
- Title calls it "TTRS"; the acronym is never spoken.

## Glossary additions
- `TTRS` (TTrades reversal sequence): purge/SMT, inversion, CISD/OB, FVG/breaker.
- `turtle soup` (purge): sweep of a low/high as reversal step 1.
- `OTE` (mishearing "OT", "705" = 70.5%): optimal trade entry Fib zone.
- `propulsion block`: named, undefined here.
- Mishearings: "A5 FIB" = 0.5 Fib, "pair value gaps" = fair value gaps, "main threshold" = mean threshold, "EV consolidation" = consolidation, "inaday" = intraday.
