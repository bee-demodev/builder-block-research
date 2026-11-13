"""``python -m companion.desktop``, and the packaged app's entry point (``Trading Companion.exe``).

Absolute imports only: PyInstaller runs this file as a plain script."""

import logging
import os

from companion.desktop.app import main

if __name__ == "__main__":
    code = main()
    logging.shutdown()
    # The window is closed and the core stopped (selections saved, TradingView released).
    # A worker still blocked on a slow read must not keep the process, or its port, alive.
    os._exit(code)
