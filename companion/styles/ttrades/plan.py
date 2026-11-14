"""What has to happen, and the trade it leads to (rules.md section 10.6).

Presentation only, like ``read.py``: nothing here decides anything. From what
``bias.py``, ``continuation.py`` and ``reversal.py`` already computed it builds

- the steps: the selected path's step criteria as an ordered list, highest timeframe
  first, each done / next / later / blocked, the next one with the exact price the rules
  are waiting on;
- the position plan: entry, stop and target. "triggered" restates the rules' own trade
  plan and says what price has done since the trigger; "planned" projects it from the
  level the trigger has to clear and the current structural extreme.

Prices inside are in the side's mirrored space, as everywhere in the style; everything
that leaves is a real price.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from companion.contracts import CONTRACTS, cost_in_r, root
from companion.styles.ttrades.bias import BiasRead
from companion.styles.ttrades.config import TTradesConfig
from companion.styles.ttrades.context import Context, View
from companion.styles.ttrades.continuation import PathOutcome
from companion.styles.ttrades.primitives import BEAR, BULL, CisdRead, Side, candle3_edge
from companion.styles.ttrades.read import _Teller, _blockers, _cap, level_words, money
from companion.styles.ttrades.reversal import KeyLevel, key_levels, nearest_level
from companion.types import LookFor, LookOption, LookStep, PlanStep, PositionPlan, ReadStep

DONE, NEXT, LATER, BLOCKED = "done", "next", "later", "blocked"


@dataclass
class _Draft:
    """One step before its status is known."""

    role: str
    timeframe: str  # where it was seen once done
    label: str
    done: bool
    seen: str = ""  # what was observed, shown when done
    need: str = ""  # the exact condition, shown when it is the next step
    price: float | None = None  # real price of the condition
    level_label: str = ""
    watch: str = ""  # the timeframe to watch while it is not done ("" = ``timeframe``)


def _assemble(drafts: list[_Draft], blockers: dict[str, list[str]], restart: int | None = None) -> tuple[PlanStep, ...]:
    """Statuses for the drafts, in order: done until the first step that has not happened
    (the next one), later after it. ``restart`` is the position of a step that has to
    happen afresh, whatever was seen from there on. A quality check that stands in the way
    blocks the last finished step of its timeframe's line."""
    steps: list[PlanStep] = []
    seen_next = False
    for index, draft in enumerate(drafts):
        done = draft.done and not (restart is not None and index >= restart)
        if done:
            steps.append(PlanStep(draft.role, draft.timeframe, DONE, draft.label, draft.seen))
        elif not seen_next:
            seen_next = True
            steps.append(
                PlanStep(draft.role, draft.watch or draft.timeframe, NEXT, draft.label, draft.need, draft.price, draft.level_label)
            )
        else:
            steps.append(PlanStep(draft.role, draft.watch or draft.timeframe, LATER, draft.label))
    for role, phrases in blockers.items():
        if not phrases:
            continue
        said = "; ".join(phrases)
        finished = [index for index, step in enumerate(steps) if step.role == role and step.status == DONE]
        waiting = [index for index, step in enumerate(steps) if step.role == role and step.status == NEXT]
        if finished:
            step = steps[finished[-1]]
            detail = f"{step.detail}. But {said}" if step.detail else _cap(said)
            steps[finished[-1]] = PlanStep(step.role, step.timeframe, BLOCKED, step.label, detail)
        elif waiting:
            step = steps[waiting[0]]
            steps[waiting[0]] = PlanStep(
                step.role, step.timeframe, NEXT, step.label, f"{step.detail}. As it stands a trade would still be blocked: {said}",
                step.price, step.level_label,
            )  # fmt: skip
    return tuple(steps)


# --- continuation -----------------------------------------------------------------


@dataclass(frozen=True)
class _Poi:
    """A point of interest ahead of a pullback, in the side's mirrored space."""

    near: float  # the edge a pullback from above reaches first
    top: float  # the zone drawn for it (a swing low is its candle's lower wick)
    bottom: float
    name: str  # in a sentence: "the unfilled 1h fair value gap"
    short: str  # on its own: "1h fair value gap"
    mid: float | None  # the order block's mean threshold


def _pois(view: View, bias: BiasRead, level: float) -> list[_Poi]:
    """The points of interest a setup candle can reach from above (rules.md 3.14, stage
    c2): the untaken setup swing lows, the unfilled gaps above the respect level and the
    bias order block, nearest (highest near edge) first. Ties keep this order."""
    s, b, cfg, side = view.S, view.B, view.ctx.cfg, view.side
    if not s.n or not view.has_forming:
        return []
    found: list[_Poi] = []
    first = s.first_at_or_after(b.times[b.n - 2]) if b.n >= 2 else 0
    for swing in s.swing_lows:
        if swing.pos + 1 >= s.n or swing.pos < first or float(s.low[swing.pos + 1 :].min()) < swing.price:
            continue
        body = float(min(s.open[swing.pos], s.close[swing.pos]))
        found.append(_Poi(swing.price, body, swing.price, f"the untaken {s.tf} swing {side.lo}", f"{s.tf} swing {side.lo}", None))
    for gap in s.gaps:
        if gap.pos + 1 >= s.n or gap.fill_pos is not None or gap.top - gap.bottom < cfg.fvg_min_size or not gap.top > level:
            continue
        found.append(_Poi(gap.top, gap.top, gap.bottom, f"the unfilled {s.tf} fair value gap", f"{s.tf} fair value gap", None))
    if bias.order_block is not None:
        ob = bias.order_block
        found.append(_Poi(ob.top, ob.top, ob.bottom, "the bias order block", "Bias order block", ob.mid))
    return sorted(found, key=lambda poi: poi.near, reverse=True)


