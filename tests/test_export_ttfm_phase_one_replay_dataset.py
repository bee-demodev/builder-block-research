from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import export_ttfm_phase_one_replay_dataset as etpord


def make_teacher_row(
    *,
    case_ref: str,
    bars_path: str | None,
    alignment_status: str,
    trade_models: list[str] | None = None,
    anchor_timestamp: str | None = None,
    checkpoint: str = "context",
    active_labels: list[str] | None = None,
) -> dict:
    return {
        "example_id": f"{case_ref}::{checkpoint}",
        "case_ref": case_ref,
        "topic": "bias",
        "trade_models": trade_models or ["daily_bias_framework"],
        "relation_types": ["bias_framework"],
        "checkpoint": checkpoint,
        "timeframe": "higher" if checkpoint == "context" else "lower",
        "timeframe_role": "htf" if checkpoint == "context" else "ltf",
        "timeframe_stack": {"htf": "higher", "etf": "lower", "ltf": "lower"},
        "active_labels": active_labels or ["equilibrium"],
        "supporting_topics": ["equilibrium", "top_down_alignment"],
        "draft_spec_keys": ["ttrades_curriculum__daily_bias_framework"],
        "outcome": {"decision": "trade", "reason": "daily_bias_continuation_setup"},
        "annotation_notes": ["teacher note"],
        "evidence_refs": ["https://example.com/case"],
        "source_url": "https://example.com/case",
        "screenshot_path": "artifacts/example.png",
        "market_context": {
            "alignment_status": alignment_status,
            "mapping_provenance": "case_manual" if alignment_status == "fully_aligned" else "tradingview_validation_proxy",
            "symbol": "NQ",
            "bars_path": bars_path,
            "bars_timeframe": "1m" if bars_path else None,
            "bars_first_timestamp": None,
            "bars_last_timestamp": None,
            "bars_row_count": None,
            "anchor_timestamp": anchor_timestamp,
            "window_minutes_before": 10,
            "window_minutes_after": 10,
            "source_chart_symbol": "NQM2026",
            "source_spec_key": "daily_bias_framework",
            "confidence": 1.0 if alignment_status == "fully_aligned" else 0.35,
            "notes": "demo",
        },
    }


