"""The TTrades Fractal Model as a ``Style``: checklists in, verdict out (rules.md section 10)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pandas as pd

from companion.bars import BarSource
from companion.styles.ttrades.bias import BiasRead, read_bias
from companion.styles.ttrades.checklist import (
    CONTINUATION, GATE, QUALITY, REVERSAL, SESSION, SHARED, STAGES, STOP_SIZE, Checklist,
)
from companion.styles.ttrades.config import TTradesConfig, load_config
from companion.styles.ttrades.context import Context, at_clock, load_context, trading_day
from companion.styles.ttrades.continuation import PathOutcome, evaluate_continuation
from companion.styles.ttrades.plan import build_look_for, build_plan
from companion.styles.ttrades.primitives import BEAR, BULL, Side, fmt, when
from companion.styles.ttrades.read import build_read
from companion.styles.ttrades.reversal import evaluate_reversal
from companion.styles.ttrades.risk import session_filter
from companion.timeframes import parse_timeframe, to_new_york
from companion.types import (
    CriterionResult,
    Decision,
    LookFor,
    MarkupItem,
    PlanStep,
    PositionPlan,
    ReadStep,
    TimeframeStack,
    TradeSide,
    Verdict,
)

STYLE_NAME = "ttrades"
_REWARD_OR_SESSION = ("cont_reward_at_least_2r", "rev_reward_at_least_2r", "session_filter_ok")
# At an entry-ready stage that is not a trade, the trigger's own levels are still told
# when nothing but these stands in the way: the trigger formed inside its entry window and
# the window has since passed, or its stop has since been taken.
_PLAN_STILL_TOLD = (*_REWARD_OR_SESSION, "stop_size_ok", "cont_entry_window_open", "cont_protected_swing_intact")
# A few words per check, for the label of a drawn trigger the checks hold back (plan A4).
BLOCK_WORDS = {
    "cont_setup_closure_body_aligned": "body against",
    "cont_entry_window_open": "window passed",
    "cont_protected_swing_intact": "stop taken",
    "cont_trigger_clear_of_liquidity": "ran liquidity",
    "cont_trigger_v_shape": "not a V",
    "cont_not_inside_consolidation": "in a range",
    "cont_objective_open_at_trigger": "target already hit",
    "cont_entry_early_in_candle": "late in candle",
    "cont_reward_at_least_2r": "under 2R",
    "rev_expansion_into_level": "no expansion",
    "rev_opposing_run_small": "wick too big",
    "rev_formed_early": "wick too late",
    "rev_cisd_swift": "slow turn",
    "rev_wick_intact": "extreme retaken",
    "rev_reward_at_least_2r": "under 2R",
    "session_filter_ok": "outside kill zone",
    "stop_size_ok": "stop too small",
    "played_out": "played out",
}


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def blocked_words(keys: list[str]) -> str:
    return ", ".join(BLOCK_WORDS.get(key, key.replace("_", " ")) for key in keys)


def _shared(ctx: Context) -> Checklist:
    """``data_sufficient`` and ``stack_pairing_stated`` (rules.md section 6, stage c1)."""
    cfg, stack = ctx.cfg, ctx.stack
    roles = {"stack_pairing_stated": GATE} if cfg.block_unstated_stacks else {}
    cl = Checklist(SHARED, stack, None, roles)
    needed = cfg.bias_bars_needed(stack.bias)
    problems: list[str] = []
    if len(ctx.b) < needed:
        problems.append(f"{len(ctx.b)} closed {stack.bias} bars, need {needed}")
    if len(ctx.b) >= 3:
        if not len(ctx.s) or ctx.s.index[0] > ctx.b.index[-3]:
            first = when(ctx.s.index[0]) if len(ctx.s) else "none"
            problems.append(f"{stack.setup} bars start {first}, need them from {when(ctx.b.index[-3])}")
        if not len(ctx.e) or ctx.e.index[0] > ctx.b.index[-1]:
            first = when(ctx.e.index[0]) if len(ctx.e) else "none"
            problems.append(f"{stack.entry} bars start {first}, need them from {when(ctx.b.index[-1])}")
    if problems:
        cl.set("data_sufficient", False, "; ".join(problems))
    else:
        cl.set(
            "data_sufficient",
            True,
            f"{len(ctx.b)} closed {stack.bias} bars (need {needed}); {len(ctx.s)} {stack.setup} bars from "
            f"{when(ctx.s.index[0])}; {len(ctx.e)} {stack.entry} bars from {when(ctx.e.index[0])}",
        )
    triple = (stack.bias, stack.setup, stack.entry)
    in_table = triple in cfg.stated_stacks
    pairs_ok = (stack.bias, stack.setup) in cfg.stated_pairings and (stack.setup, stack.entry) in cfg.stated_pairings
    if in_table:
        text = f"{' / '.join(triple)} is a stack TTrades states"
    elif pairs_ok:
        text = f"{stack.bias}:{stack.setup} and {stack.setup}:{stack.entry} are both pairings TTrades states"
    else:
        text = f"{' / '.join(triple)} is not a stack or pair of pairings TTrades states; the checklist still runs"
    cl.set("stack_pairing_stated", in_table or pairs_ok, text)
    return cl


def _alive(shared: Checklist, path: PathOutcome) -> bool:
    if not shared.gates_pass() or not path.checklist.gates_pass():
        return False
    return path.family == "continuation" or path.checklist.passed("rev_key_level_reached") is True


def _stage_rank(stage: str) -> int:
    return 0 if stage == "none" else STAGES.index(stage) + 1


def _select(shared: Checklist, cont: PathOutcome, reversal: PathOutcome, cont_allowed: bool = True) -> PathOutcome | None:
    """rules.md 10.1: the path to report. Both alive: the higher stage, continuation on a tie."""
    cont_alive, rev_alive = cont_allowed and _alive(shared, cont), _alive(shared, reversal)
    if cont_alive and rev_alive:
        return cont if _stage_rank(cont.checklist.stage()) >= _stage_rank(reversal.checklist.stage()) else reversal
    if cont_alive:
        return cont
    return reversal if rev_alive else None


def _base_markup(ctx: Context) -> list[MarkupItem]:
    if not len(ctx.b):
        return []
    stack = ctx.stack
    last = ctx.b.iloc[-1]
    start = ctx.b.index[-1]
    high, low = float(last["high"]), float(last["low"])
    eq = (high + low) / 2.0
    daily = stack.bias == "1D"
    hi_name, lo_name = ("PDH", "PDL") if daily else (f"Prev {stack.bias} high", f"Prev {stack.bias} low")
    items = [
        MarkupItem(
            "level", "Previous bias candle high", stack.bias, price=high, start=start, role="reference", short=hi_name,
            shared=True,
        ),
        MarkupItem(
            "level", "Previous bias candle low", stack.bias, price=low, start=start, role="reference", short=lo_name,
            shared=True,
        ),
        MarkupItem(
            "level", "Previous bias candle equilibrium", stack.bias, price=eq, start=start, role="reference",
            short="PD EQ" if daily else "EQ",
        ),
    ]
    if ctx.forming is not None:
        items.append(
            MarkupItem(
                "level", "Forming bias candle open", stack.bias, price=ctx.forming.open, start=ctx.forming.open_time,
                role="info", short="Open",
            )
        )
    return items


def stop_big_enough(risk: float, adr: float, frac: float) -> bool:
    """``risk / adr >= frac``, with room for float error so a stop of exactly that share passes."""
    return risk / adr >= frac - 1e-9


def _session_levels(ctx: Context) -> list[MarkupItem]:
    """Intraday reference levels of the current trading day, as ``session`` markup (plan A6).

    Information only: no rule reads them. A window's high / low is drawn once the window
    has closed. Needs an entry timeframe of 1h or less. Read from ``ctx.sess`` (entry
    bars from the trading day's open) and drawn on the entry chart. A level whose moment is
    not a bar open of the entry timeframe (09:30 on a 1h entry) is left out."""
    e, sess, stack = ctx.e, ctx.sess, ctx.stack
    if not len(e) or parse_timeframe(stack.entry).nominal_minutes > 60:
        return []
    items: list[MarkupItem] = []
    if stack.bias != "1D" and ctx.d is not None and len(ctx.d):  # needs no session bars
        prev, start = ctx.d.iloc[-1], ctx.d.index[-1]
        for word, short, price in (("high", "PDH", float(prev["high"])), ("low", "PDL", float(prev["low"]))):
            items.append(
                MarkupItem("level", f"Previous day {word}", stack.entry, price=price, start=start, role="session", short=short)
            )
    if sess is None or not len(sess):
        return items
    tz = e.index.tz
    day = trading_day(e.index[-1])
    for name, begin, end in (("Asia", -6.0, 0.0), ("London", 2.0, 5.0)):
        start, stop = at_clock(day, tz, begin), at_clock(day, tz, end)
        inside = sess[(sess.index >= start) & (sess.index < stop)]
        if not len(inside) or ctx.as_of < stop:
            continue
        for word, price in (("high", float(inside["high"].max())), ("low", float(inside["low"].min()))):
            items.append(
                MarkupItem(
                    "level", f"{name} session {word}", stack.entry, price=price, start=start, role="session",
                    short=f"{name} {word[0].upper()}",
                )
            )
    for name, hours in (("Midnight open", 0.0), ("09:30 open", 9.5)):
        moment = at_clock(day, tz, hours)
        if moment in sess.index:
            price = float(sess.loc[moment, "open"])
            items.append(MarkupItem("level", name, stack.entry, price=price, start=moment, role="session", short=name))
    return items


class TTradesStyle:
    """Rule-based TTrades Fractal Model. Deterministic; reads only closed bars."""

    name = STYLE_NAME

    def __init__(self, config: TTradesConfig | None = None, config_path: Path | None = None) -> None:
        self.config = config if config is not None else load_config(config_path)

    def evaluate(
        self,
        symbol: str,
        as_of: datetime,
        stack: TimeframeStack,
        source: BarSource,
        direction: TradeSide | None = None,
    ) -> Verdict:
        if direction not in (None, "long", "short"):
            raise ValueError(f"The side to look for must be long or short, not {direction!r}")
        forced: Side | None = None if direction is None else (BULL if direction == "long" else BEAR)
        requested = direction or ""
        cfg = self.config
        moment = to_new_york(as_of)
        ctx = load_context(symbol, moment, stack, source, cfg)
        shared = _shared(ctx)
        session = Checklist((SESSION,), stack, None, {"session_filter_ok": cfg.session_filter_role})
        session_blocks = cfg.session_filter_role == "quality"
        stop_size = Checklist((STOP_SIZE,), stack, None, {"stop_size_ok": cfg.stop_size_role})

        def verdict(
            decision: Decision,
            bias: str,
            family: str,
            stage: str,
            groups: list[Checklist],
            summary: str,
            path: PathOutcome | None = None,
            show_plan: bool = False,
            told: tuple[tuple[ReadStep, ...], str, str] = ((), "", ""),
            planned: tuple[tuple[PlanStep, ...], PositionPlan | None] = ((), None),
            auto_note: str = "",
            look_for: LookFor | None = None,
            blocked: list[str] | None = None,
        ) -> Verdict:
            criteria: list[CriterionResult] = []
            for group in groups:
                criteria.extend(group.results())
            markup = _base_markup(ctx) + _session_levels(ctx)
            invalidation = ""
            entry = stop = None
            targets: tuple[float, ...] = ()
            if path is not None and path.side is not None:
                side = path.side
                if blocked:
                    # say on the chart why a drawn trigger is not a trade (plan A4)
                    markup.extend(
                        replace(item, short=f"{item.short or 'Trigger'} · blocked: {blocked_words(blocked)}")
                        if item.role == "entry" and item.label == "Entry trigger"
                        else item
                        for item in path.markup
                    )
                else:
                    markup.extend(path.markup)
                parts = list(path.invalidation)
                if show_plan and path.plan is not None:
                    plan = path.plan
                    entry, stop = side.px(plan.entry), side.px(plan.stop)
                    targets = tuple(side.px(target) for target in plan.targets)
                    parts.insert(0, f"a trade through the stop {fmt(stop)} ({plan.stop_label})")
                    since = ctx.e.index[path.trigger.pos] if path.trigger is not None else path.trigger_close
                    markup.append(
                        MarkupItem("level", "Entry", stack.entry, price=entry, start=since, role="entry", short="Entry")
                    )
                    markup.append(
                        MarkupItem(
                            "level", "Stop (body stop)" if plan.stop_is_body else "Stop", stack.entry, price=stop,
                            start=since, role="stop", short="Body stop" if plan.stop_is_body else "Stop",
                        )
                    )
                    for number, target in enumerate(targets, start=1):
                        markup.append(
                            MarkupItem(
                                "level", f"Target {number}", stack.entry, price=target, start=since, role="target",
                                short=f"Target {number}",
                            )
                        )
                    if plan.structural != plan.targets:
                        # information only: where the structural levels sit (rules.md 8.3)
                        for number, price in enumerate(plan.structural, start=1):
                            markup.append(
                                MarkupItem(
                                    "level", f"Structural level {number}", stack.bias, price=side.px(price),
                                    start=path.trigger_close, role="info", short=f"Structural {number}",
                                )
                            )
                if parts:
                    invalidation = "Invalid on: " + "; or ".join(parts) + "."
            return Verdict(
                style=self.name,
                symbol=symbol,
                as_of=moment.to_pydatetime(),
                stack=stack,
                decision=decision,
                bias=bias,  # type: ignore[arg-type]
                path_family=family,  # type: ignore[arg-type]
                stage=stage,  # type: ignore[arg-type]
                criteria=tuple(criteria),
                entry=entry,
                stop=stop,
                targets=targets,
                invalidation=invalidation,
                summary=summary,
                markup=tuple(markup),
                read=told[0],
                why=told[1],
                waiting_for=told[2],
                requested=requested,
                idea=path.side.trade if path is not None and path.side is not None else "",
                auto_note=auto_note,
                steps=planned[0],
                plan=planned[1],
                look_for=look_for,
            )

        if shared.passed("data_sufficient") is not True:
            empty = [Checklist(CONTINUATION, stack), Checklist(REVERSAL, stack), session, stop_size]
            for group in empty:
                group.fill("not enough history")
            detail = shared.results()[0].detail
            short_of = (
                ReadStep("bias", stack.bias, "not_applicable", "Not enough history", f"{detail[:1].upper()}{detail[1:]}."),
                ReadStep("setup", stack.setup, "not_applicable", "Not read", ""),
                ReadStep("entry", stack.entry, "not_applicable", "Not read", ""),
            )
            return verdict(
                "no_trade", "neutral", "none", "none", [shared, *empty], f"No trade: not enough history ({detail}).",
                told=(short_of, "There is not enough history to read this stack at this time.", ""),
                planned=((PlanStep("bias", stack.bias, "blocked", "Not enough history", f"{detail[:1].upper()}{detail[1:]}"),), None),
            )

        bias: BiasRead = read_bias(ctx)
        cont = evaluate_continuation(ctx, bias)
        reversals = [evaluate_reversal(ctx, side) for side in (BULL, BEAR)]

        # rules.md 10.1: pick the path. Reversal sides compete first, then against continuation.
        def reversal_key(path: PathOutcome) -> tuple[int, int, int, float]:
            taken = path.checklist.passed("rev_key_level_reached") is True
            assert path.side is not None
            view = ctx.view(path.side)
            recency = view.f_low_time.value if taken and view.has_forming else 0
            return (int(_alive(shared, path)), _stage_rank(path.checklist.stage()), int(taken), float(recency))

        reversal = max(reversals, key=reversal_key)
        if reversal_key(reversal)[:3] == (0, 0, 0) and ctx.forming is not None and len(ctx.b):
            # no key level reached on either side: report the side whose previous-candle extreme is nearer to price
            last = ctx.b.iloc[-1]
            nearer_low = abs(ctx.forming.last - float(last["low"])) <= abs(float(last["high"]) - ctx.forming.last)
            reversal = reversals[0] if nearer_low else reversals[1]

        auto = _select(shared, cont, reversal)
        selected = auto
        auto_note = ""
        if forced is not None:
            # rules.md 10.6: the trader chose the side. Only that side's paths compete: the
            # continuation when the bias closure points that way, and that side's reversal.
            reversal = reversals[0] if forced.bullish else reversals[1]
            selected = _select(shared, cont, reversal, cont_allowed=cont.side is forced)
            if auto is not None and auto.side is not None and auto.side is not forced:
                auto_note = f"Auto reads this as a {auto.side.trade} setup ({auto.family})."

        # rules.md 9.1: judge the session on the trigger bar's close, else on as_of
        if selected is not None and selected.trigger_close is not None:
            ok, text = session_filter(stack.entry, selected.trigger_close, "trigger bar close", cfg)
        else:
            ok, text = session_filter(stack.entry, moment, "no trigger yet; as_of", cfg)
        session.set("session_filter_ok", ok, text)
        # plan A1: the stop against the average daily range, judged on the trigger's own stop
        if selected is not None and selected.trigger is not None and selected.plan is not None:
            risk = selected.plan.entry - selected.plan.stop
            if ctx.adr:
                share = risk / ctx.adr
                big_enough = stop_big_enough(risk, ctx.adr, cfg.min_stop_adr_frac)
                stop_size.set(
                    "stop_size_ok", big_enough,
                    f"stop {fmt(risk)} is {share:.1%} of the {cfg.adr_days}-day average daily range {fmt(ctx.adr)} "
                    f"(at least {cfg.min_stop_adr_frac:.0%} wanted)"
                    + ("" if big_enough else "; costs take a large share of a stop this small"),
                )  # fmt: skip
            else:
                stop_size.set("stop_size_ok", None, f"no {cfg.adr_days}-day average daily range yet")
        else:
            stop_size.set("stop_size_ok", None, "no trigger yet; judged on the trigger's stop once it forms")
        stop_blocks = cfg.stop_size_role == QUALITY and stop_size.passed("stop_size_ok") is False
        groups = [shared, cont.checklist, reversal.checklist, session, stop_size]
        bias_text = f"Bias {bias.bias} (case {bias.case}: {bias.text})."

        # why an entry-ready trigger is held back besides its own checks: told on the entry line and step
        held: list[str] = []
        if stop_blocks:
            held.append(f"the stop is under {cfg.min_stop_adr_frac:.0%} of the daily range, so costs take a large share of it")

        def tell(decision: str, stage: str, extra: tuple[str, ...] = ()) -> tuple[tuple[ReadStep, ...], str, str]:
            return build_read(
                ctx, bias, shared, cont, reversal, selected, decision=decision, stage=stage, session_ok=ok,
                session_blocks=session_blocks, forced=forced, entry_blocks=(*held, *extra),
            )

        def plan_for(
            decision: str, stage: str, told: tuple[tuple[ReadStep, ...], str, str], plan_told: bool = False,
            extra: tuple[str, ...] = (),
        ) -> tuple[tuple[PlanStep, ...], PositionPlan | None]:
            routes: dict[str, bool] = {}
            if shared.gates_pass():  # a reversal route can be named where no key level is reached yet
                routes = {
                    path.side.direction: path.checklist.passed("rev_key_level_reached") is not True
                    for path in reversals
                    if path.side is not None
                }
            return build_plan(
                ctx, bias, selected, told[0], decision=decision, stage=stage, session_ok=ok, session_blocks=session_blocks,
                plan_told=plan_told, forced=forced, reversals_open=routes, entry_blocks=(*held, *extra),
            )

        if selected is None:
            reasons: list[str] = []
            for path in (cont, reversal):
                unknown = [key for key in path.checklist.gate_unknown()]
                failed = [key for key in path.checklist.keys(GATE) if path.checklist.passed(key) is False]
                if failed:
                    reasons.append(f"{path.family} gate failed: {', '.join(failed)}")
                elif unknown:
                    reasons.append(f"{path.family} could not be evaluated: {', '.join(unknown)}")
                elif path.family == "reversal":
                    reasons.append("reversal: price has not reached a key level")
            if shared.keys(GATE) and not shared.gates_pass():
                reasons.insert(0, "shared gate failed")
            told = tell("no_trade", "none")
            lead = f"No {forced.trade} route." if forced is not None else "No trade."
            return verdict(
                "no_trade", bias.bias, "none", "none", groups, f"{lead} {bias_text} {'; '.join(reasons)}.",
                told=told, planned=plan_for("no_trade", "none", told), auto_note=auto_note,
            )

        side = selected.side
        assert side is not None
        checklist = selected.checklist
        stage = checklist.stage()
        failing = (
            checklist.failing_quality()
            + (["session_filter_ok"] if session_blocks and not ok else [])
            + (["stop_size_ok"] if stop_blocks else [])
        )
        head = f"{selected.family} {side.trade} at stage {stage}"
        if stage != "c4":
            next_stage = STAGES[_stage_rank(stage)]
            waiting = [
                spec.key
                for spec in checklist.specs
                if spec.stage == next_stage and checklist.role(spec.key) == "step" and checklist.passed(spec.key) is not True
            ]
            summary = f"Watch: {head}. {bias_text} Waiting for: {', '.join(waiting)}."
            told = tell("watch", stage)
            planned = plan_for("watch", stage, told)
            return verdict(
                "watch", bias.bias, selected.family, stage, groups, summary, selected, told=told,
                planned=planned, auto_note=auto_note, look_for=build_look_for(ctx, bias, selected, planned[0]),
            )
        def played_out(position: PositionPlan | None) -> tuple[str, ...]:
            """rules.md question 33: why a triggered plan whose target or stop has traded is no longer an entry."""
            if position is None or position.state != "triggered" or position.outcome == "open":
                return ()
            what = "reached its target" if position.outcome == "target_reached" else "been stopped"
            return (f"this trigger has already played out (it has {what})",)

        if failing:
            show = all(key in _REWARD_OR_SESSION for key in failing)
            told = tell("watch", stage)
            still_told = all(key in _PLAN_STILL_TOLD for key in failing)
            planned = plan_for("watch", stage, told, still_told)
            blocked, gone = list(failing), played_out(planned[1])
            tail = ""
            if gone:  # the trigger has also played out: say so, and keep the legacy levels for a trade (10.3)
                show, blocked, tail = False, [*failing, "played_out"], f" {_cap(gone[0])}."
                told = tell("watch", stage, gone)
                planned = plan_for("watch", stage, told, still_told, gone)
            summary = f"Watch: {head}, entry-ready structure but quality checks fail: {', '.join(failing)}.{tail} {bias_text}"
            return verdict(
                "watch", bias.bias, selected.family, stage, groups, summary, selected, show_plan=show,
                told=told, planned=planned, auto_note=auto_note, blocked=blocked,
            )
        decision: Decision = "long" if side.bullish else "short"
        plan = selected.plan
        assert plan is not None
        forced = " Conservative entry was forced because the bias Candle 2 expanded." if selected.conservative_forced else ""
        body = " The BODY STOP is in use." if plan.stop_is_body else ""
        fired = "entry CISD" if selected.trigger is not None and selected.trigger.mode == "aggressive" else "continuation order block"
        exit_kind = "exit at" if cfg.target_mode == "r_multiple" else "first target"
        outside = "" if ok else " Outside the kill zones (information only)."
        summary = (
            f"{decision.upper()}: {head}; every quality check passes. Trigger: {fired}. Entry {side.p(plan.entry)}, stop "
            f"{side.p(plan.stop)}, {exit_kind} {side.p(plan.targets[0])} "
            f"({plan.reward / plan.risk:.2f}R).{body}{forced}{outside} {bias_text}"
        )
        told = tell(decision, stage)
        planned = plan_for(decision, stage, told)
        gone = played_out(planned[1])
        if gone:
            # rules.md open question 33: a trade whose target or stop has traded is no longer an entry
            summary = f"Watch: {head}; {gone[0]}. {bias_text}"
            told = tell("watch", stage, gone)
            return verdict(  # the levels stay on the position plan; the legacy fields are for a trade (10.3)
                "watch", bias.bias, selected.family, stage, groups, summary, selected,
                told=told, planned=plan_for("watch", stage, told, True, gone), auto_note=auto_note, blocked=["played_out"],
            )
        return verdict(
            decision, bias.bias, selected.family, stage, groups, summary, selected, show_plan=True,
            told=told, planned=planned, auto_note=auto_note,
        )


def create_style() -> TTradesStyle:
    return TTradesStyle()
