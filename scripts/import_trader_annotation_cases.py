from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from record_trader_annotation import (
    ensure_profile,
    parse_json_payload,
    resolve_source_id,
    resolve_trade_model_ids,
)


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_CASES_PATH = ROOT / "data" / "trader_annotation_cases.json"


def load_cases(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    return payload.get("cases", [])


def load_trade_model_links(connection: sqlite3.Connection, case: dict) -> list[dict]:
    explicit_links = case.get("trade_model_links", [])
    if explicit_links:
        resolved_links: list[dict] = []
        for link in explicit_links:
            trade_model = link["trade_model"]
            trade_model_id = resolve_trade_model_ids(connection, [trade_model])[0]
            resolved_links.append(
                {
                    "trade_model_id": trade_model_id,
                    "relation_type": link.get("relation_type", "primary_execution_model"),
                    "confidence": float(link.get("confidence", 1.0)),
                    "notes": link.get("notes", "").strip() or "Linked during annotation-case import.",
                }
            )
        return resolved_links

    legacy_trade_model_ids = resolve_trade_model_ids(connection, case.get("trade_models", []))
    return [
        {
            "trade_model_id": trade_model_id,
            "relation_type": case.get("trade_model_relation_type", "primary_execution_model"),
            "confidence": float(case.get("trade_model_confidence", 1.0)),
            "notes": "Linked during annotation-case import.",
        }
        for trade_model_id in legacy_trade_model_ids
    ]


def upsert_case(connection: sqlite3.Connection, case: dict) -> None:
    trader_profile_id = ensure_profile(
        connection,
        case["profile_slug"],
        case.get("profile_name"),
        case.get("profile_type", "trader"),
    )
    source_id = resolve_source_id(connection, case.get("source_url"))
    trade_model_links = load_trade_model_links(connection, case)

    chart_context_json = parse_json_payload(json.dumps(case["chart_context"]))
    annotation_json = parse_json_payload(json.dumps(case["annotation"]))
    outcome_json = parse_json_payload(json.dumps(case["outcome"])) if case.get("outcome") else None

    connection.execute(
        """
        INSERT INTO trader_annotations (
            trader_profile_id,
            topic_slug,
            source_id,
            case_ref,
            symbol,
            timeframe,
            chart_context_json,
            annotation_json,
            outcome_json,
            notes,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(case_ref) DO UPDATE SET
            trader_profile_id = excluded.trader_profile_id,
            topic_slug = excluded.topic_slug,
            source_id = excluded.source_id,
            symbol = excluded.symbol,
            timeframe = excluded.timeframe,
            chart_context_json = excluded.chart_context_json,
            annotation_json = excluded.annotation_json,
            outcome_json = excluded.outcome_json,
            notes = excluded.notes,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            trader_profile_id,
            case["topic"],
            source_id,
            case["case_ref"],
            case.get("symbol"),
            case.get("timeframe"),
            chart_context_json,
            annotation_json,
            outcome_json,
            case.get("notes", "").strip(),
        ),
    )

    annotation_id = int(
        connection.execute(
            "SELECT id FROM trader_annotations WHERE case_ref = ?",
            (case["case_ref"],),
        ).fetchone()[0]
    )
    connection.execute(
        "DELETE FROM trader_annotation_trade_models WHERE trader_annotation_id = ?",
        (annotation_id,),
    )
    for link in trade_model_links:
        connection.execute(
            """
            INSERT INTO trader_annotation_trade_models (
                trader_annotation_id, trade_model_id, relation_type, confidence, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                annotation_id,
                link["trade_model_id"],
                link["relation_type"],
                link["confidence"],
                link["notes"],
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import durable trader annotation cases from JSON into SQLite."
    )
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--profile-slug")
    parser.add_argument("--topic")
    args = parser.parse_args()

    cases = load_cases(Path(args.cases))
    if args.profile_slug:
        cases = [case for case in cases if case.get("profile_slug") == args.profile_slug]
    if args.topic:
        cases = [case for case in cases if case.get("topic") == args.topic]

    imported_refs: list[str] = []
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        for case in cases:
            upsert_case(connection, case)
            imported_refs.append(case["case_ref"])
        connection.commit()

    print(json.dumps({"imported_cases": len(imported_refs), "case_refs": imported_refs}, indent=2))


if __name__ == "__main__":
    main()
