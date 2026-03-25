# TTFM Multimodal Historical Learning Loop

## Purpose

Define the autonomous historical-learning loop for `TTFM` (`TTrades fractal model`) so the repo can:
- learn TTFM components from screenshots, docs, videos, and historical outcomes,
- turn machine-expressible concepts into Pine drafts and validate them inside TradingView,
- improve from repeated visual and rules-based mistakes,
- write findings back into durable research artifacts,
- and stay explicitly historical/offline rather than drifting into live-trading claims.

## Understanding Summary

- `TTFM` is the target framework and should be treated as a first-class concept in the repo.
- The first model target is `component mapping`, not trade execution or profit prediction.
- Screenshots are a first-class training source from day one.
- TradingView editor validation is a first-class translation check for Pine-ready concepts.
- Multi-timeframe analysis is core to TTFM and must be explicit in every historical case.
- Training labels are hybrid:
  - strong anchor labels where confidence is high,
  - weak labels derived from docs, videos, specs, and historical rules.
- The autonomous loop learns from `visual mismatch + rules mismatch`.
- The loop may update labels, findings, draft specs, and `open_questions`, but not core rulebooks.

## Non-Goals

- No live execution.
- No real-time neural decisioning.
- No silent rewriting of core rulebooks.
- No end-to-end black-box trade policy as the first model.

## Core Architecture

### 1. Source Layer

The learning loop ingests:
- topic rulebooks,
- draft indicator specs,
- generated Pine drafts,
- topic `open_questions`,
- extracted docs and video notes,
- historical case outcomes,
- screenshot checkpoints,
- and TradingView validation outcomes.

### 2. Case Packet Layer

Each historical TTFM example is stored as one durable multimodal case packet.

Each packet contains:
- framework identifier: `TTFM`
- instrument and market metadata
- date or session window
- higher timeframe (`HTF`) context
- execution timeframe (`ETF`) context
- lower timeframe (`LTF`) confirmation context
- outcome metadata
- links to supporting rule/spec references

### 3. Labeling Layer

Labels are created in two passes:
- anchor labels from trusted cases
- weak labels from rules, specs, docs, video extraction, and prior case structure

Every label must carry provenance:
- `anchor_manual`
- `rule_derived`
- `video_derived`
- `model_corrected`

### 4. Vision Model Layer

The first model only answers:
- what TTFM components are visible here?

It does not answer:
- should we trade?
- what direction should we take?
- what profit should we expect?

### 5. Disagreement Layer

A case counts as mistaken when:
- the predicted labels do not match the screenshot evidence, and/or
- the predicted labels violate current rulebook or draft-spec logic

Repeated disagreement should become a durable finding rather than getting buried in training logs.

### 6. Research Feedback Layer

Autonomous write-back is allowed for:
- weak-label relabeling
- findings updates
- draft spec updates
- topic `open_questions` updates

Autonomous write-back is not allowed for:
- core rulebook rewrites
- silent ontology replacement
- live-trading readiness claims

## Historical Case Schema

Each case should usually contain `3` to `5` screenshot checkpoints:
- `context`
- `sweep`
- `closure`
- `confirmation`
- `outcome`

Each checkpoint should store:
- screenshot path
- timeframe (`HTF`, `ETF`, or `LTF`)
- bar or candle range
- component labels
- optional zone geometry
- short reasoning note
- supporting rule or spec references

## TTFM Component Vocabulary

### Existing Repo-Aligned Labels

- `candle_2_closure`
- `candle_3_closure`
- `protected_swing`
- `equilibrium`
- `invalidation`
- `wick_logic`
- `top_down_alignment`

### TTFM Visual Object Labels

- `fair_value_gap`
- `order_block`
- `breaker`
- `point_of_interest`
- `liquidity_sweep`
- `zone_boundary`

This vocabulary is intentionally constrained. The model should learn the repo's visual language, not invent a separate one.

