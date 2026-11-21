---
id: tv-2025-baseline
title: "TTFM backtest tv-2025-baseline: 2025, variant baseline"
type: backtest-run
model: TTFM
concepts: [reversal, continuation, cisd, candle-2, protected-swing]
run_date: 2026-11-20
from: 2025-01-01
to: 2025-12-31
symbols: ["6E", "CL", "ES", "GC", "NQ", "RTY", "SI", "YM"]
switches: {"variant": "baseline", "stacks": ["1D-1h-5m", "1D-4h-15m", "1M-1D-1h", "1W-1D-1h", "1W-4h-15m"]}
tests: []
plans: 1219
total_r: 8.45
data: results/backtest_tv/2025/baseline
---

# TTFM backtest tv-2025-baseline

2025, variant baseline

1219 taken trades, +8.45 R at the 2R plan over 2025-01-01 to 2025-12-31. The companion's own rules on TradingView bars; cost model included, no slippage. Evidence, not a validated rule.

## Per setup

| Symbol | Stack + path | Session | Trades | 1R wins | 2R wins | Stopped | Avg R | Total R |
|---|---|---|---|---|---|---|---|---|
| 6E | 1D-1h-5m continuation | asia | 22 | 17 | 10 | 12 | +0.188 | +4.14 |
| 6E | 1D-1h-5m continuation | london | 10 | 6 | 3 | 7 | -0.218 | -2.18 |
| 6E | 1D-1h-5m continuation | ny_am | 2 | 2 | 1 | 1 | +0.407 | +0.81 |
| 6E | 1D-1h-5m continuation | ny_lunch | 2 | 1 | 0 | 2 | -1.060 | -2.12 |
| 6E | 1D-1h-5m continuation | ny_pm | 2 | 1 | 1 | 1 | +0.449 | +0.90 |
| 6E | 1D-1h-5m continuation | pre_ny | 6 | 2 | 1 | 5 | -0.573 | -3.44 |
| 6E | 1D-1h-5m reversal | asia | 14 | 10 | 5 | 9 | +0.043 | +0.60 |
| 6E | 1D-1h-5m reversal | london | 9 | 5 | 3 | 6 | -0.025 | -0.22 |
| 6E | 1D-1h-5m reversal | ny_am | 26 | 11 | 7 | 18 | -0.210 | -5.45 |
| 6E | 1D-1h-5m reversal | ny_lunch | 1 | 0 | 0 | 1 | -1.082 | -1.08 |
| 6E | 1D-1h-5m reversal | ny_pm | 1 | 0 | 0 | 1 | -1.014 | -1.01 |
| 6E | 1D-1h-5m reversal | pre_ny | 13 | 3 | 1 | 12 | -0.808 | -10.50 |
| 6E | 1D-4h-15m continuation | london | 2 | 2 | 1 | 1 | +0.445 | +0.89 |
| 6E | 1D-4h-15m continuation | ny_am | 1 | 0 | 0 | 1 | -1.022 | -1.02 |
| 6E | 1D-4h-15m continuation | pre_ny | 2 | 1 | 1 | 1 | +0.426 | +0.85 |
| 6E | 1D-4h-15m reversal | london | 2 | 1 | 1 | 1 | +0.489 | +0.98 |
| 6E | 1D-4h-15m reversal | ny_am | 16 | 5 | 4 | 12 | -0.274 | -4.38 |
| 6E | 1D-4h-15m reversal | ny_lunch | 1 | 0 | 0 | 1 | -1.014 | -1.01 |
| 6E | 1D-4h-15m reversal | ny_pm | 3 | 1 | 0 | 3 | -1.018 | -3.05 |
| 6E | 1D-4h-15m reversal | pre_ny | 2 | 2 | 2 | 0 | +1.992 | +3.98 |
| 6E | 1M-1D-1h continuation | pre_ny | 1 | 0 | 0 | 1 | -1.061 | -1.06 |
| 6E | 1W-1D-1h continuation | asia | 1 | 1 | 1 | 0 | +1.967 | +1.97 |
| 6E | 1W-4h-15m continuation | asia | 6 | 3 | 0 | 6 | -1.073 | -6.44 |
| 6E | 1W-4h-15m continuation | london | 2 | 1 | 1 | 1 | +0.462 | +0.92 |
| 6E | 1W-4h-15m continuation | ny_am | 2 | 1 | 1 | 1 | +0.448 | +0.90 |
| 6E | 1W-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.992 | +1.99 |
| 6E | 1W-4h-15m continuation | pre_ny | 4 | 2 | 1 | 3 | -0.350 | -1.40 |
| 6E | 1W-4h-15m reversal | asia | 1 | 1 | 0 | 0 | +1.034 | +1.03 |
| 6E | 1W-4h-15m reversal | london | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| 6E | 1W-4h-15m reversal | ny_am | 1 | 0 | 0 | 1 | -1.026 | -1.03 |
| 6E | 1W-4h-15m reversal | ny_pm | 2 | 1 | 1 | 1 | +0.493 | +0.99 |
| 6E | 1W-4h-15m reversal | pre_ny | 2 | 2 | 2 | 0 | +1.992 | +3.98 |
| CL | 1D-1h-5m continuation | asia | 20 | 7 | 3 | 17 | -0.694 | -13.87 |
| CL | 1D-1h-5m continuation | london | 9 | 4 | 4 | 5 | +0.292 | +2.63 |
| CL | 1D-1h-5m continuation | ny_am | 5 | 2 | 2 | 3 | +0.153 | +0.77 |
| CL | 1D-1h-5m continuation | pre_ny | 5 | 1 | 1 | 4 | -0.488 | -2.44 |
| CL | 1D-1h-5m reversal | asia | 5 | 3 | 2 | 3 | +0.184 | +0.92 |
| CL | 1D-1h-5m reversal | london | 3 | 2 | 2 | 1 | +0.985 | +2.95 |
| CL | 1D-1h-5m reversal | ny_am | 16 | 9 | 4 | 11 | -0.188 | -3.00 |
| CL | 1D-1h-5m reversal | ny_lunch | 5 | 1 | 1 | 4 | -0.413 | -2.07 |
| CL | 1D-1h-5m reversal | pre_ny | 15 | 9 | 6 | 8 | +0.287 | +4.31 |
| CL | 1D-4h-15m continuation | asia | 2 | 0 | 0 | 2 | -1.187 | -2.37 |
| CL | 1D-4h-15m continuation | london | 2 | 1 | 1 | 1 | +0.481 | +0.96 |
| CL | 1D-4h-15m continuation | ny_am | 2 | 1 | 1 | 1 | +0.451 | +0.90 |
| CL | 1D-4h-15m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.132 | -1.13 |
| CL | 1D-4h-15m reversal | ny_am | 16 | 10 | 6 | 10 | +0.103 | +1.64 |
| CL | 1D-4h-15m reversal | ny_lunch | 6 | 5 | 4 | 1 | +1.268 | +7.61 |
| CL | 1D-4h-15m reversal | ny_pm | 1 | 1 | 1 | 0 | +1.995 | +2.00 |
| CL | 1D-4h-15m reversal | pre_ny | 7 | 2 | 0 | 6 | -0.764 | -5.35 |
| CL | 1M-1D-1h reversal | asia | 1 | 0 | 0 | 0 | +0.774 | +0.77 |
| CL | 1W-1D-1h continuation | pre_ny | 1 | 1 | 1 | 0 | +1.995 | +1.99 |
| CL | 1W-1D-1h reversal | asia | 5 | 1 | 0 | 1 | +0.237 | +1.18 |
| CL | 1W-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.112 | -1.11 |
| CL | 1W-4h-15m continuation | london | 2 | 2 | 1 | 1 | +0.456 | +0.91 |
| CL | 1W-4h-15m continuation | ny_am | 1 | 1 | 1 | 0 | +1.980 | +1.98 |
| CL | 1W-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.987 | +1.99 |
| CL | 1W-4h-15m continuation | pre_ny | 2 | 2 | 1 | 1 | +0.481 | +0.96 |
| CL | 1W-4h-15m reversal | asia | 3 | 0 | 0 | 3 | -1.013 | -3.04 |
| CL | 1W-4h-15m reversal | ny_am | 5 | 4 | 3 | 1 | +1.203 | +6.01 |
| CL | 1W-4h-15m reversal | ny_pm | 3 | 0 | 0 | 2 | -0.490 | -1.47 |
| CL | 1W-4h-15m reversal | pre_ny | 1 | 1 | 0 | 1 | -1.014 | -1.01 |
| ES | 1D-1h-5m continuation | asia | 13 | 6 | 4 | 9 | -0.169 | -2.20 |
| ES | 1D-1h-5m continuation | london | 11 | 7 | 4 | 7 | +0.033 | +0.36 |
| ES | 1D-1h-5m continuation | ny_am | 1 | 1 | 1 | 0 | +1.990 | +1.99 |
| ES | 1D-1h-5m continuation | pre_ny | 7 | 2 | 1 | 6 | -0.636 | -4.45 |
| ES | 1D-1h-5m reversal | asia | 8 | 2 | 0 | 8 | -1.015 | -8.12 |
| ES | 1D-1h-5m reversal | ny_am | 32 | 16 | 6 | 25 | -0.413 | -13.21 |
| ES | 1D-1h-5m reversal | ny_lunch | 17 | 9 | 6 | 11 | +0.047 | +0.80 |
| ES | 1D-1h-5m reversal | ny_pm | 2 | 1 | 1 | 1 | +0.491 | +0.98 |
| ES | 1D-1h-5m reversal | pre_ny | 6 | 3 | 2 | 4 | -0.015 | -0.09 |
| ES | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.068 | -1.07 |
| ES | 1D-4h-15m continuation | london | 1 | 1 | 1 | 0 | +1.993 | +1.99 |
| ES | 1D-4h-15m continuation | ny_pm | 1 | 0 | 0 | 1 | -1.004 | -1.00 |
| ES | 1D-4h-15m continuation | pre_ny | 5 | 5 | 4 | 1 | +1.379 | +6.90 |
| ES | 1D-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.006 | -2.01 |
| ES | 1D-4h-15m reversal | ny_am | 26 | 16 | 11 | 14 | +0.322 | +8.37 |
| ES | 1D-4h-15m reversal | ny_lunch | 3 | 2 | 0 | 3 | -1.005 | -3.02 |
| ES | 1D-4h-15m reversal | ny_pm | 3 | 2 | 2 | 1 | +0.995 | +2.98 |
| ES | 1D-4h-15m reversal | pre_ny | 1 | 1 | 1 | 0 | +1.996 | +2.00 |
| ES | 1W-1D-1h reversal | asia | 2 | 1 | 0 | 1 | -0.001 | -0.00 |
| ES | 1W-4h-15m reversal | asia | 2 | 2 | 0 | 2 | -1.006 | -2.01 |
| ES | 1W-4h-15m reversal | london | 3 | 0 | 0 | 3 | -1.007 | -3.02 |
| ES | 1W-4h-15m reversal | ny_am | 1 | 1 | 0 | 0 | +1.284 | +1.28 |
| ES | 1W-4h-15m reversal | ny_pm | 3 | 1 | 1 | 2 | -0.005 | -0.01 |
| GC | 1D-1h-5m continuation | asia | 16 | 11 | 7 | 9 | +0.291 | +4.66 |
| GC | 1D-1h-5m continuation | london | 7 | 2 | 2 | 5 | -0.195 | -1.36 |
| GC | 1D-1h-5m continuation | ny_am | 1 | 1 | 1 | 0 | +1.999 | +2.00 |
| GC | 1D-1h-5m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.081 | -1.08 |
| GC | 1D-1h-5m reversal | asia | 20 | 12 | 8 | 12 | +0.193 | +3.86 |
| GC | 1D-1h-5m reversal | london | 2 | 1 | 1 | 1 | +0.495 | +0.99 |
| GC | 1D-1h-5m reversal | ny_am | 15 | 8 | 5 | 9 | +0.076 | +1.14 |
| GC | 1D-1h-5m reversal | ny_lunch | 5 | 2 | 1 | 4 | -0.407 | -2.04 |
| GC | 1D-1h-5m reversal | pre_ny | 2 | 1 | 1 | 1 | +0.496 | +0.99 |
| GC | 1D-4h-15m continuation | asia | 3 | 0 | 0 | 3 | -1.028 | -3.08 |
| GC | 1D-4h-15m continuation | london | 3 | 1 | 0 | 3 | -1.010 | -3.03 |
| GC | 1D-4h-15m continuation | ny_lunch | 2 | 1 | 1 | 1 | +0.484 | +0.97 |
| GC | 1D-4h-15m continuation | ny_pm | 1 | 0 | 0 | 1 | -1.010 | -1.01 |
| GC | 1D-4h-15m continuation | pre_ny | 3 | 2 | 1 | 2 | -0.020 | -0.06 |
| GC | 1D-4h-15m reversal | london | 2 | 2 | 2 | 0 | +1.998 | +4.00 |
| GC | 1D-4h-15m reversal | ny_am | 14 | 8 | 7 | 7 | +0.492 | +6.88 |
| GC | 1D-4h-15m reversal | ny_lunch | 2 | 2 | 1 | 1 | +0.498 | +1.00 |
| GC | 1D-4h-15m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.006 | -2.01 |
| GC | 1D-4h-15m reversal | pre_ny | 1 | 1 | 1 | 0 | +1.998 | +2.00 |
| GC | 1M-1D-1h reversal | asia | 1 | 1 | 0 | 0 | +1.107 | +1.11 |
| GC | 1W-1D-1h reversal | asia | 2 | 0 | 0 | 0 | +0.032 | +0.06 |
| GC | 1W-4h-15m reversal | london | 2 | 2 | 1 | 0 | +1.301 | +2.60 |
| GC | 1W-4h-15m reversal | ny_am | 1 | 0 | 0 | 1 | -1.006 | -1.01 |
| NQ | 1D-1h-5m continuation | asia | 16 | 6 | 6 | 10 | +0.096 | +1.53 |
| NQ | 1D-1h-5m continuation | london | 6 | 3 | 3 | 3 | +0.488 | +2.93 |
| NQ | 1D-1h-5m continuation | ny_am | 2 | 1 | 0 | 2 | -1.012 | -2.02 |
| NQ | 1D-1h-5m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.997 | +2.00 |
| NQ | 1D-1h-5m continuation | pre_ny | 5 | 3 | 3 | 2 | +0.777 | +3.88 |
| NQ | 1D-1h-5m reversal | asia | 12 | 6 | 3 | 9 | -0.254 | -3.05 |
| NQ | 1D-1h-5m reversal | ny_am | 32 | 12 | 6 | 25 | -0.390 | -12.47 |
| NQ | 1D-1h-5m reversal | ny_lunch | 18 | 8 | 6 | 12 | -0.004 | -0.07 |
| NQ | 1D-1h-5m reversal | pre_ny | 5 | 1 | 0 | 5 | -1.006 | -5.03 |
| NQ | 1D-4h-15m continuation | after_hours | 1 | 1 | 1 | 0 | +1.974 | +1.97 |
| NQ | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.016 | -1.02 |
| NQ | 1D-4h-15m continuation | london | 1 | 1 | 0 | 1 | -1.009 | -1.01 |
| NQ | 1D-4h-15m continuation | pre_ny | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| NQ | 1D-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| NQ | 1D-4h-15m reversal | ny_am | 25 | 15 | 9 | 15 | +0.166 | +4.15 |
| NQ | 1D-4h-15m reversal | ny_lunch | 6 | 3 | 1 | 4 | -0.120 | -0.72 |
| NQ | 1D-4h-15m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.002 | -2.00 |
| NQ | 1M-1D-1h continuation | asia | 1 | 0 | 0 | 1 | -1.013 | -1.01 |
| NQ | 1M-1D-1h continuation | ny_am | 1 | 0 | 0 | 1 | -1.004 | -1.00 |
| NQ | 1M-1D-1h reversal | asia | 1 | 0 | 0 | 0 | +0.519 | +0.52 |
| NQ | 1W-1D-1h reversal | asia | 2 | 1 | 1 | 1 | +0.499 | +1.00 |
| NQ | 1W-4h-15m reversal | asia | 2 | 1 | 1 | 1 | +0.498 | +1.00 |
| NQ | 1W-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| NQ | 1W-4h-15m reversal | ny_am | 2 | 2 | 1 | 0 | +1.720 | +3.44 |
| NQ | 1W-4h-15m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.002 | -2.00 |
| RTY | 1D-1h-5m continuation | asia | 20 | 7 | 3 | 16 | -0.636 | -12.09 |
| RTY | 1D-1h-5m continuation | london | 8 | 3 | 3 | 5 | +0.040 | +0.32 |
| RTY | 1D-1h-5m continuation | ny_am | 5 | 2 | 2 | 3 | +0.166 | +0.83 |
| RTY | 1D-1h-5m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.037 | -1.04 |
| RTY | 1D-1h-5m continuation | pre_ny | 14 | 11 | 8 | 6 | +0.669 | +9.37 |
| RTY | 1D-1h-5m reversal | asia | 9 | 5 | 2 | 7 | -0.348 | -3.13 |
| RTY | 1D-1h-5m reversal | london | 2 | 1 | 1 | 1 | +0.479 | +0.96 |
| RTY | 1D-1h-5m reversal | ny_am | 37 | 19 | 14 | 22 | +0.135 | +4.98 |
| RTY | 1D-1h-5m reversal | ny_lunch | 21 | 8 | 4 | 17 | -0.439 | -9.22 |
| RTY | 1D-1h-5m reversal | pre_ny | 10 | 6 | 3 | 7 | -0.115 | -1.15 |
| RTY | 1D-4h-15m continuation | london | 2 | 2 | 2 | 0 | +1.977 | +3.95 |
| RTY | 1D-4h-15m continuation | ny_am | 1 | 1 | 1 | 0 | +1.993 | +1.99 |
| RTY | 1D-4h-15m continuation | pre_ny | 4 | 2 | 1 | 3 | -0.283 | -1.13 |
| RTY | 1D-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.003 | -1.00 |
| RTY | 1D-4h-15m reversal | ny_am | 20 | 12 | 9 | 11 | +0.332 | +6.63 |
| RTY | 1D-4h-15m reversal | ny_lunch | 3 | 2 | 2 | 1 | +0.994 | +2.98 |
| RTY | 1D-4h-15m reversal | ny_pm | 1 | 1 | 1 | 0 | +1.998 | +2.00 |
| RTY | 1D-4h-15m reversal | pre_ny | 1 | 1 | 1 | 0 | +1.997 | +2.00 |
| RTY | 1M-1D-1h continuation | asia | 1 | 1 | 1 | 0 | +1.953 | +1.95 |
| RTY | 1W-4h-15m continuation | asia | 2 | 1 | 0 | 2 | -1.082 | -2.16 |
| RTY | 1W-4h-15m continuation | london | 2 | 1 | 1 | 1 | +0.471 | +0.94 |
| RTY | 1W-4h-15m continuation | ny_am | 3 | 1 | 1 | 2 | -0.014 | -0.04 |
| RTY | 1W-4h-15m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.036 | -1.04 |
| RTY | 1W-4h-15m reversal | asia | 2 | 0 | 0 | 2 | -1.007 | -2.01 |
| RTY | 1W-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.006 | -2.01 |
| RTY | 1W-4h-15m reversal | ny_pm | 2 | 1 | 0 | 2 | -1.011 | -2.02 |
| SI | 1D-1h-5m continuation | after_hours | 1 | 0 | 0 | 1 | -1.025 | -1.03 |
| SI | 1D-1h-5m continuation | asia | 27 | 16 | 8 | 19 | -0.171 | -4.63 |
| SI | 1D-1h-5m continuation | london | 5 | 2 | 1 | 4 | -0.445 | -2.22 |
| SI | 1D-1h-5m continuation | ny_am | 3 | 2 | 2 | 1 | +0.991 | +2.97 |
| SI | 1D-1h-5m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.118 | -1.12 |
| SI | 1D-1h-5m continuation | ny_pm | 1 | 0 | 0 | 1 | -1.027 | -1.03 |
| SI | 1D-1h-5m continuation | pre_ny | 9 | 3 | 2 | 7 | -0.406 | -3.65 |
| SI | 1D-1h-5m reversal | asia | 21 | 12 | 9 | 12 | +0.274 | +5.75 |
| SI | 1D-1h-5m reversal | london | 4 | 2 | 2 | 2 | +0.487 | +1.95 |
| SI | 1D-1h-5m reversal | ny_am | 15 | 7 | 5 | 10 | -0.039 | -0.58 |
| SI | 1D-1h-5m reversal | ny_lunch | 3 | 0 | 0 | 3 | -1.011 | -3.03 |
| SI | 1D-1h-5m reversal | pre_ny | 4 | 2 | 2 | 2 | +0.490 | +1.96 |
| SI | 1D-4h-15m continuation | asia | 3 | 1 | 0 | 3 | -1.028 | -3.09 |
| SI | 1D-4h-15m continuation | london | 2 | 2 | 2 | 0 | +1.996 | +3.99 |
| SI | 1D-4h-15m continuation | ny_am | 2 | 2 | 2 | 0 | +1.998 | +4.00 |
| SI | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.997 | +2.00 |
| SI | 1D-4h-15m continuation | pre_ny | 1 | 1 | 0 | 1 | -1.045 | -1.05 |
| SI | 1D-4h-15m reversal | london | 2 | 1 | 1 | 1 | +0.496 | +0.99 |
| SI | 1D-4h-15m reversal | ny_am | 6 | 6 | 6 | 0 | +1.996 | +11.98 |
| SI | 1D-4h-15m reversal | ny_lunch | 1 | 1 | 0 | 0 | +1.505 | +1.50 |
| SI | 1D-4h-15m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.010 | -2.02 |
| SI | 1D-4h-15m reversal | pre_ny | 1 | 1 | 1 | 0 | +1.998 | +2.00 |
| SI | 1M-1D-1h continuation | london | 1 | 1 | 1 | 0 | +1.994 | +1.99 |
| SI | 1M-1D-1h reversal | asia | 2 | 2 | 1 | 0 | +1.441 | +2.88 |
| SI | 1W-1D-1h continuation | london | 3 | 3 | 1 | 2 | -0.022 | -0.07 |
| SI | 1W-4h-15m continuation | asia | 5 | 3 | 2 | 3 | +0.095 | +0.47 |
| SI | 1W-4h-15m continuation | london | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| SI | 1W-4h-15m continuation | ny_am | 2 | 1 | 0 | 2 | -1.018 | -2.04 |
| SI | 1W-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.982 | +1.98 |
| SI | 1W-4h-15m continuation | ny_pm | 1 | 0 | 0 | 1 | -1.037 | -1.04 |
| SI | 1W-4h-15m continuation | pre_ny | 3 | 1 | 1 | 2 | -0.070 | -0.21 |
| SI | 1W-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.009 | -1.01 |
| SI | 1W-4h-15m reversal | pre_ny | 1 | 0 | 0 | 1 | -1.014 | -1.01 |
| YM | 1D-1h-5m continuation | after_hours | 1 | 1 | 0 | 1 | -1.079 | -1.08 |
| YM | 1D-1h-5m continuation | asia | 19 | 9 | 6 | 13 | -0.128 | -2.44 |
| YM | 1D-1h-5m continuation | london | 10 | 3 | 2 | 8 | -0.469 | -4.69 |
| YM | 1D-1h-5m continuation | ny_am | 3 | 1 | 0 | 3 | -1.026 | -3.08 |
| YM | 1D-1h-5m continuation | ny_lunch | 3 | 2 | 1 | 2 | -0.026 | -0.08 |
| YM | 1D-1h-5m continuation | pre_ny | 12 | 6 | 4 | 8 | -0.050 | -0.60 |
| YM | 1D-1h-5m reversal | after_hours | 1 | 1 | 0 | 0 | +0.917 | +0.92 |
| YM | 1D-1h-5m reversal | asia | 7 | 5 | 4 | 3 | +0.706 | +4.94 |
| YM | 1D-1h-5m reversal | london | 3 | 2 | 2 | 1 | +0.991 | +2.97 |
| YM | 1D-1h-5m reversal | ny_am | 38 | 22 | 18 | 18 | +0.478 | +18.18 |
| YM | 1D-1h-5m reversal | ny_lunch | 11 | 3 | 1 | 10 | -0.734 | -8.07 |
| YM | 1D-1h-5m reversal | pre_ny | 5 | 4 | 2 | 3 | +0.189 | +0.94 |
| YM | 1D-4h-15m continuation | asia | 1 | 1 | 0 | 1 | -1.083 | -1.08 |
| YM | 1D-4h-15m continuation | london | 4 | 2 | 1 | 3 | -0.326 | -1.30 |
| YM | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.982 | +1.98 |
| YM | 1D-4h-15m continuation | ny_pm | 2 | 1 | 0 | 2 | -1.012 | -2.02 |
| YM | 1D-4h-15m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.041 | -1.04 |
| YM | 1D-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.005 | -2.01 |
| YM | 1D-4h-15m reversal | ny_am | 27 | 11 | 10 | 16 | +0.133 | +3.58 |
| YM | 1D-4h-15m reversal | ny_lunch | 7 | 6 | 3 | 1 | +1.058 | +7.41 |
| YM | 1D-4h-15m reversal | ny_pm | 4 | 2 | 0 | 3 | -0.470 | -1.88 |
| YM | 1M-1D-1h continuation | ny_am | 1 | 1 | 0 | 1 | -1.022 | -1.02 |
| YM | 1W-1D-1h continuation | asia | 1 | 0 | 0 | 1 | -1.063 | -1.06 |
| YM | 1W-1D-1h continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.980 | +1.98 |
| YM | 1W-1D-1h continuation | pre_ny | 1 | 0 | 0 | 1 | -1.040 | -1.04 |
| YM | 1W-1D-1h reversal | asia | 2 | 1 | 0 | 0 | +0.905 | +1.81 |
| YM | 1W-4h-15m continuation | asia | 2 | 2 | 1 | 1 | +0.493 | +0.99 |
| YM | 1W-4h-15m continuation | london | 1 | 1 | 0 | 1 | -1.083 | -1.08 |
| YM | 1W-4h-15m continuation | ny_am | 3 | 1 | 0 | 3 | -1.023 | -3.07 |
| YM | 1W-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.051 | -1.05 |
| YM | 1W-4h-15m continuation | ny_pm | 5 | 1 | 1 | 4 | -0.412 | -2.06 |
| YM | 1W-4h-15m continuation | pre_ny | 4 | 2 | 2 | 2 | +0.463 | +1.85 |
| YM | 1W-4h-15m reversal | asia | 2 | 2 | 1 | 1 | +0.496 | +0.99 |
| YM | 1W-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.007 | -1.01 |
| YM | 1W-4h-15m reversal | ny_am | 3 | 2 | 1 | 1 | +0.699 | +2.10 |
| YM | 1W-4h-15m reversal | ny_pm | 3 | 2 | 0 | 2 | -0.718 | -2.15 |
| YM | 1W-4h-15m reversal | pre_ny | 2 | 1 | 0 | 1 | -0.445 | -0.89 |
