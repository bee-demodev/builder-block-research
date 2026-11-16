"""Continuation path (rules.md section 6): trade Candle 3 / Candle 4 of the bias swing.

Written for the bullish case on the side's mirrored frames; see ``primitives.Side``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import numpy as np
import pandas as pd

from companion.styles.ttrades.bias import BiasRead
from companion.styles.ttrades.checklist import ADVISORY, CONTINUATION, GATE, Checklist
from companion.styles.ttrades.context import Context, View
from companion.styles.ttrades.primitives import (
    Bars,
    CisdRead,
    PoiHit,
    Side,
    Zone,
    anchored_cisd,
    candle3_edge,
    cisd_text,
    closed_wick_is_large,
    completes_candle3_closure,
    fmt,
    is_reversal_closure,
    poi_reached,
    when,
)
from companion.styles.ttrades.risk import (
    TradePlan,
    Trigger,
    body_stop_of,
    find_continuation_triggers,
    pick_trigger,
    plan_trade,
)
from companion.timeframes import bar_close_time
from companion.types import MarkupItem


@dataclass
class PathOutcome:
    """What one path's checklist produced."""

    family: str  # "continuation" | "reversal"
    side: Side | None
    checklist: Checklist
    trigger: Trigger | None = None
    trigger_close: pd.Timestamp | None = None
    plan: TradePlan | None = None
    markup: list[MarkupItem] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)
    conservative_forced: bool = False
    # What the path found, kept for the top-down read (``read.py``). Descriptive only:
    # nothing here feeds the decision. Prices are in the side's mirrored space.
    seen: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Setup:
    """A setup-timeframe Candle 2 or Candle 3 closure at a tagged point of interest."""

    kind: str  # "c2" | "c3"
    swing: int  # setup-frame position of the swing candle (the bar that tagged the POI)
    closing: int  # position of the candle that completed the closure
    low: float
    hit: PoiHit
    broken_at: int | None  # entry-frame position where the swing low was later taken


def respect_level(view: View, bias: BiasRead) -> tuple[float, float, float, bool, str]:
    """(respect level, EQ, wick midpoint, closed wick large?, description) of ``B[-1]`` (rules.md 3.9)."""
    b, side, cfg = view.B, view.side, view.ctx.cfg
    k = b.n - 1
    eq = float((b.high[k] + b.low[k]) / 2.0)
    wick_mid = float((min(b.open[k], b.close[k]) + b.low[k]) / 2.0)
    large, wick, span = closed_wick_is_large(b, k, cfg.closed_wick_large_frac)
    use_wick = cfg.respect_level_mode == "wick_mid" or (
        cfg.respect_level_mode == "auto" and bias.closure == "A" and large
    )
    level = wick_mid if use_wick else eq
    share = wick / span if span > 0 else 0.0
    text = (
        f"respect level {side.p(level)} = {'wick midpoint' if use_wick else 'equilibrium'} of the previous "
        f"{b.tf} candle (EQ {side.p(eq)}, wick midpoint {side.p(wick_mid)}; its {side.lo}-side wick is "
        f"{share:.0%} of its range, mode {cfg.respect_level_mode})"
    )
    return level, eq, wick_mid, large, text


def _tags(view: View, bias: BiasRead, s0: int, level: float) -> dict[int, PoiHit]:
    """Setup bars inside ``B[0]`` that reached a point of interest (rules.md 6, c2)."""
    b, s, cfg = view.B, view.S, view.ctx.cfg
    min_swing = s.first_at_or_after(b.times[b.n - 2])
    tags: dict[int, PoiHit] = {}
    for pos in range(s0, s.n):
        hit = poi_reached(
            s,
            float(s.low[pos]),
            pos,
            min_swing_pos=min_swing,
            fvg_min_size=cfg.fvg_min_size,
            min_fvg_top=level,
            close=float(s.close[pos]),
            order_block=bias.order_block,
            order_block_name="bias order block",
        )
        if hit is None and pos - 1 in tags and s.low[pos] < s.low[pos - 1]:
            # rules.md 3.6: a bar that takes the tagged bar's low is the new swing candle
            previous = tags[pos - 1]
            hit = replace(previous, text=f"traded {view.side.below} the tagged bar before it, which {previous.text}")
        if hit is not None:
            tags[pos] = hit
    return tags


def _dropped(s_view: View, pos: int, hit: PoiHit) -> str | None:
    """Why a tagged POI no longer counts (rules.md 9.3), or ``None`` while it stands."""
    s, side = s_view.S, s_view.side
    if hit.gap is not None and hit.gap.fill_pos is not None:
        return f"the gap was closed through at {s.at(hit.gap.fill_pos)}"
    if hit.kind == "order_block":
        mid = (hit.top + hit.bottom) / 2.0
        lost = np.flatnonzero(s.close[pos + 1 :] < mid)
        if len(lost):
            return f"a {s.tf} close {side.below} its mean threshold {s.p(mid)} at {s.at(pos + 1 + int(lost[0]))}"
    return None


@dataclass(frozen=True)
class EntryRange:
    """A consolidation on the entry timeframe (rules.md 6, stage c4; "Why Your Continuations
    Fail"): the entry CISD closed through, but slowly, so price was ranging, not continuing.
    ``low`` is the swing it was meant to protect, ``high`` the top of the leg it fell from."""

    low: float
    high: float
    first: int  # first bar of the range (the leg's top)
    confirm: int  # the slow close-through: a sweep of the range high, not a continuation
    bars: int  # bars it took


def entry_range(e: Bars, read: CisdRead | None, max_bars: int) -> EntryRange | None:
    """The range a slow entry CISD leaves behind, or ``None`` when the turn was a quick V."""
    if read is None or read.confirm is None or (read.bars_to_confirm or 0) <= max_bars:
        return None
    # the leg's top: the bar before the down-close series (it may sit before the swing candle)
    first = max(0, (read.series[0] if read.series is not None else read.anchor) - 1)
    high = float(e.high[first : read.confirm].max())
    return EntryRange(read.anchor_low, high, first, read.confirm, read.bars_to_confirm or 0)


def breakout_before(e: Bars, rng: EntryRange, before: int) -> int | None:
    """First bar from the slow close-through up to ``before`` that closed above the range high."""
    for pos in range(rng.confirm, before):
        if float(e.close[pos]) > rng.high:
            return pos
    return None


TRAIL_LEVELS_SHOWN = 3  # newer protected swings drawn after the entry, newest kept


