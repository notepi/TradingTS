"""
Tushare 数据接口 - 双模式 API（HTTP 代理 / 官方 SDK）

与 y_finance.py 保持相同接口，实现平滑切换。
"""

from typing import Annotated

# 从基类导入常量
from .base_provider import INDICATOR_DESCRIPTIONS

# 导入 provider 和 get_provider
from .provider import TushareProvider, get_provider


def _get_tushare_indicators() -> list[str]:
    """返回 tushare 支持的指标列表"""
    return list(INDICATOR_DESCRIPTIONS.keys())


# ========== 暴露函数（兼容现有调用）==========

def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    raw: bool = False,
) -> str:
    """获取股票历史数据 (OHLCV)

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_stock_data(symbol, start_date, end_date, raw=raw)


def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days of values to display in the output"] = 30,
    raw: bool = False,
) -> str:
    """获取技术指标数据

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）

    注意：此函数固定获取1年历史数据以确保指标计算准确，
    look_back_days 只控制输出显示的日期范围，不影响计算精度。
    """
    return get_provider().get_indicators(symbol, indicator, curr_date, look_back_days, raw=raw)


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str | None, "start date for history query"] = None,
    end_date: Annotated[str | None, "end date for history query"] = None,
    curr_date: Annotated[str | None, "single date query"] = None,
    raw: bool = False,
) -> str:
    """获取公司基本面数据

    Args:
        start_date: 开始日期（日期范围查询）
        end_date: 结束日期（日期范围查询）
        curr_date: 单日查询（返回该日期数据）
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_fundamentals(ticker, start_date, end_date, curr_date, raw=raw)


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
    raw: bool = False,
) -> str:
    """获取资产负债表

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_balance_sheet(ticker, freq, curr_date, raw=raw)


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
    raw: bool = False,
) -> str:
    """获取现金流量表

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_cashflow(ticker, freq, curr_date, raw=raw)


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None,
    raw: bool = False,
) -> str:
    """获取利润表

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_income_statement(ticker, freq, curr_date, raw=raw)


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"],
    raw: bool = False,
) -> str:
    """获取高管和股东增减持数据

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_insider_transactions(ticker, raw=raw)


# ========== 别名（兼容现有调用）==========

get_Tushare_data_online = get_stock_data
get_stock_stats_indicators_window = get_indicators