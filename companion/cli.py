"""Command line for the companion.

    python -m companion check --symbol NQ --at "2025-11-12 10:45" --stack "1D / 1h / 5m" --style ttrades
    python -m companion check --symbol NQ --at "2025-11-12 10:45" --bias 4h --setup 15m --entry 1m --json
    python -m companion --list-stacks
    python -m companion --list-styles

``--at`` is New York time.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from companion.engine import analyze, render_json, render_text
from companion.styles.base import list_styles
from companion.timeframes import default_stack, get_stack, list_stacks, make_stack
from companion.types import TimeframeStack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="companion", description="Rule-based trading companion.")
    parser.add_argument("command", nargs="?", choices=["check"], help="check: evaluate one moment")
    parser.add_argument("--symbol", help="NQ, ES or GC")
    parser.add_argument("--at", help='moment to evaluate, New York time, e.g. "2025-11-12 10:45"')
    parser.add_argument("--stack", help='name of a configured stack, e.g. "1D / 1h / 5m" (default: the configured default)')
    parser.add_argument("--bias", help="custom stack: bias timeframe")
    parser.add_argument("--setup", help="custom stack: setup timeframe")
    parser.add_argument("--entry", help="custom stack: entry timeframe")
    parser.add_argument("--style", default="ttrades", help="trading style (see --list-styles)")
    parser.add_argument("--side", choices=["auto", "long", "short"], default="auto", help="look only for longs or shorts (default: auto)")
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON")
    parser.add_argument("--list-stacks", action="store_true", help="list the configured stacks and exit")
    parser.add_argument("--list-styles", action="store_true", help="list the available styles and exit")
    return parser


def _resolve_stack(args: argparse.Namespace) -> TimeframeStack:
    custom = [args.bias, args.setup, args.entry]
    if any(custom):
        if not all(custom):
            raise ValueError("A custom stack needs --bias, --setup and --entry together")
        if args.stack:
            raise ValueError("Give either --stack or --bias/--setup/--entry, not both")
        return make_stack(args.bias, args.setup, args.entry)
    return get_stack(args.stack) if args.stack else default_stack()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_stacks or args.list_styles:
        if args.list_stacks:
            default = default_stack().name
            for stack in list_stacks():
                print(f"{stack.name}{'  (default)' if stack.name == default else ''}")
        if args.list_styles:
            for name in list_styles():
                print(name)
        return 0
    if args.command != "check":
        parser.print_help()
        return 2
    if not args.symbol or not args.at:
        parser.error("check needs --symbol and --at")
    try:
        stack = _resolve_stack(args)
        verdict = analyze(args.symbol.upper(), args.at, stack, args.style, direction=args.side)
    except (KeyError, ValueError) as error:
        message = error.args[0] if error.args else str(error)
        print(f"error: {message}", file=sys.stderr)
        return 2
    print(render_json(verdict) if args.json else render_text(verdict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
