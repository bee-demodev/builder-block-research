from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "knowledge" / "ttfm_video_corpus"
DEFAULT_CHANNEL_URL = "https://www.youtube.com/@TTrades_edu/videos"
DEFAULT_INVENTORY_OUTPUT = CORPUS_DIR / "channel_inventory.json"
DEFAULT_TRADE_REVIEW_MANIFEST_OUTPUT = CORPUS_DIR / "trade_review_video_manifest.json"
DEFAULT_EDUCATIONAL_MANIFEST_OUTPUT = CORPUS_DIR / "educational_video_manifest.json"
DEFAULT_MANIFEST_OUTPUT = DEFAULT_TRADE_REVIEW_MANIFEST_OUTPUT

REVIEW_CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "trade_review": (r"\btrade review\b",),
    "weekly_recap": (r"\bweekly recap\b",),
    "chart_lesson": (r"\btop[- ]down chart lessons?\b",),
    "trade_example": (r"\btrade example\b",),
}

EDUCATIONAL_CATEGORY_PATTERNS: dict[str, tuple[str, ...]] = {
    "bias_framework": (
        r"\bdaily bias\b",
        r"\bintraday bias\b",
        r"\bmechanical framework\b",
    ),
    "fractal_model": (
        r"\bfractal model\b",
        r"\bttfm\b",
        r"\bcandle 2\b",
        r"\bcandle 3\b",
        r"\bcandle 4\b",
        r"\bplaybook\b",
    ),
    "execution_model": (
        r"\bcisd\b",
        r"\border blocks?\b",
        r"\bbreaker(?: block)?s?\b",
        r"\bfair value gaps?\b",
        r"\bfvg\b",
        r"\bifvg\b",
        r"\bprotected swings?\b",
        r"\bliquidity\b",
        r"\bpoints? of interest\b",
        r"\bpoi\b",
        r"\bequilibrium\b",
        r"\bdiscount\b",
        r"\bpremium\b",
        r"\bote\b",
    ),
    "timeframe_alignment": (
        r"\bhigher timeframe\b",
        r"\blower timeframe\b",
        r"\btime frame\b",
        r"\btimeframe\b",
        r"\baligning\b",
        r"\btop[- ]down\b",
    ),
    "market_structure": (
        r"\bswing highs?\b",
        r"\bswing lows?\b",
        r"\bswing points?\b",
        r"\bmarket structure\b",
        r"\bphases of price\b",
        r"\bdisplacement\b",
        r"\btargets?\b",
        r"\bprojections?\b",
        r"\bpower of three\b",
        r"\bohlc\b",
        r"\bolhc\b",
    ),
    "continuation_reversal": (
        r"\bcontinuations?\b",
        r"\breversals?\b",
        r"\bretracement\b",
        r"\bexpansion\b",
        r"\bconsolidation\b",
    ),
    "relative_strength": (
        r"\brelative strength\b",
        r"\bweakness\b",
        r"\bsmt\b",
        r"\bdivergence\b",
    ),
    "trading_framework": (
        r"\btrading framework\b",
        r"\bstrategy\b",
        r"\bmodel\b",
        r"\bentry checklist\b",
    ),
}

EXCLUDED_EDUCATIONAL_PATTERNS: tuple[str, ...] = (
    r"\bthinkorswim\b",
    r"\bsierra chart\b",
    r"\bchartbook\b",
    r"\btrading log\b",
    r"\bshared chartbook\b",
    r"\bloading symbol\b",
    r"\bmarket profile settings\b",
    r"\bpan vertically\b",
    r"\bdom\b",
    r"\bsetup\b",
    r"\bexcel\b",
)

