# TradingAgents 多智能体协同

## 整体架构：四个团队

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TradingAgents 工作流                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │                    阶段1: 分析团队                                │      │
│  │                                                                 │      │
│  │  Market Analyst ─┐                                                │      │
│  │  Social Analyst  ─┼─→ 各自写报告 → 传给下一团队                   │      │
│  │  News Analyst    ─┤                                                │      │
│  │  Fundamentals   ─┘                                                │      │
│  └─────────────────────────────┬───────────────────────────────────┘      │
│                                ↓                                            │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │                    阶段2: 研究团队                                │      │
│  │                                                                 │      │
│  │  Bull Researcher ↔ Bear Researcher  ← 互相辩论                   │      │
│  │         ↓                                                        │      │
│  │  Research Manager (裁判) → 输出投资决策                           │      │
│  └─────────────────────────────┬───────────────────────────────────┘      │
│                                ↓                                            │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │                    阶段3: 交易团队                                │      │
│  │                                                                 │      │
│  │  Trader → 根据投资决策，制定具体交易计划                          │      │
│  └─────────────────────────────┬───────────────────────────────────┘      │
│                                ↓                                            │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │                    阶段4: 风险团队                                │      │
│  │                                                                 │      │
│  │  Aggressive ↔ Conservative ↔ Neutral  ← 三角辩论                 │      │
│  │         ↓                                                        │      │
│  │  Portfolio Manager (裁判) → 最终交易信号                          │      │
│  └─────────────────────────────────────────────────────────────────┘      │
│                                ↓                                            │
│                          BUY / SELL / HOLD                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 阶段1: 分析团队

### 团队成员

| 成员 | 职责 | 使用的工具 |
|------|------|-----------|
| Market Analyst | 技术分析 | get_stock_data, get_indicators |
| Social Analyst | 社交媒体情绪分析 | get_news |
| News Analyst | 新闻分析 | get_news, get_global_news |
| Fundamentals Analyst | 基本面分析 | get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement |

### 工作流程

```
分析团队成员按顺序执行（不是并行）：

Market Analyst → Social Analyst → News Analyst → Fundamentals Analyst
      ↓              ↓              ↓              ↓
  市场报告       情绪报告       新闻报告       基本面报告
      ↓              ↓              ↓              ↓
  market_      sentiment_       news_         fundamentals_
  report       report          report        report
```

### 各成员产出

| 成员 | 产出 |
|------|------|
| Market Analyst | market_report（MACD/RSI/布林带等技术指标分析） |
| Social Analyst | sentiment_report（社交媒体情绪分析） |
| News Analyst | news_report（公司新闻 + 全球宏观新闻） |
| Fundamentals Analyst | fundamentals_report（财务数据：营收、利润、现金流等） |

### 怎么传给下一团队

每个成员完成分析后，把自己的报告写入 state：
- `market_report`
- `sentiment_report`
- `news_report`
- `fundamentals_report`

同时清理 messages（临时工具调用记录不传给下一团队）。

---

## 阶段2: 研究团队

### 团队成员

| 成员 | 职责 |
|------|------|
| Bull Researcher | 看涨分析师，强调利好因素 |
| Bear Researcher | 看跌分析师，强调风险因素 |
| Research Manager | 裁判，综合多空观点做投资决策 |

### 能读取什么

研究团队能读取分析团队的所有报告：
- market_report（技术分析）
- sentiment_report（情绪分析）
- news_report（新闻分析）
- fundamentals_report（基本面分析）

### 工作流程

```
Bull Researcher ← 读分析报告 → 写看涨论点
        ↓
Bear Researcher ← 读分析报告 + Bull论点 → 写看跌论点
        ↓
Bull Researcher ← 读 Bear论点 → 写反驳
        ↓
Bear Researcher ← 读 Bull反驳 → 写反驳
        ↓
Research Manager ← 读所有辩论 → 做投资裁决
```

### 辩论过程（max_debate_rounds = 1）

```
第1轮：
┌────────────────────────────────────────────────────────────────┐
│ Bull Researcher:                                                │
│ "基于分析报告，我建议买入，原因：                                │
│  1. MACD 金叉，技术面利好                                        │
│  2. 净利润增长 10%，基本面强劲                                   │
│  3. 行业前景广阔"                                               │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ Bear Researcher:                                                 │
│ "我不同意，应该谨慎，原因：                                       │
│  1. RSI 处于超买区间                                            │
│  2. 宏观环境不确定                                              │
│  3. 估值偏高"                                                   │
└────────────────────────────────────────────────────────────────┘
                              ↓
第2轮：
┌────────────────────────────────────────────────────────────────┐
│ Bull Researcher:                                                │
│ "针对 Bear 的观点，我反驳：                                      │
│  - 超买不代表立即下跌，可能继续上涨                               │
│  - 公司有护城河，宏观影响有限"                                   │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ Bear Researcher:                                                 │
│ "针对 Bull 的反驳，我再指出：                                    │
│  - 估值已充分反映利好                                            │
│  - 行业周期风险被低估"                                           │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ Research Manager（裁判）:                                        │
│ "综合多空辩论，我的投资决策：增持                                 │
│  理由：..."                                                     │
│  investment_plan = "建议增持，目标价 XXX"                        │
└────────────────────────────────────────────────────────────────┘
```

### 辩论几轮

- `max_debate_rounds = 1` 时：Bull + Bear 各发言 2 次 = 4 次发言
- `max_debate_rounds = 2` 时：Bull + Bear 各发言 4 次 = 8 次发言

发言次数达到上限后，Research Manager 做裁决。

### 裁判怎么裁决

Research Manager 阅读：
- 分析团队的所有报告
- Bull Researcher 的所有论点
- Bear Researcher 的所有论点

