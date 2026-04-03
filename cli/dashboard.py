from __future__ import annotations

import datetime
import json
import os
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from rich.console import Console

from cli.analysis_runtime import (
    ANALYST_AGENT_NAMES,
    ANALYST_ORDER,
    AnalysisBuffer,
    apply_stream_chunk,
    finalize_buffer,
)
from cli.display_translation import DisplayTranslator
from cli.reporting import save_report_to_disk
from cli.stats_handler import StatsCallbackHandler
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS, get_model_options


console = Console()

PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1",
    "anthropic": "https://api.anthropic.com/",
    "xai": "https://api.x.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "dashscope": "https://coding.dashscope.aliyuncs.com/v1",
    "ollama": "http://localhost:11434/v1",
}
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
        self._display_translator: DisplayTranslator | None = None

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

    def start(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        selections = normalize_dashboard_request(payload)

        with self._lock:
            if self._status in {"running", "stopping"}:
                raise RuntimeError("An analysis is already running.")

            if self._display_translator is not None:
                self._display_translator.close()
                self._display_translator = None

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
                model=selections["quick_think_llm"],
                base_url=selections["backend_url"],
                google_thinking_level=selections.get("google_thinking_level"),
                openai_reasoning_effort=selections.get("openai_reasoning_effort"),
                anthropic_effort=selections.get("anthropic_effort"),
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

        return self.snapshot()

    def snapshot(self) -> Dict[str, Any]:
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
            display_translator = self._display_translator

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
            **buffer_snapshot,
        }

        if display_translator is not None:
            display_translator.queue_snapshot(snapshot)
            snapshot = display_translator.localize_snapshot(snapshot)

        return snapshot

    def _run_analysis(self, selections: Dict[str, Any], run_dir: Path) -> None:
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
                trace.append(chunk)
                if self._stop_requested.is_set():
                    break

            if self._stop_requested.is_set():
                with self._lock:
                    self._status = "stopped"
                    self._finished_at = datetime.datetime.now()
                self._buffer.add_message("System", "Analysis stopped by user.")
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

            with self._lock:
                self._decision = decision
                self._report_file = str(report_file.resolve())
                self._status = "completed"
                self._finished_at = datetime.datetime.now()
        except Exception as exc:
            if self._stop_requested.is_set():
                with self._lock:
                    self._status = "stopped"
                    self._finished_at = datetime.datetime.now()
                self._buffer.add_message("System", "Analysis stopped by user.")
                return
            with self._lock:
                self._status = "error"
                self._error = str(exc)
                self._finished_at = datetime.datetime.now()
            self._buffer.add_message("System", f"Error: {exc}")
            error_log = run_dir / "dashboard_error.log"
            error_log.write_text(traceback.format_exc(), encoding="utf-8")

    @staticmethod
    def _build_message_hook(log_file: Path):
        def hook(timestamp: str, message_type: str, content: str) -> None:
            flattened = content.replace("\n", " ")
            with open(log_file, "a", encoding="utf-8") as handle:
                handle.write(f"{timestamp} [{message_type}] {flattened}\n")

        return hook

    @staticmethod
    def _build_tool_hook(log_file: Path):
        def hook(timestamp: str, tool_name: str, args: Any) -> None:
            if isinstance(args, dict):
                args_str = ", ".join(f"{key}={value}" for key, value in args.items())
            else:
                args_str = str(args)
            with open(log_file, "a", encoding="utf-8") as handle:
                handle.write(f"{timestamp} [Tool Call] {tool_name}({args_str})\n")

        return hook

    @staticmethod
    def _build_report_hook(report_dir: Path):
        def hook(section_name: str, content: str) -> None:
            section_file = report_dir / f"{section_name}.md"
            section_file.write_text(content, encoding="utf-8")

        return hook


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
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
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
