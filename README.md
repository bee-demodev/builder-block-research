# Trading Autoresearch

This repository adapts Andrej Karpathy's `autoresearch` pattern to a trading research workflow.

The goal is to:
- learn trading basics from the TTrades Education Center as an initial corpus,
- convert those lessons into explicit, source-grounded rulebooks,
- separate canonical concepts from teacher-specific execution styles,
- score those rulebooks for determinism and Pine translatability,
- only generate Pine indicators after the rules are explicit enough to code,
- and use historical replay and structured backtesting understanding as the gate before any real-time trading claim.

## Start Here

If you are working on the Gemini-first TTFM brain, the canonical public surface is only:

```bash
python scripts/run_ttfm_brain_loop.py
python scripts/export_ttfm_brain_review_packets.py
python scripts/export_ttfm_brain_improvement_plan.py
```

Those three scripts are the operator-facing path for the current autonomous learning lane:
- `scripts/run_ttfm_brain_loop.py` validates or refreshes Google embedding manifests, rebuilds the multimodal training surface, retrains the brain, exports review packets, and writes the final loop report.
- `scripts/export_ttfm_brain_review_packets.py` turns the latest disagreement queue into reviewer-ready packets.
- `scripts/export_ttfm_brain_improvement_plan.py` turns the latest loop state into the next-iteration contract.

Everything else in the TTFM lane should be treated as one of these:
- internal helpers: `scripts/run_ttfm_visual_teacher_loop.py`, `scripts/run_ttfm_multimodal_teacher_loop.py`
- downstream Pine/readiness flow: `scripts/run_trading_learning_loop.py`

The current brain loop is intentionally offline and historical:
- it learns from TradingView-style screenshots, transcript context, and audio-derived Gemini summaries
- it trains a compact embedding-fusion classifier for `brain_type = setup_scorer`
- it reports whether the brain is ready for Pine translation later
- it does not generate or validate Pine directly in this milestone

Gemini embeddings are assumed to already exist as the normal operating baseline. The brain loop checks the existing manifests and only refreshes the Google text or visual indexes when the expected row counts drift.

## Core idea

Instead of optimizing model loss, this repo optimizes rule quality.

Each research loop improves one topic at a time, starting with:
- `expansion`
- `protected_swings`
- `bias`
- `reversal`
- `continuation`
- `retracement`
- `consolidation`
- `equilibrium`
- `wick_logic`
- `top_down_alignment`
- `invalidation`
- `daily_profiles`
- `candle_2_closure`
- `candle_3_closure`

The loop keeps changes only when the active topic becomes:
- more grounded in sources,
- more deterministic,
- more visually verified,
- and more translatable to Pine Script.

## Repo shape

```text
data/schema.sql
knowledge/trading_basics.md
knowledge/modeling_strategy.md
knowledge/pine_basics.md
knowledge/ttrades_corpus.md
topics/bias/rulebook.json
topics/continuation/rulebook.json
topics/consolidation/rulebook.json
topics/expansion/rulebook.json
topics/protected_swings/rulebook.json
topics/retracement/rulebook.json
topics/reversal/rulebook.json
scripts/prepare.py
scripts/evaluate_rulebook.py
scripts/log_research_run.py
scripts/sync_rulebook_to_db.py
scripts/run_topic_loop.py
scripts/record_trader_annotation.py
scripts/import_trader_annotation_cases.py
scripts/discover_ttrades_corpus.py
scripts/import_ttrades_manifest.py
scripts/ingest_ttrades_pages.py
scripts/register_source_artifact.py
scripts/build_research_backlog.py
scripts/materialize_indicator_candidates.py
scripts/build_pine_draft_spec.py
scripts/export_trader_dataset.py
scripts/export_topic_model_report.py
scripts/export_understanding_report.py
scripts/export_model_training_surface.py
scripts/export_neural_net_readiness_report.py
scripts/export_backtesting_readiness_report.py
scripts/export_ttfm_case_packets.py
scripts/export_ttfm_training_loop_report.py
scripts/export_ttfm_feedback_queue.py
scripts/run_trading_learning_loop.py
results/research_runs.tsv
results/indicator_specs/reversal_sequence_model.json
results/model_training_report.json
results/neural_net_readiness_report.json
results/backtesting_readiness_report.json
results/ttfm_case_packets.json
results/ttfm_training_loop_report.json
data/ttfm_component_taxonomy.json
data/tradingview_pine_validation.json
data/ttfm_feedback_queue.json
program.md
IMPLEMENTATION_PLAN.md
data/trader_annotation_cases.json
```

