# Companion web UI

The screen for the Trading Companion. The Python core pushes decisions over a local
WebSocket (wire contract v1, see `src/wire.ts`); this app renders them. It calls no
external service at runtime: it uses TradingView's own system font stack (Trebuchet MS on
Windows), nothing is downloaded, and there are no CDN links.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server on http://127.0.0.1:5173. Connects to `ws://127.0.0.1:8765/ws` (or `VITE_COMPANION_WS`). |
| `npm run build` | Type check, then build to `dist/` with relative asset paths, ready for the core to serve from `/`. |
| `npm run check` | TypeScript type check plus the Vitest suite. |
| `npm test` | Vitest only. |

When served by the core, the page connects to `ws://<page host>/ws`. Add `?ws=<url>` to
point it anywhere else.

## Demo mode (sample data only)

Add `?demo` to the URL, or set `VITE_COMPANION_DEMO=1`. A stand-in server in
`src/demo/` plays hand-written fixtures through the same validation and reducer as the
live socket. Every number in the hand-written fixtures is invented (`?demo=real` is the exception, below).

- `?demo` (tour): Check cycles watch (a planned long with its steps and tool), long
  (triggered), error with stale verdict, chart problem. Choosing Short shows a blocked first
  step and the Auto note.
- `?demo=watch`, `long`, `error`, `chart-problem`, `no-verdict`, `history`: start on that state.
- `?demo=connecting`: stays in the skeleton.
- `?demo=drop`: the server drops the socket after 6 s to show the reconnect banner.
- `?demo=real`: one REAL snapshot saved from the core on saved history
  (`src/demo/real-snapshot.json`, a copy of `tests/companion/fixtures/snapshot_v1.json`).
  It has the long sentences, nine checklist groups and ~160 candles per chart the core
  really sends; use it to check layout. Check shows it again; nothing moves.
- `?demo=real-triggered` (2025-11-18 08:30, side Short, plan triggered, every step done) and
  `?demo=real-planned` (2025-11-19 10:15, side Short, plan only planned; steps blocked, next,
  later): copies of `tests/companion/fixtures/snapshot_v1_triggered.json` and
  `snapshot_v1_planned.json`, loaded only when opened.

Keys: left and right arrows step one bar, Space plays or pauses a bar replay, Esc leaves its
Select bar, A / L / S set the side (Auto, Long, Short), D opens Details, Ctrl+= / Ctrl+- /
Ctrl+0 change the text size.

In demo mode a step or a replay cuts the sample candles to that moment (`cutView` in
`src/demo/server.ts`); the verdict and plan stay the sample's own, so only the core shows a
replay's verdict changing bar by bar. The sample reaches six hours back from its latest bar.

## Bar replay

Replay in the top bar works like TradingView's bar replay. Select bar, then click a candle on
either chart: the replay starts after it (the client sends `set when` with that candle's close,
then `check`). Play sends `step +1` once per bar at the chosen speed (0.1x to 10x, 1x being one
bar a second), and never before the last step's snapshot is in, so every bar is a real check of
that moment and no later bar reaches the screen early. The fastest a replay goes is one check per
bar. An error reply pauses it (the end of the data, the start of what TradingView has loaded), and
so does reaching the live bar. Back to latest (or Latest, or Replay again) ends it; a new symbol,
stack, style or data source ends it too. Live, the start must lie inside the bars TradingView has
loaded. The speed is kept per device (`companion.replay.speed`).

## Sections: TTrades and TCM Expansions

Tabs beside the wordmark switch between the TTrades companion and **TCM Expansions**
(kept per device in `localStorage`, `companion.section`). Under 1600 px wide the tabs
replace the wordmark so the top bar keeps room for the live status.

TCM Expansions draws the expansion -> range -> CSD process from the TCM Core call
"Revisiting Expansions" (rules, timestamps and transcript in `knowledge/tcm/`). Click a
candle of an expansion (two or more candles closing beyond each other) and the tab draws
the range high and low, EQ, 50% of the last candle and the CSD level, then walks the
decision points candle by candle: range confirmed, size, OLR, 50%, CSD, the entry from
the CSD candle's wick, the close past EQ that allows a hold, and the targets. A close
through the range's far side voids it.

- **Live** (default): the companion core's own entry, setup or bias chart, TradingView live
  or saved history (Settings, Data). Symbol and Stack drive the same core as the TTrades
  tab. With no candle picked the tab follows the newest range still in play, re-read on
  every closed candle; a click pins one ("Follow the newest instead" unpins). Forming
  candles are ignored. Not connected: the chart says so; no read yet: "Read the chart".
- **Practice**: lessons redrawn from the video with invented prices, each tied to a video
  timestamp.
- **Shadow** (S, or the switch in the chart header): at the decision pending now, the next
  candle both ways, A on plan and B not, as a pale ghost in a "What if" column, with the
  rules' read of it under the header. Off when nothing is pending.
- Arrows step the replay, Home restarts a lesson, End shows every candle (live: follows).
- "Find latest expansion" picks the newest range still in play; Start / End nudge the
  range by hand ("Use the rule" undoes that).
- Settings (kept in `localStorage`, `companion.tcm.*`): min range in points (the size
  rule), and in live mode the data source.
- Code: `src/tcm/expansion.ts` (the rules, pure, tested in `expansion.test.ts`),
  `src/tcm/RangeChart.ts` (drawing), `src/tcm/TcmExpansions.tsx` (the screen),
  `src/styles/tcm.css`.

## Display options (per device)

The Display button in the footer, a right-click on a chart, or the gear in a chart's header
(shown on hover or focus) opens them. They are kept in `localStorage` (`companion.display`)
and never sent to the core: text size (Normal, Large, Larger), direction colours (Grey
candles, Green / red, Blue / orange, Monochrome; `html[data-scheme]`, tokens in
`src/styles/tokens.css`) and the chart overlays (level names, zones, marker labels, risk /
reward box, key levels, look for). Entry, stop and target lines always show.
`src/styles/contrast.test.ts` holds every scheme to WCAG AA in both themes.

## Layout of the code

- `src/wire.ts`: contract types and boundary validation (a malformed frame is logged and dropped).
- `src/store.ts`: the reducer (seq ordering, stale handling, ticks).
- `src/connection.ts`: socket lifecycle and reconnect backoff.
- `src/chart/`: Lightweight Charts wrapper. `MarksPrimitive.ts` draws zones, levels, markers and
  the plan's risk / reward tool as one series primitive; `tool.ts` holds the tool's pure decisions.
- `src/decision.ts`: what the decision panel shows (suggestion, focused step, plan words, side).
- `src/display.ts`: the display options and their storage.
- `src/tones.ts`: every meaning-to-colour decision.
- `src/styles/tokens.css`: the whole token set, both themes.

## Third-party notice

Charts use TradingView Lightweight Charts (Apache License 2.0). The attribution notice
from its NOTICE file is in `public/NOTICE` (copied to `dist/NOTICE`) and in a comment in
`src/main.tsx`. The footer links to https://www.tradingview.com/ as the licence asks. The
on-chart logo is turned off because the footer link meets that requirement.
