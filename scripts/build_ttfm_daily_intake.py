from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
DEFAULT_INTAKE_ROOT = ROOT / "intake"
DEFAULT_INTAKE_VIDEOS_DIR = DEFAULT_INTAKE_ROOT / "videos"
DEFAULT_INTAKE_IMAGES_DIR = DEFAULT_INTAKE_ROOT / "images"
DEFAULT_VIDEO_MANIFEST_OUTPUT = CORPUS_DIR / "daily_intake_video_manifest.json"
DEFAULT_IMAGE_CASES_OUTPUT = ROOT / "results" / "ttfm_daily_intake_image_cases.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_daily_intake_report.json"
VIDEO_SUFFIXES = (".mp4", ".mkv", ".mov", ".webm")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
PROMOTABLE_IMAGE_REVIEW_STATUSES = {
    "ready_for_weak_training",
    "approved_for_teacher",
    "teacher_approved",
}


def path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower())
    return cleaned.strip("_") or "intake_asset"


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def load_sidecar_metadata(asset_path: Path) -> tuple[dict[str, Any], Path | None]:
    metadata_path = asset_path.with_suffix(".json")
    if not metadata_path.exists():
        return {}, None
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}, metadata_path
    return payload, metadata_path


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_video_manifest_row(video_path: Path) -> dict[str, Any]:
    metadata, metadata_path = load_sidecar_metadata(video_path)
    title = str(metadata.get("title", "")).strip() or video_path.stem.replace("_", " ").replace("-", " ").title()
    slug = str(metadata.get("slug", "")).strip() or slugify(video_path.stem)
    transcript_segments = metadata.get("transcript_segments")
    transcript_text = str(metadata.get("transcript_text", "")).strip()
    has_manifest_transcript = bool(transcript_text) or (
        isinstance(transcript_segments, list) and bool(transcript_segments)
    )
    intake_status = "trainable_after_refresh" if has_manifest_transcript else "queued_review_only"

    return {
        "slug": slug,
        "title": title,
        "video_id": str(metadata.get("video_id", "")).strip() or f"local_{slug}",
        "url": str(metadata.get("url", "")).strip() or None,
        "source_url": str(metadata.get("source_url", "")).strip() or None,
        "source_page": str(metadata.get("source_page", "")).strip() or None,
        "topics": normalize_string_list(metadata.get("topics")),
        "review_categories": normalize_string_list(metadata.get("review_categories")),
        "corpus_partition": "daily_intake_video",
        "discovery_source": "daily_local_intake",
        "local_video_path": path_for_manifest(video_path),
        "metadata_path": path_for_manifest(metadata_path) if metadata_path else None,
        "transcript_text": transcript_text or None,
        "transcript_segments": transcript_segments if isinstance(transcript_segments, list) else None,
        "manifest_clip_duration_seconds": metadata.get("manifest_clip_duration_seconds"),
        "intake_status": intake_status,
    }


def build_image_embedding_text(
    *,
    title: str,
    checkpoint: str,
    topics: list[str],
    notes: str,
) -> str:
    lines = [f"Title: {title}", f"Checkpoint: {checkpoint}"]
    if topics:
        lines.append(f"Topics: {', '.join(topics)}")
    if notes:
        lines.append(f"Notes: {notes}")
    return "\n".join(lines)


