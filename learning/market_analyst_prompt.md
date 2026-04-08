# Market Analyst 完整 Prompt 解读

## ⚠️ 重要：Agent 是循环执行的，不是"一次完成"

```
┌─────────────────────────────────────────────────────────────┐
│                     LangChain Agent 循环                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Agent 看到 Prompt + 历史消息                            │
│         ↓                                                   │
│  2. Agent 决定：调用工具 or 写回复                          │
│         ↓                                                   │
│  3. [如果调用工具]                                          │
│     → 工具执行（抓取数据）                                   │
│     → 返回结果给 Agent                                       │
│         ↓                                                   │
│  4. Agent 看到工具返回结果                                   │
│         ↓                                                   │
│  5. Agent 决定：继续调用工具 or 写回复                       │
│         ↓                                                   │
│  6. [如果继续] → 返回步骤2，继续循环                        │
│         ↓                                                   │
│  7. [如果写回复] → 结束                                     │
│                                                             │
│  循环直到 Agent 认为任务完成                                 │
└─────────────────────────────────────────────────────────────┘
```

### Market Analyst 的实际执行流程

```
Agent 收到 Prompt（内有任务：分析股票）
        ↓
[循环1] 调用 get_stock_data("600519.SH", ...)
        ↓ 收到K线数据
[循环2] 调用 get_indicators("600519.SH", "macd,rsi,boll", ...)
        ↓ 收到技术指标
[循环3] 调用 get_indicators("600519.SH", "atr,vwma", ...)  ← 继续要更多指标
        ↓ 收到更多指标
[循环4] Agent 认为数据够了
        ↓
Agent 写出完整报告
        ↓
结束
```

### 关键点

| 观点 | 说明 |
|------|------|
| **Agent 可以多次调用工具** | 不是"Prompt → 一次工具 → 完成"，而是循环调用 |
| **Agent 自己决定调用次数** | 看 Prompt 后，Agent 决定要哪些工具、调用几次 |
| **工具结果会返回给 Agent** | Agent 看到数据后决定下一步 |
| **循环直到 Agent 认为完成** | Agent 自己判断"我已经有足够信息写报告了" |

---

## 原始 Prompt

```
System: You are a helpful AI assistant, collaborating with other assistants.
Use the provided tools to progress towards answering the question.
If you are unable to fully answer, that is OK; another assistant with different tools
will help where you left off. Execute what you can to make progress.
If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,
prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop.
You have access to the following tools: get_stock_data, get_indicators.

You are a trading assistant tasked with analyzing financial markets. Your role is to select the most relevant indicators for a given market condition or trading strategy from the following list. The goal is to choose up to 8 indicators that provide complementary insights without redundancy. Categories and each category indicators are:

Moving Averages:
- close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.
- close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.
- close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.

MACD Related:
- macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.
- macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.
- macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.

Momentum Indicators:
- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.

Volatility Indicators:
- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.
- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.
- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.
- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It is a reactive measure, so use it as part of a broader risk management strategy.

Volume-Based Indicators:
- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.

Select indicators that provide diverse and complementary information. Avoid redundancy. When you tool call, please use the exact name of the indicators provided above as they are defined parameters. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. Then use get_indicators with the specific indicator names. Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions.
Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read.

For your reference, the current date is 2024-01-15. The instrument to analyze is `600519.SH`. Use this exact ticker in every tool call, report, and recommendation, preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`).
```

---

## 分层解读

### 第一层：协作框架（最外层）

```
You are a helpful AI assistant, collaborating with other assistants.
Use the provided tools to progress towards answering the question.
If you are unable to fully answer, that is OK; another assistant with different tools
will help where you left off. Execute what you can to make progress.
```

| 关键点 | 含义 |
|--------|------|
| **collaborating with other assistants** | Agent 不是孤立的，是团队协作 |
| **another assistant with different tools will help** | 如果我工具不够，别人会补上 |
| **Execute what you can to make progress** | 不需要等，先做能做的 |

**设计意图**：解耦 Agent，让他专注于自己的任务，不需要操心其他人的工作。

---

### 第二层：终止条件

```
If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,
prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop.
```

| 关键点 | 含义 |
|--------|------|
| **FINAL TRANSACTION PROPOSAL** | 如果有最终交易建议 |
| **prefix your response** | 在回复开头标注 |
| **so the team knows to stop** | 让整个团队知道可以停止 |

**设计意图**：统一团队的通信协议，任何 Agent 都可以触发终止。

---

### 第三层：工具定义

```
You have access to the following tools: get_stock_data, get_indicators.
```

告诉 Agent 有哪些工具可用。工具的详细说明由 LangChain 的 `@tool` 装饰器提供。

---

### 第四层：核心任务（最重要）

#### 4.1 角色定位

```
You are a trading assistant tasked with analyzing financial markets.
```

简单的角色定义。

#### 4.2 任务描述

```
Your role is to select the most relevant indicators for a given market condition
or trading strategy from the following list.
The goal is to choose up to 8 indicators that provide complementary insights without redundancy.
```

| 关键点 | 含义 |
|--------|------|
| **select the most relevant indicators** | 不是全选，是挑最相关的 |
| **up to 8 indicators** | 最多8个，不要贪多 |
| **complementary insights without redundancy** | 互补不冗余 |

**设计意图**：让 Agent 学会根据情况选择指标，而不是机械地全部调用。

#### 4.3 指标分类（专业知识注入）

```
Moving Averages: (均线类 - 3个)
  - close_50_sma: 50日简单均线
  - close_200_sma: 200日简单均线
  - close_10_ema: 10日指数均线