## Multi-Timeframe Requirements

TTFM understanding is invalid if the model only reads one timeframe in isolation.

Each case packet must preserve:
- `HTF` directional and zone context
- `ETF` working setup structure
- `LTF` confirmation detail

Evaluation must penalize:
- valid local component reads that contradict higher-timeframe context
- loss of zone continuity between checkpoints
- confirmation labels that appear before the required prior sequence steps

## Autonomous Training Loop

Each offline training pass should follow this order:

1. Ingest updated docs, videos, rulebooks, specs, screenshots, TradingView validation logs, and historical outcomes.
2. Build or refresh TTFM case packets.
3. Weak-label unlabeled or partially labeled checkpoints.
4. Generate or refresh Pine drafts from Pine-target indicator specs.
5. Validate generated Pine drafts in TradingView.
   TradingView validation only counts when the Monaco editor buffer is confirmed to match the generated draft.
6. Train the component mapper.
7. Re-run the model on anchor and weak-labeled cases.
8. Detect disagreement against screenshot truth and rule/spec logic.
9. Cluster repeated mistakes into durable findings.
10. Relabel weak cases when confidence improves.
11. Update draft specs and `open_questions` when repeated ambiguity or rule conflicts appear.
12. Emit a graded `training_loop_report`.
13. Compare the current loop against the previous recorded run and emit a bounded improvement plan.

## Training Loop Grading

Every loop should be graded so the repo can distinguish genuine progress from noisy churn.

### Scoring Buckets

1. `data_quality` (`20%`)
- case count growth
- screenshot coverage
- HTF/ETF/LTF completeness
- provenance coverage

2. `label_quality` (`25%`)
- anchor-case agreement
- rule mismatch rate
- contradiction rate across checkpoints
- ambiguity handling quality

3. `model_quality` (`25%`)
- per-label precision, recall, and F1
- timeframe consistency
- sequence consistency
- confidence calibration on anchor cases

4. `research_yield` (`15%`)
- useful findings generated
- repeated mistake clusters reduced
- clarified draft specs
- clarified `open_questions`
- TradingView/Pine workflow progress

5. `regression_safety` (`15%`)
- anchor-case regressions
- label collapse
- rising rule disagreement
- excessive relabel churn

### Loop Output

Each pass should emit:
- `loop_score` from `0.0` to `1.0`
- `grade`
- `verdict`
- a self-improvement plan with:
  - the current bottleneck phase
  - prioritized next actions
  - the success metric for the next iteration
  - progress or regression relative to the previous recorded run

Allowed verdicts:
- `keep`
- `keep_with_warnings`
- `discard`
- `investigate`

### Bad Loop Criteria

A loop should be considered bad even if one metric improves when:
- anchor-case agreement drops,
- rule mismatch rises,
- timeframe consistency weakens,
- or relabel churn increases without better findings quality.

## Guardrails

- Core rulebooks are read-only to the autonomous loop.
- Every relabel must preserve provenance and previous state.
- Draft spec updates must be diffable and reversible.
- Repeated ambiguity should open an `open_question`, not force a bad label.
- A concept is not Pine-mature until a generated draft has been checked in TradingView.
- The loop must remain historical/offline until separate readiness gates are passed.

## Decision Log

- Chosen framework target: `TTFM` (`TTrades fractal model`)
- Chosen model target: `component mapping`
- Screenshots are first-class from day one.
- Training label policy: `hybrid`
- Historical case shape: `3 to 5` checkpoints
- Mistake signal: `visual mismatch + rules mismatch`
- Autonomous write-back scope:
  - labels
  - findings
  - draft specs
  - `open_questions`
- Protected artifacts:
  - core rulebooks
  - live-trading readiness claims

## Implementation Implication

The next implementation step should create a dedicated TTFM multimodal learning lane in the repo, rather than overloading the existing rulebook and report exporters with hidden vision-training behavior.
