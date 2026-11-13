from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import sys
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
from PIL import Image


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


DEFAULT_DATA_DIR = Path("data") / "databento"
DEFAULT_OUTPUT_DIR = Path("results") / "controlled_charts"
DEFAULT_SYMBOLS = ("NQ", "ES", "GC")
DEFAULT_TIMEZONE = "America/New_York"
REVIEW_ACTIONS = ("accept", "adjust", "reject", "defer")
TIMEFRAME_SPECS = {
    "1D": {"rule": "1D", "visible_bars": 80, "raw_span": timedelta(days=1), "filename": "daily"},
    "1h": {"rule": "1h", "visible_bars": 120, "raw_span": timedelta(hours=1), "filename": "h1"},
    "5m": {"rule": "5min", "visible_bars": 240, "raw_span": timedelta(minutes=5), "filename": "m5"},
}
_CHART_DEPS: tuple[Any, Any] | None = None


def load_chart_dependencies() -> tuple[Any, Any]:
    global _CHART_DEPS
    if _CHART_DEPS is not None:
        return _CHART_DEPS
    # Pandas may print noisy optional-extension traces when numexpr/bottleneck
    # were compiled against an older NumPy. Those accelerators are not required
    # for this deterministic rendering lane.
    with contextlib.redirect_stderr(io.StringIO()):
        import mplfinance as mpf
        import pandas as pd

    _CHART_DEPS = (pd, mpf)
    return _CHART_DEPS