@dataclass(frozen=True)
class RangeOutcome:
    """Where a possible consolidation stands against the ways out of it that "Why Your
    Continuations Fail" gives (transcript @08:13-12:30; playbook
    ``ttfm-consolidations-why-continuations-fail``):

    - manipulation: the range low is swept, then a quick CISD (<= ``cisd_max_bars``)
      closes back through: "now we have a low we can trust";
    - breakout and a new continuation: a close above the range high, then a pullback into
      a point of interest and a quick CISD: "we're not going to trade the breakout unless
      we have a continuation";
    - failure: the close above the high was a sweep of it and price trades across the
      range, or the sweep of the low gets no quick turn.

    ``state``: "open" (still inside), "swept" (low taken, no clean CISD yet), "manipulated"
    (low taken, then a clean CISD), "broke_out" (no new continuation yet), "continued"
    (breakout, then a clean continuation), "failed" (no clean way out: the idea is off).
    """

    state: str
    exit_at: int | None  # bar that left the range (the sweep or the breakout)
    cisd: CisdRead | None  # the read that has to close through (swept) or did (manipulated / continued)
    trusted_low: float | None  # the low a clean way out leaves behind
    lines: tuple[str, ...]  # the tooltip, one outcome per line


CLEAN_WAYS = ("manipulated", "continued")


def range_outcome(e: Bars, side: Side, rng: EntryRange, cfg: Any, what: str) -> RangeOutcome:
    """How ``rng`` has resolved so far, and what still has to happen for a clean expansion."""
    lo, hi, quick = e.p(rng.low), e.p(rng.high), cfg.cisd_max_bars
    head = f"Possible consolidation: {what} took {rng.bars} {e.tf} bars to close through, not a quick V (<= {quick})"
    start = rng.confirm + 1  # the slow close itself flagged the range; it is not a way out of it
    swept = next((pos for pos in range(start, e.n) if e.low[pos] < rng.low), None)
    broke = next((pos for pos in range(start, e.n) if e.close[pos] > rng.high), None)

    if swept is None and broke is None:
        return RangeOutcome(
            "open", None, None, None,
            (
                head + ". Closes inside it are internal: ignore them. Ways out:",
                f"1. Sweep of {lo}, then a CISD back through in <= {quick} bars: a {side.lo} to trust (clean)",
                f"2. Close {side.above} {hi}, then a pullback to a POI and a quick CISD: a new continuation (clean)",
                f"3. A close {side.above} {hi} that falls back across to {lo} was a sweep of the {side.hi}: no trade",
            ),
        )

    if swept is not None and (broke is None or swept <= broke):
        low_pos = swept + int(np.argmin(e.low[swept:]))
        read = anchored_cisd(e, low_pos, cfg.doji_in_series)
        took = f"Swept the range {side.lo} {lo} at {e.at(swept)}"
        if read.confirm is not None and (read.bars_to_confirm or 0) <= quick:
            return RangeOutcome(
                "manipulated", swept, read, read.anchor_low,
                (
                    f"{took}, then a CISD in {read.bars_to_confirm} bar(s) at {e.at(read.confirm)}: manipulation",
                    f"A {side.lo} to trust at {e.p(read.anchor_low)}: clean expansion expected",
                ),
            )
        if read.confirm is not None:
            return RangeOutcome(
                "failed", swept, read, None,
                (f"{took}, but the turn took {read.bars_to_confirm} bars: no {side.lo} to trust, still ranging",),
            )
        waited = e.n - 1 - low_pos
        if waited > quick:
            return RangeOutcome(
                "failed", swept, read, None,
                (f"{took} with no CISD back {side.above} {e.p(read.level)} in {waited} bars: the range {side.lo} failed",),
            )
        return RangeOutcome(
            "swept", swept, read, None,
            (
                f"{took}: possible manipulation",
                f"Clean only with a close {side.above} {e.p(read.level)} within {quick} bars of the {side.lo} "
                f"{e.p(read.anchor_low)}",
            ),
        )

    assert broke is not None
    out = f"Broke out: closed {side.above} the range {side.hi} {hi} at {e.at(broke)}"
    across = next((pos for pos in range(broke + 1, e.n) if e.low[pos] < rng.low), None)
    later = find_continuation_triggers(
        e, start=broke + 1, protected_low=rng.low, protected_pos=rng.first, order_block=None, cfg=cfg
    )
    clean = next((t for t in later if _swift(t, cfg) and (across is None or t.pos < across)), None)
    if clean is not None:
        assert clean.read is not None
        return RangeOutcome(
            "continued", broke, clean.read, clean.wick_stop,
            (
                f"{out}, then a new continuation: a quick CISD at {e.at(clean.pos)}",
                f"Protected {side.lo} {e.p(clean.wick_stop)}: clean expansion expected",
            ),
        )
    if across is not None:
        return RangeOutcome(
            "failed", broke, None, None,
            (f"{out}, but price traded back across to {lo} at {e.at(across)}: it was a sweep of the {side.hi}",),
        )
    return RangeOutcome(
        "broke_out", broke, None, None,
        (
            f"{out}: don't trade the breakout itself",
            f"Clean only after a pullback to a POI and a CISD within {quick} bars (a new continuation)",
        ),
    )


def _is_range_hint(item: MarkupItem) -> bool:
    return item.kind == "level" and (
        item.short in ("Sweep + quick CISD", "Break + new continuation") or item.short.endswith(" to trust")
    )


def drop_repeated_hints(items: list[MarkupItem]) -> list[MarkupItem]:
    """Drop a range's edge or trusted-low line where another line of the same chart already
    sits at that price (the stop swing, a trail level): the range's note still says it."""

    def taken(at: int, hint: MarkupItem) -> bool:
        return any(
            j != at and other.kind == "level" and other.timeframe == hint.timeframe
            and other.price is not None and hint.price is not None and abs(other.price - hint.price) < 1e-9
            and not (_is_range_hint(other) and j > at)  # of two hints at one price, the first stays
            for j, other in enumerate(items)
        )  # fmt: skip

    return [item for at, item in enumerate(items) if not (_is_range_hint(item) and taken(at, item))]