def _nearest_poi(view: View, bias: BiasRead, level: float) -> tuple[float, str, float | None] | None:
    """The point of interest a setup candle reaches first from above: its near edge, its
    name and, for the order block, the mean threshold a candle that trades into it has to
    close at or above."""
    found = _pois(view, bias, level)
    return (found[0].near, found[0].name, found[0].mid) if found else None


def _conservative(cfg: TTradesConfig, path: PathOutcome) -> bool:
    """The continuation entry is the conservative one: by configuration, or forced because
    the bias Candle 2 expanded (rules.md 6)."""
    return cfg.entry_mode_continuation == "conservative" or path.checklist.passed("bias_c2_not_expanded") is False


def _order_block_need(tell: _Teller, read: CisdRead, low: float) -> tuple[str, float, str]:
    side, e = tell.side, tell.view.E
    need = (
        f"{e.tf} pullback into {tell.zone(read.level, read.ob_bottom)} that holds the {side.lo} {tell.p(low)}, then a "
        f"{e.tf} close back {tell.up} (a continuation order block)"
    )
    return need, side.px(read.level), f"{e.tf} pullback to"


def _continuation(ctx: Context, bias: BiasRead, path: PathOutcome, tell: _Teller) -> tuple[list[_Draft], int | None]:
    side, b, s, e = tell.side, tell.view.B, tell.view.S, tell.view.E
    cl, seen, cfg = path.checklist, path.seen, ctx.cfg
    above, up = side.above, tell.up
    level = seen["level"]
    respect = tell.p(level)
    drafts: list[_Draft] = []

    # the bias swing, confirmed on the setup timeframe
    swing = tell.p(float(b.low[bias.swing_pos])) if bias.swing_pos is not None else ""
    first = _Draft("bias", b.tf, f"{b.tf} bias is {side.direction}", cl.passed("bias_cisd_confirmed") is True, watch=s.tf)
    first.seen = f"Candle {bias.candle_number} forming; the {s.tf} confirmed the swing {side.lo} {swing}"
    cisd = bias.cisd
    if cisd is not None and not cisd.confirmed and cisd.lower_low is None:
        first.need = f"{s.tf} close {above} {tell.p(cisd.level)}, which confirms the {b.tf} swing {side.lo} {swing}"
        first.price, first.level_label = side.px(cisd.level), f"{s.tf} close {above}"
    else:
        first.need = f"The {s.tf} has to confirm the {b.tf} swing {side.lo} {swing}"
    drafts.append(first)

    # the pullback
    setup, tag = seen.get("setup"), seen.get("tag")
    reached = (setup.swing, setup.hit) if setup is not None else tag
    pullback = _Draft("setup", s.tf, f"{s.tf} pulls back to a point of interest", reached is not None)
    if reached is not None:
        pullback.seen = f"{_cap(tell.candle(s, reached[0]))} reached {tell.hit(s, reached[1])}"
    else:
        nearest = _nearest_poi(tell.view, bias, level)
        part = e.first_at_or_after(s.closes_at[s.n - 1]) if s.n else e.n
        low_now = float(e.low[part:].min()) if part < e.n else None  # the setup candle still forming, from closed entry bars
        if nearest is not None and low_now is not None and low_now <= nearest[0]:
            edge, name, mid = nearest
            if mid is not None:
                pullback.need = (
                    f"The {s.tf} candle now forming is in {name} ({side.lo} {tell.p(low_now)}): it has to close at or "
                    f"{above} the block's midpoint {tell.p(mid)}"
                )
                pullback.price, pullback.level_label = side.px(mid), f"{s.tf} close {above}"
            else:
                pullback.need = f"The {s.tf} candle now forming has reached {name} {tell.p(edge)} ({side.lo} {tell.p(low_now)}): it has to close"
                pullback.price, pullback.level_label = side.px(edge), f"{s.tf} pullback to"
        elif nearest is not None:
            pullback.need = (
                f"{s.tf} candle trades {'down' if side.bullish else 'up'} to {tell.p(nearest[0])} ({nearest[1]}, the nearest "
                f"point of interest), with {s.tf} closes holding {above} {respect}"
            )
            pullback.price, pullback.level_label = side.px(nearest[0]), f"{s.tf} pullback to"
        else:
            pullback.need = f"A {s.tf} pullback into a point of interest, with {s.tf} closes holding {above} {respect}"
    drafts.append(pullback)

    # the closure there
    closure = _Draft("setup", s.tf, f"{s.tf} closes back {up} there", setup is not None)
    if setup is not None:
        name = "Candle 2" if setup.kind == "c2" else "Candle 3"
        closure.seen = f"{name} closure at {tell.at(s, setup.closing)}, close {tell.p(float(s.close[setup.closing]))}"
    else:
        closure.need = f"A {s.tf} candle closes back {up} at a point of interest, holding {above} {respect}"
        floor = level - cfg.eq_tolerance_frac * float(b.high[b.n - 1] - b.low[b.n - 1])  # closes below it lose the respect level
        part = e.first_at_or_after(s.closes_at[s.n - 1]) if s.n else e.n
        low_now = float(e.low[part:].min()) if part < e.n else None  # the setup candle still forming, from closed entry bars
        tagged_last = tag is not None and tag[0] == s.n - 1
        nearest = _nearest_poi(tell.view, bias, level)
        at_poi = tagged_last or (nearest is not None and low_now is not None and low_now <= nearest[0])
        if s.n and low_now is not None and low_now < s.low[s.n - 1] and at_poi:
            # it has taken the candle before it at a point of interest: a close back above that low is the Candle 2 closure (3.5)
            edge = max(float(s.low[s.n - 1]), floor)
            closure.need = (
                f"The {s.tf} candle now forming ({side.lo} {tell.p(low_now)}, at a point of interest) closes back {above} "
                f"{tell.p(edge)}, the {side.lo} of the candle before it (a Candle 2 closure)"
            )
            closure.price, closure.level_label = side.px(edge), f"{s.tf} close {above}"
        elif tagged_last and tag is not None:
            # the candle at the point of interest has closed without a closure: the next one can complete a Candle 3 closure (3.6)
            edge = max(candle3_edge(s, tag[0], cfg.candle3_body_edge), floor)
            closure.need = (
                f"The {s.tf} candle now forming closes {above} {tell.p(edge)} while holding the {side.lo} "
                f"{tell.p(float(s.low[tag[0]]))} (a Candle 3 closure)"
            )
            closure.price, closure.level_label = side.px(edge), f"{s.tf} close {above}"
    drafts.append(closure)

    # the turn on the entry timeframe, and the entry
    read: CisdRead | None = seen.get("entry_read")
    trigger = path.trigger
    conservative = _conservative(cfg, path)

    def turn_need() -> tuple[str, float | None, str]:
        if read is None:
            return f"A {e.tf} close through the {side.down_close} run into the setup {side.lo}", None, ""
        if read.lower_low is not None:
            return f"A fresh {s.tf} closure: the {side.lo} {tell.p(read.anchor_low)} was taken before the {e.tf} turned", None, ""
        need = (
            f"{e.tf} close {above} {tell.p(read.level)}, the open of the {side.down_close} run into the {side.lo} "
            f"{tell.p(read.anchor_low)}"
        )
        return need, side.px(read.level), f"{e.tf} close {above}"

    turned = read is not None and read.confirmed and read.confirm is not None
    if conservative:
        turn = _Draft("entry", e.tf, f"{e.tf} turns {up}", turned)
        if turned and read is not None and read.confirm is not None:
            turn.seen = f"{_cap(tell.at(e, read.confirm))} close {tell.p(float(e.close[read.confirm]))}, {above} {tell.p(read.level)}"
        else:
            turn.need, turn.price, turn.level_label = turn_need()
        drafts.append(turn)
        entry = _Draft("entry", e.tf, f"{e.tf} pulls back, holds and closes back {up}: the entry", trigger is not None)
    else:
        entry = _Draft("entry", e.tf, f"{e.tf} turns {up}: the entry", trigger is not None)
    if trigger is not None:
        kind = "the turn" if trigger.mode == "aggressive" else f"a continuation order block off {tell.p(trigger.wick_stop)}"
        entry.seen = f"{_cap(tell.at(e, trigger.pos))} close {tell.p(trigger.entry)} ({kind})"
    elif turned and read is not None:
        entry.need, entry.price, entry.level_label = _order_block_need(tell, read, read.anchor_low)
    else:
        entry.need, entry.price, entry.level_label = turn_need()
    drafts.append(entry)

    restart: int | None = None
    if trigger is None and setup is not None and cl.passed("cont_entry_window_open") is False:
        # the window of this closure has passed without an entry: a fresh closure is what comes next
        restart = 2
        closure.need = (
            f"A fresh {s.tf} closure at a point of interest: the entry window of the one at {tell.at(s, setup.closing)} has passed"
        )
        closure.price, closure.level_label = None, ""
    return drafts, restart


