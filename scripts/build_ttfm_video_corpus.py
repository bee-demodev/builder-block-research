from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from youtube_transcript_api import YouTubeTranscriptApi


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
DEFAULT_YT_DLP_BIN = "yt-dlp"
DEFAULT_YT_DLP_TIMEOUT_SECONDS = 15

VIDEO_MANIFEST = [
    {
        "slug": "fractal_model_fundamentals",
        "title": "TTrades Playbook | Fractal Model Fundamentals (TTFM)",
        "video_id": "TNybDCtwBnc",
        "url": "https://youtu.be/TNybDCtwBnc",
        "source_page": "https://ttrades.com/fractal-model-playbook-aligning-daily-hourly-and-5-minute-charts/",
        "topics": ["fractal_model", "candle_2", "candle_3", "cisd", "daily_bias", "poi"],
    },
    {
        "slug": "equilibrium_for_expansions",
        "title": "You Are Using Discount and Premium Wrong! - EQ For Expansions",
        "video_id": "IPZjNI1B5a0",
        "url": "https://youtu.be/IPZjNI1B5a0",
        "source_page": "https://ttrades.com/using-equilibrium-in-continuations/",
        "topics": ["equilibrium", "continuation", "expansion", "range_half", "cisd"],
    },
    {
        "slug": "easy_daily_bias_mechanical_framework",
        "title": "Easy Daily Bias - Mechanical Framework",
        "video_id": "-KKuZb5Z5aU",
        "url": "https://youtu.be/-KKuZb5Z5aU",
        "source_page": "https://ttrades.com/easy-daily-bias-a-mechanical-trading-framework/",
        "topics": ["daily_bias", "continuation", "reversal", "equilibrium", "wick_logic"],
    },
    {
        "slug": "candle_2_closure_foundation",
        "title": "Candle 2 Closure: The Foundation of TTrades Fractal Model",
        "video_id": "tyoxl1l-6iI",
        "url": "https://youtu.be/tyoxl1l-6iI",
        "source_page": "https://ttrades.com/understanding-candle-2-closures-within-the-fractal-model/",
        "topics": ["candle_2", "reversal_closure", "candle_3", "poi", "equilibrium"],
    },
    {
        "slug": "trading_candle_3",
        "title": "TTrades Fractal Model - Trading Candle 3",
        "video_id": "qdQYhePcvGE",
        "url": "https://youtu.be/qdQYhePcvGE",
        "source_page": "https://ttrades.com/how-to-trade-candle-3-in-the-fractal-model/",
        "topics": ["candle_3", "candle_4", "wick_logic", "continuation", "cisd", "protected_swing"],
    },
    {
        "slug": "cisd_validates_swing_points",
        "title": "Validating Swing Points Using Lower Timeframe Confirmation (CISD)",
        "video_id": "vn1RYjhJUnQ",
        "url": "https://youtu.be/vn1RYjhJUnQ",
        "source_page": "https://ttrades.com/how-change-in-the-state-of-delivery-confirms-swing-points/",
        "topics": ["cisd", "candle_2", "candle_3", "swing_validation", "continuation"],
    },
]

FALLBACK_TRANSCRIPT_SEGMENTS = (
    ("context", 0.10, "Higher timeframe context daily bias equilibrium point of interest."),
    ("sweep", 0.30, "Liquidity sweep or run on the highs and lows."),
    ("closure", 0.50, "Candle 2 or Candle 3 closure with CISD through the level."),
    ("confirmation", 0.70, "Entry confirmation around order block, breaker, fair value gap, or protected swing."),
    ("outcome", 0.90, "Trade outcome, expansion, target delivery, or invalidation."),
)


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def default_video_manifest() -> dict[str, Any]:
    videos: list[dict[str, Any]] = []
    for video in VIDEO_MANIFEST:
        row = dict(video)
        row.setdefault("corpus_partition", "seed_curriculum")
        row.setdefault("discovery_source", "seed_curriculum")
        row.setdefault("review_categories", [])
        row.setdefault("educational_categories", [])
        videos.append(row)
    return {
        "manifest_source": "seed_curriculum",
        "video_count": len(videos),
        "videos": videos,
    }


def load_video_manifest(path: Path | None = None) -> dict[str, Any]:
    if path is not None and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default_video_manifest()


