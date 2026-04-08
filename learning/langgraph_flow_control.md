# LangGraph 流程控制详解

## 核心概念：StateGraph

LangGraph 用 **StateGraph** 定义工作流程：

```python
from langgraph.graph import END, StateGraph, START

# 创建工作流图
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("节点名", 节点函数)

# 添加边（流程控制）
workflow.add_edge("节点A", "节点B")           # 固定顺序
workflow.add_conditional_edges("节点A", 条件函数, {"选项1": "节点B", "选项2": "节点C"})  # 条件分支

# 编译
graph = workflow.compile()
```

---

## 三种流程控制方式

| 方式 | 代码 | 用途 |
|------|------|------|
| **固定边** | `add_edge(A, B)` | A 完成后必须去 B，固定顺序 |
| **条件边** | `add_conditional_edges(A, 条件函数, {选项: 目标})` | A 完成后根据条件决定去向 |
| **终止** | `END` | 流程结束 |

---

## 项目中的流程结构

```
START
    ↓
[分析团队] ← 固定顺序 + 条件边（工具调用循环）
    ↓
[研究团队] ← 条件边（辩论循环）
    ↓
[交易团队] ← 固定边
    ↓
[风险团队] ← 条件边（三角辩论循环）
    ↓
END
```

---

## 阶段1：分析团队的流程控制

### 节点添加

```python
# setup.py

# 每个分析师有3个节点：
#   1. Analyst 节点（调用LLM）
#   2. Tools 节点（执行工具）
#   3. Msg Clear 节点（清理消息）

for analyst_type in ["market", "social", "news", "fundamentals"]:
    workflow.add_node(f"{analyst_type.capitalize()} Analyst", analyst_nodes[analyst_type])
    workflow.add_node(f"Msg Clear {analyst_type.capitalize()}", delete_nodes[analyst_type])
    workflow.add_node(f"tools_{analyst_type}", tool_nodes[analyst_type])
```

### 边的定义

```python
# 1. 从 START 到第一个分析师
workflow.add_edge(START, f"{first_analyst.capitalize()} Analyst")

# 2. 分析师 → 条件判断 → Tools 或 Msg Clear
workflow.add_conditional_edges(
    "Market Analyst",
    self.conditional_logic.should_continue_market,
    ["tools_market", "Msg Clear Market"],
)

# 3. Tools → 回到分析师（继续循环）
workflow.add_edge("tools_market", "Market Analyst")

# 4. Msg Clear → 下一个分析师（或 Bull Researcher）
workflow.add_edge("Msg Clear Market", "Social Analyst")
workflow.add_edge("Msg Clear Social", "News Analyst")
workflow.add_edge("Msg Clear News", "Fundamentals Analyst")
workflow.add_edge("Msg Clear Fundamentals", "Bull Researcher")  # 最后一个
```

### 条件判断函数

```python
# conditional_logic.py

def should_continue_market(self, state: AgentState):
    """判断是否需要继续调用工具"""
    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        # Agent 还想调用工具 → 去 Tools 节点
        return "tools_market"

    # Agent 不需要工具了 → 去 Msg Clear（清理后进入下一个）
    return "Msg Clear Market"
```

### 流程图

```
START
    ↓
Market Analyst
    ↓ (条件判断)
    ├── tool_calls 存在 → tools_market → Market Analyst (循环)
    └── 无 tool_calls → Msg Clear Market
                          ↓
Social Analyst
    ↓ (条件判断)
    ├── tool_calls 存在 → tools_social → Social Analyst (循环)
    └── 无 tool_calls → Msg Clear Social
                          ↓
News Analyst → ... → Fundamentals Analyst → Bull Researcher
```

### 循环计数与 recursion_limit

```
Market Analyst 第1次 → 调用 get_stock_data
    ↓
tools_market → 返回数据
    ↓
Market Analyst 第2次 → 调用 get_indicators
    ↓
tools_market → 返回数据
    ↓
Market Analyst 第3次 → 不调用工具 → 写报告
    ↓
Msg Clear Market → 清理 messages → 进入 Social Analyst
```

**限制**：`recursion_limit` 防止无限循环（默认 100 次）

---

## 阶段2：研究团队的流程控制

### 节点添加

```python
# setup.py

workflow.add_node("Bull Researcher", bull_researcher_node)
workflow.add_node("Bear Researcher", bear_researcher_node)
workflow.add_node("Research Manager", research_manager_node)
```

### 边的定义