def consolidation_marks(e: Bars, side: Side, rng: EntryRange, cfg: Any, what: str) -> list[MarkupItem]:
    """A possible consolidation on the entry chart, with its ways out in the hover note.

    The box runs until price leaves the range. While it is open, its two edges carry what
    each way out needs; once price has left, the CISD that makes the way out clean is drawn,
    or the level it still has to close through."""
    found = range_outcome(e, side, rng, cfg, what)
    top, bottom = side.zone(rng.high, rng.low)
    tip = "\n".join(found.lines)
    short = {"open": "Consolidation?", "manipulated": "Range: manipulated", "continued": "Range: broke out"}
    items = [
        MarkupItem(
            "zone", tip, e.tf, top=top, bottom=bottom, start=e.times[rng.first],
            end=e.times[found.exit_at] if found.exit_at is not None else None, role="waiting",
            short=short.get(found.state, "Consolidation"),
        )
    ]
    if found.state == "open":
        items.append(
            MarkupItem(
                "level", found.lines[1][3:], e.tf, price=side.px(rng.low), start=e.times[rng.first], role="waiting",
                short="Sweep + quick CISD",
            )
        )
        items.append(
            MarkupItem(
                "level", found.lines[2][3:], e.tf, price=side.px(rng.high), start=e.times[rng.first], role="waiting",
                short="Break + new continuation",
            )
        )
    elif found.state == "swept" and found.cisd is not None:
        read = found.cisd
        items.append(
            MarkupItem(
                "level", found.lines[1], e.tf, price=side.px(read.level),
                start=e.times[read.series[0] if read.series else read.anchor], role="waiting",
                short=f"Close {side.above} = clean CISD",
            )
        )
    elif found.state in CLEAN_WAYS and found.cisd is not None and found.cisd.confirm is not None:
        confirm = found.cisd.confirm
        items.append(
            MarkupItem(
                "marker", tip, e.tf, price=side.px(float(e.close[confirm])), start=e.times[confirm], role="confirm",
                short="Clean CISD",
            )
        )
        assert found.trusted_low is not None
        items.append(
            MarkupItem(
                "level", found.lines[-1], e.tf, price=side.px(found.trusted_low), start=e.times[found.cisd.anchor],
                role="protected", short=f"{side.lo.capitalize()} to trust",
            )
        )
    return items


@dataclass(frozen=True)
class AfterEntry:
    """Continuations on the entry timeframe since the trigger that still hold, each with
    a protected low above the stop. ``trail`` turned in a quick V: their lows are the
    stepping stones a stop can trail to. ``slow`` took longer than ``cisd_max_bars`` to
    close through: possible consolidations, so their lows are not treated as protected."""

    trail: tuple[Trigger, ...]  # oldest first
    slow: tuple[Trigger, ...]
    inside: tuple[Trigger, ...] = ()  # quick, but inside a slow one's range before it broke out: internal moves


def after_entry(e: Bars, trigger: Trigger, protected_pos: int, cfg: Any) -> AfterEntry:
    """What formed after ``trigger``. ``protected_pos`` is the entry-frame position of its stop swing."""
    later = find_continuation_triggers(
        e, start=trigger.pos + 1, protected_low=trigger.wick_stop, protected_pos=protected_pos, order_block=None, cfg=cfg
    )
    trail: list[Trigger] = []
    slow: list[Trigger] = []
    inside: list[Trigger] = []

    def internal(item: Trigger) -> bool:
        """Quick, but formed inside a slow one's range before it broke out. One whose low is
        below the range low swept it: that is the manipulation, a way out, not internal."""
        for s in slow:
            rng = entry_range(e, s.read, cfg.cisd_max_bars)
            if rng is not None and item.wick_stop >= rng.low and _internal(e, rng, item):
                return True
        return False

    for item in later:
        if item.wick_stop <= trigger.wick_stop:
            continue
        if not _swift(item, cfg):
            slow.append(item)  # kept once its low is swept too: the sweep is how its range resolves
        elif item.stopped_at is not None:
            continue
        elif internal(item):
            inside.append(item)
        else:
            trail.append(item)
    return AfterEntry(tuple(trail), tuple(slow), tuple(inside))


def after_entry_markup(e: Bars, side: Side, found: AfterEntry, cfg: Any) -> list[MarkupItem]:
    """The newer protected swings since the entry (the newest ``TRAIL_LEVELS_SHOWN``) and
    the slow continuations as possible consolidations."""
    items: list[MarkupItem] = []
    shown = found.trail[-TRAIL_LEVELS_SHOWN:]
    for number, item in enumerate(shown, start=1):
        newest = number == len(shown)
        made = when(e.closes_at[item.pos])
        assert item.read is not None
        items.append(
            MarkupItem(
                "level",
                f"Newer protected {side.lo} {e.p(item.wick_stop)}: a continuation closed through in a quick V at {made}"
                + ("; the stop can trail here" if newest else ""),
                e.tf,
                price=side.px(item.wick_stop),
                start=e.times[item.read.anchor],
                role="protected",
                short=f"Trail: protected {side.lo}" if newest else f"Protected {side.lo}",
            )
        )
    for item in found.slow:
        rng = entry_range(e, item.read, cfg.cisd_max_bars)
        if rng is not None:
            items.extend(consolidation_marks(e, side, rng, cfg, f"the continuation at {e.at(item.pos)}"))
    return items


def ran_liquidity(e: Bars, pos: int, e_lo: int) -> Any:
    """The first entry-timeframe swing high formed since ``e_lo`` that bar ``pos`` was the
    first to take, or ``None`` (rules.md 6, ``cont_trigger_clear_of_liquidity``)."""
    bar_high = float(e.high[pos])
    for swing_high in e.swing_highs:
        if (
            e_lo <= swing_high.pos
            and swing_high.pos + 1 < pos
            and bar_high > swing_high.price
            and float(e.high[swing_high.pos + 1 : pos].max()) <= swing_high.price
        ):
            return swing_high
    return None


