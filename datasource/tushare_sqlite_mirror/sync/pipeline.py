"""
sync/pipeline.py - 数据同步管道

新架构：调用 datasource.tushare 函数获取 DataFrame（raw=True），存入 SQLite
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from datasource.tushare import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_peg_ratio,
    get_yoy_growth,
)
from datasource.tushare.symbols import normalize_a_share_symbol

from .storage import connect, initialize_database, log_batch, upsert_dataframe


def _resolve_batch_id(batch_id: str | None) -> str:
    """解析批次 ID"""
    if batch_id:
        return batch_id
    env_batch = os.getenv("SYNC_BATCH_DATE")
    if env_batch:
        return env_batch
    return datetime.utcnow().strftime("%Y%m%d")


def _resolve_as_of_date(as_of_date: str | None) -> datetime:
    """解析日期，支持 YYYY-MM-DD 或 YYYYMMDD 格式"""
    if as_of_date:
        # 支持 YYYY-MM-DD 和 YYYYMMDD 两种格式
        if "-" in as_of_date:
            return datetime.strptime(as_of_date, "%Y-%m-%d")
        return datetime.strptime(as_of_date, "%Y%m%d")
    env_date = os.getenv("SYNC_BATCH_DATE")
    if env_date:
        if "-" in env_date:
            return datetime.strptime(env_date, "%Y-%m-%d")
        return datetime.strptime(env_date, "%Y%m%d")
    return datetime.utcnow()


def run_bootstrap(db_path: Path | str) -> Path:
    """初始化数据库"""
    initialize_database(db_path)
    return Path(db_path)


def sync_stock_data(
    connection,
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    batch_id: str,
) -> int:
    """同步股票行情数据"""
    ts_code = normalize_a_share_symbol(symbol)

    # 调用 tushare 函数获取 DataFrame
    result = get_stock_data(symbol, start_date, end_date, raw=True)

    if isinstance(result, str) and (result.startswith("Error") or result.startswith("No data")):
        log_batch(
            connection,
            batch_id=batch_id,
            table_name="stock_data",
            status="error",
            row_count=0,
            message=result,
        )
        return 0

    df = result
    if df is None or df.empty:
        return 0

    # 存入 SQLite
    count = upsert_dataframe(connection, "stock_data", df, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="stock_data", status="completed", row_count=count)
    return count


def sync_indicators(
    connection,
    *,
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 30,
    batch_id: str,
) -> int:
    """同步技术指标数据"""
    ts_code = normalize_a_share_symbol(symbol)

    # 调用 tushare 函数获取 DataFrame
    result = get_indicators(symbol, indicator, curr_date, look_back_days, raw=True)

    if isinstance(result, str) and result.startswith("Error"):
        log_batch(
            connection,
            batch_id=batch_id,
            table_name="indicators",
            status="error",
            row_count=0,
            message=result,
        )
        return 0

    df = result
    if df is None or df.empty:
        return 0

    count = upsert_dataframe(connection, "indicators", df, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="indicators", status="completed", row_count=count)
    return count


def sync_fundamentals(
    connection,
    *,
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
    curr_date: str | None = None,
    batch_id: str,
) -> int:
    """同步基本面数据

    Args:
        start_date/end_date: 日期范围查询（每日估值历史）
        curr_date: 单日查询（当前已废弃，建议用 start_date + end_date）
    """
    ts_code = normalize_a_share_symbol(ticker)

    # 调用 tushare 函数获取 DataFrame
    # 优先使用日期范围查询
    if start_date and end_date:
        result = get_fundamentals(ticker, start_date=start_date, end_date=end_date, raw=True)
    else:
        # 单日查询（返回1行）
        result = get_fundamentals(ticker, curr_date=end_date or curr_date, raw=True)

    if isinstance(result, str) and (result.startswith("Error") or result.startswith("No")):
        log_batch(
            connection,
            batch_id=batch_id,
            table_name="fundamentals",
            status="error",
            row_count=0,
            message=result,
        )
        return 0

    df = result
    if df is None or df.empty:
        return 0

    count = upsert_dataframe(connection, "fundamentals", df, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="fundamentals", status="completed", row_count=count)
    return count


def sync_balance_sheet(
    connection,
    *,
    ticker: str,
    freq: str = "quarterly",
    curr_date: str | None = None,
    batch_id: str,
) -> int:
    """同步资产负债表"""
    ts_code = normalize_a_share_symbol(ticker)

    result = get_balance_sheet(ticker, freq, curr_date, raw=True)

    if isinstance(result, str) and (result.startswith("Error") or result.startswith("No")):
        log_batch(connection, batch_id=batch_id, table_name="balance_sheet", status="error", row_count=0, message=result)
        return 0

    df = result
    if df is None or df.empty:
        return 0

    count = upsert_dataframe(connection, "balance_sheet", df, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="balance_sheet", status="completed", row_count=count)
    return count


def sync_cashflow(
    connection,
    *,
    ticker: str,
    freq: str = "quarterly",
    curr_date: str | None = None,
    batch_id: str,
) -> int:
    """同步现金流量表"""
    ts_code = normalize_a_share_symbol(ticker)

    result = get_cashflow(ticker, freq, curr_date, raw=True)

    if isinstance(result, str) and (result.startswith("Error") or result.startswith("No")):
        log_batch(connection, batch_id=batch_id, table_name="cashflow", status="error", row_count=0, message=result)
        return 0

    df = result
    if df is None or df.empty:
        return 0

    count = upsert_dataframe(connection, "cashflow", df, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="cashflow", status="completed", row_count=count)
    return count


def sync_income_statement(
    connection,
    *,
    ticker: str,
    freq: str = "quarterly",
    curr_date: str | None = None,
    batch_id: str,
) -> int:
    """同步利润表"""
    ts_code = normalize_a_share_symbol(ticker)

    result = get_income_statement(ticker, freq, curr_date, raw=True)

    if isinstance(result, str) and (result.startswith("Error") or result.startswith("No")):
        log_batch(connection, batch_id=batch_id, table_name="income_statement", status="error", row_count=0, message=result)
        return 0

    df = result
    if df is None or df.empty:
        return 0

    count = upsert_dataframe(connection, "income_statement", df, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="income_statement", status="completed", row_count=count)
    return count


def sync_peg_ratio(
    connection,
    *,
    ticker: str,
    curr_date: str | None = None,
    batch_id: str,
) -> int:
    """同步 PEG 数据"""
    ts_code = normalize_a_share_symbol(ticker)

    result = get_peg_ratio(ticker, curr_date, raw=True)

    if isinstance(result, str) and result.startswith("Error"):
        log_batch(connection, batch_id=batch_id, table_name="peg_ratio", status="error", row_count=0, message=result)
        return 0

    df = result
    if df is None or df.empty:
        return 0

    count = upsert_dataframe(connection, "peg_ratio", df, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="peg_ratio", status="completed", row_count=count)
    return count


def sync_yoy_growth(
    connection,
    *,
    ticker: str,
    curr_date: str | None = None,
    batch_id: str,
) -> int:
    """同步 YoY 增长数据"""
    ts_code = normalize_a_share_symbol(ticker)

    result = get_yoy_growth(ticker, curr_date, raw=True)

    if isinstance(result, str) and result.startswith("Error"):
        log_batch(connection, batch_id=batch_id, table_name="yoy_growth", status="error", row_count=0, message=result)
        return 0

    df = result
    if df is None or df.empty:
        return 0

    count = upsert_dataframe(connection, "yoy_growth", df, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="yoy_growth", status="completed", row_count=count)
    return count


def run_pipeline(
    db_path: Path | str,
    *,
    batch_id: str | None = None,
    symbol: str,
    start_date: str,
    end_date: str,
    curr_date: str | None = None,
    indicators: list[str] | None = None,
) -> Path:
    """运行完整同步管道"""
    initialize_database(db_path)
    resolved_batch_id = _resolve_batch_id(batch_id)
    resolved_date = _resolve_as_of_date(curr_date)

    ts_code = normalize_a_share_symbol(symbol)

    connection = connect(db_path)
    try:
        # 1. 股票行情
        sync_stock_data(
            connection,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            batch_id=resolved_batch_id,
        )

        # 2. 技术指标（默认同步常用指标）
        default_indicators = ["close_10_ema", "close_50_sma", "close_200_sma", "macd", "rsi"]
        for indicator in (indicators or default_indicators):
            sync_indicators(
                connection,
                symbol=symbol,
                indicator=indicator,
                curr_date=end_date,
                look_back_days=30,
                batch_id=resolved_batch_id,
            )

        # 3. 基本面（每日估值历史）
        sync_fundamentals(connection, ticker=symbol, start_date=start_date, end_date=end_date, batch_id=resolved_batch_id)

        # 4. 财务报表
        sync_balance_sheet(connection, ticker=symbol, freq="quarterly", curr_date=end_date, batch_id=resolved_batch_id)
        sync_cashflow(connection, ticker=symbol, freq="quarterly", curr_date=end_date, batch_id=resolved_batch_id)
        sync_income_statement(connection, ticker=symbol, freq="quarterly", curr_date=end_date, batch_id=resolved_batch_id)

        # 5. Lynch 指标
        sync_peg_ratio(connection, ticker=symbol, curr_date=end_date, batch_id=resolved_batch_id)
        sync_yoy_growth(connection, ticker=symbol, curr_date=end_date, batch_id=resolved_batch_id)

        connection.commit()
        log_batch(
            connection,
            batch_id=resolved_batch_id,
            table_name="pipeline",
            status="completed",
            row_count=0,
            message=f"Synced {symbol} from {start_date} to {end_date}",
        )
        connection.commit()
    except Exception as exc:
        connection.rollback()
        log_batch(
            connection,
            batch_id=resolved_batch_id,
            table_name="pipeline",
            status="failed",
            row_count=0,
            message=str(exc),
        )
        connection.commit()
        raise
    finally:
        connection.close()

    return Path(db_path)


def run_daily_sync(
    db_path: Path | str,
    *,
    batch_id: str | None = None,
    symbol: str,
    curr_date: str | None = None,
) -> Path:
    """每日同步（同步最近一年数据）"""
    resolved_date = _resolve_as_of_date(curr_date)
    start_date = (resolved_date - timedelta(days=365)).strftime("%Y-%m-%d")
    end_date = resolved_date.strftime("%Y-%m-%d")

    return run_pipeline(
        db_path,
        batch_id=batch_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        curr_date=end_date,
    )