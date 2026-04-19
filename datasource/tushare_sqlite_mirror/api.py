"""SQLite-backed Tushare compatibility API."""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

DATA_SOURCE_LABEL = "SQLite mirror of Tushare via citydata"
_METADATA_COLUMNS = {"synced_at", "source", "batch_id"}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_RAW_TABLE_MAP = {
    "stock_basic": "stock_basic_raw",
    "daily": "daily_raw",
    "daily_basic": "daily_basic_raw",
    "income": "income_raw",
    "balancesheet": "balancesheet_raw",
    "cashflow": "cashflow_raw",
    "fina_indicator": "fina_indicator_raw",
    "dividend": "dividend_raw",
    "index_daily": "index_daily_raw",
    "stk_rewards": "stk_rewards_raw",
}


def _validate_factory_mode(mode: Optional[str]) -> None:
    if mode in (None, "", "proxy", "sqlite"):
        return
    if mode == "sdk":
        raise ValueError(
            "tushare_sqlite_mirror does not support SDK mode. "
            "Use the original tushare package for SDK-backed calls."
        )
    raise ValueError(
        f"Unsupported mode '{mode}' for tushare_sqlite_mirror. "
        "Supported values are None, 'proxy', or 'sqlite'."
    )


def _validate_factory_token(token: Optional[str]) -> None:
    if token in (None, ""):
        return
    raise ValueError(
        "tushare_sqlite_mirror reads from a local SQLite mirror and does not accept "
        "online API tokens. Remove the token argument and configure TUSHARE_SQLITE_PATH instead."
    )


def _default_sqlite_path() -> Path:
    package_root = Path(__file__).resolve().parent
    return package_root / "data" / "tushare.db"


