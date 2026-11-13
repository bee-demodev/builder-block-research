from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import YOLO_CLASS_NAMES
from labeler.vision_labeler import is_teaching_slide_image


DEFAULT_PACKET_PATH = Path("results") / "ttfm_corpus_prep_packet.json"
DEFAULT_REPORT_PATH = Path("results") / "ttfm_corpus_prep_report.json"
DEFAULT_ANSWER_TEMPLATE_PATH = Path("results") / "ttfm_corpus_prep_phase2_answers.example.json"
DEFAULT_LIMIT = 180
DEFAULT_HARD_NEGATIVE_LIMIT = 25

SCARCE_CLASS_NAMES = {"liquidity_sweep_high", "bearish_reaction_zone"}
REACTION_SOURCE_LABELS = {
    "order_block",
    "order block",
    "fair_value_gap",
    "fair value gap",
    "breaker",
    "point_of_interest",
    "point of interest",
    "poi",
    "equilibrium",
}
LIQUIDITY_LABELS = {"liquidity_sweep", "liquidity sweep", "sweep"}
PROTECTED_SWING_LABELS = {"protected_swing", "protected swing"}

HIGH_MARKERS = (
    "previous day high",
    "previous high",
    "protected high",
    "swing high",
    "buy side",
    "buyside",
    "highs",
    "above",
)
LOW_MARKERS = (
    "previous day low",
    "previous low",
    "protected low",
    "swing low",
    "sell side",
    "sellside",
    "lows",
    "below",
)
BEARISH_MARKERS = (
    "bearish",
    "short",
    "sell",
    "lower",
    "resistance",
    "down close",
    "continuation lower",
)
BULLISH_MARKERS = (
    "bullish",
    "long",
    "buy",
    "higher",
    "support",
    "up close",
    "continuation higher",
)
CHART_MARKERS = (
    "here we are",
    "let this play",
    "drop down",
    "5 minute",
    "5-minute",
    "hourly",
    "daily",
    "take an entry",
    "put my stop",
    "target",
    "retest",
    "previous day",
    "protected swing",
    "sweep",
)
NARRATED_CHART_MARKERS = (
    "here we are",
    "you can see",
    "let's see",
    "lets see",
    "we get",
    "we have",
    "price ",
    "candle ",
    "take an entry",
    "put my stop",
    "drop down",
    "let this play",
)

LEGACY_TO_V1_CLASS_ID = {
    5: 0,  # legacy liquidity_sweep_high
    6: 1,  # legacy liquidity_sweep_low
    8: 2,  # legacy protected_swing
}


@dataclass(slots=True)
class CorpusPrepConfig:
    root_dir: Path
    limit: int = DEFAULT_LIMIT
    hard_negative_limit: int = DEFAULT_HARD_NEGATIVE_LIMIT
    output_packet_path: Path = DEFAULT_PACKET_PATH
    output_report_path: Path = DEFAULT_REPORT_PATH
    output_answer_template_path: Path = DEFAULT_ANSWER_TEMPLATE_PATH
    skip_image_quality: bool = False


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def resolve_path(root_dir: Path, raw_path: str | None) -> Path | None:
    cleaned = str(raw_path or "").strip()
    if not cleaned:
        return None
    path = Path(cleaned)
    if not path.is_absolute():
        path = root_dir / path
    return path.resolve()


def normalize_terms(values: Any) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, str):
        values = [values]
    return {str(value).strip().lower().replace("-", "_") for value in values if str(value).strip()}


def text_blob(row: dict[str, Any], *, audio_text: str = "") -> str:
    parts = [
        row.get("title", ""),
        row.get("text", ""),
        row.get("nearby_transcript_text", ""),
        row.get("transcript_window", ""),
        " ".join(str(value) for value in row.get("candidate_labels", []) or []),
        " ".join(str(value) for value in row.get("cue_terms", []) or []),
        audio_text,
    ]
    return " ".join(str(part) for part in parts if str(part).strip()).lower()


def marker_score(text: str, markers: tuple[str, ...]) -> int:
    return sum(1 for marker in markers if marker in text)


