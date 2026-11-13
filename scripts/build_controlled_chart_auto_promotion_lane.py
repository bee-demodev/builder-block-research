from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import YOLO_CLASS_NAMES, YOLO_CLASS_TO_ID
from labeler.vision_labeler import load_supervision_answers
from scripts.build_ttrades_state_builder_fixtures import fixture_from_row


DEFAULT_LINEAGE_MANIFEST = Path("results") / "controlled_charts" / "controlled_chart_lineage_manifest.json"
DEFAULT_OUTPUT_ANSWERS = Path("results") / "controlled_charts" / "auto_pseudo_labels.json"
DEFAULT_OUTPUT_REPORT = Path("results") / "controlled_charts" / "auto_pseudo_label_report.json"
DEFAULT_OUTPUT_STATE_FIXTURES = Path("results") / "ttrades_state_builder_fixtures.auto.json"
MODEL_VERSION = "controlled_ohlc_weak_supervision_v1"
PRICE_ROI = {"left": 0.06, "right": 0.94, "top": 0.05, "bottom": 0.62}
MAX_HIGH_CONFIDENCE_QUALITY_FILTER_REMOVED_RATIO = 0.20


@dataclass(slots=True)
class Bar:
    bucket: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    session: str


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(str(value).strip())


def bucket_time(timestamp: datetime, timeframe: str) -> datetime:
    normalized = str(timeframe).strip().lower()
    if normalized in {"1d", "d", "daily"}:
        return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    if normalized in {"1h", "h", "60m"}:
        return timestamp.replace(minute=0, second=0, microsecond=0)
    if normalized in {"5m", "m5"}:
        minute = (timestamp.minute // 5) * 5
        return timestamp.replace(minute=minute, second=0, microsecond=0)
    return timestamp


def load_bars_for_image(root_dir: Path, image: dict[str, Any]) -> list[Bar]:
    source_path = resolve(root_dir, str(image.get("source_csv_path") or ""))
    visible = image.get("visible_range", {}) if isinstance(image.get("visible_range"), dict) else {}
    start = parse_dt(str(visible.get("start")))
    end = parse_dt(str(visible.get("end")))
    timeframe = str(image.get("timeframe") or "")
    quality = image.get("quality_filter", {}) if isinstance(image.get("quality_filter"), dict) else {}
    min_price = float(quality.get("min_price") or float("-inf"))
    max_price = float(quality.get("max_price") or float("inf"))
    buckets: dict[datetime, dict[str, Any]] = {}
    session_counts: dict[datetime, Counter[str]] = defaultdict(Counter)

    with source_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = parse_dt(str(row["timestamp"]))
            if timestamp < start or timestamp > end:
                continue
            open_price = float(row["open"])
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            if (
                open_price < min_price
                or high < min_price
                or low < min_price
                or close < min_price
                or open_price > max_price
                or high > max_price
                or low > max_price
                or close > max_price
            ):
                continue
            bucket = bucket_time(timestamp, timeframe)
            current = buckets.get(bucket)
            if current is None:
                buckets[bucket] = {
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": float(row.get("volume") or 0.0),
                    "last_timestamp": timestamp,
                }
            else:
                current["high"] = max(float(current["high"]), high)
                current["low"] = min(float(current["low"]), low)
                current["volume"] = float(current["volume"]) + float(row.get("volume") or 0.0)
                if timestamp >= current["last_timestamp"]:
                    current["close"] = close
                    current["last_timestamp"] = timestamp
            session_counts[bucket][str(row.get("session") or "unknown")] += 1

    bars: list[Bar] = []
    for bucket in sorted(buckets):
        payload = buckets[bucket]
        session = (session_counts[bucket].most_common(1)[0][0] if session_counts[bucket] else "unknown")
        bars.append(
            Bar(
                bucket=bucket,
                open=float(payload["open"]),
                high=float(payload["high"]),
                low=float(payload["low"]),
                close=float(payload["close"]),
                volume=float(payload["volume"]),
                session=session,
            )
        )
    return bars


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def y_for_price(price: float, *, min_price: float, max_price: float) -> float:
    span = max(0.000001, max_price - min_price)
    return PRICE_ROI["top"] + ((max_price - price) / span) * (PRICE_ROI["bottom"] - PRICE_ROI["top"])


def x_for_index(index: int, *, bar_count: int) -> float:
    span = PRICE_ROI["right"] - PRICE_ROI["left"]
    return PRICE_ROI["left"] + ((index + 0.5) / max(1, bar_count)) * span


def bbox_for_price_zone(
    *,
    index: int,
    bar_count: int,
    price_center: float,
    price_height: float,
    min_price: float,
    max_price: float,
    width_bars: float = 3.0,
) -> list[float]:
    y_center = y_for_price(price_center, min_price=min_price, max_price=max_price)
    price_span = max(0.000001, max_price - min_price)
    width = clamp((width_bars / max(1, bar_count)) * (PRICE_ROI["right"] - PRICE_ROI["left"]), 0.014, 0.085)
    height = clamp((price_height / price_span) * (PRICE_ROI["bottom"] - PRICE_ROI["top"]), 0.022, 0.12)
    return [
        round(clamp(x_for_index(index, bar_count=bar_count), width / 2.0, 1.0 - (width / 2.0)), 6),
        round(clamp(y_center, height / 2.0, 1.0 - (height / 2.0)), 6),
        round(width, 6),
        round(height, 6),
    ]


def atr_proxy(bars: list[Bar]) -> float:
    ranges = [max(0.000001, bar.high - bar.low) for bar in bars]
    return max(0.000001, float(median(ranges))) if ranges else 0.000001


def detect_price_action_primitives(bars: list[Bar]) -> list[dict[str, Any]]:
    if len(bars) < 16:
        return []
    atr = atr_proxy(bars)
    min_price = min(bar.low for bar in bars)
    max_price = max(bar.high for bar in bars)
    detections: list[dict[str, Any]] = []
    lookback = min(10, max(4, len(bars) // 12))

    for index in range(lookback, len(bars)):
        bar = bars[index]
        previous = bars[max(0, index - lookback) : index]
        previous_high = max(item.high for item in previous)
        previous_low = min(item.low for item in previous)
        high_excursion = bar.high - previous_high
        low_excursion = previous_low - bar.low
        if high_excursion > atr * 0.12 and bar.close < previous_high:
            confidence = clamp(0.74 + min(0.18, high_excursion / max(atr * 8.0, 0.000001)), 0.74, 0.92)
            detections.append(
                {
                    "class_id": YOLO_CLASS_TO_ID["liquidity_sweep_high"],
                    "class_name": "liquidity_sweep_high",
                    "bbox": bbox_for_price_zone(
                        index=index,
                        bar_count=len(bars),
                        price_center=(bar.high + previous_high) / 2.0,
                        price_height=max(atr * 1.6, high_excursion * 1.4),
                        min_price=min_price,
                        max_price=max_price,
                    ),
                    "confidence": round(confidence, 4),
                    "rule": "swept_prior_high_and_closed_back_below",
                    "bar_time": bar.bucket.isoformat(),
                }
            )
        if low_excursion > atr * 0.12 and bar.close > previous_low:
            confidence = clamp(0.74 + min(0.18, low_excursion / max(atr * 8.0, 0.000001)), 0.74, 0.92)
            detections.append(
                {
                    "class_id": YOLO_CLASS_TO_ID["liquidity_sweep_low"],
                    "class_name": "liquidity_sweep_low",
                    "bbox": bbox_for_price_zone(
                        index=index,
                        bar_count=len(bars),
                        price_center=(bar.low + previous_low) / 2.0,
                        price_height=max(atr * 1.6, low_excursion * 1.4),
                        min_price=min_price,
                        max_price=max_price,
                    ),
                    "confidence": round(confidence, 4),
                    "rule": "swept_prior_low_and_closed_back_above",
                    "bar_time": bar.bucket.isoformat(),
                }
            )

    pivot_window = 2
    for index in range(pivot_window, len(bars) - pivot_window):
        bar = bars[index]
        neighbors = bars[index - pivot_window : index] + bars[index + 1 : index + pivot_window + 1]
        if bar.high > max(item.high for item in neighbors):
            detections.append(
                {
                    "class_id": YOLO_CLASS_TO_ID["protected_swing"],
                    "class_name": "protected_swing",
                    "bbox": bbox_for_price_zone(
                        index=index,
                        bar_count=len(bars),
                        price_center=bar.high,
                        price_height=atr * 1.5,
                        min_price=min_price,
                        max_price=max_price,
                        width_bars=2.5,
                    ),
                    "confidence": 0.705,
                    "rule": "local_pivot_high",
                    "bar_time": bar.bucket.isoformat(),
                }
            )
        if bar.low < min(item.low for item in neighbors):
            detections.append(
                {
                    "class_id": YOLO_CLASS_TO_ID["protected_swing"],
                    "class_name": "protected_swing",
                    "bbox": bbox_for_price_zone(
                        index=index,
                        bar_count=len(bars),
                        price_center=bar.low,
                        price_height=atr * 1.5,
                        min_price=min_price,
                        max_price=max_price,
                        width_bars=2.5,
                    ),
                    "confidence": 0.705,
                    "rule": "local_pivot_low",
                    "bar_time": bar.bucket.isoformat(),
                }
            )

    detections.sort(key=lambda item: (float(item["confidence"]), item["bbox"][2] * item["bbox"][3]), reverse=True)
    selected: list[dict[str, Any]] = []
    seen_classes: set[int] = set()
    for detection in detections:
        class_id = int(detection["class_id"])
        if class_id in seen_classes and class_id != YOLO_CLASS_TO_ID["protected_swing"]:
            continue
        selected.append(detection)
        seen_classes.add(class_id)
        if len(selected) >= 3:
            break
    return selected


def answer_for_image(root_dir: Path, image: dict[str, Any], bars: list[Bar]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    image_id = str(image.get("image_id") or "").strip()
    image_path = resolve(root_dir, str(image.get("image_path") or ""))
    quality = image.get("quality_filter", {}) if isinstance(image.get("quality_filter"), dict) else {}
    removed_ratio = float(quality.get("removed_ratio") or 0.0)
    report = {
        "image_id": image_id,
        "symbol": image.get("symbol"),
        "timeframe": image.get("timeframe"),
        "image_path": relative_or_absolute(image_path, root_dir),
        "bar_count": len(bars),
        "quality_filter_removed_ratio": removed_ratio,
    }
    if not image_path.exists():
        report["status"] = "missing_image"
        return None, report
    if removed_ratio > MAX_HIGH_CONFIDENCE_QUALITY_FILTER_REMOVED_RATIO:
        report["status"] = "quality_filter_removed_ratio_too_high"
        return None, report
    detections = detect_price_action_primitives(bars)
    high_confidence = [item for item in detections if float(item.get("confidence") or 0.0) >= 0.70]
    if not high_confidence:
        report["status"] = "no_high_confidence_detections"
        return None, report
    min_confidence = min(float(item["confidence"]) for item in high_confidence)
    report.update(
        {
            "status": "auto_promoted_high_confidence",
            "detection_count": len(high_confidence),
            "min_confidence": round(min_confidence, 4),
            "class_counts": dict(Counter(str(item["class_name"]) for item in high_confidence)),
        }
    )
    end_value = (image.get("visible_range") or {}).get("end") if isinstance(image.get("visible_range"), dict) else ""
    time_index = int(parse_dt(str(end_value)).timestamp()) if end_value else 0
    return (
        {
            "example_id": image_id,
            "image_path": relative_or_absolute(image_path, root_dir),
            "time_index": time_index,
            "detections": [
                {"class_id": int(item["class_id"]), "bbox": item["bbox"]}
                for item in high_confidence
            ],
            "review_outcome": "accepted",
            "note": (
                f"Auto-promoted high-confidence controlled OHLC pseudo label; "
                f"source={MODEL_VERSION}; min_confidence={min_confidence:.3f}."
            ),
            "source": "controlled_chart_auto_pseudo_label",
            "promotion_type": "auto_promoted_high_confidence",
            "weak_supervision": True,
            "symbol": image.get("symbol"),
            "timeframe": image.get("timeframe"),
            "confidence": round(min_confidence, 4),
        },
        report,
    )


def flatten_images(lineage_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for item in lineage_manifest.get("items", []):
        if not isinstance(item, dict):
            continue
        for image in item.get("images", []):
            if isinstance(image, dict):
                images.append(image)
    return images


def dominant_direction(answers: list[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    counts = Counter()
    latest_directional_signal: tuple[float, str] | None = None
    timeframe_rank = {"1d": 1.0, "1h": 2.0, "5m": 3.0}
    for answer in answers:
        timeframe = str(answer.get("timeframe") or "").lower()
        rank = timeframe_rank.get(timeframe, 0.0)
        for detection in answer.get("detections", []):
            class_name = YOLO_CLASS_NAMES[int(detection["class_id"])]
            bbox = [float(value) for value in detection.get("bbox", [])]
            x_center = bbox[0] if bbox else 0.0
            if class_name in {"liquidity_sweep_low", "bullish_reaction_zone"}:
                counts["bullish"] += 1
                priority = rank * 10.0 + x_center
                if latest_directional_signal is None or priority > latest_directional_signal[0]:
                    latest_directional_signal = (priority, "bullish")
            if class_name in {"liquidity_sweep_high", "bearish_reaction_zone"}:
                counts["bearish"] += 1
                priority = rank * 10.0 + x_center
                if latest_directional_signal is None or priority > latest_directional_signal[0]:
                    latest_directional_signal = (priority, "bearish")
    if counts["bullish"] > counts["bearish"]:
        return "bullish", dict(counts)
    if counts["bearish"] > counts["bullish"]:
        return "bearish", dict(counts)
    if latest_directional_signal is not None:
        counts[f"tie_break_latest_ltf_{latest_directional_signal[1]}"] += 1
        return latest_directional_signal[1], dict(counts)
    return "none", dict(counts)


def build_auto_state_fixtures(
    *,
    root_dir: Path,
    lineage_manifest: dict[str, Any],
    answers: list[dict[str, Any]],
) -> dict[str, Any]:
    answers_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for answer in answers:
        answers_by_symbol[str(answer.get("symbol") or "")].append(answer)
    image_paths_by_symbol: dict[str, dict[str, str]] = defaultdict(dict)
    session_by_symbol: dict[str, str] = {}
    for image in flatten_images(lineage_manifest):
        symbol = str(image.get("symbol") or "")
        timeframe = str(image.get("timeframe") or "")
        key = {"1D": "daily", "1h": "h1", "5m": "m5"}.get(timeframe)
        if key:
            image_paths_by_symbol[symbol][key] = str(image.get("image_path") or "")
        session_payload = image.get("session", {}) if isinstance(image.get("session"), dict) else {}
        if timeframe == "5m":
            session_by_symbol[symbol] = str(session_payload.get("dominant") or "unknown")

    fixtures: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    for symbol, symbol_answers in sorted(answers_by_symbol.items()):
        chart_paths = image_paths_by_symbol.get(symbol, {})
        if not all(key in chart_paths for key in ("daily", "h1", "m5")):
            skipped["missing_timeframe_chart_paths"] += 1
            continue
        direction, direction_counts = dominant_direction(symbol_answers)
        if direction == "none":
            skipped["direction_tie_or_missing"] += 1
            continue
        confidence = min(float(answer.get("confidence") or 0.0) for answer in symbol_answers)
        row = {
            "bundle_id": f"controlled_auto_state::{symbol}",
            "cue_summary": f"Auto state fixture from controlled ES/NQ/GC OHLC pseudo labels for {symbol}.",
            "detector_boxes_by_frame": {
                str(answer.get("timeframe") or ""): answer.get("detections", [])
                for answer in symbol_answers
            },
            "direction": direction,
            "entry_state": "wait",
            "fractal_stage": "c3",
            "htf_bias": direction,
            "htf_frame_path": chart_paths["daily"],
            "htf_timeframe": "1D",
            "invalidation_state": "intact",
            "itf_frame_path": chart_paths["h1"],
            "itf_timeframe": "1h",
            "kill_zone_alignment": "neutral",
            "label_confidence": confidence,
            "ltf_frame_path": chart_paths["m5"],
            "ltf_timeframe": "5m",
            "path_family": "reversal",
            "poi_direction": direction,
            "poi_source": "rule_derived",
            "poi_type": "liquidity_target_zone",
            "poi_validity": True,
            "review_outcome": "adjusted",
            "session_context": session_by_symbol.get(symbol, "unknown") if session_by_symbol.get(symbol) in {"london", "new_york"} else "unknown",
            "setup_quality": "good_setup",
            "source": "controlled_chart_auto_pseudo_label",
            "source_path": "results/controlled_charts/auto_pseudo_labels.json",
            "source_pointer": symbol,
            "auto_promotion_type": "auto_promoted_high_confidence",
            "direction_counts": direction_counts,
        }
        fixtures.append(fixture_from_row(root_dir=root_dir, row=row, labels={key: str(row[key]) for key in (
            "path_family",
            "fractal_stage",
            "direction",
            "htf_bias",
            "poi_type",
            "poi_direction",
            "poi_source",
            "setup_quality",
            "entry_state",
            "invalidation_state",
            "session_context",
            "kill_zone_alignment",
        )}, index=len(fixtures) + 1))

    verdict_counts = Counter(fixture["expected_decision"]["verdict"] for fixture in fixtures)
    missing_counts = Counter(
        missing
        for fixture in fixtures
        for missing in fixture["expected_state"]["missing_evidence"]
    )
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Auto-promoted deterministic state-builder fixtures from controlled OHLC pseudo labels.",
        "source": MODEL_VERSION,
        "review_policy": {
            "manual_review_required": False,
            "weak_supervision": True,
            "promotion_type": "auto_promoted_high_confidence",
        },
        "summary": {
            "fixture_gate": "pass" if fixtures else "blocked",
            "fixture_count": len(fixtures),
            "skipped_counts": dict(sorted(skipped.items())),
            "expected_decision_counts": dict(sorted(verdict_counts.items())),
            "missing_evidence_counts": dict(sorted(missing_counts.items())),
        },
        "fixtures": fixtures,
    }


def build_auto_promotion_lane(
    *,
    root_dir: Path,
    lineage_manifest_path: Path = DEFAULT_LINEAGE_MANIFEST,
    output_answers_path: Path = DEFAULT_OUTPUT_ANSWERS,
    output_state_fixtures_path: Path = DEFAULT_OUTPUT_STATE_FIXTURES,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    root_dir = root_dir.resolve()
    lineage_path = resolve(root_dir, lineage_manifest_path)
    lineage_manifest = read_json(lineage_path)
    answers: list[dict[str, Any]] = []
    image_reports: list[dict[str, Any]] = []
    for image in flatten_images(lineage_manifest):
        bars = load_bars_for_image(root_dir, image)
        answer, report = answer_for_image(root_dir, image, bars)
        image_reports.append(report)
        if answer is not None:
            answers.append(answer)

    answer_payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "controlled_chart_auto_pseudo_labels",
        "source_lineage_manifest": relative_or_absolute(lineage_path, root_dir),
        "model_version": MODEL_VERSION,
        "review_policy": {
            "manual_review_required": False,
            "weak_supervision": True,
            "not_human_reviewed": True,
            "promotion_type": "auto_promoted_high_confidence",
        },
        "items": answers,
    }
    output_answers = resolve(root_dir, output_answers_path)
    output_answers.parent.mkdir(parents=True, exist_ok=True)
    output_answers.write_text(json.dumps(answer_payload, indent=2) + "\n", encoding="utf-8")
    validated = load_supervision_answers(output_answers)
    class_counts = Counter(
        YOLO_CLASS_NAMES[int(detection["class_id"])]
        for answer in answers
        for detection in answer.get("detections", [])
    )
    status_counts = Counter(str(report.get("status")) for report in image_reports)
    report_payload = {
        "schema_version": "1.0.0",
        "generated_at": answer_payload["generated_at"],
        "mode": "controlled_chart_auto_promotion_report",
        "source_lineage_manifest": answer_payload["source_lineage_manifest"],
        "output_answers_path": relative_or_absolute(output_answers, root_dir),
        "model_version": MODEL_VERSION,
        "image_count": len(image_reports),
        "answer_item_count": len(answers),
        "validated_trainable_item_count": len(validated),
        "status_counts": dict(sorted(status_counts.items())),
        "class_counts": dict(sorted(class_counts.items())),
        "auto_training_gate": "pass" if validated else "blocked_no_high_confidence_pseudo_labels",
        "image_reports": image_reports,
    }
    state_fixtures = build_auto_state_fixtures(
        root_dir=root_dir,
        lineage_manifest=lineage_manifest,
        answers=answers,
    )
    state_output = resolve(root_dir, output_state_fixtures_path)
    state_output.parent.mkdir(parents=True, exist_ok=True)
    state_output.write_text(json.dumps(state_fixtures, indent=2) + "\n", encoding="utf-8")
    report_payload["output_state_fixtures_path"] = relative_or_absolute(state_output, root_dir)
    report_payload["auto_state_fixture_count"] = state_fixtures["summary"]["fixture_count"]
    return answer_payload, report_payload, state_fixtures


def write_report(report: dict[str, Any], *, root_dir: Path, output_report_path: Path) -> None:
    output = resolve(root_dir, output_report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build controlled-chart auto pseudo labels and auto state fixtures.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--lineage-manifest", type=Path, default=DEFAULT_LINEAGE_MANIFEST)
    parser.add_argument("--output-answers", type=Path, default=DEFAULT_OUTPUT_ANSWERS)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-state-fixtures", type=Path, default=DEFAULT_OUTPUT_STATE_FIXTURES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    _answers, report, state_fixtures = build_auto_promotion_lane(
        root_dir=root_dir,
        lineage_manifest_path=args.lineage_manifest,
        output_answers_path=args.output_answers,
        output_state_fixtures_path=args.output_state_fixtures,
    )
    write_report(report, root_dir=root_dir, output_report_path=args.output_report)
    print(
        "Built controlled-chart auto promotion lane: "
        f"{relative_or_absolute(resolve(root_dir, args.output_answers), root_dir)} "
        f"validated_trainable={report['validated_trainable_item_count']} "
        f"auto_state_fixtures={state_fixtures['summary']['fixture_count']} "
        f"gate={report['auto_training_gate']}"
    )


if __name__ == "__main__":
    main()