def build_chunk_records(
    video: dict,
    transcript: list[dict],
    *,
    max_chars: int = 1200,
    force_individual_snippets: bool = False,
) -> list[dict]:
    records: list[dict] = []
    current_text: list[str] = []
    chunk_start = 0.0
    chunk_end = 0.0
    shared_metadata = {
        "source_page": video.get("source_page"),
        "topics": video.get("topics", []),
        "corpus_partition": video.get("corpus_partition", "seed_curriculum"),
        "review_categories": video.get("review_categories", []),
        "discovery_source": video.get("discovery_source", "seed_curriculum"),
        "channel_url": video.get("channel_url"),
        "transcript_source": video.get("transcript_source"),
    }

    if force_individual_snippets:
        for snippet in transcript:
            text = normalize_text(str(snippet["text"]))
            if not text:
                continue
            start = float(snippet["start"])
            duration = float(snippet["duration"])
            records.append(
                {
                    "video_slug": video["slug"],
                    "video_id": video["video_id"],
                    "title": video["title"],
                    **shared_metadata,
                    "start": start,
                    "end": start + duration,
                    "text": text,
                }
            )
        return records

    for snippet in transcript:
        text = normalize_text(str(snippet["text"]))
        if not text:
            continue

        candidate = " ".join(current_text + [text]).strip()
        if current_text and len(candidate) > max_chars:
            records.append(
                {
                    "video_slug": video["slug"],
                    "video_id": video["video_id"],
                    "title": video["title"],
                    **shared_metadata,
                    "start": chunk_start,
                    "end": chunk_end,
                    "text": " ".join(current_text).strip(),
                }
            )
            current_text = [text]
            chunk_start = float(snippet["start"])
            chunk_end = float(snippet["start"]) + float(snippet["duration"])
        else:
            if not current_text:
                chunk_start = float(snippet["start"])
            current_text.append(text)
            chunk_end = float(snippet["start"]) + float(snippet["duration"])

    if current_text:
        records.append(
            {
                "video_slug": video["slug"],
                "video_id": video["video_id"],
                "title": video["title"],
                **shared_metadata,
                "start": chunk_start,
                "end": chunk_end,
                "text": " ".join(current_text).strip(),
            }
        )

    return records


def serialize_transcript(transcript: list[dict]) -> list[dict]:
    return [
        {
            "text": normalize_text(str(snippet["text"])),
            "start": float(snippet["start"]),
            "duration": float(snippet["duration"]),
        }
        for snippet in transcript
        if normalize_text(str(snippet["text"]))
    ]


def load_existing_transcript(json_path: Path) -> list[dict] | None:
    if not json_path.exists():
        return None
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return None
    return serialize_transcript(payload)


def load_manifest_supplied_transcript(video: dict[str, Any]) -> tuple[list[dict] | None, str | None]:
    transcript_segments = video.get("transcript_segments")
    if isinstance(transcript_segments, list) and transcript_segments:
        return serialize_transcript(transcript_segments), "manifest_transcript_segments"

    transcript_text = str(video.get("transcript_text", "")).strip()
    if transcript_text:
        return (
            [
                {
                    "text": transcript_text,
                    "start": 0.0,
                    "duration": max(float(video.get("manifest_clip_duration_seconds", 60.0) or 60.0), 8.0),
                }
            ],
            "manifest_transcript_text",
        )

    return None, None


