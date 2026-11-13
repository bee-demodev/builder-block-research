"""Check the live TradingView link, one assumption at a time.

    .venv/Scripts/python.exe -m companion.tradingview.diagnose
    .venv/Scripts/python.exe -m companion.tradingview.diagnose --symbol ES --stack "4h / 15m / 1m"

Read-only. The feed opens private data series inside one of the open TradingView chart
tabs (see ``companion.tradingview.pagefeed``); no chart is changed and no tab is opened,
closed or brought forward. Every chart tab is asked what it shows before and after, to
prove nothing moved, and the charts' own bars are read to compare them with the feed's.
At the end the feed is taken out of the page again, unless it was already there when the
diagnostic started (a companion window is using it) or ``--keep`` is given.

Each line is PASS, FAIL or INFO. The checks run in the order the assumptions are most
likely to be wrong, so the first FAIL is the thing to fix.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import pandas as pd

from companion import timeframes as _timeframes
from companion.bars import bar_close_times, closed_bars, resample
from companion.tradingview import cdp
from companion.tradingview.bridge import CdpBridge
from companion.tradingview.errors import TradingViewError
from companion.tradingview.mapping import RESOLUTIONS, off_grid, resolution_for, rows_to_frame, same_resolution, stamps_to_new_york, trading_dates
from companion.tradingview.pagefeed import symbol_string
from companion.tradingview.source import TradingViewBarSource, nests
from companion.tradingview.symbols import settings as read_settings
from companion.tradingview.symbols import ticker_for

_PRICES = ["open", "high", "low", "close"]


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def line(self, verdict: str, text: str, detail: str = "") -> None:
        if verdict == "FAIL":
            self.failed += 1
        print(f"[{verdict}] {text}" + (f"\n         {detail}" if detail else ""), flush=True)

    def check(self, passed: bool, text: str, detail: str = "") -> bool:
        self.line("PASS" if passed else "FAIL", text, detail)
        return passed


def _fmt(frame: pd.DataFrame, rows: int = 3) -> str:
    return "; ".join(
        f"{when.strftime('%a %Y-%m-%d %H:%M')} O {row.open:.2f} H {row.high:.2f} L {row.low:.2f} C {row.close:.2f}"
        for when, row in zip(frame.index[-rows:], frame.iloc[-rows:].itertuples())
    )


def _compare(report: Report, source: TradingViewBarSource, symbol: str, higher: str, lower: str, now: pd.Timestamp) -> None:
    """TradingView's own ``higher`` bars against the same bars built from its ``lower`` bars."""
    tf_high, tf_low = _timeframes.parse_timeframe(higher), _timeframes.parse_timeframe(lower)
    if not nests(tf_low, tf_high):
        report.line("INFO", f"{higher} cannot be cross-checked against {lower} (bars do not nest)")
        return
    native = source.get_bars(symbol, higher, now, 6)
    if len(native) < 3:
        report.line("INFO", f"{higher}: too few closed bars to cross-check ({len(native)})")
        return
    span = int(tf_high.nominal_minutes / tf_low.nominal_minutes * 5 * 1.6) + 20
    built = resample(source.get_bars(symbol, lower, now, min(span, 6000)), higher)
    both = native.index.intersection(built.index)[-3:]
    both = both[both > built.index[0]] if len(built) else both  # the first built bar may be partial
    if not len(both):
        report.check(False, f"{higher} bars line up with bars built from {lower}", f"no common open times. native: {_fmt(native)} | built: {_fmt(built)}")
        return
    a, b = native.loc[both], built.loc[both]
    range_ok = bool(((a["high"] - b["high"]).abs() < 1e-6).all() and ((a["low"] - b["low"]).abs() < 1e-6).all())
    open_ok = bool(((a["open"] - b["open"]).abs() < 1e-6).all())
    close_ok = bool(((a["close"] - b["close"]).abs() < 1e-6).all())
    detail = f"native: {_fmt(a)}\n         built from {lower}: {_fmt(b)}"
    report.check(range_ok and open_ok, f"{higher}: open time, open, high and low equal the bars built from {lower} ({len(both)} bars)", detail)
    if close_ok:
        report.line("PASS", f"{higher}: close equals the last {lower} close")
    else:
        note = "TradingView's close is probably the settlement price; the companion uses TradingView's" if not tf_high.is_intraday else "unexpected for an intraday bar"
        report.line("INFO" if not tf_high.is_intraday else "FAIL", f"{higher}: close differs from the last {lower} close ({note})")


