from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, time
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    session: str | None = None


@dataclass(frozen=True)
class TradeSignal:
    timestamp: datetime
    side: Side
    stop_price: float
    target_price: float
    quantity: float = 1.0
    thesis: str = ""
    session: str | None = None


@dataclass(frozen=True)
class CostModel:
    tick_size: float = 0.25
    spread_ticks: float = 1.0
    slippage_ticks: float = 0.5
    commission_per_contract: float = 0.0
    contract_multiplier: float = 1.0

    @property
    def execution_adjustment(self) -> float:
        return self.tick_size * ((self.spread_ticks / 2.0) + self.slippage_ticks)


@dataclass(frozen=True)
class ExecutedTrade:
    side: str
    signal_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    entry_reason: str
    exit_reason: str
    quantity: float
    raw_entry_price: float
    raw_exit_price: float
    entry_price: float
    exit_price: float
    gross_pnl: float
    net_pnl: float
    spread_cost: float
    slippage_cost: float
    commission_cost: float
    holding_bars: int
    session_bucket: str


@dataclass(frozen=True)
class BacktestSummary:
    trade_count: int
    win_rate: float
    gross_pnl: float
    net_pnl: float
    average_net_pnl: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    average_holding_bars: float
    skipped_signal_count: int
    exit_reason_counts: dict[str, int]
    cost_model: dict[str, float]
    session_mode: str


DEFAULT_TIMEZONE = "America/New_York"
SESSION_BUCKETS: dict[str, tuple[time, time]] = {
    "london": (time(2, 0), time(6, 59)),
    "new_york": (time(8, 30), time(11, 59)),
}


def parse_timestamp(value: str, *, timezone_name: str = DEFAULT_TIMEZONE) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise ValueError("timestamp is required")
    normalized = raw.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed


def infer_session_bucket(timestamp: datetime, *, timezone_name: str = DEFAULT_TIMEZONE) -> str:
    local_timestamp = timestamp.astimezone(ZoneInfo(timezone_name))
    local_time = local_timestamp.timetz().replace(tzinfo=None)
    for bucket, (start, end) in SESSION_BUCKETS.items():
        if start <= local_time <= end:
            return bucket
    return "other"


def normalize_session_mode(session_mode: str) -> set[str]:
    normalized = str(session_mode or "all").strip().lower()
    if normalized in {"all", ""}:
        return {"london", "new_york", "other"}
    if normalized == "both":
        return {"london", "new_york"}
    if normalized not in {"london", "new_york", "other"}:
        raise ValueError(f"Unsupported session mode: {session_mode}")
    return {normalized}


def bar_session_bucket(bar: Bar, *, timezone_name: str = DEFAULT_TIMEZONE) -> str:
    return str(bar.session).strip().lower() if bar.session else infer_session_bucket(
        bar.timestamp,
        timezone_name=timezone_name,
    )


def matches_session(
    bar: Bar,
    *,
    allowed_sessions: set[str],
    desired_session: str | None,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> bool:
    bucket = bar_session_bucket(bar, timezone_name=timezone_name)
    if bucket not in allowed_sessions:
        return False
    if desired_session:
        return bucket == desired_session.strip().lower()
    return True


def load_bars_csv(path: Path | str, *, timezone_name: str = DEFAULT_TIMEZONE) -> list[Bar]:
    bars: list[Bar] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            bars.append(
                Bar(
                    timestamp=parse_timestamp(row["timestamp"], timezone_name=timezone_name),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]) if row.get("volume") else None,
                    session=str(row.get("session", "")).strip() or None,
                )
            )
    return sorted(bars, key=lambda item: item.timestamp)


