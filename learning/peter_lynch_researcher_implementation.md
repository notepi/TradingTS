# Peter Lynch Researcher 实现

## 概述

在研究团队添加第三个研究员：Peter Lynch Researcher，提供"股票分类 + 价值成长"视角。

---

## 辩论流程变化

### 原流程（2人）

```
Bull → Bear → Bull → Bear → Research Manager
（共 2 * max_debate_rounds 次发言）
```

### 新流程（3人）

```
Bull → Bear → Peter Lynch → Bull → Bear → Peter Lynch → ... → Research Manager
（共 3 * max_debate_rounds 次发言）
```

---

## Peter Lynch Researcher 核心设计

### Prompt 要点

| 要点 | 内容 |
|------|------|
| **先分类** | 6种股票类型：Slow Grower, Stalwart, Fast Grower, Cyclical, Turnaround, Asset Play |
| **PEG评估** | P/E / Growth Rate，<1 为低估 |
| **业务理解** | 卖什么、谁买、为什么赢 |
| **增长持续性** | 收入/利润增长是否真实可持续 |
| **市场预期差** | 市场是否忽视或错误定价 |
| **输出格式** | 分类 → Lynch分析 → 投资视角 → 回应前一位分析师 |

### 与 Bull/Bear 的区别

| Agent | 视角 | 逻辑 |
|-------|------|------|
| Bull | 看涨 | 利好因素罗列 |
| Bear | 看跌 | 风险因素罗列 |
| Peter Lynch | 分类+价值 | 先判断股票类型，再按类型评估 |

---

## 修改的文件清单

### 核心框架文件（9个）

| 文件 | 修改内容 |
|------|---------|
| `tradingagents/agents/utils/agent_states.py` | InvestDebateState 新增 `peter_lynch_history` |
| `tradingagents/agents/researchers/peter_lynch_researcher.py` | **新建**，研究员工厂函数 |
| `tradingagents/agents/researchers/bull_researcher.py` | 状态更新包含新字段 |
| `tradingagents/agents/researchers/bear_researcher.py` | 状态更新包含新字段 |
| `tradingagents/agents/managers/research_manager.py` | 状态返回包含新字段 |
| `tradingagents/agents/__init__.py` | 导出新研究员 |
| `tradingagents/graph/conditional_logic.py` | `should_continue_debate` 支持3人循环 |
| `tradingagents/graph/propagation.py` | 初始状态添加字段 |
| `tradingagents/graph/trading_graph.py` | memory 初始化 + 反思调用 + 日志 |
| `tradingagents/graph/setup.py` | 添加节点和边 |
| `tradingagents/graph/reflection.py` | 添加反思方法 |

### CLI/Web 相关文件（6个）

| 文件 | 修改内容 |
|------|---------|
| `cli/dashboard.py` | 显示 Peter Lynch 辩论历史 |
| `cli/main.py` | 报告输出包含 Peter Lynch |
| `cli/reporting.py` | 报告生成包含 Peter Lynch |
| `cli/analysis_runtime.py` | 运行时显示 Peter Lynch 分析 |
| `cli/history_loader.py` | 历史加载包含 Peter Lynch |
| `cli/static/dashboard.html` | 研究团队角色列表添加 Peter Lynch |

### 测试文件（1个）

| 文件 | 修改内容 |
|------|---------|
| `tests/test_dashboard_runtime.py` | 测试数据包含 `peter_lynch_history` |

### 翻译

✅ **不需要修改** - 翻译是 LLM 动态处理，无硬编码映射

---

## 条件判断逻辑

```python
def should_continue_debate(self, state: AgentState) -> str:
    # 达上限 → 结束
    if state["investment_debate_state"]["count"] >= 3 * self.max_debate_rounds:
        return "Research Manager"

    # 循环顺序：Bull → Bear → Peter Lynch → Bull
    current = state["investment_debate_state"]["current_response"]
    if current.startswith("Bull"):
        return "Bear Researcher"
    if current.startswith("Bear"):
        return "Peter Lynch Researcher"
    return "Bull Researcher"
```

---

## 状态更新逻辑

```python
# Peter Lynch 发言后更新
new_investment_debate_state = {
    "history": history + "\n" + argument,
    "bull_history": investment_debate_state.get("bull_history", ""),
    "bear_history": investment_debate_state.get("bear_history", ""),
    "peter_lynch_history": peter_lynch_history + "\n" + argument,
    "current_response": argument,
    "count": investment_debate_state["count"] + 1,
}
```

---

## 验证方法

1. **语法检查**: `python -m py_compile xxx.py`
2. **运行测试**: `uv run python main.py`
3. **日志检查**: 查看 `eval_results/{ticker}/TradingAgentsStrategy_logs/`

---

## 设计启示

1. **参考风险团队**：风险团队已实现三角辩论（Aggressive→Conservative→Neutral），可借鉴
2. **状态完整性**：新增字段后，所有研究员都需要返回该字段（即使不修改）
3. **流程一致性**：条件判断的返回值需要与 `add_conditional_edges` 的路由字典匹配