---
title: "Back Testing Live Session - FX Replay (2023-01-12)"
type: ttrades-source
slug: livestream_20230112_back_testing_live_session_fx_replay_8r6pxpeldiu
source: youtube-livestream
youtube_id: 8r6pXPEldiU
youtube_url: https://www.youtube.com/watch?v=8r6pXPEldiU
partition: livestream
recorded: 2023-01-12
format: live-session
speakers: [ttrades]
instruments: ["S&P500 (FX Replay feed, labelled 'S&P500')"]
timeframes: ["15m", "15m / 1D", "15m / 1H", "15m / 1m", "1D", "1H", "1H / 1D", "1m", "1m / 1H", "4H", "5m", "5m / 1H", "5m / 1m", "5m / 4H"]
concepts: ["time-of-day", "cisd", "daily-bias", "psychology", "poi", "prep-routine", "risk", "other", "equilibrium", "protected-swing", "fvg", "smt"]
transcript: "[[../../ttfm_video_corpus/transcripts/livestream_20230112_back_testing_live_session_fx_replay_8r6pxpeldiu.txt]]"
frames: "../../ttfm_video_corpus/livestream_frames/livestream_20230112_back_testing_live_session_fx_replay_8r6pxpeldiu/"
day_type: "Backtest/replay session, not a live market day; replayed S&P500 4-14 July 2022"
analysis: ../../ttfm_video_corpus/livestream_analysis/livestream_20230112_back_testing_live_session_fx_replay_8r6pxpeldiu.json
confidence: medium
---

# Back Testing Live Session - FX Replay (2023-01-12)

