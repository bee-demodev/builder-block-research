"""Reversal path (rules.md section 7): the forming bias candle expands out to, or near,
a key level and turns there with a change in state of delivery.

Evaluated once per side. On the side's mirrored frames the trade is always a long off a
level below price, so "low" below means the high for a short reversal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from companion.styles.ttrades.checklist import ADVISORY, QUALITY, REVERSAL, Checklist
from companion.styles.ttrades.context import Context
from companion.styles.ttrades.continuation import PathOutcome
from companion.styles.ttrades.primitives import Bars, CisdRead, Side, Zone, anchored_cisd, cisd_text, fmt, when
from companion.styles.ttrades.risk import Trigger, body_stop_of, find_continuation_triggers, pick_trigger, plan_trade
from companion.types import MarkupItem


@dataclass(frozen=True)
class KeyLevel:
    """A bias-timeframe level a reversal can form at (rules.md 7.1), in mirrored prices."""

    kind: str  # "previous_candle" | "swing" | "fvg"
    edge: float  # the price the forming candle's low has to reach (a gap: its top)
    hold: float  # a setup close back above this holds the level (a gap: its bottom)
    name: str  # plain-language description in real prices

    def through(self, low: float) -> bool:
        """Did a candle with this low trade through the level (a gap: into it)?"""
        return low <= self.edge if self.kind == "fvg" else low < self.edge

    def held_by(self, close: float) -> bool:
        return close >= self.hold if self.kind == "fvg" else close > self.hold


def key_levels(ctx: Context, side: Side) -> list[KeyLevel]:
    """The key levels below price for a long (above, mirrored, for a short), rules.md 7.1:
    the previous bias candle's low, untaken bias-timeframe swing lows and unfilled bullish
    bias-timeframe fair value gaps, the last two inside ``bias_poi_lookback_bars``."""
    cfg, b = ctx.cfg, ctx.view(side).B
    levels: list[KeyLevel] = []
    if b.n < 1:
        return levels
    k = b.n - 1
    first = max(0, b.n - ctx.lookback)
    if "previous_candle" in cfg.reversal_key_levels:
        price = float(b.low[k])
        levels.append(KeyLevel("previous_candle", price, price, f"the previous {b.tf} candle's {side.lo} {b.p(price)}"))
    if "swing" in cfg.reversal_key_levels:
        for swing in b.swing_lows:
            # knowable once the bar after it has closed; untaken = nothing has traded below it since
            if swing.pos < first or swing.pos + 1 > k or float(b.low[swing.pos + 1 :].min()) < swing.price:
                continue
            name = f"the untaken {b.tf} swing {side.lo} {b.p(swing.price)} from {b.at(swing.pos)}"
            levels.append(KeyLevel("swing", swing.price, swing.price, name))
    if "fvg" in cfg.reversal_key_levels:
        for gap in b.gaps:
            if gap.pos < first or gap.pos + 1 > k or gap.fill_pos is not None or gap.top - gap.bottom < cfg.fvg_min_size:
                continue
            name = (
                f"the unfilled {side.direction} {b.tf} fair value gap {side.zone_text(gap.top, gap.bottom)} "
                f"formed at {b.at(gap.pos)}"
            )
            levels.append(KeyLevel("fvg", gap.top, gap.bottom, name))
    return levels


def nearest_level(ctx: Context, side: Side) -> tuple[KeyLevel, float | None] | None:
    """The key level on this side the forming candle has not traded through and is nearest
    to, and how far its low still is from it (``None`` when no candle is forming yet).

    Descriptive only: it names what would open a reversal route; ``_reached`` decides.
    """
    view = ctx.view(side)
    levels = key_levels(ctx, side)
    if view.has_forming:
        levels = [level for level in levels if not level.through(view.f_low)]
    if not levels:
        return None
    nearest = max(levels, key=lambda level: level.edge)
    return nearest, (float(view.f_low - nearest.edge) if view.has_forming else None)


def _reached(ctx: Context, side: Side) -> tuple[KeyLevel | None, str]:
    """Which key level the forming candle's low has reached, and how far it got (rules.md 7.1).

    A level that was traded through wins over one that was only approached; among those
    traded through the deepest is reported, among those only approached the nearest.
    """
    cfg, view = ctx.cfg, ctx.view(side)
    low = view.f_low
    tolerance = cfg.reversal_level_tolerance_frac * (ctx.avg_range or 0.0)
    levels = key_levels(ctx, side)
    where = f"forming {view.B.tf} candle {side.lo} so far {side.p(low)} at {when(view.f_low_time)}"
    allowance = (
        f"tolerance {cfg.reversal_level_tolerance_frac:.0%} of the average {view.B.tf} range = {fmt(tolerance)}"
        if tolerance > 0
        else "tolerance 0: a level must be traded through"
    )
    if not levels:
        return None, f"{where}; no key level of the kinds {list(cfg.reversal_key_levels)} on this side"
    through = [level for level in levels if level.through(low)]
    near = [level for level in levels if tolerance > 0 and not level.through(low) and low <= level.edge + tolerance]
    if through:
        chosen = min(through, key=lambda level: level.edge)
        verb = "traded into" if chosen.kind == "fvg" else f"traded {side.below}"
        text = f"{where}: {verb} {chosen.name} by {fmt(chosen.edge - low)}"
    elif near:
        chosen = max(near, key=lambda level: level.edge)
        short_by = low - chosen.edge
        share = f" = {short_by / ctx.avg_range:.0%} of the average {view.B.tf} range" if ctx.avg_range else ""
        text = f"{where}: came within {fmt(short_by)}{share} of {chosen.name} without trading through it ({allowance})"
    else:
        nearest = max(levels, key=lambda level: level.edge)
        return None, (
            f"{where}; the nearest key level, {nearest.name}, is still {fmt(low - nearest.edge)} away ({allowance})"
        )
    others = [level.name for level in (*through, *near) if level is not chosen]
    if others:
        text += f". Also reached: {'; '.join(others[:3])}" + (f" and {len(others) - 3} more" if len(others) > 3 else "")
    return chosen, text


def _expansion(ctx: Context, side: Side) -> tuple[bool | None, str]:
    """rules.md 7.1, "expansion out": was the move into the extreme a directional run on the
    setup timeframe? The run is the unbroken series of setup candles closing toward the
    level that ends at the extreme (the series a CISD there has to close through). The
    setup candle still forming is built from closed entry bars, so the read never waits
    for it to close.
    """
    cfg, view = ctx.cfg, ctx.view(side)
    s, e = view.S, view.E
    if ctx.b_last_close is None or not view.has_forming or s.n < 2:
        return None, "no forming bias candle, or fewer than two closed setup candles"
    opens, closes, lows = list(s.open), list(s.close), list(s.low)
    times = list(s.times)
    part = e.first_at_or_after(s.closes_at[s.n - 1])
    partial = part < e.n
    if partial:
        opens.append(float(e.open[part]))
        closes.append(float(e.close[e.n - 1]))
        lows.append(float(e.low[part:].min()))
        times.append(e.times[part])
    s0 = s.first_at_or_after(ctx.b_last_close)
    if s0 >= len(lows):
        return None, f"no {s.tf} candle in the forming {view.B.tf} candle yet"
    anchor = s0 + int(np.argmin(lows[s0:]))

    def member(i: int) -> bool:
        return bool(closes[i] < opens[i] or (cfg.doji_in_series and closes[i] == opens[i]))

    end = anchor if member(anchor) else anchor - 1
    start = end + 1
    while start - 1 >= 0 and member(start - 1):
        start -= 1
    while start <= end and closes[start] == opens[start]:  # a doji never starts a series
        start += 1
    count = max(0, end - start + 1)
    level = max(opens[start : end + 1]) if count else max(opens[anchor], closes[anchor])
    travel = float(level - lows[anchor])
    average = float((s.high[-cfg.avg_range_bars :] - s.low[-cfg.avg_range_bars :]).mean())
    multiple = travel / average if average > 0 else float("inf")
    passed = count >= cfg.reversal_expansion_min_bars and multiple >= cfg.reversal_expansion_min_travel_frac
    run = (
        f"{count} {side.down_close} {s.tf} candle(s) from {when(times[start])} (first open {side.p(level)})"
        if count
        else f"no {side.down_close} {s.tf} candle leads into it"
    )
    forming_note = f"; the {s.tf} candle still forming is counted from closed {e.tf} bars" if partial else ""
    text = (
        f"run into the {side.lo} {side.p(lows[anchor])}: {run}, travelling {fmt(travel)} = {multiple:.2f} times the "
        f"average {s.tf} range {fmt(average)} (a directional run needs >= {cfg.reversal_expansion_min_bars} candle(s) "
        f"and >= {cfg.reversal_expansion_min_travel_frac:g} times){forming_note}"
    )
    if cfg.reversal_expansion_test == "off":
        text += "; the test is switched off, so this is information only"
    return passed, text


def evaluate_reversal(ctx: Context, side: Side) -> PathOutcome:
    """The reversal checklist for a trade in ``side``'s direction."""
    cfg, stack = ctx.cfg, ctx.stack
    roles = {
        "rev_reward_at_least_2r": cfg.reward_check_role,
        "rev_expansion_into_level": QUALITY if cfg.reversal_expansion_test == "directional_run" else ADVISORY,
    }
    cl = Checklist(REVERSAL, stack, side, roles)
    out = PathOutcome("reversal", side, cl)
    view = ctx.view(side)
    b, s, e = view.B, view.S, view.E
    if b.n < 1:
        cl.fill("no closed bias candle")
        return out
    k = b.n - 1
    eq = float((b.high[k] + b.low[k]) / 2.0)
    far = float(b.high[k])

    # --- c1 --------------------------------------------------------------------
    if not view.has_forming:
        cl.set("rev_key_level_reached", None, f"no closed {e.tf} bar in the forming {b.tf} candle yet")
        cl.fill("the forming bias candle has no closed entry bars yet")
        return out
    level, level_text = _reached(ctx, side)
    cl.set("rev_key_level_reached", level is not None, level_text)
    expanded, expansion_text = _expansion(ctx, side)
    cl.set("rev_expansion_into_level", expanded, expansion_text)
    wick = view.forming_wick()
    if wick is None:
        cl.set("rev_opposing_run_small", None, "average bias range not computable")
    else:
        cl.set("rev_opposing_run_small", wick.size == "small", wick.text)
    early, timing = view.wick_timing()
    cl.set("rev_formed_early", early, timing)
    out.invalidation.append(f"a new {side.lo} {side.below} {side.p(view.f_low)} (the read re-anchors on it)")
    out.invalidation.append(f"the next {b.tf} candle opening at {when(ctx.forming.close_time) if ctx.forming else '?'}")
    out.markup.append(
        MarkupItem(
            "marker", f"Reversal wick {side.lo}", e.tf, price=side.px(view.f_low), start=view.f_low_time,
            role="protected", short=f"Wick {side.lo}",
        )
    )
    out.seen.update(level=level, low=view.f_low, low_time=view.f_low_time)
    if level is None:
        cl.set("rev_reclaim", False, "no key level has been reached")
        cl.set("rev_cisd_confirmed", False, "nothing to confirm: no key level has been reached")
        cl.set("rev_entry_trigger", False, "no CISD yet")
        cl.fill("no key level has been reached")
        return out
    if level.kind == "fvg":
        top, bottom = side.zone(level.edge, level.hold)
        out.markup.append(
            MarkupItem("zone", "Key level: fair value gap", b.tf, top=top, bottom=bottom, role="poi", short="Key level: gap")
        )
        out.markup.append(
            MarkupItem(
                "zone", "Key level on the setup timeframe", s.tf, top=top, bottom=bottom, role="poi",
                short=f"Key level: {b.tf} gap",
            )
        )
    else:
        if level.kind == "swing":
            out.markup.append(
                MarkupItem(
                    "level", f"Key level: swing {side.lo}", b.tf, price=side.px(level.edge), role="poi",
                    short=f"Key level: swing {side.lo}",
                )
            )
        what = f"prev {b.tf} {side.lo}" if level.kind == "previous_candle" else f"{b.tf} swing {side.lo}"
        out.markup.append(
            MarkupItem(
                "level", "Key level on the setup timeframe", s.tf, price=side.px(level.edge), role="poi",
                short=f"Key level: {what}",
            )
        )

    # --- c2: a setup bar that closed after the extreme, back on the right side of the level ----
    held = np.array([level.held_by(float(value)) for value in s.close], dtype=bool)
    after = np.flatnonzero((s.closes_at > view.f_low_time) & held)
    if len(after):
        first = int(after[0])
        out.seen["reclaim"] = first
        out.markup.append(
            MarkupItem(
                "marker", "Close back on the trade's side of the key level", s.tf, price=side.px(float(s.close[first])),
                start=s.times[first], role="confirm",
                short="Closed back" if level.through(view.f_low) else f"Close after the {side.lo}",
            )
        )
        cl.set(
            "rev_reclaim",
            True,
            f"{s.tf} bar {s.at(first)} closed at {s.p(s.close[first])}, {side.above} {level.name}, after the "
            f"{side.lo} {side.p(view.f_low)} was made",
        )
    else:
        cl.set(
            "rev_reclaim",
            False,
            f"no {s.tf} bar has closed {side.above} {level.name} since the {side.lo} {side.p(view.f_low)} "
            f"at {when(view.f_low_time)}",
        )

    # --- c3: CISD anchored at the wick low, on the setup frame or (rules.md 4.3) the entry frame ----
    frames: list[Bars] = [s]
    entry_ok = stack.bias in cfg.reversal_entry_tf_confirm_bias and ctx.in_window(
        ctx.as_of, cfg.reversal_entry_tf_confirm_window
    )
    if entry_ok:
        frames.append(e)
    reads: list[tuple[Bars, CisdRead]] = []
    covered = False
    notes: list[str] = []
    pending: list[tuple[Bars, CisdRead]] = []  # reads still waiting for their close-through
    for x in frames:
        start = x.first_at_or_after(ctx.b_last_close) if ctx.b_last_close is not None else x.n
        if start >= x.n:
            notes.append(f"{x.tf}: no closed bar in the forming candle")
            continue
        covered = True
        anchor = start + int(np.argmin(x.low[start:]))
        if x.low[anchor] > view.f_low:
            notes.append(f"{x.tf}: the bar holding the {side.lo} {side.p(view.f_low)} has not closed")
            continue
        read = anchored_cisd(x, anchor, cfg.doji_in_series)
        notes.append(f"{x.tf}: {cisd_text(x, read)}")
        if read.confirmed:
            reads.append((x, read))
        elif read.lower_low is None:
            pending.append((x, read))
    window = cfg.reversal_entry_tf_confirm_window
    scope = (
        f"read on {s.tf} and {e.tf} (as_of is inside {window[0]}-{window[1]} New York with a {stack.bias} bias)"
        if entry_ok
        else f"read on {s.tf} only"
    )
    chosen: tuple[Bars, CisdRead] | None = None
    if reads:
        chosen = min(reads, key=lambda item: item[0].closes_at[item[1].confirm or 0])
    cisd_tf = chosen[0].tf if chosen else s.tf
    out.seen.update(cisd=chosen, pending=pending, entry_frame_allowed=entry_ok)
    if chosen is None:
        for frame, waiting in pending:  # the price a close has to get through, per frame it may print on
            out.markup.append(
                MarkupItem(
                    "level", "Reversal CISD level (no close through it yet)", frame.tf, price=side.px(waiting.level),
                    start=frame.times[waiting.series[0] if waiting.series else waiting.anchor], role="waiting",
                    short=f"Close {side.above} = CISD",
                )
            )
    if not covered:
        cl.set("rev_cisd_confirmed", None, f"{scope}; " + "; ".join(notes))
    else:
        cl.set("rev_cisd_confirmed", chosen is not None, f"{scope}; " + "; ".join(notes), timeframe=cisd_tf)
    if chosen is None or chosen[1].confirm is None:
        cl.set("rev_cisd_swift", None, "Not evaluated: no CISD yet", timeframe=cisd_tf)
        cl.set("rev_entry_trigger", False, "no CISD yet")
        cl.fill("no CISD confirms the wick yet")
        return out
    x, read = chosen
    confirm = read.confirm
    assert confirm is not None
    bars = read.bars_to_confirm or 0
    cl.set(
        "rev_cisd_swift",
        bars <= cfg.cisd_max_bars,
        f"confirmed {bars} {x.tf} bar(s) after the {side.lo} (swift is <= {cfg.cisd_max_bars})",
        timeframe=x.tf,
    )
    top, bottom = side.zone(read.level, read.ob_bottom)
    out.markup.append(
        MarkupItem(
            "zone", "Reversal order block (CISD)", x.tf, top=top, bottom=bottom, start=x.times[read.anchor],
            role="confirm", short=f"{side.down_close} run" if read.series else "candle body",
        )
    )
    out.markup.append(
        MarkupItem(
            "marker", "Reversal CISD", x.tf, price=side.px(float(x.close[confirm])), start=x.times[confirm],
            role="confirm", short="CISD",
        )
    )

    # --- c4 --------------------------------------------------------------------
    mode = cfg.entry_mode_reversal
    confirmed_at = x.closes_at[confirm]
    cisd_trigger: Trigger | None = None
    if mode != "conservative":
        pos = e.last_closed_by(confirmed_at)
        if pos >= 0:
            cisd_trigger = Trigger(
                pos=pos,
                mode="aggressive",
                entry=float(e.close[pos]),
                wick_stop=view.f_low,
                stop_label=f"the reversal wick {side.lo}",
                body_stop=body_stop_of(x, read, cfg),
                read=read,
                poi=None,
            )
    blocks: list[Trigger] = []
    stopped_note = ""
    if mode != "aggressive":
        candidates = find_continuation_triggers(
            e,
            start=e.first_at_or_after(confirmed_at),
            protected_low=view.f_low,
            protected_pos=view.f_low_pos,
            order_block=Zone(read.level, read.ob_bottom),
            cfg=cfg,
        )
        blocks = [item for item in candidates if item.stopped_at is None]
        stopped = [item for item in candidates if item.stopped_at is not None]
        if stopped:
            last = stopped[-1]
            stopped_note = (
                f" The continuation at {e.at(last.pos)} was stopped: {e.at(last.stopped_at or 0)} traded "
                f"{side.below} its pullback {side.lo} {e.p(last.wick_stop)}."
            )
    trigger, how = pick_trigger(mode, cisd_trigger, blocks, cfg)
    out.seen["mode"] = mode
    if trigger is None:
        block_text = (
            f"a pullback that holds the wick {side.lo} {side.p(view.f_low)}, reaches an entry-timeframe point of "
            f"interest and closes through its {side.down_close} series"
        )
        waiting = block_text if mode == "conservative" else f"an entry bar closed at the CISD, or {block_text}"
        cl.set("rev_entry_trigger", False, f"mode {mode}: waiting for {waiting}.{stopped_note}")
        cl.fill("no entry trigger yet")
        return out
    if trigger.mode == "aggressive":
        cl.set(
            "rev_entry_trigger",
            True,
            f"{how}: the {x.tf} bar that confirmed the CISD is the trigger; it closed {e.p(trigger.entry)} at "
            f"{when(confirmed_at)}.{stopped_note}",
        )
    else:
        assert trigger.read is not None and trigger.poi is not None
        cl.set(
            "rev_entry_trigger",
            True,
            f"{how}: continuation order block. The pullback {trigger.poi.text}; "
            f"{cisd_text(e, trigger.read)}. Trigger bar closed at {when(e.closes_at[trigger.pos])}.{stopped_note}",
        )

    out.trigger = trigger
    out.trigger_close = e.closes_at[trigger.pos]
    cl.set(
        "rev_wick_intact",
        True,
        f"no bar since the CISD has traded {side.below} the wick {side.lo} {side.p(view.f_low)} "
        f"(the read re-anchors on any new {side.lo}, so a confirmed CISD always refers to the current one)",
    )
    plan = plan_trade(side, trigger, eq, far, f"previous {b.tf} candle equilibrium", cfg)
    out.plan = plan
    cl.set(
        "rev_reward_at_least_2r",
        plan.passed,
        plan.text + f" Second structural level {side.p(far)} (previous {b.tf} candle {side.hi}).",
    )
    out.markup.append(
        MarkupItem(
            "level", f"Protected {side.lo} (stop swing)", e.tf, price=side.px(trigger.wick_stop),
            start=e.times[trigger.read.anchor] if trigger.mode == "conservative" and trigger.read else view.f_low_time,
            role="protected", short=f"Protected {side.lo}",
        )
    )
    out.markup.append(
        MarkupItem(
            "marker", "Entry trigger", e.tf, price=side.px(trigger.entry), start=e.times[trigger.pos],
            role="entry", short="Trigger",
        )
    )
    return out
