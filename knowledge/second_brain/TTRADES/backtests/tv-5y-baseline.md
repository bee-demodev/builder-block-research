---
id: tv-5y-baseline
title: "TTFM backtest tv-5y-baseline: 5 years (2021-11-14 to 2026-11-13), the engine's default rules, 8 symbols, stacks 1D/1h/5m, 1D/4h/15m, 1W/1D/1h; every taken trigger (the weekly-R view with one position per book is in backtests/5y-summary.md)"
type: backtest-run
model: TTFM
concepts: [reversal, continuation, cisd, candle-2, protected-swing]
run_date: 2026-11-21
from: 2021-11-15
to: 2026-11-13
symbols: ["6E", "CL", "ES", "GC", "NQ", "RTY", "SI", "YM"]
switches: {"variant": "baseline", "stacks": ["1D-1h-5m", "1D-4h-15m", "1W-1D-1h"]}
tests: []
plans: 4559
total_r: -197.24
data: ["results/backtest_tv_5y/2021/baseline", "results/backtest_tv_5y/2022/baseline", "results/backtest_tv_5y/2023/baseline", "results/backtest_tv_5y/2024/baseline", "results/backtest_tv_5y/2025/baseline", "results/backtest_tv_5y/2026/baseline"]
---

# TTFM backtest tv-5y-baseline

5 years (2021-11-14 to 2026-11-13), the engine's default rules, 8 symbols, stacks 1D/1h/5m, 1D/4h/15m, 1W/1D/1h; every taken trigger (the weekly-R view with one position per book is in backtests/5y-summary.md)

4559 taken trades, -197.24 R at the 2R plan over 2021-11-15 to 2026-11-13. The companion's own rules on TradingView bars; cost model included, no slippage. Evidence, not a validated rule.

## Per setup

