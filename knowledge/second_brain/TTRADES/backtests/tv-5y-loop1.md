---
id: tv-5y-loop1
title: "TTFM backtest tv-5y-loop1: loop turn 11: cont_setup_pick wick_extreme + c4_after_double_expansion skip + stop_size_role quality, 5 years, 8 symbols, stacks 1D/4h/15m and 1W/1D/1h; every taken trigger"
type: backtest-run
model: TTFM
concepts: [reversal, continuation, cisd, candle-2, protected-swing]
run_date: 2026-11-21
from: 2021-11-17
to: 2026-11-11
symbols: ["6E", "CL", "ES", "GC", "NQ", "RTY", "SI", "YM"]
switches: {"variant": "loop1", "stacks": ["1D-4h-15m", "1W-1D-1h"]}
tests: ["TD-008", "TD-009", "TD-011"]
plans: 915
total_r: 86.76
data: ["results/backtest_tv_5y/2021/loop1", "results/backtest_tv_5y/2022/loop1", "results/backtest_tv_5y/2023/loop1", "results/backtest_tv_5y/2024/loop1", "results/backtest_tv_5y/2025/loop1", "results/backtest_tv_5y/2026/loop1"]
---

# TTFM backtest tv-5y-loop1

loop turn 11: cont_setup_pick wick_extreme + c4_after_double_expansion skip + stop_size_role quality, 5 years, 8 symbols, stacks 1D/4h/15m and 1W/1D/1h; every taken trigger

915 taken trades, +86.76 R at the 2R plan over 2021-11-17 to 2026-11-11. The companion's own rules on TradingView bars; cost model included, no slippage. Evidence, not a validated rule.

## Per setup

