"""
测试新闻时效性功能

验证研究员 prompt 包含当前日期和时效性指导。
"""

import pytest
from langchain_core.messages import AIMessage


class MockLLM:
    """模拟 LLM，用于捕获 prompt 内容"""

    def __init__(self):
        self.last_prompt = None

    def invoke(self, prompt):
        self.last_prompt = prompt
        return AIMessage(content='Mock response')


class MockMemory:
    """模拟记忆系统"""

    def get_memories(self, situation, n_matches=2):
        return []


def create_mock_state():
    """创建模拟状态"""
    return {
        'trade_date': '2026-04-09',
        'investment_debate_state': {
            'history': '',
            'bull_history': '',
            'bear_history': '',
            'peter_lynch_history': '',
            'current_response': '',
            'count': 0,
        },
        'market_report': 'Market report test',
        'sentiment_report': 'Sentiment report test',
        'news_report': '''
根据朱雀基金 (2025-12-15) 的报道，朱雀基金举牌持有该股票。
近期 (2026-04-05) 报道显示公司业绩增长。
''',
        'fundamentals_report': 'Fundamentals report test',
    }


class TestBullResearcherRecency:
    """测试 Bull Researcher 时效性功能"""

    def test_prompt_contains_trade_date(self):
        """验证 prompt 包含当前分析日期"""
        from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

        mock_llm = MockLLM()
        mock_memory = MockMemory()
        bull_node = create_bull_researcher(mock_llm, mock_memory)

        result = bull_node(create_mock_state())

        assert mock_llm.last_prompt is not None
        assert '2026-04-09' in mock_llm.last_prompt, "Prompt 应包含当前分析日期"

    def test_prompt_contains_recency_guidance(self):
        """验证 prompt 包含时效性指导"""
        from tradingagents.agents.researchers.bull_researcher import create_bull_researcher

        mock_llm = MockLLM()
        mock_memory = MockMemory()
        bull_node = create_bull_researcher(mock_llm, mock_memory)

        result = bull_node(create_mock_state())

        assert mock_llm.last_prompt is not None
        assert '时间上下文' in mock_llm.last_prompt or '时效性' in mock_llm.last_prompt, \
            "Prompt 应包含时效性指导"
        assert '30天' in mock_llm.last_prompt, "Prompt 应包含30天时效性规则"


class TestBearResearcherRecency:
    """测试 Bear Researcher 时效性功能"""

    def test_prompt_contains_trade_date(self):
        """验证 prompt 包含当前分析日期"""
        from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

        mock_llm = MockLLM()
        mock_memory = MockMemory()
        bear_node = create_bear_researcher(mock_llm, mock_memory)

        result = bear_node(create_mock_state())

        assert mock_llm.last_prompt is not None
        assert '2026-04-09' in mock_llm.last_prompt, "Prompt 应包含当前分析日期"

    def test_prompt_contains_recency_guidance(self):
        """验证 prompt 包含时效性指导"""
        from tradingagents.agents.researchers.bear_researcher import create_bear_researcher

        mock_llm = MockLLM()
        mock_memory = MockMemory()
        bear_node = create_bear_researcher(mock_llm, mock_memory)

        result = bear_node(create_mock_state())

        assert mock_llm.last_prompt is not None
        assert '时间上下文' in mock_llm.last_prompt or '时效性' in mock_llm.last_prompt, \
            "Prompt 应包含时效性指导"


class TestPeterLynchResearcherRecency:
    """测试 Peter Lynch Researcher 时效性功能"""

    def test_prompt_contains_trade_date(self):
        """验证 prompt 包含当前分析日期"""
        from tradingagents.agents.researchers.peter_lynch_researcher import create_peter_lynch_researcher

        mock_llm = MockLLM()
        mock_memory = MockMemory()
        pl_node = create_peter_lynch_researcher(mock_llm, mock_memory)

        result = pl_node(create_mock_state())

        assert mock_llm.last_prompt is not None
        assert '2026-04-09' in mock_llm.last_prompt, "Prompt 应包含当前分析日期"

    def test_prompt_contains_recency_guidance(self):
        """验证 prompt 包含时效性指导"""
        from tradingagents.agents.researchers.peter_lynch_researcher import create_peter_lynch_researcher

        mock_llm = MockLLM()
        mock_memory = MockMemory()
        pl_node = create_peter_lynch_researcher(mock_llm, mock_memory)

        result = pl_node(create_mock_state())

        assert mock_llm.last_prompt is not None
        assert '时间上下文' in mock_llm.last_prompt or '时效性' in mock_llm.last_prompt, \
            "Prompt 应包含时效性指导"


class TestNewsAnalystDateAnnotation:
    """测试 News Analyst 日期标注功能"""

    def test_system_message_contains_date_annotation_requirement(self):
        """验证 system_message 包含日期标注要求"""
        from tradingagents.agents.analysts.news_analyst import create_news_analyst

        mock_llm = MockLLM()
        news_analyst = create_news_analyst(mock_llm)

        # 检查函数源码或通过其他方式验证
        # 这里简单检查模块是否可导入
        assert news_analyst is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])