def load_signals(path: Path | str, *, timezone_name: str = DEFAULT_TIMEZONE) -> list[TradeSignal]:
    signal_path = Path(path)
    if signal_path.suffix.lower() == ".csv":
        with signal_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            payload = list(reader)
    else:
        loaded = json.loads(signal_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = list(loaded.get("signals", []))
        elif isinstance(loaded, list):
            payload = loaded
        else:
            raise ValueError("Signal file must contain a list or a {'signals': [...]} object")

    signals: list[TradeSignal] = []
    for row in payload:
        signals.append(
            TradeSignal(
                timestamp=parse_timestamp(row["timestamp"], timezone_name=timezone_name),
                side=Side(str(row["side"]).strip().lower()),
                stop_price=float(row["stop_price"]),
                target_price=float(row["target_price"]),
                quantity=float(row.get("quantity", 1.0) or 1.0),
                thesis=str(row.get("thesis", "")).strip(),
                session=str(row.get("session", "")).strip() or None,
            )
        )
    return sorted(signals, key=lambda item: item.timestamp)


def apply_execution_adjustment(
    price: float,
    *,
    side: Side,
    cost_model: CostModel,
    is_entry: bool,
) -> float:
    adjustment = cost_model.execution_adjustment
    if side is Side.LONG:
        return price + adjustment if is_entry else price - adjustment
    return price - adjustment if is_entry else price + adjustment


def build_trade(
    *,
    signal: TradeSignal,
    entry_bar: Bar,
    exit_bar: Bar,
    raw_exit_price: float,
    exit_reason: str,
    holding_bars: int,
    cost_model: CostModel,
    timezone_name: str,
) -> ExecutedTrade:
    raw_entry_price = entry_bar.open
    entry_price = apply_execution_adjustment(
        raw_entry_price,
        side=signal.side,
        cost_model=cost_model,
        is_entry=True,
    )
    exit_price = apply_execution_adjustment(
        raw_exit_price,
        side=signal.side,
        cost_model=cost_model,
        is_entry=False,
    )
    signed_direction = 1.0 if signal.side is Side.LONG else -1.0
    gross_pnl = signed_direction * (raw_exit_price - raw_entry_price) * signal.quantity * cost_model.contract_multiplier
    spread_cost = cost_model.tick_size * cost_model.spread_ticks * signal.quantity * cost_model.contract_multiplier
    slippage_cost = (
        2.0
        * cost_model.tick_size
        * cost_model.slippage_ticks
        * signal.quantity
        * cost_model.contract_multiplier
    )
    commission_cost = 2.0 * cost_model.commission_per_contract * signal.quantity
    net_pnl = gross_pnl - spread_cost - slippage_cost - commission_cost
    return ExecutedTrade(
        side=signal.side.value,
        signal_timestamp=signal.timestamp.isoformat(),
        entry_timestamp=entry_bar.timestamp.isoformat(),
        exit_timestamp=exit_bar.timestamp.isoformat(),
        entry_reason=signal.thesis or "signal",
        exit_reason=exit_reason,
        quantity=signal.quantity,
        raw_entry_price=round(raw_entry_price, 6),
        raw_exit_price=round(raw_exit_price, 6),
        entry_price=round(entry_price, 6),
        exit_price=round(exit_price, 6),
        gross_pnl=round(gross_pnl, 6),
        net_pnl=round(net_pnl, 6),
        spread_cost=round(spread_cost, 6),
        slippage_cost=round(slippage_cost, 6),
        commission_cost=round(commission_cost, 6),
        holding_bars=holding_bars,
        session_bucket=bar_session_bucket(entry_bar, timezone_name=timezone_name),
    )


def resolve_exit(
    signal: TradeSignal,
    bar: Bar,
    *,
    intrabar_conflict_policy: str,
) -> tuple[float, str] | None:
    if signal.side is Side.LONG:
        stop_hit = bar.low <= signal.stop_price
        target_hit = bar.high >= signal.target_price
        if stop_hit and target_hit:
            if intrabar_conflict_policy != "worst_case_stop":
                raise ValueError(f"Unsupported intrabar conflict policy: {intrabar_conflict_policy}")
            return signal.stop_price, "stop"
        if stop_hit:
            return signal.stop_price, "stop"
        if target_hit:
            return signal.target_price, "target"
        return None

    stop_hit = bar.high >= signal.stop_price
    target_hit = bar.low <= signal.target_price
    if stop_hit and target_hit:
        if intrabar_conflict_policy != "worst_case_stop":
            raise ValueError(f"Unsupported intrabar conflict policy: {intrabar_conflict_policy}")
        return signal.stop_price, "stop"
    if stop_hit:
        return signal.stop_price, "stop"
    if target_hit:
        return signal.target_price, "target"
    return None


def build_backtest_summary(
    trades: Sequence[ExecutedTrade],
    *,
    skipped_signal_count: int,
    cost_model: CostModel,
    session_mode: str,
) -> BacktestSummary:
    trade_count = len(trades)
    wins = [trade for trade in trades if trade.net_pnl > 0.0]
    losses = [trade for trade in trades if trade.net_pnl < 0.0]
    gross_profit = sum(trade.net_pnl for trade in wins)
    gross_loss = abs(sum(trade.net_pnl for trade in losses))
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    exit_reason_counts: dict[str, int] = {}

    for trade in trades:
        cumulative += trade.net_pnl
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)
        exit_reason_counts[trade.exit_reason] = exit_reason_counts.get(trade.exit_reason, 0) + 1

    profit_factor = gross_profit / gross_loss if gross_loss else (gross_profit if gross_profit else 0.0)
    average_net_pnl = sum(trade.net_pnl for trade in trades) / trade_count if trade_count else 0.0
    expectancy = average_net_pnl
    average_holding_bars = (
        sum(trade.holding_bars for trade in trades) / trade_count if trade_count else 0.0
    )

    return BacktestSummary(
        trade_count=trade_count,
        win_rate=round(len(wins) / trade_count, 4) if trade_count else 0.0,
        gross_pnl=round(sum(trade.gross_pnl for trade in trades), 6),
        net_pnl=round(sum(trade.net_pnl for trade in trades), 6),
        average_net_pnl=round(average_net_pnl, 6),
        profit_factor=round(profit_factor, 6),
        expectancy=round(expectancy, 6),
        max_drawdown=round(max_drawdown, 6),
        average_holding_bars=round(average_holding_bars, 4),
        skipped_signal_count=skipped_signal_count,
        exit_reason_counts=dict(sorted(exit_reason_counts.items())),
        cost_model={
            "tick_size": cost_model.tick_size,
            "spread_ticks": cost_model.spread_ticks,
            "slippage_ticks": cost_model.slippage_ticks,
            "commission_per_contract": cost_model.commission_per_contract,
            "contract_multiplier": cost_model.contract_multiplier,
        },
        session_mode=session_mode,
    )


