"""
tradingagents.dataflows - 数据流路由层

启动时自动发现并注册各数据源的函数实现。
"""

# 导入 yfinance 新闻函数，触发 @auto_tool 注册
from .yfinance_news import get_news, get_global_news

__all__ = [
    "get_news",
    "get_global_news",
]