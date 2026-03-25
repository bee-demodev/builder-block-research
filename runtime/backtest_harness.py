from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime.harness import CostModel, load_bars_csv, load_signals, run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a minimal next-bar historical backtest over OHLC bars and structured trade signals."
    )
    parser.add_argument("--bars", required=True)
    parser.add_argument("--signals", required=True)
    parser.add_argument("--session-mode", default="all")
    parser.add_argument("--tick-size", type=float, default=0.25)
    parser.add_argument("--spread-ticks", type=float, default=1.0)
    parser.add_argument("--slippage-ticks", type=float, default=0.5)
    parser.add_argument("--commission-per-contract", type=float, default=0.0)
    parser.add_argument("--contract-multiplier", type=float, default=1.0)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = run_backtest(
        load_bars_csv(args.bars),
        load_signals(args.signals),
        cost_model=CostModel(
            tick_size=args.tick_size,
            spread_ticks=args.spread_ticks,
            slippage_ticks=args.slippage_ticks,
            commission_per_contract=args.commission_per_contract,
            contract_multiplier=args.contract_multiplier,
        ),
        session_mode=args.session_mode,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()

