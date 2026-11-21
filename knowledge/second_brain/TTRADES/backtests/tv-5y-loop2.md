---
id: tv-5y-loop2
title: "TTFM backtest tv-5y-loop2: loop turn 12: loop1 + htf_align_role quality (the 4H candle must support the trade), 5 years, 8 symbols, stacks 1D/1h/5m, 1D/4h/15m, 1W/1D/1h; every taken trigger"
type: backtest-run
model: TTFM
concepts: [reversal, continuation, cisd, candle-2, protected-swing]
run_date: 2026-11-21
from: 2021-11-15
to: 2026-11-12
symbols: ["6E", "CL", "ES", "GC", "NQ", "RTY", "SI", "YM"]
switches: {"variant": "loop2", "stacks": ["1D-1h-5m", "1D-4h-15m", "1W-1D-1h"]}
tests: ["TD-008", "TD-009", "TD-010", "TD-011"]
plans: 1277
total_r: 89.36
data: ["results/backtest_tv_5y/2021/loop2", "results/backtest_tv_5y/2022/loop2", "results/backtest_tv_5y/2023/loop2", "results/backtest_tv_5y/2024/loop2", "results/backtest_tv_5y/2025/loop2", "results/backtest_tv_5y/2026/loop2"]
---

# TTFM backtest tv-5y-loop2

loop turn 12: loop1 + htf_align_role quality (the 4H candle must support the trade), 5 years, 8 symbols, stacks 1D/1h/5m, 1D/4h/15m, 1W/1D/1h; every taken trigger

1277 taken trades, +89.36 R at the 2R plan over 2021-11-15 to 2026-11-12. The companion's own rules on TradingView bars; cost model included, no slippage. Evidence, not a validated rule.

## Per setup

