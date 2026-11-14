# Phase B backtests: scored against PREREGISTERED.md

## Test 1: weekly / monthly stacks, 35-day horizon (risk_adr >= 0.10, all triggers)

| stack | hypothesis | n | mean | t | years_pos | symbols_pos | by_year | verdict | taken_n | taken_mean |
|---|---|---|---|---|---|---|---|---|---|---|
| 1W / 4h / 15m | H1a net_2r, 35 d | 4390 | -0.031 | -1.337 | 1/5 | 3/8 | 2022: -0.106 / 2023: -0.012 / 2024: +0.038 / 2025: -0.027 / 2026: -0.052 | FAIL | 518 | -0.005 |
| 1W / 4h / 15m | H1b r_bias_close | 4390 | 0.023 | 0.522 | 2/5 | 6/8 | 2022: -0.133 / 2023: -0.040 / 2024: +0.247 / 2025: +0.034 / 2026: -0.000 | FAIL | 518 | 0.244 |
| 1W / 1D / 1h | H1a net_2r, 35 d | 985 | 0.015 | 0.337 | 4/5 | 5/8 | 2022: -0.169 / 2023: +0.023 / 2024: +0.038 / 2025: +0.107 / 2026: +0.092 | FAIL | 103 | 0.090 |
| 1W / 1D / 1h | H1b r_bias_close | 985 | 0.049 | 0.992 | 3/5 | 5/8 | 2022: -0.078 / 2023: +0.019 / 2024: +0.087 / 2025: +0.227 / 2026: -0.022 | FAIL | 103 | -0.041 |
| 1M / 1D / 1h | H1a net_2r, 35 d | 538 | -0.022 | -0.413 | 1/4 | 3/8 | 2023: +0.059 / 2024: -0.093 / 2025: -0.049 / 2026: -0.020 | FAIL | 57 | 0.446 |
| 1M / 1D / 1h | H1b r_bias_close | 538 | -0.079 | -1.079 | 1/4 | 2/8 | 2023: +0.074 / 2024: -0.097 / 2025: -0.268 / 2026: -0.015 | FAIL | 57 | 0.178 |

- 1W / 4h / 15m: n 4390; 2R open at 10 d 9.7%, at 35 d 1.7%; r_bias_close unresolved 0.0% (10 d: 0.0%); mean net_2r 10 d -0.036 vs 35 d -0.031; r_bias_close 10 d +0.023 vs 35 d +0.023
- 1W / 1D / 1h: n 985; 2R open at 10 d 35.2%, at 35 d 9.5%; r_bias_close unresolved 0.0% (10 d: 0.0%); mean net_2r 10 d -0.016 vs 35 d +0.015; r_bias_close 10 d +0.049 vs 35 d +0.049
- 1M / 1D / 1h: n 538; 2R open at 10 d 42.9%, at 35 d 16.2%; r_bias_close unresolved 0.0% (10 d: 0.0%); mean net_2r 10 d -0.078 vs 35 d -0.022; r_bias_close 10 d -0.116 vs 35 d -0.079

## Test 2: limit at the plan entry (1D/1h/5m + 1D/4h/15m)

