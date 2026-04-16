"""
tradingagents.dataflows - 数据流路由层

启动时自动发现并注册各数据源的函数实现（通过 interface.py）。
数据源位于 datasource/ 目录。
"""

from .interface import (
    discover_and_register,
    route_to_vendor,
    get_vendor,
    get_category_for_method,
    _VENDOR_REGISTRY,
    TOOLS_CATEGORIES,
)

from .decorators import auto_tool, TOOL_REGISTRY

# 惰性初始化：首次访问时才触发 discover_and_register()
# （由 _ensure_registered() 在 interface.py 中保证）

__all__ = [
    "discover_and_register",
    "route_to_vendor",
    "get_vendor",
    "get_category_for_method",
    "_VENDOR_REGISTRY",
    "TOOLS_CATEGORIES",
    "auto_tool",
    "TOOL_REGISTRY",
]