def evaluate_continuation(ctx: Context, bias: BiasRead) -> PathOutcome:
    cfg, stack, side = ctx.cfg, ctx.stack, bias.side
    roles = {
        "cont_objective_open": cfg.objective_open_role,
        "cont_reward_at_least_2r": cfg.reward_check_role,
        "cont_objective_open_at_trigger": cfg.objective_at_trigger_role,
    }
    if not cfg.setup_body_alignment_required:
        roles["cont_setup_closure_body_aligned"] = ADVISORY
    cl = Checklist(CONTINUATION, stack, side, roles)
    out = PathOutcome("continuation", side, cl)
    if bias.case == "none":
        cl.set("bias_closure_directional", None, bias.text)
        cl.fill("fewer than 3 closed bias candles")
        return out
    if side is None or not bias.closure:
        cl.set("bias_closure_directional", False, f"case {bias.case}: {bias.text}")
        cl.set("bias_candle_index_ok", False, "no directional closure, so no Candle 3 or Candle 4 to trade")
        cl.fill("the bias candle closed without a direction")
        return out

    view = ctx.view(side)
    b, s, e = view.B, view.S, view.E
    k = b.n - 1
    swing = bias.swing_pos if bias.swing_pos is not None else k
    swing_low = float(b.low[swing])
    cl.set("bias_closure_directional", True, f"case {bias.case}: {bias.text}")

    # --- c1 --------------------------------------------------------------------
    where = f"swing candle {b.at(swing)} ({side.lo} {b.p(swing_low)})"
    if bias.case == "D":
        cl.set(
            "bias_poi_present",
            False,
            f"case D: a continuation closure whose {where} reached no point of interest; the move is late "
            f"(Candle 5 or later, or no identifiable swing)",
        )
    elif swing - ctx.lookback < 0:
        cl.set("bias_poi_present", None, f"only {swing} {b.tf} bars before the swing candle; need {ctx.lookback}")
    elif bias.poi is not None:
        cl.set("bias_poi_present", True, f"{where} {bias.poi.text}")
    else:
        cl.set(
            "bias_poi_present",
            False,
            f"{where} took no untaken {b.tf} swing {side.lo} and traded into no unfilled {side.direction} "
            f"{b.tf} fair value gap within {ctx.lookback} bars",
        )

    if bias.cisd is not None:
        cl.set("bias_cisd_confirmed", bias.cisd.confirmed, cisd_text(s, bias.cisd))
    elif bias.poi is None:
        cl.set("bias_cisd_confirmed", None, "Not evaluated: the bias swing has no point of interest to confirm")
    else:
        cl.set("bias_cisd_confirmed", None, f"no closed {s.tf} bar inside the swing candle {b.at(swing)}")

    if bias.candle_number is not None:
        cl.set("bias_candle_index_ok", True, f"case {bias.closure}: the forming {b.tf} candle is Candle {bias.candle_number}")
        since = e.first_at_or_after(b.closes_at[swing])
        broke = e.first_break(since, swing_low, cfg.protected_swing_break_on)
        if broke is None:
            cl.set("bias_swing_intact", True, f"nothing has traded {side.below} the bias swing {side.lo} {b.p(swing_low)} of {b.at(swing)}")
        else:
            cl.set(
                "bias_swing_intact",
                False,
                f"{e.tf} bar {e.at(broke)} traded to {e.p(e.low[broke])}, {side.below} the bias swing {side.lo} "
                f"{b.p(swing_low)} of {b.at(swing)}",
            )
    else:
        cl.set("bias_candle_index_ok", False, "case D: Candle 5 or later, or no identifiable swing")
        cl.set("bias_swing_intact", None, "Not evaluated: case D has no identifiable bias swing")

    t1 = float(b.high[k])
    if not view.has_forming:
        cl.set("cont_objective_open", None, f"no closed {e.tf} bar in the forming {b.tf} candle yet")
    else:
        open_ = view.f_high <= t1
        cl.set(
            "cont_objective_open",
            open_,
            f"forming {b.tf} candle {side.hi} so far {side.p(view.f_high)} at {when(view.f_high_time)}; the previous "
            f"candle's {side.hi} {side.p(t1)} (the structural level) is {'not taken' if open_ else 'already taken'}"
            + ("" if cfg.objective_open_role == GATE else "; information only: the exit is the R multiple"),
        )

    level, eq, wick_mid, large, level_text = respect_level(view, bias)
    out.seen.update(level=level, eq=eq)
    c2_not_expanded: bool | None
    if bias.closure == "A":
        c2_not_expanded = large
        _, wick, span = closed_wick_is_large(b, k, cfg.closed_wick_large_frac)
        cl.set(
            "bias_c2_not_expanded",
            large,
            f"bias Candle 2 {b.at(k)}: {side.lo}-side wick {fmt(wick)} of range {fmt(span)} "
            f"({wick / span if span > 0 else 0:.0%}; large >= {cfg.closed_wick_large_frac:.0%})"
            + ("" if large else "; it expanded, so only the conservative entry is allowed"),
        )
    elif bias.case == "D":
        c2_not_expanded = None
        cl.set("bias_c2_not_expanded", None, "Not evaluated: case D has no bias Candle 2")
    else:
        c2_not_expanded = True
        cl.set("bias_c2_not_expanded", True, f"case {bias.closure}: the forming candle is Candle 4, the check applies to Candle 3 trades only")

    # --- c2 --------------------------------------------------------------------
    span_b = float(b.high[k] - b.low[k])
    threshold = level - cfg.eq_tolerance_frac * span_b
    s0 = s.first_at_or_after(ctx.b_last_close) if ctx.b_last_close is not None else s.n
    if s0 >= s.n:
        cl.set("cont_eq_respected", None, f"no closed {s.tf} bar in the forming {b.tf} candle yet; {level_text}")
    else:
        wrong = np.flatnonzero(s.close[s0:] < threshold)
        if len(wrong):
            first = s0 + int(wrong[0])
            out.seen["eq_break"] = first
            cl.set(
                "cont_eq_respected",
                False,
                f"{s.tf} bar {s.at(first)} closed at {s.p(s.close[first])}, {side.below} the {level_text}",
            )
        else:
            worst = s0 + int(np.argmin(s.close[s0:]))
            cl.set(
                "cont_eq_respected",
                True,
                f"all {s.n - s0} closed {s.tf} bar(s) of the forming candle closed at or {side.above} it "
                f"(closest close {s.p(s.close[worst])} at {s.at(worst)}); {level_text}",
            )

    if view.has_forming:
        first_low = view.f_low_time < view.f_high_time and view.f_low < view.f_open
        cl.set(
            "cont_opened_against_bias_first",
            first_low,
            f"forming {b.tf} candle opened {side.p(view.f_open)}; {side.lo} {side.p(view.f_low)} at "
            f"{when(view.f_low_time)}, {side.hi} {side.p(view.f_high)} at {when(view.f_high_time)}",
        )
    else:
        cl.set("cont_opened_against_bias_first", None, f"no closed {e.tf} bar in the forming {b.tf} candle yet")

    tags = _tags(view, bias, s0, level) if s0 < s.n else {}
    live: dict[int, PoiHit] = {}
    dropped: list[str] = []
    for pos, hit in tags.items():
        reason = _dropped(view, pos, hit)
        if reason is None:
            live[pos] = hit
        else:
            dropped.append(f"{s.at(pos)} ({reason})")
    dropped_text = f" Dropped: {'; '.join(dropped[-3:])}." if dropped else ""
    out.seen.update(s0=s0, tag=(max(live), live[max(live)]) if live else None)
    if s0 >= s.n:
        cl.set("cont_poi_tagged", None, f"no closed {s.tf} bar in the forming {b.tf} candle yet")
    elif live:
        last = max(live)
        cl.set(
            "cont_poi_tagged",
            True,
            f"{s.tf} bar {s.at(last)} ({side.lo} {s.p(s.low[last])}) {live[last].text}; "
            f"{len(live)} tagged bar(s) in the forming candle.{dropped_text}",
        )
    else:
        ob = bias.order_block
        ob_text = f"retested the bias order block {side.zone_text(ob.top, ob.bottom)}" if ob else "had a bias order block to retest"
        cl.set(
            "cont_poi_tagged",
            False,
            f"none of the {s.n - s0} closed {s.tf} bar(s) of the forming candle took an untaken swing {side.lo}, "
            f"traded into an unfilled {side.direction} gap {side.above} {side.p(level)} or {ob_text}.{dropped_text}",
        )

    # --- c3 --------------------------------------------------------------------
    setups: list[Setup] = []
    for pos, hit in sorted(live.items()):
        if is_reversal_closure(s, pos):
            kind, closing = "c2", pos
        elif pos + 1 < s.n and completes_candle3_closure(s, pos + 1, cfg.candle3_body_edge):
            kind, closing = "c3", pos + 1
        else:
            continue
        if s.close[closing] < threshold:
            continue
        after = e.first_at_or_after(s.closes_at[closing])
        low = float(s.low[pos])
        setups.append(Setup(kind, pos, closing, low, hit, e.first_break(after, low, cfg.protected_swing_break_on)))
    intact = [item for item in setups if item.broken_at is None]
    broken = [item for item in setups if item.broken_at is not None]
    setup = max(intact, key=lambda item: (item.closing, item.swing)) if intact else None
    out.seen["setup"] = setup
    broken_text = ""
    if broken:
        last_broken = broken[-1]
        broken_text = (
            f" Discarded: the closure at {s.at(last_broken.closing)} had its {side.lo} {s.p(last_broken.low)} "
            f"taken at {e.at(last_broken.broken_at or 0)}."
        )
    if setup is None:
        reason = "no point of interest is tagged" if not live else f"none of the {len(live)} tagged bar(s) closed as a Candle 2 or Candle 3 closure"
        cl.set("cont_setup_closure", False, f"{reason}.{broken_text}")
        cl.set("cont_entry_cisd_confirmed", False, "no active setup closure to confirm yet")
        cl.set("cont_entry_trigger", False, "no entry CISD yet")
        cl.fill("no active setup closure")
        _markup(out, view, bias, level, eq, None, None)
        _invalidation(out, view, bias, level, t1)
        return out

    sw, closing = setup.swing, setup.closing
    if setup.kind == "c2":
        closure_text = (
            f"Candle 2 closure: {s.tf} bar {s.at(sw)} took the prior bar's {side.lo} {s.p(s.low[sw - 1])} "
            f"({side.lo} {s.p(setup.low)}) and closed back {side.above} it at {s.p(s.close[sw])}"
        )
    else:
        closure_text = (
            f"Candle 3 closure: {s.tf} bar {s.at(closing)} held the {side.lo} {s.p(setup.low)} of {s.at(sw)} and "
            f"closed at {s.p(s.close[closing])}, {side.above} its body edge "
            f"{s.p(candle3_edge(s, sw, cfg.candle3_body_edge))}"
        )
    cl.set("cont_setup_closure", True, f"{closure_text}; the swing candle {setup.hit.text}.{broken_text}")
    if setup.kind == "c2":
        aligned = bool(s.close[sw] > s.open[sw])
        cl.set(
            "cont_setup_closure_body_aligned",
            aligned,
            f"swing candle {s.at(sw)} opened {s.p(s.open[sw])} and closed {s.p(s.close[sw])}: "
            f"{'' if aligned else 'not '}{'an' if side.bullish else 'a'} {side.up_close} body",
        )
    else:
        cl.set("cont_setup_closure_body_aligned", True, "Candle 3 closure: the body check applies to Candle 2 closures only")

    e_lo = e.first_at_or_after(s.times[sw])
    e_hi = e.first_at_or_after(s.closes_at[closing])
    read: CisdRead | None = None
    if e_lo >= e_hi:
        cl.set("cont_entry_cisd_confirmed", None, f"no {e.tf} bars inside the setup swing candle {s.at(sw)}")
        cl.set("cont_entry_cisd_swift", None, "Not evaluated: no entry CISD")
    else:
        read = anchored_cisd(e, e_lo + int(np.argmin(e.low[e_lo:e_hi])), cfg.doji_in_series)
        cl.set("cont_entry_cisd_confirmed", read.confirmed, cisd_text(e, read))
        if read.confirmed:
            bars = read.bars_to_confirm or 0
            cl.set(
                "cont_entry_cisd_swift",
                bars <= cfg.cisd_max_bars,
                f"confirmed {bars} {e.tf} bar(s) after the {side.lo} (swift is <= {cfg.cisd_max_bars})",
            )
        else:
            cl.set("cont_entry_cisd_swift", None, "Not evaluated: no entry CISD yet")
    out.seen["entry_read"] = read

    rng = entry_range(e, read, cfg.cisd_max_bars)
    out.seen["entry_range"] = rng

    # --- c4 --------------------------------------------------------------------
    allowed = 1 + cfg.entry_window_extra_candles
    strong_text = ""
    if setup.kind == "c2" and closing + 1 < s.n:
        strong = bool(s.close[closing + 1] > s.high[sw])
        strong_text = (
            f"; setup Candle 3 closed {s.p(s.close[closing + 1])}, "
            f"{'beyond' if strong else 'not beyond'} Candle 2's {side.hi} {s.p(s.high[sw])}"
            f"{', so Candle 4 is allowed' if strong else ''}"
        )
        allowed += 1 if strong else 0
    window_start = s.closes_at[closing]
    end_pos = closing + allowed
    window_end = s.closes_at[end_pos] if end_pos < s.n else None
    window_open = window_end is None or ctx.as_of <= window_end
    cl.set(
        "cont_entry_window_open",
        window_open,
        f"entry window opened {when(window_start)} (close of the {'Candle 2' if setup.kind == 'c2' else 'Candle 3'} "
        f"closure) and {'is still open' if window_end is None else 'ended ' + when(window_end)}{strong_text}",
    )

    mode = cfg.entry_mode_continuation
    cisd_allowed = c2_not_expanded is not False  # rules.md 6: an expanded bias Candle 2 demands a continuation
    if not cisd_allowed and mode != "conservative":
        out.conservative_forced = True
    trigger: Trigger | None = None
    if read is None or not read.confirmed or read.confirm is None:
        cl.set("cont_entry_trigger", False, "no entry CISD yet")
    else:

        def in_window(item: Trigger) -> bool:
            return window_end is None or bool(e.closes_at[item.pos] <= window_end)

        formed = 0
        cisd_trigger: Trigger | None = None
        if mode != "conservative" and cisd_allowed:
            at = max(e.closes_at[read.confirm], window_start)
            pos = max(read.confirm, e.last_closed_by(at))
            candidate = Trigger(
                pos=pos,
                mode="aggressive",
                entry=float(e.close[pos]),
                wick_stop=read.anchor_low,
                stop_label=f"{side.lo} of the setup swing candle (protected {side.lo} from the entry CISD)",
                body_stop=body_stop_of(e, read, cfg),
                read=read,
                poi=None,
                stopped_at=e.first_break(pos + 1, read.anchor_low, cfg.protected_swing_break_on),
            )
            formed += 1
            cisd_trigger = candidate if in_window(candidate) else None
        blocks: list[Trigger] = []
        if mode != "aggressive" or not cisd_allowed:
            candidates = find_continuation_triggers(
                e,
                start=read.confirm + 1,
                protected_low=read.anchor_low,
                protected_pos=read.anchor,
                order_block=Zone(read.level, read.ob_bottom),
                cfg=cfg,
            )
            formed += len(candidates)
            blocks = [item for item in candidates if e.times[item.pos] >= window_start and in_window(item)]
        effective = "conservative" if mode == "aggressive" and not cisd_allowed else mode
        out.seen.update(mode=effective, cisd_allowed=cisd_allowed)
        preferred = ""
        if cfg.wait_for_clean_continuation:

            def clean(item: Trigger) -> bool:
                return _swift(item, cfg) and ran_liquidity(e, item.pos, e_lo) is None and _internal(e, rng, item) is None

            first_pick, _ = pick_trigger(effective, cisd_trigger, blocks, cfg)
            clean_cisd = cisd_trigger if cisd_trigger is not None and clean(cisd_trigger) else None
            clean_blocks = [item for item in blocks if clean(item)]
            if first_pick is not None and not clean(first_pick) and (clean_cisd is not None or clean_blocks):
                cisd_trigger, blocks = clean_cisd, clean_blocks
                preferred = (
                    f"; the trigger at {e.at(first_pick.pos)} was not a clean continuation, so the next clean "
                    f"continuation after it is used"
                )
        trigger, how = pick_trigger(effective, cisd_trigger, blocks, cfg)
        how += preferred
        forced = " (the CISD entry is not allowed: the bias Candle 2 expanded)" if out.conservative_forced else ""
        if trigger is None:
            outside = f" {formed} formed outside the entry window." if formed else ""
            block_text = (
                "a pullback into an entry-timeframe point of interest that then closes through its "
                f"{side.down_close} series"
            )
            waiting = {
                "conservative": block_text,
                "aggressive": "the entry CISD inside the window",
                "either": block_text if not cisd_allowed else f"the entry CISD inside the window, or {block_text}",
            }[effective]
            cl.set("cont_entry_trigger", False, f"mode {effective}{forced}: waiting for {waiting}.{outside}")
        elif trigger.mode == "aggressive":
            cl.set(
                "cont_entry_trigger",
                True,
                f"{how}: the entry CISD is the trigger; trigger bar {e.at(trigger.pos)} closed "
                f"{e.p(trigger.entry)} at {when(e.closes_at[trigger.pos])}",
            )
        else:
            assert trigger.read is not None and trigger.poi is not None
            cl.set(
                "cont_entry_trigger",
                True,
                f"{how}{forced}: continuation order block. The pullback {trigger.poi.text}; "
                f"{cisd_text(e, trigger.read)}. Trigger bar closed at {when(e.closes_at[trigger.pos])}",
            )

    if trigger is not None:
        _v_shape(cl, cfg, e, side, trigger)
        _consolidation(cl, cfg, e, side, rng, trigger)

    if trigger is None:
        cl.fill("no entry trigger yet")
    else:
        out.trigger = trigger
        out.trigger_close = e.closes_at[trigger.pos]
        if trigger.stopped_at is None:
            cl.set(
                "cont_protected_swing_intact",
                True,
                f"nothing since the trigger has traded {side.below} the stop swing {e.p(trigger.wick_stop)}; the setup "
                f"swing {side.lo} {s.p(setup.low)} is untaken",
            )
        else:
            cl.set(
                "cont_protected_swing_intact",
                False,
                f"{e.tf} bar {e.at(trigger.stopped_at)} traded to {e.p(e.low[trigger.stopped_at])}, {side.below} the "
                f"stop swing {e.p(trigger.wick_stop)}",
            )
        bar_high = float(e.high[trigger.pos])
        ran_first = ran_liquidity(e, trigger.pos, e_lo)
        if ran_first is not None:
            cl.set(
                "cont_trigger_clear_of_liquidity",
                False,
                f"trigger bar {e.at(trigger.pos)} ({side.hi} {e.p(bar_high)}) was the first to take the {e.tf} swing "
                f"{side.hi} {e.p(ran_first.price)} from {e.at(ran_first.pos)}: it formed while running short-term liquidity",
            )
        else:
            cl.set(
                "cont_trigger_clear_of_liquidity",
                True,
                f"trigger bar {e.at(trigger.pos)} ({side.hi} {e.p(bar_high)}) took no untaken {e.tf} swing {side.hi} "
                f"formed since {s.at(sw)}",
            )
        forming_wick = view.forming_wick()
        t2: float | None = None
        if forming_wick is None or forming_wick.size != "large":
            first_pos = max(0, b.n - ctx.lookback)
            above = [
                swing_high.price
                for swing_high in b.swing_highs
                if swing_high.pos >= first_pos
                and swing_high.price > t1
                and float(b.high[swing_high.pos + 1 :].max()) <= swing_high.price
                and view.f_high <= swing_high.price
            ]
            t2 = min(above) if above else None
        plan = plan_trade(side, trigger, t1, t2, f"previous {b.tf} candle {side.hi}", cfg)
        out.plan = plan
        t2_text = (
            f" Second structural level {side.p(t2)} (nearest untaken {b.tf} swing {side.hi})." if t2 is not None
            else (" No second structural level: the forming candle's wick is large."
                  if forming_wick is not None and forming_wick.size == "large"
                  else f" No second structural level: no untaken {b.tf} swing {side.hi} beyond it within {ctx.lookback} bars.")
        )
        cl.set("cont_reward_at_least_2r", plan.passed, plan.text + t2_text)
        _objective_at_trigger(cl, ctx, view, side, trigger, t1)
        _early_in_candle(cl, cfg, s, e, trigger)
        found = after_entry(e, trigger, trigger.read.anchor if trigger.read is not None else trigger.pos, cfg)
        out.seen["after_entry"] = found
        _newer_protected_low(cl, cfg, e, side, found, trigger, plan)

    _markup(out, view, bias, level, eq, setup, read)
    _invalidation(out, view, bias, level, t1)
    return out