def infer_v1_classes(row: dict[str, Any], *, audio_text: str = "") -> list[str]:
    terms = normalize_terms(row.get("candidate_labels", [])) | normalize_terms(row.get("cue_terms", []))
    text = text_blob(row, audio_text=audio_text)
    classes: set[str] = set()

    high_score = marker_score(text, HIGH_MARKERS)
    low_score = marker_score(text, LOW_MARKERS)
    bearish_score = marker_score(text, BEARISH_MARKERS)
    bullish_score = marker_score(text, BULLISH_MARKERS)

    has_liquidity = bool(terms & {term.replace(" ", "_") for term in LIQUIDITY_LABELS}) or "liquidity" in text
    if has_liquidity:
        if high_score > low_score or (high_score == low_score and bearish_score > bullish_score):
            classes.add("liquidity_sweep_high")
        if low_score > high_score or (low_score == high_score and bullish_score > bearish_score):
            classes.add("liquidity_sweep_low")

    if terms & {term.replace(" ", "_") for term in PROTECTED_SWING_LABELS} or "protected swing" in text:
        classes.add("protected_swing")
    elif "protected high" in text or "protected low" in text:
        classes.add("protected_swing")

    has_reaction = bool(terms & {term.replace(" ", "_") for term in REACTION_SOURCE_LABELS})
    if has_reaction:
        if bearish_score > bullish_score:
            classes.add("bearish_reaction_zone")
        elif bullish_score > bearish_score:
            classes.add("bullish_reaction_zone")

    return sorted(classes, key=YOLO_CLASS_NAMES.index)


def normalize_detection_class_name(detection: dict[str, Any]) -> str | None:
    raw_class_id = detection.get("class_id")
    try:
        class_id = int(raw_class_id)
    except (TypeError, ValueError):
        return None
    if 0 <= class_id < len(YOLO_CLASS_NAMES):
        return YOLO_CLASS_NAMES[class_id]
    mapped = LEGACY_TO_V1_CLASS_ID.get(class_id)
    if mapped is not None:
        return YOLO_CLASS_NAMES[mapped]
    return None


def load_reviewed_examples(root_dir: Path) -> tuple[dict[str, set[str]], set[str]]:
    answer_paths = [
        root_dir / "results" / "phase2_supervision_answers.json",
        root_dir / "results" / "phase2_dense_supervision_answers.json",
        root_dir / "results" / "phase2_dense_heuristic_promotions.json",
        root_dir / "results" / "phase2_teacher_heuristic_promotions.json",
        root_dir / "results" / "phase2_weak_visual_promotions.json",
    ]
    reviewed_classes: dict[str, set[str]] = defaultdict(set)
    reviewed_ids: set[str] = set()
    for path in answer_paths:
        payload = load_json(path, {})
        for item in payload.get("items", []) if isinstance(payload, dict) else []:
            example_id = str(item.get("example_id", "")).strip()
            if not example_id:
                continue
            reviewed_ids.add(example_id)
            for detection in item.get("detections", []) or []:
                class_name = normalize_detection_class_name(detection)
                if class_name is not None:
                    reviewed_classes[example_id].add(class_name)
    return dict(reviewed_classes), reviewed_ids


def load_audio_context(root_dir: Path) -> dict[tuple[str, str], str]:
    payload = load_json(root_dir / "knowledge" / "ttfm_video_corpus" / "audio_semantic_cache.json", {})
    entries = payload.get("entries", payload) if isinstance(payload, dict) else {}
    contexts: dict[tuple[str, str], str] = {}
    if not isinstance(entries, dict):
        return contexts
    for value in entries.values():
        if not isinstance(value, dict):
            continue
        audio_path = str(value.get("audio_path", "")).replace("\\", "/")
        semantic_text = str(value.get("semantic_text", "")).strip()
        if not audio_path or not semantic_text:
            continue
        parts = audio_path.split("/")
        try:
            audio_index = parts.index("audio_clips")
        except ValueError:
            continue
        if len(parts) <= audio_index + 2:
            continue
        video_slug = parts[audio_index + 1]
        checkpoint = Path(parts[audio_index + 2]).stem.split("_", 1)[0]
        contexts[(video_slug, checkpoint)] = semantic_text
    return contexts


