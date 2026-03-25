# Task Plan

## Goal
Build a fresh research-first baseline for learning trading basics from the TTrades Education Center, formalizing them into durable rules and data structures, and then using that knowledge base to support high-quality Pine indicator design.

## Current Understanding
- The repository has been intentionally reset to an empty baseline.
- The first research domain is TTrades trading basics, with expansion as the first detailed subtopic.
- The workflow should use Playwriter for browser-side research and drawing practice.
- The output should improve conceptual understanding, backend determinism, and Pine translatability.
- The project should evolve toward a rules-based, database-backed indicator research system.
- The corpus is now large enough that explicit source-to-topic and source-to-model links are required; `topic_hint` alone is no longer sufficient.
- The graph now needs to stay portable across similar trading curricula, so canonical topics and models should remain generic while educator-specific vocabulary is stored separately.
- Teacher execution styles should be modeled as first-class profile bundles that can later support indicator design from a specific educator's trading style.
- Indicator generation should now flow through teacher-style trade models instead of jumping directly from topic prose to Pine ideas.
- We now have fourteen scored topic baselines: `bias`, `expansion`, `protected_swings`, `reversal`, `continuation`, `retracement`, `consolidation`, `daily_profiles`, `candle_2_closure`, `candle_3_closure`, `equilibrium`, `wick_logic`, `top_down_alignment`, and `invalidation`.
- We now also have a durable teacher-style annotation-case importer and nine exported annotation rows, so indicator candidates can be evaluated against labeled execution examples rather than source coverage alone.
- Durable cases can now model composite teacher-style executions by linking one chart case to multiple trade models with distinct relation types.
- `fractal_closure_model` has now crossed into the indicator-ready tier, bringing the current exported indicator-candidate count to `3`.
- `daily_profile_models` has now also crossed into the indicator-ready tier, bringing the current exported indicator-candidate count to `4`.
- `reversal_sequence_model` has now also crossed into the indicator-ready tier after its direct-topic stack was fully formalized, bringing the current exported indicator-candidate count to `5`.
- The indicator-spec layer now contains `5` total specs: `0` remain `candidate`, while `ttrades_curriculum__continuation_entry_model`, `ttrades_curriculum__daily_bias_framework`, `ttrades_curriculum__daily_profile_models`, `ttrades_curriculum__fractal_closure_model`, and `ttrades_curriculum__reversal_sequence_model` are now preserved first-pass `draft` specs with their own artifact files.
- The repo now also exports a model-training surface from annotation-to-trade-model links, so the future neural layer can be evaluated against a real supervised dataset instead of an abstract idea.
- The repo now also exports a staged neural-readiness report that separates autoresearch maturity from narrow offline ML, real-time assist, and real-time execution claims.
- The repo now also exports a historical-backtesting readiness report that separates manual replay understanding from rules-based and model-assisted historical testing.
- The agreed next architecture is now a dedicated TTFM multimodal historical-learning lane with screenshot-first case packets, hybrid labeling, autonomous mistake review, and per-loop grading.
- The first implementation slice of that TTFM lane now exists:
  - `ttfm` is an active framework in the graph
  - a component taxonomy exists
  - timeframe-aware case packets can be exported
  - each loop can be graded with a fixed scorecard and verdict
- The current staged grades are:
  - autoresearch loop = `A`
  - narrow offline ML = `B`
  - real-time neural assist = `C`
  - real-time neural execution = `D`
- The current historical-first grades are:
  - historical backtesting research foundation = `A`
  - manual chart replay understanding = `A-`
  - rules-based historical backtesting = `B-`
  - model-assisted historical backtesting = `C`
- The understanding harness now treats missing scenario expectation contracts as `ungraded` instead of silently awarding scenario credit.
- Scenario contract coverage has now been raised to `15 / 16`, and the only remaining ungraded link is the `phases_of_price_framework` expansion baseline.
- Real-time trading remains explicitly deferred; the clean path is manual replay first, then structured historical backtests, then only later any narrow model-assisted evaluation.

## Assumptions
- The relevant TTrades lessons are publicly accessible through the Education Center.
- We can use article pages plus linked videos as the primary research corpus.
- The first scaffold should be minimal: schema, research notes, evaluation plan, and a few scripts are enough.
- Pine is a later target, but the first codification and evaluation utilities can be written in Python.

