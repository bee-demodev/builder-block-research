from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_OUTPUT = ROOT / "results" / "trader_dataset.jsonl"


def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def load_profile_frameworks(connection: sqlite3.Connection) -> dict[int, list[dict]]:
    mapping: dict[int, list[dict]] = {}
    rows = rows_to_dicts(
        connection.execute(
            """
            SELECT
              tpf.trader_profile_id AS profile_id,
              f.slug AS framework,
              f.name AS framework_name,
              tpf.relation_type,
              tpf.confidence,
              tpf.notes
            FROM trader_profile_frameworks tpf
            JOIN frameworks f
              ON f.id = tpf.framework_id
            ORDER BY tpf.trader_profile_id, f.slug
            """
        )
    )
    for row in rows:
        mapping.setdefault(row["profile_id"], []).append(
            {
                "framework": row["framework"],
                "framework_name": row["framework_name"],
                "relation_type": row["relation_type"],
                "confidence": row["confidence"],
                "notes": row["notes"],
            }
        )
    return mapping


def load_profile_trade_models(connection: sqlite3.Connection) -> dict[int, list[dict]]:
    mapping: dict[int, list[dict]] = {}
    rows = rows_to_dicts(
        connection.execute(
            """
            SELECT
              tptm.trader_profile_id AS profile_id,
              tm.slug AS trade_model,
              tm.name AS trade_model_name,
              tptm.role,
              tptm.priority,
              tptm.indicator_ready,
              tptm.notes
            FROM trader_profile_trade_models tptm
            JOIN trade_models tm
              ON tm.id = tptm.trade_model_id
            ORDER BY tptm.trader_profile_id, tptm.priority, tm.slug
            """
        )
    )
    for row in rows:
        mapping.setdefault(row["profile_id"], []).append(
            {
                "trade_model": row["trade_model"],
                "trade_model_name": row["trade_model_name"],
                "role": row["role"],
                "priority": row["priority"],
                "indicator_ready": bool(row["indicator_ready"]),
                "notes": row["notes"],
            }
        )
    return mapping


def load_profile_topics(connection: sqlite3.Connection) -> dict[int, list[dict]]:
    mapping: dict[int, list[dict]] = {}
    rows = rows_to_dicts(
        connection.execute(
            """
            SELECT
              tpt.trader_profile_id AS profile_id,
              rt.slug AS topic,
              rt.name AS topic_name,
              tpt.emphasis,
              tpt.priority,
              tpt.notes
            FROM trader_profile_topics tpt
            JOIN research_topics rt
              ON rt.id = tpt.topic_id
            ORDER BY tpt.trader_profile_id, tpt.priority, rt.slug
            """
        )
    )
    for row in rows:
        mapping.setdefault(row["profile_id"], []).append(
            {
                "topic": row["topic"],
                "topic_name": row["topic_name"],
                "emphasis": row["emphasis"],
                "priority": row["priority"],
                "notes": row["notes"],
            }
        )
    return mapping


def load_annotation_trade_models(connection: sqlite3.Connection) -> dict[int, list[dict]]:
    mapping: dict[int, list[dict]] = {}
    rows = rows_to_dicts(
        connection.execute(
            """
            SELECT
              tatm.trader_annotation_id AS annotation_id,
              tm.slug AS trade_model,
              tm.name AS trade_model_name,
              tatm.relation_type,
              tatm.confidence,
              tatm.notes
            FROM trader_annotation_trade_models tatm
            JOIN trade_models tm
              ON tm.id = tatm.trade_model_id
            ORDER BY tatm.trader_annotation_id, tm.slug
            """
        )
    )
    for row in rows:
        mapping.setdefault(row["annotation_id"], []).append(
            {
                "trade_model": row["trade_model"],
                "trade_model_name": row["trade_model_name"],
                "relation_type": row["relation_type"],
                "confidence": row["confidence"],
                "notes": row["notes"],
            }
        )
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export trader annotations as JSONL for future embedding, retrieval, or model training."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--profile-slug")
    parser.add_argument("--topic")
    args = parser.parse_args()

    filters: list[str] = []
    params: list[str] = []
    if args.profile_slug:
        filters.append("tp.slug = ?")
        params.append(args.profile_slug)
    if args.topic:
        filters.append("ta.topic_slug = ?")
        params.append(args.topic)

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    query = f"""
        SELECT
            ta.id,
            tp.id,
            tp.slug,
            tp.display_name,
            tp.profile_type,
            tp.status,
            tp.style_json,
            ta.topic_slug,
            ta.case_ref,
            ta.symbol,
            ta.timeframe,
            ta.chart_context_json,
            ta.annotation_json,
            ta.outcome_json,
            ta.notes,
            s.canonical_url
        FROM trader_annotations ta
        JOIN trader_profiles tp ON tp.id = ta.trader_profile_id
        LEFT JOIN sources s ON s.id = ta.source_id
        {where_clause}
        ORDER BY tp.slug, ta.topic_slug, ta.case_ref
    """

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    with sqlite3.connect(DB_PATH) as connection, output_path.open("w", encoding="utf-8") as handle:
        profile_frameworks = load_profile_frameworks(connection)
        profile_trade_models = load_profile_trade_models(connection)
        profile_topics = load_profile_topics(connection)
        annotation_trade_models = load_annotation_trade_models(connection)

        for row in connection.execute(query, params):
            record = {
                "profile_slug": row[2],
                "profile_name": row[3],
                "profile_type": row[4],
                "profile_status": row[5],
                "profile_style": json.loads(row[6]) if row[6] else None,
                "profile_frameworks": profile_frameworks.get(row[1], []),
                "profile_trade_models": profile_trade_models.get(row[1], []),
                "profile_topics": profile_topics.get(row[1], []),
                "topic": row[7],
                "case_ref": row[8],
                "symbol": row[9],
                "timeframe": row[10],
                "chart_context": json.loads(row[11]),
                "annotation": json.loads(row[12]),
                "outcome": json.loads(row[13]) if row[13] else None,
                "notes": row[14],
                "source_url": row[15],
                "annotation_trade_models": annotation_trade_models.get(row[0], []),
            }
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            rows_written += 1

    print(json.dumps({"output": str(output_path), "rows_written": rows_written}, indent=2))


if __name__ == "__main__":
    main()
