---
title: "TTrades Playbook | Fractal Model Fundamentals (TTFM)"
type: ttrades-source
slug: fractal_model_fundamentals
source: youtube
youtube_id: TNybDCtwBnc
youtube_url: https://www.youtube.com/watch?v=TNybDCtwBnc
partition: seed_curriculum
duration_min: 20
recorded: unknown
format: playbook
speakers: [ttrades]
instruments: [NQ, GC, GBPUSD]
timeframes: [1D, 1h, 5m]
concepts: [fractal-model, daily-bias, cisd, candle-2, candle-3, swing-points, poi, timeframe-pairing, protected-swing, entry, stop-placement, targets, consolidation, premium-discount, backtesting]
transcript: "[[../../ttfm_video_corpus/transcripts/fractal_model_fundamentals.txt]]"
page: "artifacts/ttrades/pages/fractal_model_playbook_aligning_daily_hourly_and_5_minute_charts.md"
confidence: high
---

# TTrades Playbook | Fractal Model Fundamentals (TTFM)

## TL;DR
The base TTFM playbook for the 1D-1h-5m pairing, shown as a Tradezella playbook and backtested on five trades. Foundation: price cannot reverse without a swing point; candles are numbered 1-4 around the swing (candle 2 = swing high/low). Step 1: a one-sided daily bias from daily closures (close beyond previous day high/low = continuation; failure to close beyond = reversal); no bias, no hourly. Step 2: on the hourly, confirm a CISD in the daily candle 2, find a POI in the correct half of the previous day's range, and wait for an hourly candle closure (sweep and close back inside) at that POI. Step 3: on the 5m, wait for a CISD in that hourly candle 2, then enter for the hourly candle 3 continuation with stop on the protected swing and 2R minimum (or higher-timeframe targets). Backtest: 4 of 5 wins, 2.79R.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | Price cannot reverse without forming a swing point (swing low for bearish→bullish, swing high for bullish→bearish). | swing-points | stated | 00:22 | "the foundation of the fractal model is based off the idea that price cannot reverse without a swing point." |
| 2 | Candle 2 is always the swing high/low; candle 1 is before it, candle 3 and 4 follow; candle 4 is always a continuation if the trend is correct. | candle-2 | stated | 00:46 | "Candle 2 will always be the swing low or swing high." |
| 3 | Without a daily bias, do not drop to the hourly timeframe. | daily-bias | stated | 01:10 | "If I do not have a daily bias I do not drop down to the hourly time frame." |
| 4 | Daily close below the previous day low → expect continuation lower; failure to close below it → expect reversal and bullish; mirror for previous day high. | daily-bias | stated | 01:20 | "if price closes below its previous day low, I'm expecting a continuation lower." |
| 5 | Ideally find a daily closure where price reverses (swing point) and trade the continuation that follows. | candle-3 | stated | 01:38 | "I want to find a closure where price reverses and look to trade the continuation following." |
| 6 | On the hourly, confirm a CISD at the daily candle 2 in the direction of the swing (bullish swing → bullish CISD). | cisd | stated | 01:53 | "go to that candle 2 or the swing point on the daily and make sure we have a change in the state of delivery there." |
| 7 | Entries require both the daily closure and the hourly CISD. | cisd | stated | 02:11 | "Once I have both the closure and the change in the state of delivery, then I can look for entries." |
| 8 | Entries should occur in the upper or lower half of the previous day's range (discount for longs, premium for shorts) and at a POI where the next day forms its wick. | premium-discount | stated | 02:17 | "I want to see them in the upper half or lower half of the previous day's range and then at a point of interest." |
| 9 | At the POI, wait for an hourly candle closure that runs beyond the previous candle and closes back in (reversal). | candle-2 | stated | 02:35 | "once I've identified a point of interest, I'm going to wait for a candle closure similar to what we did on the daily chart." |
| 10 | Then on the 5m, a CISD confirms the hourly reversal; trade continuations in hourly candle 3. | timeframe-pairing | stated | 02:52 | "Look for a change in the state of delivery to confirm that reversal." |
| 11 | When the hourly closes through the POI against bias, either invalidate the bias or keep it and lower the target (large wick) instead of expecting expansion toward the daily open. | daily-bias | stated | 05:32 | "I can either invalidate my bias and not continue to look short or I can see that we're making quite a large wick" |
| 12 | Ideal candle 3 for a short: opens, makes a high first, then trades lower (inverse for longs); trading the wrong side first is a warning. | expansion | stated | 06:15 | "it's most ideal to have it open, make a high, get inside and trade it lower." |
| 13 | In a consolidation with bullish bias, want the consolidation lows run, then a bullish candle closure, then the LTF entry. | consolidation | stated | 07:42 | "We want to see lows ran out in the consolidation to trade it higher." |
| 14 | Expansion met with expansion is a reversal. | reversal | stated | 07:35 | "So expansion met with expansion is a reversal." |
| 15 | No 5m entry until the 5m closes over the series of opposite-close candles (CISD); part of the checklist. | cisd | stated | 09:05 | "I have to wait for that to occur before I can take an entry. That's part of my checklist." |
| 16 | Stop on the protected low (e.g. the low out of a fair value gap); target 2R or the -1 standard deviation of the manipulation leg. | stop-placement | demonstrated | 09:30 | "Or I can look for those standard deviations, right? Which is a negative one standard deviation from this manipulation leg." |
| 17 | A sweep that closes back inside but as a bearish candle is not a bullish candle closure; wait for displacement up or another sweep. | candle-2 | stated | 11:52 | "Yes, it closed back inside its previous range, but this is a bearish candle." |
| 18 | Do not trust LTF lows that did not reach a POI; wait for more confirmation or for a sweep then a continuation entry. | poi | stated | 12:30 | "Do I trust any of these lows? No. Because none of them reach into a point of interest." |
| 19 | Best R:R comes from a lower-timeframe entry with a higher-timeframe target (e.g. hourly / previous day high instead of 5m highs: 5.63R vs 2R). | targets | stated | 13:57 | "the best way to get high risk-to-reward trades is to take a lower time frame entry and just use a higher time frame target." |
| 20 | Even a few daily candles (sweep and close back in, engulfing) give enough context; don't overthink the daily chart. | daily-bias | stated | 14:26 | "a lot of people overthink the daily chart." |
| 21 | After the first target (previous day low) is taken, a reversal would show as displacement back into the range (ignore if against bias); a shallow retrace into an FVG then continuation is tradable. | retracement | stated | 16:42 | "I want to see does price displace back into the range, right?" |
| 22 | Stop can sit above the LTF high if price should not trade above 50% of the opposing candles, or allow extra room for a sweep. | stop-placement | stated | 18:01 | "I don't want to see price trade above 50% of these opposing candles. That's why I can trust this high." |
| 23 | An hourly candle that closes below its previous allows the next candle to expand as well. | candle-4 | stated | 18:34 | "it closed below the previous which allows this next candle to expand as well." |
| 24 | Minimum target 2R; with 2R, a win rate over about 34% is breakeven or profitable. | risk | stated | 19:08 | "For my system, I'm looking for a minimum of 2R" |

