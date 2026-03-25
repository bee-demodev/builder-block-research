# Pine Basics Knowledge Base

This document captures the Pine constraints that matter before indicator generation starts.

## Guiding rule

Do not attempt Pine generation from prose alone. First convert the trading idea into explicit rules with inputs, states, transitions, and invalidation.

## Official implementation constraints

### Script organization
TradingView recommends this ordering:
- version
- declaration
- imports
- constants
- inputs
- functions
- calculations
- visuals
- alerts

This matters because our generated specs should already map to those sections.

### Naming
- use `camelCase` for identifiers
- use `SNAKE_CASE` for constants
- use explicit suffixes when helpful, e.g. `biasInput`, `rangeBox`, `swingArray`

### Data structures
- arrays, maps, and matrices are first-class collection types
- user-defined types can group related fields into one object
- UDTs can hold collections and references to other UDTs

This is important for trading concepts because topics like protected swings or expansion ranges are naturally multi-field objects.

### Request limits
- a script can use up to 40 unique `request.*()` calls, or 64 on higher plans
- lower-timeframe requests are capped by intrabar limits
- all `request.*()` tuple outputs combined cannot exceed 127 tuple elements

Implication:
- avoid overusing multi-timeframe requests
- compress related state into UDTs where useful
- prefer a focused timeframe model instead of combinatorial requests

## Translation principles for this repo

### Good Pine candidates
- state machines
- explicit candle body and wick measurements
- range objects with stored anchors
- protected swing tracking
- equilibrium calculations
- finite session and bias filters

### Bad Pine candidates
- rules that depend on vague chart artistry
- "important level" without a measurable definition
- discretionary POI selection with no ranking logic
- visual intuition that cannot be reduced to OHLCV/time/session data

## Topic-to-Pine mapping

### Protected swing object
Likely fields:
- direction
- anchorBarIndex
- anchorPrice
- seriesOpenPrice
- confirmationBarIndex
- invalidated

### Expansion range object
Likely fields:
- direction
- startBarIndex
- rangeHigh
- rangeLow
- anchorTimeframe
- protectedSwingId
- active
- exhausted

## Anti-repaint baseline

Generated Pine specs should prefer:
- bar-close confirmation
- explicit use of confirmed data
- careful multi-timeframe requests
- no hidden repaint assumptions

If a rule needs intrabar discretion to work, it should not be labeled indicator-ready.
