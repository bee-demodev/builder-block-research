# Karpathy-Style Autoresearch Plan for Trading Basics -> Pine Indicators

## Objective
Build a tiny research repo that learns trading concepts from TTrades, converts them into explicit rulebooks, and only then emits Pine-ready indicator specifications. The loop should improve the rulebase over time in a measurable, keep/discard fashion.

## Why Karpathy's Pattern Fits
Karpathy's `autoresearch` works because it narrows the problem:
- tiny repo
- fixed evaluator
- short comparable iterations
- one main editable target
- keep only measured improvements

Our use case should keep those same constraints, but replace model training with rule extraction and indicator-spec generation.

## Core Adaptation
Instead of optimizing `val_bpb`, we optimize a research score for each topic rulebook.

### Primary Scores
- `grounding_score`: percent of claims backed by one or more TTrades or official Pine sources
- `determinism_score`: percent of rules with explicit conditions, anchors, invalidation, and state transitions
- `visual_verification_score`: percent of rules observed on chart examples or browser practice passes
- `pine_translatability_score`: percent of rules that can be expressed from OHLCV/time/session/request data without hidden discretion
- `contradiction_penalty`: count of conflicting definitions or unresolved ambiguities

### Keep / Discard Rule
Advance the active rulebook only when:
- total weighted score improves, and
- contradiction count does not increase materially, and
- complexity remains reasonable

## Small-Repo Design
The repo should stay intentionally narrow.

```text
program.md
README.md
data/schema.sql
knowledge/trading_basics.md
knowledge/modeling_strategy.md
knowledge/pine_basics.md
topics/expansion/rulebook.json
topics/expansion/examples.md
topics/expansion/open_questions.md
scripts/prepare.py
scripts/evaluate_rulebook.py
scripts/sync_rulebook_to_db.py
scripts/run_topic_loop.py
scripts/record_trader_annotation.py
results/research_runs.tsv
```

## Fixed vs Mutable Surface Area
To preserve the spirit of `autoresearch`, keep most files stable.

### Fixed Harness
- `program.md`: loop instructions
- `data/schema.sql`: storage model
- `scripts/prepare.py`: source ingestion, normalization, DB helpers
- `scripts/evaluate_rulebook.py`: deterministic scoring harness
- `scripts/sync_rulebook_to_db.py`: writes the active topic and evidence links into SQLite
- `scripts/run_topic_loop.py`: one-command sync + score + log cycle
- `results/research_runs.tsv`: append-only run ledger

### Mutable Per Loop
- one active topic rulebook, e.g. `topics/expansion/rulebook.json`
- one topic examples file
- one topic open-questions file

This is the equivalent of Karpathy's single mutable `train.py`, but adapted to knowledge codification.

## Proposed Database Structure
The schema should support learning, evidence, and translation.

### Core Tables
- `sources`
  - article, video, pdf, note
- `source_artifacts`
  - transcript, markdown extract, screenshot, frame, annotation
- `concepts`
  - phase, bias, structure, execution, risk, profile
- `claims`
  - atomic source-grounded statements
- `rules`
  - codified if/then logic linked to a concept
- `rule_evidence`
  - citations from specific sources or frames
- `chart_markup_attempts`
  - browser practice runs for drawing ranges, protected swings, invalidations
- `trader_profiles`
  - baseline teacher profiles, individual traders, or future model personas
- `trader_annotations`
  - trader-specific chart context, annotation payloads, and outcomes for training data
- `indicator_specs`
  - Pine-oriented outputs derived from stable rules
- `research_runs`
  - loop scorecard and keep/discard decision

## Topic-Centric Rulebook Format
Each topic gets a strict rulebook.

For `topics/expansion/rulebook.json`, every rule should include:
- `id`
- `name`
- `timeframe_scope`
- `market_phase_precondition`
- `direction`
- `setup_anchor`
- `confirmation_trigger`
- `protected_swing_definition`
- `invalidation_condition`
- `target_logic`
- `exceptions`
- `evidence_refs`
- `pine_inputs_needed`
- `ambiguity_notes`

If any of those fields are missing, the rule is not ready for indicator design.

## Research Loop
Each loop should be short, measurable, and repeatable.

### Loop Steps
1. Read `program.md` and current topic rulebook.
2. Pick 1-3 source items from TTrades or official Pine docs.
3. Extract atomic claims.
4. Normalize claims into rules or open questions.
5. Use Playwriter for visual review:
   - inspect article charts or embedded videos
   - identify anchors, swing points, and invalidations
   - record markup attempts
6. Run `scripts/sync_rulebook_to_db.py`.
7. Run `scripts/evaluate_rulebook.py`.
8. Log the outcome to `results/research_runs.tsv` and `research_runs`.
9. Keep or discard the iteration based on score movement.
10. Repeat until interrupted.

## Phase Plan

### Phase 1: Trading Basics Foundation
Goal: build the minimum ontology of trading concepts from TTrades.

Deliverables:
- `knowledge/trading_basics.md`
- `knowledge/modeling_strategy.md`
- baseline DB schema
- topic folders for:
  - expansion
  - consolidation
  - retracement
  - reversal
  - bias
  - protected_swings

### Phase 2: Expansion First
Goal: make expansion the first deterministic topic.

Deliverables:
- expansion rulebook
- example set
- chart markup attempts
- first scoring harness

### Phase 3: Pine Knowledge Base
Goal: learn official Pine constraints before code generation.

Deliverables:
- `knowledge/pine_basics.md`
- Pine implementation patterns:
  - state machines
  - arrays / UDT-backed structures
  - session handling
  - request limits
  - anti-repaint rules

### Phase 4: Indicator Specs
Goal: convert stable rulebooks into Pine-ready specs.

Deliverables:
- spec objects in `indicator_specs`
- a translation checklist from rulebook fields to Pine series logic

### Phase 4.5: Personalized Trader Data
Goal: capture how specific traders annotate and act on the same structural ideas.

Deliverables:
- `trader_profiles`
- `trader_annotations`
- benchmark cases with trader-specific decisions and outcomes

### Phase 5: Generation
Goal: generate actual Pine indicators only after the spec passes scoring thresholds.

Gate:
- no indicator generation if determinism or Pine translatability is below threshold

## First Scoring Thresholds
Suggested initial gates for a topic to be considered "indicator-ready":
- `grounding_score >= 0.80`
- `determinism_score >= 0.75`
- `visual_verification_score >= 0.60`
- `pine_translatability_score >= 0.75`
- `contradiction_penalty <= 2`

## First Practical Topic Order
Recommended sequence:
1. `expansion`
2. `protected_swings`
3. `bias`
4. `consolidation`
5. `retracement`
6. `reversal`
7. `execution confirmation`
8. `risk and targets`

This order matters because expansion without protected swings and bias is too discretionary to code well.

## What Not to Do
- Do not try to learn all of trading before storing anything.
- Do not write Pine directly from article prose.
- Do not let the loop modify the evaluator and the rulebook at the same time.
- Do not optimize for quantity of notes; optimize for explicit, testable rules.
- Do not treat every visual idea as codable. Some ideas should remain tagged as discretionary.
