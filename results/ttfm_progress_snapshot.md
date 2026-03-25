# TTFM Brain Workflow V2 Snapshot

Generated at: 2026-03-24T21:33:54.774509+00:00

## Corpus Coverage

- Active corpus videos: 121
- Delta vs prior run: 121
- Partition counts: {"educational_youtube": 106, "trade_review": 9, "unknown": 6}

## Daily Intake

- Video files scanned: 0
- Image files scanned: 0
- Trainable videos added: 0
- Queued videos: 0
- Trainable image rows: 0
- Review-only image rows: 0

## Embeddings

- Text embeddings: 1209 (ran)
- Visual embeddings: 75 (ran)

## Trainability

- Trainable rows: 55
- Blocked rows: 20
- Blocked reasons: {}

## Frozen Benchmark

- Benchmark rows: 33
- Winner: tie
- Challenger micro F1: 0.603
- Challenger precision/recall: 0.456 / 0.891
- Benchmark deltas: {"disagreement_count": 0, "exact_match_ratio": 0.0, "micro_f1": 0.0, "precision": 0.0, "recall": 0.0}

## Top Disagreement Cases

### youtube_candle_2_closure_foundation_visual_v1::confirmation
- Title: Candle 2 Closure: The Foundation of TTrades Fractal Model
- Checkpoint: confirmation
- Review status: ready_for_weak_training
- Active labels: candle_2_closure, candle_3_closure, equilibrium, fair_value_gap
- Screenshot: knowledge\ttfm_video_corpus\frames\candle_2_closure_foundation\confirmation_00165120.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/candle_2_closure_foundation/confirmation_00165120.wav
- Embedding excerpt: 
- Weak labels: candle_2_closure, candle_3_closure, equilibrium, fair_value_gap
- Predicted labels: liquidity_sweep, candle_3_closure, candle_2_closure, breaker, order_block, fair_value_gap, protected_swing, invalidation, point_of_interest, wick_logic, equilibrium
- Top probabilities: liquidity_sweep=0.853, candle_3_closure=0.807, candle_2_closure=0.801, breaker=0.737, order_block=0.680
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.364
- Disagreement count: 7

### youtube_easy_daily_bias_mechanical_framework_visual_v1::confirmation
- Title: Easy Daily Bias - Mechanical Framework
- Checkpoint: confirmation
- Review status: ready_for_weak_training
- Active labels: breaker, candle_2_closure, equilibrium, fair_value_gap, liquidity_sweep, order_block, protected_swing
- Screenshot: knowledge\ttfm_video_corpus\frames\easy_daily_bias_mechanical_framework\confirmation_00303480.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/easy_daily_bias_mechanical_framework/confirmation_00303480.wav
- Embedding excerpt: 
- Weak labels: breaker, candle_2_closure, equilibrium, fair_value_gap, liquidity_sweep, order_block, protected_swing
- Predicted labels: liquidity_sweep, breaker, order_block, fair_value_gap, candle_2_closure, candle_3_closure, invalidation, protected_swing, point_of_interest, wick_logic, equilibrium
- Top probabilities: liquidity_sweep=0.812, breaker=0.741, order_block=0.704, fair_value_gap=0.703, candle_2_closure=0.701
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.636
- Disagreement count: 4

### youtube_fractal_model_fundamentals_visual_v1::confirmation
- Title: TTrades Playbook | Fractal Model Fundamentals (TTFM)
- Checkpoint: confirmation
- Review status: ready_for_weak_training
- Active labels: invalidation, liquidity_sweep, order_block
- Screenshot: knowledge\ttfm_video_corpus\frames\fractal_model_fundamentals\confirmation_00959840.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/fractal_model_fundamentals/confirmation_00959840.wav
- Embedding excerpt: 
- Weak labels: invalidation, liquidity_sweep, order_block
- Predicted labels: invalidation, fair_value_gap, order_block, breaker, point_of_interest, liquidity_sweep, wick_logic, equilibrium
- Top probabilities: invalidation=0.783, fair_value_gap=0.774, order_block=0.763, breaker=0.675, point_of_interest=0.671
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.375
- Disagreement count: 5

### youtube_trading_candle_3_visual_v1::confirmation
- Title: TTrades Fractal Model - Trading Candle 3
- Checkpoint: confirmation
- Review status: ready_for_weak_training
- Active labels: breaker, fair_value_gap, invalidation, liquidity_sweep, order_block, protected_swing
- Screenshot: knowledge\ttfm_video_corpus\frames\trading_candle_3\confirmation_00857440.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/trading_candle_3/confirmation_00857440.wav
- Embedding excerpt: 
- Weak labels: breaker, fair_value_gap, invalidation, liquidity_sweep, order_block, protected_swing
- Predicted labels: invalidation, liquidity_sweep, fair_value_gap, order_block, breaker, point_of_interest, candle_2_closure, candle_3_closure, wick_logic, protected_swing, equilibrium
- Top probabilities: invalidation=0.768, liquidity_sweep=0.756, fair_value_gap=0.744, order_block=0.732, breaker=0.700
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.545
- Disagreement count: 5

