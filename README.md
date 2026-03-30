# ttrades_autoresearch

Root-level Karpathy-style trading autoresearch workflow for TTrades chart embeddings, pseudo-labeling, markup generation, and detector training.

For a fresh Codex session, start with [TTRADES_AUTORESEARCH_WORKFLOW.md](C:\Users\satvi\Repos\builder-block-research\TTRADES_AUTORESEARCH_WORKFLOW.md) and [results/workflow_status.json](C:\Users\satvi\Repos\builder-block-research\results\workflow_status.json).

Copy-paste prompt for a fresh session:

```text
Follow TTRADES_AUTORESEARCH_WORKFLOW.md and results/workflow_status.json. Continue from the current next_action without asking me for permission unless something is destructive or ambiguous.
```

This reset keeps the useful corpus assets already in the repo:
- `knowledge/ttfm_video_corpus/*` for the current `768`-dim Gemini visual corpus
- `artifacts/ttfm/screenshots/*` for optional screenshot merges
- `data/ttrades_anchor_examples.json` for a ready-to-run starter anchor set

The active v1 vector space is `768` dimensions. If you add more embeddings from the TTrades YouTube channel, generate them into the same space.

## Project Layout

```text
main.py
config.py
data_loader.py
labeler/
  embedding_labeler.py
  vision_labeler.py
trainer/
  mlp_trainer.py
  yolo_trainer.py
dataset/
  yolo/
models/
results/
predict.py
requirements.txt
README.md
```

## Install

```bash
uv venv .venv
uv pip install -r requirements.txt pytest
```

## WandB Login And First Run

```bash
wandb login
uv run python main.py --phase 1 --anchors data/ttrades_anchor_examples.json
```

If you want to avoid sending logs while testing locally:

```bash
uv run python main.py --phase 1 --anchors data/ttrades_anchor_examples.json --wandb-mode offline
```

## Run Commands

Phase 1, retrieval-first pseudo-labeling plus MLP:

```bash
uv run python main.py --phase 1 --anchors data/ttrades_anchor_examples.json
```

Phase 2, representative sampling plus GPT-5.4 Pro vision labeling:

```bash
uv run python main.py --phase 2
```

Phase 2 with explicit corpus expansion opt-in:

```bash
uv run python main.py --phase 2 --allow-expand
```

Phase 3, YOLO training plus ONNX export:

```bash
uv run python main.py --phase 3
```

Autonomous workflow loop, which keeps refreshing Phase 2 and only retrains when the loop decides it is justified:

```bash
uv run python main.py --phase loop --wandb-mode disabled
```

Prediction on any chart image:

```bash
uv run python predict.py --image path\\to\\chart.png
```

## Current Data Sources

The loader consumes, in order:

1. `knowledge/ttfm_video_corpus/visual_embedding_index.json`
2. Optional extra `.npy` directories configured in `config.py`
3. Optional future TTrades YouTube expansion when Phase 2 needs more representative coverage

When the input image already exists in the indexed corpus, prediction reuses the stored vector. Otherwise it embeds the image on demand with Gemini Embedding 2.

## Output Files

Phase 1 writes:
- `results/phase1_pseudo_labels.jsonl`
- `results/phase1_review_queue.json`
- `results/results_mlp.tsv`
- `models/mlp_ttrades_best.pth`

Phase 2 writes:
- `results/phase2_representatives.json`
- `results/phase2_review_queue.json`
- `results/phase2_supervision_packet.json`
- `results/phase2_supervision_answers.example.json`
- `results/phase2_supervision_answers.json` when you or a later Codex pass provide reviewed detections
- `results/phase2_dense_supervision_packet.json`
- `results/phase2_dense_supervision_answers.example.json`
- `results/phase2_dense_heuristic_promotions.json`
- `results/phase2_dataset_stats.json`
- `results/benchmark_manifest.json`
- `dataset/yolo/images/train`
- `dataset/yolo/images/val`
- `dataset/yolo/labels/train`
- `dataset/yolo/labels/val`
- `dataset/yolo/data.yaml`
- `dataset/yolo_benchmark/images`
- `dataset/yolo_benchmark/labels`
- `dataset/yolo_benchmark/data.yaml`

