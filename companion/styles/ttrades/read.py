"""The top-down read: what each timeframe of the stack says, in the trader's words.

Presentation only. Nothing here decides anything: it describes what ``bias.py``,
``continuation.py`` and ``reversal.py`` already computed, for the path that is in play.
One ``ReadStep`` per role, bias first, plus one sentence on why and, on a watch, what
has to happen next.

Candle numbers are the trader's (rules.md 3.3: Candle 2 is the swing candle), never the
internal stage codes of rules.md 2.3, and criterion keys never appear in the text. Where
the rules give no candle number (the setup timeframe on the reversal path, a neutral
bias) the text does not offer one.
"""

from __future__ import annotations

from dataclasses import dataclass

from companion.styles.ttrades.bias import BiasRead
from companion.styles.ttrades.checklist import GATE, QUALITY, Checklist
from companion.styles.ttrades.context import Context
from companion.styles.ttrades.continuation import PathOutcome
from companion.styles.ttrades.primitives import Bars, CisdRead, PoiHit, Side
from companion.styles.ttrades.reversal import KeyLevel, nearest_level
from companion.timeframes import candle_label
from companion.types import ReadStatus, ReadStep

CONFIRMED, WAITING, FAILED, NOT_APPLICABLE = "confirmed", "waiting", "failed", "not_applicable"

# Why a quality check blocks, in plain words. {lo} / {hi} are the extremes on the
# trade's stop / target side.
_BLOCKERS = {
    "cont_setup_closure_body_aligned": "the closing candle's body points against the trade",
    "cont_entry_cisd_swift": "the turn was slow, not a quick V",
    "cont_entry_window_open": "the entry window has passed: the setup is beyond its Candle 3, or the Candle 4 it was allowed",
    "cont_protected_swing_intact": "the stop swing has since been taken",
    "cont_trigger_clear_of_liquidity": "the trigger formed while running short-term {hi}s",
    "cont_trigger_v_shape": "the trigger's turn was slow, not a quick V: wait for another continuation",
    "cont_not_inside_consolidation": "price is consolidating: wait for a sweep of the range {lo} or a breakout and a new continuation",
    "cont_objective_open_at_trigger": "the higher-timeframe target was already taken before the trigger",
    "cont_entry_early_in_candle": "the trigger came late in its setup candle: wait for the next one",
    "cont_reward_at_least_2r": "the structural level is closer than the minimum reward",
    "rev_expansion_into_level": "the move into the level was a drift, not a directional run",
    "rev_opposing_run_small": "the wick is not small, so it does not read as a reversal candle",
    "rev_formed_early": "the {lo} formed late in the candle",
    "rev_cisd_swift": "the turn was slow, not a quick V",
    "rev_wick_intact": "the reversal {lo} has been taken again",
    "rev_reward_at_least_2r": "the structural level is closer than the minimum reward",
}


def money(price: float) -> str:
    return f"{price:,.2f}"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


@dataclass
class _Line:
    step: ReadStep
    clause: str  # this line's part of the "why" sentence
    block: str = ""  # what blocks it, when a quality check stands in the way


def _line(role: str, timeframe: str, status: ReadStatus, headline: str, reason: str, clause: str) -> _Line:
    reason = _cap(reason.strip())
    if reason and not reason.endswith("."):
        reason += "."
    return _Line(ReadStep(role, timeframe, status, headline, reason), clause)


