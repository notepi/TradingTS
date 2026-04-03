# TradingAgents 使用说明

> 多代理 LLM 金融交易框架 - 让 AI 代理团队帮你分析股票

## 目录

- [项目简介](#项目简介)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [使用方式](#使用方式)
- [工作流程](#工作流程)
- [输出解读](#输出解读)
- [成本优化](#成本优化)
- [常见问题](#常见问题)

---

## 项目简介

TradingAgents 是一个多代理交易框架，模拟真实交易公司的运作方式：

```
分析师团队 → 研究员辩论 → 交易员决策 → 风险管理 → 最终决策
```

**核心特点：**
- 支持 OpenAI、Anthropic、Google、xAI、DashScope 等多家 LLM 提供商
- 默认使用 Tushare citydata 代理获取 A 股股票数据
- 多代理协作决策，降低单一模型偏差
- 可配置的辩论和风险评估流程

---

## 快速开始

### 环境要求

- Python 3.10+
- uv 或 pip

### 安装步骤

```bash
# 克隆项目
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install .
```

### 配置 API Key

复制配置模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key：

```bash
# 至少配置一个 LLM 提供商 + Tushare citydata 令牌
OPENAI_API_KEY=sk-...           # OpenAI (GPT 系列)
ANTHROPIC_API_KEY=sk-ant-...    # Anthropic (Claude 系列)
GOOGLE_API_KEY=...              # Google (Gemini 系列)
XAI_API_KEY=...                 # xAI (Grok 系列)
OPENROUTER_API_KEY=sk-or-...    # OpenRouter (多模型)
DASHSCOPE_API_KEY=sk-sp-...     # DashScope (通义千问/GLM)
CITYDATA_TOKEN=...              # Tushare citydata 代理
# 或 TUSHARE_TOKEN=...
```

**推荐：** 国内用户可使用 DashScope（阿里云通义千问），无需翻墙。

### 运行第一个分析

```bash
# 方式一：CLI 交互模式
tradingagents

# 方式二：直接运行
python main.py
```

CLI 模式会让你选择：
- A 股股票代码（如 600519.SH、000001.SZ、688333.SH、688333.SS 或 600519）
- 分析日期
- LLM 提供商
- 研究深度

---

## 配置说明

### LLM 提供商

| 提供商 | 环境变量 | 推荐模型 | 特点 |
|--------|----------|----------|------|
| **DashScope** | DASHSCOPE_API_KEY | glm-5 | 国内可用，无需翻墙 |
| OpenAI | OPENAI_API_KEY | gpt-5.4-mini | 综合能力强 |
| Anthropic | ANTHROPIC_API_KEY | claude-sonnet-4-6 | 推理出色 |
| Google | GOOGLE_API_KEY | gemini-3-flash | 速度快，便宜 |
| xAI | XAI_API_KEY | grok-4-fast | 实时信息 |
| OpenRouter | OPENROUTER_API_KEY | 多种模型 | 统一接口 |

### Python 配置

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()

# LLM 配置
config["llm_provider"] = "dashscope"        # 选择提供商
config["deep_think_llm"] = "glm-5"          # 复杂推理模型
config["quick_think_llm"] = "glm-5"         # 快速任务模型

# 流程控制
config["max_debate_rounds"] = 1             # 辩论轮数（0 跳过辩论）
config["max_risk_discuss_rounds"] = 1       # 风险讨论轮数（0 跳过）

# 输出语言
config["output_language"] = "Chinese"       # 中文输出

ta = TradingAgentsGraph(debug=True, config=config)
```

默认情况下，`DEFAULT_CONFIG` 已经将 `data_vendors` 四个类别都切到 `tushare`。当前项目按 A 股模式运行，新闻、全球新闻和 insider 在 Tushare 模式下会返回稳定的占位提示文本，不会中断工作流。

### 高级配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `max_debate_rounds` | 1 | 多空辩论轮数，0 表示跳过辩论环节 |
| `max_risk_discuss_rounds` | 1 | 风险讨论轮数，0 表示跳过风险评估 |
| `output_language` | English | 报告输出语言 |
| `data_vendors` | tushare | 默认 A 股数据源，走 citydata 代理 |

---

## 使用方式

### CLI 交互模式

```bash
tradingagents
```

按提示选择：
1. **股票代码** - 输入如 600519.SH、000001.SZ、688333.SH、688333.SS 或 600519
2. **分析日期** - 选择历史日期进行回测
3. **LLM 提供商** - 选择已配置 API Key 的提供商
4. **研究深度** - Quick（快）或 Deep（深度）

### Python API 模式

**基础用法：**

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 中的 API Key

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())
_, decision = ta.propagate("600519.SH", "2024-05-10")
print(decision)  # 输出: BUY / HOLD / SELL
```

**精简模式（跳过辩论和风险评估）：**

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"
config["max_debate_rounds"] = 0           # 跳过辩论
config["max_risk_discuss_rounds"] = 0     # 跳过风险评估

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("688333.SH", "2024-05-10")
```

**完整配置示例：**

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from dotenv import load_dotenv

load_dotenv()

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"
config["deep_think_llm"] = "glm-5"
config["quick_think_llm"] = "glm-5"
config["max_debate_rounds"] = 2
config["max_risk_discuss_rounds"] = 1
config["output_language"] = "Chinese"

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("000001.SZ", "2024-06-01")
print(decision)
```

---

## 工作流程

TradingAgents 模拟真实交易公司的决策流程：

```
┌─────────────────────────────────────────────────────────────┐
│                     分析师团队 (Analysts)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 技术分析 │ │ 基本面   │ │ 新闻分析 │ │ 情绪分析 │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       └────────────┴────────────┴────────────┘              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   研究员辩论 (Researchers)                   │
│         多头研究员 ←→ 空头研究员 → 研究经理决策              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     交易员 (Trader)                          │
│              综合报告，制定交易计划                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   风险管理 (Risk Management)                 │
│      激进辩论者 ←→ 保守辩论者 ←→ 中立辩论者                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  投资组合经理 (Portfolio Manager)            │
│                   最终决策: BUY / HOLD / SELL                │
└─────────────────────────────────────────────────────────────┘
```

### 各阶段说明

| 阶段 | 角色 | 任务 |
|------|------|------|
| 分析师 | 技术分析师、基本面分析师、新闻分析师、情绪分析师 | 收集市场数据，生成分析报告 |
| 研究员 | 多头研究员、空头研究员、研究经理 | 多空辩论，形成投资计划 |
| 交易员 | 交易员 | 制定具体交易方案 |
| 风险管理 | 激进/保守/中立辩论者 | 评估风险，调整建议 |
| 决策 | 投资组合经理 | 最终决策 |

---

## 输出解读

### 评级含义

| 评级 | 含义 | 建议操作 |
|------|------|----------|
| **Buy** | 强烈看好 | 建仓或加仓 |
| **Overweight** | 看好 | 逐步增仓 |
| **Hold** | 中性 | 维持现有仓位 |
| **Underweight** | 看淡 | 减仓 |
| **Sell** | 强烈看淡 | 清仓 |

### 报告结构

每份分析报告包含：

1. **技术分析** - 价格趋势、支撑阻力、技术指标信号
2. **基本面分析** - 财务指标、估值水平
3. **新闻分析** - 市场动态、行业趋势
4. **辩论摘要** - 多空双方核心论点
5. **交易建议** - 入场位、止损位、目标位

---

## 成本优化

### 模型选择建议

| 场景 | 推荐配置 | 预估成本/次 |
|------|----------|-------------|
| 测试体验 | DashScope + max_debate_rounds=0 | ¥0.1-0.5 |
| 日常分析 | DashScope + max_debate_rounds=1 | ¥0.5-1 |
| 深度研究 | OpenAI GPT-5.4 + max_debate_rounds=2 | ¥2-5 |

### 跳过辩论节省成本

```python
# 精简模式：仅分析师 + 交易员 + 最终决策
config["max_debate_rounds"] = 0
config["max_risk_discuss_rounds"] = 0
```

可节省约 50-70% 的 API 调用成本。

### 使用 DashScope

国内用户推荐使用 DashScope：
- 无需翻墙，访问稳定
- 价格相对低廉
- 支持中文输出

---

## 常见问题

### Q: 提示 "No API key found"？

确保 `.env` 文件存在且配置了正确的 API Key：

```bash
# 检查 .env 文件
cat .env

# 确保加载了环境变量
from dotenv import load_dotenv
load_dotenv()
```

### Q: 数据获取失败？

默认使用 Tushare citydata 代理获取 A 股数据：
- 需要 `CITYDATA_TOKEN` 或 `TUSHARE_TOKEN`
- 当前项目默认只支持上交所/深交所 A 股代码
- 新闻、全球新闻、内部交易在 Tushare 模式下为占位提示，不是实时新闻源

### Q: 分析时间太长？

优化建议：
1. 减少辩论轮数：`max_debate_rounds = 0`
2. 跳过风险评估：`max_risk_discuss_rounds = 0`
3. 使用更快的模型：如 gpt-5.4-mini、gemini-3-flash

### Q: 如何使用本地模型？

配置 Ollama：

```python
config["llm_provider"] = "ollama"
config["deep_think_llm"] = "qwen3:latest"
config["quick_think_llm"] = "qwen3:latest"
```

确保 Ollama 已安装并运行相应模型。

### Q: 输出是英文？

设置输出语言：

```python
config["output_language"] = "Chinese"
```

---

## 免责声明

本框架仅供研究和教育目的，不构成任何投资建议。交易决策需自行判断，作者不承担任何投资损失责任。

---

**相关链接：**
- [GitHub 仓库](https://github.com/TauricResearch/TradingAgents)
- [论文](https://arxiv.org/abs/2412.20138)
- [Discord 社区](https://discord.com/invite/hk9PGKShPK)
