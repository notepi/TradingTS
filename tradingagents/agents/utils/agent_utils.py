from langchain_core.messages import HumanMessage, RemoveMessage
import yaml
from pathlib import Path

# Import tools from separate utility files
from tradingagents.agents.utils.core_stock_tools import (
    get_stock_data
)
from tradingagents.agents.utils.technical_indicators_tools import (
    get_indicators
)
from tradingagents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement
)
from tradingagents.agents.utils.news_data_tools import (
    get_news,
    get_insider_transactions,
    get_global_news
)

# Legacy tool map (for backward compatibility)
LEGACY_TOOL_MAP = {
    "get_stock_data": get_stock_data,
    "get_indicators": get_indicators,
    "get_fundamentals": get_fundamentals,
    "get_balance_sheet": get_balance_sheet,
    "get_cashflow": get_cashflow,
    "get_income_statement": get_income_statement,
    "get_news": get_news,
    "get_insider_transactions": get_insider_transactions,
    "get_global_news": get_global_news,
}


def load_agents_registry() -> dict:
    """加载 agents_registry.yaml 配置"""
    config_path = Path(__file__).parent.parent.parent / "config" / "agents_registry.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"agents_registry.yaml not found: {config_path}")
    return yaml.safe_load(config_path.read_text())


def load_agent_tools(agent_name: str) -> list:
    """从配置加载智能体工具列表。

    优先从 TOOL_REGISTRY（装饰器注册）获取，
    未找到则 fallback 到 LEGACY_TOOL_MAP。

    Args:
        agent_name: 智能体名称（如 fundamentals_analyst）

    Returns:
        list: LangChain tool 对象列表
    """
    from tradingagents.dataflows.decorators import TOOL_REGISTRY

    registry = load_agents_registry()
    agent_config = registry.get("agents", {}).get(agent_name)

    if not agent_config:
        raise KeyError(f"Agent '{agent_name}' not found in agents_registry.yaml")

    tools_config = agent_config.get("tools", [])
    tools = []

    for tool_item in tools_config:
        # 新格式：{name: "...", usage: "..."} 或旧格式：直接字符串
        if isinstance(tool_item, dict):
            name = tool_item.get("name")
        else:
            name = tool_item

        # 优先用装饰器注册的 tool
        if name in TOOL_REGISTRY:
            tools.append(TOOL_REGISTRY[name])
        # fallback 到 legacy tool
        elif name in LEGACY_TOOL_MAP:
            tools.append(LEGACY_TOOL_MAP[name])
        else:
            raise KeyError(f"Tool '{name}' not found in TOOL_REGISTRY or LEGACY_TOOL_MAP")

    return tools


def build_tools_usage(agent_name: str) -> str:
    """从配置生成工具使用说明（只对有 usage 字段的）。

    Args:
        agent_name: 智能体名称

    Returns:
        str: 工具使用说明，无 usage 工具时返回空字符串
    """
    registry = load_agents_registry()
    agent_config = registry.get("agents", {}).get(agent_name)

    if not agent_config:
        return ""

    tools_config = agent_config.get("tools", [])
    tools_with_usage = [t for t in tools_config if isinstance(t, dict) and "usage" in t]

    if not tools_with_usage:
        return ""

    lines = [f"- `{t['name']}`: {t['usage']}" for t in tools_with_usage]
    return "\n\nTool usage guide:\n" + "\n".join(lines)


def get_language_instruction() -> str:
    """Return a prompt instruction for the configured output language.

    Returns empty string when English (default), so no extra tokens are used.
    Only applied to user-facing agents (analysts, portfolio manager).
    Internal debate agents stay in English for reasoning quality.
    """
    from tradingagents.dataflows.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def build_instrument_context(ticker: str) -> str:
    """Describe the exact instrument so agents preserve exchange-qualified tickers."""
    return (
        f"The instrument to analyze is `{ticker}`. "
        "Use this exact ticker in every tool call, report, and recommendation, "
        "preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`)."
    )

def create_msg_delete():
    def delete_messages(state):
        """Clear messages and add placeholder for Anthropic compatibility"""
        messages = state["messages"]

        # Remove all messages
        removal_operations = [RemoveMessage(id=m.id) for m in messages]

        # Add a minimal placeholder message
        placeholder = HumanMessage(content="Continue")

        return {"messages": removal_operations + [placeholder]}

    return delete_messages


        