Phase 3 writes:
- `results/results_yolo.tsv`
- `results/workflow_loop_report.json` when you use `--phase loop`
- `models/yolo26_ttrades_markup_best.pt`
- `models/yolo26_ttrades_markup_best.onnx`

Prediction writes:
- `results/predictions/<image>_annotated.<ext>`

## GPT-5.4 Pro Vision System Prompt

Use this exact system prompt for Phase 2:

```text
You are an expert chart markup labeler for TTrades-style TradingView screenshots.
Identify only visible chart structures and return a strict JSON array.
Each item must be exactly:
{"class_id": int, "bbox": [x_center, y_center, width, height]}

Rules:
- Use normalized bbox coordinates in the inclusive range 0 to 1.
- Return only classes that are clearly visible on the chart.
- Do not include commentary, markdown, prose, code fences, or keys other than class_id and bbox.
- If no valid markup is visible, return [].

Classes:
0 fractal_swing_high
1 fractal_swing_low
2 order_block_bullish
3 order_block_bearish
4 inversion_fvg
5 liquidity_sweep_high
6 liquidity_sweep_low
7 candle_3_closure_zone
8 protected_swing
```

## Suggested Anchor Examples

The repo already ships a starter anchor manifest in `data/ttrades_anchor_examples.json`. The current nine suggestions are:

- `high_probability_long`
  - `youtube_mara_trade_review_h1_market_maker_buy_model_mmxm_visual_v1::closure`
  - `youtube_trading_candle_3_visual_v1::sweep`
  - `youtube_mara_trade_review_h1_market_maker_buy_model_mmxm_visual_v1::context`
- `high_probability_short`
  - `youtube_ict_index_futures_weekly_recap_week_of_5_16_22_visual_v1::closure`
  - `youtube_fractal_model_fundamentals_visual_v1::outcome`
  - `youtube_equilibrium_for_expansions_visual_v1::sweep`
- `invalid_chop`
  - `youtube_equilibrium_for_expansions_visual_v1::outcome`
  - `youtube_fractal_model_fundamentals_visual_v1::closure`
  - `youtube_fractal_model_fundamentals_visual_v1::confirmation`

Replace these with your stronger hand-picked anchors whenever you have them.

## Notes

- Phase 1 is retrieval-first by design. It only trains on confident pseudo-labels and pushes uncertain cases into a review queue.
- Phase 2 validates every vision response before it becomes YOLO truth. Invalid or suspicious outputs stay in `results/phase2_review_queue.json`.
- If `OPENAI_API_KEY` is missing, Phase 2 automatically switches to Codex supervision-only mode and writes `results/phase2_supervision_packet.json`. You can then answer that packet by creating `results/phase2_supervision_answers.json` with:

```json
{
  "items": [
    {
      "example_id": "youtube_some_chart::confirmation",
      "detections": [
        {"class_id": 0, "bbox": [0.50, 0.42, 0.18, 0.10]}
      ]
    }
  ]
}
```

- A starter template is also written to `results/phase2_supervision_answers.example.json`.
- When dense chunk frames are available, Phase 2 also emits a larger `results/phase2_dense_supervision_packet.json` plus `results/phase2_dense_supervision_answers.example.json` so you can review a much broader slice of the TTrades corpus without waiting on external vision APIs.

- When `results/phase2_supervision_answers.json` exists, rerunning `uv run python main.py --phase 2 --wandb-mode disabled` will validate those detections and export the YOLO dataset without needing an OpenAI key.
- Phase 3 assumes your Ultralytics install can resolve `yolo26n.pt`. If your local version does not support that checkpoint yet, change `config.phase3.model_name` to a supported alternative such as `yolo11n.pt`.
