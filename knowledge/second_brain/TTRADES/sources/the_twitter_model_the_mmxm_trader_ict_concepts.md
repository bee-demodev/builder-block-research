---
title: "The \"Twitter Model\" The MMXM Trader - ICT Concepts"
type: ttrades-source
slug: the_twitter_model_the_mmxm_trader_ict_concepts
source: youtube
youtube_id: WwmS47Gb3M0
youtube_url: https://www.youtube.com/watch?v=WwmS47Gb3M0
partition: educational_youtube
duration_min: 9
recorded: unknown
format: playbook
speakers: [ttrades]
instruments: [XAUUSD, XAGUSD, NQ, ES, YM, GBPCAD]
timeframes: [1W, 1D, 4h, 1h, 15m]
concepts: [liquidity, fvg, smt, market-structure, cisd, ifvg, time-of-day, premium-discount, order-block, entry, stop-placement, targets, timeframe-pairing, risk, ttfm-indicator]
transcript: "[[../../ttfm_video_corpus/transcripts/the_twitter_model_the_mmxm_trader_ict_concepts.txt]]"
page: "none"
confidence: high
---

# The "Twitter Model" The MMXM Trader - ICT Concepts

## TL;DR
TTrades walks through the MMXM Trader's "Twitter model": external → internal liquidity on a small timeframe set. Short version: price raids previous day high, the target is a 1h bullish FVG below, entry on a 15m market structure shift with SMT, and shorts only above midnight open (longs: previous day low, 1h bearish FVG above, 15m MSS + SMT, only below midnight open). It is fractal (weekly/4H/1H, or lower). TTrades adds: accept an inversion FVG or CISD (close over the last opposing candle / series) instead of a strict MSS, pick the hourly FVG with premium/discount (equilibrium) in mind, require a 2R minimum when choosing the stop, and optionally swap midnight open for the daily open. Five examples: gold (SMT with silver), NQ (SMT with ES), GBP pair with GBPCAD SMT, NQ with YM SMT and FOMC candle, NQ short off PDH with daily open. In TTFM terms this is the daily C2/C3 PDH/PDL sweep plus 15m CISD, with an hourly FVG as the draw.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | The model moves from external liquidity to internal liquidity on a smaller timeframe, paired with an MSS and SMT. | liquidity | stated | 00:02 | "it is moving from external liquidity to internal liquidity on a smaller timeframe and pairing that with a market structure shift and SMT" |
| 2 | Short: previous day high taken, target a 1h bullish FVG, 15m MSS + SMT, only short above midnight open. | entry | stated | 00:02-00:39 | "Looking for a M15 market structure shift and SMT, and then looking to only short above midnight open" |
| 3 | Long: previous day low taken, target a 1h bearish FVG, same MSS + SMT, only long below midnight open. | entry | stated | 00:39 | "it would be previous days low, a one hour bearish fair value gap, and then the same market structure shift and SMT, and then only longing below midnight open" |
| 4 | The model is fractal: daily/1h/15m can move up to weekly/4H/1H or down to lower timeframes. | timeframe-pairing | stated | 01:33 | "I can move that up a timeframe to the weekly four hour and one hour, or I could move it down to the lower timeframes" |
| 5 | Instead of a strict MSS he also accepts an inversion FVG or a change in the state of delivery (close over the last down-close candle). | cisd | stated | 02:31, 05:47 | "although the model says a market structure shift, I will also look for an inversion or a change in the state of delivery" |
| 6 | Choose the stop that still gives a 2R minimum to the hourly FVG target. | risk | stated | 02:59 | "I want to have a 2R minimum, so that is what I would look to do." |
| 7 | Choose the hourly FVG target with premium/discount in mind: prefer the one whose reach lines up with the range's equilibrium. | premium-discount | stated | 03:29 | "considering premium and discount of the range, reaching an equilibrium of the range would be somewhere above the start of this fair value gap" |
| 8 | SMT with a correlated asset at the PDH/PDL raid (gold-silver, NQ-ES, NQ-YM, GBP pair-GBPCAD). | smt | demonstrated | 02:31, 03:56, 05:19, 06:18 | "Here's our purge of previous day low. And here we actually create an SMT with silver." |
| 9 | Entry can be at the close of the MSS candle (if below midnight open) or on a retracement; retrace may give a better price. | entry | demonstrated | 05:19-05:47 | "I'm going to go ahead and just enter right on the close of this market structure shift candle as we're below midnight." |
| 10 | Once price closes over a series of down-close candles (order block), he does not expect that low to be touched again. | order-block | stated | 05:47 | "Here we close over the series of downclosed candles, making an order block, so now I wouldn't anticipate this low being touched." |
| 11 | Midnight open is drawn with the "ICT kill zones and pivots" indicator, all off except the midnight opening price. | tooling | stated | 04:22 | "the indicator I'm using to mark out midnight open is ICT kill zones and pivots" |
| 12 | You may trade the weaker asset of an SMT pair for shorts; here he stays on NQ. | asset-strength | stated | 07:47 | "I could go look to trade ES or the weaker asset as we have an hourly fair value gap here" |
| 13 | Variation: use the daily open instead of midnight open as the premium/discount filter. | time-of-day | stated | 08:15, 08:44 | "instead of using midnight open, I use the daily open" |
| 14 | An up-close series into the POI that sweeps liquidity becomes a bearish order block once closed below; stop above the opposing candles. | stop-placement | demonstrated | 08:15-08:44 | "So if it gets closed below, that validates as an order block." |