class SQLiteTushareAPI:
    """Read-only API that serves layered Tushare data from SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        raw_path = db_path or os.getenv("TUSHARE_SQLITE_PATH")
        self.db_path = Path(raw_path) if raw_path else _default_sqlite_path()
        self.mode = "sqlite"
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"SQLite mirror not found at '{self.db_path}'. "
                "Set TUSHARE_SQLITE_PATH to a valid database file."
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.db_path))
        try:
            yield connection
        finally:
            connection.close()

    def _table_exists(self, table: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
        return row is not None

    def _query(
        self,
        table: str,
        *,
        filters: list[tuple[str, str, object]] | None = None,
        order_by: list[tuple[str, str]] | None = None,
        limit: int | None = None,
        fields: str = "",
    ) -> pd.DataFrame:
        if not self._table_exists(table):
            return pd.DataFrame()

        selected_columns = "*"
        if fields:
            requested = [part.strip() for part in fields.split(",") if part.strip()]
            if requested:
                for column in requested:
                    if not _IDENTIFIER_RE.fullmatch(column):
                        raise ValueError(f"Invalid field name: {column}")
                selected_columns = ", ".join(requested)
        else:
            with self._connect() as connection:
                available_columns = [
                    row[1]
                    for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
                    if row[1] not in _METADATA_COLUMNS
                ]
            if available_columns:
                selected_columns = ", ".join(available_columns)

        sql = [f"SELECT {selected_columns} FROM {table}"]
        params: list[object] = []

        if filters:
            clauses = []
            for column, operator, value in filters:
                if value in (None, ""):
                    continue
                if not _IDENTIFIER_RE.fullmatch(column):
                    raise ValueError(f"Invalid column name: {column}")
                clauses.append(f"{column} {operator} ?")
                params.append(value)
            if clauses:
                sql.append("WHERE " + " AND ".join(clauses))

        if order_by:
            order_parts = []
            for column, direction in order_by:
                if not _IDENTIFIER_RE.fullmatch(column):
                    raise ValueError(f"Invalid sort column: {column}")
                order_parts.append(f"{column} {direction}")
            if order_parts:
                sql.append("ORDER BY " + ", ".join(order_parts))

        if limit is not None:
            sql.append("LIMIT ?")
            params.append(int(limit))

        query = " ".join(sql)
        with self._connect() as connection:
            return pd.read_sql_query(query, connection, params=params)

    def _query_api_table(self, api_name: str, **kwargs) -> pd.DataFrame:
        table = _RAW_TABLE_MAP.get(api_name, api_name)
        limit = kwargs.pop("limit", None)
        fields = kwargs.pop("fields", "")
        order_by = kwargs.pop("_order_by", None)
        filters = []
        for key, value in kwargs.items():
            if value in (None, ""):
                continue
            if key == "start_date":
                target = "trade_date" if api_name in {"daily", "daily_basic", "index_daily"} else "end_date"
                filters.append((target, ">=", value))
            elif key == "end_date":
                target = "trade_date" if api_name in {"daily", "daily_basic", "index_daily"} else "end_date"
                filters.append((target, "<=", value))
            else:
                filters.append((key, "=", value))
        return self._query(
            table,
            filters=filters,
            order_by=order_by,
            limit=limit,
            fields=fields,
        )

    def query_table(
        self,
        table_name: str,
        *,
        filters: list[tuple[str, str, object]] | None = None,
        order_by: list[tuple[str, str]] | None = None,
        limit: int | None = None,
        fields: str = "",
    ) -> pd.DataFrame:
        return self._query(
            table_name,
            filters=filters,
            order_by=order_by,
            limit=limit,
            fields=fields,
        )

    def _call(self, api_name: str, **kwargs) -> pd.DataFrame:
        method = getattr(self, api_name, None)
        if callable(method):
            return method(**kwargs)
        return self._query_api_table(api_name, **kwargs)

    def daily(
        self,
        ts_code: str = "",
        trade_date: str = "",
        start_date: str = "",
        end_date: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "daily",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            limit=limit,
            _order_by=[("trade_date", "DESC")],
        )

    def stock_basic(
        self,
        exchange: str = "",
        list_status: str = "L",
        ts_code: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "stock_basic",
            exchange=exchange,
            list_status=list_status,
            ts_code=ts_code,
            fields=fields,
            limit=limit,
            _order_by=[("ts_code", "ASC")],
        )

    def daily_basic(
        self,
        ts_code: str = "",
        trade_date: str = "",
        start_date: str = "",
        end_date: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "daily_basic",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            limit=limit,
            _order_by=[("trade_date", "DESC")],
        )

    def income(
        self,
        ts_code: str = "",
        period: str = "",
        start_date: str = "",
        end_date: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "income",
            ts_code=ts_code,
            period=period,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            limit=limit,
            _order_by=[("end_date", "DESC"), ("ann_date", "DESC")],
        )

    def balancesheet(
        self,
        ts_code: str = "",
        period: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "balancesheet",
            ts_code=ts_code,
            period=period,
            fields=fields,
            limit=limit,
            _order_by=[("end_date", "DESC"), ("ann_date", "DESC")],
        )

    def cashflow(
        self,
        ts_code: str = "",
        period: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "cashflow",
            ts_code=ts_code,
            period=period,
            fields=fields,
            limit=limit,
            _order_by=[("end_date", "DESC"), ("ann_date", "DESC")],
        )

    def fina_indicator(
        self,
        ts_code: str = "",
        period: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "fina_indicator",
            ts_code=ts_code,
            period=period,
            fields=fields,
            limit=limit,
            _order_by=[("end_date", "DESC"), ("ann_date", "DESC")],
        )

    def dividend(
        self,
        ts_code: str = "",
        period: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "dividend",
            ts_code=ts_code,
            period=period,
            fields=fields,
            limit=limit,
            _order_by=[("ann_date", "DESC"), ("end_date", "DESC")],
        )

    def stk_rewards(
        self,
        ts_code: str = "",
        ann_date: str = "",
        start_date: str = "",
        end_date: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "stk_rewards",
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            limit=limit,
            _order_by=[("ann_date", "DESC"), ("end_date", "DESC")],
        )

    def index_daily(
        self,
        ts_code: str = "",
        trade_date: str = "",
        start_date: str = "",
        end_date: str = "",
        fields: str = "",
        limit: int | None = None,
        **_: object,
    ) -> pd.DataFrame:
        return self._query_api_table(
            "index_daily",
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            limit=limit,
            _order_by=[("trade_date", "DESC")],
        )

    def market_daily_features(
        self,
        ts_code: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int | None = None,
    ) -> pd.DataFrame:
        return self.query_table(
            "market_daily_features",
            filters=[
                ("ts_code", "=", ts_code),
                ("trade_date", ">=", start_date),
                ("trade_date", "<=", end_date),
            ],
            order_by=[("trade_date", "DESC")],
            limit=limit,
        )

    def financial_period_features(
        self,
        ts_code: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int | None = None,
    ) -> pd.DataFrame:
        return self.query_table(
            "financial_period_features",
            filters=[
                ("ts_code", "=", ts_code),
                ("end_date", ">=", start_date),
                ("end_date", "<=", end_date),
            ],
            order_by=[("end_date", "DESC"), ("ann_date", "DESC")],
            limit=limit,
        )

    def dividend_features(self, ts_code: str = "", limit: int | None = None) -> pd.DataFrame:
        return self.query_table(
            "dividend_features",
            filters=[("ts_code", "=", ts_code)],
            order_by=[("ann_date", "DESC"), ("end_date", "DESC")],
            limit=limit,
        )

    def result_fundamentals_latest(self, ts_code: str = "") -> pd.DataFrame:
        return self.query_table(
            "result_fundamentals_latest",
            filters=[("ts_code", "=", ts_code)],
            order_by=[("ts_code", "ASC")],
            limit=1,
        )

    def result_yoy_growth(
        self,
        ts_code: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int | None = None,
    ) -> pd.DataFrame:
        return self.query_table(
            "result_yoy_growth",
            filters=[
                ("ts_code", "=", ts_code),
                ("report_period", ">=", start_date),
                ("report_period", "<=", end_date),
            ],
            order_by=[("report_period", "DESC")],
            limit=limit,
        )

    def result_peg_ratio(
        self,
        ts_code: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int | None = None,
    ) -> pd.DataFrame:
        return self.query_table(
            "result_peg_ratio",
            filters=[
                ("ts_code", "=", ts_code),
                ("end_date", ">=", start_date),
                ("end_date", "<=", end_date),
            ],
            order_by=[("end_date", "DESC")],
            limit=limit,
        )

    def result_technical_indicators_daily(
        self,
        ts_code: str = "",
        start_date: str = "",
        end_date: str = "",
        limit: int | None = None,
    ) -> pd.DataFrame:
        return self.query_table(
            "result_technical_indicators_daily",
            filters=[
                ("ts_code", "=", ts_code),
                ("trade_date", ">=", start_date),
                ("trade_date", "<=", end_date),
            ],
            order_by=[("trade_date", "DESC")],
            limit=limit,
        )

    def pro_bar_with_ma(
        self,
        ts_code: str,
        ma: list[int],
        start_date: str = "",
        end_date: str = "",
        adj: str = "qfq",
        freq: str = "D",
    ) -> pd.DataFrame:
        """获取带 MA 均线的数据（从本地 SQLite 计算）。

        Args:
            ts_code: 股票代码，如 600519.SH
            ma: 均线周期列表，如 [5, 10, 20, 50]
            start_date: 开始日期，YYYYMMDD 格式
            end_date: 结束日期，YYYYMMDD 格式
            adj: 复权类型（qfq/hfq/None），本地按 qfq 前复权处理
            freq: 数据周期，仅支持 D（日线）

        Returns:
            DataFrame 包含日线 OHLCV 字段及 MA 列（ma5, ma10 等），
            按 trade_date 升序排列。

        Note:
            - 本地数据默认按前复权（qfq）处理，无法精确支持 hfq 或不复权。
            - 若需精确复权数据，请使用原始 tushare SDK。
        """
        if freq != "D":
            raise ValueError(
                f"pro_bar_with_ma 仅支持日频（D），当前传入 freq='{freq}'。"
                "本地 SQLite 仅存储日线数据。"
            )

        filters = [("ts_code", "=", ts_code)]
        if start_date:
            filters.append(("trade_date", ">=", start_date))
        if end_date:
            filters.append(("trade_date", "<=", end_date))

        df = self._query(
            "daily_raw",
            filters=filters,
            order_by=[("trade_date", "ASC")],
        )

        if df.empty:
            return df

        df = df.sort_values("trade_date")

        for period in ma:
            col_name = f"ma{period}"
            df[col_name] = df["close"].rolling(window=period, min_periods=period).mean()

        return df


TushareAPI = SQLiteTushareAPI


def get_api(mode: Optional[str] = None, token: Optional[str] = None) -> SQLiteTushareAPI:
    """Compatibility factory that always returns the SQLite-backed API."""
    _validate_factory_mode(mode)
    _validate_factory_token(token)
    return SQLiteTushareAPI()


def pro_api(token: Optional[str] = None) -> SQLiteTushareAPI:
    """Compatibility alias for historical callers."""
    _validate_factory_token(token)
    return get_api()
