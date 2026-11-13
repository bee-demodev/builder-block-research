"""Bias from the last closed bias candle (rules.md section 5).

``read_bias`` classifies ``B[-1]`` against ``B[-2]`` (and ``B[-3]``) into the cases of
rules.md 5.2:

==== ==========================================================================
A    ``B[-1]`` is a Candle 2 closure at a point of interest; forming = Candle 3
B    ``B[-1]`` is a strong Candle 3 after a Candle 2 at ``B[-2]``; forming = Candle 4
C    ``B[-1]`` completes a Candle 3 closure on swing candle ``B[-2]``; forming = Candle 4
D    continuation closure with no point of interest behind it: direction, but late
E    inside bar: neutral
F    outside bar closing inside: neutral
G    closure without a point of interest: neutral
H    A / B / C by closure and POI, but the setup-timeframe CISD has not printed: neutral
I    conflicting reads in the two directions: neutral
N    none of the above (a close exactly on the prior high / low): neutral; not in rules.md
==== ==========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from companion.styles.ttrades.context import Context, View
from companion.styles.ttrades.primitives import (
    BEAR,
    BULL,
    CisdRead,
    PoiHit,
    Side,
    Zone,
    anchored_cisd,
    candle3_edge,
    completes_candle3_closure,
    is_continuation_closure,
    is_inside_bar,
    is_reversal_closure,
    poi_reached,
)


@dataclass(frozen=True)
class BiasRead:
    case: str  # "A".."I", "N", or "none" when there are fewer than three closed bias candles
    side: Side | None  # direction of the closure; None for E, F, I and "none"
    bias: Literal["bullish", "bearish", "neutral"]
    closure: str  # "A" | "B" | "C": what the closure alone says (before POI / CISD)
    swing_pos: int | None  # bias-frame position of the swing candle
    candle_number: int | None  # 3 or 4: which candle of the swing is forming
    poi: PoiHit | None
    cisd: CisdRead | None  # on the setup frame, anchored at the swing candle's low
    cisd_evaluable: bool
    text: str  # what was observed, in real prices

    @property
    def order_block(self) -> Zone | None:
        """The bias order block: the series the bias CISD closed through (rules.md 5.3)."""
        if self.cisd is None or not self.cisd.confirmed:
            return None
        return Zone(self.cisd.level, self.cisd.ob_bottom)


def _closure_candidate(view: View) -> str | None:
    """What ``B[-1]`` is on this side by closure alone: "A", "B", "C" or nothing."""
    b, k = view.B, view.B.n - 1
    edge = view.ctx.cfg.candle3_body_edge
    if is_reversal_closure(b, k):
        return "A"
    previous_was_candle2 = is_reversal_closure(b, k - 1)
    if previous_was_candle2 and is_continuation_closure(b, k):
        return "B"
    if not previous_was_candle2 and completes_candle3_closure(b, k, edge):
        return "C"
    return None


def _closure_text(view: View, closure: str) -> str:
    b, k, side = view.B, view.B.n - 1, view.side
    last, prev = b.at(k), b.at(k - 1)
    if closure == "A":
        return (
            f"{side.direction} reversal closure: {b.tf} candle {last} took the prior candle's {side.lo} "
            f"{b.p(b.low[k - 1])} ({side.lo} {b.p(b.low[k])}) and closed back {side.above} it at {b.p(b.close[k])}"
        )
    if closure == "B":
        return (
            f"{side.direction} strong Candle 3: {b.tf} candle {last} closed at {b.p(b.close[k])}, {side.above} the "
            f"{side.hi} {b.p(b.high[k - 1])} of Candle 2 ({prev}, itself a reversal closure)"
        )
    edge = candle3_edge(b, k - 1, view.ctx.cfg.candle3_body_edge)
    return (
        f"{side.direction} Candle 3 closure: {b.tf} candle {last} held the {side.lo} {b.p(b.low[k - 1])} of {prev} "
        f"({side.lo} {b.p(b.low[k])}) and closed at {b.p(b.close[k])}, {side.above} its body edge {b.p(edge)}"
    )


def _swing_cisd(view: View, swing_pos: int) -> tuple[CisdRead | None, bool]:
    """The setup-timeframe CISD anchored at the swing candle's low (rules.md 5.3).

    The low is searched from the swing candle's open to the close of ``B[-1]``.
    Returns ``(read, evaluable)``; not evaluable when no setup bar lies in that span.
    """
    b, s = view.B, view.S
    start = s.first_at_or_after(b.times[swing_pos])
    end = s.first_at_or_after(b.closes_at[b.n - 1])
    if start >= end:
        return None, False
    anchor = start + int(np.argmin(s.low[start:end]))
    return anchored_cisd(s, anchor, view.ctx.cfg.doji_in_series), True


def read_bias(ctx: Context) -> BiasRead:
    if len(ctx.b) < 3:
        return BiasRead("none", None, "neutral", "", None, None, None, None, False, "fewer than 3 closed bias candles")
    candidates = {side: _closure_candidate(ctx.view(side)) for side in (BULL, BEAR)}
    found = {side: closure for side, closure in candidates.items() if closure is not None}
    b = ctx.bull.B
    k = b.n - 1
    ohlc = (
        f"{b.tf} candle {b.at(k)} O {b.p(b.open[k])} H {b.p(b.high[k])} L {b.p(b.low[k])} C {b.p(b.close[k])} "
        f"against prior H {b.p(b.high[k - 1])} L {b.p(b.low[k - 1])}"
    )
    if len(found) == 2:
        if found[BULL] == "A" and found[BEAR] == "A":
            return BiasRead(
                "F", None, "neutral", "", None, None, None, None, False,
                f"outside bar closing inside the prior range: {ohlc}",
            )
        text = f"conflicting reads ({_closure_text(ctx.bull, found[BULL])}; {_closure_text(ctx.bear, found[BEAR])})"
        return BiasRead("I", None, "neutral", "", None, None, None, None, False, text)
    if not found:
        case = "E" if is_inside_bar(b, k) else "N"
        label = "inside bar" if case == "E" else "no closure pattern (the close sits exactly on the prior high or low)"
        return BiasRead(case, None, "neutral", "", None, None, None, None, False, f"{label}: {ohlc}")

    side, closure = next(iter(found.items()))
    view = ctx.view(side)
    vb = view.B
    swing_pos = k if closure == "A" else k - 1
    candle_number = 3 if closure == "A" else 4
    text = _closure_text(view, closure)
    poi = poi_reached(
        vb,
        float(vb.low[swing_pos]),
        swing_pos,
        min_swing_pos=max(0, swing_pos - ctx.lookback),
        fvg_min_size=ctx.cfg.fvg_min_size,
    )
    if poi is None:
        if closure in ("B", "C") and is_continuation_closure(vb, k):
            return BiasRead("D", side, side.direction, closure, swing_pos, None, None, None, False, text)
        case = "E" if is_inside_bar(vb, k) else "G"
        return BiasRead(case, side, "neutral", closure, swing_pos, candle_number, None, None, False, text)
    cisd, evaluable = _swing_cisd(view, swing_pos)
    if cisd is not None and cisd.confirmed:
        return BiasRead(closure, side, side.direction, closure, swing_pos, candle_number, poi, cisd, True, text)
    return BiasRead("H", side, "neutral", closure, swing_pos, candle_number, poi, cisd, evaluable, text)