MACD Related: (MACD类 - 3个)
  - macd: MACD主线
  - macds: MACD信号线
  - macdh: MACD柱状图

Momentum Indicators: (动量类 - 1个)
  - rsi: 相对强弱指数

Volatility Indicators: (波动类 - 4个)
  - boll: 布林带中轨
  - boll_ub: 布林带上轨
  - boll_lb: 布林带下轨
  - atr: 平均真实波幅

Volume-Based Indicators: (成交量类 - 1个)
  - vwma: 成交量加权均线
```

每个指标都包含：
- **名称**：精确的参数名
- **用途**：这个指标干什么
- **使用方法**：怎么用
- **Tips**：注意事项

---

### 第五层：操作指令（强制顺序）

```
Select indicators that provide diverse and complementary information. Avoid redundancy.
When you tool call, please use the exact name of the indicators provided above
as they are defined parameters, otherwise your call will fail.

Please make sure to call get_stock_data first to retrieve the CSV that is needed
to generate indicators.
Then use get_indicators with the specific indicator names.
```

| 关键点 | 含义 |
|--------|------|
| **use the exact name** | 必须用精确的参数名 |
| **call get_stock_data first** | **必须先调用这个** |
| **Then use get_indicators** | 然后才能调用这个 |

**设计意图**：**强制工具调用顺序**，防止 Agent 跳过数据获取直接分析。

---

### 第六层：输出要求

```
Write a very detailed and nuanced report of the trends you observe.
Provide specific, actionable insights with supporting evidence
to help traders make informed decisions.

Make sure to append a Markdown table at the end of the report
to organize key points in the report, organized and easy to read.
```

| 要求 | 含义 |
|------|------|
| **detailed and nuanced report** | 详细、有深度的报告 |
| **actionable insights** | 可操作的见解 |
| **supporting evidence** | 有证据支撑 |
| **Markdown table** | 最后要加表格 |

---

### 第七层：上下文信息

```
For your reference, the current date is 2024-01-15.
The instrument to analyze is `600519.SH`.
Use this exact ticker in every tool call, report, and recommendation,
preserving any exchange suffix (e.g. `.TO`, `.L`, `.HK`, `.T`).
```

| 信息 | 值 |
|------|-----|
| 当前日期 | 2024-01-15 |
| 分析标的 | 600519.SH（贵州茅台） |
| 注意事项 | 保留交易所后缀 |

---

## Prompt 设计模式总结

### 1. 协作模式
```
你 → Agent A → Agent B → Agent C → 结果
```
每个 Agent 做自己的部分，不需要知道其他 Agent 在干嘛。

### 2. 工具驱动
```
Prompt 说明任务 → Agent 选择工具 → 获取数据 → 处理 → 输出
```

### 3. 强制顺序
```
必须先 A，再 B，最后 C
```
防止 Agent 跳过关键步骤。

### 4. 知识注入
```
Prompt 里直接写：指标名称、用途、使用方法、注意事项
```
不需要 Agent 自己想，告诉他怎么做。

### 5. 输出格式约束
```
详细报告 + Markdown表格
```
统一输出格式，方便后续处理。

---

## 代码对应

```python
# 1. 定义工具
@tool
def get_stock_data(symbol, start_date, end_date) -> str:
    ...

