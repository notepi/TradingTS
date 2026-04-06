# TradingAgents

## 背景

- 定位: 多代理 LLM 金融交易框架
- 目的: 模拟真实交易公司，协同评估市场并做出交易决策
- 技术栈: Python 3.10+, LangGraph, LangChain
- 数据源: Tushare citydata (A股) + Tavily (新闻)
- 默认 LLM: DashScope GLM-5

## 项目开发协作流程

严格按以下顺序执行：
1. 用户定任务（新功能、bug 修复、代码审查等）
2. Claude 做 plan → 写入项目目录 `.claude/plans/active/`
3. 用户确认 plan
4. Claude 执行
5. 测试验证
6. **用户确认测试通过后**，Claude 才能修改 CLAUDE.md
7. plan 归档到 `.claude/plans/archive/`

## 操作指令

### 快速运行

```bash
uv run python main.py                    # 单股票分析（默认 688333.SH）
```

### CLI 模式

```bash
tradingagents                            # 交互式 CLI
tradingagents dashboard                  # Web Dashboard
tradingagents dashboard --port 9000      # 指定端口
python -m cli.main                       # 直接运行
```

### Python API

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from dotenv import load_dotenv

load_dotenv()

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"
config["deep_think_llm"] = "glm-5"
config["quick_think_llm"] = "glm-5"

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("600519.SH", "2024-05-10")
print(decision)
```

## 数据说明

### 环境配置

`.env` 文件：

```
# 必需
DASHSCOPE_API_KEY=sk-xxx        # LLM API Key
CITYDATA_TOKEN=xxx              # A股数据
TAVILY_API_KEYS=tvly-xxx        # 新闻搜索

# 可选
TUSHARE_TOKEN=xxx               # Tushare 原生 token
TRANSLATION_MODEL=glm-5         # 翻译模型覆盖
```

### 数据源映射

| 数据类型 | 默认源 | 环境变量 |
|----------|--------|----------|
| 行情 OHLCV | Tushare citydata | CITYDATA_TOKEN |
| 技术指标 | Tushare citydata | CITYDATA_TOKEN |
| 基本面 | Tushare citydata | CITYDATA_TOKEN |
| 新闻 | Tavily | TAVILY_API_KEYS |

### 文件位置

| 目录 | 内容 |
|------|------|
| cli/ | CLI 交互界面 |
| cli/dashboard.py | Web Dashboard 服务 |
| tradingagents/ | 核心框架 |
| tradingagents/agents/ | 代理实现 |
| tradingagents/dataflows/ | 数据接口 |
| tradingagents/llm_clients/ | LLM 客户端 |
| results/ | 运行结果输出 |

## 文档索引

| 文档 | 内容 |
|------|------|
| [README.md](README.md) | 项目介绍 |
| [docs/usage.md](docs/usage.md) | 快速使用说明 |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | 完整使用说明 |

## 改造说明

相比原始版本，本项目做了以下优化：

1. **新增 DashScope 支持** - 国内用户无需翻墙
2. **新增 Tavily 新闻源** - 替代 Tushare placeholder
3. **新增 Web Dashboard** - 可视化操作界面
4. **多语言输出** - 支持 11 种语言