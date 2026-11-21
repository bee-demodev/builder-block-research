---
title: "TTrades Indicator Updates - Walkthrough and Q&A (2026-07-26)"
type: ttrades-source
slug: livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy
source: youtube-livestream
youtube_id: sdZkE-naNiY
youtube_url: https://www.youtube.com/watch?v=sdZkE-naNiY
partition: livestream
recorded: 2026-07-26
format: live-session
speakers: [ttrades]
instruments: ["NQ1!", "ES1!", "YM1!", "GC1!", "CL1!", "EURUSD", "BTCUSD", "AMD"]
timeframes: ["15m (4H fractal)", "1D", "1H", "1H (daily fractal)", "30s (custom 10m fractal)", "5m with Auto Bias 2", "W/M"]
concepts: ["other", "timeframe-pairing", "protected-swing", "smt", "cisd", "candle-3", "candle-2", "time-of-day", "poi", "daily-bias", "risk", "equilibrium"]
transcript: "[[../../ttfm_video_corpus/transcripts/livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy.txt]]"
frames: "../../ttfm_video_corpus/livestream_frames/livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy/"
day_type: "Sunday, markets closed; indicator walkthrough in bar replay, no live trading"
analysis: ../../ttfm_video_corpus/livestream_analysis/livestream_20260726_ttrades_indicator_updates_walkthrough_and_q_a_sdzke_naniy.json
confidence: medium
---

# TTrades Indicator Updates - Walkthrough and Q&A (2026-07-26)

