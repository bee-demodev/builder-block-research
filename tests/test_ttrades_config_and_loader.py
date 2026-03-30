from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from config import build_config
from data_loader import (
    build_dense_chunk_plan,
    canonical_time_index,
    dense_visual_corpus_is_fresh,
    ensure_corpus_size,
    load_chart_corpus,
    split_examples_by_time,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_load_chart_corpus_merges_visual_index_and_external_embeddings(tmp_path: Path) -> None:
    frame_dir = tmp_path / "knowledge" / "ttfm_video_corpus" / "frames" / "demo"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_a = frame_dir / "context_0001.jpg"
    frame_b = frame_dir / "context_0002.jpg"
    frame_a.write_bytes(b"a")
    frame_b.write_bytes(b"b")

    manifest_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_embedding_manifest.json"
    index_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_embedding_index.json"
    screenshot_manifest_path = tmp_path / "data" / "ttfm_screenshot_manifest.json"
    extra_embeddings_dir = tmp_path / "extra_embeddings"
    extra_images_dir = tmp_path / "extra_images"
    extra_embeddings_dir.mkdir(parents=True, exist_ok=True)
    extra_images_dir.mkdir(parents=True, exist_ok=True)

    np.save(extra_embeddings_dir / "extra_case.npy", np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))
    (extra_images_dir / "extra_case.png").write_bytes(b"png")

    _write_json(
        manifest_path,
        {
            "model": "models/gemini-embedding-2-preview",
            "output_dimensionality": 4,
            "item_count": 2,
            "index_path": str(index_path),
        },
    )
    _write_json(
        index_path,
        {
            "model": "models/gemini-embedding-2-preview",
            "output_dimensionality": 4,
            "item_count": 2,
            "items": [
                {
                    "chunk_id": "demo::context",
                    "video_slug": "demo",
                    "title": "Demo",
                    "start": 1.0,
                    "end": 2.0,
                    "text": "bullish continuation long",
                    "vector": [1.0, 0.0, 0.0, 0.0],
                    "frame_path": str(frame_a.relative_to(tmp_path)),
                    "checkpoint": "context",
                },
                {
                    "chunk_id": "demo::sweep",
                    "video_slug": "demo",
                    "title": "Demo",
                    "start": 3.0,
                    "end": 4.0,
                    "text": "bearish reversal short",
                    "vector": [0.0, 1.0, 0.0, 0.0],
                    "frame_path": str(frame_b.relative_to(tmp_path)),
                    "checkpoint": "sweep",
                },
            ],
        },
    )
    _write_json(screenshot_manifest_path, {"attachments": []})

    config = build_config(root_dir=tmp_path)
    config = replace(
        config,
        active_embedding_dim=4,
        paths=replace(
            config.paths,
            visual_embedding_manifest_path=manifest_path,
            visual_embedding_index_path=index_path,
            screenshot_manifest_path=screenshot_manifest_path,
            additional_embedding_dirs=[extra_embeddings_dir],
            additional_image_dirs=[extra_images_dir],
        ),
    )

    corpus = load_chart_corpus(config)

    assert corpus.dimension == 4
    assert len(corpus.examples) == 3
    assert corpus.examples[0].example_id == "demo::context"
    assert corpus.examples[-1].source_type == "external_embedding_dir"

    train_examples, val_examples = split_examples_by_time(corpus.examples, validation_ratio=0.34)
    assert len(train_examples) == 2
    assert len(val_examples) == 1
    assert train_examples[0].time_index < train_examples[-1].time_index


