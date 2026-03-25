from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import build_ttfm_video_visual_windows as btvw
import export_ttfm_video_multimodal_dataset as etvmd


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REVIEW_QUEUE_PATH = ROOT / "results" / "ttfm_multimodal_review_queue.json"
DEFAULT_MULTIMODAL_DATASET_PATH = ROOT / "results" / "ttfm_video_multimodal_dataset.jsonl"
DEFAULT_FRAME_OUTPUT_DIR = ROOT / "results" / "ttfm_dense_review" / "frames"
DEFAULT_AUDIO_OUTPUT_DIR = ROOT / "results" / "ttfm_dense_review" / "audio"
DEFAULT_OUTPUT = ROOT / "results" / "ttfm_dense_review_samples.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_dense_review_samples_report.json"
DEFAULT_OFFSETS_SECONDS = (-12, -6, 0, 6, 12)
DEFAULT_CLIP_DURATION_SECONDS = 6.0


def load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return etvmd.load_jsonl_rows(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def normalize_review_queue_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items")
    if isinstance(items, list):
        return items
    return []


def slug_component(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value))
    compact = "_".join(part for part in cleaned.split("_") if part)
    return compact or "sample"


def offset_token(offset_seconds: float) -> str:
    offset_value = int(round(float(offset_seconds)))
    prefix = "plus" if offset_value >= 0 else "minus"
    return f"{prefix}_{abs(offset_value)}s"


def build_sample_id(*, case_ref: str, checkpoint: str, offset_seconds: float) -> str:
    return "__".join(
        [
            slug_component(case_ref),
            slug_component(checkpoint),
            offset_token(offset_seconds),
        ]
    )


def build_dense_review_samples(
    *,
    review_queue_items: list[dict[str, Any]],
    multimodal_rows: list[dict[str, Any]],
    offsets_seconds: Iterable[float] = DEFAULT_OFFSETS_SECONDS,
    frame_output_dir: Path = DEFAULT_FRAME_OUTPUT_DIR,
    audio_output_dir: Path = DEFAULT_AUDIO_OUTPUT_DIR,
    clip_duration_seconds: float = DEFAULT_CLIP_DURATION_SECONDS,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    row_lookup = {
        str(row.get("example_id", "")).strip(): row
        for row in multimodal_rows
        if str(row.get("example_id", "")).strip()
    }
    selected_items = list(review_queue_items[:limit] if limit is not None else review_queue_items)
    offsets = [float(offset) for offset in offsets_seconds]
    samples: list[dict[str, Any]] = []
    sampled_case_ids: set[str] = set()
    skipped_missing_video_count = 0

    for item in selected_items:
        example_id = str(item.get("example_id", "")).strip()
        row = row_lookup.get(example_id)
        video_path = str((row or {}).get("video_path", "")).strip()
        midpoint = (row or {}).get("midpoint_seconds")
        if not video_path or midpoint is None:
            skipped_missing_video_count += 1
            continue

        case_ref = str(item.get("case_ref", "")).strip() or example_id.replace("::", "__")
        checkpoint = str(item.get("checkpoint", "")).strip() or str((row or {}).get("checkpoint", "")).strip() or "unknown"
        video_slug = str(item.get("video_slug", "")).strip() or str((row or {}).get("video_slug", "")).strip() or "unknown_video"
        sampled_case_ids.add(example_id)

        for offset in offsets:
            timestamp_seconds = max(0.0, float(midpoint) + offset)
            sample_id = build_sample_id(
                case_ref=case_ref,
                checkpoint=checkpoint,
                offset_seconds=offset,
            )
            frame_path = frame_output_dir / video_slug / f"{sample_id}.jpg"
            audio_path = audio_output_dir / video_slug / f"{sample_id}.wav"
            samples.append(
                {
                    "sample_id": sample_id,
                    "parent_example_id": example_id,
                    "case_ref": case_ref,
                    "video_slug": video_slug,
                    "title": str(item.get("title", "")).strip() or str((row or {}).get("title", "")).strip() or None,
                    "checkpoint": checkpoint,
                    "offset_seconds": offset,
                    "sample_timestamp_seconds": timestamp_seconds,
                    "video_path": video_path,
                    "frame_path": str(frame_path).replace("\\", "/"),
                    "audio_path": str(audio_path).replace("\\", "/"),
                    "source_screenshot_path": str((row or {}).get("screenshot_path", "")).strip() or None,
                    "source_audio_path": str((row or {}).get("audio_path", "")).strip() or None,
                    "weak_active_labels": list(item.get("weak_active_labels", [])),
                    "predicted_labels": list(item.get("predicted_labels", [])),
                    "top_predicted_labels": list(item.get("top_predicted_labels", [])),
                    "priority_score": int(item.get("priority_score", 0) or 0),
                    "prediction_status": str(item.get("prediction_status", "")).strip() or "unknown",
                    "clip_duration_seconds": clip_duration_seconds,
                }
            )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue_candidate_count": len(review_queue_items),
        "sampled_case_count": len(sampled_case_ids),
        "sample_count": len(samples),
        "skipped_missing_video_count": skipped_missing_video_count,
        "offsets_seconds": offsets,
    }
    return samples, report


