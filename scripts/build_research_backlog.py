from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_OUTPUT = ROOT / "results" / "research_backlog.json"

TEXT_ARTIFACT_TYPES = ("page_markdown", "markdown_extract", "manual_notes", "transcript")


def rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a JSON backlog of sources missing key research artifacts.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys=ON")

        article_backlog = rows_to_dicts(
            connection.execute(
                f"""
                SELECT
                  s.slug,
                  s.title,
                  s.canonical_url,
                  pt.slug AS primary_topic,
                  pm.slug AS primary_trade_model,
                  s.topic_hint
                FROM sources s
                LEFT JOIN source_topics st
                  ON st.source_id = s.id
                 AND st.relation_type = 'primary_hint'
                LEFT JOIN research_topics pt
                  ON pt.id = st.topic_id
                LEFT JOIN source_trade_models stm
                  ON stm.source_id = s.id
                 AND stm.relation_type = 'primary_hint'
                LEFT JOIN trade_models pm
                  ON pm.id = stm.trade_model_id
                WHERE s.source_type IN ('article', 'pdf_landing', 'doc')
                  AND NOT EXISTS (
                    SELECT 1
                    FROM source_artifacts sa
                    WHERE sa.source_id = s.id
                      AND sa.artifact_type IN ({",".join("?" for _ in TEXT_ARTIFACT_TYPES)})
                  )
                ORDER BY
                  COALESCE(pt.slug, pm.slug, s.topic_hint, 'unknown'),
                  s.title
                """,
                TEXT_ARTIFACT_TYPES,
            )
        )

        video_backlog = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  s.slug,
                  s.title,
                  s.canonical_url,
                  pt.slug AS primary_topic,
                  pm.slug AS primary_trade_model,
                  s.topic_hint
                FROM sources s
                LEFT JOIN source_topics st
                  ON st.source_id = s.id
                 AND st.relation_type = 'primary_hint'
                LEFT JOIN research_topics pt
                  ON pt.id = st.topic_id
                LEFT JOIN source_trade_models stm
                  ON stm.source_id = s.id
                 AND stm.relation_type = 'primary_hint'
                LEFT JOIN trade_models pm
                  ON pm.id = stm.trade_model_id
                WHERE s.source_type = 'video'
                  AND NOT EXISTS (
                    SELECT 1
                    FROM source_artifacts sa
                    WHERE sa.source_id = s.id
                      AND sa.artifact_type = 'transcript'
                  )
                ORDER BY
                  COALESCE(pt.slug, pm.slug, s.topic_hint, 'unknown'),
                  s.title
                """
            )
        )

        topic_summary = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  rt.slug AS topic_slug,
                  rt.name AS topic_name,
                  COUNT(DISTINCT st.source_id) AS source_count,
                  SUM(CASE WHEN s.source_type = 'video' THEN 1 ELSE 0 END) AS video_count
                FROM source_topics st
                JOIN research_topics rt
                  ON rt.id = st.topic_id
                JOIN sources s
                  ON s.id = st.source_id
                GROUP BY rt.slug, rt.name
                ORDER BY source_count DESC, rt.slug
                """
            )
        )

        trade_model_summary = rows_to_dicts(
            connection.execute(
                """
                SELECT
                  tm.slug AS trade_model_slug,
                  tm.name AS trade_model_name,
                  COUNT(DISTINCT stm.source_id) AS source_count,
                  SUM(CASE WHEN s.source_type = 'video' THEN 1 ELSE 0 END) AS video_count
                FROM source_trade_models stm
                JOIN trade_models tm
                  ON tm.id = stm.trade_model_id
                JOIN sources s
                  ON s.id = stm.source_id
                GROUP BY tm.slug, tm.name
                ORDER BY source_count DESC, tm.slug
                """
            )
        )

    backlog = {
        "article_sources_missing_text_artifacts": article_backlog,
        "video_sources_missing_transcripts": video_backlog,
        "topic_summary": topic_summary,
        "trade_model_summary": trade_model_summary,
        "counts": {
            "article_sources_missing_text_artifacts": len(article_backlog),
            "video_sources_missing_transcripts": len(video_backlog),
            "topic_groups": len(topic_summary),
            "trade_model_groups": len(trade_model_summary),
        },
    }
    output_path.write_text(json.dumps(backlog, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "counts": backlog["counts"]}, indent=2))


if __name__ == "__main__":
    main()
