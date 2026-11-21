---
id: tv-2026-baseline
title: "TTFM backtest tv-2026-baseline: the companion's default rules, 9 symbols x 5 stacks, 2026"
type: backtest-run
model: TTFM
concepts: [reversal, continuation, cisd, candle-2, protected-swing]
run_date: 2026-11-20
from: 2026-01-01
to: 2026-11-13
symbols: ["6E", "CL", "ES", "GC", "NQ", "RTY", "SI", "YM"]
switches: {"variant": "baseline", "stacks": ["1D-1h-5m", "1D-4h-15m", "1M-1D-1h", "1W-1D-1h", "1W-4h-15m"]}
tests: []
plans: 1137
total_r: 9.25
data: results/backtest_tv/2026/baseline
---

# TTFM backtest tv-2026-baseline

the companion's default rules, 9 symbols x 5 stacks, 2026

1137 taken trades, +9.25 R at the 2R plan over 2026-01-01 to 2026-11-13. The companion's own rules on TradingView bars; cost model included, no slippage. Evidence, not a validated rule.

## Per setup

| Symbol | Stack + path | Session | Trades | 1R wins | 2R wins | Stopped | Avg R | Total R |
|---|---|---|---|---|---|---|---|---|
| 6E | 1D-1h-5m continuation | asia | 14 | 9 | 4 | 10 | -0.324 | -4.54 |
| 6E | 1D-1h-5m continuation | london | 5 | 3 | 2 | 3 | +0.046 | +0.23 |
| 6E | 1D-1h-5m continuation | ny_am | 1 | 0 | 0 | 1 | -1.115 | -1.11 |
| 6E | 1D-1h-5m continuation | pre_ny | 6 | 3 | 1 | 5 | -0.604 | -3.62 |
| 6E | 1D-1h-5m reversal | asia | 11 | 6 | 4 | 7 | +0.052 | +0.57 |
| 6E | 1D-1h-5m reversal | london | 2 | 0 | 0 | 2 | -1.041 | -2.08 |
| 6E | 1D-1h-5m reversal | ny_am | 16 | 7 | 4 | 12 | -0.284 | -4.54 |
| 6E | 1D-1h-5m reversal | ny_lunch | 5 | 3 | 3 | 2 | +0.778 | +3.89 |
| 6E | 1D-1h-5m reversal | pre_ny | 6 | 2 | 2 | 4 | -0.034 | -0.20 |
| 6E | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.123 | -1.12 |
| 6E | 1D-4h-15m continuation | london | 3 | 2 | 1 | 2 | -0.070 | -0.21 |
| 6E | 1D-4h-15m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.123 | -1.12 |
| 6E | 1D-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.018 | -1.02 |
| 6E | 1D-4h-15m reversal | ny_am | 19 | 12 | 8 | 11 | +0.214 | +4.07 |
| 6E | 1D-4h-15m reversal | ny_lunch | 10 | 6 | 6 | 4 | +0.788 | +7.88 |
| 6E | 1D-4h-15m reversal | pre_ny | 2 | 2 | 2 | 0 | +1.993 | +3.99 |
| 6E | 1W-1D-1h reversal | asia | 4 | 2 | 1 | 1 | +0.812 | +3.25 |
| 6E | 1W-4h-15m reversal | asia | 1 | 0 | 0 | 1 | -1.016 | -1.02 |
| 6E | 1W-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.018 | -1.02 |
| 6E | 1W-4h-15m reversal | ny_am | 1 | 1 | 1 | 0 | +1.992 | +1.99 |
| CL | 1D-1h-5m continuation | asia | 19 | 5 | 4 | 15 | -0.433 | -8.23 |
| CL | 1D-1h-5m continuation | london | 8 | 2 | 1 | 7 | -0.661 | -5.28 |
| CL | 1D-1h-5m continuation | ny_am | 1 | 1 | 1 | 0 | +1.984 | +1.98 |
| CL | 1D-1h-5m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.999 | +2.00 |
| CL | 1D-1h-5m continuation | pre_ny | 6 | 2 | 1 | 5 | -0.573 | -3.44 |
| CL | 1D-1h-5m reversal | asia | 4 | 1 | 1 | 3 | -0.255 | -1.02 |
| CL | 1D-1h-5m reversal | london | 9 | 3 | 1 | 8 | -0.681 | -6.13 |
| CL | 1D-1h-5m reversal | ny_am | 17 | 7 | 6 | 11 | +0.046 | +0.78 |
| CL | 1D-1h-5m reversal | ny_lunch | 4 | 0 | 0 | 3 | -0.828 | -3.31 |
| CL | 1D-1h-5m reversal | ny_pm | 1 | 0 | 0 | 1 | -1.006 | -1.01 |
| CL | 1D-1h-5m reversal | pre_ny | 9 | 3 | 2 | 7 | -0.342 | -3.08 |
| CL | 1D-4h-15m continuation | asia | 3 | 1 | 0 | 3 | -1.031 | -3.09 |
| CL | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.992 | +1.99 |
| CL | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.995 | +1.99 |
| CL | 1D-4h-15m continuation | pre_ny | 3 | 1 | 0 | 3 | -1.014 | -3.04 |
| CL | 1D-4h-15m reversal | london | 3 | 3 | 2 | 1 | +0.995 | +2.99 |
| CL | 1D-4h-15m reversal | ny_am | 7 | 3 | 2 | 5 | -0.151 | -1.06 |
| CL | 1D-4h-15m reversal | ny_lunch | 3 | 2 | 0 | 1 | +0.184 | +0.55 |
| CL | 1D-4h-15m reversal | ny_pm | 1 | 0 | 0 | 1 | -1.008 | -1.01 |
| CL | 1D-4h-15m reversal | pre_ny | 2 | 1 | 1 | 1 | +0.498 | +1.00 |
| CL | 1M-1D-1h reversal | asia | 2 | 2 | 0 | 0 | +1.054 | +2.11 |
| CL | 1W-1D-1h continuation | london | 1 | 0 | 0 | 1 | -1.015 | -1.01 |
| CL | 1W-4h-15m continuation | asia | 8 | 4 | 4 | 4 | +0.454 | +3.63 |
| CL | 1W-4h-15m continuation | ny_pm | 2 | 1 | 1 | 1 | +0.494 | +0.99 |
| CL | 1W-4h-15m continuation | pre_ny | 4 | 3 | 2 | 2 | +0.492 | +1.97 |
| CL | 1W-4h-15m reversal | asia | 1 | 1 | 1 | 0 | +1.995 | +1.99 |
| CL | 1W-4h-15m reversal | ny_am | 2 | 0 | 0 | 2 | -1.009 | -2.02 |
| CL | 1W-4h-15m reversal | ny_pm | 1 | 0 | 0 | 1 | -1.006 | -1.01 |
| CL | 1W-4h-15m reversal | pre_ny | 1 | 0 | 0 | 1 | -1.015 | -1.01 |
| ES | 1D-1h-5m continuation | asia | 16 | 9 | 5 | 11 | -0.118 | -1.89 |
| ES | 1D-1h-5m continuation | london | 5 | 2 | 1 | 4 | -0.447 | -2.23 |
| ES | 1D-1h-5m continuation | ny_am | 1 | 0 | 0 | 1 | -1.050 | -1.05 |
| ES | 1D-1h-5m continuation | ny_lunch | 1 | 1 | 0 | 1 | -1.035 | -1.03 |
| ES | 1D-1h-5m continuation | pre_ny | 6 | 2 | 1 | 5 | -0.543 | -3.26 |
| ES | 1D-1h-5m reversal | asia | 12 | 9 | 5 | 7 | +0.237 | +2.85 |
| ES | 1D-1h-5m reversal | london | 2 | 2 | 2 | 0 | +1.994 | +3.99 |
| ES | 1D-1h-5m reversal | ny_am | 18 | 9 | 6 | 12 | -0.017 | -0.30 |
| ES | 1D-1h-5m reversal | ny_lunch | 7 | 2 | 2 | 4 | -0.063 | -0.44 |
| ES | 1D-1h-5m reversal | ny_pm | 1 | 0 | 0 | 1 | -1.011 | -1.01 |
| ES | 1D-1h-5m reversal | pre_ny | 4 | 2 | 2 | 2 | +0.492 | +1.97 |
| ES | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.013 | -1.01 |
| ES | 1D-4h-15m continuation | london | 1 | 1 | 1 | 0 | +1.983 | +1.98 |
| ES | 1D-4h-15m continuation | pre_ny | 4 | 3 | 1 | 3 | -0.287 | -1.15 |
| ES | 1D-4h-15m reversal | london | 3 | 1 | 1 | 2 | -0.005 | -0.02 |
| ES | 1D-4h-15m reversal | ny_am | 27 | 16 | 9 | 17 | +0.062 | +1.68 |
| ES | 1D-4h-15m reversal | ny_lunch | 6 | 3 | 2 | 4 | -0.003 | -0.02 |
| ES | 1D-4h-15m reversal | ny_pm | 5 | 3 | 1 | 3 | -0.178 | -0.89 |
| ES | 1D-4h-15m reversal | pre_ny | 6 | 3 | 3 | 3 | +0.495 | +2.97 |
| ES | 1M-1D-1h reversal | asia | 1 | 1 | 0 | 0 | +0.663 | +0.66 |
| ES | 1W-1D-1h reversal | asia | 3 | 2 | 0 | 1 | -0.007 | -0.02 |
| ES | 1W-4h-15m continuation | asia | 2 | 0 | 0 | 2 | -1.033 | -2.07 |
| ES | 1W-4h-15m continuation | london | 5 | 2 | 1 | 4 | -0.458 | -2.29 |
| ES | 1W-4h-15m continuation | ny_am | 5 | 3 | 3 | 2 | +0.782 | +3.91 |
| ES | 1W-4h-15m continuation | ny_pm | 2 | 0 | 0 | 2 | -1.014 | -2.03 |
| ES | 1W-4h-15m continuation | pre_ny | 5 | 4 | 2 | 3 | +0.161 | +0.81 |
| ES | 1W-4h-15m reversal | asia | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| ES | 1W-4h-15m reversal | london | 2 | 1 | 1 | 1 | +0.496 | +0.99 |
| ES | 1W-4h-15m reversal | ny_am | 2 | 0 | 0 | 2 | -1.004 | -2.01 |
| ES | 1W-4h-15m reversal | ny_pm | 2 | 1 | 0 | 2 | -1.006 | -2.01 |
| ES | 1W-4h-15m reversal | pre_ny | 2 | 0 | 0 | 2 | -1.008 | -2.02 |
| GC | 1D-1h-5m continuation | asia | 15 | 9 | 6 | 9 | +0.186 | +2.79 |
| GC | 1D-1h-5m continuation | london | 6 | 1 | 1 | 5 | -0.531 | -3.18 |
| GC | 1D-1h-5m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.031 | -1.03 |
| GC | 1D-1h-5m reversal | asia | 27 | 17 | 12 | 15 | +0.330 | +8.92 |
| GC | 1D-1h-5m reversal | london | 4 | 2 | 0 | 4 | -1.006 | -4.02 |
| GC | 1D-1h-5m reversal | ny_am | 31 | 14 | 7 | 23 | -0.291 | -9.01 |
| GC | 1D-1h-5m reversal | ny_lunch | 5 | 2 | 2 | 3 | +0.199 | +0.99 |
| GC | 1D-1h-5m reversal | ny_pm | 1 | 0 | 0 | 1 | -1.003 | -1.00 |
| GC | 1D-1h-5m reversal | pre_ny | 1 | 0 | 0 | 1 | -1.004 | -1.00 |
| GC | 1D-4h-15m continuation | asia | 1 | 1 | 0 | 1 | -1.020 | -1.02 |
| GC | 1D-4h-15m continuation | london | 1 | 1 | 0 | 1 | -1.005 | -1.00 |
| GC | 1D-4h-15m continuation | pre_ny | 1 | 1 | 1 | 0 | +1.995 | +1.99 |
| GC | 1D-4h-15m reversal | london | 4 | 3 | 2 | 2 | +0.498 | +1.99 |
| GC | 1D-4h-15m reversal | ny_am | 20 | 12 | 6 | 13 | -0.013 | -0.27 |
| GC | 1D-4h-15m reversal | ny_lunch | 5 | 2 | 0 | 4 | -0.850 | -4.25 |
| GC | 1D-4h-15m reversal | ny_pm | 1 | 1 | 1 | 0 | +1.999 | +2.00 |
| GC | 1D-4h-15m reversal | pre_ny | 3 | 2 | 2 | 1 | +0.998 | +3.00 |
| GC | 1M-1D-1h reversal | asia | 4 | 0 | 0 | 1 | -0.370 | -1.48 |
| GC | 1W-1D-1h continuation | asia | 1 | 0 | 0 | 1 | -1.012 | -1.01 |
| GC | 1W-1D-1h reversal | asia | 2 | 1 | 0 | 1 | +0.014 | +0.03 |
| GC | 1W-4h-15m continuation | asia | 4 | 1 | 1 | 3 | -0.259 | -1.04 |
| GC | 1W-4h-15m continuation | london | 2 | 2 | 2 | 0 | +1.999 | +4.00 |
| GC | 1W-4h-15m continuation | ny_am | 1 | 0 | 0 | 1 | -1.007 | -1.01 |
| GC | 1W-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.997 | +2.00 |
| GC | 1W-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.999 | +2.00 |
| GC | 1W-4h-15m continuation | pre_ny | 2 | 1 | 1 | 1 | +0.497 | +0.99 |
| GC | 1W-4h-15m reversal | london | 1 | 1 | 0 | 1 | -1.003 | -1.00 |
| GC | 1W-4h-15m reversal | ny_am | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| GC | 1W-4h-15m reversal | pre_ny | 1 | 0 | 0 | 1 | -1.003 | -1.00 |
| NQ | 1D-1h-5m continuation | asia | 11 | 6 | 5 | 6 | +0.345 | +3.80 |
| NQ | 1D-1h-5m continuation | london | 3 | 2 | 1 | 2 | -0.010 | -0.03 |
| NQ | 1D-1h-5m continuation | ny_am | 2 | 2 | 2 | 0 | +1.998 | +4.00 |
| NQ | 1D-1h-5m continuation | pre_ny | 5 | 3 | 2 | 3 | +0.184 | +0.92 |
| NQ | 1D-1h-5m reversal | asia | 21 | 13 | 9 | 12 | +0.283 | +5.95 |
| NQ | 1D-1h-5m reversal | london | 4 | 3 | 2 | 2 | +0.498 | +1.99 |
| NQ | 1D-1h-5m reversal | ny_am | 17 | 6 | 3 | 14 | -0.475 | -8.07 |
| NQ | 1D-1h-5m reversal | ny_lunch | 5 | 3 | 2 | 3 | +0.198 | +0.99 |
| NQ | 1D-1h-5m reversal | pre_ny | 3 | 3 | 1 | 2 | -0.003 | -0.01 |
| NQ | 1D-4h-15m continuation | asia | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| NQ | 1D-4h-15m continuation | london | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| NQ | 1D-4h-15m continuation | ny_am | 2 | 0 | 0 | 2 | -1.002 | -2.00 |
| NQ | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 0 | 1 | -1.007 | -1.01 |
| NQ | 1D-4h-15m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| NQ | 1D-4h-15m reversal | london | 4 | 1 | 1 | 3 | -0.252 | -1.01 |
| NQ | 1D-4h-15m reversal | ny_am | 20 | 10 | 4 | 16 | -0.403 | -8.05 |
| NQ | 1D-4h-15m reversal | ny_lunch | 6 | 3 | 2 | 4 | -0.001 | -0.00 |
| NQ | 1D-4h-15m reversal | ny_pm | 1 | 1 | 0 | 1 | -1.001 | -1.00 |
| NQ | 1D-4h-15m reversal | pre_ny | 2 | 2 | 1 | 1 | +0.499 | +1.00 |
| NQ | 1M-1D-1h continuation | asia | 1 | 0 | 0 | 1 | -1.010 | -1.01 |
| NQ | 1M-1D-1h reversal | asia | 2 | 0 | 0 | 2 | -1.000 | -2.00 |
| NQ | 1W-4h-15m continuation | asia | 1 | 1 | 1 | 0 | +1.995 | +1.99 |
| NQ | 1W-4h-15m continuation | london | 3 | 1 | 0 | 3 | -1.009 | -3.03 |
| NQ | 1W-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.028 | -1.03 |
| NQ | 1W-4h-15m reversal | asia | 2 | 1 | 1 | 1 | +0.499 | +1.00 |
| NQ | 1W-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.001 | -1.00 |
| NQ | 1W-4h-15m reversal | ny_am | 4 | 2 | 1 | 2 | +0.362 | +1.45 |
| NQ | 1W-4h-15m reversal | ny_pm | 2 | 2 | 2 | 0 | +1.999 | +4.00 |
| NQ | 1W-4h-15m reversal | pre_ny | 1 | 1 | 1 | 0 | +1.999 | +2.00 |
| RTY | 1D-1h-5m continuation | asia | 18 | 7 | 3 | 15 | -0.580 | -10.45 |
| RTY | 1D-1h-5m continuation | london | 13 | 5 | 4 | 9 | -0.107 | -1.39 |
| RTY | 1D-1h-5m continuation | ny_am | 4 | 1 | 1 | 3 | -0.293 | -1.17 |
| RTY | 1D-1h-5m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.024 | -1.02 |
| RTY | 1D-1h-5m continuation | pre_ny | 8 | 6 | 4 | 4 | +0.424 | +3.39 |
| RTY | 1D-1h-5m reversal | asia | 13 | 7 | 6 | 7 | +0.374 | +4.86 |
| RTY | 1D-1h-5m reversal | london | 2 | 1 | 1 | 1 | +0.489 | +0.98 |
| RTY | 1D-1h-5m reversal | ny_am | 22 | 10 | 8 | 14 | +0.074 | +1.63 |
| RTY | 1D-1h-5m reversal | ny_lunch | 13 | 5 | 4 | 8 | +0.037 | +0.48 |
| RTY | 1D-1h-5m reversal | pre_ny | 6 | 2 | 1 | 5 | -0.511 | -3.07 |
| RTY | 1D-4h-15m continuation | asia | 2 | 0 | 0 | 2 | -1.085 | -2.17 |
| RTY | 1D-4h-15m continuation | london | 2 | 2 | 1 | 1 | +0.458 | +0.92 |
| RTY | 1D-4h-15m continuation | ny_am | 2 | 1 | 1 | 1 | +0.485 | +0.97 |
| RTY | 1D-4h-15m continuation | pre_ny | 3 | 2 | 2 | 1 | +0.970 | +2.91 |
| RTY | 1D-4h-15m reversal | ny_am | 22 | 12 | 9 | 13 | +0.210 | +4.63 |
| RTY | 1D-4h-15m reversal | ny_lunch | 3 | 2 | 2 | 1 | +0.999 | +3.00 |
| RTY | 1D-4h-15m reversal | ny_pm | 3 | 2 | 1 | 1 | +0.445 | +1.33 |
| RTY | 1D-4h-15m reversal | pre_ny | 3 | 1 | 1 | 2 | -0.007 | -0.02 |
| RTY | 1M-1D-1h reversal | asia | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| RTY | 1W-1D-1h reversal | asia | 3 | 1 | 0 | 1 | -0.053 | -0.16 |
| RTY | 1W-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.063 | -1.06 |
| RTY | 1W-4h-15m continuation | ny_am | 2 | 2 | 2 | 0 | +1.972 | +3.94 |
| RTY | 1W-4h-15m continuation | pre_ny | 2 | 1 | 1 | 1 | +0.433 | +0.87 |
| RTY | 1W-4h-15m reversal | asia | 2 | 0 | 0 | 2 | -1.006 | -2.01 |
| RTY | 1W-4h-15m reversal | ny_am | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| RTY | 1W-4h-15m reversal | pre_ny | 1 | 0 | 0 | 1 | -1.009 | -1.01 |
| SI | 1D-1h-5m continuation | after_hours | 2 | 1 | 1 | 1 | +0.425 | +0.85 |
| SI | 1D-1h-5m continuation | asia | 29 | 14 | 11 | 18 | +0.116 | +3.37 |
| SI | 1D-1h-5m continuation | london | 5 | 5 | 4 | 1 | +1.397 | +6.98 |
| SI | 1D-1h-5m continuation | ny_am | 2 | 1 | 1 | 1 | +0.479 | +0.96 |
| SI | 1D-1h-5m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.031 | -1.03 |
| SI | 1D-1h-5m continuation | ny_pm | 2 | 1 | 1 | 1 | +0.490 | +0.98 |
| SI | 1D-1h-5m continuation | pre_ny | 6 | 4 | 4 | 2 | +0.986 | +5.92 |
| SI | 1D-1h-5m reversal | asia | 26 | 17 | 11 | 14 | +0.297 | +7.71 |
| SI | 1D-1h-5m reversal | london | 6 | 4 | 2 | 4 | -0.005 | -0.03 |
| SI | 1D-1h-5m reversal | ny_am | 21 | 8 | 6 | 14 | -0.106 | -2.22 |
| SI | 1D-1h-5m reversal | ny_lunch | 4 | 3 | 1 | 3 | -0.257 | -1.03 |
| SI | 1D-1h-5m reversal | pre_ny | 2 | 0 | 0 | 2 | -1.010 | -2.02 |
| SI | 1D-4h-15m continuation | asia | 2 | 1 | 0 | 2 | -1.007 | -2.01 |
| SI | 1D-4h-15m continuation | london | 1 | 0 | 0 | 1 | -1.006 | -1.01 |
| SI | 1D-4h-15m continuation | ny_am | 1 | 0 | 0 | 1 | -1.020 | -1.02 |
| SI | 1D-4h-15m continuation | ny_pm | 1 | 1 | 0 | 1 | -1.022 | -1.02 |
| SI | 1D-4h-15m continuation | pre_ny | 2 | 0 | 0 | 2 | -1.008 | -2.02 |
| SI | 1D-4h-15m reversal | london | 3 | 2 | 1 | 2 | -0.004 | -0.01 |
| SI | 1D-4h-15m reversal | ny_am | 11 | 5 | 4 | 7 | +0.088 | +0.97 |
| SI | 1D-4h-15m reversal | ny_lunch | 1 | 1 | 0 | 0 | +0.332 | +0.33 |
| SI | 1D-4h-15m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.004 | -2.01 |
| SI | 1D-4h-15m reversal | pre_ny | 2 | 2 | 2 | 0 | +1.999 | +4.00 |
| SI | 1M-1D-1h reversal | asia | 3 | 1 | 1 | 1 | +0.394 | +1.18 |
| SI | 1W-1D-1h reversal | asia | 3 | 1 | 1 | 0 | +0.897 | +2.69 |
| SI | 1W-4h-15m continuation | asia | 5 | 3 | 2 | 3 | +0.190 | +0.95 |
| SI | 1W-4h-15m continuation | london | 4 | 1 | 1 | 3 | -0.267 | -1.07 |
| SI | 1W-4h-15m continuation | ny_am | 2 | 0 | 0 | 2 | -1.013 | -2.03 |
| SI | 1W-4h-15m continuation | pre_ny | 1 | 1 | 1 | 0 | +1.998 | +2.00 |
| SI | 1W-4h-15m reversal | asia | 2 | 2 | 2 | 0 | +2.000 | +4.00 |
| SI | 1W-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.003 | -2.01 |
| SI | 1W-4h-15m reversal | ny_am | 4 | 2 | 0 | 2 | +0.012 | +0.05 |
| YM | 1D-1h-5m continuation | asia | 23 | 11 | 10 | 13 | +0.265 | +6.10 |
| YM | 1D-1h-5m continuation | london | 14 | 8 | 6 | 8 | +0.246 | +3.45 |
| YM | 1D-1h-5m continuation | ny_am | 2 | 2 | 1 | 1 | +0.470 | +0.94 |
| YM | 1D-1h-5m continuation | ny_lunch | 2 | 1 | 0 | 1 | +0.062 | +0.12 |
| YM | 1D-1h-5m continuation | pre_ny | 13 | 7 | 6 | 7 | +0.349 | +4.53 |
| YM | 1D-1h-5m reversal | asia | 10 | 7 | 7 | 3 | +1.093 | +10.93 |
| YM | 1D-1h-5m reversal | london | 2 | 0 | 0 | 2 | -1.009 | -2.02 |
| YM | 1D-1h-5m reversal | ny_am | 21 | 10 | 7 | 14 | -0.020 | -0.42 |
| YM | 1D-1h-5m reversal | ny_lunch | 11 | 4 | 3 | 8 | -0.194 | -2.13 |
| YM | 1D-1h-5m reversal | ny_pm | 1 | 1 | 0 | 1 | -1.003 | -1.00 |
| YM | 1D-1h-5m reversal | pre_ny | 6 | 1 | 0 | 6 | -1.011 | -6.07 |
| YM | 1D-4h-15m continuation | ny_am | 2 | 2 | 2 | 0 | +1.992 | +3.98 |
| YM | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.990 | +1.99 |
| YM | 1D-4h-15m continuation | pre_ny | 1 | 1 | 1 | 0 | +1.987 | +1.99 |
| YM | 1D-4h-15m reversal | ny_am | 15 | 6 | 2 | 13 | -0.618 | -9.27 |
| YM | 1D-4h-15m reversal | ny_lunch | 6 | 1 | 0 | 5 | -0.870 | -5.22 |
| YM | 1D-4h-15m reversal | ny_pm | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| YM | 1D-4h-15m reversal | pre_ny | 1 | 0 | 0 | 1 | -1.006 | -1.01 |
| YM | 1M-1D-1h reversal | asia | 1 | 0 | 0 | 1 | -1.003 | -1.00 |
| YM | 1W-1D-1h continuation | asia | 1 | 1 | 0 | 1 | -1.025 | -1.03 |
| YM | 1W-1D-1h reversal | asia | 2 | 1 | 0 | 0 | +0.640 | +1.28 |
| YM | 1W-4h-15m continuation | asia | 2 | 2 | 1 | 1 | +0.468 | +0.94 |
| YM | 1W-4h-15m continuation | london | 5 | 5 | 2 | 3 | +0.158 | +0.79 |
| YM | 1W-4h-15m continuation | ny_am | 2 | 0 | 0 | 2 | -1.008 | -2.02 |
| YM | 1W-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.020 | -1.02 |
| YM | 1W-4h-15m continuation | ny_pm | 1 | 0 | 0 | 1 | -1.004 | -1.00 |
| YM | 1W-4h-15m continuation | pre_ny | 3 | 2 | 2 | 1 | +0.983 | +2.95 |
| YM | 1W-4h-15m reversal | asia | 1 | 0 | 0 | 1 | -1.003 | -1.00 |
| YM | 1W-4h-15m reversal | ny_am | 4 | 0 | 0 | 4 | -1.003 | -4.01 |
| YM | 1W-4h-15m reversal | ny_pm | 2 | 1 | 1 | 1 | +0.496 | +0.99 |
