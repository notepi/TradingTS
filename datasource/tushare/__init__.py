"""
datasource.tushare - Tushare A股数据源（citydata.club代理）

提供A股数据接口，与yfinance接口兼容。

自动注册到 tradingagents.dataflows.interface 的 VENDOR_REGISTRY。
"""

from .data import (
    get_Tushare_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_insider_transactions,
    get_news,
    get_global_news,
)


def _register_vendors():
    """Register all tushare vendor implementations."""
    # Import here to avoid circular import
    from tradingagents.dataflows.interface import register_vendor

    register_vendor("get_stock_data", "tushare", get_Tushare_data_online)
    register_vendor("get_indicators", "tushare", get_stock_stats_indicators_window)
    register_vendor("get_fundamentals", "tushare", get_fundamentals)
    register_vendor("get_balance_sheet", "tushare", get_balance_sheet)
    register_vendor("get_cashflow", "tushare", get_cashflow)
    register_vendor("get_income_statement", "tushare", get_income_statement)
    register_vendor("get_insider_transactions", "tushare", get_insider_transactions)
    register_vendor("get_news", "tushare", get_news)
    register_vendor("get_global_news", "tushare", get_global_news)


# Auto-register when module is imported
_register_vendors()


__all__ = [
    "get_Tushare_data_online",
    "get_stock_stats_indicators_window",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_insider_transactions",
    "get_news",
    "get_global_news",
]
