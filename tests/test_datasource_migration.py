"""测试数据源迁移 - 验证 yfinance/alpha_vantage 迁移到 datasource/ 后正常工作"""

import pytest


def test_yfinance_datasource_exists():
    """验证 yfinance 数据源存在于 datasource/yfinance/"""
    from datasource import yfinance
    assert hasattr(yfinance, 'get_news')
    assert hasattr(yfinance, 'get_global_news')


def test_alpha_vantage_datasource_exists():
    """验证 alpha_vantage 数据源存在于 datasource/alpha_vantage/"""
    from datasource import alpha_vantage
    assert hasattr(alpha_vantage, 'get_stock_data')
    assert hasattr(alpha_vantage, 'get_indicators')
    assert hasattr(alpha_vantage, 'get_news')
    assert hasattr(alpha_vantage, 'get_global_news')
    assert hasattr(alpha_vantage, 'get_insider_transactions')


def test_discover_and_register_finds_yfinance():
    """验证 discover_and_register 能发现 datasource/yfinance 下的工具"""
    from tradingagents.dataflows import discover_and_register
    discover_and_register()
    from datasource.datahub.servers.interface import _VENDOR_REGISTRY

    # 检查 yfinance 是否在 vendor registry 中
    yfinance_found = False
    for method, vendors in _VENDOR_REGISTRY.items():
        if 'yfinance' in vendors:
            yfinance_found = True
            break

    assert yfinance_found, "yfinance tools not found in vendor registry"


def test_discover_and_register_finds_alpha_vantage():
    """验证 discover_and_register 能发现 datasource/alpha_vantage 下的工具"""
    from tradingagents.dataflows import discover_and_register
    discover_and_register()
    from datasource.datahub.servers.interface import _VENDOR_REGISTRY

    # 检查 alpha_vantage 是否在 vendor registry 中
    alpha_vantage_found = False
    for method, vendors in _VENDOR_REGISTRY.items():
        if 'alpha_vantage' in vendors:
            alpha_vantage_found = True
            break

    assert alpha_vantage_found, "alpha_vantage tools not found in vendor registry"


def test_vendor_paths_config():
    """验证 vendor_paths 配置正确"""
    from datasource.datahub.servers.config import get_config
    config = get_config()

    vendor_paths = config.get('vendor_paths', {})
    assert vendor_paths.get('yfinance') == 'datasource.yfinance', \
        f"yfinance path incorrect: {vendor_paths.get('yfinance')}"
    assert vendor_paths.get('alpha_vantage') == 'datasource.alpha_vantage', \
        f"alpha_vantage path incorrect: {vendor_paths.get('alpha_vantage')}"