def resolve(root_dir: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root_dir / candidate


def relative_or_absolute(path: Path, root_dir: Path) -> str:
    try:
        return str(path.resolve().relative_to(root_dir.resolve()))
    except ValueError:
        return str(path)


def normalize_symbol(value: str) -> str:
    return value.strip().upper()


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_tail_rows(csv_path: Path, *, max_rows: int) -> pd.DataFrame:
    pd, _mpf = load_chart_dependencies()
    rows: deque[dict[str, str]] = deque(maxlen=max_rows)
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(dict(row))
    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    timestamp = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.assign(timestamp=timestamp).dropna(subset=["timestamp"])
    if frame.empty:
        return frame
    frame["timestamp"] = frame["timestamp"].dt.tz_convert(DEFAULT_TIMEZONE)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close"])
    frame["volume"] = frame["volume"].fillna(0)
    if "session" not in frame.columns:
        frame["session"] = "unknown"
    frame["session"] = frame["session"].fillna("unknown").astype(str)
    frame = frame.sort_values("timestamp").set_index("timestamp")
    return frame


def dominant_session(values: pd.Series) -> str:
    cleaned = [str(value).strip() or "unknown" for value in values.tolist()]
    if not cleaned:
        return "unknown"
    return Counter(cleaned).most_common(1)[0][0]


def filter_price_outliers(
    frame: pd.DataFrame,
    *,
    min_ratio: float = 0.5,
    max_ratio: float = 1.5,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if frame.empty:
        return frame, {
            "method": "median_ohlc_ratio",
            "input_row_count": 0,
            "kept_row_count": 0,
            "removed_row_count": 0,
        }
    median_close = float(frame["close"].median())
    min_price = median_close * min_ratio
    max_price = median_close * max_ratio
    valid = (
        frame[["open", "high", "low", "close"]]
        .ge(min_price)
        .all(axis=1)
        & frame[["open", "high", "low", "close"]].le(max_price).all(axis=1)
    )
    filtered = frame[valid].copy()
    return filtered, {
        "method": "median_ohlc_ratio",
        "median_close": round(median_close, 6),
        "min_price": round(min_price, 6),
        "max_price": round(max_price, 6),
        "input_row_count": int(len(frame)),
        "kept_row_count": int(len(filtered)),
        "removed_row_count": int(len(frame) - len(filtered)),
        "removed_ratio": round((len(frame) - len(filtered)) / max(1, len(frame)), 6),
    }


def resample_bars(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    spec = TIMEFRAME_SPECS[timeframe]
    resampled = frame.resample(
        str(spec["rule"]),
        label="right",
        closed="right",
    ).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "session": dominant_session,
        }
    )
    return resampled.dropna(subset=["open", "high", "low", "close"])


def iso(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def contract_for_symbol(symbol: str, source_item: dict[str, Any] | None) -> str:
    if source_item and source_item.get("source_path"):
        return f"{symbol}_continuous_from_{Path(str(source_item['source_path'])).stem}"
    return f"{symbol}_continuous_1m"


def render_chart(
    bars: pd.DataFrame,
    *,
    output_path: Path,
    title: str,
    width: int,
    height: int,
    dpi: int,
) -> dict[str, Any]:
    _pd, mpf = load_chart_dependencies()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plot_frame = bars.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )[["Open", "High", "Low", "Close", "Volume"]]
    market_colors = mpf.make_marketcolors(
        up="#089981",
        down="#f23645",
        edge="inherit",
        wick="inherit",
        volume="in",
    )
    style = mpf.make_mpf_style(
        base_mpf_style="yahoo",
        marketcolors=market_colors,
        gridstyle="-",
        facecolor="white",
        figcolor="white",
        rc={"font.size": 8},
    )
    fig, _axes = mpf.plot(
        plot_frame,
        type="candle",
        volume=True,
        style=style,
        returnfig=True,
        figsize=(width / dpi, height / dpi),
        tight_layout=False,
    )
    for axis in fig.axes:
        axis.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    fig.subplots_adjust(left=0.06, right=0.90, top=0.98, bottom=0.12, hspace=0.03)
    fig.savefig(output_path, dpi=dpi, facecolor="white")
    plt.close(fig)
    with Image.open(output_path) as image:
        actual_width, actual_height = image.size
    return {
        "library": "mplfinance",
        "width": actual_width,
        "height": actual_height,
        "requested_width": width,
        "requested_height": height,
        "dpi": dpi,
    }


def build_image_lineage(
    *,
    root_dir: Path,
    symbol: str,
    contract: str,
    source_csv_path: Path,
    source_item: dict[str, Any] | None,
    raw_frame: pd.DataFrame,
    timeframe: str,
    output_dir: Path,
    width: int,
    height: int,
    dpi: int,
    quality_filter: dict[str, Any],
) -> dict[str, Any]:
    rendered = resample_bars(raw_frame, timeframe)
    spec = TIMEFRAME_SPECS[timeframe]
    visible = rendered.tail(int(spec["visible_bars"]))
    if visible.empty:
        return {
            "symbol": symbol,
            "contract": contract,
            "timeframe": timeframe,
            "status": "blocked",
            "blocking_reasons": ["no_renderable_bars"],
            "image_path": "",
        }

    raw_start_cutoff = visible.index.min() - spec["raw_span"] + timedelta(minutes=1)
    raw_window = raw_frame[(raw_frame.index >= raw_start_cutoff) & (raw_frame.index <= visible.index.max())]
    if raw_window.empty:
        raw_window = raw_frame.tail(1)

    image_id = f"controlled_{symbol}_{str(spec['filename'])}_{visible.index.max().strftime('%Y%m%dT%H%M%S%z')}"
    image_path = output_dir / "images" / symbol.lower() / f"{image_id}.png"
    renderer = render_chart(
        visible,
        output_path=image_path,
        title=f"{contract} {timeframe}",
        width=width,
        height=height,
        dpi=dpi,
    )
    session_counts = Counter(str(value) for value in raw_window["session"].tolist())
    session_values = sorted(session_counts)
    return {
        "image_id": image_id,
        "symbol": symbol,
        "contract": contract,
        "timeframe": timeframe,
        "source_timeframe": "1m",
        "status": "captured",
        "image_path": relative_or_absolute(image_path, root_dir),
        "source_csv_path": relative_or_absolute(source_csv_path, root_dir),
        "source_raw_path": relative_or_absolute(
            resolve(root_dir, source_item.get("raw_copy_path", "")) if source_item else source_csv_path,
            root_dir,
        ),
        "visible_range": {
            "start": iso(visible.index.min()),
            "end": iso(visible.index.max()),
            "bar_count": int(len(visible)),
        },
        "raw_timestamp_range": {
            "start": iso(raw_window.index.min()),
            "end": iso(raw_window.index.max()),
            "row_count": int(len(raw_window)),
        },
        "session": {
            "dominant": session_counts.most_common(1)[0][0] if session_counts else "unknown",
            "values": session_values,
            "counts": dict(sorted(session_counts.items())),
        },
        "quality_filter": quality_filter,
        "renderer": renderer,
        "review": {
            "status": "defer",
            "allowed_actions": list(REVIEW_ACTIONS),
            "training_eligible": False,
            "note": "Controlled raw-bar chart is review-only until accepted or adjusted in CVAT/Label Studio.",
        },
        "source_manifest_item": source_item or {},
    }


def source_manifest_index(data_dir: Path) -> dict[str, dict[str, Any]]:
    manifest = read_json(data_dir / "manifest.json", {})
    if not isinstance(manifest, dict):
        return {}
    indexed = {}
    for item in manifest.get("files", []):
        if not isinstance(item, dict):
            continue
        symbol = normalize_symbol(str(item.get("symbol") or ""))
        if symbol:
            indexed[symbol] = item
    return indexed


def clear_previous_symbol_images(output_dir: Path, symbols: tuple[str, ...]) -> None:
    for symbol in symbols:
        symbol_dir = output_dir / "images" / normalize_symbol(symbol).lower()
        if not symbol_dir.exists():
            continue
        for image_path in symbol_dir.glob("controlled_*.png"):
            if image_path.is_file():
                image_path.unlink()


def build_controlled_chart_lineage(
    *,
    root_dir: Path,
    data_dir: Path,
    output_dir: Path,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    tail_rows: int = 250_000,
    width: int = 1280,
    height: int = 720,
    dpi: int = 100,
) -> dict[str, Any]:
    root_dir = root_dir.resolve()
    data_dir = resolve(root_dir, data_dir)
    output_dir = resolve(root_dir, output_dir)
    normalized_symbols = tuple(normalize_symbol(symbol) for symbol in symbols)
    clear_previous_symbol_images(output_dir, normalized_symbols)
    indexed = source_manifest_index(data_dir)
    items: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw_symbol in normalized_symbols:
        symbol = normalize_symbol(raw_symbol)
        source_item = indexed.get(symbol)
        source_csv = resolve(
            root_dir,
            source_item.get("normalized_csv_path") if source_item else data_dir / "bars" / f"{symbol.lower()}_minute.csv",
        )
        if not source_csv.exists():
            missing.append(symbol)
            items.append(
                {
                    "symbol": symbol,
                    "status": "blocked",
                    "blocking_reasons": ["normalized_1m_csv_missing"],
                    "source_csv_path": relative_or_absolute(source_csv, root_dir),
                    "images": [],
                }
            )
            continue
        raw_frame = load_tail_rows(source_csv, max_rows=tail_rows)
        filtered_frame, quality_filter = filter_price_outliers(raw_frame)
        if filtered_frame.empty:
            missing.append(symbol)
            items.append(
                {
                    "symbol": symbol,
                    "status": "blocked",
                    "blocking_reasons": ["no_quality_filtered_raw_rows_loaded"],
                    "source_csv_path": relative_or_absolute(source_csv, root_dir),
                    "quality_filter": quality_filter,
                    "images": [],
                }
            )
            continue
        contract = contract_for_symbol(symbol, source_item)
        images = [
            build_image_lineage(
                root_dir=root_dir,
                symbol=symbol,
                contract=contract,
                source_csv_path=source_csv,
                source_item=source_item,
                raw_frame=filtered_frame,
                timeframe=timeframe,
                output_dir=output_dir,
                width=width,
                height=height,
                dpi=dpi,
                quality_filter=quality_filter,
            )
            for timeframe in ("1D", "1h", "5m")
        ]
        blocked = [image for image in images if image.get("status") != "captured"]
        if blocked:
            missing.append(symbol)
        items.append(
            {
                "symbol": symbol,
                "contract": contract,
                "status": "captured" if not blocked else "partial",
                "source_csv_path": relative_or_absolute(source_csv, root_dir),
                "tail_rows_loaded": int(len(raw_frame)),
                "quality_filtered_rows_loaded": int(len(filtered_frame)),
                "quality_filter": quality_filter,
                "raw_tail_timestamp_range": {
                    "start": iso(raw_frame.index.min()),
                    "end": iso(raw_frame.index.max()),
                },
                "images": images,
            }
        )

    image_count = sum(1 for item in items for image in item.get("images", []) if image.get("status") == "captured")
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Controlled raw-bar chart image lineage for pre-GPU TTrades review.",
        "review_policy": {
            "candidate_only": True,
            "training_eligible_default": False,
            "allowed_actions": list(REVIEW_ACTIONS),
            "promotion_requires_visual_review": True,
        },
        "source_data_dir": relative_or_absolute(data_dir, root_dir),
        "output_dir": relative_or_absolute(output_dir, root_dir),
        "symbols": list(normalized_symbols),
        "summary": {
            "symbol_count": len(symbols),
            "captured_symbol_count": sum(1 for item in items if item.get("status") == "captured"),
            "image_count": image_count,
            "blocked_or_partial_symbols": sorted(set(missing)),
            "lineage_gate": "pass" if not missing and image_count else "blocked",
        },
        "items": items,
    }


def write_manifest(manifest: dict[str, Any], *, root_dir: Path, output_dir: Path) -> Path:
    output_dir = resolve(root_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "controlled_chart_lineage_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render controlled chart images from raw 1m bars and emit lineage.")
    parser.add_argument("--root-dir", type=Path, default=Path("."))
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--tail-rows", type=int, default=250_000)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--dpi", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = args.root_dir.resolve()
    manifest = build_controlled_chart_lineage(
        root_dir=root_dir,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        symbols=tuple(args.symbols),
        tail_rows=args.tail_rows,
        width=args.width,
        height=args.height,
        dpi=args.dpi,
    )
    manifest_path = write_manifest(manifest, root_dir=root_dir, output_dir=args.output_dir)
    print(
        "Built controlled chart lineage: "
        f"{relative_or_absolute(manifest_path, root_dir)} "
        f"gate={manifest['summary']['lineage_gate']} "
        f"images={manifest['summary']['image_count']}"
    )


if __name__ == "__main__":
    main()
