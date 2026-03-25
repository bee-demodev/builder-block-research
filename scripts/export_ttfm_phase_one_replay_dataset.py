from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from export_ttfm_teacher_visual_dataset import DEFAULT_DATASET_OUTPUT as DEFAULT_TEACHER_DATASET_PATH
from phase_one_focus import (
    PHASE_ONE_EXECUTION_SPEC,
    PHASE_ONE_PRIMARY_TRADE_MODEL,
    PHASE_ONE_TIMEFRAME_STACK,
)
from runtime.harness import DEFAULT_TIMEZONE, infer_session_bucket, load_bars_csv, parse_timestamp


DEFAULT_DATASET_OUTPUT = ROOT / "results" / "ttfm_phase_one_replay_dataset.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_phase_one_replay_dataset_report.json"


def load_teacher_visual_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            cleaned = line.strip()
            if cleaned:
                rows.append(json.loads(cleaned))
    return rows


def unique_strings(values: Iterable[object]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in seen:
            ordered.append(cleaned)
            seen.add(cleaned)
    return ordered


def sort_rows_for_case(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: (str(row.get("checkpoint", "")), str(row.get("example_id", ""))))


def group_rows_by_case(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        case_ref = str(row.get("case_ref", "")).strip()
        if case_ref:
            grouped[case_ref].append(row)
    return {case_ref: sort_rows_for_case(case_rows) for case_ref, case_rows in grouped.items()}


def case_trade_models(case_rows: list[dict[str, Any]]) -> list[str]:
    return unique_strings(
        trade_model
        for row in case_rows
        for trade_model in row.get("trade_models", [])
    )


def case_relation_types(case_rows: list[dict[str, Any]]) -> list[str]:
    return unique_strings(
        relation_type
        for row in case_rows
        for relation_type in row.get("relation_types", [])
    )


def is_phase_one_case(case_rows: list[dict[str, Any]]) -> bool:
    return PHASE_ONE_PRIMARY_TRADE_MODEL in case_trade_models(case_rows)


def resolve_case_market_context(case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in case_rows:
        market_context = row.get("market_context")
        if isinstance(market_context, dict):
            return market_context
    return {}


def build_checkpoint_labels(case_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_checkpoint: dict[str, list[str]] = {}
    for row in case_rows:
        checkpoint = str(row.get("checkpoint", "")).strip()
        if not checkpoint:
            continue
        existing = by_checkpoint.setdefault(checkpoint, [])
        for label in row.get("active_labels", []):
            cleaned = str(label or "").strip()
            if cleaned and cleaned not in existing:
                existing.append(cleaned)
    return by_checkpoint


def build_checkpoint_notes(case_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_checkpoint: dict[str, list[str]] = {}
    for row in case_rows:
        checkpoint = str(row.get("checkpoint", "")).strip()
        if not checkpoint:
            continue
        existing = by_checkpoint.setdefault(checkpoint, [])
        for note in row.get("annotation_notes", []):
            cleaned = str(note or "").strip()
            if cleaned and cleaned not in existing:
                existing.append(cleaned)
    return by_checkpoint


def floor_timestamp_to_bucket(timestamp: datetime, bucket_minutes: int) -> datetime:
    if bucket_minutes <= 0:
        raise ValueError("bucket_minutes must be positive")
    minute = (timestamp.minute // bucket_minutes) * bucket_minutes
    return timestamp.replace(minute=minute, second=0, microsecond=0)


def resolve_session_start(
    timestamp: datetime,
    *,
    session_roll_hour: int,
    timezone_name: str,
) -> datetime:
    local_timestamp = timestamp.astimezone(ZoneInfo(timezone_name))
    session_date = local_timestamp.date()
    if local_timestamp.timetz().replace(tzinfo=None) < time(session_roll_hour, 0):
        session_date -= timedelta(days=1)
    return datetime.combine(
        session_date,
        time(session_roll_hour, 0),
        tzinfo=ZoneInfo(timezone_name),
    )


def build_window_bar(
    *,
    timestamp: datetime,
    end_timestamp: datetime,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: float | None,
    session: str | None,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp.isoformat(),
        "end_timestamp": end_timestamp.isoformat(),
        "open": round(float(open_price), 6),
        "high": round(float(high_price), 6),
        "low": round(float(low_price), 6),
        "close": round(float(close_price), 6),
        "volume": round(float(volume), 6) if volume is not None else None,
        "session": session,
    }


def aggregate_intraday_bars(
    bars: list[Any],
    *,
    bucket_minutes: int,
) -> list[dict[str, Any]]:
    aggregated: dict[datetime, dict[str, Any]] = {}
    ordered_keys: list[datetime] = []
    for bar in bars:
        bucket_timestamp = floor_timestamp_to_bucket(bar.timestamp, bucket_minutes)
        payload = aggregated.get(bucket_timestamp)
        if payload is None:
            payload = {
                "timestamp": bucket_timestamp,
                "end_timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume or 0.0,
                "session": bar.session or infer_session_bucket(bar.timestamp),
            }
            aggregated[bucket_timestamp] = payload
            ordered_keys.append(bucket_timestamp)
        else:
            payload["end_timestamp"] = bar.timestamp
            payload["high"] = max(float(payload["high"]), float(bar.high))
            payload["low"] = min(float(payload["low"]), float(bar.low))
            payload["close"] = bar.close
            payload["volume"] = float(payload["volume"]) + float(bar.volume or 0.0)
    return [
        build_window_bar(
            timestamp=aggregated[key]["timestamp"],
            end_timestamp=aggregated[key]["end_timestamp"],
            open_price=aggregated[key]["open"],
            high_price=aggregated[key]["high"],
            low_price=aggregated[key]["low"],
            close_price=aggregated[key]["close"],
            volume=aggregated[key]["volume"],
            session=aggregated[key]["session"],
        )
        for key in sorted(ordered_keys)
    ]


def aggregate_daily_session_bars(
    bars: list[Any],
    *,
    session_roll_hour: int,
    timezone_name: str,
) -> list[dict[str, Any]]:
    aggregated: dict[datetime, dict[str, Any]] = {}
    ordered_keys: list[datetime] = []
    for bar in bars:
        session_start = resolve_session_start(
            bar.timestamp,
            session_roll_hour=session_roll_hour,
            timezone_name=timezone_name,
        )
        payload = aggregated.get(session_start)
        if payload is None:
            payload = {
                "timestamp": session_start,
                "end_timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume or 0.0,
                "session": "session_daily",
            }
            aggregated[session_start] = payload
            ordered_keys.append(session_start)
        else:
            payload["end_timestamp"] = bar.timestamp
            payload["high"] = max(float(payload["high"]), float(bar.high))
            payload["low"] = min(float(payload["low"]), float(bar.low))
            payload["close"] = bar.close
            payload["volume"] = float(payload["volume"]) + float(bar.volume or 0.0)
    return [
        build_window_bar(
            timestamp=aggregated[key]["timestamp"],
            end_timestamp=aggregated[key]["end_timestamp"],
            open_price=aggregated[key]["open"],
            high_price=aggregated[key]["high"],
            low_price=aggregated[key]["low"],
            close_price=aggregated[key]["close"],
            volume=aggregated[key]["volume"],
            session=aggregated[key]["session"],
        )
        for key in sorted(ordered_keys)
    ]


def build_intraday_window(
    bars: list[Any],
    *,
    anchor_timestamp: datetime,
    bucket_minutes: int,
    window_minutes_before: int,
    window_minutes_after: int,
) -> dict[str, Any]:
    window_start = anchor_timestamp - timedelta(minutes=window_minutes_before)
    window_end = anchor_timestamp + timedelta(minutes=window_minutes_after)
    visible_bars = [
        bar
        for bar in bars
        if window_start <= bar.timestamp <= window_end
    ]
    aggregated_bars = aggregate_intraday_bars(visible_bars, bucket_minutes=bucket_minutes)
    anchor_bucket_timestamp = floor_timestamp_to_bucket(anchor_timestamp, bucket_minutes).isoformat()
    anchor_bar_index = next(
        (
            index
            for index, bar in enumerate(aggregated_bars)
            if bar["timestamp"] == anchor_bucket_timestamp
        ),
        -1,
    )
    if anchor_bar_index < 0:
        raise ValueError(
            f"Missing anchor bucket {anchor_bucket_timestamp} for {bucket_minutes}m window."
        )
    return {
        "anchor_bucket_timestamp": anchor_bucket_timestamp,
        "anchor_bar_index": anchor_bar_index,
        "bar_count": len(aggregated_bars),
        "bars": aggregated_bars,
    }


def build_daily_window(
    bars: list[Any],
    *,
    anchor_timestamp: datetime,
    daily_lookback_sessions: int,
    daily_lookahead_sessions: int,
    session_roll_hour: int,
    timezone_name: str,
) -> dict[str, Any]:
    aggregated_bars = aggregate_daily_session_bars(
        bars,
        session_roll_hour=session_roll_hour,
        timezone_name=timezone_name,
    )
    anchor_bucket_timestamp = resolve_session_start(
        anchor_timestamp,
        session_roll_hour=session_roll_hour,
        timezone_name=timezone_name,
    ).isoformat()
    anchor_bar_index = next(
        (
            index
            for index, bar in enumerate(aggregated_bars)
            if bar["timestamp"] == anchor_bucket_timestamp
        ),
        -1,
    )
    if anchor_bar_index < 0:
        raise ValueError(f"Missing anchor daily session {anchor_bucket_timestamp}.")
    start_index = max(0, anchor_bar_index - daily_lookback_sessions)
    end_index = min(len(aggregated_bars), anchor_bar_index + daily_lookahead_sessions + 1)
    selected_bars = aggregated_bars[start_index:end_index]
    return {
        "anchor_bucket_timestamp": anchor_bucket_timestamp,
        "anchor_bar_index": anchor_bar_index - start_index,
        "bar_count": len(selected_bars),
        "bars": selected_bars,
    }


def build_phase_one_case_example(
    case_rows: list[dict[str, Any]],
    *,
    bars_cache: dict[str, list[Any]],
    daily_lookback_sessions: int,
    daily_lookahead_sessions: int,
    session_roll_hour: int,
    timezone_name: str,
) -> tuple[dict[str, Any] | None, str | None]:
    market_context = resolve_case_market_context(case_rows)
    alignment_status = str(market_context.get("alignment_status", "")).strip()
    if alignment_status != "fully_aligned":
        return None, "not_fully_aligned"

    bars_path_text = str(market_context.get("bars_path", "")).strip()
    if not bars_path_text:
        return None, "missing_bars_path"
    bars_path = Path(bars_path_text)
    if not bars_path.exists():
        return None, "missing_bars_file"

    anchor_timestamp_text = str(market_context.get("anchor_timestamp", "")).strip()
    if not anchor_timestamp_text:
        return None, "missing_anchor_timestamp"
    anchor_timestamp = parse_timestamp(anchor_timestamp_text, timezone_name=timezone_name)

    cache_key = str(bars_path.resolve())
    if cache_key not in bars_cache:
        bars_cache[cache_key] = load_bars_csv(bars_path, timezone_name=timezone_name)
    bars = bars_cache[cache_key]
    if not bars:
        return None, "empty_bars"

    try:
        daily_window = build_daily_window(
            bars,
            anchor_timestamp=anchor_timestamp,
            daily_lookback_sessions=daily_lookback_sessions,
            daily_lookahead_sessions=daily_lookahead_sessions,
            session_roll_hour=session_roll_hour,
            timezone_name=timezone_name,
        )
        structure_window = build_intraday_window(
            bars,
            anchor_timestamp=anchor_timestamp,
            bucket_minutes=60,
            window_minutes_before=int(market_context.get("window_minutes_before", 180) or 180),
            window_minutes_after=int(market_context.get("window_minutes_after", 240) or 240),
        )
        execution_window = build_intraday_window(
            bars,
            anchor_timestamp=anchor_timestamp,
            bucket_minutes=5,
            window_minutes_before=int(market_context.get("window_minutes_before", 180) or 180),
            window_minutes_after=int(market_context.get("window_minutes_after", 240) or 240),
        )
    except ValueError:
        return None, "missing_anchor_bucket"

    primary_row = case_rows[0]
    example_id = f"{primary_row['case_ref']}::phase_one_replay"
    checkpoint_labels = build_checkpoint_labels(case_rows)
    checkpoint_notes = build_checkpoint_notes(case_rows)
    supporting_topics = unique_strings(
        topic
        for row in case_rows
        for topic in row.get("supporting_topics", [])
    )
    draft_spec_keys = unique_strings(
        key
        for row in case_rows
        for key in row.get("draft_spec_keys", [])
    )
    outcome = primary_row.get("outcome") if isinstance(primary_row.get("outcome"), dict) else {}

    return {
        "example_id": example_id,
        "case_ref": primary_row.get("case_ref"),
        "topic": primary_row.get("topic"),
        "profile_slug": "ttrades_curriculum",
        "phase_one_primary_trade_model": PHASE_ONE_PRIMARY_TRADE_MODEL,
        "phase_one_execution_spec": PHASE_ONE_EXECUTION_SPEC,
        "trade_models": case_trade_models(case_rows),
        "relation_types": case_relation_types(case_rows),
        "source_url": primary_row.get("source_url"),
        "market_context": market_context,
        "anchor_context": {
            "anchor_timestamp": anchor_timestamp.isoformat(),
            "anchor_session_bucket": infer_session_bucket(anchor_timestamp, timezone_name=timezone_name),
            "window_minutes_before": int(market_context.get("window_minutes_before", 180) or 180),
            "window_minutes_after": int(market_context.get("window_minutes_after", 240) or 240),
            "timeframe_stack": dict(PHASE_ONE_TIMEFRAME_STACK),
            "session_roll_hour": session_roll_hour,
        },
        "teacher_summary": {
            "checkpoint_count": len(case_rows),
            "checkpoint_labels": checkpoint_labels,
            "checkpoint_notes": checkpoint_notes,
            "supporting_topics": supporting_topics,
            "draft_spec_keys": draft_spec_keys,
            "outcome": outcome,
        },
        "training_targets": {
            "primary_trade_model": PHASE_ONE_PRIMARY_TRADE_MODEL,
            "execution_spec": PHASE_ONE_EXECUTION_SPEC,
            "alignment_status": alignment_status,
            "outcome_decision": outcome.get("decision"),
            "outcome_reason": outcome.get("reason"),
        },
        "timeframe_windows": {
            "D": daily_window,
            "60": structure_window,
            "5": execution_window,
        },
    }, None


def build_phase_one_replay_dataset(
    rows: list[dict[str, Any]],
    *,
    daily_lookback_sessions: int = 5,
    daily_lookahead_sessions: int = 1,
    session_roll_hour: int = 18,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> dict[str, Any]:
    grouped_rows = group_rows_by_case(rows)
    phase_one_case_refs = [
        case_ref
        for case_ref, case_rows in grouped_rows.items()
        if is_phase_one_case(case_rows)
    ]

    bars_cache: dict[str, list[Any]] = {}
    examples: list[dict[str, Any]] = []
    skipped_case_counts = {
        "not_fully_aligned": 0,
        "missing_bars_path": 0,
        "missing_bars_file": 0,
        "missing_anchor_timestamp": 0,
        "empty_bars": 0,
        "missing_anchor_bucket": 0,
    }

    for case_ref in phase_one_case_refs:
        example, skip_reason = build_phase_one_case_example(
            grouped_rows[case_ref],
            bars_cache=bars_cache,
            daily_lookback_sessions=daily_lookback_sessions,
            daily_lookahead_sessions=daily_lookahead_sessions,
            session_roll_hour=session_roll_hour,
            timezone_name=timezone_name,
        )
        if example is not None:
            examples.append(example)
            continue
        if skip_reason:
            skipped_case_counts[skip_reason] += 1

    summary = {
        "teacher_row_count": len(rows),
        "teacher_case_count": len(grouped_rows),
        "phase_one_case_count": len(phase_one_case_refs),
        "exported_case_count": len(examples),
        "exported_case_refs": [example["case_ref"] for example in examples],
        "skipped_case_counts": skipped_case_counts,
        "timeframe_stack": dict(PHASE_ONE_TIMEFRAME_STACK),
        "phase_one_primary_trade_model": PHASE_ONE_PRIMARY_TRADE_MODEL,
        "phase_one_execution_spec": PHASE_ONE_EXECUTION_SPEC,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "examples": examples,
    }


def export_phase_one_replay_dataset(
    *,
    dataset_path: Path,
    dataset_output: Path,
    report_output: Path,
    daily_lookback_sessions: int = 5,
    daily_lookahead_sessions: int = 1,
    session_roll_hour: int = 18,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> dict[str, Any]:
    rows = load_teacher_visual_rows(dataset_path)
    report = build_phase_one_replay_dataset(
        rows,
        daily_lookback_sessions=daily_lookback_sessions,
        daily_lookahead_sessions=daily_lookahead_sessions,
        session_roll_hour=session_roll_hour,
        timezone_name=timezone_name,
    )

    dataset_output.parent.mkdir(parents=True, exist_ok=True)
    dataset_output.write_text(
        "\n".join(json.dumps(example, sort_keys=True) for example in report["examples"])
        + ("\n" if report["examples"] else ""),
        encoding="utf-8",
    )

    persisted_report = {
        "generated_at": report["generated_at"],
        "dataset_path": str(dataset_path),
        "dataset_output": str(dataset_output),
        "report_output": str(report_output),
        "summary": report["summary"],
    }
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(persisted_report, indent=2), encoding="utf-8")
    return persisted_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export phase-1 TTFM replay examples from fully aligned teacher cases so the "
            "next neural model can learn daily bias and D/60m/5m chart state."
        )
    )
    parser.add_argument("--dataset", default=str(DEFAULT_TEACHER_DATASET_PATH))
    parser.add_argument("--dataset-output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    parser.add_argument("--daily-lookback-sessions", type=int, default=5)
    parser.add_argument("--daily-lookahead-sessions", type=int, default=1)
    parser.add_argument("--session-roll-hour", type=int, default=18)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    args = parser.parse_args()

    report = export_phase_one_replay_dataset(
        dataset_path=Path(args.dataset),
        dataset_output=Path(args.dataset_output),
        report_output=Path(args.report_output),
        daily_lookback_sessions=args.daily_lookback_sessions,
        daily_lookahead_sessions=args.daily_lookahead_sessions,
        session_roll_hour=args.session_roll_hour,
        timezone_name=args.timezone,
    )
    print(
        json.dumps(
            {
                "dataset_output": report["dataset_output"],
                "report_output": report["report_output"],
                "phase_one_case_count": report["summary"]["phase_one_case_count"],
                "exported_case_count": report["summary"]["exported_case_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
