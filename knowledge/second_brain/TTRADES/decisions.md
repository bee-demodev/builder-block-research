---
title: "TTRADES: Vik's decisions"
type: ttrades-decisions
created: 2026-11-20
last_updated: 2026-11-20
---

# Vik's decisions (TTrades)

Vik's answers where the teacher's videos disagree, leave a number undefined, or the companion needs
one exact rule. Kept apart from the teacher's words. Ids are `TD-nnn` (TCM uses `D-nnn`), so the two
brains never collide. Cite the id in a comment beside the rule in code:
`# TD-001: a C2 closure needs a body close back inside the range (Vik, 2026-11-21)`.

`settles` lists conflict ids from [[conflicts]]; the lookup then shows those conflicts as DECIDED.

Rows marked **proposed (backtest evidence)** are not decisions: they come from the 5-year
walk-forward ([[evidence]], [[loop-log]], `backtests/5y-summary.md`) and wait for Vik. Their switch
exists with the old behaviour as default; `Settles` stays empty until he decides.

| Id | Date | Question | Choice | Reason | Settles | Code |
|---|---|---|---|---|---|---|
| TD-001 | 2026-11-21 | Continuation entry: the CISD or the next continuation after it? (CISD-19, ENT-1: "we're not going to enter on that change in the state of delivery. We're going to wait for another continuation", the_only_trading_strategy_you_need_for_2026 02:46) | proposed (backtest evidence): keep `entry_mode_continuation` = either | `next_continuation` gains on train (+0.09 R/wk, t 0.77) but loses in 2025 (-0.24) and 2026 (-0.02); continuation order-block triggers lose in every period (-0.27 / -0.19 / -0.12 R a trade) | none (proposed) | companion/tools/backtest.py VARIANTS next_continuation |
| TD-002 | 2026-11-21 | Is a setup close through EQ a kill or a soft invalidation? (BIAS-1, RNG-3: "soft invalidation ... I'm just adjusting my targets", livestream_20260819 1:33:56) | proposed (backtest evidence): keep `eq_respect_role` = gate | `eq_soft` is worse on train (-0.08 R/wk, t -1.53) | none (proposed) | companion/styles/ttrades/continuation.py roles |
| TD-003 | 2026-11-21 | Should the daily profile (open, low first, then higher) veto a continuation? (BIAS-9, PROF-1: "I can't trade long when my daily profile looks like this", livestream_20261006 26:21) | proposed (backtest evidence): keep `profile_check_role` = advisory | `profile_veto`: train +0.02 (t 0.26), 2025 -0.29, 2026 -0.06; the engine's profile test is weak on 5m data | none (proposed) | companion/styles/ttrades/continuation.py roles |
| TD-004 | 2026-11-21 | Trade reversals at all? (ENT-6: "I don't trade reversals ... I don't really trade reversals", livestream_20260325 50:13) | proposed (backtest evidence): keep `trade_reversals` = true | in this engine the reversals carry the result (+0.002 / +0.051 / +0.054 R a trade) and continuations lose; `no_reversals`: 2025 -0.93 R/wk, 2026 -0.39 | none (proposed) | companion/styles/ttrades/style.py _select |
| TD-005 | 2026-11-21 | Kill zone 08:00-10:30 New York as a filter? (SES-1: "capture the move from 8 normally to 10-ish ... Sometimes 10.30", livestream_20260728 36:35; against SES-12, "kill zones don't matter") | proposed (backtest evidence): keep `session_filter_role` = advisory; revisit with one trade a day | with no cap it loses out of sample (2025 -0.31, 2026 -0.12); with one trade a day it gains in 2025 (+0.31) and 2026 (+0.42) but not enough on train (t 0.63) to be chosen | none (proposed) | companion/tools/backtest.py VARIANTS ny_window |
| TD-006 | 2026-11-21 | One trade a day? (PSY-1: "Best way to go about that is max one trade a day", livestream_20261110 17:44) | proposed (backtest evidence): a trading rule, not an engine setting; report both | the engine is stateless; `weekly_r --max-per-day 1 --day-scope portfolio` applies it; it cuts trades from ~14 to ~4 a week and changes which switches win (see [[evidence]]) | none (proposed) | companion/tools/weekly_r.py take |
| TD-007 | 2026-11-21 | Which stack by default? (FM: "best off with using daily and hourly fractal for bias and then using the H4 and 15 model", livestream_20260721 09:12) | proposed (backtest evidence): prefer 1D/4h/15m (and 1W/1D/1h) over 1D/1h/5m | 1D/1h/5m: -0.64 / -1.03 / +0.02 R/wk; 1D/4h/15m: -0.07 / +1.00 / +0.21 | none (proposed) | run selection |
| TD-008 | 2026-11-21 | Skip Candle 4 when Candle 2 and Candle 3 both expanded? (C4c: "When to avoid trading candle 4? Well, generally when candle 2 and candle 3 both expand.", livestream_20260317 50:05) | proposed (backtest evidence): `c4_after_double_expansion` = skip | train +0.07 (t 0.92; 1/day t 1.17), 2025 +0.04, 2026 +0.05: small, same sign everywhere | none (proposed) | companion/styles/ttrades/continuation.py c1 |
| TD-009 | 2026-11-21 | Trade only the setup whose swing made the day's wick? (T1: "you really only have one change in the state of delivery per day. That forms the daily wick.", livestream_20260505 rule 5) | proposed (backtest evidence): `cont_setup_pick` = wick_extreme | strongest train gain of the teacher switches (+0.10 R/wk, t 2.85); with one trade a day 2025 +0.08, 2026 +0.05; with no cap 2025 -0.09 | none (proposed) | companion/styles/ttrades/continuation.py c3 |
| TD-011 | 2026-11-21 | Revisit question 38 (stop size against the ADR; answered 2026-11-13, "ADR is not that big of a deal") | proposed (backtest evidence): `stop_size_role` = quality | stops under 4% of the ADR lose in every period (-0.49 / -0.30 / -0.44 R a continuation trade), mostly costs; `stop_gate` train t 1.71, 2025 +0.03, 2026 +0.03 | none (proposed) | companion/styles/ttrades/style.py stop_size |
