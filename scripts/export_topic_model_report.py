from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_OUTPUT = ROOT / "results" / "topic_model_report.json"


def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_framework_entries(connection: sqlite3.Connection) -> list[dict]:
    frameworks = rows_to_dicts(
        connection.execute(
            """
            SELECT id, slug, name, framework_type, style_family, status, description, notes
            FROM frameworks
            WHERE status <> 'archived'
            ORDER BY slug
            """
        )
    )

    framework_entries: list[dict] = []
    for framework in frameworks:
        source_count = int(
            connection.execute(
                "SELECT COUNT(DISTINCT source_id) FROM source_frameworks WHERE framework_id = ?",
                (framework["id"],),
            ).fetchone()[0]
        )
        topic_terms = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  rt.slug AS topic,
                  rt.name AS topic_name,
                  ftt.term,
                  ftt.term_kind,
                  ftt.notes
                FROM framework_topic_terms ftt
                JOIN research_topics rt
                  ON rt.id = ftt.topic_id
                WHERE ftt.framework_id = ?
                ORDER BY rt.slug, ftt.term
                """,
                (framework["id"],),
            )
        )
        trade_model_terms = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  tm.slug AS trade_model,
                  tm.name AS trade_model_name,
                  ftmt.term,
                  ftmt.term_kind,
                  ftmt.notes
                FROM framework_trade_model_terms ftmt
                JOIN trade_models tm
                  ON tm.id = ftmt.trade_model_id
                WHERE ftmt.framework_id = ?
                ORDER BY tm.slug, ftmt.term
                """,
                (framework["id"],),
            )
        )

        framework_entries.append(
            {
                "slug": framework["slug"],
                "name": framework["name"],
                "framework_type": framework["framework_type"],
                "style_family": framework["style_family"],
                "status": framework["status"],
                "description": framework["description"],
                "notes": framework["notes"],
                "source_count": source_count,
                "topic_terms": topic_terms,
                "trade_model_terms": trade_model_terms,
            }
        )

    return framework_entries


def build_topic_entries(connection: sqlite3.Connection) -> list[dict]:
    topics = rows_to_dicts(
        connection.execute(
            """
            SELECT id, slug, name, topic_type, status, description
            FROM research_topics
            WHERE status <> 'archived'
            ORDER BY slug
            """
        )
    )

    topic_entries: list[dict] = []
    for topic in topics:
        dependencies = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  dep.slug AS depends_on,
                  dep.name AS depends_on_name,
                  td.dependency_kind,
                  td.rationale
                FROM topic_dependencies td
                JOIN research_topics dep
                  ON dep.id = td.dependency_topic_id
                WHERE td.topic_id = ?
                ORDER BY dep.slug
                """,
                (topic["id"],),
            )
        )
        trade_models = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  tm.slug AS trade_model,
                  tm.name AS trade_model_name,
                  tmt.role,
                  tmt.priority
                FROM trade_model_topics tmt
                JOIN trade_models tm
                  ON tm.id = tmt.trade_model_id
                WHERE tmt.topic_id = ?
                ORDER BY tmt.priority, tm.slug
                """,
                (topic["id"],),
            )
        )
        source_count = int(
            connection.execute(
                "SELECT COUNT(DISTINCT source_id) FROM source_topics WHERE topic_id = ?",
                (topic["id"],),
            ).fetchone()[0]
        )

        topic_entries.append(
            {
                "slug": topic["slug"],
                "name": topic["name"],
                "topic_type": topic["topic_type"],
                "status": topic["status"],
                "description": topic["description"],
                "source_count": source_count,
                "dependencies": dependencies,
                "trade_models": trade_models,
            }
        )

    return topic_entries


