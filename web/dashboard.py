from __future__ import annotations

import datetime
import hashlib
import json
import os
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from rich.console import Console

from web.runtime import (
    ANALYST_AGENT_NAMES,
    ANALYST_ORDER,
    AnalysisBuffer,
    apply_stream_chunk,
    build_process_tree,
    finalize_buffer,
    pick_current_focus_event,
)
from web.history import delete_dashboard_run, list_dashboard_runs, load_dashboard_run
from web.reporting import save_report_to_disk
from web.stats import StatsCallbackHandler
from web.translation import (
    DisplayTranslator,
    load_translated_text,
    materialize_translated_run,
    translated_path,
)
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS, get_model_options


console = Console()
load_dotenv()

PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1",
    "anthropic": "https://api.anthropic.com/",
    "xai": "https://api.x.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "dashscope": "https://coding.dashscope.aliyuncs.com/v1",
    "ollama": "http://localhost:11434/v1",
}
TRANSLATION_MODEL_ENV = "TRANSLATION_MODEL"
OUTPUT_LANGUAGES = [
    "English",
    "Chinese",
    "Japanese",
    "Korean",
    "Hindi",
    "Spanish",
    "Portuguese",
    "French",
    "German",
    "Arabic",
    "Russian",
]
RESEARCH_DEPTH_OPTIONS = [
    {
        "label": "Shallow",
        "value": 1,
        "description": "Quick research with fewer debate rounds.",
    },
    {
        "label": "Medium",
        "value": 3,
        "description": "Balanced debate and strategy depth.",
    },
    {
        "label": "Deep",
        "value": 5,
        "description": "Longer, more comprehensive analysis.",
    },
]
ANALYST_OPTIONS = [
    {"label": "Market Analyst", "value": "market"},
    {"label": "Social Analyst", "value": "social"},
    {"label": "News Analyst", "value": "news"},
    {"label": "Fundamentals Analyst", "value": "fundamentals"},
]
RUNTIME_AGENT_FILE_MAP = {
    "Market Analyst": Path("1_analysts/market.md"),
    "Social Analyst": Path("1_analysts/sentiment.md"),
    "News Analyst": Path("1_analysts/news.md"),
    "Fundamentals Analyst": Path("1_analysts/fundamentals.md"),
    "Bull Researcher": Path("2_research/bull.md"),
    "Bear Researcher": Path("2_research/bear.md"),
    "Research Manager": Path("2_research/manager.md"),
    "Trader": Path("3_trading/trader.md"),
    "Aggressive Analyst": Path("4_risk/aggressive.md"),
    "Conservative Analyst": Path("4_risk/conservative.md"),
    "Neutral Analyst": Path("4_risk/neutral.md"),
    "Portfolio Manager": Path("5_portfolio/decision.md"),
}
RUNTIME_AGENT_EVENT_HEADINGS = {
    "Bull Researcher": "### Bull Researcher Analysis",
    "Bear Researcher": "### Bear Researcher Analysis",
    "Research Manager": "### Research Manager Decision",
    "Aggressive Analyst": "### Aggressive Analyst Analysis",
    "Conservative Analyst": "### Conservative Analyst Analysis",
    "Neutral Analyst": "### Neutral Analyst Analysis",
    "Portfolio Manager": "### Portfolio Manager Decision",
}
RUNTIME_SECTION_MEMBERS = {
    "market_report": [("Market Analyst", None)],
    "sentiment_report": [("Social Analyst", None)],
    "news_report": [("News Analyst", None)],
    "fundamentals_report": [("Fundamentals Analyst", None)],
    "investment_plan": [
        ("Bull Researcher", "### Bull Researcher Analysis"),
        ("Bear Researcher", "### Bear Researcher Analysis"),
        ("Research Manager", "### Research Manager Decision"),
    ],
    "trader_investment_plan": [("Trader", None)],
    "final_trade_decision": [
        ("Aggressive Analyst", "### Aggressive Analyst Analysis"),
        ("Conservative Analyst", "### Conservative Analyst Analysis"),
        ("Neutral Analyst", "### Neutral Analyst Analysis"),
        ("Portfolio Manager", "### Portfolio Manager Decision"),
    ],
}