# --- reversal ---------------------------------------------------------------------


def _reversal(ctx: Context, path: PathOutcome, tell: _Teller) -> list[_Draft]:
    side, b, s, e = tell.side, tell.view.B, tell.view.S, tell.view.E
    seen, cfg = path.seen, ctx.cfg
    above, up = side.above, tell.up
    level, low = seen["level"], seen["low"]
    verb = ("into" if level.kind == "fvg" else f"{side.below}") if level.through(low) else "close to"
    made = tell.at(e, tell.view.f_low_pos)
    drafts = [
        _Draft(
            "bias", b.tf, f"{b.tf} reaches a key level", True,
            seen=f"{_cap(side.lo)} {tell.p(low)} at {made}, {verb} {level_words(tell, level)}",
        )  # fmt: skip
    ]
    reclaim = seen.get("reclaim")
    hold = tell.p(level.hold)
    back = _Draft("setup", s.tf, f"{s.tf} closes back {above} the level", reclaim is not None)
    if reclaim is not None:
        back.seen = f"{_cap(tell.candle(s, reclaim))} closed {tell.p(float(s.close[reclaim]))}"
    else:
        back.need = f"{s.tf} close back {above} {hold}, after the {side.lo} {tell.p(low)}"
        back.price, back.level_label = side.px(level.hold), f"{s.tf} close {above}"
    drafts.append(back)

    chosen = seen.get("cisd")
    pending = seen.get("pending") or []
    trigger = path.trigger

    def turn_need() -> tuple[str, float | None, str, str]:
        if not pending:
            return (
                f"The candle holding the {side.lo} {tell.p(low)} closes, then a close through the {side.down_close} run into it",
                None, "", e.tf,
            )  # fmt: skip
        frame, nearest = min(pending, key=lambda item: item[1].level)
        need = " or ".join(f"{x.tf} close {above} {tell.p(waiting.level)}" for x, waiting in pending)
        return f"{need}: a close through the {side.down_close} run into the {side.lo}", side.px(nearest.level), f"{frame.tf} close {above}", frame.tf

    conservative = cfg.entry_mode_reversal == "conservative"
    if conservative:
        turn = _Draft("entry", chosen[0].tf if chosen is not None else e.tf, f"Price turns {up} at the level", chosen is not None)
        if chosen is not None:
            x, read = chosen
            turn.seen = f"{_cap(tell.at(x, read.confirm or 0))} {x.tf} close {tell.p(float(x.close[read.confirm or 0]))}, {above} {tell.p(read.level)}"
        else:
            turn.need, turn.price, turn.level_label, turn.watch = turn_need()
        drafts.append(turn)
        entry = _Draft("entry", e.tf, f"{e.tf} pulls back, holds and closes back {up}: the entry", trigger is not None)
    else:
        entry = _Draft("entry", e.tf, f"Price turns {up} at the level: the entry", trigger is not None)
    if trigger is not None:
        kind = "the turn" if trigger.mode == "aggressive" else f"a continuation order block off {tell.p(trigger.wick_stop)}"
        entry.seen = f"{_cap(tell.at(e, trigger.pos))} {e.tf} close {tell.p(trigger.entry)} ({kind})"
    elif chosen is not None:
        entry.need, entry.price, entry.level_label = _order_block_need(tell, chosen[1], low)
    else:
        entry.need, entry.price, entry.level_label, entry.watch = turn_need()
    drafts.append(entry)
    return drafts


