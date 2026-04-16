from langchain_core.messages import HumanMessage, RemoveMessage
import yaml
import importlib
from pathlib import Path

# 工具名到模块的映射（用于按需导入触发 @auto_tool 注册）
TOOL_MODULES = {
    "get_stock_data": "tradingagents.agents.utils.core_stock_tools",
    "get_indicators": "tradingagents.agents.utils.technical_indicators_tools",
    "get_fundamentals": "tradingagents.agents.utils.fundamental_data_tools",
    "get_balance_sheet": "tradingagents.agents.utils.fundamental_data_tools",
    "get_cashflow": "tradingagents.agents.utils.fundamental_data_tools",
    "get_income_statement": "tradingagents.agents.utils.fundamental_data_tools",
    "get_news": "tradingagents.agents.utils.news_data_tools",
    "get_global_news": "tradingagents.agents.utils.news_data_tools",
    "get_insider_transactions": "tradingagents.agents.utils.news_data_tools",
    # datasource 层工具（通过 @auto_tool 注册）
    "get_peg_ratio": "datasource.tushare.indicators.enhanced_data",
    "get_yoy_growth": "datasource.tushare.indicators.enhanced_data",
}


def load_agents_registry() -> dict:
    """加载 agents_registry.yaml 配置"""
    config_path = Path(__file__).parent.parent.parent / "config" / "agents_registry.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"agents_registry.yaml not found: {config_path}")
    return yaml.safe_load(config_path.read_text())


def load_agent_tools(agent_name: str) -> list:
    """从配置加载智能体工具列表。

    所有工具必须通过 @auto_tool 装饰器注册到 TOOL_REGISTRY。
    如果工具未注册，会自动导入对应模块触发注册。

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

        # 如果工具未注册，尝试导入对应模块触发 @auto_tool
        if name not in TOOL_REGISTRY:
            if name in TOOL_MODULES:
                importlib.import_module(TOOL_MODULES[name])
            else:
                raise KeyError(f"Tool '{name}' not in TOOL_MODULES mapping")

        # 再次检查注册状态
        if name in TOOL_REGISTRY:
            tools.append(TOOL_REGISTRY[name])
        else:
            raise KeyError(f"Tool '{name}' not found in TOOL_REGISTRY after module import")

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


        
