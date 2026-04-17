"""
tradingagents.dataflows - 数据流路由层

路由核心已移至 datasource/datahub/servers/interface.py。
这里保留装饰器和向后兼容的导入。
"""

from datasource.datahub.servers.interface import (
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