def load_text_embedding_context(root_dir: Path) -> dict[str, list[dict[str, Any]]]:
    payload = load_json(root_dir / "knowledge" / "ttfm_video_corpus" / "google_embedding_index.json", {})
    by_video: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in payload.get("items", []) if isinstance(payload, dict) else []:
        video_slug = str(item.get("video_slug", "")).strip()
        if not video_slug:
            continue
        by_video[video_slug].append(
            {
                "chunk_id": str(item.get("chunk_id", "")).strip(),
                "text": str(item.get("text", "")).strip(),
                "topics": item.get("topics", []),
                "candidate_labels": item.get("candidate_labels", []),
            }
        )
    return dict(by_video)


def select_text_context(
    row: dict[str, Any],
    text_context_by_video: dict[str, list[dict[str, Any]]],
    *,
    max_items: int = 2,
) -> list[dict[str, str]]:
    video_slug = str(row.get("video_slug", "")).strip()
    candidates = text_context_by_video.get(video_slug, [])
    if not candidates:
        return []
    row_terms = normalize_terms(row.get("candidate_labels", [])) | normalize_terms(row.get("cue_terms", []))
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in candidates:
        item_text = " ".join(
            [
                str(item.get("text", "")),
                " ".join(str(value) for value in item.get("topics", []) or []),
                " ".join(str(value) for value in item.get("candidate_labels", []) or []),
            ]
        ).lower().replace("-", "_")
        overlap = sum(1 for term in row_terms if term and term in item_text)
        if overlap:
            scored.append((overlap, item))
    scored.sort(key=lambda entry: entry[0], reverse=True)
    return [
        {
            "chunk_id": str(item.get("chunk_id", "")),
            "text_excerpt": str(item.get("text", ""))[:280],
            "overlap_score": str(score),
        }
        for score, item in scored[:max_items]
    ]


def load_embedding_vectors(root_dir: Path) -> dict[str, list[float]]:
    vector_map: dict[str, list[float]] = {}
    for path in (
        root_dir / "knowledge" / "ttfm_video_corpus" / "visual_embedding_index.json",
        root_dir / "knowledge" / "ttfm_video_corpus" / "dense_visual_embedding_index.json",
    ):
        payload = load_json(path, {})
        for item in payload.get("items", []) if isinstance(payload, dict) else []:
            chunk_id = str(item.get("chunk_id", "")).strip()
            vector = item.get("vector")
            if chunk_id and isinstance(vector, list):
                vector_map[chunk_id] = [float(value) for value in vector]
    return vector_map


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def select_embedding_neighbors(
    example_id: str,
    vector_map: dict[str, list[float]],
    reviewed_classes: dict[str, set[str]],
    *,
    max_items: int = 3,
) -> list[dict[str, Any]]:
    vector = vector_map.get(example_id)
    if vector is None:
        return []
    scored: list[tuple[float, str]] = []
    for reviewed_id, class_names in reviewed_classes.items():
        if reviewed_id == example_id or not class_names:
            continue
        reviewed_vector = vector_map.get(reviewed_id)
        if reviewed_vector is None:
            continue
        score = cosine_similarity(vector, reviewed_vector)
        scored.append((score, reviewed_id))
    scored.sort(key=lambda entry: entry[0], reverse=True)
    return [
        {
            "example_id": reviewed_id,
            "similarity": round(score, 6),
            "class_names": sorted(reviewed_classes.get(reviewed_id, []), key=YOLO_CLASS_NAMES.index),
        }
        for score, reviewed_id in scored[:max_items]
        if score > 0
    ]


def is_metadata_only(row: dict[str, Any], text: str) -> bool:
    transcript_source = str(row.get("transcript_source", "")).strip().lower()
    has_chart_marker = any(marker in text for marker in CHART_MARKERS)
    has_narrated_chart_marker = any(marker in text for marker in NARRATED_CHART_MARKERS)
    if "educational_channel" in text and not has_narrated_chart_marker:
        return True
    if transcript_source != "synthetic_from_video_metadata":
        return "educational_channel" in text and not has_chart_marker
    return not has_chart_marker


