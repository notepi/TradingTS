# Graph 执行流程

## 概述

TradingAgents 使用 LangGraph 构建多智能体协作图。`TradingAgentsGraph` 是入口类，负责初始化、执行和处理信号。

## 核心类

### TradingAgentsGraph

**文件**: `tradingagents/graph/trading_graph.py`

```python
class TradingAgentsGraph:
    def __init__(self, debug=False, config=None):
        # 初始化两个 LLM 客户端
        # 创建 ToolNode
        # 创建记忆系统
        # 构建并编译图

    def propagate(self, company_name, trade_date):
        # 执行图
        # 返回 (final_state, decision)
```

## 初始化流程

### 1. LLM 客户端创建

```python
deep_thinking_llm = create_llm_client(config["deep_think_llm"], **config)
quick_thinking_llm = create_llm_client(config["quick_think_llm"], **config)
```

- `deep_thinking_llm`: 用于复杂推理（Research Manager、Portfolio Manager）
- `quick_thinking_llm`: 用于快速决策（分析师、交易员）

### 2. ToolNode 创建

```python
tool_nodes = {
    "market": ToolNode(load_agent_tools("market_analyst")),
    "social": ToolNode(load_agent_tools("social_media_analyst")),
    "news": ToolNode(load_agent_tools("news_analyst")),
    "fundamentals": ToolNode(load_agent_tools("fundamentals_analyst")),
}
```

ToolNode 将工具调用结果注入到消息中，供下游节点使用。

### 3. 记忆系统创建

```python
memories = {
    "bull": FinancialSituationMemory(),
    "bear": FinancialSituationMemory(),
    "trader": FinancialSituationMemory(),
    "invest_judge": FinancialSituationMemory(),
    "portfolio_manager": FinancialSituationMemory(),
}
```

每个记忆实例独立存储历史情况和建议。

## 图构建 (GraphSetup)

### setup_graph()

```python
def setup_graph(self, selected_analysts=["market", "social", "news", "fundamentals"]):
    # 创建节点
    nodes = {
        "Market Analyst": create_market_analyst(self.deep_think_llm),
        "Msg Clear Market": create_msg_delete(),
        # ... 其他分析师和消息清理节点
        "tools_market": self.tool_nodes["market"],
        # ... 其他工具节点
        "Bull Researcher": create_bull_researcher(self.deep_think_llm, self.memories["bull"]),
        # ... 研究员节点
        "Trader": create_trader(self.quick_think_llm, self.memories["trader"]),
        # ... 风险管理节点
    }

    # 定义边
    edges = [
        # 分析师顺序
        ("Market Analyst", "Msg Clear Market"),
        ("Msg Clear Market", "Social Media Analyst"),
        ("Social Media Analyst", "Msg Clear Social"),
        # ... 其他分析师连接
        # 辩论边
        ("Bull Researcher", "should_continue_debate"),
        ("should_continue_debate", "Bear Researcher"),
        # ... 风险管理边
    ]

    return StateGraph(AgentState, ...) | ...
```

## 状态定义 (AgentState)

```python
class AgentState(MessagesState):
    # 公司和日期
    company_of_interest: str
    trade_date: str

    # 分析师报告
    market_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str

    # 投资辩论状态
    investment_debate_state: InvestDebateState
    investment_plan: str
    trader_investment_plan: str

    # 风险管理辩论状态
    risk_debate_state: RiskDebateState
    final_trade_decision: str
```

## 执行流程 (propagate)

```python
def propagate(self, company_name, trade_date):
    # 1. 创建初始状态
    init_agent_state = self.propagator.create_initial_state(
        company_name, trade_date
    )

    # 2. 执行图
    final_state = self.graph.invoke(
        init_agent_state,
        config={"recursion_limit": 150}
    )

    # 3. 处理信号
    decision = self.process_signal(final_state["final_trade_decision"])

    return final_state, decision
```

## 消息清理机制

每个分析师后面都有一个 `Msg Clear` 节点：

```python
def create_msg_delete():
    def delete_messages(state):
        messages = state["messages"]
        removal_operations = [RemoveMessage(id=m.id) for m in messages]
        placeholder = HumanMessage(content="Continue")
        return {"messages": removal_operations + [placeholder]}
    return delete_messages
```

**作用**: 避免消息历史过长导致上下文溢出，只保留关键报告字段。

## 信号处理 (SignalProcessor)

### process_signal()

从 `final_trade_decision` 文本中提取结构化信息：

```python
def process_signal(self, signal_text: str):
    # 使用 LLM 从复杂文本中提取评级
    # BUY / OVERWEIGHT / HOLD / UNDERWEIGHT / SELL
```

## 调试模式

```python
ta = TradingAgentsGraph(debug=True, config=config)
```

启用后会在 `results/{ticker}/{date}/TradingAgentsStrategy_logs/` 目录生成完整的状态日志。

### 日志文件

| 文件 | 内容 |
|------|------|
| `full_states_log_{date}.json` | 所有中间状态，包含每个节点的输入输出 |

### 日志结构

```json
{
    "company_of_interest": "688333.SH",
    "trade_date": "2026-04-08",
    "market_report": "...",
    "sentiment_report": "...",
    "news_report": "...",
    "fundamentals_report": "...",
    "investment_debate_state": {...},
    "risk_debate_state": {...},
    "final_trade_decision": "..."
}
```

## 配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `max_debate_rounds` | Bull/Bear 辩论轮数 | 2 |
| `max_risk_discuss_rounds` | 风险管理辩论轮数 | 3 |
| `max_conversation_length` | 对话最大长度 | 20 |
| `recursion_limit` | 图执行最大递归深度 | 150 |

---

*最后更新：2026-04-14*
