from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import build_ttfm_video_corpus as btvc
import build_ttfm_video_visual_windows as btvw
import discover_ttfm_trade_review_videos as dtrv
import download_ttfm_youtube_videos as dtyv
import export_ttfm_video_weak_visual_dataset as etvwvd
import validate_ttfm_video_corpus as vtvc


ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
DEFAULT_CHANNEL_INVENTORY_PATH = CORPUS_DIR / "channel_inventory.json"
DEFAULT_TRADE_REVIEW_MANIFEST_PATH = CORPUS_DIR / "trade_review_video_manifest.json"
DEFAULT_EDUCATIONAL_MANIFEST_PATH = CORPUS_DIR / "educational_video_manifest.json"
DEFAULT_ACTIVE_MANIFEST_PATH = CORPUS_DIR / "video_manifest.json"
DEFAULT_WINDOWS_OUTPUT = CORPUS_DIR / "visual_windows.jsonl"
DEFAULT_WINDOWS_REPORT_OUTPUT = CORPUS_DIR / "visual_windows_report.json"
DEFAULT_VIDEO_DOWNLOAD_REPORT_OUTPUT = CORPUS_DIR / "video_download_report.json"
DEFAULT_REPORT_OUTPUT = CORPUS_DIR / "corpus_refresh_report.json"
DEFAULT_WEAK_DATASET_OUTPUT = ROOT / "results" / "ttfm_video_weak_visual_dataset.jsonl"
DEFAULT_WEAK_DATASET_REPORT_OUTPUT = ROOT / "results" / "ttfm_video_weak_visual_dataset_report.json"


def path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def manifest_identity(video: dict[str, Any]) -> str:
    video_id = str(video.get("video_id", "")).strip()
    if video_id:
        return f"youtube::{video_id}"

    local_video_path = str(video.get("local_video_path", "")).strip()
    if local_video_path:
        return f"local::{local_video_path.lower()}"

    slug = str(video.get("slug", "")).strip()
    if slug:
        return f"slug::{slug}"
    return json.dumps(video, sort_keys=True)


def merge_video_manifests(*manifests: dict[str, Any]) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    seen_identities: set[str] = set()
    for manifest in manifests:
        for video in manifest.get("videos", []):
            identity = manifest_identity(video)
            if identity in seen_identities:
                continue
            seen_identities.add(identity)
            merged.append(dict(video))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_source": "seed_plus_educational_channel",
        "video_count": len(merged),
        "videos": merged,
    }


def summarize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    partition_counts: dict[str, int] = {}
    discovery_source_counts: dict[str, int] = {}
    for video in manifest.get("videos", []):
        partition = str(video.get("corpus_partition", "seed_curriculum")).strip() or "seed_curriculum"
        discovery_source = str(video.get("discovery_source", "seed_curriculum")).strip() or "seed_curriculum"
        partition_counts[partition] = partition_counts.get(partition, 0) + 1
        discovery_source_counts[discovery_source] = discovery_source_counts.get(discovery_source, 0) + 1
    return {
        "video_count": len(manifest.get("videos", [])),
        "partition_counts": dict(sorted(partition_counts.items())),
        "discovery_source_counts": dict(sorted(discovery_source_counts.items())),
    }