class _Teller:
    """Wording helpers for one side of one evaluation."""

    def __init__(self, ctx: Context, side: Side) -> None:
        self.ctx = ctx
        self.side = side
        self.view = ctx.view(side)
        self.up = "up" if side.bullish else "down"
        self.direction = "Bullish" if side.bullish else "Bearish"

    def p(self, mirrored: float) -> str:
        return money(self.side.px(mirrored))

    def zone(self, top: float, bottom: float) -> str:
        real_top, real_bottom = self.side.zone(top, bottom)
        return f"{money(real_bottom)}–{money(real_top)}"

    def candle(self, x: Bars, pos: int) -> str:
        label = candle_label(x.times[pos], x.tf, self.ctx.as_of)
        return f"the {x.tf} candle at {label}" if ":" in label else f"the {label} {x.tf} candle"

    def at(self, x: Bars, pos: int) -> str:
        return candle_label(x.times[pos], x.tf, self.ctx.as_of)

    def hit(self, x: Bars, hit: PoiHit) -> str:
        side = self.side
        if hit.kind == "swing":
            return f"the {x.tf} swing {side.lo} {self.p(hit.top)}"
        if hit.kind == "fvg":
            return f"the {x.tf} fair value gap {self.zone(hit.top, hit.bottom)}"
        return f"the bias order block {self.zone(hit.top, hit.bottom)}"

    def cisd(self, x: Bars, read: CisdRead) -> str:
        """The confirmed close-through, naming the candle, its close and the level."""
        side = self.side
        assert read.confirm is not None
        level = (
            f"the {side.down_close} run's open {self.p(read.level)}"
            if read.series
            else f"the body {self.p(read.level)} of the candle at the {side.lo}"
        )
        return (
            f"{self.candle(x, read.confirm)} closed at {self.p(float(x.close[read.confirm]))}, {side.above} {level} "
            f"(CISD, the change in state of delivery)"
        )


def _blockers(path: PathOutcome, ctx: Context, at_entry_ready: bool) -> dict[str, list[str]]:
    """Quality checks that stand in the way, as phrases, by role. A check that could not
    be measured only blocks once the structure is entry-ready (rules.md 10.3)."""
    stack, side = ctx.stack, path.side
    roles = {stack.bias: "bias", stack.setup: "setup", stack.entry: "entry"}
    found: dict[str, list[str]] = {"bias": [], "setup": [], "entry": []}
    assert side is not None
    for result in path.checklist.results():
        if result.role != QUALITY or result.passed is True:
            continue
        if result.passed is None and not at_entry_ready:
            continue
        phrase = _BLOCKERS.get(result.key, result.label[:1].lower() + result.label[1:] + ": not passed")
        phrase = phrase.format(lo=side.lo, hi=side.hi)
        if result.passed is None:
            phrase += " (could not be measured)"
        found[roles.get(result.timeframe or "", "entry")].append(phrase)
    return found


def _blocked(line: _Line, phrases: list[str], tf: str) -> _Line:
    """The same line, failed, with what blocks it said after what was seen."""
    if not phrases:
        return line
    step = line.step
    said = "; ".join(phrases)
    reason = f"{step.reason.rstrip('.')}. But {said}" if step.reason else said
    headline = step.headline if step.status != CONFIRMED else f"{step.headline} · blocked"
    blocked = _line(step.role, step.timeframe, FAILED, headline, reason, line.clause)
    blocked.block = f"on the {tf} {phrases[0]}"
    return blocked


# --- the bias line (continuation, and no trade) -----------------------------------


