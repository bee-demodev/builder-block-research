from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_GRAPH_PATH = ROOT / "data" / "topic_model_graph.json"


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load_graph(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def ensure_trader_profile_status_column(connection: sqlite3.Connection) -> None:
    if not column_exists(connection, "trader_profiles", "status"):
        connection.execute(
            """
            ALTER TABLE trader_profiles
            ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
            """
        )


def json_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def archive_missing_entities(connection: sqlite3.Connection, table: str, active_slugs: list[str]) -> None:
    if active_slugs:
        placeholders = ",".join("?" for _ in active_slugs)
        connection.execute(
            f"""
            UPDATE {table}
            SET status = 'archived',
                updated_at = CURRENT_TIMESTAMP
            WHERE slug NOT IN ({placeholders})
            """,
            active_slugs,
        )
    else:
        connection.execute(
            f"""
            UPDATE {table}
            SET status = 'archived',
                updated_at = CURRENT_TIMESTAMP
            """
        )


def upsert_framework(connection: sqlite3.Connection, framework: dict) -> int:
    connection.execute(
        """
        INSERT INTO frameworks (
            slug, name, framework_type, style_family, status, description, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            framework_type = excluded.framework_type,
            style_family = excluded.style_family,
            status = excluded.status,
            description = excluded.description,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            framework["slug"],
            framework["name"],
            framework["framework_type"],
            framework.get("style_family"),
            framework.get("status", "active"),
            framework["description"],
            framework.get("notes"),
        ),
    )
    row = connection.execute("SELECT id FROM frameworks WHERE slug = ?", (framework["slug"],)).fetchone()
    return int(row[0])


def upsert_topic(connection: sqlite3.Connection, topic: dict) -> int:
    connection.execute(
        """
        INSERT INTO research_topics (
            slug, name, topic_type, status, description, rulebook_path, examples_path, open_questions_path, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            topic_type = excluded.topic_type,
            status = excluded.status,
            description = excluded.description,
            rulebook_path = excluded.rulebook_path,
            examples_path = excluded.examples_path,
            open_questions_path = excluded.open_questions_path,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            topic["slug"],
            topic["name"],
            topic["topic_type"],
            topic.get("status", "planned"),
            topic["description"],
            topic.get("rulebook_path"),
            topic.get("examples_path"),
            topic.get("open_questions_path"),
        ),
    )
    row = connection.execute("SELECT id FROM research_topics WHERE slug = ?", (topic["slug"],)).fetchone()
    return int(row[0])


def upsert_trade_model(connection: sqlite3.Connection, model: dict) -> int:
    connection.execute(
        """
        INSERT INTO trade_models (
            slug, name, model_type, status, description, source_notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            model_type = excluded.model_type,
            status = excluded.status,
            description = excluded.description,
            source_notes = excluded.source_notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            model["slug"],
            model["name"],
            model["model_type"],
            model.get("status", "draft"),
            model["description"],
            model.get("source_notes"),
        ),
    )
    row = connection.execute("SELECT id FROM trade_models WHERE slug = ?", (model["slug"],)).fetchone()
    return int(row[0])


def upsert_trader_profile(connection: sqlite3.Connection, profile: dict) -> int:
    connection.execute(
        """
        INSERT INTO trader_profiles (
            slug, display_name, profile_type, status, notes, style_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(slug) DO UPDATE SET
            display_name = excluded.display_name,
            profile_type = excluded.profile_type,
            status = excluded.status,
            notes = excluded.notes,
            style_json = excluded.style_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            profile["slug"],
            profile["display_name"],
            profile.get("profile_type", "trader"),
            profile.get("status", "active"),
            profile.get("notes"),
            json_or_none(profile.get("style_json")),
        ),
    )
    row = connection.execute("SELECT id FROM trader_profiles WHERE slug = ?", (profile["slug"],)).fetchone()
    return int(row[0])


def sync_topic_aliases(connection: sqlite3.Connection, topics: list[dict], topic_id_by_slug: dict[str, int]) -> int:
    connection.execute("DELETE FROM research_topic_aliases")
    alias_count = 0
    for topic in topics:
        for alias in sorted({normalize_key(alias) for alias in topic.get("aliases", []) if alias}):
            connection.execute(
                "INSERT INTO research_topic_aliases (topic_id, alias) VALUES (?, ?)",
                (topic_id_by_slug[topic["slug"]], alias),
            )
            alias_count += 1
    return alias_count


def sync_trade_model_aliases(connection: sqlite3.Connection, trade_models: list[dict], trade_model_id_by_slug: dict[str, int]) -> int:
    connection.execute("DELETE FROM trade_model_aliases")
    alias_count = 0
    for model in trade_models:
        for alias in sorted({normalize_key(alias) for alias in model.get("aliases", []) if alias}):
            connection.execute(
                "INSERT INTO trade_model_aliases (trade_model_id, alias) VALUES (?, ?)",
                (trade_model_id_by_slug[model["slug"]], alias),
            )
            alias_count += 1
    return alias_count


def sync_framework_topic_terms(
    connection: sqlite3.Connection,
    framework_topic_terms: list[dict],
    framework_id_by_slug: dict[str, int],
    topic_id_by_slug: dict[str, int],
) -> int:
    connection.execute("DELETE FROM framework_topic_terms")
    term_count = 0
    for term in framework_topic_terms:
        connection.execute(
            """
            INSERT INTO framework_topic_terms (framework_id, topic_id, term, term_kind, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                framework_id_by_slug[term["framework"]],
                topic_id_by_slug[term["topic"]],
                term["term"],
                term.get("term_kind", "native"),
                term.get("notes"),
            ),
        )
        term_count += 1
    return term_count


def sync_framework_trade_model_terms(
    connection: sqlite3.Connection,
    framework_trade_model_terms: list[dict],
    framework_id_by_slug: dict[str, int],
    trade_model_id_by_slug: dict[str, int],
) -> int:
    connection.execute("DELETE FROM framework_trade_model_terms")
    term_count = 0
    for term in framework_trade_model_terms:
        connection.execute(
            """
            INSERT INTO framework_trade_model_terms (framework_id, trade_model_id, term, term_kind, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                framework_id_by_slug[term["framework"]],
                trade_model_id_by_slug[term["trade_model"]],
                term["term"],
                term.get("term_kind", "native"),
                term.get("notes"),
            ),
        )
        term_count += 1
    return term_count


def sync_trader_profile_frameworks(
    connection: sqlite3.Connection,
    mappings: list[dict],
    trader_profile_id_by_slug: dict[str, int],
    framework_id_by_slug: dict[str, int],
) -> int:
    connection.execute("DELETE FROM trader_profile_frameworks")
    link_count = 0
    for mapping in mappings:
        connection.execute(
            """
            INSERT INTO trader_profile_frameworks (
                trader_profile_id, framework_id, relation_type, confidence, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                trader_profile_id_by_slug[mapping["profile"]],
                framework_id_by_slug[mapping["framework"]],
                mapping.get("relation_type", "primary_framework"),
                mapping.get("confidence", 1.0),
                mapping.get("notes"),
            ),
        )
        link_count += 1
    return link_count


def sync_trader_profile_trade_models(
    connection: sqlite3.Connection,
    mappings: list[dict],
    trader_profile_id_by_slug: dict[str, int],
    trade_model_id_by_slug: dict[str, int],
) -> int:
    connection.execute("DELETE FROM trader_profile_trade_models")
    link_count = 0
    for mapping in mappings:
        connection.execute(
            """
            INSERT INTO trader_profile_trade_models (
                trader_profile_id, trade_model_id, role, priority, indicator_ready, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                trader_profile_id_by_slug[mapping["profile"]],
                trade_model_id_by_slug[mapping["trade_model"]],
                mapping["role"],
                mapping.get("priority", 2),
                int(bool(mapping.get("indicator_ready", False))),
                mapping.get("notes"),
            ),
        )
        link_count += 1
    return link_count


def sync_trader_profile_topics(
    connection: sqlite3.Connection,
    mappings: list[dict],
    trader_profile_id_by_slug: dict[str, int],
    topic_id_by_slug: dict[str, int],
) -> int:
    connection.execute("DELETE FROM trader_profile_topics")
    link_count = 0
    for mapping in mappings:
        connection.execute(
            """
            INSERT INTO trader_profile_topics (
                trader_profile_id, topic_id, emphasis, priority, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                trader_profile_id_by_slug[mapping["profile"]],
                topic_id_by_slug[mapping["topic"]],
                mapping.get("emphasis", "core"),
                mapping.get("priority", 2),
                mapping.get("notes"),
            ),
        )
        link_count += 1
    return link_count


def build_lookup(items: list[dict], id_by_slug: dict[str, int]) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for item in items:
        lookup[normalize_key(item["slug"])] = id_by_slug[item["slug"]]
        for alias in item.get("aliases", []):
            normalized_alias = normalize_key(alias)
            if normalized_alias:
                lookup[normalized_alias] = id_by_slug[item["slug"]]
    return lookup


def build_dependency_lookup(dependencies: list[dict]) -> dict[str, list[dict]]:
    dependency_lookup: dict[str, list[dict]] = {}
    for dependency in dependencies:
        dependency_lookup.setdefault(dependency["topic"], []).append(dependency)
    return dependency_lookup


def compute_dependency_closure(root_slug: str, dependency_lookup: dict[str, list[dict]]) -> list[dict]:
    queue: deque[tuple[str, list[str], list[str]]] = deque([(root_slug, [root_slug], [])])
    best_depth_by_slug: dict[str, int] = {}
    resolved: list[dict] = []

    while queue:
        current_slug, path, chain = queue.popleft()
        for dependency in dependency_lookup.get(current_slug, []):
            dependency_slug = dependency["depends_on"]
            dependency_path = path + [dependency_slug]
            dependency_chain = chain + [dependency["dependency_kind"]]
            depth = len(dependency_path) - 1

            if dependency_slug in best_depth_by_slug and best_depth_by_slug[dependency_slug] <= depth:
                continue

            best_depth_by_slug[dependency_slug] = depth
            resolved.append(
                {
                    "topic": dependency_slug,
                    "depth": depth,
                    "path": dependency_path,
                    "chain": dependency_chain,
                    "rationale": dependency.get("rationale"),
                }
            )
            queue.append((dependency_slug, dependency_path, dependency_chain))

    return resolved


def sync_trade_model_topic_requirements(
    connection: sqlite3.Connection,
    trade_model_topics: list[dict],
    topic_id_by_slug: dict[str, int],
    trade_model_id_by_slug: dict[str, int],
    dependency_lookup: dict[str, list[dict]],
) -> int:
    connection.execute("DELETE FROM trade_model_topic_requirements")
    requirement_count = 0

    for mapping in trade_model_topics:
        trade_model_id = trade_model_id_by_slug[mapping["trade_model"]]
        root_topic_id = topic_id_by_slug[mapping["topic"]]
        relation_role = mapping["role"]
        notes = mapping.get("notes")

        connection.execute(
            """
            INSERT INTO trade_model_topic_requirements (
                trade_model_id,
                topic_id,
                introduced_by_topic_id,
                requirement_type,
                relation_role,
                dependency_depth,
                dependency_path,
                dependency_chain,
                notes
            ) VALUES (?, ?, ?, 'direct', ?, 0, ?, ?, ?)
            """,
            (
                trade_model_id,
                root_topic_id,
                root_topic_id,
                relation_role,
                json.dumps([mapping["topic"]]),
                json.dumps([]),
                notes,
            ),
        )
        requirement_count += 1

        for dependency in compute_dependency_closure(mapping["topic"], dependency_lookup):
            connection.execute(
                """
                INSERT INTO trade_model_topic_requirements (
                    trade_model_id,
                    topic_id,
                    introduced_by_topic_id,
                    requirement_type,
                    relation_role,
                    dependency_depth,
                    dependency_path,
                    dependency_chain,
                    notes
                ) VALUES (?, ?, ?, 'dependency', ?, ?, ?, ?, ?)
                """,
                (
                    trade_model_id,
                    topic_id_by_slug[dependency["topic"]],
                    root_topic_id,
                    relation_role,
                    dependency["depth"],
                    json.dumps(dependency["path"]),
                    json.dumps(dependency["chain"]),
                    dependency["rationale"],
                ),
            )
            requirement_count += 1

    return requirement_count


def infer_source_framework_slugs(canonical_url: str, author: str | None) -> list[str]:
    normalized_url = canonical_url.lower()
    normalized_author = (author or "").lower()
    frameworks: list[str] = []

    if "ttrades.com" in normalized_url or normalized_author == "ttrades":
        frameworks.append("ttrades_curriculum")
    if "tradingview.com/pine-script-docs" in normalized_url or normalized_author == "tradingview":
        frameworks.append("tradingview_reference")

    return frameworks


def backfill_source_frameworks(connection: sqlite3.Connection, framework_id_by_slug: dict[str, int]) -> int:
    connection.execute("DELETE FROM source_frameworks WHERE relation_type = 'primary'")
    link_count = 0
    rows = connection.execute("SELECT id, canonical_url, author FROM sources").fetchall()
    for source_id, canonical_url, author in rows:
        for framework_slug in infer_source_framework_slugs(canonical_url, author):
            framework_id = framework_id_by_slug.get(framework_slug)
            if framework_id is None:
                continue
            connection.execute(
                """
                INSERT INTO source_frameworks (
                    source_id, framework_id, relation_type, confidence, notes, updated_at
                ) VALUES (?, ?, 'primary', 1.0, ?, CURRENT_TIMESTAMP)
                """,
                (source_id, framework_id, "Inferred from source domain and author metadata."),
            )
            link_count += 1
    return link_count


def build_framework_term_index(items: list[dict], item_key: str) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for item in items:
        if item.get("term_kind") == "canonical":
            continue
        framework_slug = item["framework"]
        index.setdefault(framework_slug, []).append(
            {
                "entity_slug": item[item_key],
                "term": item["term"],
                "term_normalized": normalize_key(item["term"]),
                "term_kind": item.get("term_kind", "native"),
            }
        )
    return index


def source_search_text(title: str, canonical_url: str, summary: str | None) -> str:
    return normalize_key(" ".join(part for part in [title, canonical_url, summary or ""] if part))


def contains_normalized_term(searchable: str, normalized_term: str) -> bool:
    if not searchable or not normalized_term:
        return False
    pattern = rf"(^|_){re.escape(normalized_term)}(_|$)"
    return re.search(pattern, searchable) is not None


def backfill_source_links(
    connection: sqlite3.Connection,
    topic_lookup: dict[str, int],
    trade_model_lookup: dict[str, int],
    framework_topic_term_index: dict[str, list[dict]],
    framework_trade_model_term_index: dict[str, list[dict]],
) -> tuple[int, int, int, int]:
    connection.execute("DELETE FROM source_topics WHERE relation_type IN ('primary_hint', 'framework_term')")
    connection.execute("DELETE FROM source_trade_models WHERE relation_type IN ('primary_hint', 'framework_term')")

    topic_links = 0
    trade_model_links = 0
    topic_term_links = 0
    trade_model_term_links = 0

    rows = connection.execute(
        """
        SELECT s.id, s.title, s.canonical_url, s.summary, s.topic_hint, f.slug
        FROM sources s
        LEFT JOIN source_frameworks sf
          ON sf.source_id = s.id
         AND sf.relation_type = 'primary'
        LEFT JOIN frameworks f
          ON f.id = sf.framework_id
        ORDER BY s.id
        """
    ).fetchall()

    frameworks_by_source: dict[int, set[str]] = {}
    source_rows: dict[int, tuple[str, str, str | None, str | None]] = {}
    for source_id, title, canonical_url, summary, topic_hint, framework_slug in rows:
        source_rows[source_id] = (title, canonical_url, summary, topic_hint)
        if framework_slug:
            frameworks_by_source.setdefault(source_id, set()).add(framework_slug)

    for source_id, (title, canonical_url, summary, topic_hint) in source_rows.items():
        if topic_hint:
            key = normalize_key(topic_hint)
            if key in topic_lookup:
                connection.execute(
                    """
                    INSERT INTO source_topics (
                        source_id, topic_id, relation_type, confidence, notes, updated_at
                    ) VALUES (?, ?, 'primary_hint', 1.0, ?, CURRENT_TIMESTAMP)
                    """,
                    (source_id, topic_lookup[key], "Derived from sources.topic_hint during graph sync."),
                )
                topic_links += 1
            if key in trade_model_lookup:
                connection.execute(
                    """
                    INSERT INTO source_trade_models (
                        source_id, trade_model_id, relation_type, confidence, notes, updated_at
                    ) VALUES (?, ?, 'primary_hint', 1.0, ?, CURRENT_TIMESTAMP)
                    """,
                    (source_id, trade_model_lookup[key], "Derived from sources.topic_hint during graph sync."),
                )
                trade_model_links += 1

        searchable = source_search_text(title, canonical_url, summary)
        for framework_slug in sorted(frameworks_by_source.get(source_id, set())):
            for term in framework_topic_term_index.get(framework_slug, []):
                if contains_normalized_term(searchable, term["term_normalized"]):
                    topic_id = topic_lookup[normalize_key(term["entity_slug"])]
                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO source_topics (
                            source_id, topic_id, relation_type, confidence, notes, updated_at
                        ) VALUES (?, ?, 'framework_term', 0.7, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            source_id,
                            topic_id,
                            f"Matched framework-scoped topic term '{term['term']}' from framework '{framework_slug}'.",
                        ),
                    )
                    topic_term_links += cursor.rowcount
            for term in framework_trade_model_term_index.get(framework_slug, []):
                if contains_normalized_term(searchable, term["term_normalized"]):
                    trade_model_id = trade_model_lookup[normalize_key(term["entity_slug"])]
                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO source_trade_models (
                            source_id, trade_model_id, relation_type, confidence, notes, updated_at
                        ) VALUES (?, ?, 'framework_term', 0.7, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            source_id,
                            trade_model_id,
                            f"Matched framework-scoped trade-model term '{term['term']}' from framework '{framework_slug}'.",
                        ),
                    )
                    trade_model_term_links += cursor.rowcount

    return topic_links, trade_model_links, topic_term_links, trade_model_term_links


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync topic and trade-model dependency graph into SQLite.")
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH_PATH))
    args = parser.parse_args()

    graph = load_graph(Path(args.graph))
    frameworks = graph.get("frameworks", [])
    topics = graph.get("topics", [])
    dependencies = graph.get("dependencies", [])
    trade_models = graph.get("trade_models", [])
    framework_topic_terms = graph.get("framework_topic_terms", [])
    framework_trade_model_terms = graph.get("framework_trade_model_terms", [])
    trade_model_topics = graph.get("trade_model_topics", [])
    trader_profiles = graph.get("trader_profiles", [])
    trader_profile_frameworks = graph.get("trader_profile_frameworks", [])
    trader_profile_trade_models = graph.get("trader_profile_trade_models", [])
    trader_profile_topics = graph.get("trader_profile_topics", [])
    manage_trader_profiles = "trader_profiles" in graph

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        ensure_trader_profile_status_column(connection)

        archive_missing_entities(connection, "frameworks", [framework["slug"] for framework in frameworks])
        framework_id_by_slug: dict[str, int] = {}
        for framework in frameworks:
            framework_id_by_slug[framework["slug"]] = upsert_framework(connection, framework)

        archive_missing_entities(connection, "research_topics", [topic["slug"] for topic in topics])
        topic_id_by_slug: dict[str, int] = {}
        for topic in topics:
            topic_id_by_slug[topic["slug"]] = upsert_topic(connection, topic)
        topic_alias_count = sync_topic_aliases(connection, topics, topic_id_by_slug)

        connection.execute("DELETE FROM topic_dependencies")
        for dependency in dependencies:
            connection.execute(
                """
                INSERT INTO topic_dependencies (topic_id, dependency_topic_id, dependency_kind, rationale)
                VALUES (?, ?, ?, ?)
                """,
                (
                    topic_id_by_slug[dependency["topic"]],
                    topic_id_by_slug[dependency["depends_on"]],
                    dependency["dependency_kind"],
                    dependency.get("rationale"),
                ),
            )

        archive_missing_entities(connection, "trade_models", [model["slug"] for model in trade_models])
        trade_model_id_by_slug: dict[str, int] = {}
        for model in trade_models:
            trade_model_id_by_slug[model["slug"]] = upsert_trade_model(connection, model)
        trade_model_alias_count = sync_trade_model_aliases(connection, trade_models, trade_model_id_by_slug)

        framework_topic_term_count = sync_framework_topic_terms(
            connection,
            framework_topic_terms,
            framework_id_by_slug,
            topic_id_by_slug,
        )
        framework_trade_model_term_count = sync_framework_trade_model_terms(
            connection,
            framework_trade_model_terms,
            framework_id_by_slug,
            trade_model_id_by_slug,
        )

        connection.execute("DELETE FROM trade_model_topics")
        for mapping in trade_model_topics:
            connection.execute(
                """
                INSERT INTO trade_model_topics (trade_model_id, topic_id, role, priority, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    trade_model_id_by_slug[mapping["trade_model"]],
                    topic_id_by_slug[mapping["topic"]],
                    mapping["role"],
                    mapping.get("priority", 2),
                    mapping.get("notes"),
                ),
            )

        dependency_lookup = build_dependency_lookup(dependencies)
        requirement_count = sync_trade_model_topic_requirements(
            connection,
            trade_model_topics,
            topic_id_by_slug,
            trade_model_id_by_slug,
            dependency_lookup,
        )

        trader_profile_count = 0
        trader_profile_framework_count = 0
        trader_profile_trade_model_count = 0
        trader_profile_topic_count = 0
        if manage_trader_profiles:
            archive_missing_entities(connection, "trader_profiles", [profile["slug"] for profile in trader_profiles])
            trader_profile_id_by_slug: dict[str, int] = {}
            for profile in trader_profiles:
                trader_profile_id_by_slug[profile["slug"]] = upsert_trader_profile(connection, profile)
            trader_profile_count = len(trader_profiles)
            trader_profile_framework_count = sync_trader_profile_frameworks(
                connection,
                trader_profile_frameworks,
                trader_profile_id_by_slug,
                framework_id_by_slug,
            )
            trader_profile_trade_model_count = sync_trader_profile_trade_models(
                connection,
                trader_profile_trade_models,
                trader_profile_id_by_slug,
                trade_model_id_by_slug,
            )
            trader_profile_topic_count = sync_trader_profile_topics(
                connection,
                trader_profile_topics,
                trader_profile_id_by_slug,
                topic_id_by_slug,
            )

        source_framework_links = backfill_source_frameworks(connection, framework_id_by_slug)
        topic_lookup = build_lookup(topics, topic_id_by_slug)
        trade_model_lookup = build_lookup(trade_models, trade_model_id_by_slug)
        framework_topic_term_index = build_framework_term_index(framework_topic_terms, "topic")
        framework_trade_model_term_index = build_framework_term_index(framework_trade_model_terms, "trade_model")
        (
            source_topic_primary_links,
            source_trade_model_primary_links,
            source_topic_framework_term_links,
            source_trade_model_framework_term_links,
        ) = backfill_source_links(
            connection,
            topic_lookup,
            trade_model_lookup,
            framework_topic_term_index,
            framework_trade_model_term_index,
        )

        connection.commit()

    print(
        json.dumps(
            {
                "frameworks": len(frameworks),
                "topics": len(topics),
                "topic_aliases": topic_alias_count,
                "dependencies": len(dependencies),
                "trade_models": len(trade_models),
                "trade_model_aliases": trade_model_alias_count,
                "framework_topic_terms": framework_topic_term_count,
                "framework_trade_model_terms": framework_trade_model_term_count,
                "trade_model_topics": len(trade_model_topics),
                "trade_model_topic_requirements": requirement_count,
                "trader_profiles": trader_profile_count,
                "trader_profile_frameworks": trader_profile_framework_count,
                "trader_profile_trade_models": trader_profile_trade_model_count,
                "trader_profile_topics": trader_profile_topic_count,
                "source_framework_primary_links": source_framework_links,
                "source_topic_primary_links": source_topic_primary_links,
                "source_trade_model_primary_links": source_trade_model_primary_links,
                "source_topic_framework_term_links": source_topic_framework_term_links,
                "source_trade_model_framework_term_links": source_trade_model_framework_term_links,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
