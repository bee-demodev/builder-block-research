from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "ttrades_manifest.json"

EDUCATION_CENTER_URL = "https://ttrades.com/trading-education-center/"
USER_AGENT = "Mozilla/5.0 (compatible; trading-autoresearch/0.1; +https://ttrades.com/)"

YOUTUBE_HOST_MARKERS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
TTTRADES_HOST = "ttrades.com"
MEDIA_EXTENSIONS = (".pdf", ".mp4", ".mov", ".webm", ".m4v")


@dataclass
class DiscoveredItem:
    title: str
    url: str
    source_type: str
    category_hint: str
    discovered_from: str
    embedded_youtube_urls: list[str] = field(default_factory=list)
    embedded_asset_urls: list[str] = field(default_factory=list)
    canonical_url: str | None = None


class LinkCollector(HTMLParser):
    def __init__(self, page_url: str) -> None:
        super().__init__()
        self.page_url = page_url
        self.links: list[tuple[str, str]] = []
        self.iframes: list[str] = []
        self._inside_title = False
        self._title_parts: list[str] = []
        self._current_anchor_href: str | None = None
        self._current_anchor_text: list[str] = []

    @property
    def page_title(self) -> str:
        return " ".join("".join(self._title_parts).split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key: value for key, value in attrs}
        if tag == "title":
            self._inside_title = True
            return
        if tag == "a":
            href = attrs_map.get("href")
            if href:
                self._current_anchor_href = urljoin(self.page_url, href)
                self._current_anchor_text = []
            return
        if tag == "iframe":
            src = attrs_map.get("src")
            if src:
                self.iframes.append(urljoin(self.page_url, src))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._inside_title = False
            return
        if tag == "a" and self._current_anchor_href:
            text = " ".join("".join(self._current_anchor_text).split())
            self.links.append((text, self._current_anchor_href))
            self._current_anchor_href = None
            self._current_anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_parts.append(data)
        if self._current_anchor_href is not None:
            self._current_anchor_text.append(data)


def fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean_path = re.sub(r"/+$", "/", parsed.path or "/")
    query = parsed.query if any(marker in parsed.netloc for marker in YOUTUBE_HOST_MARKERS) else ""
    return parsed._replace(fragment="", query=query, path=clean_path).geturl()


def infer_category_hint(title: str, url: str) -> str:
    value = f"{title} {url}".lower()
    if "bias" in value or "next-day" in value or "next day" in value or "profile" in value:
        return "bias"
    if "expansion" in value:
        return "expansion"
    if "protected swing" in value or "stop loss" in value:
        return "protected_swings"
    if "retracement" in value:
        return "retracement"
    if "reversal" in value or "wick" in value:
        return "reversal"
    if "consolidation" in value:
        return "consolidation"
    if "continuation" in value:
        return "continuation"
    if "candle" in value:
        return "fractal_model"
    return "general"


def infer_source_type(title: str, url: str) -> str:
    if any(marker in url for marker in YOUTUBE_HOST_MARKERS):
        return "video"
    if "pdf" in title.lower() or "/pdf" in url.lower():
        return "pdf_landing"
    return "article"


def discover_index_items(index_url: str) -> list[DiscoveredItem]:
    parser = LinkCollector(index_url)
    parser.feed(fetch_html(index_url))

    seen: set[str] = set()
    items: list[DiscoveredItem] = []
    for text, href in parser.links:
        normalized = normalize_url(href)
        if TTTRADES_HOST not in normalized:
            continue
        if not text or len(text) < 6:
            continue
        if "/trading-education-center" in normalized and normalized != EDUCATION_CENTER_URL:
            continue
        if normalized in {
            EDUCATION_CENTER_URL,
            "https://ttrades.com/trading-education-center",
            "https://ttrades.com/privacy-policy/",
            "https://ttrades.com/opt-out-preferences/",
        }:
            continue
        if "#" in normalized:
            continue
        key = normalized
        if key in seen:
            continue
        seen.add(key)
        items.append(
            DiscoveredItem(
                title=text,
                url=normalized,
                source_type=infer_source_type(text, normalized),
                category_hint=infer_category_hint(text, normalized),
                discovered_from=index_url,
            )
        )
    return items


def enrich_item(item: DiscoveredItem) -> None:
    parser = LinkCollector(item.url)
    parser.feed(fetch_html(item.url))
    item.canonical_url = normalize_url(item.url)

    youtube_urls: list[str] = []
    asset_urls: list[str] = []
    for _, href in parser.links:
        normalized = normalize_url(href)
        if any(marker in normalized for marker in YOUTUBE_HOST_MARKERS):
            youtube_urls.append(normalized)
        elif normalized.lower().endswith(MEDIA_EXTENSIONS) or "pdf" in normalized.lower():
            asset_urls.append(normalized)

    for iframe_src in parser.iframes:
        normalized = normalize_url(iframe_src)
        if any(marker in normalized for marker in YOUTUBE_HOST_MARKERS):
            youtube_urls.append(normalized)
        elif normalized.lower().endswith(MEDIA_EXTENSIONS) or "pdf" in normalized.lower():
            asset_urls.append(normalized)

    item.embedded_youtube_urls = sorted(set(youtube_urls))
    item.embedded_asset_urls = sorted(set(asset_urls))
    if parser.page_title and parser.page_title.strip():
        item.title = item.title or parser.page_title.strip()


def serialize_item(item: DiscoveredItem) -> dict:
    return {
        "title": item.title,
        "url": item.url,
        "source_type": item.source_type,
        "category_hint": item.category_hint,
        "discovered_from": item.discovered_from,
        "canonical_url": item.canonical_url or item.url,
        "embedded_youtube_urls": item.embedded_youtube_urls,
        "embedded_asset_urls": item.embedded_asset_urls,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover TTrades article and embedded media sources from the Education Center.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--fetch-details", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--category", action="append", default=[])
    args = parser.parse_args()

    items = discover_index_items(EDUCATION_CENTER_URL)
    if args.category:
        allowed = set(args.category)
        items = [item for item in items if item.category_hint in allowed]
    if args.limit is not None:
        items = items[: args.limit]

    if args.fetch_details:
        for index, item in enumerate(items, start=1):
            try:
                enrich_item(item)
            except Exception as exc:  # pragma: no cover - network variability
                item.embedded_asset_urls.append(f"error://detail-fetch-failed::{exc}")
            print(
                json.dumps(
                    {
                        "detail_progress": f"{index}/{len(items)}",
                        "title": item.title,
                        "youtube_urls": len(item.embedded_youtube_urls),
                        "asset_urls": len(item.embedded_asset_urls),
                    }
                ),
                flush=True,
            )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed_url": EDUCATION_CENTER_URL,
        "item_count": len(items),
        "items": [serialize_item(item) for item in items],
    }
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "item_count": len(items)}, indent=2))


if __name__ == "__main__":
    main()