def _swift(trigger: Trigger, cfg: Any) -> bool:
    bars = trigger.read.bars_to_confirm if trigger.read is not None else None
    return bars is not None and bars <= cfg.cisd_max_bars


def _internal(e: Bars, rng: EntryRange | None, trigger: Trigger) -> str | None:
    """Why ``trigger`` is an internal move of the entry range, or ``None`` when it is not."""
    if rng is None:
        return None
    if trigger.mode == "aggressive":
        return "it is the slow close-through itself"
    anchor = trigger.read.anchor if trigger.read is not None else trigger.pos
    if breakout_before(e, rng, anchor) is None:
        return "no close above the range high came before its pullback"
    return None


def _v_shape(cl: Checklist, cfg: Any, e: Bars, side: Side, trigger: Trigger) -> None:
    """``cont_trigger_v_shape`` (rules.md 6, stage c4): the trigger's own close-through came
    within ``cisd_max_bars`` of its extreme. Slow means consolidating: wait for another
    continuation (the trigger choice does that when ``wait_for_clean_continuation`` is on)."""
    read = trigger.read
    bars = read.bars_to_confirm if read is not None else None
    if read is None or bars is None:
        cl.set("cont_trigger_v_shape", None, "the trigger has no close-through to measure")
        return
    head = f"the trigger's close-through came {bars} {e.tf} bar(s) after its {side.lo}"
    if bars <= cfg.cisd_max_bars:
        cl.set("cont_trigger_v_shape", True, f"{head} (a V-shape is <= {cfg.cisd_max_bars})")
    else:
        cl.set(
            "cont_trigger_v_shape",
            False,
            f"{head}: too slow, price is consolidating rather than continuing. Wait for another continuation",
        )


