# Phase B pre-registered tests: results

Checked: all 152 baseline files list a quality check as blocking somewhere (the checks were on).

## T1 limit at the plan entry vs market at the first report (taken signals, R per signal)

| group | n | market | limit | limit - market | t diff | fill rate | R per fill |
|---|---|---|---|---|---|---|---|
| u21 | 382 | -0.142 | -0.151 | -0.009 | -0.321 | +0.919 | -0.164 |
| 2022 | 193 | +0.101 | +0.050 | -0.051 | -1.492 | +0.876 | +0.058 |
| 2023 | 208 | -0.093 | -0.118 | -0.025 | -0.568 | +0.885 | -0.133 |
| 2024 | 1071 | -0.080 | -0.067 | +0.013 | +0.702 | +0.941 | -0.071 |
| 2025 | 969 | -0.003 | +0.018 | +0.021 | +1.139 | +0.935 | +0.020 |
| 2026 | 927 | +0.022 | +0.002 | -0.020 | -1.081 | +0.933 | +0.002 |


Pooled: limit - market -0.001 R per signal, clustered t -0.07, n 3750; years > 0: 2 of 6; symbols > 0: 3 of 8.

Limit itself -0.033 (t -1.37); market -0.033 (t -1.29). Cancel reasons: ran to 2R first 173, expired 92, opened beyond the stop 2


By stack:

| stack | n | market | limit | fill rate |
|---|---|---|---|---|
| 1D / 1h / 5m | 2262 | -0.075 | -0.059 | +0.946 |
| 1D / 4h / 15m | 1008 | +0.042 | -0.002 | +0.866 |
| 1W / 1D / 1h | 119 | +0.054 | +0.082 | +0.975 |
| 1W / 4h / 15m | 361 | +0.000 | +0.005 | +0.981 |


By symbol:

| symbol | n | limit - market |
|---|---|---|
| 6E | 408 | +0.045 |
| CL | 443 | -0.004 |
| ES | 496 | +0.004 |
| GC | 407 | -0.020 |
| NQ | 448 | -0.023 |
| RTY | 534 | -0.012 |
| SI | 493 | -0.011 |
| YM | 521 | +0.019 |


**T1 FAIL**


## T2 exits on U21 (taken, 1D-bias stacks, market entry)

- bias close - 2R: -0.088 R (t -1.01, n 372), symbols > 0: 2 of 8; 2R -0.140, bias close -0.228. **FAIL**

- 3R - 2R: -0.060 R (t -1.10, n 373), symbols > 0: 2 of 8; 2R -0.143, 3R -0.203. **FAIL**


## T3 quality checks: replay with the checks off

| group | kept n | kept | removed n | removed | kept - removed | taken only with checks on |
|---|---|---|---|---|---|---|
| U21 | 382 | -0.142 | 2970 | -0.054 | -0.088 | 0 |
| 2022-2023 | 401 | +0.001 | 4434 | -0.057 | +0.058 | 0 |


**T3 FAIL**


## T4 best-measured setup on U21

+0.060 R (t 0.37, n 73), symbols > 0: 4 of 8. **T4 FAIL**
