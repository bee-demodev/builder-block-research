"""``python -m companion.core``: the headless companion on a local WebSocket.

    python -m companion.core [--data live|history] [--host 127.0.0.1] [--port 8765] [--watch-ms 500]

``--data`` switches the remembered data choice before starting (the Tk window's Data
drop-down; it is saved). Ctrl+C stops the server, saves the selections and takes the
feed out of TradingView's page.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from companion.app_model import DATA_LABELS, DATA_LIVE, CompanionController, SessionBarSource


def build_parser() -> argparse.ArgumentParser:
    from companion.core.server import DEFAULT_HOST, DEFAULT_PORT, DIST
    from companion.core.loop import WATCH_MS

    parser = argparse.ArgumentParser(prog="python -m companion.core", description="Headless Trading Companion with a local WebSocket.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"loopback address to bind (default {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default {DEFAULT_PORT})")
    parser.add_argument("--data", choices=sorted(DATA_LABELS), help="live (TradingView) or history (saved minute bars); remembered")
    parser.add_argument("--watch-ms", type=int, default=WATCH_MS, help=f"live: how often to look at the forming entry bar (default {WATCH_MS})")
    parser.add_argument("--data-dir", type=Path, help="folder of the saved <symbol>_minute.csv files (default: the repo's data/databento/bars)")
    parser.add_argument("--dist", type=Path, default=DIST, help="built UI to serve at / (default companion/web/dist)")
    parser.add_argument("--allow-origin", action="append", default=[], metavar="URL", help="another origin allowed to open the WebSocket, e.g. http://localhost:5173")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from companion.core.server import is_loopback

    if not is_loopback(args.host):
        print(f"--host must be a loopback address (127.0.0.1, ::1 or localhost), not {args.host}.", file=sys.stderr)
        return 2
    try:
        from aiohttp import web
    except ImportError:
        print("aiohttp is missing: pip install -r companion/requirements.txt", file=sys.stderr)
        return 2
    from companion.core.loop import Core
    from companion.core.server import make_app

    controller = CompanionController(source=SessionBarSource(args.data_dir), default_data=DATA_LIVE)
    if args.data:
        controller.set_data(args.data)
        controller.save()
    core = Core(controller, watch_ms=args.watch_ms)
    app = make_app(core, host=args.host, port=args.port, dist=args.dist, allow_origins=args.allow_origin)
    print(f"Trading Companion core: http://{args.host}:{args.port}/  (WebSocket /ws, data: {controller.state.data}). Ctrl+C stops it.", flush=True)
    web.run_app(app, host=args.host, port=args.port, print=None, handle_signals=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
