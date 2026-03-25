from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import build_daily_bias_c123_spec as bdcs
import refresh_daily_bias_c123_rulepack as rdcr
import ttfm_video_embeddings as tve


ROOT = Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "results" / "daily_bias_c123_loop_summary.json"
PINE_MANIFEST_PATH = ROOT / "results" / "pine_scripts" / "daily_bias_c123_map_manifest.json"


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def build_loop_steps(python_executable: str) -> list[dict]:
    return [
        {
            "id": "validate_ttfm_video_corpus",
            "cmd": [python_executable, "scripts/validate_ttfm_video_corpus.py"],
        },
        {
            "id": "build_ttfm_google_embeddings",
            "cmd": [python_executable, "scripts/build_ttfm_google_embeddings.py"],
        },
        {
            "id": "refresh_daily_bias_c123_rulepack",
            "cmd": [python_executable, "scripts/refresh_daily_bias_c123_rulepack.py"],
        },
        {
            "id": "build_daily_bias_c123_spec",
            "cmd": [python_executable, "scripts/build_daily_bias_c123_spec.py"],
        },
        {
            "id": "generate_daily_bias_c123_pine",
            "cmd": [
                python_executable,
                "scripts/generate_pine_from_spec.py",
                "--spec-path",
                str(bdcs.SPEC_PATH),
                "--manifest-output",
                str(PINE_MANIFEST_PATH),
            ],
        },
    ]


def parse_step_stdout(stdout: str) -> dict:
    cleaned = stdout.strip()
    if not cleaned:
        return {}
    try:
        payload = json.loads(cleaned)
        return payload if isinstance(payload, dict) else {"value": payload}
    except json.JSONDecodeError:
        return {"stdout": cleaned}


def run_step(step: dict) -> dict:
    completed = subprocess.run(
        step["cmd"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return {
        "id": step["id"],
        "cmd": step["cmd"],
        "result": parse_step_stdout(completed.stdout),
    }


def build_loop_summary(
    *,
    step_results: list[dict],
    corpus_manifest: dict,
    embedding_manifest: dict,
    rulepack: dict,
    spec: dict,
    pine_manifest: dict,
) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "step_count": len(step_results),
        "steps": step_results,
        "corpus": {
            "video_count": int(corpus_manifest.get("video_count", 0)),
            "output_dir": corpus_manifest.get("output_dir"),
        },
        "embeddings": {
            "model": embedding_manifest.get("model"),
            "item_count": int(embedding_manifest.get("item_count", 0)),
            "index_path": embedding_manifest.get("index_path"),
        },
        "rulepack": {
            "slug": rulepack.get("trade_model", {}).get("slug"),
            "query_groups": rulepack.get("query_groups", []),
            "citation_count": len(rulepack.get("sources", [])),
        },
        "indicator_spec": {
            "slug": spec.get("trade_model", {}).get("slug"),
            "chart_timeframe": spec.get("timeframe_contract", {}).get("chart"),
            "bias_timeframe": spec.get("timeframe_contract", {}).get("bias"),
            "execution_timeframe": spec.get("timeframe_contract", {}).get("execution")
            or spec.get("timeframe_contract", {}).get("htf"),
        },
        "pine": {
            "generated_script_count": int(
                pine_manifest.get("summary", {}).get("generated_script_count", 0)
            ),
            "candidate_contract_count": int(
                pine_manifest.get("summary", {}).get("generated_candidate_contract_count", 0)
            ),
            "generated_scripts": pine_manifest.get("generated_scripts", []),
            "candidate_event_contracts": pine_manifest.get("candidate_event_contracts", []),
        },
    }


def run_loop(*, python_executable: str = sys.executable, output_path: Path = SUMMARY_PATH) -> dict:
    step_results = [run_step(step) for step in build_loop_steps(python_executable)]

    summary = build_loop_summary(
        step_results=step_results,
        corpus_manifest=load_json(tve.CORPUS_DIR / "video_manifest.json", {}),
        embedding_manifest=load_json(tve.MANIFEST_PATH, {}),
        rulepack=load_json(rdcr.RULEPACK_PATH, {}),
        spec=load_json(bdcs.SPEC_PATH, {}),
        pine_manifest=load_json(PINE_MANIFEST_PATH, {"summary": {}, "generated_scripts": []}),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the narrow daily bias C1/C2/C3 generation loop.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output", type=Path, default=SUMMARY_PATH)
    args = parser.parse_args()

    summary = run_loop(python_executable=args.python, output_path=args.output)
    print(
        json.dumps(
            {
                "output": tve.path_for_manifest(args.output),
                "step_count": summary["step_count"],
                "generated_script_count": summary["pine"]["generated_script_count"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
