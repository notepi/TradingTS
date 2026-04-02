# TradingAgents Project

> Multi-Agents LLM Financial Trading Framework - 多代理 LLM 金融交易框架

**文档：** [使用说明](docs/USER_GUIDE.md) | [README](README.md)

## Project Overview

TradingAgents 是一个多代理交易框架，模拟真实交易公司的运作方式。通过部署专门的 LLM 代理团队：基本面分析师、情绪分析师、技术分析师、交易员、风险管理团队，协同评估市场状况并做出交易决策。

**技术栈**: Python 3.10+, LangGraph, LangChain, yfinance

**入口点**:
- CLI: `tradingagents` 命令或 `python -m cli.main`
- Python API: `TradingAgentsGraph` 类

## Directory Structure

```
TradingAgents/
├── cli/                    # CLI 交互界面
│   ├── main.py             # CLI 入口 (typer app)
│   ├── config.py           # CLI 配置
│   └── utils.py            # CLI 工具函数
├── tradingagents/          # 核心框架
│   ├── agents/             # 代理实现
│   │   ├── analysts/       # 分析师团队 (基本面、新闻、情绪、技术)
│   │   ├── researchers/    # 研究员团队 (多头、空头)
│   │   ├── trader/         # 交易员
│   │   ├── risk_mgmt/      # 风险管理 (激进、保守、中立辩论者)
│   │   ├── managers/       # 管理层 (投资组合经理、研究经理)
│   │   └── utils/          # 代理工具函数
│   ├── dataflows/          # 数据流处理
│   │   ├── y_finance.py    # Yahoo Finance 数据接口
│   │   └── alpha_vantage_*.py  # Alpha Vantage API
│   ├── graph/              # LangGraph 工作流
│   │   ├── trading_graph.py    # 主图入口
│   │   ├── setup.py        # 图初始化
│   │   └── propagation.py  # 前向传播
│   ├── llm_clients/        # LLM 客户端
│   │   ├── factory.py      # 客户端工厂
│   │   ├── model_catalog.py    # 模型选项
│   │   └── *_client.py     # 各提供商客户端
│   └── default_config.py   # 默认配置
├── tests/                  # 测试文件
├── main.py                 # 快速运行示例
└── results/                # 运行结果输出
```

## Key Files

| File | Purpose |
|------|---------|
| [main.py](main.py) | 快速运行示例，单股票分析 |
| [tradingagents/default_config.py](tradingagents/default_config.py) | 默认配置：LLM、数据源、辩论轮数 |
| [tradingagents/graph/trading_graph.py](tradingagents/graph/trading_graph.py) | 核心图类 `TradingAgentsGraph` |
| [tradingagents/llm_clients/model_catalog.py](tradingagents/llm_clients/model_catalog.py) | 支持的模型列表 |
| [cli/main.py](cli/main.py) | CLI 入口 |

## Running the Project

### 1. Environment Setup

```bash
# 已有 .env 文件，确保 API Key 已配置
# 支持的提供商：openai, google, anthropic, xai, openrouter, dashscope, ollama

# 激活虚拟环境
source .venv/bin/activate  # 或 conda activate tradingagents
```

### 2. CLI Mode

```bash
tradingagents          # 交互式 CLI
python -m cli.main     # 直接运行
```

### 3. Python API

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from dotenv import load_dotenv

load_dotenv()

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-5.4-mini"
config["quick_think_llm"] = "gpt-5.4-mini"

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2024-05-10")
print(decision)
```

## Configuration

### LLM Providers

| Provider | API Key Env Var | Example Models |
|----------|-----------------|----------------|
| openai | OPENAI_API_KEY | gpt-5.4, gpt-5.4-mini, gpt-5.4-pro |
| anthropic | ANTHROPIC_API_KEY | claude-opus-4-6, claude-sonnet-4-6 |
| google | GOOGLE_API_KEY | gemini-3.1-pro, gemini-3-flash |
| xai | XAI_API_KEY | grok-4, grok-4-fast-reasoning |
| openrouter | OPENROUTER_API_KEY | nvidia/nemotron-3-nano-30b-a3b:free |
| dashscope | DASHSCOPE_API_KEY | glm-5 |
| ollama | (本地) | qwen3:latest, glm-4.7-flash:latest |

### Data Vendors

默认使用 `yfinance`（免费，无需额外 API Key）。可选 `alpha_vantage`（需 ALPHA_VANTAGE_API_KEY）。

### Key Config Options

```python
config["llm_provider"] = "openai"       # LLM 提供商
config["deep_think_llm"] = "gpt-5.4"    # 复杂推理模型
config["quick_think_llm"] = "gpt-5.4-mini"  # 快速任务模型
config["max_debate_rounds"] = 1         # 辩论轮数
config["max_risk_discuss_rounds"] = 1   # 风险讨论轮数
config["output_language"] = "English"   # 输出语言
```

## Development Guidelines

### Code Style
- PEP 8 规范
- 类型注解
- 使用 black/ruff 格式化

### Testing
```bash
pytest tests/
pytest --cov=tradingagents
```

### Agent Flow
1. **Analysts** → 分析市场数据（基本面、新闻、情绪、技术）
2. **Researchers** → 多空辩论，评估风险收益
3. **Trader** → 综合报告，做出交易决策
4. **Risk Management** → 风险评估，调整策略
5. **Portfolio Manager** → 最终批准/拒绝

## Notes

- 项目用于研究目的，不构成投资建议
- 默认使用 yfinance，无额外费用
- LLM 调用会产生 API 费用，注意控制成本
- `eval_results/` 和 `srcMO/` 是临时目录，已忽略

## 改造说明

相比原始版本，本项目做了以下优化：

1. **新增 DashScope 支持** - 添加阿里云通义千问/GLM 作为 LLM 提供商，国内用户无需翻墙
2. **简化所有 Agent Prompt** - 大幅精简 prompt，减少 token 消耗和 API 成本
3. **限制输出长度** - 所有代理输出限制在 180-220 字，提高效率
4. **工作流优化** - 支持跳过辩论和风险讨论环节（设置 `max_debate_rounds=0` 或 `max_risk_discuss_rounds=0`）
5. **技术指标优化** - 从最多 8 个指标减少到 4 个，聚焦关键信号
6. **报告格式简化** - 更简洁清晰的报告输出