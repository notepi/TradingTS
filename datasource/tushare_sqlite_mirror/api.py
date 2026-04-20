"""
datasource.tushare_sqlite_mirror.api - SQLite 缓存查询 API

简化的 SQLite 查询接口。
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd


def _get_db_path() -> Path:
    """获取数据库路径"""
    raw_path = os.getenv("TUSHARE_SQLITE_PATH")
    if raw_path:
        return Path(raw_path)
    return Path(__file__).resolve().parent / "data" / "tushare.db"


class SQLiteCacheAPI:
    """SQLite 缓存查询 API"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else _get_db_path()
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite 缓存不存在: {self.db_path}")

    def query(self, sql: str, params: list | None = None) -> pd.DataFrame:
        """执行 SQL 查询"""
        with sqlite3.connect(str(self.db_path)) as conn:
            return pd.read_sql_query(sql, conn, params=params or [])

    def query_table(self, table: str, filters: dict | None = None, order_by: str | None = None) -> pd.DataFrame:
        """查询表"""
        sql = f"SELECT * FROM {table}"
        params = []

        if filters:
            clauses = []
            for key, value in filters.items():
                if value is not None and value != "":
                    clauses.append(f"{key} = ?")
                    params.append(value)
            if clauses:
                sql += " WHERE " + " AND ".join(clauses)

        if order_by:
            sql += f" ORDER BY {order_by}"

        return self.query(sql, params)


def get_api(db_path: Optional[str] = None) -> SQLiteCacheAPI:
    """获取 SQLite 缓存 API"""
    return SQLiteCacheAPI(db_path)


# 兼容别名
def pro_api(db_path: Optional[str] = None) -> SQLiteCacheAPI:
    """兼容别名"""
    return get_api(db_path)