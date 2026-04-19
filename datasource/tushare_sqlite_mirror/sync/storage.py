from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

SYNC_METADATA_COLUMNS = {
    "synced_at": "TEXT",
    "source": "TEXT",
    "batch_id": "TEXT",
}

TABLE_UNIQUE_KEYS = {
    "stock_basic_raw": ["ts_code"],
    "daily_raw": ["ts_code", "trade_date"],
    "daily_basic_raw": ["ts_code", "trade_date"],
    "income_raw": ["ts_code", "end_date", "end_type", "ann_date", "update_flag"],
    "balancesheet_raw": ["ts_code", "end_date", "end_type", "ann_date", "update_flag"],
    "cashflow_raw": ["ts_code", "end_date", "end_type", "ann_date", "update_flag"],
    "fina_indicator_raw": ["ts_code", "end_date", "end_type", "ann_date", "update_flag"],
    "dividend_raw": ["ts_code", "end_date", "ann_date", "div_proc"],
    "stk_rewards_raw": ["ts_code", "ann_date", "name"],
    "market_daily_features": ["ts_code", "trade_date"],
    "financial_period_features": ["ts_code", "end_date", "end_type"],
    "dividend_features": ["ts_code", "end_date"],
    "result_fundamentals_latest": ["ts_code"],
    "result_yoy_growth": ["ts_code", "report_period", "end_type"],
    "result_peg_ratio": ["ts_code", "end_date", "end_type"],
    "result_technical_indicators_daily": ["ts_code", "trade_date"],
}

TABLE_INDEXES = {
    "daily_raw": [["ts_code", "trade_date"]],
    "daily_basic_raw": [["ts_code", "trade_date"]],
    "income_raw": [["ts_code", "end_date", "end_type"], ["ts_code", "ann_date"]],
    "balancesheet_raw": [["ts_code", "end_date", "end_type"], ["ts_code", "ann_date"]],
    "cashflow_raw": [["ts_code", "end_date", "end_type"], ["ts_code", "ann_date"]],
    "fina_indicator_raw": [["ts_code", "end_date", "end_type"], ["ts_code", "ann_date"]],
    "dividend_raw": [["ts_code", "ann_date"]],
    "stock_basic_raw": [["ts_code"]],
    "stk_rewards_raw": [["ts_code", "ann_date"]],
    "market_daily_features": [["ts_code", "trade_date"]],
    "financial_period_features": [["ts_code", "end_date", "end_type"]],
    "dividend_features": [["ts_code", "ann_date"]],
    "result_fundamentals_latest": [["ts_code"]],
    "result_yoy_growth": [["ts_code", "report_period"]],
    "result_peg_ratio": [["ts_code", "end_date"]],
    "result_technical_indicators_daily": [["ts_code", "trade_date"]],
}


def _sqlite_type_for_series(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "REAL"
    return "TEXT"


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def initialize_database(db_path: Path | str) -> None:
    connection = connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                table_name TEXT NOT NULL,
                status TEXT NOT NULL,
                row_count INTEGER NOT NULL DEFAULT 0,
                message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def ensure_table(connection: sqlite3.Connection, table_name: str, frame: pd.DataFrame) -> None:
    columns = {column: _sqlite_type_for_series(frame[column]) for column in frame.columns}
    columns.update(SYNC_METADATA_COLUMNS)

    existing = {
        row[1]: row[2]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    if not existing:
        definitions = ", ".join(f'"{name}" {type_name}' for name, type_name in columns.items())
        connection.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({definitions})')
    else:
        for name, type_name in columns.items():
            if name not in existing:
                connection.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{name}" {type_name}')

    unique_keys = TABLE_UNIQUE_KEYS.get(table_name, [])
    if unique_keys:
        connection.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "ux_{table_name}" '
            f'ON "{table_name}" ({", ".join(unique_keys)})'
        )

    for index_columns in TABLE_INDEXES.get(table_name, []):
        index_name = f'ix_{table_name}_{"_".join(index_columns)}'
        connection.execute(
            f'CREATE INDEX IF NOT EXISTS "{index_name}" '
            f'ON "{table_name}" ({", ".join(index_columns)})'
        )


def upsert_dataframe(
    connection: sqlite3.Connection,
    table_name: str,
    frame: pd.DataFrame,
    *,
    batch_id: str,
    source: str = "citydata",
) -> int:
    if frame.empty:
        return 0

    working = frame.copy()
    working["synced_at"] = pd.Timestamp.utcnow().isoformat()
    working["source"] = source
    working["batch_id"] = batch_id
    ensure_table(connection, table_name, working)

    columns = list(working.columns)
    placeholders = ", ".join(["?"] * len(columns))
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    sql = (
        f'INSERT OR REPLACE INTO "{table_name}" '
        f"({quoted_columns}) "
        f"VALUES ({placeholders})"
    )
    records = [
        tuple(None if pd.isna(value) else value for value in row)
        for row in working.itertuples(index=False, name=None)
    ]
    connection.executemany(sql, records)
    return len(records)


def log_batch(
    connection: sqlite3.Connection,
    *,
    batch_id: str,
    table_name: str,
    status: str,
    row_count: int,
    message: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO sync_batches (batch_id, table_name, status, row_count, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (batch_id, table_name, status, row_count, message),
    )