def _against_charts(report: Report, bridge: CdpBridge, tabs: list[dict[str, Any]], now: pd.Timestamp, keep_open: tuple[str, str], limit: int = 4) -> None:
    """The feed's bars against the bars the open charts hold themselves, same symbol and resolution."""
    settings = bridge.settings
    ours_asks = json.loads(symbol_string("X", settlement_as_close=settings.settlement_as_close, session=settings.session)[1:])
    labels = {resolution: label for label, resolution in RESOLUTIONS.items()}
    done: set[tuple[str, str]] = set()
    for tab in tabs:
        label = next((name for resolution, name in labels.items() if same_resolution(resolution, tab.get("resolution"))), None)
        key = (str(tab.get("symbol")), str(label))
        if label is None or not tab.get("symbol") or key in done or len(done) >= limit:
            continue
        done.add(key)
        try:
            chart = bridge.chart_bars(str(tab["id"]))
            theirs = closed_bars(rows_to_frame(chart.get("rows") or [], label, settings.daily_stamp_shift_days), label, now)
            ours = closed_bars(rows_to_frame(bridge.fetch_bars(key[0], resolution_for(label), 300).rows, label, settings.daily_stamp_shift_days), label, now)
        except (TradingViewError, cdp.CdpError) as error:
            report.line("INFO", f"{key[0]} {label}: could not be compared with your chart ({error})")
            continue
        finally:
            if key != keep_open:
                bridge.release(key[0], resolution_for(label))
        both = ours.index.intersection(theirs.index)
        if len(both) < 3:
            report.line("INFO", f"{key[0]} {label}: too few bars in common with your chart to compare ({len(both)})")
            continue
        differ = int(((ours.loc[both, _PRICES] - theirs.loc[both, _PRICES]).abs().max(axis=1) > 1e-9).sum())
        missing = int((theirs.index.difference(ours.index) >= ours.index[0]).sum()) + int((ours.index.difference(theirs.index) >= theirs.index[0]).sum())
        asked = json.loads(str(chart.get("asked") or "={}")[1:] or "{}")
        other = {name: asked.get(name) for name in ("session", "settlement-as-close") if asked.get(name, ours_asks.get(name)) != ours_asks.get(name)}
        text = f"{key[0]} {label}: the feed's bars equal the bars on your own chart ({len(both)} closed bars, times and OHLC)"
        detail = f"feed:  {_fmt(ours.loc[both], 2)}\n         chart: {_fmt(theirs.loc[both], 2)}"
        if other and (differ or missing):
            report.line("INFO", f"{key[0]} {label}: {differ} bar(s) differ from your chart, which is set differently ({other}); see settings in companion/config/symbols.json", detail)
        else:
            report.check(not differ and not missing, text, detail if not differ and not missing else f"{differ} differ, {missing} not in both\n         {detail}")


