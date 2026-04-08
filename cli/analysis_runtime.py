from __future__ import annotations

import ast
import datetime
import threading
from collections import deque
from typing import Any, Callable, Dict


MessageHook = Callable[[str, str, str], None]
ToolHook = Callable[[str, str, Any], None]
ReportHook = Callable[[str, str], None]


ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}
WORKFLOW_STAGE_DEFS = [
    (
        "analysts",
        "Analyst Team",
        [
            "Market Analyst",
            "Social Analyst",
            "News Analyst",
            "Fundamentals Analyst",
        ],
    ),
    (
        "research",
        "Research Team",
        ["Bull Researcher", "Bear Researcher", "Research Manager"],
    ),
    ("trading", "Trading Team", ["Trader"]),
    (
        "risk",
        "Risk Management",
        ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
    ),
    ("portfolio", "Portfolio Management", ["Portfolio Manager"]),
]
AGENT_STAGE_MAP = {
    "System": "setup",
    "Market Analyst": "analysts",
    "Social Analyst": "analysts",
    "News Analyst": "analysts",
    "Fundamentals Analyst": "analysts",
    "Bull Researcher": "research",
    "Bear Researcher": "research",
    "Research Manager": "research",
    "Trader": "trading",
    "Aggressive Analyst": "risk",
    "Neutral Analyst": "risk",
    "Conservative Analyst": "risk",
    "Portfolio Manager": "portfolio",
}


