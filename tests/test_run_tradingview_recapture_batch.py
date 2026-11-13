from __future__ import annotations

import json
from pathlib import Path

from config import build_config
from scripts.run_tradingview_recapture_batch import run_recapture_batch, select_recapture_targets


def _target(example_id: str, *, symbol: str, severity: float, flags: list[str] | None = None) -> dict:
    return {
        "example_id": example_id,
        "symbol": symbol,
        "severity_score": severity,
        "quality_flags": flags or [],
    }


def test_select_recapture_targets_filters_and_sorts_by_severity() -> None:
    plan = {
        "recapture_targets": [
            _target("nq-low", symbol="CME_MINI:NQM2026", severity=295.0),
            _target("es-top", symbol="CME_MINI:ESM2026", severity=305.0),
            _target("es-next", symbol="CME_MINI:ESM2026", severity=285.0),
        ]
    }

    selected = select_recapture_targets(plan, limit=2, symbols=["CME_MINI:ESM2026"])

    assert [target["example_id"] for target in selected] == ["es-top", "es-next"]


def test_recapture_batch_dry_run_writes_selected_plan(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    plan = {
        "recapture_targets": [
            _target("nq-low", symbol="CME_MINI:NQM2026", severity=295.0, flags=["low_information_timeframe_image"]),
            _target("es-top", symbol="CME_MINI:ESM2026", severity=305.0, flags=["exact_duplicate_timeframe_images"]),
        ]
    }
    output_path = tmp_path / "results" / "dry_run.json"

    batch = run_recapture_batch(
        config=config,
        plan=plan,
        plan_path=tmp_path / "plan.json",
        output_path=output_path,
        limit=1,
        execute=False,
    )

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert batch["summary"] == saved["summary"]
    assert batch["mode"] == "dry_run"
    assert batch["summary"]["selected_count"] == 1
    assert batch["summary"]["captured_count"] == 0
    assert batch["results"][0]["status"] == "dry_run"
    assert batch["results"][0]["example_id"] == "es-top"
    assert batch["results"][0]["would_run"][0] == "symbol CME_MINI:ESM2026"
    assert batch["policy"]["training_gate"].startswith("Recaptured rows must pass capture quality")


def test_recapture_batch_execute_sets_symbol_and_dispatches_capture(tmp_path: Path) -> None:
    config = build_config(root_dir=tmp_path)
    plan = {
        "recapture_targets": [
            _target("nq-low", symbol="CME_MINI:NQM2026", severity=295.0),
            _target("es-top", symbol="CME_MINI:ESM2026", severity=305.0),
        ]
    }
    commands: list[list[str]] = []
    capture_calls: list[dict] = []

    def fake_runner(args: list[str]) -> dict:
        commands.append(args)
        return {"success": True}

    def fake_runner_factory(_config):
        return fake_runner

    def fake_capture_func(_config, *, cli_runner, allow_quality_fail, max_quality_attempts, retry_delay_seconds):
        capture_calls.append(
            {
                "cli_runner": cli_runner,
                "allow_quality_fail": allow_quality_fail,
                "max_quality_attempts": max_quality_attempts,
                "retry_delay_seconds": retry_delay_seconds,
            }
        )
        return {
            "capture_quality_passed": True,
            "bundle_seed_appended": True,
            "capture_quality_attempt_count": 1,
            "capture_dir": str(tmp_path / "capture"),
            "raw_capture_path": str(tmp_path / "capture" / "raw.json"),
        }

    output_path = tmp_path / "results" / "execute.json"
    batch = run_recapture_batch(
        config=config,
        plan=plan,
        plan_path=tmp_path / "plan.json",
        output_path=output_path,
        limit=1,
        execute=True,
        allow_quality_fail=False,
        max_quality_attempts=3,
        retry_delay_seconds=0.25,
        cli_runner_factory=fake_runner_factory,
        capture_func=fake_capture_func,
    )

    assert commands == [["symbol", "CME_MINI:ESM2026"]]
    assert len(capture_calls) == 1
    assert capture_calls[0]["allow_quality_fail"] is False
    assert capture_calls[0]["max_quality_attempts"] == 3
    assert capture_calls[0]["retry_delay_seconds"] == 0.25
    assert batch["mode"] == "execute"
    assert batch["summary"]["captured_count"] == 1
    assert batch["summary"]["quality_passed_count"] == 1
    assert batch["summary"]["bundle_seed_appended_count"] == 1
    assert batch["results"][0]["status"] == "captured"
    assert batch["results"][0]["example_id"] == "es-top"
