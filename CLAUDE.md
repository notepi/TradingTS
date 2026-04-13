# TradingAgents

## 快速运行

```bash
# 单股票分析（API 调用，生成本地日志）
# 1. 启动 dashboard 服务
uv run python -m web

# 2. 调用 API 触发分析（另开终端）
curl -X POST http://localhost:8765/api/start \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "688333.SH",
    "analysis_date": "2026-04-14",
    "analysts": ["market", "social", "news", "fundamentals"],
    "output_language": "Chinese"
  }'

# output_language 支持: Chinese, English, Japanese 等
# 设置为 Chinese 会启用翻译功能

# 结果目录：results/688333.SH/2026-04-14/dashboard_YYYYMMDD_HHMMSS/
```

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

详见 [docs/dataflow-architecture.md](docs/dataflow-architecture.md)

## 智能体

| 角色 | 功能 |
|------|------|
| 基本面分析师 | 财务分析 |
| 技术分析师 | 技术指标 |
| 新闻分析师 | 新闻影响 |
| 研究员 | 多空辩论 |
| 风险评估 | 风险分析 |
| 投资组合经理 | 最终审批 |

## 添加工具

加工具只改配置，不改代码。

详见 [docs/agent-tools-configuration.md](docs/agent-tools-configuration.md)

```yaml
# agents_registry.yaml
- name: get_new_metric
  usage: "Use for XYZ analysis"
```

## 目录结构

```
TradingAgents/
├── datasource/tushare/    # A股数据源
├── tradingagents/         # 核心库
│   ├── agents/            # 智能体
│   ├── dataflows/         # @auto_tool 装饰器
│   └── config/            # 配置文件
└── docs/                  # 文档
```