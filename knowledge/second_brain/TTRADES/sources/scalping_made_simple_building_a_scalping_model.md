---
title: "Scalping Made Simple - Building A Scalping Model"
type: ttrades-source
slug: scalping_made_simple_building_a_scalping_model
source: youtube
youtube_id: 1uw4Vgyk9lc
youtube_url: https://www.youtube.com/watch?v=1uw4Vgyk9lc
partition: educational_youtube
duration_min: 6
recorded: unknown
format: playbook
speakers: [ttrades]
instruments: [NQ]
timeframes: [1m]
concepts: [entry, ote, liquidity-sweep, stop-placement, targets, trade-management, premium-discount, tooling]
transcript: "[[../../ttfm_video_corpus/transcripts/scalping_made_simple_building_a_scalping_model.txt]]"
page: "none"
confidence: high
---

# Scalping Made Simple - Building A Scalping Model

## TL;DR
Short pre-TTFM playbook: a strategy needs three things: entry criteria, stop placement, and where to take profit and/or move the stop to break even. His scalping model: a stop hunt (aggressive move beyond a recent high/low and aggressive move back into the range) followed by an OTE entry (0.62 fib of the stop-hunt leg back in), stop at the stop-hunt extreme, first partial / break even at the low (or high) that the OTE leg created. OTE gives over 1.5 R:R, allowing a lower win rate. Two NQ 1m examples, then a TFO-coded indicator that automates the stop-hunt + OTE criteria. Not a TTFM model; useful as an early rules-to-indicator template.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | A strategy needs entry criteria, stop placement, and a profit / break-even rule. | trade-management | stated | 00:09 | "There are three things that I need to know when building a strategy, and that is criteria for entry, stop placement, and where I'm going to take my profit" |
| 2 | Entry criteria: a stop hunt, then an OTE entry. | entry | stated | 00:09 | "So in this model, I decided on a stop hunt and then an OTE entry. This is my criteria for entry." |
| 3 | Stop always at the stop-hunt extreme; first profit or break even after price breaks the low created for the OTE leg. | stop-placement | stated | 00:38 | "I always place my stop at this high and then I take my first profit or move my stop to break even after we break through this low" |
| 4 | OTE is chosen because it gives over 1.5 R:R, which tolerates a lower win rate. | ote | stated | 00:38 | "it creates a risk to reward over 1.5 which allows me to have a lower win rate." |
| 5 | Mark recent highs and lows; those are what the strategy wants taken. | liquidity | stated | 01:28 | "I'm going to mark out recent highs and lows as that is what I am looking to be taken out in this strategy." |
| 6 | A stop hunt requires an aggressive move out of the range and an aggressive move back in; otherwise disregard. | liquidity-sweep | stated | 01:28 | "I want to see an aggressive move out and then back into the range." |
| 7 | An invalid sweep becomes the new high to watch. | liquidity-sweep | demonstrated | 01:57 | "So this doesn't validate the criteria for my entry, so I disregard it, but I now have a new high to be watching." |
| 8 | OTE entry at the 0.62 of the leg from the stop-hunt high to the current low, tracked as the low extends. | ote | stated | 02:33 | "from this high to the current low, I'm going to be looking for the 0.62 as far as it goes down." |
| 9 | Moving beyond an old low without returning into the range is invalid. | liquidity-sweep | demonstrated | 03:14 | "you can see we move below this low, but we don't move back into the range. So this is invalid" |
| 10 | Bullish version: stop on the swept low, first TP / break even at the high of the leg; full target the highs or premium of the range. | targets | demonstrated | 03:46 | "Well, either these highs up here, or when we reach into a premium of the range" |
| 11 | Defined rules can be coded into an indicator. | tooling | stated | 04:26 | "The nice thing about creating a model with defined rules is that it can be coded and turned into an indicator." |
| 12 | Indicator logic: aggressive take of a high, aggressive displacement back in, fib drawn, OTE highlighted, swing high formed in the OTE, then move down. | tooling | demonstrated | 04:56 | "the indicator draws a fib and highlights the OTE here and shows when it creates a swing high in that OTE" |
| 13 | No aggressive move back in or no swing formed in the OTE = no trade even if there is a reaction. | entry | demonstrated | 05:25 | "as we couldn't displace below here, there's no aggressive move back in, or swing low put in." |

## Definitions
- **Stop hunt**: aggressive move beyond a recent high/low and aggressive move back into the range (01:28, 03:14).
- **OTE (optimal trade entry)**: fib retracement of the leg back into the range; he uses 0.62 (02:33).
- **First TP / break even**: the low (bearish) or high (bullish) of the OTE leg; on its break, take a partial or move stop to break even (00:38, 04:26).

## Procedure / checklist
1. Mark recent highs/lows and old highs/lows on NQ 1m (01:28, 03:14).
2. Wait for an aggressive move beyond one and an aggressive move back into the range (01:28).
3. Draw a fib from the stop-hunt extreme to the current extreme of the move back in; track it as it extends (02:33).
4. Enter at 0.62; stop at the stop-hunt extreme (02:33, 03:46).
5. First partial / break even at the leg's extreme; final target the opposite highs/lows or premium/discount of the range (04:26).

## Worked examples
### Example 1: NQ 1m short (01:28-03:14)
- High and low marked. First high taken without an aggressive return -> disregarded; new high to watch. Next: aggressive move over the high with a large wick and aggressive fall back -> stop hunt. 0.62 entry, stop on the high, target/partial at the low; target hit.

### Example 2: NQ 1m long off old lows (03:14-04:26)
- First old low broken without returning into the range -> invalid. Next low: aggressive move down and back in -> OTE entry, stop on the low, first TP / break even at the high; targets the highs or premium of the range.

### Example 3: TFO indicator (04:26-05:49)
- Friend TFO coded the criteria: draws the fib, highlights OTE, marks the swing in the OTE. One reaction without an aggressive move back in or swing = no signal; one valid long. Settings: stop-hunt sensitivity, inducement, volume spikes, OTE, trend/counter-trend.

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:09 | Three components of a strategy; stop hunt + OTE |
| 00:38 | Stop, first TP / break even; why OTE (1.5R) |
| 01:28 | NQ 1m short example |
| 03:14 | NQ 1m old lows; long example |
| 04:26 | Rules -> indicator; TFO indicator demo |
| 05:49 | Thanks, link in description |

## Mistakes and warnings
- Taking a sweep without an aggressive move back into the range (01:57, 03:14).

## Conflicts and open questions
- "Aggressive" is undefined; the indicator exposes a sensitivity setting for it (05:25).
- OTE given as 0.62 only; the usual OTE band (0.62-0.79) is not mentioned, and whether entry needs a swing in the OTE (indicator) vs a limit at 0.62 (manual) differs.
- "Recent highs and lows" has no lookback.

## Glossary additions
- `TFO`: friend who coded the indicator (link in description).
- `OTE` = optimal trade entry (0.62 here).
