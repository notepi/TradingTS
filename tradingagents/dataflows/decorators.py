"""
数据流工具装饰器

用于声明函数的 category 并自动注册到 VENDOR_REGISTRY。
"""

from typing import Callable

_current_vendor_context: str | None = None


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
            from tradingagents.dataflows.interface import register_vendor
            register_vendor(func.__name__, _current_vendor_context, func)

        return func
    return decorator