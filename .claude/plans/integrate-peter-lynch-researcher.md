# 集成 Peter Lynch Researcher 智能体计划

## Context

**目标**：从 `origin/feature/peter-lynch-researcher` 分支提取 Peter Lynch Researcher 智能体，集成到 main 分支。

**挑战**：
- 该分支删除了 `datasource/datahub/servers` 目录（与 main 的 datahub 架构冲突）
- 该分支删除了 `web2`（刚提交的前端）
- 该分支重构了工具调用方式（从 `load_agent_tools` 改为直接导入函数）

**策略**：只提取 Peter Lynch Researcher 相关改动，保留 main 的架构。

---

## 架构理解

### 当前辩论架构（基于 docs/agent-architecture.md）

```
Bull Researcher ←──辩论──→ Bear Researcher
     ↓                              ↓
     └──────────────────────────────┘
                    ↓
            Research Manager
                    ↓
                  Trader
```

- **状态结构**：`InvestDebateState` 包含 `bull_history`, `bear_history`, `history`, `current_response`, `count`
- **辩论轮数**：`count >= 2 * max_debate_rounds` 时结束
- **路由逻辑**：`current_response` 以 "Bull" 开头 → Bear，否则 → Bull

### 目标辩论架构（三方辩论）

```
Bull Researcher ←──辩论──→ Bear Researcher ←──辩论──→ Peter Lynch Researcher
     ↓                              ↓                              ↓
     └──────────────────────────────┴──────────────────────────────┘
                                   ↓
                          Research Manager
                                   ↓
                                 Trader
```

- **状态结构**：添加 `peter_lynch_history`
- **辩论轮数**：`count >= 3 * max_debate_rounds` 时结束（三方辩论）
- **路由逻辑**：类似风险管理的三方循环（Aggressive → Conservative → Neutral → 循环）

### Peter Lynch Researcher 定位

**角色**：Peter Lynch 风格分析师，参与 Bull/Bear 辩论循环，提供独特的价值-成长视角。

**分析方法**：
- 6 种股票分类（Slow Grower, Stalwart, Fast Grower, Cyclical, Turnaround, Asset Play）
- PEG 评估（P/E(TTM) / Net Income Growth Rate）
- 业务质量、增长可持续性分析
- 市场预期差距识别

---

## 需要修改的文件

### 1. 新增文件

| 文件 | 内容 |
|------|------|
| `tradingagents/agents/researchers/peter_lynch_researcher.py` | Peter Lynch Researcher 智能体实现 |

### 2. 修改文件

| 文件 | 改动 |
|------|------|
| `tradingagents/agents/utils/agent_states.py` | 添加 `peter_lynch_history` 到 InvestDebateState |
| `tradingagents/agents/researchers/bull_researcher.py` | 添加 `peter_lynch_history` 到返回 state（保持不变） |
| `tradingagents/agents/researchers/bear_researcher.py` | 添加 `peter_lynch_history` 到返回 state（保持不变） |
| `tradingagents/graph/setup.py` | 创建 Peter Lynch node，添加三方辩论路由 |
| `tradingagents/graph/trading_graph.py` | 创建 peter_lynch_memory，传递给 setup |
| `tradingagents/graph/reflection.py` | 添加 reflect_peter_lynch_researcher 方法 |
| `tradingagents/graph/conditional_logic.py` | 更新辩论路由逻辑（三方循环） |
| `web/dashboard.py` | 多处前端配置（详见下方） |
| `web2/lib/types.ts` | 更新 WORKFLOW_BLUEPRINT 的 Research Team roles |
| `web/translation/translated_run_materializer.py` | 添加 `2_research/peter_lynch.md` 到翻译列表 |

**注意**：Peter Lynch Researcher 和 Bull/Bear一样，**不需要配置工具**（基于架构文档）。

**架构分层**（基于 docs/agent-architecture.md）：
- **分析师层**：有工具绑定（在 agents_registry.yaml 配置）
- **研究员层**：无工具绑定，基于分析师报告辩论（Bull, Bear, Peter Lynch）
- **交易员/风险管理层**：无工具，基于上层报告决策/辩论

---

## 详细改动说明

