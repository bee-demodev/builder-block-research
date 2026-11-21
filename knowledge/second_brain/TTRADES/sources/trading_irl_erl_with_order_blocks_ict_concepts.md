---
title: "Trading IRL & ERL With Order Blocks! - ICT Concepts"
type: ttrades-source
slug: trading_irl_erl_with_order_blocks_ict_concepts
source: youtube
youtube_id: TfHlNgAZ_II
youtube_url: https://www.youtube.com/watch?v=TfHlNgAZ_II
partition: educational_youtube
duration_min: 15
recorded: unknown
format: lesson
speakers: [ttrades]
instruments: [GC]
timeframes: [1W, 1D, 4h, 1h, 15m, 5m]
concepts: [liquidity, fvg, swing-points, cisd, order-block, daily-bias, timeframe-pairing, stop-placement, targets, time-of-day, continuation, market-structure]
transcript: "[[../../ttfm_video_corpus/transcripts/trading_irl_erl_with_order_blocks_ict_concepts.txt]]"
page: "none"
confidence: high
---

# Trading IRL & ERL With Order Blocks! - ICT Concepts

## TL;DR
TTrades defines internal range liquidity (IRL) as a fair value gap and external range liquidity (ERL) as a swing high/low, and teaches that price oscillates ERL -> IRL -> ERL -> IRL until trend shifts. Model flow: HTF bias -> HTF IRL (FVG) or ERL (swing) reached -> drop to LTF -> stop raid -> CISD (close over the opening price of the series of candles that made the low) -> target ~2R, inside a kill zone. Shown on gold weekly/4h/15m and two 1h/5m and 1D/1h cases. Useful detail for a rule engine: the CISD reference candle moves when price makes a new low before closing over, messy legs can be treated as one series, and the stop may sit at 0.5 of the order-block candle body (breaker-style) to hit 2R.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | Internal range liquidity = a fair value gap (bullish or bearish). | fvg | stated | 00:28 | "internal range liquidity is just a fair value Gap" |
| 2 | External range liquidity = a swing high or swing low. | swing-points | stated | 00:43 | "external range liquidity is just a swing high or a swing low" |
| 3 | Price moves internal -> external and external -> internal, alternately. | liquidity | stated | 00:55 | "we expect price to move from internal to external and external to internal" |
| 4 | After ERL is purged, expect a move back into the range to IRL; a lower high forming at IRL then targets ERL. | liquidity | stated | 01:00 | none |
| 5 | The oscillation continues until a trend shift or other movement breaks it, then restarts. | market-structure | stated | 01:33 | "or until we shift Trend or have some other movement which breaks this" |
| 6 | Flow: HTF bias first, then the HTF IRL/ERL criterion, then LTF stop raid and CISD. | top-down-alignment | stated | 02:06 | "I am then going down to the lower time frame looking for a stop raid a change in the state of delivery" |
| 7 | Target about 2R, and the whole sequence must happen within a kill zone. | targets | stated | 02:11 | "I will be targeting just around a 2R trade and this must all be done within a Kill Zone" |
| 8 | Weekly bias: if the previous week closed over the week before, anticipate a reach for the previous week high. | daily-bias | stated | 03:00 | "previous week closed over the previous" |
| 9 | If price makes a new low before closing over the series, the CISD reference shifts to the new candle(s) that made the new low. | cisd | stated | 04:18 | "with making a new low this would not be our change in the state of delivery" |
| 10 | CISD = close over the series (or single) candle that made the low. | cisd | stated | 04:25 | "I'm finding the series or singular candle that made the low and then if price closes over it" |
| 11 | CISD level precisely = the opening price of the series of candles that made the low; a close over it confirms. | cisd | stated | 10:41 | "I Mark out the opening price in that Series so I would need a close over this to continue higher" |
| 12 | If the swing-low stop does not give 2R, extend the target or move the invalidation. | stop-placement | stated | 05:16 | "to meet that 2 R minimum I'll either have to extend my price Target or move my invalidation" |
| 13 | Tighter invalidation: price should not disrespect 0.5 of the down-close candle body (order block); stop there, like a breaker-block stop. | stop-placement | stated | 05:21 | "I wouldn't really want to see price disrespect .5 of this down Clos candle body" |
| 14 | A sweep of another low then a close over the down-close candle forms a propulsion block. | order-block | stated | 05:45 | "that would be the propulsion block" |
| 15 | Do not use a sweep of a low whose break would invalidate the HTF idea (e.g. the daily low expected to hold); use a FVG instead. | liquidity-sweep | stated | 06:38 | "we could sweep out this low but then that would invalidate the idea" |
| 16 | If the down-move has no clean series of down-close candles, treat the whole move (large down-close candle + continuation) as the series for CISD. | cisd | stated | 07:16 | "we don't have a clean series of down closed candles so generally what I do here is I just use this whole move" |
| 17 | If the CISD close is too far from the stop for acceptable RR, wait for a retest (limit order) instead of entering on the close. | entry | stated | 07:47 | "in this case I would have to wait for a retest" |
| 18 | Once the LTF ERL (buy-side) is already taken, avoid further longs unless the HTF narrative is strong; next draw may be IRL or the other side of the range. | targets | stated | 08:06 | "if I'm lacking that strong narrative this is going to be something I want to avoid" |
| 19 | A reaction out of the mean threshold (upper half) of the down-close series supports price; entry there with stop below the mean threshold requires a strong bias. | order-block | stated | 08:33 | "reaction out of the mean threshold of this series" |
| 20 | In a bullish trend, each higher low forms in IRL (FVG) and targets the next ERL (higher high). | continuation | demonstrated | 09:51 | none |
| 21 | Continuation entry after CISD: a retest that validates the new low gives another entry, stop on that low, target 2R. | continuation | demonstrated | 10:56 | "I can always wait for a retest and place a limit order" |
| 22 | Two entry options on the hourly CISD: enter with stop below 0.5 of the order block, or wait for a new order block in the next candle. | entry | stated | 12:56 | "I can take an entry with where I would need my stop below 0 five of this" |
| 23 | A new order block requires either a sweep of a low or a reach into a FVG, then a close over the down-close candles. | order-block | stated | 13:08 | "I'd want to see if we either sweep out a low or reach into a fair value Gap" |
| 24 | Manage: take 2R, or hold runners toward the ERL. | trade-management | stated | 13:36 | "I can Target Two r or hold Runners towards our external range liquidity" |

