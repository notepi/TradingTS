from typing import Callable
import importlib

# Import from vendor-specific modules
from .y_finance import (
    get_YFin_data_online,
    get_stock_stats_indicators_window,
    get_fundamentals as get_yfinance_fundamentals,
    get_balance_sheet as get_yfinance_balance_sheet,
    get_cashflow as get_yfinance_cashflow,
    get_income_statement as get_yfinance_income_statement,
    get_insider_transactions as get_yfinance_insider_transactions,
)
from .yfinance_news import get_news_yfinance, get_global_news_yfinance
from .alpha_vantage import (
    get_stock as get_alpha_vantage_stock,
    get_indicator as get_alpha_vantage_indicator,
    get_fundamentals as get_alpha_vantage_fundamentals,
    get_balance_sheet as get_alpha_vantage_balance_sheet,
    get_cashflow as get_alpha_vantage_cashflow,
    get_income_statement as get_alpha_vantage_income_statement,
    get_insider_transactions as get_alpha_vantage_insider_transactions,
    get_news as get_alpha_vantage_news,
    get_global_news as get_alpha_vantage_global_news,
)
from .alpha_vantage_common import AlphaVantageRateLimitError

# Configuration and routing logic
from .config import get_config

# Tools organized by category
TOOLS_CATEGORIES = {
    "core_stock_apis": {
        "description": "OHLCV stock price data",
        "tools": [
            "get_stock_data"
        ]
    },
    "technical_indicators": {
        "description": "Technical analysis indicators",
        "tools": [
            "get_indicators"
        ]
    },
    "fundamental_data": {
        "description": "Company fundamentals",
        "tools": [
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement"
        ]
    },
    "lynch_metrics": {
        "description": "Peter Lynch analysis metrics",
        "tools": [
            "get_peg_ratio",
            "get_yoy_growth"
        ]
    },
    "news_data": {
        "description": "News and insider data",
        "tools": [
            "get_news",
            "get_global_news",
            "get_insider_transactions",
        ]
    }
}

VENDOR_LIST = [
    "yfinance",
    "alpha_vantage",
]

# Dynamic vendor registry - populated by builtin vendors at load time,
# and by external vendors (datasource.*) when first used
_VENDOR_REGISTRY: dict[str, dict[str, Callable]] = {
    # core_stock_apis
    "get_stock_data": {
        "alpha_vantage": get_alpha_vantage_stock,
        "yfinance": get_YFin_data_online,
    },
    # technical_indicators
    "get_indicators": {
        "alpha_vantage": get_alpha_vantage_indicator,
        "yfinance": get_stock_stats_indicators_window,
    },
    # fundamental_data
    "get_fundamentals": {
        "alpha_vantage": get_alpha_vantage_fundamentals,
        "yfinance": get_yfinance_fundamentals,
    },
    "get_balance_sheet": {
        "alpha_vantage": get_alpha_vantage_balance_sheet,
        "yfinance": get_yfinance_balance_sheet,
    },
    "get_cashflow": {
        "alpha_vantage": get_alpha_vantage_cashflow,
        "yfinance": get_yfinance_cashflow,
    },
    "get_income_statement": {
        "alpha_vantage": get_alpha_vantage_income_statement,
        "yfinance": get_yfinance_income_statement,
    },
    # news_data
    "get_news": {
        "alpha_vantage": get_alpha_vantage_news,
        "yfinance": get_news_yfinance,
    },
    "get_global_news": {
        "yfinance": get_global_news_yfinance,
        "alpha_vantage": get_alpha_vantage_global_news,
    },
    "get_insider_transactions": {
        "alpha_vantage": get_alpha_vantage_insider_transactions,
        "yfinance": get_yfinance_insider_transactions,
    },
}


def register_vendor(method: str, vendor: str, func: Callable):
    """Register a vendor implementation for a method."""
    _VENDOR_REGISTRY.setdefault(method, {})[vendor] = func


