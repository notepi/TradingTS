# TradingAgents

多智能体 LLM 金融交易框架。

## 快速运行

### CLI 自动化（推荐给 LLM 测试）

```bash
# 一条命令：启动 Dashboard → 分析 → 关闭端口
tradingagents test 688333.SH --date 2026-04-14
```

### Dashboard 网页

```bash
uv run python -m web
# 浏览器打开 http://localhost:8765
```

### CLI 交互式

```bash
tradingagents analyze
```

**结果目录**：`results/{ticker}/{date}/dashboard_*/reports/`

## 环境配置

`.env` 文件：
- `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`
- `CITYDATA_TOKEN` - A股数据

## 配置文件

| 文件 | 用途 |
|------|------|
| `config.yaml` | LLM 和数据源 |
| `agents_registry.yaml` | 智能体工具绑定 |
| `tools_registry.yaml` | 工具定义 |

## 目录结构

```
TradingAgents/
├── cli/                    # CLI 入口（analyze 交互 / test 自动化）
├── web/                    # Dashboard HTTP 服务（端口 8765）
├── tradingagents/          # 核心库
│   ├── agents/            # 智能体实现
│   │   ├── analysts/      # 市场/新闻/基本面/情绪分析师
│   │   └── utils/        # 工具（indicator_docs_loader.py 动态加载指标）
│   ├── dataflows/         # @auto_tool 装饰器
│   └── config/            # 配置文件
├── datasource/tushare/    # A股数据源
└── docs/                  # 详细文档
```

## 核心文件

- `tradingagents/agents/analysts/market_analyst.py` - 市场分析师（含动态指标加载）
- `tradingagents/agents/utils/indicator_docs_loader.py` - 从 tools_registry.yaml 动态读取指标文档
- `web/dashboard.py` - Dashboard HTTP API（POST /api/start, GET /api/state）

## 详细文档

- [docs/agent-architecture.md](docs/agent-architecture.md) - 智能体架构与辩论机制
- [docs/dataflow-architecture.md](docs/dataflow-architecture.md) - 数据流架构
- [docs/graph-execution.md](docs/graph-execution.md) - LangGraph 执行流程
- [docs/agent-tools-configuration.md](docs/agent-tools-configuration.md) - 工具配置
- [docs/indicator_analysis_final_report.md](docs/indicator_analysis_final_report.md) - 技术指标修复报告
