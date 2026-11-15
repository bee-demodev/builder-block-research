# Design System: Trading Companion

The single source of truth for how the companion looks. Tokens live in
`src/styles/tokens.css`; this file says what they are for and what is never done.
`src/styles/contrast.test.ts` enforces the numbers below.

Taste dials (Stitch scale 1-10): **Density 8, Cockpit Dense. Variance 2, Predictable
Symmetric. Motion 2, Static Restrained.** These override the Stitch defaults (Variance 8,
Motion 6, Density 4) on purpose: this is a live decision instrument read at a glance
during a trade, not a marketing page. There is no hero section, no CTA funnel, and no
perpetual animation.

## 1. Visual Theme & Atmosphere

A quiet, dark instrument panel framing two bright paper charts, like a trading desk lamp
over printed charts. The window recedes; the charts and the one decision word carry the
eye. Everything that is not a price, a level or the decision sits in muted ink.

- The window (top bar, decision column, chart headers, footer) is dark charcoal.
- The chart plot area is the trader's own TradingView pane: warm cream paper, no grid,
  near-black prices. A trader moving their eyes between TradingView and the companion
  sees the same chart.
- Colour is reserved for meaning. Neutral ink is the default; a hue on screen always
  answers "long or short", "done or blocked", "waiting", "risk or reward".

## 2. Color Palette & Roles

### Window (dark theme; grey and TradingView schemes)