class AnalysisBuffer:
    FIXED_AGENTS = {
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": [
            "Aggressive Analyst",
            "Neutral Analyst",
            "Conservative Analyst",
        ],
        "Portfolio Management": ["Portfolio Manager"],
    }

    ANALYST_MAPPING = ANALYST_AGENT_NAMES

    REPORT_SECTIONS = {
        "market_report": ("market", "Market Analyst"),
        "sentiment_report": ("social", "Social Analyst"),
        "news_report": ("news", "News Analyst"),
        "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
        "investment_plan": (None, "Research Manager"),
        "trader_investment_plan": (None, "Trader"),
        "final_trade_decision": (None, "Portfolio Manager"),
    }

    SECTION_TITLES = {
        "market_report": "Market Analysis",
        "sentiment_report": "Social Sentiment",
        "news_report": "News Analysis",
        "fundamentals_report": "Fundamentals Analysis",
        "investment_plan": "Research Team Decision",
        "trader_investment_plan": "Trading Team Plan",
        "final_trade_decision": "Portfolio Management Decision",
    }

    def __init__(
        self,
        max_length: int = 100,
        on_message: MessageHook | None = None,
        on_tool_call: ToolHook | None = None,
        on_report_section: ReportHook | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._max_length = max_length
        self.messages = deque(maxlen=max_length)
        self.tool_calls = deque(maxlen=max_length)
        self.current_report = None
        self.final_report = None
        self.agent_status: Dict[str, str] = {}
        self.current_agent = None
        self.report_sections: Dict[str, str | None] = {}
        self.events = deque(maxlen=max_length * 6)
        self.selected_analysts: list[str] = []
        self._last_message_id = None
        self._last_updated_section = None
        self._event_counter = 0
        self._on_message = on_message
        self._on_tool_call = on_tool_call
        self._on_report_section = on_report_section

    def set_hooks(
        self,
        on_message: MessageHook | None = None,
        on_tool_call: ToolHook | None = None,
        on_report_section: ReportHook | None = None,
    ) -> None:
        with self._lock:
            self._on_message = on_message
            self._on_tool_call = on_tool_call
            self._on_report_section = on_report_section

    def init_for_analysis(self, selected_analysts: list[str]) -> None:
        with self._lock:
            self.selected_analysts = [a.lower() for a in selected_analysts]
            self.agent_status = {}

            for analyst_key in self.selected_analysts:
                if analyst_key in self.ANALYST_MAPPING:
                    self.agent_status[self.ANALYST_MAPPING[analyst_key]] = "pending"

            for team_agents in self.FIXED_AGENTS.values():
                for agent in team_agents:
                    self.agent_status[agent] = "pending"

            self.report_sections = {}
            for section, (analyst_key, _) in self.REPORT_SECTIONS.items():
                if analyst_key is None or analyst_key in self.selected_analysts:
                    self.report_sections[section] = None

            self.current_report = None
            self.final_report = None
            self.current_agent = None
            self.messages = deque(maxlen=self._max_length)
            self.tool_calls = deque(maxlen=self._max_length)
            self.events = deque(maxlen=self._max_length * 6)
            self._last_message_id = None
            self._last_updated_section = None
            self._event_counter = 0

    def should_process_message(self, message_id: Any) -> bool:
        with self._lock:
            if message_id == self._last_message_id:
                return False
            self._last_message_id = message_id
            return True

    def get_completed_reports_count(self) -> int:
        with self._lock:
            count = 0
            for section in self.report_sections:
                if section not in self.REPORT_SECTIONS:
                    continue
                _, finalizing_agent = self.REPORT_SECTIONS[section]
                has_content = self.report_sections.get(section) is not None
                agent_done = self.agent_status.get(finalizing_agent) == "completed"
                if has_content and agent_done:
                    count += 1
            return count

    def add_message(self, message_type: str, content: str) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.messages.append((timestamp, message_type, content))
            agent = self.current_agent if message_type not in {"System", "User"} else "System"
            self._append_event_locked(
                timestamp=timestamp,
                event_type="message",
                label=message_type,
                content=content,
                agent=agent,
            )
            hook = self._on_message
        if hook is not None:
            hook(timestamp, message_type, content)

    def add_tool_call(self, tool_name: str, args: Any) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.tool_calls.append((timestamp, tool_name, args))
            self._append_event_locked(
                timestamp=timestamp,
                event_type="tool",
                label=tool_name,
                content=format_tool_args(args, max_length=240),
                agent=self.current_agent,
            )
            hook = self._on_tool_call
        if hook is not None:
            hook(timestamp, tool_name, args)

    def update_agent_status(self, agent: str, status: str) -> None:
        with self._lock:
            if agent in self.agent_status:
                previous_status = self.agent_status.get(agent)
                self.agent_status[agent] = status
                self.current_agent = agent
                if previous_status != status:
                    self._append_event_locked(
                        timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                        event_type="status",
                        label="status",
                        content=f"{agent} -> {status}",
                        agent=agent,
                    )

    def update_report_section(self, section_name: str, content: str) -> None:
        with self._lock:
            if section_name not in self.report_sections:
                return
            self.report_sections[section_name] = content
            self._last_updated_section = section_name
            self._update_current_report_locked()
            self._append_event_locked(
                timestamp=datetime.datetime.now().strftime("%H:%M:%S"),
                event_type="report",
                label=section_name,
                content=content,
                agent=infer_agent_for_section(section_name, content),
            )
            hook = self._on_report_section
        if hook is not None and content:
            hook(section_name, content)

    def _update_current_report_locked(self) -> None:
        latest_section = self._last_updated_section
        latest_content = (
            self.report_sections.get(latest_section) if latest_section else None
        )

        if latest_section and latest_content:
            self.current_report = (
                f"### {self.SECTION_TITLES[latest_section]}\n{latest_content}"
            )
        else:
            self.current_report = None

        self._update_final_report_locked()

    def _update_final_report_locked(self) -> None:
        report_parts = []

        analyst_sections = [
            "market_report",
            "sentiment_report",
            "news_report",
            "fundamentals_report",
        ]
        if any(self.report_sections.get(section) for section in analyst_sections):
            report_parts.append("## Analyst Team Reports")
            if self.report_sections.get("market_report"):
                report_parts.append(
                    f"### Market Analysis\n{self.report_sections['market_report']}"
                )
            if self.report_sections.get("sentiment_report"):
                report_parts.append(
                    f"### Social Sentiment\n{self.report_sections['sentiment_report']}"
                )
            if self.report_sections.get("news_report"):
                report_parts.append(
                    f"### News Analysis\n{self.report_sections['news_report']}"
                )
            if self.report_sections.get("fundamentals_report"):
                report_parts.append(
                    "### Fundamentals Analysis\n"
                    f"{self.report_sections['fundamentals_report']}"
                )

        if self.report_sections.get("investment_plan"):
            report_parts.append("## Research Team Decision")
            report_parts.append(f"{self.report_sections['investment_plan']}")

        if self.report_sections.get("trader_investment_plan"):
            report_parts.append("## Trading Team Plan")
            report_parts.append(f"{self.report_sections['trader_investment_plan']}")

        if self.report_sections.get("final_trade_decision"):
            report_parts.append("## Portfolio Management Decision")
            report_parts.append(f"{self.report_sections['final_trade_decision']}")

        self.final_report = "\n\n".join(report_parts) if report_parts else None

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            agent_status = dict(self.agent_status)
            report_sections = dict(self.report_sections)
            events = list(self.events)
            current_stage_id = AGENT_STAGE_MAP.get(self.current_agent, None)
            current_stage_title = get_stage_title(current_stage_id)
            current_focus_event = pick_current_focus_event(self.current_agent, events)
            return {
                "messages": [
                    {"timestamp": timestamp, "type": msg_type, "content": content}
                    for timestamp, msg_type, content in self.messages
                ],
                "tool_calls": [
                    {"timestamp": timestamp, "tool_name": tool_name, "args": args}
                    for timestamp, tool_name, args in self.tool_calls
                ],
                "current_report": self.current_report,
                "final_report": self.final_report,
                "agent_status": agent_status,
                "current_agent": self.current_agent,
                "current_stage_id": current_stage_id,
                "current_stage_title": current_stage_title,
                "current_focus_event": current_focus_event,
                "report_sections": report_sections,
                "events": events,
                "selected_analysts": list(self.selected_analysts),
                "counts": {
                    "agents_completed": sum(
                        1 for status in agent_status.values() if status == "completed"
                    ),
                    "agents_total": len(agent_status),
                    "reports_completed": self.get_completed_reports_count(),
                    "reports_total": len(report_sections),
                },
                "workflow": build_workflow_stages(agent_status),
                "process_tree": build_process_tree(agent_status, events),
            }

    def _append_event_locked(
        self,
        timestamp: str,
        event_type: str,
        label: str,
        content: str,
        agent: str | None,
    ) -> None:
        self._event_counter += 1
        effective_agent = agent or self.current_agent or "System"
        self.events.append(
            {
                "id": self._event_counter,
                "timestamp": timestamp,
                "type": event_type,
                "label": label,
                "content": content,
                "agent": effective_agent,
                "stage_id": AGENT_STAGE_MAP.get(effective_agent, "setup"),
            }
        )


def build_workflow_stages(agent_status: Dict[str, str]) -> list[dict[str, Any]]:
    stages = []
    for stage_id, title, agent_names in WORKFLOW_STAGE_DEFS:
        active_agents = [name for name in agent_names if name in agent_status]
        if not active_agents:
            continue

        statuses = [agent_status.get(name, "pending") for name in active_agents]
        if any(status == "error" for status in statuses):
            stage_status = "error"
        elif all(status == "completed" for status in statuses):
            stage_status = "completed"
        elif any(status in {"in_progress", "completed"} for status in statuses):
            stage_status = "in_progress"
        else:
            stage_status = "pending"

        stages.append(
            {
                "id": stage_id,
                "title": title,
                "status": stage_status,
                "completed_agents": sum(
                    1 for status in statuses if status == "completed"
                ),
                "total_agents": len(active_agents),
                "agents": [
                    {"name": name, "status": agent_status.get(name, "pending")}
                    for name in active_agents
                ],
            }
        )
    return stages


def build_process_tree(
    agent_status: Dict[str, str], events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    events_by_agent: Dict[str, list[dict[str, Any]]] = {}
    for event in events:
        events_by_agent.setdefault(event["agent"], []).append(event)

    stages = []
    setup_events = events_by_agent.get("System", [])
    if setup_events:
        stages.append(
            {
                "id": "setup",
                "title": "Run Setup",
                "status": "completed",
                "completed_agents": 1,
                "total_agents": 1,
                "agents": [
                    {
                        "name": "System",
                        "status": "completed",
                        "events": setup_events,
                    }
                ],
            }
        )

    for stage in build_workflow_stages(agent_status):
        stage_agents = []
        for agent in stage["agents"]:
            stage_agents.append(
                {
                    **agent,
                    "events": events_by_agent.get(agent["name"], []),
                }
            )
        stages.append({**stage, "agents": stage_agents})

    return stages


def get_stage_title(stage_id: str | None) -> str | None:
    if stage_id == "setup":
        return "Run Setup"
    for item_id, title, _agents in WORKFLOW_STAGE_DEFS:
        if item_id == stage_id:
            return title
    return None


def pick_current_focus_event(
    current_agent: str | None, events: list[dict[str, Any]]
) -> dict[str, Any] | None:
    preferred_types = {"message", "tool", "report"}

    if current_agent:
        for event in reversed(events):
            if event["agent"] == current_agent and event["type"] in preferred_types:
                return event

    for event in reversed(events):
        if event["type"] in preferred_types:
            return event

    return events[-1] if events else None


def infer_agent_for_section(section_name: str, content: str) -> str:
    if section_name == "investment_plan":
        for agent in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
            if agent in content:
                return agent
        return "Research Manager"

    if section_name == "final_trade_decision":
        for agent in [
            "Aggressive Analyst",
            "Conservative Analyst",
            "Neutral Analyst",
            "Portfolio Manager",
        ]:
            if agent in content:
                return agent
        return "Portfolio Manager"

    if section_name == "trader_investment_plan":
        return "Trader"

    section_agents = {
        "market_report": "Market Analyst",
        "sentiment_report": "Social Analyst",
        "news_report": "News Analyst",
        "fundamentals_report": "Fundamentals Analyst",
    }
    return section_agents.get(section_name, "System")


def update_research_team_status(buffer: AnalysisBuffer, status: str) -> None:
    for agent in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
        buffer.update_agent_status(agent, status)


def update_analyst_statuses(buffer: AnalysisBuffer, chunk: Dict[str, Any]) -> None:
    selected = buffer.selected_analysts
    found_active = False

    for analyst_key in ANALYST_ORDER:
        if analyst_key not in selected:
            continue

        agent_name = ANALYST_AGENT_NAMES[analyst_key]
        report_key = ANALYST_REPORT_MAP[analyst_key]

        if chunk.get(report_key):
            buffer.update_report_section(report_key, chunk[report_key])

        has_report = bool(buffer.report_sections.get(report_key))

        if has_report:
            buffer.update_agent_status(agent_name, "completed")
        elif not found_active:
            buffer.update_agent_status(agent_name, "in_progress")
            found_active = True
        else:
            buffer.update_agent_status(agent_name, "pending")

    if not found_active and selected:
        if buffer.agent_status.get("Bull Researcher") == "pending":
            buffer.update_agent_status("Bull Researcher", "in_progress")


def extract_content_string(content: Any) -> str | None:
    def is_empty(val: Any) -> bool:
        if val is None or val == "":
            return True
        if isinstance(val, str):
            stripped = val.strip()
            if not stripped:
                return True
            try:
                return not bool(ast.literal_eval(stripped))
            except (ValueError, SyntaxError):
                return False
        return not bool(val)

    if is_empty(content):
        return None

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() if not is_empty(text) else None

    if isinstance(content, list):
        text_parts = [
            item.get("text", "").strip()
            if isinstance(item, dict) and item.get("type") == "text"
            else (item.strip() if isinstance(item, str) else "")
            for item in content
        ]
        result = " ".join(part for part in text_parts if part and not is_empty(part))
        return result if result else None

    return str(content).strip() if not is_empty(content) else None


def classify_message_type(message: Any) -> tuple[str, str | None]:
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    content = extract_content_string(getattr(message, "content", None))

    if isinstance(message, HumanMessage):
        if content and content.strip() == "Continue":
            return ("Control", content)
        return ("User", content)

    if isinstance(message, ToolMessage):
        return ("Data", content)

    if isinstance(message, AIMessage):
        return ("Agent", content)

    return ("System", content)


def format_tool_args(args: Any, max_length: int = 80) -> str:
    result = str(args)
    if len(result) > max_length:
        return result[: max_length - 3] + "..."
    return result


def apply_stream_chunk(buffer: AnalysisBuffer, chunk: Dict[str, Any]) -> None:
    messages = chunk.get("messages") or []
    if messages:
        last_message = messages[-1]
        msg_id = getattr(last_message, "id", None)

        if buffer.should_process_message(msg_id):
            msg_type, content = classify_message_type(last_message)
            if content and content.strip():
                buffer.add_message(msg_type, content)

            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                    if isinstance(tool_call, dict):
                        buffer.add_tool_call(tool_call["name"], tool_call["args"])
                    else:
                        buffer.add_tool_call(tool_call.name, tool_call.args)

    update_analyst_statuses(buffer, chunk)

    if chunk.get("investment_debate_state"):
        debate_state = chunk["investment_debate_state"]
        bull_hist = debate_state.get("bull_history", "").strip()
        bear_hist = debate_state.get("bear_history", "").strip()
        peter_lynch_hist = debate_state.get("peter_lynch_history", "").strip()
        judge = debate_state.get("judge_decision", "").strip()

        if bull_hist or bear_hist or peter_lynch_hist:
            update_research_team_status(buffer, "in_progress")
        if bull_hist:
            buffer.update_report_section(
                "investment_plan", f"### Bull Researcher Analysis\n{bull_hist}"
            )
        if bear_hist:
            buffer.update_report_section(
                "investment_plan", f"### Bear Researcher Analysis\n{bear_hist}"
            )
        if peter_lynch_hist:
            buffer.update_report_section(
                "investment_plan", f"### Peter Lynch Researcher Analysis\n{peter_lynch_hist}"
            )
        if judge:
            buffer.update_report_section(
                "investment_plan", f"### Research Manager Decision\n{judge}"
            )
            update_research_team_status(buffer, "completed")
            buffer.update_agent_status("Trader", "in_progress")

    if chunk.get("trader_investment_plan"):
        buffer.update_report_section(
            "trader_investment_plan", chunk["trader_investment_plan"]
        )
        if buffer.agent_status.get("Trader") != "completed":
            buffer.update_agent_status("Trader", "completed")
            buffer.update_agent_status("Aggressive Analyst", "in_progress")

    if chunk.get("risk_debate_state"):
        risk_state = chunk["risk_debate_state"]
        agg_hist = risk_state.get("aggressive_history", "").strip()
        con_hist = risk_state.get("conservative_history", "").strip()
        neu_hist = risk_state.get("neutral_history", "").strip()
        judge = risk_state.get("judge_decision", "").strip()

        if agg_hist:
            if buffer.agent_status.get("Aggressive Analyst") != "completed":
                buffer.update_agent_status("Aggressive Analyst", "in_progress")
            buffer.update_report_section(
                "final_trade_decision",
                f"### Aggressive Analyst Analysis\n{agg_hist}",
            )
        if con_hist:
            if buffer.agent_status.get("Conservative Analyst") != "completed":
                buffer.update_agent_status("Conservative Analyst", "in_progress")
            buffer.update_report_section(
                "final_trade_decision",
                f"### Conservative Analyst Analysis\n{con_hist}",
            )
        if neu_hist:
            if buffer.agent_status.get("Neutral Analyst") != "completed":
                buffer.update_agent_status("Neutral Analyst", "in_progress")
            buffer.update_report_section(
                "final_trade_decision", f"### Neutral Analyst Analysis\n{neu_hist}"
            )
        if judge:
            if buffer.agent_status.get("Portfolio Manager") != "completed":
                buffer.update_agent_status("Portfolio Manager", "in_progress")
                buffer.update_report_section(
                    "final_trade_decision", f"### Portfolio Manager Decision\n{judge}"
                )
                buffer.update_agent_status("Aggressive Analyst", "completed")
                buffer.update_agent_status("Conservative Analyst", "completed")
                buffer.update_agent_status("Neutral Analyst", "completed")
                buffer.update_agent_status("Portfolio Manager", "completed")


def finalize_buffer(buffer: AnalysisBuffer, final_state: Dict[str, Any]) -> None:
    for agent in list(buffer.agent_status):
        buffer.update_agent_status(agent, "completed")

    for section in list(buffer.report_sections):
        content = final_state.get(section)
        if content:
            buffer.update_report_section(section, content)