def build_trade_model_entries(connection: sqlite3.Connection) -> list[dict]:
    trade_models = rows_to_dicts(
        connection.execute(
            """
            SELECT id, slug, name, model_type, status, description
            FROM trade_models
            WHERE status <> 'archived'
            ORDER BY slug
            """
        )
    )

    model_entries: list[dict] = []
    for trade_model in trade_models:
        direct_topics = rows_to_dicts(
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
                (trade_model["id"],),
            )
        )
        requirement_rows = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  rt.slug AS topic,
                  rt.name AS topic_name,
                  intro.slug AS introduced_by_topic,
                  tmtr.requirement_type,
                  tmtr.relation_role,
                  tmtr.dependency_depth,
                  tmtr.dependency_path,
                  tmtr.dependency_chain,
                  tmtr.notes
                FROM trade_model_topic_requirements tmtr
                JOIN research_topics rt
                  ON rt.id = tmtr.topic_id
                JOIN research_topics intro
                  ON intro.id = tmtr.introduced_by_topic_id
                WHERE tmtr.trade_model_id = ?
                ORDER BY tmtr.dependency_depth, rt.slug, intro.slug
                """,
                (trade_model["id"],),
            )
        )

        requirements_by_topic: dict[str, dict] = {}
        for row in requirement_rows:
            entry = requirements_by_topic.setdefault(
                row["topic"],
                {
                    "topic": row["topic"],
                    "topic_name": row["topic_name"],
                    "direct": False,
                    "minimum_depth": row["dependency_depth"],
                    "requirement_types": set(),
                    "relation_roles": set(),
                    "introduced_by_topics": set(),
                    "dependency_paths": [],
                    "notes": set(),
                },
            )
            entry["direct"] = entry["direct"] or row["requirement_type"] == "direct"
            entry["minimum_depth"] = min(entry["minimum_depth"], row["dependency_depth"])
            entry["requirement_types"].add(row["requirement_type"])
            if row["relation_role"]:
                entry["relation_roles"].add(row["relation_role"])
            entry["introduced_by_topics"].add(row["introduced_by_topic"])
            if len(entry["dependency_paths"]) < 3:
                entry["dependency_paths"].append(
                    {
                        "path": json.loads(row["dependency_path"]),
                        "chain": json.loads(row["dependency_chain"] or "[]"),
                    }
                )
            if row["notes"]:
                entry["notes"].add(row["notes"])

        direct_source_count = int(
            connection.execute(
                "SELECT COUNT(DISTINCT source_id) FROM source_trade_models WHERE trade_model_id = ?",
                (trade_model["id"],),
            ).fetchone()[0]
        )
        dependency_source_count = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT st.source_id)
                FROM source_topics st
                JOIN trade_model_topic_requirements tmtr
                  ON tmtr.topic_id = st.topic_id
                WHERE tmtr.trade_model_id = ?
                """,
                (trade_model["id"],),
            ).fetchone()[0]
        )

        resolved_requirements = [
            {
                "topic": entry["topic"],
                "topic_name": entry["topic_name"],
                "direct": entry["direct"],
                "minimum_depth": entry["minimum_depth"],
                "requirement_types": sorted(entry["requirement_types"]),
                "relation_roles": sorted(entry["relation_roles"]),
                "introduced_by_topics": sorted(entry["introduced_by_topics"]),
                "dependency_paths": entry["dependency_paths"],
                "notes": sorted(entry["notes"]),
            }
            for entry in sorted(requirements_by_topic.values(), key=lambda item: (item["minimum_depth"], item["topic"]))
        ]

        model_entries.append(
            {
                "slug": trade_model["slug"],
                "name": trade_model["name"],
                "model_type": trade_model["model_type"],
                "status": trade_model["status"],
                "description": trade_model["description"],
                "direct_topic_count": len(direct_topics),
                "resolved_topic_count": len(resolved_requirements),
                "source_counts": {
                    "direct_model_sources": direct_source_count,
                    "topic_coverage_sources": dependency_source_count,
                },
                "direct_topics": direct_topics,
                "resolved_requirements": resolved_requirements,
            }
        )

    return model_entries


