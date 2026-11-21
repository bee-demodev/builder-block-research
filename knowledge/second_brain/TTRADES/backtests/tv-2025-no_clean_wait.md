---
id: tv-2025-no_clean_wait
title: "TTFM backtest tv-2025-no_clean_wait: 2025, variant no_clean_wait"
type: backtest-run
model: TTFM
concepts: [reversal, continuation, cisd, candle-2, protected-swing]
run_date: 2026-11-20
from: 2025-01-07
to: 2025-12-30
symbols: ["ES", "GC", "NQ", "RTY", "YM"]
switches: {"variant": "no_clean_wait", "stacks": ["1D-1h-5m", "1D-4h-15m", "1W-4h-15m"]}
tests: []
plans: 677
total_r: 9.56
data: results/backtest_tv/2025/no_clean_wait
---

# TTFM backtest tv-2025-no_clean_wait

2025, variant no_clean_wait

677 taken trades, +9.56 R at the 2R plan over 2025-01-07 to 2025-12-30. The companion's own rules on TradingView bars; cost model included, no slippage. Evidence, not a validated rule.

## Per setup

| Symbol | Stack + path | Session | Trades | 1R wins | 2R wins | Stopped | Avg R | Total R |
|---|---|---|---|---|---|---|---|---|
| ES | 1D-1h-5m continuation | asia | 8 | 5 | 3 | 5 | +0.083 | +0.66 |
| ES | 1D-1h-5m continuation | london | 10 | 7 | 4 | 6 | +0.153 | +1.53 |
| ES | 1D-1h-5m continuation | ny_am | 1 | 1 | 1 | 0 | +1.990 | +1.99 |
| ES | 1D-1h-5m continuation | pre_ny | 4 | 1 | 0 | 4 | -1.062 | -4.25 |
| ES | 1D-1h-5m reversal | asia | 8 | 2 | 0 | 8 | -1.015 | -8.12 |
| ES | 1D-1h-5m reversal | ny_am | 32 | 16 | 6 | 25 | -0.413 | -13.21 |
| ES | 1D-1h-5m reversal | ny_lunch | 17 | 9 | 6 | 11 | +0.047 | +0.80 |
| ES | 1D-1h-5m reversal | ny_pm | 2 | 1 | 1 | 1 | +0.491 | +0.98 |
| ES | 1D-1h-5m reversal | pre_ny | 6 | 3 | 2 | 4 | -0.015 | -0.09 |
| ES | 1D-4h-15m continuation | london | 1 | 1 | 1 | 0 | +1.993 | +1.99 |
| ES | 1D-4h-15m continuation | pre_ny | 1 | 1 | 1 | 0 | +1.992 | +1.99 |
| ES | 1D-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.006 | -2.01 |
| ES | 1D-4h-15m reversal | ny_am | 26 | 16 | 11 | 14 | +0.322 | +8.37 |
| ES | 1D-4h-15m reversal | ny_lunch | 3 | 2 | 0 | 3 | -1.005 | -3.02 |
| ES | 1D-4h-15m reversal | ny_pm | 3 | 2 | 2 | 1 | +0.995 | +2.98 |
| ES | 1D-4h-15m reversal | pre_ny | 1 | 1 | 1 | 0 | +1.996 | +2.00 |
| ES | 1W-4h-15m reversal | asia | 2 | 2 | 0 | 2 | -1.006 | -2.01 |
| ES | 1W-4h-15m reversal | london | 3 | 0 | 0 | 3 | -1.007 | -3.02 |
| ES | 1W-4h-15m reversal | ny_am | 1 | 1 | 0 | 0 | +1.284 | +1.28 |
| ES | 1W-4h-15m reversal | ny_pm | 3 | 1 | 1 | 2 | -0.005 | -0.01 |
| GC | 1D-1h-5m continuation | asia | 11 | 9 | 6 | 5 | +0.624 | +6.87 |
| GC | 1D-1h-5m continuation | london | 3 | 1 | 1 | 2 | -0.016 | -0.05 |
| GC | 1D-1h-5m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.081 | -1.08 |
| GC | 1D-1h-5m reversal | asia | 20 | 12 | 8 | 12 | +0.193 | +3.86 |
| GC | 1D-1h-5m reversal | london | 2 | 1 | 1 | 1 | +0.495 | +0.99 |
| GC | 1D-1h-5m reversal | ny_am | 15 | 8 | 5 | 9 | +0.076 | +1.14 |
| GC | 1D-1h-5m reversal | ny_lunch | 5 | 2 | 1 | 4 | -0.407 | -2.04 |
| GC | 1D-1h-5m reversal | pre_ny | 2 | 1 | 1 | 1 | +0.496 | +0.99 |
| GC | 1D-4h-15m continuation | asia | 2 | 0 | 0 | 2 | -1.027 | -2.05 |
| GC | 1D-4h-15m continuation | london | 3 | 1 | 0 | 3 | -1.010 | -3.03 |
| GC | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.991 | +1.99 |
| GC | 1D-4h-15m continuation | ny_pm | 1 | 0 | 0 | 1 | -1.010 | -1.01 |
| GC | 1D-4h-15m continuation | pre_ny | 3 | 2 | 1 | 2 | -0.020 | -0.06 |
| GC | 1D-4h-15m reversal | london | 2 | 2 | 2 | 0 | +1.998 | +4.00 |
| GC | 1D-4h-15m reversal | ny_am | 14 | 8 | 7 | 7 | +0.492 | +6.88 |
| GC | 1D-4h-15m reversal | ny_lunch | 2 | 2 | 1 | 1 | +0.498 | +1.00 |
| GC | 1D-4h-15m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.006 | -2.01 |
| GC | 1D-4h-15m reversal | pre_ny | 1 | 1 | 1 | 0 | +1.998 | +2.00 |
| GC | 1W-4h-15m reversal | london | 2 | 2 | 1 | 0 | +1.301 | +2.60 |
| GC | 1W-4h-15m reversal | ny_am | 1 | 0 | 0 | 1 | -1.006 | -1.01 |
| NQ | 1D-1h-5m continuation | asia | 9 | 3 | 3 | 6 | -0.014 | -0.13 |
| NQ | 1D-1h-5m continuation | london | 4 | 2 | 2 | 2 | +0.491 | +1.96 |
| NQ | 1D-1h-5m continuation | ny_am | 2 | 1 | 0 | 2 | -1.012 | -2.02 |
| NQ | 1D-1h-5m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.997 | +2.00 |
| NQ | 1D-1h-5m continuation | pre_ny | 2 | 2 | 2 | 0 | +1.994 | +3.99 |
| NQ | 1D-1h-5m reversal | asia | 12 | 6 | 3 | 9 | -0.254 | -3.05 |
| NQ | 1D-1h-5m reversal | ny_am | 32 | 12 | 6 | 25 | -0.390 | -12.47 |
| NQ | 1D-1h-5m reversal | ny_lunch | 18 | 8 | 6 | 12 | -0.004 | -0.07 |
| NQ | 1D-1h-5m reversal | pre_ny | 5 | 1 | 0 | 5 | -1.006 | -5.03 |
| NQ | 1D-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| NQ | 1D-4h-15m reversal | ny_am | 25 | 15 | 9 | 15 | +0.166 | +4.15 |
| NQ | 1D-4h-15m reversal | ny_lunch | 6 | 3 | 1 | 4 | -0.120 | -0.72 |
| NQ | 1D-4h-15m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.002 | -2.00 |
| NQ | 1W-4h-15m reversal | asia | 2 | 1 | 1 | 1 | +0.498 | +1.00 |
| NQ | 1W-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.002 | -1.00 |
| NQ | 1W-4h-15m reversal | ny_am | 2 | 2 | 1 | 0 | +1.720 | +3.44 |
| NQ | 1W-4h-15m reversal | ny_pm | 2 | 0 | 0 | 2 | -1.002 | -2.00 |
| RTY | 1D-1h-5m continuation | asia | 15 | 6 | 2 | 13 | -0.679 | -10.18 |
| RTY | 1D-1h-5m continuation | london | 4 | 3 | 3 | 1 | +1.226 | +4.90 |
| RTY | 1D-1h-5m continuation | ny_am | 5 | 2 | 2 | 3 | +0.166 | +0.83 |
| RTY | 1D-1h-5m continuation | ny_lunch | 1 | 0 | 0 | 1 | -1.037 | -1.04 |
| RTY | 1D-1h-5m continuation | pre_ny | 9 | 7 | 4 | 5 | +0.292 | +2.63 |
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
| RTY | 1W-4h-15m continuation | asia | 1 | 1 | 0 | 1 | -1.037 | -1.04 |
| RTY | 1W-4h-15m continuation | london | 2 | 1 | 1 | 1 | +0.471 | +0.94 |
| RTY | 1W-4h-15m continuation | ny_am | 3 | 1 | 1 | 2 | -0.014 | -0.04 |
| RTY | 1W-4h-15m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.036 | -1.04 |
| RTY | 1W-4h-15m reversal | asia | 2 | 0 | 0 | 2 | -1.007 | -2.01 |
| RTY | 1W-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.006 | -2.01 |
| RTY | 1W-4h-15m reversal | ny_pm | 2 | 1 | 0 | 2 | -1.011 | -2.02 |
| YM | 1D-1h-5m continuation | after_hours | 1 | 1 | 0 | 1 | -1.079 | -1.08 |
| YM | 1D-1h-5m continuation | asia | 11 | 4 | 3 | 8 | -0.246 | -2.70 |
| YM | 1D-1h-5m continuation | london | 8 | 3 | 2 | 6 | -0.301 | -2.41 |
| YM | 1D-1h-5m continuation | ny_am | 2 | 0 | 0 | 2 | -1.024 | -2.05 |
| YM | 1D-1h-5m continuation | ny_lunch | 2 | 1 | 0 | 2 | -1.030 | -2.06 |
| YM | 1D-1h-5m continuation | pre_ny | 8 | 5 | 3 | 5 | +0.085 | +0.68 |
| YM | 1D-1h-5m reversal | after_hours | 1 | 1 | 0 | 0 | +0.917 | +0.92 |
| YM | 1D-1h-5m reversal | asia | 7 | 5 | 4 | 3 | +0.706 | +4.94 |
| YM | 1D-1h-5m reversal | london | 3 | 2 | 2 | 1 | +0.991 | +2.97 |
| YM | 1D-1h-5m reversal | ny_am | 38 | 22 | 18 | 18 | +0.478 | +18.18 |
| YM | 1D-1h-5m reversal | ny_lunch | 11 | 3 | 1 | 10 | -0.734 | -8.07 |
| YM | 1D-1h-5m reversal | pre_ny | 5 | 4 | 2 | 3 | +0.189 | +0.94 |
| YM | 1D-4h-15m continuation | london | 3 | 2 | 1 | 2 | -0.064 | -0.19 |
| YM | 1D-4h-15m continuation | ny_lunch | 1 | 1 | 1 | 0 | +1.982 | +1.98 |
| YM | 1D-4h-15m continuation | ny_pm | 1 | 1 | 0 | 1 | -1.004 | -1.00 |
| YM | 1D-4h-15m continuation | pre_ny | 1 | 0 | 0 | 1 | -1.041 | -1.04 |
| YM | 1D-4h-15m reversal | london | 2 | 1 | 0 | 2 | -1.005 | -2.01 |
| YM | 1D-4h-15m reversal | ny_am | 27 | 11 | 10 | 16 | +0.133 | +3.58 |
| YM | 1D-4h-15m reversal | ny_lunch | 7 | 6 | 3 | 1 | +1.058 | +7.41 |
| YM | 1D-4h-15m reversal | ny_pm | 4 | 2 | 0 | 3 | -0.470 | -1.88 |
| YM | 1W-4h-15m continuation | asia | 2 | 2 | 1 | 1 | +0.493 | +0.99 |
| YM | 1W-4h-15m continuation | london | 1 | 1 | 0 | 1 | -1.083 | -1.08 |
| YM | 1W-4h-15m continuation | ny_am | 2 | 1 | 0 | 2 | -1.011 | -2.02 |
| YM | 1W-4h-15m continuation | ny_pm | 3 | 0 | 0 | 3 | -1.009 | -3.03 |
| YM | 1W-4h-15m continuation | pre_ny | 3 | 2 | 2 | 1 | +0.972 | +2.92 |
| YM | 1W-4h-15m reversal | asia | 2 | 2 | 1 | 1 | +0.496 | +0.99 |
| YM | 1W-4h-15m reversal | london | 1 | 0 | 0 | 1 | -1.007 | -1.01 |
| YM | 1W-4h-15m reversal | ny_am | 3 | 2 | 1 | 1 | +0.699 | +2.10 |
| YM | 1W-4h-15m reversal | ny_pm | 3 | 2 | 0 | 2 | -0.718 | -2.15 |
| YM | 1W-4h-15m reversal | pre_ny | 2 | 1 | 0 | 1 | -0.445 | -0.89 |