class ExportTTFMPhaseOneReplayDatasetTests(unittest.TestCase):
    def test_build_phase_one_replay_dataset_exports_multi_timeframe_windows_for_aligned_case(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bars_path = root / "nq.csv"
            bars_path.write_text(
                "\n".join(
                    [
                        "timestamp,open,high,low,close,volume,session",
                        "2026-03-21T18:00:00-04:00,100,101,99,100.5,10,other",
                        "2026-03-21T18:01:00-04:00,100.5,102,100,101.5,10,other",
                        "2026-03-22T18:00:00-04:00,101.5,103,101,102.5,10,other",
                        "2026-03-22T18:01:00-04:00,102.5,104,102,103.5,10,other",
                        "2026-03-23T09:58:00-04:00,103.5,104,103,103.75,10,new_york",
                        "2026-03-23T09:59:00-04:00,103.75,104.5,103.5,104.25,10,new_york",
                        "2026-03-23T10:00:00-04:00,104.25,105,104,104.75,10,new_york",
                        "2026-03-23T10:01:00-04:00,104.75,105.25,104.5,105.0,10,new_york",
                        "2026-03-23T10:02:00-04:00,105.0,105.5,104.75,105.25,10,new_york",
                        "2026-03-23T10:03:00-04:00,105.25,105.75,105.0,105.5,10,new_york",
                        "2026-03-23T10:04:00-04:00,105.5,106.0,105.25,105.75,10,new_york",
                        "2026-03-23T10:05:00-04:00,105.75,106.25,105.5,106.0,10,new_york",
                    ]
                ),
                encoding="utf-8",
            )

            rows = [
                make_teacher_row(
                    case_ref="ttrades_daily_bias_continuation_baseline_v1",
                    bars_path=str(bars_path),
                    alignment_status="fully_aligned",
                    anchor_timestamp="2026-03-23T10:03:00-04:00",
                    checkpoint="context",
                    active_labels=["equilibrium"],
                ),
                make_teacher_row(
                    case_ref="ttrades_daily_bias_continuation_baseline_v1",
                    bars_path=str(bars_path),
                    alignment_status="fully_aligned",
                    anchor_timestamp="2026-03-23T10:03:00-04:00",
                    checkpoint="confirmation",
                    active_labels=["equilibrium", "zone_boundary"],
                ),
            ]

            dataset = etpord.build_phase_one_replay_dataset(
                rows,
                daily_lookback_sessions=1,
                daily_lookahead_sessions=0,
            )

            self.assertEqual(dataset["summary"]["phase_one_case_count"], 1)
            self.assertEqual(dataset["summary"]["exported_case_count"], 1)
            self.assertEqual(dataset["summary"]["skipped_case_counts"]["not_fully_aligned"], 0)

            example = dataset["examples"][0]
            self.assertEqual(example["case_ref"], "ttrades_daily_bias_continuation_baseline_v1")
            self.assertEqual(example["phase_one_primary_trade_model"], "daily_bias_framework")
            self.assertEqual(example["phase_one_execution_spec"], "daily_bias_c123_map")
            self.assertEqual(example["teacher_summary"]["checkpoint_labels"]["context"], ["equilibrium"])
            self.assertEqual(
                example["teacher_summary"]["checkpoint_labels"]["confirmation"],
                ["equilibrium", "zone_boundary"],
            )

            daily_window = example["timeframe_windows"]["D"]
            hourly_window = example["timeframe_windows"]["60"]
            execution_window = example["timeframe_windows"]["5"]
            self.assertEqual(daily_window["anchor_bar_index"], 1)
            self.assertEqual(daily_window["bar_count"], 2)
            self.assertEqual(hourly_window["anchor_bucket_timestamp"], "2026-03-23T10:00:00-04:00")
            self.assertEqual(hourly_window["anchor_bar_index"], 1)
            self.assertEqual(hourly_window["bar_count"], 2)
            self.assertEqual(execution_window["anchor_bucket_timestamp"], "2026-03-23T10:00:00-04:00")
            self.assertEqual(execution_window["anchor_bar_index"], 1)
            self.assertEqual(execution_window["bar_count"], 3)
            self.assertEqual(example["anchor_context"]["anchor_session_bucket"], "new_york")

    def test_build_phase_one_replay_dataset_skips_case_without_full_alignment(self) -> None:
        rows = [
            make_teacher_row(
                case_ref="ttrades_daily_bias_continuation_baseline_v1",
                bars_path="C:/demo/nq.csv",
                alignment_status="market_context_only",
                anchor_timestamp=None,
            )
        ]

        dataset = etpord.build_phase_one_replay_dataset(rows)

        self.assertEqual(dataset["examples"], [])
        self.assertEqual(dataset["summary"]["phase_one_case_count"], 1)
        self.assertEqual(dataset["summary"]["exported_case_count"], 0)
        self.assertEqual(dataset["summary"]["skipped_case_counts"]["not_fully_aligned"], 1)

    def test_export_phase_one_replay_dataset_writes_jsonl_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_input = root / "teacher.jsonl"
            output_path = root / "phase_one.jsonl"
            report_path = root / "phase_one_report.json"

            dataset_input.write_text(
                json.dumps(
                    make_teacher_row(
                        case_ref="non_phase_one_case",
                        bars_path=None,
                        alignment_status="unmapped",
                        trade_models=["continuation_entry_model"],
                        anchor_timestamp=None,
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            report = etpord.export_phase_one_replay_dataset(
                dataset_path=dataset_input,
                dataset_output=output_path,
                report_output=report_path,
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "")
            self.assertTrue(report_path.exists())
            self.assertEqual(report["summary"]["phase_one_case_count"], 0)
            self.assertEqual(report["summary"]["exported_case_count"], 0)


if __name__ == "__main__":
    unittest.main()