def _bias_line(ctx: Context, bias: BiasRead, cont: PathOutcome) -> _Line:
    stack = ctx.stack
    tf = stack.bias
    if bias.case == "none":
        return _line("bias", tf, NOT_APPLICABLE, "Not enough candles", f"fewer than three closed {tf} candles", f"there are fewer than three closed {tf} candles")
    real = ctx.bull.B
    k = real.n - 1
    last = f"the last closed {tf} candle ({candle_label(real.times[k], tf, ctx.as_of)})"
    prior_high, prior_low = money(float(real.high[k - 1])), money(float(real.low[k - 1]))
    no_bias = {
        "E": ("inside candle", f"{last} stayed inside the range {prior_low}–{prior_high} of the candle before it"),
        "F": ("outside candle", f"{last} took both the high {prior_high} and the low {prior_low} of the candle before it and closed back inside"),
        "I": ("conflicting closes", f"{last} reads bullish and bearish at once against the candles before it"),
        "N": ("no closure pattern", f"{last} closed at {money(float(real.close[k]))}, exactly on the high or low of the candle before it"),
    }
    if bias.case in no_bias or bias.side is None:
        name, reason = no_bias.get(bias.case, ("no direction", f"{last} closed without a direction"))
        return _line("bias", tf, FAILED, f"No bias · {name}", _cap(reason), f"the {tf} gives no bias ({name})")

    tell = _Teller(ctx, bias.side)
    side, b, s = tell.side, tell.view.B, tell.view.S
    if bias.closure == "A":
        closure = (
            f"{last} took the {side.lo} {tell.p(b.low[k - 1])} of the candle before it and closed back {side.above} it at "
            f"{tell.p(b.close[k])} (Candle 2 closure)"
        )
    elif bias.closure == "B":
        closure = (
            f"{last} closed at {tell.p(b.close[k])}, {side.above} Candle 2's {side.hi} {tell.p(b.high[k - 1])} "
            f"(a strong Candle 3)"
        )
    else:
        closure = (
            f"{last} held Candle 2's {side.lo} {tell.p(b.low[k - 1])} and closed at {tell.p(b.close[k])}, "
            f"{side.above} its body (Candle 3 closure)"
        )
    lower = side.direction
    if bias.case == "G":
        return _line(
            "bias", tf, FAILED, "No bias · no point of interest",
            f"{_cap(closure)}, but that swing formed at no point of interest",
            f"the {tf} closed {lower} but not from a point of interest",
        )
    if bias.case == "D":
        return _line(
            "bias", tf, FAILED, f"{tell.direction} but late · no swing to trade from",
            f"{_cap(last)} closed at {tell.p(b.close[k])}, {side.above} the {side.hi} {tell.p(b.high[k - 1])} of the candle "
            f"before it, but the swing behind the move formed at no point of interest: this is Candle 5 or later, or "
            f"there is no swing to count from",
            f"the {tf} is {lower} but late (Candle 5 or later, or no swing at a point of interest)",
        )
    cl = cont.checklist
    number = bias.candle_number
    swing_price = tell.p(float(b.low[bias.swing_pos])) if bias.swing_pos is not None else "?"
    if cl.passed("bias_poi_present") is None:
        return _line(
            "bias", tf, NOT_APPLICABLE, f"{tell.direction} close · cannot be placed",
            f"{_cap(closure)}, but there is too little {tf} history before the swing to look for a point of interest",
            f"the {tf} bias could not be read (too little history)",
        )
    if cl.passed("bias_swing_intact") is False:
        return _line(
            "bias", tf, FAILED, f"{tell.direction} swing broken",
            f"{_cap(closure)}, but price has since traded {side.below} the swing {side.lo} {swing_price}",
            f"the {tf} swing {side.lo} {swing_price} has been broken",
        )
    if cl.role("cont_objective_open") == GATE and cl.passed("cont_objective_open") is False:
        taken = tell.p(float(b.high[k]))
        return _line(
            "bias", tf, FAILED, f"{tell.direction} · objective already taken",
            f"{_cap(closure)}, but the previous candle's {side.hi} {taken} has already been taken",
            f"the previous {tf} {side.hi} {taken} has already been taken",
        )
    if bias.cisd is None or not bias.cisd.confirmed:
        need = (
            f"no {s.tf} close {side.above} {tell.p(bias.cisd.level)} yet"
            if bias.cisd is not None and bias.cisd.lower_low is None
            else f"the {s.tf} has not confirmed the swing"
        )
        return _line(
            "bias", tf, WAITING, f"{tell.direction} close · not confirmed",
            f"{_cap(closure)}; {need}",
            f"the {tf} closed {lower} but the {s.tf} has not confirmed the swing",
        )
    return _line(
        "bias", tf, CONFIRMED, f"{tell.direction} · Candle {number} forming",
        f"{_cap(closure)}; the {s.tf} confirmed the swing {side.lo} {swing_price}",
        f"{tf} bias is {lower} (Candle {number} forming)",
    )


# --- continuation -----------------------------------------------------------------


