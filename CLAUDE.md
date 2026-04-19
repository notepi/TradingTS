# TradingAgents

多智能体 LLM 金融交易框架。

## 快速运行

### CLI 自动化（推荐给 LLM 测试）

```bash
# 一条命令：启动 Dashboard → 分析 → 关闭端口
uv run tradingagents test 688333.SH --date 2026-04-14
2026-04-14是日期，要自己修改
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
| `tradingagents/config.yaml` | LLM 和数据源配置 |
| `tradingagents/config/agents_registry.yaml` | 智能体工具绑定 |
| `datasource/datahub/servers/registry.yaml` | 工具定义 + vendor 路由 |

## 目录结构

```
TradingAgents/
├── cli/                    # CLI 入口（analyze 交互 / test 自动化）
├── web/                    # Dashboard HTTP 服务（端口 8765）
├── tradingagents/          # 核心库
│   ├── agents/            # 智能体实现
│   │   ├── analysts/      # 市场/新闻/基本面/情绪分析师
│   │   └── utils/         # 工具函数
│   ├── dataflows/         # @auto_tool 装饰器
│   └── config/            # 配置文件
├── datasource/
│   ├── datahub/servers/   # 数仓层（@tool 定义 + vendor 路由）
│   ├── tushare/           # A股数据源
│   ├── yfinance/          # 美股数据源
│   └── alpha_vantage/     # Alpha Vantage 数据源
└── docs/                  # 详细文档
```

## 核心文件

- `datasource/datahub/servers/interface.py` - vendor 路由机制 + 自动注册
- `datasource/datahub/servers/registry.yaml` - 工具定义 + vendor 配置
- `web/dashboard.py` - Dashboard HTTP API（POST /api/start, GET /api/state）

## 详细文档

**文档入口**：[docs/README.md](docs/README.md)

**用户文档**：
- [docs/getting-started.md](docs/getting-started.md) - 快速上手
- [docs/cli-guide.md](docs/cli-guide.md) - CLI 使用
- [docs/dashboard-guide.md](docs/dashboard-guide.md) - Dashboard 使用

**开发者文档**：
- [docs/datahub-design.md](docs/datahub-design.md) - 数仓层架构设计
- [docs/agent-architecture.md](docs/agent-architecture.md) - 智能体架构
- [docs/graph-execution.md](docs/graph-execution.md) - LangGraph 执行流程
