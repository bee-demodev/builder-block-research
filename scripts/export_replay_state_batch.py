from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.harness import load_bars_csv, parse_timestamp
from runtime.replay_harness import ReplayFrame, build_replay_frames


def load_candidate_events(path: Path) -> list[dict[str, Any]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        return list(loaded.get("events", []))
    if isinstance(loaded, list):
        return loaded
    raise ValueError("Candidate events must be a list or a {'events': [...]} object.")


def normalize_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def latest_bar_direction(open_price: float, close_price: float) -> str:
    if close_price > open_price:
        return "bullish"
    if close_price < open_price:
        return "bearish"
    return "flat"


def latest_close_location(*, low: float, high: float, close: float) -> str:
    bar_range = high - low
    if bar_range <= 0:
        return "mid"
    fraction = (close - low) / bar_range
    if fraction >= 0.67:
        return "upper"
    if fraction <= 0.33:
        return "lower"
    return "mid"


def build_replay_frame_lookup(
    *,
    bars_path: Path,
    warmup_bars: int,
    session_mode: str,
) -> tuple[list[Any], dict[str, ReplayFrame]]:
    bars = load_bars_csv(bars_path)
    frames = build_replay_frames(
        bars,
        warmup_bars=warmup_bars,
        session_mode=session_mode,
    )
    return bars, {frame.timestamp: frame for frame in frames}


def build_replay_observation(*, bars: list[Any], frame: ReplayFrame) -> dict[str, Any]:
    visible_bars = bars[frame.visible_start_index : frame.visible_end_index + 1]
    first_bar = visible_bars[0]
    last_bar = visible_bars[-1]
    visible_high = max(float(bar.high) for bar in visible_bars)
    visible_low = min(float(bar.low) for bar in visible_bars)
    last_range = float(last_bar.high) - float(last_bar.low)
    last_body = float(last_bar.close) - float(last_bar.open)
    return {
        "session_bucket": frame.session_bucket,
        "visible_start_timestamp": first_bar.timestamp.isoformat(),
        "visible_end_timestamp": last_bar.timestamp.isoformat(),
        "visible_bar_count": frame.visible_bar_count,
        "visible_high": round(visible_high, 6),
        "visible_low": round(visible_low, 6),
        "visible_net_change": round(float(last_bar.close) - float(first_bar.open), 6),
        "latest_bar_direction": latest_bar_direction(float(last_bar.open), float(last_bar.close)),
        "latest_close_location": latest_close_location(
            low=float(last_bar.low),
            high=float(last_bar.high),
            close=float(last_bar.close),
        ),
        "latest_bar_range": round(last_range, 6),
        "latest_bar_body": round(last_body, 6),
    }


def build_candidate_signal(
    event: dict[str, Any],
    *,
    frame: ReplayFrame,
) -> dict[str, Any]:
    candidate_signal = event.get("candidate_signal")
    if isinstance(candidate_signal, dict):
        payload = dict(candidate_signal)
    else:
        payload = {}

    payload.setdefault("timestamp", event.get("timestamp") or frame.timestamp)
    payload.setdefault("side", event.get("side"))
    payload.setdefault("stop_price", event.get("stop_price"))
    payload.setdefault("target_price", event.get("target_price"))
    payload.setdefault("quantity", event.get("quantity", 1.0))
    payload.setdefault("session", event.get("session") or frame.session_bucket)
    if "thesis" not in payload and event.get("thesis"):
        payload["thesis"] = event.get("thesis")
    return payload


def build_state_from_event(
    event: dict[str, Any],
    *,
    bars: list[Any],
    frame: ReplayFrame,
) -> dict[str, Any]:
    existing_chart_context = event.get("chart_context")
    chart_context = dict(existing_chart_context) if isinstance(existing_chart_context, dict) else {}
    annotation = dict(event.get("annotation")) if isinstance(event.get("annotation"), dict) else {}
    replay_observation = build_replay_observation(bars=bars, frame=frame)

    rule_states = event.get("rule_states")
    if isinstance(rule_states, dict):
        annotation["rule_states"] = dict(rule_states)
    annotation["replay_observation"] = replay_observation

    chart_context["setup_variant"] = str(
        event.get("setup_variant")
        or chart_context.get("setup_variant")
        or chart_context.get("pattern_variant")
        or ""
    ).strip()
    chart_context["source_kind"] = str(
        event.get("source_kind")
        or chart_context.get("source_kind")
        or "runtime_replay"
    ).strip()
    chart_context["timeframe_scope"] = normalize_string_list(
        event.get("timeframe_scope") or chart_context.get("timeframe_scope")
    )
    chart_context["session_scope"] = normalize_string_list(
        event.get("session_scope") or chart_context.get("session_scope")
    ) or [frame.session_bucket]
    chart_context["replay_window"] = {
        key: replay_observation[key]
        for key in (
            "visible_start_timestamp",
            "visible_end_timestamp",
            "visible_bar_count",
            "visible_high",
            "visible_low",
            "visible_net_change",
        )
    }

    candidate_signal = build_candidate_signal(event, frame=frame)
    trade_model = str(event.get("trade_model") or "").strip()
    case_ref = str(event.get("case_ref") or "").strip()
    if not case_ref:
        case_ref = f"replay::{trade_model or 'unknown'}::{frame.timestamp}"

    return {
        "case_ref": case_ref,
        "profile_slug": str(event.get("profile_slug", "")).strip(),
        "topic": str(event.get("topic", "")).strip(),
        "trade_model": trade_model,
        "relation_type": str(event.get("relation_type", "")).strip(),
        "chart_context": chart_context,
        "annotation": annotation,
        "candidate_signal": candidate_signal,
    }


def build_state_batch_from_events(
    *,
    bars_path: Path,
    candidate_events_path: Path,
    warmup_bars: int = 20,
    session_mode: str = "all",
) -> dict[str, Any]:
    events = load_candidate_events(candidate_events_path)
    bars, frame_lookup = build_replay_frame_lookup(
        bars_path=bars_path,
        warmup_bars=warmup_bars,
        session_mode=session_mode,
    )

    states: list[dict[str, Any]] = []
    missing_case_refs: list[str] = []
    for index, event in enumerate(events):
        raw_timestamp = (
            (event.get("candidate_signal") or {}).get("timestamp")
            if isinstance(event.get("candidate_signal"), dict)
            else None
        ) or event.get("timestamp")
        if not raw_timestamp:
            raw_timestamp = ""
        frame = frame_lookup.get(parse_timestamp(str(raw_timestamp)).isoformat()) if raw_timestamp else None
        if frame is None:
            case_ref = str(event.get("case_ref") or f"event_{index}")
            missing_case_refs.append(case_ref)
            continue
        states.append(build_state_from_event(event, bars=bars, frame=frame))

    return {
        "states": states,
        "summary": {
            "bars_path": str(bars_path),
            "candidate_events_path": str(candidate_events_path),
            "warmup_bars": warmup_bars,
            "session_mode": session_mode,
            "event_count": len(events),
            "emitted_state_count": len(states),
            "missing_frame_count": len(missing_case_refs),
            "missing_case_refs": missing_case_refs,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build model-ready replay states from candidate rule events and historical bars so "
            "the neural bridge can score realistic runtime snapshots."
        )
    )
    parser.add_argument("--bars", required=True)
    parser.add_argument("--candidate-events", required=True)
    parser.add_argument("--warmup-bars", type=int, default=20)
    parser.add_argument("--session-mode", default="all")
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_state_batch_from_events(
        bars_path=Path(args.bars),
        candidate_events_path=Path(args.candidate_events),
        warmup_bars=args.warmup_bars,
        session_mode=args.session_mode,
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
