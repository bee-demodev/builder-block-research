# Candle 3 Closure Examples

## Core Reversal Hand-Off

- Wait for price to reach the mapped point of interest.
- Confirm Candle 2 did not already qualify as the reversal closure.
- Accept Candle 3 only when it closes through the Candle 2 body in the new direction.
- Frame Candle 4 as the expected expansion candle after the delayed confirmation.

## Equilibrium Refinement

- Mark Candle 3 wick high and wick low, then compute the midpoint.
- In bullish conditions, prefer Candle 4 to retest and respect the upper half of Candle 3.
- In bearish conditions, prefer Candle 4 to retest and respect the lower half of Candle 3.
- Drop to the lower timeframe only after the midpoint logic and directional hand-off remain intact.

## Invalid Swing Filter

- Ignore any swing candidate that has a point of interest but no qualifying Candle 2 or Candle 3 closure.
- Ignore any Candle 3 body-engulfing close that forms away from the mapped point of interest.
- Keep the sequence pending until lower-timeframe displacement appears after the closure.
