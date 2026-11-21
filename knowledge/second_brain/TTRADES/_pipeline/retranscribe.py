"""Replace placeholder transcripts in the corpus with real ones (faster-whisper large-v3-turbo, GPU).

  python retranscribe.py [slugs.txt] [--download]   default: _pipeline/placeholder_slugs.txt; --download skips the local mp4

62 education transcripts in knowledge/ttfm_video_corpus/transcripts/ held 5 template lines instead of
speech. For each slug: the placeholder pair is copied to transcripts/_placeholder_backup/ (once), the
local mp4 is used when it has an audio stream longer than 30 s, otherwise the audio is fetched with
yt-dlp into ttfm_video_corpus/audio_redownload/, and the transcript is written in the corpus format
(<slug>.json: [{text, start, duration}], <slug>.txt: "[seconds] text").
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parents[2] / "ttfm_video_corpus"
T = CORPUS / "transcripts"
BACKUP = T / "_placeholder_backup"
REDL = CORPUS / "audio_redownload"
PROMPT = ("TTrades fractal model trading lesson on NQ, ES and YM futures: candle 2 closure, candle 3, candle 4, CISD, change in the state "
          "of delivery, IC-CISD, protected swing, FVG, fair value gap, IFVG, order block, breaker block, SMT, PSP, POI, equilibrium, EQ, "
          "premium, discount, ADR, daily bias, weekly profile, OHLC, OLHC, liquidity sweep, MMXM, ICT, OTE, displacement, Asia, London, New York.")


def video_ids() -> dict[str, str]:
    ids = {}
    for line in (CORPUS / "chunks.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        ids.setdefault(d["video_slug"], d["video_id"])
    return ids


def audio_seconds(p: Path) -> float:
    if not p.exists():
        return 0.0
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration:format=duration",
                        "-of", "json", str(p)], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout or "{}")
        if not d.get("streams"):
            return 0.0
        return float(d["streams"][0].get("duration") or d.get("format", {}).get("duration") or 0)
    except (ValueError, KeyError):
        return 0.0


def media_for(slug: str, vid: str, force_download: bool = False) -> Path | None:
    mp4 = CORPUS / "videos" / f"{slug}.mp4"
    if not force_download and audio_seconds(mp4) > 30:  # a truncated download can still claim its full duration
        return mp4
    REDL.mkdir(exist_ok=True)
    have = list(REDL.glob(f"{slug}.*"))
    if not have:
        subprocess.run(["yt-dlp", "-q", "--no-warnings", "-f", "bestaudio", "-o", str(REDL / f"{slug}.%(ext)s"),
                        f"https://www.youtube.com/watch?v={vid}"], check=False)
        have = list(REDL.glob(f"{slug}.*"))
    return have[0] if have and audio_seconds(have[0]) > 30 else None


def main() -> None:
    pos = [a for a in sys.argv[1:] if not a.startswith("--")]
    lst = Path(pos[0]) if pos else HERE / "placeholder_slugs.txt"
    slugs = [s.strip() for s in lst.read_text(encoding="utf-8").splitlines() if s.strip()]
    ids = video_ids()
    from faster_whisper import BatchedInferencePipeline, WhisperModel
    model = WhisperModel("mobiuslabsgmbh/faster-whisper-large-v3-turbo", device="cuda", compute_type="float16")
    pipe = BatchedInferencePipeline(model=model)
    BACKUP.mkdir(exist_ok=True)
    for s in slugs:
        j = T / f"{s}.json"
        if j.exists():
            rows = json.loads(j.read_text(encoding="utf-8"))
            if isinstance(rows, list) and len(rows) > 6:
                print("skip (real transcript)", s, flush=True)
                continue
            for ext in ("json", "txt"):
                if (T / f"{s}.{ext}").exists() and not (BACKUP / f"{s}.{ext}").exists():
                    shutil.copy2(T / f"{s}.{ext}", BACKUP / f"{s}.{ext}")
        media = media_for(s, ids.get(s, ""), "--download" in sys.argv)
        if media is None:
            print("NO AUDIO", s, flush=True)
            continue
        t0 = time.time()
        segs, info = pipe.transcribe(str(media), language="en", batch_size=16, vad_filter=True, initial_prompt=PROMPT)
        out = [{"text": " ".join(x.text.split()), "start": round(x.start, 2), "duration": round(x.end - x.start, 2)} for x in segs if x.text.strip()]
        j.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        (T / f"{s}.txt").write_text("\n".join(f"[{x['start']:.2f}] {x['text']}" for x in out) + "\n", encoding="utf-8")
        print(f"done {s} {info.duration / 60:.1f} min in {time.time() - t0:.0f}s, {len(out)} segs, from {media.name}", flush=True)


if __name__ == "__main__":
    main()
