from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RAW_MANIFEST = Path("results") / "raw_market_data_ingestion_manifest.json"
DEFAULT_LINEAGE_MANIFEST = Path("results") / "controlled_charts" / "controlled_chart_lineage_manifest.json"
DEFAULT_LABELSTUDIO_MANIFEST = Path("results") / "controlled_charts" / "label_studio" / "manifest.json"
DEFAULT_LABELSTUDIO_IMPORT_REPORT = Path("results") / "controlled_charts" / "label_studio" / "import_report.json"
DEFAULT_AUTO_PSEUDO_LABEL_REPORT = Path("results") / "controlled_charts" / "auto_pseudo_label_report.json"
DEFAULT_STATE_FIXTURES = Path("results") / "ttrades_state_builder_fixtures.json"
DEFAULT_AUTO_STATE_FIXTURES = Path("results") / "ttrades_state_builder_fixtures.auto.json"
DEFAULT_RUNPOD_PLAN = Path("results") / "runpod_next_experiment_plan_20260622.json"
DEFAULT_OUTPUT = Path("results") / "pre_gpu_readiness_report.json"
DEFAULT_SCOPE_SYMBOLS = ("NQ", "ES", "GC")
REQUIRED_LABEL_ACTIONS = ("accept", "adjust", "reject", "defer")


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def gate(
    name: str,
    *,
    status: str,
    evidence: dict[str, Any],
    blocking_reasons: list[str] | None = None,
    next_action: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "evidence": evidence,
        "blocking_reasons": blocking_reasons or [],
        "next_action": next_action,
    }


def raw_data_gate(payload: dict[str, Any] | None, *, scope_symbols: tuple[str, ...]) -> dict[str, Any]:
    if payload is None:
        return gate(
            "raw_data_ingestion",
            status="blocked",
            evidence={},
            blocking_reasons=["raw_manifest_missing"],
            next_action="Run scripts/build_raw_market_data_manifest.py for the ES/NQ/GC scope.",
        )
    summary = payload.get("summary") or {}
    required = list(payload.get("required_symbols") or [])
    expected = list(scope_symbols)
    reasons: list[str] = []
    if summary.get("raw_data_gate") != "pass":
        reasons.append("raw_data_gate_not_pass")
    if required != expected:
        reasons.append("raw_scope_mismatch")
    evidence = {
        "required_symbols": required,
        "expected_scope_symbols": expected,
        "raw_data_gate": summary.get("raw_data_gate"),
        "missing_or_partial_required_symbols": summary.get("missing_or_partial_required_symbols", []),
    }
    return gate(
        "raw_data_ingestion",
        status="pass" if not reasons else "blocked",
        evidence=evidence,
        blocking_reasons=reasons,
        next_action="" if not reasons else "Regenerate the raw-data manifest for ES/NQ/GC before GPU work.",
    )


def lineage_gate(payload: dict[str, Any] | None, *, min_image_count: int) -> dict[str, Any]:
    if payload is None:
        return gate(
            "controlled_chart_lineage",
            status="blocked",
            evidence={},
            blocking_reasons=["lineage_manifest_missing"],
            next_action="Run scripts/build_controlled_chart_lineage.py.",
        )
    summary = payload.get("summary") or {}
    image_count = int(summary.get("image_count") or 0)
    reasons: list[str] = []
    if summary.get("lineage_gate") != "pass":
        reasons.append("lineage_gate_not_pass")
    if image_count < min_image_count:
        reasons.append("controlled_chart_image_count_below_minimum")
    evidence = {
        "lineage_gate": summary.get("lineage_gate"),
        "image_count": image_count,
        "minimum_image_count": min_image_count,
        "blocked_or_partial_symbols": summary.get("blocked_or_partial_symbols", []),
    }
    return gate(
        "controlled_chart_lineage",
        status="pass" if not reasons else "blocked",
        evidence=evidence,
        blocking_reasons=reasons,
        next_action="" if not reasons else "Regenerate controlled chart lineage and inspect blocked symbols.",
    )


