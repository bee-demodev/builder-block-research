from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from export_replay_state_batch import build_state_batch_from_events
from runtime.harness import CostModel, Side, TradeSignal, load_bars_csv, parse_timestamp, run_backtest
from score_state_batch_to_signals import score_states_to_signals


def load_state_batch(path: Path) -> list[dict[str, Any]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        return list(loaded.get("states", []))
    if isinstance(loaded, list):
        return loaded
    raise ValueError("State batch must be a list or a {'states': [...]} object.")


def signals_payload_to_runtime(signals: list[dict[str, Any]]) -> list[TradeSignal]:
    runtime_signals: list[TradeSignal] = []
    for signal in signals:
        runtime_signals.append(
            TradeSignal(
                timestamp=parse_timestamp(signal["timestamp"]),
                side=Side(str(signal["side"]).strip().lower()),
                stop_price=float(signal["stop_price"]),
                target_price=float(signal["target_price"]),
                quantity=float(signal.get("quantity", 1.0) or 1.0),
                thesis=str(signal.get("thesis", "")).strip(),
                session=str(signal.get("session", "")).strip() or None,
            )
        )
    return runtime_signals


def resolve_state_batch(
    *,
    bars_path: Path,
    states_path: Path | None,
    candidate_events_path: Path | None,
    warmup_bars: int,
    session_mode: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if (states_path is None) == (candidate_events_path is None):
        raise ValueError("Provide exactly one of states_path or candidate_events_path.")

    if states_path is not None:
        states = load_state_batch(states_path)
        return states, {
            "source": "states_path",
            "path": str(states_path),
            "summary": {
                "event_count": len(states),
                "emitted_state_count": len(states),
                "missing_frame_count": 0,
                "missing_case_refs": [],
            },
        }

    payload = build_state_batch_from_events(
        bars_path=bars_path,
        candidate_events_path=candidate_events_path,
        warmup_bars=warmup_bars,
        session_mode=session_mode,
    )
    return list(payload["states"]), {
        "source": "candidate_events",
        "path": str(candidate_events_path),
        "summary": payload["summary"],
    }


def build_model_assisted_backtest(
    *,
    bars_path: Path,
    model_path: Path,
    threshold: float,
    states_path: Path | None = None,
    candidate_events_path: Path | None = None,
    warmup_bars: int = 20,
    device_preference: str = "auto",
    cost_model: CostModel | None = None,
    session_mode: str = "all",
) -> dict[str, Any]:
    states, state_batch = resolve_state_batch(
        bars_path=bars_path,
        states_path=states_path,
        candidate_events_path=candidate_events_path,
        warmup_bars=warmup_bars,
        session_mode=session_mode,
    )
    scoring = score_states_to_signals(
        states,
        model_path=model_path,
        device_preference=device_preference,
        threshold=threshold,
    )
    runtime_signals = signals_payload_to_runtime(scoring["signals"])
    backtest_result = run_backtest(
        load_bars_csv(bars_path),
        runtime_signals,
        cost_model=cost_model,
        session_mode=session_mode,
    )

    return {
        "bars_path": str(bars_path),
        "states_path": str(states_path) if states_path else "",
        "candidate_events_path": str(candidate_events_path) if candidate_events_path else "",
        "model_path": str(model_path),
        "threshold": threshold,
        "state_batch": {
            "source": state_batch["source"],
            "path": state_batch["path"],
            "state_count": len(states),
            "summary": state_batch["summary"],
        },
        "scoring": {
            "task_name": scoring["task_name"],
            "state_count": scoring["state_count"],
            "accepted_signal_count": scoring["accepted_signal_count"],
            "scores": scoring["scores"],
        },
        "signals": {
            "signals": scoring["signals"],
        },
        "backtest": backtest_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a model-assisted historical backtest by scoring structured chart states, "
            "emitting accepted signals, and sending them through the existing next-bar harness."
        )
    )
    parser.add_argument("--bars", required=True)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--states")
    source_group.add_argument("--candidate-events")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--session-mode", default="all")
    parser.add_argument("--warmup-bars", type=int, default=20)
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--spread-ticks", type=float, default=1.0)
    parser.add_argument("--slippage-ticks", type=float, default=0.5)
    parser.add_argument("--commission-per-contract", type=float, default=0.0)
    parser.add_argument("--contract-multiplier", type=float, default=1.0)
    parser.add_argument("--output", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analysis = build_model_assisted_backtest(
        bars_path=Path(args.bars),
        model_path=Path(args.model_path),
        threshold=args.threshold,
        states_path=Path(args.states) if args.states else None,
        candidate_events_path=Path(args.candidate_events) if args.candidate_events else None,
        warmup_bars=args.warmup_bars,
        device_preference=args.device,
        cost_model=CostModel(
            tick_size=args.tick_size,
            spread_ticks=args.spread_ticks,
            slippage_ticks=args.slippage_ticks,
            commission_per_contract=args.commission_per_contract,
            contract_multiplier=args.contract_multiplier,
        ),
        session_mode=args.session_mode,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")

    print(json.dumps(analysis["backtest"]["summary"], indent=2))


if __name__ == "__main__":
    main()
