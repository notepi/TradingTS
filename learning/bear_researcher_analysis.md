# Bear Researcher 分析

## 关键区别：研究团队不调用工具

```
┌─────────────────────────────────────────────────────────────┐
│               分析团队 vs 研究团队                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  分析团队 (Market Analyst 等)                               │
│  ┌─────────────────────────────────────────────┐           │
│  │  Agent → 调用工具 → 获取数据 → 分析 → 报告    │           │
│  │         (get_stock_data, get_indicators...)  │           │
│  └─────────────────────────────────────────────┘           │
│                                                             │
│  研究团队 (Bull/Bear Researcher)                            │
│  ┌─────────────────────────────────────────────┐           │
│  │  Agent → 读 state → 生成论点 → 写入 state    │           │
│  │         (无工具调用，纯辩论)                  │           │
│  └─────────────────────────────────────────────┘           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 为什么不调用工具？

| 原因 | 说明 |
|------|------|
| **分工明确** | 分析团队负责获取数据，研究团队负责解读数据 |
| **避免重复** | 数据已经获取过了，不需要再调用 |
| **聚焦辩论** | 研究团队的任务是"辩论"，不是"收集信息" |
| **效率优化** | 减少不必要的 API 调用和 token 消耗 |

---

## 角色定位

```
Bear Researcher = 看跌分析师 + 辩论参与者
```

**与 Bull 的关系**：
- Bull 强调利好（看涨）
- Bear 强调风险（看跌）
- 互相辩论，为裁判提供多角度视角

---

## 能读取什么（全部来自 state）

| 数据源 | 内容 | 来源 |
|--------|------|------|
| market_report | 技术分析报告 | Market Analyst |
| sentiment_report | 情绪分析报告 | Social Analyst |
| news_report | 新闻分析报告 | News Analyst |
| fundamentals_report | 基本面分析报告 | Fundamentals Analyst |
| history | 辩论历史 | investment_debate_state |
| current_response | Bull 最后说的话 | investment_debate_state |
| past_memories | 历史决策记忆 | memory 系统 |

**注意**：Bear 读取的"数据"是其他 Agent 的**分析报告**，不是原始数据。

---

## 完整 Prompt

```python
prompt = f"""You are a Bear Analyst making the case against investing in the stock.
Your goal is to present a well-reasoned argument emphasizing risks, challenges,
and negative indicators. Leverage the provided research and data to highlight
potential downsides and counter bullish arguments effectively.

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial
  instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market
  positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or
  recent adverse news to support your position.
- Bull Counterpoints: Critically analyze the bull argument with specific data
  and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Present your argument in a conversational style, directly engaging
  with the bull analyst's points and debating effectively rather than simply
  listing facts.

Resources available:

Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Company fundamentals report: {fundamentals_report}
Conversation history of the debate: {history}
Last bull argument: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}

Use this information to deliver a compelling bear argument, refute the bull's
claims, and engage in a dynamic debate that demonstrates the risks and weaknesses
of investing in the stock. You must also address reflections and learn from
lessons and mistakes you made in the past.
"""
```

---

## Prompt 解读

### 1. 角色设定

```
"You are a Bear Analyst making the case against investing in the stock."
```

明确告诉 Agent：你是看跌分析师，主张谨慎/卖出。

### 2. 任务描述

```
"present a well-reasoned argument emphasizing risks, challenges,
and negative indicators"
```

强调三点：
- 风险和挑战
- 竞争劣势
- 负面指标

### 3. 关键要点

| 要点 | 说明 |
|------|------|
| **Risks and Challenges** | 市场饱和、财务不稳定、宏观经济威胁 |
| **Competitive Weaknesses** | 市场地位弱、创新衰退、竞争对手威胁 |
| **Negative Indicators** | 财务数据、市场趋势、负面新闻 |
| **Bull Counterpoints** | 针对 Bull 的论点反驳，暴露弱点 |
| **Engagement** | 对话式辩论，不是列数据清单 |

### 4. 数据注入方式

```
Prompt 里直接嵌入报告内容：
    Market research report: {market_research_report}
    ...
```

**与 Market Analyst 的区别**：

| Agent | 数据来源 | Prompt 处理 |
|-------|---------|-------------|
| Market Analyst | 调用工具获取 | Prompt 告诉 Agent "可以调用哪些工具" |
| Bear Researcher | 从 state 读取 | Prompt 直接把报告内容嵌入 |

---

## 代码执行流程

```python
def bear_node(state) -> dict:
    # 1. 从 state 读取数据（不调用工具！）
    market_research_report = state["market_report"]
    sentiment_report = state["sentiment_report"]
    news_report = state["news_report"]
    fundamentals_report = state["fundamentals_report"]

    # 2. 从辩论状态读取历史
    investment_debate_state = state["investment_debate_state"]
    history = investment_debate_state.get("history", "")
    current_response = investment_debate_state.get("current_response", "")

    # 3. 从 memory 获取历史教训
    curr_situation = f"{market_research_report}\n{sentiment_report}..."
    past_memories = memory.get_memories(curr_situation, n_matches=2)

    # 4. 构建 Prompt（把报告内容嵌入）
    prompt = f"""...
    Market research report: {market_research_report}
    Last bull argument: {current_response}
    ..."""

    # 5. LLM 生成看跌论点（无工具调用）
    response = llm.invoke(prompt)

    # 6. 包装成辩论格式
    argument = f"Bear Analyst: {response.content}"

    # 7. 更新辩论状态
    return {"investment_debate_state": new_state}