def run_backtest(
    bars: Sequence[Bar],
    signals: Sequence[TradeSignal],
    *,
    cost_model: CostModel | None = None,
    session_mode: str = "all",
    intrabar_conflict_policy: str = "worst_case_stop",
    close_open_positions: bool = True,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> dict:
    if not bars:
        raise ValueError("At least one bar is required")

    cost_model = cost_model or CostModel()
    allowed_sessions = normalize_session_mode(session_mode)
    ordered_bars = sorted(bars, key=lambda item: item.timestamp)
    ordered_signals = sorted(signals, key=lambda item: item.timestamp)
    trades: list[ExecutedTrade] = []
    skipped_signal_count = 0
    last_exit_index = -1

    for signal in ordered_signals:
        entry_index: int | None = None
        for index, bar in enumerate(ordered_bars):
            if index <= last_exit_index:
                continue
            if bar.timestamp <= signal.timestamp:
                continue
            if not matches_session(
                bar,
                allowed_sessions=allowed_sessions,
                desired_session=signal.session,
                timezone_name=timezone_name,
            ):
                continue
            entry_index = index
            break

        if entry_index is None:
            skipped_signal_count += 1
            continue

        entry_bar = ordered_bars[entry_index]
        exit_index: int | None = None
        raw_exit_price: float | None = None
        exit_reason: str | None = None

        for index in range(entry_index + 1, len(ordered_bars)):
            resolved = resolve_exit(
                signal,
                ordered_bars[index],
                intrabar_conflict_policy=intrabar_conflict_policy,
            )
            if not resolved:
                continue
            raw_exit_price, exit_reason = resolved
            exit_index = index
            break

        if exit_index is None:
            if not close_open_positions:
                skipped_signal_count += 1
                continue
            exit_index = len(ordered_bars) - 1
            raw_exit_price = ordered_bars[exit_index].close
            exit_reason = "close"

        trade = build_trade(
            signal=signal,
            entry_bar=entry_bar,
            exit_bar=ordered_bars[exit_index],
            raw_exit_price=float(raw_exit_price),
            exit_reason=str(exit_reason),
            holding_bars=(exit_index - entry_index) + 1,
            cost_model=cost_model,
            timezone_name=timezone_name,
        )
        trades.append(trade)
        last_exit_index = exit_index

    summary = build_backtest_summary(
        trades,
        skipped_signal_count=skipped_signal_count,
        cost_model=cost_model,
        session_mode=session_mode,
    )
    return {
        "summary": asdict(summary),
        "trades": [asdict(trade) for trade in trades],
    }

