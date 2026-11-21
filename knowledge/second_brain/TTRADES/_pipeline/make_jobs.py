"""Write analyst batch job files for the TTrades education videos that have no source note yet.

  python make_jobs.py [batches=12] [--only slugs.txt] [--prefix redo]

--only: just these slugs, even when a note exists (the job says to overwrite it); --prefix names the files.

Reads the corpus chunks (knowledge/ttfm_video_corpus/chunks.jsonl), packs the videos without a
`sources/<slug>.md` into N batches of similar total length, and writes `_pipeline/jobs/batch-NN.md`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent
REPO = KB.parents[2]
CORPUS = REPO / "knowledge" / "ttfm_video_corpus"
PAGES = REPO / "artifacts" / "ttrades" / "pages"
EDU = ("educational_youtube", "trade_review", "seed_curriculum")


def videos() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in (CORPUS / "chunks.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        if d["corpus_partition"] not in EDU:
            continue
        v = out.setdefault(d["video_slug"], {"slug": d["video_slug"], "title": d["title"], "id": d["video_id"],
                                             "partition": d["corpus_partition"], "page": d.get("source_page") or "", "end": 0.0})
        v["end"] = max(v["end"], d["end"])
    return out


def page_for(v: dict) -> str:
    cands = [v["slug"]]
    if "ttrades.com/" in v["page"]:
        cands.append(v["page"].rstrip("/").rsplit("/", 1)[-1].replace("-", "_"))
    for c in cands:
        if (PAGES / f"{c}.md").exists():
            return (PAGES / f"{c}.md").as_posix()
    return "none"


def main() -> None:
    args = sys.argv[1:]
    only = set(Path(args[args.index("--only") + 1]).read_text(encoding="utf-8").split()) if "--only" in args else None
    prefix = args[args.index("--prefix") + 1] if "--prefix" in args else "batch"
    n = int(args[0]) if args and args[0].isdigit() else 12
    todo = [v for v in videos().values() if (v["slug"] in only if only else not (KB / "sources" / f"{v['slug']}.md").exists())]
    todo.sort(key=lambda v: -v["end"])
    bins: list[list[dict]] = [[] for _ in range(n)]
    for v in todo:  # longest first into the lightest bin
        min(bins, key=lambda b: sum(x["end"] for x in b)).append(v)
    jobs = HERE / "jobs"
    jobs.mkdir(exist_ok=True)
    for i, b in enumerate(x for x in bins if x):
        lines = [f"# Analyst {prefix} {i + 1:02d}", "",
                 f"Read and follow {HERE.as_posix()}/analyst_brief.md exactly. Write one source note per video below,",
                 "one at a time (read a transcript, write its note, then the next).", ""]
        if only:
            lines += ["Each video already has a note written WITHOUT a real transcript (from frames or a temporary Whisper run).",
                      "Its corpus transcript has now been re-made with Whisper. Overwrite the note entirely from the new",
                      "transcript; quotes must be verbatim from it. Do not run Whisper yourself.", ""]
        for v in b:
            lines += [f"## {v['slug']}",
                      f"- title: \"{v['title']}\"",
                      f"- youtube_id: {v['id']}; youtube_url: https://www.youtube.com/watch?v={v['id']}; partition: {v['partition']}; {v['end'] / 60:.0f} min",
                      f"- transcript: {(CORPUS / 'transcripts' / (v['slug'] + '.txt')).as_posix()}",
                      f"- frames: {(CORPUS / 'frames' / v['slug']).as_posix()} and {(CORPUS / 'dense_frames' / v['slug']).as_posix()} (either may be missing)",
                      f"- page: {page_for(v)}",
                      f"- write: {(KB / 'sources' / (v['slug'] + '.md')).as_posix()}", ""]
        p = jobs / f"{prefix}-{i + 1:02d}.md"
        p.write_text("\n".join(lines), encoding="utf-8")
        print(f"{p.as_posix()} | {len(b)} videos | {sum(x['end'] for x in b) / 60:.0f} min")
    print(len(todo), "videos without a note")


if __name__ == "__main__":
    main()