def score_row(
    row: dict[str, Any],
    *,
    root_dir: Path,
    audio_contexts: dict[tuple[str, str], str],
    text_context_by_video: dict[str, list[dict[str, Any]]],
    vector_map: dict[str, list[float]],
    reviewed_classes: dict[str, set[str]],
    reviewed_ids: set[str],
    skip_image_quality: bool = False,
) -> tuple[dict[str, Any] | None, str | None]:
    example_id = str(row.get("window_id") or row.get("example_id") or row.get("chunk_id") or "").strip()
    if not example_id:
        return None, "missing_example_id"
    if example_id in reviewed_ids:
        return None, "already_reviewed"

    raw_image_path = str(row.get("frame_path") or row.get("image_path") or "").strip()
    image_path = resolve_path(root_dir, raw_image_path)
    if image_path is None or not image_path.exists():
        return None, "missing_image"

    if not skip_image_quality and is_teaching_slide_image(image_path):
        return None, "teaching_slide_image"

    video_slug = str(row.get("video_slug", "")).strip()
    checkpoint = str(row.get("checkpoint", "")).strip()
    audio_text = audio_contexts.get((video_slug, checkpoint), "")
    text = text_blob(row, audio_text=audio_text)
    if is_metadata_only(row, text):
        return None, "metadata_only"

    candidate_classes = infer_v1_classes(row, audio_text=audio_text)
    text_context = select_text_context(row, text_context_by_video)
    neighbors = select_embedding_neighbors(example_id, vector_map, reviewed_classes)

    score = 0
    reasons: list[str] = []
    source_type = str(row.get("source_type", "")).strip()
    if source_type == "youtube_visual_window":
        score += 15
        reasons.append("checkpoint_visual_window")
    elif source_type == "youtube_dense_window":
        score += 8
        reasons.append("dense_visual_window")

    checkpoint_weight = {
        "sweep": 10,
        "confirmation": 8,
        "closure": 6,
        "outcome": 4,
        "context": 3,
    }.get(checkpoint, 1)
    score += checkpoint_weight
    if checkpoint_weight > 1:
        reasons.append(f"checkpoint:{checkpoint}")

    if candidate_classes:
        score += len(candidate_classes) * 12
        reasons.append("mapped_yolo_classes")
    for class_name in candidate_classes:
        if class_name in SCARCE_CLASS_NAMES:
            score += 12
            reasons.append(f"scarce_class:{class_name}")

    cue_count = len(set(row.get("cue_terms", []) or []))
    if cue_count:
        score += min(10, cue_count)
        reasons.append("cue_terms")
    if audio_text:
        score += 8
        reasons.append("audio_semantic_context")
    if text_context:
        score += 5
        reasons.append("google_text_embedding_context")
    if neighbors:
        score += min(9, len(neighbors) * 3)
        reasons.append("accepted_visual_embedding_neighbors")

    if not candidate_classes:
        score = max(score, 18)
        recommended_action = "hard_negative_review"
        reasons.append("chart_like_no_mapped_class")
    elif score >= 55:
        recommended_action = "accept_or_adjust"
    else:
        recommended_action = "review"

    item = {
        "example_id": example_id,
        "source_type": source_type,
        "video_slug": video_slug,
        "checkpoint": checkpoint,
        "start": row.get("start"),
        "image_path": str(image_path),
        "relative_image_path": str(image_path.relative_to(root_dir)) if image_path.is_relative_to(root_dir) else str(image_path),
        "title": str(row.get("title", "")),
        "score": round(float(score), 4),
        "recommended_action": recommended_action,
        "candidate_labels": candidate_classes,
        "raw_candidate_labels": list(row.get("candidate_labels", []) or []),
        "cue_terms": list(row.get("cue_terms", []) or []),
        "selection_reasons": sorted(set(reasons)),
        "transcript_excerpt": str(row.get("text") or row.get("nearby_transcript_text") or "")[:500],
        "audio_excerpt": audio_text[:500],
        "google_text_context": text_context,
        "embedding_neighbors": neighbors,
    }
    return item, None


def build_candidate_rows(root_dir: Path) -> list[dict[str, Any]]:
    corpus_dir = root_dir / "knowledge" / "ttfm_video_corpus"
    rows: list[dict[str, Any]] = []
    rows.extend(load_jsonl(corpus_dir / "visual_windows.jsonl"))
    rows.extend(load_jsonl(corpus_dir / "dense_visual_windows.jsonl"))
    return rows