def test_load_chart_corpus_merges_screenshot_manifest_embeddings(tmp_path: Path) -> None:
    frame_dir = tmp_path / "knowledge" / "ttfm_video_corpus" / "frames" / "demo"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_a = frame_dir / "context_0001.jpg"
    frame_a.write_bytes(b"a")

    manifest_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_embedding_manifest.json"
    index_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_embedding_index.json"
    screenshot_manifest_path = tmp_path / "data" / "ttfm_screenshot_manifest.json"
    screenshots_dir = tmp_path / "artifacts" / "ttfm" / "screenshots" / "case_a"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshots_dir / "confirmation_case.png"
    screenshot_path.write_bytes(b"png")
    extra_embeddings_dir = tmp_path / "extra_embeddings"
    extra_embeddings_dir.mkdir(parents=True, exist_ok=True)
    np.save(extra_embeddings_dir / "case_a__confirmation.npy", np.array([0.9, 0.0, 0.1, 0.0], dtype=np.float32))

    _write_json(
        manifest_path,
        {
            "model": "models/gemini-embedding-2-preview",
            "output_dimensionality": 4,
            "item_count": 1,
            "index_path": str(index_path),
        },
    )
    _write_json(
        index_path,
        {
            "model": "models/gemini-embedding-2-preview",
            "output_dimensionality": 4,
            "item_count": 1,
            "items": [
                {
                    "chunk_id": "demo::context",
                    "video_slug": "demo",
                    "title": "Demo",
                    "start": 1.0,
                    "end": 2.0,
                    "text": "bullish continuation long",
                    "vector": [1.0, 0.0, 0.0, 0.0],
                    "frame_path": str(frame_a.relative_to(tmp_path)),
                    "checkpoint": "context",
                }
            ],
        },
    )
    _write_json(
        screenshot_manifest_path,
        {
            "attachments": [
                {
                    "case_ref": "case_a",
                    "checkpoint": "confirmation",
                    "screenshot_path": str(screenshot_path.relative_to(tmp_path)),
                    "annotation_notes": ["strong confirmation zone"],
                }
            ]
        },
    )

    config = build_config(root_dir=tmp_path)
    config = replace(
        config,
        active_embedding_dim=4,
        paths=replace(
            config.paths,
            visual_embedding_manifest_path=manifest_path,
            visual_embedding_index_path=index_path,
            screenshot_manifest_path=screenshot_manifest_path,
            additional_embedding_dirs=[extra_embeddings_dir],
        ),
    )

    corpus = load_chart_corpus(config)

    assert len(corpus.examples) == 2
    assert corpus.examples[-1].source_type == "screenshot_manifest_embedding"


def test_load_chart_corpus_uses_screenshot_embedding_dir_by_default(tmp_path: Path) -> None:
    frame_dir = tmp_path / "knowledge" / "ttfm_video_corpus" / "frames" / "demo"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_a = frame_dir / "context_0001.jpg"
    frame_a.write_bytes(b"a")

    manifest_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_embedding_manifest.json"
    index_path = tmp_path / "knowledge" / "ttfm_video_corpus" / "visual_embedding_index.json"
    screenshot_manifest_path = tmp_path / "data" / "ttfm_screenshot_manifest.json"
    screenshot_embeddings_dir = tmp_path / "data" / "embeddings" / "screenshots"
    screenshot_embeddings_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = tmp_path / "artifacts" / "ttfm" / "screenshots" / "case_b"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshots_dir / "closure_case.png"
    screenshot_path.write_bytes(b"png")
    np.save(screenshot_embeddings_dir / "case_b__closure.npy", np.array([0.9, 0.0, 0.1, 0.0], dtype=np.float32))

    _write_json(
        manifest_path,
        {
            "model": "models/gemini-embedding-2-preview",
            "output_dimensionality": 4,
            "item_count": 1,
            "index_path": str(index_path),
        },
    )
    _write_json(
        index_path,
        {
            "model": "models/gemini-embedding-2-preview",
            "output_dimensionality": 4,
            "item_count": 1,
            "items": [
                {
                    "chunk_id": "demo::context",
                    "video_slug": "demo",
                    "title": "Demo",
                    "start": 1.0,
                    "end": 2.0,
                    "text": "bullish continuation long",
                    "vector": [1.0, 0.0, 0.0, 0.0],
                    "frame_path": str(frame_a.relative_to(tmp_path)),
                    "checkpoint": "context",
                }
            ],
        },
    )
    _write_json(
        screenshot_manifest_path,
        {
            "attachments": [
                {
                    "case_ref": "case_b",
                    "checkpoint": "closure",
                    "screenshot_path": str(screenshot_path.relative_to(tmp_path)),
                    "annotation_notes": ["teacher screenshot closure"],
                }
            ]
        },
    )

    config = build_config(root_dir=tmp_path)
    config = replace(
        config,
        active_embedding_dim=4,
        paths=replace(
            config.paths,
            visual_embedding_manifest_path=manifest_path,
            visual_embedding_index_path=index_path,
            screenshot_manifest_path=screenshot_manifest_path,
            screenshot_embedding_dir=screenshot_embeddings_dir,
            additional_embedding_dirs=[],
        ),
    )

    corpus = load_chart_corpus(config)

    assert len(corpus.examples) == 2
    assert corpus.examples[-1].example_id == "case_b::closure"


