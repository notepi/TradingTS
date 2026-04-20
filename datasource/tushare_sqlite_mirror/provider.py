"""
datasource/tushare_sqlite_mirror/provider.py - SQLite 缓存数据提供者

继承 StockDataProvider，实现 SQLite 查询逻辑。
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from datasource.tushare.base_provider import StockDataProvider


# 数据库路径
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "tushare.db"


def _get_db_path() -> Path:
    """获取数据库路径"""
    raw_path = os.getenv("TUSHARE_SQLITE_PATH")
    if raw_path:
        return Path(raw_path)
    return DEFAULT_DB_PATH


# Provider 实例（延迟初始化）
_provider = None


def get_provider() -> SQLiteMirrorProvider:
    """获取 Provider 实例"""
    global _provider
    if _provider is None:
        _provider = SQLiteMirrorProvider()
    return _provider


class SQLiteMirrorProvider(StockDataProvider):
    """SQLite 缓存数据提供者"""

    def __init__(self, db_path=None):
        self.db_path = db_path or _get_db_path()

    @property
    def source_name(self) -> str:
        return "SQLite mirror (cached)"

    def _connect(self):
        """连接数据库"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite 缓存不存在: {self.db_path}")
        return sqlite3.connect(str(self.db_path))

    def _query(self, table: str, filters: dict | None = None, order_by: str | None = None) -> pd.DataFrame:
        """从 SQLite 查询数据"""
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

        with self._connect() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    # ========== 数据获取实现 ==========
    def _fetch_stock_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票行情数据"""
        df = self._query("stock_data", {"ts_code": ts_code}, order_by="Date ASC")

        if df.empty:
            return pd.DataFrame()

        # 过滤日期范围
        df["Date"] = pd.to_datetime(df["Date"])
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df["Date"] >= start_dt) & (df["Date"] <= end_dt)]

        if df.empty:
            return pd.DataFrame()

        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

        # 选择需要的列
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        df = df[[c for c in cols if c in df.columns]]

        return df

    def _fetch_indicators(
        self,
        ts_code: str,
        indicator: str,
        curr_date: str,
        look_back_days: int
    ) -> dict:
        """获取技术指标数据"""
        df = self._query("indicators", {"ts_code": ts_code, "indicator": indicator}, order_by="Date ASC")

        if df.empty:
            return {}

        # 计算显示范围
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        display_start_dt = curr_dt - timedelta(days=look_back_days)

        df["Date"] = pd.to_datetime(df["Date"])
        df = df[(df["Date"] >= display_start_dt) & (df["Date"] <= curr_dt)]

        value_by_date = {}
        for _, row in df.iterrows():
            date_str = row["Date"].strftime("%Y-%m-%d")
            value_by_date[date_str] = row.get("value")

        return value_by_date

    def _fetch_fundamentals(self, ts_code: str, curr_date: str | None, start_date: str | None, end_date: str | None) -> dict | pd.DataFrame:
        """获取估值数据

        Args:
            curr_date: 单日查询（返回估值 dict）
            start_date/end_date: 日期范围查询（返回估值历史 DataFrame）
        """
        # 日期范围查询：返回每日估值历史
        if start_date and end_date:
            df = self._query("fundamentals", {"ts_code": ts_code}, order_by="Date ASC")

            if df.empty:
                return None

            # 过滤日期范围
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                df = df[(df["Date"] >= start_dt) & (df["Date"] <= end_dt)]
                df["Date"] = df["Date"].dt.strftime("%Y%m%d")

            # 选择估值相关列
            cols = ["Date", "close", "pe", "pe_ttm", "pb", "total_mv", "circ_mv", "total_share", "turnover_rate"]
            df = df[[c for c in cols if c in df.columns]]

            return df

        # 单日查询：返回估值 dict
        date_str = curr_date.replace("-", "") if curr_date else datetime.now().strftime("%Y%m%d")

        # 查询指定日期的数据
        df = self._query("fundamentals", {"ts_code": ts_code, "Date": date_str})

        if df.empty:
            # 如果指定日期没有数据，查询最近的估值数据
            df = self._query("fundamentals", {"ts_code": ts_code}, order_by="Date DESC")
            if df.empty:
                return None
            df = df.head(1)

        row = df.iloc[0]

        data = {}
        data["Date"] = row.get("Date")

        close = row.get("close")
        if close:
            data["Stock_Price_元"] = f"{float(close):.2f}"

        pe = row.get("pe")
        if pe and float(pe) > 0:
            data["P/E_Ratio"] = f"{float(pe):.2f}"
        else:
            data["P/E_Ratio"] = "N/A"

        pe_ttm = row.get("pe_ttm")
        if pe_ttm and float(pe_ttm) > 0:
            data["P/E_Ratio_TTM"] = f"{float(pe_ttm):.2f}"
        else:
            data["P/E_Ratio_TTM"] = "N/A"

        pb = row.get("pb")
        if pb and float(pb) > 0:
            data["P/B_Ratio"] = f"{float(pb):.2f}"
        else:
            data["P/B_Ratio"] = "N/A"

        total_mv = row.get("total_mv")
        if total_mv:
            data["Total_Market_Cap_元"] = f"{float(total_mv) * 10000:.2f}"

        circ_mv = row.get("circ_mv")
        if circ_mv:
            data["Circulating_Market_Cap_元"] = f"{float(circ_mv) * 10000:.2f}"

        return data

    def _fetch_balance_sheet(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取资产负债表"""
        df = self._query("balance_sheet", {"ts_code": ts_code}, order_by="end_date DESC")

        if df.empty:
            return pd.DataFrame()

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        return df

    def _fetch_cashflow(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取现金流量表"""
        df = self._query("cashflow", {"ts_code": ts_code}, order_by="end_date DESC")

        if df.empty:
            return pd.DataFrame()

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        return df

    def _fetch_income_statement(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取利润表"""
        df = self._query("income_statement", {"ts_code": ts_code}, order_by="end_date DESC")

        if df.empty:
            return pd.DataFrame()

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        return df

    def _fetch_insider_transactions(self, ts_code: str) -> pd.DataFrame:
        """获取内部交易数据"""
        df = self._query("insider_transactions", {"ts_code": ts_code}, order_by="ann_date DESC")

        if df.empty:
            return pd.DataFrame()

        df = df.head(30)

        return df

    def _fetch_peg_ratio(self, ts_code: str, curr_date: str | None) -> pd.DataFrame:
        """获取 PEG 数据"""
        df = self._query("peg_ratio", {"ts_code": ts_code}, order_by="end_date DESC")

        if df.empty:
            return pd.DataFrame()

        return df

    def _fetch_yoy_growth(self, ts_code: str, curr_date: str | None) -> pd.DataFrame:
        """获取 YoY 增长数据"""
        df = self._query("yoy_growth", {"ts_code": ts_code}, order_by="end_date DESC")

        if df.empty:
            return pd.DataFrame()

        return df