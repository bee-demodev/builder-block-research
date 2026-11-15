# TCM Core: Revisiting Expansions

Source: `C:\Users\satvi\Videos\Trading\TCM Core\Revisting Expansions.mp4` (1 h 45 min, a
Sunday group call). Transcript: [revisiting_expansions_transcript.txt](revisiting_expansions_transcript.txt),
made locally with faster-whisper large-v3-turbo on 2026-11-15. Timestamps are mm:ss from
the start of the recording.

Whisper writes "FEG" throughout; read it as FVG (fair value gap). "CSD" is the change in
the state of delivery. "OLR" is the opposing liquidity run.

These rules drive the **TCM Expansions** tab of the companion web app
(`companion/web/src/tcm/expansion.ts`). The tab encodes rules 1 to 9; rules 10 to 12 are
shown as text only.

## The process

| # | Rule | What he says | Video |
|---|---|---|---|
| 1 | Expansion | Down candles closing below each other (up candles above, for the other side). One big candle is not an expansion. | 05:52, 40:55 |
| 2 | Range | When a candle stops closing beyond, that candle confirms the range: the expansion's high and low. EQ is its 50%. | 06:23 |
| 3 | Size | A range north of about 30 points is worth a scalp. A tight range demands a perfect entry and may need a sweep of its high to pay. | 07:25 |
| 4 | OLR | "OLR this range low, CSD higher." A run of the range low that closes back inside strengthens the turn. Optional in the tab. | 42:50, 26:33 |
| 5 | 50% | "Nine times out of ten I want it to be a green candle that closes above 50% of this guy" (the last expansion candle). Enough to participate, not an expansion. | 09:32 |
| 6 | CSD | "That candle open, which is the last candle in the expansion": a close above it. When CSD takes several candles he watches the open of the second candle. | 55:51, 59:44 |
| 7 | Wick | A big wick on the green candle: about 95% of the time the next candle trades below its close, so buy below the close; the bigger the candle, the deeper. No big wick: do not look for a deep retracement. | 10:41, 26:33 |
| 8 | Plan versus reality | A big green candle that does not retrace and spikes up says the deep retracement is not done. Do not chase. | 17:22 |
| 9 | EQ | "Conditions are we must close above there for me to hold." Without the close it is a scalp: cut, partial or break even at the line. | 12:14, 13:48 |
| 10 | Inside the range | Do not buy above EQ or sell below it. If you insist, only in an FVG after the high (low) is taken. | 93:36 |
| 11 | Targets | EQ, the range high, and failure swings with an FVG through them. A breakaway gap that stays open keeps the move going. | 22:02, 39:30, 49:53 |
| 12 | Time | Time raises the probability; it does not change delivery. At 9:55 the new hour is likely to take the previous hour first. | 43:26, 92:18 |

Other points from the call, not in the tab:

- Order block: the down candle left of the expansion that breaks structure. A close above a
  level that falls back below it makes that candle an order block candidate for
  continuation; it must prove itself before you buy again (19:35, 24:32, 44:01).
- Failure swing: a push toward a high or low that fails. Look for an FVG through it; if
  the FVG stays open price continues, if it closes "game over" (38:45 to 52:26).
- The same fractal works on M1, M5, H1, daily and monthly; pick the timeframe that gives
  ranges big enough for the trade size you like (35:15, 64:46).
- "Sometimes no trade is a good decision because there's not enough information there."
  (102:21)

## How the tab reads it

`readRange` in `companion/web/src/tcm/expansion.ts` walks the candles after the expansion
up to the replay cursor:

- **Void**: a close past the range's far side ends the range (20:41: "this range is now
  irrelevant because the low has been swept"). The tab says to pick the new expansion.
- **Entry**: the CSD candle's close. A wick of 30% or more of that candle is "big" (my
  threshold; the video gives no number). The entry fills when a later candle trades
  past the close.
- **Stop**: the extreme of the expansion and everything up to the CSD candle.
- **EQ hold**: a close past EQ, from the CSD candle on, by a candle that traded through
  EQ (its low below it, for a long). A gap past EQ is not a close above it (71:27: "that's
  not the same as market opening and closing above"). A close back past the CSD level
  first makes it "scalp only".
- **Shadow** (off by default): at the decision pending now (range, 50%, CSD, the fill, EQ)
  the tab can draw the next candle both ways, A on plan and B not, as a pale ghost in a
  "What if" column. The ghost's size is invented; its caption is the rules' own read with
  the ghost added, never hand-written. Off once the idea is held, void, too small, or the
  target has traded.

The practice charts in `companion/web/src/tcm/scenarios.ts` redraw six situations from the
video with invented prices.
