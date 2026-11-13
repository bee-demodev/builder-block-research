"""Ingest TTrades YouTube livestreams (New York Open Live Q&A etc.) into the TTFM video corpus.

YouTube blocks caption fetching from this machine (IpBlocked / HTTP 429), so this script
downloads each stream's audio with yt-dlp and transcribes it locally with faster-whisper.

Outputs, all under knowledge/ttfm_video_corpus/:
  transcripts/<slug>.json|.txt   same shape build_ttfm_video_corpus.py writes
  livestream_manifest.json       one row per stream, corpus_partition="livestream_qa"

Audio is cached outside the repo (--audio-dir) and is not needed once a transcript exists.
Re-running skips streams whose transcript JSON is already present, so new streams can be
picked up by running it again.

To (re)build livestream_chunks.jsonl and splice it into chunks.jsonl afterwards:
  python scripts/ingest_ttrades_livestreams.py --merge-only
Full pipeline: this script -> extract_livestream_keyframes.py -> Opus analysis per stream
(livestream_analysis/README.md) -> --merge-only.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
TRANSCRIPTS_DIR = CORPUS_DIR / "transcripts"
LIVESTREAM_MANIFEST = CORPUS_DIR / "livestream_manifest.json"
VIDEO_MANIFEST = CORPUS_DIR / "video_manifest.json"
STREAMS_URL = "https://www.youtube.com/@TTrades_edu/streams"
CHANNEL_URL = "https://www.youtube.com/@TTrades_edu"
PARTITION = "livestream_qa"
WHISPER_MODEL = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
WHISPER_PROMPT = (
    "TTrades New York Open live Q&A about futures and forex trading: NQ, ES, YM, MNQ, "
    "CISD, change in the state of delivery, FVG, fair value gap, IFVG, candle 2, candle 3, "
    "TTFM fractal model, daily bias, SMT divergence, PO3, power of three, protected swing, "
    "liquidity sweep, equilibrium, order block, breaker, daily profile, 4-hour, 1-hour, 15-minute."
)

# Counted on the transcript. A stream mentions most concepts once in passing, so a topic is
# only tagged when it comes up repeatedly (TOPIC_MIN_MENTIONS).
TOPIC_MARKERS: dict[str, tuple[str, ...]] = {
    "daily_bias": ("daily bias", "bias"),
    "fractal_model": ("fractal model", "ttfm", "fractal"),
    "candle_2": ("candle 2", "candle two"),
    "candle_3": ("candle 3", "candle three"),
    "candle_4": ("candle 4", "candle four"),
    "cisd": ("cisd", "change in the state of delivery", "change in state of delivery"),
    "equilibrium": ("equilibrium", "discount", "premium"),
    "continuation": ("continuation",),
    "reversal": ("reversal",),
    "expansion": ("expansion",),
    "consolidation": ("consolidation", "consolidating"),
    "order_block": ("order block",),
    "breaker": ("breaker",),
    "fair_value_gap": ("fair value gap", "fvg"),
    "protected_swing": ("protected swing", "protected high", "protected low"),
    "liquidity_sweep": ("sweep", "swept", "take out", "took out", "run the high", "run the low"),
    "point_of_interest": ("point of interest", "poi"),
    "wick_logic": ("wick",),
    "relative_strength": ("smt", "relative strength", "divergence"),
    "top_down_alignment": ("higher timeframe", "lower timeframe", "top down", "top-down"),
    "power_of_three": ("power of three", "po3"),
    "daily_profiles": ("daily profile", "profile"),
    "session_profile": ("london", "asia", "new york open", "silver bullet", "macro"),
    "news_events": ("cpi", "fomc", "nfp", "news", "ppi"),
    "risk_management": ("risk", "stop loss", "position size", "drawdown", "prop firm", "funded"),
    "psychology": ("discipline", "patience", "emotion", "psychology", "overtrad", "revenge"),
}
TOPIC_MIN_MENTIONS = 4


def log(message: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}", flush=True)


def run_yt_dlp(args: list[str], timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["yt-dlp", "--no-update", "--js-runtimes", "node", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def list_streams() -> list[dict[str, Any]]:
    completed = run_yt_dlp(["--flat-playlist", "--print", "%(id)s\t%(title)s\t%(duration)s", STREAMS_URL], 300)
    rows = []
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not re.fullmatch(r"[\w-]{11}", parts[0]):
            continue
        try:
            duration = float(parts[2])
        except ValueError:
            duration = None  # still live or upcoming: skip, it has no finished recording yet
        if duration:
            rows.append({"video_id": parts[0], "title": parts[1], "duration_seconds": duration})
    if not rows:
        raise RuntimeError(f"No streams listed from {STREAMS_URL}:\n{completed.stderr[-2000:]}")
    return rows


def fetch_metadata(video_id: str) -> dict[str, Any]:
    completed = run_yt_dlp(["--dump-single-json", "--skip-download", f"https://youtu.be/{video_id}"])
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-1000:])
    payload = json.loads(completed.stdout)
    upload = payload.get("release_date") or payload.get("upload_date") or ""
    return {
        "upload_date": f"{upload[:4]}-{upload[4:6]}-{upload[6:8]}" if len(upload) == 8 else None,
        "description": (payload.get("description") or "")[:4000],
        "chapters": [
            {"title": c.get("title"), "start": c.get("start_time"), "end": c.get("end_time")}
            for c in payload.get("chapters") or []
        ],
        "view_count": payload.get("view_count"),
    }


def download_audio(video_id: str, audio_dir: Path) -> Path:
    audio_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(audio_dir.glob(f"{video_id}.*"))
    existing = [p for p in existing if p.suffix in {".m4a", ".webm", ".opus", ".mp3"}]
    if existing:
        return existing[0]
    completed = run_yt_dlp(
        ["-f", "bestaudio[ext=m4a]/bestaudio", "-o", str(audio_dir / "%(id)s.%(ext)s"), f"https://youtu.be/{video_id}"],
        timeout=1800,
    )
    found = [p for p in audio_dir.glob(f"{video_id}.*") if p.suffix in {".m4a", ".webm", ".opus", ".mp3"}]
    if completed.returncode != 0 or not found:
        raise RuntimeError(completed.stderr[-1000:])
    return found[0]


def make_slug(row: dict[str, Any]) -> str:
    date = (row.get("upload_date") or "undated").replace("-", "")
    title = re.sub(r"[^a-z0-9]+", "_", row["title"].lower()).strip("_")[:60]
    return f"livestream_{date}_{title}_{row['video_id'].lower().replace('-', '_')}"


def tag_topics(text: str) -> tuple[list[str], dict[str, int]]:
    lowered = text.lower()
    counts = {}
    for topic, markers in TOPIC_MARKERS.items():
        n = sum(len(re.findall(r"\b" + re.escape(m), lowered)) for m in markers)
        if n:
            counts[topic] = n
    topics = sorted(t for t, n in counts.items() if n >= TOPIC_MIN_MENTIONS)
    return topics, dict(sorted(counts.items(), key=lambda kv: -kv[1]))


class Transcriber:
    def __init__(self, batch_size: int) -> None:
        from faster_whisper import BatchedInferencePipeline, WhisperModel

        self.model = WhisperModel(WHISPER_MODEL, device="cuda", compute_type="float16")
        self.pipeline = BatchedInferencePipeline(model=self.model)
        self.batch_size = batch_size

    def __call__(self, audio_path: Path) -> list[dict[str, Any]]:
        segments, _ = self.pipeline.transcribe(
            str(audio_path),
            language="en",
            batch_size=self.batch_size,
            vad_filter=True,
            initial_prompt=WHISPER_PROMPT,
        )
        out = []
        for seg in segments:
            text = " ".join(seg.text.split())
            if text:
                out.append({"text": text, "start": round(seg.start, 2), "duration": round(seg.end - seg.start, 2)})
        return out


def write_transcript(slug: str, transcript: list[dict[str, Any]]) -> None:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    (TRANSCRIPTS_DIR / f"{slug}.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    (TRANSCRIPTS_DIR / f"{slug}.txt").write_text(
        "\n".join(f"[{s['start']:.2f}] {s['text']}" for s in transcript) + "\n", encoding="utf-8"
    )


def load_livestream_manifest() -> dict[str, dict[str, Any]]:
    if not LIVESTREAM_MANIFEST.exists():
        return {}
    payload = json.loads(LIVESTREAM_MANIFEST.read_text(encoding="utf-8"))
    return {row["video_id"]: row for row in payload.get("videos", [])}


def save_livestream_manifest(rows: dict[str, dict[str, Any]]) -> None:
    videos = sorted(rows.values(), key=lambda r: r.get("upload_date") or "", reverse=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_source": "ttrades_youtube_streams_tab",
        "source_channel_url": STREAMS_URL,
        "transcription": {"engine": "faster-whisper", "model": WHISPER_MODEL, "reason": "YouTube caption fetch is IP-blocked"},
        "video_count": len(videos),
        "total_hours": round(sum(v.get("duration_seconds") or 0 for v in videos) / 3600, 1),
        "videos": videos,
    }
    LIVESTREAM_MANIFEST.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def ingest(audio_dir: Path, limit: int | None, batch_size: int) -> None:
    rows = load_livestream_manifest()
    listed = list_streams()
    log(f"{len(listed)} finished streams listed, {len(rows)} already in livestream_manifest.json")
    todo = [s for s in listed if not (s["video_id"] in rows and (TRANSCRIPTS_DIR / f"{rows[s['video_id']]['slug']}.json").exists())]
    if limit:
        todo = todo[:limit]
    log(f"{len(todo)} streams to ingest")
    transcriber: Transcriber | None = None
    for index, stream in enumerate(todo, 1):
        vid = stream["video_id"]
        try:
            row = {**stream, **fetch_metadata(vid)}
            row["slug"] = make_slug(row)
            audio = download_audio(vid, audio_dir)
            if transcriber is None:
                transcriber = Transcriber(batch_size)
            started = time.time()
            transcript = transcriber(audio)
            write_transcript(row["slug"], transcript)
            topics, mentions = tag_topics(" ".join(s["text"] for s in transcript))
            rows[vid] = {
                "slug": row["slug"],
                "title": row["title"],
                "video_id": vid,
                "url": f"https://youtu.be/{vid}",
                "source_page": None,
                "topics": topics,
                "topic_mentions": mentions,
                "corpus_partition": PARTITION,
                "review_categories": [],
                "educational_categories": [],
                "discovery_source": "youtube_streams_tab",
                "channel": "TTrades",
                "channel_url": CHANNEL_URL,
                "upload_date": row.get("upload_date"),
                "duration_seconds": row["duration_seconds"],
                "description": row.get("description"),
                "chapters": row.get("chapters"),
                "transcript_source": "local_whisper_large_v3_turbo",
            }
            save_livestream_manifest(rows)
            log(f"[{index}/{len(todo)}] {row['upload_date']} {vid} {len(transcript)} segs in {time.time() - started:.0f}s")
        except Exception as exc:  # keep going; a re-run picks up whatever failed
            log(f"[{index}/{len(todo)}] FAILED {vid}: {str(exc)[:300]}")
        time.sleep(2)


def merge_into_corpus() -> None:
    """Write livestream_chunks.jsonl and splice it into chunks.jsonl.

    The streams are deliberately NOT added to video_manifest.json: the uploads pipeline
    (data_loader.expand_ttrades_youtube_corpus) downloads every video in that manifest.
    """
    from build_livestream_corpus_chunks import build

    log(f"livestream chunks: {build()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audio-dir", type=Path, required=False, help="Where downloaded audio is cached (keep outside the repo).")
    parser.add_argument("--limit", type=int, default=None, help="Only ingest this many new streams.")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--merge-only", action="store_true", help="Skip ingest; only merge streams into chunks.jsonl.")
    parser.add_argument("--no-merge", action="store_true", help="Ingest only; do not rebuild chunks.jsonl.")
    args = parser.parse_args()
    if not args.merge_only:
        if args.audio_dir is None:
            parser.error("--audio-dir is required unless --merge-only")
        ingest(args.audio_dir, args.limit, args.batch_size)
    if not args.no_merge:
        merge_into_corpus()


if __name__ == "__main__":
    main()