def load_optional_manifest(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"video_count": 0, "videos": []}
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_corpus(
    *,
    channel_url: str,
    yt_dlp_bin: str,
    include_review_categories: set[str] | None,
    include_educational_categories: set[str] | None,
    output_dir: Path,
    inventory_output: Path,
    trade_review_manifest_output: Path,
    educational_manifest_output: Path,
    active_manifest_output: Path,
    intake_video_manifest_path: Path | None,
    video_dir: Path,
    video_download_report_output: Path,
    windows_output: Path,
    windows_report_output: Path,
    weak_dataset_output: Path,
    weak_dataset_report_output: Path,
    report_output: Path,
    ffmpeg_bin: str,
    extract_frames: bool,
    overwrite_transcripts: bool,
    overwrite_videos: bool,
) -> dict[str, Any]:
    channel_payload = dtrv.fetch_channel_inventory(channel_url=channel_url, yt_dlp_bin=yt_dlp_bin)
    inventory, educational_manifest, trade_review_manifest = dtrv.build_channel_corpus_manifests(
        channel_payload,
        channel_url=channel_url,
        include_review_categories=include_review_categories,
        include_educational_categories=include_educational_categories,
    )
    intake_video_manifest = load_optional_manifest(intake_video_manifest_path)

    write_json(inventory_output, inventory)
    write_json(trade_review_manifest_output, trade_review_manifest)
    write_json(educational_manifest_output, educational_manifest)

    active_manifest = merge_video_manifests(
        btvc.default_video_manifest(),
        educational_manifest,
        intake_video_manifest,
    )
    write_json(active_manifest_output, active_manifest)

    corpus_manifest = btvc.build_corpus(
        output_dir,
        video_manifest=active_manifest,
        overwrite=overwrite_transcripts,
    )
    download_report = dtyv.download_videos(
        active_manifest,
        video_dir=video_dir,
        yt_dlp_bin=yt_dlp_bin,
        overwrite=overwrite_videos,
    )
    write_json(video_download_report_output, download_report)

    chunk_rows = btvw.load_jsonl(output_dir / "chunks.jsonl")
    taxonomy = btvw.load_component_taxonomy()
    window_rows, window_report = btvw.build_visual_windows_dataset(
        corpus_manifest,
        chunk_rows,
        taxonomy=taxonomy,
        video_dir=video_dir,
        frame_dir=btvw.DEFAULT_FRAME_DIR,
        extract_frames=extract_frames,
        ffmpeg_bin=ffmpeg_bin,
    )
    write_jsonl(windows_output, window_rows)
    write_json(windows_report_output, window_report)

    weak_rows, weak_report = etvwvd.build_video_weak_visual_dataset_report(window_rows)
    write_jsonl(weak_dataset_output, weak_rows)
    write_json(weak_dataset_report_output, weak_report)

    validation_report = vtvc.validate_corpus(
        manifest_path=output_dir / "video_manifest.json",
        chunks_path=output_dir / "chunks.jsonl",
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel_inventory": {
            "inventory_output": path_for_manifest(inventory_output),
            "entry_count": inventory["entry_count"],
            "educational_candidate_count": inventory.get("educational_candidate_count", 0),
            "trade_review_candidate_count": inventory["trade_review_candidate_count"],
            "category_counts": inventory["category_counts"],
            "educational_category_counts": inventory.get("educational_category_counts", {}),
            "selected_partition_counts": inventory.get("selected_partition_counts", {}),
        },
        "educational_manifest": {
            "manifest_output": path_for_manifest(educational_manifest_output),
            **summarize_manifest(educational_manifest),
        },
        "trade_review_manifest": {
            "manifest_output": path_for_manifest(trade_review_manifest_output),
            **summarize_manifest(trade_review_manifest),
        },
        "daily_intake_video_manifest": {
            "manifest_output": path_for_manifest(intake_video_manifest_path)
            if intake_video_manifest_path
            else None,
            **summarize_manifest(intake_video_manifest),
        },
        "active_manifest": {
            "manifest_output": path_for_manifest(active_manifest_output),
            **summarize_manifest(active_manifest),
        },
        "corpus_manifest": {
            "manifest_output": path_for_manifest(output_dir / "video_manifest.json"),
            "chunk_output": path_for_manifest(output_dir / "chunks.jsonl"),
            "video_count": corpus_manifest["video_count"],
            "transcript_fetch_count": corpus_manifest["transcript_fetch_count"],
            "transcript_reuse_count": corpus_manifest["transcript_reuse_count"],
            "synthetic_transcript_count": corpus_manifest.get("synthetic_transcript_count", 0),
        },
        "video_downloads": download_report["summary"],
        "visual_windows": {
            "windows_output": path_for_manifest(windows_output),
            "report_output": path_for_manifest(windows_report_output),
            **window_report["summary"],
        },
        "weak_visual_dataset": {
            "dataset_output": path_for_manifest(weak_dataset_output),
            "report_output": path_for_manifest(weak_dataset_report_output),
            **weak_report["summary"],
        },
        "validation": validation_report,
    }
    write_json(report_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the TTFM YouTube corpus by merging the seed curriculum with the broader "
            "educational TTrades channel inventory and optional local intake videos."
        )
    )
    parser.add_argument("--channel-url", default=dtrv.DEFAULT_CHANNEL_URL)
    parser.add_argument("--yt-dlp-bin", default="yt-dlp")
    parser.add_argument(
        "--include-category",
        action="append",
        choices=sorted(dtrv.REVIEW_CATEGORY_PATTERNS),
        dest="include_review_categories",
    )
    parser.add_argument(
        "--include-educational-category",
        action="append",
        choices=sorted(dtrv.EDUCATIONAL_CATEGORY_PATTERNS),
        dest="include_educational_categories",
    )
    parser.add_argument("--output-dir", type=Path, default=CORPUS_DIR)
    parser.add_argument("--inventory-output", type=Path, default=DEFAULT_CHANNEL_INVENTORY_PATH)
    parser.add_argument(
        "--trade-review-manifest-output",
        type=Path,
        default=DEFAULT_TRADE_REVIEW_MANIFEST_PATH,
    )
    parser.add_argument(
        "--educational-manifest-output",
        type=Path,
        default=DEFAULT_EDUCATIONAL_MANIFEST_PATH,
    )
    parser.add_argument("--active-manifest-output", type=Path, default=DEFAULT_ACTIVE_MANIFEST_PATH)
    parser.add_argument(
        "--intake-video-manifest",
        type=Path,
        default=None,
        help="Optional local intake video manifest to merge into the active corpus.",
    )
    parser.add_argument("--video-dir", type=Path, default=dtyv.DEFAULT_VIDEO_DIR)
    parser.add_argument(
        "--video-download-report-output",
        type=Path,
        default=DEFAULT_VIDEO_DOWNLOAD_REPORT_OUTPUT,
    )
    parser.add_argument("--windows-output", type=Path, default=DEFAULT_WINDOWS_OUTPUT)
    parser.add_argument("--windows-report-output", type=Path, default=DEFAULT_WINDOWS_REPORT_OUTPUT)
    parser.add_argument("--weak-dataset-output", type=Path, default=DEFAULT_WEAK_DATASET_OUTPUT)
    parser.add_argument(
        "--weak-dataset-report-output",
        type=Path,
        default=DEFAULT_WEAK_DATASET_REPORT_OUTPUT,
    )
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument(
        "--skip-frame-extraction",
        action="store_true",
        help="Build the visual windows dataset without extracting fresh screenshots from local videos.",
    )
    parser.add_argument(
        "--overwrite-transcripts",
        action="store_true",
        help="Refetch transcripts instead of reusing cached transcript JSON artifacts.",
    )
    parser.add_argument(
        "--overwrite-videos",
        action="store_true",
        help="Redownload videos even when a local file already exists.",
    )
    args = parser.parse_args()

    report = refresh_corpus(
        channel_url=args.channel_url,
        yt_dlp_bin=args.yt_dlp_bin,
        include_review_categories=set(args.include_review_categories or dtrv.REVIEW_CATEGORY_PATTERNS),
        include_educational_categories=set(
            args.include_educational_categories or dtrv.EDUCATIONAL_CATEGORY_PATTERNS
        ),
        output_dir=args.output_dir,
        inventory_output=args.inventory_output,
        trade_review_manifest_output=args.trade_review_manifest_output,
        educational_manifest_output=args.educational_manifest_output,
        active_manifest_output=args.active_manifest_output,
        intake_video_manifest_path=args.intake_video_manifest,
        video_dir=args.video_dir,
        video_download_report_output=args.video_download_report_output,
        windows_output=args.windows_output,
        windows_report_output=args.windows_report_output,
        weak_dataset_output=args.weak_dataset_output,
        weak_dataset_report_output=args.weak_dataset_report_output,
        report_output=args.report_output,
        ffmpeg_bin=args.ffmpeg_bin,
        extract_frames=not args.skip_frame_extraction,
        overwrite_transcripts=args.overwrite_transcripts,
        overwrite_videos=args.overwrite_videos,
    )
    print(json.dumps({"report_output": path_for_manifest(args.report_output), **report["active_manifest"]}, indent=2))


if __name__ == "__main__":
    main()