def labelstudio_export_gate(payload: dict[str, Any] | None, *, min_task_count: int) -> dict[str, Any]:
    if payload is None:
        return gate(
            "label_studio_export",
            status="blocked",
            evidence={},
            blocking_reasons=["label_studio_manifest_missing"],
            next_action="Run scripts/export_controlled_chart_labelstudio_tasks.py.",
        )
    review_policy = payload.get("review_policy") or {}
    allowed_actions = list(review_policy.get("allowed_actions") or [])
    task_count = int(payload.get("task_count") or 0)
    missing_image_count = int(payload.get("missing_image_count") or 0)
    reasons: list[str] = []
    if task_count < min_task_count:
        reasons.append("label_studio_task_count_below_lineage_image_count")
    if missing_image_count:
        reasons.append("label_studio_export_has_missing_images")
    if any(action not in allowed_actions for action in REQUIRED_LABEL_ACTIONS):
        reasons.append("label_studio_review_actions_incomplete")
    evidence = {
        "task_count": task_count,
        "minimum_task_count": min_task_count,
        "missing_image_count": missing_image_count,
        "allowed_actions": allowed_actions,
        "required_actions": list(REQUIRED_LABEL_ACTIONS),
    }
    return gate(
        "label_studio_export",
        status="pass" if not reasons else "blocked",
        evidence=evidence,
        blocking_reasons=reasons,
        next_action="" if not reasons else "Regenerate Label Studio tasks/config before review.",
    )


def auto_pseudo_label_pass(payload: dict[str, Any] | None, *, min_trainable_items: int) -> bool:
    if payload is None:
        return False
    return (
        str(payload.get("auto_training_gate") or "") == "pass"
        and int(payload.get("validated_trainable_item_count") or 0) >= min_trainable_items
    )


def labelstudio_review_import_gate(
    payload: dict[str, Any] | None,
    *,
    auto_payload: dict[str, Any] | None,
    min_trainable_items: int,
    min_auto_trainable_items: int,
) -> dict[str, Any]:
    trainable_count = int((payload or {}).get("validated_trainable_item_count") or 0)
    training_gate = str((payload or {}).get("training_gate") or "")
    labelstudio_ok = payload is not None and training_gate == "pass" and trainable_count >= min_trainable_items
    auto_trainable_count = int((auto_payload or {}).get("validated_trainable_item_count") or 0)
    auto_gate = str((auto_payload or {}).get("auto_training_gate") or "")
    auto_ok = auto_pseudo_label_pass(auto_payload, min_trainable_items=min_auto_trainable_items)
    reasons: list[str] = []
    if not labelstudio_ok and not auto_ok:
        if payload is None:
            reasons.append("label_studio_import_report_missing")
        elif training_gate != "pass":
            reasons.append("label_studio_training_gate_not_pass")
        if trainable_count < min_trainable_items:
            reasons.append("label_studio_trainable_item_count_below_minimum")
        if auto_payload is None:
            reasons.append("auto_pseudo_label_report_missing")
        elif auto_gate != "pass":
            reasons.append("auto_pseudo_label_gate_not_pass")
        if auto_trainable_count < min_auto_trainable_items:
            reasons.append("auto_pseudo_label_trainable_item_count_below_minimum")
    evidence = {
        "selected_label_source": "label_studio_review" if labelstudio_ok else "auto_pseudo_labels" if auto_ok else "none",
        "label_studio": {
            "training_gate": training_gate,
            "validated_trainable_item_count": trainable_count,
            "minimum_trainable_item_count": min_trainable_items,
            "review_outcome_counts": (payload or {}).get("review_outcome_counts", {}),
            "issue_counts": (payload or {}).get("issue_counts", {}),
        },
        "auto_pseudo_labels": {
            "auto_training_gate": auto_gate,
            "validated_trainable_item_count": auto_trainable_count,
            "minimum_auto_trainable_item_count": min_auto_trainable_items,
            "class_counts": (auto_payload or {}).get("class_counts", {}),
            "status_counts": (auto_payload or {}).get("status_counts", {}),
        },
    }
    return gate(
        "label_studio_review_import",
        status="pass" if not reasons else "blocked",
        evidence=evidence,
        blocking_reasons=reasons,
        next_action="" if not reasons else "Run scripts/build_controlled_chart_auto_promotion_lane.py or import reviewed Label Studio annotations.",
    )