def _consolidation(cl: Checklist, cfg: Any, e: Bars, side: Side, rng: EntryRange | None, trigger: Trigger) -> None:
    """``cont_not_inside_consolidation`` (rules.md 6, stage c4; "Why Your Continuations Fail")."""
    if rng is None:
        cl.set(
            "cont_not_inside_consolidation",
            True,
            f"no consolidation: the entry CISD closed through in a quick V, so its {side.lo} is protected",
        )
        return
    box = (
        f"the entry CISD took {rng.bars} {e.tf} bars to close through (at {e.at(rng.confirm)}), so price was "
        f"consolidating between {e.p(rng.low)} and {e.p(rng.high)}; that close was a sweep of the range {side.hi}, "
        f"not a continuation"
    )
    why = _internal(e, rng, trigger)
    if why is None:
        brk = breakout_before(e, rng, trigger.read.anchor if trigger.read is not None else trigger.pos)
        cl.set(
            "cont_not_inside_consolidation",
            True,
            f"{box}. Breakout: {e.tf} bar {e.at(brk or 0)} closed {side.above} {e.p(rng.high)}, and the trigger is a "
            f"new continuation after it",
        )
        return
    cl.set(
        "cont_not_inside_consolidation",
        False,
        f"{box}. This trigger is internal to the range ({why}). Wait for a sweep of the range {side.lo} "
        f"{e.p(rng.low)} and a quick V back through, or a close {side.above} {e.p(rng.high)} followed by a new "
        f"continuation. Now: {_range_now(e, side, rng, cfg)}",
    )


