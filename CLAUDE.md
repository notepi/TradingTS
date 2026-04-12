# TradingAgents

## 快速运行

```bash
uv run python main.py          # 单股票分析（默认 NVDA）
uv run python -m web           # Web Dashboard（端口 8765）
tradingagents                  # 交互式 CLI
```

## 环境配置

至少配置一个 LLM API Key（`.env`）：
- `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY`
- `CITYDATA_TOKEN` - A股数据（tushare + citydata.club 代理）

## 核心配置

`config.yaml` 管理 LLM 和数据源：

```yaml
llm_provider: "dashscope"
deep_think_llm: "glm-5"
quick_think_llm: "glm-5"
backend_url: "https://coding.dashscope.aliyuncs.com/v1"

data_vendors:
  core_stock_apis: "tushare"
  fundamental_data: "tushare"
  news_data: "yfinance"
```

**配置文件：**
- `config.yaml` - LLM 和数据源
- `agents_registry.yaml` - 智能体工具绑定
- `tools_registry.yaml` - 工具定义

**架构文档详见 [docs/dataflow-architecture.md](docs/dataflow-architecture.md)**

## 智能体团队

| 角色 | 文件 | 功能 |
|------|------|------|
| 基本面分析师 | `tradingagents/agents/analysts/fundamentals_analyst.py` | 公司财务分析 |
| 技术/市场分析师 | `tradingagents/agents/analysts/market_analyst.py` | 技术指标分析 |
| 新闻分析师 | `tradingagents/agents/analysts/news_analyst.py` | 新闻影响分析 |
| 社交媒体分析师 | `tradingagents/agents/analysts/social_media_analyst.py` | 情绪分析 |
| 多头研究员 | `tradingagents/agents/researchers/bull_researcher.py` | 正面观点辩论 |
| 空头研究员 | `tradingagents/agents/researchers/bear_researcher.py` | 负面观点辩论 |
| 风险辩论者 | `tradingagents/agents/risk_mgmt/*.py` | 风险评估辩论 |
| 交易员 | `tradingagents/agents/trader/trader.py` | 交易决策 |
| 投资组合经理 | `tradingagents/agents/managers/portfolio_manager.py` | 最终审批 |

## 工作流程

```
分析师 → 研究员辩论 → 风险评估 → 经理审批 → 交易员执行
```

## 添加工具

**加工具只改配置，不改代码。**

详见 [docs/agent-tools-configuration.md](docs/agent-tools-configuration.md)

| 工具类型 | 改动 |
|---------|------|
| 通用工具 | 数据函数 + `@auto_tool` + 2个配置文件 |
| 专业工具 | 以上 + `agents_registry.yaml` 加 `usage` 字段 |

**示例：**
```yaml
# agents_registry.yaml
- name: get_new_metric
  usage: "Use for XYZ analysis. Check ABC."
```

## 目录结构

```
TradingAgents/
├── datasource/tushare/      # A股数据源
│   ├── data.py              # 数据接口
│   └── indicators/          # Lynch 指标
├── web/                     # Web Dashboard
├── cli/                     # CLI 模块
├── docs/                    # 文档
└── tradingagents/           # 核心库
    ├── agents/              # 智能体
    ├── dataflows/           # 数据流路由
    │   └── decorators.py    # @auto_tool 装饰器
    └── config/              # 配置管理
        ├── tools_registry.yaml    # 工具定义
        └── agents_registry.yaml   # 智能体工具绑定
```

## 开发规范

### Plan 工作流
- 全局：`~/.claude/plans/`
- 本地：`.claude/plans/current.md`
- 执行前 git commit，执行后 git commit

### Git 提交
每次操作后立即 commit：
```bash
git add -A && git commit -m "描述"
```

## 注意

- `backtrader` / `redis` 在依赖中但未实际使用
- Web Dashboard 无翻译功能（如需翻译请用 CLI）