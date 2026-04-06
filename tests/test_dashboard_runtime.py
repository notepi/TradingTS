import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from cli.analysis_runtime import AnalysisBuffer, finalize_buffer
from cli.display_translation import DisplayTranslator
from cli.dashboard import normalize_dashboard_request, _translation_model
from cli.history_loader import delete_dashboard_run, list_dashboard_runs, load_dashboard_run
from cli.translated_run_materializer import materialize_translated_run


class DashboardRuntimeTests(unittest.TestCase):
    def test_history_loader_lists_dashboard_runs(self):
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            run_dir.mkdir(parents=True)
            (run_dir / "message_tool.log").write_text(
                "21:46:12 [System] Selected analysts: market, social, news, fundamentals\n",
                encoding="utf-8",
            )
            (run_dir / "complete_report.md").write_text("# done", encoding="utf-8")

            runs = list_dashboard_runs(run_dir.parents[2])

            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["ticker"], "688333.SH")
            self.assertEqual(runs[0]["status"], "completed")

    def test_history_loader_deletes_run_directory(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            run_dir.mkdir(parents=True)
            (run_dir / "message_tool.log").write_text("x", encoding="utf-8")

            delete_dashboard_run("688333.SH/2026-04-05/dashboard_20260405_214612", root)

            self.assertFalse(run_dir.exists())

    def test_history_loader_builds_snapshot_from_results(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            (run_dir / "1_analysts").mkdir(parents=True)
            (run_dir / "2_research").mkdir(parents=True)
            (run_dir / "3_trading").mkdir(parents=True)
            (run_dir / "4_risk").mkdir(parents=True)
            (run_dir / "5_portfolio").mkdir(parents=True)
            (run_dir / "message_tool.log").write_text(
                "\n".join(
                    [
                        "21:46:12 [System] Selected analysts: market, social, news, fundamentals",
                        "21:46:30 [Agent] 技术分析开始",
                        "21:46:31 [Tool Call] get_stock_data(symbol=688333.SH)",
                    ]
                ),
                encoding="utf-8",
            )
            (run_dir / "1_analysts" / "market.md").write_text("市场报告", encoding="utf-8")
            (run_dir / "2_research" / "bull.md").write_text("多头观点", encoding="utf-8")
            (run_dir / "2_research" / "bear.md").write_text("空头观点", encoding="utf-8")
            (run_dir / "2_research" / "manager.md").write_text("研究结论", encoding="utf-8")
            (run_dir / "3_trading" / "trader.md").write_text("交易计划", encoding="utf-8")
            (run_dir / "5_portfolio" / "decision.md").write_text("**Rating**: **Sell**", encoding="utf-8")
            (run_dir / "complete_report.md").write_text("# 完整报告", encoding="utf-8")

            snapshot = load_dashboard_run("688333.SH/2026-04-05/dashboard_20260405_214612", root)

            self.assertEqual(snapshot["status"], "completed")
            self.assertEqual(snapshot["decision"], "SELL")
            self.assertEqual(snapshot["selections"]["ticker"], "688333.SH")
            self.assertIn("market_report", snapshot["report_sections"])
            self.assertEqual(snapshot["report_sections"]["market_report"], "市场报告")
            self.assertTrue(snapshot["history_loaded"])
            research_stage = next(stage for stage in snapshot["process_tree"] if stage["id"] == "research")
            research_events = {agent["name"]: len(agent["events"]) for agent in research_stage["agents"]}
            self.assertGreaterEqual(research_events["Bull Researcher"], 1)
            self.assertGreaterEqual(research_events["Bear Researcher"], 1)
            self.assertGreaterEqual(research_events["Research Manager"], 1)

    def test_history_loader_prefers_translated_file_mirror(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            (run_dir / "2_research").mkdir(parents=True)
            (run_dir / "3_trading").mkdir(parents=True)
            (run_dir / "message_tool.log").write_text(
                "21:46:12 [System] Selected analysts: market, social, news, fundamentals\n",
                encoding="utf-8",
            )
            (run_dir / "2_research" / "manager.md").write_text(
                "Research manager original",
                encoding="utf-8",
            )
            translated_dir = run_dir / "translated" / "Chinese" / "2_research"
            translated_dir.mkdir(parents=True)
            (translated_dir / "manager.md").write_text(
                "研究经理中文版本",
                encoding="utf-8",
            )

            snapshot = load_dashboard_run(
                "688333.SH/2026-04-05/dashboard_20260405_214612",
                root,
                language="Chinese",
            )

            self.assertIn("研究经理中文版本", snapshot["events"][-1]["content"])

    def test_materialize_translated_run_writes_file_mirror(self):
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            (run_dir / "2_research").mkdir(parents=True)
            (run_dir / "2_research" / "manager.md").write_text(
                "### Research Manager Decision\nBull Analyst: Hello",
                encoding="utf-8",
            )

            translator = DisplayTranslator(output_language="Chinese", runtime_enabled=False)
            translator._cache["### Research Manager Decision\nBull Analyst: Hello"] = (
                "### 研究经理决策\n多头分析师：你好"
            )

            written = materialize_translated_run(run_dir, "Chinese", translator)

            target = run_dir / "translated" / "Chinese" / "2_research" / "manager.md"
            self.assertIn(target, written)
            self.assertEqual(
                target.read_text(encoding="utf-8"),
                "### 研究经理决策\n多头分析师：你好",
            )

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
                    "label": "Agent",
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
                                    "label": "Agent",
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

    def test_translation_model_prefers_env_override(self):
        with patch.dict("os.environ", {"TRANSLATION_MODEL": "glm-4.7-flash"}, clear=False):
            selected = _translation_model(
                "dashscope",
                {"quick_think_llm": "glm-5"},
            )

        self.assertEqual(selected, "glm-4.7-flash")

    def test_display_translator_exposes_last_error(self):
        translator = DisplayTranslator(output_language="Chinese", runtime_enabled=False)
        translator._last_error = "Document translation failed: boom"

        self.assertEqual(translator.last_error, "Document translation failed: boom")


if __name__ == "__main__":
    unittest.main()
