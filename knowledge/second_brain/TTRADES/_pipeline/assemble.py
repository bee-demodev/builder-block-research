"""Join the merge fragments into conflicts.md and glossary.md, then rebuild the index.

  python assemble.py

conflicts.md: one `## [[page]]` section per page, from _merge/<page>/conflicts-fragment.md.
glossary.md:  one Terms table (every fragment's rows, sorted by term) and one Mishearings table.
"""
from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
KB = HERE.parent
sys.path.insert(0, str(HERE))
from merge_digests import PAGES  # noqa: E402


def main() -> None:
    today = date.today().isoformat()
    conf = ["---", 'title: "TTRADES: conflicts and open questions"', "type: ttrades-conflicts", f"last_updated: {today}", "---", "",
            "# Conflicts and open questions",
            "",
            "Where the teacher's videos disagree, speech and chart disagree, the companion's engine differs from the teacher, or a",
            "rule engine still needs a number he never gives. Vik settles them in [[decisions]] (TD-nnn); the lookup then shows",
            "them as DECIDED. Do not code against an open row without asking.", ""]
    terms, mis, n_conf = [], [], 0
    for pid in PAGES:
        d = KB / "_merge" / pid
        f = d / "conflicts-fragment.md"
        if f.exists():
            t = f.read_text(encoding="utf-8").strip()
            n_conf += sum(1 for l in t.splitlines() if re.match(r"\|\s*[A-Z0-9]+-\d+\s*\|", l))
            conf += [t, ""]
        g = d / "glossary-fragment.md"
        if g.exists():
            for line in g.read_text(encoding="utf-8").splitlines():
                c = [x.strip() for x in line.strip().split("|")[1:-1]]
                if len(c) >= 5 and not c[0].lower().startswith("term") and not set(c[0]) <= set("-: "):
                    terms.append(line.strip())
                elif re.match(r"\s*[-*]\s*[\"“`]", line):
                    mis.append(line.strip())
    (KB / "conflicts.md").write_text("\n".join(conf) + "\n", encoding="utf-8")
    seen, rows = set(), []
    for t in sorted(terms, key=lambda s: s.split("|")[1].strip().lower()):
        key = t.split("|")[1].strip().lower()
        if key not in seen:
            seen.add(key)
            rows.append(t)
    gl = ["---", 'title: "TTRADES: glossary"', "type: ttrades-glossary", f"last_updated: {today}", "---", "", "# Glossary", "",
          "Terms as TTrades uses them, the concept page that owns each, and transcript mishearings. The index uses the",
          "aliases so `tt_lookup.py <term>` resolves to the right page.", "", "## Terms", "",
          "| Term | Aliases / mishearings | Meaning (as TTrades uses it) | Concept page | Main source (slug, time) |", "|---|---|---|---|---|", *rows, "",
          "## Mishearings", "", "| Spelling | Term |", "|---|---|"]
    # the mishearings the analyst and livestream briefs already knew; the fragments only list new ones
    for spelling, term in (("sis D", "CISD"), ("CSD", "CISD"), ("C SD", "CISD"), ("ICCISD", "IC-CISD"), ("intro candle", "IC-CISD"),
                           ("IFEG", "IFVG"), ("FEG", "FVG"), ("PSB", "PSP"), ("candle to", "candle 2"), ("Bractal", "fractal")):
        gl.append(f"| {spelling} | {term} (analyst brief) |")
    for m in sorted(set(mis)):
        mm = re.match(r"[-*]\s*[\"“`](.+?)[\"”`]\s*(?:->|→)\s*(.+)$", m)
        if mm:
            gl.append(f"| {mm.group(1)} | {mm.group(2).replace('|', '/')} |")
    (KB / "glossary.md").write_text("\n".join(gl) + "\n", encoding="utf-8")
    print(f"conflicts.md: {n_conf} rows | glossary.md: {len(rows)} terms, {len(gl) - len(rows) - 17} mishearings")
    subprocess.run([sys.executable, str(HERE / "build_index.py")], check=True)


if __name__ == "__main__":
    main()