def materialize_dense_review_samples(
    samples: list[dict[str, Any]],
    *,
    ffmpeg_bin: str,
) -> dict[str, int]:
    frame_extracted_count = 0
    frame_skipped_existing_count = 0
    audio_extracted_count = 0
    audio_skipped_existing_count = 0
    missing_video_count = 0

    for sample in samples:
        video_path_value = str(sample.get("video_path", "")).strip()
        if not video_path_value:
            missing_video_count += 1
            continue
        video_path = etvmd.resolve_repo_path(video_path_value)
        if not video_path.exists():
            missing_video_count += 1
            continue

        frame_path = etvmd.resolve_repo_path(str(sample.get("frame_path", "")).strip())
        if frame_path.exists():
            frame_skipped_existing_count += 1
        else:
            frame_status, _frame_error = btvw.extract_frame(
                video_path,
                timestamp_seconds=float(sample.get("sample_timestamp_seconds", 0.0) or 0.0),
                output_path=frame_path,
                ffmpeg_bin=ffmpeg_bin,
            )
            if frame_status == "extracted":
                frame_extracted_count += 1

        audio_path = etvmd.resolve_repo_path(str(sample.get("audio_path", "")).strip())
        if audio_path.exists():
            audio_skipped_existing_count += 1
        else:
            etvmd.extract_audio_clip(
                video_path=video_path,
                audio_path=audio_path,
                midpoint_seconds=float(sample.get("sample_timestamp_seconds", 0.0) or 0.0),
                clip_duration_seconds=float(
                    sample.get("clip_duration_seconds", DEFAULT_CLIP_DURATION_SECONDS)
                    or DEFAULT_CLIP_DURATION_SECONDS
                ),
                ffmpeg_bin=ffmpeg_bin,
            )
            audio_extracted_count += 1

    return {
        "frame_extracted_count": frame_extracted_count,
        "frame_skipped_existing_count": frame_skipped_existing_count,
        "audio_extracted_count": audio_extracted_count,
        "audio_skipped_existing_count": audio_skipped_existing_count,
        "missing_video_count": missing_video_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export dense review frame/audio samples around top TTFM disagreement checkpoints."
    )
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE_PATH)
    parser.add_argument("--multimodal-dataset", type=Path, default=DEFAULT_MULTIMODAL_DATASET_PATH)
    parser.add_argument("--frame-output-dir", type=Path, default=DEFAULT_FRAME_OUTPUT_DIR)
    parser.add_argument("--audio-output-dir", type=Path, default=DEFAULT_AUDIO_OUTPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--offset-seconds", type=float, nargs="+", default=list(DEFAULT_OFFSETS_SECONDS))
    parser.add_argument("--clip-duration-seconds", type=float, default=DEFAULT_CLIP_DURATION_SECONDS)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    args = parser.parse_args()

    review_queue = load_json(args.review_queue, {"items": []})
    rows = load_jsonl(args.multimodal_dataset)
    samples, report = build_dense_review_samples(
        review_queue_items=normalize_review_queue_items(review_queue),
        multimodal_rows=rows,
        offsets_seconds=args.offset_seconds,
        frame_output_dir=args.frame_output_dir,
        audio_output_dir=args.audio_output_dir,
        clip_duration_seconds=args.clip_duration_seconds,
        limit=args.limit,
    )
    report.update(materialize_dense_review_samples(samples, ffmpeg_bin=args.ffmpeg_bin))
    write_jsonl(args.output, samples)
    write_json(args.report_output, report)
    print(json.dumps({"output": str(args.output), "report_output": str(args.report_output), **report}, indent=2))


if __name__ == "__main__":
    main()
