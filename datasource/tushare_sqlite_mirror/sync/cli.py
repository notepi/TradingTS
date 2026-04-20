from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_bootstrap, run_daily_sync, run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync citydata Tushare data into SQLite.")
    parser.add_argument("command", choices=["bootstrap", "sync_daily", "pipeline"])
    parser.add_argument("--db", dest="db_path", required=True, help="Path to the SQLite mirror file.")
    parser.add_argument("--batch-id", dest="batch_id", help="Optional sync batch id.")
    parser.add_argument("--as-of-date", dest="as_of_date", help="As-of date in YYYYMMDD format.")
    parser.add_argument("--ts-code", dest="ts_code", action="append", default=None, help="Stock code to sync (e.g. 688333.SH). Can be specified multiple times.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db_path = Path(args.db_path)
    ts_codes = args.ts_code  # list of codes or None

    if args.command == "bootstrap":
        run_bootstrap(db_path)
    elif args.command == "sync_daily":
        run_daily_sync(db_path, batch_id=args.batch_id, as_of_date=args.as_of_date, ts_codes=ts_codes)
    else:
        run_pipeline(db_path, batch_id=args.batch_id, as_of_date=args.as_of_date, ts_codes=ts_codes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
