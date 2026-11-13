from __future__ import annotations

import json
from pathlib import Path

from scripts.build_raw_market_data_manifest import build_raw_market_data_manifest


def _write_csv(path: Path, timestamps: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["timestamp,open,high,low,close,volume"]
    rows.extend(f"{timestamp},1,2,0.5,1.5,10" for timestamp in timestamps)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_raw(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"parquet-placeholder")


def _write_source_manifest(data_dir: Path, symbols: list[str]) -> None:
    files = []
    for symbol in symbols:
        normalized = symbol.lower()
        files.append(
            {
                "symbol": symbol,
                "timeframe": "1m",
                "raw_copy_path": str(data_dir / "raw" / f"{normalized}_minute.parquet"),
                "normalized_csv_path": str(data_dir / "bars" / f"{normalized}_minute.csv"),
                "row_count": 6,
                "first_timestamp": "2026-06-01T09:30:00-04:00",
                "last_timestamp": "2026-06-01T09:35:00-04:00",
            }
        )
    payload = {
        "timezone": "America/New_York",
        "imported_at": "2026-06-23T10:00:00-04:00",
        "files": files,
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_default_raw_market_data_gate_passes_for_es_nq_gc(tmp_path: Path) -> None:
    data_dir = tmp_path / "data" / "databento"
    for symbol in ("ES", "NQ", "GC"):
        _write_raw(data_dir / "raw" / f"{symbol.lower()}_minute.parquet")
        _write_csv(
            data_dir / "bars" / f"{symbol.lower()}_minute.csv",
            [
                "2026-06-01T09:30:00-04:00",
                "2026-06-01T09:31:00-04:00",
                "2026-06-01T09:32:00-04:00",
                "2026-06-01T09:33:00-04:00",
                "2026-06-01T09:34:00-04:00",
                "2026-06-01T09:35:00-04:00",
            ],
        )
    _write_source_manifest(data_dir, ["ES", "NQ", "GC"])

    manifest = build_raw_market_data_manifest(root_dir=tmp_path, data_dir=data_dir)

    assert manifest["required_symbols"] == ["NQ", "ES", "GC"]
    assert manifest["summary"]["raw_data_gate"] == "pass"
    assert manifest["summary"]["available_required_symbol_count"] == 3
    assert manifest["summary"]["missing_or_partial_required_symbols"] == []
    assert manifest["summary"]["extra_source_symbols_present"] == []
    nq = next(symbol for symbol in manifest["symbols"] if symbol["symbol"] == "NQ")
    assert nq["status"] == "available"
    assert nq["blocking_reasons"] == []
    assert nq["derived_timeframes"] == [
        {
            "timeframe": "5m",
            "source_timeframe": "1m",
            "status": "derivable",
            "estimated_bar_count": 2,
        }
    ]


def test_csv_without_raw_parquet_is_partial_and_blocks_gate(tmp_path: Path) -> None:
    data_dir = tmp_path / "data" / "databento"
    _write_csv(
        data_dir / "bars" / "gc_minute.csv",
        ["2026-06-01T09:30:00-04:00", "2026-06-01T09:31:00-04:00"],
    )

    manifest = build_raw_market_data_manifest(
        root_dir=tmp_path,
        data_dir=data_dir,
        required_symbols=("GC",),
    )

    assert manifest["summary"]["raw_data_gate"] == "blocked"
    assert manifest["summary"]["missing_or_partial_required_symbols"] == ["GC"]
    gc = manifest["symbols"][0]
    assert gc["status"] == "partial"
    assert gc["row_count"] == 2
    assert gc["first_timestamp"] == "2026-06-01T09:30:00-04:00"
    assert gc["last_timestamp"] == "2026-06-01T09:31:00-04:00"
    assert gc["blocking_reasons"] == ["raw_parquet_missing"]
    assert gc["derived_timeframes"][0]["status"] == "blocked"
