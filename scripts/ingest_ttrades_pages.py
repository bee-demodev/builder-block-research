from __future__ import annotations

import argparse
import json
import re
import sqlite3
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_MANIFEST = ROOT / "data" / "ttrades_core_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "ttrades" / "pages"
USER_AGENT = "Mozilla/5.0 (compatible; trading-autoresearch/0.1; +https://ttrades.com/)"

BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "blockquote"}
SKIP_TAGS = {"script", "style", "noscript", "svg"}


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


class TTradesArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.in_content = False
        self.content_depth = 0
        self.skip_depth = 0
        self.current_block: str | None = None
        self.current_text: list[str] = []
        self.title_parts: list[str] = []
        self.published_at: str | None = None
        self.lines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key: value for key, value in attrs}
        class_name = attrs_map.get("class") or ""

        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return

        if tag == "title":
            self.in_title = True
            return

        if tag == "meta" and attrs_map.get("property") == "article:published_time" and attrs_map.get("content") and not self.published_at:
            self.published_at = attrs_map["content"]

        if tag == "time" and attrs_map.get("datetime") and not self.published_at:
            self.published_at = attrs_map["datetime"]

        if not self.in_content and "elementor-widget-theme-post-content" in class_name:
            self.in_content = True
            self.content_depth = 1
        elif self.in_content:
            self.content_depth += 1

        if self.in_content and self.skip_depth == 0 and tag in BLOCK_TAGS:
            self.current_block = tag
            self.current_text = []

        if self.in_content and self.current_block and tag == "br":
            self.current_text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return

        if tag == "title":
            self.in_title = False
            return

        if self.current_block == tag:
            text = clean_text("".join(self.current_text))
            self.current_block = None
            self.current_text = []
            if not text:
                return
            if text.lower() in {"related posts", "related post"}:
                return
            prefix = ""
            if tag == "h1":
                prefix = "# "
            elif tag == "h2":
                prefix = "## "
            elif tag == "h3":
                prefix = "### "
            elif tag == "h4":
                prefix = "#### "
            elif tag == "li":
                prefix = "- "
            elif tag == "blockquote":
                prefix = "> "
            self.lines.append(f"{prefix}{text}")

        if self.in_content:
            self.content_depth -= 1
            if self.content_depth <= 0:
                self.in_content = False
                self.content_depth = 0

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        if self.in_title:
            self.title_parts.append(data)
        if self.in_content and self.current_block:
            self.current_text.append(data)

    @property
    def title(self) -> str:
        return clean_text("".join(self.title_parts))


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def resolve_source(connection: sqlite3.Connection, source_ref: str) -> tuple[int, str, str]:
    row = connection.execute(
        "SELECT id, slug, canonical_url FROM sources WHERE canonical_url = ? OR slug = ?",
        (source_ref, source_ref),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown source reference: {source_ref}")
    return int(row[0]), row[1], row[2]


def render_markdown(title: str, canonical_url: str, published_at: str | None, lines: list[str]) -> str:
    deduped_lines: list[str] = []
    previous = None
    for line in lines:
        if line == previous:
            continue
        previous = line
        deduped_lines.append(line)

    body = "\n\n".join(deduped_lines).strip()
    sections = [f"# {title}", "", f"- Source: {canonical_url}"]
    if published_at:
        sections.append(f"- Published: {published_at}")
    sections.extend(["", body])
    return "\n".join(sections).strip() + "\n"


def upsert_artifact(connection: sqlite3.Connection, source_id: int, path: Path) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO source_artifacts (source_id, artifact_type, path, notes)
        VALUES (?, 'page_markdown', ?, ?)
        """,
        (source_id, str(path), "Auto-ingested article markdown extract from TTrades page."),
    )


def load_manifest(manifest_path: Path, categories: set[str] | None) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest.get("items", [])
    if categories:
        items = [item for item in items if item.get("category_hint") in categories]
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and store local markdown extracts for TTrades pages.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    categories = set(args.category) if args.category else None
    items = load_manifest(Path(args.manifest), categories)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if args.source:
            source_id, slug, canonical_url = resolve_source(connection, args.source)
            items = [{"canonical_url": canonical_url, "url": canonical_url, "title": slug.replace("_", " "), "category_hint": None}]

        if args.limit is not None:
            items = items[: args.limit]

        written = 0
        for item in items:
            source_id, slug, canonical_url = resolve_source(connection, item.get("canonical_url") or item["url"])
            html = fetch_html(canonical_url)
            parser_instance = TTradesArticleParser()
            parser_instance.feed(html)
            title = parser_instance.title or item.get("title") or slug.replace("_", " ").title()
            markdown = render_markdown(title, canonical_url, parser_instance.published_at, parser_instance.lines)
            output_path = output_dir / f"{slug}.md"
            output_path.write_text(markdown, encoding="utf-8")
            upsert_artifact(connection, source_id, output_path)
            written += 1

        connection.commit()

    print(json.dumps({"output_dir": str(output_dir), "pages_written": written}, indent=2))


if __name__ == "__main__":
    main()
