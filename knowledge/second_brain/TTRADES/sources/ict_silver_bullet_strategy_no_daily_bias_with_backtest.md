---
title: "ICT Silver Bullet Strategy - No Daily Bias | With Backtest!"
type: ttrades-source
slug: ict_silver_bullet_strategy_no_daily_bias_with_backtest
source: youtube
youtube_id: o0v4KQxZbpU
youtube_url: https://www.youtube.com/watch?v=o0v4KQxZbpU
partition: educational_youtube
duration_min: 27
recorded: unknown
format: playbook
speakers: [ttrades]
instruments: [NQ, NAS100]
timeframes: [1h, 1m]
concepts: [silver-bullet, time-of-day, new-york-session, liquidity-sweep, reversal, breaker, fvg, order-block, entry, stop-placement, targets, trade-management, backtesting]
transcript: "[[../../ttfm_video_corpus/transcripts/ict_silver_bullet_strategy_no_daily_bias_with_backtest.txt]]"
page: "none"
confidence: high
---

# ICT Silver Bullet Strategy - No Daily Bias | With Backtest!

## TL;DR
An early ICT-era playbook plus an FX Replay backtest of a New York AM "silver bullet" on NQ that needs no daily bias. At 10:00 he marks the high and low of the 9 AM hourly candle (the previous hour's range, an early form of the TTFM "previous candle high/low frames the reversal" idea). Inside the 10:00-11:00 window he waits for a stop raid of one side, then on the 1m wants aggressive displacement back the other way and enters on a breaker, FVG or order block; stop on the sweep extreme, target the opposite side of the 9 AM candle. Entries must fill before 11:00. In the backtest he moves the stop to break-even at 3R. Result: 15 trades in 45 days (July plus half of August, year not said), average RR about 5, +23.5% July, +16.93% August, +44.41% total at 1% risk per trade; he calls the sample small.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | Only take entries that appear between 10:00 and 11:00 New York (AM silver bullet window). | time-of-day | stated | 00:03 | "The only time I will take entries is if it appears between 10 and 11 AM." |
| 2 | Frame the reversal with the previous hour's high and low, i.e. the 9 AM hourly candle, marked once 10:00 hits. | liquidity | stated | 00:38 | "in this framework, I'm going to use the previous hours high and low. And in this case, that's the 9am hourly candle." |
| 3 | Wait for price to take one side of the 9 AM range, then look for an entry targeting the opposite side. | liquidity-sweep | stated | 01:07 | "Price to take one side of this range. So in this case, it takes the 9am high. And then I look for a entry to target the 9am low." |
| 4 | The setup trigger is a stop raid above the 9 AM high or below the 9 AM low inside the window; then look for an entry model the other way. | liquidity-sweep | stated | 01:37 | "All I do is sit back and wait for a stop raid to occur below this low or above this high." |
| 5 | If neither side of the 9 AM range is swept within 10:00-11:00, there is no trade that session. | time-of-day | stated | 03:19 | "price never swept the low or the high of this range, so this would be a session where I would not be looking to take a trade." |
| 6 | After the raid, require displacement back the other way before entering; no displacement means wait. | expansion | demonstrated | 02:08 | "No displacement down yet." |
| 7 | Entry arrays used: order block, FVG (or its consequent encroachment), breaker, midnight opening price confluence. | entry | demonstrated | 02:08 | "We have a fair value gap there as well and midnight opening price. So what I'll do is I'll look to take a short entry." |
| 8 | Stop goes on the sweep high/low; target is the other side of the previous hour's candle. | stop-placement | demonstrated | 02:48 | "my stop on this high, and where am I targeting the other side of this previous hours candle." |
| 9 | A breaker forms when price closes below the low that made the new high (short) or above the corresponding high (long); enter on the breaker. | breaker | demonstrated | 05:34 | "Now I wanna see if we can close below this low that made the new high. Okay, so we do. So what I'm gonna mark out is this breaker block here." |
| 10 | The limit order must fill before 11:00; if it does not, cancel it. | time-of-day | stated | 09:14 | "we cancel our order, because it's outside the 11am window." |
| 11 | Risk 1% per trade in the backtest. | risk | demonstrated | 05:34 | "So click here, hit place order, risking 1%, sell limit." |
| 12 | Move the stop to break-even once the trade reaches 3R. | trade-management | stated | 06:09 | "what I did in backtesting was once this hits 3R, I will move my stop to break even." |
| 13 | Equal highs touched without running are not counted as a sweep. | liquidity-sweep | stated | 09:57 | "We do touch that high. I don't really consider that a sweep, just equal highs." |
| 14 | A small FVG after a shallow sweep is not enough; he wants more aggressive displacement. | expansion | stated | 08:02 | "Not super convincing to me. I want to see a more aggressive displacement down." |
| 15 | Skip setups where the stop would need to sit above nearby equal highs and the price action has no clear displacement. | stop-placement | demonstrated | 14:33 | "There's no clear displacement. And then if I was to enter in here, we have equal highs, and I want my stop up there." |
| 16 | After a sweep he wants it met immediately by aggressive displacement; a mere retracement suggests continuation the sweep's way. | reversal | stated | 15:55 | "I'd want to see this met immediately with aggressive displacement higher, or if we just get a retracement, it's likely to go lower." |
| 17 | Prefer a lower-timeframe sweep forming the entry model, not just the raw range sweep. | liquidity-sweep | stated | 15:55 | "I'd like to see a lower timeframe sweep, so the entry model below here, not just this." |
| 18 | Do not enter once price has already almost reached the target; prefer entries on the sell side of the curve, not when price is coming back. | entry | stated | 19:08 | "Generally, once it already reaches almost to that low, I'm not really looking to enter that. I prefer the entry on the sell side of the curve" |
| 19 | If the 10 AM candle already took one side and price does not come back into the range, the opposite side is unlikely. | liquidity | stated | 20:27 | "Seems the 10 AM candle just took this low, so if we don't come back into the range, not a large possibility of going for that high." |
| 20 | No trade when the structure cannot be read. | entry | stated | 20:27 | "I'm not going to do anything about it because I can't see the structure." |
| 21 | When the target is only about 3R, there is no need to project a fib for the break-even point. | trade-management | stated | 21:02 | "And that's just at 3R, so no reason to project a FIB." |
| 22 | Before entering on an order block, wait for the third candle to close beyond the swept low (structure) rather than enter early. | order-block | demonstrated | 23:52 | "I want to see this third candle close below here before returning to this order block." |
| 23 | Very shallow sweeps without displacement or FVGs are low quality. | liquidity-sweep | stated | 26:37 | "It's very shallow, which not a huge fan of that. No real displacement up, no fair value gaps, just met." |
| 24 | A 45-day, 15-trade backtest is too small; a deeper backtest is needed to judge the model. | backtesting | stated | 28:02 | "Now it's important to notice I only tested this over 45 days and 15 trades." |

## Definitions
- **Silver bullet window (AM)**: 10:00-11:00 New York; entries only inside it (00:03, 03:19).
- **Framing range**: high and low of the 9 AM hourly candle, the previous hour at 10:00 (00:38).
- **Stop raid**: price trading through the 9 AM high or low inside the window (01:37).
- **Breaker (as used)**: after a new high, the candle range whose low is closed through; entry on the return to it (05:34, 07:24).
- **Order block (as used)**: the last opposite-close candle (e.g. down-close before the move up) that supports or resists price; an order block "inside this mitigation or breaker" (09:57-10:39).
- **Consequent encroachment**: midpoint of the FVG, used as an entry level (02:48).

## Procedure / checklist
1. At 10:00 on the 1h, mark the 9 AM candle's high and low (00:38, 01:37); drop to 1m and mark 10:00 and 11:00 verticals (03:19).
2. Wait for a stop raid of one side inside the window (01:37). No raid by 11:00 means no trade (03:19).
3. Require aggressive displacement back into / through the range; skip shallow sweeps, equal-high touches and choppy action (08:02, 09:57, 15:55, 26:37).
4. Mark the entry array: breaker after a close through the low/high that made the extreme, FVG (or its CE), or order block (05:34, 02:48, 10:39).
5. Limit entry, stop on the sweep extreme, target the other side of the 9 AM candle (02:48, 05:34).
6. Order must fill before 11:00 or be cancelled (09:14).
7. Risk 1%; at 3R move the stop to break-even (05:34, 06:09); target may be held into the next day (06:45).

## Worked examples
### Example 1: NQ 1m (TradingView), date not said (01:37-02:48)
- 9 AM range marked (TFO session indicator draws it). Raid of the high, no displacement down at first, re-raid. Order block supporting price, FVG plus midnight opening price; short at midnight open / FVG CE, stop on the high, target the 9 AM low.
### Example 2: NQ 1m, no sweep (02:48-03:19)
- Price never swept either side between 10:00 and 11:00, so no trade.
### Example 3: FX Replay NAS100 CFD, first replay day (04:26-06:45)
- $100,000 account, July to current Friday. Shallow sweeps, aggressive move up, then a close below the low that made the new high; short on the breaker, stop on the high, target the 9 AM low. Filled right before 11:00; at 3R stop to break-even; target hit the next day.
### Example 4: FX Replay, next day (06:45-07:24)
- Sweep below the low, up-close candle before the sweep becomes a breaker after a close over it; long, stop at the low, target the other side; hit about 3.5R ("3.56 hour" is a mishearing of R).
### Example 5: FX Replay, short (08:02-08:36)
- Shallow sweep, small FVG rejected as not convincing, then aggressive displacement down; up-close candle entry, about 7.18R target, break-even at 3R, target hit.
### Example 6: Missed fills and cancellations (09:14-12:05)
- 09:14: FVG entry did not fill before 11:00; order cancelled. 11:22-12:05: FVG entry not tagged; the breaker would have filled for about 7.5R.
### Example 7: Losses (13:18-17:13, 21:02, 23:07)
- 13:18 FVG long stopped. 13:54 FVG stopped. 16:25 FVG plus breaker short stopped ("looks to be unlucky"). 21:02 long at 3R target stopped. 23:07 breaker stopped.
### Example 8: Backtest result (27:33-28:30)
- Average RR about 5, average trade 1 h 29 min, 15 trades over 45 days; July +23.5%, August (half) +16.93%, total +44.41%; Wednesday best day.

## Timeline
| Time | Topic (one line) |
|---|---|
| 00:03 | Scope: AM session silver bullet, NQ, 10-11 AM entries only |
| 00:38 | Framework: previous hour (9 AM) high/low frames the reversal |
| 01:37 | TradingView example 1: raid, displacement, OB/FVG/midnight open short |
| 02:48 | Example 2: no sweep, no trade |
| 03:54 | FX Replay setup (strategy, $100k, NAS100, July onward) |
| 04:26 | Replay day 1: breaker short, break-even at 3R |
| 06:45 | Replay days: breaker long, FVG and OB entries |
| 09:14 | Missed fill after 11:00, cancel order |
| 13:18 | Losses and skipped low-quality sweeps |
| 19:08 | Do not enter when price is already near the target |
| 23:52 | Waiting for the third candle close before an OB entry |
| 27:33 | Analytics: equity curve, RR about 5, +44.41% |
| 28:30 | FX Replay code; possible PM silver bullet video |

## Mistakes and warnings
- Taking a small FVG after a shallow sweep instead of waiting for aggressive displacement (08:02, 26:37).
- Treating equal-high touches as a sweep (09:57).
- Entering late when price is already returning to/near the target (19:08).
- Keeping orders live past 11:00 (09:14).
- Trading unreadable or choppy structure (20:27, 18:27).
- Over-reading a 15-trade backtest (28:02).

## Conflicts and open questions
- "Aggressive displacement" and "shallow sweep" have no number (points, % of range, candle count).
- Entry choice among breaker, FVG and order block is discretionary; at 12:05 the FVG choice missed a 7.5R the breaker would have caught. No rule picks one.
- Time zone is implied New York; he never says ET.
- At 06:09 the order "got tagged in right before 11 a.m." but the target filled the next day: the 11:00 cut-off applies to fills, not exits.
- Some losses he would have avoided by stop on a higher high (17:13 "Should I put my stop on that high?"); stop rule is "on the sweep extreme" but which extreme is unclear when there are several.
- Silver bullet is ICT terminology, not TTFM; the 9 AM-candle framing precedes his later candle 2/candle 3 logic.

## Glossary additions
- `silver bullet` (AM silver bullet, silver bullet window): ICT 10:00-11:00 NY entry window.
- `3.56 hour` (mishearing): 3.56R.
- `cell limit` (mishearing): sell limit.
- `TFO's indicator`: a session-range indicator he uses to draw the 9 AM range.
- `FX Replay`: backtesting platform used here.
