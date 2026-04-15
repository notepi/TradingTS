"""yfinance 数据源

从 yfinance 获取股票数据、技术指标、新闻等。
"""

from .news import get_news, get_global_news
from .stock import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_stockstats_indicator,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_insider_transactions,
)

# 别名映射（兼容 route_to_vendor 的函数名）
get_stock_data = get_YFin_data_online
get_indicators = get_stock_stats_indicators_window

__all__ = [
    "get_news",
    "get_global_news",
    "get_YFin_data_online",
    "get_stock_stats_indicators_window",
    "get_stockstats_indicator",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_insider_transactions",
]