def summarize_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts = Counter(str(item.get("recommended_action", "")) for item in items)
    class_counts: Counter[str] = Counter()
    source_counts = Counter(str(item.get("source_type", "")) for item in items)
    for item in items:
        for class_name in item.get("candidate_labels", []):
            class_counts[str(class_name)] += 1
    return {
        "action_counts": dict(action_counts),
        "candidate_class_counts": dict(class_counts),
        "source_counts": dict(source_counts),
    }


def resolve_output_path(root_dir: Path, output_path: Path) -> Path:
    return output_path if output_path.is_absolute() else root_dir / output_path


def build_phase2_answer_template(packet: dict[str, Any]) -> dict[str, Any]:
    template_items: list[dict[str, Any]] = []
    for item in packet.get("items", []):
        candidate_labels = [str(label) for label in item.get("candidate_labels", [])]
        note_bits = [
            "Review required before YOLO promotion.",
            f"recommended_action={item.get('recommended_action', '')}",
        ]
        if candidate_labels:
            note_bits.append(f"candidate_labels={','.join(candidate_labels)}")
        template_items.append(
            {
                "example_id": str(item.get("example_id", "")).strip(),
                "detections": [],
                "review_outcome": "ambiguous",
                "note": " ".join(bit for bit in note_bits if bit.strip()),
                "source": "ttfm_corpus_prep_review",
                "image_path": str(item.get("image_path", "")),
                "candidate_labels": candidate_labels,
                "recommended_action": str(item.get("recommended_action", "")),
                "score": item.get("score"),
            }
        )
    return {
        "generated_at": packet.get("generated_at"),
        "mode": "ttfm_corpus_prep_phase2_answers_template",
        "source_packet_mode": packet.get("mode"),
        "instructions": (
            "Copy reviewed items from this template into a Phase 2 supervision answers file only "
            "after adding normalized YOLO detections or marking true hard negatives as no_setup. "
            "Rows left as ambiguous are ignored by the Phase 2 answer loader."
        ),
        "items": template_items,
    }


