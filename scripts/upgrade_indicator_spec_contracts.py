from __future__ import annotations

import argparse
import json
import sqlite3
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "research.db"
DEFAULT_VALIDATION_PATH = ROOT / "data" / "tradingview_pine_validation.json"
SUCCESS_VALIDATION_STATUSES = {"compiled", "added_to_chart", "validated"}
PROMOTABLE_STATUSES = {"candidate", "draft"}
BACKTEST_GROUP_NAME = "Backtest Contract"
BACKTEST_ACCEPTANCE_CHECKS = (
    "Backtest results must include spread, slippage, commission, and fee assumptions before performance is treated as credible.",
    "Historical execution must assume next-bar-open entry after a confirmed bar-close signal instead of intrabar lookahead fills.",
    "If stop and target touch in the same bar, assume the stop prints first unless lower-timeframe replay evidence proves the target filled first.",
)
BACKTEST_INPUTS = (
    {
        "key": "backtestTickSize",
        "type": "float",
        "default": 0.25,
        "description": "First-pass tick size used by the historical harness when translating bar movement into execution and stop-distance units.",
    },
    {
        "key": "backtestSpreadTicks",
        "type": "float",
        "default": 1.0,
        "description": "Explicit spread assumption in ticks for historical backtests.",
    },
    {
        "key": "backtestSlippageTicks",
        "type": "float",
        "default": 0.5,
        "description": "Explicit slippage assumption in ticks for historical backtests, with larger values required in illiquid sessions.",
    },
    {
        "key": "backtestCommissionPerContract",
        "type": "float",
        "default": 2.5,
        "description": "Commission and fee assumption per contract for historical backtests.",
    },
)


def load_validation_log(path: Path = DEFAULT_VALIDATION_PATH) -> dict:
    if not path.exists():
        return {"validations": []}
    return json.loads(path.read_text(encoding="utf-8"))


def select_latest_success_validation(validations: list[dict]) -> dict | None:
    successful = [
        validation
        for validation in validations
        if str(validation.get("validation_status", "")).strip() in SUCCESS_VALIDATION_STATUSES
    ]
    if not successful:
        return None
    return max(successful, key=lambda validation: str(validation.get("recorded_at", "")))


def promote_status_from_validations(
    current_status: str,
    validations: list[dict],
) -> tuple[str, dict | None]:
    status = str(current_status).strip().lower() or "draft"
    evidence = select_latest_success_validation(validations)
    if evidence and status in PROMOTABLE_STATUSES:
        return "reviewed", evidence
    return current_status, evidence


def merge_input_group(existing_groups: list[dict], new_group: dict) -> list[dict]:
    groups = [deepcopy(group) for group in existing_groups]
    for group in groups:
        if str(group.get("group", "")).strip() != new_group["group"]:
            continue
        existing_inputs = {
            str(item.get("key", "")).strip(): deepcopy(item)
            for item in group.get("inputs", [])
            if str(item.get("key", "")).strip()
        }
        for item in new_group.get("inputs", []):
            existing_inputs.setdefault(str(item["key"]), deepcopy(item))
        group["inputs"] = list(existing_inputs.values())
        return groups

    groups.append(deepcopy(new_group))
    return groups


def merge_acceptance_checks(existing_checks: list[str], new_checks: tuple[str, ...]) -> list[str]:
    merged = list(existing_checks)
    seen = {check.strip() for check in merged}
    for check in new_checks:
        normalized = check.strip()
        if normalized and normalized not in seen:
            merged.append(check)
            seen.add(normalized)
    return merged


def apply_backtest_contract(spec: dict) -> dict:
    upgraded = deepcopy(spec)
    implementation_scope = upgraded.setdefault("implementation_scope", {})
    implementation_scope["historical_execution_contract"] = "next_bar_open_after_bar_close_signal"
    implementation_scope["historical_fill_collision_policy"] = "stop_first_when_stop_and_target_touch_same_bar"
    implementation_scope["transaction_costs_required"] = True
    implementation_scope["liquidity_constraint"] = "Increase slippage or skip illiquid session windows instead of assuming frictionless fills."

    upgraded["backtest_contract"] = {
        "execution_model": {
            "entry_fill": "next_bar_open_after_confirmed_bar_close_signal",
            "intrabar_policy": "no_intrabar_lookahead",
            "stop_target_collision_policy": "stop_first_when_stop_and_target_touch_same_bar",
        },
        "transaction_cost_model": {
            "tick_size": 0.25,
            "spread_ticks": 1.0,
            "slippage_ticks": 0.5,
            "commission_per_contract": 2.5,
            "contract_multiplier": 20.0,
            "fee_notes": "Commission should include exchange and brokerage fees, and slippage should be increased or the setup skipped in illiquid sessions.",
        },
    }
    upgraded["input_groups"] = merge_input_group(
        upgraded.get("input_groups", []),
        {"group": BACKTEST_GROUP_NAME, "inputs": list(BACKTEST_INPUTS)},
    )
    upgraded["acceptance_checks"] = merge_acceptance_checks(
        upgraded.get("acceptance_checks", []),
        BACKTEST_ACCEPTANCE_CHECKS,
    )
    return upgraded


