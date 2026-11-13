from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


from config import AppConfig, build_config
from labeler.tradingview_weak_labeler import _default_cli_runner, capture_live_tradingview_bundle


DEFAULT_PLAN_PATH = Path("results") / "tradingview_recapture_plan_20260622.json"
DEFAULT_OUTPUT_PATH = Path("results") / "tradingview_recapture_batch_20260622.json"
CaptureFunc = Callable[..., dict[str, Any]]
CliRunner = Callable[[list[str]], dict[str, Any]]
CliRunnerFactory = Callable[[AppConfig], CliRunner]


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def normalize_symbols(symbols: list[str] | tuple[str, ...] | None) -> set[str]:
    return {str(symbol).strip() for symbol in symbols or [] if str(symbol).strip()}


def select_recapture_targets(
    plan: dict[str, Any],
    *,
    limit: int,
    symbols: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    allowed_symbols = normalize_symbols(symbols)
    targets = [target for target in plan.get("recapture_targets", []) if isinstance(target, dict)]
    if allowed_symbols:
        targets = [target for target in targets if str(target.get("symbol") or "") in allowed_symbols]
    targets.sort(key=lambda row: (-float(row.get("severity_score") or 0.0), str(row.get("symbol") or ""), str(row.get("example_id") or "")))
    return targets[: max(int(limit), 0)]


def dry_run_entry(target: dict[str, Any]) -> dict[str, Any]:
    return {
        "example_id": str(target.get("example_id") or ""),
        "symbol": str(target.get("symbol") or ""),
        "severity_score": float(target.get("severity_score") or 0.0),
        "quality_flags": [str(flag) for flag in target.get("quality_flags", [])],
        "would_run": [
            f"symbol {target.get('symbol')}",
            "capture_live_tradingview_bundle(max_quality_attempts=2, allow_quality_fail=False)",
            "rerun scripts/analyze_tradingview_capture_quality.py and require review_state_labels before promotion",
        ],
    }


def execute_target(
    target: dict[str, Any],
    *,
    config: AppConfig,
    cli_runner: CliRunner,
    capture_func: CaptureFunc = capture_live_tradingview_bundle,
    allow_quality_fail: bool = False,
    max_quality_attempts: int = 2,
    retry_delay_seconds: float = 1.0,
) -> dict[str, Any]:
    symbol = str(target.get("symbol") or "").strip()
    if not symbol:
        raise ValueError(f"Recapture target is missing a symbol: {target.get('example_id')}")
    cli_runner(["symbol", symbol])
    report = capture_func(
        config,
        cli_runner=cli_runner,
        allow_quality_fail=allow_quality_fail,
        max_quality_attempts=max_quality_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    return {
        "example_id": str(target.get("example_id") or ""),
        "symbol": symbol,
        "severity_score": float(target.get("severity_score") or 0.0),
        "quality_flags": [str(flag) for flag in target.get("quality_flags", [])],
        "capture_quality_passed": bool(report.get("capture_quality_passed", False)),
        "bundle_seed_appended": bool(report.get("bundle_seed_appended", False)),
        "capture_quality_attempt_count": int(report.get("capture_quality_attempt_count") or 0),
        "capture_dir": str(report.get("capture_dir") or ""),
        "raw_capture_path": str(report.get("raw_capture_path") or ""),
        "report": report,
    }


def run_recapture_batch(
    *,
    config: AppConfig,
    plan: dict[str, Any],
    plan_path: Path,
    output_path: Path,
    limit: int,
    symbols: list[str] | tuple[str, ...] | None = None,
    execute: bool = False,
    allow_quality_fail: bool = False,
    max_quality_attempts: int = 2,
    retry_delay_seconds: float = 1.0,
    cli_runner_factory: CliRunnerFactory = _default_cli_runner,
    capture_func: CaptureFunc = capture_live_tradingview_bundle,
) -> dict[str, Any]:
    selected = select_recapture_targets(plan, limit=limit, symbols=symbols)
    results: list[dict[str, Any]] = []
    cli_runner: CliRunner | None = None
    if execute and selected:
        cli_runner = cli_runner_factory(config)
    for target in selected:
        if execute:
            assert cli_runner is not None
            try:
                result = execute_target(
                    target,
                    config=config,
                    cli_runner=cli_runner,
                    capture_func=capture_func,
                    allow_quality_fail=allow_quality_fail,
                    max_quality_attempts=max_quality_attempts,
                    retry_delay_seconds=retry_delay_seconds,
                )
                result["status"] = "captured"
            except Exception as exc:  # pragma: no cover - exercised in real capture runs.
                result = {
                    "example_id": str(target.get("example_id") or ""),
                    "symbol": str(target.get("symbol") or ""),
                    "severity_score": float(target.get("severity_score") or 0.0),
                    "quality_flags": [str(flag) for flag in target.get("quality_flags", [])],
                    "status": "error",
                    "error": str(exc),
                }
        else:
            result = dry_run_entry(target)
            result["status"] = "dry_run"
        results.append(result)
    summary = {
        "selected_count": len(selected),
        "dry_run": not execute,
        "captured_count": sum(1 for row in results if row.get("status") == "captured"),
        "error_count": sum(1 for row in results if row.get("status") == "error"),
        "quality_passed_count": sum(1 for row in results if row.get("capture_quality_passed") is True),
        "bundle_seed_appended_count": sum(1 for row in results if row.get("bundle_seed_appended") is True),
    }
    batch = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "execute" if execute else "dry_run",
        "source_plan_path": relative_or_absolute(plan_path, config.root_dir),
        "policy": {
            "dry_run_default": True,
            "training_gate": "Recaptured rows must pass capture quality and still require visual promotion before training.",
            "allow_quality_fail": allow_quality_fail,
            "max_quality_attempts": max_quality_attempts,
        },
        "selection": {
            "limit": int(limit),
            "symbols": sorted(normalize_symbols(symbols)),
        },
        "summary": summary,
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(batch, indent=2) + "\n", encoding="utf-8")
    return batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or execute TradingView recaptures from the prioritized recapture plan.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--symbol", action="append", default=[], help="Filter to one symbol. Can be repeated.")
    parser.add_argument("--execute", action="store_true", help="Actually drive TradingView via the local CLI. Default is dry-run.")
    parser.add_argument("--allow-quality-fail", action="store_true", help="Append bundle seed even if capture quality fails. Keep off for training data.")
    parser.add_argument("--max-quality-attempts", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    config = build_config(root_dir=root_dir)
    plan_path = resolve(root_dir, args.plan)
    output_path = resolve(root_dir, args.output)
    batch = run_recapture_batch(
        config=config,
        plan=load_json(plan_path),
        plan_path=plan_path,
        output_path=output_path,
        limit=args.limit,
        symbols=args.symbol,
        execute=args.execute,
        allow_quality_fail=args.allow_quality_fail,
        max_quality_attempts=args.max_quality_attempts,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    print(json.dumps({"output_path": str(output_path), **batch["summary"]}, indent=2))


if __name__ == "__main__":
    main()
