# Findings

## Session Start
- Repository reset complete; only `.git` remains.
- We are rebuilding from zero around one initial bounded research topic: expansion range drawing.

## TTrades Education Center - Initial Curriculum Scan
- The site exposes a structured trading curriculum rather than isolated videos.
- The visible curriculum strongly clusters around:
  - phases of price
  - timeframe alignment
  - expansion
  - retracement
  - reversal
  - continuations
  - protected swings
  - stop loss / invalidation
  - candle closures
  - projections
  - daily bias and profiles
- The most relevant entries for the first loop are:
  - `Phases of Price - Part 2: Mastering Expansion for Strong Trend Trades`
  - `Aligning Candles for Expansion: How True Trends Actually Form`
  - `Mastering Top-Down Analysis: Aligning Multiple Timeframes for Expansion Trading`
  - `Protected Swings in Trading: How to Identify and Use Them for Entries & Continuations`
  - `Stop Loss Mastery - Using Protected Swings for Precise Invalidations`
  - `Understanding Wick Sizes, Reversals, and Expansion Candles in Price Action`
- This suggests the knowledge base should be organized as a concept graph, not just a flat list of indicators.

## Early Domain Structure Hypothesis
- Core market state: consolidation, expansion, retracement, reversal.
- Core alignment layer: higher timeframe bias, lower timeframe execution, candle alignment.
- Core structure layer: protected swing, invalidation, projection, continuation.
- Core execution layer: entry model, stop placement, target logic, session/profile context.

## Source-Grounded Expansion Rules from TTrades
- Expansion is defined as a one-sided trending move with large-range candles and shallow countertrend pullbacks.
- Expansion usually emerges after a smaller range:
  - after consolidation via breakout
  - after retracement via trend resumption
- Visual expansion signatures:
  - shallow pullbacks
  - protected swings forming along the move
  - opposing candles being respected as support/resistance
- Trading workflow for expansion:
  - establish higher-timeframe context
  - mark protected swings on the execution timeframe
  - wait for reaction at a point of interest
  - require candle closure confirmation
  - enter with trend, stop at the protected swing, target external liquidity
- Expansion is explicitly fractal across timeframe pairs.
- TTrades also teaches practical guards:
  - do not engage after long same-direction expansion without expecting a new phase
  - wait for external highs/lows to be taken after post-expansion consolidations

## Source-Grounded Protected Swing Rules
- A protected swing is a high/low expected to hold if trend continuation remains valid.
- Protected swings form after price interacts with an important level and then closes beyond the candle series that drove into that level.
- Two creation modes are emphasized:
  - liquidity sweep based
  - fair value gap based
- Protected swings are used for:
  - directional filtering
  - invalidation
  - stop placement
  - continuation tracking
- TTrades stop-loss logic is structural rather than fixed-distance:
  - bullish stop under protected low
  - bearish stop above protected high
  - trail with newly formed protected swings

## Source-Grounded Bias and Timeframe Rules
- Bias is top-down and should not be predicted from the execution chart alone.
- Timeframe alignment is a prerequisite for high-probability expansion trading.
- Candle body and wick behavior are treated as evidence for whether a timeframe supports expansion.
- Lower-timeframe execution should wait for higher-timeframe intent to align, not fight it.
- `Easy Daily Bias` reframes each day as a continuation day or reversal day.
- `Next Day Model` makes that more mechanical:
  - close outside the previous candle range -> continuation bias
  - sweep and close back inside -> reversal bias
- `Easy Daily Bias` also introduces equilibrium of the previous day range as the continuation anchor.
- `Understanding Wick Sizes, Reversals, and Expansion Candles in Price Action` adds a target-selection filter:
  - small opposing run/wick -> expansion potential
  - large opposing run/wick -> reversion toward the open or nearby liquidity
- These pages together make `bias` codifiable as a state machine rather than a loose narrative.

## Corpus Baseline Direction
- The Education Center is large enough that manual page-by-page research will not scale.
- A proper baseline should include:
  - a discovered source manifest,
  - article and embedded-media registration,
  - durable rulebooks for the core concepts,
  - and trader-annotation exports for future local embedding and training workflows.

## Source / Topic / Model Structure Update
- `sources.topic_hint` was too weak as the only way to connect corpus items to the research graph.
- The repo now has explicit normalized link tables for:
  - `source_topics`
  - `source_trade_models`
  - `trade_model_topic_requirements`