## Definitions
- **IRL (internal range liquidity)**: a FVG (00:28).
- **ERL (external range liquidity)**: a swing high or swing low (00:43).
- **CISD (here)**: close over the opening price of the series (or single) candle that made the low (bearish mirror) (04:25, 10:41).
- **Propulsion block**: an order block formed after a further sweep, then closed over; retested as support (05:45, 08:48).
- **Mean threshold**: 50% of the order-block series/candle body (05:21, 08:33).

## Procedure / checklist
1. HTF bias (e.g. weekly close over previous week -> previous week high; daily sweep + close back inside -> bullish next day) (03:00, 06:16).
2. On the intermediate TF (4h / 1h / 1D), identify the IRL being reached (FVG) and the ERL target (swing, PWH, equal highs) (03:10, 06:47, 12:28).
3. Drop to the LTF (15m / 5m / 1h): wait for the stop raid into IRL (03:46).
4. Mark the opening price of the series that made the low; wait for a body close over it (CISD); reset if a new low forms first (04:12-04:43).
5. Enter on the close or on a retest limit; stop at the swing low or at 0.5 of the order-block body; ensure ~2R (05:14, 07:47).
6. Within a kill zone; target 2R / ERL; optional continuation entries on retests (02:11, 10:56, 13:36).

## Worked examples
### Example 1: Gold weekly -> 4h -> 15m (02:57-06:16)
- Weekly: previous week closed over the prior week -> target previous week high (03:00).
- 4h: FVG (IRL) retested; ERL = 4h swing high + PWH (03:10-03:42).
- 15m: sweep into the 4h FVG; first CISD attempt fails as price makes a new low; reference candle moves; close over the down-close candle = CISD (03:46-04:43).
- Swing-low stop does not give 2R, so stop at 0.5 of the down-close candle body (breaker-like); another sweep + close forms a propulsion block; 2R hit (05:14-05:45).

### Example 2: 1h -> 5m bullish, Tue 29 Oct (year not shown; price scale ~87.3-87.6, symbol not readable) (06:16-11:26)
- Daily low swept, close back inside -> bullish next day; sweeping the nearby low would break the daily low, so the hourly FVG is used as IRL; ERL = equal highs (06:16-06:47).
- 5m: messy, so the whole down move is the CISD series; close over confirms; entry at close too far from stop -> retest; ERL taken (07:04-07:48).
- With strong bias only: consolidation, low swept, reaction from the mean threshold; propulsion block entry, stop below mean threshold, 2R hit (08:18-09:19).
- Hourly: price fails to reach the FVG first (equal lows), then reaches it; 5m CISD via opening price of the series; limit retest entry and a continuation entry each hit 2R (09:51-11:26).

### Example 3: 1D -> 1h bullish, Tue 08 Oct (year not shown; price scale ~147-149, symbol not readable) (11:57-14:22)
- Daily uptrend retraces into a daily FVG (IRL); ERL = daily high (11:57-12:28).
- Hourly CISD; entry option with stop below 0.5 of the OB, or wait; low swept, close over the down-close candles = new OB; stop on the low; 2R hit; daily ERL reached later (12:28-14:01).

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:05 | IRL vs ERL definitions |
| 00:55 | ERL <-> IRL oscillation |
| 01:37 | Flowchart: bias, IRL/ERL, stop raid, CISD, 2R, kill zone |
| 02:57 | Example 1: gold weekly/4h/15m |
| 06:16 | Example 2: 1h/5m, messy series, propulsion block |
| 09:51 | Hourly higher-low via IRL, 5m CISD by opening price |
| 11:57 | Example 3: daily FVG, hourly CISD |
| 14:22 | Outro; PDF in free Discord |

## Mistakes and warnings
- Calling CISD before the close over the candle that made the latest low; a new low resets the reference (04:12).
- Entering on a CISD close far from the stop (bad RR); wait for the retest (07:47, 10:54).
- Using a sweep that would break the HTF swing expected to hold (06:38).
- Taking longs after the LTF buy-side ERL is already taken without strong HTF narrative (08:06).

## Conflicts and open questions
- Kill zone is required (02:11) but no hours are given and not checked in the examples.
- 2R is a "minimum" (05:16) and also "just around" the target (02:11); the two framings differ slightly.
- Mean-threshold stop is "body" 0.5 at 05:21 but at 12:56 "0.5 of this" (OB series) without saying body or wick.
- Symbols for examples 2 and 3 not spoken or readable on frames.

## Glossary additions
- `IRL` (internal range liquidity) = FVG; `ERL` (external range liquidity) = swing high/low.
- `propulsion block`: order block formed after an additional sweep, then retested.
- `wretch into` = reach into; `downlo candles` = down-close candles; `to R` / `Two r` = 2R.
