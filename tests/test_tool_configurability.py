"""测试工具配置化 - 验证 Market/Social/News Analyst 通过 load_agent_tools() 加载工具"""

import pytest


def test_market_analyst_loads_tools_from_config():
    """验证 market_analyst 从配置加载工具"""
    from tradingagents.agents.utils.agent_utils import load_agent_tools

    tools = load_agent_tools("market_analyst")
    tool_names = [t.name for t in tools]

    assert 'get_stock_data' in tool_names, "get_stock_data not in market_analyst tools"
    assert 'get_indicators' in tool_names, "get_indicators not in market_analyst tools"


def test_social_analyst_loads_tools_from_config():
    """验证 social_analyst 从配置加载工具"""
    from tradingagents.agents.utils.agent_utils import load_agent_tools

    tools = load_agent_tools("social_analyst")
    tool_names = [t.name for t in tools]

    assert 'get_news' in tool_names, "get_news not in social_analyst tools"


def test_news_analyst_loads_tools_from_config():
    """验证 news_analyst 从配置加载工具（包含 get_insider_transactions）"""
    from tradingagents.agents.utils.agent_utils import load_agent_tools

    tools = load_agent_tools("news_analyst")
    tool_names = [t.name for t in tools]

    assert 'get_news' in tool_names, "get_news not in news_analyst tools"
    assert 'get_global_news' in tool_names, "get_global_news not in news_analyst tools"
    assert 'get_insider_transactions' in tool_names, \
        "get_insider_transactions not in news_analyst tools - P1-6 bug not fixed!"


def test_fundamentals_analyst_still_works():
    """验证 fundamentals_analyst 仍然使用 load_agent_tools()"""
    from tradingagents.agents.utils.agent_utils import load_agent_tools

    tools = load_agent_tools("fundamentals_analyst")
    tool_names = [t.name for t in tools]

    assert 'get_fundamentals' in tool_names, "get_fundamentals not in fundamentals_analyst tools"
    assert 'get_balance_sheet' in tool_names, "get_balance_sheet not in fundamentals_analyst tools"
    assert 'get_cashflow' in tool_names, "get_cashflow not in fundamentals_analyst tools"
    assert 'get_income_statement' in tool_names, "get_income_statement not in fundamentals_analyst tools"


def test_all_analysts_use_load_agent_tools():
    """验证所有 analyst 都使用 load_agent_tools() 而非硬编码"""
    import inspect
    from tradingagents.agents.analysts import market_analyst, social_media_analyst, news_analyst

    # 检查 market_analyst 源码不包含硬编码的工具列表
    market_source = inspect.getsource(market_analyst.create_market_analyst)
    assert 'load_agent_tools' in market_source, \
        "market_analyst should use load_agent_tools()"
    assert 'get_stock_data,' not in market_source, \
        "market_analyst should not hardcode get_stock_data"
    assert 'get_indicators,' not in market_source, \
        "market_analyst should not hardcode get_indicators"

    # 检查 social_media_analyst 源码
    social_source = inspect.getsource(social_media_analyst.create_social_media_analyst)
    assert 'load_agent_tools' in social_source, \
        "social_media_analyst should use load_agent_tools()"
    assert 'get_news,' not in social_source, \
        "social_media_analyst should not hardcode get_news"

    # 检查 news_analyst 源码
    news_source = inspect.getsource(news_analyst.create_news_analyst)
    assert 'load_agent_tools' in news_source, \
        "news_analyst should use load_agent_tools()"
    assert 'get_news,' not in news_source, \
        "news_analyst should not hardcode get_news"