@tool
def get_indicators(symbol, indicator, curr_date) -> str:
    ...

# 2. 构建 Prompt（把上面的内容组装起来）
prompt = ChatPromptTemplate.from_messages([
    ("system", 完整的 prompt 模板),
    MessagesPlaceholder(variable_name="messages"),
])

# 3. 绑定工具
chain = prompt | llm.bind_tools([get_stock_data, get_indicators])

# 4. 执行
result = chain.invoke({"messages": []})
# Agent 会自动调用 get_stock_data → get_indicators → 写报告
```

---

## 关键教训

1. **Prompt 不是越多越好**：这个 prompt 约 1500 字，包含了所有必要信息
2. **顺序很重要**：强制告诉 Agent 先做什么、再做什么
3. **知识要注入**：不要假设 Agent 知道，给出完整的知识库
4. **协作要解耦**：告诉 Agent "别人会帮你"，让它专注自己的任务
5. **终止要统一**：用统一的格式让任何 Agent 都能触发终止

---

## LangChain Agent 机制补充说明

### ReAct 模式（Reasoning + Acting）

LangChain 的 Agent 通常使用 ReAct 模式：

```
Thought: 我需要先获取K线数据
Action: get_stock_data
Action Input: {"symbol": "600519.SH", "start_date": "2024-01-01", ...}
Observation: [K线数据返回]

Thought: 数据拿到了，现在需要技术指标
Action: get_indicators
Action Input: {"symbol": "600519.SH", "indicator": "macd,rsi", ...}
Observation: [指标数据返回]

Thought: 数据足够，可以写报告了
Final Answer: [完整分析报告]
```

每次循环：
- **Thought**: Agent 思考"我要做什么"
- **Action**: 选择并调用工具
- **Observation**: 获取工具返回的结果
- 循环直到 **Final Answer**

### 消息历史的作用

```python
# Agent 节点返回后，结果会加到 messages 里
return {
    "messages": [result],  # 工具调用结果加入消息历史
    "market_report": report,
}

# 下一次循环，Agent 会看到：
# - 原始 Prompt
# - 历史消息（含之前的工具调用和结果）
# - 决定下一步
```

### 工具调用 vs 消息

| 类型 | 说明 |
|------|------|
| **ToolMessage** | 工具返回的结果，会加入 messages |
| **AIMessage** | Agent 的回复（可能是下一个 Action 或最终答案） |

Agent 看到 messages 后，决定：
- 调用更多工具（返回 ToolMessage）
- 或者输出最终答案（结束）

---

## 防止无限循环：recursion_limit

LangGraph 有 `recursion_limit` 配置，限制最大工具调用次数：

```python
# default_config.py
"max_recur_limit": 100  # 默认100次

# propagation.py
config = {"recursion_limit": self.max_recur_limit}

# LangGraph 执行
graph.invoke(initial_state, config={"recursion_limit": 100})
```

### 循环计数

```
循环1:  Agent → get_stock_data        (计数=1)
循环2:  Agent → get_indicators       (计数=2)
循环3:  Agent → get_indicators       (计数=3)
...
循环100: Agent → get_indicators       (计数=100)
循环101: ❌ 超过限制，报错停止
```

### 防止无限循环的机制

| 机制 | 说明 |
|------|------|
| **recursion_limit=100** | 硬限制，最多100次工具调用 |
| **辩论条件判断** | `should_continue_debate()` 控制辩论轮数 |
| **终止关键词** | `FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**` 触发结束 |
| **报告输出** | Agent 输出报告后不再调用工具 |

**实际影响**：如果 Agent 一直觉得"数据不够"，调用超过100次后会被强制停止。

---

## 工具的数据传递机制

### 1. 工具怎么返回数据给 Agent

```
Agent 调用工具 → 工具返回字符串 → LangChain 包装成 ToolMessage → 加入 messages → Agent 下一轮看到
```

```python
# 工具定义 (@tool 装饰器)
@tool
def get_stock_data(symbol, start_date, end_date) -> str:
    """返回格式化后的数据字符串"""
    data = route_to_vendor("get_stock_data", symbol, ...)
    return data  # 返回字符串