- This makes the graph answer three different questions cleanly:
  - which sources support a topic,
  - which sources relate directly to a trade model,
  - and which topics a trade model depends on directly versus transitively.
- Topic and trade-model aliases are now stored explicitly so hints like `risk`, `alignment`, and `fractal_model` can resolve into the canonical research graph.

## Corpus Ingestion Update
- The core concept article set now has 28 local `page_markdown` artifacts under `artifacts/ttrades/pages/`.
- The markdown extractor is correctly targeting the Elementor post-content container rather than pulling related-post noise.
- After re-importing the manifests into the normalized link tables, the SQLite baseline expanded to:
  - 640 total sources
  - 674 source artifacts
  - 288 source-topic links
  - 56 source-trade-model links
- The source count is much larger than the original core-only snapshot because the broader manifest import preserves embedded media and asset URLs across the Education Center, not just the first 28 pages.

## Reversal Topic Baseline
- `reversal` is no longer only a planned node in the graph; it now has a first rulebook, examples, and open questions.
- The initial reversal score is:
  - `weighted_score = 0.7862`
  - `determinism_score = 0.7375`
  - `pine_translatability_score = 0.7000`
- This is good enough for a baseline but still clearly behind `bias`, `expansion`, and `protected_swings`, which is consistent with reversal logic still relying on less-formalized CISD, wick, and sequence rules.

## Portability / Framework Layer Update
- The project now separates:
  - canonical topics and trade models
  - framework-scoped vocabulary
  - source-to-framework membership
- This keeps the core ontology reusable for adjacent educators instead of baking TTrades phrasing into the graph itself.
- The first three frameworks are:
  - `canonical_price_action`
  - `ttrades_curriculum`
  - `tradingview_reference`
- Framework-term matching now uses token boundaries, which prevents short teacher-native terms such as `eq` from falsely matching unrelated words.
- The old teacher-named `ttrades_fractal_model` has been canonicalized into `fractal_closure_model`; the stale teacher-named row is archived rather than left active.

## Coverage Update After Framework Matching
- Current normalized coverage is now:
  - 541 `source_topics` links
  - 282 `source_trade_models` links
- Those totals break down as:
  - `source_topics`
    - 222 `primary_hint`
    - 206 `embedded_parent_category`
    - 113 `framework_term`
  - `source_trade_models`
    - 55 `primary_hint`
    - 51 `embedded_parent_category`
    - 176 `framework_term`
- This is a better fit for the user's goal because dependency reporting is now anchored to canonical topics and models while still retaining source-family language.

## Continuation Topic Baseline
- `continuation` now has a first rulebook, examples, and open questions.
- The initial continuation score is:
  - `weighted_score = 0.9175`
  - `determinism_score = 0.8416`
  - `pine_translatability_score = 0.8600`
  - `contradiction_penalty = 0`
- This score is materially stronger than the current reversal baseline, which suggests the first-pass continuation rules are already close to indicator-ready once anchor ranking and continuation-failure filters are tightened further.

## Retracement Topic Baseline
- `retracement` now has a first rulebook, examples, and open questions.
- The initial retracement score is:
  - `weighted_score = 0.9194`
  - `determinism_score = 0.8812`
  - `pine_translatability_score = 0.8200`
  - `contradiction_penalty = 0`
- This is currently the strongest phase baseline in the repo, which makes sense because the source material defines retracement cleanly as a slow, shallow countertrend pullback with explicit protected-swing failure criteria.

## Trade-Model Dependency Update
- `continuation_entry_model` no longer leaves retracement context implicit.
- Its direct topics are now:
  - `continuation`
  - `expansion`
  - `invalidation`
  - `protected_swings`
  - `consolidation`
  - `equilibrium`
  - `retracement`
- Its resolved requirement set now spans:
  - `continuation`
  - `equilibrium`
  - `expansion`
  - `invalidation`
  - `protected_swings`
  - `retracement`
  - `bias`
  - `candle_3_closure`
  - `reversal`
  - `top_down_alignment`
  - `wick_logic`
- This is closer to the intended data model: topics describe concepts, trade models describe how concepts are combined, and dependency closure makes those relationships queryable without hard-coding one educator’s naming scheme.

