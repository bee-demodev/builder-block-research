# Companion web UI

The screen for the Trading Companion. The Python core pushes decisions over a local
WebSocket (wire contract v1, see `src/wire.ts`); this app renders them. It calls no
external service at runtime: fonts are bundled, and there are no CDN links.

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

Keys: left and right arrows step one bar, space pauses, A / L / S set the side (Auto, Long,
Short), D opens Details, Ctrl+= / Ctrl+- / Ctrl+0 change the text size.

## Display options (per device)

The Display button in the footer, a right-click on a chart, or the gear in a chart's header
(shown on hover or focus) opens them. They are kept in `localStorage` (`companion.display`)
and never sent to the core: text size (Normal, Large, Larger), direction colours (Grey
candles, Green / red, Blue / orange, Monochrome; `html[data-scheme]`, tokens in
`src/styles/tokens.css`) and the chart overlays (level names, zones, marker labels, risk /
reward box). Entry, stop and target lines always show. `src/styles/contrast.test.ts` holds
every scheme to WCAG AA in both themes.

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
