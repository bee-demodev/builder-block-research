"""What can go wrong with the live feed, each with a sentence the trader can act on."""

from __future__ import annotations

LAUNCHER = "Start-TradingView-Live.cmd"

# kind -> what the window says. One or two plain sentences each; {detail} is optional extra.
MESSAGES: dict[str, str] = {
    "not_running": (
        "TradingView Desktop is not running. "
        f"Restart the Trading Companion (it starts TradingView with the live-data link), or start it with {LAUNCHER}."
    ),
    "no_debug_port": (
        "TradingView is running, but it was started without the live-data link, so the companion cannot read it. "
        "Restart the Trading Companion and answer Yes when it offers to restart TradingView, "
        f"or close TradingView and start it again with {LAUNCHER}."
    ),
    "loading": "TradingView is still loading the chart{detail}. The companion will try again in a moment.",
    "symbol_not_found": (
        "TradingView does not know the symbol {detail}. "
        "Correct its ticker in companion/config/symbols.json."
    ),
    "no_permission": (
        "TradingView is not sending market data for {detail}. "
        "Your TradingView account may lack the market-data subscription for it; open the symbol in TradingView to check."
    ),
    "unknown_symbol": "{detail}",
    "no_chart_tab": (
        "TradingView is running with the live-data link, but no chart tab is open in it{detail}. "
        "Open any chart in TradingView and leave that tab open: the companion reads market data through it without changing it."
    ),
    "unexpected_bars": "TradingView returned bars the companion cannot place{detail}. Nothing was read from them.",
    "protocol": "The link to TradingView dropped{detail}. The companion will reconnect by itself.",
}

# The feed itself is missing (as opposed to one symbol being wrong): the window offers
# the saved history and keeps retrying quietly.
CONNECTION_KINDS = frozenset({"not_running", "no_debug_port", "protocol", "no_chart_tab"})
# Worth trying again without the trader doing anything.
RETRY_KINDS = frozenset({"not_running", "no_debug_port", "protocol", "loading", "no_chart_tab"})
_NAMED = frozenset({"symbol_not_found", "no_permission", "unknown_symbol"})


class TradingViewError(Exception):
    """A live-feed problem. ``str(error)`` is the plain-language sentence for the window."""

    def __init__(self, kind: str, detail: str = "", technical: str = "") -> None:
        self.kind = kind
        self.detail = detail
        self.technical = technical  # for the diagnostic command and the log, never the window
        template = MESSAGES.get(kind, "TradingView live data is not available{detail}.")
        if kind in _NAMED:
            text = template.format(detail=detail or "this symbol")
        else:
            text = template.format(detail=f" ({detail})" if detail else "")
        super().__init__(text)

    @property
    def is_connection(self) -> bool:
        return self.kind in CONNECTION_KINDS

    @property
    def retry(self) -> bool:
        return self.kind in RETRY_KINDS