```python
# Bull → 条件判断 → Bear 或 Research Manager
workflow.add_conditional_edges(
    "Bull Researcher",
    self.conditional_logic.should_continue_debate,
    {
        "Bear Researcher": "Bear Researcher",
        "Research Manager": "Research Manager",
    },
)

# Bear → 条件判断 → Bull 或 Research Manager
workflow.add_conditional_edges(
    "Bear Researcher",
    self.conditional_logic.should_continue_debate,
    {
        "Bull Researcher": "Bull Researcher",
        "Research Manager": "Research Manager",
    },
)

# Research Manager → Trader（固定边）
workflow.add_edge("Research Manager", "Trader")
```

### 条件判断函数

```python
# conditional_logic.py

def should_continue_debate(self, state: AgentState) -> str:
    """判断辩论是否继续"""

    # 1. 达到最大轮数 → 结束辩论
    if state["investment_debate_state"]["count"] >= 2 * self.max_debate_rounds:
        return "Research Manager"

    # 2. Bull 刚说完 → Bear 回应
    if state["investment_debate_state"]["current_response"].startswith("Bull"):
        return "Bear Researcher"

    # 3. Bear 刚说完 → Bull 回应
    return "Bull Researcher"
```

### 流程图

```
Bull Researcher
    ↓ (条件判断)
    ├── count >= 2*max_rounds → Research Manager (结束)
    └── current_response 以 "Bull" 开头 → Bear Researcher
                                          ↓
Bear Researcher
    ↓ (条件判断)
    ├── count >= 2*max_rounds → Research Manager (结束)
    └── current_response 以 "Bear" 开头 → Bull Researcher (循环)
                                          ↓
... 循环直到 count 达上限 ...

Research Manager → Trader
```

### 辩论计数逻辑

```
max_debate_rounds = 1

Bull 第1轮: count = 1, current_response = "Bull Analyst: ..."
    ↓ (条件: count < 2, 以 Bull 开头) → Bear
Bear 第1轮: count = 2, current_response = "Bear Analyst: ..."
    ↓ (条件: count < 2, 以 Bear 开头) → Bull
Bull 第2轮: count = 3, current_response = "Bull Analyst: ..."
    ↓ (条件: count >= 2) → Research Manager (结束)
```

**count >= 2 * max_debate_rounds**：每个 max_round 包含 Bull + Bear 各发言一次

---

## 阶段3：交易团队

简单固定顺序：

```python
# Research Manager → Trader（固定边）
workflow.add_edge("Research Manager", "Trader")

# Trader → Aggressive Analyst（固定边）
workflow.add_edge("Trader", "Aggressive Analyst")
```

---

## 阶段4：风险团队的流程控制

### 节点添加

```python
# setup.py

workflow.add_node("Aggressive Analyst", aggressive_analyst)
workflow.add_node("Neutral Analyst", neutral_analyst)
workflow.add_node("Conservative Analyst", conservative_analyst)
workflow.add_node("Portfolio Manager", portfolio_manager_node)
```

### 边的定义

```python
# Aggressive → 条件判断 → Conservative 或 Portfolio Manager
workflow.add_conditional_edges(
    "Aggressive Analyst",
    self.conditional_logic.should_continue_risk_analysis,
    {
        "Conservative Analyst": "Conservative Analyst",
        "Portfolio Manager": "Portfolio Manager",
    },
)

# Conservative → 条件判断 → Neutral 或 Portfolio Manager
workflow.add_conditional_edges(
    "Conservative Analyst",
    self.conditional_logic.should_continue_risk_analysis,
    {
        "Neutral Analyst": "Neutral Analyst",
        "Portfolio Manager": "Portfolio Manager",
    },
)

# Neutral → 条件判断 → Aggressive（循环）或 Portfolio Manager
workflow.add_conditional_edges(
    "Neutral Analyst",
    self.conditional_logic.should_continue_risk_analysis,
    {
        "Aggressive Analyst": "Aggressive Analyst",
        "Portfolio Manager": "Portfolio Manager",
    },
)

# Portfolio Manager → END
workflow.add_edge("Portfolio Manager", END)
```

### 条件判断函数

```python
# conditional_logic.py

def should_continue_risk_analysis(self, state: AgentState) -> str:
    """判断风险辩论是否继续"""

    # 1. 达到最大轮数 → 结束辩论
    if state["risk_debate_state"]["count"] >= 3 * self.max_risk_discuss_rounds:
        return "Portfolio Manager"

    # 2. Aggressive 刚说完 → Conservative
    if state["risk_debate_state"]["latest_speaker"].startswith("Aggressive"):
        return "Conservative Analyst"

    # 3. Conservative 刚说完 → Neutral
    if state["risk_debate_state"]["latest_speaker"].startswith("Conservative"):
        return "Neutral Analyst"

    # 4. Neutral 刚说完 → Aggressive（循环）
    return "Aggressive Analyst"
```

### 流程图（三角辩论）

