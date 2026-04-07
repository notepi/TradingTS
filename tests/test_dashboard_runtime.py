import unittest
import time
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory

from cli.analysis_runtime import AnalysisBuffer, finalize_buffer
from cli.display_translation import DisplayTranslator
from cli.dashboard import DashboardSession, normalize_dashboard_request, _translation_model
from cli.history_loader import delete_dashboard_run, list_dashboard_runs, load_dashboard_run
from cli.translated_run_materializer import materialize_translated_run
from tradingagents.default_config import DEFAULT_CONFIG


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
            (run_dir / "reports").mkdir(parents=True)
            (run_dir / "2_research" / "manager.md").write_text(
                "### Research Manager Decision\nBull Analyst: Hello",
                encoding="utf-8",
            )
            (run_dir / "reports" / "investment_plan.md").write_text(
                "This duplicate report should not be translated",
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
            duplicate_target = run_dir / "translated" / "Chinese" / "reports" / "investment_plan.md"
            self.assertFalse(duplicate_target.exists())

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

    def test_display_translator_localizes_snapshot_decision_only(self):
        translator = DisplayTranslator(
            output_language="Chinese",
            runtime_enabled=False,
        )

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
        self.assertEqual(localized["current_report"], snapshot["current_report"])
        self.assertEqual(localized["events"][0]["content"], snapshot["events"][0]["content"])

    def test_completed_snapshot_prefers_translated_file_mirror(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            (run_dir / "3_trading").mkdir(parents=True)
            (run_dir / "message_tool.log").write_text(
                "21:46:12 [System] Selected analysts: market, social, news, fundamentals\n",
                encoding="utf-8",
            )
            (run_dir / "3_trading" / "trader.md").write_text(
                "Trader original",
                encoding="utf-8",
            )
            (run_dir / "complete_report.md").write_text(
                "# Original complete report",
                encoding="utf-8",
            )
            translated_dir = run_dir / "translated" / "Chinese" / "3_trading"
            translated_dir.mkdir(parents=True)
            (translated_dir / "trader.md").write_text(
                "交易员中文版本",
                encoding="utf-8",
            )
            translated_root = run_dir / "translated" / "Chinese"
            (translated_root / "complete_report.md").write_text(
                "# 中文完整报告",
                encoding="utf-8",
            )
            (run_dir / "analysis_stats.json").write_text(
                '{"llm_calls": 4, "tool_calls": 1, "tokens_in": 100, "tokens_out": 30}',
                encoding="utf-8",
            )
            (run_dir / "translation_stats.json").write_text(
                '{"translation_calls": 1, "translation_tokens_in": 40, "translation_tokens_out": 22, "translation_documents": 1, "translation_failures": 0, "enabled": true, "language": "Chinese"}',
                encoding="utf-8",
            )

            session = DashboardSession()
            session._display_translator = DisplayTranslator(output_language="Chinese", runtime_enabled=False)
            selections = {
                "ticker": "688333.SH",
                "analysis_date": "2026-04-05",
                "analysts": ["market", "social", "news", "fundamentals"],
                "research_depth": 1,
                "llm_provider": "dashscope",
                "backend_url": "https://coding.dashscope.aliyuncs.com/v1",
                "quick_think_llm": "glm-5",
                "deep_think_llm": "glm-5",
                "output_language": "Chinese",
            }

            with patch.dict(DEFAULT_CONFIG, {"results_dir": str(root)}, clear=False):
                snapshot = session._build_file_backed_snapshot(run_dir, selections)

            self.assertFalse(snapshot["history_loaded"])
            self.assertEqual(snapshot["current_report"], "### Trading Team Plan\n交易员中文版本")
            self.assertEqual(snapshot["final_report"], "# 中文完整报告")
            self.assertEqual(snapshot["report_sections"]["trader_investment_plan"], "交易员中文版本")

    def test_snapshot_prefers_loaded_history_when_not_running(self):
        session = DashboardSession()
        session._status = "stopped"
        session._historical_snapshot = {
            "status": "completed",
            "counts": {"agents_completed": 12, "agents_total": 12},
            "workflow": [{"id": "research", "status": "completed"}],
            "current_agent": "Portfolio Manager",
            "decision": "BUY",
            "history_loaded": True,
        }

        snapshot = session.snapshot()

        self.assertEqual(snapshot["status"], "completed")
        self.assertEqual(snapshot["counts"]["agents_completed"], 12)
        self.assertEqual(snapshot["current_agent"], "Portfolio Manager")
        self.assertTrue(snapshot["history_loaded"])

    def test_runtime_member_output_writes_translated_member_file_for_analyst(self):
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            session = DashboardSession()
            translator = DisplayTranslator(output_language="Chinese", runtime_enabled=False)
            translator.translate_document = lambda text, force=False: "市场报告中文版本"
            session._display_translator = translator

            session._sync_runtime_member_outputs(
                run_dir=run_dir,
                chunk={"market_report": "Market report original"},
            )

            original_path = run_dir / "1_analysts" / "market.md"
            translated_path = run_dir / "translated" / "Chinese" / "1_analysts" / "market.md"

            self.assertEqual(original_path.read_text(encoding="utf-8"), "Market report original")

            deadline = time.time() + 1.0
            while time.time() < deadline and not translated_path.exists():
                time.sleep(0.01)

            self.assertTrue(translated_path.exists())
            self.assertEqual(
                translated_path.read_text(encoding="utf-8"),
                "市场报告中文版本",
            )

    def test_runtime_member_translation_deduplicates_same_content(self):
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            session = DashboardSession()
            translator = DisplayTranslator(output_language="Chinese", runtime_enabled=False)
            calls = []

            def fake_translate(text, force=False):
                calls.append(text)
                return "同一篇译文"

            translator.translate_document = fake_translate
            session._display_translator = translator

            session._sync_runtime_member_outputs(
                run_dir=run_dir,
                chunk={"market_report": "Same content"},
            )
            session._sync_runtime_member_outputs(
                run_dir=run_dir,
                chunk={"market_report": "Same content"},
            )

            deadline = time.time() + 1.0
            translated_path = run_dir / "translated" / "Chinese" / "1_analysts" / "market.md"
            while time.time() < deadline and not translated_path.exists():
                time.sleep(0.01)

            self.assertEqual(calls, ["Same content"])

    def test_runtime_member_outputs_waits_for_research_team_completion(self):
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            session = DashboardSession()
            translator = DisplayTranslator(output_language="Chinese", runtime_enabled=False)
            calls = []

            def fake_translate(text, force=False):
                calls.append(text)
                return f"ZH:{text}"

            translator.translate_document = fake_translate
            session._display_translator = translator

            session._sync_runtime_member_outputs(
                run_dir=run_dir,
                chunk={
                    "investment_debate_state": {
                        "bull_history": "Bull round 1",
                        "bear_history": "",
                        "judge_decision": "",
                    }
                },
            )

            self.assertFalse((run_dir / "2_research" / "bull.md").exists())
            self.assertEqual(calls, [])

    def test_runtime_member_outputs_write_research_files_on_manager_completion(self):
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            session = DashboardSession()
            translator = DisplayTranslator(output_language="Chinese", runtime_enabled=False)
            translator.translate_document = lambda text, force=False: f"ZH:{text}"
            session._display_translator = translator

            session._sync_runtime_member_outputs(
                run_dir=run_dir,
                chunk={
                    "investment_debate_state": {
                        "bull_history": "Bull final",
                        "bear_history": "Bear final",
                        "judge_decision": "Manager final",
                    }
                },
            )

            deadline = time.time() + 1.0
            translated_bull = run_dir / "translated" / "Chinese" / "2_research" / "bull.md"
            while time.time() < deadline and not translated_bull.exists():
                time.sleep(0.01)

            self.assertEqual((run_dir / "2_research" / "bull.md").read_text(encoding="utf-8"), "Bull final")
            self.assertEqual((run_dir / "2_research" / "bear.md").read_text(encoding="utf-8"), "Bear final")
            self.assertEqual((run_dir / "2_research" / "manager.md").read_text(encoding="utf-8"), "Manager final")
            self.assertEqual(translated_bull.read_text(encoding="utf-8"), "ZH:Bull final")

    def test_running_snapshot_prefers_translated_member_file_for_analyst(self):
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            translated_dir = run_dir / "translated" / "Chinese" / "1_analysts"
            translated_dir.mkdir(parents=True)
            (translated_dir / "market.md").write_text("市场报告中文版本", encoding="utf-8")
            (run_dir / "1_analysts").mkdir(parents=True)
            (run_dir / "1_analysts" / "market.md").write_text("Market report original", encoding="utf-8")

            session = DashboardSession()
            snapshot = {
                "current_agent": "Market Analyst",
                "agent_status": {"Market Analyst": "completed"},
                "report_sections": {"market_report": "Market report original"},
                "current_report": "### Market Analysis\nMarket report original",
                "final_report": "## Analyst Team Reports\n\n### Market Analysis\nMarket report original",
                "events": [
                    {
                        "id": 1,
                        "timestamp": "21:00:00",
                        "type": "report",
                        "label": "market_report",
                        "content": "Market report original",
                        "agent": "Market Analyst",
                        "stage_id": "analysts",
                    }
                ],
            }

            localized = session._localize_running_snapshot(
                snapshot,
                run_dir=run_dir,
                language="Chinese",
            )

            self.assertEqual(localized["report_sections"]["market_report"], "市场报告中文版本")
            self.assertEqual(localized["current_report"], "### Market Analysis\n市场报告中文版本")
            self.assertIn("市场报告中文版本", localized["final_report"])
            self.assertEqual(localized["events"][0]["content"], "市场报告中文版本")

    def test_running_snapshot_composes_research_team_from_member_files(self):
        with TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            (run_dir / "2_research").mkdir(parents=True)
            (run_dir / "2_research" / "bull.md").write_text("Bull final", encoding="utf-8")
            (run_dir / "2_research" / "bear.md").write_text("Bear final", encoding="utf-8")
            translated_dir = run_dir / "translated" / "Chinese" / "2_research"
            translated_dir.mkdir(parents=True)
            (translated_dir / "bull.md").write_text("多头终稿", encoding="utf-8")

            session = DashboardSession()
            snapshot = {
                "current_agent": "Bear Researcher",
                "agent_status": {
                    "Bull Researcher": "completed",
                    "Bear Researcher": "in_progress",
                    "Research Manager": "pending",
                },
                "report_sections": {
                    "investment_plan": "### Bear Researcher Analysis\nBear partial",
                },
                "current_report": "### Research Team Decision\n### Bear Researcher Analysis\nBear partial",
                "final_report": "## Research Team Decision\n\n### Bear Researcher Analysis\nBear partial",
                "events": [
                    {
                        "id": 1,
                        "timestamp": "21:00:00",
                        "type": "report",
                        "label": "investment_plan",
                        "content": "### Bull Researcher Analysis\nBull partial",
                        "agent": "Bull Researcher",
                        "stage_id": "research",
                    },
                    {
                        "id": 2,
                        "timestamp": "21:01:00",
                        "type": "report",
                        "label": "investment_plan",
                        "content": "### Bear Researcher Analysis\nBear partial",
                        "agent": "Bear Researcher",
                        "stage_id": "research",
                    },
                ],
            }

            localized = session._localize_running_snapshot(
                snapshot,
                run_dir=run_dir,
                language="Chinese",
            )

            self.assertEqual(
                localized["report_sections"]["investment_plan"],
                "### Bull Researcher Analysis\n多头终稿\n\n### Bear Researcher Analysis\nBear final",
            )
            self.assertEqual(
                localized["events"][0]["content"],
                "### Bull Researcher Analysis\n多头终稿",
            )
            self.assertEqual(
                localized["events"][1]["content"],
                "### Bear Researcher Analysis\nBear final",
            )
            self.assertIn("多头终稿", localized["final_report"])

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

    def test_display_translator_tracks_usage_stats(self):
        translator = DisplayTranslator(output_language="Chinese", runtime_enabled=False)
        translator._llm = SimpleNamespace(
            invoke=lambda prompt: SimpleNamespace(
                content="研究经理决策",
                usage_metadata={"input_tokens": 12, "output_tokens": 8},
            )
        )

        translated = translator.translate_document("Research Manager Decision")

        self.assertEqual(translated, "研究经理决策")
        self.assertEqual(
            translator.get_stats()["translation_documents"],
            1,
        )
        self.assertEqual(translator.get_stats()["translation_calls"], 1)
        self.assertEqual(translator.get_stats()["translation_tokens_in"], 12)
        self.assertEqual(translator.get_stats()["translation_tokens_out"], 8)

    def test_history_loader_reads_analysis_and_translation_stats(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_dir = root / "688333.SH" / "2026-04-05" / "dashboard_20260405_214612"
            (run_dir / "1_analysts").mkdir(parents=True)
            (run_dir / "2_research").mkdir(parents=True)
            (run_dir / "3_trading").mkdir(parents=True)
            (run_dir / "4_risk").mkdir(parents=True)
            (run_dir / "5_portfolio").mkdir(parents=True)
            (run_dir / "message_tool.log").write_text(
                "21:46:12 [System] Selected analysts: market, social, news, fundamentals\n",
                encoding="utf-8",
            )
            (run_dir / "1_analysts" / "market.md").write_text("市场报告", encoding="utf-8")
            (run_dir / "2_research" / "bull.md").write_text("多头观点", encoding="utf-8")
            (run_dir / "2_research" / "bear.md").write_text("空头观点", encoding="utf-8")
            (run_dir / "2_research" / "manager.md").write_text("研究结论", encoding="utf-8")
            (run_dir / "3_trading" / "trader.md").write_text("交易计划", encoding="utf-8")
            (run_dir / "5_portfolio" / "decision.md").write_text("**Rating**: **Sell**", encoding="utf-8")
            (run_dir / "complete_report.md").write_text("# 完整报告", encoding="utf-8")
            (run_dir / "analysis_stats.json").write_text(
                '{"llm_calls": 18, "tool_calls": 9, "tokens_in": 1200, "tokens_out": 480}',
                encoding="utf-8",
            )
            (run_dir / "translation_stats.json").write_text(
                '{"translation_calls": 4, "translation_tokens_in": 200, "translation_tokens_out": 90, "translation_documents": 3, "translation_failures": 0, "enabled": true, "language": "Chinese"}',
                encoding="utf-8",
            )

            snapshot = load_dashboard_run("688333.SH/2026-04-05/dashboard_20260405_214612", root)

            self.assertEqual(snapshot["stats"]["llm_calls"], 18)
            self.assertEqual(snapshot["stats"]["tokens_in"], 1200)
            self.assertEqual(snapshot["translation_stats"]["translation_calls"], 4)
            self.assertEqual(snapshot["translation_stats"]["translation_documents"], 3)


if __name__ == "__main__":
    unittest.main()
