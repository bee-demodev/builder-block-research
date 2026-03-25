from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"


def parse_json_payload(value: str) -> str:
    parsed = json.loads(value)
    return json.dumps(parsed, sort_keys=True)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def ensure_profile(connection: sqlite3.Connection, slug: str, display_name: str | None, profile_type: str) -> int:
    row = connection.execute(
        "SELECT id FROM trader_profiles WHERE slug = ?",
        (slug,),
    ).fetchone()
    if row:
        return int(row[0])

    connection.execute(
        """
        INSERT INTO trader_profiles (slug, display_name, profile_type, notes, style_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            slug,
            display_name or slug.replace("_", " ").title(),
            profile_type,
            "Auto-created while recording an annotation case.",
            json.dumps({"status": "draft_profile"}, sort_keys=True),
        ),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def resolve_source_id(connection: sqlite3.Connection, source_url: str | None) -> int | None:
    if not source_url:
        return None
    row = connection.execute(
        "SELECT id FROM sources WHERE canonical_url = ?",
        (source_url,),
    ).fetchone()
    return int(row[0]) if row else None


def build_trade_model_lookup(connection: sqlite3.Connection) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for trade_model_id, slug in connection.execute("SELECT id, slug FROM trade_models"):
        lookup[normalize_key(slug)] = int(trade_model_id)
    for trade_model_id, alias in connection.execute("SELECT trade_model_id, alias FROM trade_model_aliases"):
        lookup[normalize_key(alias)] = int(trade_model_id)
    return lookup


def resolve_trade_model_ids(connection: sqlite3.Connection, trade_models: list[str]) -> list[int]:
    lookup = build_trade_model_lookup(connection)
    resolved_ids: list[int] = []
    missing: list[str] = []
    for trade_model in trade_models:
        trade_model_id = lookup.get(normalize_key(trade_model))
        if trade_model_id is None:
            missing.append(trade_model)
            continue
        if trade_model_id not in resolved_ids:
            resolved_ids.append(trade_model_id)
    if missing:
        raise SystemExit(f"Unknown trade model(s): {', '.join(missing)}")
    return resolved_ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a trader-specific chart annotation case in SQLite.")
    parser.add_argument("--profile-slug", required=True)
    parser.add_argument("--profile-name")
    parser.add_argument("--profile-type", default="trader")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--case-ref", required=True)
    parser.add_argument("--symbol")
    parser.add_argument("--timeframe")
    parser.add_argument("--source-url")
    parser.add_argument("--trade-model", action="append")
    parser.add_argument("--trade-model-relation-type", default="primary_execution_model")
    parser.add_argument("--trade-model-confidence", type=float, default=1.0)
    parser.add_argument("--chart-context-json", required=True)
    parser.add_argument("--annotation-json", required=True)
    parser.add_argument("--outcome-json")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    chart_context_json = parse_json_payload(args.chart_context_json)
    annotation_json = parse_json_payload(args.annotation_json)
    outcome_json = parse_json_payload(args.outcome_json) if args.outcome_json else None

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        trader_profile_id = ensure_profile(connection, args.profile_slug, args.profile_name, args.profile_type)
        source_id = resolve_source_id(connection, args.source_url)
        trade_model_ids = resolve_trade_model_ids(connection, args.trade_model or []) if args.trade_model else []
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
                args.topic,
                source_id,
                args.case_ref,
                args.symbol,
                args.timeframe,
                chart_context_json,
                annotation_json,
                outcome_json,
                args.notes.strip(),
            ),
        )
        annotation_id = int(
            connection.execute(
                "SELECT id FROM trader_annotations WHERE case_ref = ?",
                (args.case_ref,),
            ).fetchone()[0]
        )
        if args.trade_model is not None:
            connection.execute(
                "DELETE FROM trader_annotation_trade_models WHERE trader_annotation_id = ?",
                (annotation_id,),
            )
            for trade_model_id in trade_model_ids:
                connection.execute(
                    """
                    INSERT INTO trader_annotation_trade_models (
                        trader_annotation_id, trade_model_id, relation_type, confidence, notes, updated_at
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        annotation_id,
                        trade_model_id,
                        args.trade_model_relation_type,
                        args.trade_model_confidence,
                        "Linked during annotation capture.",
                    ),
                )
        connection.commit()

    print(
        json.dumps(
            {
                "profile_slug": args.profile_slug,
                "topic": args.topic,
                "case_ref": args.case_ref,
                "source_url": args.source_url,
                "trade_models": args.trade_model or [],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