## Definitions
- **MMXM Trader "Twitter model"**: PDH/PDL raid (external) → 1h FVG target (internal), 15m MSS + SMT, entry on the correct side of midnight open (00:02-00:39).
- **Midnight open**: opening price at 00:00 New York, used as premium/discount filter (shorts above, longs below) (00:39, 04:22).
- **Change in the state of delivery**: close over the last down-close candle (bullish) (02:31).
- **Inversion**: an opposing FVG closed through and used the other way (02:31, 06:18).

## Procedure / checklist
1. Daily: mark previous day high (short) or low (long) (00:39, 03:29).
2. 1h: find the FVG on the other side (bullish FVG below for shorts, bearish above for longs); prefer one consistent with the range equilibrium (01:08, 03:29).
3. Wait for the PDH/PDL raid (02:02).
4. 15m: SMT with a correlated asset, then MSS / inversion / CISD (02:31).
5. Entry only above midnight open (shorts) / below (longs); or use daily open (01:08, 08:15).
6. Stop on the FVG candle / swing that gives ≥2R; target the 1h FVG (02:59).

## Worked examples
### Example 1: Gold daily → 1h → 15m long (01:33-03:29)
- Gold daily uptrend; previous day low on 1h; bearish 1h FVG above (01:33-02:02).
- 15m: purge of PDL, SMT with silver, inversion + CISD (close over a down-close candle) (02:31).
- Entry on the FVG, stop on the FVG candle's low (stop at the swing low would be only 1.4R; wants 2R min); below midnight → target hit (02:59).

### Example 2: NQ daily → 1h → 15m long (03:29-04:22)
- Large 1h FVG chosen because reaching equilibrium of the range sits just above its start (03:29).
- 15m: PDL swept, SMT with ES, broke and closed over a high; entry below midnight open, stop on the low, 2R minimum (03:56).
- Tagged in at midnight open, move to the 1h FVG; on the 1h price reached equilibrium (04:22).

### Example 3: GBP pair (SMT with GBPCAD) long (04:48-05:47)
- PDL marked; 1h FVG slightly tapped, equal highs/failure swings (04:48).
- 15m: SMT with GBPCAD at the low, MSS after PDL; entered on the close of the MSS candle (below midnight) (05:19).
- Retraced to an order block (better entry possible); took until the next day to reach the draw (05:47).

### Example 4: NQ with YM SMT, inversion entry, 2.26R (05:47-07:18)
- 1h: PDL raided, SMT with YM; target FVG partly mitigated by an FOMC candle (06:18).
- 15m: bearish FVG closed over = inversion entry; stop below 50% of the wick (06:48).
- Later order block entry via midnight open never filled; first entry reached the hourly FVG for 2.26R (06:48-07:18).

### Example 5: NQ short off PDH with daily open (07:18-08:44)
- PDH and a daily FVG above; 1h FVGs below as targets; NQ higher high vs ES lower high = SMT (07:18-07:47).
- 15m: short above the daily open; FVG plus up-close series into the POI sweeping liquidity; close below = inversion + order block (08:15).
- Entry on the order block, stop above the opposing candles, target the hourly FVG; 2R not yet hit at first, then continued lower (08:44).

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:02 | Model definition (PDF) |
| 00:39 | Long version; daily → 1h → 15m walk-through |
| 01:33 | Fractal timeframes |
| 01:33 | Gold example |
| 03:29 | NQ example; FVG choice by equilibrium |
| 04:22 | Midnight open indicator |
| 04:48 | GBP / GBPCAD SMT example |
| 05:47 | Inversion / CISD variant; NQ-YM, FOMC candle |
| 07:18 | NQ short off PDH with daily open |
| 09:08 | Outro |

## Mistakes and warnings
- A stop that gives under 2R (1.4R at the swing low) is rejected; move the stop to the FVG candle instead (02:59).
- Do not long above midnight open / short below it (00:39).

## Conflicts and open questions
- The original model says MSS; TTrades loosens it to inversion or CISD (05:47) — a rule engine must pick one.
- The GBP pair traded in Example 3 is not named; only the SMT pair GBPCAD is heard ("GBV CAD").
- Choice between several 1h FVGs is judgment (equilibrium) with no fixed rule.
- Daily open vs midnight open: no rule for when to use which.
- 08:44 "return 2R entry" is garbled; whether 2R was eventually hit is unclear.

## Glossary additions
- `GBV CAD` (Whisper, 05:19): GBPCAD.
- `RTP` (Whisper, 02:59): "our TP" (take profit).
- `retch` (Whisper): reached.
- `MMXM Traders Twitter model`: PDH/PDL → 1h FVG, 15m MSS + SMT, midnight open filter.