def build_prep_packet(config: CorpusPrepConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    root_dir = config.root_dir.resolve()
    rows = build_candidate_rows(root_dir)
    reviewed_classes, reviewed_ids = load_reviewed_examples(root_dir)
    audio_contexts = load_audio_context(root_dir)
    text_context_by_video = load_text_embedding_context(root_dir)
    vector_map = load_embedding_vectors(root_dir)

    exclusions: Counter[str] = Counter()
    scored_items: list[dict[str, Any]] = []
    hard_negative_items: list[dict[str, Any]] = []
    for row in rows:
        item, exclusion = score_row(
            row,
            root_dir=root_dir,
            audio_contexts=audio_contexts,
            text_context_by_video=text_context_by_video,
            vector_map=vector_map,
            reviewed_classes=reviewed_classes,
            reviewed_ids=reviewed_ids,
            skip_image_quality=config.skip_image_quality,
        )
        if item is None:
            exclusions[str(exclusion or "unknown")] += 1
            continue
        if item["recommended_action"] == "hard_negative_review":
            hard_negative_items.append(item)
        else:
            scored_items.append(item)

    scored_items.sort(key=lambda item: (float(item["score"]), item["example_id"]), reverse=True)
    hard_negative_items.sort(key=lambda item: (float(item["score"]), item["example_id"]), reverse=True)
    selected_items = scored_items[: config.limit] + hard_negative_items[: config.hard_negative_limit]

    manifest_paths = {
        "google_embedding_manifest": root_dir / "knowledge" / "ttfm_video_corpus" / "google_embedding_manifest.json",
        "visual_embedding_manifest": root_dir / "knowledge" / "ttfm_video_corpus" / "visual_embedding_manifest.json",
        "dense_visual_embedding_manifest": root_dir / "knowledge" / "ttfm_video_corpus" / "dense_visual_embedding_manifest.json",
    }
    manifests = {name: load_json(path, {}) for name, path in manifest_paths.items()}
    current_dataset_stats = load_json(root_dir / "results" / "phase2_dataset_stats.json", {})

    generated_at = datetime.now(timezone.utc).isoformat()
    packet = {
        "generated_at": generated_at,
        "mode": "ttfm_corpus_prep_review",
        "instructions": (
            "Review each item before promotion. Candidate labels come from transcript, audio, "
            "Google text embedding context, and visual embedding neighbors; they are not ground truth."
        ),
        "item_count": len(selected_items),
        "items": selected_items,
    }
    report = {
        "generated_at": generated_at,
        "input_counts": {
            "candidate_rows": len(rows),
            "reviewed_ids": len(reviewed_ids),
            "reviewed_with_classes": len(reviewed_classes),
            "audio_context_keys": len(audio_contexts),
            "text_embedding_videos": len(text_context_by_video),
            "visual_vectors": len(vector_map),
        },
        "eligible_count": len(scored_items) + len(hard_negative_items),
        "selected_count": len(selected_items),
        "selected_positive_count": len(scored_items[: config.limit]),
        "selected_hard_negative_count": len(hard_negative_items[: config.hard_negative_limit]),
        "exclusion_counts": dict(exclusions),
        "selected_summary": summarize_items(selected_items),
        "all_eligible_summary": summarize_items(scored_items + hard_negative_items),
        "current_yolo_dataset": {
            "train_count": current_dataset_stats.get("train_count", 0),
            "val_count": current_dataset_stats.get("val_count", 0),
            "benchmark_count": current_dataset_stats.get("benchmark_count", 0),
            "class_counts": current_dataset_stats.get("class_counts", {}),
        },
        "manifests": {
            name: {
                "generated_at": payload.get("generated_at"),
                "item_count": payload.get("item_count"),
                "source_path": payload.get("source_path"),
                "source_fingerprint": payload.get("source_fingerprint"),
                "model": payload.get("model"),
            }
            for name, payload in manifests.items()
        },
        "review_artifacts": {
            "phase2_answer_template_path": str(resolve_output_path(root_dir, config.output_answer_template_path).resolve()),
            "answer_template_mode": "ambiguous_until_reviewed",
        },
        "training_gate": {
            "ready_to_train_from_packet": False,
            "reason": "Prep packet candidates must be reviewed or explicitly promoted before Phase 2 exports YOLO labels.",
            "minimum_train_images_for_confidence": 150,
            "minimum_val_images_for_confidence": 40,
            "hard_negative_target": 25,
        },
    }
    return packet, report


def write_outputs(packet: dict[str, Any], report: dict[str, Any], config: CorpusPrepConfig) -> None:
    packet_path = resolve_output_path(config.root_dir, config.output_packet_path)
    report_path = resolve_output_path(config.root_dir, config.output_report_path)
    answer_template_path = resolve_output_path(config.root_dir, config.output_answer_template_path)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    answer_template_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    answer_template_path.write_text(json.dumps(build_phase2_answer_template(packet), indent=2), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a conservative corpus prep review packet from TTFM video, transcript, audio, and embedding artifacts."
    )
    parser.add_argument("--root-dir", type=Path, default=Path.cwd())
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--hard-negative-limit", type=int, default=DEFAULT_HARD_NEGATIVE_LIMIT)
    parser.add_argument("--output-packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--output-answer-template", type=Path, default=DEFAULT_ANSWER_TEMPLATE_PATH)
    parser.add_argument("--skip-image-quality", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    args = build_arg_parser().parse_args(argv)
    config = CorpusPrepConfig(
        root_dir=args.root_dir,
        limit=args.limit,
        hard_negative_limit=args.hard_negative_limit,
        output_packet_path=args.output_packet,
        output_report_path=args.output_report,
        output_answer_template_path=args.output_answer_template,
        skip_image_quality=args.skip_image_quality,
    )
    packet, report = build_prep_packet(config)
    write_outputs(packet, report, config)
    print(
        json.dumps(
            {
                "packet_path": str(resolve_output_path(config.root_dir, config.output_packet_path).resolve()),
                "report_path": str(resolve_output_path(config.root_dir, config.output_report_path).resolve()),
                "answer_template_path": str(resolve_output_path(config.root_dir, config.output_answer_template_path).resolve()),
                "item_count": packet["item_count"],
                "selected_summary": report["selected_summary"],
                "exclusion_counts": report["exclusion_counts"],
            },
            indent=2,
        )
    )
    return packet, report


if __name__ == "__main__":
    main()
