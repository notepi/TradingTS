import unittest

from cli.analysis_runtime import AnalysisBuffer, finalize_buffer
from cli.display_translation import DisplayTranslator
from cli.dashboard import normalize_dashboard_request


class DashboardRuntimeTests(unittest.TestCase):
    def test_buffer_snapshot_filters_selected_analysts(self):
        buffer = AnalysisBuffer()
        buffer.init_for_analysis(["market", "news"])

        snapshot = buffer.snapshot()
        workflow = {stage["id"]: stage for stage in snapshot["workflow"]}

        self.assertEqual(
            [agent["name"] for agent in workflow["analysts"]["agents"]],
            ["Market Analyst", "News Analyst"],
        )
        self.assertEqual(workflow["research"]["status"], "pending")

    def test_finalize_buffer_builds_final_report(self):
        buffer = AnalysisBuffer()
        buffer.init_for_analysis(["market"])

        final_state = {
            "market_report": "Market outlook",
            "investment_plan": "Research plan",
            "trader_investment_plan": "Trader plan",
            "final_trade_decision": "Portfolio manager says hold",
        }

        finalize_buffer(buffer, final_state)
        snapshot = buffer.snapshot()

        self.assertIn("Analyst Team Reports", snapshot["final_report"])
        self.assertIn("Portfolio Management Decision", snapshot["final_report"])
        self.assertEqual(snapshot["counts"]["agents_completed"], snapshot["counts"]["agents_total"])

    def test_snapshot_exposes_current_stage_metadata(self):
        buffer = AnalysisBuffer()
        buffer.init_for_analysis(["market", "news"])
        buffer.update_agent_status("Market Analyst", "in_progress")
        buffer.add_message("Agent", "Analyzing price structure")

        snapshot = buffer.snapshot()

        self.assertEqual(snapshot["current_agent"], "Market Analyst")
        self.assertEqual(snapshot["current_stage_id"], "analysts")
        self.assertEqual(snapshot["current_stage_title"], "Analyst Team")
        self.assertEqual(snapshot["current_focus_event"]["agent"], "Market Analyst")
        self.assertEqual(snapshot["current_focus_event"]["content"], "Analyzing price structure")

    def test_dashboard_request_normalizes_a_share_input(self):
        normalized = normalize_dashboard_request(
            {
                "ticker": "600519",
                "analysis_date": "2025-04-02",
                "analysts": ["market", "fundamentals"],
                "research_depth": 1,
                "llm_provider": "dashscope",
                "quick_think_llm": "glm-5",
                "deep_think_llm": "glm-5",
                "output_language": "Chinese",
            }
        )

        self.assertEqual(normalized["ticker"], "600519.SH")
        self.assertEqual(normalized["analysts"], ["market", "fundamentals"])
        self.assertEqual(normalized["llm_provider"], "dashscope")

    def test_dashboard_request_rejects_invalid_analyst(self):
        with self.assertRaises(ValueError):
            normalize_dashboard_request(
                {
                    "ticker": "600519.SH",
                    "analysis_date": "2025-04-02",
                    "analysts": ["market", "macro"],
                    "research_depth": 1,
                    "llm_provider": "dashscope",
                    "quick_think_llm": "glm-5",
                    "deep_think_llm": "glm-5",
                }
            )

    def test_display_translator_localizes_snapshot_from_cache(self):
        translator = DisplayTranslator(
            output_language="Chinese",
            runtime_enabled=False,
        )
        translator._cache["### Bull Researcher Analysis\nBull Analyst: Hello"] = (
            "### 多头研究员分析\n多头分析师：你好"
        )
        translator._cache["Bull Analyst: Hello"] = "多头分析师：你好"

        snapshot = {
            "decision": "SELL",
            "current_report": "### Bull Researcher Analysis\nBull Analyst: Hello",
            "events": [
                {
                    "id": 1,
                    "content": "Bull Analyst: Hello",
                    "type": "message",
                }
            ],
            "process_tree": [
                {
                    "agents": [
                        {
                            "events": [
                                {
                                    "id": 1,
                                    "content": "Bull Analyst: Hello",
                                    "type": "message",
                                }
                            ]
                        }
                    ]
                }
            ],
        }

        localized = translator.localize_snapshot(snapshot)

        self.assertEqual(localized["decision"], "卖出")
        self.assertEqual(
            localized["current_report"],
            "### 多头研究员分析\n多头分析师：你好",
        )
        self.assertEqual(localized["events"][0]["content"], "多头分析师：你好")
        self.assertEqual(
            localized["process_tree"][0]["agents"][0]["events"][0]["content"],
            "多头分析师：你好",
        )


if __name__ == "__main__":
    unittest.main()