### 1. peter_lynch_researcher.py（新增）

从分支提取，关键结构：

```python
DATA_ACCURACY_INSTRUCTION = """
DATA ACCURACY: Quote EXACT numbers from the reports. Cite sources: "fundamentals_report: inventory = 14.50 billion"
"""


def create_peter_lynch_researcher(llm, memory):
    def peter_lynch_node(state) -> dict:
        # 获取 peter_lynch_history
        peter_lynch_history = investment_debate_state.get("peter_lynch_history", "")

        # prompt 使用 DATA_ACCURACY_INSTRUCTION（与 Bull/Bear 一致）
        prompt = f"""...
{DATA_ACCURACY_INSTRUCTION}
..."""

        # 返回更新后的 state
        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "peter_lynch_history": peter_lynch_history + "\n" + argument,
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }
        return {"investment_debate_state": new_investment_debate_state}

    return peter_lynch_node
```

**适配说明**：
- **移除**：时间上下文约束（main 分支暂不合并）
- **保留**：数字准确性约束，但使用 main 分支风格（DATA_ACCURACY_INSTRUCTION）
- **新增**：`DATA_ACCURACY_INSTRUCTION` 常量（与 bull_researcher.py / bear_researcher.py 一致）

### 2. agent_states.py

添加字段：

```python
class InvestDebateState(TypedDict):
    bull_history: Annotated[str, "Bullish Conversation history"]
    bear_history: Annotated[str, "Bearish Conversation history"]
    peter_lynch_history: Annotated[str, "Peter Lynch style Conversation history"]  # 新增
    history: Annotated[str, "Conversation history"]
    current_response: Annotated[str, "Latest response"]
    judge_decision: Annotated[str, "Final judge decision"]
    count: Annotated[int, "Length of the current conversation"]
```

### 3. bull_researcher.py / bear_researcher.py

修改返回结构，添加 `peter_lynch_history`（保持不变）：

```python
new_investment_debate_state = {
    "history": history + "\n" + argument,
    "bull_history": bull_history + "\n" + argument,  # Bull 更新自己的
    "bear_history": investment_debate_state.get("bear_history", ""),  # 保持 Bear 不变
    "peter_lynch_history": investment_debate_state.get("peter_lynch_history", ""),  # 新增：保持 Peter Lynch 不变
    "current_response": argument,
    "count": investment_debate_state["count"] + 1,
}
```

**原因**：LangGraph state 要求每个节点返回完整的 state 字段，否则未返回的字段会被丢弃。

### 4. setup.py

改动：

1. `__init__` 添加 `peter_lynch_memory` 参数
2. 创建 `peter_lynch_researcher_node`
3. 添加节点：`workflow.add_node("Peter Lynch Researcher", peter_lynch_researcher_node)`
4. 更新辩论路由（三方循环）

```python
# __init__ 添加参数
def __init__(
    self,
    ...
    bull_memory,
    bear_memory,
    peter_lynch_memory,  # 新增
    ...
)

# 创建 node
peter_lynch_researcher_node = create_peter_lynch_researcher(
    self.quick_thinking_llm, self.peter_lynch_memory
)

# 添加三方辩论路由
workflow.add_conditional_edges(
    "Bull Researcher",
    self.conditional_logic.should_continue_debate,
    {
        "Bear Researcher": "Bear Researcher",
        "Peter Lynch Researcher": "Peter Lynch Researcher",  # 新增
        "Research Manager": "Research Manager",
    },
)
# Bear → Peter Lynch 或 Bull
workflow.add_conditional_edges(
    "Bear Researcher",
    self.conditional_logic.should_continue_debate,
    {
        "Bull Researcher": "Bull Researcher",
        "Peter Lynch Researcher": "Peter Lynch Researcher",  # 新增
        "Research Manager": "Research Manager",
    },
)
# Peter Lynch → Bull 或 Research Manager
workflow.add_conditional_edges(
    "Peter Lynch Researcher",
    self.conditional_logic.should_continue_debate,
    {
        "Bull Researcher": "Bull Researcher",
        "Research Manager": "Research Manager",
    },
)
```

### 5. trading_graph.py

改动：

