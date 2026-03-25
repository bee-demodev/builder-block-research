from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
VIDEO_MANIFEST_PATH = CORPUS_DIR / "video_manifest.json"
DEFAULT_VIDEO_DIR = CORPUS_DIR / "videos"
DEFAULT_REPORT_OUTPUT = CORPUS_DIR / "video_download_report.json"
SUPPORTED_VIDEO_SUFFIXES = (".mp4", ".mkv", ".webm", ".mov")
DEFAULT_FORMAT_SELECTOR = (
    "best[acodec!=none][vcodec!=none][ext=mp4]/best[acodec!=none][vcodec!=none]/best"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def resolve_downloaded_video_path(video_dir: Path, slug: str) -> Path | None:
    for suffix in SUPPORTED_VIDEO_SUFFIXES:
        candidate = video_dir / f"{slug}{suffix}"
        if candidate.exists():
            return candidate
    matches = sorted(video_dir.glob(f"{slug}.*"))
    return matches[0] if matches else None


def resolve_repo_path(path_value: object) -> Path | None:
    cleaned = str(path_value or "").strip()
    if not cleaned:
        return None
    candidate = Path(cleaned)
    if candidate.is_absolute():
        return candidate
    return ROOT / candidate


def build_download_command(*, yt_dlp_bin: str, url: str, output_template: Path) -> list[str]:
    return [
        yt_dlp_bin,
        "--no-update",
        "--js-runtimes",
        "node",
        "--no-playlist",
        "--format",
        DEFAULT_FORMAT_SELECTOR,
        "--output",
        str(output_template),
        url,
    ]


def download_videos(
    video_manifest: dict,
    *,
    video_dir: Path,
    yt_dlp_bin: str,
    overwrite: bool,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict:
    video_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    for video in video_manifest.get("videos", []):
        slug = str(video.get("slug", "")).strip()
        url = str(video.get("url", "")).strip()
        if not slug:
            continue

        local_video_path = resolve_repo_path(video.get("local_video_path"))
        if local_video_path is not None:
            if local_video_path.exists():
                status_counts["linked_local_intake"] += 1
                rows.append(
                    {
                        "slug": slug,
                        "video_id": str(video.get("video_id", "")).strip(),
                        "status": "linked_local_intake",
                        "video_path": path_for_manifest(local_video_path),
                    }
                )
            else:
                status_counts["missing_local_intake"] += 1
                rows.append(
                    {
                        "slug": slug,
                        "video_id": str(video.get("video_id", "")).strip(),
                        "status": "missing_local_intake",
                        "video_path": path_for_manifest(local_video_path),
                        "error": "Local intake video path does not exist.",
                    }
                )
            continue

        if not url:
            status_counts["missing_url"] += 1
            rows.append(
                {
                    "slug": slug,
                    "video_id": str(video.get("video_id", "")).strip(),
                    "status": "missing_url",
                    "video_path": None,
                    "error": "No download URL was supplied for this manifest row.",
                }
            )
            continue

        existing_path = resolve_downloaded_video_path(video_dir, slug)
        if existing_path is not None and not overwrite:
            status_counts["skipped_exists"] += 1
            rows.append(
                {
                    "slug": slug,
                    "video_id": str(video.get("video_id", "")).strip(),
                    "status": "skipped_exists",
                    "video_path": path_for_manifest(existing_path),
                }
            )
            continue

        output_template = video_dir / f"{slug}.%(ext)s"
        command = build_download_command(
            yt_dlp_bin=yt_dlp_bin,
            url=url,
            output_template=output_template,
        )
        try:
            completed = runner(command, capture_output=True, text=True, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError(f"{yt_dlp_bin} was not found on PATH.") from exc

        downloaded_path = resolve_downloaded_video_path(video_dir, slug)
        if completed.returncode == 0 and downloaded_path is not None:
            status = "downloaded"
            error = None
        else:
            status = "download_failed"
            error = completed.stderr.strip() or completed.stdout.strip() or "yt-dlp download failed."
        status_counts[status] += 1
        rows.append(
            {
                "slug": slug,
                "video_id": str(video.get("video_id", "")).strip(),
                "status": status,
                "video_path": path_for_manifest(downloaded_path) if downloaded_path else None,
                "error": error,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "video_count": len(rows),
            "status_counts": dict(sorted(status_counts.items())),
            "video_dir": path_for_manifest(video_dir),
            "overwrite": overwrite,
        },
        "videos": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download missing TTFM YouTube source videos into the local corpus directory."
    )
    parser.add_argument("--video-manifest", type=Path, default=VIDEO_MANIFEST_PATH)
    parser.add_argument("--video-dir", type=Path, default=DEFAULT_VIDEO_DIR)
    parser.add_argument("--yt-dlp-bin", default="yt-dlp")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT)
    args = parser.parse_args()

    report = download_videos(
        load_json(args.video_manifest),
        video_dir=args.video_dir,
        yt_dlp_bin=args.yt_dlp_bin,
        overwrite=args.overwrite,
    )
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