| population | window_bars | scored | fill_rate | at_open | market_mean | H2a_n | H2a_mean_filled | H2a_t | H2a_years | H2a_symbols | H2a | H2a_by_year | H2b_diff | H2b_t | H2b_years | H2b | H2b_by_year | excluded_gap_or_nodata |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| taken | 3 | yes | 0.872 | 0.703 | -0.039 | 3768 | -0.030 | -1.163 | 3/5 | 2/8 | FAIL | 2022: +0.050 / 2023: -0.128 / 2024: -0.095 / 2025: +0.029 / 2026: +0.021 | 0.013 | 1.326 | 4/5 | FAIL | 2022: -0.003 / 2023: +0.025 / 2024: +0.010 / 2025: +0.028 / 2026: +0.007 | 11 |
| taken | 1 | no | 0.837 | 0.727 | -0.040 | 3620 | -0.019 | -0.711 | 3/5 | 4/8 | FAIL | 2022: +0.049 / 2023: -0.112 / 2024: -0.084 / 2025: +0.044 / 2026: +0.033 | 0.024 | 2.231 | 4/5 | PASS | 2022: -0.005 / 2023: +0.043 / 2024: +0.023 / 2025: +0.039 / 2026: +0.018 | 10 |
| taken | 12 | no | 0.921 | 0.670 | -0.040 | 3978 | -0.034 | -1.352 | 3/5 | 3/8 | FAIL | 2022: +0.058 / 2023: -0.135 / 2024: -0.094 / 2025: +0.021 / 2026: +0.006 | 0.009 | 0.946 | 4/5 | FAIL | 2022: +0.007 / 2023: +0.014 / 2024: +0.005 / 2025: +0.024 / 2026: -0.007 | 12 |
| all triggers | 3 | no | 0.775 | 0.683 | -0.049 | 38268 | -0.062 | -6.824 | 0/5 | 0/8 | FAIL | 2022: -0.077 / 2023: -0.090 / 2024: -0.063 / 2025: -0.023 / 2026: -0.052 | 0.002 | 0.349 | 3/5 | FAIL | 2022: +0.004 / 2023: +0.005 / 2024: -0.006 / 2025: -0.000 / 2026: +0.006 | 60 |
| all triggers | 1 | no | 0.741 | 0.710 | -0.049 | 36622 | -0.060 | -6.537 | 0/5 | 0/8 | FAIL | 2022: -0.079 / 2023: -0.090 / 2024: -0.057 / 2025: -0.019 / 2026: -0.052 | 0.005 | 1.095 | 5/5 | FAIL | 2022: +0.005 / 2023: +0.008 / 2024: +0.001 / 2025: +0.003 / 2026: +0.008 | 57 |
| all triggers | 12 | no | 0.834 | 0.636 | -0.049 | 41189 | -0.066 | -7.468 | 0/5 | 0/8 | FAIL | 2022: -0.081 / 2023: -0.092 / 2024: -0.065 / 2025: -0.028 / 2026: -0.058 | -0.005 | -1.265 | 0/5 | FAIL | 2022: -0.004 / 2023: -0.002 / 2024: -0.012 / 2025: -0.006 / 2026: -0.002 | 63 |

- 1D / 1h / 5m taken, W=3: n 3391, fill rate 89.1%, filled mean -0.039, per signal -0.034 vs market -0.062
- 1D / 4h / 15m taken, W=3: n 931, fill rate 80.1%, filled mean +0.006, per signal +0.005 vs market +0.042
- 1M / 1D / 1h taken (35-day horizon, not scored), W=3: n 63, fill rate 88.9%, filled mean +0.322, per signal +0.286 vs market +0.350
- 1W / 1D / 1h taken (35-day horizon, not scored), W=3: n 110, fill rate 90.0%, filled mean +0.143, per signal +0.129 vs market +0.099
- 1W / 4h / 15m taken (35-day horizon, not scored), W=3: n 620, fill rate 93.5%, filled mean +0.026, per signal +0.025 vs market -0.001

## Test 3: taken vs shadow, 1D/4h/15m, stage c4: **FAIL**