1. 创建 `peter_lynch_memory`
2. 传递给 `GraphSetup`
3. 在 `reflect_and_remember` 中调用 reflection
4. 在 `_log_state` 中保存 `peter_lynch_history`

```python
# 创建 memory
self.peter_lynch_memory = FinancialSituationMemory("peter_lynch_memory", self.config)

# 传递给 setup
self.graph_setup = GraphSetup(
    ...
    self.bull_memory,
    self.bear_memory,
    self.peter_lynch_memory,  # 新增
    ...
)

# reflection
def reflect_and_remember(self, returns_losses):
    ...
    self.reflector.reflect_peter_lynch_researcher(
        self.curr_state, returns_losses, self.peter_lynch_memory
    )

# log state
"investment_debate_state": {
    ...
    "peter_lynch_history": final_state["investment_debate_state"]["peter_lynch_history"],
    ...
}
```

### 6. reflection.py

添加方法：

```python
def reflect_peter_lynch_researcher(self, current_state, returns_losses, peter_lynch_memory):
    """Reflect on Peter Lynch researcher's analysis and update memory."""
    situation = self._extract_current_situation(current_state)
    peter_lynch_history = current_state["investment_debate_state"]["peter_lynch_history"]

    result = self._reflect_on_component(
        "PETER LYNCH", peter_lynch_history, situation, returns_losses
    )
    peter_lynch_memory.add_situations([(situation, result)])
```

### 7. conditional_logic.py

更新 `should_continue_debate`（三方循环逻辑）：

```python
def should_continue_debate(self, state: AgentState) -> str:
    """Determine if debate should continue (3-party cycle)."""

    # 三方辩论：count >= 3 * max_debate_rounds 时结束
    if state["investment_debate_state"]["count"] >= 3 * self.max_debate_rounds:
        return "Research Manager"

    # 根据 current_response 判断下一个是谁
    current_response = state["investment_debate_state"]["current_response"]

    if current_response.startswith("Bull"):
        return "Bear Researcher"
    if current_response.startswith("Bear"):
        return "Peter Lynch Researcher"
    if current_response.startswith("Peter Lynch"):
        return "Bull Researcher"

    # 默认（第一轮）
    return "Bull Researcher"
```

### 8. translated_run_materializer.py

添加翻译文件：

```python
TRANSLATABLE_RUN_FILES = (
    ...
    "2_research/bull.md",
    "2_research/bear.md",
    "2_research/peter_lynch.md",  # 新增
    "2_research/manager.md",
    ...
)
```

### 9. web/dashboard.py（前端配置 - 多处修改）

**修改 RUNTIME_AGENT_FILE_MAP**（第89-102行）：

```python
RUNTIME_AGENT_FILE_MAP = {
    ...
    "Bull Researcher": Path("2_research/bull.md"),
    "Bear Researcher": Path("2_research/bear.md"),
    "Peter Lynch Researcher": Path("2_research/peter_lynch.md"),  # 新增
    "Research Manager": Path("2_research/manager.md"),
    ...
}
```

**修改 RUNTIME_AGENT_EVENT_HEADINGS**（第103-111行）：

```python
RUNTIME_AGENT_EVENT_HEADINGS = {
    "Bull Researcher": "### Bull Researcher Analysis",
    "Bear Researcher": "### Bear Researcher Analysis",
    "Peter Lynch Researcher": "### Peter Lynch Researcher Analysis",  # 新增
    "Research Manager": "### Research Manager Decision",
    ...
}
```

**修改 RUNTIME_SECTION_MEMBERS**（第112-129行）：

```python
RUNTIME_SECTION_MEMBERS = {
    ...
    "investment_plan": [
        ("Bull Researcher", "### Bull Researcher Analysis"),
        ("Bear Researcher", "### Bear Researcher Analysis"),
        ("Peter Lynch Researcher", "### Peter Lynch Researcher Analysis"),  # 新增
        ("Research Manager", "### Research Manager Decision"),
    ],
    ...
}
```

**修改 _sync_runtime_member_outputs**（第724-773行）：

