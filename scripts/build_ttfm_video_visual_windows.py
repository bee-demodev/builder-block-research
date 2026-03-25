from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ttfm_video_embeddings as tve


ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
VIDEO_MANIFEST_PATH = CORPUS_DIR / "video_manifest.json"
CHUNKS_PATH = CORPUS_DIR / "chunks.jsonl"
DEFAULT_VIDEO_DIR = CORPUS_DIR / "videos"
DEFAULT_FRAME_DIR = CORPUS_DIR / "frames"
DEFAULT_OUTPUT = CORPUS_DIR / "visual_windows.jsonl"
DEFAULT_REPORT_OUTPUT = CORPUS_DIR / "visual_windows_report.json"
DEFAULT_TAXONOMY_PATH = ROOT / "data" / "ttfm_component_taxonomy.json"
SUPPORTED_VIDEO_SUFFIXES = (".mp4", ".mkv", ".webm", ".mov")

CHECKPOINT_ORDER = (
    ("context", "htf", 0.10),
    ("sweep", "etf", 0.30),
    ("closure", "ltf", 0.50),
    ("confirmation", "ltf", 0.70),
    ("outcome", "etf", 0.90),
)

CHECKPOINT_CUE_TERMS = {
    "context": (
        "bias",
        "framework",
        "higher timeframe",
        "premium",
        "discount",
        "equilibrium",
        "point of interest",
        "poi",
    ),
    "sweep": (
        "sweep",
        "liquidity",
        "take the highs",
        "take the lows",
        "run the highs",
        "run the lows",
    ),
    "closure": (
        "closure",
        "candle 2",
        "candle 3",
        "cisd",
        "close through",
        "engulf",
    ),
    "confirmation": (
        "confirmation",
        "entry",
        "retest",
        "order block",
        "breaker",
        "fair value gap",
        "protected swing",
    ),
    "outcome": (
        "target",
        "expansion",
        "outcome",
        "invalidation",
        "take profit",
        "stop",
    ),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def normalize_text(text: str) -> str:
    return " ".join(str(text).replace("_", " ").replace("-", " ").lower().split())


def load_component_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> dict:
    return load_json(path)


def enumerate_chunks(chunk_rows: list[dict]) -> list[dict]:
    counters: dict[str, int] = defaultdict(int)
    normalized_rows: list[dict] = []
    for row in chunk_rows:
        video_slug = str(row.get("video_slug", "")).strip()
        if not video_slug:
            continue
        chunk_index = counters[video_slug]
        counters[video_slug] += 1
        normalized_rows.append(
            {
                **row,
                "chunk_id": str(row.get("chunk_id", "")).strip()
                or f"{video_slug}:{chunk_index:04d}",
            }
        )
    return normalized_rows


def index_chunks_by_video(chunk_rows: list[dict]) -> dict[str, list[dict]]:
    indexed: dict[str, list[dict]] = defaultdict(list)
    for row in enumerate_chunks(chunk_rows):
        indexed[str(row.get("video_slug", "")).strip()].append(row)
    return indexed


def infer_candidate_labels(
    checkpoint: str,
    *,
    text: str,
    video_topics: list[str],
    taxonomy: dict,
) -> tuple[list[str], list[str]]:
    normalized_text = normalize_text(text)
    normalized_topics = {normalize_text(topic) for topic in video_topics}
    labels: list[str] = []
    matched_terms: list[str] = []

    for component in taxonomy.get("components", []):
        if checkpoint not in component.get("checkpoints", []):
            continue

        matched = False
        for marker in component.get("markers", []):
            normalized_marker = normalize_text(marker)
            if normalized_marker and normalized_marker in normalized_text:
                matched = True
                matched_terms.append(normalized_marker)
        for topic in component.get("supporting_topics", []):
            normalized_topic = normalize_text(topic)
            if normalized_topic and normalized_topic in normalized_topics:
                matched = True
                matched_terms.append(normalized_topic)

        if matched:
            labels.append(str(component.get("label", "")).strip())

    return sorted(set(label for label in labels if label)), sorted(set(matched_terms))


def score_chunk_for_checkpoint(row: dict, checkpoint: str, taxonomy: dict) -> dict[str, Any]:
    normalized_text = normalize_text(str(row.get("text", "")))
    cue_terms: list[str] = []
    score = 0

    for cue in CHECKPOINT_CUE_TERMS[checkpoint]:
        normalized_cue = normalize_text(cue)
        occurrences = normalized_text.count(normalized_cue)
        if occurrences:
            cue_terms.append(normalized_cue)
            score += occurrences

    candidate_labels, label_terms = infer_candidate_labels(
        checkpoint,
        text=str(row.get("text", "")),
        video_topics=[str(topic).strip() for topic in row.get("topics", []) if str(topic).strip()],
        taxonomy=taxonomy,
    )
    score += len(candidate_labels) * 2

    return {
        "score": score,
        "candidate_labels": candidate_labels,
        "cue_terms": sorted(set(cue_terms + label_terms)),
    }


def chunk_relative_position(chunk: dict, *, max_end: float) -> float:
    if max_end <= 0.0:
        return 0.5
    midpoint = (float(chunk.get("start", 0.0)) + float(chunk.get("end", 0.0))) / 2.0
    return midpoint / max_end


def select_chunk_for_checkpoint(
    chunks: list[dict],
    checkpoint: str,
    *,
    taxonomy: dict,
    target_position: float,
    used_chunk_ids: set[str],
) -> dict[str, Any]:
    max_end = max(float(chunk.get("end", 0.0)) for chunk in chunks) if chunks else 0.0
    candidates: list[dict[str, Any]] = []
    for chunk in chunks:
        metrics = score_chunk_for_checkpoint(chunk, checkpoint, taxonomy)
        candidates.append(
            {
                "chunk": chunk,
                "score": int(metrics["score"]),
                "candidate_labels": metrics["candidate_labels"],
                "cue_terms": metrics["cue_terms"],
                "distance": abs(
                    chunk_relative_position(chunk, max_end=max_end) - float(target_position)
                ),
            }
        )

    def choose(pool: list[dict[str, Any]]) -> dict[str, Any]:
        return max(
            pool,
            key=lambda item: (
                1 if item["score"] > 0 else 0,
                item["score"],
                len(item["candidate_labels"]),
                -float(item["distance"]),
            ),
        )

    unused_candidates = [
        candidate
        for candidate in candidates
        if str(candidate["chunk"].get("chunk_id", "")) not in used_chunk_ids
    ]
    selected = choose(unused_candidates or candidates)
    used_chunk_ids.add(str(selected["chunk"].get("chunk_id", "")))
    return selected


def resolve_local_video_path(video: dict, video_dir: Path) -> Path | None:
    candidates = [
        str(video.get("slug", "")).strip(),
        str(video.get("video_id", "")).strip(),
    ]
    for base_name in candidates:
        if not base_name:
            continue
        for suffix in SUPPORTED_VIDEO_SUFFIXES:
            candidate = video_dir / f"{base_name}{suffix}"
            if candidate.exists():
                return candidate
    return None


def planned_frame_path(frame_dir: Path, *, video_slug: str, checkpoint: str, timestamp_seconds: float) -> Path:
    timestamp_ms = int(round(timestamp_seconds * 1000))
    return frame_dir / video_slug / f"{checkpoint}_{timestamp_ms:08d}.jpg"


def extract_frame(
    video_path: Path,
    *,
    timestamp_seconds: float,
    output_path: Path,
    ffmpeg_bin: str,
) -> tuple[str, str | None]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_bin,
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{timestamp_seconds:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "ffmpeg_missing", "ffmpeg was not found on PATH."

    if completed.returncode != 0:
        error_text = completed.stderr.strip() or completed.stdout.strip() or "ffmpeg extraction failed."
        return "extract_failed", error_text
    if not output_path.exists():
        return "extract_failed", "ffmpeg completed without creating the frame output."
    return "extracted", None


def build_market_context(checkpoint: str) -> dict:
    return {
        "alignment_status": "youtube_visual_window",
        "mapping_provenance": "youtube_transcript_checkpoint_heuristic",
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
        "confidence": 0.35,
        "notes": (
            "Checkpoint window inferred from YouTube transcript cues to seed visual review and multimodal retrieval. "
            f"Active checkpoint: {checkpoint}."
        ),
    }


def build_visual_window_row(
    video: dict,
    selection: dict[str, Any],
    *,
    timeframe_role: str,
    video_path: Path | None,
    frame_dir: Path,
    extract_frames: bool,
    ffmpeg_bin: str,
) -> dict:
    chunk = selection["chunk"]
    checkpoint = str(selection["checkpoint"])
    midpoint_seconds = (float(chunk.get("start", 0.0)) + float(chunk.get("end", 0.0))) / 2.0
    frame_output_path = planned_frame_path(
        frame_dir,
        video_slug=str(video.get("slug", "")).strip(),
        checkpoint=checkpoint,
        timestamp_seconds=midpoint_seconds,
    )

    if video_path is None:
        frame_status = "missing_video"
        frame_error = "No local video file was found for this YouTube manifest row."
        frame_path_value = None
    elif extract_frames:
        frame_status, frame_error = extract_frame(
            video_path,
            timestamp_seconds=midpoint_seconds,
            output_path=frame_output_path,
            ffmpeg_bin=ffmpeg_bin,
        )
        frame_path_value = tve.path_for_manifest(frame_output_path) if frame_output_path.exists() else None
    else:
        frame_status = "pending_extraction"
        frame_error = None
        frame_path_value = tve.path_for_manifest(frame_output_path)

    case_ref = f"youtube_{video['slug']}_visual_v1"
    window_id = f"{case_ref}::{checkpoint}"
    candidate_labels = list(selection["candidate_labels"])
    cue_terms = list(selection["cue_terms"])
    transcript_text = str(chunk.get("text", "")).strip()

    return {
        "window_id": window_id,
        "example_id": window_id,
        "case_ref": case_ref,
        "source_type": "youtube_visual_window",
        "video_slug": str(video.get("slug", "")).strip(),
        "video_id": str(video.get("video_id", "")).strip(),
        "title": str(video.get("title", "")).strip(),
        "source_url": str(video.get("url", "")).strip(),
        "source_page": str(video.get("source_page", "")).strip(),
        "corpus_partition": str(video.get("corpus_partition", "seed_curriculum")).strip()
        or "seed_curriculum",
        "transcript_source": str(video.get("transcript_source", "")).strip() or None,
        "review_categories": [
            str(category).strip()
            for category in video.get("review_categories", [])
            if str(category).strip()
        ],
        "discovery_source": str(video.get("discovery_source", "seed_curriculum")).strip()
        or "seed_curriculum",
        "topics": [str(topic).strip() for topic in video.get("topics", []) if str(topic).strip()],
        "supporting_topics": [str(topic).strip() for topic in video.get("topics", []) if str(topic).strip()],
        "checkpoint": checkpoint,
        "timeframe": timeframe_role,
        "timeframe_role": timeframe_role,
        "start": float(chunk.get("start", 0.0)),
        "end": float(chunk.get("end", 0.0)),
        "midpoint_seconds": midpoint_seconds,
        "source_chunk_id": str(chunk.get("chunk_id", "")).strip(),
        "nearby_transcript_text": transcript_text,
        "text": transcript_text,
        "cue_score": int(selection["score"]),
        "cue_terms": cue_terms,
        "candidate_labels": candidate_labels,
        "candidate_label_provenance": "youtube_transcript_checkpoint_heuristic",
        "video_path": tve.path_for_manifest(video_path) if video_path else None,
        "frame_path": frame_path_value,
        "chart_crop_path": None,
        "frame_status": frame_status,
        "frame_error": frame_error,
        "market_context": build_market_context(checkpoint),
        "embedding_text": tve.build_visual_embedding_text(
            title=str(video.get("title", "")).strip(),
            checkpoint=checkpoint,
            topics=[str(topic).strip() for topic in video.get("topics", []) if str(topic).strip()],
            text=transcript_text,
            cue_terms=cue_terms,
            candidate_labels=candidate_labels,
        ),
    }


def build_visual_windows_dataset(
    video_manifest: dict,
    chunk_rows: list[dict],
    *,
    taxonomy: dict,
    video_dir: Path,
    frame_dir: Path,
    extract_frames: bool,
    ffmpeg_bin: str,
) -> tuple[list[dict], dict]:
    chunks_by_video = index_chunks_by_video(chunk_rows)
    rows: list[dict] = []
    checkpoint_counts: Counter[str] = Counter()
    frame_status_counts: Counter[str] = Counter()
    with_local_video_count = 0
    missing_chunk_video_count = 0

    for video in video_manifest.get("videos", []):
        video_slug = str(video.get("slug", "")).strip()
        video_chunks = chunks_by_video.get(video_slug, [])
        if not video_chunks:
            missing_chunk_video_count += 1
            continue

        video_path = resolve_local_video_path(video, video_dir)
        if video_path is not None:
            with_local_video_count += 1

        used_chunk_ids: set[str] = set()
        for checkpoint, timeframe_role, target_position in CHECKPOINT_ORDER:
            selection = select_chunk_for_checkpoint(
                video_chunks,
                checkpoint,
                taxonomy=taxonomy,
                target_position=target_position,
                used_chunk_ids=used_chunk_ids,
            )
            selection["checkpoint"] = checkpoint
            row = build_visual_window_row(
                video,
                selection,
                timeframe_role=timeframe_role,
                video_path=video_path,
                frame_dir=frame_dir,
                extract_frames=extract_frames,
                ffmpeg_bin=ffmpeg_bin,
            )
            rows.append(row)
            checkpoint_counts[checkpoint] += 1
            frame_status_counts[str(row.get("frame_status", "unknown"))] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "window_count": len(rows),
            "video_count": int(video_manifest.get("video_count", len(video_manifest.get("videos", [])))),
            "with_local_video_count": with_local_video_count,
            "missing_chunk_video_count": missing_chunk_video_count,
            "checkpoint_counts": dict(sorted(checkpoint_counts.items())),
            "frame_status_counts": dict(sorted(frame_status_counts.items())),
            "extract_frames": extract_frames,
        },
    }
    return rows, report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build checkpoint-level YouTube visual windows for the TTFM corpus, with optional frame extraction."
        )
    )
    parser.add_argument("--video-manifest", type=Path, default=VIDEO_MANIFEST_PATH)
    parser.add_argument("--chunks-path", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--taxonomy-path", type=Path, default=DEFAULT_TAXONOMY_PATH)
    parser.add_argument("--video-dir", type=Path, default=DEFAULT_VIDEO_DIR)
    parser.add_argument("--frame-dir", type=Path, default=DEFAULT_FRAME_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--extract-frames", action="store_true")
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    args = parser.parse_args()

    video_manifest = load_json(args.video_manifest)
    chunk_rows = load_jsonl(args.chunks_path)
    taxonomy = load_component_taxonomy(args.taxonomy_path)
    rows, report = build_visual_windows_dataset(
        video_manifest,
        chunk_rows,
        taxonomy=taxonomy,
        video_dir=args.video_dir,
        frame_dir=args.frame_dir,
        extract_frames=args.extract_frames,
        ffmpeg_bin=args.ffmpeg_bin,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