# LangChain 自动完成：
# 1. Agent 决定调用 get_stock_data
# 2. 工具执行，返回 "Date,Open,High,Low,Close..."
# 3. LangChain 包装成 ToolMessage
# 4. 加入 state["messages"]
# 5. Agent 下一轮循环看到这条消息，继续工作
```

### 2. Agent 看到的消息历史

```
[循环1] 人类: 分析 600519.SH
        Agent: 我需要获取K线数据
        工具:  Date,Open,High,Low,Close...
             2024-01-02,1850,1880,1845,1875...

[循环2] Agent: 数据拿到了，现在分析MACD和RSI
        工具:  Date,macd,signal,histogram...
             2024-01-02,12.5,10.2,2.3...

[循环3] Agent: 数据足够，写报告...
```

### 3. 超时限制

| 层级 | 限制 | 说明 |
|------|------|------|
| 工具执行 | **无显式超时** | 工具会等 API 返回 |
| LLM 调用 | `timeout` | 超过时间报错/重试 |
| 循环次数 | `recursion_limit=100` | 最多100次工具调用 |

### 4. 内容长度限制

| 限制类型 | 说明 | 示例 |
|---------|------|------|
| **Context Window** | 模型能处理的输入+输出总量 | GPT-4o: 128K tokens |
| **max_tokens** | 单次输出的最大 tokens | 可配置 |
| **工具截断** | 工具自己限制返回大小 | 新闻每条限制500字符 |

```python
# 工具层面的截断示例
# tavily_news.py
content = article.get("content", "")[:500]  # 每条新闻只取前500字符

# 工具层面的截断示例
# tushare_data.py
df = pro.daily(..., limit=100)  # 限制条数
```

### 5. 数据量估算

| 数据类型 | 大概大小 | 说明 |
|---------|---------|------|
| K线数据（1年） | ~10KB | 244天 × 5列 |
| 技术指标（30天） | ~5KB | 几个指标的值 |
| 新闻数据 | ~20KB | 10-15条新闻 |
| 财务报表 | ~30KB | 季度数据CSV |

**注意**：如果 messages 越来越长，Agent 可能会"忘记"早期内容。LangGraph 可以配置自动摘要。

---

## 消息状态管理

### 消息是怎么累积的

```
初始状态: messages = [HumanMessage("分析 600519.SH")]

循环1:  Agent → get_stock_data
        ↓
        messages = [
            HumanMessage("分析 600519.SH"),  ← 初始
            AIMessage("我需要获取K线数据"),   ← Agent 决策
            ToolMessage("Date,Open,High...") ← 工具返回
        ]

循环2:  Agent → get_indicators
        ↓
        messages = [
            HumanMessage("分析 600519.SH"),
            AIMessage("我需要获取K线数据"),
            ToolMessage("Date,Open,High..."),
            AIMessage("数据拿到了，现在分析MACD"),  ← 新增
            ToolMessage("Date,macd,RSI..."),     ← 新增
        ]