def apply_validation_evidence(spec: dict, evidence: dict | None) -> dict:
    if evidence is None:
        return deepcopy(spec)
    upgraded = deepcopy(spec)
    upgraded["validation_evidence"] = {
        "latest_success": {
            "recorded_at": evidence.get("recorded_at"),
            "validation_status": evidence.get("validation_status"),
            "validation_method": evidence.get("validation_method"),
            "chart_url": evidence.get("chart_url"),
            "chart_symbol": evidence.get("chart_symbol"),
            "script_path": evidence.get("script_path"),
            "notes": evidence.get("notes"),
        }
    }
    return upgraded


def apply_status_markers(spec: dict, status: str) -> dict:
    upgraded = deepcopy(spec)
    normalized_status = str(status).strip().lower()
    if not normalized_status:
        return upgraded
    upgraded["translation_stage"] = normalized_status
    implementation_scope = upgraded.setdefault("implementation_scope", {})
    implementation_scope["translation_stage"] = normalized_status
    return upgraded


def load_indicator_specs(connection: sqlite3.Connection) -> list[dict]:
    rows = connection.execute(
        """
        SELECT spec_key, status, spec_json
        FROM indicator_specs
        ORDER BY spec_key
        """
    ).fetchall()

    specs: list[dict] = []
    for spec_key, status, spec_json in rows:
        specs.append(
            {
                "spec_key": str(spec_key),
                "status": str(status),
                "spec_json": json.loads(str(spec_json)),
            }
        )
    return specs


def build_validation_lookup(validation_log: dict) -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for entry in validation_log.get("validations", []):
        spec_key = str(entry.get("spec_key", "")).strip()
        if not spec_key:
            continue
        lookup.setdefault(spec_key, []).append(entry)
    return lookup


def candidate_validation_keys(spec_entry: dict) -> set[str]:
    trade_model_slug = str(
        spec_entry["spec_json"].get("trade_model", {}).get("slug", "")
    ).strip()
    keys = {spec_entry["spec_key"]}
    if trade_model_slug:
        keys.add(trade_model_slug)
    return keys


def validations_for_spec(spec_entry: dict, validation_lookup: dict[str, list[dict]]) -> list[dict]:
    matched: list[dict] = []
    for key in candidate_validation_keys(spec_entry):
        matched.extend(validation_lookup.get(key, []))
    return matched


def resolve_artifact_path(spec_entry: dict) -> Path:
    artifact_path = str(spec_entry["spec_json"].get("artifact_path", "")).strip()
    if artifact_path:
        return ROOT / artifact_path
    fallback_name = (
        str(spec_entry["spec_json"].get("trade_model", {}).get("slug", "")).strip()
        or spec_entry["spec_key"].split("__", 1)[-1]
    )
    return ROOT / "results" / "indicator_specs" / f"{fallback_name}.json"


def persist_spec(
    connection: sqlite3.Connection,
    *,
    spec_key: str,
    status: str,
    spec_json: dict,
) -> None:
    connection.execute(
        """
        UPDATE indicator_specs
        SET status = ?,
            spec_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE spec_key = ?
        """,
        (status, json.dumps(spec_json, sort_keys=True), spec_key),
    )


def upgrade_indicator_specs(
    connection: sqlite3.Connection,
    *,
    validation_log: dict | None = None,
) -> dict:
    validation_lookup = build_validation_lookup(validation_log or {"validations": []})
    updated_specs: list[str] = []
    promoted_specs: list[str] = []
    validation_backed_specs: list[str] = []

    for spec_entry in load_indicator_specs(connection):
        original_status = spec_entry["status"]
        original_spec = deepcopy(spec_entry["spec_json"])
        spec_with_contract = apply_backtest_contract(original_spec)
        promoted_status, evidence = promote_status_from_validations(
            original_status,
            validations_for_spec(spec_entry, validation_lookup),
        )
        final_spec = apply_status_markers(spec_with_contract, promoted_status)
        final_spec = apply_validation_evidence(final_spec, evidence)

        if evidence is not None:
            validation_backed_specs.append(spec_entry["spec_key"])

        if final_spec == original_spec and promoted_status == original_status:
            continue

        persist_spec(
            connection,
            spec_key=spec_entry["spec_key"],
            status=promoted_status,
            spec_json=final_spec,
        )
        artifact_path = resolve_artifact_path(
            {"spec_key": spec_entry["spec_key"], "spec_json": final_spec}
        )
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(final_spec, indent=2), encoding="utf-8")
        updated_specs.append(spec_entry["spec_key"])
        if promoted_status != original_status:
            promoted_specs.append(spec_entry["spec_key"])

    return {
        "updated_spec_count": len(updated_specs),
        "updated_specs": updated_specs,
        "promoted_spec_count": len(promoted_specs),
        "promoted_specs": promoted_specs,
        "validation_backed_spec_count": len(sorted(set(validation_backed_specs))),
        "validation_backed_specs": sorted(set(validation_backed_specs)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upgrade indicator specs with explicit backtest contracts and promote specs backed by successful TradingView validations."
    )
    parser.add_argument("--validation-log", default=str(DEFAULT_VALIDATION_PATH))
    args = parser.parse_args()

    validation_log = load_validation_log(Path(args.validation_log))
    with sqlite3.connect(DB_PATH) as connection:
        result = upgrade_indicator_specs(connection, validation_log=validation_log)
        connection.commit()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
