from __future__ import annotations

import datetime
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict

from cli.analysis_runtime import (
    AGENT_STAGE_MAP,
    ANALYST_AGENT_NAMES,
    AnalysisBuffer,
    build_process_tree,
    build_workflow_stages,
    get_stage_title,
    infer_agent_for_section,
    pick_current_focus_event,
)
from cli.translated_run_materializer import load_translated_text, translated_path
from tradingagents.default_config import DEFAULT_CONFIG


LOG_LINE_PATTERN = re.compile(r"^(?P<time>\d{2}:\d{2}:\d{2}) \[(?P<label>[^\]]+)\] (?P<content>.*)$")
RUN_STAMP_PATTERN = re.compile(r"dashboard_(\d{8})_(\d{6})$")

REPORT_FILE_MAP = {
    "market_report": "1_analysts/market.md",
    "sentiment_report": "1_analysts/sentiment.md",
    "news_report": "1_analysts/news.md",
    "fundamentals_report": "1_analysts/fundamentals.md",
    "trader_investment_plan": "3_trading/trader.md",
}
INDIVIDUAL_REPORT_EVENTS = [
    ("market_report", "Market Analyst", "1_analysts/market.md", None),
    ("sentiment_report", "Social Analyst", "1_analysts/sentiment.md", None),
    ("news_report", "News Analyst", "1_analysts/news.md", None),
    ("fundamentals_report", "Fundamentals Analyst", "1_analysts/fundamentals.md", None),
    ("investment_plan", "Bull Researcher", "2_research/bull.md", "### Bull Researcher Analysis"),
    ("investment_plan", "Bear Researcher", "2_research/bear.md", "### Bear Researcher Analysis"),
    ("investment_plan", "Research Manager", "2_research/manager.md", "### Research Manager Decision"),
    ("trader_investment_plan", "Trader", "3_trading/trader.md", None),
    ("final_trade_decision", "Aggressive Analyst", "4_risk/aggressive.md", "### Aggressive Analyst Analysis"),
    ("final_trade_decision", "Conservative Analyst", "4_risk/conservative.md", "### Conservative Analyst Analysis"),
    ("final_trade_decision", "Neutral Analyst", "4_risk/neutral.md", "### Neutral Analyst Analysis"),
    ("final_trade_decision", "Portfolio Manager", "5_portfolio/decision.md", "### Portfolio Manager Decision"),
]


def list_dashboard_runs(results_root: Path | None = None, limit: int = 100) -> list[dict[str, Any]]:
    root = (results_root or Path(DEFAULT_CONFIG["results_dir"])).resolve()
    if not root.exists():
        return []

    runs: list[dict[str, Any]] = []
    for run_dir in root.glob("*/*/dashboard_*"):
        if not run_dir.is_dir():
            continue
        try:
            meta = _build_run_metadata(run_dir, root)
        except Exception:
            continue
        runs.append(meta)

    runs.sort(
        key=lambda item: item.get("started_at") or item.get("updated_at") or "",
        reverse=True,
    )
    return runs[:limit]