| Symbol | Stack + path | Session | Trades | 1R wins | 2R wins | Stopped | Avg R | Total R |
|---|---|---|---|---|---|---|---|---|
| 6E | 1D-4h-15m continuation | asia | 4 | 1 | 1 | 3 | -0.321 | -1.28 |
| 6E | 1D-4h-15m continuation | london | 6 | 4 | 1 | 5 | -0.580 | -3.48 |
| 6E | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.051 | -1.05 |
| 6E | 1D-4h-15m continuation | pre_ny | 4 | 1 | 1 | 3 | -0.312 | -1.25 |
| 6E | 1D-4h-15m reversal | london | 3 | 1 | 1 | 2 | -0.013 | -0.04 |
| 6E | 1D-4h-15m reversal | ny_am | 22 | 7 | 5 | 17 | -0.372 | -8.19 |
| 6E | 1D-4h-15m reversal | ny_lunch | 23 | 11 | 10 | 11 | +0.448 | +10.29 |
| 6E | 1D-4h-15m reversal | ny_pm | 8 | 3 | 1 | 7 | -0.642 | -5.13 |
| 6E | 1D-4h-15m reversal | pre_ny | 11 | 9 | 7 | 3 | +1.010 | +11.11 |
| 6E | 1W-1D-1h reversal | asia | 7 | 4 | 1 | 1 | +0.628 | +4.40 |
| CL | 1D-4h-15m continuation | asia | 7 | 3 | 2 | 5 | -0.184 | -1.29 |
| CL | 1D-4h-15m continuation | london | 10 | 4 | 4 | 6 | +0.177 | +1.77 |
| CL | 1D-4h-15m continuation | ny_am | 4 | 2 | 1 | 3 | -0.285 | -1.14 |
| CL | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.995 | +1.99 |
| CL | 1D-4h-15m continuation | pre_ny | 5 | 1 | 1 | 4 | -0.444 | -2.22 |
| CL | 1D-4h-15m reversal | london | 5 | 5 | 3 | 2 | +0.794 | +3.97 |
| CL | 1D-4h-15m reversal | ny_am | 17 | 8 | 8 | 9 | +0.398 | +6.77 |
| CL | 1D-4h-15m reversal | ny_lunch | 19 | 12 | 8 | 6 | +0.685 | +13.01 |
| CL | 1D-4h-15m reversal | ny_pm | 10 | 5 | 4 | 5 | +0.340 | +3.40 |
| CL | 1D-4h-15m reversal | pre_ny | 17 | 10 | 7 | 9 | +0.329 | +5.60 |
| CL | 1W-1D-1h continuation | london | 1 | 1 | 1 | 0 | +1.975 | +1.98 |
| CL | 1W-1D-1h reversal | asia | 16 | 4 | 0 | 5 | -0.104 | -1.66 |
| ES | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.068 | -1.07 |
| ES | 1D-4h-15m continuation | london | 3 | 3 | 2 | 1 | +0.975 | +2.92 |
| ES | 1D-4h-15m continuation | ny_am | 3 | 2 | 2 | 1 | +0.978 | +2.93 |
| ES | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.030 | -1.03 |
| ES | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.997 | +2.00 |
| ES | 1D-4h-15m continuation | pre_ny | 5 | 3 | 2 | 3 | +0.160 | +0.80 |
| ES | 1D-4h-15m reversal | london | 5 | 2 | 1 | 4 | -0.406 | -2.03 |
| ES | 1D-4h-15m reversal | ny_am | 60 | 29 | 17 | 42 | -0.142 | -8.52 |
| ES | 1D-4h-15m reversal | ny_lunch | 29 | 10 | 5 | 23 | -0.468 | -13.59 |
| ES | 1D-4h-15m reversal | ny_pm | 20 | 11 | 5 | 11 | +0.156 | +3.12 |
| ES | 1D-4h-15m reversal | pre_ny | 12 | 7 | 6 | 6 | +0.495 | +5.94 |
| ES | 1W-1D-1h continuation | asia | 1 | 0 | 0 | 1 | -1.076 | -1.08 |
| ES | 1W-1D-1h reversal | asia | 16 | 4 | 0 | 7 | -0.314 | -5.02 |
| GC | 1D-4h-15m continuation | after_hours | 1 | 0 | 0 | 1 | -1.066 | -1.07 |
| GC | 1D-4h-15m continuation | asia | 4 | 1 | 0 | 4 | -1.044 | -4.17 |
| GC | 1D-4h-15m continuation | london | 3 | 1 | 0 | 3 | -1.030 | -3.09 |
| GC | 1D-4h-15m continuation | ny_am | 1 | 0 | 0 | 1 | -1.031 | -1.03 |
| GC | 1D-4h-15m continuation | ny_pm | 1 | 1 | 1 | 0 | +1.999 | +2.00 |
| GC | 1D-4h-15m continuation | pre_ny | 3 | 2 | 1 | 2 | -0.040 | -0.12 |
| GC | 1D-4h-15m reversal | london | 10 | 9 | 5 | 2 | +0.881 | +8.81 |
| GC | 1D-4h-15m reversal | ny_am | 32 | 15 | 9 | 23 | -0.192 | -6.15 |
| GC | 1D-4h-15m reversal | ny_lunch | 17 | 11 | 5 | 9 | +0.093 | +1.58 |
| GC | 1D-4h-15m reversal | ny_pm | 9 | 4 | 1 | 7 | -0.551 | -4.96 |
| GC | 1D-4h-15m reversal | pre_ny | 8 | 5 | 5 | 3 | +0.872 | +6.98 |
| GC | 1W-1D-1h continuation | asia | 4 | 1 | 0 | 4 | -1.034 | -4.14 |
| GC | 1W-1D-1h continuation | london | 1 | 1 | 1 | 0 | +1.985 | +1.98 |
| GC | 1W-1D-1h continuation | ny_am | 1 | 0 | 0 | 1 | -1.016 | -1.02 |
| GC | 1W-1D-1h continuation | pre_ny | 1 | 0 | 0 | 1 | -1.025 | -1.03 |
| GC | 1W-1D-1h reversal | asia | 13 | 2 | 0 | 3 | +0.039 | +0.50 |
| NQ | 1D-4h-15m continuation | after_hours | 1 | 1 | 1 | 0 | +1.974 | +1.97 |
| NQ | 1D-4h-15m continuation | asia | 2 | 1 | 1 | 1 | +0.488 | +0.98 |
| NQ | 1D-4h-15m continuation | london | 7 | 6 | 5 | 2 | +1.129 | +7.90 |
| NQ | 1D-4h-15m continuation | ny_am | 3 | 2 | 2 | 1 | +0.996 | +2.99 |
| NQ | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 0 | 1 | -1.007 | -1.01 |
| NQ | 1D-4h-15m continuation | pre_ny | 2 | 1 | 1 | 1 | +0.488 | +0.98 |
| NQ | 1D-4h-15m reversal | london | 6 | 1 | 1 | 5 | -0.502 | -3.01 |
| NQ | 1D-4h-15m reversal | ny_am | 43 | 24 | 8 | 34 | -0.394 | -16.94 |
| NQ | 1D-4h-15m reversal | ny_lunch | 22 | 11 | 8 | 12 | +0.228 | +5.02 |
| NQ | 1D-4h-15m reversal | ny_pm | 17 | 10 | 5 | 8 | +0.288 | +4.89 |
| NQ | 1D-4h-15m reversal | pre_ny | 6 | 5 | 3 | 3 | +0.497 | +2.98 |
| NQ | 1W-1D-1h continuation | pre_ny | 1 | 1 | 1 | 0 | +1.995 | +2.00 |
| NQ | 1W-1D-1h reversal | asia | 10 | 2 | 1 | 6 | -0.359 | -3.59 |
| RTY | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.024 | -1.02 |
| RTY | 1D-4h-15m continuation | london | 6 | 5 | 4 | 2 | +0.957 | +5.74 |
| RTY | 1D-4h-15m continuation | ny_am | 2 | 1 | 1 | 1 | +0.488 | +0.98 |
| RTY | 1D-4h-15m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.025 | -1.02 |
| RTY | 1D-4h-15m continuation | pre_ny | 9 | 5 | 3 | 6 | -0.034 | -0.31 |
| RTY | 1D-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.003 | -1.00 |
| RTY | 1D-4h-15m reversal | ny_am | 44 | 30 | 22 | 22 | +0.481 | +21.15 |
| RTY | 1D-4h-15m reversal | ny_lunch | 22 | 11 | 8 | 12 | +0.194 | +4.26 |
| RTY | 1D-4h-15m reversal | ny_pm | 15 | 8 | 5 | 7 | +0.356 | +5.34 |
| RTY | 1D-4h-15m reversal | pre_ny | 6 | 3 | 2 | 4 | -0.007 | -0.04 |
| RTY | 1W-1D-1h reversal | asia | 8 | 2 | 1 | 4 | -0.046 | -0.37 |
| SI | 1D-4h-15m continuation | asia | 6 | 3 | 2 | 4 | -0.047 | -0.28 |
| SI | 1D-4h-15m continuation | london | 3 | 2 | 2 | 1 | +0.996 | +2.99 |
| SI | 1D-4h-15m continuation | ny_am | 3 | 1 | 1 | 2 | -0.023 | -0.07 |
| SI | 1D-4h-15m continuation | ny_pm | 2 | 1 | 1 | 1 | +0.433 | +0.87 |
| SI | 1D-4h-15m continuation | pre_ny | 4 | 4 | 4 | 0 | +1.989 | +7.96 |
| SI | 1D-4h-15m reversal | london | 7 | 4 | 3 | 4 | +0.280 | +1.96 |
| SI | 1D-4h-15m reversal | ny_am | 25 | 17 | 12 | 13 | +0.424 | +10.60 |
| SI | 1D-4h-15m reversal | ny_lunch | 19 | 13 | 6 | 9 | +0.317 | +6.02 |
| SI | 1D-4h-15m reversal | ny_pm | 6 | 1 | 0 | 6 | -1.012 | -6.07 |
| SI | 1D-4h-15m reversal | pre_ny | 12 | 5 | 3 | 8 | -0.122 | -1.47 |
| SI | 1W-1D-1h continuation | london | 2 | 2 | 1 | 1 | +0.483 | +0.97 |
| SI | 1W-1D-1h reversal | asia | 7 | 4 | 1 | 0 | +0.782 | +5.48 |
| YM | 1D-4h-15m continuation | asia | 1 | 0 | 0 | 1 | -1.030 | -1.03 |
| YM | 1D-4h-15m continuation | london | 3 | 2 | 2 | 1 | +0.970 | +2.91 |
| YM | 1D-4h-15m continuation | ny_am | 4 | 2 | 2 | 2 | +0.490 | +1.96 |
| YM | 1D-4h-15m continuation | ny_lunch | 3 | 2 | 2 | 1 | +0.983 | +2.95 |
| YM | 1D-4h-15m continuation | pre_ny | 7 | 5 | 4 | 3 | +0.690 | +4.83 |
| YM | 1D-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.005 | -2.01 |
| YM | 1D-4h-15m reversal | ny_am | 38 | 19 | 10 | 27 | -0.204 | -7.76 |
| YM | 1D-4h-15m reversal | ny_lunch | 25 | 11 | 6 | 15 | -0.035 | -0.87 |
| YM | 1D-4h-15m reversal | ny_pm | 17 | 10 | 5 | 10 | +0.103 | +1.75 |
| YM | 1D-4h-15m reversal | pre_ny | 3 | 0 | 0 | 3 | -1.005 | -3.02 |
| YM | 1W-1D-1h continuation | asia | 2 | 2 | 0 | 2 | -1.048 | -2.10 |
| YM | 1W-1D-1h reversal | asia | 11 | 4 | 1 | 1 | +0.300 | +3.30 |