def build_image_case_row(image_path: Path) -> dict[str, Any]:
    metadata, metadata_path = load_sidecar_metadata(image_path)
    title = str(metadata.get("title", "")).strip() or image_path.stem.replace("_", " ").replace("-", " ").title()
    slug = str(metadata.get("slug", "")).strip() or slugify(image_path.stem)
    checkpoint = str(metadata.get("checkpoint", "")).strip() or "context"
    case_ref = str(metadata.get("case_ref", "")).strip() or f"daily_image_{slug}_v1"
    active_labels = normalize_string_list(metadata.get("active_labels"))
    notes = str(metadata.get("notes", "")).strip() or str(metadata.get("transcript_text", "")).strip()
    topics = normalize_string_list(metadata.get("topics"))
    requested_review_status = str(metadata.get("review_status", "")).strip()

    review_status = requested_review_status
    if not review_status:
        review_status = "ready_for_weak_training" if active_labels else "review_only"

    eligible_for_training = bool(active_labels) and review_status in PROMOTABLE_IMAGE_REVIEW_STATUSES
    training_blockers: list[str] = []
    if not active_labels:
        training_blockers.append("missing_active_labels")
    if not notes:
        training_blockers.append("missing_context_notes")

    if not eligible_for_training and review_status == "ready_for_weak_training":
        review_status = "review_only"

    weak_label_confidence = metadata.get("weak_label_confidence", 0.5 if active_labels else 0.0)
    sample_weight = metadata.get("sample_weight", weak_label_confidence or 0.35)

    return {
        "example_id": f"{case_ref}::{checkpoint}",
        "case_ref": case_ref,
        "video_slug": None,
        "video_id": None,
        "title": title,
        "checkpoint": checkpoint,
        "active_labels": active_labels,
        "weak_label_confidence": float(weak_label_confidence or 0.0),
        "sample_weight": float(sample_weight or 0.35),
        "eligible_for_training": eligible_for_training,
        "review_status": review_status,
        "contradiction_status": "unreviewed",
        "training_blockers": training_blockers,
        "screenshot_path": path_for_manifest(image_path),
        "video_path": None,
        "audio_path": None,
        "clip_duration_seconds": None,
        "midpoint_seconds": None,
        "window_start_seconds": None,
        "window_end_seconds": None,
        "transcript_text": notes,
        "transcript_source": "daily_intake_image_metadata" if notes else None,
        "embedding_text": build_image_embedding_text(
            title=title,
            checkpoint=checkpoint,
            topics=topics,
            notes=notes,
        ),
        "evidence_refs": [
            value
            for value in (
                str(metadata.get("source_url", "")).strip() or None,
                str(metadata.get("source_page", "")).strip() or None,
                path_for_manifest(image_path),
            )
            if value
        ],
        "source_url": str(metadata.get("source_url", "")).strip() or None,
        "source_page": str(metadata.get("source_page", "")).strip() or None,
        "source_chunk_id": None,
        "corpus_partition": "daily_intake_image",
        "review_categories": normalize_string_list(metadata.get("review_categories")),
        "topics": topics,
        "supporting_topics": topics,
        "framework_slug": "ttfm",
        "profile_slug": "ttrades_curriculum",
        "brain_type": "setup_scorer",
        "embedding_backend": "google_gemini",
        "metadata_path": path_for_manifest(metadata_path) if metadata_path else None,
        "source_type": "daily_intake_image",
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def summarize_daily_intake(video_rows: list[dict[str, Any]], image_rows: list[dict[str, Any]]) -> dict[str, Any]:
    video_status_counts: Counter[str] = Counter()
    image_review_status_counts: Counter[str] = Counter()
    image_training_blocker_counts: Counter[str] = Counter()

    for row in video_rows:
        video_status_counts[str(row.get("intake_status", "unknown"))] += 1
    for row in image_rows:
        image_review_status_counts[str(row.get("review_status", "unknown"))] += 1
        for blocker in row.get("training_blockers", []):
            image_training_blocker_counts[str(blocker)] += 1

    return {
        "video_file_count": len(video_rows),
        "image_file_count": len(image_rows),
        "trainable_video_count": video_status_counts.get("trainable_after_refresh", 0),
        "queued_video_count": video_status_counts.get("queued_review_only", 0),
        "trainable_image_count": sum(1 for row in image_rows if bool(row.get("eligible_for_training"))),
        "review_only_image_count": sum(1 for row in image_rows if not bool(row.get("eligible_for_training"))),
        "video_status_counts": dict(sorted(video_status_counts.items())),
        "image_review_status_counts": dict(sorted(image_review_status_counts.items())),
        "image_training_blocker_counts": dict(sorted(image_training_blocker_counts.items())),
    }


def scan_daily_intake(
    *,
    intake_videos_dir: Path,
    intake_images_dir: Path,
    video_manifest_output: Path,
    image_cases_output: Path,
    report_output: Path,
) -> dict[str, Any]:
    ensure_directory(intake_videos_dir)
    ensure_directory(intake_images_dir)

    video_rows = [
        build_video_manifest_row(path)
        for path in sorted(intake_videos_dir.iterdir())
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    ]
    image_rows = [
        build_image_case_row(path)
        for path in sorted(intake_images_dir.iterdir())
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]

    video_manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_source": "daily_local_intake",
        "video_count": len(video_rows),
        "videos": video_rows,
    }
    write_json(video_manifest_output, video_manifest)
    write_jsonl(image_cases_output, image_rows)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "intake_videos_dir": path_for_manifest(intake_videos_dir),
        "intake_images_dir": path_for_manifest(intake_images_dir),
        "video_manifest_output": path_for_manifest(video_manifest_output),
        "image_cases_output": path_for_manifest(image_cases_output),
        "summary": summarize_daily_intake(video_rows, image_rows),
    }
    write_json(report_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan daily intake folders and export local video/image manifests for the TTFM brain workflow."
    )
    parser.add_argument("--intake-videos-dir", type=Path, default=DEFAULT_INTAKE_VIDEOS_DIR)
    parser.add_argument("--intake-images-dir", type=Path, default=DEFAULT_INTAKE_IMAGES_DIR)
    parser.add_argument("--video-manifest-output", type=Path, default=DEFAULT_VIDEO_MANIFEST_OUTPUT)
    parser.add_argument("--image-cases-output", type=Path, default=DEFAULT_IMAGE_CASES_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    args = parser.parse_args()

    report = scan_daily_intake(
        intake_videos_dir=args.intake_videos_dir,
        intake_images_dir=args.intake_images_dir,
        video_manifest_output=args.video_manifest_output,
        image_cases_output=args.image_cases_output,
        report_output=args.report_output,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