def _level_name(cont: PathOutcome, tell: _Teller) -> str:
    level, eq = cont.seen["level"], cont.seen["eq"]
    what = "wick midpoint" if abs(level - eq) > 1e-9 else "equilibrium"
    return f"the previous {tell.view.B.tf} candle's {what} {tell.p(level)}"


def _continuation_setup(ctx: Context, cont: PathOutcome, tell: _Teller) -> tuple[_Line, str]:
    """The setup line and what the setup timeframe is still waiting for ("" when nothing)."""
    side, b, s = tell.side, tell.view.B, tell.view.S
    seen = cont.seen
    level = _level_name(cont, tell)
    setup, tag = seen.get("setup"), seen.get("tag")
    if setup is None and tag is None:
        return _line(
            "setup", s.tf, WAITING, "No pullback yet",
            f"No {s.tf} candle of the forming {b.tf} candle has reached a point of interest; closes are respecting {level}",
            f"the {s.tf} has not pulled back into a point of interest yet",
        ), (
            f"a {s.tf} pullback into a point of interest (an untaken swing {side.lo}, an unfilled {side.direction} "
            f"gap or the bias order block) that respects {level}"
        )
    if setup is None:
        pos, hit = tag
        return _line(
            "setup", s.tf, WAITING, "At a point of interest · no closure yet",
            f"{_cap(tell.candle(s, pos))} reached {tell.hit(s, hit)} ({side.lo} {tell.p(float(s.low[pos]))}), but no "
            f"Candle 2 or Candle 3 closure stands there yet",
            f"the {s.tf} is at a point of interest without a close back {tell.up} yet",
        ), f"a {s.tf} candle to close back {tell.up} there (a Candle 2 or Candle 3 closure) while respecting {level}"
    sw, closing = setup.swing, setup.closing
    number = 3 + (s.n - 1 - sw)
    headline = f"Candle {number} forming" if number <= 4 else f"Candle {number} forming · past Candle 4"
    if setup.kind == "c2":
        reason = (
            f"{_cap(tell.candle(s, sw))} dipped to {tell.p(setup.low)} at {tell.hit(s, setup.hit)} and closed back "
            f"{side.above} the {side.lo} of the candle before it, at {tell.p(float(s.close[sw]))} (Candle 2 closure)"
        )
    else:
        reason = (
            f"{_cap(tell.candle(s, closing))} held the {side.lo} {tell.p(setup.low)} made at {tell.at(s, sw)} "
            f"({tell.hit(s, setup.hit)}) and closed at {tell.p(float(s.close[closing]))}, {side.above} that candle's "
            f"body (Candle 3 closure)"
        )
    if side.bullish is False:
        reason = reason.replace("dipped to", "rallied to")
    return _line(
        "setup", s.tf, CONFIRMED, headline, reason,
        f"the {s.tf} pulled back to a point of interest, respected {level} and closed back {tell.up}",
    ), ""


def _order_block_entry(tell: _Teller, path: PathOutcome) -> str:
    side, e = tell.side, tell.view.E
    trigger = path.trigger
    assert trigger is not None and trigger.read is not None
    return (
        f"After the turn price pulled back to {tell.p(trigger.wick_stop)} and {tell.candle(e, trigger.pos)} closed at "
        f"{tell.p(trigger.entry)}, {side.above} {tell.p(trigger.read.level)} (continuation order block)"
    )