输出 `investment_plan`（投资计划），包含：
- 投资建议（增持/减持）
- 理由
- 风险提示

---

## 阶段3: 交易团队

### 团队成员

| 成员 | 职责 |
|------|------|
| Trader | 交易员，根据投资决策制定具体交易计划 |

### 能读取什么

Trader 能读取：
- 分析团队的所有报告
- Research Manager 的 investment_plan

### 工作流程

```
Trader:
"根据 Research Manager 的投资决策（增持），
  我来制定具体交易计划：
  - 买入时机
  - 买入数量
  - 目标价位
  - 止损价位
  - 预期收益"
```

### 输出

`trader_investment_plan`（交易计划），包含：
- 买入/卖出建议
- 仓位建议
- 入场价格
- 止损价格
- 止盈价格

---

## 阶段4: 风险团队

### 团队成员

| 成员 | 职责 |
|------|------|
| Aggressive Analyst | 激进分析师，主张高回报高风险策略 |
| Conservative Analyst | 保守分析师，主张低风险稳健策略 |
| Neutral Analyst | 中立分析师，平衡多空观点 |
| Portfolio Manager | 裁判，综合风险评估做最终决策 |

### 能读取什么

风险团队能读取：
- 分析团队的所有报告
- Research Manager 的 investment_plan
- Trader 的 trader_investment_plan

### 工作流程

三角辩论，轮流发言：

```
Aggressive Analyst ← 读交易计划 → 激进风险评估
        ↓
Conservative Analyst ← 读激进观点 → 保守风险评估
        ↓
Neutral Analyst ← 读保守观点 → 中立风险评估
        ↓
Aggressive Analyst ← 读中立观点 → 激进反驳
        ↓
Conservative Analyst ← 读激进反驳 → 保守反驳
        ↓
Neutral Analyst ← 读保守反驳 → 中立综合
        ↓
Portfolio Manager ← 读所有辩论 → 最终决策
```

### 辩论过程（max_risk_discuss_rounds = 1）

```
第1轮：
┌────────────────────────────────────────────────────────────────┐
│ Aggressive Analyst:                                              │
│ "我支持这个交易计划，风险可控，理由：                             │
│  - 回报潜力大                                                   │
│  - 技术面支撑强"                                               │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ Conservative Analyst:                                            │
│ "我认为风险过高，原因：                                           │
│  - 波动性太大                                                   │
│  - 可能损失超过承受范围"                                         │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│ Neutral Analyst:                                                 │
│ "综合双方观点，我认为：                                          │
│  - 可以做，但需要控制仓位"                                      │
└────────────────────────────────────────────────────────────────┘
                              ↓
第2轮：
Aggressive ← 保守观点 → 激进反驳
        ↓
Conservative ← 激进反驳 → 保守反驳
        ↓
Neutral ← 保守反驳 → 中立综合
                              ↓
第3轮：
Aggressive ← 中立综合 → 激进最终观点
        ↓
Portfolio Manager ← 读所有辩论 → 最终决策
```

### 辩论几轮

- `max_risk_discuss_rounds = 1` 时：Aggressive + Conservative + Neutral 各发言 3 次 = 9 次发言
- `max_risk_discuss_rounds = 2` 时：各发言 6 次

发言次数达到上限后，Portfolio Manager 做最终裁决。

### 裁判怎么裁决

Portfolio Manager 阅读：
- 分析团队的所有报告
- investment_plan
- trader_investment_plan
- Aggressive/Conservative/Neutral 的所有论点

输出 `final_trade_decision`（最终交易决策）：
- BUY（买入）
- HOLD（持有）
- SELL（卖出）
- OVERWEIGHT（增持）
- UNDERWEIGHT（减持）

---

## 数据流向总览

```
分析团队 ─────────────────────────────────────────────────────────
│ market_report
│ sentiment_report
│ news_report
│ fundamentals_report
└────────────────────────────────────────────────────────────────
                          ↓
研究团队 ─────────────────────────────────────────────────────────
│ [读分析报告]
│ Bull Researcher ──→ bull_history
│ Bear Researcher ──→ bear_history
│ Research Manager ──→ investment_plan
└────────────────────────────────────────────────────────────────
                          ↓
交易团队 ─────────────────────────────────────────────────────────
│ [读分析报告 + investment_plan]
│ Trader ──→ trader_investment_plan
└────────────────────────────────────────────────────────────────
                          ↓
风险团队 ─────────────────────────────────────────────────────────
│ [读所有报告 + 交易计划]
│ Aggressive ──→ aggressive_history
│ Conservative ──→ conservative_history
│ Neutral ──→ neutral_history
│ Portfolio Manager ──→ final_trade_decision
└────────────────────────────────────────────────────────────────
                          ↓
                        结束
                      BUY/SELL/HOLD
```

---

## 信息共享方式

### 不是直接"对话"，而是通过 state 共享

```
每个团队成员都知道：
- 自己要做什么
- 能从 state 读什么
- 要把什么写入 state

不需要主动"告诉"别人，让别人从 state 自己读。
```

### 裁判的优势

- 可以读到所有辩论内容
- 立场中立
- 做最终决策

---

## 总结

| 阶段 | 团队 | 协同方式 |
|------|------|---------|
| 1 | 分析团队 | 顺序执行，各自写报告 |
| 2 | 研究团队 | Bull ↔ Bear 辩论，Research Manager 裁判 |
| 3 | 交易团队 | Trader 制定交易计划 |
| 4 | 风险团队 | Aggressive ↔ Conservative ↔ Neutral 三角辩论，Portfolio Manager 裁判 |

**核心思想**：每个团队专注自己的任务，通过 state 共享信息，最后由裁判做决策。