## Consolidation Topic Baseline
- `consolidation` now has a first rulebook, examples, and open questions.
- The initial consolidation score is:
  - `weighted_score = 0.9299`
  - `determinism_score = 0.8662`
  - `pine_translatability_score = 0.8800`
  - `contradiction_penalty = 0`
- This is the strongest phase baseline so far, which fits the source material: consolidation is described with a compact rule set of internal range, wait for sweep or clean breakout, use equilibrium as the middle, and avoid forcing trades inside unresolved chop.

## Consolidation Dependency Update
- `consolidation` now depends explicitly on:
  - `bias`
  - `equilibrium`
  - `protected_swings`
- `daily_profile_models` now carry explicit consolidation context alongside bias and wick logic, which better matches seek-and-destroy and New York manipulation materials.
- `trade_model_topic_requirements` increased to `82`, reflecting the more complete phase-to-model closure after adding both retracement and consolidation context to the graph.

## Teacher-Style Modeling Update
- The repo no longer has to treat teacher-specific execution as loose notes layered on top of canonical topics.
- `trader_profiles` can now act as explicit execution-style bundles that attach to:
  - source frameworks
  - canonical trade models
  - emphasized topics
- Individual trader annotations can now also link to the exact trade model being executed, which is important for future indicator or imitation-style datasets.
- This keeps the ontology clean:
  - topics describe concepts,

## Model-Training Surface Update
- The repo now exports a model-ready supervised surface from the same durable annotation graph instead of treating the future neural layer as a vague later step.
- `results/model_training_surface.jsonl` contains one row per annotation-to-trade-model link, not one row per source article or one row per topic.
- The current exported surface is still tiny:
  - `11` example rows
  - `9` unique chart cases
  - `6` distinct trade-model labels
  - only `2` explicit outcome labels
- This is enough to define the training problem honestly, but not enough to train a credible classifier.
- The new gating report in `results/model_training_report.json` now makes that explicit:
  - multi-class trade-model classification is not ready
  - relation-type classification is not ready
  - the first stand-aside / `no_trade` filter is not ready
- The cheapest narrow-task path is now visible too:
  - `continuation_entry_model`, `daily_bias_framework`, `daily_profile_models`, `fractal_closure_model`, and `reversal_sequence_model` each need `3` more positive labeled cases to reach the first one-vs-rest baseline threshold
- This is the right shape for a rules-first hybrid system:
  - rulebooks and draft specs define the structure
  - annotations define the labels
  - the model layer only comes in after the report shows enough data to justify it
  - trade models describe reusable execution logic,
  - teacher profiles describe how a specific educator combines and prioritizes those models.

## Scenario Contract Accounting Update
- The original scenario harness had an honesty bug:
  - new labeled cases without explicit `SCENARIO_EXPECTATIONS` would have received free `1.0` concept coverage if the understanding report were regenerated.
- That is now fixed.
- `scripts/export_understanding_report.py` now marks those links as:
  - `contract_defined = false`
  - `scenario_score = null`
  - `grade = ungraded`
- Five continuation-related scenario contracts were then added, and the legacy expansion baseline was restored to the durable manifest.
- The current understanding report now shows:
  - `15` graded scenario links
  - `scenario_average = 0.9193`
  - `scenario_total_count = 16`
  - `scenario_contract_coverage = 0.9375`
  - only `1` current case-model link remains ungraded: `ttrades_expansion_curriculum_baseline_v1` linked to `phases_of_price_framework`
- This is important because the user explicitly wanted harder scenario-based proof of understanding, not silent inflation from unlabeled contracts.

## Staged Neural-Readiness Gate
- The repo now has a dedicated staged readiness report at `results/neural_net_readiness_report.json`.
- It separates four different claims that were previously being conflated:
  - Karpathy-style autoresearch loop maturity
  - narrow offline ML readiness
  - real-time neural assist readiness
  - real-time neural execution readiness
- The current grades are:
  - autoresearch loop = `A`
  - narrow offline ML = `B`
  - real-time neural assist = `C`
  - real-time neural execution = `D`
- The key insight is that the repo is already strong at research-loop structure, but still weak at live-decision readiness.
- The report makes that separation explicit by hard-capping live stages when:
  - no runtime or paper-trade harness exists
  - all indicator specs are still `draft`
  - too few trade-model scorers are baseline-ready
  - multiclass trade-model and relation-type tasks are still under-labeled

