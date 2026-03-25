from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from export_ttfm_case_packets import DEFAULT_OUTPUT as DEFAULT_CASE_PACKET_PATH


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET_OUTPUT = ROOT / "results" / "ttfm_component_dataset.jsonl"
DEFAULT_REPORT_OUTPUT = ROOT / "results" / "ttfm_component_dataset_report.json"


def load_case_packet_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_component_dataset_rows(case_packet_report: dict) -> list[dict]:
    rows: list[dict] = []
    for packet in case_packet_report.get("case_packets", []):
        for checkpoint in packet.get("checkpoints", []):
            screenshot_path = checkpoint.get("screenshot_path")
            if not screenshot_path:
                continue
            rows.append(
                {
                    "example_id": f"{packet['case_ref']}::{checkpoint['checkpoint']}",
                    "case_ref": packet["case_ref"],
                    "topic": packet.get("topic"),
                    "checkpoint": checkpoint["checkpoint"],
                    "timeframe": checkpoint.get("timeframe"),
                    "timeframe_role": checkpoint.get("timeframe_role"),
                    "active_labels": checkpoint.get("expected_component_labels", []),
                    "active_label_provenance": checkpoint.get("active_label_provenance"),
                    "labels_by_provenance": checkpoint.get("labels_by_provenance", {}),
                    "supporting_topics": packet.get("supporting_topics", []),
                    "draft_spec_keys": packet.get("draft_spec_keys", []),
                    "outcome": packet.get("outcome"),
                    "annotation_notes": checkpoint.get("annotation_notes", []),
                    "evidence_refs": checkpoint.get("evidence_refs", []),
                    "zone_geometry": checkpoint.get("zone_geometry"),
                    "screenshot_path": screenshot_path,
                }
            )
    return rows


def summarize_component_dataset(rows: list[dict], case_packet_report: dict) -> dict:
    case_summary = case_packet_report.get("summary", {})
    checkpoint_count = int(case_summary.get("checkpoint_count", 0))
    row_count = len(rows)
    skipped_missing_screenshot_count = max(0, checkpoint_count - row_count)
    active_provenance_counts: dict[str, int] = {}
    label_counts: dict[str, int] = {}
    for row in rows:
        provenance = str(row.get("active_label_provenance", "unknown"))
        active_provenance_counts[provenance] = active_provenance_counts.get(provenance, 0) + 1
        for label in row.get("active_labels", []):
            label_counts[label] = label_counts.get(label, 0) + 1

    return {
        "row_count": row_count,
        "checkpoint_count": checkpoint_count,
        "skipped_missing_screenshot_count": skipped_missing_screenshot_count,
        "active_label_provenance_counts": dict(sorted(active_provenance_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
    }


def build_component_dataset_report(case_packet_report: dict) -> tuple[list[dict], dict]:
    rows = build_component_dataset_rows(case_packet_report)
    summary = summarize_component_dataset(rows, case_packet_report)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }
    return rows, report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export screenshot-backed TTFM checkpoint rows for component-mapper training."
    )
    parser.add_argument("--case-packets", default=str(DEFAULT_CASE_PACKET_PATH))
    parser.add_argument("--output", default=str(DEFAULT_DATASET_OUTPUT))
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT))
    args = parser.parse_args()

    case_packet_report = load_case_packet_report(Path(args.case_packets))
    rows, report = build_component_dataset_report(case_packet_report)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )

    report_path = Path(args.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "dataset_output": str(output_path),
                "report_output": str(report_path),
                "row_count": report["summary"]["row_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