```

---

## Bull vs Bear 对比

| 方面 | Bull Researcher | Bear Researcher |
|------|----------------|-----------------|
| **立场** | 看涨（买入） | 看跌（谨慎/卖出） |
| **强调** | 增长潜力、竞争优势、积极指标 | 风险挑战、竞争劣势、负面指标 |
| **反驳对象** | Bear 的论点 | Bull 的论点 |
| **数据来源** | state 中的报告 | state 中的报告 |
| **工具调用** | ❌ 无 | ❌ 无 |
| **输出格式** | `Bull Analyst: ...` | `Bear Analyst: ...` |

---

## 辩论流程

```
第1轮：
    Bull: 基于4份报告，提出看涨论点
        ↓
    Bear: 基于4份报告 + Bull论点，提出看跌论点

第2轮：
    Bull: 基于4份报告 + Bear反驳，继续辩论
        ↓
    Bear: 基于4份报告 + Bull反驳，继续辩论

...

第N轮：
    Bull/Bear 继续辩论，直到达到 max_debate_rounds
        ↓
    Research Manager: 读所有辩论历史，做裁决
```

### 辩论状态变化

```python
# 初始状态
investment_debate_state = {
    "history": "",
    "bull_history": "",
    "bear_history": "",
    "current_response": "",
    "count": 0,
}

# Bull 第1轮发言后
investment_debate_state = {
    "history": "Bull Analyst: [看涨论点]",
    "bull_history": "Bull Analyst: [看涨论点]",
    "bear_history": "",
    "current_response": "Bull Analyst: [看涨论点]",  # Bull 最后说的
    "count": 1,
}

# Bear 第1轮发言后
investment_debate_state = {
    "history": "Bull Analyst: [...]\nBear Analyst: [看跌论点]",
    "bull_history": "Bull Analyst: [...]",
    "bear_history": "Bear Analyst: [看跌论点]",
    "current_response": "Bear Analyst: [看跌论点]",  # Bear 最后说的
    "count": 2,
}
```

---

## current_response 的作用

```
current_response = 最后一个发言者的论点
```

**用途**：让下一个发言者知道要反驳什么。

| 发言者 | current_response 是什么 | 作用 |
|--------|------------------------|------|
| Bull（第1轮） | 空（没人说过） | 自由发挥，不看别人 |
| Bear（第1轮） | Bull 第1轮论点 | 针对 Bull 反驳 |
| Bull（第2轮） | Bear 第1轮论点 | 针对 Bear 反驳 |
| Bear（第2轮） | Bull 第2轮论点 | 针对 Bull 反驳 |

---

## 数据传递机制：从分析到研究

```
┌─────────────────────────────────────────────────────────────┐
│                    数据传递路径                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Market Analyst                                             │
│      ├── 调用 get_stock_data → 获取K线数据（10KB）           │
│      ├── 调用 get_indicators → 获取技术指标（5KB）           │
│      ├── 分析数据                                            │
│      └── 写报告 → market_report（500字）                     │
│                                                             │
│  Bear Researcher                                            │
│      ├── 读 market_report（500字，不是10KB原始数据）         │
│      ├── 读其他报告                                          │
│      └── 生成论点                                            │
│                                                             │
│  传递的是"结论"，不是"原始数据"                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 为什么这样设计？

| 设计 | 原因 |
|------|------|
| **报告是压缩的结论** | 原始数据太大，报告是精华 |
| **后续 Agent 不需要原始数据** | Bear 只需要知道"MACD金叉"，不需要244天K线 |
| **token 效率** | 传报告几百字，传原始数据几KB |
| **职责分离** | 分析团队负责"看数据"，研究团队负责"解读结论" |

---

## 无工具协同的关键设计

### 1. 状态字段专用化

```
state 结构：
    ├── messages (临时通信，工具调用记录)
    ├── market_report (Market Analyst 的结论)
    ├── sentiment_report (Social Analyst 的结论)
    ├── news_report (News Analyst 的结论)
    ├── fundamentals_report (Fundamentals Analyst 的结论)
    └── investment_debate_state (辩论状态)
```

**关键**：每个团队的产出存在专用字段，后续团队从字段读取，不需要从 messages 解析。

### 2. Prompt 嵌入数据

```python
# 不是告诉 Agent "你可以调用工具"
# 而是直接把数据嵌入 Prompt

prompt = f"""
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
...
"""
```

**效果**：Agent 直接看到数据，不需要调用工具。

### 3. 输出格式统一

```python
argument = f"Bear Analyst: {response.content}"
```

统一格式让后续 Agent（包括裁判）容易解析。

---

## 总结

| 方面 | Bear Researcher |
|------|----------------|
| **本质** | 看跌分析师 + 辩论参与者 |
| **核心能力** | 基于报告生成看跌论点 + 反驳看涨观点 |
| **数据来源** | state 中的报告（不调用工具） |
| **输出** | 看跌论点（格式：Bear Analyst: ...） |
| **状态更新** | 累积辩论历史 + 记录发言 |
| **与 Bull 配合** | current_response 传递反驳对象 |

### 无工具协同的核心思想

```
1. 分析团队调用工具，获取数据，生成报告
2. 报告存入 state 专用字段
3. 研究团队从 state 读报告，不调用工具
4. 研究团队专注辩论，基于已有结论
5. 裁判读所有辩论，做最终决策
```

**设计原则**：
- **分工**：谁负责获取数据，谁负责解读数据
- **压缩**：传递结论，不传递原始数据
- **专用字段**：重要产出存 state，不存 messages
- **效率**：减少重复工具调用，节省 token