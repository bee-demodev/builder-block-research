from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_MANIFEST = ROOT / "data" / "ttrades_manifest.json"


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def normalize_key(value: str) -> str:
    return slugify(value)


def infer_title_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1].replace("-", " ").title()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def load_topic_lookup(connection: sqlite3.Connection) -> dict[str, int]:
    if not table_exists(connection, "research_topics"):
        return {}

    lookup = {
        normalize_key(slug): int(topic_id)
        for topic_id, slug in connection.execute("SELECT id, slug FROM research_topics")
    }
    if table_exists(connection, "research_topic_aliases"):
        for topic_id, alias in connection.execute("SELECT topic_id, alias FROM research_topic_aliases"):
            lookup[normalize_key(alias)] = int(topic_id)
    return lookup


def load_trade_model_lookup(connection: sqlite3.Connection) -> dict[str, int]:
    if not table_exists(connection, "trade_models"):
        return {}

    lookup = {
        normalize_key(slug): int(model_id)
        for model_id, slug in connection.execute("SELECT id, slug FROM trade_models")
    }
    if table_exists(connection, "trade_model_aliases"):
        for model_id, alias in connection.execute("SELECT trade_model_id, alias FROM trade_model_aliases"):
            lookup[normalize_key(alias)] = int(model_id)
    return lookup


def link_source_coverage(
    connection: sqlite3.Connection,
    source_id: int,
    coverage_hint: str | None,
    relation_type: str,
    notes: str,
    topic_lookup: dict[str, int],
    trade_model_lookup: dict[str, int],
    *,
    clear_existing: bool = False,
) -> tuple[int, int]:
    if not coverage_hint:
        return 0, 0

    key = normalize_key(coverage_hint)
    topic_links = 0
    trade_model_links = 0

    if clear_existing:
        if table_exists(connection, "source_topics"):
            connection.execute(
                "DELETE FROM source_topics WHERE source_id = ? AND relation_type = ?",
                (source_id, relation_type),
            )
        if table_exists(connection, "source_trade_models"):
            connection.execute(
                "DELETE FROM source_trade_models WHERE source_id = ? AND relation_type = ?",
                (source_id, relation_type),
            )

    if key in topic_lookup and table_exists(connection, "source_topics"):
        connection.execute(
            """
            INSERT OR IGNORE INTO source_topics (
                source_id, topic_id, relation_type, confidence, notes, updated_at
            ) VALUES (?, ?, ?, 1.0, ?, CURRENT_TIMESTAMP)
            """,
            (source_id, topic_lookup[key], relation_type, notes),
        )
        topic_links += 1

    if key in trade_model_lookup and table_exists(connection, "source_trade_models"):
        connection.execute(
            """
            INSERT OR IGNORE INTO source_trade_models (
                source_id, trade_model_id, relation_type, confidence, notes, updated_at
            ) VALUES (?, ?, ?, 1.0, ?, CURRENT_TIMESTAMP)
            """,
            (source_id, trade_model_lookup[key], relation_type, notes),
        )
        trade_model_links += 1

    return topic_links, trade_model_links