> [!info] Converted from the livestream analysis JSON (an Opus agent read the stream's frames and transcript).

## TL;DR
Sunday stream (markets closed) dedicated to the update of his TradingView indicator TTFM [Pro+]. He explains the two headline additions, protected swings (dot + line, printed on the candle after a closure through, never repainted, turned gray when they fail) and PSP (shown as 'C2+PSP'), then walks through every setting in the inputs panel: history, fractal (automatic / fixed / custom), bias filter (neutral, bullish, bearish, auto bias 1/2), HTF candle count/size/offset, HTF open, vertical lines, H/L lines, previous EQ, time labels, early C2 CISD, CISD/EQ/C1-sweep styles, labels, T-spot, protected swings, SMT (display, auto/custom pairs, inverse), PSP, standard-deviation projections, formation liquidity, session filters, info table and calculation bars. Demos run in bar replay on NQ 1H, GC 1H, ES 1H, NQ 30s (custom 10m-30s model), NQ 3m and NQ 15m. The rest is Q&A (alerts on a watchlist, templates, two-stage SMT, PSP vs SMT, T-spot boxes, timeframe pairings) plus a lot of chat about a 72-hour sale, giveaways and support tickets. Market read is minimal: gold had a poor/doji daily closure so no bias (wait for NY intraday profile, slight upside lean on SMT); for NQ next week he only says watch how Monday reacts relative to the previous week's low and the monthly model. No trades taken.

## Key rules
| # | Rule (one sentence, operational) | Concept | Conf. | Time | Quote |
|---|---|---|---|---|---|
| 1 | Indicator update: update the script from the three-dot menu, right-click or the purple dot; saved indicator templates do not update themselves and must be re-saved. | other | stated | 02:50 | "if you have templates up here like I do, right, that's not going to update itself, right? You need to go ahead and go back and make new templates" |
| 2 | Default behaviour: the indicator prints nothing until the candle closure; on the closure the PSP shows and the SMT is marked when it forms. | other | stated | 04:00 | "default settings, it's gonna not print anything until the candle closure." |
| 3 | Protected swings (new): a protected swing forms on a closure through; it is printed on the next candle's open, drawn as a dot plus a line, and new ones keep forming as price continues (trailing stop use). | protected-swing | stated | 04:20 | "Protected swings will form on the closure through. So on this candle here, that closes through, right? Once we get a closure through that, so on this next candle open, it will print that, right? And it's labeled with a dot." |
| 4 | Protected swings never repaint: when one is taken out it is turned gray (kept for review) and a new line forms. | protected-swing | stated | 25:00 | "The protected swings don't repaint, right? I don't repaint things because I find it dishonest, right?" |
| 5 | History setting = how many past models stay on the chart; 0 shows only the most recent. He keeps 0 when actively trading, 1 in his template; panel default shows 4. | other | stated | 05:55 | "History is just going to show you how many models show up on your chart at one time" |
| 6 | Fractal setting: Automatic picks the HTF from the chart timeframe (1H chart -> daily, 15m -> 4H, 5m -> 1H); a fixed pair (e.g. daily-hourly) stays the same on any chart timeframe; Custom lets you choose any pair. | timeframe-pairing | stated | 06:20 | "So default, it's automatic. So that means if I'm right here on the hourly, it's going to use the daily, right?" |
| 7 | Bias filter: Neutral shows bullish and bearish models; Bullish/Bearish show only that side; Auto Bias 1 only shows setups aligned with the model one fractal up (5m/H1 aligned with H4-15m), Auto Bias 2 two fractals up (daily-H1). | timeframe-pairing | stated | 07:30 | "If you have auto bias 1 on the 5-minute, it's only going to align when the 4-hour's in line. If you have auto bias 2, it's going to go up two timeframes instead of one." |
| 8 | HTF candles: count (default 4, he uses 4 because his model needs it; minimum 4), size small/medium/large or hide; offset shifts them right so two copies can sit side by side. | other | stated | 08:20 | "Default, I use four, because that's how I use it in my model." |
| 9 | To overlay two HTF sets: copy/paste the indicator, lock the copy to the daily with offset 17 and turn off its model (C2/C3/C4) so only candles show. | other | demonstrated | 09:20 | "I can offset it. I use 17, and I can lock it to the daily." |
| 10 | HTF drawing options: HTF open line, vertical lines separating HTF periods, H/L lines of previous candles (he keeps off), previous EQ shown on the previous HTF candle and/or the chart (drawings type: chart, HTF candles, both). | equilibrium | stated | 10:10 | "previous EQ, you know how I use EQ so it'll show it on the previous higher time frame candle as well as On the lower time frame" |
| 11 | HTF candle labels show weekday names on daily candles or the time/period open on lower ones; custom time zone available if not EST. | other | stated | 10:50 | "we have Monday, Tuesday, Wednesday, Thursday, if you go to a lower time frame, going to say, you know, what time frame those candles are" |
| 12 | Early C2 CISD (off by default): shows the CISD before the candle closes as a dotted line; on the closure the model confirms and turns solid. With it on, continuations also show dotted before the closure. | cisd | stated | 11:40 | "If you do want to see that marked out prior to, you can just turn on early CISD." |
| 13 | He leaves early C2 off by default because learners should not trade C2 (more complex), but he personally turns it on. | candle-2 | stated | 25:40 | "I have that off by default because people learning my model, I don't really want you trading C2. It's more complex." |
| 14 | Model style settings: bullish CISD line, bearish CISD line, candle EQ, candle 1 sweep with C1 sweep display (HTF candles only, chart, or both), TTFM label size, T-spot colours. | other | stated | 12:50 | "C1 sweep, we had a lot of people asking to see the C1 on a higher timeframe candle, but not the lower." |
| 15 | Protected swing settings: enable, style (solid/dashed/dotted), width, bullish/bearish colours; the same width setting controls continuation line thickness. | protected-swing | stated | 13:20 | "Now, protected swings, this is one of the new settings. This is where you can choose the width of the protected swings and what you want it to look like and the color of it" |
| 16 | SMT settings: display on chart, HTF candles or both; labels and size; correlated pairs Automatic (for NQ: ES and YM, shown in the table) or Custom with an optional second pair and an Inverse flag for inversely correlated pairs (e.g. dollar vs euro); SMT line style. | smt | stated | 15:00 | "SMT, I'll use ES and YM for NQ. If you don't want to use the pairs I selected, you can turn off automatic and turn it to custom." |
| 17 | PSP (new): enable and choose candle 1, candle 2 or both; on the chart only 'C2+PSP' is labelled; to see which candle is the PSP look at the HTF candles. | smt | stated | 15:30 | "it will only display C2 plus a PSP if you want to see what the PSP is. You have to look on the higher term from candles here" |
| 18 | PSP definition: the HTF candle closes bearish on one asset and bullish on its correlated asset; SMT is a divergence between the assets. | smt | stated | 34:40 | "SMT is a divergence between the assets." |
| 19 | Session filter: restrict printed setups to a session (e.g. New York only) so nothing prints while you are asleep. | time-of-day | stated | 16:00 | "Turn on a filter and filter it only for New York session. You won't see anything else in your chart but setups that occur in New York session." |
| 20 | Calculation bars sets how many bars back the script calculates; lower it if slow. He uses about 2,000. | other | stated | 16:20 | "Calculation bars is how many bars it calculates back." |
| 21 | A setup prints only if it qualifies as a fractal setup: candle closure plus a change in state of delivery (CISD). | cisd | stated | 22:20 | "If it doesn't have both of those, it's not going to." |
| 22 | Continuations are printed only for a limited time after the model; a continuation that forms too late into the move, or does not meet the demands, is not marked. | candle-3 | stated | 27:20 | "this one forms too late into the move because I mark them out specifically." |
| 23 | Continuation labels are shown only for continuations that form in a fair value gap. | fvg | stated | 43:40 | "we just label the ones that are in a fair value gap, right?" |
| 24 | T-spot box: the area where he wants the daily candle's wick to form (bearish gray box for a high, green box for a bullish wick low to be held) before price trades away. | poi | stated | 39:40 | "when this shows up and I have this gray box, I'm looking for the wick of the daily candle to essentially try to form somewhere in this area" |
| 25 | SMT naming: reversal SMT forms with the reversal (indicator shows it on the CISD); continuation SMT forms later in the move (prints live once the correlated asset takes the level); both = double SMT. | smt | stated | 34:20 | "That will be a reversal SMT because it's an SMT formed with the reversal." |
| 26 | Standard-deviation projections: off by default (he keeps them off); can be drawn from wicks or bodies. | other | stated | 46:40 | "I prefer to just have them off on my indicator." |
| 27 | Alerts: enable alerts and pick types in the inputs; create the alert while on the entry timeframe of the pair (hourly chart for daily closures, 15m for 4H) and add it to the whole watchlist. | other | stated | 26:20 | "instead of doing it one by one, you can create an alert on the watch list." |
| 28 | The indicator gives no signals, stops or targets and has no win rate; it marks his model mechanically, and a printed model is not automatically one to take. | other | stated | 42:40 | "There is, in fact, no win rate for the indicator." |
| 29 | The indicator is kept deliberately clean: no C1-C4 labels on chart/HTF candles and no HTF FVGs. | other | stated | 1:13:20 | "I don't want a billion things on my charts, right?" |
| 30 | C1 is not marked by the indicator; it is just the liquidity for candle 2's reversal. | candle-2 | stated | 52:50 | "it doesn't mark out C1. C1 is just the liquidity for the reversal of candle 2." |
| 31 | Learners should trade only C3/C4 after a valid model prints; trading C2 comes later. | candle-3 | stated | 53:10 | "Trade CD3, CD4, after valid model prints." |
| 32 | He prefers the confirmed continuation over an early CISD and takes early CISD only when bias is very strong. | cisd | stated | 1:08:50 | "I'll sometimes take an early CISD in the case that my bias is that strong." |
| 33 | A doji / poor daily closure gives little bias; wait for the NY session intraday profile, or wait another day. | daily-bias | stated | 1:16:00 | "So usually that means I don't really have much bias going into the day, because it could really do whatever it wants." |
| 34 | When price sits between protected swings on both sides, let the day form (watch Asia/London) before choosing a side. | protected-swing | stated | 28:10 | "you have a protected swing on this side you have a protected swing on the side we're in the middle so this is where you just kind of need to let the day form" |
| 35 | At a liquidity target / POI, judge reversal vs continuation from the reaction: running out the opposite high versus forming a continuation, retracement or consolidation. | poi | stated | 48:20 | "So what's our reaction at the low? Do we go run out this high? Or do we form a continuation or a retracement or consolidation?" |
| 36 | Timeframe pairings: 30s entries pair with 10m (not 3m); 15s with 5m; automatic pairs are 1H-D, 15m-4H, 5m-1H; custom pairs such as 7H-15m are possible. | timeframe-pairing | stated | 49:10 | "I would do just 5-minute, 15-second is what I would use. So if you're doing 30-second. I would probably use 10-minute." |
| 37 | Session-dependent pairing (typed on screen): before 9:30 focus on the H4/M15 model with M15 entries; after 9:30 use the H4 chart with LTF fractals H1-M5 or M30-M3. Daily/H1 for bias. | timeframe-pairing | stated | 1:26:20 | "Something like that is how I would do it if you want to master a 4-hour candle." |
| 38 | After an intraday reversal, either trade the 4H swing on the 15m (London) or wait for NY and trade an hourly swing on the 5m. | timeframe-pairing | stated | 1:05:50 | "Or we could wait for the New York session, look to trade an hourly swing somewhere in there on the 5-minute." |
| 39 | A 4H/15m trader focused on NY C3 continuations will have many no-trade days; that is normal for a mechanical system. | risk | stated | 53:40 | "it's not every day that you get a 15-minute entry, right?" |
| 40 | Even intraday entries need structure/context on a higher timeframe; it is not pattern trading. | timeframe-pairing | stated | 1:30:30 | "You need the context. You're not just pattern trading it." |
| 41 | Use the normal daily open (18:00, data-feed open), not true day open or midnight; use the Sunday weekly open for the weekly profile, where a reversal after an expansion generally trades back toward the weekly open. | daily-bias | stated | 1:30:10 | "If it reverses here, then generally your weekly profile is to trade back towards the weekly open." |
| 42 | He prefers continuation trades; reversals only when bias is very strong. | candle-3 | stated | 1:30:20 | "I don't really trade the reversals. I'll trade reversals in the case that it's very strong on my bias." |
| 43 | He prefers the New York session for most instruments, including gold. | time-of-day | stated | 1:30:00 | "I prefer New York for most things" |
| 44 | On stocks, turn protected swings off (messy); prefer higher timeframes there. | protected-swing | stated | 47:30 | "It's going to be a bit messy with the protected swings, honestly." |
| 45 | Once a bias is set, do not flip it just because the previous day high was taken. | psychology | stated | 43:50 | "just stop changing your bias once previous day highs taken." |
| 46 | On evaluations he would risk more, trading money for time; a 1:1 R approach needs a higher win rate. | risk | stated | 1:32:40 | "You just have to have a higher win rate." |

## The day read (prep)
- **GC1! 1D: neutral** (28:10): Not a good closure for gold: a bearish-ish/doji daily closure with a protected swing on each side and price in the middle, so the day could be framed either way. He would let Asia and London form, then see whether price respects one side of the wick and trades away, or sweeps the previous day high. Later repeats: doji candle means not much bias going into the day; wait for the NY session intraday profile, otherwise wait another day. Favors the upside slightly because of the SMT. Draw: not stated (previous day high mentioned as a possible sweep).
- **NQ1! W/M: neutral** (52:10): Asked for a trade plan after NQ touched a monthly level: 'you just have to see how Monday reacts'. Only reference is the previous week's low; on the monthly model (daily candles with monthly fractal) a protected swing just formed. Draw: previous week's low (only level named).
- Level NQ1!: previous week's low: the only level he names for the coming week (52:10)
- Level GC1!: previous day high; protected swings on both sides of current price: possible sweep target; price sits between two protected swings so no clean side (28:10)
- SMT GC1!: Gold: 'I favor to the upside with the SMT, but it could go either way' (correlated asset not named). (1:16:00)
- Context: Sunday 2026-07-26, 10:57-12:30 NY, markets closed; all chart work is bar replay or historical. Sale (35% off yearly, 25% off monthly/quarterly) announced for Mon-Wed.
- If gold opens and respects the side of the wick (holds the low) → trade higher (28:10)
- If gold opens and respects the other side (holds the high) → trade lower (28:10)
- If gold sweeps out the previous day high → alternative path; he waits to see Asia/London before deciding (28:10)
- If gold NY session forms no anticipatable intraday profile → wait another day (1:16:00)

## Live read
| Time | NY | Symbol | TF | Stage | What he sees | What he does / waits for |
|---|---|---|---|---|---|---|
| 05:50 |  | NQ1! | 1H (daily fractal) | none | Replay demo of a bearish daily-hourly model: on the closure the PSP prints ('C2+PSP' label), the SMT line is marked when it forms, then protected swings print one candle after a closure through, labelled with a dot and a line; stepping an hour at a time, new protected swings keep forming (trailing). | Demonstrating the new protected swing and PSP features, not trading. |
| 24:10 |  | NQ1! | 5m with Auto Bias 2 | none | Bearish daily-H1 model for the day; with Auto Bias 2 the indicator suppresses a bullish setup that formed and shows only the bearish one: sweep, closure back in, then three protected swings ('three different possible entries'), later new protected swings in chop; one fails and turns gray. | Explaining auto bias. Frame shows GC1! 1H (he moved on to gold afterwards). |
| 27:00 |  | GC1! | 1H | none | Gold example from whatever is on the chart: swing, closure, continuations print; one continuation does not meet the demands, another forms too late into the move so is not marked; reversal with CISD, candle 3 closure, continuation; a later mechanical continuation fails and is turned gray rather than removed. | Showing indicator behaviour without cherry-picking. |
| 32:30 |  | ES1! | 1H | none | SMT shown both on the HTF candle and on the chart, C2+PSP, CISD, then protected swing x3 and expansion. NQ was the weakest on this continuation day. Protected swings that fail turn gray and a new one forms. | Demonstrating SMT display 'both' and non-repainting protected swings. |
| 50:00 |  | NQ1! | 30s (custom 10m fractal) | none | Custom 10-minute / 30-second model with protected swings turned back on: 'Pretty clean, honestly.' | Showing the custom fractal; says he personally prefers the 15-minute. |
| 55:30 |  | GC1! | 1H | none | Bullish model prints with early CISD on and SMT; the small green box (T-spot) is where he wants the wick low of the day to form and be held so price can open, make a low and trade higher. 'Quite choppy. It works.' | Answering 'what is the green rectangle'. Frame t03590 actually shows NQ1! 3m with history raised. |
| 1:06:40 |  | NQ1! | 15m (4H fractal) | C3 | After an intraday reversal: London entry is 'the obvious entry', candle 3 prints; SMT prints only once YM takes out the high, which happens during replay. Stepping one minute: the T-spot prints with a fair value gap in it and the continuation prints by itself. | Options: trade a 4H swing on the 15m in London, or wait for NY and trade an hourly swing on the 5m; London entry could hold to the previous daily low. |

## Trades
- none taken

## Q&A
- **Q (22:20):** I bought the indicator; sometimes I see setups but the indicator does not print. **A:** It is automatic. If it does not print, the setup did not qualify as a fractal setup. His model is candle 2 / candle 3 closure (early C2 optional); a setup needs the closure and the change in state of delivery (CISD) to print.
- **Q (24:10):** How is the auto bias determined? **A:** Auto bias aligns a higher-timeframe model with the lower one. Auto Bias 1 goes up one fractal (on 5m with an H1 fractal it aligns with the H4-15m model); Auto Bias 2 goes up two (the daily-H1 model). If the daily-H1 model is bearish, Auto Bias 2 on the 5m shows only bearish setups for the whole day, hiding bullish ones.
- **Q (25:00):** How do you make templates and put a shortcut in TradingView? **A:** Set the inputs how you want (his: history 1, automatic fractal, 4 HTF candles, no offset, early CISD on, rest default), click OK, save indicator template (he names his 'all'), star it so it appears in the toolbar. Templates do not update with the script, so re-save them after an update. 'Clean' is his empty-chart template; his daily template is just daily candles with EQ.
- **Q (26:20):** Can you set up alerts? **A:** Enable alerts in the inputs and choose which (e.g. SMT). Add the alert on the timeframe whose closure you want: on the hourly for daily closures, on the 15m for 4H closures. He keeps a layout called 'alerts daily hourly' and creates the alert on the whole watchlist instead of one by one.
- **Q (29:20):** Can you make it fewer than four HTF candles? **A:** No. The model needs four candles because he trades swing points: candle 0/1, 2, 3, 4.
- **Q (29:40):** Could fair value gaps be shown on the HTF candles? **A:** Maybe in the future; he finds it cluttering and wants the indicator very clean (even the big update is 'one line and one dot').
- **Q (30:50):** Does it stop printing continuations if price has expanded too much? **A:** Yes. Continuations are only printed for a certain extent of time after the model, because the model focuses on a couple of candles; it will not print a continuation far away when there is no valid model.
- **Q (32:30):** Do PSP and SMT mark on your indicator? **A:** Yes. If there is SMT within the swing point it is marked; with display set to both it shows on the HTF candle and the chart, plus a 'C2+PSP' label when candle 2 is a PSP.
- **Q (34:20):** Does it handle two-stage SMT? **A:** An SMT formed with the reversal is a reversal SMT; another SMT forming later in the move is a continuation SMT; both together he calls double SMT. Later (t~3480) he says the indicator marks both: the reversal SMT shows on the CISD and the other forms live.
- **Q (34:40):** What is the difference between PSP and SMT? **A:** PSP: the higher-timeframe candle closes bearish on one asset and bullish on the correlated one (e.g. YM). SMT is a divergence between the assets (one takes a high/low the other does not).
- **Q (34:50):** Are you trading CRT with SMT? **A:** No, this is not CRT.
- **Q (39:40):** What are the gray boxes? **A:** The T-spot: the area where he wants the daily candle's wick to form before price trades away. Shown on examples where the wick formed there and price moved, and one day where it failed and chopped.
- **Q (39:30):** Any hidden sauce in your trading apart from the model/indicator? **A:** Not really; he shows everything.
- **Q (42:40):** What is the indicator's win rate? **A:** There is none: no buy/sell signals, no stop or take-profit; it only marks out his model.
- **Q (43:20):** How to align higher-timeframe SMT on the lower timeframe? **A:** Did not understand; the SMT shown is the higher-timeframe SMT displayed on the lower timeframe.
- **Q (42:40):** What logic do you use for protected swings? Sometimes it gives a false protected swing. **A:** Send a screenshot. A protected swing that later fails is not false: it was valid mechanically and then failed.
- **Q (43:40):** Why are only some continuations labelled? **A:** Only continuations that form in a fair value gap get the label; the others are not from an FVG. Sometimes labels do not work.
- **Q (43:50):** My bias is bullish but I change it once the previous day high is taken. **A:** Then stop changing your bias once the previous day high is taken.
- **Q (46:20):** When does daily bias fail? **A:** Points to his article/video 'trading the invalidation of daily bias' on ttrades.com (search 'invalidation'). He does not use rejection blocks.
- **Q (46:40):** Can you add projections? **A:** Already there: enable projections; default from the wicks, can switch to bodies; levels around 2-2.5 and 4. He keeps them off because they distort drawings/scaling.
- **Q (47:30):** Does the indicator work for options/stocks? **A:** Depends what underlying; on AMD daily it works but protected swings are messy, so for stocks he would turn protected swings off. Prefers higher timeframes on stocks.
- **Q (48:20):** A protected swing is protected until price hits liquidity; how do we know if it is likely to reverse there? **A:** Watch the price action at that point of interest/level: does it run the high, or form a continuation, retracement or consolidation? In the example, price retraced into a gap and continued lower.
- **Q (49:10):** Can we trade a 3-minute / 30-second model? **A:** For 30-second entries he would not use the 3-minute; he would use 10-minute/30-second, or 5-minute/15-second. Demonstrates a custom 10m-30s model; personally prefers the 15-minute.
- **Q (52:10):** What is your NQ plan for the coming week after it touched the monthly level? **A:** See how Monday reacts; previous week's low is the only reference; on the monthly model a protected swing just formed.
- **Q (52:50):** I am not seeing C1 and PSP on my charts. **A:** PSP only shows when there is one; C1 is not marked, it is just the liquidity for the candle-2 reversal.
- **Q (53:10):** What should we do after learning your model to get more advanced? **A:** First trade only C3/C4 after a valid model prints (the indicator makes this easy); once advanced, learn to trade C2.
- **Q (53:40):** With 4H/15m entries focused on NY and C3 continuations, there are many no-trade days? **A:** Correct; not every day gives a 15m entry, maybe one trade a day; that is how a mechanical system works.
- **Q (55:30):** What is the green rectangle? **A:** The (bullish) T-spot: where he wants the day's wick low to form and be held so price can open, make a low and trade higher.
- **Q (57:30):** If a protected swing has SMT and the swing formed without interaction, and a fair value gap is showing to the protected swing...? **A:** That would not be a protected swing (question garbled; answer short).
- **Q (1:00:50):** How do you run two sets of higher-timeframe candles? **A:** Lock one copy to a fractal (e.g. 15m), copy/paste the indicator, set the other to automatic or daily with offset 17, and remove the model (C2/C3/C4) from the second copy.
- **Q (1:01:20):** I saw it give wrong signals. **A:** It does not give signals, and what it prints is mechanically valid; a printed model is not necessarily one he wants to take.
- **Q (1:05:50):** How do you trade an NQ session? **A:** Watch his 'Intraday Reversals' video. After an intraday reversal: trade a 4H swing on the 15m chart (London), or wait for NY and trade an hourly swing on the 5m.
- **Q (1:08:20):** How does the indicator print the T-spot? **A:** It is coded in; stepping the replay one minute into the candle, the T-spot prints with a fair value gap in it, then the continuation prints on its own.
- **Q (1:08:50):** Would you prefer early CISD? **A:** No, he prefers the actual continuation; takes an early CISD only when his bias is very strong.
- **Q (1:09:10):** Does it work with the free version of TradingView? **A:** Yes.
- **Q (1:10:00):** Is there a reason to use YM/NQ instead of NQ/ES for SMT? **A:** He uses all three. To change: set correlated pairs from automatic to custom, turn off the second pair, pick the one you want (e.g. ES for NQ).
- **Q (1:13:20):** Can you label C2, C3, C4 on the chart and HTF candles? **A:** No; would make the chart sloppy and he will not add it.
- **Q (1:13:00):** Can we add custom timeframes like 7-hour? **A:** Already possible via custom fractal, e.g. 7-hour with 15-minute (may need a TradingView plan).
- **Q (1:13:40):** Does it work on forex / Bitcoin? **A:** Yes, on anything; shows EURUSD 15m-4H (messier on the hourly) and Bitcoin.
- **Q (1:14:10):** Are you more of a reversal or continuation trader? **A:** Continuation.
- **Q (1:16:00):** Elaborate on gold. **A:** Doji daily candle, so not much bias; wait for NY session to see the intraday profile; otherwise wait another day. Slight upside lean on SMT.
- **Q (1:16:30):** Can the thickness of continuation lines be adjusted? **A:** Yes: Protected Swings section, Width (e.g. 2), and style solid/dashed/dotted. He prefers solid.
- **Q (1:17:10):** Can someone explain C1 through C4? **A:** Learn the basics of candle 2 closure and candle 3 closure on his website.
- **Q (1:23:10):** How and when to trade C2? **A:** Three videos on his channel; search 'C2' or 'candle 2' on his website.
- **Q (1:26:20):** I want to master the 4-hour power of three; simplest way? **A:** That is the 10 a.m. candle. He typed on screen: before 9:30 focus on the H4/M15 model with M15 entries; after 9:30 use the H4 chart with lower-timeframe fractals H1-M5 or M30-M3.
- **Q (1:28:20):** Can you do an order flow tutorial? **A:** No, he does not use order flow.
- **Q (1:30:00):** Which session is best for trading gold? **A:** He prefers New York for most things.
- **Q (1:30:10):** Do you use the True Day Open? **A:** No, the normal daily open (CME/data feed), because he trades the actual daily candle. Also uses the weekly (Sunday) open for weekly profile: if the week reverses after an expansion, the weekly profile is generally to trade back toward the weekly open.
- **Q (1:30:20):** Gold on Friday? **A:** He would not trade gold on Friday there because he does not really trade reversals; only takes reversals when the bias is very strong, and this was not.
- **Q (1:30:30):** After 9:30, hourly or 30-minute, do we need structure on the hourly? **A:** Yes, you still need structure/context aligned with something; not pattern trading. Frame t05420 shows 'daily / h1 for bias' typed on screen.
- **Q (1:30:40):** In an SMT, the weaker asset's C2 is a bearish candle? **A:** That is a PSP.
- **Q (1:30:50):** Which assets for beginners? **A:** Assets do not matter much; pick ones you like and focus; timeframes matter more (see 'best model for beginners').
- **Q (1:31:20):** Midnight open or 18:00? **A:** Always 18:00.
- **Q (1:31:30):** Sometimes C2 closes and I rush in without waiting for the entry in the consolidation. **A:** Just be patient.
- **Q (1:32:40):** Risk when trading evaluations? / framing 1:1 R? **A:** For evaluations he would risk a lot more (trade-off between time and money). 1:1 R needs a higher win rate.

## Mistakes and warnings
- Expecting saved indicator templates to pick up the new version/settings. Fix: Re-make and re-save the templates after updating the script. (02:50)
- Calling a protected swing that later failed a 'false' protected swing. Fix: It was mechanically valid and then failed; the indicator grays it out instead of repainting. (42:40)
- Treating every printed model as a signal to take. Fix: The indicator only marks valid mechanical models; you still decide whether to take it. (1:01:20)
- Changing bias once the previous day high is taken. Fix: Stop changing the bias at that point. (43:50)
- Rushing in as soon as C2 closes without waiting for the entry in the consolidation. Fix: Be patient. (1:31:30)
- Beginners trading C2 / early CISD. Fix: Leave early C2 off and trade C3/C4 after a valid model prints. (25:40)
- Pairing a 30-second entry with a 3-minute model. Fix: Use 10m-30s or 5m-15s. (49:10)

## Conflicts and open questions
- Visual only (05:50): NQ1! 1H with TTFM [Pro+]: 'C2+PSP' label above the swing high on the chart and 'PSP' above the HTF candle on the right; orange SMT line from the high; red/blue dots for protected swings; 'C4' label. Watchlist includes NQ1!, ES1!, YM1!, RTY1!, MBT1!, BTCUSD, GC1!, XAUEUR, XAUGBP, SI1!, XAGGBP, XAGEUR, CL1!, RB1!, HO1!, DXY, 6E1!, 6B1!, 6J1!, 6C1!, 6S1!, 6N1!, 6A1!.
- Visual only (06:00): Inputs panel (top): Warnings and error messages 'Show?' (off); General settings: Alerts? (on), History 4, Fractal 'Automa...' with C2/C3/C4 checkboxes (all on), Custom Fractal '1 hour - 1 day', Bias 'Neutral'; HTF Candles: HTF Candles 4, Size Small, Hide? (off), Offset 0, Body/Border/Wick colours (green/black, gray/black, gray/gray); HTF Open Solid width 1 (on), Vertical Lines Solid width 1 (on), L/H Lines Dotted (off), Previous EQ Dotted width 1 (on), Drawings Type 'Both'.
- Visual only (10:00): Same panel with History 0 and Bias 'Bullish' while demonstrating; 'HTF Candles Time Labels' section: Enable Time Labels? (off), Time Format 24h.
- Visual only (14:00): Inputs panel (middle): Bullish CISD Solid width 2 (blue), Bearish CISD Solid width 2 (red), Candle Equilibrium Dotted width 1, Candle 1 Sweep Solid width 1, C1 Sweep Display 'Both', Show TTFM Labels? Small, T-Spot Bullish/Bearish; Protected Swings: Enable (on), Style Solid, Width 1, Bullish blue / Bearish red; Asset Correlation: Enable SMT? (on), Alerts? (on), SMT Display 'HTF Ca...', Labels? Small, Correlated Pairs 'Automa...', Enable Second Pair? (on), pairs grayed (CME_MINI:ES1!, CME_MINI:...), Inverse? per pair, SMT Line orange Solid width 1, Enable PSP? 'Both'; next section header 'Standard Deviation Projections'.
- Visual only (22:00): Inputs panel: 'Custom Timezone? UTC' field; Model Style section begins with 'Show Early C2 CISD' (checked, Dotted, with its own Alerts? box) above the CISD lines.
- Visual only (26:00): GC1! 1H in replay: 'C2' label at a swing low with an orange label beside it, blue protected-swing dot, gray box; four HTF candles on the right.
- Visual only (30:00): ES1! 1H: 'C2+PSP' at the high, orange 'NQ1!' SMT label on a line from the prior high (NQ named as the diverging asset), 'PSP' above the HTF candle, red hand-drawn arcs near the high, gray box with 'C4' label, red and blue dots for protected swings.
- Visual only (38:20): ES1! 1H: green box near the C2 area and gray box at C4 (T-spot boxes he explains as gray boxes); 'C2' label at the swing low on the left.
- Visual only (51:50): NQ1! 30-second chart in replay (Thu 16 Jul '26 around 09:51) with the custom 10m model: HTF candles on the right, 'C2' at the top of the swing, red protected-swing dots descending with price.
- Visual only (55:50): NQ1! 15m: 'C2' at the high with a red dot, gray T-spot box, red 'XC2' label and an orange SMT label near the low. Meaning of the 'XC2' label is not explained in speech.
- Visual only (59:50): NQ1! 3m with history raised: many labels visible at once, 'C2+PSP', 'XC2+PSP', 'XC2', 'C3', 'C4', 'C2' in black (bullish) and red (bearish/X-prefixed). Speech at this point is about a gold example, so the frame differs.
- Visual only (1:10:20): Inputs panel on NQ 15m after switching SMT to custom: SMT Display 'Both', Correlated Pairs 'Custom', Enable Second Pair? (off), pair 1 'CME_MINI:ES1!'; Standard Deviation Projections: Enable Projections? (off), Labels Small, Type 'Wick', levels '-1, -2, -2.5, ...'; Formation Liquidity: Enable Formation Liquidity? (on), Dotted width 1.
- Visual only (1:16:50): GC1! 1H inputs panel: same Model Style / Protected Swings / SMT layout; SMT Display 'Both', Correlated Pairs 'Automa...' with Enable Second Pair on; gray T-spot box with a red dot on the chart.
- Visual only (1:26:00): Typed on chart: 'before 9:30 focus on h4/m15 model / m15 entries' and 'after 9:30. h4 chart, can use ltf fractals / h1-m5 or m30/m3'. Speech only says 'Something like that is how I would do it'.
- Visual only (1:30:20): Typed on chart: 'daily / h1 for bias'.
- Visual only (1:33:40): GC1! 1H: gray T-spot box with red dot at top, blue horizontal line at the prior low, blue protected-swing dots on the earlier rally, 'C2' at the low.
- Open question 22 (49:10): Automatic fractal pairs: 1H chart -> daily, 15m -> 4H, 5m -> 1H. For 30s entries use 10m (not 3m); for 15s use 5m. Custom 7H-15m possible. Typed on screen: before 9:30 H4/M15 model with M15 entries; after 9:30 H4 chart with LTF fractals H1-M5 or M30-M3; daily/H1 for bias. Leans: D-1H, 4H-15m, 1H-5m standard; 10m-30s / 5m-15s for very low TF; 30m-3m after the open
- Open question 19 (1:26:20): Typed note during the 4H power-of-three answer: before 9:30 focus on the H4/M15 model and M15 entries; after 9:30 drop to LTF fractals (H1-M5 or M30-M3). Also: after an intraday reversal trade 4H swing on 15m in London, or hourly swing on 5m in NY. Leans: yes: higher confirmation TF before the NY open (M15), lower after (M5/M3)
- Open question 23 (34:20): SMT = divergence between correlated assets; PSP = HTF candle closes opposite colours on correlated assets. Reversal SMT forms with the reversal (shown on the CISD), continuation SMT forms later, both = double SMT. Default pairs for NQ are ES and YM; he uses all three. On an ES continuation day he notes NQ was the weakest. Leans: SMT/PSP are confluence marks within the swing point; reversal vs continuation SMT distinguished
- Open question 21 (30:50): The indicator only prints continuations for a limited time after the model; ones that form too late into the move are not marked. Beginners trade C3/C4 after a valid model. Leans: later continuations allowed (C3, C4) but not far beyond the model's few candles
- Open question 37 (27:20): On gold he points at a continuation the indicator did not mark because it formed too late into the move. Leans: a continuation that forms too late into the move is not taken/marked (no precise cutoff given)
- Open question 33 (30:50): Continuations are printed only within a window after the model; no continuation is printed far away when no valid model exists. Leans: setup is done once price moves well beyond the model's few candles
- Open question 24 (25:00): Protected swing forms on a closure through; when it 'gets taken out' it turns gray. Whether 'taken out' is by wick or close is not stated. Leans: formation needs a close through; break criterion not specified
- Open question 7 (1:16:00): Gold daily closed as a doji / ambiguous bearish closure with protected swings on both sides. Leans: no bias; wait for NY intraday profile or skip the day
- Open question 34 (28:10): Gold: protected swing on each side, price in the middle; he waits to see whether price respects one side of the wick or sweeps the previous day high, using Asia and London. Leans: let the day form and pick the side price respects
- Open question 26 (46:40): Projections exist in the indicator (standard deviation, from wick or body) but he keeps them off. Weekly profile: uses the Sunday weekly open; after an expansion that reverses, price generally trades back to the weekly open. Points to his Intraday Reversals video for daily profile entries. Leans: projections not used by him; weekly open used for weekly profile
- Open question 3 (39:40): T-spot box marks where the daily wick should form before price trades away; no timing given. Leans: location given (T-spot), timing not addressed

## Glossary additions
- Whisper: 'CD2/CD3/CD4' = C2/C3/C4; 'protected sphinx' = protected swings; 'YN' = YM; 'N2' = NQ; 'WAP'/'Wall' = Whop; 'chatGBT' = ChatGPT; 'Dtrades' = TTrades. The protected-swing/SMT/FVG question at ~3450 is garbled.
