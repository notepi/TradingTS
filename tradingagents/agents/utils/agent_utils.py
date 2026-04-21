from langchain_core.messages import HumanMessage, RemoveMessage
import yaml
import importlib
from pathlib import Path


def load_agents_registry() -> dict:
    """加载 agents_registry.yaml 配置"""
    config_path = Path(__file__).parent.parent.parent / "config" / "agents_registry.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"agents_registry.yaml not found: {config_path}")
    return yaml.safe_load(config_path.read_text())


def load_report_source_config(agent_name: str) -> dict:
    """从 agents_registry.yaml 加载报告来源配置。

    Args:
        agent_name: 智能体名称（如 fundamentals_analyst）

    Returns:
        dict: 报告来源配置，无配置时返回默认模式 {"mode": "llm_generate"}
    """
    registry = load_agents_registry()
    agent_config = registry.get("agents", {}).get(agent_name, {})
    return agent_config.get("report_source", {"mode": "llm_generate"})


def resolve_report_path(path_template: str, state: dict) -> Path:
    """解析报告路径模板中的动态变量。

    支持变量:
    - {results_dir}: 从配置获取的结果目录
    - {ticker}: 从 state["company_of_interest"] 获取
    - {agent_name}: 分析师名称（去掉 _analyst 后缀）

    Args:
        path_template: 路径模板字符串
        state: 当前 AgentState

    Returns:
        Path: 解析后的文件路径
    """
    from datasource.datahub.servers.config import get_config

    config = get_config()
    results_dir = config.get("results_dir", "./results")

    # 从 agent_name 推断报告名称（去掉 _analyst 后缀）
    ticker = state.get("company_of_interest", "")

    replacements = {
        "{results_dir}": results_dir,
        "{ticker}": ticker,
    }

    resolved_path = path_template
    for var, value in replacements.items():
        resolved_path = resolved_path.replace(var, value)

    return Path(resolved_path)


def load_local_report(agent_name: str, state: dict) -> str | None:
    """从本地文件加载报告。

    Args:
        agent_name: 智能体名称（如 fundamentals_analyst）
        state: 当前 AgentState

    Returns:
        str | None: 报告内容，文件不存在或模式不匹配时返回 None
    """
    report_config = load_report_source_config(agent_name)

    if report_config.get("mode") != "local_file":
        return None

    local_config = report_config.get("local_file", {})

    # 解析路径模板
    path_template = local_config.get(
        "path_template",
        "{results_dir}/{ticker}/reports/{agent_name}_report.md"
    )
    # 替换 {agent_name} 变量（去掉 _analyst 后缀）
    agent_short_name = agent_name.replace("_analyst", "")
    path_template = path_template.replace("{agent_name}", agent_short_name)

    path = resolve_report_path(path_template, state)

    if not path.exists():
        on_missing = local_config.get("on_missing", "fallback_to_llm")
        if on_missing == "fallback_to_llm":
            return None
        elif on_missing == "error":
            raise FileNotFoundError(f"Report file not found: {path}")
        elif on_missing == "empty":
            return ""

    return path.read_text(encoding="utf-8")


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
    from datasource.datahub.servers.interface import get_all_tool_modules

    registry = load_agents_registry()
    agent_config = registry.get("agents", {}).get(agent_name)

    if not agent_config:
        raise KeyError(f"Agent '{agent_name}' not found in agents_registry.yaml")

    tools_config = agent_config.get("tools", [])
    tools = []

    # 动态获取工具模块映射
    tool_modules = get_all_tool_modules()

    for tool_item in tools_config:
        # 新格式：{name: "...", usage: "..."} 或旧格式：直接字符串
        if isinstance(tool_item, dict):
            name = tool_item.get("name")
        else:
            name = tool_item

        # 如果工具未注册，尝试导入对应模块触发 @auto_tool
        if name not in TOOL_REGISTRY:
            if name in tool_modules and tool_modules[name]:
                importlib.import_module(tool_modules[name])
            else:
                raise KeyError(f"Tool '{name}' not in tools_registry.yaml or missing module_path")

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
    from datasource.datahub.servers.config import get_config
    lang = get_config().get("output_language", "English")
    if lang.strip().lower() == "english":
        return ""
    return f" Write your entire response in {lang}."


def get_output_language_instruction() -> str:
    """Return instruction for analysts to write reports in English.

    Ensures consistent English output regardless of input data language.
    """
    return (
        "You are a financial analyst. "
        "Input data may contain Chinese or other languages. "
        "Understand the input correctly and write your entire report in English.\n"
        "IMPORTANT: Pay close attention to unit annotations in data headers. "
        "Chinese units (亿元/万元/手) are NOT the same as English units (Billion/Million/Lot). "
        "Convert values correctly when writing English reports."
    )


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


        
