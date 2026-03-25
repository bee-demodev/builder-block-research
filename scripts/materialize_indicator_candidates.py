from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"


def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def load_candidate_rows(connection: sqlite3.Connection, profile_slug: str | None) -> list[dict]:
    filters = ["tptm.indicator_ready = 1", "tp.status <> 'archived'", "tm.status <> 'archived'"]
    params: list[str] = []
    if profile_slug:
        filters.append("tp.slug = ?")
        params.append(profile_slug)

    where_clause = " AND ".join(filters)
    return rows_to_dicts(
        connection.execute(
            f"""
            SELECT
              tp.id AS profile_id,
              tp.slug AS profile_slug,
              tp.display_name AS profile_name,
              tp.profile_type,
              tp.style_json,
              tm.id AS trade_model_id,
              tm.slug AS trade_model_slug,
              tm.name AS trade_model_name,
              tm.model_type,
              tptm.role,
              tptm.priority,
              tptm.notes AS profile_trade_model_notes
            FROM trader_profile_trade_models tptm
            JOIN trader_profiles tp
              ON tp.id = tptm.trader_profile_id
            JOIN trade_models tm
              ON tm.id = tptm.trade_model_id
            WHERE {where_clause}
            ORDER BY tp.slug, tptm.priority, tm.slug
            """,
            params,
        )
    )


def load_direct_topics(connection: sqlite3.Connection, trade_model_id: int) -> list[dict]:
    return rows_to_dicts(
        connection.execute(
            """
            SELECT
              rt.slug AS topic,
              rt.name AS topic_name,
              tmt.role,
              tmt.priority,
              tmt.notes
            FROM trade_model_topics tmt
            JOIN research_topics rt
              ON rt.id = tmt.topic_id
            WHERE tmt.trade_model_id = ?
            ORDER BY tmt.priority, rt.slug
            """,
            (trade_model_id,),
        )
    )


def load_resolved_requirements(connection: sqlite3.Connection, trade_model_id: int) -> list[dict]:
    rows = rows_to_dicts(
        connection.execute(
            """
            SELECT
              rt.slug AS topic,
              rt.name AS topic_name,
              intro.slug AS introduced_by_topic,
              tmtr.requirement_type,
              tmtr.relation_role,
              tmtr.dependency_depth
            FROM trade_model_topic_requirements tmtr
            JOIN research_topics rt
              ON rt.id = tmtr.topic_id
            JOIN research_topics intro
              ON intro.id = tmtr.introduced_by_topic_id
            WHERE tmtr.trade_model_id = ?
            ORDER BY tmtr.dependency_depth, rt.slug, intro.slug
            """,
            (trade_model_id,),
        )
    )

    requirements_by_topic: dict[str, dict] = {}
    for row in rows:
        entry = requirements_by_topic.setdefault(
            row["topic"],
            {
                "topic": row["topic"],
                "topic_name": row["topic_name"],
                "minimum_depth": row["dependency_depth"],
                "direct": False,
                "requirement_types": set(),
                "relation_roles": set(),
                "introduced_by_topics": set(),
            },
        )
        entry["minimum_depth"] = min(entry["minimum_depth"], row["dependency_depth"])
        entry["direct"] = entry["direct"] or row["requirement_type"] == "direct"
        entry["requirement_types"].add(row["requirement_type"])
        if row["relation_role"]:
            entry["relation_roles"].add(row["relation_role"])
        entry["introduced_by_topics"].add(row["introduced_by_topic"])

    return [
        {
            "topic": entry["topic"],
            "topic_name": entry["topic_name"],
            "minimum_depth": entry["minimum_depth"],
            "direct": entry["direct"],
            "requirement_types": sorted(entry["requirement_types"]),
            "relation_roles": sorted(entry["relation_roles"]),
            "introduced_by_topics": sorted(entry["introduced_by_topics"]),
        }
        for entry in sorted(requirements_by_topic.values(), key=lambda item: (item["minimum_depth"], item["topic"]))
    ]