def fetch_video_duration_seconds(
    video: dict[str, Any],
    *,
    yt_dlp_bin: str = DEFAULT_YT_DLP_BIN,
    timeout_seconds: int = DEFAULT_YT_DLP_TIMEOUT_SECONDS,
) -> float:
    manifest_duration = video.get("duration_seconds", video.get("manifest_clip_duration_seconds"))
    try:
        if manifest_duration is not None:
            return max(float(manifest_duration), 60.0)
    except (TypeError, ValueError):
        pass

    allow_remote_probe = bool(video.get("allow_remote_duration_probe", False))
    if not allow_remote_probe:
        return 300.0

    url = str(video.get("url", "")).strip()
    if not url:
        return 300.0
    try:
        completed = subprocess.run(
            [
                yt_dlp_bin,
                "--no-update",
                "--dump-single-json",
                "--skip-download",
                url,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return 300.0
    if completed.returncode != 0:
        return 300.0
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return 300.0
    return float(payload.get("duration") or 300.0)


def build_synthetic_transcript(video: dict[str, Any], *, duration_seconds: float) -> list[dict[str, float | str]]:
    duration_seconds = max(float(duration_seconds or 0.0), 60.0)
    snippet_duration = max(duration_seconds * 0.06, 8.0)
    title = str(video.get("title", "")).strip()
    topics = ", ".join(str(topic).strip() for topic in video.get("topics", []) if str(topic).strip())
    transcript: list[dict[str, float | str]] = []
    for _, position, base_text in FALLBACK_TRANSCRIPT_SEGMENTS:
        midpoint = duration_seconds * position
        start = max(0.0, midpoint - (snippet_duration / 2.0))
        transcript.append(
            {
                "text": normalize_text(f"{title}. {topics}. {base_text}"),
                "start": float(start),
                "duration": float(snippet_duration),
            }
        )
    return transcript


def is_synthetic_transcript(transcript: list[dict[str, Any]]) -> bool:
    if len(transcript) != len(FALLBACK_TRANSCRIPT_SEGMENTS):
        return False
    normalized_fallback_markers = [normalize_text(text) for _, _, text in FALLBACK_TRANSCRIPT_SEGMENTS]
    snippet_texts = [normalize_text(str(snippet.get("text", ""))) for snippet in transcript]
    return all(marker in snippet_text for marker, snippet_text in zip(normalized_fallback_markers, snippet_texts))


def build_corpus(
    output_dir: Path,
    *,
    video_manifest: dict[str, Any] | None = None,
    overwrite: bool = False,
    youtube_api_factory: Callable[[], Any] = YouTubeTranscriptApi,
    yt_dlp_bin: str = DEFAULT_YT_DLP_BIN,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir = output_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    existing_manifest_path = output_dir / "video_manifest.json"
    existing_manifest_lookup: dict[str, dict[str, Any]] = {}
    if existing_manifest_path.exists():
        try:
            existing_manifest = json.loads(existing_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing_manifest = {}
        existing_manifest_lookup = {
            str(row.get("slug", "")).strip(): row
            for row in existing_manifest.get("videos", [])
            if str(row.get("slug", "")).strip()
        }

    api = youtube_api_factory()
    active_manifest = video_manifest or default_video_manifest()
    manifest_rows: list[dict] = []
    chunk_rows: list[dict] = []
    fetched_count = 0
    reused_count = 0
    synthetic_count = 0

    for video in active_manifest.get("videos", []):
        video_row = dict(video)
        text_path = transcripts_dir / f"{video['slug']}.txt"
        json_path = transcripts_dir / f"{video['slug']}.json"
        transcript = None if overwrite else load_existing_transcript(json_path)
        transcript_source = "cached_json"
        transcript_error = None
        if transcript is None:
            manifest_transcript, manifest_transcript_source = load_manifest_supplied_transcript(video_row)
            if manifest_transcript is not None:
                transcript = manifest_transcript
                transcript_source = manifest_transcript_source or "manifest_transcript_text"
            else:
                video_id = str(video.get("video_id", "")).strip()
                url = str(video.get("url", "")).strip()
                if video_id and url:
                    try:
                        fetched = api.fetch(video["video_id"], languages=["en"])
                        transcript = serialize_transcript(fetched.to_raw_data())
                        transcript_source = "youtube_caption_api"
                        fetched_count += 1
                    except Exception as exc:
                        transcript = build_synthetic_transcript(
                            video_row,
                            duration_seconds=fetch_video_duration_seconds(video_row, yt_dlp_bin=yt_dlp_bin),
                        )
                        transcript_source = "synthetic_from_video_metadata"
                        transcript_error = str(exc)
                        synthetic_count += 1
                else:
                    transcript = build_synthetic_transcript(
                        video_row,
                        duration_seconds=fetch_video_duration_seconds(video_row, yt_dlp_bin=yt_dlp_bin),
                    )
                    transcript_source = "synthetic_from_video_metadata"
                    transcript_error = "No YouTube video_id/url was supplied for this manifest row."
                    synthetic_count += 1
        else:
            reused_count += 1
            previous_row = existing_manifest_lookup.get(str(video_row.get("slug", "")).strip(), {})
            transcript_source = str(
                previous_row.get("transcript_source", video_row.get("transcript_source", transcript_source))
            )
            transcript_error = previous_row.get("transcript_error")
            if transcript_source == "cached_json" and is_synthetic_transcript(transcript):
                transcript_source = "synthetic_from_video_metadata"
            if transcript_source == "synthetic_from_video_metadata":
                synthetic_count += 1

        video_row["transcript_source"] = transcript_source

        text_path.write_text(
            "\n".join(
                f"[{snippet['start']:.2f}] {snippet['text']}"
                for snippet in transcript
            )
            + "\n",
            encoding="utf-8",
        )
        json_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")

        chunks = build_chunk_records(
            video_row,
            transcript,
            force_individual_snippets=transcript_source == "synthetic_from_video_metadata",
        )
        chunk_rows.extend(chunks)
        manifest_rows.append(
            {
                **video_row,
                "transcript_path": str(text_path.relative_to(ROOT)),
                "transcript_json_path": str(json_path.relative_to(ROOT)),
                "chunk_count": len(chunks),
                "snippet_count": len(transcript),
                "transcript_error": transcript_error,
            }
        )

    manifest = {
        "generated_at": active_manifest.get("generated_at"),
        "manifest_source": active_manifest.get("manifest_source", "seed_curriculum"),
        "source_channel_url": active_manifest.get("source_channel_url"),
        "output_dir": str(output_dir.relative_to(ROOT)),
        "video_count": len(manifest_rows),
        "transcript_fetch_count": fetched_count,
        "transcript_reuse_count": reused_count,
        "synthetic_transcript_count": synthetic_count,
        "videos": manifest_rows,
    }
    (output_dir / "video_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (output_dir / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for row in chunk_rows:
            handle.write(json.dumps(row) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a transcript corpus for key TTFM/TTrades videos.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory where transcripts and chunk records should be written.",
    )
    parser.add_argument(
        "--video-manifest",
        type=Path,
        default=None,
        help="Optional manifest to use instead of the built-in TTFM seed video list.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Refetch transcripts even when cached transcript JSON artifacts already exist.",
    )
    parser.add_argument(
        "--yt-dlp-bin",
        default=DEFAULT_YT_DLP_BIN,
        help="yt-dlp executable used to fetch video metadata when transcript captions are unavailable.",
    )
    args = parser.parse_args()
    manifest = build_corpus(
        args.output_dir,
        video_manifest=load_video_manifest(args.video_manifest),
        overwrite=args.overwrite,
        yt_dlp_bin=args.yt_dlp_bin,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
