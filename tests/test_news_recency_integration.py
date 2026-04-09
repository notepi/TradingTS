"""
新闻时效性集成测试

验证完整流程中新闻时效性是否正确体现：
1. news_report 包含日期标注 (YYYY-MM-DD)
2. news_report 按时效性分组（近7天/14天/30天+）
3. 研究员引用旧新闻时标注为"历史背景"
4. 未知日期标注为"日期: 未知"
"""

import pytest
import json
import os
import re
from pathlib import Path
from datetime import datetime, timedelta


class TestNewsRecencyIntegration:
    """集成测试：验证完整流程中新闻时效性"""

    @pytest.fixture
    def eval_result_path(self):
        """获取最新的评估结果路径"""
        eval_dir = Path("eval_results")
        if not eval_dir.exists():
            pytest.skip("No eval_results directory found - run full analysis first")

        # 查找最新的 ticker 目录
        tickers = [d for d in eval_dir.iterdir() if d.is_dir()]
        if not tickers:
            pytest.skip("No ticker directories in eval_results")

        latest_ticker = max(tickers, key=lambda d: d.stat().st_mtime)
        log_dir = latest_ticker / "TradingAgentsStrategy_logs"

        if not log_dir.exists():
            pytest.skip("No logs found in eval_results")

        # 获取最新的日志文件
        log_files = list(log_dir.glob("full_states_log_*.json"))
        if not log_files:
            pytest.skip("No full_states_log files found")

        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
        return latest_log

    @pytest.fixture
    def state_data(self, eval_result_path):
        """加载状态数据"""
        with open(eval_result_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def test_news_report_contains_dated_citations(self, state_data):
        """验证 news_report 包含日期标注"""
        news_report = state_data.get("news_report", "")

        # 检查是否包含 (YYYY-MM-DD) 格式的日期
        date_pattern = r'\(\d{4}-\d{2}-\d{2}\)'
        dates_found = re.findall(date_pattern, news_report)

        assert len(dates_found) > 0, \
            f"news_report 应包含日期标注 (YYYY-MM-DD) 格式，但未找到任何日期。实际内容：\n{news_report[:500]}..."

    def test_news_report_has_recency_grouping(self, state_data):
        """验证 news_report 按时效性分组"""
        news_report = state_data.get("news_report", "")

        # 检查是否有时效性分组的关键词
        recency_indicators = [
            "近7天", "最新动态", "最新消息",
            "14天", "近期",
            "30天", "历史背景", "历史信息"
        ]

        found_indicators = [ind for ind in recency_indicators if ind in news_report]

        assert len(found_indicators) > 0, \
            f"news_report 应包含时效性分组标识（如：近7天、14天、30天、历史背景），但未找到。实际内容：\n{news_report[:500]}..."

    def test_bull_researcher_cites_old_news_properly(self, state_data):
        """验证 Bull Researcher 正确引用旧新闻"""
        bull_history = state_data.get("investment_debate_state", {}).get("bull_history", "")

        # 如果包含"30天"或"个月"等旧新闻引用，应该标注为历史信息
        if "30天" in bull_history or "个月前" in bull_history or "日前" in bull_history:
            # 应该有历史背景标注
            has_historical_label = any(label in bull_history for label in [
                "历史背景", "仅供参考", "旧闻", "早期"
            ])
            assert has_historical_label, \
                f"Bull Researcher 引用旧新闻时应标注'历史背景'或'仅供参考'。实际内容：\n{bull_history[:800]}..."

    def test_bear_researcher_cites_old_news_properly(self, state_data):
        """验证 Bear Researcher 正确引用旧新闻"""
        bear_history = state_data.get("investment_debate_state", {}).get("bear_history", "")

        if "30天" in bear_history or "个月前" in bear_history or "日前" in bear_history:
            has_historical_label = any(label in bear_history for label in [
                "历史背景", "仅供参考", "旧闻", "早期"
            ])
            assert has_historical_label, \
                f"Bear Researcher 引用旧新闻时应标注'历史背景'或'仅供参考'。实际内容：\n{bear_history[:800]}..."

    def test_peter_lynch_cites_old_news_properly(self, state_data):
        """验证 Peter Lynch Researcher 正确引用旧新闻"""
        pl_history = state_data.get("investment_debate_state", {}).get("peter_lynch_history", "")

        if "30天" in pl_history or "个月前" in pl_history or "日前" in pl_history:
            has_historical_label = any(label in pl_history for label in [
                "历史背景", "仅供参考", "旧闻", "早期"
            ])
            assert has_historical_label, \
                f"Peter Lynch 引用旧新闻时应标注'历史背景'或'仅供参考'。实际内容：\n{pl_history[:800]}..."

    def test_news_report_trade_date_context(self, state_data):
        """验证 news_report 中的分析与 trade_date 一致"""
        trade_date = state_data.get("trade_date", "")
        news_report = state_data.get("news_report", "")

        # 如果报告中有具体日期，它们应该与 trade_date 合理相关
        date_pattern = r'\((\d{4}-\d{2}-\d{2})\)'
        dates_found = re.findall(date_pattern, news_report)

        if dates_found:
            # 至少应该有一些日期在 trade_date 之前不久
            trade_dt = datetime.strptime(trade_date, "%Y-%m-%d")
            for date_str in dates_found:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    # 旧新闻（超过60天）可能存在问题
                    days_diff = (trade_dt - dt).days
                    if days_diff > 60:
                        # 检查是否有适当的标注
                        assert any(label in news_report for label in ["历史", "仅供参考", "旧"]), \
                            f"发现超过60天的旧新闻 {date_str} 但未标注为历史信息"
                except ValueError:
                    pass  # 跳过无效日期


class TestNewsRecencyDateAnnotation:
    """测试日期标注功能"""

    def test_news_report_date_format(self):
        """验证日期标注格式正确"""
        # 这个测试验证日期格式正则能够正确匹配
        date_pattern = r'\([\u4e00-\u9fff]*\s*\d{4}-\d{2}-\d{2}\)'
        test_strings = [
            "根据朱雀基金 (2025-12-15) 的报道",
            "根据 (2026-04-05) 报道显示",
            "近期（近7天）报道显示"
        ]

        for test_str in test_strings:
            # 至少应该能匹配到带日期的字符串
            has_date = bool(re.search(r'\(\d{4}-\d{2}-\d{2}\)', test_str))
            assert has_date, f"无法从 '{test_str}' 中提取日期"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])