def state_fixture_gate(
    payload: dict[str, Any] | None,
    *,
    auto_payload: dict[str, Any] | None = None,
    min_fixture_count: int,
    min_non_insufficient_decisions: int,
    min_auto_fixture_count: int = 1,
) -> dict[str, Any]:
    summary = (payload or {}).get("summary") or {}
    fixture_count = int(summary.get("fixture_count") or 0)
    decision_counts = dict(summary.get("expected_decision_counts") or {})
    insufficient = int(decision_counts.get("insufficient_evidence") or 0)
    non_insufficient = sum(int(count or 0) for name, count in decision_counts.items() if name != "insufficient_evidence")
    reviewed_ok = (
        payload is not None
        and summary.get("fixture_gate") == "pass"
        and fixture_count >= min_fixture_count
        and non_insufficient >= min_non_insufficient_decisions
    )
    auto_summary = (auto_payload or {}).get("summary") or {}
    auto_fixture_count = int(auto_summary.get("fixture_count") or 0)
    auto_decision_counts = dict(auto_summary.get("expected_decision_counts") or {})
    auto_non_insufficient = sum(
        int(count or 0)
        for name, count in auto_decision_counts.items()
        if name != "insufficient_evidence"
    )
    auto_ok = (
        auto_payload is not None
        and auto_summary.get("fixture_gate") == "pass"
        and auto_fixture_count >= min_auto_fixture_count
        and auto_non_insufficient >= min_non_insufficient_decisions
    )
    reasons: list[str] = []
    if not reviewed_ok and not auto_ok:
        if payload is None:
            reasons.append("state_fixture_file_missing")
        elif summary.get("fixture_gate") != "pass":
            reasons.append("state_fixture_gate_not_pass")
        if fixture_count < min_fixture_count:
            reasons.append("state_fixture_count_below_minimum")
        if non_insufficient < min_non_insufficient_decisions:
            reasons.append("state_fixture_decision_coverage_below_minimum")
        if auto_payload is None:
            reasons.append("auto_state_fixture_file_missing")
        elif auto_summary.get("fixture_gate") != "pass":
            reasons.append("auto_state_fixture_gate_not_pass")
        if auto_fixture_count < min_auto_fixture_count:
            reasons.append("auto_state_fixture_count_below_minimum")
        if auto_non_insufficient < min_non_insufficient_decisions:
            reasons.append("auto_state_fixture_decision_coverage_below_minimum")
    evidence = {
        "selected_state_source": "reviewed_state_fixtures" if reviewed_ok else "auto_state_fixtures" if auto_ok else "none",
        "reviewed_state_fixtures": {
            "fixture_gate": summary.get("fixture_gate"),
            "fixture_count": fixture_count,
            "minimum_fixture_count": min_fixture_count,
            "expected_decision_counts": decision_counts,
            "insufficient_evidence_count": insufficient,
            "non_insufficient_decision_count": non_insufficient,
            "minimum_non_insufficient_decision_count": min_non_insufficient_decisions,
            "missing_evidence_counts": summary.get("missing_evidence_counts", {}),
        },
        "auto_state_fixtures": {
            "fixture_gate": auto_summary.get("fixture_gate"),
            "fixture_count": auto_fixture_count,
            "minimum_auto_fixture_count": min_auto_fixture_count,
            "expected_decision_counts": auto_decision_counts,
            "non_insufficient_decision_count": auto_non_insufficient,
            "missing_evidence_counts": auto_summary.get("missing_evidence_counts", {}),
        },
    }
    return gate(
        "state_builder_fixtures",
        status="pass" if not reasons else "blocked",
        evidence=evidence,
        blocking_reasons=reasons,
        next_action="" if not reasons else "Promote reviewed directional state labels so fixtures cover more than insufficient evidence.",
    )