The window follows the system theme unless the theme toggle sets it; the light theme has
its own block in `tokens.css` (Fog #F1F2F4 floor, Paper #FBFBFC panel, Ink #15171A text).
Other direction schemes (Green / red, Green / black, Blue / orange, Monochrome) swap only
the nine direction tokens below; every one passes the same contrast test in both themes.

- **Charcoal Floor** (#1A1C1F) — window background
- **Charcoal Panel** (#212327) — panels, chart headers
- **Raised Charcoal** (#2A2D31) — hover, chips, inputs
- **Hairline Charcoal** (#34383D) — 1px structural borders
- **Paper Ink** (#ECEDEE) — primary text
- **Dust Grey** (#A2A7AF) — secondary text, captions
- **Long Jade** (#4CBB8D) — long side, reward
- **Short Coral** (#F07878) — short side, risk, failed
- **Confirm Blue** (#5B9DFF) — confirmed, passed, done
- **Watch Amber** (#E2A63B) — waiting, the next step, stale

### Chart plot area (TradingView scheme, same in light and dark themes)

- **Cream Paper** (#FAF8F0) — plot background, copied from the trader's TradingView pane
- **Cream Raised** (#EBE8DD) — crosshair labels, reference-level price tags
- **Desk Ink** (#131722) — axis prices and times, candle outlines and wicks
- **Graphite Ink** (#4A4E59) — reference-level names, secondary chart text
- **Pencil Grey** (#6F727C) — dashed reference-level lines (4.5:1 on Cream Paper)
- **Mist Up Body** (#CFDEE7) — up candle fill (outlined in Desk Ink)
- **Carbon Down Body** (#181817) — down candle fill (outlined in Desk Ink)
- **Deep Jade** (#0A6B47) — long, reward zone edge and caption
- **Brick Red** (#B02C2C) — short, risk zone edge and caption
- **Ink Blue** (#1F5BBD) — confirmed marks
- **Umber Amber** (#7F5300) — waiting marks, the next level

Rules:

- One status hue per meaning, never decoration. No accent colour beyond these roles.
- Saturation stays below 80% (a rule for new colours; not tested), with one exemption: the
  amber status colours (Watch Amber and its light and chart versions) are fully saturated
  so waiting reads at a glance. No neon, no glow, no gradient fills.
- Never pure black (#000000) or pure white (#FFFFFF) as a surface.
- Enforced by `src/styles/contrast.test.ts` for every scheme, both themes and the
  TradingView chart: text tokens 4.5:1 on bg, surface and raised; status words 4.5:1 on
  their 11% tints; price-tag text 4.5:1 on every tag colour; zone captions 4.5:1 on their
  zone fill; candle outlines 3:1 on the plot and over both risk / reward fills; axis text
  4.5:1 on the plot; the crosshair label text, which Lightweight Charts picks itself as
  black or white for its background, 4.5:1 on Cream Raised; reference-level lines 3:1 on
  the plot; reference-level tag text 4.5:1 on Cream Raised.
- Not covered by the test (checked by eye in screenshots): translucent hairlines and
  label halos.
- A stale chart is never faded. Fading cream into the charcoal window reads as muddy grey
  and drops every label below AA; the Stale word in the pane header and the hatched,
  dashed plan say it.

## 3. Typography Rules

- **UI:** Geist, 500 for labels, 600 for headings. 14px base, scaled by the Display menu
  text size (Normal 1, Large 1.25, Larger 1.5).
- **Numbers:** Geist Mono for every price, time and count (density override). Tabular
  figures so columns of prices align.
- **Chart axis:** Geist Mono 12px x text scale, in Desk Ink (the chart's text token),
  as TradingView's own axis.
- **Decision word:** the one large element on screen ("Trade short", "Watch, long"):
  Geist 600, track-tight, sized by weight and colour rather than sheer scale.
- **Chart labels:** Geist 500 at 12px x text scale on a 15px label box; zone captions 600.
  Nothing drawn on the chart canvas (labels, captions, axes) is smaller than 12px. The
  off-scale notes on the plot are 12px too; only the OHLC readout in the dark pane header
  is 11px x text scale.
- **Banned:** Inter, any serif, system UI fallback as a design choice, letter-spaced
  all-caps paragraphs.

## 4. Component Stylings

- **Chart pane:** charcoal header strip (timeframe, role, status, OHLC), cream plot below.
  No card shadow; a 1px Hairline Charcoal border separates panes.
- **Role levels** (entry, stop, target, next, confirm, waiting, point of interest,
  protected): 1px solid in the role colour, the next level 2px, drawn over the candles.
  Price tag filled in the role colour, text in the pane's bg ink.
- **Reference levels** (any role with no meaning colour: session highs and lows, opens,
  PDH / PDL, equilibrium): 1px dashed 4 / 4 in Pencil Grey, drawn behind the candles so
  structure never reads as price. Price tag in Cream Raised with Desk Ink text, so the
  filled tags are the ones that matter.
- **Price tags on the axis** are laid out by the companion, not the chart library
  (`layoutTags` in `src/chart/marks.ts`), on every frame: role and "look for" tags first,
  spread 22px x text scale apart (a tag is drawn 21px tall) around their shared centre
  where they would overlap; then a reference tag only where it clears every tag already
  placed by that distance (a reference level never wins a shared price). Tags are drawn at
  exactly those places, and an axis tick price under any of them is not drawn, as in
  TradingView. So a cluster of session levels never piles onto the axis.
- **Mark zones:** the role colour fill at 11% alpha, no edge stroke.
- **Risk / reward tool:** reward and risk fills at 12% (`ZONE_ALPHA`), with solid edges.
  Planned or stale: the fill drops to 7.2% and gets 28% diagonal hatching on a 7px step,
  and its entry line is dashed.
- **Candles:** forming candle drawn as outline only. Higher-timeframe candles sit right of
  the last candle in a separated column: full-ink outline and wick, body at 50% of the
  candle colour, at most 12px wide, so the context column never outshouts the pane's own
  candles. Their high / low hairlines across the bars they cover are the muted ink at 65%.
- **Labels:** each sits on a halo of the pane colour (92% for names, 85% for captions). A
  label first takes a spot clear of the candles (high-low box plus 2px), the trade lines
  and the next level; if none exists it keeps its usual spot on its halo. A label with no
  room at all is left out; its line and hover title still show, and its price tag follows
  the tag rules above.
- **Buttons:** flat, 6px radius, no glow. Ordinary buttons sit on Raised Charcoal; the
  primary (Check) is the one inverted button, light on dark.
- **Status words:** Stale is a plain word in Watch Amber in the pane header and the top
  bar. The plan state is a small outlined chip: Triggered solid, Planned dashed (as its
  tool is dashed on the chart). Waiting and error notes sit on their status colour's 11%
  tint.
- **Loading:** skeleton panes in the exact layout; no spinners.
- **Empty and error states:** a sentence saying what happened and the one thing to do,
  inline in the pane or the decision column.

## 5. Layout Principles

- Fixed cockpit grid: top bar, decision column (296px x text scale) on the left, charts
  filling the rest, footer status line. No page scroll on a desktop window.
- Two charts side by side (setup and entry timeframes), equal width.
- Price tags never overlap each other. Chart labels never overlap each other; they avoid
  candles where any spot allows; when room runs out a label takes a shorter wording, then
  gives way (see Labels above). Levels too far off the scale are listed as a note at the
  top of the pane.
- Desktop window only (WebView2, min 1280px wide). No mobile layout.

## 6. Motion & Interaction

- Motion 2: 140ms transitions on hover and focus, and a 140ms fade-and-rise of the
  verdict when a new one arrives. All of it is off with reduced motion.
- No perpetual loops, pulses or shimmer: anything that moves on a trading screen reads as
  a price move.
- Ticks update the last candle in place; nothing re-animates.
- Keyboard first: arrows step bars, space pauses, A / L / S set the side, D details,
  Ctrl+= / Ctrl+- / Ctrl+0 text size.

## 7. Anti-Patterns (Banned)

- No emojis.
- No Inter, no serif fonts.
- No pure black or pure white surfaces.
- No neon or glow shadows, no gradient text, no oversaturated accents.
- No decorative colour: a hue that does not mean long, short, done, blocked, waiting,
  risk or reward is removed.
- No grid lines on the plot (TradingView pane has none).
- No fading a light chart into the dark window (muddy grey); fade the drawing, keep the
  paper.
- No canvas chart text under 12px, no overlapping labels, no label on a candle when a clear
  spot exists.
- No faded stale chart; no dark filled price tag on a plain reference level.
- No spinners, no perpetual animation, no custom cursors.
- No AI copy clichés ("Elevate", "Seamless", "Unleash"); words say what happened and what
  to do next.
