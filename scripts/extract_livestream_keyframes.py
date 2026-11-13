"""Pick chart keyframes from TTrades livestreams and pair each with the speech around it.

For each stream in knowledge/ttfm_video_corpus/livestream_manifest.json that already has a
transcript, this:
  1. downloads the 1080p video-only stream into --video-dir (outside the repo),
  2. samples a tiny grayscale frame every SAMPLE_SECONDS and finds view changes
     (symbol/timeframe switch, chart redraw), keeping the frame just BEFORE each change
     because that is the view with the most markup on it,
  3. fills gaps so no stretch longer than MAX_GAP_SECONDS has no frame, caps at --max-frames,
  4. writes 1280px JPEGs to livestream_frames/<slug>/ and a packet.md that lists each frame
     with the transcript spoken between the previous frame and this one.

packet.md is the input for the vision+transcript analysis pass (see
knowledge/ttfm_video_corpus/livestream_analysis/README.md).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

NY = ZoneInfo("America/New_York")

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
LIVESTREAM_MANIFEST = CORPUS_DIR / "livestream_manifest.json"
TRANSCRIPTS_DIR = CORPUS_DIR / "transcripts"
FRAMES_DIR = CORPUS_DIR / "livestream_frames"

SAMPLE_SECONDS = 10
THUMB_W, THUMB_H = 160, 90
CUT_THRESHOLD = 10.0  # mean abs gray diff (0-255) between consecutive samples that counts as a view change
MIN_HOLD_SECONDS = 20  # ignore views shown for less than this (scrolling, menus)
MAX_GAP_SECONDS = 240
FORMAT = "303/399/299/bestvideo[height<=1080]"


def log(msg: str) -> None:
    print(msg, flush=True)


def download_video(video_id: str, video_dir: Path) -> Path:
    video_dir.mkdir(parents=True, exist_ok=True)
    found = [p for p in video_dir.glob(f"{video_id}.*") if p.suffix in {".webm", ".mp4", ".mkv"}]
    if found:
        return found[0]
    completed = subprocess.run(
        ["yt-dlp", "--no-update", "--js-runtimes", "node", "-f", FORMAT, "-o", str(video_dir / "%(id)s.%(ext)s"), f"https://youtu.be/{video_id}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600, check=False,
    )
    found = [p for p in video_dir.glob(f"{video_id}.*") if p.suffix in {".webm", ".mp4", ".mkv"}]
    if completed.returncode != 0 or not found:
        raise RuntimeError(completed.stderr[-800:])
    return found[0]


def sample_thumbs(video: Path) -> np.ndarray:
    completed = subprocess.run(
        ["ffmpeg", "-v", "error", "-skip_frame", "nokey", "-i", str(video), "-vf", f"fps=1/{SAMPLE_SECONDS},scale={THUMB_W}:{THUMB_H},format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True, timeout=3600,
    )
    frames = np.frombuffer(completed.stdout, dtype=np.uint8)
    return frames.reshape(-1, THUMB_H, THUMB_W).astype(np.int16)


def select_times(thumbs: np.ndarray, max_frames: int) -> list[int]:
    n = len(thumbs)
    if n == 0:
        return []
    diffs = np.zeros(n)
    diffs[1:] = np.abs(thumbs[1:] - thumbs[:-1]).mean(axis=(1, 2))
    cuts = [i for i in range(1, n) if diffs[i] > CUT_THRESHOLD]
    picks: list[int] = []
    view_start = 0
    for cut in cuts + [n]:
        last = cut - 1
        if (last - view_start) * SAMPLE_SECONDS >= MIN_HOLD_SECONDS:
            picks.append(last)
        view_start = cut
    picks = sorted(set(picks) | {n - 1})
    filled: list[int] = []
    prev = 0
    for p in picks:
        while (p - prev) * SAMPLE_SECONDS > MAX_GAP_SECONDS:
            prev += MAX_GAP_SECONDS // SAMPLE_SECONDS
            filled.append(prev)
        filled.append(p)
        prev = p
    filled = sorted(set(filled))
    if len(filled) > max_frames:
        idx = np.linspace(0, len(filled) - 1, max_frames).round().astype(int)
        filled = [filled[i] for i in sorted(set(idx))]
    return [i * SAMPLE_SECONDS for i in filled]


def extract_frame(video: Path, seconds: int, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", str(seconds), "-i", str(video), "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "4", str(out)],
        check=True, timeout=300,
    )


def fmt(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def stream_start_ts(video_id: str) -> int | None:
    """Unix time the live broadcast started (the VOD's t=0), or None for non-live uploads."""
    completed = subprocess.run(
        ["yt-dlp", "--no-update", "--js-runtimes", "node", "--skip-download", "--print", "%(release_timestamp)s", f"https://youtu.be/{video_id}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False,
    )
    value = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    return int(value) if value.isdigit() else None


def ny_clock(start_ts: int | None, seconds: float) -> str:
    if start_ts is None:
        return ""
    return datetime.fromtimestamp(start_ts + seconds, NY).strftime(" (%H:%M New York)")


def build_packet(row: dict, times: list[int], transcript: list[dict], frame_dir: Path, start_ts: int | None = None) -> str:
    start_line = (
        f"stream start: {datetime.fromtimestamp(start_ts, NY):%Y-%m-%d %H:%M:%S} New York — frame headings carry New York clock time"
        if start_ts else "stream start: unknown (no clock times)"
    )
    lines = [
        f"# {row['title']} — {row.get('upload_date')}",
        f"video_id: {row['video_id']}  url: {row['url']}  duration: {fmt(row['duration_seconds'])}",
        f"slug: {row['slug']}",
        start_line,
        "",
        "## Description",
        (row.get("description") or "").strip()[:1500],
        "",
        "## Frames with the speech leading up to each",
        "Each frame shows the screen at that time. The text under it is what was said since the previous frame.",
        "",
    ]
    prev = 0.0
    for t in times + [None]:
        end = t if t is not None else 10**9
        speech = " ".join(s["text"] for s in transcript if prev <= s["start"] < end)
        if t is None:
            if speech:
                lines += ["### After last frame", speech, ""]
            break
        lines += [f"### Frame {fmt(t)}{ny_clock(start_ts, t)}",f"image: {(frame_dir / f't{t:05d}.jpg').as_posix()}", speech or "(no speech)", ""]
        prev = t
    return "\n".join(lines)


def process(row: dict, video_dir: Path, max_frames: int) -> int:
    transcript_path = TRANSCRIPTS_DIR / f"{row['slug']}.json"
    if not transcript_path.exists():
        raise RuntimeError("no transcript yet")
    frame_dir = FRAMES_DIR / row["slug"]
    if (frame_dir / "packet.md").exists():
        return -1
    # One worker per stream: parallel runs (different --shard or --reverse) skip locked streams.
    lock = video_dir / f"{row['video_id']}.lock"
    video_dir.mkdir(parents=True, exist_ok=True)
    if lock.exists() and time.time() - lock.stat().st_mtime < 3600:
        return -1
    lock.write_text(str(os.getpid()), encoding="utf-8")
    try:
        return _process_locked(row, video_dir, max_frames, frame_dir, transcript_path)
    finally:
        lock.unlink(missing_ok=True)


def _process_locked(row: dict, video_dir: Path, max_frames: int, frame_dir: Path, transcript_path: Path) -> int:
    video = download_video(row["video_id"], video_dir)
    times = select_times(sample_thumbs(video), max_frames)
    frame_dir.mkdir(parents=True, exist_ok=True)
    for t in times:
        extract_frame(video, t, frame_dir / f"t{t:05d}.jpg")
    start_ts = stream_start_ts(row["video_id"])
    (frame_dir / "frames.json").write_text(
        json.dumps({"slug": row["slug"], "video_id": row["video_id"], "stream_start_ts": start_ts, "frame_seconds": times}, indent=2),
        encoding="utf-8",
    )
    write_packet(row, frame_dir)
    return len(times)


def write_packet(row: dict, frame_dir: Path) -> None:
    meta = json.loads((frame_dir / "frames.json").read_text(encoding="utf-8"))
    if "stream_start_ts" not in meta:
        meta["stream_start_ts"] = stream_start_ts(row["video_id"])
        (frame_dir / "frames.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    transcript = json.loads((TRANSCRIPTS_DIR / f"{row['slug']}.json").read_text(encoding="utf-8"))
    packet = build_packet(row, meta["frame_seconds"], transcript, frame_dir, meta["stream_start_ts"])
    (frame_dir / "packet.md").write_text(packet, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video-dir", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=30)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only", default=None, help="Only this video_id.")
    parser.add_argument("--shard", default=None, help="i/n: only process every n-th stream starting at i (parallel runs).")
    parser.add_argument("--reverse", action="store_true", help="Process oldest streams first (for a second parallel worker).")
    parser.add_argument("--repacket",action="store_true", help="Only rebuild packet.md (adds New York clock times) for streams with frames.")
    args = parser.parse_args()
    rows = json.loads(LIVESTREAM_MANIFEST.read_text(encoding="utf-8"))["videos"]
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        rows = rows[i::n]
    if args.reverse:
        rows = rows[::-1]
    if args.only:
        rows = [r for r in rows if r["video_id"] == args.only]
    if args.repacket:
        for row in rows:
            frame_dir = FRAMES_DIR / row["slug"]
            if (frame_dir / "frames.json").exists():
                write_packet(row, frame_dir)
                log(f"repacketed {row['video_id']}")
        return
    done = 0
    for row in rows:
        if args.limit and done >= args.limit:
            break
        try:
            n = process(row, args.video_dir, args.max_frames)
            if n >= 0:
                done += 1
                log(f"{row['upload_date']} {row['video_id']}: {n} frames")
        except Exception as exc:
            log(f"{row['upload_date']} {row['video_id']}: FAILED {str(exc)[:300]}")


if __name__ == "__main__":
    main()