def _range_now(e: Bars, side: Side, rng: EntryRange, cfg: Any) -> str:
    """Where the range stands, in one sentence for the checklist."""
    found = range_outcome(e, side, rng, cfg, "the entry CISD")
    if found.state == "open":
        return "price is still inside the range"
    return "; ".join(found.lines)


def _objective_at_trigger(cl: Checklist, ctx: Context, view: View, side: Side, trigger: Trigger, t1: float) -> None:
    """``cont_objective_open_at_trigger``: was the higher-timeframe target already met when
    the trigger closed? Judged at the trigger, so a target reached after entry is the exit,
    not a reason to drop the trade."""
    e, b = view.E, view.B
    if ctx.b_last_close is None:
        cl.set("cont_objective_open_at_trigger", None, "no forming bias candle")
        return
    start = e.first_at_or_after(ctx.b_last_close)
    if start > trigger.pos:
        cl.set("cont_objective_open_at_trigger", None, f"no {e.tf} bar of the forming {b.tf} candle up to the trigger")
        return
    top = float(e.high[start : trigger.pos + 1].max())
    taken = top > t1
    cl.set(
        "cont_objective_open_at_trigger",
        not taken,
        f"by the trigger close {when(e.closes_at[trigger.pos])} the forming {b.tf} candle had reached {side.p(top)}; the "
        f"previous candle's {side.hi} {side.p(t1)} was "
        + (
            "already taken: the higher-timeframe target is met, where a new phase of price (consolidation or "
            "reversal) can start, so a continuation here is late"
            if taken
            else "still open"
        ),
    )


def _early_in_candle(cl: Checklist, cfg: Any, s: Bars, e: Bars, trigger: Trigger) -> None:
    """``cont_entry_early_in_candle``: how far into its setup candle the trigger closed."""
    closed = e.closes_at[trigger.pos]
    last = s.last_closed_by(closed)
    if last < 0:
        cl.set("cont_entry_early_in_candle", None, f"no closed {s.tf} candle before the trigger")
        return
    opened = s.closes_at[last]
    ends = bar_close_time(opened, s.tf)
    frac = float((closed - opened) / (ends - opened)) if ends > opened else 0.0
    ok = frac <= cfg.entry_latest_candle_frac + 1e-9
    detail = f"trigger closed {when(closed)}, {frac:.0%} into the {s.tf} candle {when(opened)} to {when(ends)}" + (
        " (first half: the mechanical ideal)" if frac <= 0.5 else ""
    )
    if not ok:
        detail += f"; later than {cfg.entry_latest_candle_frac:.0%}, so wait for the next {s.tf} candle"
    cl.set("cont_entry_early_in_candle", ok, detail)


def _newer_protected_low(cl: Checklist, cfg: Any, e: Bars, side: Side, found: AfterEntry, trigger: Trigger, plan: TradePlan) -> None:
    """``cont_newer_protected_low`` (advisory): continuations after the entry that each leave
    a higher protected low, the stepping stones a stop can trail to. A slow one is a
    possible consolidation ("Why Your Continuations Fail"), so its low is not one of them."""
    slow = ""
    if found.slow:
        times = ", ".join(e.at(item.pos) for item in found.slow)
        slow = (
            f" {len(found.slow)} slow continuation(s) since the entry ({times}) took more than {cfg.cisd_max_bars} bars "
            f"to close through: possible consolidation, so their {side.lo}s are not used"
        )
        if found.inside:
            slow += f"; {len(found.inside)} quick one(s) formed inside that range before it broke out (internal moves)"
    if not found.trail:
        cl.set(
            "cont_newer_protected_low",
            None,
            f"no newer protected {side.lo} since the entry; the stop stays on {e.p(trigger.wick_stop)}.{slow}".rstrip("."),
        )
        return
    newest = found.trail[-1]
    locked = (newest.wick_stop - cfg.stop_buffer - plan.entry) / plan.risk if plan.risk > 0 else float("nan")
    cl.set(
        "cont_newer_protected_low",
        True,
        f"{len(found.trail)} newer protected {side.lo}(s) since the entry; the newest is {e.p(newest.wick_stop)} "
        f"(continuation at {when(e.closes_at[newest.pos])}). The stop can trail there: {locked:+.2f}R.{slow}".rstrip("."),
    )


