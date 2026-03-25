from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC_DIR = ROOT / "results" / "indicator_specs"
DEFAULT_SCRIPT_DIR = ROOT / "results" / "pine_scripts"
DEFAULT_VALIDATION_PATH = ROOT / "data" / "tradingview_pine_validation.json"
DEFAULT_WORKFLOW_DOC_PATH = ROOT / "knowledge" / "tradingview_pine_workflow.md"
DEFAULT_OUTPUT = ROOT / "results" / "tradingview_pine_readiness_report.json"

# These statuses indicate the generated draft made it into TradingView's editor/runtime
# surface and can be scored by the QA gate. The log currently uses both
# `added_to_chart` and `compiled_on_chart` for successful chart-side passes.
VALIDATED_STATUSES = {"compiled", "added_to_chart", "compiled_on_chart", "validated"}
QA_PASS_STATUS = "pass"
QA_SCORE_THRESHOLD = 0.75


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def load_validation_log(path: Path) -> dict:
    if not path.exists():
        return {"validations": []}
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def validation_reached_editor(entry: dict) -> bool:
    return normalize_text(entry.get("validation_status")) in VALIDATED_STATUSES


def validation_passed_qa_gate(entry: dict, *, threshold: float = QA_SCORE_THRESHOLD) -> bool:
    if not validation_reached_editor(entry):
        return False
    if normalize_text(entry.get("qa_status")) != QA_PASS_STATUS:
        return False
    score_fields = ("semantic_score", "visual_score", "scope_score")
    scores: list[float] = []
    for field in score_fields:
        value = entry.get(field)
        if value is None:
            return False
        try:
            scores.append(float(value))
        except (TypeError, ValueError):
            return False
    return all(score >= threshold for score in scores)


