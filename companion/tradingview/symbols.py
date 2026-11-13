"""Companion symbol -> TradingView ticker, read from ``companion/config/symbols.json``.

The file is read on every use, so an edit takes effect at the next check.

Settings (all optional):

- ``port``: TradingView Desktop's debug port (the launcher starts it on 9222)
- ``settle_seconds``: how long after a bar's scheduled close it counts as closed, so the
  last trade of the bar has arrived
- ``daily_stamp_shift_days``: correction, in days, added to the trading date read from
  TradingView's daily / weekly / monthly bar times (see ``companion.tradingview.mapping``)
- ``daily_and_above``: ``"native"`` re-reads TradingView's own daily / weekly / monthly bar
  when one closes (its close can be the settlement price); ``"derived"`` builds it from
  the entry-timeframe bars instead
- ``max_series``: how many private data series the feed keeps open at once inside
  TradingView (one per symbol and timeframe read; the least recently read is closed first)
- ``settlement_as_close``: ask TradingView for daily bars that close at the settlement
  price (its "Use settlement as close on daily interval" chart setting) instead of the
  last trade. Off, as on the trader's own charts
- ``session``: the session asked for, as a chart does: ``"extended"`` is the full
  electronic session for futures (18:00 -> 17:00 New York); ``"regular"`` for stocks
  leaves out pre- and post-market
- ``close_on_next_bar``: the headless core's live loop (``python -m companion.core``) may
  count an intraday entry bar as closed as soon as TradingView has opened the bar after
  it, instead of waiting ``settle_seconds`` past its scheduled close (see
  ``companion.tradingview.source``). ``false`` waits for the settle time as the Tk window
  does. The Tk window never uses it
"""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from companion import paths as _paths
from companion.tradingview.errors import TradingViewError

SYMBOLS_PATH = _paths.resource("config", "symbols.json")


@dataclass(frozen=True)
class FeedSettings:
    port: int = 9222
    settle_seconds: float = 3.0
    daily_stamp_shift_days: int = 0
    daily_and_above: str = "native"
    max_series: int = 4
    settlement_as_close: bool = False
    session: str = "extended"
    close_on_next_bar: bool = True


def _read(path: Path | None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else SYMBOLS_PATH
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError:
        raise TradingViewError(
            "unknown_symbol", f"The symbol list {config_path} is missing, so no symbol can be matched to a TradingView ticker."
        ) from None
    except ValueError as error:
        raise TradingViewError("unknown_symbol", f"The symbol list {config_path} is not valid JSON ({error}). Fix it and press Check.") from None
    if not isinstance(data, dict) or not isinstance(data.get("symbols"), dict):
        raise TradingViewError("unknown_symbol", f"The symbol list {config_path} needs a 'symbols' object.")
    return data


def list_symbols(path: Path | None = None) -> list[str]:
    """The symbols the live feed offers, in file order."""
    return [str(name).upper() for name in _read(path)["symbols"]]


def ticker_for(symbol: str, path: Path | None = None) -> str:
    """The TradingView ticker of ``symbol``; a plain-language error when it has none."""
    entries = {str(name).upper(): entry for name, entry in _read(path)["symbols"].items()}
    key = str(symbol).upper()
    if key not in entries:
        known = ", ".join(entries) or "none"
        raise TradingViewError(
            "unknown_symbol",
            f"{symbol} has no TradingView ticker yet. Add it to companion/config/symbols.json (it lists: {known}).",
        )
    entry = entries[key]
    ticker = entry.get("ticker") if isinstance(entry, dict) else entry
    if not isinstance(ticker, str) or not ticker.strip():
        raise TradingViewError(
            "unknown_symbol", f"The entry for {symbol} in companion/config/symbols.json needs a 'ticker', for example CME_MINI:NQ1!."
        )
    return ticker.strip()


def settings(path: Path | None = None) -> FeedSettings:
    """The feed settings; defaults for anything missing or of the wrong type."""
    try:
        raw = _read(path).get("settings")
    except TradingViewError:
        return FeedSettings()
    values: dict[str, Any] = {}
    if isinstance(raw, dict):
        defaults = FeedSettings()
        for item in fields(FeedSettings):
            value = raw.get(item.name)
            default = getattr(defaults, item.name)
            if isinstance(default, bool):
                if isinstance(value, bool):
                    values[item.name] = value
            elif isinstance(default, (int, float)):
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    values[item.name] = type(default)(value)
            elif isinstance(value, str) and value:
                values[item.name] = value
    return FeedSettings(**values)