## Current Readiness Blockers
- `results/model_training_report.json` now shows:
  - `16` example rows
  - `15` explicit outcome labels
  - `no_trade_filter = ready`
  - only `continuation_entry_model` is ready for one-vs-rest scoring among the indicator-ready models
- `trade_model_classification` is still blocked by:
  - only `16` rows instead of `25`
  - smallest class size `1` instead of `5`
- `relation_type_classification` is blocked by the same data scarcity.
- The label space is also still slightly messy for the first neural layer:
  - `phases_of_price_framework` appears in the training labels
  - but it does not belong to the current indicator-spec set
- There is still no live runtime, paper-trade harness, or backtest harness in the current repo tree, so any real-time neural claim would be structurally dishonest even if the labels were stronger.

## Indicator Candidate Bridge
- The repo now materializes teacher-style indicator candidates from `trader_profile_trade_models` rows that are marked `indicator_ready = 1`.
- This uses the existing `indicator_specs` table rather than inventing a second indicator-candidate store.
- The current teacher-style candidates are expected to come from:
  - `ttrades_curriculum` + `daily_bias_framework`
  - `ttrades_curriculum` + `continuation_entry_model`
  - `ttrades_curriculum` + `daily_profile_models`
  - `ttrades_curriculum` + `fractal_closure_model`
  - `ttrades_curriculum` + `reversal_sequence_model`
- This is the first direct bridge from teacher-style execution modeling into Pine-oriented build artifacts.

## Teacher-Style Annotation Evidence Update
- The teacher-style layer now has a durable annotation-case manifest at `data/trader_annotation_cases.json`, which means baseline examples for an educator can be versioned and reimported instead of recreated manually.
- Four new baseline cases were imported for:
  - `daily_bias_framework`
  - `continuation_entry_model`
- Together with the earlier expansion baseline, the repo now has:
  - `5` trader annotation cases
  - `5` annotation-to-trade-model links
- The indicator candidates are no longer evidence-empty:
  - `ttrades_curriculum__daily_bias_framework` now has `annotation_link_count = 2`
  - `ttrades_curriculum__continuation_entry_model` now has `annotation_link_count = 2`
- This matters because the next Pine translation step can now be grounded in:
  - canonical concept dependencies,
  - teacher-style model selection,
  - and concrete labeled examples of how that teacher executes the model.

## Composite Case Modeling Update
- The durable annotation importer now supports `trade_model_links`, not just a flat `trade_models` list.
- This is important because a single teacher-style chart case often demonstrates more than one layer at once:
  - session profile context
  - execution model
  - confirmation framework
- The repo now has two explicit composite cases:
  - `ttrades_new_york_reversal_profile_baseline_v1`
    - `daily_profile_models`
    - `reversal_sequence_model`
  - `ttrades_candle_2_closure_reversal_baseline_v1`
    - `fractal_closure_model`
    - `reversal_sequence_model`
- After importing the expanded manifest, the teacher-style layer now covers all active trade models with at least one labeled case:
  - `daily_bias_framework = 2`
  - `continuation_entry_model = 2`
  - `daily_profile_models = 2`
  - `fractal_closure_model = 2`
  - `reversal_sequence_model = 2`
  - `phases_of_price_framework = 1`
- This is a stronger representation of the user's original requirement:
  - keep concepts separate,
  - keep teacher execution styles composable,
  - and let indicator design emerge from how a teacher combines models in execution, not from one collapsed monolith.

## New Topic Baselines
- `daily_profiles`, `candle_2_closure`, and `candle_3_closure` are now active topics with first-pass rulebooks, examples, and open questions.
- Their initial scores are:
  - `daily_profiles`
    - `weighted_score = 0.9347`
    - `determinism_score = 0.8822`
    - `pine_translatability_score = 0.8800`
  - `candle_2_closure`
    - `weighted_score = 0.8977`
    - `determinism_score = 0.8256`
    - `pine_translatability_score = 0.8000`
  - `candle_3_closure`
    - `weighted_score = 0.8775`
    - `determinism_score = 0.8166`
    - `pine_translatability_score = 0.7300`
- `daily_profiles` was already strong as a codified context layer before `wick_logic` and `top_down_alignment` were formalized; that earlier blocker is now removed.
- `candle_2_closure` and `candle_3_closure` give the fractal model the explicit closure-topic grounding that had been missing from the earlier graph.

