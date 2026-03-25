from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEAK_DATASET_PATH = ROOT / "results" / "ttfm_video_weak_visual_dataset.jsonl"
DEFAULT_WINDOW_DATASET_PATH = ROOT / "knowledge" / "ttfm_video_corpus" / "visual_windows.jsonl"
DEFAULT_AUDIO_OUTPUT_DIR = ROOT / "knowledge" / "ttfm_video_corpus" / "audio_clips"
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "ttfm_video_multimodal_dataset.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_video_multimodal_dataset_report.json"
DEFAULT_CLIP_DURATION_SECONDS = 6.0


def load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if cleaned:
            rows.append(json.loads(cleaned))
    return rows


def normalize_string_list(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    if isinstance(values, str):
        cleaned = values.strip()
        return [cleaned] if cleaned else []
    return []


def path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def resolve_repo_path(path_value: str) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def build_audio_clip_output_path(
    window_row: dict[str, Any],
    *,
    audio_output_dir: Path,
    checkpoint: str | None = None,
) -> Path:
    video_slug = str(window_row.get("video_slug", "")).strip() or "unknown_video"
    checkpoint_name = (
        str(checkpoint).strip()
        if checkpoint is not None
        else str(window_row.get("checkpoint", "")).strip()
    ) or "unknown"
    midpoint_seconds = float(window_row.get("midpoint_seconds", 0.0) or 0.0)
    midpoint_millis = int(round(midpoint_seconds * 1000.0))
    filename = f"{checkpoint_name}_{midpoint_millis:08d}.wav"
    return audio_output_dir / video_slug / filename


def build_video_multimodal_dataset_report(
    *,
    weak_rows: list[dict[str, Any]],
    window_rows: list[dict[str, Any]],
    audio_output_dir: Path,
    clip_duration_seconds: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    window_lookup = {
        str(row.get("example_id", "")).strip(): row
        for row in window_rows
        if str(row.get("example_id", "")).strip()
    }
    rows: list[dict[str, Any]] = []
    skipped_missing_window_count = 0
    review_status_counts: Counter[str] = Counter()

    for weak_row in weak_rows:
        example_id = str(weak_row.get("example_id", "")).strip()
        window_row = window_lookup.get(example_id)
        if not window_row:
            skipped_missing_window_count += 1
            continue

        audio_output_path = build_audio_clip_output_path(
            window_row,
            audio_output_dir=audio_output_dir,
            checkpoint=str(weak_row.get("checkpoint", "")).strip() or None,
        )
        review_status = str(weak_row.get("review_status", "")).strip() or "unknown"
        review_status_counts[review_status] += 1

        rows.append(
            {
                "example_id": example_id,
                "case_ref": str(weak_row.get("case_ref", "")).strip(),
                "video_slug": str(window_row.get("video_slug", "")).strip() or None,
                "video_id": str(window_row.get("video_id", "")).strip() or None,
                "title": str(window_row.get("title", "")).strip() or None,
                "checkpoint": str(weak_row.get("checkpoint", "")).strip()
                or str(window_row.get("checkpoint", "")).strip()
                or "unknown",
                "active_labels": normalize_string_list(weak_row.get("active_labels")),
                "weak_label_confidence": float(weak_row.get("weak_label_confidence", 0.35) or 0.35),
                "sample_weight": float(
                    weak_row.get(
                        "sample_weight",
                        weak_row.get("weak_label_confidence", 0.35),
                    )
                    or 0.35
                ),
                "eligible_for_training": bool(weak_row.get("eligible_for_training", False)),
                "review_status": review_status,
                "contradiction_status": str(weak_row.get("contradiction_status", "")).strip() or "unknown",
                "training_blockers": normalize_string_list(weak_row.get("training_blockers")),
                "screenshot_path": str(weak_row.get("screenshot_path", "")).strip()
                or str(window_row.get("frame_path", "")).strip()
                or None,
                "video_path": str(window_row.get("video_path", "")).strip() or None,
                "audio_path": path_for_manifest(audio_output_path),
                "clip_duration_seconds": float(clip_duration_seconds),
                "midpoint_seconds": float(window_row.get("midpoint_seconds", 0.0) or 0.0),
                "window_start_seconds": float(window_row.get("start", 0.0) or 0.0),
                "window_end_seconds": float(window_row.get("end", 0.0) or 0.0),
                "transcript_text": str(window_row.get("nearby_transcript_text", "")).strip()
                or str(window_row.get("text", "")).strip()
                or None,
                "transcript_source": str(window_row.get("transcript_source", "")).strip() or None,
                "embedding_text": str(window_row.get("embedding_text", "")).strip() or None,
                "evidence_refs": normalize_string_list(weak_row.get("evidence_refs"))
                or normalize_string_list(window_row.get("evidence_refs")),
                "source_url": str(window_row.get("source_url", "")).strip() or None,
                "source_page": str(window_row.get("source_page", "")).strip() or None,
                "source_chunk_id": str(window_row.get("source_chunk_id", "")).strip() or None,
                "corpus_partition": str(window_row.get("corpus_partition", "seed_curriculum")).strip()
                or "seed_curriculum",
                "review_categories": [
                    str(category).strip()
                    for category in window_row.get("review_categories", [])
                    if str(category).strip()
                ],
                "framework_slug": "ttfm",
                "profile_slug": "ttrades_curriculum",
                "brain_type": "setup_scorer",
                "embedding_backend": "google_gemini",
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "row_count": len(rows),
            "input_weak_row_count": len(weak_rows),
            "input_window_row_count": len(window_rows),
            "audio_clip_job_count": len(rows),
            "skipped_missing_window_count": skipped_missing_window_count,
            "ready_for_weak_training_count": review_status_counts.get("ready_for_weak_training", 0),
            "eligible_for_training_count": sum(1 for row in rows if bool(row.get("eligible_for_training"))),
            "review_status_counts": dict(sorted(review_status_counts.items())),
        },
    }
    return rows, report


def extract_audio_clip(
    *,
    video_path: Path,
    audio_path: Path,
    midpoint_seconds: float,
    clip_duration_seconds: float,
    ffmpeg_bin: str,
) -> None:
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    clip_start = max(0.0, midpoint_seconds - (clip_duration_seconds / 2.0))
    subprocess.run(
        [
            ffmpeg_bin,
            "-y",
            "-ss",
            f"{clip_start:.3f}",
            "-t",
            f"{clip_duration_seconds:.3f}",
            "-i",
            str(video_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def materialize_audio_clips(
    rows: list[dict[str, Any]],
    *,
    ffmpeg_bin: str,
) -> dict[str, int]:
    extracted_count = 0
    skipped_existing_count = 0
    missing_video_count = 0

    for row in rows:
        video_path_value = str(row.get("video_path", "")).strip()
        audio_path_value = str(row.get("audio_path", "")).strip()
        if not video_path_value or not audio_path_value:
            missing_video_count += 1
            continue

        video_path = resolve_repo_path(video_path_value)
        audio_path = resolve_repo_path(audio_path_value)
        if not video_path.exists():
            missing_video_count += 1
            continue
        if audio_path.exists():
            skipped_existing_count += 1
            continue

        extract_audio_clip(
            video_path=video_path,
            audio_path=audio_path,
            midpoint_seconds=float(row.get("midpoint_seconds", 0.0) or 0.0),
            clip_duration_seconds=float(row.get("clip_duration_seconds", DEFAULT_CLIP_DURATION_SECONDS)),
            ffmpeg_bin=ffmpeg_bin,
        )
        extracted_count += 1

    return {
        "audio_clips_extracted_count": extracted_count,
        "audio_clips_skipped_existing_count": skipped_existing_count,
        "audio_clips_missing_video_count": missing_video_count,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a joined image+transcript+audio dataset from the TTFM video weak visual rows."
    )
    parser.add_argument("--weak-dataset", default=str(DEFAULT_WEAK_DATASET_PATH))
    parser.add_argument("--window-dataset", default=str(DEFAULT_WINDOW_DATASET_PATH))
    parser.add_argument("--audio-output-dir", default=str(DEFAULT_AUDIO_OUTPUT_DIR))
    parser.add_argument("--output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    parser.add_argument("--clip-duration-seconds", type=float, default=DEFAULT_CLIP_DURATION_SECONDS)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    args = parser.parse_args()

    rows, report = build_video_multimodal_dataset_report(
        weak_rows=load_jsonl_rows(Path(args.weak_dataset)),
        window_rows=load_jsonl_rows(Path(args.window_dataset)),
        audio_output_dir=Path(args.audio_output_dir),
        clip_duration_seconds=args.clip_duration_seconds,
    )
    clip_stats = materialize_audio_clips(rows, ffmpeg_bin=args.ffmpeg_bin)
    report["summary"].update(clip_stats)

    output_path = Path(args.output)
    report_path = Path(args.report_output)
    write_jsonl(output_path, rows)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "dataset_output": str(output_path),
                "report_output": str(report_path),
                "row_count": report["summary"]["row_count"],
                "audio_clips_extracted_count": report["summary"]["audio_clips_extracted_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
