from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_DATA_DIR = Path("data") / "databento"
DEFAULT_OUTPUT_PATH = Path("results") / "raw_market_data_ingestion_manifest.json"
DEFAULT_REQUIRED_SYMBOLS = ("NQ", "ES", "GC")
DEFAULT_DERIVED_TIMEFRAMES = ("5m",)


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_symbol(value: str) -> str:
    return value.strip().upper()


def manifest_file_index(source_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in source_manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        symbol = normalize_symbol(str(item.get("symbol") or ""))
        if symbol:
            indexed[symbol] = item
    return indexed


def csv_fallback_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    row_count = 0
    first_timestamp = ""
    last_timestamp = ""
    first_row: dict[str, str] | None = None
    last_row: dict[str, str] | None = None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if first_row is None:
                first_row = dict(row)
                first_timestamp = str(row.get("timestamp") or "")
            last_row = dict(row)
            last_timestamp = str(row.get("timestamp") or "")
            row_count += 1
    return {
        "row_count": row_count,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "first_row": first_row or {},
        "last_row": last_row or {},
    }


def estimate_derived_bar_count(row_count: int, timeframe: str) -> int | None:
    if timeframe.endswith("m"):
        try:
            minutes = int(timeframe[:-1])
        except ValueError:
            return None
        if minutes > 0:
            return (row_count + minutes - 1) // minutes
    return None


def symbol_entry(
    symbol: str,
    *,
    source_item: dict[str, Any] | None,
    data_dir: Path,
    root_dir: Path,
    derived_timeframes: tuple[str, ...],
) -> dict[str, Any]:
    normalized = normalize_symbol(symbol)
    raw_path = data_dir / "raw" / f"{normalized.lower()}_minute.parquet"
    csv_path = data_dir / "bars" / f"{normalized.lower()}_minute.csv"
    if source_item:
        raw_path = resolve(root_dir, source_item.get("raw_copy_path") or raw_path)
        csv_path = resolve(root_dir, source_item.get("normalized_csv_path") or csv_path)

    fallback = csv_fallback_stats(csv_path) if source_item is None or source_item.get("row_count") is None else {}
    row_count = int(source_item.get("row_count") if source_item else fallback.get("row_count") or 0)
    first_timestamp = str((source_item or {}).get("first_timestamp") or fallback.get("first_timestamp") or "")
    last_timestamp = str((source_item or {}).get("last_timestamp") or fallback.get("last_timestamp") or "")
    has_raw = raw_path.exists()
    has_csv = csv_path.exists()
    blockers: list[str] = []
    if not has_raw:
        blockers.append("raw_parquet_missing")
    if not has_csv:
        blockers.append("normalized_1m_csv_missing")
    if row_count <= 0 and (has_raw or has_csv):
        blockers.append("row_count_missing_or_zero")
    status = "available" if has_raw and has_csv and row_count > 0 else "partial" if has_raw or has_csv else "missing"

    derived = []
    for timeframe in derived_timeframes:
        derived.append(
            {
                "timeframe": timeframe,
                "source_timeframe": "1m",
                "status": "derivable" if status == "available" and row_count > 0 else "blocked",
                "estimated_bar_count": estimate_derived_bar_count(row_count, timeframe) if row_count > 0 else None,
            }
        )

    return {
        "symbol": normalized,
        "status": status,
        "blocking_reasons": blockers,
        "available_timeframes": ["1m"] if has_csv else [],
        "derived_timeframes": derived,
        "raw_copy_path": relative_or_absolute(raw_path, root_dir),
        "normalized_csv_path": relative_or_absolute(csv_path, root_dir),
        "row_count": row_count,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "source_manifest_item": source_item or {},
    }


def build_raw_market_data_manifest(
    *,
    root_dir: Path,
    data_dir: Path,
    required_symbols: tuple[str, ...] = DEFAULT_REQUIRED_SYMBOLS,
    derived_timeframes: tuple[str, ...] = DEFAULT_DERIVED_TIMEFRAMES,
) -> dict[str, Any]:
    source_manifest_path = data_dir / "manifest.json"
    source_manifest = load_json(source_manifest_path, {})
    indexed = manifest_file_index(source_manifest if isinstance(source_manifest, dict) else {})
    required = tuple(normalize_symbol(symbol) for symbol in required_symbols)
    required_entries = [
        symbol_entry(
            symbol,
            source_item=indexed.get(symbol),
            data_dir=data_dir,
            root_dir=root_dir,
            derived_timeframes=derived_timeframes,
        )
        for symbol in required
    ]
    extra_symbols = sorted(symbol for symbol in indexed if symbol not in set(required))
    missing = [entry["symbol"] for entry in required_entries if entry["status"] != "available"]
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Pre-GPU raw market data ingestion audit for NQ / ES / GC chart-state and controlled-chart work.",
        "source_manifest_path": relative_or_absolute(source_manifest_path, root_dir),
        "source_manifest_imported_at": str(source_manifest.get("imported_at") or "") if isinstance(source_manifest, dict) else "",
        "timezone": str(source_manifest.get("timezone") or "America/New_York") if isinstance(source_manifest, dict) else "America/New_York",
        "required_symbols": list(required),
        "derived_timeframes_required": list(derived_timeframes),
        "summary": {
            "required_symbol_count": len(required_entries),
            "available_required_symbol_count": sum(1 for entry in required_entries if entry["status"] == "available"),
            "missing_or_partial_required_symbols": missing,
            "extra_source_symbols_present": extra_symbols,
            "raw_data_gate": "pass" if not missing else "blocked",
            "next_action": (
                "Raw NQ/ES/GC lane is complete enough for controlled-chart lineage."
                if not missing
                else "Add or import the missing required symbols before treating raw data as complete."
            ),
        },
        "symbols": required_entries,
        "extra_symbols_present": [
            symbol_entry(
                symbol,
                source_item=indexed.get(symbol),
                data_dir=data_dir,
                root_dir=root_dir,
                derived_timeframes=derived_timeframes,
            )
            for symbol in extra_symbols
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a pre-GPU raw market data ingestion manifest.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_REQUIRED_SYMBOLS))
    parser.add_argument("--derived-timeframes", nargs="+", default=list(DEFAULT_DERIVED_TIMEFRAMES))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    data_dir = resolve(root_dir, args.data_dir)
    output_path = resolve(root_dir, args.output)
    manifest = build_raw_market_data_manifest(
        root_dir=root_dir,
        data_dir=data_dir,
        required_symbols=tuple(args.symbols),
        derived_timeframes=tuple(args.derived_timeframes),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        "Built raw market data manifest: "
        f"{relative_or_absolute(output_path, root_dir)} "
        f"gate={manifest['summary']['raw_data_gate']} "
        f"missing={manifest['summary']['missing_or_partial_required_symbols']}"
    )


if __name__ == "__main__":
    main()
