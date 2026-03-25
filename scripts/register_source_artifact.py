from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"


def resolve_source_id(connection: sqlite3.Connection, source_ref: str) -> int:
    row = connection.execute(
        "SELECT id FROM sources WHERE canonical_url = ? OR slug = ?",
        (source_ref, source_ref),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown source reference: {source_ref}")
    return int(row[0])


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a local or remote artifact against a known source.")
    parser.add_argument("--source", required=True, help="Source canonical URL or slug")
    parser.add_argument("--artifact-type", required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        source_id = resolve_source_id(connection, args.source)
        connection.execute(
            """
            INSERT OR IGNORE INTO source_artifacts (source_id, artifact_type, path, notes)
            VALUES (?, ?, ?, ?)
            """,
            (source_id, args.artifact_type, args.path, args.notes.strip()),
        )
        connection.commit()

    print(
        json.dumps(
            {
                "source": args.source,
                "artifact_type": args.artifact_type,
                "path": args.path,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
