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


def evaluate_continuation(ctx: Context, bias: BiasRead) -> PathOutcome:
    cfg, stack, side = ctx.cfg, ctx.stack, bias.side
    roles = {"cont_objective_open": cfg.objective_open_role, "cont_reward_at_least_2r": cfg.reward_check_role}
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
        trigger, how = pick_trigger(effective, cisd_trigger, blocks, cfg)
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
        ran = [
            swing_high
            for swing_high in e.swing_highs
            if e_lo <= swing_high.pos
            and swing_high.pos + 1 < trigger.pos
            and bar_high > swing_high.price
            and float(e.high[swing_high.pos + 1 : trigger.pos].max()) <= swing_high.price
        ]
        if ran:
            ran_first = ran[0]
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

    _markup(out, view, bias, level, eq, setup, read)
    _invalidation(out, view, bias, level, t1)
    return out


def _markup(
    out: PathOutcome, view: View, bias: BiasRead, level: float, eq: float, setup: Setup | None, read: CisdRead | None
) -> None:
    side, b, s, e = view.side, view.B, view.S, view.E
    use_wick = abs(level - eq) > 1e-9
    if use_wick:
        out.markup.append(
            MarkupItem(
                "level", "Respect level (wick midpoint)", b.tf, price=side.px(level), start=b.times[b.n - 1],
                role="reference", short="Wick 50%",
            )
        )
    # the same level on the setup chart, where the closes are judged against it
    out.markup.append(
        MarkupItem(
            "level", "Respect level on the setup timeframe", s.tf, price=side.px(level), start=view.ctx.b_last_close,
            role="reference", short=f"{b.tf} wick 50%" if use_wick else f"{b.tf} EQ",
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
    elif read is not None and read.lower_low is None:
        # not confirmed yet: the price an entry-timeframe close has to get through
        out.markup.append(
            MarkupItem(
                "level", "Entry CISD level (no close through it yet)", e.tf, price=side.px(read.level),
                start=e.times[read.series[0] if read.series else read.anchor], role="waiting",
                short=f"Close {side.above} = CISD",
            )
        )
    trigger = out.trigger
    if trigger is not None:
        out.markup.append(
            MarkupItem(
                "level", f"Protected {side.lo} (stop swing)", e.tf, price=side.px(trigger.wick_stop),
                start=e.times[trigger.read.anchor] if trigger.read else e.times[trigger.pos],
                role="protected", short=f"Protected {side.lo}",
            )
        )
        out.markup.append(
            MarkupItem(
                "marker", "Entry trigger", e.tf, price=side.px(trigger.entry), start=e.times[trigger.pos],
                role="entry", short="Trigger",
            )
        )


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
