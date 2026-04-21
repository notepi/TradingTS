from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from .pipeline import run_bootstrap, run_daily_sync, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync citydata Tushare data into SQLite.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # bootstrap 子命令
    bootstrap_parser = subparsers.add_parser("bootstrap", help="Initialize empty database")
    bootstrap_parser.add_argument("--db", dest="db_path", required=True, help="Path to the SQLite mirror file.")

    # pipeline 子命令（完整同步）
    pipeline_parser = subparsers.add_parser("pipeline", help="Full sync pipeline for a single symbol")
    pipeline_parser.add_argument("--db", dest="db_path", required=True, help="Path to the SQLite mirror file.")
    pipeline_parser.add_argument("--symbol", required=True, help="Stock symbol to sync (e.g. 688333.SH)")
    pipeline_parser.add_argument("--start-date", dest="start_date", required=True, help="Start date (YYYY-MM-DD)")
    pipeline_parser.add_argument("--end-date", dest="end_date", required=True, help="End date (YYYY-MM-DD)")
    pipeline_parser.add_argument("--batch-id", dest="batch_id", help="Optional sync batch id.")
    pipeline_parser.add_argument(
        "--indicators",
        nargs="+",
        default=["close_10_ema", "close_50_sma", "close_200_sma", "macd", "rsi"],
        help="Technical indicators to sync",
    )

    # sync_daily 子命令（同步最近一年）
    sync_daily_parser = subparsers.add_parser("sync_daily", help="Sync last 365 days for a single symbol")
    sync_daily_parser.add_argument("--db", dest="db_path", required=True, help="Path to the SQLite mirror file.")
    sync_daily_parser.add_argument("--symbol", required=True, help="Stock symbol to sync (e.g. 688333.SH)")
    sync_daily_parser.add_argument("--batch-id", dest="batch_id", help="Optional sync batch id.")
    sync_daily_parser.add_argument("--curr-date", dest="curr_date", help="Current date (YYYY-MM-DD, defaults to today)")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db_path)

    if args.command == "bootstrap":
        run_bootstrap(db_path)
    elif args.command == "sync_daily":
        curr_date = args.curr_date or datetime.now().strftime("%Y-%m-%d")
        run_daily_sync(
            db_path,
            batch_id=args.batch_id,
            symbol=args.symbol,
            curr_date=curr_date,
        )
    elif args.command == "pipeline":
        run_pipeline(
            db_path,
            batch_id=args.batch_id,
            symbol=args.symbol,
            start_date=args.start_date,
            end_date=args.end_date,
            indicators=args.indicators,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