### youtube_ict_index_futures_weekly_recap_week_of_5_16_22_visual_v1::confirmation
- Title: ICT Index Futures Weekly Recap - Week of 5/16/22
- Checkpoint: confirmation
- Review status: ready_for_weak_training
- Active labels: order_block
- Screenshot: knowledge\ttfm_video_corpus\frames\ict_index_futures_weekly_recap_week_of_5_16_22\confirmation_00368460.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/ict_index_futures_weekly_recap_week_of_5_16_22/confirmation_00368460.wav
- Embedding excerpt: 
- Weak labels: order_block
- Predicted labels: fair_value_gap, order_block, wick_logic, invalidation, point_of_interest, equilibrium, liquidity_sweep
- Top probabilities: fair_value_gap=0.711, order_block=0.711, wick_logic=0.631, invalidation=0.630, point_of_interest=0.625
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.143
- Disagreement count: 6

### youtube_ttrades_top_down_chart_lessons_1_visual_v1::confirmation
- Title: TTrades Top-Down Chart Lessons #1
- Checkpoint: confirmation
- Review status: needs_teacher_review
- Active labels: invalidation
- Screenshot: knowledge\ttfm_video_corpus\frames\ttrades_top_down_chart_lessons_1\confirmation_00868500.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/ttrades_top_down_chart_lessons_1/confirmation_00868500.wav
- Embedding excerpt: 
- Weak labels: invalidation
- Predicted labels: order_block, fair_value_gap, invalidation, breaker, point_of_interest, wick_logic, liquidity_sweep, equilibrium
- Top probabilities: order_block=0.688, fair_value_gap=0.684, invalidation=0.596, breaker=0.565, point_of_interest=0.564
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.125
- Disagreement count: 7

### youtube_candle_2_closure_foundation_visual_v1::closure
- Title: Candle 2 Closure: The Foundation of TTrades Fractal Model
- Checkpoint: closure
- Review status: ready_for_weak_training
- Active labels: candle_2_closure, candle_3_closure
- Screenshot: knowledge\ttfm_video_corpus\frames\candle_2_closure_foundation\closure_00041600.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/candle_2_closure_foundation/closure_00041600.wav
- Embedding excerpt: 
- Weak labels: candle_2_closure, candle_3_closure
- Predicted labels: liquidity_sweep, candle_3_closure, candle_2_closure, breaker, protected_swing, order_block, fair_value_gap, equilibrium
- Top probabilities: liquidity_sweep=0.880, candle_3_closure=0.854, candle_2_closure=0.838, breaker=0.752, protected_swing=0.678
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.250
- Disagreement count: 6

### youtube_cisd_validates_swing_points_visual_v1::closure
- Title: Validating Swing Points Using Lower Timeframe Confirmation (CISD)
- Checkpoint: closure
- Review status: ready_for_weak_training
- Active labels: candle_2_closure, candle_3_closure
- Screenshot: knowledge\ttfm_video_corpus\frames\cisd_validates_swing_points\closure_00167719.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/cisd_validates_swing_points/closure_00167719.wav
- Embedding excerpt: 
- Weak labels: candle_2_closure, candle_3_closure
- Predicted labels: liquidity_sweep, candle_3_closure, candle_2_closure, breaker, protected_swing, order_block, fair_value_gap, equilibrium
- Top probabilities: liquidity_sweep=0.901, candle_3_closure=0.888, candle_2_closure=0.870, breaker=0.765, protected_swing=0.710
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.250
- Disagreement count: 6

### youtube_easy_daily_bias_mechanical_framework_visual_v1::closure
- Title: Easy Daily Bias - Mechanical Framework
- Checkpoint: closure
- Review status: ready_for_weak_training
- Active labels: candle_2_closure, candle_3_closure, wick_logic
- Screenshot: knowledge\ttfm_video_corpus\frames\easy_daily_bias_mechanical_framework\closure_00657280.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/easy_daily_bias_mechanical_framework/closure_00657280.wav
- Embedding excerpt: 
- Weak labels: candle_2_closure, candle_3_closure, wick_logic
- Predicted labels: liquidity_sweep, fair_value_gap, breaker, order_block, candle_2_closure, candle_3_closure, invalidation, point_of_interest, protected_swing, wick_logic, equilibrium
- Top probabilities: liquidity_sweep=0.793, fair_value_gap=0.728, breaker=0.721, order_block=0.717, candle_2_closure=0.716
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.273
- Disagreement count: 8

### youtube_fractal_model_fundamentals_visual_v1::closure
- Title: TTrades Playbook | Fractal Model Fundamentals (TTFM)
- Checkpoint: closure
- Review status: ready_for_weak_training
- Active labels: candle_2_closure, wick_logic
- Screenshot: knowledge\ttfm_video_corpus\frames\fractal_model_fundamentals\closure_00322600.jpg
- Audio: knowledge/ttfm_video_corpus/audio_clips/fractal_model_fundamentals/closure_00322600.wav
- Embedding excerpt: 
- Weak labels: candle_2_closure, wick_logic
- Predicted labels: liquidity_sweep, fair_value_gap, order_block, breaker, invalidation, candle_2_closure, candle_3_closure, point_of_interest, protected_swing, wick_logic, equilibrium
- Top probabilities: liquidity_sweep=0.738, fair_value_gap=0.721, order_block=0.709, breaker=0.674, invalidation=0.647
- Recommended action: review_model_disagreement
- Priority band: high
- Label Jaccard: 0.182
- Disagreement count: 9

## Operator Artifacts

- C:/Users/satvi/Repos/builder-block-research/results/ttfm_brain_dashboard.html
- C:/Users/satvi/Repos/builder-block-research/results/ttfm_progress_snapshot.md
- C:/Users/satvi/Repos/builder-block-research/results/ttfm_brain_workflow_report.json
- C:/Users/satvi/Repos/builder-block-research/results/ttfm_brain_workflow_history.jsonl