| Symbol | Stack + path | Session | Trades | 1R wins | 2R wins | Stopped | Avg R | Total R |
|---|---|---|---|---|---|---|---|---|
| 6E | 1D-1h-5m continuation | after_hours | 1 | 1 | 0 | 1 | -1.082 | -1.08 |
| 6E | 1D-1h-5m continuation | asia | 106 | 48 | 33 | 73 | -0.247 | -26.19 |
| 6E | 1D-1h-5m continuation | london | 48 | 22 | 15 | 33 | -0.185 | -8.86 |
| 6E | 1D-1h-5m continuation | ny_am | 12 | 7 | 4 | 8 | -0.065 | -0.78 |
| 6E | 1D-1h-5m continuation | ny_lunch | 3 | 1 | 0 | 3 | -1.064 | -3.19 |
| 6E | 1D-1h-5m continuation | ny_pm | 2 | 1 | 1 | 1 | +0.449 | +0.90 |
| 6E | 1D-1h-5m continuation | pre_ny | 31 | 13 | 7 | 23 | -0.364 | -11.27 |
| 6E | 1D-1h-5m reversal | asia | 43 | 24 | 15 | 28 | +0.011 | +0.46 |
| 6E | 1D-1h-5m reversal | london | 35 | 22 | 14 | 21 | +0.171 | +5.98 |
| 6E | 1D-1h-5m reversal | ny_am | 29 | 13 | 9 | 20 | -0.144 | -4.19 |
| 6E | 1D-1h-5m reversal | ny_lunch | 18 | 7 | 5 | 13 | -0.209 | -3.77 |
| 6E | 1D-1h-5m reversal | ny_pm | 2 | 1 | 0 | 1 | -0.291 | -0.58 |
| 6E | 1D-1h-5m reversal | pre_ny | 57 | 22 | 18 | 39 | -0.083 | -4.76 |
| 6E | 1D-4h-15m continuation | asia | 7 | 1 | 1 | 6 | -0.654 | -4.58 |
| 6E | 1D-4h-15m continuation | london | 9 | 7 | 3 | 6 | -0.066 | -0.60 |
| 6E | 1D-4h-15m continuation | ny_am | 2 | 1 | 1 | 1 | +0.482 | +0.96 |
| 6E | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.051 | -1.05 |
| 6E | 1D-4h-15m continuation | ny_pm | 2 | 2 | 1 | 1 | +0.483 | +0.97 |
| 6E | 1D-4h-15m continuation | pre_ny | 11 | 4 | 3 | 8 | -0.240 | -2.64 |
| 6E | 1D-4h-15m reversal | london | 3 | 1 | 1 | 2 | -0.013 | -0.04 |
| 6E | 1D-4h-15m reversal | ny_am | 21 | 6 | 4 | 17 | -0.484 | -10.17 |
| 6E | 1D-4h-15m reversal | ny_lunch | 23 | 11 | 10 | 11 | +0.448 | +10.29 |
| 6E | 1D-4h-15m reversal | ny_pm | 9 | 3 | 1 | 8 | -0.683 | -6.15 |
| 6E | 1D-4h-15m reversal | pre_ny | 11 | 9 | 7 | 3 | +1.010 | +11.11 |
| 6E | 1W-1D-1h continuation | asia | 1 | 1 | 1 | 0 | +1.967 | +1.97 |
| 6E | 1W-1D-1h reversal | asia | 7 | 4 | 1 | 1 | +0.628 | +4.40 |
| CL | 1D-1h-5m continuation | after_hours | 2 | 1 | 1 | 1 | +0.458 | +0.92 |
| CL | 1D-1h-5m continuation | asia | 112 | 59 | 42 | 70 | +0.044 | +4.89 |
| CL | 1D-1h-5m continuation | london | 54 | 25 | 18 | 36 | -0.056 | -3.04 |
| CL | 1D-1h-5m continuation | ny_am | 10 | 5 | 5 | 5 | +0.461 | +4.61 |
| CL | 1D-1h-5m continuation | ny_lunch | 5 | 1 | 1 | 4 | -0.459 | -2.29 |
| CL | 1D-1h-5m continuation | pre_ny | 34 | 15 | 12 | 22 | +0.012 | +0.39 |
| CL | 1D-1h-5m reversal | asia | 29 | 13 | 10 | 19 | +0.019 | +0.55 |
| CL | 1D-1h-5m reversal | london | 28 | 14 | 11 | 17 | +0.164 | +4.60 |
| CL | 1D-1h-5m reversal | ny_am | 40 | 19 | 13 | 27 | -0.051 | -2.04 |
| CL | 1D-1h-5m reversal | ny_lunch | 35 | 17 | 9 | 25 | -0.222 | -7.77 |
| CL | 1D-1h-5m reversal | ny_pm | 4 | 0 | 0 | 4 | -1.009 | -4.04 |
| CL | 1D-1h-5m reversal | pre_ny | 67 | 36 | 26 | 41 | +0.151 | +10.10 |
| CL | 1D-4h-15m continuation | asia | 17 | 4 | 2 | 15 | -0.739 | -12.56 |
| CL | 1D-4h-15m continuation | london | 14 | 4 | 4 | 10 | -0.187 | -2.61 |
| CL | 1D-4h-15m continuation | ny_am | 5 | 2 | 1 | 4 | -0.435 | -2.17 |
| CL | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.992 | +1.99 |
| CL | 1D-4h-15m continuation | ny_pm | 2 | 1 | 1 | 1 | +0.489 | +0.98 |
| CL | 1D-4h-15m continuation | pre_ny | 9 | 3 | 2 | 7 | -0.365 | -3.28 |
| CL | 1D-4h-15m reversal | london | 5 | 5 | 3 | 2 | +0.794 | +3.97 |
| CL | 1D-4h-15m reversal | ny_am | 17 | 8 | 8 | 9 | +0.398 | +6.77 |
| CL | 1D-4h-15m reversal | ny_lunch | 19 | 12 | 8 | 6 | +0.685 | +13.01 |
| CL | 1D-4h-15m reversal | ny_pm | 9 | 4 | 4 | 5 | +0.328 | +2.95 |
| CL | 1D-4h-15m reversal | pre_ny | 17 | 10 | 7 | 9 | +0.329 | +5.60 |
| CL | 1W-1D-1h continuation | london | 2 | 1 | 1 | 1 | +0.480 | +0.96 |
| CL | 1W-1D-1h continuation | pre_ny | 1 | 1 | 1 | 0 | +1.995 | +1.99 |
| CL | 1W-1D-1h reversal | asia | 16 | 4 | 0 | 5 | -0.104 | -1.66 |
| ES | 1D-1h-5m continuation | after_hours | 2 | 1 | 0 | 2 | -1.021 | -2.04 |
| ES | 1D-1h-5m continuation | asia | 93 | 40 | 29 | 64 | -0.146 | -13.54 |
| ES | 1D-1h-5m continuation | london | 64 | 27 | 17 | 47 | -0.268 | -17.18 |
| ES | 1D-1h-5m continuation | ny_am | 18 | 11 | 8 | 10 | +0.303 | +5.46 |
| ES | 1D-1h-5m continuation | ny_lunch | 9 | 8 | 5 | 4 | +0.633 | +5.70 |
| ES | 1D-1h-5m continuation | ny_pm | 3 | 1 | 1 | 2 | -0.013 | -0.04 |
| ES | 1D-1h-5m continuation | pre_ny | 42 | 13 | 8 | 34 | -0.489 | -20.53 |
| ES | 1D-1h-5m reversal | asia | 33 | 18 | 11 | 22 | -0.014 | -0.47 |
| ES | 1D-1h-5m reversal | london | 7 | 4 | 2 | 5 | -0.164 | -1.15 |
| ES | 1D-1h-5m reversal | ny_am | 59 | 27 | 16 | 43 | -0.218 | -12.84 |
| ES | 1D-1h-5m reversal | ny_lunch | 67 | 34 | 23 | 43 | +0.025 | +1.68 |
| ES | 1D-1h-5m reversal | ny_pm | 5 | 2 | 1 | 4 | -0.415 | -2.08 |
| ES | 1D-1h-5m reversal | pre_ny | 35 | 14 | 8 | 27 | -0.334 | -11.69 |
| ES | 1D-4h-15m continuation | asia | 6 | 3 | 1 | 5 | -0.544 | -3.26 |
| ES | 1D-4h-15m continuation | london | 6 | 5 | 4 | 2 | +0.979 | +5.87 |
| ES | 1D-4h-15m continuation | ny_am | 4 | 2 | 1 | 3 | -0.278 | -1.11 |
| ES | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.030 | -1.03 |
| ES | 1D-4h-15m continuation | ny_pm | 1 | 0 | 0 | 1 | -1.004 | -1.00 |
| ES | 1D-4h-15m continuation | pre_ny | 17 | 13 | 7 | 10 | +0.206 | +3.49 |
| ES | 1D-4h-15m reversal | london | 5 | 2 | 1 | 4 | -0.406 | -2.03 |
| ES | 1D-4h-15m reversal | ny_am | 58 | 29 | 17 | 40 | -0.110 | -6.38 |
| ES | 1D-4h-15m reversal | ny_lunch | 28 | 10 | 5 | 22 | -0.449 | -12.58 |
| ES | 1D-4h-15m reversal | ny_pm | 19 | 10 | 5 | 10 | +0.217 | +4.13 |
| ES | 1D-4h-15m reversal | pre_ny | 12 | 7 | 6 | 6 | +0.495 | +5.94 |
| ES | 1W-1D-1h continuation | asia | 1 | 0 | 0 | 1 | -1.076 | -1.08 |
| ES | 1W-1D-1h reversal | asia | 16 | 4 | 0 | 7 | -0.314 | -5.02 |
| GC | 1D-1h-5m continuation | asia | 104 | 53 | 36 | 68 | -0.053 | -5.52 |
| GC | 1D-1h-5m continuation | london | 41 | 14 | 11 | 30 | -0.251 | -10.27 |
| GC | 1D-1h-5m continuation | ny_am | 13 | 8 | 4 | 9 | -0.118 | -1.53 |
| GC | 1D-1h-5m continuation | ny_lunch | 5 | 4 | 4 | 1 | +1.377 | +6.89 |
| GC | 1D-1h-5m continuation | pre_ny | 22 | 13 | 9 | 13 | +0.177 | +3.89 |
| GC | 1D-1h-5m reversal | asia | 95 | 60 | 45 | 50 | +0.411 | +39.06 |
| GC | 1D-1h-5m reversal | london | 27 | 17 | 10 | 17 | +0.100 | +2.69 |
| GC | 1D-1h-5m reversal | ny_am | 32 | 15 | 10 | 22 | -0.083 | -2.64 |
| GC | 1D-1h-5m reversal | ny_lunch | 19 | 9 | 8 | 11 | +0.258 | +4.90 |
| GC | 1D-1h-5m reversal | ny_pm | 2 | 1 | 0 | 2 | -1.008 | -2.02 |
| GC | 1D-1h-5m reversal | pre_ny | 22 | 10 | 7 | 15 | -0.060 | -1.31 |
| GC | 1D-4h-15m continuation | after_hours | 1 | 0 | 0 | 1 | -1.066 | -1.07 |
| GC | 1D-4h-15m continuation | asia | 8 | 1 | 0 | 8 | -1.032 | -8.25 |
| GC | 1D-4h-15m continuation | london | 7 | 2 | 0 | 7 | -1.026 | -7.18 |
| GC | 1D-4h-15m continuation | ny_am | 1 | 0 | 0 | 1 | -1.031 | -1.03 |
| GC | 1D-4h-15m continuation | ny_lunch | 2 | 1 | 1 | 1 | +0.484 | +0.97 |
| GC | 1D-4h-15m continuation | ny_pm | 1 | 0 | 0 | 1 | -1.010 | -1.01 |
| GC | 1D-4h-15m continuation | pre_ny | 12 | 6 | 4 | 8 | -0.029 | -0.35 |
| GC | 1D-4h-15m reversal | london | 10 | 9 | 5 | 2 | +0.881 | +8.81 |
| GC | 1D-4h-15m reversal | ny_am | 31 | 15 | 9 | 22 | -0.165 | -5.13 |
| GC | 1D-4h-15m reversal | ny_lunch | 17 | 11 | 5 | 9 | +0.093 | +1.58 |
| GC | 1D-4h-15m reversal | ny_pm | 9 | 4 | 1 | 7 | -0.551 | -4.96 |
| GC | 1D-4h-15m reversal | pre_ny | 8 | 5 | 5 | 3 | +0.872 | +6.98 |
| GC | 1W-1D-1h continuation | asia | 4 | 1 | 0 | 4 | -1.034 | -4.14 |
| GC | 1W-1D-1h continuation | london | 1 | 1 | 1 | 0 | +1.985 | +1.98 |
| GC | 1W-1D-1h continuation | ny_am | 1 | 0 | 0 | 1 | -1.016 | -1.02 |
| GC | 1W-1D-1h continuation | pre_ny | 1 | 0 | 0 | 1 | -1.025 | -1.03 |
| GC | 1W-1D-1h reversal | asia | 13 | 2 | 0 | 3 | +0.039 | +0.50 |
| NQ | 1D-1h-5m continuation | asia | 102 | 47 | 29 | 73 | -0.184 | -18.78 |
| NQ | 1D-1h-5m continuation | london | 46 | 23 | 17 | 29 | +0.088 | +4.05 |
| NQ | 1D-1h-5m continuation | ny_am | 21 | 12 | 10 | 11 | +0.413 | +8.67 |
| NQ | 1D-1h-5m continuation | ny_lunch | 8 | 4 | 4 | 4 | +0.491 | +3.93 |
| NQ | 1D-1h-5m continuation | ny_pm | 2 | 2 | 1 | 1 | +0.496 | +0.99 |
| NQ | 1D-1h-5m continuation | pre_ny | 53 | 31 | 20 | 33 | +0.106 | +5.62 |
| NQ | 1D-1h-5m reversal | asia | 51 | 30 | 20 | 31 | +0.172 | +8.79 |
| NQ | 1D-1h-5m reversal | london | 13 | 8 | 5 | 8 | +0.150 | +1.95 |
| NQ | 1D-1h-5m reversal | ny_am | 48 | 20 | 10 | 38 | -0.386 | -18.53 |
| NQ | 1D-1h-5m reversal | ny_lunch | 66 | 30 | 21 | 43 | -0.017 | -1.15 |
| NQ | 1D-1h-5m reversal | pre_ny | 34 | 21 | 13 | 21 | +0.142 | +4.83 |
| NQ | 1D-4h-15m continuation | after_hours | 1 | 1 | 1 | 0 | +1.974 | +1.97 |
| NQ | 1D-4h-15m continuation | asia | 3 | 2 | 2 | 1 | +0.985 | +2.96 |
| NQ | 1D-4h-15m continuation | london | 9 | 7 | 5 | 4 | +0.653 | +5.88 |
| NQ | 1D-4h-15m continuation | ny_am | 5 | 2 | 2 | 3 | +0.197 | +0.98 |
| NQ | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 0 | 1 | -1.007 | -1.01 |
| NQ | 1D-4h-15m continuation | ny_pm | 2 | 0 | 0 | 2 | -1.006 | -2.01 |
| NQ | 1D-4h-15m continuation | pre_ny | 12 | 4 | 3 | 9 | -0.261 | -3.13 |
| NQ | 1D-4h-15m reversal | london | 6 | 1 | 1 | 5 | -0.502 | -3.01 |
| NQ | 1D-4h-15m reversal | ny_am | 43 | 24 | 8 | 34 | -0.394 | -16.94 |
| NQ | 1D-4h-15m reversal | ny_lunch | 22 | 11 | 8 | 12 | +0.228 | +5.02 |
| NQ | 1D-4h-15m reversal | ny_pm | 16 | 9 | 4 | 8 | +0.181 | +2.89 |
| NQ | 1D-4h-15m reversal | pre_ny | 6 | 5 | 3 | 3 | +0.497 | +2.98 |
| NQ | 1W-1D-1h continuation | pre_ny | 1 | 1 | 1 | 0 | +1.995 | +2.00 |
| NQ | 1W-1D-1h reversal | asia | 10 | 2 | 1 | 6 | -0.359 | -3.59 |
| RTY | 1D-1h-5m continuation | after_hours | 2 | 2 | 2 | 0 | +1.933 | +3.87 |
| RTY | 1D-1h-5m continuation | asia | 120 | 52 | 30 | 89 | -0.365 | -43.40 |
| RTY | 1D-1h-5m continuation | london | 72 | 37 | 26 | 46 | +0.015 | +1.07 |
| RTY | 1D-1h-5m continuation | ny_am | 23 | 7 | 5 | 18 | -0.377 | -8.68 |
| RTY | 1D-1h-5m continuation | ny_lunch | 10 | 3 | 3 | 7 | -0.131 | -1.31 |
| RTY | 1D-1h-5m continuation | pre_ny | 60 | 35 | 24 | 36 | +0.143 | +8.58 |
| RTY | 1D-1h-5m reversal | after_hours | 1 | 0 | 0 | 1 | -1.008 | -1.01 |
| RTY | 1D-1h-5m reversal | asia | 33 | 15 | 10 | 23 | -0.105 | -3.45 |
| RTY | 1D-1h-5m reversal | london | 9 | 6 | 5 | 4 | +0.649 | +5.84 |
| RTY | 1D-1h-5m reversal | ny_am | 61 | 29 | 19 | 40 | -0.043 | -2.61 |
| RTY | 1D-1h-5m reversal | ny_lunch | 94 | 41 | 32 | 58 | +0.072 | +6.75 |
| RTY | 1D-1h-5m reversal | pre_ny | 41 | 24 | 11 | 30 | -0.212 | -8.70 |
| RTY | 1D-4h-15m continuation | asia | 4 | 1 | 1 | 3 | -0.304 | -1.21 |
| RTY | 1D-4h-15m continuation | london | 12 | 7 | 6 | 6 | +0.449 | +5.39 |
| RTY | 1D-4h-15m continuation | ny_am | 5 | 3 | 3 | 2 | +0.788 | +3.94 |
| RTY | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.025 | -1.02 |
| RTY | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| RTY | 1D-4h-15m continuation | pre_ny | 15 | 7 | 5 | 10 | -0.035 | -0.52 |
| RTY | 1D-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.003 | -1.00 |
| RTY | 1D-4h-15m reversal | ny_am | 43 | 29 | 21 | 22 | +0.446 | +19.17 |
| RTY | 1D-4h-15m reversal | ny_lunch | 22 | 11 | 8 | 12 | +0.194 | +4.26 |
| RTY | 1D-4h-15m reversal | ny_pm | 14 | 8 | 5 | 6 | +0.453 | +6.35 |
| RTY | 1D-4h-15m reversal | pre_ny | 6 | 3 | 2 | 4 | -0.007 | -0.04 |
| RTY | 1W-1D-1h reversal | asia | 8 | 2 | 1 | 4 | -0.046 | -0.37 |
| SI | 1D-1h-5m continuation | after_hours | 4 | 2 | 2 | 2 | +0.447 | +1.79 |
| SI | 1D-1h-5m continuation | asia | 117 | 59 | 39 | 78 | -0.076 | -8.92 |
| SI | 1D-1h-5m continuation | london | 29 | 12 | 7 | 22 | -0.349 | -10.11 |
| SI | 1D-1h-5m continuation | ny_am | 14 | 8 | 7 | 7 | +0.468 | +6.55 |
| SI | 1D-1h-5m continuation | ny_lunch | 5 | 1 | 1 | 4 | -0.478 | -2.39 |
| SI | 1D-1h-5m continuation | ny_pm | 6 | 2 | 1 | 5 | -0.651 | -3.90 |
| SI | 1D-1h-5m continuation | pre_ny | 33 | 14 | 8 | 25 | -0.341 | -11.25 |
| SI | 1D-1h-5m reversal | asia | 106 | 56 | 38 | 67 | +0.066 | +7.01 |
| SI | 1D-1h-5m reversal | london | 42 | 24 | 16 | 26 | +0.123 | +5.15 |
| SI | 1D-1h-5m reversal | ny_am | 26 | 11 | 6 | 20 | -0.335 | -8.71 |
| SI | 1D-1h-5m reversal | ny_lunch | 24 | 11 | 8 | 16 | -0.013 | -0.30 |
| SI | 1D-1h-5m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.019 | -2.04 |
| SI | 1D-1h-5m reversal | pre_ny | 23 | 5 | 5 | 18 | -0.370 | -8.50 |
| SI | 1D-4h-15m continuation | asia | 11 | 6 | 4 | 7 | +0.058 | +0.64 |
| SI | 1D-4h-15m continuation | london | 7 | 3 | 3 | 4 | +0.237 | +1.66 |
| SI | 1D-4h-15m continuation | ny_am | 8 | 5 | 5 | 3 | +0.858 | +6.87 |
| SI | 1D-4h-15m continuation | ny_pm | 5 | 3 | 2 | 3 | +0.165 | +0.83 |
| SI | 1D-4h-15m continuation | pre_ny | 9 | 5 | 4 | 5 | +0.298 | +2.69 |
| SI | 1D-4h-15m reversal | london | 7 | 4 | 3 | 4 | +0.280 | +1.96 |
| SI | 1D-4h-15m reversal | ny_am | 24 | 17 | 12 | 12 | +0.484 | +11.60 |
| SI | 1D-4h-15m reversal | ny_lunch | 19 | 13 | 6 | 9 | +0.317 | +6.02 |
| SI | 1D-4h-15m reversal | ny_pm | 6 | 1 | 0 | 6 | -1.012 | -6.07 |
| SI | 1D-4h-15m reversal | pre_ny | 12 | 5 | 3 | 8 | -0.122 | -1.47 |
| SI | 1W-1D-1h continuation | asia | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| SI | 1W-1D-1h continuation | london | 3 | 3 | 1 | 2 | -0.022 | -0.07 |
| SI | 1W-1D-1h continuation | ny_am | 1 | 1 | 1 | 0 | +1.998 | +2.00 |
| SI | 1W-1D-1h reversal | asia | 7 | 4 | 1 | 0 | +0.782 | +5.48 |
| YM | 1D-1h-5m continuation | after_hours | 2 | 1 | 0 | 2 | -1.049 | -2.10 |
| YM | 1D-1h-5m continuation | asia | 112 | 51 | 31 | 81 | -0.252 | -28.24 |
| YM | 1D-1h-5m continuation | london | 55 | 26 | 19 | 36 | -0.017 | -0.92 |
| YM | 1D-1h-5m continuation | ny_am | 21 | 11 | 8 | 13 | +0.111 | +2.33 |
| YM | 1D-1h-5m continuation | ny_lunch | 12 | 4 | 2 | 9 | -0.354 | -4.24 |
| YM | 1D-1h-5m continuation | ny_pm | 5 | 2 | 2 | 3 | +0.163 | +0.82 |
| YM | 1D-1h-5m continuation | pre_ny | 58 | 26 | 19 | 39 | -0.074 | -4.31 |
| YM | 1D-1h-5m reversal | after_hours | 1 | 1 | 0 | 0 | +0.917 | +0.92 |
| YM | 1D-1h-5m reversal | asia | 29 | 17 | 16 | 13 | +0.644 | +18.67 |
| YM | 1D-1h-5m reversal | london | 8 | 4 | 2 | 6 | -0.263 | -2.10 |
| YM | 1D-1h-5m reversal | ny_am | 58 | 24 | 15 | 42 | -0.235 | -13.64 |
| YM | 1D-1h-5m reversal | ny_lunch | 75 | 26 | 13 | 62 | -0.492 | -36.94 |
| YM | 1D-1h-5m reversal | ny_pm | 2 | 2 | 1 | 1 | +0.496 | +0.99 |
| YM | 1D-1h-5m reversal | pre_ny | 35 | 16 | 7 | 28 | -0.416 | -14.57 |
| YM | 1D-4h-15m continuation | asia | 2 | 1 | 0 | 2 | -1.056 | -2.11 |
| YM | 1D-4h-15m continuation | london | 9 | 5 | 3 | 6 | -0.049 | -0.44 |
| YM | 1D-4h-15m continuation | ny_am | 4 | 2 | 2 | 2 | +0.490 | +1.96 |
| YM | 1D-4h-15m continuation | ny_lunch | 3 | 2 | 2 | 1 | +0.983 | +2.95 |
| YM | 1D-4h-15m continuation | ny_pm | 2 | 0 | 0 | 2 | -1.014 | -2.03 |
| YM | 1D-4h-15m continuation | pre_ny | 7 | 4 | 3 | 4 | +0.257 | +1.80 |
| YM | 1D-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.005 | -2.01 |
| YM | 1D-4h-15m reversal | ny_am | 38 | 19 | 10 | 27 | -0.202 | -7.68 |
| YM | 1D-4h-15m reversal | ny_lunch | 25 | 11 | 6 | 15 | -0.035 | -0.87 |
| YM | 1D-4h-15m reversal | ny_pm | 17 | 10 | 5 | 10 | +0.103 | +1.75 |
| YM | 1D-4h-15m reversal | pre_ny | 3 | 0 | 0 | 3 | -1.005 | -3.02 |
| YM | 1W-1D-1h continuation | asia | 3 | 2 | 0 | 3 | -1.053 | -3.16 |
| YM | 1W-1D-1h continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.980 | +1.98 |
| YM | 1W-1D-1h continuation | pre_ny | 1 | 0 | 0 | 1 | -1.040 | -1.04 |
| YM | 1W-1D-1h reversal | asia | 11 | 4 | 1 | 1 | +0.300 | +3.30 |