def upsert_source(connection: sqlite3.Connection, item: dict) -> int:
    canonical_url = item.get("canonical_url") or item["url"]
    source_title = item.get("title") or infer_title_from_url(canonical_url)
    slug = slugify(source_title) or slugify(canonical_url)
    source_type = item.get("source_type", "article")
    topic_hint = item.get("category_hint")
    summary = f"Discovered from TTrades Education Center baseline manifest ({item.get('discovered_from', 'unknown source')})."

    existing = connection.execute(
        "SELECT id FROM sources WHERE canonical_url = ?",
        (canonical_url,),
    ).fetchone()
    if existing:
        connection.execute(
            """
            UPDATE sources
            SET slug = ?, source_type = ?, title = ?, author = ?, topic_hint = ?, summary = ?
            WHERE id = ?
            """,
            (slug, source_type, source_title, "TTrades", topic_hint, summary, existing[0]),
        )
        return int(existing[0])

    connection.execute(
        """
        INSERT INTO sources (slug, source_type, title, canonical_url, author, topic_hint, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (slug, source_type, source_title, canonical_url, "TTrades", topic_hint, summary),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def ensure_media_source(connection: sqlite3.Connection, url: str, topic_hint: str | None, parent_title: str) -> int:
    existing = connection.execute(
        "SELECT id FROM sources WHERE canonical_url = ?",
        (url,),
    ).fetchone()
    if existing:
        return int(existing[0])

    source_type = "video" if "youtu" in url else "asset"
    title = f"Embedded media from {parent_title}"
    slug = slugify(url)
    summary = f"Embedded media discovered from TTrades page '{parent_title}'."
    connection.execute(
        """
        INSERT INTO sources (slug, source_type, title, canonical_url, author, topic_hint, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (slug, source_type, title, url, "TTrades", topic_hint, summary),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def upsert_artifact(connection: sqlite3.Connection, source_id: int, artifact_type: str, path: str, notes: str) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO source_artifacts (source_id, artifact_type, path, notes)
        VALUES (?, ?, ?, ?)
        """,
        (source_id, artifact_type, path, notes),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a discovered TTrades corpus manifest into SQLite.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    items = manifest.get("items", [])
    source_count = 0
    artifact_count = 0
    media_source_count = 0
    source_topic_links = 0
    source_trade_model_links = 0

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        topic_lookup = load_topic_lookup(connection)
        trade_model_lookup = load_trade_model_lookup(connection)

        for item in items:
            source_id = upsert_source(connection, item)
            source_count += 1

            topic_link_count, trade_model_link_count = link_source_coverage(
                connection,
                source_id,
                item.get("category_hint"),
                "primary_hint",
                "Primary category derived from the imported TTrades manifest.",
                topic_lookup,
                trade_model_lookup,
                clear_existing=True,
            )
            source_topic_links += topic_link_count
            source_trade_model_links += trade_model_link_count

            parent_title = item.get("title", "TTrades page")
            parent_hint = item.get("category_hint")

            for youtube_url in item.get("embedded_youtube_urls", []):
                media_source_id = ensure_media_source(connection, youtube_url, parent_hint, parent_title)
                media_source_count += 1
                topic_link_count, trade_model_link_count = link_source_coverage(
                    connection,
                    media_source_id,
                    parent_hint,
                    "embedded_parent_category",
                    f"Inherited from parent page '{parent_title}'.",
                    topic_lookup,
                    trade_model_lookup,
                )
                source_topic_links += topic_link_count
                source_trade_model_links += trade_model_link_count
                upsert_artifact(
                    connection,
                    source_id,
                    "embedded_youtube",
                    youtube_url,
                    f"Linked media source id={media_source_id}",
                )
                artifact_count += 1

            for asset_url in item.get("embedded_asset_urls", []):
                if asset_url.startswith("error://"):
                    upsert_artifact(connection, source_id, "detail_fetch_error", asset_url, "Detail fetch error during discovery")
                else:
                    media_source_id = ensure_media_source(connection, asset_url, parent_hint, parent_title)
                    media_source_count += 1
                    topic_link_count, trade_model_link_count = link_source_coverage(
                        connection,
                        media_source_id,
                        parent_hint,
                        "embedded_parent_category",
                        f"Inherited from parent page '{parent_title}'.",
                        topic_lookup,
                        trade_model_lookup,
                    )
                    source_topic_links += topic_link_count
                    source_trade_model_links += trade_model_link_count
                    upsert_artifact(
                        connection,
                        source_id,
                        "embedded_asset",
                        asset_url,
                        f"Linked media source id={media_source_id}",
                    )
                artifact_count += 1

        connection.commit()

    print(
        json.dumps(
            {
                "manifest_items": len(items),
                "page_sources_processed": source_count,
                "embedded_media_sources_created_or_seen": media_source_count,
                "source_topic_links_added_or_seen": source_topic_links,
                "source_trade_model_links_added_or_seen": source_trade_model_links,
                "artifacts_processed": artifact_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