```python
def _sync_runtime_member_outputs(self, *, run_dir: Path, chunk: Dict[str, Any]) -> None:
    ...
    debate_state = chunk.get("investment_debate_state") or {}
    judge = str(debate_state.get("judge_decision") or "").strip()
    if judge:
        bull_hist = str(debate_state.get("bull_history") or "").strip()
        bear_hist = str(debate_state.get("bear_history") or "").strip()
        peter_lynch_hist = str(debate_state.get("peter_lynch_history") or "").strip()  # 新增
        if bull_hist:
            member_outputs.append(("Bull Researcher", bull_hist))
        if bear_hist:
            member_outputs.append(("Bear Researcher", bear_hist))
        if peter_lynch_hist:  # 新增
            member_outputs.append(("Peter Lynch Researcher", peter_lynch_hist))
        member_outputs.append(("Research Manager", judge))
    ...
```

### 10. web2/lib/types.ts（前端类型定义）

**修改 WORKFLOW_BLUEPRINT**（第194-220行）：

```typescript
export const WORKFLOW_BLUEPRINT = [
  {
    id: "analysts",
    title: "Analyst Team",
    roles: ["market", "social", "news", "fundamentals"],
  },
  {
    id: "research",
    title: "Research Team",
    roles: ["Bull Researcher", "Bear Researcher", "Peter Lynch Researcher", "Research Manager"],  // 新增 Peter Lynch
  },
  ...
]
```

---

## Implementation 步骤

```
Step 1: 创建 peter_lynch_researcher.py
        - 从分支提取文件内容
        - 移除时间上下文约束
        - 使用 DATA_ACCURACY_INSTRUCTION（与 Bull/Bear 一致）

Step 2: 修改 agent_states.py
        - 添加 peter_lynch_history 字段

Step 3: 修改 bull_researcher.py 和 bear_researcher.py
        - 添加 peter_lynch_history 到返回 state（保持不变）

Step 4: 修改 setup.py
        - 添加 peter_lynch_memory 参数
        - 创建 Peter Lynch node
        - 更新辩论路由（三方循环）

Step 5: 修改 trading_graph.py
        - 创建 peter_lynch_memory
        - 传递给 setup
        - 添加 reflection 调用
        - 添加 log state

Step 6: 修改 reflection.py
        - 添加 reflect_peter_lynch_researcher 方法

Step 7: 修改 conditional_logic.py
        - 更新辩论路由逻辑（三方循环）

Step 8: 修改 web/dashboard.py（前端配置）
        - RUNTIME_AGENT_FILE_MAP 添加 Peter Lynch 文件路径
        - RUNTIME_AGENT_EVENT_HEADINGS 添加事件标题
        - RUNTIME_SECTION_MEMBERS 更新 investment_plan 成员
        - _sync_runtime_member_outputs 添加 peter_lynch_history 同步

Step 9: 修改 web2/lib/types.ts（前端类型）
        - WORKFLOW_BLUEPRINT 更新 Research Team roles

Step 10: 修改 translated_run_materializer.py
        - 添加 2_research/peter_lynch.md 到翻译文件列表

Step 11: 测试验证
        - 运行 tradingagents test 验证新智能体工作
        - 打开 Dashboard 验证前端显示
```

---

## Verification

运行测试：
```bash
uv run tradingagents test 600519.SH --date 2026-04-19
```

检查：
- 辩论流程包含 Peter Lynch Researcher（三方循环）
- `investment_debate_state` 包含 `peter_lynch_history`
- 分析输出包含 Lynch 风格的股票分类和 PEG 评估
- 辩论轮数正确（3 * max_debate_rounds）

前端验证：
```bash
uv run python -m web
# 浏览器打开 http://localhost:8765
```

检查：
- Workflow Overview 显示 "Peter Lynch Researcher"
- Research Team 阶段显示 4 个智能体（Bull, Bear, Peter Lynch, Manager）
- 分析结果包含 Peter Lynch 的分析报告

---

## 不提取的内容

保留 main 分支的：
- `datasource/datahub/servers/` 架构
- `web2` 前端
- `load_agent_tools` 工具加载方式
- 时间上下文功能（暂不合并）
- 新增的 `research_company_news`, `research_macro_news` 工具（需要额外处理）

---

*文档版本：2026-04-19*