"""Run reproducible backtests for the current strategy presets.

The script intentionally reuses tradingagents.ranking.strategy_optimizer so the
CLI result matches the Streamlit Factor Engine tab.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_CODES = [
    "600519",
    "000858",
    "300750",
    "002594",
    "600036",
    "601318",
    "000001",
    "600276",
    "603259",
    "600900",
    "601857",
    "600030",
    "000725",
    "000333",
    "600585",
]


def parse_codes(raw: str | None, codes_file: str | None) -> list[str]:
    if codes_file:
        text = Path(codes_file).read_text(encoding="utf-8")
        return [c.strip() for c in text.replace(",", "\n").splitlines() if c.strip()]
    if raw:
        return [c.strip() for c in raw.replace(",", "\n").splitlines() if c.strip()]
    return DEFAULT_CODES


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def flatten_strategy_row(row: dict[str, Any]) -> dict[str, Any]:
    metrics = row["metrics"]
    return {
        "key": row["key"],
        "label": row["label"],
        "total_return": metrics["total_return"],
        "annual_return": metrics["annual_return"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "max_drawdown": metrics["max_drawdown"],
        "win_rate": metrics["win_rate"],
        "avg_turnover": metrics["avg_turnover"],
        "total_trades": metrics["total_trades"],
        "objective_score": metrics["objective_score"],
    }


def print_strategy_table(rows: list[dict[str, Any]]) -> None:
    print(
        "| rank | strategy | total | annual | sharpe | max_dd | win_rate | turnover | objective |"
    )
    print("| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for rank, row in enumerate(rows, start=1):
        print(
            f"| {rank} | {row['key']} ({row['label']}) | "
            f"{percent(row['total_return'])} | {percent(row['annual_return'])} | "
            f"{row['sharpe_ratio']:.2f} | {percent(row['max_drawdown'])} | "
            f"{percent(row['win_rate'])} | {percent(row['avg_turnover'])} | "
            f"{row['objective_score']:.1f} |"
        )


def write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codes", help="Comma or newline separated stock codes.")
    parser.add_argument("--codes-file", help="UTF-8 file with one stock code per line.")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--strategy", action="append", help="Preset key to backtest. Repeatable.")
    parser.add_argument("--top-pct", type=float, default=0.2)
    parser.add_argument("--rebalance-days", type=int, default=10)
    parser.add_argument("--max-positions", type=int, default=10)
    parser.add_argument("--cost-rate", type=float, default=0.0012)
    parser.add_argument("--optimize-base", help="Also optimize weights around this preset key.")
    parser.add_argument("--output-csv", help="Optional CSV output path.")
    args = parser.parse_args()

    from tradingagents.ranking.scoring_engine import ScoringEngine
    from tradingagents.ranking.strategy_optimizer import (
        compare_strategy_presets,
        optimize_strategy_weights,
    )

    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start_date or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    codes = parse_codes(args.codes, args.codes_file)

    result = compare_strategy_presets(
        codes,
        start_date,
        end_date,
        strategy_keys=args.strategy,
        top_pct=args.top_pct,
        rebalance_days=args.rebalance_days,
        max_positions=args.max_positions,
        cost_rate=args.cost_rate,
    )
    rows = [flatten_strategy_row(r) for r in result["ranked"]]

    print(f"Period: {start_date} to {end_date}")
    print(f"Universe requested: {len(codes)}; loaded: {len(result['prepared_meta']['codes'])}")
    print_strategy_table(rows)

    if args.output_csv and rows:
        write_csv(args.output_csv, rows)
        print(f"\nCSV written: {args.output_csv}")

    if args.optimize_base:
        catalog = ScoringEngine.get_strategies()
        if args.optimize_base not in catalog:
            raise SystemExit(f"Unknown strategy key: {args.optimize_base}")
        optimized = optimize_strategy_weights(
            codes,
            start_date,
            end_date,
            base_weights=catalog[args.optimize_base]["weights"],
            top_pct=args.top_pct,
            rebalance_days=args.rebalance_days,
            max_positions=args.max_positions,
            cost_rate=args.cost_rate,
        )
        best = optimized["best"]
        metrics = best["metrics"]
        print(f"\nOptimized from: {args.optimize_base}")
        print(f"Weights: {best['weights']}")
        print(
            "Metrics: "
            f"total={percent(metrics['total_return'])}, "
            f"annual={percent(metrics['annual_return'])}, "
            f"sharpe={metrics['sharpe_ratio']:.2f}, "
            f"max_dd={percent(metrics['max_drawdown'])}, "
            f"win_rate={percent(metrics['win_rate'])}, "
            f"objective={metrics['objective_score']:.1f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
