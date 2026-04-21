"""
datasource.tushare_sqlite_mirror.data - SQLite 缓存数据接口

从 SQLite 缓存取数，输出格式和 datasource.tushare 一致。
"""

from typing import Annotated

import pandas as pd

# 从 tushare 导入常量
from datasource.tushare.data import INDICATOR_DESCRIPTIONS

# 导入 provider 和 get_provider
from .provider import SQLiteMirrorProvider, get_provider


# ========== 暴露函数（兼容现有调用）==========

def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    raw: bool = False,
) -> str:
    """获取股票历史数据 (OHLCV) - 从 SQLite 缓存

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_stock_data(symbol, start_date, end_date, raw=raw)


def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator"],
    curr_date: Annotated[str, "The current trading date, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to display"] = 30,
    raw: bool = False,
) -> str:
    """获取技术指标数据 - 从 SQLite 缓存

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_indicators(symbol, indicator, curr_date, look_back_days, raw=raw)


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str | None, "start date for history query"] = None,
    end_date: Annotated[str | None, "end date for history query"] = None,
    curr_date: Annotated[str | None, "single date query"] = None,
    raw: bool = False,
) -> str:
    """获取公司基本面数据 - 从 SQLite 缓存

    Args:
        start_date: 开始日期（日期范围查询）
        end_date: 结束日期（日期范围查询）
        curr_date: 单日查询（返回该日期数据）
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_fundamentals(ticker, start_date, end_date, curr_date, raw=raw)


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str | None, "current date"] = None,
    raw: bool = False,
) -> str:
    """获取资产负债表 - 从 SQLite 缓存

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_balance_sheet(ticker, freq, curr_date, raw=raw)


def get_cashflow(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str | None, "current date"] = None,
    raw: bool = False,
) -> str:
    """获取现金流量表 - 从 SQLite 缓存

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_cashflow(ticker, freq, curr_date, raw=raw)


def get_income_statement(
    ticker: Annotated[str, "ticker symbol"],
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str | None, "current date"] = None,
    raw: bool = False,
) -> str:
    """获取利润表 - 从 SQLite 缓存

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_income_statement(ticker, freq, curr_date, raw=raw)


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
    raw: bool = False,
) -> str:
    """获取高管增减持数据 - 从 SQLite 缓存

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_insider_transactions(ticker, raw=raw)


# ========== 别名（兼容现有调用）==========

get_Tushare_data_online = get_stock_data
get_stock_stats_indicators_window = get_indicators


# ========== 批量计算函数（从 SQLite 读数据，本地计算）==========

from .calculator import calc_peg_ratio_batch, calc_yoy_growth_batch


def get_peg_ratio_batch(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str | None, "start date"] = None,
    end_date: Annotated[str | None, "end date"] = None,
) -> str:
    """批量计算 PEG（从 SQLite 读数据，本地计算）

    Args:
        ticker: 股票代码
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）

    Returns:
        DataFrame: end_date, pe_ttm, n_income, n_income_yoy, peg, valuation
    """
    from .provider import get_provider
    ts_code = get_provider()._normalize_symbol(ticker)
    return calc_peg_ratio_batch(ts_code, start_date, end_date)


def get_yoy_growth_batch(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """批量计算增长率（从 SQLite 读数据，本地计算）

    Args:
        ticker: 股票代码

    Returns:
        DataFrame: end_date, revenue, n_income, revenue_yoy, n_income_yoy
    """
    from .provider import get_provider
    ts_code = get_provider()._normalize_symbol(ticker)
    return calc_yoy_growth_batch(ts_code)


# ========== 技术分析表查询函数 ==========

def get_price_daily(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"],
    raw: bool = False,
) -> str | pd.DataFrame:
    """获取技术分析行情数据 - price_daily 表

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）

    Returns:
        格式化字符串或 DataFrame
    """
    return get_provider().get_price_daily(symbol, start_date, end_date, raw=raw)


def get_trend_ma_daily(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"],
    raw: bool = False,
) -> str | pd.DataFrame:
    """获取均线趋势数据 - trend_ma_daily 表

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）

    Returns:
        格式化字符串或 DataFrame（包含 SMA/EMA + 趋势标签）
    """
    return get_provider().get_trend_ma_daily(symbol, start_date, end_date, raw=raw)


def get_momentum_volatility_daily(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"],
    raw: bool = False,
) -> str | pd.DataFrame:
    """获取动量波动数据 - momentum_volatility_daily 表

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）

    Returns:
        格式化字符串或 DataFrame（包含 RSI/MACD/ATR + 状态标签）
    """
    return get_provider().get_momentum_volatility_daily(symbol, start_date, end_date, raw=raw)


def get_technical_labels_daily(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"],
    raw: bool = False,
) -> str | pd.DataFrame:
    """获取技术标签数据 - technical_labels_daily 表

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）

    Returns:
        格式化字符串或 DataFrame（包含综合趋势/动量/风险标签）
    """
    return get_provider().get_technical_labels_daily(symbol, start_date, end_date, raw=raw)