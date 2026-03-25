from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from evaluate_rulebook import score_determinism, score_pine_translatability


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
TOPICS_DIR = ROOT / "topics"


def load_rulebook(topic: str) -> dict:
    path = TOPICS_DIR / topic / "rulebook.json"
    if not path.exists():
        raise FileNotFoundError(f"Rulebook not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def infer_source_type(url: str) -> str:
    if "tradingview.com" in url:
        return "doc"
    if "youtube.com" in url or "youtu.be" in url:
        return "video"
    return "article"


def ensure_source(connection: sqlite3.Connection, source: dict) -> int:
    row = connection.execute(
        "SELECT id FROM sources WHERE canonical_url = ?",
        (source["url"],),
    ).fetchone()
    if row:
        return int(row[0])

    connection.execute(
        """
        INSERT INTO sources (slug, source_type, title, canonical_url, topic_hint, summary)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            source["id"],
            infer_source_type(source["url"]),
            source["id"].replace("_", " ").title(),
            source["url"],
            None,
            f"Auto-registered from topic rulebook '{source['id']}'.",
        ),
    )
    return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])


def upsert_rule(connection: sqlite3.Connection, topic: str, rule: dict) -> int:
    rule_key = f"{topic}.{rule['id']}"
    connection.execute(
        """
        INSERT INTO rules (
            topic_slug,
            rule_key,
            rule_name,
            rule_json,
            determinism_score,
            pine_translatability_score,
            ambiguity_count,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(rule_key) DO UPDATE SET
            topic_slug = excluded.topic_slug,
            rule_name = excluded.rule_name,
            rule_json = excluded.rule_json,
            determinism_score = excluded.determinism_score,
            pine_translatability_score = excluded.pine_translatability_score,
            ambiguity_count = excluded.ambiguity_count,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            topic,
            rule_key,
            rule["name"],
            json.dumps(rule, indent=2, sort_keys=True),
            round(score_determinism([rule]), 4),
            round(score_pine_translatability([rule]), 4),
            len(rule.get("ambiguityNotes", [])),
        ),
    )
    row = connection.execute(
        "SELECT id FROM rules WHERE rule_key = ?",
        (rule_key,),
    ).fetchone()
    return int(row[0])


def sync_topic(topic: str) -> dict:
    rulebook = load_rulebook(topic)
    source_entries = rulebook.get("sources", [])
    rules = rulebook.get("rules", [])
    source_id_by_rulebook_id: dict[str, int] = {}
    evidence_rows = 0

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")

        for source in source_entries:
            source_id_by_rulebook_id[source["id"]] = ensure_source(connection, source)

        for rule in rules:
            rule_id = upsert_rule(connection, topic, rule)
            connection.execute("DELETE FROM rule_evidence WHERE rule_id = ?", (rule_id,))

            for evidence_ref in rule.get("evidenceRefs", []):
                source_key = evidence_ref.split("#", 1)[0]
                source_id = source_id_by_rulebook_id.get(source_key)
                if source_id is None:
                    continue
                connection.execute(
                    """
                    INSERT INTO rule_evidence (rule_id, source_id, evidence_ref)
                    VALUES (?, ?, ?)
                    """,
                    (rule_id, source_id, evidence_ref),
                )
                evidence_rows += 1

        connection.commit()

    return {
        "topic": topic,
        "source_count": len(source_entries),
        "rule_count": len(rules),
        "rule_evidence_count": evidence_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync a topic rulebook into SQLite tables.")
    parser.add_argument("--topic", required=True, help="Topic folder name under topics/")
    args = parser.parse_args()

    summary = sync_topic(args.topic)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
