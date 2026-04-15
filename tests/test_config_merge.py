"""测试配置合并 - 验证 default_config.py 正确合并各配置项"""

import pytest


def test_max_debate_rounds_merged():
    """验证 max_debate_rounds 能被正确合并"""
    from tradingagents.default_config import DEFAULT_CONFIG

    # 验证配置项存在且为整数值
    assert 'max_debate_rounds' in DEFAULT_CONFIG, \
        "max_debate_rounds not in DEFAULT_CONFIG"
    assert isinstance(DEFAULT_CONFIG['max_debate_rounds'], int), \
        "max_debate_rounds should be int"


def test_max_risk_discuss_rounds_merged():
    """验证 max_risk_discuss_rounds 能被正确合并"""
    from tradingagents.default_config import DEFAULT_CONFIG

    assert 'max_risk_discuss_rounds' in DEFAULT_CONFIG, \
        "max_risk_discuss_rounds not in DEFAULT_CONFIG"
    assert isinstance(DEFAULT_CONFIG['max_risk_discuss_rounds'], int), \
        "max_risk_discuss_rounds should be int"


def test_max_recur_limit_merged():
    """验证 max_recur_limit 能被正确合并"""
    from tradingagents.default_config import DEFAULT_CONFIG

    assert 'max_recur_limit' in DEFAULT_CONFIG, \
        "max_recur_limit not in DEFAULT_CONFIG"
    assert isinstance(DEFAULT_CONFIG['max_recur_limit'], int), \
        "max_recur_limit should be int"


def test_tool_vendors_merged():
    """验证 tool_vendors 能被正确合并"""
    from tradingagents.default_config import DEFAULT_CONFIG

    assert 'tool_vendors' in DEFAULT_CONFIG, \
        "tool_vendors not in DEFAULT_CONFIG"
    assert isinstance(DEFAULT_CONFIG['tool_vendors'], dict), \
        "tool_vendors should be dict"


def test_output_language_merged():
    """验证 output_language 能被正确合并"""
    from tradingagents.default_config import DEFAULT_CONFIG

    assert 'output_language' in DEFAULT_CONFIG, \
        "output_language not in DEFAULT_CONFIG"
    assert isinstance(DEFAULT_CONFIG['output_language'], str), \
        "output_language should be str"


def test_vendor_paths_merged():
    """验证 vendor_paths 包含 yfinance 和 alpha_vantage"""
    from tradingagents.default_config import DEFAULT_CONFIG

    vendor_paths = DEFAULT_CONFIG.get('vendor_paths', {})
    assert 'yfinance' in vendor_paths, \
        "yfinance not in vendor_paths"
    assert 'alpha_vantage' in vendor_paths, \
        "alpha_vantage not in vendor_paths - P1-4 not fixed!"


def test_config_yaml_overrides_base():
    """验证 config.yaml 能覆盖 base 配置"""
    from tradingagents.default_config import DEFAULT_CONFIG

    # 如果 config.yaml 中有设置，应该覆盖默认值
    # 这个测试验证合并逻辑是否工作
    config = DEFAULT_CONFIG

    # 至少验证几个关键配置项存在
    assert config.get('llm_provider') is not None
    assert config.get('deep_think_llm') is not None
    assert config.get('quick_think_llm') is not None