def _markup(
    out: PathOutcome, view: View, bias: BiasRead, level: float, eq: float, setup: Setup | None, read: CisdRead | None
) -> None:
    side, b, s, e = view.side, view.B, view.S, view.E
    use_wick = abs(level - eq) > 1e-9
    if use_wick:
        out.markup.append(
            MarkupItem(
                "level", "Respect level (wick midpoint)", b.tf, price=side.px(level), start=b.times[b.n - 1],
                role="reference", short=f"{b.tf} wick 50%",
            )
        )
    # the same level on the setup chart, where the closes are judged against it
    out.markup.append(
        MarkupItem(
            "level", "Respect level on the setup timeframe", s.tf, price=side.px(level), start=view.ctx.b_last_close,
            role="reference", short=f"{b.tf} wick 50%" if use_wick else f"{b.tf} EQ", shared=True,
        )
    )
    if bias.swing_pos is not None and bias.candle_number is not None:
        # the candles of the bias swing, by number: C1 (whose low C2 swept), C2, and C3 once closed
        swing = bias.swing_pos
        for number, pos in ((1, swing - 1), (2, swing), (3, swing + 1)):
            if number > bias.candle_number - 1 or not 0 <= pos < b.n:
                continue
            out.markup.append(
                MarkupItem(
                    "marker", f"Bias Candle {number}", b.tf, price=side.px(float(b.low[pos])), start=b.times[pos],
                    role="reference", short=f"C{number}",
                )
            )
    if bias.swing_pos is not None and bias.candle_number is not None:
        out.markup.append(
            MarkupItem(
                "level",
                f"Bias swing {side.lo} (protected)",
                b.tf,
                price=side.px(float(b.low[bias.swing_pos])),
                start=b.times[bias.swing_pos],
                role="protected",
                short=f"Swing {side.lo}",
            )
        )
    tag = out.seen.get("tag")
    tagged_kind = setup.hit.kind if setup is not None else (tag[1].kind if tag else "")
    if bias.order_block is not None and bias.cisd is not None:
        top, bottom = side.zone(bias.order_block.top, bias.order_block.bottom)
        start = s.times[bias.cisd.series[0]] if bias.cisd.series else s.times[bias.cisd.anchor]
        out.markup.append(
            MarkupItem(
                "zone", "Bias order block", s.tf, top=top, bottom=bottom, start=start,
                role="poi" if tagged_kind == "order_block" else "info", short="POI: bias order block",
            )
        )
    if bias.cisd is not None and bias.cisd.confirm is not None:
        confirm = bias.cisd.confirm
        out.markup.append(
            MarkupItem(
                "marker", "Bias swing confirmed (CISD)", s.tf, price=side.px(float(s.close[confirm])),
                start=s.times[confirm], role="confirm", short="Bias CISD",
            )
        )
    reached = (setup.swing, setup.hit) if setup is not None else tag  # the bar at the point of interest, and the POI
    if reached is not None:
        at, hit = reached
        top, bottom = side.zone(hit.top, hit.bottom)
        names = {"swing": f"POI: swing {side.lo} taken", "fvg": "POI: fair value gap", "order_block": "POI: bias order block"}
        if hit.kind == "swing":
            out.markup.append(
                MarkupItem(
                    "level", names["swing"], s.tf, price=top, end=s.times[at], role="poi",
                    short=f"POI: swing {side.lo}",
                )
            )
        elif hit.kind == "fvg":
            out.markup.append(
                MarkupItem(
                    "zone", names["fvg"], s.tf, top=top, bottom=bottom, end=s.times[at], role="poi",
                    short="POI: gap",
                )
            )
    if setup is None and tag is not None:
        # reached, but no closure stands there yet: mark the bar the read is talking about
        out.markup.append(
            MarkupItem(
                "marker", "At the point of interest (no closure yet)", s.tf, price=side.px(float(s.low[tag[0]])),
                start=s.times[tag[0]], role="waiting", short="At the POI",
            )
        )
    if setup is not None:
        out.markup.append(
            MarkupItem(
                "marker", f"Setup swing {side.lo}", s.tf, price=side.px(setup.low), start=s.times[setup.swing],
                role="protected", short=f"Swing {side.lo}",
            )
        )
        closure = "Candle 2 closure" if setup.kind == "c2" else "Candle 3 closure"
        out.markup.append(
            MarkupItem(
                "marker", f"Setup closure ({closure})", s.tf, price=side.px(float(s.close[setup.closing])),
                start=s.times[setup.closing], role="confirm", short=closure,
            )
        )
    if read is not None and read.confirmed and read.confirm is not None:
        top, bottom = side.zone(read.level, read.ob_bottom)
        out.markup.append(
            MarkupItem(
                "zone", "Entry order block (entry CISD)", e.tf, top=top, bottom=bottom, start=e.times[read.anchor],
                role="confirm", short=f"{side.down_close} run" if read.series else "candle body",
            )
        )
        out.markup.append(
            MarkupItem(
                "marker", "Entry CISD", e.tf, price=side.px(float(e.close[read.confirm])), start=e.times[read.confirm],
                role="confirm", short="CISD",
            )
        )
        rng = out.seen.get("entry_range")
        if rng is not None:
            out.markup.extend(consolidation_marks(e, side, rng, view.ctx.cfg, "the entry CISD"))
    elif read is not None and read.lower_low is None:
        # not confirmed yet: the price an entry-timeframe close has to get through
        out.markup.append(
            MarkupItem(
                "level", "Entry CISD level (no close through it yet)", e.tf, price=side.px(read.level),
                start=e.times[read.series[0] if read.series else read.anchor], role="waiting",
                short=f"Close {side.above} = CISD", shared=True,
            )
        )
    trigger = out.trigger
    if trigger is not None:
        out.markup.append(
            MarkupItem(
                "level", f"Protected {side.lo} (stop swing)", e.tf, price=side.px(trigger.wick_stop),
                start=e.times[trigger.read.anchor] if trigger.read else e.times[trigger.pos],
                role="protected", short=f"Protected {side.lo}", shared=True,
            )
        )
        out.markup.append(
            MarkupItem(
                "marker", "Entry trigger", e.tf, price=side.px(trigger.entry), start=e.times[trigger.pos],
                role="entry", short="Trigger",
            )
        )
        found = out.seen.get("after_entry")
        if found is not None:
            out.markup.extend(after_entry_markup(e, side, found, view.ctx.cfg))
    out.markup[:] = drop_repeated_hints(out.markup)


def _invalidation(out: PathOutcome, view: View, bias: BiasRead, level: float, t1: float) -> None:
    side, b, s = view.side, view.B, view.S
    if bias.swing_pos is not None and bias.candle_number is not None:
        out.invalidation.append(
            f"a trade {side.below} the bias swing {side.lo} {b.p(float(b.low[bias.swing_pos]))}"
        )
    out.invalidation.append(f"a {s.tf} close {side.below} the respect level {side.p(level)}")
    if out.checklist.role("cont_objective_open") == GATE:
        out.invalidation.append(f"the previous {b.tf} candle {side.hi} {side.p(t1)} being taken before entry")
    if view.ctx.forming is not None:
        out.invalidation.append(f"the next {b.tf} candle opening at {when(view.ctx.forming.close_time)}")