## Fractal Indicator Promotion
- `fractal_closure_model` is now promoted to `indicator_ready = true` in the teacher-style profile graph.
- The promotion is supported by:
  - `2` labeled teacher-style annotation links,
  - explicit `candle_2_closure` and `candle_3_closure` rulebooks,
  - and a stronger trade-model dependency closure around the fractal sequence.
- The materializer needed one small architectural fix before that promotion was safe:
  - indicator candidates now choose a `core` direct topic as their primary topic anchor when one exists,
  - which prevents context topics like `bias` from incorrectly becoming the lead topic for a closure-centric model.
- The exported candidate set now contains:
  - `ttrades_curriculum__daily_bias_framework`
  - `ttrades_curriculum__continuation_entry_model`
  - `ttrades_curriculum__fractal_closure_model`
- The new fractal candidate is anchored to `candle_2_closure`, not the generic `bias` topic, which is a much better fit for later Pine-spec generation.

## Support Topic Baselines
- `equilibrium`, `wick_logic`, and `top_down_alignment` are now active topics with first-pass rulebooks, examples, and open questions.
- Their initial scores are:
  - `equilibrium`
    - `weighted_score = 0.9114`
    - `determinism_score = 0.8631`
    - `pine_translatability_score = 0.8100`
  - `wick_logic`
    - `weighted_score = 0.9235`
    - `determinism_score = 0.8616`
    - `pine_translatability_score = 0.8600`
  - `top_down_alignment`
    - `weighted_score = 0.9184`
    - `determinism_score = 0.8531`
    - `pine_translatability_score = 0.8500`
- This matters because several existing trade models were already depending on these topics transitively, so the graph is now less reliant on planned placeholders and more grounded in actual rulebooks.

## Daily Profile Promotion
- `daily_profile_models` is now promoted to `indicator_ready = true`.
- The promotion is justified by:
  - `2` labeled teacher-style annotation links,
  - an active `daily_profiles` core topic with a `0.9347` score,
  - and now-active supporting topics for `wick_logic` and `top_down_alignment`.
- The exported candidate set now contains:
  - `ttrades_curriculum__daily_bias_framework`
  - `ttrades_curriculum__continuation_entry_model`
  - `ttrades_curriculum__daily_profile_models`
  - `ttrades_curriculum__fractal_closure_model`
- The new daily-profile candidate anchors to `daily_profiles`, which is the correct core topic for a session-context indicator.
- At that stage, `reversal_sequence_model` was still not promoted because:
  - `reversal` remains the weakest major topic baseline at `0.7862`,
  - and `invalidation` is still a planned dependency rather than an active rulebook-backed topic.

## Invalidation Baseline
- `invalidation` now has an active rulebook, examples, and open questions.
- Its initial score is:
  - `weighted_score = 0.8940`
  - `determinism_score = 0.7966`
  - `pine_translatability_score = 0.8200`
  - `contradiction_penalty = 0`
- This matters because reversal execution is no longer relying on an implicit stop-placement concept; the risk layer is now rulebook-backed and queryable like the rest of the graph.

## Reversal Tightening
- `reversal` has now been materially tightened rather than simply re-labeled as ready.
- The updated rulebook now:
  - makes reversal anchors explicit as previous-day, previous-week, session, or tracked swing liquidity references,
  - delegates wick midpoint behavior to `wick_logic`,
  - delegates zone quality and alignment burden to the higher-timeframe context instead of restating it locally,
  - and narrows the reversal-sequence model to a first-pass codable subset of sweep, reclaim, CISD, and entry-location confirmation.
- The tightened score is now:
  - `weighted_score = 0.9389`
  - `determinism_score = 0.8962`
  - `pine_translatability_score = 0.8800`
  - `contradiction_penalty = 0`
- This is a major change from the earlier `0.7862` baseline and removes the main reason `reversal_sequence_model` had been held back.

## Reversal Indicator Promotion
- `reversal_sequence_model` is now promoted to `indicator_ready = true`.
- The promotion is supported by:
  - `2` labeled teacher-style annotation links,
  - an active `invalidation` topic with a `0.8940` score,
  - and a tightened `reversal` topic with a `0.9389` score plus active `wick_logic` and `top_down_alignment` support.
- The exported candidate set now contains:
  - `ttrades_curriculum__daily_bias_framework`
  - `ttrades_curriculum__continuation_entry_model`
  - `ttrades_curriculum__daily_profile_models`
  - `ttrades_curriculum__fractal_closure_model`
  - `ttrades_curriculum__reversal_sequence_model`
