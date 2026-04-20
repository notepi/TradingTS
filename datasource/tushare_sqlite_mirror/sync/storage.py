"""
sync/storage.py - SQLite 存储层

新表结构：直接存格式化数据，每个函数对应一个表
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

# 表结构定义：函数名 -> 表名
FUNCTION_TABLE_MAP = {
    "get_stock_data": "stock_data",
    "get_indicators": "indicators",
    "get_fundamentals": "fundamentals",
    "get_balance_sheet": "balance_sheet",
    "get_cashflow": "cashflow",
    "get_income_statement": "income_statement",
    "get_peg_ratio": "peg_ratio",
    "get_yoy_growth": "yoy_growth",
    "get_insider_transactions": "insider_transactions",
}

# 每个表的唯一键（用于 upsert）
TABLE_UNIQUE_KEYS = {
    "stock_data": ["ts_code", "Date"],
    "indicators": ["ts_code", "indicator", "Date"],
    "fundamentals": ["ts_code", "Date"],  # 每日估值历史
    "balance_sheet": ["ts_code", "end_date", "end_type"],
    "cashflow": ["ts_code", "end_date", "end_type"],
    "income_statement": ["ts_code", "end_date", "end_type"],
    "peg_ratio": ["ts_code", "end_date", "end_type"],
    "yoy_growth": ["ts_code", "end_date", "end_type"],
    "insider_transactions": ["ts_code", "ann_date", "name"],
}

# 元数据列（自动添加到所有表）
SYNC_METADATA_COLUMNS = {
    "synced_at": "TEXT",
    "source": "TEXT",
    "batch_id": "TEXT",
}


def connect(db_path: Path | str) -> sqlite3.Connection:
    """连接数据库"""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def initialize_database(db_path: Path | str) -> None:
    """初始化数据库（创建 sync_batches 表）"""
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


def _sqlite_type_for_series(series: pd.Series) -> str:
    """推断 SQLite 类型"""
    if pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "REAL"
    return "TEXT"


def ensure_table(connection: sqlite3.Connection, table_name: str, frame: pd.DataFrame) -> None:
    """确保表存在，动态创建列"""
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

    # 创建唯一索引
    unique_keys = TABLE_UNIQUE_KEYS.get(table_name, [])
    if unique_keys:
        connection.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "ux_{table_name}" '
            f'ON "{table_name}" ({", ".join(unique_keys)})'
        )

    # 创建查询索引
    if table_name in {"stock_data", "indicators"}:
        connection.execute(
            f'CREATE INDEX IF NOT EXISTS "ix_{table_name}_date" '
            f'ON "{table_name}" ("ts_code", "Date")'
        )
    elif table_name in {"balance_sheet", "cashflow", "income_statement", "peg_ratio", "yoy_growth"}:
        connection.execute(
            f'CREATE INDEX IF NOT EXISTS "ix_{table_name}_end_date" '
            f'ON "{table_name}" ("ts_code", "end_date")'
        )


def upsert_dataframe(
    connection: sqlite3.Connection,
    table_name: str,
    frame: pd.DataFrame,
    *,
    batch_id: str,
    source: str = "tushare",
) -> int:
    """Upsert DataFrame 到表"""
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
        tuple(
            None if (not isinstance(value, (list, tuple)) and pd.isna(value))
            else (str(value) if isinstance(value, (list, tuple, dict)) else value)
            for value in row
        )
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
    """记录同步批次"""
    connection.execute(
        """
        INSERT INTO sync_batches (batch_id, table_name, status, row_count, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (batch_id, table_name, status, row_count, message),
    )