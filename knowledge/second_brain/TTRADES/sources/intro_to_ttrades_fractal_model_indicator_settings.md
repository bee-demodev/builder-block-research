---
title: "Intro To TTrades Fractal Model [Indicator & Settings]"
type: ttrades-source
slug: intro_to_ttrades_fractal_model_indicator_settings
source: youtube
youtube_id: CqMIh-Vvhbg
youtube_url: https://www.youtube.com/watch?v=CqMIh-Vvhbg
partition: educational_youtube
duration_min: 19
recorded: unknown
format: lesson
speakers: [ttrades]
instruments: [FX pair (ticker not legible), ES]
timeframes: [1D, 1h, 5m, 1m, 15m, 30m]
concepts: [ttfm-indicator, fractal-model, candle-2, candle-3, candle-4, cisd, protected-swing, swing-points, daily-bias, timeframe-pairing, time-of-day, targets, liquidity, equilibrium, consolidation, expansion, order-block, fvg, tooling]
transcript: "[[../../ttfm_video_corpus/transcripts/intro_to_ttrades_fractal_model_indicator_settings.txt]]"
page: "none"
confidence: high
---

# Intro To TTrades Fractal Model [Indicator & Settings]

## TL;DR
A short recap of the TTFM core loop (higher-timeframe sweep + close back inside the range, a lower-timeframe CISD that confirms the swing, then trading the next HTF candle's open-high-low-close) followed by a setting-by-setting walkthrough of the TTrades Fractal Model TradingView indicator (built "with the help of two degrees" [?]). It defines what the indicator draws: C2/C3/C4 labels with a gray/red/orange validity colour code, T-spot boxes (where the HTF wick should form), CISD lines, candle-1 sweep, candle equilibrium, projections drawn from the CISD bodies, formation liquidity, HTF open and time separators, time filters (kill zones) and an info table. It ends with three replays: stacking a second indicator copy on a lower pair (hourly T-spot overlapped by a 5m T-spot), a failed continuation flagged early by a close over the level, and an ES daily C2 where consolidation, manipulation and expansion reach formation liquidity. For Vik's companion app this is the closest thing to a spec for the indicator's objects and colours.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | No reversal without a swing point: a reversal is always preceded by the formation of a swing high/low. | swing-points | stated | 00:28 | "my fractal model relies on the foundational understanding that the market cannot reverse without a swing point" |
| 2 | Use HTF candle closures to judge a likely reversal: a sweep of the previous candle's high then a close back inside its range makes him bearish (target previous-day low). | candle-2 | stated | 00:48-01:01 | "price has swept out its previous candle high and then closed back inside the range" |
| 3 | Confirm the HTF bias by dropping one pair down (1D -> 1h) and requiring a CISD: a close through the series of up-close candles that made the high. | cisd | stated | 01:12-01:27 | "you can see we have closed through the series of up closed candles that have made this high" |
| 4 | Once the CISD closes through, the high that made it is considered protected. | protected-swing | stated | 01:29-01:32 | "so I consider this High protected" |
| 5 | After the HTF closure + CISD, trade the following HTF candle's open-high-low-close in the bias direction (for a bearish day: open, high, then lower, close). | daily-profile | stated | 01:32-01:37 | "and then I will look to trade the Open high low close in the following candle" |
| 6 | Entry example: on the close of the LTF candle that closes through the down/up-close candle that made the sweep high, stop on the high, target 2R. | entry | demonstrated | 02:07-02:20 | "I could put on a position on the close of this candle my stop on the high and looking for 2 R" |
| 7 | The T-spot is the zone inside the next HTF candle where he expects the HTF wick to form; for a short he wants price to trade into the gray box, form a high, then trade lower. | ttfm-indicator | stated | 03:17-03:30 | "Mark out a t-spot which is an area that I look for higher time frame Wicks to be formed" |
| 8 | After a bearish HTF close, look for continuation in the following candle (candle 4). | candle-4 | stated | 03:44-03:51 | "because we have closed bearish I will then look for a continuation in this following candle" |
| 9 | The model is fractal: the same logic applies on any timeframe pair (1D-1h, 1h-5m, 15m-1m); in Automatic mode the indicator picks the pair from the chart timeframe. | timeframe-pairing | stated | 04:11-04:29 | "since my model is fractal hence the name of the fractal model I can apply this on multiple time frames" |
| 10 | Setting a bias (bullish/bearish) hides opposite-direction setups; neutral shows both. | daily-bias | stated | 07:06-07:38 | "if I don't have any bias or a neutral bias I can select neutral and it will show me both bearish and bullish setups" |
| 11 | Validity colour code: gray C2 = setup stayed valid through candle 4; red C2 = failed in the first candle after; orange C2 = failed in the second candle after. | candle-2 | stated | 06:50-07:03 | "a gray C2 is when the setup has remained valid throughout candle 4 a red C2 is when that setup fails within the first candle" |
| 12 | Time filters (kill zones, up to 3) are applied on whole HTF candles: to include the 8:00 hourly close you must start the filter at 7:00. | time-of-day | stated | 07:58-08:13 | "it's going to choose the whole hours candle so this means I would have to wait for the 9:00 a.m. closure" |
| 13 | Time filters only apply at or below the "Apply below" timeframe; a filter set for 30m and below will hide setups on the hourly until adjusted. | ttfm-indicator | stated | 12:33-12:59 | "this time filter will only apply on the 30 minute time frame or below for the this given Kill Zone" |
| 14 | Projections (targets) are drawn from the series of bodies of the CISD; defaults are negative standard-deviation levels and custom ones can be appended comma-separated. | targets | stated | 11:44-12:07 | "these are currently drawn from the bodies so the series of bodies in the change in the state of delivery" |
| 15 | Formation liquidity marks the previous candle's / previous day's low (for a bearish closure) that has not yet been taken; already-taken lows are not marked. | liquidity | stated | 13:04-13:27 | "I want to see price run out previous candle's lows or previous day's lows" |
| 16 | Vertical open/close time lines separating each HTF candle's OHLC are "very important" to his analysis. | ttfm-indicator | stated | 09:41-09:49 | "open close time is going to be those vertical lines which I find very important in my analysis" |
| 17 | Overlap: run a second indicator copy on the lower pair so an HTF T-spot can be refined by an LTF (5m) T-spot; entry either directly with stop at invalidation or after a confirmation setup inside. | top-down-alignment | demonstrated | 14:12-15:21 | "I could either just take an entry here with my stop on an invalidation or look for a confirmation setup" |
| 18 | A counter-HTF LTF setup that prints inside an HTF setup tends to fail right away. | fractal-model | demonstrated | 15:31-15:40 | "that did fail right away as it was opposing the higher time frame one" |
| 19 | When price closes over the level you need to hold for continuation, the indicator turns it red and that close is the early warning the continuation is unlikely. | candle-4 | stated | 15:53-16:09 | "that closure right there over my level was the early warning that this setup was not likely to continue" |
| 20 | A failed continuation from a bearish setup can itself create the opposite (bullish) candle-2 closure. | reversal | demonstrated | 16:49-17:00 | "the continuation from this bearish setup has failed and that is what actually creates the bullish candle to closure" |
| 21 | In a bullish setup, a close through the opposing (down-close) candles forms an order block he can enter in, stop on the low, target 2R; after the close over down-close candles he expects that low to hold. | order-block | demonstrated | 17:06-17:38 | "that would be an order block I could look to take an entry in here my stop on this low and looking for 2 R" |
| 22 | For continuation lower, price should hold / not close over the T-spot area. | candle-3 | stated | 18:23-18:28 | "I'd like to see price hold or not close over this t-spot area here" |
| 23 | Consolidation into the session means expect a manipulation of one side before expansion, ideally into formation liquidity in line with projections. | consolidation | stated | 18:37-18:58 | "with a consolidation I'd like to see a manipulation before we get expansion" |

## Definitions
- **Fractal model (TTFM)**: HTF candle closure (sweep of the prior candle's extreme + close back inside), LTF CISD confirming the swing, then trading the next HTF candle's OHLC in that direction; applicable on any timeframe pair (00:28-02:46, 04:11).
- **CISD (change in the state of delivery)**: a close through the series of up-close candles that made the high (bearish) or down-close candles that made the low (bullish) (01:12-01:27, 02:04-02:10).
- **Protected high/low**: the swing extreme that the CISD confirmed; the trade's invalidation (01:29).
- **T-spot**: shaded box in the next HTF candle where he expects the HTF wick to form ("open high, go lower, close" for a short, high forms in the box). Default colours gray and green (03:17, 11:19-11:42).
- **C2 / C3 / C4**: higher-timeframe candle-2, candle-3 closures and candle-4 continuation; requirements are taught in his course/mentorship, not here (06:16-06:35).
- **Candle 1 sweep**: line marking the first candle's extreme that was swept by the HTF closure, drawn on HTF and LTF (10:29-10:40).
- **Candle equilibrium (EQ)**: the midpoint of the HTF candle, drawn on both HTF and LTF (11:05-11:17).
- **Projections**: standard-deviation targets drawn from the CISD bodies; default list visible as "-1, -2, -2.5, ..." (truncated in frame 12:07) under an "ORDERBLOCK PROJECTIONS" heading (11:44-12:30).
- **Formation liquidity**: dotted line at the untaken previous candle / previous day low (bearish) or high (bullish) the setup should draw to (13:04-13:27).
- **HTF candles / power of three candles**: the HTF candles drawn to the right of the chart, sizes small/medium/large, with offset (08:28-09:21).
- **Time until close / info table**: table showing timeframe, asset, fractal pair (e.g. daily and hourly in Automatic), time until HTF close, bias, time filters (13:31-13:55).

## Procedure / checklist
1. HTF candle sweeps the prior candle's high (low) and closes back inside its range -> bearish (bullish) next candle, draw to previous-day low (high) (00:48-01:06).
2. Drop to the paired LTF (1D -> 1h; 1h -> 5m) and wait for a CISD that closes through the candles that made the extreme; that extreme becomes protected (01:12-01:32).
3. In the next HTF candle, expect price to trade into the T-spot, form the HTF wick, then expand in the bias direction (03:17-03:30).
4. Entry on the LTF close through the opposing candle(s), stop on the protected extreme, target 2R or projections / formation liquidity (02:07-02:20, 18:45-18:58).
5. Optional refinement: stack a second indicator copy on the lower pair (hide its HTF candles) to get an LTF T-spot inside the HTF T-spot (14:30-15:12).
6. Manage continuation: after a bearish HTF close look for candle 4 continuation; a close over the hold level (indicator turns red) is the early warning to stand aside (03:44, 15:53-16:09).

Indicator settings walked through, in order (05:05-13:55): Warnings/error messages (on: warns when the chart TF is above the pair's LTF, e.g. 5m chart on a 1m-15m model); Alerts; History (0 = current setup only, up to 40, shown as 15 in frame); Fractal (Automatic or fixed pair) with C2/C3/C4 toggles; Bias (Bullish/Bearish/Neutral); Time filter "Apply below" + up to 3 filters (frame at 06:35 shows 02:00-05:00, 08:00-11:00, 13:30-16:15); HTF candles (hide, size, offset, body/border/wick colours); HTF open (solid/dashed/dotted); open/close time vertical lines; low and high lines per HTF candle (he leaves off); TTFM labels and size; Candle 1 sweep; bullish/bearish CISD colours; candle equilibrium; T-spot; projections + labels; formation liquidity; info table.

## Worked examples
### Example 1: FX pair (ticker not legible), 1D-1h (00:28-02:46)
- Daily candle sweeps the previous candle's high, closes back inside -> bearish next day, draw to previous-day low (00:48-01:06).
- Hourly CISD: close through the up-close series that made the high; that high is protected (01:12-01:32).
- Next day: price sweeps a high to the left, opposing candle formation forms the wick; options: enter next candle, next hourly candle, or wait for New York (01:39-02:00).
- Into New York, price sweeps a high to the left and closes through the down-close candle that made it [speech says down-close; for a short entry this would normally be the up-close candle]; entry on that close, stop on the high, 2R target; TP hit after some waiting (02:00-02:25).
- Replayed with the indicator (02:59-04:03): C2 label, projections, T-spot; next day bearish close -> continuation lower to the lows to the left.

### Example 2: same move on 1h-5m with bias = bearish (04:03-05:02)
- Drops to the 5m, indicator auto-adjusts to the hourly-5m pair; with bias set to bearish only bearish setups show. HTF closure prints, he anticipates the hourly wick in the T-spot; price respects it and continues to the lows and the standard-deviation projections.

### Example 3: hourly T-spot overlapped with 5m T-spot (14:12-16:09)
- In an HTF T-spot price sweeps consolidation highs and closes back inside the previous bar -> looking lower. Second indicator copy on Automatic, 5m chart, HTF candles hidden; a 5m setup prints with its own T-spot (14:21-15:12).
- Entry either immediately with stop at invalidation or on a confirmation setup inside; price trades lower; a bullish 5m setup inside fails right away because it opposes the HTF (15:12-15:40).
- Then price closes over the continuation level -> red; that close was the early warning (15:40-16:09).

### Example 4: daily candle 2 -> bullish hourly setup with FVG (16:12-17:44)
- Next day a daily candle-2 closure sets up an hourly setup; he wants the HTF wick in the T-spot area where there is an FVG (16:17-16:36).
- 1h-5m: a bearish setup prints but its continuation fails, which creates the bullish candle-2 closure (16:43-17:00). Hourly T-spot must hold, 5m T-spot inside it; close through opposing candles = order block entry, stop on the low, 2R (17:00-17:16).
- Continuation higher; candle-4 continuation expected after the close over down-close candles; TP hit (17:16-17:44).

### Example 5: ES 1D-1h (18:02-19:04)
- Daily closes inside the previous-day high: candle-2 closure with CISD; projections from the reversal (18:02-18:23).
- For continuation lower price should not close over the T-spot. New York opens in consolidation -> expects manipulation of one side, then expansion to formation liquidity / previous-day low in line with projections; price manipulates one side, then expands to those lows and hits the targets (18:32-19:07).

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:10 | Intro: fractal model basics + indicator settings |
| 00:28 | Swing point needed to reverse; HTF candle closures |
| 01:12 | Hourly CISD confirms; protected high; trade next candle OHLC |
| 02:00 | New York entry, stop on high, 2R |
| 02:27 | Recap of the three foundations |
| 02:52 | Indicator replay: C2, projections, T-spot, continuation |
| 04:03 | Same setup on 1h-5m, bias filter |
| 05:05 | Settings: warnings, alerts, history |
| 06:16 | C2/C3/C4 toggles and validity colours |
| 07:06 | Bias setting |
| 07:40 | Time filters (kill zones), whole-hour rule, up to 3 |
| 08:28 | HTF candles, offset, colours, HTF open, open/close lines, high/low lines |
| 10:12 | Model style: labels, candle 1 sweep, CISD colours, candle EQ, T-spot |
| 11:44 | Projections and labels |
| 12:32 | Why a setup is not shown on the hourly: "Apply below" time filter |
| 13:04 | Formation liquidity |
| 13:31 | Info table |
| 14:10 | Overlapping indicators: hourly + 5m T-spots |
| 16:12 | Daily C2 -> bullish setup with FVG and order block entry |
| 18:02 | ES daily example: consolidation, manipulation, expansion to formation liquidity |

## Mistakes and warnings
- Viewing a model on a chart timeframe above its LTF (e.g. 5m chart for the 1m-15m model) shows nothing; keep warnings on to see why (05:07-05:32).
- A time filter whose "Apply below" is lower than the current chart hides valid setups on that chart (12:33-12:59).
- Kill-zone filters snap to whole HTF candles; set the start one hour early to include the 8:00 hourly candle (07:58-08:13).
- Stacking two copies without hiding the second copy's HTF candles makes the 5m chart messy (14:48-15:00).
- Taking LTF setups against the HTF setup: they fail right away (15:31-15:40).

## Conflicts and open questions
- 02:07: speech says he closes "through the down close candle that made that high" for a short entry; under his own CISD definition the high is made by up-close candles. Likely a slip; frame not checked at that second.
- C2/C3/C4 requirements are explicitly deferred to the course/mentorship (06:20); this video does not define what separates a C2 from a C3 closure.
- Default projection values are only partly legible ("-1, -2, -2.5, ..."); the full default list is not spoken.
- T-spot boundaries (how the box's top/bottom are computed) are not stated; only its role (where the HTF wick forms).
- Formation liquidity: "previous candle's lows or previous day's lows" without a rule for which one when both are untaken.
- "with the help of two degrees" (02:54) is probably a person or collaborator name misheard; not resolved.
- The red/orange failure colours mean "fails within the first / second candle after", but what counts as "fail" (close over protected swing? close over T-spot?) is not defined here.

## Glossary additions
- `t-spot` (aliases: "t-pot", "te-spot", "T-Spot"): indicator box in the next HTF candle where the HTF wick is expected to form.
- `formation liquidity`: indicator dotted line at the untaken prior-candle / prior-day extreme opposite the setup's protected swing.
- `candle 1 sweep`: indicator line at the extreme of candle 1 swept by the HTF closure.
- `candle to closure` (mishearing): candle 2 closure.
- `two degrees` (unresolved): named collaborator on the indicator, transcription uncertain.