```
Aggressive Analyst
    ↓ (条件判断)
    ├── count >= 3*max_rounds → Portfolio Manager (结束)
    └── latest_speaker = "Aggressive" → Conservative Analyst
                                        ↓
Conservative Analyst
    ↓ (条件判断)
    ├── count >= 3*max_rounds → Portfolio Manager (结束)
    └── latest_speaker = "Conservative" → Neutral Analyst
                                          ↓
Neutral Analyst
    ↓ (条件判断)
    ├── count >= 3*max_rounds → Portfolio Manager (结束)
    └── latest_speaker = "Neutral" → Aggressive Analyst (循环)
                                     ↓
... 循环直到 count 达上限 ...

Portfolio Manager → END
```

### 辩论计数逻辑

```
max_risk_discuss_rounds = 1

Aggressive: count = 1, latest_speaker = "Aggressive Analyst"
    ↓ → Conservative
Conservative: count = 2, latest_speaker = "Conservative Analyst"
    ↓ → Neutral
Neutral: count = 3, latest_speaker = "Neutral Analyst"
    ↓ (条件: count >= 3) → Portfolio Manager (结束)
```

**count >= 3 * max_risk_discuss_rounds**：每个 round 包含 3 人各发言一次

---

## 完整流程图

```
START
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Market Analyst ←→ tools_market (循环)                      │
│         ↓ Msg Clear Market                                  │
│  Social Analyst ←→ tools_social (循环)                      │
│         ↓ Msg Clear Social                                  │
│  News Analyst ←→ tools_news (循环)                          │
│         ↓ Msg Clear News                                    │
│  Fundamentals Analyst ←→ tools_fundamentals (循环)          │
│         ↓ Msg Clear Fundamentals                            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Bull Researcher ←→ Bear Researcher (循环辩论)              │
│         ↓ (达到 max_debate_rounds)                          │
│  Research Manager                                           │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Trader                                                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Aggressive → Conservative → Neutral → Aggressive (循环)    │
│         ↓ (达到 max_risk_discuss_rounds)                    │
│  Portfolio Manager                                          │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
  END
```

---

## 代码与流程对照表

| 流程阶段 | 代码文件 | 关键函数 |
|---------|---------|---------|
| 节点添加 | setup.py | `add_node()` |
| 固定顺序 | setup.py | `add_edge()` |
| 条件分支 | setup.py | `add_conditional_edges()` |
| 分析师判断 | conditional_logic.py | `should_continue_xxx()` |
| 辩论判断 | conditional_logic.py | `should_continue_debate()` |
| 风险判断 | conditional_logic.py | `should_continue_risk_analysis()` |
| 编译执行 | setup.py | `workflow.compile()` |
| 运行 | trading_graph.py | `graph.invoke()` / `graph.stream()` |

---

## 条件判断的核心逻辑

### 分析师：看 tool_calls

```python
if last_message.tool_calls:
    return "tools_xxx"  # 继续调用工具
return "Msg Clear xxx"  # 结束，进入下一个
```

**Agent 自己决定**：通过 tool_calls 表示"我还需要数据"

### 研究团队：看 count + current_response

```python
if count >= 2 * max_rounds:
    return "Research Manager"  # 达上限，结束
if current_response.startswith("Bull"):
    return "Bear Researcher"   # Bull 说完，Bear 回应
return "Bull Researcher"       # Bear 说完，Bull 回应
```

**规则驱动**：轮数上限 + 发言顺序

### 风险团队：看 count + latest_speaker

```python
if count >= 3 * max_rounds:
    return "Portfolio Manager"     # 达上限，结束
if latest_speaker.startswith("Aggressive"):
    return "Conservative Analyst"  # Aggressive → Conservative
if latest_speaker.startswith("Conservative"):
    return "Neutral Analyst"       # Conservative → Neutral
return "Aggressive Analyst"        # Neutral → Aggressive (循环)
```

**三角循环**：Aggressive → Conservative → Neutral → Aggressive

---

## 执行方式

### invoke（一次性执行）

```python
final_state = graph.invoke(init_state, config={"recursion_limit": 100})
```

### stream（流式执行，调试用）

```python
for chunk in graph.stream(init_state):
    chunk["messages"][-1].pretty_print()  # 打印每一步
```

---

## 设计总结

| 设计模式 | 说明 |
|---------|------|
| **节点职责单一** | 每个节点只做一件事 |
| **条件函数分离** | 判断逻辑写在 conditional_logic.py |
| **状态驱动** | 条件判断从 state 读取信息 |
| **循环上限** | recursion_limit + count 防止无限循环 |
| **固定 + 条件组合** | 主流程固定，子循环条件控制 |

**核心思想**：流程是预先定义的"剧本"，Agent 只演好自己的角色，LangGraph 是"导演"控制谁上场、什么时候结束。