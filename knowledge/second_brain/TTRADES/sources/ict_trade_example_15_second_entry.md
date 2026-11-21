---
title: "ICT Trade Example - 15 Second Entry"
type: ttrades-source
slug: ict_trade_example_15_second_entry
source: youtube
youtube_id: k_Qoou9vi5c
youtube_url: https://www.youtube.com/watch?v=k_Qoou9vi5c
partition: trade_review
duration_min: 2
recorded: 2022-09-14
format: trade-review
speakers: [ttrades]
instruments: [ES]
timeframes: [15m, 1m, 15s]
concepts: [liquidity-sweep, ote, entry, stop-placement, consolidation, retracement, trade-management, risk]
transcript: "[[../../ttfm_video_corpus/transcripts/ict_trade_example_15_second_entry.txt]]"
page: "none"
confidence: low
---

# ICT Trade Example - 15 Second Entry

## TL;DR
A 2-minute, music-only trade recap with no narration. Everything here is read from the chart and the on-screen captions. ES on 14 Sep 2022: a 15m consolidation marked "bullish", a 1m sweep of the range lows near the NY open, then a long planned on the 15-second chart at the Fib 0.62 of the sweep-up leg, stop under the swept low, about 3R. The NinjaTrader execution replay shows a counter-trend scalp short first ("bad market fill"), then a 4-lot long near the 0.62. Order problems followed, and the position was closed manually. This is an ICT-era example of a sweep + OTE entry on a seconds chart; it carries no TTFM candle 2/3 or CISD language.

Source note: the corpus transcript contains only song lyrics and "[Music]" (no teaching speech). The local mp4 in `ttfm_video_corpus/videos/` is truncated (49 KB, ffmpeg "partial file"), and the corpus has no frames for this slug. Frames below come from a fresh yt-dlp download viewed on 2026-11-20. No quotes are possible.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | Read higher-timeframe context first: a 15m consolidation range is marked and labelled "bullish" before dropping down. | consolidation | demonstrated | 00:08 | none (no speech) |
| 2 | On the 1m, the trigger is a sweep of the consolidation's range lows, followed by a sharp move back up. | liquidity-sweep | demonstrated | 00:17 | none (no speech) |
| 3 | Plan the long at a retracement of the sweep-up leg: a Fib drawn from the swept low to the high, with 0.5, 0.62 and 0.79 levels; the entry sits at about 0.62. | ote | demonstrated | 00:20 | none (no speech) |
| 4 | Stop just below the swept low. | stop-placement | demonstrated | 00:28 | none (no speech) |
| 5 | The planned trade is about 3R (TradingView position tool: stop 3.50 pts, target 10.75 pts, R:R 3.07). | risk | demonstrated | 00:28 | none (no speech) |
| 6 | Use a seconds chart (15s) to refine the entry inside the 1m retracement. | entry | demonstrated | 00:24 | none (no speech) |
| 7 | A counter-trend scalp short was taken into the expected retracement before the long; the caption calls it a counter-trend scalp with a bad market fill. | retracement | demonstrated | 00:40 | none (no speech) |
| 8 | Scale out with several limit targets (multiple "Target" fills of 1 contract) while keeping a protective stop on the rest. | trade-management | demonstrated | 01:05 | none (no speech) |

## Definitions
- **15 second entry**: entry timed on a 15-second chart (TradingView "15s", NinjaTrader replay) after the setup forms on 15m/1m (00:24).

## Procedure / checklist
1. 15m: mark the consolidation range and the expected direction ("bullish") (00:08-00:13).
2. 1m: wait for a sweep of the range lows and a strong move back up (00:17-00:20).
3. 15s: Fib the sweep-up leg, place a limit near 0.62, stop below the swept low, target about 3R (00:20-00:28).
4. Manage with partial limit targets and a stop (01:05-01:50).

## Worked examples
### Example 1: ES1 (S&P 500 E-mini), 14 Sep 2022, NY morning (00:06-02:04)
- 15m (00:08-00:13): chart reads 13-14 Sep '22. Drop, then a range with marked highs/lows, dashed trendlines diverging, arrow up and text "bullish".
- 1m (00:17-00:20): a grey zone marks the range lows near 3949.50; price wicks into it around 09:35-09:37 (UTC-4) and rallies to about 3972. A side schematic shows 0.5 / 0.62 levels, a grey zone and a projected path: dip, then up.
- 15s (00:24-00:28): Fib from the swept low to the swing high, with 0.5, 0.62 and 0.79 lines. Long position tool from about 3953.5 (0.62) with stop about 3950.00 (3.50 pts, below the 3949.50 swept low) and target about 3964.25 (10.75 pts), R:R 3.07. The label reads "Closed P&L: 10.75" (on the position tool, not the account).
- NinjaTrader execution replay (00:32-02:04):
  - Short 4 @ 3957.50 with caption "expecting retracement to get long, counter trend scalp (bad market fill)" (00:40). Buy targets at about 3956.00 (1-lot fills).
  - Right-click menu shows "Buy Limit 4 @ 3953.75" (01:05). Caption "ninja cancelled my order, had to submit order again" (about 01:08).
  - Long entry shown as 4 @ 3953.75 with a 1 @ 3954.00 fill, Sell LMT targets above and a Sell STP below (01:20-01:50). The P&L box shows 9.25 at 01:50.
  - Caption "ninja didnt fill so cancelled and closed position" (about 02:00). Exit price not readable.
- Outcome: price rallied well above the entry. The actual realized result is not shown.

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:00 | Intro card (TTRADES) |
| 00:08 | ES 15m: consolidation, "bullish" |
| 00:16 | Discord screenshot (chat; not legible at this resolution) |
| 00:17 | ES 1m: sweep of range lows, schematic |
| 00:24 | ES 15s: Fib 0.5/0.62/0.79, long position ~3R |
| 00:32 | NinjaTrader replay: counter-trend scalp short |
| 01:05 | Re-submitted buy limit, long 4 @ 3953.75 |
| 02:00 | Targets not filled; cancelled and closed |
| 02:04 | Outro card |

## Mistakes and warnings
- On-screen caption flags the counter-trend scalp short as a "bad market fill" (00:40).
- Platform/order issues: "ninja cancelled my order, had to submit order again" (01:08) and "ninja didnt fill so cancelled and closed position" (02:00).

## Conflicts and open questions
- The corpus transcript is music lyrics (YouTube captions of the soundtrack), not teaching; the index has nothing to check quotes against.
- The local mp4 is a truncated download, so dense/labelled frames for this slug are missing from the corpus.
- The TradingView position tool (entry ~3953.5, R:R 3.07, "Closed P&L 10.75") and the NinjaTrader fills (short 3957.50 scalp, long 3953.75, manual close) disagree about what was actually realized. The planned trade and the executed trade are not the same.
- Why the counter-trend short was taken against a "bullish" read is only explained by the caption "expecting retracement to get long".
- Prices are read from low-resolution frames; treat them as approximate (±0.25).

## Glossary additions
- `15s` (15 second chart): seconds-timeframe execution chart.
- `ninja` (NinjaTrader): execution platform shown in the replay.
