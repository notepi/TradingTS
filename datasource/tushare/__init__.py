"""
datasource.tushare - Tushare A股数据源（citydata.club代理）

提供A股数据接口，与yfinance接口兼容。

函数从 tools_registry.yaml 自动发现，无需手动注册。
"""

# 导入 data.py 的函数
from .data import (
    get_Tushare_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_insider_transactions,
)

# 导入 Lynch 指标函数
from .indicators.enhanced_data import (
    get_peg_ratio,
    get_yoy_growth,
)

# 别名映射（兼容 route_to_vendor 的函数名）
get_stock_data = get_Tushare_data_online
get_indicators = get_stock_stats_indicators_window

__all__ = [
    # 基础数据函数
    "get_stock_data",
    "get_indicators",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_insider_transactions",
    # Lynch 指标函数
    "get_peg_ratio",
    "get_yoy_growth",
]