def _route(ctx: Context, side: Side, status: str) -> list[PlanStep]:
    """The reversal route to ``side`` while no key level is reached: what would open it."""
    tell = _Teller(ctx, side)
    b, s = tell.view.B, tell.view.S
    found = nearest_level(ctx, side)
    label = f"{b.tf} reaches a key level"
    if found is None:
        return [PlanStep("bias", b.tf, BLOCKED if status == NEXT else LATER, label, f"The rules give no key level on the {side.lo} side right now")]
    level, away = found
    name = level_words(tell, level)
    tolerance = ctx.cfg.reversal_level_tolerance_frac * (ctx.avg_range or 0.0)
    near = f" (within {money(tolerance)} of it counts)" if tolerance > 0 else ""
    if away is None:
        detail = f"The new {b.tf} candle trades to {name}{near}"
    else:
        detail = (
            f"{b.tf} candle trades to {name}{near}; its {side.lo} so far is {tell.p(tell.view.f_low)}, {money(away)} away"
        )
    steps = [PlanStep("bias", b.tf, status, label, detail, side.px(level.edge), f"{b.tf} trades to")]  # type: ignore[arg-type]
    if status == NEXT:
        steps.append(PlanStep("setup", s.tf, LATER, f"{s.tf} closes back {side.above} the level"))
        steps.append(PlanStep("entry", tell.view.E.tf, LATER, f"Price turns {tell.up} at the level: the entry"))
    return steps