## First research sources

Trading concepts:
- [TTrades Education Center](https://ttrades.com/trading-education-center/)
- [Phases of Price - Part 2: Mastering Expansion for Strong Trend Trades](https://ttrades.com/phases-of-price-part-2-mastering-expansion-for-strong-trend-trades/)
- [Protected Swings in Trading: How to Identify and Use Them for Entries & Continuations](https://ttrades.com/protected-swings-understanding-trends-and-invalidations/)
- [Stop Loss Mastery - Using Protected Swings for Precise Invalidations](https://ttrades.com/stop-loss-mastery-using-protected-swings-for-precise-invalidations/)
- [Easy Daily Bias: A Mechanical Trading Framework](https://ttrades.com/easy-daily-bias-a-mechanical-trading-framework/)
- [Aligning Candles for Expansion: How True Trends Actually Form](https://ttrades.com/aligning-candles-for-expansion-how-true-trends-actually-form/)
- [Mastering Top-Down Analysis: Aligning Multiple Timeframes for Expansion Trading](https://ttrades.com/mastering-top-down-analysis-aligning-multiple-timeframes-for-expansion-trading/)

Pine implementation constraints:
- [TradingView Pine Script Style Guide](https://www.tradingview.com/pine-script-docs/writing/style-guide/)
- [TradingView Pine Script Type System](https://www.tradingview.com/pine-script-docs/language/type-system/)
- [TradingView Pine Script Limitations](https://www.tradingview.com/pine-script-docs/writing/limitations/)

## Usage

Initialize the baseline:

```bash
python scripts/prepare.py
```

Evaluate a topic rulebook:

```bash
python scripts/evaluate_rulebook.py --topic bias
python scripts/evaluate_rulebook.py --topic expansion
python scripts/evaluate_rulebook.py --topic protected_swings
```

Log a research run:

```bash
python scripts/log_research_run.py --topic expansion --status keep --description "tightened invalidation rules"
```

Sync a topic into SQLite and run one full bookkeeping pass:

```bash
python scripts/run_topic_loop.py --topic bias --status keep --description "initial bias baseline"
python scripts/run_topic_loop.py --topic continuation --status keep --description "initial continuation baseline"
python scripts/run_topic_loop.py --topic consolidation --status keep --description "initial consolidation baseline"
python scripts/run_topic_loop.py --topic expansion --status keep --description "baseline synced after evaluator hardening"
python scripts/run_topic_loop.py --topic protected_swings --status keep --description "baseline synced after evaluator hardening"
python scripts/run_topic_loop.py --topic retracement --status keep --description "initial retracement baseline"
python scripts/run_topic_loop.py --topic daily_profiles --status keep --description "initial daily profile baseline"
python scripts/run_topic_loop.py --topic candle_2_closure --status keep --description "initial candle 2 closure baseline"
python scripts/run_topic_loop.py --topic candle_3_closure --status keep --description "initial candle 3 closure baseline"
python scripts/run_topic_loop.py --topic equilibrium --status keep --description "initial equilibrium baseline"
python scripts/run_topic_loop.py --topic wick_logic --status keep --description "initial wick logic baseline"
python scripts/run_topic_loop.py --topic top_down_alignment --status keep --description "initial top down alignment baseline"
python scripts/run_topic_loop.py --topic invalidation --status keep --description "initial invalidation baseline"
```

Record a trader-specific chart annotation case:

```bash
python scripts/record_trader_annotation.py \
  --profile-slug ttrades_curriculum \
  --topic expansion \
  --trade-model continuation_entry_model \
  --case-ref demo_case_001 \
  --source-url https://ttrades.com/phases-of-price-part-2-mastering-expansion-for-strong-trend-trades/ \
  --chart-context-json "{\"timeframe\":\"daily\",\"phase\":\"expansion\"}" \
  --annotation-json "{\"range_type\":\"expansion_leg\",\"invalidation\":\"protected_swing\"}"
```

Import the durable teacher-style annotation baselines:

```bash
python scripts/import_trader_annotation_cases.py
python scripts/materialize_indicator_candidates.py
python scripts/build_pine_draft_spec.py --spec-key ttrades_curriculum__continuation_entry_model
python scripts/build_pine_draft_spec.py --spec-key ttrades_curriculum__daily_bias_framework
python scripts/build_pine_draft_spec.py --spec-key ttrades_curriculum__daily_profile_models
python scripts/build_pine_draft_spec.py --spec-key ttrades_curriculum__fractal_closure_model
python scripts/build_pine_draft_spec.py --spec-key ttrades_curriculum__reversal_sequence_model
python scripts/export_trader_dataset.py
python scripts/export_topic_model_report.py
python scripts/export_understanding_report.py
python scripts/export_model_training_surface.py
python scripts/export_neural_net_readiness_report.py
python scripts/export_backtesting_readiness_report.py
python scripts/export_ttfm_case_packets.py
python scripts/export_ttfm_training_loop_report.py
```

The annotation-case manifest can now express either:
- a simple single-model case, or
- a composite teacher-style case with `trade_model_links`, where one chart example links to multiple trade models with distinct relation types.

Discover and import the TTrades corpus baseline:

```bash
python scripts/discover_ttrades_corpus.py
python scripts/import_ttrades_manifest.py
python scripts/discover_ttrades_corpus.py --fetch-details --category bias --category expansion --category protected_swings --output data/ttrades_core_manifest.json
python scripts/import_ttrades_manifest.py --manifest data/ttrades_core_manifest.json
```

Build the ingestion backlog and export trader data:

```bash
python scripts/build_research_backlog.py
python scripts/materialize_indicator_candidates.py
python scripts/export_trader_dataset.py
python scripts/export_topic_model_report.py
python scripts/export_understanding_report.py
python scripts/export_model_training_surface.py
```

Export the model-ready training surface plus the readiness gates for historical backtesting first and any future neural layer second:

```bash
python scripts/export_model_training_surface.py
python scripts/export_neural_net_readiness_report.py
python scripts/export_backtesting_readiness_report.py
```

This writes:
- `results/model_training_surface.jsonl`
- `results/model_training_report.json`
- `results/neural_net_readiness_report.json`
- `results/backtesting_readiness_report.json`
- `results/ttfm_case_packets.json`
- `results/ttfm_training_loop_report.json`

The current training-surface baseline is intentionally small:
- `16` example rows from `14` unique chart cases
- `6` distinct trade-model labels
- `15` explicit outcome labels

That means the repo can now support a rules-first hybrid path, but it still does **not** justify end-to-end neural training or any real-time trading system yet.

The historical backtesting readiness report currently says:
- historical backtesting research foundation: `A`
- manual chart replay understanding: `A-`
- rules-based historical backtesting: `B-` and still not ready
- model-assisted historical backtesting: `C` and still not ready

The current historical blockers are explicit:
- no transaction-cost model is encoded in the indicator specs yet
- no commission, spread, slippage, or transaction-cost model is encoded yet
- all five indicator specs are still `draft`
- the tracked backtesting methodology article is still missing a local text artifact

The repo now includes a minimal historical harness surface:
- `runtime/harness.py` provides next-bar execution, explicit stop/target handling, session-aware filtering, and configurable spread/slippage/commission inputs
- `runtime/backtest_harness.py` is a thin CLI runner for structured signal backtests
- `runtime/replay_harness.py` builds replay frames for bar-by-bar review workflows
- `scripts/backtest_analyzer.py` summarizes trade runs into JSON-ready metrics

So the clean next move is still manual replay discipline plus explicit cost assumptions in the specs, not live trading.

The repo now also has a dedicated `TTFM` lane for screenshot-first historical learning:
- `data/ttfm_component_taxonomy.json` defines the initial TTFM visual vocabulary
- `scripts/export_ttfm_case_packets.py` converts current historical cases into timeframe-aware multimodal packets
- `scripts/export_ttfm_training_loop_report.py` grades each autonomous training pass so bad loops can be investigated or discarded
- `scripts/export_ttfm_feedback_queue.py` merges Pine verification failures and TradingView validation failures into a durable safe-feedback queue
- `scripts/run_trading_learning_loop.py` runs the repeatable research -> Pine -> readiness loop in one command
- `scripts/export_trading_learning_improvement_plan.py` turns the latest loop outputs into a prioritized next-iteration contract and records loop history

The first bootstrap TTFM export currently says:
- `14` TTFM case packets
- `70` checkpoint slots across `context`, `sweep`, `closure`, `confirmation`, and `outcome`
- multi-timeframe coverage ratio = `0.7857`
- current training-loop bootstrap grade = `D`

That `D` is expected at this stage because the new lane has:
- screenshot attachments are now bootstrapped automatically, but anchor labels are still missing
- no anchor-vs-model comparison metrics yet
- no trained multimodal component mapper yet

The new staged readiness report currently says:
- Karpathy-style autoresearch loop: `A`
- narrow offline ML: `B`
- real-time neural assist: `C` and still not ready
- real-time neural execution: `D` and still a hard no

## Reproducible loop

Run the repo's repeatable trading-learning loop:

```bash
python scripts/run_trading_learning_loop.py
```

Optional flags:

```bash
python scripts/run_trading_learning_loop.py --bootstrap-screenshots
python scripts/run_trading_learning_loop.py --apply-safe-feedback
```

Historical harness helpers:

```bash
python runtime/backtest_harness.py --bars path/to/bars.csv --signals path/to/signals.json
python scripts/backtest_analyzer.py --bars path/to/bars.csv --signals path/to/signals.json
```

This loop refreshes:
- imported teacher-style annotation cases
- TTFM case packets
- Pine verification queue and report
- generated Pine drafts
- TradingView Pine readiness
- safe feedback queue
- TTFM training-loop report
- neural-net readiness report
- backtesting readiness report
- self-improvement plan plus loop history

It writes a compact orchestration summary to:
- `results/trading_learning_loop_summary.json`

It also writes the self-improvement artifacts to:
- `results/trading_learning_improvement_plan.json`
- `results/trading_learning_history.jsonl`

Those files are the loop's durable memory:
- each run records a compact metric snapshot
- the current plan compares against the previous recorded run
- the plan surfaces the current bottleneck phase, prioritized actions, and the success metric for the next pass

TradingView validation is intentionally strict:
- successful Playwriter validation only counts when the actual Monaco editor buffer contains the generated draft and TradingView compiles that exact draft
- blocked browser/editor sync attempts are logged to `data/tradingview_pine_validation.json` and can feed findings instead of inflating readiness
- the reliable Playwriter path is Monaco textarea focus -> `Ctrl+A` replacement -> `Update on chart`; changing editor title or store metadata alone is not validation

Screenshot bootstrap is now idempotent:
- `python scripts/run_trading_learning_loop.py --bootstrap-screenshots` preserves existing screenshot manifest entries on reruns
- reruns only re-download files when an attachment path exists in the manifest but the local artifact is missing

The first neural layer should stay narrow and task-specific:
- `continuation_entry_model` one-vs-rest scoring
- `trade` vs `no_trade` filtering

The report also now penalizes missing scenario contracts instead of giving them free credit. Right now `15` of `16` case-model links have explicit scenario expectation contracts, and the only remaining `ungraded` link is the legacy `phases_of_price_framework` expansion baseline that still sits outside the indicator-spec set.

Sync the topic/model graph and ingest local article markdown:

```bash
python scripts/sync_topic_model_graph.py
python scripts/ingest_ttrades_pages.py --category bias --category expansion --category protected_swings --category reversal --category retracement --category consolidation --category continuation
```

## Current principle

Do not write Pine directly from prose.

A topic becomes indicator-ready only when:
- its rules are explicit,
- its exceptions are known,
- its ambiguity is low,
- and its inputs can be expressed from Pine-accessible data.

## Modeling principle

For this repo, reproducibility comes from labels and rules before it comes from GPUs.

That means the build order is:
- deterministic topic rulebooks,
- teacher-style profiles plus trader-specific annotations and examples,
- local embeddings / local vision if needed,
- and only then PyTorch-style training or imitation.

## Corpus baseline

The current baseline now includes:
- a discovered TTrades source manifest from the Education Center,
- a core concept manifest with embedded YouTube and PDF/media discovery,
- article, video, and asset URLs imported into SQLite,
- a portable framework layer with canonical topics and trade models plus framework-scoped vocabulary,
- a teacher-style layer that links trader profiles to frameworks, trade models, and emphasized topics,
- a durable teacher-style annotation-case manifest for repeatable baseline imports,
- materialized indicator specs derived from indicator-ready teacher-style trade models,
- a model-ready training-surface export that converts each annotation-to-trade-model link into a supervised example,
- and a gating report that shows whether any classifier task is actually ready for baseline training,
- annotation-backed evidence linking teacher-style chart cases to exact trade models,
- support for composite chart cases that can link one example to multiple teacher-style trade models with distinct roles,
- explicit source-to-topic and source-to-model links,
- a materialized trade-model dependency closure table,
- local markdown extracts for the 28 core concept pages,
- a staged readiness report that separates research maturity from real-time neural trading readiness,
- a historical-backtesting readiness report that separates manual replay understanding from structured backtest readiness,
- fourteen scored topic baselines: `bias`, `expansion`, `protected_swings`, `reversal`, `continuation`, `retracement`, `consolidation`, `daily_profiles`, `candle_2_closure`, `candle_3_closure`, `equilibrium`, `wick_logic`, `top_down_alignment`, and `invalidation`,
- and a backlog report for missing text artifacts and video transcripts.

Current snapshot:
- 640 sources
- 674 source artifacts
- 3 frameworks
- 14 research topics
- 6 active trade models
- 91 materialized trade-model topic requirements
- 557 source-topic links
- 282 source-trade-model links
- 1 active teacher-style profile
- 14 durable trader-annotation manifest cases
- 14 trader annotation rows currently present in SQLite
- 16 annotation-to-trade-model links
- 6 trade models with at least one labeled teacher-style case
- 5 indicator specs total: 0 `candidate` rows plus 5 `draft` rows for `ttrades_curriculum__continuation_entry_model`, `ttrades_curriculum__daily_bias_framework`, `ttrades_curriculum__daily_profile_models`, `ttrades_curriculum__fractal_closure_model`, and `ttrades_curriculum__reversal_sequence_model`
- understanding report available in `results/understanding_report.json` with current repo-wide score `0.9256` (`A-`)
- scenario contracts currently cover `15` of `16` exported case-model links; `1` link remains `ungraded`
- staged neural-readiness report available in `results/neural_net_readiness_report.json`
- staged historical-backtesting report available in `results/backtesting_readiness_report.json`
- current historical-first grades:
  - backtesting research foundation = `A`
  - manual chart replay understanding = `A-`
  - rules-based historical backtesting = `B-`
  - model-assisted historical backtesting = `C`
- TTFM case-packet export available in `results/ttfm_case_packets.json`
- TTFM training-loop grading report available in `results/ttfm_training_loop_report.json`
- current staged grades:
  - autoresearch loop = `A`
  - offline narrow ML = `B`
  - real-time neural assist = `C`
  - real-time neural execution = `D`
- current weakest topics by measured understanding are `bias`, `expansion`, and `protected_swings`
- current weakest draft spec by measured understanding is `ttrades_curriculum__reversal_sequence_model`, mainly on machine-checkability rather than coverage
- 60 article or doc sources still missing text artifacts
- 79 video sources still missing transcripts