def _continuation_entry(ctx: Context, cont: PathOutcome, tell: _Teller) -> tuple[_Line, str]:
    side, s, e = tell.side, tell.view.S, tell.view.E
    seen = cont.seen
    setup = seen.get("setup")
    read: CisdRead | None = seen.get("entry_read")
    trigger = cont.trigger
    if setup is None:
        return _line(
            "entry", e.tf, WAITING, f"Waiting for the {s.tf}",
            f"Nothing to confirm on the {e.tf} until the {s.tf} closes back {tell.up} at a point of interest",
            f"the {e.tf} has nothing to confirm yet",
        ), ""
    if read is None:
        return _line(
            "entry", e.tf, WAITING, "No turn yet", f"No closed {e.tf} candle inside the {s.tf} swing candle to read",
            f"the {e.tf} has not turned yet",
        ), f"{e.tf} candles to close inside the setup"
    if not read.confirmed:
        last = tell.p(float(e.close[e.n - 1]))
        if read.lower_low is not None:
            reason = (
                f"Price traded {side.below} the {side.lo} {tell.p(read.anchor_low)} before any {e.tf} close "
                f"{side.above} {tell.p(read.level)}"
            )
        else:
            reason = (
                f"Needs a {e.tf} close {side.above} {tell.p(read.level)}, the open of the {side.down_close} run into "
                f"the {side.lo} {tell.p(read.anchor_low)} (CISD); the last close is {last}"
            )
        return _line("entry", e.tf, WAITING, "No turn yet", reason, f"the {e.tf} has not turned yet"), (
            f"a {e.tf} close {side.above} {tell.p(read.level)} (the change in state of delivery)"
        )
    turned = _cap(tell.cisd(e, read))
    pullback = (
        f"a {e.tf} pullback that holds {tell.p(read.anchor_low)}, reaches a point of interest and closes back "
        f"{tell.up} (a continuation order block)"
    )
    if trigger is None:
        why = "the entry it gives is outside the entry window"
        if cont.checklist.passed("cont_entry_window_open") is not False:
            why = (
                "the bias Candle 2 expanded, so only a continuation order block may be entered"
                if cont.conservative_forced
                else "the entry needs a continuation order block"
            )
        return _line(
            "entry", e.tf, WAITING, "Turned · no entry yet", f"{turned}, but {why}",
            f"no entry has formed on the {e.tf} since it turned",
        ), pullback
    if trigger.mode == "aggressive":
        reason = turned
        if trigger.pos != read.confirm:
            reason += (
                f"; the entry is the {tell.at(e, trigger.pos)} close {tell.p(trigger.entry)}, once the {s.tf} "
                f"closure candle had closed"
            )
        headline = "Confirmed · CISD"
    else:
        reason = _order_block_entry(tell, cont)
        headline = "Confirmed · continuation order block"
    return _line("entry", e.tf, CONFIRMED, headline, reason, f"the {e.tf} confirmed the turn"), ""


# --- reversal ---------------------------------------------------------------------


def _key_level(tell: _Teller, path: PathOutcome) -> str:
    return level_words(tell, path.seen["level"])


def level_words(tell: _Teller, level: KeyLevel) -> str:
    """A reversal key level in the trader's words, with its price."""
    side, b = tell.side, tell.view.B
    if level.kind == "previous_candle":
        return f"the previous {b.tf} candle's {side.lo} {tell.p(level.edge)}"
    if level.kind == "swing":
        return f"the untaken {b.tf} swing {side.lo} {tell.p(level.edge)}"
    return f"the unfilled {b.tf} fair value gap {tell.zone(level.edge, level.hold)}"


