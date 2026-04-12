"""
datasource.tushare - Tushare A股数据源（citydata.club代理）

提供A股数据接口，与yfinance接口兼容。

自动注册到 tradingagents.dataflows.interface 的 VENDOR_REGISTRY。
"""

import pkgutil
import importlib
import inspect
from pathlib import Path

from tradingagents.dataflows.decorators import set_vendor_context

# 导入现有 data.py 的函数（保持向后兼容）
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
    """自动扫描 indicators/ 子目录，注册所有函数"""
    from tradingagents.dataflows.interface import register_vendor

    # 设置 vendor 上下文，让装饰器能自动注册
    set_vendor_context("tushare")

    # 注册 data.py 的函数
    register_vendor("get_stock_data", "tushare", get_Tushare_data_online)
    register_vendor("get_indicators", "tushare", get_stock_stats_indicators_window)
    register_vendor("get_fundamentals", "tushare", get_fundamentals)
    register_vendor("get_balance_sheet", "tushare", get_balance_sheet)
    register_vendor("get_cashflow", "tushare", get_cashflow)
    register_vendor("get_income_statement", "tushare", get_income_statement)
    register_vendor("get_insider_transactions", "tushare", get_insider_transactions)
    register_vendor("get_news", "tushare", get_news)
    register_vendor("get_global_news", "tushare", get_global_news)

    # 自动扫描 indicators/ 子目录，注册所有函数
    # 被装饰器装饰的函数会在导入时自动注册
    indicators_path = Path(__file__).parent / "indicators"
    if not indicators_path.exists():
        set_vendor_context(None)
        return

    for importer, modname, ispkg in pkgutil.iter_modules([str(indicators_path)]):
        module = importlib.import_module(f".indicators.{modname}", package=__name__)
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj) and not name.startswith('_'):
                # 如果函数没有装饰器（没有 _dataflow_category），手动注册
                if not hasattr(obj, '_dataflow_category'):
                    register_vendor(name, "tushare", obj)

    # 清除 vendor 上下文
    set_vendor_context(None)


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
