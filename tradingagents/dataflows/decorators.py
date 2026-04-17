"""
数据流工具装饰器

用于声明函数的 category 并自动注册到 VENDOR_REGISTRY。
同时支持自动创建 LangChain tool wrapper。
"""

from typing import Callable
from functools import wraps
from langchain_core.tools import tool

_current_vendor_context: str | None = None

# LangChain Tool 注册表
TOOL_REGISTRY: dict = {}


def set_vendor_context(vendor: str | None):
    """设置当前 vendor 上下文（用于模块导入时）"""
    global _current_vendor_context
    _current_vendor_context = vendor


def get_vendor_context() -> str | None:
    """获取当前 vendor 上下文"""
    return _current_vendor_context


def dataflow_tool(category: str, description: str | None = None):
    """
    装饰器：声明函数的 category 并自动注册到 VENDOR_REGISTRY。

    用法:
        @dataflow_tool("lynch_metrics")
        def get_lynch_metrics(ticker, curr_date=None):
            '''获取 Peter Lynch 分析指标'''
            ...

    参数:
        category: 工具所属的分类（如 lynch_metrics, technical_indicators）
        description: 可选描述，默认使用函数的 __doc__

    效果:
        1. 将 category 存储到函数属性 _dataflow_category
        2. 将 description 存储到函数属性 _dataflow_description
        3. 如果有 vendor 上下文，自动注册到 VENDOR_REGISTRY
    """
    def decorator(func: Callable) -> Callable:
        # 存储元数据到函数属性
        func._dataflow_category = category
        func._dataflow_description = description or (func.__doc__ or "")

        # 自动注册（如果当前有 vendor 上下文）
        if _current_vendor_context:
            from datasource.datahub.servers.interface import register_vendor
            register_vendor(func.__name__, _current_vendor_context, func)

        return func
    return decorator


def auto_tool(description: str | None = None):
    """
    装饰器：自动创建 LangChain tool wrapper 并注册到 TOOL_REGISTRY。

    用法:
        @auto_tool(description="PEG Ratio 分析 - Lynch 核心指标")
        def get_peg_ratio(ticker: str, curr_date: str = None):
            '''PEG Ratio 分析'''
            ...

    效果:
        1. 创建 LangChain @tool wrapper，保留原函数签名
        2. 注册到 TOOL_REGISTRY[函数名]
        3. 返回原函数（数据层仍可正常调用）

    注意: 装饰器顺序很重要！如果同时用 @dataflow_tool，要放在它上面:
        @auto_tool(description="...")
        @dataflow_tool("fundamental_data")
        def get_peg_ratio(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # 创建 LangChain tool wrapper
        @tool
        @wraps(func)
        def langchain_tool_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # 设置 tool 名称和描述
        langchain_tool_wrapper.name = func.__name__
        langchain_tool_wrapper.description = description or (func.__doc__ or "")

        # 注册到 TOOL_REGISTRY
        TOOL_REGISTRY[func.__name__] = langchain_tool_wrapper

        # 返回原函数，不影响数据层调用
        return func

    return decorator