def _no_route(ctx: Context, read: tuple[ReadStep, ...], bias: BiasRead, forced: Side | None, reversals_open: dict[str, bool]) -> tuple[PlanStep, ...]:
    """No idea is alive. Say where the read stops, then what would open a route."""
    steps: list[PlanStep] = []
    for row in read:  # a forced side the bias does not agree with opens on a waiting row: nothing to restate
        if row.status == "confirmed":
            steps.append(PlanStep(row.role, row.timeframe, DONE, row.headline, row.reason.rstrip(".")))
            continue
        if row.status != "waiting":
            steps.append(PlanStep(row.role, row.timeframe, BLOCKED, row.headline, row.reason.rstrip(".")))
        break
    if not len(ctx.b) or not reversals_open:
        return tuple(steps)
    if forced is not None:
        if reversals_open.get(forced.direction):
            steps.extend(_route(ctx, forced, NEXT))
        return tuple(steps)
    for side in (BULL, BEAR):
        if not reversals_open.get(side.direction):
            continue
        for step in _route(ctx, side, LATER):
            label = f"A {side.trade} opens if the {step.label[0].lower()}{step.label[1:]}"
            steps.append(PlanStep(step.role, step.timeframe, LATER, label, step.detail, step.price, step.level_label))
    return tuple(steps)


# --- the position -----------------------------------------------------------------


def _position(ctx: Context, path: PathOutcome, tell: _Teller, decision: str, stage: str, told: bool) -> PositionPlan | None:
    side, b, e = tell.side, tell.view.B, tell.view.E
    cfg = ctx.cfg
    if not e.n:
        return None
    last = float(e.close[e.n - 1])
    trade = side.trade
    trigger, plan = path.trigger, path.plan

    def build(state: str, entry: float, stop: float, target: float, since: int, note: str) -> PositionPlan | None:
        risk = entry - stop
        if not risk > 0 or not target > entry:
            return None  # the rules cannot give these levels a reward-to-risk
        outcome, at, r_now = "open", None, None
        stage_label, age = "forming", None
        if state == "triggered":
            after = since + 1
            stopped = np.flatnonzero(e.low[after:] < stop)
            reached = np.flatnonzero(e.high[after:] >= target)
            first_stop = int(stopped[0]) + after if len(stopped) else None
            first_target = int(reached[0]) + after if len(reached) else None
            if first_stop is not None and (first_target is None or first_stop <= first_target):
                outcome, at = "stopped", e.times[first_stop].to_pydatetime()  # a bar that did both counts as stopped
            elif first_target is not None:
                outcome, at = "target_reached", e.times[first_target].to_pydatetime()
            r_now = (last - entry) / risk
            age = e.n - 1 - since  # closed entry bars after the trigger bar
            if outcome != "open":
                stage_label = "played_out"
            elif age > cfg.actionable_entry_bars or abs(r_now) > cfg.actionable_max_r:
                stage_label = "late"
            else:
                stage_label = "actionable"
        cost_mini, cost_micro = cost_in_r(ctx.symbol, risk)
        return PositionPlan(
            direction=trade,  # type: ignore[arg-type]
            state=state,  # type: ignore[arg-type]
            entry=side.px(entry),
            stop=side.px(stop),
            target=side.px(target),
            r_multiple=(target - entry) / risk,
            timeframe=e.tf,
            since=e.times[since].to_pydatetime(),
            outcome=outcome,  # type: ignore[arg-type]
            outcome_at=at,
            last=side.px(last),
            r_now=r_now,
            note=note,
            stage_label=stage_label,  # type: ignore[arg-type]
            age_bars=age,
            risk_adr=risk / ctx.adr if ctx.adr else None,
            cost_r_mini=cost_mini,
            cost_r_micro=cost_micro,
        )

    if trigger is not None and plan is not None:
        how = "the turn" if trigger.mode == "aggressive" else "a continuation order block"
        stop_note = "the bodies of the trigger candles (body stop)" if plan.stop_is_body else plan.stop_label
        if stage == "c4" and (decision in ("long", "short") or told):
            note = f"Entry is the close of the {e.tf} candle at {tell.at(e, trigger.pos)} ({how}). Stop: {stop_note}."
            return build("triggered", plan.entry, plan.stop, plan.targets[0], trigger.pos, note)
        if stage != "c4":
            note = (
                f"Planned: the {e.tf} has turned ({how} at {tell.at(e, trigger.pos)}) but the steps above it are not "
                f"complete. Stop: {stop_note}; the levels move if price makes a new {side.lo} first."
            )
            return build("planned", plan.entry, plan.stop, plan.targets[0], e.n - 1, note)
        return None
    if decision != "watch" or stage == "c4":
        return None

    # nothing has triggered: project from the level the trigger has to clear
    k = b.n - 1
    if path.family == "continuation":
        read: CisdRead | None = path.seen.get("entry_read")
        conservative = _conservative(cfg, path)
        if path.seen.get("setup") is None or conservative or read is None or read.confirmed or read.lower_low is not None:
            return None
        if path.checklist.passed("cont_entry_window_open") is False:
            return None
        entry, low, frame = read.level, read.anchor_low, e.tf
        structural = float(b.high[k])
        what = f"the setup swing {side.lo}"
    else:
        level = path.seen.get("level")
        pending = path.seen.get("pending") or []
        if level is None or not pending or cfg.entry_mode_reversal == "conservative" or path.seen.get("cisd") is not None:
            return None
        x, waiting = min(pending, key=lambda item: item[1].level)
        entry, low, frame = waiting.level, tell.view.f_low, x.tf
        structural = float((b.high[k] + b.low[k]) / 2.0)
        what = f"the reversal {side.lo}"
    stop = low - cfg.stop_buffer
    target = entry + cfg.target_rr * (entry - stop) if cfg.target_mode == "r_multiple" else structural
    note = (
        f"Planned, not triggered: the entry shown is the level a {frame} close has to clear (the real entry is that "
        f"candle's close, so a little further). Stop: {what} {tell.p(low)}. Entry, stop and target all move if price "
        f"makes a new {side.lo} first."
    )
    return build("planned", entry, stop, target, e.n - 1, note)


