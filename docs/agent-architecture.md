# Agent 架构与协作流程

## 概述

TradingAgents 采用多智能体协作架构，包含分析师、研究员、交易员和风险管理团队，通过结构化辩论形成最终交易决策。

## 智能体分类

| 类别 | 智能体 | 职责 |
|------|--------|------|
| **分析师** | Market Analyst | 技术分析 |
| | Social Media Analyst | 社交媒体情绪 |
| | News Analyst | 新闻事件分析 |
| | Fundamentals Analyst | 基本面分析 |
| **研究员** | Bull Researcher | 构建看涨论点 |
| | Bear Researcher | 构建看跌论点 |
| | Research Manager | 主持辩论，生成投资计划 |
| **交易员** | Trader | 基于投资计划生成交易决策 |
| **风险管理** | Aggressive Analyst | 高风险高回报观点 |
| | Conservative Analyst | 保守观点 |
| | Neutral Analyst | 平衡观点 |
| | Portfolio Manager | 综合风险评估，输出最终决策 |

## 协作流程图

```
                                    ┌──────────────────────────────┐
                                    │      Market Analyst          │
                                    │   (get_stock_data,           │
                                    │    get_indicators)           │
                                    └──────────────┬───────────────┘
                                                   ↓
                                    ┌──────────────────────────────┐
                                    │    Social Media Analyst       │
                                    │      (get_news)               │
                                    └──────────────┬───────────────┘
                                                   ↓
                                    ┌──────────────────────────────┐
                                    │       News Analyst           │
                                    │  (get_news, get_global_news) │
                                    └──────────────┬───────────────┘
                                                   ↓
                                    ┌──────────────────────────────┐
                                    │   Fundamentals Analyst       │
                                    │   (get_fundamentals,         │
                                    │    get_balance_sheet, ...)    │
                                    └──────────────┬───────────────┘
                                                   ↓
                              ┌────────────────────┴────────────────────┐
                              ↓                                          ↓
                 ┌────────────────────┐                    ┌────────────────────┐
                 │   Bull Researcher │←──── 辩论 ────→   │   Bear Researcher  │
                 │   (看涨论点)       │    max_debate_     │   (看跌论点)        │
                 │                   │    rounds          │                    │
                 └────────┬──────────┘                    └──────────┬─────────┘
                          ↓                                          ↓
                 ┌─────────────────────────────────────────────────────┐
                 │              Research Manager                         │
                 │  - 总结辩论                                            │
                 │  - 生成 investment_plan                               │
                 │  - 决策: BUY/SELL/HOLD                                │
                 └────────────────────┬────────────────────────────────┘
                                      ↓
                 ┌─────────────────────────────────────────────────────┐
                 │                    Trader                             │
                 │  - 基于 investment_plan 生成交易决策                  │
                 │  - 输出 trader_investment_plan                      │
                 │  - 决策: BUY/HOLD/SELL                              │
                 └────────────────────┬────────────────────────────────┘
                                      ↓
        ┌─────────────────────────────┼─────────────────────────────┐
        ↓                             ↓                             ↓
┌───────────────┐          ┌─────────────────┐          ┌───────────────┐
│   Aggressive  │←──辩论──→│   Conservative  │←──辩论──→│    Neutral    │
│   Analyst     │          │   Analyst       │          │   Analyst     │
│ (高风险高回报) │          │ (低风险保守)     │          │ (平衡观点)    │
└───────┬───────┘          └────────┬────────┘          └───────┬───────┘
        │                             │                             │
        └─────────────────────────────┴─────────────────────────────┘
                                      ↓
                 ┌─────────────────────────────────────────────────────┐
                 │              Portfolio Manager                        │
                 │  - 综合风险辩论                                        │
                 │  - 输出 final_trade_decision                         │
                 │  - 评级: BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL        │
                 └─────────────────────────────────────────────────────┘
```

## 分析师详情

### Market Analyst

**工具**: `get_stock_data`, `get_indicators`

**职责**:
- 获取股票 OHLCV 数据
- 计算并分析技术指标（MA, MACD, RSI, Bollinger, ATR 等）
- 生成技术分析报告

**提示词问题**: 硬编码了 12 个指标，未包含 mfi/cci/wr/kdj（见 `indicator_analysis_report.md`）

### Fundamentals Analyst

**工具**: `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement`, `get_peg_ratio`, `get_yoy_growth`

**职责**:
- 分析公司财务状况
- 计算估值指标（PE, PB, PEG）
- 评估盈利能力、偿债能力、成长性

## 研究员辩论机制

### Bull vs Bear Researcher

**流程**:
1. 双方同时看到所有分析师报告
2. 各自构建论点（Bull 看涨，Bear 看跌）
3. 进行多轮辩论（`max_debate_rounds`）
4. Research Manager 总结并生成 `investment_plan`

**状态结构** (`InvestDebateState`):
```python
{
    "bull_history": str,      # Bull 的辩论历史
    "bear_history": str,       # Bear 的辩论历史
    "history": str,            # 完整历史
    "current_response": str,   # 当前响应
    "judge_decision": str,    # Judge 的决策
    "count": int              # 辩论轮数
}
```

## 风险管理辩论

### 三方辩论机制

**Aggressive Analyst**:
- 关注高回报机会
- 挑战保守观点
- 认为风险可控

**Conservative Analyst**:
- 强调资产保护
- 批评激进决策
- 关注下行风险

**Neutral Analyst**:
- 调和两方极端观点
- 提出平衡方案
- 寻找共识

**流程**:
1. Aggressive → Conservative → Neutral → 循环
2. 最多 `max_risk_discuss_rounds` 轮
3. Portfolio Manager 综合输出最终决策

**状态结构** (`RiskDebateState`):
```python
{
    "aggressive_history": str,
    "conservative_history": str,
    "neutral_history": str,
    "history": str,
    "latest_speaker": str,
    "current_aggressive_response": str,
    "current_conservative_response": str,
    "current_neutral_response": str,
    "judge_decision": str,
    "count": int
}
```

## 记忆系统 (BM25)

### FinancialSituationMemory

使用 BM25 算法进行词汇相似度匹配，无需 API 调用。

```python
class FinancialSituationMemory:
    def add_situations(situations_and_advice):
        """添加 (情况, 建议) 对到记忆库"""

    def get_memories(current_situation, n_matches=2):
        """查找最相似的 n 条记忆"""
```

**用途**:
- 存储历史交易决策和结果
- 为新决策提供历史参考
- Trader 和 Portfolio Manager 使用

**局限性**:
- BM25 是词汇匹配，非语义匹配
- 相似市场情况可能因词汇不同而匹配失败

## 条件逻辑 (ConditionalLogic)

### should_continue_debate

```python
def should_continue_debate(state):
    # count >= 2 * max_debate_rounds → 结束
    # current_response 以 "Bull" 开头 → 切换到 Bear
    # 否则 → Bull
```

### should_continue_risk_analysis

```python
def should_continue_risk_analysis(state):
    # count >= 3 * max_risk_discuss_rounds → 结束
    # latest_speaker 是 Aggressive → 切换到 Conservative
    # latest_speaker 是 Conservative → 切换到 Neutral
    # 否则 → Aggressive
```

## 配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `max_debate_rounds` | Bull/Bear 辩论轮数 | 2 |
| `max_risk_discuss_rounds` | 风险管理辩论轮数 | 3 |
| `max_conversation_length` | 对话最大长度 | 20 |

---

*最后更新：2026-04-14*
