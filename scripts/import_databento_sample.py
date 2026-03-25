from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pyarrow.parquet as pq

from runtime.harness import DEFAULT_TIMEZONE, infer_session_bucket


DEFAULT_DEST_DIR = ROOT / "data" / "databento"
FALLBACK_SOURCE_DIR = Path.home() / "Repos" / "Trade-Analytics" / "data" / "databento"
PARQUET_COLUMNS = ["Open", "High", "Low", "Close", "Volume", "ts_event"]
CSV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "session"]


@dataclass
class ImportedFileSummary:
    symbol: str
    timeframe: str
    source_path: str
    raw_copy_path: str
    normalized_csv_path: str
    row_count: int
    first_timestamp: str | None
    last_timestamp: str | None


def resolve_source_dir(explicit_source_dir: str | None) -> Path:
    if explicit_source_dir:
        return Path(explicit_source_dir).expanduser().resolve()
    return FALLBACK_SOURCE_DIR


def iter_batches(parquet_path: Path):
    parquet_file = pq.ParquetFile(parquet_path)
    yield from parquet_file.iter_batches(batch_size=100_000, columns=PARQUET_COLUMNS)


def copy_raw_file(source_path: Path, raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / source_path.name
    shutil.copy2(source_path, destination)
    return destination


def normalize_symbol(source_path: Path) -> str:
    return source_path.stem.replace("_minute", "").upper()


def arrow_timestamp_to_datetime(raw_nanoseconds: int, *, timezone_name: str) -> datetime:
    seconds, nanoseconds = divmod(raw_nanoseconds, 1_000_000_000)
    timestamp = datetime.fromtimestamp(seconds, tz=UTC).replace(
        microsecond=nanoseconds // 1_000
    )
    return timestamp.astimezone(ZoneInfo(timezone_name))


def write_normalized_csv(
    source_path: Path,
    destination_path: Path,
    *,
    timezone_name: str,
) -> ImportedFileSummary:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    symbol = normalize_symbol(source_path)
    row_count = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None

    with destination_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for batch in iter_batches(source_path):
            open_array = batch.column(batch.schema.get_field_index("Open"))
            high_array = batch.column(batch.schema.get_field_index("High"))
            low_array = batch.column(batch.schema.get_field_index("Low"))
            close_array = batch.column(batch.schema.get_field_index("Close"))
            volume_array = batch.column(batch.schema.get_field_index("Volume"))
            timestamp_array = batch.column(batch.schema.get_field_index("ts_event"))
            batch_length = batch.num_rows
            for index in range(batch_length):
                timestamp = arrow_timestamp_to_datetime(
                    timestamp_array[index].value,
                    timezone_name=timezone_name,
                )
                timestamp_iso = timestamp.isoformat()
                session = infer_session_bucket(timestamp, timezone_name=timezone_name)
                writer.writerow(
                    {
                        "timestamp": timestamp_iso,
                        "open": open_array[index].as_py(),
                        "high": high_array[index].as_py(),
                        "low": low_array[index].as_py(),
                        "close": close_array[index].as_py(),
                        "volume": volume_array[index].as_py(),
                        "session": session,
                    }
                )
                row_count += 1
                if first_timestamp is None:
                    first_timestamp = timestamp_iso
                last_timestamp = timestamp_iso

    return ImportedFileSummary(
        symbol=symbol,
        timeframe="1m",
        source_path=str(source_path),
        raw_copy_path="",
        normalized_csv_path=str(destination_path),
        row_count=row_count,
        first_timestamp=first_timestamp,
        last_timestamp=last_timestamp,
    )


def import_databento_sample(
    *,
    source_dir: Path,
    dest_dir: Path,
    timezone_name: str,
) -> dict[str, object]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    parquet_files = sorted(source_dir.glob("*_minute.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No *_minute.parquet files found in {source_dir}")

    raw_dir = dest_dir / "raw"
    bars_dir = dest_dir / "bars"
    dest_dir.mkdir(parents=True, exist_ok=True)

    imported_files: list[ImportedFileSummary] = []
    for source_path in parquet_files:
        raw_copy_path = copy_raw_file(source_path, raw_dir)
        normalized_csv_path = bars_dir / f"{source_path.stem}.csv"
        summary = write_normalized_csv(
            source_path,
            normalized_csv_path,
            timezone_name=timezone_name,
        )
        summary.raw_copy_path = str(raw_copy_path)
        imported_files.append(summary)

    manifest = {
        "source_dir": str(source_dir),
        "destination_dir": str(dest_dir),
        "raw_dir": str(raw_dir),
        "bars_dir": str(bars_dir),
        "timezone": timezone_name,
        "imported_at": datetime.now().astimezone().isoformat(),
        "files": [asdict(item) for item in imported_files],
    }

    manifest_path = dest_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Copy databento sample parquet files into the repo and emit replay-compatible CSV bars."
        )
    )
    parser.add_argument("--source-dir", default=str(FALLBACK_SOURCE_DIR))
    parser.add_argument("--dest-dir", default=str(DEFAULT_DEST_DIR))
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    args = parser.parse_args()

    manifest = import_databento_sample(
        source_dir=resolve_source_dir(args.source_dir),
        dest_dir=Path(args.dest_dir).expanduser().resolve(),
        timezone_name=args.timezone,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