def load_dashboard_run(
    run_id: str,
    results_root: Path | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    root = (results_root or Path(DEFAULT_CONFIG["results_dir"])).resolve()
    run_dir = _resolve_run_dir(run_id, root)
    if not run_dir.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")

    meta = _build_run_metadata(run_dir, root)
    selected_analysts = _parse_selected_analysts(run_dir / "message_tool.log")

    buffer = AnalysisBuffer()
    buffer.init_for_analysis(selected_analysts)

    report_sections = _load_report_sections(run_dir, language)
    agent_status = dict(buffer.agent_status)

    status = meta["status"]
    if status == "completed":
        for agent in agent_status:
            agent_status[agent] = "completed"
    else:
        for section_name, content in report_sections.items():
            if content:
                agent_status[infer_agent_for_section(section_name, content)] = "completed"

    events = _parse_history_events(run_dir, status, language)
    if status != "completed" and events:
        last_agent = next(
            (event["agent"] for event in reversed(events) if event["agent"] != "System"),
            None,
        )
        if last_agent and agent_status.get(last_agent) == "pending":
            agent_status[last_agent] = "in_progress"

    current_agent = next(
        (event["agent"] for event in reversed(events) if event["agent"] != "System"),
        None,
    )
    current_stage_id = AGENT_STAGE_MAP.get(current_agent, None)
    current_focus_event = pick_current_focus_event(current_agent, events)

    current_report = next(
        (
            f"### {AnalysisBuffer.SECTION_TITLES[section_name]}\n{content}"
            for section_name in [
                "final_trade_decision",
                "trader_investment_plan",
                "investment_plan",
                "fundamentals_report",
                "news_report",
                "sentiment_report",
                "market_report",
            ]
            if report_sections.get(section_name)
            for content in [report_sections[section_name]]
        ),
        None,
    )
    final_report = _load_complete_report(run_dir, language)
    decision = _infer_decision(report_sections.get("final_trade_decision") or final_report)

    buffer.report_sections = report_sections
    reports_completed = sum(1 for value in report_sections.values() if value)

    analysis_stats = _load_stats_file(run_dir / "analysis_stats.json")
    fallback_stats = {
        "llm_calls": 0,
        "tool_calls": sum(1 for event in events if event["type"] == "tool"),
        "tokens_in": 0,
        "tokens_out": 0,
    }
    if analysis_stats is None:
        analysis_stats = fallback_stats
    else:
        analysis_stats = {
            **fallback_stats,
            **analysis_stats,
        }
    translation_stats = _load_stats_file(run_dir / "translation_stats.json") or {
        "translation_calls": 0,
        "translation_tokens_in": 0,
        "translation_tokens_out": 0,
        "translation_documents": 0,
        "translation_failures": 0,
        "enabled": bool(language and language.strip().lower() != "english"),
        "language": language or DEFAULT_CONFIG.get("output_language", "English"),
        "provider": None,
        "model": None,
    }

    return {
        "status": status,
        "error": _load_error(run_dir),
        "decision": decision,
        "started_at": meta["started_at"],
        "finished_at": meta["finished_at"],
        "elapsed_seconds": _elapsed_seconds(meta["started_at"], meta["finished_at"]),
        "results_path": str(run_dir.resolve()),
        "report_file": _resolve_report_file(run_dir, language),
        "selections": {
            "ticker": meta["ticker"],
            "analysis_date": meta["analysis_date"],
            "analysts": selected_analysts,
            "research_depth": DEFAULT_CONFIG["max_debate_rounds"],
            "llm_provider": DEFAULT_CONFIG["llm_provider"],
            "backend_url": DEFAULT_CONFIG["backend_url"],
            "quick_think_llm": DEFAULT_CONFIG["quick_think_llm"],
            "deep_think_llm": DEFAULT_CONFIG["deep_think_llm"],
            "output_language": DEFAULT_CONFIG.get("output_language", "English"),
        },
        "stop_requested": status == "stopped",
        "stats": analysis_stats,
        "translation_stats": translation_stats,
        "messages": [
            {
                "timestamp": event["timestamp"],
                "type": event["label"],
                "content": event["content"],
            }
            for event in events
            if event["type"] == "message"
        ],
        "tool_calls": [
            {
                "timestamp": event["timestamp"],
                "tool_name": event["label"],
                "args": event["content"],
            }
            for event in events
            if event["type"] == "tool"
        ],
        "current_report": current_report,
        "final_report": final_report,
        "agent_status": agent_status,
        "current_agent": current_agent,
        "current_stage_id": current_stage_id,
        "current_stage_title": get_stage_title(current_stage_id),
        "current_focus_event": current_focus_event,
        "report_sections": report_sections,
        "events": events,
        "selected_analysts": list(selected_analysts),
        "counts": {
            "agents_completed": sum(1 for value in agent_status.values() if value == "completed"),
            "agents_total": len(agent_status),
            "reports_completed": reports_completed,
            "reports_total": len(report_sections),
        },
        "workflow": build_workflow_stages(agent_status),
        "process_tree": build_process_tree(agent_status, events),
        "history_run_id": meta["id"],
        "history_loaded": True,
    }


def delete_dashboard_run(run_id: str, results_root: Path | None = None) -> None:
    root = (results_root or Path(DEFAULT_CONFIG["results_dir"])).resolve()
    run_dir = _resolve_run_dir(run_id, root)
    if not run_dir.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")
    shutil.rmtree(run_dir)


def _build_run_metadata(run_dir: Path, root: Path) -> dict[str, Any]:
    relative = run_dir.resolve().relative_to(root)
    parts = relative.parts
    ticker = parts[0] if len(parts) > 0 else ""
    analysis_date = parts[1] if len(parts) > 1 else ""
    started_at = _parse_run_started_at(run_dir.name)
    finished_at = _infer_finished_at(run_dir)
    return {
        "id": relative.as_posix(),
        "ticker": ticker,
        "analysis_date": analysis_date,
        "run_name": run_dir.name,
        "status": _infer_status(run_dir),
        "started_at": started_at.isoformat() if started_at else None,
        "finished_at": finished_at.isoformat() if finished_at else None,
        "updated_at": datetime.datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat(),
        "has_report": (run_dir / "complete_report.md").exists(),
        "has_error": (run_dir / "dashboard_error.log").exists(),
    }


def _resolve_run_dir(run_id: str, root: Path) -> Path:
    candidate = (root / run_id).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("Run path is outside of results directory.")
    return candidate


def _load_stats_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _infer_status(run_dir: Path) -> str:
    if (run_dir / "complete_report.md").exists():
        return "completed"
    if (run_dir / "dashboard_error.log").exists():
        return "error"
    if (run_dir / "message_tool.log").exists():
        return "stopped"
    return "idle"


def _parse_run_started_at(run_name: str) -> datetime.datetime | None:
    match = RUN_STAMP_PATTERN.match(run_name)
    if not match:
        return None
    return datetime.datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")


def _infer_finished_at(run_dir: Path) -> datetime.datetime | None:
    candidates = [
        run_dir / "complete_report.md",
        run_dir / "dashboard_error.log",
        run_dir / "message_tool.log",
    ]
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return None
    latest = max(existing, key=lambda path: path.stat().st_mtime)
    return datetime.datetime.fromtimestamp(latest.stat().st_mtime)


def _elapsed_seconds(started_at: str | None, finished_at: str | None) -> float | None:
    if not started_at or not finished_at:
        return None
    start = datetime.datetime.fromisoformat(started_at)
    end = datetime.datetime.fromisoformat(finished_at)
    return round((end - start).total_seconds(), 1)


def _parse_selected_analysts(log_path: Path) -> list[str]:
    if not log_path.exists():
        return list(ANALYST_AGENT_NAMES.keys())
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if "[System] Selected analysts:" not in line:
            continue
        raw = line.split("Selected analysts:", 1)[1].strip()
        selected = [item.strip().lower() for item in raw.split(",") if item.strip()]
        return selected or list(ANALYST_AGENT_NAMES.keys())
    return list(ANALYST_AGENT_NAMES.keys())


def _load_report_sections(run_dir: Path, language: str | None = None) -> dict[str, str | None]:
    sections: dict[str, str | None] = {}
    for section_name, relative_path in REPORT_FILE_MAP.items():
        sections[section_name] = _read_report_text(run_dir, relative_path, language)

    sections["investment_plan"] = _join_parts(
        [
            ("### Bull Researcher Analysis", run_dir / "2_research/bull.md"),
            ("### Bear Researcher Analysis", run_dir / "2_research/bear.md"),
            ("### Research Manager Decision", run_dir / "2_research/manager.md"),
        ],
        language,
    )
    sections["final_trade_decision"] = _join_parts(
        [
            ("### Aggressive Analyst Analysis", run_dir / "4_risk/aggressive.md"),
            ("### Conservative Analyst Analysis", run_dir / "4_risk/conservative.md"),
            ("### Neutral Analyst Analysis", run_dir / "4_risk/neutral.md"),
            ("### Portfolio Manager Decision", run_dir / "5_portfolio/decision.md"),
        ],
        language,
    )
    return sections


def _join_parts(parts: list[tuple[str, Path]], language: str | None = None) -> str | None:
    content_parts: list[str] = []
    for heading, path in parts:
        content = _read_report_text(path.parent.parent, path.relative_to(path.parent.parent), language)
        if content:
            content_parts.append(f"{heading}\n{content}")
    return "\n\n".join(content_parts) if content_parts else None


def _load_complete_report(run_dir: Path, language: str | None = None) -> str | None:
    return _read_report_text(run_dir, "complete_report.md", language)


def _load_error(run_dir: Path) -> str | None:
    path = run_dir / "dashboard_error.log"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _parse_history_events(
    run_dir: Path,
    status: str,
    language: str | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    log_path = run_dir / "message_tool.log"
    event_id = 0
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            match = LOG_LINE_PATTERN.match(line)
            if not match:
                continue
            label = match.group("label")
            content = match.group("content")
            timestamp = match.group("time")
            event_type = _map_log_label_to_event_type(label)
            agent = _infer_agent_from_log(label, content)
            event_id += 1
            events.append(
                {
                    "id": event_id,
                    "timestamp": timestamp,
                    "type": event_type,
                    "label": label if event_type != "tool" else _tool_name(content),
                    "content": content,
                    "agent": agent,
                    "stage_id": AGENT_STAGE_MAP.get(agent, "setup"),
                }
            )

    report_timestamp = _infer_finished_at(run_dir)
    report_time = report_timestamp.strftime("%H:%M:%S") if report_timestamp else "00:00:00"
    for section_name, agent, relative_path, heading in INDIVIDUAL_REPORT_EVENTS:
        content = _read_report_text(run_dir, relative_path, language)
        if not content:
            continue
        if heading:
            content = f"{heading}\n{content}"
        event_id += 1
        events.append(
            {
                "id": event_id,
                "timestamp": report_time,
                "type": "report",
                "label": section_name,
                "content": content,
                "agent": agent,
                "stage_id": AGENT_STAGE_MAP.get(agent, "setup"),
            }
        )

    if status == "completed":
        event_id += 1
        events.append(
            {
                "id": event_id,
                "timestamp": report_time,
                "type": "status",
                "label": "status",
                "content": "Analysis completed",
                "agent": "System",
                "stage_id": "setup",
            }
        )
    return events


def _read_report_text(run_dir: Path, relative_path: str | Path, language: str | None = None) -> str | None:
    translated = load_translated_text(run_dir, language, relative_path)
    if translated is not None:
        return translated
    path = run_dir / relative_path
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _resolve_report_file(run_dir: Path, language: str | None = None) -> str | None:
    if language and language.strip().lower() != "english":
        translated_file = translated_path(run_dir, language, "complete_report.md")
        if translated_file.exists():
            return str(translated_file.resolve())
    report_file = run_dir / "complete_report.md"
    if report_file.exists():
        return str(report_file.resolve())
    return None


def _map_log_label_to_event_type(label: str) -> str:
    normalized = label.strip().lower()
    if normalized == "tool call":
        return "tool"
    if normalized == "control":
        return "status"
    return "message"


def _tool_name(content: str) -> str:
    return content.split("(", 1)[0].strip() if "(" in content else "tool"


def _infer_agent_from_log(label: str, content: str) -> str:
    if label in {"System", "User"}:
        return "System"

    text = content.lower()
    if "bull analyst" in text or "bull researcher" in text:
        return "Bull Researcher"
    if "bear analyst" in text or "bear researcher" in text:
        return "Bear Researcher"
    if "research manager" in text or "summary of the debate" in text:
        return "Research Manager"
    if "aggressive analyst" in text:
        return "Aggressive Analyst"
    if "conservative analyst" in text:
        return "Conservative Analyst"
    if "neutral analyst" in text:
        return "Neutral Analyst"
    if "portfolio manager" in text or "rating" in text and "executive summary" in text:
        return "Portfolio Manager"
    if "investment plan" in text or "final transaction proposal" in text:
        return "Trader"
    if "现金流" in content or "资产负债" in content or "财务" in content:
        return "Fundamentals Analyst"
    if "新闻" in content or "news" in text:
        return "News Analyst"
    if "社交" in content or "social" in text or "sentiment" in text:
        return "Social Analyst"
    if "技术分析" in content or "indicator" in text or "macd" in text or "rsi" in text:
        return "Market Analyst"
    return "System"


def _infer_decision(content: str | None) -> str | None:
    if not content:
        return None
    upper = content.upper()
    for decision in ["OVERWEIGHT", "UNDERWEIGHT", "BUY", "SELL", "HOLD"]:
        if decision in upper:
            return decision
    if "卖出" in content:
        return "SELL"
    if "买入" in content:
        return "BUY"
    if "持有" in content:
        return "HOLD"
    if "增持" in content:
        return "OVERWEIGHT"
    if "减持" in content:
        return "UNDERWEIGHT"
    return None
