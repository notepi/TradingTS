"""数据流路由接口 - 自动发现机制

从 tools_registry.yaml 加载工具定义，自动发现并注册各数据源的函数实现。
"""

import importlib
import os
import sys
import yaml
from typing import Callable

from .config import get_config


# Alpha Vantage rate limit 异常
class AlphaVantageRateLimitError(Exception):
    """Exception raised when Alpha Vantage API rate limit is exceeded."""
    pass


# 动态生成的注册表（启动时填充）
_VENDOR_REGISTRY: dict[str, dict[str, Callable]] = {}
TOOLS_CATEGORIES: dict[str, dict] = {}
_registered = False


def _ensure_registered():
    """惰性初始化：首次访问时触发 discover_and_register()"""
    global _registered
    if not _registered:
        # 先确保 config 已初始化
        get_config()
        _discover_and_register_impl()
        _registered = True


def load_tools_registry() -> dict:
    """从 tools_registry.yaml 加载工具定义"""
    config = get_config()
    project_dir = config.get("project_dir", "")

    # project_dir 是 tradingagents/ 目录，需要往上找项目根目录
    # tools_registry.yaml 在项目根目录的 datasource/tools/
    registry_path = os.path.join(project_dir, "..", "datasource/tools/tools_registry.yaml")

    with open(registry_path, encoding="utf-8") as f:
        return yaml.safe_load(f)["tools"]


def register_vendor(method: str, vendor: str, func: Callable):
    """注册一个数据源的函数实现"""
    if func is None:
        return  # 跳过 None 函数（模块部分加载时的占位）
    _VENDOR_REGISTRY.setdefault(method, {})[vendor] = func


def _discover_and_register_impl():
    """启动时自动发现并注册工具

    1. 从 tools_registry.yaml 读取工具定义
    2. 动态生成 TOOLS_CATEGORIES
    3. 扫描各 datasource/{vendor}/ 找函数并注册
    """
    registry = load_tools_registry()
    config = get_config()
    vendor_paths = config.get("vendor_paths", {})

    for tool_name, spec in registry.items():
        category = spec["category"]
        vendors = spec["vendors"]

        # 动态生成 TOOLS_CATEGORIES
        TOOLS_CATEGORIES.setdefault(category, {"description": "", "tools": []})
        TOOLS_CATEGORIES[category]["tools"].append(tool_name)

        # 扫描各 vendor 找函数并注册
        for vendor in vendors:
            try:
                module_path = vendor_paths.get(vendor, f"datasource.{vendor}")

                # 处理 filesystem path（和 _ensure_vendor_loaded 类似逻辑）
                is_module_name = '.' in module_path and '/' not in module_path
                if not is_module_name:
                    # Filesystem path
                    project_dir = config.get("project_dir", "")
                    if not os.path.isabs(module_path):
                        module_path = os.path.join(project_dir, module_path)
                    parent_dir = os.path.dirname(module_path)
                    module_name = os.path.basename(module_path)

                    did_insert = False
                    if parent_dir and parent_dir not in sys.path:
                        sys.path.insert(0, parent_dir)
                        did_insert = True

                    try:
                        module = importlib.import_module(module_name)
                        func = getattr(module, tool_name, None)
                        if func:
                            register_vendor(tool_name, vendor, func)
                    finally:
                        if did_insert and parent_dir in sys.path:
                            sys.path.remove(parent_dir)
                else:
                    # Module path
                    module = importlib.import_module(module_path)
                    func = getattr(module, tool_name, None)
                    if func:
                        register_vendor(tool_name, vendor, func)

            except (ImportError, AttributeError) as e:
                import logging
                logging.debug(f"Vendor {vendor} does not implement {tool_name}: {e}")


def discover_and_register():
    """暴露给外部的初始化入口。调用后触发 discover 并返回 _VENDOR_REGISTRY"""
    _ensure_registered()
    return _VENDOR_REGISTRY


def get_category_for_method(method: str) -> str:
    """获取工具所属的 category

    优先查 TOOLS_CATEGORIES（从 tools_registry.yaml 生成）。
    Fallback: 从函数元数据获取，或返回 'default'。
    """
    _ensure_registered()
    # 优先查 TOOLS_CATEGORIES
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category

    # Fallback: 从函数元数据获取
    if method in _VENDOR_REGISTRY:
        for vendor, func in _VENDOR_REGISTRY[method].items():
            if hasattr(func, '_dataflow_category'):
                return func._dataflow_category
        return "default"

    raise ValueError(f"Method '{method}' not found in any category")


def get_vendor(category: str, method: str | None = None) -> str:
    """获取配置的数据源

    优先级：tool_vendors > data_vendors > default > yfinance
    """
    _ensure_registered()
    config = get_config()

    # 工具级别配置（最高优先级）
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Category 级别配置
    data_vendors = config.get("data_vendors", {})
    if category in data_vendors:
        return data_vendors[category]

    # Default fallback
    if "default" in data_vendors:
        return data_vendors["default"]

    return "yfinance"  # 系统默认


def route_to_vendor(method: str, *args, **kwargs):
    """路由调用到配置的数据源实现，支持 fallback

    1. 从配置获取数据源（支持逗号分隔的多数据源）
    2. 按顺序尝试，失败时自动切换到下一个
    3. AlphaVantageRateLimitError 触发 fallback
    """
    _ensure_registered()
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    if method not in _VENDOR_REGISTRY:
        raise ValueError(f"Method '{method}' not supported")

    # 构建 fallback 链：主数据源优先，然后是其他可用数据源
    all_available_vendors = list(_VENDOR_REGISTRY[method].keys())
    fallback_vendors = primary_vendors.copy()
    for vendor in all_available_vendors:
        if vendor not in fallback_vendors:
            fallback_vendors.append(vendor)

    for vendor in fallback_vendors:
        if vendor not in _VENDOR_REGISTRY[method]:
            continue

        vendor_impl = _VENDOR_REGISTRY[method][vendor]
        impl_func = vendor_impl[0] if isinstance(vendor_impl, list) else vendor_impl

        try:
            return impl_func(*args, **kwargs)
        except AlphaVantageRateLimitError:
            continue  # Rate limit 触发 fallback

    raise RuntimeError(f"No available vendor for '{method}'")