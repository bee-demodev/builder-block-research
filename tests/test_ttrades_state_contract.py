import json
from pathlib import Path
from typing import Any

from fractal_state import load_state_machine


CONTRACT_PATH = Path("data") / "ttrades_state_contract.schema.json"


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _enum(contract: dict[str, Any], name: str) -> list[str]:
    return list(contract["$defs"][name]["enum"])


def test_contract_file_exists_and_declares_runtime_handoff_shape() -> None:
    contract = _load_contract()

    assert contract["version"] == "1.0.0"
    assert contract["additionalProperties"] is False
    assert {
        "timeframes",
        "detections",
        "ttrades_state",
        "retrieval",
        "decision",
        "journal",
    }.issubset(set(contract["required"]))
    assert contract["properties"]["timeframes"]["required"] == ["daily", "h1", "m5"]


def test_contract_enums_match_fractal_state_machine() -> None:
    contract = _load_contract()
    machine = load_state_machine()

    for enum_name in (
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
    ):
        assert _enum(contract, enum_name) == list(machine.enums[enum_name])


def test_contract_detector_classes_match_locked_detector_primitives() -> None:
    contract = _load_contract()
    machine = load_state_machine()

    assert _enum(contract, "detector_class") == machine.raw["locked_decisions"]["detector_primitives"]


def test_contract_supports_decision_and_journal_error_taxonomy() -> None:
    contract = _load_contract()

    assert _enum(contract, "decision_verdict") == [
        "valid_long_setup",
        "valid_short_setup",
        "watch_only",
        "no_trade",
        "insufficient_evidence",
    ]

    journal_classification = contract["properties"]["journal"]["properties"]["classification"]["enum"]
    assert "valid_loss_part_of_odds" in journal_classification
    assert {
        "vision_error",
        "state_error",
        "retrieval_error",
        "risk_rule_error",
        "execution_error",
    }.issubset(set(journal_classification))


def test_contract_example_payload_uses_required_runtime_sections() -> None:
    contract = _load_contract()
    required = set(contract["required"])
    example = {
        "contract_version": "1.0.0",
        "engine_run_id": "example-nq-20260622-ny",
        "generated_at": "2026-06-22T13:30:00-04:00",
        "mode": "paper_decision",
        "symbol": "CME_MINI:NQ1!",
        "timeframes": {
            "daily": {
                "timeframe": "1D",
                "screenshot_path": "results/live_tradingview/nq_daily.png",
                "captured_at": "2026-06-22T13:30:00-04:00",
                "viewport": {"width": 1600, "height": 900, "device_scale_factor": 1},
                "candle_range": {"visible_candles": 90, "right_edge_time": "2026-06-22T13:30:00-04:00"},
                "status": "captured",
            },
            "h1": {
                "timeframe": "1h",
                "screenshot_path": "results/live_tradingview/nq_h1.png",
                "captured_at": "2026-06-22T13:30:00-04:00",
                "viewport": {"width": 1600, "height": 900, "device_scale_factor": 1},
                "candle_range": {"visible_candles": 120, "right_edge_time": "2026-06-22T13:30:00-04:00"},
                "status": "captured",
            },
            "m5": {
                "timeframe": "5m",
                "screenshot_path": "results/live_tradingview/nq_m5.png",
                "captured_at": "2026-06-22T13:30:00-04:00",
                "viewport": {"width": 1600, "height": 900, "device_scale_factor": 1},
                "candle_range": {"visible_candles": 180, "right_edge_time": "2026-06-22T13:30:00-04:00"},
                "status": "captured",
            },
        },
        "detections": {
            "model": {
                "name": "yolo26_ttrades_markup",
                "weights_path": "models/yolo26_ttrades_markup_best.pt",
                "onnx_path": "models/yolo26_ttrades_markup_best.onnx",
                "confidence_threshold": 0.25,
                "iou_threshold": 0.7,
            },
            "classes": ["liquidity_sweep_high", "protected_swing", "bearish_reaction_zone"],
            "by_timeframe": {
                "daily": [],
                "h1": [],
                "m5": [
                    {
                        "class_name": "protected_swing",
                        "confidence": 0.76,
                        "bbox_xyxy": [120.0, 320.0, 220.0, 410.0],
                        "source": "yolo",
                    }
                ],
            },
            "latency_ms": 24.5,
        },
        "ttrades_state": {
            "path_family": "reversal",
            "direction": "bearish",
            "fractal_stage": "c3",
            "htf_bias": "bearish",
            "timeframe_alignment": {"daily": "bearish", "h1": "bearish", "m5": "bearish", "is_aligned": True},
            "poi": {"type": "reaction_zone", "direction": "bearish", "source": "detector", "validity": True},
            "setup_quality": "bad_setup",
            "entry_state": "wait",
            "invalidation": {"state": "intact", "reason": "Protected swing remains intact."},
            "session_context": "new_york",
            "kill_zone_alignment": "neutral",
            "state_confidence": 0.68,
            "missing_evidence": ["Needs C4 entry-ready confirmation."],
        },
        "retrieval": {
            "query_text": "bearish reversal c3 after high sweep",
            "neighbors": [],
            "evidence_summary": ["No directly matched validated C4 analog yet."],
            "knowledge_base_versions": {"ttfm_video_corpus": "local"},
        },
        "decision": {
            "verdict": "watch_only",
            "confidence": 0.62,
            "reasons": ["C3 state without C4 entry-ready confirmation."],
            "blocking_conditions": ["Entry state is wait."],
            "risk": {
                "entry_price": None,
                "stop_price": None,
                "target_price": None,
                "max_risk_r": None,
                "position_size_contracts": None,
            },
        },
        "journal": {
            "status": "pending_outcome",
            "outcome": "unknown",
            "classification": "not_reviewed",
            "notes": [],
            "follow_up_labels": ["collect_c4_confirmation_case"],
        },
    }

    assert required == set(example)
    assert set(example["timeframes"]) == {"daily", "h1", "m5"}
    assert example["decision"]["verdict"] in _enum(contract, "decision_verdict")