| engine | metric | years | taken_n | taken_mean | shadow_n | shadow_mean | gap | t | excluded_played_out_only |
|---|---|---|---|---|---|---|---|---|---|
| 05209b4 | net_2r | 2024 | 188 | -0.209 | 2566 | 0.025 | -0.234 | -2.310 | 494 |
| 05209b4 | net_2r | 2025 | 189 | 0.282 | 2333 | -0.010 | 0.293 | 2.552 | 494 |
| 05209b4 | net_2r | 2026 | 197 | 0.067 | 2147 | 0.018 | 0.049 | 0.433 | 494 |
| 05209b4 | net_2r | 2024-26 | 574 | 0.048 | 7046 | 0.011 | 0.036 | 0.568 | 494 |
| 05209b4 | net_2r | 2022 (ref) | 176 | 0.149 | 2413 | -0.045 | 0.194 | 1.654 | 494 |
| 05209b4 | net_2r | 2023 (ref) | 181 | -0.081 | 2415 | -0.052 | -0.029 | -0.262 | 494 |
| 05209b4 | net_2r | 2022-23 (ref) | 357 | 0.032 | 4828 | -0.048 | 0.081 | 0.990 | 494 |
| 05209b4 | r_bias_close | 2024 | 188 | -0.019 | 2566 | 0.004 | -0.023 | -0.179 | 494 |
| 05209b4 | r_bias_close | 2025 | 189 | 0.147 | 2333 | 0.003 | 0.144 | 1.100 | 494 |
| 05209b4 | r_bias_close | 2026 | 197 | 0.013 | 2147 | 0.034 | -0.021 | -0.213 | 494 |
| 05209b4 | r_bias_close | 2024-26 | 574 | 0.047 | 7046 | 0.013 | 0.034 | 0.487 | 494 |
| 05209b4 | r_bias_close | 2022 (ref) | 176 | -0.052 | 2413 | -0.014 | -0.038 | -0.298 | 494 |
| 05209b4 | r_bias_close | 2023 (ref) | 181 | -0.192 | 2415 | -0.061 | -0.130 | -1.050 | 494 |
| 05209b4 | r_bias_close | 2022-23 (ref) | 357 | -0.123 | 4828 | -0.038 | -0.085 | -0.953 | 494 |
| a146893 (earlier study files) | net_2r | 2024 | 287 | -0.222 | 2566 | 0.025 | -0.247 | -2.798 | 0 |
| a146893 (earlier study files) | net_2r | 2025 | 283 | 0.233 | 2333 | -0.010 | 0.243 | 2.520 | 0 |
| a146893 (earlier study files) | net_2r | 2026 | 282 | 0.032 | 2147 | 0.018 | 0.013 | 0.127 | 0 |
| a146893 (earlier study files) | net_2r | 2024-26 | 852 | 0.013 | 7046 | 0.011 | 0.002 | 0.028 | 0 |
| a146893 (earlier study files) | net_2r | 2022 (ref) | 290 | 0.189 | 2413 | -0.045 | 0.234 | 2.407 | 0 |
| a146893 (earlier study files) | net_2r | 2023 (ref) | 283 | -0.011 | 2415 | -0.052 | 0.041 | 0.422 | 0 |
| a146893 (earlier study files) | net_2r | 2022-23 (ref) | 573 | 0.090 | 4828 | -0.048 | 0.139 | 2.013 | 0 |

## Test 4: eligibility replay, 1D/4h/15m (0 check-metric cells not run)