# --- putting it together ----------------------------------------------------------


def build_plan(
    ctx: Context,
    bias: BiasRead,
    selected: PathOutcome | None,
    read: tuple[ReadStep, ...],
    *,
    decision: str,
    stage: str,
    session_ok: bool,
    session_blocks: bool,
    plan_told: bool,
    forced: Side | None = None,
    reversals_open: dict[str, bool] | None = None,
    entry_blocks: tuple[str, ...] = (),
) -> tuple[tuple[PlanStep, ...], PositionPlan | None]:
    """``(steps, plan)`` for the verdict being returned.

    ``reversals_open`` says, per direction, whether a reversal route can be named there
    (the path was evaluated and its key level is not reached); used when nothing is alive.
    ``plan_told``: at an entry-ready stage that is not a trade, whether the trigger's own
    levels are still worth telling (only the reward / session checks, or the stop swing
    having been taken, stand in the way).
    """
    if selected is None or selected.side is None:
        return _no_route(ctx, read, bias, forced, reversals_open or {}), None
    tell = _Teller(ctx, selected.side)
    blockers = _blockers(selected, ctx, at_entry_ready=stage == "c4")
    if session_blocks and not session_ok:
        blockers["entry"].append("the trigger closed outside the kill zones")
    blockers["entry"].extend(entry_blocks)
    restart: int | None = None
    if selected.family == "continuation":
        drafts, restart = _continuation(ctx, bias, selected, tell)
    else:
        drafts = _reversal(ctx, selected, tell)
    if restart is not None:
        blockers = {role: [phrase for phrase in phrases if "entry window" not in phrase] for role, phrases in blockers.items()}
    steps = _assemble(drafts, blockers, restart)
    return steps, _position(ctx, selected, tell, decision, stage, plan_told)


# --- what to look for -------------------------------------------------------------


def look_options(found: list[_Poi], side: Side, setup_tf: str) -> tuple[LookOption, ...]:
    """Option A, the nearest point of interest, and option B, the first one wholly beyond A
    (one that overlaps A is part of the same pullback, not a next level). Real prices."""
    if not found:
        return ()

    def option(key: str, poi: _Poi, condition: str = "") -> LookOption:
        top, bottom = side.zone(poi.top, poi.bottom)
        return LookOption(key, poi.short, top, bottom, condition)

    a = found[0]
    beyond = min(a.top, a.bottom)
    b = next((poi for poi in found[1:] if max(poi.top, poi.bottom) < beyond), None)
    if b is None:
        return (option("A", a),)
    return option("A", a), option("B", b, f"only after a {setup_tf} close {side.below} the POI")


def build_look_for(ctx: Context, bias: BiasRead, path: PathOutcome | None, steps: tuple[PlanStep, ...]) -> LookFor | None:
    """What to look for while a continuation waits on its setup (display only).

    Shown while no setup closure has happened and a point of interest lies ahead: the
    setup timeframe's C1 into the nearest one (option A), its C2 sweeping C1, and the entry
    while that C2 forms. Option B is the next point of interest beyond A, in play only
    after a setup close through A. Nothing here changes a decision, a check or a level.
    """
    if path is None or path.side is None or path.family != "continuation" or path.trigger is not None:
        return None
    if path.seen.get("setup") is not None:
        return None
    setup_steps = [step for step in steps if step.role == "setup"]
    entry_steps = [step for step in steps if step.role == "entry"]
    if len(setup_steps) != 2 or not entry_steps:
        return None  # not the continuation's pullback, closure and entry: nothing to restate
    level = path.seen.get("level")
    if level is None:
        return None
    tell = _Teller(ctx, path.side)
    side, b, s, e = tell.side, tell.view.B, tell.view.S, tell.view.E
    found = _pois(tell.view, bias, level)
    if not found or not b.n:
        return None
    cfg = ctx.cfg
    options = look_options(found, side, s.tf)
    conservative = _conservative(cfg, path)
    if conservative:
        entry_step = f"After that C2: a {e.tf} turn {tell.up}, a pullback that holds, and a close back {tell.up}"
        entry_words = f"{e.tf} close back {tell.up} after a pullback that holds"
    else:
        entry_step = f"While that C2 forms: a {e.tf} close {side.above} the {side.down_close} run"
        entry_words = f"{e.tf} close {side.above} the run"
    pullback, closure = setup_steps
    statuses = _look_progress(tell, found[0], (pullback.status, closure.status, entry_steps[-1].status))
    look_steps = (
        LookStep(f"{s.tf} C1 pushes into the POI", statuses[0]),
        LookStep(f"{s.tf} C2 sweeps C1's {side.lo}", statuses[1]),
        LookStep(entry_step, statuses[2]),
    )
    structural = float(b.high[b.n - 1])  # the previous bias candle's high: the structural level (rules.md 8.3)
    name = ("PDH" if side.bullish else "PDL") if b.tf == "1D" else f"previous {b.tf} {side.hi}"
    target = f"{cfg.target_rr:g}R, then {name}" if cfg.target_mode == "r_multiple" else name
    return LookFor(
        direction=side.trade,  # type: ignore[arg-type]
        timeframe=s.tf,
        entry_timeframe=e.tf,
        steps=look_steps,
        options=options,
        entry=entry_words,
        stop=f"{side.below} the {s.tf} C2 {side.lo}",
        target=target,
        target_price=side.px(structural),
        entry_during=not conservative,
    )