def build_trader_profile_entries(connection: sqlite3.Connection) -> list[dict]:
    trader_profiles = rows_to_dicts(
        connection.execute(
            """
            SELECT id, slug, display_name, profile_type, status, notes, style_json
            FROM trader_profiles
            WHERE status <> 'archived'
            ORDER BY slug
            """
        )
    )

    profile_entries: list[dict] = []
    for profile in trader_profiles:
        frameworks = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  f.slug AS framework,
                  f.name AS framework_name,
                  tpf.relation_type,
                  tpf.confidence,
                  tpf.notes
                FROM trader_profile_frameworks tpf
                JOIN frameworks f
                  ON f.id = tpf.framework_id
                WHERE tpf.trader_profile_id = ?
                ORDER BY f.slug
                """,
                (profile["id"],),
            )
        )
        trade_models = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  tm.slug AS trade_model,
                  tm.name AS trade_model_name,
                  tptm.role,
                  tptm.priority,
                  tptm.indicator_ready,
                  tptm.notes
                FROM trader_profile_trade_models tptm
                JOIN trade_models tm
                  ON tm.id = tptm.trade_model_id
                WHERE tptm.trader_profile_id = ?
                ORDER BY tptm.priority, tm.slug
                """,
                (profile["id"],),
            )
        )
        topics = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  rt.slug AS topic,
                  rt.name AS topic_name,
                  tpt.emphasis,
                  tpt.priority,
                  tpt.notes
                FROM trader_profile_topics tpt
                JOIN research_topics rt
                  ON rt.id = tpt.topic_id
                WHERE tpt.trader_profile_id = ?
                ORDER BY tpt.priority, rt.slug
                """,
                (profile["id"],),
            )
        )
        annotation_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM trader_annotations WHERE trader_profile_id = ?",
                (profile["id"],),
            ).fetchone()[0]
        )
        annotated_trade_model_count = int(
            connection.execute(
                """
                SELECT COUNT(DISTINCT tatm.trade_model_id)
                FROM trader_annotation_trade_models tatm
                JOIN trader_annotations ta
                  ON ta.id = tatm.trader_annotation_id
                WHERE ta.trader_profile_id = ?
                """,
                (profile["id"],),
            ).fetchone()[0]
        )

        for trade_model in trade_models:
            trade_model["indicator_ready"] = bool(trade_model["indicator_ready"])

        profile_entries.append(
            {
                "slug": profile["slug"],
                "display_name": profile["display_name"],
                "profile_type": profile["profile_type"],
                "status": profile["status"],
                "notes": profile["notes"],
                "style": json.loads(profile["style_json"]) if profile["style_json"] else None,
                "annotation_count": annotation_count,
                "annotated_trade_model_count": annotated_trade_model_count,
                "frameworks": frameworks,
                "trade_models": trade_models,
                "topics": topics,
            }
        )

    return profile_entries


def build_indicator_spec_entries(connection: sqlite3.Connection) -> list[dict]:
    rows = rows_to_dicts(
        connection.execute(
            """
            SELECT spec_key, topic_slug, name, target_language, status, spec_json
            FROM indicator_specs
            ORDER BY spec_key
            """
        )
    )

    entries: list[dict] = []
    for row in rows:
        spec = json.loads(row["spec_json"])
        trader_profile = spec.get("trader_profile", {})
        trade_model = spec.get("trade_model", {})
        entries.append(
            {
                "spec_key": row["spec_key"],
                "topic": row["topic_slug"],
                "name": row["name"],
                "target_language": row["target_language"],
                "status": row["status"],
                "profile_slug": trader_profile.get("slug"),
                "trade_model_slug": trade_model.get("slug"),
                "spec_version": spec.get("spec_version"),
                "translation_stage": spec.get("translation_stage"),
                "artifact_path": spec.get("artifact_path"),
                "implementation_summary": spec.get("implementation_summary"),
                "open_implementation_question_count": len(spec.get("open_implementation_questions", [])),
                "implementation_scope": spec.get("implementation_scope"),
                "direct_topics": spec.get("direct_topics", []),
                "resolved_requirements": spec.get("resolved_requirements", []),
            }
        )

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a topic/model dependency and coverage report from SQLite.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "frameworks": build_framework_entries(connection),
            "topics": build_topic_entries(connection),
            "trade_models": build_trade_model_entries(connection),
            "trader_profiles": build_trader_profile_entries(connection),
            "indicator_specs": build_indicator_spec_entries(connection),
        }

    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "framework_count": len(report["frameworks"]),
                "topic_count": len(report["topics"]),
                "trade_model_count": len(report["trade_models"]),
                "trader_profile_count": len(report["trader_profiles"]),
                "indicator_spec_count": len(report["indicator_specs"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
