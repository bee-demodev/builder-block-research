"""What a trading style is, and where styles are found.

A style is a package under ``companion/styles/`` that exposes ``create_style()``
returning an object with a ``name`` and an ``evaluate`` method. Adding a style is adding
such a package; nothing here changes.
"""

from __future__ import annotations

import importlib
import pkgutil
from datetime import datetime
from typing import Protocol, runtime_checkable

from companion import paths as _paths
from companion.bars import BarSource
from companion.types import TimeframeStack, TradeSide, Verdict


@runtime_checkable
class Style(Protocol):
    """One rule set that turns closed bars into a verdict."""

    name: str

    def evaluate(
        self,
        symbol: str,
        as_of: datetime,
        stack: TimeframeStack,
        source: BarSource,
        direction: TradeSide | None = None,
    ) -> Verdict:
        """The verdict at ``as_of``, using only what ``source.get_bars(..., as_of, ...)`` returns.

        ``direction`` None: the style proposes the idea itself. "long" / "short": the
        trader chose the side, so only ideas in that direction are selected and described
        (``Verdict.requested``); when the rules give no route to that side the verdict says
        so and names what would open one. Forcing a side changes which idea is told, never
        what a rule passes or fails.
        """
        ...


def list_styles() -> list[str]:
    """Names of the available styles, sorted (what a drop-down shows)."""
    root = _paths.resource("styles")
    return sorted(
        module.name
        for module in pkgutil.iter_modules([str(root)])
        if module.ispkg and not module.name.startswith("_")
    )


def get_style(name: str) -> Style:
    """The style called ``name``; ``KeyError`` when there is none."""
    if name not in list_styles():
        raise KeyError(f"No style named {name!r}; available: {', '.join(list_styles())}")
    module = importlib.import_module(f"{__package__}.{name}")
    style: Style = module.create_style()
    return style