TOPIC_MARKERS: dict[str, tuple[str, ...]] = {
    "daily_bias": ("daily bias", "intraday bias", "bias"),
    "fractal_model": ("fractal model", "ttfm"),
    "candle_2": ("candle 2", "trading candle 2"),
    "candle_3": ("candle 3", "trading candle 3"),
    "candle_4": ("candle 4", "trading candle 4"),
    "cisd": ("cisd", "change in state of delivery"),
    "equilibrium": ("equilibrium", "discount", "premium"),
    "continuation": ("continuation", "continuations"),
    "reversal": ("reversal", "reversals"),
    "retracement": ("retracement",),
    "expansion": ("expansion", "expansions"),
    "consolidation": ("consolidation",),
    "order_block": ("order block", "order blocks"),
    "breaker": ("breaker", "breaker blocks"),
    "fair_value_gap": ("fair value gap", "fair value gaps", "fvg", "ifvg"),
    "protected_swing": ("protected swing", "protected swings", "swing points"),
    "liquidity_sweep": ("liquidity", "sweep", "run the highs", "run the lows"),
    "point_of_interest": ("point of interest", "points of interest", "poi"),
    "wick_logic": ("wick", "wicks"),
    "relative_strength": ("relative strength", "weakness", "smt divergence", "smt"),
    "top_down_alignment": ("top-down", "higher timeframe", "lower timeframe", "timeframe"),
    "power_of_three": ("power of three", "ohlc", "olhc"),
    "targets": ("targets", "projections", "price targets"),
}

EDUCATIONAL_CATEGORY_TOPICS: dict[str, tuple[str, ...]] = {
    "bias_framework": ("daily_bias",),
    "fractal_model": ("fractal_model",),
    "execution_model": (),
    "timeframe_alignment": ("top_down_alignment",),
    "market_structure": (),
    "continuation_reversal": (),
    "relative_strength": ("relative_strength",),
    "trading_framework": (),
}


