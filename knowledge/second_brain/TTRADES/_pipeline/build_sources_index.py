"""Write TTRADES/sources-index.md: every source note by date (recorded, else YouTube upload date).

  python build_sources_index.py
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

KB = Path(__file__).resolve().parent.parent
UPLOADS = KB / "_pipeline" / "upload_dates.txt"


def main() -> None:
    uploads = {}
    for line in UPLOADS.read_text(encoding="utf-8").split("\n") if UPLOADS.exists() else []:
        p = line.split()
        if len(p) == 2 and re.fullmatch(r"\d{8}", p[1]):
            uploads[p[0]] = f"{p[1][:4]}-{p[1][4:6]}-{p[1][6:]}"
    rows = []
    for p in sorted((KB / "sources").glob("*.md")):
        t = p.read_text(encoding="utf-8")
        try:
            fm = yaml.safe_load(t.split("---", 2)[1]) or {}
        except yaml.YAMLError:
            fm = {}
        rec = str(fm.get("recorded") or "unknown")
        when, mark = (rec, "") if re.match(r"\d{4}-\d{2}-\d{2}", rec) else (uploads.get(str(fm.get("youtube_id")), "unknown"), " (upload)")
        n = len(re.findall(r"^\|\s*\d+\s*\|", t.split("## Key rules", 1)[-1].split("\n## ", 1)[0], re.M))
        concepts = ", ".join((fm.get("concepts") or [])[:5])
        title = str(fm.get("title", p.stem)).replace("|", "/")
        rows.append((when, f"| {when}{mark} | [[sources/{p.stem}\\|{title}]] | {fm.get('format', '?')} | {fm.get('confidence', '?')} | {n} | {concepts} |"))
    rows.sort()
    out = ["---", 'title: "TTRADES: sources by date"', "type: ttrades-sources-index", f"last_updated: {date.today()}", "---", "",
           f"# Sources ({len(rows)})", "", "Dates are the recording date when the video shows or says it, otherwise the YouTube upload date.", "",
           "| Date | Source | Format | Conf. | Rules | Main concepts |", "|---|---|---|---|---|---|", *[r for _, r in rows]]
    (KB / "sources-index.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(len(rows), "sources")


if __name__ == "__main__":
    main()
