"""Live bars from TradingView Desktop for the companion. Read-only.

``TradingViewBarSource`` is a ``companion.bars.BarSource``. It talks to TradingView
through a small ``Bridge`` (``companion.tradingview.bridge.CdpBridge`` for real, a fake in
the tests). ``python -m companion.tradingview.diagnose`` checks the link end to end.
"""

from companion.tradingview.errors import TradingViewError
from companion.tradingview.source import BarsPayload, Bridge, LiveUpdate, TradingViewBarSource

__all__ = ["BarsPayload", "Bridge", "LiveUpdate", "TradingViewBarSource", "TradingViewError"]