def _reversal_lines(ctx: Context, bias: BiasRead, path: PathOutcome, tell: _Teller, stage: str) -> tuple[list[_Line], str]:
    side, b, s, e = tell.side, tell.view.B, tell.view.S, tell.view.E
    seen = path.seen
    level = seen["level"]
    low = seen["low"]
    name = _key_level(tell, path)
    verb = ("traded into" if level.kind == "fvg" else f"traded {side.below}") if level.through(low) else "came close to"
    made = candle_label(seen["low_time"], e.tf, ctx.as_of)
    reason = f"The forming {b.tf} candle {verb} {name}; its {side.lo} so far is {tell.p(low)}, made at {made}"
    if bias.bias in ("bullish", "bearish") and bias.bias != side.direction:
        reason += f". The last closed {b.tf} candle still reads {bias.bias}, so this may be a retracement"
    bias_line = _line(
        "bias", b.tf, CONFIRMED, f"{tell.direction} reversal · Candle 2 forming", reason,
        f"the forming {b.tf} candle {'turned' if stage == 'c4' else 'is'} at a key level ({name})",
    )

    hold = tell.p(level.hold)
    if level.kind == "fvg":
        hold = f"the gap's far edge {hold}"
    reclaim = seen.get("reclaim")
    chosen: tuple[Bars, CisdRead] | None = seen.get("cisd")
    pending: list[tuple[Bars, CisdRead]] = seen.get("pending") or []
    waiting: list[str] = []
    if reclaim is None:
        setup_line = _line(
            "setup", s.tf, WAITING, f"Not back {side.above} the level",
            f"No {s.tf} candle has closed back {side.above} {hold} since the {side.lo} {tell.p(low)}",
            f"the {s.tf} has not closed back {side.above} it yet",
        )
        waiting.append(f"a {s.tf} close back {side.above} {hold}")
    else:
        if level.through(low):
            reason = f"{_cap(tell.candle(s, reclaim))} closed at {tell.p(float(s.close[reclaim]))}, back {side.above} {hold}"
            headline = f"Closed back {side.above} the level"
        else:  # only approached: any close after the extreme is on the trade's side of it
            reason = (
                f"{_cap(tell.candle(s, reclaim))} closed at {tell.p(float(s.close[reclaim]))} after the {side.lo}; the "
                f"level {hold} was approached, not traded through"
            )
            headline = f"Closed {side.above} the level"
        if chosen is not None and chosen[0] is s:
            reason += f"; {tell.cisd(s, chosen[1])}"
            headline = "Turned · CISD"
        closed = "closed back" if level.through(low) else "closed"
        setup_line = _line("setup", s.tf, CONFIRMED, headline, reason, f"the {s.tf} {closed} {side.above} it")

    trigger = path.trigger
    pullback = (
        f"a {e.tf} pullback that holds the {side.lo} {tell.p(low)} and closes back {tell.up} (a continuation order block)"
    )
    if chosen is None:
        if pending:
            needs = " or ".join(f"a {x.tf} close {side.above} {tell.p(read.level)}" for x, read in pending)
            reason = f"Needs {needs}: a close through the {side.down_close} run into the {side.lo}"
            waiting.append(f"{needs} (the change in state of delivery)")
        else:
            reason = f"The candle holding the {side.lo} has not closed, so there is no {side.down_close} run to close through yet"
            waiting.append(f"a close through the {side.down_close} run into the {side.lo} (the change in state of delivery)")
        entry_line = _line("entry", e.tf, WAITING, "No turn yet", reason, "there is no change in state of delivery yet")
    else:
        x, read = chosen
        turned = _cap(tell.cisd(x, read))
        if trigger is None:
            entry_line = _line(
                "entry", e.tf, WAITING, "Turned · no entry yet", f"{turned}, but the entry needs a continuation order block",
                f"no entry has formed since the {x.tf} turned",
            )
            waiting.append(pullback)
        else:
            if trigger.mode == "aggressive":
                reason = turned
                if x is not e:
                    reason = (
                        f"The {x.tf} turn is the trigger: the entry is the {tell.at(e, trigger.pos)} {e.tf} close "
                        f"{tell.p(trigger.entry)}, when that {x.tf} candle closed"
                    )
                headline = "Confirmed · CISD"
            else:
                reason, headline = _order_block_entry(tell, path), "Confirmed · continuation order block"
            if stage == "c4":
                entry_line = _line("entry", e.tf, CONFIRMED, headline, reason, f"the {e.tf} confirmed the turn")
            else:
                entry_line = _line(
                    "entry", e.tf, WAITING, f"Turned · waiting for the {s.tf}", reason,
                    f"the {e.tf} turned",
                )
    return [bias_line, setup_line, entry_line], " and ".join(waiting[:2])