- The new reversal candidate anchors to `reversal`, which is the correct core topic for the execution model.

## Reversal Pine Draft
- `ttrades_curriculum__reversal_sequence_model` now has a first-pass Pine draft spec.
- The draft artifact lives at `results/indicator_specs/reversal_sequence_model.json`.
- The draft adds:
  - explicit input groups for sessions, anchor selection, confirmation proxies, and risk mode,
  - a finite-state reversal sequence model from sweep through entry-ready or invalidated,
  - a Pine program outline, derived-series inventory, signal pipeline, visuals, alerts, and acceptance checks,
  - and explicit provisional proxies for reclaim, CISD, and aggressive body invalidation.
- The indicator-spec layer now contains:
  - `4` rows at `candidate`
  - `1` row at `draft`
- Candidate rematerialization was verified after the draft build:
  - rerunning `scripts/materialize_indicator_candidates.py` keeps the reversal spec at `draft`,
  - and preserves draft-only fields such as `spec_version`, `translation_stage`, `artifact_path`, and `implementation_summary`.
- The main remaining implementation uncertainty is no longer graph readiness; it is the quality of the first-pass machine proxies for CISD, reclaim/inversion, and aggressive body invalidation.

## Daily Bias Pine Draft
- `ttrades_curriculum__daily_bias_framework` now also has a first-pass Pine draft spec.
- The draft artifact lives at `results/indicator_specs/daily_bias_framework.json`.
- The daily-bias draft is intentionally scoped as a bias and reference overlay, not a full entry engine.
- The draft adds:
  - explicit reference-range inputs for previous-day versus previous-candle framing,
  - wick-based expectation filters and equilibrium hold/fail logic,
  - a finite-state bias model for continuation, reversal watch, reversal confirmed, and exhausted conditions,
  - and provisional lower-timeframe confirmation, wick-ratio, and equilibrium-tolerance proxies.
- The indicator-spec layer now contains:
  - `3` rows at `candidate`
  - `2` rows at `draft`
- Candidate rematerialization was re-verified after building the daily-bias draft:
  - rerunning `scripts/materialize_indicator_candidates.py` keeps both `daily_bias_framework` and `reversal_sequence_model` at `draft`,
  - and `results/topic_model_report.json` now exports both draft rows with `spec_version = 2` and `translation_stage = draft`.
- The main open questions for the daily-bias draft are the numeric wick threshold, the equilibrium tolerance band, and the strictest useful lower-timeframe confirmation proxy.

## Fractal Closure Pine Draft
- `ttrades_curriculum__fractal_closure_model` now also has a first-pass Pine draft spec.
- The draft artifact lives at `results/indicator_specs/fractal_closure_model.json`.
- The fractal draft is intentionally scoped as a sequence overlay:
  - point of interest first,
  - then Candle 2 or Candle 3 closure detection,
  - then midpoint or equilibrium refinement,
  - then lower-timeframe displacement confirmation.
- The draft adds:
  - explicit inputs for point-of-interest ranking, Candle 2 and Candle 3 detection, midpoint tolerance, equilibrium-half tolerance, and lower-timeframe displacement,
  - a finite-state model covering `poi_ready`, `candle2_confirmed`, `candle3_confirmed`, `refinement_ready`, `entry_ready`, and `invalidated`,
  - and provisional machine proxies for point-of-interest ranking, Candle 3 body engulfing, midpoint tolerance, and displacement confirmation.
- The indicator-spec layer now contains:
  - `2` rows at `candidate`
  - `3` rows at `draft`
- Candidate rematerialization was re-verified after the fractal draft build:
  - rerunning `scripts/materialize_indicator_candidates.py` keeps `daily_bias_framework`, `fractal_closure_model`, and `reversal_sequence_model` at `draft`,
  - and `results/topic_model_report.json` now exports all three draft rows with `spec_version = 2` and `translation_stage = draft`.
- The main open questions for the fractal draft are the numeric Candle 3 engulf threshold, the midpoint and correct-half tolerances, the fallback point-of-interest ranking rule, and the minimum useful lower-timeframe displacement strength.