def _look_progress(tell: _Teller, a: _Poi, statuses: tuple[str, str, str]) -> tuple[str, str, str]:
    """Where the look-for sequence stands, read from the setup candle still forming.

    The steps the rules keep move on closed setup candles only, so on their own they would
    show "C1 next" all through a forming C2. For display only, the closed entry bars inside
    the forming setup candle say more: C1 (the last closed setup candle) or the forming one
    has reached the zone, and the forming one has taken C1's low. Nothing here feeds a
    check or a decision; a blocked step keeps what the rules say.
    """
    if "blocked" in statuses or "done" in statuses[1:]:
        return statuses
    s, e = tell.view.S, tell.view.E
    if not s.n:
        return statuses
    part = e.first_at_or_after(s.closes_at[s.n - 1])
    low_now = float(e.low[part:].min()) if part < e.n else None  # the forming setup candle, from closed entry bars
    c1_low = float(s.low[s.n - 1])
    c1_in = c1_low <= a.near
    swept = low_now is not None and low_now < c1_low
    reached = c1_in or (low_now is not None and low_now <= a.near)
    if swept and reached:
        return "done", "done", "next"  # C2 is forming and has swept C1: its entry is what comes now
    if c1_in:
        return "done", "next", "later"
    return statuses


# --- what to look for: the reversal -----------------------------------------------


def _level_band(ctx: Context, side: Side, level: KeyLevel) -> tuple[float, float] | None:
    """The zone drawn for a key level, mirrored ``(top, bottom)``: a gap is the gap itself; a
    price level is the band the rules count as reaching it (rules.md 7.1, the level plus
    ``reversal_level_tolerance_frac`` of the average bias range, on price's side of it).
    The band's far edge is the last tick that still counts (rounded toward the level), so
    the box never prints a price the market cannot trade. With no tolerance, the wick of
    the bias candle that made the level. None: no height."""
    if level.kind == "fvg":
        return level.edge, level.hold
    tolerance = ctx.cfg.reversal_level_tolerance_frac * (ctx.avg_range or 0.0)
    pair = CONTRACTS.get(root(ctx.symbol))
    tick = pair[0].tick if pair is not None else 0.0
    if tolerance > 0:
        far = level.edge + tolerance
        if tick:
            far = round(math.floor(far / tick + 1e-9) * tick, 10)
        if far > level.edge:
            return far, level.edge
    # no tolerance: price has to trade to the level itself, so the box runs from the level one
    # tick through it (every price in it counts), never a wick the rules do not test against
    return (level.edge, round(level.edge - tick, 10)) if tick else None


def _level_names(tf: str, side: Side, level: KeyLevel) -> tuple[str, str]:
    """A key level on its own ("Previous 1W high") and in a sentence ("the previous 1W high")."""
    if level.kind == "previous_candle":
        return f"Previous {tf} {side.lo}", f"the previous {tf} {side.lo}"
    if level.kind == "swing":
        return f"{tf} swing {side.lo}", f"the {tf} swing {side.lo}"
    return f"{tf} fair value gap", f"the {tf} fair value gap"


def reversal_options(ctx: Context, side: Side, level: KeyLevel, levels: list[KeyLevel], setup_tf: str) -> tuple[LookOption, ...]:
    """Option A, the key level the reversal waits for, and option B, the nearest key level on
    the same side wholly beyond A (one that overlaps A is the same place). Real prices."""
    tf = ctx.stack.bias
    band = _level_band(ctx, side, level)
    if band is None:
        return ()

    def option(key: str, found: KeyLevel, zone: tuple[float, float], condition: str = "") -> LookOption:
        top, bottom = side.zone(*zone)
        return LookOption(key, _level_names(tf, side, found)[0], top, bottom, condition)

    a = option("A", level, band)
    beyond = min(band)
    for other in sorted(levels, key=lambda item: item.edge, reverse=True):
        zone = None if other is level else _level_band(ctx, side, other)
        if zone is not None and max(zone) < beyond:
            return a, option("B", other, zone, "if price trades through A first")
    return (a,)