def _recommended_provider() -> str:
    env_preferences = [
        ("DASHSCOPE_API_KEY", "dashscope"),
        ("OPENAI_API_KEY", "openai"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("GOOGLE_API_KEY", "google"),
        ("XAI_API_KEY", "xai"),
        ("OPENROUTER_API_KEY", "openrouter"),
    ]
    for env_name, provider in env_preferences:
        if os.getenv(env_name):
            return provider
    return DEFAULT_CONFIG["llm_provider"]


def _preferred_model(provider: str, mode: str, fallback: str | None = None) -> str:
    options = [value for _, value in get_model_options(provider, mode)]
    if fallback and fallback in options:
        return fallback
    return options[0]


def _translation_model(provider: str, payload: Dict[str, Any] | None = None) -> str:
    env_model = (os.getenv(TRANSLATION_MODEL_ENV) or "").strip()
    if env_model:
        return env_model
    payload = payload or {}
    return str(payload.get("quick_think_llm") or _preferred_model(provider, "quick"))


def get_dashboard_defaults() -> Dict[str, Any]:
    provider = _recommended_provider()
    quick_default = DEFAULT_CONFIG["quick_think_llm"]
    deep_default = DEFAULT_CONFIG["deep_think_llm"]

    if provider != DEFAULT_CONFIG["llm_provider"]:
        quick_default = None
        deep_default = None

    return {
        "ticker": "600519.SH",
        "analysis_date": datetime.date.today().isoformat(),
        "analysts": [option["value"] for option in ANALYST_OPTIONS],
        "research_depth": DEFAULT_CONFIG["max_debate_rounds"],
        "llm_provider": provider,
        "backend_url": PROVIDER_BASE_URLS[provider],
        "quick_think_llm": _preferred_model(provider, "quick", quick_default),
        "deep_think_llm": _preferred_model(provider, "deep", deep_default),
        "google_thinking_level": DEFAULT_CONFIG.get("google_thinking_level"),
        "openai_reasoning_effort": DEFAULT_CONFIG.get("openai_reasoning_effort"),
        "anthropic_effort": DEFAULT_CONFIG.get("anthropic_effort"),
        "output_language": DEFAULT_CONFIG.get("output_language", "English"),
    }


def normalize_dashboard_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    from cli.utils import normalize_ticker_symbol

    ticker = normalize_ticker_symbol(str(payload.get("ticker", "")).strip())

    analysis_date = str(payload.get("analysis_date", "")).strip()
    try:
        parsed_date = datetime.datetime.strptime(analysis_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Analysis date must use YYYY-MM-DD format.") from exc

    if parsed_date > datetime.date.today():
        raise ValueError("Analysis date cannot be in the future.")

    analysts = payload.get("analysts") or [option["value"] for option in ANALYST_OPTIONS]
    if not isinstance(analysts, list):
        raise ValueError("Analysts must be provided as a list.")
    analysts = [str(item).lower() for item in analysts]
    invalid_analysts = [item for item in analysts if item not in ANALYST_ORDER]
    if invalid_analysts:
        raise ValueError(f"Unsupported analyst selection: {', '.join(invalid_analysts)}")
    if not analysts:
        raise ValueError("Select at least one analyst.")

    provider = str(payload.get("llm_provider", _recommended_provider())).lower()
    if provider not in MODEL_OPTIONS:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    quick_model = str(payload.get("quick_think_llm") or "").strip()
    deep_model = str(payload.get("deep_think_llm") or "").strip()
    quick_candidates = {value for _, value in get_model_options(provider, "quick")}
    deep_candidates = {value for _, value in get_model_options(provider, "deep")}

    if not quick_model:
        quick_model = _preferred_model(provider, "quick")
    if not deep_model:
        deep_model = _preferred_model(provider, "deep")
    if quick_model not in quick_candidates:
        raise ValueError(f"Unsupported quick model for {provider}: {quick_model}")
    if deep_model not in deep_candidates:
        raise ValueError(f"Unsupported deep model for {provider}: {deep_model}")

    try:
        research_depth = int(payload.get("research_depth", DEFAULT_CONFIG["max_debate_rounds"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("Research depth must be a number.") from exc

    valid_depths = {option["value"] for option in RESEARCH_DEPTH_OPTIONS}
    if research_depth not in valid_depths:
        raise ValueError("Research depth must be one of 1, 3, or 5.")

    output_language = str(
        payload.get("output_language", DEFAULT_CONFIG.get("output_language", "English"))
    ).strip() or "English"

    google_thinking_level = payload.get("google_thinking_level")
    if google_thinking_level not in {None, "", "high", "minimal"}:
        raise ValueError("Google thinking level must be 'high' or 'minimal'.")
    google_thinking_level = google_thinking_level or None

    openai_reasoning_effort = payload.get("openai_reasoning_effort")
    if openai_reasoning_effort not in {None, "", "low", "medium", "high"}:
        raise ValueError("OpenAI reasoning effort must be low, medium, or high.")
    openai_reasoning_effort = openai_reasoning_effort or None

    anthropic_effort = payload.get("anthropic_effort")
    if anthropic_effort not in {None, "", "low", "medium", "high"}:
        raise ValueError("Anthropic effort must be low, medium, or high.")
    anthropic_effort = anthropic_effort or None

    return {
        "ticker": ticker,
        "analysis_date": parsed_date.isoformat(),
        "analysts": [analyst for analyst in ANALYST_ORDER if analyst in analysts],
        "research_depth": research_depth,
        "llm_provider": provider,
        "backend_url": str(
            payload.get("backend_url") or PROVIDER_BASE_URLS.get(provider, DEFAULT_CONFIG["backend_url"])
        ),
        "quick_think_llm": quick_model,
        "deep_think_llm": deep_model,
        "google_thinking_level": google_thinking_level,
        "openai_reasoning_effort": openai_reasoning_effort,
        "anthropic_effort": anthropic_effort,
        "output_language": output_language,
    }


class DashboardSession:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._buffer = AnalysisBuffer()
        self._stats_handler = StatsCallbackHandler()
        self._stop_requested = threading.Event()
        self._status = "idle"
        self._error = None
        self._decision = None
        self._started_at = None
        self._finished_at = None
        self._results_path = None
        self._report_file = None
        self._selections = None
        self._thread = None
        self._historical_snapshot: Dict[str, Any] | None = None
        self._completed_snapshot: Dict[str, Any] | None = None
        self._file_write_lock = threading.RLock()
        self._display_translator: DisplayTranslator | None = None
        self._translator_signature: tuple[Any, ...] | None = None
        self._runtime_translation_hashes: Dict[str, str] = {}
        self._runtime_translation_pending: Dict[str, str] = {}

    def options(self) -> Dict[str, Any]:
        return {
            "defaults": get_dashboard_defaults(),
            "providers": list(MODEL_OPTIONS.keys()),
            "models": MODEL_OPTIONS,
            "languages": OUTPUT_LANGUAGES,
            "research_depths": RESEARCH_DEPTH_OPTIONS,
            "analysts": ANALYST_OPTIONS,
            "provider_base_urls": PROVIDER_BASE_URLS,
        }

    def history(self) -> Dict[str, Any]:
        return {"runs": list_dashboard_runs()}

    def start(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        selections = normalize_dashboard_request(payload)

        with self._lock:
            if self._status in {"running", "stopping"}:
                raise RuntimeError("An analysis is already running.")

            if self._display_translator is not None:
                self._display_translator.close()
                self._display_translator = None
                self._translator_signature = None
            self._historical_snapshot = None
            self._completed_snapshot = None
            self._runtime_translation_hashes = {}
            self._runtime_translation_pending = {}

            run_stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            run_dir = (
                Path(DEFAULT_CONFIG["results_dir"])
                / selections["ticker"]
                / selections["analysis_date"]
                / f"dashboard_{run_stamp}"
            )
            report_dir = run_dir / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            log_file = run_dir / "message_tool.log"
            log_file.touch(exist_ok=True)

            self._buffer = AnalysisBuffer(
                on_message=self._build_message_hook(log_file),
                on_tool_call=self._build_tool_hook(log_file),
                on_report_section=self._build_report_hook(report_dir),
            )
            self._buffer.init_for_analysis(selections["analysts"])
            self._stats_handler = StatsCallbackHandler()
            self._stop_requested = threading.Event()
            self._status = "running"
            self._error = None
            self._decision = None
            self._started_at = datetime.datetime.now()
            self._finished_at = None
            self._results_path = str(run_dir.resolve())
            self._report_file = None
            self._selections = selections
            self._display_translator = DisplayTranslator(
                output_language=selections.get("output_language", "English"),
                provider=selections["llm_provider"],
                model=_translation_model(selections["llm_provider"], selections),
                base_url=selections["backend_url"],
                google_thinking_level=selections.get("google_thinking_level"),
                openai_reasoning_effort=selections.get("openai_reasoning_effort"),
                anthropic_effort=selections.get("anthropic_effort"),
                cache_dir=str(run_dir.resolve()),
            )

            self._thread = threading.Thread(
                target=self._run_analysis,
                args=(selections, run_dir),
                daemon=True,
            )
            self._thread.start()

        return self.snapshot()

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            if self._status not in {"running", "stopping"}:
                raise RuntimeError("There is no running analysis to stop.")

            self._stop_requested.set()
            self._status = "stopping"

        self._buffer.add_message(
            "System", "Stop requested. Waiting for the current step to finish."
        )
        return self.snapshot()

    def reset(self) -> Dict[str, Any]:
        with self._lock:
            if self._status in {"running", "stopping"}:
                raise RuntimeError("Cannot reset while an analysis is running.")

            if self._display_translator is not None:
                self._display_translator.close()
                self._display_translator = None
                self._translator_signature = None
            self._buffer = AnalysisBuffer()
            self._stats_handler = StatsCallbackHandler()
            self._stop_requested = threading.Event()
            self._status = "idle"
            self._error = None
            self._decision = None
            self._started_at = None
            self._finished_at = None
            self._results_path = None
            self._report_file = None
            self._selections = None
            self._thread = None
            self._historical_snapshot = None
            self._completed_snapshot = None
            self._runtime_translation_hashes = {}
            self._runtime_translation_pending = {}

        return self.snapshot()

    def load_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required.")
        with self._lock:
            if self._status in {"running", "stopping"}:
                raise RuntimeError("Cannot load history while an analysis is running.")
            self._completed_snapshot = None
            self._runtime_translation_hashes = {}
            self._runtime_translation_pending = {}
            self._display_translator = self._ensure_display_translator(payload)
            historical_snapshot = load_dashboard_run(
                run_id,
                language=str(payload.get("output_language") or "English"),
            )
            selections = dict(historical_snapshot.get("selections") or {})
            selections["output_language"] = str(
                payload.get("output_language") or selections.get("output_language") or "English"
            )
            if payload.get("llm_provider"):
                selections["llm_provider"] = str(payload.get("llm_provider"))
            if payload.get("quick_think_llm"):
                selections["quick_think_llm"] = str(payload.get("quick_think_llm"))
            if payload.get("backend_url"):
                selections["backend_url"] = str(payload.get("backend_url"))
            historical_snapshot["selections"] = selections
            historical_snapshot = self._display_translator.localize_snapshot(historical_snapshot)
            self._historical_snapshot = historical_snapshot

        return self.snapshot()

    def delete_history(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required.")

        with self._lock:
            if self._status in {"running", "stopping"}:
                raise RuntimeError("Cannot delete history while an analysis is running.")
            active_run_id = (
                str(self._historical_snapshot.get("history_run_id"))
                if self._historical_snapshot
                else None
            )

        delete_dashboard_run(run_id)

        with self._lock:
            if active_run_id == run_id:
                if self._display_translator is not None:
                    self._display_translator.close()
                    self._display_translator = None
                    self._translator_signature = None
                self._historical_snapshot = None
                self._buffer = AnalysisBuffer()
                self._stats_handler = StatsCallbackHandler()
                self._status = "idle"
                self._error = None
                self._decision = None
                self._started_at = None
                self._finished_at = None
                self._results_path = None
                self._report_file = None
                self._selections = None
                self._thread = None
                self._completed_snapshot = None
                self._runtime_translation_hashes = {}
                self._runtime_translation_pending = {}

        return {
            "deleted_run_id": run_id,
            "runs": list_dashboard_runs(),
            "snapshot": self.snapshot(),
        }

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            historical_snapshot = self._historical_snapshot
            completed_snapshot = self._completed_snapshot
            status = self._status

        if historical_snapshot is not None and status not in {"running", "stopping"}:
            return dict(historical_snapshot)

        if completed_snapshot is not None and status == "completed":
            return dict(completed_snapshot)

        buffer_snapshot = self._buffer.snapshot()
        stats = self._stats_handler.get_stats()

        with self._lock:
            started_at = self._started_at
            finished_at = self._finished_at
            status = self._status
            error = self._error
            decision = self._decision
            results_path = self._results_path
            report_file = self._report_file
            selections = self._selections
            stop_requested = self._stop_requested.is_set()

        elapsed_seconds = None
        if started_at:
            end_time = finished_at or datetime.datetime.now()
            elapsed_seconds = round((end_time - started_at).total_seconds(), 1)

        snapshot = {
            "status": status,
            "error": error,
            "decision": decision,
            "started_at": started_at.isoformat() if started_at else None,
            "finished_at": finished_at.isoformat() if finished_at else None,
            "elapsed_seconds": elapsed_seconds,
            "results_path": results_path,
            "report_file": report_file,
            "selections": selections,
            "stop_requested": stop_requested,
            "stats": stats,
            "translation_stats": (
                self._display_translator.get_stats()
                if self._display_translator
                else {
                    "translation_calls": 0,
                    "translation_tokens_in": 0,
                    "translation_tokens_out": 0,
                    "translation_documents": 0,
                    "translation_failures": 0,
                    "enabled": False,
                    "language": selections.get("output_language") if selections else "English",
                    "provider": None,
                    "model": None,
                }
            ),
            **buffer_snapshot,
        }

        # Apply runtime translation if running with non-English output language
        if status in {"running", "stopping"} and results_path and selections:
            output_language = str(selections.get("output_language") or "English")
            if output_language.lower() != "english":
                snapshot = self._localize_running_snapshot(
                    snapshot,
                    run_dir=Path(results_path),
                    language=output_language,
                )

        return snapshot

    def _run_analysis(self, selections: Dict[str, Any], run_dir: Path) -> None:
        def persist_usage_stats() -> None:
            analysis_stats = self._stats_handler.get_stats()
            translation_stats = (
                self._display_translator.get_stats()
                if self._display_translator
                else {
                    "translation_calls": 0,
                    "translation_tokens_in": 0,
                    "translation_tokens_out": 0,
                    "translation_documents": 0,
                    "translation_failures": 0,
                    "enabled": False,
                    "language": selections.get("output_language", "English"),
                    "provider": None,
                    "model": None,
                }
            )
            with self._file_write_lock:
                (run_dir / "analysis_stats.json").write_text(
                    json.dumps(analysis_stats, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (run_dir / "translation_stats.json").write_text(
                    json.dumps(translation_stats, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        try:
            config = DEFAULT_CONFIG.copy()

            config["max_debate_rounds"] = selections["research_depth"]
            config["max_risk_discuss_rounds"] = selections["research_depth"]
            config["quick_think_llm"] = selections["quick_think_llm"]
            config["deep_think_llm"] = selections["deep_think_llm"]
            config["backend_url"] = selections["backend_url"]
            config["llm_provider"] = selections["llm_provider"]
            config["google_thinking_level"] = selections.get("google_thinking_level")
            config["openai_reasoning_effort"] = selections.get(
                "openai_reasoning_effort"
            )
            config["anthropic_effort"] = selections.get("anthropic_effort")
            config["output_language"] = selections.get("output_language", "English")

            graph = TradingAgentsGraph(
                selections["analysts"],
                config=config,
                debug=True,
                callbacks=[self._stats_handler],
            )

            self._buffer.add_message("System", f"Selected ticker: {selections['ticker']}")
            self._buffer.add_message(
                "System", f"Analysis date: {selections['analysis_date']}"
            )
            self._buffer.add_message(
                "System",
                f"Selected analysts: {', '.join(selections['analysts'])}",
            )

            if selections["analysts"]:
                self._buffer.update_agent_status(
                    ANALYST_AGENT_NAMES[selections["analysts"][0]], "in_progress"
                )

            init_agent_state = graph.propagator.create_initial_state(
                selections["ticker"], selections["analysis_date"]
            )
            args = graph.propagator.get_graph_args(callbacks=[self._stats_handler])

            trace = []
            for chunk in graph.graph.stream(init_agent_state, **args):
                if self._stop_requested.is_set():
                    break
                apply_stream_chunk(self._buffer, chunk)
                self._sync_runtime_member_outputs(run_dir=run_dir, chunk=chunk)
                trace.append(chunk)
                if self._stop_requested.is_set():
                    break

            if self._stop_requested.is_set():
                with self._lock:
                    self._status = "stopped"
                    self._finished_at = datetime.datetime.now()
                self._buffer.add_message("System", "Analysis stopped by user.")
                persist_usage_stats()
                return

            if not trace:
                raise RuntimeError("The graph finished without producing any state.")

            final_state = trace[-1]
            decision = graph.process_signal(final_state["final_trade_decision"])
            finalize_buffer(self._buffer, final_state)
            self._buffer.add_message(
                "System", f"Completed analysis for {selections['analysis_date']}"
            )
            report_file = save_report_to_disk(final_state, selections["ticker"], run_dir)
            if self._display_translator is not None:
                materialize_translated_run(
                    run_dir,
                    selections.get("output_language", "English"),
                    self._display_translator,
                )
            persist_usage_stats()
            completed_snapshot = self._build_file_backed_snapshot(run_dir, selections)

            with self._lock:
                self._decision = completed_snapshot.get("decision", decision)
                self._report_file = completed_snapshot.get("report_file") or str(report_file.resolve())
                self._status = "completed"
                self._finished_at = datetime.datetime.now()
                self._completed_snapshot = completed_snapshot
        except Exception as exc:
            if self._stop_requested.is_set():
                with self._lock:
                    self._status = "stopped"
                    self._finished_at = datetime.datetime.now()
                self._buffer.add_message("System", "Analysis stopped by user.")
                persist_usage_stats()
                return
            with self._lock:
                self._status = "error"
                self._error = str(exc)
                self._finished_at = datetime.datetime.now()
            self._buffer.add_message("System", f"Error: {exc}")
            error_log = run_dir / "dashboard_error.log"
            error_log.write_text(traceback.format_exc(), encoding="utf-8")
            persist_usage_stats()

    def _build_message_hook(self, log_file: Path):
        def hook(timestamp: str, message_type: str, content: str) -> None:
            flattened = content.replace("\n", " ")
            with self._file_write_lock:
                with open(log_file, "a", encoding="utf-8") as handle:
                    handle.write(f"{timestamp} [{message_type}] {flattened}\n")

        return hook

    def _build_tool_hook(self, log_file: Path):
        def hook(timestamp: str, tool_name: str, args: Any) -> None:
            if isinstance(args, dict):
                args_str = ", ".join(f"{key}={value}" for key, value in args.items())
            else:
                args_str = str(args)
            with self._file_write_lock:
                with open(log_file, "a", encoding="utf-8") as handle:
                    handle.write(f"{timestamp} [Tool Call] {tool_name}({args_str})\n")

        return hook

    def _build_report_hook(self, report_dir: Path):
        def hook(section_name: str, content: str) -> None:
            section_file = report_dir / f"{section_name}.md"
            with self._file_write_lock:
                section_file.write_text(content, encoding="utf-8")

        return hook

    def _sync_runtime_member_outputs(self, *, run_dir: Path, chunk: Dict[str, Any]) -> None:
        member_outputs: list[tuple[str, str]] = []

        analyst_chunks = [
            ("market_report", "Market Analyst"),
            ("sentiment_report", "Social Analyst"),
            ("news_report", "News Analyst"),
            ("fundamentals_report", "Fundamentals Analyst"),
        ]
        for section_name, agent_name in analyst_chunks:
            content = str(chunk.get(section_name) or "").strip()
            if content:
                member_outputs.append((agent_name, content))

        trader_plan = str(chunk.get("trader_investment_plan") or "").strip()
        if trader_plan:
            member_outputs.append(("Trader", trader_plan))

        debate_state = chunk.get("investment_debate_state") or {}
        judge = str(debate_state.get("judge_decision") or "").strip()
        if judge:
            bull_hist = str(debate_state.get("bull_history") or "").strip()
            bear_hist = str(debate_state.get("bear_history") or "").strip()
            if bull_hist:
                member_outputs.append(("Bull Researcher", bull_hist))
            if bear_hist:
                member_outputs.append(("Bear Researcher", bear_hist))
            member_outputs.append(("Research Manager", judge))

        risk_state = chunk.get("risk_debate_state") or {}
        risk_judge = str(risk_state.get("judge_decision") or "").strip()
        if risk_judge:
            aggressive_hist = str(risk_state.get("aggressive_history") or "").strip()
            conservative_hist = str(risk_state.get("conservative_history") or "").strip()
            neutral_hist = str(risk_state.get("neutral_history") or "").strip()
            if aggressive_hist:
                member_outputs.append(("Aggressive Analyst", aggressive_hist))
            if conservative_hist:
                member_outputs.append(("Conservative Analyst", conservative_hist))
            if neutral_hist:
                member_outputs.append(("Neutral Analyst", neutral_hist))
            member_outputs.append(("Portfolio Manager", risk_judge))

        for agent_name, content in member_outputs:
            self._write_runtime_member_output(
                run_dir=run_dir,
                agent_name=agent_name,
                content=content,
            )

    def _write_runtime_member_output(
        self,
        *,
        run_dir: Path,
        agent_name: str,
        content: str,
    ) -> None:
        relative_path = self._runtime_member_relative_path(agent_name)
        body = content.strip()
        if relative_path is None or not body:
            return

        target = run_dir / relative_path
        with self._file_write_lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.read_text(encoding="utf-8") != body:
                target.write_text(body, encoding="utf-8")
        self._queue_runtime_translation(
            run_dir=run_dir,
            relative_path=relative_path,
        )

    def _queue_runtime_translation(
        self,
        *,
        run_dir: Path,
        relative_path: Path,
    ) -> None:
        source = run_dir / relative_path
        if not source.exists():
            return

        stripped = source.read_text(encoding="utf-8").strip()
        if not stripped:
            return

        key = relative_path.as_posix()
        with self._lock:
            translator = self._display_translator
            if translator is None or not translator.enabled:
                return
            source_hash = hashlib.sha256(stripped.encode("utf-8")).hexdigest()
            if self._runtime_translation_hashes.get(key) == source_hash:
                return
            if self._runtime_translation_pending.get(key) == source_hash:
                return
            self._runtime_translation_pending[key] = source_hash

        def worker() -> None:
            try:
                translated = translator.translate_document(stripped)
                translator.cache_document(stripped, translated)
                with self._lock:
                    if self._runtime_translation_pending.get(key) != source_hash:
                        return
                target = translated_path(run_dir, translator.output_language, relative_path)
                with self._file_write_lock:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(translated, encoding="utf-8")
                with self._lock:
                    if self._runtime_translation_pending.get(key) == source_hash:
                        self._runtime_translation_hashes[key] = source_hash
            finally:
                with self._lock:
                    if self._runtime_translation_pending.get(key) == source_hash:
                        self._runtime_translation_pending.pop(key, None)

        threading.Thread(target=worker, daemon=True).start()

    def _ensure_display_translator(self, payload: Dict[str, Any]) -> DisplayTranslator:
        signature = self._translator_settings_signature(payload)
        with self._lock:
            if self._display_translator is None or self._translator_signature != signature:
                if self._display_translator is not None:
                    self._display_translator.close()
                self._display_translator = self._create_display_translator(payload)
                self._translator_signature = signature
            return self._display_translator

    @staticmethod
    def _translator_settings_signature(payload: Dict[str, Any]) -> tuple[Any, ...]:
        provider = str(payload.get("llm_provider") or _recommended_provider())
        return (
            str(payload.get("output_language") or "English"),
            provider,
            _translation_model(provider, payload),
            str(
                payload.get("backend_url")
                or PROVIDER_BASE_URLS.get(provider, DEFAULT_CONFIG["backend_url"])
            ),
            payload.get("google_thinking_level"),
            payload.get("openai_reasoning_effort"),
            payload.get("anthropic_effort"),
        )

    @staticmethod
    def _create_display_translator(payload: Dict[str, Any]) -> DisplayTranslator:
        provider = str(payload.get("llm_provider") or _recommended_provider())
        return DisplayTranslator(
            output_language=str(payload.get("output_language") or "English"),
            provider=provider,
            model=_translation_model(provider, payload),
            base_url=str(
                payload.get("backend_url")
                or PROVIDER_BASE_URLS.get(provider, DEFAULT_CONFIG["backend_url"])
            ),
            google_thinking_level=payload.get("google_thinking_level"),
            openai_reasoning_effort=payload.get("openai_reasoning_effort"),
            anthropic_effort=payload.get("anthropic_effort"),
        )

    @staticmethod
    def _runtime_member_relative_path(agent_name: str) -> Path | None:
        return RUNTIME_AGENT_FILE_MAP.get(agent_name)

    def _localize_running_snapshot(
        self,
        snapshot: Dict[str, Any],
        *,
        run_dir: Path,
        language: str,
    ) -> Dict[str, Any]:
        localized = dict(snapshot)
        original_sections = dict(snapshot.get("report_sections") or {})
        localized_sections: Dict[str, Any] = {}
        for section_name, content in original_sections.items():
            localized_sections[section_name] = self._load_runtime_section_content(
                run_dir=run_dir,
                language=language,
                section_name=section_name,
                fallback=content,
            )
        localized["report_sections"] = localized_sections

        latest_report_event_ids: Dict[str, int] = {}
        for event in snapshot.get("events") or []:
            if event.get("type") == "report":
                latest_report_event_ids[str(event.get("agent") or "")] = int(event.get("id") or 0)

        localized_events = []
        for event in snapshot.get("events") or []:
            localized_event = dict(event)
            if (
                event.get("type") == "report"
                and latest_report_event_ids.get(str(event.get("agent") or ""))
                == int(event.get("id") or 0)
            ):
                member_content = self._load_runtime_member_content(
                    run_dir=run_dir,
                    language=language,
                    agent_name=str(event.get("agent") or ""),
                )
                if member_content:
                    localized_event["content"] = self._format_runtime_event_content(
                        str(event.get("agent") or ""),
                        member_content,
                    )
            localized_events.append(localized_event)
        localized["events"] = localized_events

        latest_report_event = next(
            (event for event in reversed(localized_events) if event.get("type") == "report"),
            None,
        )
        if latest_report_event is not None:
            latest_section = str(latest_report_event.get("label") or "")
            localized["current_report"] = (
                f"### {AnalysisBuffer.SECTION_TITLES[latest_section]}\n"
                f"{latest_report_event.get('content') or ''}"
            )
        localized["final_report"] = self._compose_report_summary(localized_sections)
        localized["current_focus_event"] = pick_current_focus_event(
            localized.get("current_agent"),
            localized_events,
        )
        localized["process_tree"] = build_process_tree(
            localized.get("agent_status") or {},
            localized_events,
        )
        return localized

    def _load_runtime_section_content(
        self,
        *,
        run_dir: Path,
        language: str,
        section_name: str,
        fallback: str | None,
    ) -> str | None:
        members = RUNTIME_SECTION_MEMBERS.get(section_name)
        if not members:
            return fallback

        parts: list[str] = []
        for agent_name, heading in members:
            member_content = self._load_runtime_member_content(
                run_dir=run_dir,
                language=language,
                agent_name=agent_name,
            )
            if member_content:
                parts.append(
                    f"{heading}\n{member_content}" if heading else member_content
                )
        return "\n\n".join(parts) if parts else fallback

    def _load_runtime_member_content(
        self,
        *,
        run_dir: Path,
        language: str,
        agent_name: str,
    ) -> str | None:
        relative_path = self._runtime_member_relative_path(agent_name)
        if relative_path is None:
            return None
        translated = load_translated_text(run_dir, language, relative_path)
        if translated is not None:
            return translated
        source = run_dir / relative_path
        if not source.exists():
            return None
        return source.read_text(encoding="utf-8")

    @staticmethod
    def _format_runtime_event_content(agent_name: str, content: str) -> str:
        heading = RUNTIME_AGENT_EVENT_HEADINGS.get(agent_name)
        return f"{heading}\n{content}" if heading else content

    @staticmethod
    def _compose_report_summary(report_sections: Dict[str, str | None]) -> str | None:
        report_parts = []

        analyst_sections = [
            "market_report",
            "sentiment_report",
            "news_report",
            "fundamentals_report",
        ]
        if any(report_sections.get(section) for section in analyst_sections):
            report_parts.append("## Analyst Team Reports")
            if report_sections.get("market_report"):
                report_parts.append(
                    f"### Market Analysis\n{report_sections['market_report']}"
                )
            if report_sections.get("sentiment_report"):
                report_parts.append(
                    f"### Social Sentiment\n{report_sections['sentiment_report']}"
                )
            if report_sections.get("news_report"):
                report_parts.append(
                    f"### News Analysis\n{report_sections['news_report']}"
                )
            if report_sections.get("fundamentals_report"):
                report_parts.append(
                    "### Fundamentals Analysis\n"
                    f"{report_sections['fundamentals_report']}"
                )

        if report_sections.get("investment_plan"):
            report_parts.append("## Research Team Decision")
            report_parts.append(f"{report_sections['investment_plan']}")

        if report_sections.get("trader_investment_plan"):
            report_parts.append("## Trading Team Plan")
            report_parts.append(f"{report_sections['trader_investment_plan']}")

        if report_sections.get("final_trade_decision"):
            report_parts.append("## Portfolio Management Decision")
            report_parts.append(f"{report_sections['final_trade_decision']}")

        return "\n\n".join(report_parts) if report_parts else None

    def _build_file_backed_snapshot(
        self,
        run_dir: Path,
        selections: Dict[str, Any],
    ) -> Dict[str, Any]:
        results_root = Path(DEFAULT_CONFIG["results_dir"]).resolve()
        run_id = run_dir.resolve().relative_to(results_root).as_posix()
        snapshot = load_dashboard_run(
            run_id,
            results_root=results_root,
            language=selections.get("output_language", "English"),
        )
        merged_selections = {
            **(snapshot.get("selections") or {}),
            **selections,
        }
        snapshot["selections"] = merged_selections
        snapshot["history_loaded"] = False
        snapshot["translation_error"] = None
        # No translation - skip localize_snapshot
        return snapshot


def _load_dashboard_html() -> str:
    html_path = Path(__file__).parent / "static" / "dashboard.html"
    return html_path.read_text(encoding="utf-8")


def serve_dashboard(host: str = "127.0.0.1", port: int = 8765) -> None:
    session = DashboardSession()
    html = _load_dashboard_html()

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._write_html(html)
                return
            if path == "/api/options":
                self._write_json(HTTPStatus.OK, session.options())
                return
            if path == "/api/history":
                self._write_json(HTTPStatus.OK, session.history())
                return
            if path == "/api/state":
                self._write_json(HTTPStatus.OK, session.snapshot())
                return
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError:
                self._write_json(
                    HTTPStatus.BAD_REQUEST, {"error": "Request body must be valid JSON."}
                )
                return

            try:
                if path == "/api/start":
                    snapshot = session.start(payload)
                    self._write_json(HTTPStatus.ACCEPTED, snapshot)
                    return
                if path == "/api/stop":
                    snapshot = session.stop()
                    self._write_json(HTTPStatus.ACCEPTED, snapshot)
                    return
                if path == "/api/reset":
                    snapshot = session.reset()
                    self._write_json(HTTPStatus.OK, snapshot)
                    return
                if path == "/api/history/load":
                    snapshot = session.load_history(payload)
                    self._write_json(HTTPStatus.OK, snapshot)
                    return
                if path == "/api/history/delete":
                    deletion = session.delete_history(payload)
                    self._write_json(HTTPStatus.OK, deletion)
                    return
            except RuntimeError as exc:
                self._write_json(HTTPStatus.CONFLICT, {"error": str(exc)})
                return
            except ValueError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _write_html(self, html_text: str) -> None:
            body = html_text.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), DashboardHandler)
    server.daemon_threads = True
    url = f"http://{host}:{port}"

    console.print(f"[bold green]TradingAgents Dashboard[/bold green] running at {url}")
    console.print(
        "[dim]Open the URL in your browser, then start an analysis from the page. "
        "Press Ctrl+C to stop the server.[/dim]"
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down dashboard...[/yellow]")
    finally:
        server.server_close()
