from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VALIDATION_LOG_PATH = ROOT / "data" / "tradingview_pine_validation.json"


def load_validation_log(path: Path) -> dict:
    if not path.exists():
        return {"validations": []}
    return json.loads(path.read_text(encoding="utf-8"))


def append_validation_entry(
    log: dict,
    *,
    spec_key: str,
    script_path: str,
    validation_status: str,
    validation_method: str,
    notes: str = "",
    chart_url: str = "",
    chart_symbol: str = "",
    qa_status: str = "pending",
    semantic_score: float | None = None,
    visual_score: float | None = None,
    scope_score: float | None = None,
    qa_notes: str = "",
) -> dict:
    entry = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "spec_key": spec_key,
        "script_path": script_path,
        "validation_status": validation_status,
        "validation_method": validation_method,
        "notes": notes,
        "chart_url": chart_url,
        "chart_symbol": chart_symbol,
        "qa_status": qa_status,
        "semantic_score": semantic_score,
        "visual_score": visual_score,
        "scope_score": scope_score,
        "qa_notes": qa_notes,
    }
    validations = list(log.get("validations", []))
    validations.append(entry)
    return {"validations": validations}


def write_validation_log(path: Path, log: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append a TradingView Pine validation entry to the durable validation log."
    )
    parser.add_argument("--log-path", default=str(DEFAULT_VALIDATION_LOG_PATH))
    parser.add_argument("--spec-key", required=True)
    parser.add_argument("--script-path", required=True)
    parser.add_argument("--validation-status", required=True)
    parser.add_argument("--validation-method", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--chart-url", default="")
    parser.add_argument("--chart-symbol", default="")
    parser.add_argument("--qa-status", default="pending")
    parser.add_argument("--semantic-score", type=float)
    parser.add_argument("--visual-score", type=float)
    parser.add_argument("--scope-score", type=float)
    parser.add_argument("--qa-notes", default="")
    args = parser.parse_args()

    log_path = Path(args.log_path)
    log = load_validation_log(log_path)
    updated_log = append_validation_entry(
        log,
        spec_key=args.spec_key,
        script_path=args.script_path,
        validation_status=args.validation_status,
        validation_method=args.validation_method,
        notes=args.notes,
        chart_url=args.chart_url,
        chart_symbol=args.chart_symbol,
        qa_status=args.qa_status,
        semantic_score=args.semantic_score,
        visual_score=args.visual_score,
        scope_score=args.scope_score,
        qa_notes=args.qa_notes,
    )
    write_validation_log(log_path, updated_log)

    print(
        json.dumps(
            {
                "log_path": str(log_path),
                "validation_count": len(updated_log["validations"]),
                "latest_status": args.validation_status,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