def _reversal_look(ctx: Context, side: Side, level: KeyLevel, statuses: tuple[str, str, str]) -> LookFor | None:
    """The reversal at ``level`` as a look-for: the bias candle trades into the level, the
    setup's C1 / C2 there closes back, the turn is the entry (rules.md 7, 8)."""
    tell = _Teller(ctx, side)
    view, cfg = tell.view, ctx.cfg
    b, s, e = view.B, view.S, view.E
    if not b.n:
        return None
    levels = key_levels(ctx, side)
    if view.has_forming:
        levels = [item for item in levels if not item.through(view.f_low)]
    options = reversal_options(ctx, side, level, levels, s.tf)
    if not options:
        return None
    if cfg.entry_mode_reversal == "conservative":
        entry_step = f"After the turn: a {e.tf} pullback that holds, then a close back {tell.up}"
        entry_words = f"{e.tf} close back {tell.up} after a pullback that holds"
        stop = f"{side.below} the {e.tf} pullback {side.lo}"  # rules.md 8.2, order-block trigger
    else:
        # the CISD that confirms the wick is read on the setup timeframe, and on the entry
        # timeframe too only for the biases rules.md 4.3 allows it on and only inside its
        # clock window (the engine's own test in reversal.py stage c3)
        if ctx.stack.bias in cfg.reversal_entry_tf_confirm_bias:
            start, end = cfg.reversal_entry_tf_confirm_window
            turn = f"{s.tf} (or {e.tf} from {start} to {end})"
        else:
            turn = s.tf
        entry_step = f"{turn} turns {tell.up}: a close {side.above} the {side.down_close} run, the entry"
        entry_words = f"{turn} close {side.above} the run"
        stop = f"{side.below} the reversal wick {side.lo}"  # rules.md 8.2, CISD trigger
    k = b.n - 1
    eq = float((b.high[k] + b.low[k]) / 2.0)  # S1 of a reversal: the previous bias candle's equilibrium (rules.md 8.3)
    name = "previous day EQ" if b.tf == "1D" else f"previous {b.tf} EQ"
    toward = "down" if side.bullish else "up"
    return LookFor(
        direction=side.trade,  # type: ignore[arg-type]
        timeframe=s.tf,
        entry_timeframe=e.tf,
        steps=(
            LookStep(f"{b.tf} trades {toward} into {_level_names(b.tf, side, level)[1]}", statuses[0]),  # type: ignore[arg-type]
            LookStep(f"{s.tf} C1 / C2 there, closing back {side.above} it", statuses[1]),  # type: ignore[arg-type]
            LookStep(entry_step, statuses[2]),  # type: ignore[arg-type]
        ),
        options=options,
        entry=entry_words,
        stop=stop,
        target=f"{cfg.target_rr:g}R, then {name}" if cfg.target_mode == "r_multiple" else name,
        target_price=side.px(eq),
        entry_during=cfg.entry_mode_reversal != "conservative",
        kind="reversal",
    )


def build_reversal_look_for(
    ctx: Context, path: PathOutcome | None, steps: tuple[PlanStep, ...], position: PositionPlan | None
) -> LookFor | None:
    """What to look for while a reversal that has reached its key level waits on its setup
    (display only). Once the rules can price the turn (a planned or triggered position)
    the plan says it, so there is nothing to look for."""
    if path is None or path.side is None or path.family != "reversal" or path.trigger is not None or position is not None:
        return None
    level = path.seen.get("level")
    bias = [step for step in steps if step.role == "bias"]
    setup = [step for step in steps if step.role == "setup"]
    entry = [step for step in steps if step.role == "entry"]
    if level is None or not (bias and setup and entry):
        return None
    return _reversal_look(ctx, path.side, level, (bias[0].status, setup[0].status, _group_status(entry)))


def _group_status(steps: list[PlanStep]) -> str:
    """One status for the rules' steps one look-for line stands for (the conservative entry
    is a turn and then the entry): next or blocked when any is, done when all are."""
    statuses = [step.status for step in steps]
    for status in (NEXT, BLOCKED):
        if status in statuses:
            return status
    return DONE if all(status == DONE for status in statuses) else LATER


def build_route_look_for(ctx: Context, reversals_open: dict[str, bool], forced: Side | None = None) -> LookFor | None:
    """What to look for while no idea is alive and a reversal waits for price to reach a key
    level (display only): the side whose nearest key level is nearer (``forced``: that side
    only). Its first step is next; nothing after it has started."""
    best: tuple[Side, KeyLevel, float] | None = None
    for side in (forced,) if forced is not None else (BULL, BEAR):
        if not reversals_open.get(side.direction):
            continue
        found = nearest_level(ctx, side)
        if found is None:
            continue
        level, away = found
        if away is None:  # no forming candle yet: how far the last close is from the level
            e = ctx.view(side).E
            if not e.n:
                continue
            away = float(e.close[e.n - 1]) - level.edge
        if best is None or away < best[2]:
            best = (side, level, away)
    if best is None:
        return None
    return _reversal_look(ctx, best[0], best[1], (NEXT, LATER, LATER))