## Definitions
- **Candle 1/2/3/4**: candle 2 is the swing high/low; candle 1 before it; candle 3 after candle 2; candle 4 after candle 3 and a continuation if the trend is correct (00:46).
- **Daily bias (one-sided)**: direction from daily closures relative to previous day high/low (01:20, 03:43).
- **Candle closure / candle 2 closure**: candle runs beyond the previous candle's high/low (ideally into a POI) and closes back inside its range; in his examples it should also close in the bias direction (02:43, 11:52).
- **CISD**: close over the series of down-close (or up-close) candles that made the low (high); the series can be one candle (08:19).
- **Manipulation leg**: the leg from low to high used for the -1 standard deviation projection, "flipping it over" (10:36).

## Procedure / checklist
1. Daily: one-sided bias from closures; ideally a candle 2 reversal closure. No bias → stop (03:43).
2. Hourly: CISD inside the daily candle 2 (04:00).
3. Hourly: POI in the correct half of the previous day range (FVG, intraday lows/highs, consolidation sweep) (04:02).
4. Hourly: candle closure at the POI (sweep previous candle, close back inside, bias-colored) (04:05).
5. 5m: CISD in that hourly candle 2 → entries valid (04:07).
6. Entry on close or retest (market or limit); stop on protected swing; target 2R minimum, -1 SD, or higher-timeframe liquidity (09:30, 13:57).

## Worked examples
### Example 1: NQ 1D → 1h → 5m, Fri 17 Jan 2025 (frame) (04:34-07:15), loss
- Daily: reach into FVG, sweep previous day high, bearish close back inside → short bias.
- 1h: CISD in candle 2; but price already trading over the FVG POI; hourly closes through the area (not ideal) → kept bias, expect less (large wick).
- Next bearish hourly closure sweeping the previous high; 5m CISD. Candle 3 traded lower first, swept lows, then back into range (concerning). Bearish closure → short on close, stop on high, 2R; sold 2 at market. Stopped out.
- Lessons: POI not respected; short-term lows already taken before entry; expansion candle went the wrong way first.

