# Trading Basics Knowledge Base

This document is the current distilled trading foundation from TTrades materials. It is not a final truth source. It is the working knowledge base that topic rulebooks must refine and make more explicit.

## Core worldview

TTrades teaches market behavior as a sequence of recurring phases rather than a set of isolated patterns.

The current phase model is:
- consolidation
- expansion
- retracement
- reversal

The practical implication is that trades should be framed as phase transitions, not pattern-chasing.

## Core structure

### Bias
- Bias starts from the higher timeframe.
- Lower timeframe setups are only high-quality when they align with higher timeframe intent.
- Bias is not prediction. It is a contextual filter for what type of move is currently more plausible.
- A close outside the previous candle range implies continuation bias.
- A sweep of the previous candle high or low followed by a close back inside implies reversal bias.
- On daily continuation days, equilibrium of the previous day range acts as the key area of interest.
- On reversal days, the previous day high or low acts as the main anchor and lower-timeframe confirmation is required before execution.

### Protected swings
- A protected swing is a high or low expected to hold if the current directional thesis remains valid.
- Protected swings can be formed by:
  - liquidity sweep plus closure through the opposing candle series
  - fair value gap interaction plus closure through the candle series
- Protected swings matter because they:
  - define continuation structure
  - supply invalidation levels
  - reduce false reversal trading
  - support stop placement and trailing logic

### Expansion
- Expansion is a one-sided move with large directional candles and shallow countertrend pullbacks.
- Expansion commonly follows:
  - consolidation breakout
  - retracement completion
- Expansion signatures:
  - shallow pullbacks
  - protected swings forming along the move
  - opposing candles respected as support or resistance
- Expansion is fractal across timeframes.

### Timeframe alignment
- Higher timeframe sets direction.
- Intermediate timeframe confirms structure.
- Lower timeframe gives precise execution.
- TTrades repeatedly stresses that unaligned lower timeframe setups are lower quality.

## Execution logic

### Continuation framework
1. Find higher timeframe bias.
2. Wait for price to reach a point of interest.
3. Require a closure that confirms continuation.
4. Mark the new protected swing.
5. Enter with stop beyond the protected swing.
6. Target external liquidity or a higher timeframe objective.

### Reversal framework
1. Observe liquidity sweep or key-level interaction.
2. Require closure through the opposing candle series.
3. Confirm a protected swing in the new direction.
4. Use lower timeframe confirmation if needed.
5. Treat continuation setups after the first protected swing as cleaner than forcing the first reversal entry.

## Risk and invalidation

- Default invalidation is structural, not arbitrary.
- Protected swings are the preferred stop reference.
- If risk/reward is weak:
  - use candle body instead of wick only as a trade-off,
  - or wait for the next continuation protected swing.
- Trailing is done by stacking new protected swings in trend.

## Candle and wick logic

- Small opposing wick implies better support for expansion.
- Large opposing wick implies rejection and a reduced chance of clean trend continuation.
- Candle alignment across multiple timeframes is a core concept for trend quality.
- Large opposing wick often shifts the target model back toward the open or nearby liquidity instead of aggressive expansion targets.
- The next candle after a reversal candle is often a cleaner continuation entry than forcing the reversal candle itself.

## Practical rules already emerging

- After multiple same-direction expansion days, expect a possible phase shift.
- After a large expansion followed by consolidation, wait for external highs or lows to be taken before engaging.
- Lower timeframe structure should be ignored if higher timeframe candles do not support the same expansion direction.
- Below the four-hour chart, reversal framing becomes noisier and less reliable.
- Bias should be modeled as continuation-versus-reversal state first, then refined with wick logic, equilibrium respect, and lower-timeframe confirmation.

## Topic dependency map

Recommended dependency order for codification:
1. bias
2. protected swings
3. expansion
4. continuation entry
5. stop loss / invalidation
6. retracement
7. reversal

Expansion depends directly on bias and protected swings. Without those, most expansion logic remains descriptive instead of machine-checkable.
