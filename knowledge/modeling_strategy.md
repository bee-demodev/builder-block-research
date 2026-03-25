# Modeling Strategy

This project is aiming at a personalized trading research system, not just a generic note summarizer.

## Core idea

The system should eventually be able to model:
- how a specific trader identifies structure,
- how that trader confirms or rejects an entry,
- how that trader places invalidation,
- and how multiple traders differ on the same chart state.

That means the real asset is not "GPU capability" by itself. The real asset is a reproducible labeled dataset.

## What creates reproducibility

Reproducibility comes from:
- explicit topic rulebooks,
- source-grounded evidence,
- fixed evaluation logic,
- teacher-style mappings from profiles to canonical trade models,
- trader-specific annotation records,
- and benchmark cases with stable inputs and expected outputs.

Without those pieces, model training would only learn inconsistent discretion.

## Recommended build order

### 1. Deterministic rules first
- define expansion, protected swings, invalidation, continuation, and bias
- keep ambiguity visible instead of hiding it
- measure determinism and Pine translatability each loop

### 2. Trader-profile data next
- create one profile per teacher, trader, or playbook
- attach each profile to the canonical frameworks, trade models, and emphasized topics it actually uses
- record how each profile marks the same concept on the chart
- store chart context, annotations, and outcomes

The key modeling move is:
- canonical topics stay generic,
- trade models stay reusable,
- and each teacher style becomes a profile-level execution bundle that can later power indicator specifications.

### 3. Local representation layer
- use local embeddings for retrieval over transcripts, rulebooks, and examples
- use local vision when chart screenshots and markup become part of the workflow

### 4. Model-training surface before modeling
- export one supervised row per annotation-to-trade-model link
- keep features structured: topic, setup variant, timeframe scope, session scope, annotation keys, and explicit outcome labels
- generate a gating report that says which tasks are actually trainable and which are still under-labeled
- prefer narrow supervised tasks first: trade-model scoring, relation-type classification, and stand-aside filters

### 4b. Stage-gated readiness before live claims
- separate "research loop maturity" from "real-time neural trading readiness"
- grade at least four stages explicitly:
  - Karpathy-style autoresearch loop
  - narrow offline ML
  - real-time neural assist
  - real-time neural execution
- never let high ontology or rulebook scores masquerade as live-trading readiness
- cap real-time stages hard when:
  - runtime or paper-trade infrastructure is missing
  - specs are still draft-only
  - the label space is not broadly trainable
  - scenario contracts do not cover most labeled case-model links
- treat missing scenario contracts as `ungraded`, not as free positive evidence

### 4c. Historical replay and backtesting before any real-time path
- insert a historical gate before any live or real-time trading discussion
- grade at least four historical stages explicitly:
  - backtesting research foundation
  - manual chart replay understanding
  - rules-based historical backtesting
  - model-assisted historical backtesting
- cap structured historical stages hard when:
  - no repeatable replay or backtest harness exists
  - no spread, slippage, commission, or other transaction-cost assumptions are encoded
  - specs are still draft-only rather than validated backtest contracts
- keep real-time neural work deferred until manual replay and rules-based historical testing are already honest

### 5. Training layer last
- use PyTorch or similar only after enough labeled chart cases exist
- start with simple baselines first, not end-to-end black-box trading policies
- target ranking, imitation, or policy-style prediction over structured trader decisions
- only let a neural layer score or rank rule-grounded setups before asking it to drive entries directly

## Practical implication for hardware

### Useful soon
- local embeddings
- local OCR / image understanding
- screenshot comparison or chart-state retrieval

### Useful later
- PyTorch training
- local multimodal models for chart interpretation
- trader-specific fine-tuning or preference training

## Current stance

CUDA is not a blocker for the current repo state.

It becomes strategically useful once local embeddings, local vision, or training move from optional experiments to part of the core loop.

The repo now has a model-training surface export, a staged neural-readiness report, and a historical-backtesting readiness report. That is the right next step because it makes label scarcity explicit and blocks premature live claims:
- `results/model_training_surface.jsonl` turns each annotated trade-model link into one supervised example
- `results/model_training_report.json` currently shows `16` rows and `15` explicit outcome labels
- `results/neural_net_readiness_report.json` currently grades:
  - autoresearch loop = `A`
  - narrow offline ML = `B`
  - real-time neural assist = `C`
  - real-time neural execution = `D`
- `results/backtesting_readiness_report.json` currently grades:
  - historical backtesting research foundation = `A`
  - manual chart replay understanding = `A-`
  - rules-based historical backtesting = `B-`
  - model-assisted historical backtesting = `C`

So the next clean move is still more labeled chart cases, more scenario contracts, manual replay discipline, and a minimal historical harness with explicit cost assumptions, not premature end-to-end neural trading.
