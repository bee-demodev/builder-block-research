import json
from pathlib import Path

from bundle_dataset import (
    build_bundle_dataset,
    build_bundle_gold_seed,
    derive_bundle_record,
    summarize_bundle_dataset,
    write_bundle_dataset,
)
from fractal_state import load_state_machine


def test_derive_bundle_record_continuation_c4() -> None:
    machine = load_state_machine()
    record = {
        "summary": "Bullish continuation C4 with aligned reaction zone and entry-ready structure during London session.",
        "htf_frame_path": "frames/htf.png",
        "itf_frame_path": "frames/itf.png",
        "ltf_frame_path": "frames/ltf.png",
    }

    bundle = derive_bundle_record(
        record=record,
        source="unit",
        source_path=Path("unit.json"),
        pointer="$.items[0]",
        machine=machine,
    )

    assert bundle is not None
    assert bundle.path_family == "continuation"
    assert bundle.fractal_stage == "c4"
    assert bundle.direction == "bullish"
    assert bundle.entry_state == "long_ready"
    assert bundle.review_outcome in {"derived", "needs_review"}


def test_build_bundle_dataset_and_write_jsonl(tmp_path: Path) -> None:
    source = tmp_path / "cases.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "note": "Bearish reversal c3 after sweep high and protected swing change.",
                        "frame_path": "frames/reversal.png",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    bundles = build_bundle_dataset(source_paths=[source])
    assert len(bundles) == 1
    assert bundles[0].path_family == "reversal"
    assert bundles[0].fractal_stage == "c3"

    output = tmp_path / "bundle_dataset.jsonl"
    write_bundle_dataset(output, bundles)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["bundle_id"]
    assert payload["source"] == "cases"


def test_summarize_bundle_dataset_reports_benchmark_coverage(tmp_path: Path) -> None:
    source = tmp_path / "cases.json"
    source.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "note": "Bullish continuation c4 with order block entry-ready structure.",
                        "htf_frame_path": "frames/htf.png",
                        "itf_frame_path": "frames/itf.png",
                        "ltf_frame_path": "frames/ltf.png",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    benchmark_targets = tmp_path / "bundle_targets.json"
    benchmark_targets.write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "path_family": "continuation",
                        "direction": "bullish",
                        "fractal_stage": "c4",
                        "minimum_examples": 1,
                    },
                    {
                        "setup_quality": "no_setup",
                        "minimum_examples": 1,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    bundles = build_bundle_dataset(source_paths=[source])
    summary = summarize_bundle_dataset(bundles, benchmark_targets_path=benchmark_targets)

    assert summary["bundle_count"] == 1
    assert summary["counts"]["path_family"]["continuation"] == 1
    assert summary["benchmark"]["target_count"] == 2
    assert summary["benchmark"]["satisfied_target_count"] == 1
    assert summary["benchmark"]["unsatisfied_target_count"] == 1


def test_build_bundle_dataset_extracts_screenshot_paths_from_notes(tmp_path: Path) -> None:
    source = tmp_path / "validations.json"
    source.write_text(
        json.dumps(
            {
                "validations": [
                    {
                        "qa_notes": "Live chart screenshot C:/tmp/ttrades-phase1.png shows bullish continuation c4 inside the active POI.",
                        "notes": "Bullish continuation c4 with aligned reaction zone and entry-ready structure.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    bundles = build_bundle_dataset(source_paths=[source])

    assert len(bundles) == 1
    assert bundles[0].htf_frame_path == "C:/tmp/ttrades-phase1.png"
    assert bundles[0].fractal_stage == "c4"


def test_build_bundle_gold_seed_from_screenshot_manifest(tmp_path: Path) -> None:
    screenshot_manifest = tmp_path / "ttfm_screenshot_manifest.json"
    cases_path = tmp_path / "trader_annotation_cases.json"
    screenshot_manifest.write_text(
        json.dumps(
            {
                "attachments": [
                    {"case_ref": "case_a", "checkpoint": "context", "screenshot_path": "artifacts/case_a/context.png"},
                    {"case_ref": "case_a", "checkpoint": "closure", "screenshot_path": "artifacts/case_a/closure.png"},
                    {"case_ref": "case_a", "checkpoint": "confirmation", "screenshot_path": "artifacts/case_a/confirmation.png"},
                    {"case_ref": "case_a", "checkpoint": "outcome", "screenshot_path": "artifacts/case_a/outcome.png"},
                ]
            }
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_ref": "case_a",
                        "topic": "continuation",
                        "chart_context": {"setup_variant": "continuation_day_equilibrium_respect"},
                        "annotation": {"equilibrium_role": "continuation_area_of_interest"},
                        "outcome": {"decision": "trade", "reason": "continuation_setup"},
                        "notes": "Bullish continuation model.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    bundles = build_bundle_gold_seed(
        screenshot_manifest_path=screenshot_manifest,
        trader_annotation_cases_path=cases_path,
    )

    assert len(bundles) == 4
    assert {bundle.fractal_stage for bundle in bundles} == {"c1", "c2", "c3", "c4"}
    c4_bundle = next(bundle for bundle in bundles if bundle.fractal_stage == "c4")
    assert c4_bundle.review_outcome == "seed_gold"
    assert c4_bundle.setup_quality == "good_setup"