def load_pine_specs(spec_dir: Path) -> list[dict]:
    specs: list[dict] = []
    for path in sorted(spec_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        target_language = str(
            payload.get("implementation_scope", {}).get("target_language")
            or payload.get("target_language")
            or ""
        ).strip()
        if target_language != "pine":
            continue
        specs.append(
            {
                "spec_key": str(payload.get("trade_model", {}).get("slug", "")).strip() or path.stem,
                "name": str(payload.get("trade_model", {}).get("name", "")).strip() or path.stem,
                "path": path,
            }
        )
    return specs


def is_compile_shaped_script(path: Path) -> bool:
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    return "//@version=" in content and ("indicator(" in content or "strategy(" in content)


def build_tradingview_pine_readiness_report(
    *,
    spec_dir: Path = DEFAULT_SPEC_DIR,
    script_dir: Path = DEFAULT_SCRIPT_DIR,
    validation_log: dict | None = None,
    workflow_doc_path: Path = DEFAULT_WORKFLOW_DOC_PATH,
) -> dict:
    specs = load_pine_specs(spec_dir)
    validation_log = validation_log or {"validations": []}
    validations = list(validation_log.get("validations", []))

    script_paths = {path.stem: path for path in sorted(script_dir.glob("*.pine"))}
    generated_spec_keys = sorted(script_paths)
    compile_shaped_keys = sorted(
        spec_key for spec_key, path in script_paths.items() if is_compile_shaped_script(path)
    )

    validation_by_spec: dict[str, list[dict]] = {}
    for entry in validations:
        spec_key = str(entry.get("spec_key", "")).strip()
        if not spec_key:
            continue
        validation_by_spec.setdefault(spec_key, []).append(entry)

    editor_accepted_keys = sorted(
        spec_key
        for spec_key, entries in validation_by_spec.items()
        if any(validation_reached_editor(entry) for entry in entries)
    )
    validated_spec_keys = sorted(
        spec_key
        for spec_key, entries in validation_by_spec.items()
        if any(validation_passed_qa_gate(entry) for entry in entries)
    )
    playwriter_validated_keys = sorted(
        spec_key
        for spec_key, entries in validation_by_spec.items()
        if any(
            validation_passed_qa_gate(entry)
            and normalize_text(entry.get("validation_method")) == "playwriter"
            for entry in entries
        )
    )

    pine_target_spec_count = len(specs)
    generated_script_count = len(generated_spec_keys)
    compile_shaped_count = len(compile_shaped_keys)
    editor_accepted_count = len(editor_accepted_keys)
    validated_script_count = len(validated_spec_keys)
    playwriter_validated_count = len(playwriter_validated_keys)

    generated_script_coverage = generated_script_count / pine_target_spec_count if pine_target_spec_count else 0.0
    compile_shaped_coverage = compile_shaped_count / generated_script_count if generated_script_count else 0.0
    editor_success_coverage = editor_accepted_count / generated_script_count if generated_script_count else 0.0
    validation_coverage = validated_script_count / generated_script_count if generated_script_count else 0.0
    playwriter_validation_coverage = (
        playwriter_validated_count / generated_script_count if generated_script_count else 0.0
    )
    workflow_doc_present = workflow_doc_path.exists()

    workflow_score = clamp(
        0.20 * (1.0 if workflow_doc_present else 0.0)
        + 0.25 * generated_script_coverage
        + 0.20 * compile_shaped_coverage
        + 0.15 * editor_success_coverage
        + 0.15 * validation_coverage
        + 0.05 * playwriter_validation_coverage
    )

    spec_keys = [spec["spec_key"] for spec in specs]
    pending_spec_keys = sorted(set(spec_keys) - set(validated_spec_keys))

    per_spec_status = []
    for spec in specs:
        spec_key = spec["spec_key"]
        per_spec_status.append(
            {
                "spec_key": spec_key,
                "name": spec["name"],
                "generated_script": spec_key in script_paths,
                "compile_shaped_script": spec_key in compile_shaped_keys,
                "editor_accepted_in_tradingview": spec_key in editor_accepted_keys,
                "validated_in_tradingview": spec_key in validated_spec_keys,
                "validated_with_playwriter": spec_key in playwriter_validated_keys,
                "validations": validation_by_spec.get(spec_key, []),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "pine_target_spec_count": pine_target_spec_count,
            "generated_script_count": generated_script_count,
            "compile_shaped_script_count": compile_shaped_count,
            "editor_accepted_count": editor_accepted_count,
            "validated_script_count": validated_script_count,
            "playwriter_validated_count": playwriter_validated_count,
            "qa_gate_pass_count": validated_script_count,
            "generated_script_coverage": round(clamp(generated_script_coverage), 4),
            "compile_shaped_coverage": round(clamp(compile_shaped_coverage), 4),
            "editor_success_coverage": round(clamp(editor_success_coverage), 4),
            "validation_coverage": round(clamp(validation_coverage), 4),
            "playwriter_validation_coverage": round(clamp(playwriter_validation_coverage), 4),
            "workflow_doc_present": workflow_doc_present,
            "workflow_score": round(workflow_score, 4),
            "pending_spec_keys": pending_spec_keys,
        },
        "per_spec_status": per_spec_status,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export TradingView + Pine workflow readiness from repo specs, generated scripts, and validation logs."
    )
    parser.add_argument("--spec-dir", default=str(DEFAULT_SPEC_DIR))
    parser.add_argument("--script-dir", default=str(DEFAULT_SCRIPT_DIR))
    parser.add_argument("--validation-log", default=str(DEFAULT_VALIDATION_PATH))
    parser.add_argument("--workflow-doc", default=str(DEFAULT_WORKFLOW_DOC_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    report = build_tradingview_pine_readiness_report(
        spec_dir=Path(args.spec_dir),
        script_dir=Path(args.script_dir),
        validation_log=load_validation_log(Path(args.validation_log)),
        workflow_doc_path=Path(args.workflow_doc),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "workflow_score": report["summary"]["workflow_score"],
                "generated_script_count": report["summary"]["generated_script_count"],
                "validated_script_count": report["summary"]["validated_script_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