def route_words(ctx: Context, side: Side) -> str:
    """What would open a reversal to ``side`` while no key level is reached, as a clause."""
    tell = _Teller(ctx, side)
    b = tell.view.B
    found = nearest_level(ctx, side)
    if found is None:
        return f"the rules give no key level on the {side.lo} side to turn from right now"
    level, away = found
    name = level_words(tell, level)
    if away is None:
        return f"the new {b.tf} candle first has to reach a key level; the nearest is {name}"
    return (
        f"the forming {b.tf} candle first has to reach a key level; the nearest is {name}, {money(away)} {side.below} "
        f"its {side.lo} so far {tell.p(tell.view.f_low)}"
    )


# --- putting it together ----------------------------------------------------------


def _why(decision: str, lines: list[_Line], tail: str = "") -> str:
    clauses = [line.clause for line in lines]
    if decision in ("long", "short"):
        text = f"{clauses[0]}, {clauses[1]}, and {clauses[2]}" if len(clauses) == 3 else ", ".join(clauses)
    else:
        good: list[str] = []
        text = ""
        for line in lines:
            if line.step.status == CONFIRMED:
                good.append(line.clause)
                continue
            if line.block:
                text = f"{', '.join([*good, line.clause])}, but {line.block}"
            else:
                text = f"{', '.join(good)}, but {line.clause}" if good else line.clause
            break
        else:
            text = ", ".join(good)
    return f"{_cap(text)}.{tail}"