| check | metric | affected | added | removed | retimed | mean_d | t | sum_d_by_year | added_mean | base_traded_n | base_traded_mean | per_trade_change | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cont_setup_closure_body_aligned | net_2r | 104 | 104 | 0 | 0 | -0.121 | -0.884 | 2022: +2.1 / 2023: -8.1 / 2024: +2.5 / 2025: +1.5 / 2026: -10.7 | -0.121 | 963 | 0.034 | -0.015 | no measurable effect |
| cont_setup_closure_body_aligned | r_bias_close | 103 | 104 | 0 | 0 | 0.057 | 0.128 | 2022: -4.8 / 2023: -8.6 / 2024: +44.6 / 2025: -10.0 / 2026: -15.4 | 0.057 | 963 | -0.032 | 0.009 | no measurable effect |
| cont_entry_window_open | net_2r | 0 | 0 | 0 | 0 | nan | nan |  | nan | 963 | 0.034 | 0.000 | untestable |
| cont_entry_window_open | r_bias_close | 0 | 0 | 0 | 0 | nan | nan |  | nan | 963 | -0.032 | 0.000 | untestable |
| cont_protected_swing_intact | net_2r | 0 | 0 | 0 | 0 | nan | nan |  | nan | 963 | 0.034 | 0.000 | untestable |
| cont_protected_swing_intact | r_bias_close | 0 | 0 | 0 | 0 | nan | nan |  | nan | 963 | -0.032 | 0.000 | untestable |
| cont_trigger_clear_of_liquidity | net_2r | 80 | 80 | 0 | 0 | 0.206 | 1.182 | 2022: +3.5 / 2023: +4.6 / 2024: +2.0 / 2025: +3.6 / 2026: +2.8 | 0.206 | 963 | 0.034 | 0.013 | no measurable effect |
| cont_trigger_clear_of_liquidity | r_bias_close | 80 | 80 | 0 | 0 | 0.044 | 0.181 | 2022: -1.8 / 2023: +10.3 / 2024: -11.0 / 2025: +0.9 / 2026: +5.1 | 0.044 | 963 | -0.032 | 0.006 | no measurable effect |
| cont_trigger_v_shape | net_2r | 3 | 3 | 0 | 0 | -0.023 | -0.028 | 2022: -1.0 / 2024: +2.0 / 2025: -1.0 | -0.023 | 963 | 0.034 | -0.000 | untestable |
| cont_trigger_v_shape | r_bias_close | 3 | 3 | 0 | 0 | -1.041 | -64.707 | 2022: -1.0 / 2024: -1.1 / 2025: -1.0 | -1.041 | 963 | -0.032 | -0.003 | untestable |
| cont_not_inside_consolidation | net_2r | 6 | 6 | 0 | 0 | 0.434 | 0.689 | 2022: +2.0 / 2023: +2.0 / 2024: -3.3 / 2025: +2.0 | 0.434 | 963 | 0.034 | 0.002 | untestable |
| cont_not_inside_consolidation | r_bias_close | 6 | 6 | 0 | 0 | -1.091 | -50.148 | 2022: -1.0 / 2023: -1.1 / 2024: -3.3 / 2025: -1.1 | -1.091 | 963 | -0.032 | -0.007 | untestable |
| cont_objective_open_at_trigger | net_2r | 801 | 801 | 0 | 0 | -0.041 | -0.803 | 2022: -36.2 / 2023: -19.3 / 2024: +3.5 / 2025: +4.9 / 2026: +14.1 | -0.041 | 963 | 0.034 | -0.034 | no measurable effect |
| cont_objective_open_at_trigger | r_bias_close | 797 | 801 | 0 | 0 | 0.067 | 0.886 | 2022: +22.6 / 2023: -27.5 / 2024: +12.9 / 2025: +27.0 / 2026: +18.8 | 0.067 | 963 | -0.032 | 0.045 | no measurable effect |
| cont_entry_early_in_candle | net_2r | 18 | 18 | 0 | 0 | -0.580 | -2.116 | 2022: -3.4 / 2023: -1.1 / 2024: -4.6 / 2025: -3.4 / 2026: +1.9 | -0.580 | 963 | 0.034 | -0.011 | untestable |
| cont_entry_early_in_candle | r_bias_close | 18 | 18 | 0 | 0 | -0.082 | -0.124 | 2022: -3.7 / 2023: -1.1 / 2024: -4.6 / 2025: -2.7 / 2026: +10.5 | -0.082 | 963 | -0.032 | -0.001 | untestable |
| rev_expansion_into_level | net_2r | 2552 | 2549 | 0 | 3 | -0.004 | -0.148 | 2022: -74.0 / 2023: +10.1 / 2024: +34.2 / 2025: +5.0 / 2026: +13.3 | -0.003 | 963 | 0.034 | -0.028 | no measurable effect |
| rev_expansion_into_level | r_bias_close | 2552 | 2549 | 0 | 3 | 0.012 | 0.378 | 2022: -49.6 / 2023: -19.9 / 2024: +49.5 / 2025: +32.3 / 2026: +19.4 | 0.012 | 963 | -0.032 | 0.032 | no measurable effect |
| rev_opposing_run_small | net_2r | 2248 | 2248 | 0 | 0 | -0.024 | -0.801 | 2022: -4.8 / 2023: +23.5 / 2024: +1.1 / 2025: -26.0 / 2026: -48.5 | -0.024 | 963 | 0.034 | -0.041 | no measurable effect |
| rev_opposing_run_small | r_bias_close | 2248 | 2248 | 0 | 0 | 0.001 | 0.063 | 2022: +21.3 / 2023: +16.2 / 2024: -7.0 / 2025: -11.6 / 2026: -15.9 | 0.001 | 963 | -0.032 | 0.024 | no measurable effect |
| rev_formed_early | net_2r | 0 | 0 | 0 | 0 | nan | nan |  | nan | 963 | 0.034 | 0.000 | untestable |
| rev_formed_early | r_bias_close | 0 | 0 | 0 | 0 | nan | nan |  | nan | 963 | -0.032 | 0.000 | untestable |
| rev_cisd_swift | net_2r | 492 | 492 | 0 | 0 | 0.014 | 0.221 | 2022: +13.7 / 2023: -4.2 / 2024: -11.7 / 2025: +9.9 / 2026: -0.8 | 0.014 | 963 | 0.034 | -0.007 | no measurable effect |
| rev_cisd_swift | r_bias_close | 492 | 492 | 0 | 0 | -0.024 | -0.383 | 2022: -8.6 / 2023: +11.5 / 2024: -7.1 / 2025: -17.5 / 2026: +9.9 | -0.024 | 963 | -0.032 | 0.003 | no measurable effect |
| rev_wick_intact | net_2r | 0 | 0 | 0 | 0 | nan | nan |  | nan | 963 | 0.034 | 0.000 | untestable |
| rev_wick_intact | r_bias_close | 0 | 0 | 0 | 0 | nan | nan |  | nan | 963 | -0.032 | 0.000 | untestable |