| Symbol | Stack + path | Session | Trades | 1R wins | 2R wins | Stopped | Avg R | Total R |
|---|---|---|---|---|---|---|---|---|
| 6E | 1D-1h-5m continuation | asia | 12 | 7 | 5 | 7 | +0.125 | +1.49 |
| 6E | 1D-1h-5m continuation | london | 3 | 0 | 0 | 3 | -1.149 | -3.45 |
| 6E | 1D-1h-5m continuation | pre_ny | 1 | 1 | 1 | 0 | +1.989 | +1.99 |
| 6E | 1D-1h-5m reversal | asia | 16 | 9 | 4 | 12 | -0.285 | -4.57 |
| 6E | 1D-1h-5m reversal | london | 9 | 7 | 4 | 5 | +0.305 | +2.75 |
| 6E | 1D-1h-5m reversal | ny_am | 4 | 2 | 2 | 2 | +0.430 | +1.72 |
| 6E | 1D-1h-5m reversal | ny_lunch | 3 | 0 | 0 | 3 | -1.019 | -3.06 |
| 6E | 1D-1h-5m reversal | ny_pm | 2 | 1 | 0 | 1 | -0.291 | -0.58 |
| 6E | 1D-1h-5m reversal | pre_ny | 17 | 9 | 8 | 9 | +0.387 | +6.58 |
| 6E | 1D-4h-15m continuation | asia | 4 | 1 | 1 | 3 | -0.321 | -1.28 |
| 6E | 1D-4h-15m continuation | london | 6 | 4 | 1 | 5 | -0.580 | -3.48 |
| 6E | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.051 | -1.05 |
| 6E | 1D-4h-15m continuation | pre_ny | 4 | 1 | 1 | 3 | -0.312 | -1.25 |
| 6E | 1D-4h-15m reversal | london | 3 | 1 | 1 | 2 | -0.013 | -0.04 |
| 6E | 1D-4h-15m reversal | ny_am | 2 | 1 | 1 | 1 | +0.457 | +0.91 |
| 6E | 1D-4h-15m reversal | ny_lunch | 23 | 11 | 10 | 11 | +0.448 | +10.29 |
| 6E | 1D-4h-15m reversal | ny_pm | 6 | 2 | 0 | 6 | -1.016 | -6.10 |
| 6E | 1D-4h-15m reversal | pre_ny | 11 | 9 | 7 | 3 | +1.010 | +11.11 |
| 6E | 1W-1D-1h reversal | asia | 5 | 3 | 0 | 1 | +0.487 | +2.44 |
| CL | 1D-1h-5m continuation | asia | 8 | 5 | 4 | 4 | +0.462 | +3.70 |
| CL | 1D-1h-5m continuation | london | 2 | 0 | 0 | 2 | -1.030 | -2.06 |
| CL | 1D-1h-5m continuation | pre_ny | 2 | 1 | 1 | 1 | +0.453 | +0.91 |
| CL | 1D-1h-5m reversal | asia | 12 | 4 | 2 | 10 | -0.517 | -6.20 |
| CL | 1D-1h-5m reversal | london | 8 | 2 | 2 | 6 | -0.261 | -2.09 |
| CL | 1D-1h-5m reversal | ny_am | 9 | 6 | 4 | 5 | +0.308 | +2.77 |
| CL | 1D-1h-5m reversal | ny_lunch | 12 | 8 | 3 | 9 | -0.259 | -3.11 |
| CL | 1D-1h-5m reversal | ny_pm | 3 | 0 | 0 | 3 | -1.008 | -3.02 |
| CL | 1D-1h-5m reversal | pre_ny | 29 | 16 | 11 | 18 | +0.122 | +3.54 |
| CL | 1D-4h-15m continuation | asia | 7 | 3 | 2 | 5 | -0.184 | -1.29 |
| CL | 1D-4h-15m continuation | london | 9 | 4 | 4 | 5 | +0.313 | +2.82 |
| CL | 1D-4h-15m continuation | ny_am | 3 | 2 | 1 | 2 | -0.016 | -0.05 |
| CL | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.995 | +1.99 |
| CL | 1D-4h-15m continuation | pre_ny | 4 | 1 | 1 | 3 | -0.272 | -1.09 |
| CL | 1D-4h-15m reversal | london | 4 | 4 | 3 | 1 | +1.246 | +4.98 |
| CL | 1D-4h-15m reversal | ny_am | 1 | 1 | 1 | 0 | +1.998 | +2.00 |
| CL | 1D-4h-15m reversal | ny_lunch | 19 | 12 | 8 | 6 | +0.685 | +13.01 |
| CL | 1D-4h-15m reversal | ny_pm | 8 | 4 | 3 | 4 | +0.301 | +2.41 |
| CL | 1D-4h-15m reversal | pre_ny | 17 | 10 | 7 | 9 | +0.329 | +5.60 |
| CL | 1W-1D-1h continuation | london | 1 | 1 | 1 | 0 | +1.975 | +1.98 |
| CL | 1W-1D-1h reversal | asia | 11 | 2 | 0 | 4 | -0.117 | -1.29 |
| ES | 1D-1h-5m continuation | asia | 4 | 1 | 1 | 3 | -0.311 | -1.24 |
| ES | 1D-1h-5m continuation | london | 1 | 1 | 0 | 1 | -1.065 | -1.06 |
| ES | 1D-1h-5m continuation | ny_am | 4 | 2 | 1 | 3 | -0.293 | -1.17 |
| ES | 1D-1h-5m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.085 | -1.08 |
| ES | 1D-1h-5m reversal | asia | 11 | 7 | 4 | 7 | +0.079 | +0.87 |
| ES | 1D-1h-5m reversal | london | 1 | 0 | 0 | 1 | -1.039 | -1.04 |
| ES | 1D-1h-5m reversal | ny_am | 9 | 3 | 2 | 7 | -0.367 | -3.31 |
| ES | 1D-1h-5m reversal | ny_lunch | 19 | 9 | 4 | 14 | -0.354 | -6.72 |
| ES | 1D-1h-5m reversal | ny_pm | 3 | 1 | 1 | 2 | -0.015 | -0.05 |
| ES | 1D-1h-5m reversal | pre_ny | 12 | 5 | 5 | 7 | +0.232 | +2.79 |
| ES | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.068 | -1.07 |
| ES | 1D-4h-15m continuation | london | 3 | 3 | 2 | 1 | +0.975 | +2.92 |
| ES | 1D-4h-15m continuation | ny_am | 1 | 1 | 1 | 0 | +1.990 | +1.99 |
| ES | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.030 | -1.03 |
| ES | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.997 | +2.00 |
| ES | 1D-4h-15m continuation | pre_ny | 5 | 3 | 2 | 3 | +0.160 | +0.80 |
| ES | 1D-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.007 | -1.01 |
| ES | 1D-4h-15m reversal | ny_am | 5 | 3 | 1 | 4 | -0.430 | -2.15 |
| ES | 1D-4h-15m reversal | ny_lunch | 26 | 9 | 4 | 21 | -0.521 | -13.55 |
| ES | 1D-4h-15m reversal | ny_pm | 18 | 10 | 4 | 10 | +0.119 | +2.14 |
| ES | 1D-4h-15m reversal | pre_ny | 11 | 7 | 6 | 5 | +0.632 | +6.95 |
| ES | 1W-1D-1h continuation | asia | 1 | 0 | 0 | 1 | -1.076 | -1.08 |
| ES | 1W-1D-1h reversal | asia | 12 | 4 | 0 | 6 | -0.349 | -4.19 |
| GC | 1D-1h-5m continuation | asia | 14 | 13 | 9 | 5 | +0.905 | +12.67 |
| GC | 1D-1h-5m continuation | london | 2 | 1 | 1 | 1 | +0.441 | +0.88 |
| GC | 1D-1h-5m continuation | ny_am | 2 | 2 | 1 | 1 | +0.479 | +0.96 |
| GC | 1D-1h-5m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.993 | +1.99 |
| GC | 1D-1h-5m reversal | asia | 42 | 28 | 20 | 22 | +0.419 | +17.62 |
| GC | 1D-1h-5m reversal | london | 14 | 9 | 5 | 9 | +0.060 | +0.84 |
| GC | 1D-1h-5m reversal | ny_am | 4 | 3 | 2 | 2 | +0.479 | +1.92 |
| GC | 1D-1h-5m reversal | ny_lunch | 9 | 1 | 1 | 8 | -0.673 | -6.06 |
| GC | 1D-1h-5m reversal | ny_pm | 2 | 1 | 0 | 2 | -1.008 | -2.02 |
| GC | 1D-1h-5m reversal | pre_ny | 6 | 3 | 3 | 3 | +0.485 | +2.91 |
| GC | 1D-4h-15m continuation | after_hours | 1 | 0 | 0 | 1 | -1.066 | -1.07 |
| GC | 1D-4h-15m continuation | asia | 4 | 1 | 0 | 4 | -1.044 | -4.17 |
| GC | 1D-4h-15m continuation | london | 2 | 1 | 0 | 2 | -1.012 | -2.02 |
| GC | 1D-4h-15m continuation | ny_am | 1 | 0 | 0 | 1 | -1.031 | -1.03 |
| GC | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.999 | +2.00 |
| GC | 1D-4h-15m continuation | pre_ny | 3 | 2 | 1 | 2 | -0.040 | -0.12 |
| GC | 1D-4h-15m reversal | london | 9 | 8 | 4 | 2 | +0.757 | +6.81 |
| GC | 1D-4h-15m reversal | ny_am | 1 | 0 | 0 | 1 | -1.035 | -1.03 |
| GC | 1D-4h-15m reversal | ny_lunch | 17 | 11 | 5 | 9 | +0.093 | +1.58 |
| GC | 1D-4h-15m reversal | ny_pm | 9 | 4 | 1 | 7 | -0.551 | -4.96 |
| GC | 1D-4h-15m reversal | pre_ny | 8 | 5 | 5 | 3 | +0.872 | +6.98 |
| GC | 1W-1D-1h continuation | asia | 1 | 0 | 0 | 1 | -1.014 | -1.01 |
| GC | 1W-1D-1h continuation | london | 1 | 1 | 1 | 0 | +1.985 | +1.98 |
| GC | 1W-1D-1h continuation | ny_am | 1 | 0 | 0 | 1 | -1.016 | -1.02 |
| GC | 1W-1D-1h continuation | pre_ny | 1 | 0 | 0 | 1 | -1.025 | -1.03 |
| GC | 1W-1D-1h reversal | asia | 7 | 1 | 0 | 1 | +0.040 | +0.28 |
| NQ | 1D-1h-5m continuation | asia | 7 | 5 | 3 | 4 | +0.270 | +1.89 |
| NQ | 1D-1h-5m continuation | london | 1 | 0 | 0 | 1 | -1.012 | -1.01 |
| NQ | 1D-1h-5m continuation | ny_am | 2 | 2 | 2 | 0 | +1.995 | +3.99 |
| NQ | 1D-1h-5m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.039 | -1.04 |
| NQ | 1D-1h-5m reversal | asia | 20 | 12 | 8 | 12 | +0.195 | +3.91 |
| NQ | 1D-1h-5m reversal | london | 4 | 4 | 2 | 2 | +0.497 | +1.99 |
| NQ | 1D-1h-5m reversal | ny_am | 9 | 4 | 2 | 7 | -0.349 | -3.14 |
| NQ | 1D-1h-5m reversal | ny_lunch | 26 | 11 | 8 | 17 | -0.024 | -0.63 |
| NQ | 1D-1h-5m reversal | pre_ny | 8 | 5 | 3 | 5 | +0.119 | +0.96 |
| NQ | 1D-4h-15m continuation | after_hours | 1 | 1 | 1 | 0 | +1.974 | +1.97 |
| NQ | 1D-4h-15m continuation | asia | 2 | 1 | 1 | 1 | +0.488 | +0.98 |
| NQ | 1D-4h-15m continuation | london | 6 | 5 | 4 | 2 | +0.987 | +5.92 |
| NQ | 1D-4h-15m continuation | ny_am | 3 | 2 | 2 | 1 | +0.996 | +2.99 |
| NQ | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 0 | 1 | -1.007 | -1.01 |
| NQ | 1D-4h-15m continuation | pre_ny | 2 | 1 | 1 | 1 | +0.488 | +0.98 |
| NQ | 1D-4h-15m reversal | london | 5 | 1 | 1 | 4 | -0.402 | -2.01 |
| NQ | 1D-4h-15m reversal | ny_am | 5 | 4 | 0 | 5 | -1.003 | -5.02 |
| NQ | 1D-4h-15m reversal | ny_lunch | 22 | 11 | 8 | 12 | +0.228 | +5.02 |
| NQ | 1D-4h-15m reversal | ny_pm | 16 | 9 | 5 | 7 | +0.368 | +5.89 |
| NQ | 1D-4h-15m reversal | pre_ny | 5 | 4 | 3 | 2 | +0.798 | +3.99 |
| NQ | 1W-1D-1h reversal | asia | 5 | 1 | 0 | 3 | -0.357 | -1.79 |
| RTY | 1D-1h-5m continuation | asia | 10 | 3 | 2 | 8 | -0.461 | -4.61 |
| RTY | 1D-1h-5m continuation | london | 1 | 1 | 1 | 0 | +1.982 | +1.98 |
| RTY | 1D-1h-5m continuation | ny_am | 1 | 0 | 0 | 1 | -1.011 | -1.01 |
| RTY | 1D-1h-5m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.040 | -1.04 |
| RTY | 1D-1h-5m reversal | asia | 12 | 7 | 5 | 7 | +0.237 | +2.84 |
| RTY | 1D-1h-5m reversal | london | 2 | 1 | 1 | 1 | +0.489 | +0.98 |
| RTY | 1D-1h-5m reversal | ny_am | 14 | 8 | 5 | 9 | +0.053 | +0.75 |
| RTY | 1D-1h-5m reversal | ny_lunch | 53 | 23 | 19 | 32 | +0.109 | +5.76 |
| RTY | 1D-1h-5m reversal | pre_ny | 16 | 8 | 5 | 11 | -0.077 | -1.24 |
| RTY | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.024 | -1.02 |
| RTY | 1D-4h-15m continuation | london | 6 | 5 | 4 | 2 | +0.957 | +5.74 |
| RTY | 1D-4h-15m continuation | ny_am | 1 | 0 | 0 | 1 | -1.015 | -1.01 |
| RTY | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.025 | -1.02 |
| RTY | 1D-4h-15m continuation | pre_ny | 7 | 3 | 3 | 4 | +0.259 | +1.81 |
| RTY | 1D-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.003 | -1.00 |
| RTY | 1D-4h-15m reversal | ny_am | 5 | 4 | 1 | 4 | -0.410 | -2.05 |
| RTY | 1D-4h-15m reversal | ny_lunch | 17 | 9 | 6 | 9 | +0.194 | +3.30 |
| RTY | 1D-4h-15m reversal | ny_pm | 13 | 7 | 4 | 6 | +0.335 | +4.35 |
| RTY | 1D-4h-15m reversal | pre_ny | 5 | 3 | 2 | 3 | +0.194 | +0.97 |
| RTY | 1W-1D-1h reversal | asia | 7 | 2 | 1 | 3 | +0.091 | +0.64 |
| SI | 1D-1h-5m continuation | asia | 14 | 6 | 3 | 11 | -0.411 | -5.75 |
| SI | 1D-1h-5m continuation | london | 1 | 1 | 1 | 0 | +1.999 | +2.00 |
| SI | 1D-1h-5m continuation | ny_am | 1 | 0 | 0 | 1 | -1.023 | -1.02 |
| SI | 1D-1h-5m reversal | asia | 45 | 24 | 16 | 28 | +0.069 | +3.09 |
| SI | 1D-1h-5m reversal | london | 15 | 9 | 7 | 8 | +0.383 | +5.74 |
| SI | 1D-1h-5m reversal | ny_am | 7 | 4 | 1 | 6 | -0.594 | -4.16 |
| SI | 1D-1h-5m reversal | ny_lunch | 9 | 2 | 2 | 7 | -0.347 | -3.13 |
| SI | 1D-1h-5m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.019 | -2.04 |
| SI | 1D-1h-5m reversal | pre_ny | 10 | 3 | 3 | 7 | -0.115 | -1.15 |
| SI | 1D-4h-15m continuation | asia | 6 | 3 | 2 | 4 | -0.047 | -0.28 |
| SI | 1D-4h-15m continuation | london | 2 | 2 | 2 | 0 | +1.997 | +3.99 |
| SI | 1D-4h-15m continuation | ny_am | 2 | 1 | 1 | 1 | +0.475 | +0.95 |
| SI | 1D-4h-15m continuation | ny_pm | 2 | 1 | 1 | 1 | +0.433 | +0.87 |
| SI | 1D-4h-15m continuation | pre_ny | 4 | 4 | 4 | 0 | +1.989 | +7.96 |
| SI | 1D-4h-15m reversal | london | 7 | 4 | 3 | 4 | +0.280 | +1.96 |
| SI | 1D-4h-15m reversal | ny_am | 4 | 3 | 2 | 2 | +0.482 | +1.93 |
| SI | 1D-4h-15m reversal | ny_lunch | 18 | 12 | 5 | 9 | +0.223 | +4.02 |
| SI | 1D-4h-15m reversal | ny_pm | 5 | 1 | 0 | 5 | -1.012 | -5.06 |
| SI | 1D-4h-15m reversal | pre_ny | 11 | 5 | 3 | 7 | -0.040 | -0.45 |
| SI | 1W-1D-1h continuation | london | 1 | 1 | 0 | 1 | -1.028 | -1.03 |
| SI | 1W-1D-1h reversal | asia | 3 | 2 | 1 | 0 | +1.154 | +3.46 |
| YM | 1D-1h-5m continuation | asia | 12 | 6 | 4 | 8 | -0.039 | -0.47 |
| YM | 1D-1h-5m continuation | ny_am | 3 | 2 | 1 | 2 | -0.017 | -0.05 |
| YM | 1D-1h-5m continuation | ny_lunch | 1 | 1 | 0 | 0 | +1.130 | +1.13 |
| YM | 1D-1h-5m continuation | pre_ny | 1 | 1 | 1 | 0 | +1.964 | +1.96 |
| YM | 1D-1h-5m reversal | asia | 10 | 7 | 7 | 3 | +1.093 | +10.93 |
| YM | 1D-1h-5m reversal | london | 1 | 0 | 0 | 1 | -1.012 | -1.01 |
| YM | 1D-1h-5m reversal | ny_am | 19 | 5 | 3 | 16 | -0.552 | -10.48 |
| YM | 1D-1h-5m reversal | ny_lunch | 31 | 12 | 5 | 26 | -0.529 | -16.40 |
| YM | 1D-1h-5m reversal | ny_pm | 2 | 2 | 1 | 1 | +0.496 | +0.99 |
| YM | 1D-1h-5m reversal | pre_ny | 11 | 3 | 1 | 10 | -0.747 | -8.22 |
| YM | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.030 | -1.03 |
| YM | 1D-4h-15m continuation | london | 3 | 2 | 2 | 1 | +0.970 | +2.91 |
| YM | 1D-4h-15m continuation | ny_am | 4 | 2 | 2 | 2 | +0.490 | +1.96 |
| YM | 1D-4h-15m continuation | ny_lunch | 3 | 2 | 2 | 1 | +0.983 | +2.95 |
| YM | 1D-4h-15m continuation | pre_ny | 7 | 5 | 4 | 3 | +0.690 | +4.83 |
| YM | 1D-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.005 | -2.01 |
| YM | 1D-4h-15m reversal | ny_am | 7 | 3 | 1 | 6 | -0.579 | -4.05 |
| YM | 1D-4h-15m reversal | ny_lunch | 25 | 11 | 6 | 15 | -0.035 | -0.87 |
| YM | 1D-4h-15m reversal | ny_pm | 14 | 8 | 4 | 8 | +0.127 | +1.78 |
| YM | 1D-4h-15m reversal | pre_ny | 3 | 0 | 0 | 3 | -1.005 | -3.02 |
| YM | 1W-1D-1h reversal | asia | 7 | 2 | 0 | 0 | +0.166 | +1.16 |
