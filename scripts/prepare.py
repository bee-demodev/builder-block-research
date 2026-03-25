from __future__ import annotations

import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
SCHEMA_PATH = ROOT / "data" / "schema.sql"
RESULTS_PATH = ROOT / "results" / "research_runs.tsv"


SEED_SOURCES = [
    {
        "slug": "ttrades_education_center",
        "source_type": "article_index",
        "title": "Trading Education Center",
        "canonical_url": "https://ttrades.com/trading-education-center/",
        "author": "TTrades",
        "published_at": None,
        "topic_hint": "curriculum",
        "summary": "Primary curriculum index for TTrades trading lessons."
    },
    {
        "slug": "ttrades_expansion_part_2",
        "source_type": "article",
        "title": "Phases of Price - Part 2: Mastering Expansion for Strong Trend Trades",
        "canonical_url": "https://ttrades.com/phases-of-price-part-2-mastering-expansion-for-strong-trend-trades/",
        "author": "TTrades",
        "published_at": "2025-08-09",
        "topic_hint": "expansion",
        "summary": "Defines expansion, its signatures, and a practical execution workflow."
    },
    {
        "slug": "ttrades_protected_swings",
        "source_type": "article",
        "title": "Protected Swings in Trading: How to Identify and Use Them for Entries & Continuations",
        "canonical_url": "https://ttrades.com/protected-swings-understanding-trends-and-invalidations/",
        "author": "TTrades",
        "published_at": "2025-08-06",
        "topic_hint": "protected_swings",
        "summary": "Defines protected swings and their role in confirmation, invalidation, and continuation."
    },
    {
        "slug": "ttrades_stop_loss_mastery",
        "source_type": "article",
        "title": "Stop Loss Mastery - Using Protected Swings for Precise Invalidations",
        "canonical_url": "https://ttrades.com/stop-loss-mastery-using-protected-swings-for-precise-invalidations/",
        "author": "TTrades",
        "published_at": "2025-08-13",
        "topic_hint": "risk",
        "summary": "Explains structural stop placement using protected swings."
    },
    {
        "slug": "ttrades_easy_daily_bias",
        "source_type": "article",
        "title": "Easy Daily Bias: A Mechanical Trading Framework",
        "canonical_url": "https://ttrades.com/easy-daily-bias-a-mechanical-trading-framework/",
        "author": "TTrades",
        "published_at": "2025-12-13",
        "topic_hint": "bias",
        "summary": "Mechanical framework for daily bias using candle closures, wick size, and equilibrium."
    },
    {
        "slug": "ttrades_aligning_expansion_candles",
        "source_type": "article",
        "title": "Aligning Candles for Expansion: How True Trends Actually Form",
        "canonical_url": "https://ttrades.com/aligning-candles-for-expansion-how-true-trends-actually-form/",
        "author": "TTrades",
        "published_at": "2026-01-17",
        "topic_hint": "expansion",
        "summary": "Explains candle alignment, wick logic, and multi-timeframe expansion support."
    },
    {
        "slug": "ttrades_top_down_expansion",
        "source_type": "article",
        "title": "Mastering Top-Down Analysis: Aligning Multiple Timeframes for Expansion Trading",
        "canonical_url": "https://ttrades.com/mastering-top-down-analysis-aligning-multiple-timeframes-for-expansion-trading/",
        "author": "TTrades",
        "published_at": "2025-07-31",
        "topic_hint": "alignment",
        "summary": "Defines higher, intermediate, and lower timeframe roles for expansion trading."
    },
    {
        "slug": "pine_style_guide",
        "source_type": "doc",
        "title": "Pine Script Style Guide",
        "canonical_url": "https://www.tradingview.com/pine-script-docs/writing/style-guide/",
        "author": "TradingView",
        "published_at": None,
        "topic_hint": "pine",
        "summary": "Official style and script organization guidance."
    },
    {
        "slug": "pine_type_system",
        "source_type": "doc",
        "title": "Pine Script Type System",
        "canonical_url": "https://www.tradingview.com/pine-script-docs/language/type-system/",
        "author": "TradingView",
        "published_at": None,
        "topic_hint": "pine",
        "summary": "Official reference for UDTs, arrays, maps, and reference types."
    },
    {
        "slug": "pine_limitations",
        "source_type": "doc",
        "title": "Pine Script Limitations",
        "canonical_url": "https://www.tradingview.com/pine-script-docs/writing/limitations/",
        "author": "TradingView",
        "published_at": None,
        "topic_hint": "pine",
        "summary": "Official limits around request calls, tuples, and display resources."
    }
]


