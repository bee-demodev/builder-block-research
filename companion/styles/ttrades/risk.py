"""Entry trigger, stop, targets and the session filter (rules.md sections 6 c4, 8, 9.1).

All prices here are in the side's mirrored space (the trade is always a long); callers
turn them back into real prices with ``Side.px``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from companion.styles.ttrades.config import TTradesConfig, clock_minutes
from companion.styles.ttrades.primitives import Bars, CisdRead, PoiHit, Side, Zone, anchored_cisd, fmt, poi_reached, when
from companion.timeframes import parse_timeframe


@dataclass(frozen=True)
class Trigger:
    pos: int  # entry-frame position of the trigger bar
    mode: str  # "conservative" | "aggressive"
    entry: float  # close of the trigger bar
    wick_stop: float  # the protected low the stop rests on
    stop_label: str  # what that low is
    body_stop: float | None  # lowest body edge of the trigger series, when it is full-bodied
    read: CisdRead | None  # the close-through that made the trigger
    poi: PoiHit | None  # what the pullback reached (conservative)
    stopped_at: int | None = None  # entry-frame position where the stop was later taken


def body_stop_of(x: Bars, read: CisdRead, cfg: TTradesConfig) -> float | None:
    """Body stop of a trigger series, or ``None`` when it is not allowed (rules.md 8.2)."""
    if not cfg.body_stop_allowed or read.series is None:
        return None
    start, end = read.series
    for i in range(start, end + 1):
        span = x.high[i] - x.low[i]
        if span <= 0 or abs(x.close[i] - x.open[i]) < cfg.body_stop_min_body_frac * span:
            return None
    edge = float(min(x.open[start : end + 1].min(), x.close[start : end + 1].min()))
    return edge if edge > read.anchor_low else None


def find_continuation_triggers(
    e: Bars,
    *,
    start: int,
    protected_low: float,
    protected_pos: int,
    order_block: Zone | None,
    cfg: TTradesConfig,
) -> list[Trigger]:
    """Continuation order blocks on the entry frame after a confirmed CISD (rules.md 6, c4).

    From ``start`` on: price pulls back without breaking ``protected_low``, a bar reaches
    an entry-timeframe point of interest (a swing low formed after the protected low, an
    unfilled bullish fair value gap, or a retest of ``order_block``), and a later bar
    closes above the series of down-close candles of that pullback. That bar is a
    trigger; the pullback's low is its new protected low. The search then continues, so
    the list holds every continuation that formed, oldest first.
    """
    triggers: list[Trigger] = []

    def reach(at: int) -> PoiHit | None:
        return poi_reached(
            e,
            float(e.low[at]),
            at,
            min_swing_pos=protected_pos + 1,
            fvg_min_size=cfg.fvg_min_size,
            close=float(e.close[at]),
            order_block=order_block,
            order_block_name="entry order block",
        )

    def stands(hit: PoiHit, at: int, upto: int) -> bool:
        """rules.md 9.3: a gap closed through, or an order block whose mean threshold is
        lost, before the trigger bar has closed is no longer a point of interest."""
        if hit.gap is not None:
            return hit.gap.fill_pos is None or hit.gap.fill_pos > upto
        if hit.kind == "order_block":
            return not bool((e.close[at : upto + 1] < (hit.top + hit.bottom) / 2.0).any())
        return True

    pos = start
    while pos < e.n:
        if (cfg.protected_swing_break_on == "wick" and e.low[pos] < protected_low) or e.close[pos] < protected_low:
            break
        hit = reach(pos)
        if hit is None:
            pos += 1
            continue
        read = anchored_cisd(e, pos, cfg.doji_in_series)
        while read.lower_low is not None and e.low[read.lower_low] >= protected_low:
            read = anchored_cisd(e, read.lower_low, cfg.doji_in_series)  # the pullback made a new low
        if read.confirm is None:
            pos += 1
            continue
        if not stands(hit, pos, read.confirm):
            # the first reach did not hold; the pullback's low itself must be at one that did
            deeper = reach(read.anchor)
            hit = deeper if deeper is not None and stands(deeper, read.anchor, read.confirm) else None
        if hit is None:
            pos += 1
            continue
        stopped = e.first_break(read.confirm + 1, read.anchor_low, cfg.protected_swing_break_on)
        triggers.append(
            Trigger(
                pos=read.confirm,
                mode="conservative",
                entry=float(e.close[read.confirm]),
                wick_stop=read.anchor_low,
                stop_label=f"{e.side.lo} of the pullback at {e.at(read.anchor)} (the new protected {e.side.lo})",
                body_stop=body_stop_of(e, read, cfg),
                read=read,
                poi=hit,
                stopped_at=stopped,
            )
        )
        pos = read.confirm + 1
    return triggers


@dataclass(frozen=True)
class TradePlan:
    entry: float
    stop: float
    stop_is_body: bool
    stop_label: str
    targets: tuple[float, ...]  # what the verdict reports: the R-multiple exit, or the structural levels
    structural: tuple[float, ...]  # T1 (and T2): the structural levels, whatever the target mode
    risk: float
    reward: float  # entry to targets[0]
    passed: bool  # the structural first level is at least min_rr away
    text: str  # the *_reward_at_least_2r detail, in real prices


def plan_trade(
    side: Side, trigger: Trigger, t1: float, t2: float | None, t1_label: str, cfg: TTradesConfig
) -> TradePlan:
    """Entry, stop and targets for a trigger (rules.md 8).

    The exit is ``target_rr`` times the risk (``target_mode`` "r_multiple"); the structural
    levels ``t1`` / ``t2`` are measured in R and reported. With ``target_mode``
    "structural" they are the targets, as before the trader's answer. The body stop is
    only considered when the structural reward check blocks (``reward_check_role``
    "quality"), because its one job is to reach that minimum.
    """
    entry = trigger.entry

    def measure(stop: float) -> tuple[float, float, bool]:
        risk, reward = entry - stop, t1 - entry
        return risk, reward, bool(risk > 0 and reward >= cfg.min_rr * risk)

    blocking = cfg.reward_check_role == "quality"
    stop = trigger.wick_stop - cfg.stop_buffer
    risk, distance, passed = measure(stop)
    is_body = False
    note = ""
    if blocking and not passed and trigger.body_stop is not None:
        body = trigger.body_stop - cfg.stop_buffer
        body_risk, body_distance, body_passed = measure(body)
        if body_passed:
            note = (
                f" Fails on the wick stop {side.p(stop)} ({fmt(distance / risk) if risk > 0 else 'n/a'}R); the trigger "
                f"series is full-bodied, so the BODY STOP {side.p(body)} is in use."
            )
            stop, risk, distance, passed, is_body = body, body_risk, body_distance, True, True
        else:
            note = f" The body stop {side.p(body)} does not reach {cfg.min_rr:g}R either."
    multiple = distance / risk if risk > 0 else float("nan")
    exit_price = entry + cfg.target_rr * risk
    structural = (t1,) if t2 is None else (t1, t2)
    r_mode = cfg.target_mode == "r_multiple"
    text = f"entry {side.p(entry)}, stop {side.p(stop)}, risk {fmt(risk)}; "
    if r_mode:
        text += (
            f"the exit is {cfg.target_rr:g}R = {side.p(exit_price)} (fixed reward-to-risk multiple). For information: "
            f"the structural level {side.p(t1)} ({t1_label}) is {fmt(distance)} away = {multiple:.2f}R "
            f"({'at least' if passed else 'less than'} {cfg.min_rr:g}R).{note}"
        )
    else:
        text += (
            f"T1 {side.p(t1)} ({t1_label}) is {fmt(distance)} away = {multiple:.2f}R (need {cfg.min_rr:g}R); "
            f"{cfg.target_rr:g}R price {side.p(exit_price)}.{note}"
        )
    if distance <= 0:
        text += f" That level is not beyond the entry{'' if r_mode else ' any more'}."
    elif not passed and (blocking or not r_mode):
        limit = (t1 + cfg.min_rr * stop) / (1.0 + cfg.min_rr)
        text += f" A limit entry at {side.p(limit)} would give exactly {cfg.min_rr:g}R to it."
    label = "bodies of the trigger series (body stop)" if is_body else trigger.stop_label
    targets = (exit_price,) if r_mode else structural
    reward = targets[0] - entry
    return TradePlan(entry, stop, is_body, label, targets, structural, risk, reward, passed, text)


def pick_trigger(
    mode: str, cisd_trigger: Trigger | None, order_blocks: list[Trigger], cfg: TTradesConfig
) -> tuple[Trigger | None, str]:
    """Choose the entry trigger for ``mode`` (rules.md 6 / 7, stage c4) and say which kind fired.

    ``cisd_trigger`` is the CISD entry (``None`` when it has not formed or is not allowed),
    ``order_blocks`` the continuation order blocks, oldest first. A trigger whose stop
    swing has been taken is only reported when nothing else is left.
    """
    if mode == "aggressive":
        candidates = [cisd_trigger] if cisd_trigger is not None else []
    elif mode == "conservative":
        candidates = list(order_blocks)
    else:
        candidates = sorted(
            ([cisd_trigger] if cisd_trigger is not None else []) + list(order_blocks), key=lambda item: item.pos
        )
    if not candidates:
        return None, ""
    alive = [item for item in candidates if item.stopped_at is None]
    pool = alive or candidates
    if mode == "either" and cfg.entry_either_pick == "first" and alive:
        chosen = pool[0]
    else:
        chosen = pool[-1]  # conservative has always reported the latest continuation
    if mode != "either":
        return chosen, f"mode {mode}"
    kind = "the entry-timeframe CISD" if chosen.mode == "aggressive" else "a continuation order block"
    others = [item for item in alive if item is not chosen]
    extra = ""
    if others:
        kinds = ", ".join("CISD" if item.mode == "aggressive" else "order block" for item in others)
        extra = f"; {len(others)} other live trigger(s) not chosen: {kinds}"
    return chosen, f"mode either ({kind} is the {cfg.entry_either_pick} to confirm{extra})"


def session_filter(entry_timeframe: str, moment: pd.Timestamp, what: str, cfg: TTradesConfig) -> tuple[bool, str]:
    """rules.md 9.1: is ``moment`` (a trigger bar's close, or ``as_of``) inside a kill zone?"""
    minutes = parse_timeframe(entry_timeframe).nominal_minutes
    if minutes >= cfg.kill_zone_applies_below_minutes:
        return True, (
            f"entry timeframe {entry_timeframe} is not below {cfg.kill_zone_applies_below_minutes} minutes, "
            f"so kill zones do not apply"
        )
    clock = moment.hour * 60 + moment.minute
    zones = ", ".join(f"{start}-{end}" for start, end in cfg.kill_zones)
    inside = any(clock_minutes(start) <= clock <= clock_minutes(end) for start, end in cfg.kill_zones)
    return inside, f"{what} {when(moment)} New York is {'inside' if inside else 'outside'} the kill zones ({zones})"