def runpod_plan_gate(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return gate(
            "runpod_probe_plan",
            status="blocked",
            evidence={},
            blocking_reasons=["runpod_probe_plan_missing"],
            next_action="Create or refresh results/runpod_next_experiment_plan_20260622.json.",
        )
    evidence = {
        "status": payload.get("status"),
        "next_experiment": (payload.get("next_experiment") or {}).get("name"),
        "command": (payload.get("next_experiment") or {}).get("command"),
        "success_gate": payload.get("success_gate", {}),
    }
    status = str(payload.get("status") or "")
    reasons = [] if "ready" in status else ["runpod_probe_plan_not_ready"]
    return gate(
        "runpod_probe_plan",
        status="pass" if not reasons else "blocked",
        evidence=evidence,
        blocking_reasons=reasons,
        next_action="" if not reasons else "Refresh the RunPod recall-probe plan before launch.",
    )


def runpod_launch_environment_gate() -> dict[str, Any]:
    required = ("RUNPOD_JUPYTER_URL", "RUNPOD_JUPYTER_TOKEN")
    present = [name for name in required if os.environ.get(name)]
    missing = [name for name in required if name not in present]
    return gate(
        "runpod_launch_environment",
        status="pass" if not missing else "blocked",
        evidence={"required_env_vars": list(required), "present_env_vars": present, "missing_env_vars": missing},
        blocking_reasons=["runpod_jupyter_credentials_missing"] if missing else [],
        next_action="" if not missing else "Set RunPod Jupyter URL/token process-scoped, or configure SSH, before launching the GPU probe.",
    )


def summarize(gates: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(item["status"] for item in gates)
    blocked = [item for item in gates if item["status"] == "blocked"]
    blocking_reasons = [
        f"{item['name']}:{reason}"
        for item in blocked
        for reason in item["blocking_reasons"]
    ]
    next_actions = [item["next_action"] for item in blocked if item.get("next_action")]
    return {
        "pre_gpu_gate": "pass" if not blocked else "blocked",
        "gate_count": len(gates),
        "status_counts": dict(sorted(status_counts.items())),
        "blocked_gate_names": [item["name"] for item in blocked],
        "blocking_reasons": blocking_reasons,
        "recommended_next_actions": next_actions,
    }


def build_pre_gpu_readiness_report(
    *,
    root_dir: Path,
    raw_manifest_path: Path = DEFAULT_RAW_MANIFEST,
    lineage_manifest_path: Path = DEFAULT_LINEAGE_MANIFEST,
    labelstudio_manifest_path: Path = DEFAULT_LABELSTUDIO_MANIFEST,
    labelstudio_import_report_path: Path = DEFAULT_LABELSTUDIO_IMPORT_REPORT,
    auto_pseudo_label_report_path: Path = DEFAULT_AUTO_PSEUDO_LABEL_REPORT,
    state_fixtures_path: Path = DEFAULT_STATE_FIXTURES,
    auto_state_fixtures_path: Path = DEFAULT_AUTO_STATE_FIXTURES,
    runpod_plan_path: Path = DEFAULT_RUNPOD_PLAN,
    scope_symbols: tuple[str, ...] = DEFAULT_SCOPE_SYMBOLS,
    min_controlled_chart_images: int = 9,
    min_labelstudio_trainable_items: int = 1,
    min_auto_pseudo_label_trainable_items: int = 4,
    min_state_fixture_count: int = 20,
    min_non_insufficient_state_decisions: int = 1,
    min_auto_state_fixture_count: int = 1,
    require_runpod_credentials: bool = True,
) -> dict[str, Any]:
    root_dir = root_dir.resolve()
    raw_manifest = read_json(resolve(root_dir, raw_manifest_path))
    lineage_manifest = read_json(resolve(root_dir, lineage_manifest_path))
    labelstudio_manifest = read_json(resolve(root_dir, labelstudio_manifest_path))
    labelstudio_import_report = read_json(resolve(root_dir, labelstudio_import_report_path))
    auto_pseudo_label_report = read_json(resolve(root_dir, auto_pseudo_label_report_path))
    state_fixtures = read_json(resolve(root_dir, state_fixtures_path))
    auto_state_fixtures = read_json(resolve(root_dir, auto_state_fixtures_path))
    runpod_plan = read_json(resolve(root_dir, runpod_plan_path))

    lineage_image_count = int(((lineage_manifest or {}).get("summary") or {}).get("image_count") or 0)
    gates = [
        raw_data_gate(raw_manifest, scope_symbols=scope_symbols),
        lineage_gate(lineage_manifest, min_image_count=min_controlled_chart_images),
        labelstudio_export_gate(labelstudio_manifest, min_task_count=max(min_controlled_chart_images, lineage_image_count)),
        labelstudio_review_import_gate(
            labelstudio_import_report,
            auto_payload=auto_pseudo_label_report,
            min_trainable_items=min_labelstudio_trainable_items,
            min_auto_trainable_items=min_auto_pseudo_label_trainable_items,
        ),
        state_fixture_gate(
            state_fixtures,
            auto_payload=auto_state_fixtures,
            min_fixture_count=min_state_fixture_count,
            min_non_insufficient_decisions=min_non_insufficient_state_decisions,
            min_auto_fixture_count=min_auto_state_fixture_count,
        ),
        runpod_plan_gate(runpod_plan),
    ]
    if require_runpod_credentials:
        gates.append(runpod_launch_environment_gate())

    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Pre-GPU readiness gate for the ES/NQ/GC controlled-chart and TTrades state workflow.",
        "scope_symbols": list(scope_symbols),
        "inputs": {
            "raw_manifest": relative_or_absolute(resolve(root_dir, raw_manifest_path), root_dir),
            "lineage_manifest": relative_or_absolute(resolve(root_dir, lineage_manifest_path), root_dir),
            "labelstudio_manifest": relative_or_absolute(resolve(root_dir, labelstudio_manifest_path), root_dir),
            "labelstudio_import_report": relative_or_absolute(resolve(root_dir, labelstudio_import_report_path), root_dir),
            "auto_pseudo_label_report": relative_or_absolute(resolve(root_dir, auto_pseudo_label_report_path), root_dir),
            "state_fixtures": relative_or_absolute(resolve(root_dir, state_fixtures_path), root_dir),
            "auto_state_fixtures": relative_or_absolute(resolve(root_dir, auto_state_fixtures_path), root_dir),
            "runpod_plan": relative_or_absolute(resolve(root_dir, runpod_plan_path), root_dir),
        },
        "thresholds": {
            "min_controlled_chart_images": min_controlled_chart_images,
            "min_labelstudio_trainable_items": min_labelstudio_trainable_items,
            "min_auto_pseudo_label_trainable_items": min_auto_pseudo_label_trainable_items,
            "min_state_fixture_count": min_state_fixture_count,
            "min_non_insufficient_state_decisions": min_non_insufficient_state_decisions,
            "min_auto_state_fixture_count": min_auto_state_fixture_count,
            "require_runpod_credentials": require_runpod_credentials,
        },
        "summary": summarize(gates),
        "gates": gates,
    }


def write_report(payload: dict[str, Any], *, root_dir: Path, output_path: Path) -> None:
    resolved = resolve(root_dir, output_path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a pre-GPU readiness report for the TTrades workflow.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-labelstudio-trainable-items", type=int, default=1)
    parser.add_argument("--min-non-insufficient-state-decisions", type=int, default=1)
    parser.add_argument("--skip-runpod-credential-check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    payload = build_pre_gpu_readiness_report(
        root_dir=root_dir,
        min_labelstudio_trainable_items=args.min_labelstudio_trainable_items,
        min_non_insufficient_state_decisions=args.min_non_insufficient_state_decisions,
        require_runpod_credentials=not args.skip_runpod_credential_check,
    )
    write_report(payload, root_dir=root_dir, output_path=args.output)
    print(
        "Built pre-GPU readiness report: "
        f"{relative_or_absolute(resolve(root_dir, args.output), root_dir)} "
        f"gate={payload['summary']['pre_gpu_gate']} "
        f"blocked={','.join(payload['summary']['blocked_gate_names']) or 'none'}"
    )


if __name__ == "__main__":
    main()
