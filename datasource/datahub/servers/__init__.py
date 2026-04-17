"""数仓层 servers - 数据服务的唯一入口

对上暴露稳定的 @tool 接口给智能体，路由到配置的数据源 vendor。
"""

from .interface import (
    discover_and_register,
    route_to_vendor,
    get_all_tool_modules,
    get_category_for_method,
    get_vendor,
    load_tools_registry,
    register_vendor,
    AlphaVantageRateLimitError,
)

__all__ = [
    "discover_and_register",
    "route_to_vendor",
    "get_all_tool_modules",
    "get_category_for_method",
    "get_vendor",
    "load_tools_registry",
    "register_vendor",
    "AlphaVantageRateLimitError",
]