## Phases
- [completed] Extract the TTrades basics curriculum and define the knowledge graph for trading concepts.
- [completed] Adapt Karpathy's autoresearch loop to a trading-rule and Pine-spec use case.
- [in_progress] Practice chart/range interpretation in-browser and capture ambiguities.
- [completed] Design deterministic rules, evaluation metrics, and database structures.
- [completed] Create the minimal backend baseline for storing sources, rules, visual attempts, and indicator specs.
- [in_progress] Summarize what is deterministic now versus what still needs research.
- [completed] Separate canonical topic/model structure from framework-scoped source vocabulary so adjacent curricula can be ingested later.
- [completed] Add a teacher-style layer so profiles can map onto canonical frameworks, trade models, and emphasized topics without collapsing the shared ontology.
- [completed] Bridge indicator-ready teacher-style models into concrete `indicator_specs` candidates for future Pine generation.
- [completed] Seed teacher-style annotation cases so indicator-ready models have explicit example coverage in the dataset.
- [completed] Expand annotation coverage for reversal, daily profiles, and fractal-closure logic so the full current teacher-style bundle has baseline labeled coverage.
- [completed] Decide which of the newly covered models are deterministic enough to promote into the next indicator-candidate tier without overstating readiness.
- [completed] Tighten `wick_logic`, `top_down_alignment`, and `equilibrium` so `daily_profile_models` and `reversal_sequence_model` can be judged on explicit context rules instead of partial proxies.
- [completed] Formalize `invalidation` so `reversal_sequence_model` can be judged on a complete direct-topic stack instead of a partially planned one.
- [completed] Tighten `reversal` and promote `reversal_sequence_model` only after its core, filter, and risk topics were all explicit and scored.
- [completed] Build a first-pass Pine draft for `reversal_sequence_model` and verify that indicator-candidate rematerialization preserves enriched `draft` specs instead of downgrading them back to plain candidates.
- [completed] Build a first-pass Pine draft for `daily_bias_framework` so the draft workflow covers both a bias overlay and a reversal sequence model, then verify both drafts survive candidate rematerialization.
- [completed] Build a first-pass Pine draft for `fractal_closure_model` so the draft workflow now covers a bias overlay, a closure-sequence model, and a reversal-sequence model, then verify all three drafts survive candidate rematerialization.
- [completed] Build a first-pass Pine draft for `daily_profile_models` so the draft workflow also covers the session-profile overlay path, then verify all four drafts survive candidate rematerialization.
- [completed] Build a first-pass Pine draft for `continuation_entry_model` so the draft workflow covers the final remaining teacher-style execution model, then verify all five drafts survive candidate rematerialization.
- [completed] Tighten the `continuation_entry_model` draft with explicit anchor scoring, retracement-depth bands, equilibrium tolerance, and target-completion gating so the newest execution draft is less narrative and more machine-checkable.
- [completed] Add an explicit understanding-evaluation harness so repo progress can be graded directly across topics and indicator specs instead of inferred from artifact count alone.
- [completed] Add a model-training surface export and readiness report so the hybrid rules-plus-neural path is grounded in explicit supervised examples and data sufficiency checks.
- [completed] Add a staged neural-readiness gate so "research loop is strong" can no longer be confused with "real-time neural trader is ready."
- [completed] Harden scenario grading so uncontracted case-model links are marked `ungraded` instead of receiving free scenario credit.
- [completed] Add a historical-backtesting readiness gate so manual replay understanding, rules-based backtests, and model-assisted backtests are graded before any live-trading discussion.
- [completed] Document the TTFM multimodal historical-learning design so implementation can proceed against a stable offline-first architecture instead of chat-only intent.
- [completed] Scaffold the first TTFM multimodal implementation lane with component taxonomy, case-packet export, graph framework entry, and graded training-loop reporting.

## Risks
- TTrades materials may remain partially discretionary even after transcription and visual review.
- Visual chart-drawing practice may reveal ambiguities that article text alone does not resolve.
- A weak evaluation metric would let the research loop optimize noise instead of determinism.
- Pine translation may fail if trading rules remain descriptive rather than machine-checkable.
- Indicator candidates can look healthier than they really are if source coverage rises faster than labeled case coverage, so the next loop should prioritize annotation density over adding more abstract graph nodes.
- Composite chart cases can become semantically messy if relation types are vague, so future expansions should keep `trade_model_links` roles tight and reusable.
- Context-heavy models should only be promoted once their supporting topics are active and scored, which is the standard now applied to `daily_profile_models`.
- The reversal draft can still outrun implementation quality if the CISD, reclaim/inversion, and aggressive body-invalidation proxies stay too narrative, so the current draft should be treated as a translation scaffold rather than production Pine completeness.
- The daily-bias draft still depends on provisional wick and equilibrium thresholds plus a provisional lower-timeframe confirmation proxy, so it should also be treated as a translation scaffold rather than a final execution script.
- The fractal-closure draft still depends on provisional point-of-interest ranking, Candle 3 engulf thresholds, midpoint and correct-half tolerances, and lower-timeframe displacement strength, so it should also be treated as a translation scaffold rather than a finished execution script.
- The daily-profile draft still depends on provisional session CISD, London completion, overlap ranking, and rotation thresholds, so it should also be treated as a translation scaffold rather than a finished profile engine.
- The continuation-entry draft is now materially tighter, but it still depends on provisional displacement thresholds for the stronger CISD mode plus unresolved SMT-weighting rules for continuation anchors, so it should still be treated as a translation scaffold rather than a finished execution engine.
- The new understanding harness gives a cleaner prioritization signal now: `bias`, `expansion`, and `protected_swings` are the weakest measured topics, and `reversal_sequence_model` is the weakest measured draft spec on machine-checkability.
- The refreshed training-surface report is better, but the label space is still too thin for broad modeling: `16` example rows exist, and only one indicator-ready trade model is currently one-vs-rest ready.
- Multi-class trade-model and relation-type prediction are both still under-labeled, so any live neural decision claim would be premature.
- One case-model link is still outside the strict scenario-contract net, which means the understanding harness is much better but not perfectly closed yet.
- There is still no runtime, backtest, or paper-trade harness in the current repo tree, which is a hard blocker for honest real-time neural-assist or neural-execution claims.
- There is also still no repeatable historical replay or backtest harness, so the repo is ready for manual replay learning but not for honest structured backtest claims.
- No spread, slippage, commission, or other transaction-cost assumptions are encoded yet, which would make any naive historical performance estimate misleading.
- The tracked TTrades backtesting methodology article still lacks a local text artifact, so the repo's historical-testing doctrine is not yet as corpus-grounded as the strategy rules themselves.