def path_for_manifest(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def normalize_text(text: str) -> str:
    return " ".join(str(text).lower().replace("_", " ").replace("-", " ").split())


def slugify_title(title: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", normalize_text(title))
    return cleaned.strip("_") or "youtube_video"


def matches_pattern(normalized_text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, normalized_text, flags=re.IGNORECASE) for pattern in patterns)


def fetch_channel_inventory(
    *,
    channel_url: str,
    yt_dlp_bin: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    command = [
        yt_dlp_bin,
        "--no-update",
        "--flat-playlist",
        "--dump-single-json",
        channel_url,
    ]
    completed = runner(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        error = completed.stderr.strip() or completed.stdout.strip() or "yt-dlp inventory fetch failed."
        raise RuntimeError(error)
    return json.loads(completed.stdout)


def classify_review_categories(title: str) -> list[str]:
    normalized = normalize_text(title)
    return [
        category
        for category, patterns in REVIEW_CATEGORY_PATTERNS.items()
        if matches_pattern(normalized, patterns)
    ]


def classify_educational_categories(title: str) -> list[str]:
    normalized = normalize_text(title)
    if matches_pattern(normalized, EXCLUDED_EDUCATIONAL_PATTERNS):
        return []
    return [
        category
        for category, patterns in EDUCATIONAL_CATEGORY_PATTERNS.items()
        if matches_pattern(normalized, patterns)
    ]


def infer_topics_from_title(
    title: str,
    *,
    review_categories: list[str],
    educational_categories: list[str],
) -> list[str]:
    normalized = normalize_text(title)
    topics: set[str] = set()

    for topic, markers in TOPIC_MARKERS.items():
        if any(marker in normalized for marker in markers):
            topics.add(topic)

    for category in review_categories:
        if category == "chart_lesson":
            topics.update({"review", "top_down_analysis"})
        elif category == "weekly_recap":
            topics.update({"review", "recap"})
        elif category == "trade_example":
            topics.update({"review", "example"})
        elif category == "trade_review":
            topics.update({"review", "trade_review"})

    for category in educational_categories:
        topics.update(EDUCATIONAL_CATEGORY_TOPICS.get(category, ()))

    if review_categories:
        topics.add("trade_review")
    if educational_categories:
        topics.add("educational_channel")

    return sorted(topic for topic in topics if topic)


def normalize_inventory_entries(channel_payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for position, raw_entry in enumerate(channel_payload.get("entries", []), start=1):
        video_id = str(raw_entry.get("id", "")).strip()
        title = str(raw_entry.get("title", "")).strip()
        if not video_id or not title:
            continue

        review_categories = classify_review_categories(title)
        educational_categories = classify_educational_categories(title)
        topics = infer_topics_from_title(
            title,
            review_categories=review_categories,
            educational_categories=educational_categories,
        )

        entries.append(
            {
                "position": position,
                "video_id": video_id,
                "title": title,
                "url": f"https://youtu.be/{video_id}",
                "slug": slugify_title(title),
                "review_categories": review_categories,
                "educational_categories": educational_categories,
                "is_trade_review_candidate": bool(review_categories),
                "is_educational_candidate": bool(review_categories or educational_categories),
                "topics": topics,
                "corpus_partition_candidate": (
                    "trade_review"
                    if review_categories
                    else "educational_youtube"
                    if educational_categories
                    else None
                ),
            }
        )
    return entries


def build_manifest_video_row(
    entry: dict[str, Any],
    *,
    channel_url: str,
    corpus_partition: str,
    review_categories: list[str],
    educational_categories: list[str],
) -> dict[str, Any]:
    return {
        "slug": entry["slug"],
        "title": entry["title"],
        "video_id": entry["video_id"],
        "url": entry["url"],
        "source_page": None,
        "topics": list(entry.get("topics", [])),
        "corpus_partition": corpus_partition,
        "review_categories": review_categories,
        "educational_categories": educational_categories,
        "discovery_source": "youtube_channel_inventory",
        "channel_url": channel_url,
    }


def summarize_inventory(
    normalized_entries: list[dict[str, Any]],
    *,
    channel_payload: dict[str, Any],
    channel_url: str,
) -> dict[str, Any]:
    review_category_counts = {
        category: 0
        for category in sorted(REVIEW_CATEGORY_PATTERNS)
    }
    educational_category_counts = {
        category: 0
        for category in sorted(EDUCATIONAL_CATEGORY_PATTERNS)
    }
    selected_partition_counts: dict[str, int] = {}
    educational_candidate_count = 0
    trade_review_candidate_count = 0

    for entry in normalized_entries:
        if entry["is_educational_candidate"]:
            educational_candidate_count += 1
        if entry["is_trade_review_candidate"]:
            trade_review_candidate_count += 1
        for category in entry["review_categories"]:
            review_category_counts[category] += 1
        for category in entry["educational_categories"]:
            educational_category_counts[category] += 1
        partition = str(entry.get("corpus_partition_candidate") or "").strip()
        if partition:
            selected_partition_counts[partition] = selected_partition_counts.get(partition, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "channel_title": str(channel_payload.get("title", "")).strip() or "TTrades - Videos",
        "channel_url": channel_url,
        "entry_count": len(normalized_entries),
        "educational_candidate_count": educational_candidate_count,
        "trade_review_candidate_count": trade_review_candidate_count,
        "category_counts": review_category_counts,
        "educational_category_counts": educational_category_counts,
        "selected_partition_counts": dict(sorted(selected_partition_counts.items())),
        "entries": normalized_entries,
    }


def build_trade_review_manifest(
    channel_payload: dict[str, Any],
    *,
    channel_url: str,
    include_categories: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    include_categories = include_categories or set(REVIEW_CATEGORY_PATTERNS)
    normalized_entries = normalize_inventory_entries(channel_payload)
    selected_videos: list[dict[str, Any]] = []

    for entry in normalized_entries:
        categories = [
            category for category in entry["review_categories"] if category in include_categories
        ]
        if not categories:
            continue
        selected_videos.append(
            build_manifest_video_row(
                entry,
                channel_url=channel_url,
                corpus_partition="trade_review",
                review_categories=categories,
                educational_categories=list(entry["educational_categories"]),
            )
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_source": "trade_review_channel_inventory",
        "source_channel_url": channel_url,
        "video_count": len(selected_videos),
        "videos": selected_videos,
    }
    inventory = summarize_inventory(
        normalized_entries,
        channel_payload=channel_payload,
        channel_url=channel_url,
    )
    return inventory, manifest


def build_channel_corpus_manifests(
    channel_payload: dict[str, Any],
    *,
    channel_url: str,
    include_review_categories: set[str] | None = None,
    include_educational_categories: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    include_review_categories = include_review_categories or set(REVIEW_CATEGORY_PATTERNS)
    include_educational_categories = include_educational_categories or set(EDUCATIONAL_CATEGORY_PATTERNS)
    normalized_entries = normalize_inventory_entries(channel_payload)

    trade_review_videos: list[dict[str, Any]] = []
    selected_videos: list[dict[str, Any]] = []

    for entry in normalized_entries:
        review_categories = [
            category
            for category in entry["review_categories"]
            if category in include_review_categories
        ]
        educational_categories = [
            category
            for category in entry["educational_categories"]
            if category in include_educational_categories
        ]

        if review_categories:
            row = build_manifest_video_row(
                entry,
                channel_url=channel_url,
                corpus_partition="trade_review",
                review_categories=review_categories,
                educational_categories=educational_categories,
            )
            trade_review_videos.append(row)
            selected_videos.append(row)
            continue

        if not educational_categories:
            continue

        selected_videos.append(
            build_manifest_video_row(
                entry,
                channel_url=channel_url,
                corpus_partition="educational_youtube",
                review_categories=[],
                educational_categories=educational_categories,
            )
        )

    inventory = summarize_inventory(
        normalized_entries,
        channel_payload=channel_payload,
        channel_url=channel_url,
    )
    educational_manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_source": "educational_channel_inventory",
        "source_channel_url": channel_url,
        "video_count": len(selected_videos),
        "videos": selected_videos,
    }
    trade_review_manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_source": "trade_review_channel_inventory",
        "source_channel_url": channel_url,
        "video_count": len(trade_review_videos),
        "videos": trade_review_videos,
    }
    return inventory, educational_manifest, trade_review_manifest


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover educational and review-style TTrades videos from the live YouTube channel inventory."
    )
    parser.add_argument("--channel-url", default=DEFAULT_CHANNEL_URL)
    parser.add_argument("--yt-dlp-bin", default="yt-dlp")
    parser.add_argument(
        "--manifest-mode",
        choices=("trade_review_only", "educational_channel"),
        default="educational_channel",
    )
    parser.add_argument(
        "--include-category",
        action="append",
        choices=sorted(REVIEW_CATEGORY_PATTERNS),
        dest="include_review_categories",
        help="Limit the trade-review subset to one or more category buckets.",
    )
    parser.add_argument(
        "--include-educational-category",
        action="append",
        choices=sorted(EDUCATIONAL_CATEGORY_PATTERNS),
        dest="include_educational_categories",
        help="Limit the educational manifest to one or more category buckets.",
    )
    parser.add_argument("--inventory-output", type=Path, default=DEFAULT_INVENTORY_OUTPUT)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_EDUCATIONAL_MANIFEST_OUTPUT)
    parser.add_argument(
        "--trade-review-manifest-output",
        type=Path,
        default=DEFAULT_TRADE_REVIEW_MANIFEST_OUTPUT,
    )
    args = parser.parse_args()

    channel_payload = fetch_channel_inventory(
        channel_url=args.channel_url,
        yt_dlp_bin=args.yt_dlp_bin,
    )
    inventory, educational_manifest, trade_review_manifest = build_channel_corpus_manifests(
        channel_payload,
        channel_url=args.channel_url,
        include_review_categories=set(args.include_review_categories or REVIEW_CATEGORY_PATTERNS),
        include_educational_categories=set(
            args.include_educational_categories or EDUCATIONAL_CATEGORY_PATTERNS
        ),
    )
    write_json(args.inventory_output, inventory)
    write_json(args.trade_review_manifest_output, trade_review_manifest)

    if args.manifest_mode == "trade_review_only":
        selected_manifest = trade_review_manifest
    else:
        selected_manifest = educational_manifest
    write_json(args.manifest_output, selected_manifest)

    print(
        json.dumps(
            {
                "inventory_output": path_for_manifest(args.inventory_output),
                "manifest_output": path_for_manifest(args.manifest_output),
                "trade_review_manifest_output": path_for_manifest(args.trade_review_manifest_output),
                "entry_count": inventory["entry_count"],
                "educational_candidate_count": inventory["educational_candidate_count"],
                "trade_review_candidate_count": inventory["trade_review_candidate_count"],
                "manifest_video_count": selected_manifest["video_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
