from __future__ import annotations

import json
from pathlib import Path

from scripts.build_ttfm_corpus_prep_packet import (
    CorpusPrepConfig,
    build_phase2_answer_template,
    build_prep_packet,
    infer_v1_classes,
    score_row,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_infer_v1_classes_uses_transcript_and_audio_direction() -> None:
    row = {
        "candidate_labels": ["liquidity_sweep", "fair_value_gap", "protected_swing"],
        "cue_terms": ["sweep", "entry"],
        "text": "Price sweeps previous day high into resistance and gives a bearish short entry.",
    }

    classes = infer_v1_classes(row, audio_text="The protected high is the invalidation.")

    assert classes == [
        "liquidity_sweep_high",
        "protected_swing",
        "bearish_reaction_zone",
    ]


def test_score_row_selects_embedding_and_audio_context(tmp_path: Path) -> None:
    image_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "frames" / "demo" / "sweep_001.jpg"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"not-a-real-image")
    row = {
        "window_id": "demo::sweep",
        "source_type": "youtube_visual_window",
        "video_slug": "demo",
        "checkpoint": "sweep",
        "frame_path": str(image_path.relative_to(tmp_path)),
        "candidate_labels": ["liquidity_sweep"],
        "cue_terms": ["sweep", "entry"],
        "text": "We sweep previous day low and look for a bullish long entry.",
    }

    item, exclusion = score_row(
        row,
        root_dir=tmp_path,
        audio_contexts={("demo", "sweep"): "Protected low and bullish continuation context."},
        text_context_by_video={
            "demo": [
                {
                    "chunk_id": "demo::chunk1",
                    "text": "The sweep and protected low frame the long continuation.",
                    "topics": ["liquidity_sweep"],
                }
            ]
        },
        vector_map={
            "demo::sweep": [1.0, 0.0],
            "accepted::case": [0.9, 0.1],
        },
        reviewed_classes={"accepted::case": {"liquidity_sweep_low"}},
        reviewed_ids=set(),
        skip_image_quality=True,
    )

    assert exclusion is None
    assert item is not None
    assert item["candidate_labels"] == ["liquidity_sweep_low", "protected_swing"]
    assert "audio_semantic_context" in item["selection_reasons"]
    assert "google_text_embedding_context" in item["selection_reasons"]
    assert item["embedding_neighbors"][0]["example_id"] == "accepted::case"


def test_build_prep_packet_excludes_reviewed_and_reports_hard_negative(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "knowledge" / "ttfm_video_corpus"
    image_dir = corpus_dir / "dense_frames" / "demo"
    image_dir.mkdir(parents=True, exist_ok=True)
    reviewed_image = image_dir / "reviewed.jpg"
    candidate_image = image_dir / "candidate.jpg"
    negative_image = image_dir / "negative.jpg"
    for image in (reviewed_image, candidate_image, negative_image):
        image.write_bytes(b"img")

    _write_jsonl(
        corpus_dir / "dense_visual_windows.jsonl",
        [
            {
                "window_id": "demo::reviewed",
                "source_type": "youtube_dense_window",
                "video_slug": "demo",
                "checkpoint": "dense",
                "frame_path": str(reviewed_image.relative_to(tmp_path)),
                "candidate_labels": ["liquidity_sweep"],
                "cue_terms": ["sweep"],
                "text": "Reviewed previous day low sweep.",
            },
            {
                "window_id": "demo::candidate",
                "source_type": "youtube_dense_window",
                "video_slug": "demo",
                "checkpoint": "dense",
                "frame_path": str(candidate_image.relative_to(tmp_path)),
                "candidate_labels": ["liquidity_sweep", "fair_value_gap"],
                "cue_terms": ["sweep", "entry"],
                "text": "Price sweeps previous day high into bearish short continuation.",
            },
            {
                "window_id": "demo::negative",
                "source_type": "youtube_dense_window",
                "video_slug": "demo",
                "checkpoint": "dense",
                "frame_path": str(negative_image.relative_to(tmp_path)),
                "candidate_labels": [],
                "cue_terms": [],
                "text": "Chart-like consolidation with no clear target structure.",
            },
        ],
    )
    _write_jsonl(corpus_dir / "visual_windows.jsonl", [])
    _write_json(
        tmp_path / "results" / "phase2_dense_supervision_answers.json",
        {
            "items": [
                {
                    "example_id": "demo::reviewed",
                    "detections": [{"class_id": 1, "bbox": [0.5, 0.5, 0.1, 0.1]}],
                }
            ]
        },
    )
    _write_json(
        corpus_dir / "google_embedding_index.json",
        {
            "items": [
                {
                    "chunk_id": "demo::chunk",
                    "video_slug": "demo",
                    "text": "bearish short liquidity sweep previous day high",
                    "topics": ["liquidity_sweep"],
                }
            ]
        },
    )
    _write_json(tmp_path / "results" / "phase2_dataset_stats.json", {"train_count": 1, "val_count": 1})

    packet, report = build_prep_packet(
        CorpusPrepConfig(
            root_dir=tmp_path,
            limit=10,
            hard_negative_limit=10,
            skip_image_quality=True,
        )
    )

    ids = {item["example_id"] for item in packet["items"]}
    assert "demo::reviewed" not in ids
    assert "demo::candidate" in ids
    assert "demo::negative" in ids
    assert report["exclusion_counts"]["already_reviewed"] == 1
    assert report["selected_hard_negative_count"] == 1
    assert report["review_artifacts"]["answer_template_mode"] == "ambiguous_until_reviewed"

    template = build_phase2_answer_template(packet)

    assert template["mode"] == "ttfm_corpus_prep_phase2_answers_template"
    assert {item["review_outcome"] for item in template["items"]} == {"ambiguous"}
    assert all(item["detections"] == [] for item in template["items"])
    candidate_template = next(item for item in template["items"] if item["example_id"] == "demo::candidate")
    assert candidate_template["candidate_labels"] == ["liquidity_sweep_high", "bearish_reaction_zone"]