def annotation_link_count(connection: sqlite3.Connection, profile_id: int, trade_model_id: int) -> int:
    return int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM trader_annotation_trade_models tatm
            JOIN trader_annotations ta
              ON ta.id = tatm.trader_annotation_id
            WHERE ta.trader_profile_id = ?
              AND tatm.trade_model_id = ?
            """,
            (profile_id, trade_model_id),
        ).fetchone()[0]
    )


def source_counts(connection: sqlite3.Connection, trade_model_id: int) -> dict:
    direct_model_sources = int(
        connection.execute(
            "SELECT COUNT(DISTINCT source_id) FROM source_trade_models WHERE trade_model_id = ?",
            (trade_model_id,),
        ).fetchone()[0]
    )
    topic_coverage_sources = int(
        connection.execute(
            """
            SELECT COUNT(DISTINCT st.source_id)
            FROM source_topics st
            JOIN trade_model_topic_requirements tmtr
              ON tmtr.topic_id = st.topic_id
            WHERE tmtr.trade_model_id = ?
            """,
            (trade_model_id,),
        ).fetchone()[0]
    )
    return {
        "direct_model_sources": direct_model_sources,
        "topic_coverage_sources": topic_coverage_sources,
    }


def primary_topic_slug(direct_topics: list[dict]) -> str:
    if not direct_topics:
        raise ValueError("Indicator candidate requires at least one direct topic.")

    core_topics = sorted(
        (topic for topic in direct_topics if topic.get("role") == "core"),
        key=lambda topic: (topic.get("priority", 999), str(topic["topic"])),
    )
    if core_topics:
        return str(core_topics[0]["topic"])

    return str(direct_topics[0]["topic"])


def candidate_name(profile_name: str, trade_model_name: str) -> str:
    return f"{profile_name} - {trade_model_name} Indicator Candidate"


def load_existing_spec(connection: sqlite3.Connection, spec_key: str) -> dict | None:
    row = connection.execute(
        """
        SELECT status, spec_json
        FROM indicator_specs
        WHERE spec_key = ?
        """,
        (spec_key,),
    ).fetchone()
    if row is None:
        return None
    return {
        "status": str(row[0]),
        "spec_json": json.loads(str(row[1])),
    }


def merge_candidate_spec(existing_spec: dict | None, candidate_spec: dict) -> dict:
    if existing_spec is None:
        return candidate_spec

    merged = dict(existing_spec)
    for key in [
        "candidate_type",
        "trader_profile",
        "trade_model",
        "direct_topics",
        "resolved_requirements",
        "pine_translation_hints",
    ]:
        merged[key] = candidate_spec.get(key)

    existing_scope = existing_spec.get("implementation_scope", {})
    candidate_scope = candidate_spec.get("implementation_scope", {})
    if isinstance(existing_scope, dict) and isinstance(candidate_scope, dict):
        merged_scope = dict(existing_scope)
        merged_scope.update(candidate_scope)
        merged["implementation_scope"] = merged_scope
    else:
        merged["implementation_scope"] = candidate_scope

    return merged


def build_spec_json(
    row: dict,
    direct_topics: list[dict],
    resolved_requirements: list[dict],
    annotation_count: int,
    coverage: dict,
) -> dict:
    return {
        "candidate_type": "teacher_style_trade_model",
        "trader_profile": {
            "slug": row["profile_slug"],
            "display_name": row["profile_name"],
            "profile_type": row["profile_type"],
            "style": json.loads(row["style_json"]) if row["style_json"] else None,
        },
        "trade_model": {
            "slug": row["trade_model_slug"],
            "name": row["trade_model_name"],
            "model_type": row["model_type"],
            "profile_role": row["role"],
            "profile_priority": row["priority"],
            "notes": row["profile_trade_model_notes"],
        },
        "implementation_scope": {
            "status_basis": "profile_trade_model_indicator_ready",
            "annotation_link_count": annotation_count,
            "source_counts": coverage,
            "target_language": "pine",
            "anti_repaint_baseline": "bar_close_confirmation",
        },
        "direct_topics": direct_topics,
        "resolved_requirements": resolved_requirements,
        "pine_translation_hints": [
            "Prefer bar-close confirmation over intrabar discretion.",
            "Keep lower-timeframe requests focused and finite.",
            "Represent structure and invalidation as explicit state objects.",
        ],
    }


def upsert_indicator_spec(
    connection: sqlite3.Connection,
    spec_key: str,
    topic_slug: str,
    name: str,
    status: str,
    spec_json: dict,
) -> None:
    connection.execute(
        """
        INSERT INTO indicator_specs (
            topic_slug, spec_key, name, target_language, status, spec_json, updated_at
        ) VALUES (?, ?, ?, 'pine', ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(spec_key) DO UPDATE SET
            topic_slug = excluded.topic_slug,
            name = excluded.name,
            target_language = excluded.target_language,
            status = excluded.status,
            spec_json = excluded.spec_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            topic_slug,
            spec_key,
            name,
            status,
            json.dumps(spec_json, sort_keys=True),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Materialize indicator candidates from indicator-ready teacher-style trade models."
    )
    parser.add_argument("--profile-slug")
    parser.add_argument("--status", default="candidate")
    args = parser.parse_args()

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        rows = load_candidate_rows(connection, args.profile_slug)
        spec_keys: list[str] = []
        for row in rows:
            direct_topics = load_direct_topics(connection, int(row["trade_model_id"]))
            resolved_requirements = load_resolved_requirements(connection, int(row["trade_model_id"]))
            spec_key = f"{row['profile_slug']}__{row['trade_model_slug']}"
            topic_slug = primary_topic_slug(direct_topics)
            candidate_spec = build_spec_json(
                row,
                direct_topics,
                resolved_requirements,
                annotation_link_count(connection, int(row["profile_id"]), int(row["trade_model_id"])),
                source_counts(connection, int(row["trade_model_id"])),
            )
            existing_spec = load_existing_spec(connection, spec_key)
            spec_json = merge_candidate_spec(
                existing_spec["spec_json"] if existing_spec else None,
                candidate_spec,
            )
            status = args.status
            if existing_spec and args.status == "candidate" and existing_spec["status"] != "candidate":
                status = existing_spec["status"]
            upsert_indicator_spec(
                connection,
                spec_key,
                topic_slug,
                candidate_name(str(row["profile_name"]), str(row["trade_model_name"])),
                status,
                spec_json,
            )
            spec_keys.append(spec_key)
        connection.commit()

    print(json.dumps({"materialized_specs": len(spec_keys), "spec_keys": spec_keys}, indent=2))


if __name__ == "__main__":
    main()