... 继续循环，消息越来越多
```

### 问题：下一个 Agent 要读什么？

**错误的理解**：下一个 Agent 要读原始数据（K线、新闻原文）

**正确的理解**：下一个 Agent 只读上一个 Agent 的**分析报告**

---

### 关键区别：留下什么

| 留下的是 | 大小 | 传给下一个 |
|---------|------|-----------|
| **原始数据**（K线、新闻原文、财务报表） | 很大（几十KB） | ❌ 不传 |
| **分析报告**（总结性文字） | 很小（几百字） | ✅ 传给下一个 |

---

### 具体例子

**Market Analyst 的执行**：
```
1. 调用 get_stock_data → 拿到 244天K线原始数据（10KB）
2. 调用 get_indicators → 拿到 MACD、RSI 数据（5KB）
3. 分析数据，写报告："MACD金叉，RSI 65处于超买区间..."
```

**Market Analyst 的返回**：
```python
return {
    "messages": [result.tool_calls],      # 工具调用记录 → ❌ 丢弃
    "market_report": "MACD金叉，RSI 65...", # 分析报告 → ✅ 留下
}
```

**News Analyst 能读到的**：
```python
state = {
    "market_report": "MACD金叉，RSI 65...",  # ✅ 能读到
    "news_report": "",                           # 还没生成
}
```

---

### 流程图

```
Market Analyst
    ├── 调用工具 → 拿原始数据
    ├── 分析数据
    └── 写报告 → 只留 market_report
    
News Analyst
    ├── 读 market_report（上一个的报告，不是原始数据）
    ├── 调用工具 → 拿原始数据
    ├── 分析数据
    └── 写报告 → 只留 news_report

Bull Researcher
    ├── 读 market_report（贵州茅台：MACD金叉...）
    ├── 读 news_report（近期有利好消息...）
    ├── 读 fundamentals_report（净利润增长10%...）
    └── 写报告
```

---

### 传给下一个 Agent 的是什么？

| 字段 | 内容 | 传给下一个 |
|------|------|-----------|
| `market_report` | Market Analyst 的分析报告 | ✅ |
| `news_report` | News Analyst 的分析报告 | ✅ |
| `fundamentals_report` | Fundamentals Analyst 的分析报告 | ✅ |
| 原始K线数据 | get_stock_data 返回的 CSV | ❌ |
| 原始新闻内容 | get_news 返回的原文 | ❌ |
| 工具调用记录 | messages 里的 ToolMessage | ❌ |

---

### 问题：消息太长怎么办

如果循环100次，每次2条消息 = 200条消息，可能塞满 Context Window。

### 解决方案：分层存储 + 消息清理

**核心设计**：

```
┌─────────────────────────────────────────────────────┐
│                    state 结构                        │
├─────────────────────────────────────────────────────┤
│  messages: [...]      ← 临时通信用，工具调用/返回    │
│  market_report: "..." ← 重要结果，存在专门字段      │
│  fundamentals_report ← 同上                         │
│  news_report: "..."   ← 同上                        │
└─────────────────────────────────────────────────────┘
```

```python
# 各分析师节点只负责返回报告
return {
    "messages": [result],      # 新消息加入
    "market_report": report,   # 报告存在单独字段！
}

# "Msg Clear" 节点负责清理 messages
def delete_messages(state):
    messages = state["messages"]

    # 删除所有旧消息
    removal_operations = [RemoveMessage(id=m.id) for m in messages]

    # 加一个占位符，让 Agent 继续
    placeholder = HumanMessage(content="Continue")

    return {"messages": removal_operations + [placeholder]}
```

### 清理后的效果

```
清理前: messages = [H, AI, TM, AI, TM, AI, TM, AI, TM, ...]  ← 100+ 条
清理后: messages = [HumanMessage("Continue")]                    ← 只有1条
```

### 为什么这样设计

| 设计 | 原因 |
|------|------|
| **messages 只做临时通信** | 工具调用和返回不需要长期保存 |
| **报告存在 state 专门字段** | 重要数据不丢失 |
| **定期清理 messages** | 保持 Context 不超限 |
| **用 state 字段传数据** | 后续节点从 state 读取，不依赖 messages |

### 消息类型

| 类型 | 作用 |
|------|------|
| HumanMessage | 用户/系统输入 |
| AIMessage | Agent 的回复（可能含工具调用） |
| ToolMessage | 工具的返回结果 |
| RemoveMessage | 删除旧消息（标记删除） |

### 好处总结

1. **防止 Context 溢出**：删除旧 messages，保持轻量
2. **重要数据不丢失**：报告/决策存在 state 专门字段
3. **后续节点能读取**：通过 state["market_report"] 获取，不需要从 messages 解析