def _ensure_vendor_loaded(vendor: str) -> bool:
    """
    Dynamically load an external vendor module if not already loaded.
    External vendors are loaded from datasource.{vendor} by default,
    or from vendor_paths in config.yaml.

    vendor_paths supports both module paths (e.g. "datasource.tushare")
    and filesystem paths (e.g. "/path/to/my_vendor").

    Returns True if vendor was loaded or already available, False if not found.
    """
    import os
    import sys

    # Check if vendor is already registered
    if any(vendor in v for v in _VENDOR_REGISTRY.values()):
        return True

    # Get module path from config (supports custom paths)
    config = get_config()
    vendor_paths = config.get("vendor_paths", {})
    module_path = vendor_paths.get(vendor, f"datasource.{vendor}")

    # Try to load external vendor module (imports __init__.py which auto-registers)
    # Dot-separated names (e.g. "datasource.tushare") are module paths.
    # Anything containing "/" is a filesystem path (absolute, ./, ../, or relative like "plugins/my_vendor").
    is_module_name = '.' in module_path and '/' not in module_path
    if not is_module_name:
        # Filesystem path: extract parent dir and module name
        config = get_config()
        project_dir = config.get("project_dir", "")
        # Resolve relative paths against project_dir (not CWD)
        if not os.path.isabs(module_path):
            module_path = os.path.join(project_dir, module_path)
        parent_dir = os.path.dirname(module_path)
        module_name = os.path.basename(module_path)
        # Only remove from sys.path if WE added it (not pre-existing)
        did_insert = False
        if parent_dir and parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
            did_insert = True
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False
        finally:
            if did_insert and parent_dir in sys.path:
                sys.path.remove(parent_dir)
    else:
        # Dot-separated module path: direct import
        try:
            importlib.import_module(module_path)
            return True
        except ImportError:
            return False

def get_category_for_method(method: str) -> str:
    """Get the category that contains the specified method.

    优先查静态 TOOLS_CATEGORIES（官方契约）。
    Fallback: 从函数元数据直接获取，或返回 'default'。
    """
    # 优先查静态 TOOLS_CATEGORIES（官方契约）
    for category, info in TOOLS_CATEGORIES.items():
        if method in info["tools"]:
            return category

    # Fallback: 从函数元数据直接获取
    if method in _VENDOR_REGISTRY:
        for vendor, func in _VENDOR_REGISTRY[method].items():
            if hasattr(func, '_dataflow_category'):
                return func._dataflow_category
        return "default"  # 未声明 category 的函数

    raise ValueError(f"Method '{method}' not found in any category")

def get_vendor(category: str, method: str | None = None) -> str:
    """Get the configured vendor for a data category or specific tool method.
    Tool-level configuration takes precedence over category-level.

    Fallback: 使用 config 中的 'default' vendor，否则返回 'yfinance'。
    """
    config = get_config()

    # Check tool-level configuration first (if method provided)
    if method:
        tool_vendors = config.get("tool_vendors", {})
        if method in tool_vendors:
            return tool_vendors[method]

    # Fall back to category-level configuration
    data_vendors = config.get("data_vendors", {})
    if category in data_vendors:
        return data_vendors[category]

    # Default fallback（新增）
    if "default" in data_vendors:
        return data_vendors["default"]

    return "yfinance"  # 系统默认

def route_to_vendor(method: str, *args, **kwargs):
    """Route method calls to appropriate vendor implementation with fallback support."""
    category = get_category_for_method(method)
    vendor_config = get_vendor(category, method)
    primary_vendors = [v.strip() for v in vendor_config.split(',')]

    # Ensure external vendors are loaded before routing
    for vendor in primary_vendors:
        _ensure_vendor_loaded(vendor)

    if method not in _VENDOR_REGISTRY:
        raise ValueError(f"Method '{method}' not supported")

    # Build fallback chain: primary vendors first, then remaining available vendors
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
            continue  # Only rate limits trigger fallback

    raise RuntimeError(f"No available vendor for '{method}'")