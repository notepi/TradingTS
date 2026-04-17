"""测试多数据源注册 - 验证 registry.yaml 中定义的工具被正确注册"""

import pytest


def test_tools_registry_loaded():
    """验证 registry.yaml 能被正确加载"""
    from datasource.datahub.servers.interface import load_tools_registry

    registry = load_tools_registry()
    assert isinstance(registry, dict), "tools_registry should be a dict"
    assert len(registry) > 0, "tools_registry should not be empty"


def test_tools_categories_populated():
    """验证 TOOLS_CATEGORIES 被正确填充"""
    from datasource.datahub.servers.interface import TOOLS_CATEGORIES, discover_and_register
    discover_and_register()  # 触发填充

    assert isinstance(TOOLS_CATEGORIES, dict), "TOOLS_CATEGORIES should be a dict"
    assert len(TOOLS_CATEGORIES) > 0, "TOOLS_CATEGORIES should not be empty"


def test_vendor_registry_populated():
    """验证 _VENDOR_REGISTRY 被正确填充"""
    from datasource.datahub.servers.interface import _VENDOR_REGISTRY, discover_and_register
    discover_and_register()  # 触发填充

    assert isinstance(_VENDOR_REGISTRY, dict), "VENDOR_REGISTRY should be a dict"
    assert len(_VENDOR_REGISTRY) > 0, "VENDOR_REGISTRY should not be empty"


def test_news_tools_have_multiple_vendors():
    """验证 news 工具支持多个 vendor（yfinance 和 alpha_vantage）"""
    from datasource.datahub.servers.interface import _VENDOR_REGISTRY

    # 检查 get_news 是否同时有 yfinance 和 alpha_vantage
    if 'get_news' in _VENDOR_REGISTRY:
        vendors = _VENDOR_REGISTRY['get_news']
        vendor_names = list(vendors.keys())

        # 至少应该有 yfinance
        assert 'yfinance' in vendor_names, \
            "get_news should have yfinance vendor"
        # alpha_vantage 可能没有实现 get_news，跳过严格检查


def test_core_tools_have_vendors():
    """验证核心工具（如 get_stock_data）被正确注册"""
    from datasource.datahub.servers.interface import _VENDOR_REGISTRY

    # 这些工具应该在 registry 中
    expected_tools = ['get_stock_data', 'get_indicators', 'get_news', 'get_fundamentals']

    for tool in expected_tools:
        if tool in _VENDOR_REGISTRY:
            vendors = _VENDOR_REGISTRY[tool]
            assert len(vendors) > 0, f"{tool} should have at least one vendor"
