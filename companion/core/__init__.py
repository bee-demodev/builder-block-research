"""The headless companion: the live loop (``Core``), its wire contract and its local server.

    python -m companion.core                  # live from TradingView, http://127.0.0.1:8765
    python -m companion.core --data history   # the saved minute history
"""

from companion.core.loop import Core

__all__ = ["Core"]
