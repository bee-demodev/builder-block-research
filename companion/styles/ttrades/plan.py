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

from dataclasses import dataclass

import numpy as np

from companion.contracts import cost_in_r
from companion.styles.ttrades.bias import BiasRead
from companion.styles.ttrades.context import Context, View
from companion.styles.ttrades.continuation import PathOutcome
from companion.styles.ttrades.primitives import BEAR, BULL, CisdRead, Side, candle3_edge
from companion.styles.ttrades.read import _Teller, _blockers, _cap, level_words, money
from companion.styles.ttrades.reversal import nearest_level
from companion.types import PlanStep, PositionPlan, ReadStep

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


def _nearest_poi(view: View, bias: BiasRead, level: float) -> tuple[float, str, float | None] | None:
    """The point of interest a setup candle reaches first from above (rules.md 3.14, stage
    c2): the highest of the untaken setup swing lows, the unfilled gaps above the respect
    level and the bias order block. Returns its near edge, its name and, for the order
    block, the mean threshold a candle that trades into it has to close at or above."""
    s, b, cfg, side = view.S, view.B, view.ctx.cfg, view.side
    if not s.n or not view.has_forming:
        return None
    found: list[tuple[float, str, float | None]] = []
    first = s.first_at_or_after(b.times[b.n - 2]) if b.n >= 2 else 0
    for swing in s.swing_lows:
        if swing.pos + 1 >= s.n or swing.pos < first or float(s.low[swing.pos + 1 :].min()) < swing.price:
            continue
        found.append((swing.price, f"the untaken {s.tf} swing {side.lo}", None))
    for gap in s.gaps:
        if gap.pos + 1 >= s.n or gap.fill_pos is not None or gap.top - gap.bottom < cfg.fvg_min_size or not gap.top > level:
            continue
        found.append((gap.top, f"the unfilled {s.tf} fair value gap", None))
    if bias.order_block is not None:
        found.append((bias.order_block.top, "the bias order block", bias.order_block.mid))
    return max(found, key=lambda item: item[0]) if found else None


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
    conservative = cfg.entry_mode_continuation == "conservative" or cl.passed("bias_c2_not_expanded") is False

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
        conservative = cfg.entry_mode_continuation == "conservative" or path.checklist.passed("bias_c2_not_expanded") is False
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
