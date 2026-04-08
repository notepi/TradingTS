# Bull Researcher 分析

## 角色定位

```
Bull Researcher = 看涨分析师 + 辩论参与者 + 历史学习者
```

---

## 职责

1. **看涨论点生成**：基于分析报告，强调利好因素
2. **反驳 Bear 观点**：针对空头论点进行反驳
3. **历史学习**：从历史决策中学习，避免重复错误

---

## 能读取什么

| 数据源 | 内容 | 来源 |
|--------|------|------|
| market_report | 技术分析报告 | Market Analyst |
| sentiment_report | 情绪分析报告 | Social Analyst |
| news_report | 新闻分析报告 | News Analyst |
| fundamentals_report | 基本面分析报告 | Fundamentals Analyst |
| history | 辩论历史 | investment_debate_state |
| current_response | Bear 最后说的话 | investment_debate_state |
| past_memories | 历史决策记忆 | memory 系统 |

---

## 完整 Prompt

```
You are a Bull Analyst advocating for investing in the stock.
Your task is to build a strong, evidence-based case emphasizing growth potential,
competitive advantages, and positive market indicators.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points.

Resources available:
- Market research report: [market_report]
- Social media sentiment report: [sentiment_report]
- Latest world affairs news: [news_report]
- Company fundamentals report: [fundamentals_report]
- Conversation history of the debate: [history]
- Last bear argument: [current_response]
- Reflections from similar situations: [past_memory_str]
```

---

## Prompt 解读

### 1. 角色设定

```
"You are a Bull Analyst advocating for investing in the stock."
```

明确告诉 Agent：你是看涨分析师，主张买入。

### 2. 任务描述

```
"build a strong, evidence-based case emphasizing growth potential,
competitive advantages, and positive market indicators"
```

强调三点：
- 增长潜力
- 竞争优势
- 积极指标

### 3. 关键要点（重点！）

| 要点 | 说明 |
|------|------|
| **Growth Potential** | 强调市场机会、营收预测、规模化能力 |
| **Competitive Advantages** | 强调独特产品、品牌优势、市场地位 |
| **Positive Indicators** | 用财务健康、行业趋势、正面新闻作证据 |
| **Bear Counterpoints** | 针对 Bear 的论点反驳，不是无视 |
| **Engagement** | 对话式，不是列数据清单 |

### 4. 数据来源

```
分析报告（4份）
    ↓
辩论历史 + Bear 最后的话
    ↓
历史记忆
    ↓
全部给 LLM 生成看涨论点
```

---

## 代码执行流程

```python
def bull_node(state) -> dict:
    # 1. 读取数据
    market_report = state["market_report"]
    sentiment_report = state["sentiment_report"]
    news_report = state["news_report"]
    fundamentals_report = state["fundamentals_report"]
    history = state["investment_debate_state"]["history"]
    current_response = state["investment_debate_state"]["current_response"]

    # 2. 从 memory 获取历史教训
    curr_situation = f"{market_report}\n{sentiment_report}\n{news_report}\n{fundamentals_report}"
    past_memories = memory.get_memories(curr_situation, n_matches=2)

    # 3. 构建 Prompt
    prompt = f"""..."{market_report}...{history}...{current_response}...{past_memories}"""

    # 4. LLM 生成看涨论点
    response = llm.invoke(prompt)

    # 5. 包装成辩论格式
    argument = f"Bull Analyst: {response.content}"

    # 6. 更新辩论状态
    return {
        "investment_debate_state": {
            "history": history + "\n" + argument,      # 累积历史
            "bull_history": bull_history + "\n" + argument,
            "current_response": argument,              # 记录这次发言
            "count": count + 1,                       # 发言计数
        }
    }
```

---

## 输出的辩论格式

```python
argument = f"Bull Analyst: {response.content}"
```

输出格式固定为：
```
Bull Analyst: [LLM 生成的内容]
```

这样 Bear 读取时可以统一处理。

---

## 状态更新

```
更新前：
investment_debate_state = {
    "history": "...",
    "bull_history": "...",
    "current_response": "Bear Analyst: ...",  # Bear 最后说的
    "count": 3,
}

更新后：
investment_debate_state = {
    "history": "...\nBull Analyst: ...",  # 新增 Bull 的话
    "bull_history": "...\nBull Analyst: ...",
    "current_response": "Bull Analyst: ...",  # 换成 Bull 的话
    "count": 4,
}
```

---

## 辩论上下文

```
Bull 第1轮：
    - 读：market_report, sentiment_report, news_report, fundamentals_report
    - 不读：history（空的）
    - 不读：current_response（空的）
    - 输出：BULL 第一轮论点

Bull 第2轮：
    - 读：4份报告 + 第1轮辩论历史 + Bear 的反驳
    - 输出：BULL 反驳 Bear

Bull 第N轮：
    - 读：4份报告 + 历史 + Bear 的最新反驳
    - 输出：Bull 继续反驳
```

---

## 与 Bear 的配合

| 轮次 | Bull 做什么 | 依据 |
|------|-----------|------|
| 第1轮 | 写看涨论点 | 4份分析报告 |
| 第2轮 | 反驳 Bear | 4份报告 + Bear 第1轮 |
| 第3轮 | 反驳 Bear | 4份报告 + Bear 第2轮 |
| ... | 循环 | ... |

**关键**：Bull 每次都针对 `current_response`（Bear 最后说的话）进行反驳。

---

## 历史记忆机制（设计上的问题）

```python
# 获取相似历史
past_memories = memory.get_memories(curr_situation, n_matches=2)

# 传给 LLM
past_memory_str = ""
for rec in past_memories:
    past_memory_str += rec["recommendation"] + "\n\n"
```

### 记忆是怎么来的

记忆需要"交易结果"才能写入：

```
设计意图：
    分析 → 交易 → 知道结果（赚/亏）→ 写入记忆 → 下次参考

实际情况：
    你：分析 → 分析 → 分析
    结果：不知道对不对（只是分析，没有交易）
    记忆：写不进去
```

### 问题

| 设计 | 实际 |
|------|------|
| 分析 → 交易 → 有结果 → 写记忆 | 只分析，没有交易，不知道结果 |
| 记忆本有内容 | 记忆本是空的 |
| 能从历史学习 | 学不到任何东西 |

### 结论

**这个记忆系统在你当前的使用场景下用不上**，因为：

1. 你每次只是运行分析
2. 分析完就结束了，没有交易
3. 不知道分析得对不对
4. 所以无法写入记忆

如果想用记忆系统，需要：
- 回测模式（分析历史，验证结果）
- 或接入真实交易系统

**当前使用场景：记忆系统基本是摆设**。

---

## 总结

| 方面 | Bull Researcher |
|------|----------------|
| **本质** | 看涨分析师 + 辩论参与者 |
| **核心能力** | 基于报告生成论点 + 反驳空头 |
| **数据来源** | 分析报告 + 辩论历史 + 历史记忆 |
| **输出** | 看涨论点（格式：Bull Analyst: ...） |
| **状态更新** | 累积辩论历史 + 记录发言 |
| **特殊机制** | 从历史记忆学习 |
