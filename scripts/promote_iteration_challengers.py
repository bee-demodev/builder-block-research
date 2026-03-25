from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ITERATION_CHALLENGER_REPORT_PATH = ROOT / "results" / "iteration_challenger_report.json"
DEFAULT_CHAMPION_MODEL_DIR = ROOT / "results" / "neural_models"
DEFAULT_ARCHIVE_ROOT = ROOT / "results" / "neural_models" / "archive"
DEFAULT_HISTORY_PATH = ROOT / "results" / "iteration_promotion_history.jsonl"
DEFAULT_OUTPUT_PATH = ROOT / "results" / "iteration_promotion_report.json"


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build_promotion_candidates(iteration_challenger_report: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for task_report in iteration_challenger_report.get("task_reports", []):
        if not isinstance(task_report, dict):
            continue
        if task_report.get("status") != "compared":
            continue
        if task_report.get("recommendation") != "promote_after_review":
            continue
        if task_report.get("winner") != "challenger":
            continue
        candidates.append(task_report)
    return candidates


def _safe_slug(task_name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in task_name.strip())
    return cleaned or "promotion"


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _archive_current_champion(
    *,
    champion_model_path: Path,
    champion_report_path: Path,
    archive_root: Path,
    task_name: str,
) -> dict[str, str]:
    archive_dir = archive_root / _safe_slug(task_name) / _timestamp_slug()
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived_model_path = archive_dir / champion_model_path.name
    archived_report_path = archive_dir / champion_report_path.name
    shutil.copy2(champion_model_path, archived_model_path)
    if champion_report_path.exists():
        shutil.copy2(champion_report_path, archived_report_path)
    return {
        "archived_model_path": str(archived_model_path),
        "archived_report_path": str(archived_report_path),
    }


def _write_champion_report(
    *,
    champion_report_path: Path,
    champion_model_path: Path,
    champion_report: dict[str, Any],
    source_model_path: Path,
    source_report_path: Path,
    promoted_at: str,
    source_iteration_challenger_report_path: Path,
) -> dict[str, Any]:
    updated_report = dict(champion_report)
    updated_report["model_path"] = str(champion_model_path)
    updated_report["report_path"] = str(champion_report_path)
    updated_report["promotion"] = {
        "promoted_at": promoted_at,
        "source_model_path": str(source_model_path),
        "source_report_path": str(source_report_path),
        "source_iteration_challenger_report_path": str(source_iteration_challenger_report_path),
    }
    champion_report_path.write_text(json.dumps(updated_report, indent=2) + "\n", encoding="utf-8")
    return updated_report


def apply_promotion_report(
    *,
    iteration_challenger_report: dict[str, Any],
    champion_model_dir: Path,
    archive_root: Path,
    history_path: Path,
    source_iteration_challenger_report_path: Path | None = None,
) -> dict[str, Any]:
    promoted_at = datetime.now(timezone.utc).isoformat()
    source_iteration_challenger_report_path = (
        source_iteration_challenger_report_path or DEFAULT_ITERATION_CHALLENGER_REPORT_PATH
    )

    promotions: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for task_report in iteration_challenger_report.get("task_reports", []):
        if not isinstance(task_report, dict):
            continue

        task_name = str(task_report.get("task_name", ""))
        candidate = (
            task_report.get("status") == "compared"
            and task_report.get("recommendation") == "promote_after_review"
            and task_report.get("winner") == "challenger"
        )
        if not candidate:
            skipped.append(
                {
                    "task_name": task_name,
                    "reason": "not_promotable",
                    "status": task_report.get("status"),
                    "winner": task_report.get("winner"),
                    "recommendation": task_report.get("recommendation"),
                }
            )
            continue

        challenger_model_path = Path(str(task_report.get("challenger_model_path", "")))
        champion_model_path = champion_model_dir / f"{task_name}.pt"
        challenger_report_path = Path(
            str(
                (task_report.get("challenger_training_report") or {}).get(
                    "report_path",
                    champion_model_dir / f"{task_name}_report.json",
                )
            )
        )
        champion_report_path = champion_model_dir / f"{task_name}_report.json"
        if not champion_model_path.exists():
            skipped.append(
                {
                    "task_name": task_name,
                    "reason": "missing_champion_model",
                    "champion_model_path": str(champion_model_path),
                }
            )
            continue
        if not challenger_model_path.exists():
            skipped.append(
                {
                    "task_name": task_name,
                    "reason": "missing_challenger_model",
                    "challenger_model_path": str(challenger_model_path),
                }
            )
            continue

        archived_paths = _archive_current_champion(
            champion_model_path=champion_model_path,
            champion_report_path=champion_report_path,
            archive_root=archive_root,
            task_name=task_name,
        )
        shutil.copy2(challenger_model_path, champion_model_path)

        champion_report = _read_optional_json(champion_report_path)
        updated_champion_report = _write_champion_report(
            champion_report_path=champion_report_path,
            champion_model_path=champion_model_path,
            champion_report=champion_report,
            source_model_path=challenger_model_path,
            source_report_path=challenger_report_path,
            promoted_at=promoted_at,
            source_iteration_challenger_report_path=source_iteration_challenger_report_path,
        )

        promotion_entry = {
            "task_name": task_name,
            "promoted_at": promoted_at,
            "champion_model_path": str(champion_model_path),
            "challenger_model_path": str(challenger_model_path),
            "challenger_report_path": str(challenger_report_path),
            "archived_model_path": archived_paths["archived_model_path"],
            "archived_report_path": archived_paths["archived_report_path"],
            "full_surface_winner": (task_report.get("full_surface") or {}).get("winner"),
            "winner": task_report.get("winner"),
            "recommendation": task_report.get("recommendation"),
            "champion_report": updated_champion_report,
        }
        promotions.append(promotion_entry)

    history_path.parent.mkdir(parents=True, exist_ok=True)
    if promotions:
        with history_path.open("a", encoding="utf-8") as handle:
            for promotion in promotions:
                handle.write(json.dumps(promotion) + "\n")

    return {
        "generated_at": promoted_at,
        "source_iteration_challenger_report_path": str(source_iteration_challenger_report_path),
        "summary": {
            "candidate_task_count": len(build_promotion_candidates(iteration_challenger_report)),
            "promoted_task_count": len(promotions),
            "skipped_task_count": len(skipped),
            "promoted_tasks": [promotion["task_name"] for promotion in promotions],
            "skipped_tasks": [item["task_name"] for item in skipped],
        },
        "promotions": promotions,
        "skipped": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote winning iteration challengers into the champion model directory after review."
    )
    parser.add_argument(
        "--iteration-challenger-report",
        default=str(DEFAULT_ITERATION_CHALLENGER_REPORT_PATH),
    )
    parser.add_argument("--champion-model-dir", default=str(DEFAULT_CHAMPION_MODEL_DIR))
    parser.add_argument("--archive-root", default=str(DEFAULT_ARCHIVE_ROOT))
    parser.add_argument("--history-path", default=str(DEFAULT_HISTORY_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    args = parser.parse_args()

    iteration_challenger_report_path = Path(args.iteration_challenger_report)
    iteration_challenger_report = load_json(iteration_challenger_report_path, {"task_reports": []})
    report = apply_promotion_report(
        iteration_challenger_report=iteration_challenger_report,
        champion_model_dir=Path(args.champion_model_dir),
        archive_root=Path(args.archive_root),
        history_path=Path(args.history_path),
        source_iteration_challenger_report_path=iteration_challenger_report_path,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output_path": str(output_path),
                "promoted_task_count": report["summary"]["promoted_task_count"],
                "skipped_task_count": report["summary"]["skipped_task_count"],
                "promoted_tasks": report["summary"]["promoted_tasks"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