## Daily Profile Pine Draft
- `ttrades_curriculum__daily_profile_models` now also has a first-pass Pine draft spec.
- The draft artifact lives at `results/indicator_specs/daily_profile_models.json`.
- The daily-profile draft is intentionally scoped as a session-profile overlay:
  - build Asia, London, and New York ranges,
  - classify London reversal/New York continuation, New York manipulation, New York reversal, or seek-and-destroy,
  - then require provisional session-shift confirmation before calling the profile confirmed.
- The draft adds:
  - explicit session inputs for Asia, London, and New York windows,
  - a state model for the four main profile branches plus breakout override,
  - and provisional machine proxies for session CISD, London range completion, overlap ranking, and seek-and-destroy rotation.
- The indicator-spec layer now contains:
  - `1` row at `candidate`
  - `4` rows at `draft`
- Candidate rematerialization was re-verified after the daily-profile draft build:
  - rerunning `scripts/materialize_indicator_candidates.py` keeps `daily_bias_framework`, `daily_profile_models`, `fractal_closure_model`, and `reversal_sequence_model` at `draft`,
  - and `results/topic_model_report.json` now exports all four draft rows with `spec_version = 2` and `translation_stage = draft`.
- The main open questions for the daily-profile draft are the London completion threshold, overlap ranking when profiles partially collide, and the strictest useful session-level CISD proxy.

## Continuation Entry Pine Draft
- `ttrades_curriculum__continuation_entry_model` now also has a first-pass Pine draft spec.
- The draft artifact lives at `results/indicator_specs/continuation_entry_model.json`.
- The continuation-entry draft is intentionally scoped as a continuation execution overlay:
  - require higher-timeframe continuation bias and open objective context,
  - wait for a controlled retracement or breakout-resolution anchor,
  - then confirm with continuation CISD, protected swing, and failure or exhaustion filters before showing entry-ready state.
- The draft adds:
  - explicit anchor-family inputs for equilibrium, order block, fair value gap, breaker, and range-resolution paths,
  - a continuation state machine from context-ready to entry-ready or exhausted,
  - and provisional machine proxies for anchor ranking, retracement depth, continuation CISD, and higher-timeframe objective-open filtering.
- The continuation draft was then tightened with explicit first-pass machine rules:
  - anchor ranking now uses a concrete score table with `4` as the minimum usable anchor score and `6` as the preferred score,
  - retracements are now classed as shallow at `<= 0.50`, moderate at `<= 0.62`, deep above that while structure survives, and invalid once protected swing or wrong-side equilibrium failure appears,
  - equilibrium respect now carries a provisional `5%` tolerance band around the midpoint,
  - and objective-open filtering now blocks fresh continuation entries once the selected first target is already complete.
- The indicator-spec layer now contains:
  - `0` rows at `candidate`
  - `5` rows at `draft`
- Candidate rematerialization was re-verified after the continuation draft build:
  - rerunning `scripts/materialize_indicator_candidates.py` keeps `continuation_entry_model`, `daily_bias_framework`, `daily_profile_models`, `fractal_closure_model`, and `reversal_sequence_model` at `draft`,
  - and `results/topic_model_report.json` now exports all five draft rows with `spec_version = 2` and `translation_stage = draft`.
- The remaining open questions for the continuation draft are now narrower:
  - what displacement threshold should upgrade the optional continuation CISD mode beyond the simpler close-through proxy,
  - and how much SMT evidence should upgrade breaker-block or range-resolution anchors relative to direct sweep evidence.

## Understanding Report
- The repo now has a dedicated understanding harness at `scripts/export_understanding_report.py`.
- It produces `results/understanding_report.json` with two layers:
  - topic understanding from rulebook grounding, determinism, visual verification, and Pine translatability,
  - indicator-spec understanding from scope fidelity, rule-reference validity, implementation richness, machine-checkability, and ambiguity awareness.
- The first generated report currently scores the repo at:
  - topic average = `0.9000`
  - indicator-spec average = `0.9567`
  - overall understanding score = `0.9312`
  - grade = `A`
- The current weakest measured topics are:
  - `bias`
  - `expansion`
  - `protected_swings`
- The current weakest measured indicator draft is:
  - `ttrades_curriculum__reversal_sequence_model`
  - its weakest dimension is machine-checkability rather than rule-reference validity or scope coverage.

## Historical Backtesting Readiness Gate
- The repo now has a dedicated historical-first readiness harness at `scripts/export_backtesting_readiness_report.py`.
- It produces `results/backtesting_readiness_report.json` and makes the current project priority explicit:
  - historical backtesting understanding before any real-time trading work
  - real-time neural assist intentionally deferred
  - real-time neural execution intentionally deferred