### Example 2: Gold (GC) 1D → 1h → 5m (07:18-10:45), win
- Daily: range; high swept then low traded; expansion lower met with expansion higher = reversal; consolidation; lows swept, bullish closure → long bias.
- 1h: sweep of previous low, CISD through one down-close candle; consolidation; highs taken, then lows taken at POI, bullish closure.
- 5m: waited for close over the down-close series; long, stop protected low (low out of an FVG), target 2R or -1 SD of manipulation leg. Hit TP.

### Example 3: NQ 1D → 1h → 5m, Tue 03 Jun 2025 (frame; replay clock ~05:05) (10:45-14:23), win
- Daily: candle closure → long; next day trend day up, closed over previous day high → continuation.
- 1h: CISD in reversal candle; FVG not respected → use intraday lows; first sweep closed bearish (not valid); second sweep at POI → bullish hourly closure.
- 5m: close over series of down-close candles; lows not trusted (no POI) → wait for sweep, then close through the down-close candle; limit entry on retest, stop low, 2R; hit TP.
- Sauce: using the hourly target (previous day high) instead of 5m highs gives 5.63R.

### Example 4: GBPUSD 1D → 5m, Mon 23 Jun 2025 (frame) (14:23-16:09), win
- Daily four candles: high swept and close back in; low swept and engulfing candle → very bullish.
- Existing low + FVG as POI; price reaches FVG and closes back outside ("on other exchanges, this was a candle 2 closure").
- 5m: messy; close over the series of down-close candles → market long on close, stop on low, 2R; retracement then TP.

### Example 5: instrument not named, 1D → 1h → 5m short (16:09-18:40), win
- Daily: previous high swept, failure swings on lows. Hourly CISD from the series of up-close candles (with a gap); continuation order block follows.
- Previous day low (first target) taken → watch for displacement back up (ignore) vs shallow retrace into FVG (trade). Reached FVG, bearish closure.
- 5m: wait for CISD; closure through, retest, sweep of previous high, displacement lower → market short, stop on the LTF high (50% of opposing candles) or slightly wider; 2R or previous low. Continuation lower.

### Backtest result (18:43-19:20)
- 5 trades, 80% win rate, 2.79R (average). He expects the win rate to fall on a larger sample.

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:11 | Intro: hourly and 5m model aligned with daily |
| 00:22 | Swing points and candle numbering |
| 01:07 | Daily bias from daily closures |
| 01:49 | Hourly: CISD at candle 2, POI in previous day half, candle closure |
| 02:52 | 5m CISD, trade candle 3 |
| 03:05 | Tradezella playbook and rules |
| 04:14 | Backtest session setup |
| 04:34 | Example 1 NQ (loss) |
| 07:18 | Example 2 Gold |
| 10:45 | Example 3 NQ; HTF target for R:R |
| 14:23 | Example 4 GBPUSD, four daily candles |
| 16:09 | Example 5 short after previous day low taken |
| 18:43 | Session results: 80%, 2.79R; 2R minimum math |

## Mistakes and warnings
- Entering when the POI is not respected and short-term lows were already taken before entry (06:56).
- Candle 3 that trades the wrong side first then back into range: concerning (06:23, 07:06).
- Treating a bearish close back inside the range as a bullish closure (11:52).
- Trusting LTF lows that never reached a POI (12:30).
- Overthinking the daily chart (14:26).
- Five-trade win rate is not representative (19:01).

## Conflicts and open questions
- Page lists "Ignoring range EQ: entries after reaching through range EQ often don't expand"; the video only says entries in the upper/lower half of the previous day's range.
- Page says backtest win rate "~40-80%"; video shows 80% over 5 trades.
- "Upper half or lower half" (02:17) is not mapped to direction in speech; page says bullish → "POI in the upper half of the previous day's range", which contradicts the usual discount logic (longs from lower half). Rule 8 here follows discount/premium by inference; needs confirmation.
- Example 3 replay clock reads about 05:05 (London) on the frame; the 5m entry time is not said.
- How far a closure "through" the POI must go before the bias is invalidated (05:32) is left to judgment.
- 34% breakeven at 2R ignores costs (1/3 = 33.3%).

## Glossary additions
- `Tradesella` (03:10): Tradezella (journal/backtesting platform; playbook "TTrades").
- `wretched above` (02:43): "reached above".
- `RTP` (13:15): "our TP".
- `downclo candles` (15:23): down-close candles.
- `manipulation leg`: leg used for -1 standard deviation projection.