> [!info] Converted from the livestream analysis JSON (an Opus agent read the stream's frames and transcript).

## TL;DR
Evening stream (started 2023-01-11 ~19:56 NY) in which TTrades tries the FX Replay backtesting web app for the first time on an S&P500 feed, replaying July 2022 (symbol and month chosen by chat poll) with a $10,000 account and 1% risk. He shows his 2023-era ICT-style process: mark daily/4H/1H order blocks, fair value gaps and the draw on liquidity, mark midnight open and 8:30, then step the replay forward on higher timeframes and drop to 5m/1m for entries. He takes two replay trades: a 5m long on 4 Jul 2022 into the daily draw (10.83R, win) and a 4H short after a smart-money reversal off the daily order block (~3.5R, 'risking 110 to make 392', win); the account ends almost +15% after two trades. In between he skips several choppy days, declining entries when no structure validates his idea. The last part is Q&A: how he knows liquidity was swept (no displacement/closes beyond the low), his timeframe stack (daily, 4H, 1H, 15m), and how he gets large R by shrinking risk on a lower-timeframe entry while keeping the higher-timeframe target.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | Keep the higher-timeframe draw on liquidity as the target and use a lower-timeframe entry to shrink risk; R grows by cutting risk, not by stretching the target. | risk | stated | 1:11:10 | "it's a lot easier to increase your risk reward by decreasing your risk than increasing your target." |
| 2 | A sweep is a break of a low followed by an aggressive return into the range with no displacement or closes below; it points to the opposite liquidity. | cisd | stated | 1:08:10 | "see how we break this low, aggressively come back into the range, there's no displacement or closes below here, right? That's when you get your move higher" |
| 3 | If a higher-timeframe low is taken without displacement below it, expect price to go for the high. | daily-bias | stated | 1:08:10 | "if we're on a four-hour here, don't displace below it, likely to go see that high." |
| 4 | Box setup: consolidation, aggressive move one way, aggressive move back, retest/deviation of the consolidation edge, then expansion; it is a lower-timeframe wick (hammer/shooting star). Preferred on 1H, 4H and 15m. | other | stated | 35:00 | "So you have consolidation, aggressive down, aggressive up, retest the low of that consolidation before moving higher." |
| 5 | Don't enter blindly on a narrative: wait for structure at the POI to validate it; no structure means no trade and no loss. | psychology | stated | 54:10 | "that's why I don't just blindly take entries, right? Because If I have this idea, no structure came around here that validated my idea to go lower, right? So even though I was wrong, I didn't lose." |
| 6 | Discount/premium is not required if risk is managed; it only raises probability. | equilibrium | stated | 27:00 | "Really, if you can manage risk, you don't need to enter the discount premium. It's just higher probability, if that makes sense." |
| 7 | In a bullish trend, until structure shifts on a higher timeframe, down-close candles (order blocks) are buying opportunities; look for a lower-timeframe FVG inside the higher-timeframe block. | poi | stated | 47:20 | "So until we shift structure on a higher timeframe, all these downclose candles are technically buying opportunities." |
| 8 | On a trend day the candle should close into its high (open-high-low-close logic); don't fight it. | daily-bias | stated | 47:20 | "if we are going to have a trend day like this, normally you want it to do something like this and then continue up, right? Because you have your open high low close, right, on a candle." |
| 9 | Breaking the intermediate-term low at a POI is the structure shift; a breaker entry follows. | protected-swing | stated | 47:20 | "Once we break this intermediate term low right here, this is really where we shift our structure." |
| 10 | Trade only the New York AM session, normally done between 9:30 and 11:00; no afternoon session. | time-of-day | stated | 51:20 | "I'm normally done trading from 9.30 to 11" |
| 11 | A deviation below the midnight open after accumulation is the manipulation before the move higher. | time-of-day | stated | 39:00 | "I want to see a deviation below midnight. That's our manipulation before going higher." |
| 12 | When midnight open and 8:30 are far apart, expect little to happen. | time-of-day | stated | 27:00 | "normally when you have midnight and 8.30, very separated, you don't get a whole lot occurring." |
| 13 | After a rejection inside the range, price tends to return to the midnight open. | time-of-day | stated | 39:00 | "normally you get a rejection high a day, wants to return to midnight if it's in this range." |
| 14 | Don't chase a breakout you missed; let it play out. | psychology | stated | 43:20 | "considering kind of missed the breakout, this isn't something I really want to chase, so we'll let it play out." |
| 15 | Sit on the higher timeframes and only watch marked POIs, to avoid lower-timeframe confusion. | prep-routine | stated | 54:10 | "This is why I've been, you know, sitting on the higher timeframes, right? Because if we're on the lower timeframes there, we get a little confused." |
| 16 | Judge respect of an order block by closes on the higher timeframe, not wicks. | poi | demonstrated | 11:00 | "we reach into this order block, fairly respected, right, if we go to like a four-hour, see no closes below there." |
| 17 | Mark the consequent encroachment (midpoint) of a fair value gap that the bodies are respecting. | fvg | demonstrated | 51:20 | "Currently, the bodies are respecting it, but I am going to mark out the consequent encroachment of that, or just the middle" |
| 18 | Backtesting method: chat-picked symbol and month, $10,000 account, 1% risk per trade, New York time zone, step the replay on a higher timeframe (no repaint), drop down at POIs, place the position tool with stop and target, screenshot into a journal (skipped on stream), review analytics. | prep-routine | demonstrated | 19:00 | "so we risk 1%, and since we had a 10-hour trade, right, have that PML of 1,000 there, so our count is up too." |
| 19 | SMT is a big part of his strategy, used to judge whether clean lows will be run. | smt | stated | 11:00 | "so then we could do SMT, because that's like a big part of my strategy." |
| 20 | Smart money reversal (low-risk sell): at a POI, run the high, break structure, leave an FVG; enter for the second leg of distribution. | cisd | stated | 1:02:50 | "So that's your low risk cell, first leg of distribution off this order block, right? And this is your kind of your second leg down." |

## The day read (prep)
- **S&P500 1D: bullish** (11:00): Daily swept lows and moved higher off a small order block (down-close candle); he expects a reach up into the order block / fair value gap above. Says he is not completely certain. Draw: Daily fair value gap / order block area overhead (shaded zone roughly 3835-3905 on the 1H frame).
- **S&P500 1D: bullish** (23:00): Answering 'why higher on the daily': in a downtrend, after a low is taken and an aggressive move higher follows, price at least reprices to the order block, seeks liquidity above, or reaches OTE; price is only just into premium so he wants OTE or the highs. Draw: Daily order block / highs left above.
- **S&P500 1H: neutral** (27:00): 5 Jul replay: price sits at equilibrium of the larger range and midnight open and 8:30 are far apart; 'not super biased', will sideline unless 15m bullish structure appears; leans back into the range because of the daily bullish narrative. Draw: Unmitigated fair value gap / lows below, or back up into the range.
- **S&P500 4H: bearish** (58:50): Later in the replay (around 12 Jul) he reads a smart-money reversal off the daily order block: runs the high, breaks structure down, leaves a fair value gap. Draw: Equal lows below (hand-drawn curve under ~3745 on the 4H frame).
- Level S&P500: Daily order block / FVG overhead (shaded box ~3835-3905 on 1H frame): Daily draw on liquidity after lows were swept (11:00)
- Level S&P500: 1H fair value gap + breaker below price (around 3800-3810 on the 5m frame): Where he wanted price to reach down before going higher; it stopped there and he went long (15:00)
- Level S&P500: 3820 area: Draw after London took equal highs on the 5 Jul replay (19:00)
- Level S&P500: Midnight open and 8:30 open (marked each replay day): Session reference levels; wants a deviation below midnight as manipulation before higher (39:00)
- Level S&P500: ~3800: Downside narrative target on the 8 Jul replay (51:20)
- Level S&P500: Daily order block zone (green box ~3905-3945): Smart-money reversal area for the 4H short; stop 3912.80 inside/above it (58:50)
- SMT S&P500/NAS100: FX Replay has no multi-symbol view yet, so he cannot check SMT, which he calls 'a big part of my strategy'; says the clean lows likely had an SMT he can't see. (11:00)
- Context: Backtest of July 2022. He trades only the New York AM session (normally done 9:30-11:00), not the afternoon; marks midnight open and 8:30 each replay day. Notes a ~40-point hourly candle is 'most likely due to news'.
- Checklist order: Create FX Replay session (balance, symbol, date range, strategy tag), remove default indicators, set time zone to New York → Daily: mark sweeps, order blocks, fair value gaps, decide draw on liquidity → 4H then 1H: mark order blocks / FVGs / mitigation blocks / obvious lows that could be run first → Mark midnight open and 8:30 (vertical lines at 9:00/9:30) → Step the replay on a higher timeframe (no repaint) and watch only the marked points of interest → Drop to 15m/5m/1m at the POI for a structure break + FVG/order block entry; place the position with stop and target at the HTF draw, risk 1%
- If Price reaches down into the 1H FVG before the daily draw higher → Look for a long confirmation on 5m targeting the daily draw (15:00)
- If Stopped out, then price comes back and retakes the lows → Still long bias; trade again (19:00)
- If 1H reaches above highs but fails to displace → Expect a reach lower to take overnight lows before continuing higher (35:00)
- If Price takes overnight highs then deviates below midnight open → That is the manipulation before going higher (accumulation setup) (39:00)
- If Price drops but does not displace below the low (inducement) → Expect a reach for new highs (43:20)
- If 4H takes a low without displacing below it → Likely to go take the high (1:08:10)

## Live read
| Time | NY | Symbol | TF | Stage | What he sees | What he does / waits for |
|---|---|---|---|---|---|---|
| 04:00 |  |  |  | none | FX Replay dashboard, no sessions yet. | Introduces backtesting with FX Replay; will skip journaling for time. |
| 07:00 |  | S&P500 |  | none | Create-session dialog: balance 10000, pair S&P500, start 07/01/2022, end 08/01/2022, strategy 'YouTube'. | Lets chat pick symbol (S&P) and month (July 2022). |
| 11:00 |  | S&P500 | 1H | none | Daily swept lows and moved up; 1H shows price rallying toward the shaded daily OB/FVG zone; vertical line at 04 Jul '22 10:00. | Marks the daily draw higher, a 4H level, a 1H mitigation block; wants a reach into the order block, notes no 4H closes below it. |
| 15:00 |  | S&P500 | 5m | entry | Price dipped into the 1H FVG / breaker and stopped. | Places a 5m long: entry ~3809.91, stop 3807.55, target 3835.48, R:R 10.83. |
| 19:00 |  | S&P500 | 5m | managing | Target hit (10R); 1H highs taken; 4H draw would have given more. | Explains the entry (broke up, went to a POI, aggressive move out, risk off that low). Moves to the next day, marks midnight; London took equal highs. |
| 23:00 |  | S&P500 | 5m / 4H | none | 5 Jul: price falls hard from the overnight highs to ~3772 by 9:00. | Marks 8:30; still bullish on the daily but expects range-bound; not interested yet. |
| 27:00 |  | S&P500 | 1H / 1D | invalidated | Price at equilibrium of the larger range; the 1H closed below the order block. | Sidelines ('maybe we get a trend day down'); nothing on 5m/1m. |
| 31:00 |  | S&P500 | 5m / 1H | none | Price reached higher without touching his 15m long level (6 Jul 09:00). | Missed the move ('fine'); marks lows, midnight open and 8:30 for the next session. |
| 35:00 |  | S&P500 | 15m / 1D | none | Box setup on 5m/1m (consolidation, aggressive down, aggressive up, retest of the consolidation low); 1H reaching above highs but failing to displace. | Expects a reach lower to the overnight lows; calls the day choppy, notes the 15m was cleaner; no trade. |
| 39:00 |  | S&P500 | 15m / 1H | waiting for wick | Accumulation; overnight highs taken; hand-drawn circle under the range low. | Wants a deviation below midnight open as manipulation before higher; in the same breath says he wants a short off the open if his bias is right (his words are inconsistent here). |
| 39:20 |  | S&P500 | 1m | waiting for wick | 7 Jul pre-open 1m chart inside the shaded zone; Asia highs already taken. | Waits for displacement down around 9:25. |
| 43:20 |  | S&P500 | 1m / 1H | none | No move below midnight; price ripped higher toward the 4H order block. | Won't chase the missed breakout; calls the dip an inducement setup; describes a 1m displacement-up OB/FVG entry he did not take. |
| 47:20 |  | S&P500 | 15m / 1H | none | Trend day up into the 1H FVG; next day (8 Jul) price breaks an intermediate-term low at a POI before 9:30. | Down-close candles are buys until HTF structure shifts; calls the pre-9:30 breaker short valid but outside his hours. |
| 51:20 |  | S&P500 | 5m / 1m | waiting for wick | Asia range; London takes its high; box-setup deviation, retest, drop. Bodies respecting the FVG above. | Marks consequent encroachment; downside narrative to ~3800; 1m fails to respect a BPR, then he points out the breaker. |
| 54:10 |  | S&P500 | 15m / 1m | invalidated | Price instead reached up for buy side above (8 Jul ~12:54). | No structure validated the short, so no entry: 'even though I was wrong, I didn't lose'. |
| 55:10 |  | S&P500 |  | none | Session list: replay date 7/8/22 9:37 AM, strategy win rate 100%, +10.83%. | Shows the analytics page. |
| 56:50 |  | NAS100 |  | none | New-session dialog with NAS100, start 02/01/2017. | Tests how far back data goes: about 2017 (~6 years of 1m data), no seconds charts. |
| 58:50 |  | S&P500 | 4H | entry | Price rejecting the daily order block (green box); hand-drawn projected path down to the equal lows. | Places a short: entry ~3875.14, stop 3912.80, take profit 3741.56, qty 2.94; 'risking 110 to make 392'. |
| 1:02:50 |  | S&P500 | 15m | managing | Price fell into the ~3720s by 14 Jul, through the target. | Short hit ('I'm a swing trader now'); explains the low-risk sell / smart money reversal and the news-candle repricing. |
| 1:03:10 |  | S&P500 | 1D | none | Daily with the green daily order block above and price back near 3750. | Says most of his work comes from the 4H; refers to an NQ example on his Twitter. |
| 1:04:10 |  | S&P500 | 1D | none | Same daily view, zoomed out. | Mentions he used the weekly volume imbalance that day; takes the question on liquidity sweeps. |
| 1:08:10 |  | S&P500 | 1H | none | Chart-settings dialog over the 1H chart; a low with no displacement below, then a rally to the highs. | Answers how to tell a sweep: break of the low, aggressive return into the range, no displacement/closes below. |
| 1:09:10 |  | S&P500 | 15m | entry | Hindsight 15m long under the 1H POI: stop 24.18 pts, target 196.46 pts, R:R ~8.1. | Demonstrates stop placement under the box-setup deviation low (hindsight, not a replay trade). |
| 1:11:10 |  | S&P500 | 1H | none | Same rally on the 1H. | A 5m FVG entry with the stop at that low makes it 13R; prefers box setups on 1H, 4H, 15m. |

## Trades
- **S&P500 long** (15:00): Daily draw higher; 1H FVG/breaker POI; 5m entry (2023 ICT-style, pre-TTFM). Entry: Daily swept lows and was drawing to the daily order block/FVG above; price reached down into the 1H fair value gap and breaker, then on 5m broke up, came back to a POI and moved aggressively out of it. Stop: 3807.55, under the 5m low he entered off ('take the risk off that low'). Target: 3835.48, the daily draw on liquidity / 1H highs (he notes the 4H draw would have given more). R:R 10.83. Outcome: win.
- **S&P500 short** (58:50): 4H smart-money reversal off the daily order block (low-risk sell). Entry: Price ran the high into the daily order block, broke structure down and left a fair value gap; first leg of distribution off the order block, short for the second leg toward the lows. Stop: 3912.80, above the reversal high in the daily order block. Target: 3741.56, the equal lows (sell side) he drew under price on the 4H. R:R 3.55. Outcome: win.

## Q&A
- **Q (19:00):** Aren't the lows too clean (likely to be run first)? **A:** Yes and no; usually there is an SMT there he cannot check in FX Replay. He takes the trade with managed risk; if wrong he takes the stop, and if price retakes the lows he is still long-biased and trades again.
- **Q (23:00):** Why higher on the daily? **A:** After a low is taken in a downtrend and an aggressive move higher follows, price at least reprices to the order block, seeks liquidity above or reaches OTE; price is only just into premium so he wants OTE or the highs.
- **Q (23:00):** How do you keep a long bias over the 4H fair value gap? **A:** Longs are more probable when the higher timeframes are bullish; lower-timeframe shorts can happen but he stays with the higher-timeframe bullish view.
- **Q (27:00):** Do you only take longs in discount? **A:** Not always; he has shorted when price was not in premium. It depends which range he works with. With managed risk you don't need discount/premium; it only raises probability.
- **Q (31:00):** Do you feel comfortable trading the 1-minute? **A:** Yes; he shows a 1m box-setup entry (consolidation, aggressive down, aggressive up, retest of the consolidation low) but says that one carried more risk than he wants.
- **Q (31:00):** Do you normally trade London and New York? **A:** Only the New York AM session.
- **Q (39:00):** How do you manage switching timeframes during the market? **A:** Keeps higher timeframes up with points of interest marked, then watches only those points of interest; uses multiple screens.
- **Q (47:20):** Have you looked at IDR/DR (initial range)? **A:** No; he is normally done trading between 9:30 and 11:00, before the initial range has formed.
- **Q (51:20):** Which strategy gives the highest R? **A:** It comes down to risk management more than the strategy.
- **Q (1:02:50):** Explain the low-risk sell. **A:** A smart money reversal: at a point of interest price runs the high, breaks structure down and leaves a fair value gap; that is the low-risk sell, the first leg of distribution off the order block, with a second leg to follow. Once on the bearish side of the curve, look for sells. A ~40-pt hourly candle is likely news; price reprices to the order block and the sell occurs there; ideally an SMT forms too.
- **Q (1:02:50):** Do you use VWAP? **A:** No; he trades a naked chart.
- **Q (1:02:50):** Which timeframes do you use? **A:** Daily, 4H, 1H, 15m; most setups come from the 4H and 1H. He also used the weekly volume imbalance that day.
- **Q (1:04:10):** How do we know liquidity is being swept? **A:** Price breaks a low, aggressively comes back into the range, with no displacement or closes below; then expect a move higher toward the order block or highs. His box setup is really just a wick (hammer/shooting star) on a lower timeframe.
- **Q (1:08:10):** Favourite ICT model? **A:** Likes them all; will focus on market maker models over the next month.
- **Q (1:09:10):** Where would your stops be placed? **A:** He does not execute on the hourly: at the hourly POI he drops to 15m, waits for the box-setup deviation below the previous lows, enters long with the stop under that low; dropping to a 5m FVG entry shrinks risk further (13R with the same target).

## Mistakes and warnings
- Entering on a narrative before structure confirms it. Fix: Wait for a structure break at the POI; if none comes, skip and you lose nothing. (54:10)
- Shorting a strong bullish trend day. Fix: Until higher-timeframe structure shifts, treat down-close candles as buying opportunities; 'the only thing you'll regret here is selling'. (47:20)
- Reading the market only on lower timeframes and getting confused. Fix: Sit on the higher timeframes and only drop down at points of interest. (54:10)
- Taking a 1m entry with the stop far away at the lows. Fix: He passed on it as 'not really the risk I want to put on'; the 15m was cleaner. (35:00)

## Conflicts and open questions
- Visual only (15:00): Trade 1 position tool: target 3835.48 (+25.57, 0.67%), entry ~3809.91, stop 3807.55 (2.36 pts, 0.06%), qty 105, R:R 10.83; replay clock 04 Jul '22 12:15. 4 July 2022 was a US market holiday, which he does not mention; the FX Replay S&P500 feed still printed bars that day.
- Visual only (55:10): After trade 1, analytics shows strategy win rate 100% and +10.83%, replay date 7/8/22 9:37 AM.
- Visual only (58:50): Trade 2 on the 4H: stop 3912.80, entry ~3875.14, take profit 3741.56, qty 2.94 (consistent with 'risking 110 to make 392', R:R ~3.55). A hand-drawn curve under equal lows near 3745 marks the target liquidity; the green box above is the daily order block.
- Visual only (1:02:50): 15m chart on 14 Jul '22 shows price trading down to roughly the 3720s, below the 3741.56 take profit, so the short hit target.
- Visual only (39:00): Hand-drawn circle below the 15m range low marks the deviation zone he wanted before a move higher.
- Visual only (1:09:10): Hindsight 15m long at the low near ~3721: stop 24.18 pts (0.65%), target 196.46 pts (5.24%), R:R ~8.1, toward the ~3942 level under the daily order block.
- Open question 5 (11:00): Judges respect of the order block by no closes below on the 4H; later says the bodies are respecting the FVG. Leans: Respect judged by closes/bodies; wicks through allowed
- Open question 10 (1:08:10): A sweep vs a real break is told by displacement: no displacement/closes below a low = sweep and reversal. Leans: Displacement is the deciding factor
- Open question 17 (27:00): When the 1H closed below the order block he stopped trusting it, considered a trend day down and sidelined. Leans: A close through the POI suspends the bias (sideline)
- Open question 21 (43:20): Missed the 7 Jul breakout and would not chase it; yet says down-close candles in a trend are buying opportunities until HTF structure shifts. Leans: Won't chase a missed move, but would buy later pullbacks into blocks in a trend
- Open question 22 (1:02:50): States a daily, 4H, 1H, 15m stack with most setups from 4H and 1H; demonstrates 1H POI with 15m or 5m entry; the replay short was placed on the 4H itself. Leans: D/4H/1H/15m in 2023; 1H -> 15m/5m entries
- Open question 23 (19:00): SMT used to judge whether clean lows will be taken before the move; 'ideally you get an SMT' at the reversal. Leans: SMT as confirmation of a sweep/reversal at the POI
- Open question 24 (1:08:10): A low counts as broken only with displacement/closes beyond; a wick through then aggressive return is a sweep. Leans: By close/displacement, not wick
- Open question 26 (51:20): Uses breakers as entries (8 Jul pre-open breaker, 1m breaker after a failed BPR), mentions BPR, mitigation block, consequent encroachment; London takes the Asia high then deviation-retest-drop as a NY continuation profile. Leans: 2023: breakers/BPR as entry arrays; London-takes-Asia-high then NY continuation
- Open question 35 (35:00): Box setup from consolidation: aggressive move out one side, aggressive back, retest/deviation of the edge, then expansion; trades the deviation. Leans: Trades out of consolidation via a deviation and retest of its edge
- Open question 37 (51:20): Done by 11:00; does not trade the afternoon or pre-9:30 setups even when valid. Leans: After 11:00 NY is too late for him (2023)

## Glossary additions
- Whisper errors: 'PML' = P&L, 'risky $100' = risking $100, 'low risk cell' = low-risk sell, 'Lana' = London, 'repair value gap' = fair value gap, 'order black' = order block, 'SMR' probably smart money reversal, 'teach rules edu' = discount code (ttrades edu), 'IDRDR' = IDR/DR, 'aggregation' probably accumulation, 'Do whippy' and 'NNR daily' unintelligible. Speech under a frame often refers to charts shown after it. Replay date of trade 2 read from the frame (toolbar 'Tue', around 12 Jul 2022), approximate.
