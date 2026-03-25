from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_alert_payloads(path: Path) -> list[dict[str, Any]]:
    loaded = load_json(path)
    if isinstance(loaded, list):
        return loaded
    if isinstance(loaded, dict):
        if "alerts" in loaded:
            return list(loaded.get("alerts", []))
        return [loaded]
    raise ValueError("Alert payload must be a list, a single alert object, or an {'alerts': [...]} object.")


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def alert_title_from_payload(alert_payload: dict[str, Any]) -> str:
    return str(
        alert_payload.get("alert_title")
        or alert_payload.get("alert_name")
        or ""
    ).strip()


def build_candidate_signal_updates(alert_payload: dict[str, Any]) -> dict[str, Any]:
    updates = dict(alert_payload.get("candidate_signal")) if isinstance(alert_payload.get("candidate_signal"), dict) else {}
    for key in ("timestamp", "side", "stop_price", "target_price", "quantity", "session", "thesis"):
        if key in alert_payload and key not in updates:
            updates[key] = alert_payload[key]
    return updates


def build_candidate_event(contract: dict[str, Any], alert_payload: dict[str, Any]) -> dict[str, Any]:
    alert_title = alert_title_from_payload(alert_payload)
    allowed_alerts = [str(item).strip() for item in contract.get("alert_titles", []) if str(item).strip()]
    if allowed_alerts and alert_title not in allowed_alerts:
        raise ValueError(f"Alert title '{alert_title}' is not allowed for contract {contract.get('spec_key', '')}.")

    event = copy.deepcopy(contract.get("default_event", {}))
    if not isinstance(event, dict):
        raise ValueError("Contract must define a default_event object.")

    for key in ("profile_slug", "topic", "trade_model", "relation_type"):
        if key in alert_payload and alert_payload.get(key) not in (None, ""):
            event[key] = alert_payload[key]

    chart_context_updates = dict(alert_payload.get("chart_context")) if isinstance(alert_payload.get("chart_context"), dict) else {}
    event["chart_context"] = deep_merge(dict(event.get("chart_context", {})), chart_context_updates)

    annotation_updates = dict(alert_payload.get("annotation")) if isinstance(alert_payload.get("annotation"), dict) else {}
    if isinstance(alert_payload.get("rule_states"), dict):
        base_rule_states = dict(event.get("annotation", {}).get("rule_states", {}))
        annotation_updates["rule_states"] = deep_merge(base_rule_states, dict(alert_payload["rule_states"]))
    event["annotation"] = deep_merge(dict(event.get("annotation", {})), annotation_updates)
    event["annotation"]["fired_alert"] = alert_title

    event["candidate_signal"] = deep_merge(
        dict(event.get("candidate_signal", {})),
        build_candidate_signal_updates(alert_payload),
    )

    session_scope = event.get("chart_context", {}).get("session_scope")
    signal_session = str(event.get("candidate_signal", {}).get("session", "")).strip()
    if isinstance(session_scope, list) and not session_scope and signal_session:
        event["chart_context"]["session_scope"] = [signal_session]

    case_ref = str(alert_payload.get("case_ref", "")).strip()
    if not case_ref:
        timestamp = str(event.get("candidate_signal", {}).get("timestamp", "")).strip() or "unknown_time"
        case_ref = f"{contract.get('spec_key', 'contract')}::{alert_title or 'alert'}::{timestamp}"
    event["case_ref"] = case_ref

    return event


def build_candidate_events_from_alerts(
    *,
    contract_path: Path,
    alerts_path: Path,
) -> dict[str, Any]:
    contract = load_json(contract_path)
    alerts = load_alert_payloads(alerts_path)
    events = [build_candidate_event(contract, alert_payload) for alert_payload in alerts]
    return {
        "events": events,
        "summary": {
            "contract_path": str(contract_path),
            "alerts_path": str(alerts_path),
            "spec_key": str(contract.get("spec_key", "")).strip(),
            "alert_count": len(alerts),
            "candidate_event_count": len(events),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build candidate-event payloads from a generated Pine candidate-event contract and "
            "one or more TradingView alert payloads."
        )
    )
    parser.add_argument("--contract-path", required=True)
    parser.add_argument("--alerts-path", required=True)
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_candidate_events_from_alerts(
        contract_path=Path(args.contract_path),
        alerts_path=Path(args.alerts_path),
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