def test_build_dense_chunk_plan_spreads_chunks_across_video() -> None:
    chunks = [{"chunk_id": f"demo:{index:04d}", "start": float(index), "end": float(index + 1)} for index in range(20)]

    selected = build_dense_chunk_plan(chunks, max_chunks_per_video=5)

    assert len(selected) == 5
    assert selected[0]["chunk_id"] == "demo:0000"
    assert selected[-1]["chunk_id"] == "demo:0019"
    assert len({row["chunk_id"] for row in selected}) == 5


def test_ensure_corpus_size_uses_dense_pass_before_external_expansion(monkeypatch, tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    calls: list[str] = []
    corpora = [
        type("Corpus", (), {"examples": [1, 2]})(),
        type("Corpus", (), {"examples": list(range(12))})(),
    ]

    def fake_load(_config):
        calls.append("load")
        return corpora.pop(0)

    monkeypatch.setattr("data_loader.load_chart_corpus", fake_load)
    monkeypatch.setattr("data_loader.build_dense_visual_corpus", lambda _config: calls.append("dense"))
    monkeypatch.setattr("data_loader.expand_ttrades_youtube_corpus", lambda _config: calls.append("expand"))

    corpus = ensure_corpus_size(config, minimum_examples=10)

    assert len(corpus.examples) == 12
    assert calls == ["load", "dense", "load"]


def test_ensure_corpus_size_skips_dense_rebuild_when_manifest_is_fresh(monkeypatch, tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    calls: list[str] = []
    corpus = type("Corpus", (), {"examples": [1, 2, 3]})()

    monkeypatch.setattr("data_loader.load_chart_corpus", lambda _config: calls.append("load") or corpus)
    monkeypatch.setattr("data_loader.dense_visual_corpus_is_fresh", lambda _config: True)
    monkeypatch.setattr("data_loader.build_dense_visual_corpus", lambda _config: calls.append("dense"))

    result = ensure_corpus_size(config, minimum_examples=10)

    assert result.examples == [1, 2, 3]
    assert calls == ["load"]


def test_dense_visual_corpus_is_fresh_checks_counts_and_mtime(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    config.paths.dense_visual_windows_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.dense_visual_windows_path.write_text('{"example_id":"a"}\n{"example_id":"b"}\n', encoding="utf-8")
    config.paths.dense_visual_windows_report_path.write_text(
        json.dumps({"summary": {"window_count": 2, "max_chunks_per_video": config.phase2.dense_max_chunks_per_video}}),
        encoding="utf-8",
    )
    _write_json(config.paths.dense_visual_embedding_manifest_path, {"item_count": 2})
    _write_json(
        config.paths.dense_visual_embedding_index_path,
        {"item_count": 2, "items": [{"example_id": "a"}, {"example_id": "b"}]},
    )

    assert dense_visual_corpus_is_fresh(config) is True

    _write_json(config.paths.dense_visual_embedding_manifest_path, {"item_count": 1})
    assert dense_visual_corpus_is_fresh(config) is False


def test_dense_visual_corpus_is_not_fresh_when_chunk_config_changes(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    config.paths.dense_visual_windows_path.parent.mkdir(parents=True, exist_ok=True)
    config.paths.dense_visual_windows_path.write_text('{"example_id":"a"}\n', encoding="utf-8")
    config.paths.dense_visual_windows_report_path.write_text(
        json.dumps({"summary": {"window_count": 1, "max_chunks_per_video": 12}}),
        encoding="utf-8",
    )
    _write_json(config.paths.dense_visual_embedding_manifest_path, {"item_count": 1})
    _write_json(config.paths.dense_visual_embedding_index_path, {"item_count": 1, "items": [{"example_id": "a"}]})

    assert dense_visual_corpus_is_fresh(config) is False


def test_canonical_time_index_uses_shared_video_order() -> None:
    video_order_lookup = {"video_a": 2}

    canonical = canonical_time_index(
        video_slug="video_a",
        start_seconds=12.345,
        video_order_lookup=video_order_lookup,
        fallback_index=99,
    )
    fallback = canonical_time_index(
        video_slug="missing_video",
        start_seconds=12.345,
        video_order_lookup=video_order_lookup,
        fallback_index=99,
    )

    assert canonical == 2_000_012_345
    assert fallback == 99
