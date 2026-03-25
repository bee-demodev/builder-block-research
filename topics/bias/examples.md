# Bias Examples

## Source-backed examples

### Example A
- Source: `Easy Daily Bias`
- Context: reversal day framed from the previous day high or low
- Features:
  - prior-day extreme acts as the anchor
  - wick forms at the level
  - lower timeframe confirmation is required
  - first objective is equilibrium, then the opposite side of the range

### Example B
- Source: `Easy Daily Bias`
- Context: continuation day after a directional prior-day close
- Features:
  - previous day midpoint defines equilibrium
  - price retraces into the area of interest first
  - lower timeframe closures stay on the correct side of equilibrium
  - continuation seeks the previous day directional objective and beyond

### Example C
- Source: `Next Day Model`
- Context: next-candle bias from previous candle range interaction
- Features:
  - close outside prior range implies continuation bias
  - sweep and close back inside implies reversal bias
  - repeated continuation candles warn of an incoming phase shift

### Example D
- Source: `Understanding Wick Sizes, Reversals, and Expansion Candles in Price Action`
- Context: wick-size filter for choosing expansion versus reversion expectations
- Features:
  - small opposing wick supports expansion
  - large opposing wick points back toward the open or nearby liquidity
  - candle-three continuation after the reversal candle is often cleaner than forcing the reversal candle itself

## Current machine-learning style takeaway
- Bias should be modeled as a state machine with:
  - reference range anchors,
  - continuation versus reversal mode,
  - wick-based expectation filters,
  - lower-timeframe confirmation gates,
  - and phase-shift guards after repeated same-direction continuation.