def run(symbol: str, stack_name: str, keep: bool, deep: int) -> int:
    report = Report()
    settings = read_settings()
    port = settings.port
    stack = _timeframes.get_stack(stack_name)
    ticker = ticker_for(symbol)
    print(f"TradingView live diagnostic: {symbol} -> {ticker}, stack {stack.name}, port {port}\n")

    # 1. the port
    if not cdp.port_answers(port):
        running = cdp.tradingview_is_running()
        report.check(False, f"debug port {port} answers", str(TradingViewError("no_debug_port" if running else "not_running")))
        return 1
    version = cdp.http_json(port, "/json/version")
    report.line("PASS", f"debug port {port} answers", f"{version.get('Browser', '?')}")

    bridge = CdpBridge(settings)
    before = bridge.peek_tabs()
    shown = lambda e: f"{e.get('symbol', '?')} {e.get('resolution', '?')}{' [on screen]' if e.get('visible') else ''} layout {e.get('layout') or '-'}"  # noqa: E731
    report.line("INFO", f"{len(before)} TradingView chart tab(s) open (asked what they show; nothing else)", "; ".join(shown(e) for e in before))

    source = TradingViewBarSource(bridge)
    was_there = False
    try:
        # 2. the feed: private data series inside one chart page
        started = time.monotonic()
        try:
            update = source.refresh(symbol, stack.entry)
        except TradingViewError as error:
            report.check(False, "the feed opens a private data series in a chart tab and loads the entry timeframe", f"{error}\n         technical: {error.technical}")
            return 1
        first_load = time.monotonic() - started
        host = bridge.report.get("host") or {}
        was_there = bool(host.get("reused_feed"))
        where = "a background tab" if not host.get("visible") else "the tab on screen (no background chart tab is open)"
        report.line(
            "PASS",
            f"feed installed in {where}: {host.get('symbol')} {host.get('resolution')} layout {host.get('layout') or '-'}",
            "a companion's feed was already in that page and is shared" if was_there else "no chart is involved: the series are the feed's own",
        )
        if host.get("visible"):
            report.line("INFO", "nothing on that chart changes; open a second chart tab if you would rather the feed sat in a background one")

        # 3. the series as TradingView reports it
        entry_resolution = resolution_for(stack.entry)
        state = bridge.status(ticker, entry_resolution)
        info = (bridge.report.get("series") or {}).get("info") or {}
        mode = str(state.get("mode") or "")
        report.check(
            state.get("state") == "ready" and bool(state.get("connected")),
            f"{stack.entry} series is ready on the page's own data connection (mode: {mode or '?'})",
            f"symbol info: {info}",
        )
        live = mode in ("streaming", "pulsed")
        report.check(live, f"data is real-time ({mode})" if live else f"data is NOT real-time: {mode}; the window says so beside the source")
        if state.get("server_time"):
            skew = float(state["server_time"]) / 1000 - time.time()
            report.check(abs(skew) < 2.0, f"this computer's clock agrees with TradingView's ({skew:+.2f} s)", "bars are called closed by this computer's clock")

        # 4. entry timeframe: bars, forming bar, cost
        now = source.now()
        report.line(
            "PASS",
            f"{stack.entry}: first load took {first_load:.2f} s; last closed bar opens {update.last_open.strftime('%a %H:%M')} New York, closes {update.last_close.strftime('%H:%M')}",
            f"notes: {update.notes or 'none'}",
        )
        raw = bridge.fetch_bars(ticker, entry_resolution, 5)
        stamps = stamps_to_new_york([row[0] for row in raw.rows])
        forming = bar_close_times(rows_to_frame(raw.rows, stack.entry), stack.entry)[-1] > now
        what = "still forming and is dropped" if forming else "closed (market shut)"
        report.line("INFO", f"{stack.entry}: newest raw bar opens {stamps[-1].strftime('%a %H:%M:%S')} New York; the clock says {now.strftime('%H:%M:%S')}; it is {what}")
        kept = source.get_bars(symbol, stack.entry, now, 3)
        kept_close = bar_close_times(kept.iloc[-1:], stack.entry)[0]
        report.check(kept_close <= now, f"{stack.entry}: the newest bar handed to the rules closed at {kept_close.strftime('%H:%M:%S')}, not after the clock")
        report.check(not off_grid(stamps, stack.entry).any(), f"{stack.entry}: bar times sit on the companion's grid")
        lag = (now - update.last_close).total_seconds()
        market_open = lag < 3 * _timeframes.parse_timeframe(stack.entry).nominal_minutes * 60
        report.line("INFO", f"{stack.entry}: last closed bar is {lag / 60:.1f} min old" + ("" if market_open else " (market shut, or TradingView has stopped sending)"))
        timings = []
        for _ in range(5):
            tick = time.monotonic()
            source.refresh(symbol, stack.entry)
            timings.append(time.monotonic() - tick)
        report.check(max(timings) < 1.0, f"a refresh takes {1000 * sum(timings) / len(timings):.0f} ms on average, {1000 * max(timings):.0f} ms at worst")

        # 5. the series keeps updating where it lives (a background tab)
        first = bridge.status(ticker, entry_resolution)
        wait = 12 if market_open else 3
        deadline = time.monotonic() + wait
        latest = first
        while time.monotonic() < deadline and latest.get("updates") == first.get("updates"):
            time.sleep(0.5)
            latest = bridge.status(ticker, entry_resolution)
        place = "in the background" if not host.get("visible") else "on screen"
        if latest.get("updates") != first.get("updates"):
            report.line("PASS", f"{stack.entry}: live updates keep arriving while the host tab is {place}")
        elif market_open:
            report.check(False, f"{stack.entry}: no live update arrived in {wait} s although the market is open (host tab {place})")
        else:
            report.line("INFO", f"{stack.entry}: no live update in {wait} s: the market is shut, so this cannot be checked now")

        # 6. against the charts TradingView itself shows
        _against_charts(report, bridge, before, source.now(), keep_open=(ticker, stack.entry))

        # 7. every timeframe: raw stamps, mapping, cross-checks
        for label in dict.fromkeys((stack.setup, stack.bias, "1D", "4h", "1W", "1M")):
            tf = _timeframes.parse_timeframe(label)
            tick = time.monotonic()
            try:
                raw = bridge.fetch_bars(ticker, resolution_for(label), 8)
            except TradingViewError as error:
                report.check(False, f"{label}: bars can be read", f"{error} | {error.technical}")
                continue
            took = time.monotonic() - tick
            stamps = stamps_to_new_york([row[0] for row in raw.rows])
            times = ", ".join(f"{s.tz_convert('UTC').strftime('%a %Y-%m-%d %H:%M')}Z = {s.strftime('%a %H:%M')} NY" for s in stamps[-3:])
            report.line("INFO", f"{label}: read took {took:.2f} s; raw bar times: {times}")
            try:
                mapped = rows_to_frame(raw.rows, label, settings.daily_stamp_shift_days)
            except TradingViewError as error:
                report.check(False, f"{label}: bar times can be placed on the companion's grid", f"{error}" + (" (the source builds 4h from 1h bars instead)" if label == "4h" else ""))
                continue
            if not tf.is_intraday:
                dates = trading_dates(stamps, settings.daily_stamp_shift_days)
                report.check(bool((stamps.hour == 18).all()), f"{label}: stamped at the session open, 18:00 New York the evening before")
                days = ", ".join(d.strftime("%a %Y-%m-%d") for d in dates[-3:])
                opens = ", ".join(m.strftime("%a %Y-%m-%d %H:%M") for m in mapped.index[-3:])
                report.line("INFO", f"{label}: stamps fall in trading date(s) {days} -> companion opens {opens}")
            else:
                report.check(not off_grid(stamps, label).any(), f"{label}: bar times sit on the companion's grid (18:00 New York anchored)")
        source.get_bars(symbol, stack.entry, now, 10)
        for higher, lower in dict.fromkeys(((stack.setup, stack.entry), (stack.bias, stack.setup), ("1D", "1h"), ("4h", "1h"), ("1W", "1D"), ("1M", "1D"))):
            try:
                _compare(report, source, symbol, higher, lower, source.now())
            except TradingViewError as error:
                report.check(False, f"{higher} against {lower}", f"{error} | {error.technical}")

        # 8. deeper history
        tick = time.monotonic()
        try:
            deep_bars = source.get_bars(symbol, stack.entry, source.now(), deep)
            how = (bridge.report.get("series") or {}).get("deepen")
            report.check(len(deep_bars) >= deep, f"{stack.entry}: {deep} bars of history load ({len(deep_bars)} returned in {time.monotonic() - tick:.2f} s)", f"how: {how}")
        except TradingViewError as error:
            report.check(False, f"{stack.entry}: deeper history loads", f"{error} | {error.technical}")
        try:
            years = source.get_bars(symbol, "1W", source.now(), 600)
            report.check(len(years) >= 600, f"1W: 600 weeks load and every one can be placed, holiday weeks included (from {years.index[0].strftime('%Y-%m-%d')})")
        except TradingViewError as error:
            report.check(False, "1W: deep history can be placed", f"{error} | {error.technical}")

        # 9. the full default read, timed
        fresh = TradingViewBarSource(bridge)
        tick = time.monotonic()
        try:
            from companion.engine import analyze

            update = fresh.refresh(symbol, stack.entry)
            verdict = analyze(symbol, update.last_close.tz_localize(None), stack, "ttrades", fresh)
            report.line("PASS", f"full first check of {stack.name} took {time.monotonic() - tick:.2f} s: {verdict.decision} ({verdict.bias})", fresh.description)
        except Exception as error:  # the diagnostic reports, it does not crash
            report.check(False, "a full check runs on live bars", f"{type(error).__name__}: {error}")

        # 10. nothing moved
        after = bridge.peek_tabs()
        key = lambda entries: sorted((str(e.get("id")), e.get("symbol"), e.get("resolution")) for e in entries)  # noqa: E731
        report.check(key(before) == key(after), "every tab shows the same symbol and timeframe as before", f"before: {key(before)}\n         after:  {key(after)}")
        seen_before = [e.get("id") for e in before if e.get("visible")]
        seen_after = [e.get("id") for e in after if e.get("visible")]
        report.check(seen_before == seen_after, "the tab you were looking at is still the one on screen", f"before: {seen_before} after: {seen_after}")
        report.check(len(before) == len(after), f"no tab was opened or closed ({len(after)} chart tabs)")
    finally:
        if was_there or keep:
            bridge._drop()  # noqa: SLF001 - leave the feed for the companion that is using it
            report.line("INFO", "the feed was left in the page" + (" (a companion window is using it)" if was_there else " (--keep)"))
        else:
            bridge.close()
            report.line("INFO", "the feed was taken out of the page again: nothing of the companion is left in TradingView")

    print(f"\n{'ALL CHECKS PASSED' if not report.failed else str(report.failed) + ' CHECK(S) FAILED'}")
    return 1 if report.failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the live TradingView link (read-only; no chart or tab is changed).")
    parser.add_argument("--symbol", default="NQ")
    parser.add_argument("--stack", default=_timeframes.default_stack().name)
    parser.add_argument("--keep", action="store_true", help="leave the feed's data series in the page for a companion window to reuse")
    parser.add_argument("--deep", type=int, default=1200, help="how many entry bars the history test asks for")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass
    try:
        return run(args.symbol, args.stack, args.keep, args.deep)
    except TradingViewError as error:
        print(f"[FAIL] {error}\n         technical: {error.technical}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