def build_read(
    ctx: Context,
    bias: BiasRead,
    shared: Checklist,
    cont: PathOutcome,
    reversal: PathOutcome,
    selected: PathOutcome | None,
    *,
    decision: str,
    stage: str,
    session_ok: bool,
    session_blocks: bool,
    session_text: str = "",
    forced: Side | None = None,
    entry_blocks: tuple[str, ...] = (),
) -> tuple[tuple[ReadStep, ...], str, str]:
    """``(read, why, waiting_for)`` for the verdict being returned.

    ``forced`` is the side the trader asked for (rules.md 10.6); it only matters when no
    path to that side is alive, where the read then says what would open one.
    """
    stack = ctx.stack

    if selected is None:
        bias_line = _bias_line(ctx, bias, cont)
        blocked_stack = bool(shared.keys(GATE)) and not shared.gates_pass()
        if blocked_stack:
            bias_line = _line(
                "bias", stack.bias, NOT_APPLICABLE, "Stack not allowed",
                "This stack is not one TTrades teaches, and the settings block such stacks",
                "this stack is blocked by the settings",
            )
        elif forced is not None and bias.side is not forced:
            # the bias timeframe does not point the trader's way: the only route is a reversal
            directional = bias.bias in ("bullish", "bearish")
            lead = f"the {stack.bias} is {bias.bias}" if directional else f"the {stack.bias} gives no {forced.direction} bias"
            reason = f"{lead}, so a {forced.trade} here is a reversal: {route_words(ctx, forced)}"
            head = bias.bias.capitalize() if directional else "No bias"
            lines = [
                _line("bias", stack.bias, WAITING, f"{head} · a {forced.trade} needs a reversal", reason, reason),
                _line("setup", stack.setup, NOT_APPLICABLE, "Not read", f"The {stack.setup} is read once price is at a key level", ""),
                _line("entry", stack.entry, NOT_APPLICABLE, "No entry to look for", f"The {stack.entry} is read once price is at a key level", ""),
            ]
            return tuple(line.step for line in lines), f"{_cap(reason)}.", ""
        tell = _Teller(ctx, bias.side) if bias.side is not None else None
        usable = bias_line.step.status in (CONFIRMED, WAITING) and tell is not None
        if not usable or tell is None:
            setup_line = _line(
                "setup", stack.setup, NOT_APPLICABLE, "Not read", f"No {stack.setup} read without a {stack.bias} bias", ""
            )
        else:
            side, s = tell.side, tell.view.S
            level = _level_name(cont, tell)
            respected = cont.checklist.passed("cont_eq_respected")
            if respected is False:
                first = cont.seen["eq_break"]
                setup_line = _line(
                    "setup", s.tf, FAILED, f"Lost the {'upper' if side.bullish else 'lower'} half",
                    f"{_cap(tell.candle(s, first))} closed at {tell.p(float(s.close[first]))}, {side.below} {level}",
                    f"the {s.tf} closed {side.below} {level}",
                )
            elif respected is None:
                setup_line = _line(
                    "setup", s.tf, NOT_APPLICABLE, f"No closed {s.tf} candle yet",
                    f"The forming {stack.bias} candle has no closed {s.tf} candle yet, so {level} cannot be judged",
                    f"the forming {stack.bias} candle has no closed {s.tf} candle to judge yet",
                )
            else:  # every gate passes yet nothing is alive: only a shared gate can do that
                setup_line = _line("setup", s.tf, NOT_APPLICABLE, "Not read", "", "")
        entry_line = _line(
            "entry", stack.entry, NOT_APPLICABLE, "No entry to look for",
            f"The {stack.entry} is only read once the higher timeframes line up", "",
        )
        lines = [bias_line, setup_line, entry_line]
        culprit = next((line for line in lines if line.step.status not in (CONFIRMED, WAITING) and line.clause), bias_line)
        good = [line.clause for line in lines[: lines.index(culprit)] if line.step.status == CONFIRMED]
        text = f"{', '.join(good)}, but {culprit.clause}" if good else culprit.clause
        reached = reversal.checklist.passed("rev_key_level_reached")
        tail = " Price is not at a key level for a reversal either." if reached is False else ""
        if forced is not None and not blocked_stack and reached is not True:
            tail = f" A {forced.trade} reversal is not open either: {route_words(ctx, forced)}."
        return tuple(line.step for line in lines), f"{_cap(text)}.{tail}", ""

    side = selected.side
    assert side is not None
    tell = _Teller(ctx, side)
    blockers = _blockers(selected, ctx, at_entry_ready=stage == "c4")
    if session_blocks and not session_ok:
        blockers["entry"].append("the trigger closed outside the kill zones")
    blockers["entry"].extend(entry_blocks)  # held back by the style itself: stop size, played out

    if selected.family == "continuation":
        bias_line = _bias_line(ctx, bias, selected)
        setup_line, setup_wait = _continuation_setup(ctx, selected, tell)
        entry_line, entry_wait = _continuation_entry(ctx, selected, tell)
        if bias_line.step.status != CONFIRMED:
            cisd = bias.cisd
            s_tf = stack.setup
            waiting = (
                f"a {s_tf} close {side.above} {tell.p(cisd.level)} to confirm the {stack.bias} swing"
                if cisd is not None and cisd.lower_low is None and not cisd.confirmed
                else f"the {s_tf} to confirm the {stack.bias} swing"
            )
        else:
            waiting = setup_wait or entry_wait
        lines = [bias_line, setup_line, entry_line]
    else:
        lines, waiting = _reversal_lines(ctx, bias, selected, tell, stage)

    labels = {"bias": stack.bias, "setup": stack.setup, "entry": stack.entry}
    lines = [_blocked(line, blockers[line.step.role], labels[line.step.role]) for line in lines]
    every = [phrase for role in ("bias", "setup", "entry") for phrase in blockers[role]]

    tail = ""
    if decision in ("long", "short") and not session_ok:
        tail = " The trigger closed outside the kill zones (information only)."
    if decision in ("long", "short") and selected.conservative_forced:
        tail += " The bias Candle 2 expanded, so the entry had to be a continuation order block."
    why = _why(decision, lines, tail)

    waiting_for = ""
    if decision == "watch":
        if stage == "c4":
            waiting_for = f"a fresh setup. This one is complete but blocked: {'; '.join(every)}"
        else:
            waiting_for = waiting
            if every:
                waiting_for += f". As it stands a trade would still be blocked: {'; '.join(every)}"
        waiting_for = _cap(waiting_for.strip()) + "." if waiting_for.strip() else ""
    return tuple(line.step for line in lines), why, waiting_for
