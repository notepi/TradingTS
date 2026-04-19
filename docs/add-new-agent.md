# 添加新智能体指南

本文档记录添加新智能体到 TradingAgents 系统的完整流程。

---

## 核心概念：LangGraph State 传递

**关键规则**：每个节点必须返回完整的 state 字段，否则未返回的字段会被丢弃。

### 示例

假设 `InvestDebateState` 有 3 个字段：
```python
class InvestDebateState(TypedDict):
    bull_history: str
    bear_history: str
    peter_lynch_history: str  # 新增字段
```

如果 Bull Researcher 返回时漏掉 `peter_lynch_history`：
```python
# 错误 - 会丢失 peter_lynch_history
new_state = {
    "bull_history": "...",
    "bear_history": "...",
    # 缺少 peter_lynch_history
}

# 正确 - 保持所有字段
new_state = {
    "bull_history": "...",
    "bear_history": "...",
    "peter_lynch_history": investment_debate_state.get("peter_lynch_history", ""),
}
```

---

## 架构图

### 添加智能体整体流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        添加新智能体流程                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. 设计阶段                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  • 确定智能体角色（如：Peter Lynch → 成长股评估）              │   │
│  │  • 设计分析框架（如：6 种股票分类 + PEG 评估）                 │   │
│  │  • 定义与现有智能体的协作关系                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                            ↓                                        │
│  2. 后端实现                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  researcher 新文件 ──→ agent_states.py (新字段)              │   │
│  │         ↓                    ↓                               │   │
│  │  propagation.py ──→ bull/bear_researcher.py (保持字段)       │   │
│  │         ↓                    ↓                               │   │
│  │  research_manager.py ──→ setup.py + conditional_logic.py     │   │
│  │         ↓                    ↓                               │   │
│  │  reflection.py ──→ trading_graph.py ──→ agents/__init__.py   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                            ↓                                        │
│  3. 前端配置                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  web2/lib/types.ts ──→ web/dashboard.py                      │   │
│  │         ↓                    ↓                               │   │
│  │  dashboard.html ──→ translated_run_materializer.py           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                            ↓                                        │
│  4. 验证阶段                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  CLI 测试 ──→ 检查 .md 文件生成                               │   │
│  │  Dashboard ──→ 检查 agent 数量显示                            │   │
│  │  内容审查 ──→ 检查分析是否符合设计                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### LangGraph 状态传递（关键机制）

```
                    InvestDebateState
    ┌────────────────────────────────────────────┐
    │  bull_history      │ 多轮辩论历史          │
    │  bear_history      │ 多轮辩论历史          │
    │  peter_lynch_history │ 新增：必须传递      │
    │  history           │ 总辩论记录            │
    │  current_response  │ 当前响应              │
    │  count             │ 辩论轮数              │
    └────────────────────────────────────────────┘
                         ↓
    ════════════════════════════════════════════════
    ⚠️ 规则：每个节点必须返回完整 state
    ════════════════════════════════════════════════
                         ↓
    ┌──────────┐   ┌──────────┐   ┌──────────────────┐
    │   Bull   │ → │   Bear   │ → │ Peter Lynch     │
    │Researcher│   │Researcher│   │  Researcher     │
    └──────────┘   └──────────┘   └──────────────────┘
         ↓              ↓                   ↓
    ┌──────────────────────────────────────────────┐
    │         Research Manager (汇总判断)           │
    │  return {                                    │
    │    bull_history,      ← 必须包含             │
    │    bear_history,      ← 必须包含             │
    │    peter_lynch_history, ← 必须包含 (易遗漏!) │
    │    ...                                       │
    │  }                                           │
    └──────────────────────────────────────────────┘
```

### 辩论循环流程

```
    ┌──────────────────────────────────────────────────────────┐
    │                      辩论循环                             │
    │                                                          │
    │   Bull Researcher                                        │
    │        │                                                 │
    │        ↓                                                 │
    │   Bear Researcher  ←── 反驳 Bull                         │
    │        │                                                 │
    │        ↓                                                 │
    │   Peter Lynch Researcher  ←── 补充视角                   │
    │        │                                                 │
    │        ↓                                                 │
    │   Research Manager                                       │
    │        │                                                 │
    │        ├─→ count < max? ──→ 返回 Bull (继续辩论)         │
    │        │                                                 │
    │        └─→ count >= max? ──→ 输出最终判断                │
    │                                                          │
    └──────────────────────────────────────────────────────────┘
```

---

## Checklist

### 1. 后端修改

| 文件 | 操作 |
|------|------|
| `agent_states.py` | 添加新字段到对应 State TypedDict |
| `propagation.py` | 初始化时包含新字段（空字符串） |
| `researchers/*.py` | 新智能体实现文件 |
| `bull/bear_researcher.py` | 返回 state 时保持新字段不变 |
| `research_manager.py` | **关键**：返回 state 包含新字段 |
| `setup.py` | 创建 node，添加路由 |
| `conditional_logic.py` | 更新路由逻辑 |
| `reflection.py` | 添加 reflection 方法 |
| `trading_graph.py` | 创建 memory，传递给 setup |
| `agents/__init__.py` | 导入并导出新函数 |

### 2. 前端修改

| 文件 | 操作 |
|------|------|
| `web2/lib/types.ts` | `WORKFLOW_BLUEPRINT.roles` 添加新角色 |
| `web/dashboard.py` | `RUNTIME_AGENT_FILE_MAP` 添加文件路径 |
| `web/dashboard.py` | `RUNTIME_AGENT_EVENT_HEADINGS` 添加标题 |
| `web/dashboard.py` | `_sync_runtime_member_outputs` 同步新字段 |
| `web/static/dashboard.html` | `roles` 数组添加新角色 |
| `translated_run_materializer.py` | 添加翻译文件路径 |

---

## 验证步骤

1. **后端验证**：
```bash
uv run tradingagents test 600519.SH --date 2026-04-19
```
检查 `results/.../2_research/` 目录是否生成新智能体的 `.md` 文件。

2. **前端验证**：
```bash
uv run python -m web
```
检查 Workflow Overview 是否显示新智能体，数量是否正确（如 "0/4 agents"）。

3. **内容验证**：
打开生成的 `.md` 文件，检查是否包含预期的分析内容。

---

## 常见问题

### 问题：新智能体的 `.md` 文件没有生成

**原因**：`research_manager.py` 返回 state 时缺少新字段。

**解决**：检查所有返回 `new_investment_debate_state` 的节点是否包含新字段。

### 问题：前端显示 agent 数量不对

**原因**：前端配置遗漏。

**解决**：检查 `dashboard.html`、`dashboard.py`、`types.ts` 三处是否都已添加新角色。

---

## 参考案例

Peter Lynch Researcher 集成：commit `eaaf32e`