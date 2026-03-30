from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from config import AppConfig


IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


@dataclass(slots=True)
class ChartExample:
    example_id: str
    image_path: Path
    embedding: np.ndarray
    text: str
    title: str
    source_type: str
    time_index: int
    metadata: dict[str, Any]


@dataclass(slots=True)
class CorpusBundle:
    examples: list[ChartExample]
    dimension: int
    source_summaries: list[dict[str, Any]]
    warnings: list[str]


def _ensure_scripts_path(config: AppConfig) -> None:
    scripts_dir = config.paths.scripts_dir
    if scripts_dir.exists() and str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _import_script_module(config: AppConfig, module_name: str) -> Any:
    _ensure_scripts_path(config)
    return importlib.import_module(module_name)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def load_dense_window_lookup(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    lookup: dict[str, dict[str, Any]] = {}
    for order, row in enumerate(_read_jsonl(path)):
        key = str(row.get("example_id", "")).strip() or str(row.get("window_id", "")).strip()
        if key:
            enriched_row = dict(row)
            enriched_row["__lookup_order"] = order
            lookup[key] = enriched_row
    return lookup


def _resolve_path(root_dir: Path, raw_path: str | None) -> Path | None:
    cleaned = str(raw_path or "").strip()
    if not cleaned:
        return None
    candidate = Path(cleaned)
    if candidate.is_absolute():
        return candidate
    return (root_dir / candidate).resolve()


def _normalize_embedding(vector: np.ndarray) -> np.ndarray:
    flattened = vector.astype(np.float32).reshape(-1)
    norm = float(np.linalg.norm(flattened))
    if norm == 0.0:
        return flattened
    return flattened / norm


def load_video_order_lookup(config: AppConfig) -> dict[str, int]:
    lookup: dict[str, int] = {}
    if not config.paths.video_manifest_path.exists():
        return lookup
    manifest_payload = _read_json(config.paths.video_manifest_path)
    for index, row in enumerate(manifest_payload.get("videos", [])):
        slug = str(row.get("slug", "")).strip()
        if slug:
            lookup.setdefault(slug, index)
    return lookup


def canonical_time_index(
    *,
    video_slug: str | None,
    start_seconds: float | int | None,
    video_order_lookup: dict[str, int],
    fallback_index: int,
) -> int:
    normalized_slug = str(video_slug or "").strip()
    if normalized_slug and normalized_slug in video_order_lookup:
        start_millis = int(round(float(start_seconds or 0.0) * 1000))
        return int(video_order_lookup[normalized_slug]) * 1_000_000_000 + start_millis
    return int(fallback_index)


def _infer_external_image_path(stem: str, image_dirs: list[Path]) -> Path | None:
    for image_dir in image_dirs:
        for suffix in IMAGE_SUFFIXES:
            candidate = image_dir / f"{stem}{suffix}"
            if candidate.exists():
                return candidate.resolve()
    return None


def _load_index_examples(
    config: AppConfig,
    *,
    index_path: Path,
    windows_path: Path,
    source_name: str,
) -> tuple[list[ChartExample], dict[str, Any], list[str]]:
    index_payload = _read_json(index_path)
    video_order_lookup = load_video_order_lookup(config)
    window_lookup: dict[str, dict[str, Any]] = {}
    if windows_path.exists():
        for row in _read_jsonl(windows_path):
            key = str(row.get("window_id", "")).strip() or str(row.get("example_id", "")).strip()
            if key:
                window_lookup[key] = row
    dimension = int(index_payload.get("output_dimensionality", 0) or 0)
    if dimension != config.active_embedding_dim:
        raise ValueError(
            f"Expected {config.active_embedding_dim}-dim embeddings, found {dimension} in "
            f"{index_path}."
        )

    warnings: list[str] = []
    examples: list[ChartExample] = []
    for time_index, item in enumerate(index_payload.get("items", [])):
        image_path = _resolve_path(config.root_dir, item.get("frame_path"))
        if image_path is None or not image_path.exists():
            warnings.append(f"Missing frame for {item.get('chunk_id')}: {item.get('frame_path')}")
            continue
        embedding = _normalize_embedding(np.asarray(item.get("vector", []), dtype=np.float32))
        if embedding.size != config.active_embedding_dim:
            raise ValueError(
                f"Vector size mismatch for {item.get('chunk_id')}: expected "
                f"{config.active_embedding_dim}, got {embedding.size}."
            )
        metadata = {
            key: value
            for key, value in item.items()
            if key not in {"vector", "text", "title", "frame_path", "source_type"}
        }
        metadata.update(window_lookup.get(str(item.get("chunk_id", "")), {}))
        video_slug = str(metadata.get("video_slug", item.get("video_slug", ""))).strip()
        start_seconds = float(metadata.get("start", item.get("start", 0.0)) or 0.0)
        stable_time_index = canonical_time_index(
            video_slug=video_slug,
            start_seconds=start_seconds,
            video_order_lookup=video_order_lookup,
            fallback_index=time_index,
        )
        examples.append(
            ChartExample(
                example_id=str(item.get("chunk_id", f"visual::{time_index}")),
                image_path=image_path,
                embedding=embedding,
                text=str(item.get("text", "")).strip(),
                title=str(item.get("title", "")).strip() or str(item.get("chunk_id", "")),
                source_type=str(item.get("source_type", "visual_embedding_index")).strip(),
                time_index=stable_time_index,
                metadata=metadata,
            )
        )

    summary = {
        "source": source_name,
        "example_count": len(examples),
        "dimension": dimension,
        "index_path": str(index_path),
    }
    return examples, summary, warnings


def _load_visual_index_examples(config: AppConfig) -> tuple[list[ChartExample], dict[str, Any], list[str]]:
    return _load_index_examples(
        config,
        index_path=config.paths.visual_embedding_index_path,
        windows_path=config.paths.visual_windows_path,
        source_name="visual_embedding_index",
    )


def _load_dense_visual_index_examples(config: AppConfig) -> tuple[list[ChartExample], dict[str, Any] | None, list[str]]:
    if not config.paths.dense_visual_embedding_index_path.exists():
        return [], None, []
    examples, summary, warnings = _load_index_examples(
        config,
        index_path=config.paths.dense_visual_embedding_index_path,
        windows_path=config.paths.dense_visual_windows_path,
        source_name="dense_visual_embedding_index",
    )
    return examples, summary, warnings


def _load_external_embedding_examples(
    config: AppConfig,
    *,
    time_offset: int,
) -> tuple[list[ChartExample], list[dict[str, Any]], list[str]]:
    if not config.paths.additional_embedding_dirs:
        return [], [], []

    examples: list[ChartExample] = []
    summaries: list[dict[str, Any]] = []
    warnings: list[str] = []
    next_index = time_offset
    image_dirs = config.paths.additional_image_dirs or []

    for embedding_dir in config.paths.additional_embedding_dirs:
        embedding_files = sorted(Path(embedding_dir).glob("*.npy"))
        local_count = 0
        for embedding_file in embedding_files:
            vector = _normalize_embedding(np.load(embedding_file))
            if vector.size != config.active_embedding_dim:
                raise ValueError(
                    f"Embedding {embedding_file} has {vector.size} dimensions, expected "
                    f"{config.active_embedding_dim}."
                )
            image_path = _infer_external_image_path(embedding_file.stem, image_dirs)
            if image_path is None:
                warnings.append(f"Missing image pair for external embedding: {embedding_file.name}")
                continue
            examples.append(
                ChartExample(
                    example_id=embedding_file.stem,
                    image_path=image_path,
                    embedding=vector,
                    text=embedding_file.stem.replace("_", " "),
                    title=embedding_file.stem,
                    source_type="external_embedding_dir",
                    time_index=next_index,
                    metadata={"embedding_path": str(embedding_file.resolve())},
                )
            )
            next_index += 1
            local_count += 1

        summaries.append(
            {
                "source": "external_embedding_dir",
                "embedding_dir": str(Path(embedding_dir).resolve()),
                "example_count": local_count,
            }
        )

    return examples, summaries, warnings


def _find_matching_embedding_file(stems: list[str], embedding_dirs: list[Path]) -> Path | None:
    for embedding_dir in embedding_dirs:
        for stem in stems:
            candidate = embedding_dir / f"{stem}.npy"
            if candidate.exists():
                return candidate.resolve()
    return None


def _materialize_screenshot_manifest_embeddings(config: AppConfig) -> None:
    manifest_path = config.paths.screenshot_manifest_path
    if not manifest_path.exists():
        return

    payload = _read_json(manifest_path)
    attachments = list(payload.get("attachments", []))
    existing_embedding_dirs = [config.paths.screenshot_embedding_dir, *config.paths.additional_embedding_dirs]
    missing_rows: list[tuple[dict[str, Any], Path, Path]] = []
    config.paths.screenshot_embedding_dir.mkdir(parents=True, exist_ok=True)
    for attachment in attachments:
        image_path = _resolve_path(config.root_dir, attachment.get("screenshot_path"))
        if image_path is None or not image_path.exists():
            continue
        case_ref = str(attachment.get("case_ref", "")).strip() or image_path.stem
        checkpoint = str(attachment.get("checkpoint", "")).strip() or "screenshot"
        preferred_path = config.paths.screenshot_embedding_dir / f"{case_ref}__{checkpoint}.npy"
        fallback_path = config.paths.screenshot_embedding_dir / f"{image_path.stem}.npy"
        stems = [image_path.stem, f"{case_ref}__{checkpoint}", f"{case_ref}_{checkpoint}", case_ref]
        if preferred_path.exists() or fallback_path.exists() or _find_matching_embedding_file(stems, existing_embedding_dirs):
            continue
        missing_rows.append((attachment, image_path, preferred_path))

    if not missing_rows:
        return

    tve = _import_script_module(config, "ttfm_video_embeddings")
    documents = []
    output_paths: list[Path] = []
    for attachment, image_path, output_path in missing_rows:
        case_ref = str(attachment.get("case_ref", "")).strip() or image_path.stem
        checkpoint = str(attachment.get("checkpoint", "")).strip() or "screenshot"
        annotation_notes = [str(item).strip() for item in attachment.get("annotation_notes", []) if str(item).strip()]
        evidence_refs = [str(item).strip() for item in attachment.get("evidence_refs", []) if str(item).strip()]
        documents.append(
            {
                "window_id": f"{case_ref}::{checkpoint}",
                "example_id": f"{case_ref}::{checkpoint}",
                "video_slug": case_ref,
                "video_id": "",
                "title": case_ref,
                "checkpoint": checkpoint,
                "text": " ".join(annotation_notes + evidence_refs) or f"TTrades screenshot asset for {case_ref} {checkpoint}.",
                "cue_terms": [],
                "candidate_labels": [],
                "screenshot_path": str(image_path),
                "source_type": "screenshot_manifest_embedding",
            }
        )
        output_paths.append(output_path)

    prepared = tve.prepare_multimodal_embedding_documents(documents)
    vectors, _diagnostics = tve.embed_multimodal_documents_with_google(
        prepared,
        api_key=tve.resolve_google_api_key(),
        model=tve.DEFAULT_MULTIMODAL_MODEL,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=config.active_embedding_dim,
    )
    for vector, output_path in zip(vectors, output_paths):
        np.save(output_path, np.asarray(vector, dtype=np.float32))


def _load_screenshot_manifest_examples(
    config: AppConfig,
    *,
    time_offset: int,
) -> tuple[list[ChartExample], dict[str, Any] | None, list[str]]:
    manifest_path = config.paths.screenshot_manifest_path
    if not manifest_path.exists():
        return [], None, []

    if config.phase2.materialize_screenshot_embeddings:
        _materialize_screenshot_manifest_embeddings(config)
    screenshot_embedding_dirs = [config.paths.screenshot_embedding_dir, *config.paths.additional_embedding_dirs]

    payload = _read_json(manifest_path)
    attachments = list(payload.get("attachments", []))
    examples: list[ChartExample] = []
    warnings: list[str] = []
    next_index = time_offset
    for attachment in attachments:
        image_path = _resolve_path(config.root_dir, attachment.get("screenshot_path"))
        if image_path is None or not image_path.exists():
            warnings.append(f"Missing screenshot attachment image: {attachment.get('screenshot_path')}")
            continue
        screenshot_stem = image_path.stem
        case_ref = str(attachment.get("case_ref", "")).strip()
        checkpoint = str(attachment.get("checkpoint", "")).strip()
        stems = [screenshot_stem]
        if case_ref and checkpoint:
            stems.append(f"{case_ref}__{checkpoint}")
            stems.append(f"{case_ref}_{checkpoint}")
        if case_ref:
            stems.append(case_ref)
        embedding_path = _find_matching_embedding_file(stems, screenshot_embedding_dirs)
        if embedding_path is None:
            continue
        vector = _normalize_embedding(np.load(embedding_path))
        if vector.size != config.active_embedding_dim:
            raise ValueError(
                f"Screenshot embedding {embedding_path} has {vector.size} dimensions, expected {config.active_embedding_dim}."
            )
        metadata = dict(attachment)
        metadata["embedding_path"] = str(embedding_path)
        examples.append(
            ChartExample(
                example_id=f"{case_ref}::{checkpoint}" if case_ref and checkpoint else screenshot_stem,
                image_path=image_path,
                embedding=vector,
                text=" ".join(str(item) for item in attachment.get("annotation_notes", [])),
                title=case_ref or screenshot_stem,
                source_type="screenshot_manifest_embedding",
                time_index=next_index,
                metadata=metadata,
            )
        )
        next_index += 1

    if not examples:
        return [], None, warnings
    summary = {
        "source": "screenshot_manifest_embedding",
        "example_count": len(examples),
        "manifest_path": str(manifest_path),
    }
    return examples, summary, warnings


def load_chart_corpus(config: AppConfig) -> CorpusBundle:
    visual_examples, visual_summary, warnings = _load_visual_index_examples(config)
    dense_examples, dense_summary, dense_warnings = _load_dense_visual_index_examples(config)
    base_time_offset = max((example.time_index for example in [*visual_examples, *dense_examples]), default=-1) + 1
    external_examples, external_summaries, external_warnings = _load_external_embedding_examples(
        config,
        time_offset=base_time_offset,
    )
    second_time_offset = max((example.time_index for example in [*visual_examples, *dense_examples, *external_examples]), default=-1) + 1
    screenshot_examples, screenshot_summary, screenshot_warnings = _load_screenshot_manifest_examples(
        config,
        time_offset=second_time_offset,
    )
    warnings.extend(dense_warnings)
    warnings.extend(external_warnings)
    warnings.extend(screenshot_warnings)
    source_summaries = [visual_summary]
    if dense_summary is not None:
        source_summaries.append(dense_summary)
    source_summaries.extend(external_summaries)
    if screenshot_summary is not None:
        source_summaries.append(screenshot_summary)
    examples = sorted([*visual_examples, *dense_examples, *external_examples, *screenshot_examples], key=lambda item: item.time_index)
    if not examples:
        raise RuntimeError("No chart examples were loaded from the configured embedding sources.")
    return CorpusBundle(
        examples=examples,
        dimension=config.active_embedding_dim,
        source_summaries=source_summaries,
        warnings=warnings,
    )


def split_examples_by_time(
    examples: list[ChartExample],
    *,
    validation_ratio: float,
) -> tuple[list[ChartExample], list[ChartExample]]:
    if not 0.0 <= validation_ratio < 1.0:
        raise ValueError("validation_ratio must be in [0.0, 1.0).")
    ordered = sorted(examples, key=lambda item: item.time_index)
    if len(ordered) <= 1 or validation_ratio == 0.0:
        return ordered, []
    validation_count = max(1, int(round(len(ordered) * validation_ratio)))
    validation_count = min(validation_count, len(ordered) - 1)
    split_at = len(ordered) - validation_count
    return ordered[:split_at], ordered[split_at:]


def find_example_by_image(examples: list[ChartExample], image_path: Path) -> ChartExample | None:
    resolved = image_path.resolve()
    for example in examples:
        if example.image_path.resolve() == resolved:
            return example
    return None


def embed_chart_image(image_path: Path, config: AppConfig) -> np.ndarray:
    tve = _import_script_module(config, "ttfm_video_embeddings")
    document = {
        "window_id": image_path.stem,
        "video_slug": "adhoc_prediction",
        "video_id": "",
        "title": image_path.stem,
        "checkpoint": "prediction",
        "text": "Ad hoc chart image for TTrades prediction.",
        "cue_terms": [],
        "candidate_labels": [],
        "screenshot_path": str(image_path),
        "source_type": "adhoc_image",
    }
    prepared = tve.prepare_multimodal_embedding_documents([document])
    vectors, _ = tve.embed_multimodal_documents_with_google(
        prepared,
        api_key=tve.resolve_google_api_key(),
        model=tve.DEFAULT_MULTIMODAL_MODEL,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=config.active_embedding_dim,
    )
    return _normalize_embedding(np.asarray(vectors[0], dtype=np.float32))


def _merge_video_manifests(*manifests: dict[str, Any]) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for manifest in manifests:
        for row in manifest.get("videos", []):
            identity = str(row.get("video_id") or row.get("slug") or json.dumps(row, sort_keys=True))
            if identity in seen:
                continue
            seen.add(identity)
            merged.append(dict(row))
    return {
        "manifest_source": "ttrades_autoresearch_merge",
        "video_count": len(merged),
        "videos": merged,
    }


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def dense_visual_corpus_is_fresh(config: AppConfig) -> bool:
    manifest_path = config.paths.dense_visual_embedding_manifest_path
    index_path = config.paths.dense_visual_embedding_index_path
    windows_path = config.paths.dense_visual_windows_path
    report_path = config.paths.dense_visual_windows_report_path
    if not manifest_path.exists() or not index_path.exists() or not windows_path.exists() or not report_path.exists():
        return False

    try:
        manifest_payload = _read_json(manifest_path)
        index_payload = _read_json(index_path)
        report_payload = _read_json(report_path)
    except json.JSONDecodeError:
        return False

    window_count = _count_jsonl_rows(windows_path)
    manifest_count = int(manifest_payload.get("item_count", 0) or 0)
    index_count = int(index_payload.get("item_count", 0) or len(index_payload.get("items", [])))
    report_max_chunks = report_payload.get("summary", {}).get("max_chunks_per_video")
    if window_count <= 0:
        return False
    if manifest_count != window_count or index_count != window_count:
        return False
    if report_max_chunks != config.phase2.dense_max_chunks_per_video:
        return False

    latest_source_mtime = windows_path.stat().st_mtime
    latest_source_mtime = max(latest_source_mtime, report_path.stat().st_mtime)
    materialized_mtime = min(manifest_path.stat().st_mtime, index_path.stat().st_mtime)
    return materialized_mtime >= latest_source_mtime


def build_dense_chunk_plan(chunks: list[dict[str, Any]], max_chunks_per_video: int | None) -> list[dict[str, Any]]:
    if max_chunks_per_video is None or len(chunks) <= max_chunks_per_video:
        return list(chunks)
    if max_chunks_per_video <= 0:
        return []
    indices = np.linspace(0, len(chunks) - 1, num=max_chunks_per_video)
    selected_indices = sorted({int(round(index)) for index in indices})
    while len(selected_indices) < max_chunks_per_video:
        for index in range(len(chunks)):
            if index not in selected_indices:
                selected_indices.append(index)
                if len(selected_indices) >= max_chunks_per_video:
                    break
    selected_indices = sorted(selected_indices[:max_chunks_per_video])
    return [chunks[index] for index in selected_indices]


def build_dense_visual_corpus(config: AppConfig) -> dict[str, Any]:
    btvw = _import_script_module(config, "build_ttfm_video_visual_windows")
    btvve = _import_script_module(config, "build_ttfm_video_visual_embeddings")
    tve = _import_script_module(config, "ttfm_video_embeddings")

    manifest = _read_json(config.paths.knowledge_dir / "ttfm_video_corpus" / "video_manifest.json")
    chunk_rows = btvw.load_jsonl(config.paths.knowledge_dir / "ttfm_video_corpus" / "chunks.jsonl")
    taxonomy = btvw.load_component_taxonomy()
    chunks_by_video = btvw.index_chunks_by_video(chunk_rows)
    videos_by_slug = {
        str(video.get("slug", "")).strip(): video
        for video in manifest.get("videos", [])
        if str(video.get("slug", "")).strip()
    }

    rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    for video_slug, chunks in chunks_by_video.items():
        video = videos_by_slug.get(video_slug)
        if video is None:
            continue
        selected_chunks = build_dense_chunk_plan(chunks, config.phase2.dense_max_chunks_per_video)
        video_path = btvw.resolve_local_video_path(video, config.paths.video_dir)
        if video_path is None:
            continue
        for chunk in selected_chunks:
            midpoint_seconds = (float(chunk.get("start", 0.0)) + float(chunk.get("end", 0.0))) / 2.0
            timestamp_ms = int(round(midpoint_seconds * 1000))
            frame_output_path = config.paths.dense_frame_dir / video_slug / f"chunk_{timestamp_ms:08d}.jpg"
            if frame_output_path.exists():
                frame_status = "extracted"
                frame_error = None
            else:
                frame_status, frame_error = btvw.extract_frame(
                    video_path,
                    timestamp_seconds=midpoint_seconds,
                    output_path=frame_output_path,
                    ffmpeg_bin=config.paths.ffmpeg_bin,
                )
            candidate_labels: set[str] = set()
            cue_terms: set[str] = set()
            score_total = 0
            for checkpoint, _role, _position in btvw.CHECKPOINT_ORDER:
                metrics = btvw.score_chunk_for_checkpoint(chunk, checkpoint, taxonomy)
                score_total += int(metrics["score"])
                candidate_labels.update(metrics["candidate_labels"])
                cue_terms.update(metrics["cue_terms"])
            chunk_id = str(chunk.get("chunk_id", "")).strip() or f"{video_slug}:dense:{timestamp_ms}"
            row = {
                "window_id": f"{video_slug}::dense::{chunk_id}",
                "example_id": f"{video_slug}::dense::{chunk_id}",
                "case_ref": f"youtube_{video_slug}_dense_v1",
                "source_type": "youtube_dense_window",
                "video_slug": video_slug,
                "video_id": str(video.get("video_id", "")).strip(),
                "title": str(video.get("title", "")).strip(),
                "source_url": str(video.get("url", "")).strip(),
                "source_page": str(video.get("source_page", "")).strip(),
                "corpus_partition": str(video.get("corpus_partition", "educational_youtube")).strip() or "educational_youtube",
                "transcript_source": str(video.get("transcript_source", "")).strip() or None,
                "review_categories": [str(category).strip() for category in video.get("review_categories", []) if str(category).strip()],
                "discovery_source": str(video.get("discovery_source", "youtube_channel_inventory")).strip() or "youtube_channel_inventory",
                "topics": [str(topic).strip() for topic in video.get("topics", []) if str(topic).strip()],
                "supporting_topics": [str(topic).strip() for topic in video.get("topics", []) if str(topic).strip()],
                "checkpoint": "dense",
                "timeframe": "dense",
                "timeframe_role": "dense",
                "start": float(chunk.get("start", 0.0)),
                "end": float(chunk.get("end", 0.0)),
                "midpoint_seconds": midpoint_seconds,
                "source_chunk_id": chunk_id,
                "nearby_transcript_text": str(chunk.get("text", "")).strip(),
                "text": str(chunk.get("text", "")).strip(),
                "cue_score": score_total,
                "cue_terms": sorted(cue_terms),
                "candidate_labels": sorted(candidate_labels),
                "candidate_label_provenance": "dense_chunk_transcript_heuristic",
                "video_path": tve.path_for_manifest(video_path),
                "frame_path": tve.path_for_manifest(frame_output_path) if frame_output_path.exists() else None,
                "chart_crop_path": None,
                "frame_status": frame_status,
                "frame_error": frame_error,
                "market_context": {
                    "alignment_status": "youtube_dense_window",
                    "mapping_provenance": "dense_chunk_midpoint",
                    "symbol": None,
                    "bars_path": None,
                    "bars_timeframe": None,
                    "bars_first_timestamp": None,
                    "bars_last_timestamp": None,
                    "bars_row_count": None,
                    "anchor_timestamp": None,
                    "window_minutes_before": None,
                    "window_minutes_after": None,
                    "source_chart_symbol": None,
                    "source_spec_key": None,
                    "confidence": 0.25,
                    "notes": "Dense chunk frame extracted from the existing TeaTrader/TTrades YouTube corpus.",
                },
                "embedding_text": tve.build_visual_embedding_text(
                    title=str(video.get("title", "")).strip(),
                    checkpoint="dense",
                    topics=[str(topic).strip() for topic in video.get("topics", []) if str(topic).strip()],
                    text=str(chunk.get("text", "")).strip(),
                    cue_terms=sorted(cue_terms),
                    candidate_labels=sorted(candidate_labels),
                ),
            }
            rows.append(row)
        report_rows.append({"video_slug": video_slug, "selected_chunk_count": len(selected_chunks)})

    _write_jsonl(config.paths.dense_visual_windows_path, rows)
    _write_json(
        config.paths.dense_visual_windows_report_path,
        {
            "summary": {
                "window_count": len(rows),
                "video_count": len(report_rows),
                "max_chunks_per_video": config.phase2.dense_max_chunks_per_video,
                "extract_frames": True,
            },
            "videos": report_rows,
        },
    )
    embedding_report_path = config.paths.dense_visual_embedding_manifest_path.parent / "dense_visual_embedding_report.json"
    manifest = btvve.build_visual_embeddings(
        windows_path=config.paths.dense_visual_windows_path,
        index_path=config.paths.dense_visual_embedding_index_path,
        manifest_path=config.paths.dense_visual_embedding_manifest_path,
        report_path=embedding_report_path,
        model="models/gemini-embedding-2-preview",
        output_dimensionality=config.active_embedding_dim,
    )
    return {
        "window_count": len(rows),
        "video_count": len(report_rows),
        "embedding_manifest": manifest,
        "dense_windows_path": str(config.paths.dense_visual_windows_path),
    }


def expand_ttrades_youtube_corpus(config: AppConfig) -> dict[str, Any]:
    dtrv = _import_script_module(config, "discover_ttfm_trade_review_videos")
    btvc = _import_script_module(config, "build_ttfm_video_corpus")
    dtyv = _import_script_module(config, "download_ttfm_youtube_videos")
    btvw = _import_script_module(config, "build_ttfm_video_visual_windows")
    btvve = _import_script_module(config, "build_ttfm_video_visual_embeddings")

    channel_payload = dtrv.fetch_channel_inventory(
        channel_url=config.paths.yt_channel_url,
        yt_dlp_bin=config.paths.yt_dlp_bin,
    )
    inventory, educational_manifest, _ = dtrv.build_channel_corpus_manifests(
        channel_payload,
        channel_url=config.paths.yt_channel_url,
        include_review_categories=set(dtrv.REVIEW_CATEGORY_PATTERNS),
        include_educational_categories=set(dtrv.EDUCATIONAL_CATEGORY_PATTERNS),
    )
    active_manifest = _merge_video_manifests(btvc.default_video_manifest(), educational_manifest)
    corpus_manifest = btvc.build_corpus(
        config.paths.knowledge_dir / "ttfm_video_corpus",
        video_manifest=active_manifest,
        overwrite=False,
        yt_dlp_bin=config.paths.yt_dlp_bin,
    )
    download_report = dtyv.download_videos(
        active_manifest,
        video_dir=config.paths.video_dir,
        yt_dlp_bin=config.paths.yt_dlp_bin,
        overwrite=False,
    )
    chunk_rows = btvw.load_jsonl(config.paths.knowledge_dir / "ttfm_video_corpus" / "chunks.jsonl")
    taxonomy = btvw.load_component_taxonomy()
    window_rows, window_report = btvw.build_visual_windows_dataset(
        corpus_manifest,
        chunk_rows,
        taxonomy=taxonomy,
        video_dir=config.paths.video_dir,
        frame_dir=config.paths.frame_dir,
        extract_frames=True,
        ffmpeg_bin=config.paths.ffmpeg_bin,
    )
    _write_jsonl(config.paths.visual_windows_path, window_rows)
    _write_json(config.paths.knowledge_dir / "ttfm_video_corpus" / "visual_windows_report.json", window_report)
    visual_manifest = btvve.build_visual_embeddings(
        windows_path=config.paths.visual_windows_path,
        index_path=config.paths.visual_embedding_index_path,
        manifest_path=config.paths.visual_embedding_manifest_path,
        report_path=config.paths.knowledge_dir / "ttfm_video_corpus" / "visual_embedding_report.json",
        model="models/gemini-embedding-2-preview",
        output_dimensionality=config.active_embedding_dim,
    )
    report = {
        "inventory_entry_count": inventory.get("entry_count", 0),
        "active_video_count": active_manifest.get("video_count", 0),
        "transcript_video_count": corpus_manifest.get("video_count", 0),
        "download_status_counts": download_report.get("summary", {}).get("status_counts", {}),
        "window_count": len(window_rows),
        "visual_manifest": visual_manifest,
    }
    _write_json(config.paths.corpus_expansion_report_path, report)
    return report


def ensure_corpus_size(config: AppConfig, *, minimum_examples: int) -> CorpusBundle:
    corpus = load_chart_corpus(config)
    if len(corpus.examples) >= minimum_examples:
        return corpus

    if config.phase2.dense_chunk_pass_enabled and not dense_visual_corpus_is_fresh(config):
        build_dense_visual_corpus(config)
        corpus = load_chart_corpus(config)
        if len(corpus.examples) >= minimum_examples:
            return corpus

    if not config.phase2.auto_expand_if_needed:
        return corpus

    expansion_rounds = 0
    while len(corpus.examples) < minimum_examples and expansion_rounds < config.phase2.max_expansion_rounds:
        expand_ttrades_youtube_corpus(config)
        if config.phase2.dense_chunk_pass_enabled and not dense_visual_corpus_is_fresh(config):
            build_dense_visual_corpus(config)
        corpus = load_chart_corpus(config)
        expansion_rounds += 1
    return corpus