SEED_CONCEPTS = [
    ("bias", "Bias", "context", "Higher-timeframe directional context for filtering lower-timeframe trades."),
    ("expansion", "Expansion", "phase", "One-sided trending move with shallow pullbacks."),
    ("protected_swings", "Protected Swings", "structure", "Structural highs or lows expected to hold if the current thesis remains valid."),
    ("consolidation", "Consolidation", "phase", "Smaller-range condition preceding expansion or reversal."),
    ("retracement", "Retracement", "phase", "Countertrend pullback within a broader directional move."),
    ("reversal", "Reversal", "phase", "Directional change after prior structure fails and opposite structure confirms."),
    ("risk", "Risk / Invalidation", "execution", "Structural invalidation and stop placement logic."),
    ("alignment", "Timeframe Alignment", "context", "Directional agreement across higher, intermediate, and lower timeframes.")
]

SEED_TRADER_PROFILES = [
    {
        "slug": "ttrades_curriculum",
        "display_name": "TTrades Curriculum",
        "profile_type": "teacher_style",
        "notes": "Reference profile distilled from TTrades educational material before any individual trader adaptation.",
        "style_json": {
            "source_mode": "curriculum",
            "execution_style": "structure_confirmation",
            "confirmation_style": "protected_swing_and_closure",
            "risk_style": "protected_swing_invalidation",
            "indicator_intent": "teacher_style_bundle",
            "status": "baseline"
        }
    }
]


def ensure_parent_paths() -> None:
    for directory in [
        ROOT / "artifacts" / "ttrades" / "pages",
        ROOT / "data",
        ROOT / "knowledge",
        ROOT / "results",
        ROOT / "topics" / "bias",
        ROOT / "topics" / "expansion",
        ROOT / "topics" / "protected_swings",
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def initialize_database() -> list[str]:
    with sqlite3.connect(DB_PATH) as connection:
        pre_schema_upgrades = run_schema_upgrades(connection)
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)
        post_schema_upgrades = run_schema_upgrades(connection)
        connection.commit()
    return pre_schema_upgrades + post_schema_upgrades


def column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()
    return row is not None


def run_schema_upgrades(connection: sqlite3.Connection) -> list[str]:
    upgrades: list[str] = []
    if table_exists(connection, "trader_profiles") and not column_exists(connection, "trader_profiles", "status"):
        connection.execute(
            """
            ALTER TABLE trader_profiles
            ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
            """
        )
        upgrades.append("added trader_profiles.status")
    return upgrades


def seed_sources() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        for row in SEED_SOURCES:
            connection.execute(
                """
                INSERT OR IGNORE INTO sources (
                    slug, source_type, title, canonical_url, author, published_at, topic_hint, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["slug"],
                    row["source_type"],
                    row["title"],
                    row["canonical_url"],
                    row["author"],
                    row["published_at"],
                    row["topic_hint"],
                    row["summary"],
                ),
            )
        connection.commit()


def seed_concepts() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        for slug, name, category, description in SEED_CONCEPTS:
            connection.execute(
                """
                INSERT OR IGNORE INTO concepts (slug, name, category, description)
                VALUES (?, ?, ?, ?)
                """,
                (slug, name, category, description),
            )
        connection.commit()


def seed_trader_profiles() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        for profile in SEED_TRADER_PROFILES:
            connection.execute(
                """
                INSERT OR IGNORE INTO trader_profiles (
                    slug, display_name, profile_type, notes, style_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    profile["slug"],
                    profile["display_name"],
                    profile["profile_type"],
                    profile["notes"],
                    json.dumps(profile["style_json"], sort_keys=True),
                ),
            )
        connection.commit()


def ensure_results_file() -> None:
    if RESULTS_PATH.exists():
        return
    RESULTS_PATH.write_text(
        "run_at\ttopic\tgrounding_score\tdeterminism_score\tvisual_verification_score\tpine_translatability_score\tcontradiction_penalty\tweighted_score\tstatus\tdescription\n",
        encoding="utf-8",
    )


def main() -> None:
    ensure_parent_paths()
    schema_upgrades = initialize_database()
    seed_sources()
    seed_concepts()
    seed_trader_profiles()
    ensure_results_file()

    summary = {
        "database": str(DB_PATH),
        "results_tsv": str(RESULTS_PATH),
        "seed_sources": len(SEED_SOURCES),
        "seed_concepts": len(SEED_CONCEPTS),
        "seed_trader_profiles": len(SEED_TRADER_PROFILES),
        "schema_upgrades": schema_upgrades,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