- The current staged grades are:
  - historical backtesting research foundation = `A`
  - manual chart replay understanding = `A-`
  - rules-based historical backtesting = `B-`
  - model-assisted historical backtesting = `C`
- This is the most useful current distinction in the repo:
  - the research corpus, rulebooks, specs, and labeled cases are already strong enough for serious manual replay work,
  - but they are not yet strong enough for honest repeatable structured backtests.
- The manual-replay stage is genuinely ready because:
  - overall measured understanding is still `0.9256` (`A-`)
  - rules-backtestability across current specs averages `0.8067`
  - anti-lookahead discipline already averages `1.0`
  - case-level decision, reason, and entry-logic coverage are all `0.9286`
- The structured historical stages are still blocked by infrastructure and execution realism rather than by missing ontology:
  - no repeatable historical replay or backtest harness exists in the repo
  - no spread, slippage, commission, or other transaction-cost model is encoded
  - all five indicator specs remain `draft`
  - the tracked TTrades backtesting primer is still missing a local text artifact
- The label space is also still constrained for model-assisted historical testing:
  - only `continuation_entry_model` is currently one-vs-rest ready
  - the training surface still includes `phases_of_price_framework`, which has no matching indicator spec
  - scenario contracts are strong but not fully closed yet at `15 / 16`
- The clean next move is now obvious:
  - use the current rules and cases for bar-by-bar manual replay worksheets,
  - then add a minimal next-bar historical harness with explicit entry, stop, target, session, and cost assumptions,
  - and only after that consider narrow model-assisted historical scoring.

## TTFM Multimodal Learning Design
- The agreed next learning lane is now explicit:
  - `TTFM` means `TTrades fractal model`
  - the first model target is component mapping, not live trading or final trade prediction
  - screenshots are first-class training inputs from day one
  - multi-timeframe analysis is core to the case schema, not optional context
- The new design is captured in `knowledge/ttfm_multimodal_learning_loop.md`.
- The design locks in:
  - hybrid labeling from anchor cases plus weak labels derived from rules, specs, docs, videos, and historical structure
  - a `3` to `5` checkpoint historical case packet shape
  - `visual mismatch + rules mismatch` as the mistake signal
  - autonomous write-back only to labels, findings, draft specs, and `open_questions`
  - per-loop grading so bad training passes can be discarded rather than silently accepted

## TTFM Multimodal Implementation Slice
- The first concrete implementation slice now exists in the repo:
  - `data/ttfm_component_taxonomy.json`
  - `scripts/export_ttfm_case_packets.py`
  - `scripts/export_ttfm_training_loop_report.py`
  - `results/ttfm_case_packets.json`
  - `results/ttfm_training_loop_report.json`
- `ttfm` is now also an active framework in the shared graph, so the fractal-model layer is no longer only a doc-level idea.
- The current TTFM bootstrap export is intentionally structural rather than impressive:
  - `14` historical case packets
  - `70` checkpoint slots
  - no screenshot attachments yet
  - no trained model metrics yet
- The first bootstrap loop grade is therefore `D` rather than a false green light.
- That is the correct signal:
  - the architecture exists,
  - the ontology exists,
  - the case-packet export exists,
  - but the actual screenshot corpus and model-vs-anchor disagreement loop do not exist yet.

## Karpathy Autoresearch Principles to Reuse
- Keep the repo intentionally small.
- Keep the evaluation harness fixed and difficult to game.
- Restrict each loop to a small editable surface area.
- Run short, comparable iterations instead of huge all-at-once refactors.
- Log every attempt with keep/discard/crash style outcomes.
- Advance only when the measured result improves.

## Autoresearch Adaptation for This Project
- Replace model-loss optimization with knowledge-quality optimization.
- The primary score should reward:
  - source grounding
  - rule determinism
  - contradiction reduction
  - Pine translatability
  - visual verification coverage
- Instead of one mutable `train.py`, use one mutable active rulebook per topic.
- First active topic should be `expansion`.

## Open Research Questions
- What are the canonical anchors of an expansion range in TTrades terminology?
- When does an expansion begin, continue, pause, or end?
- How are protected swings tied to expansion maintenance and invalidation?
- What parts are objective enough for code versus still discretionary?
