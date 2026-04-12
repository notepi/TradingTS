# TradingAgents

> 项目介绍详见 @TradingAgents/README.md

## 快速运行

```bash
cd TradingAgents
uv run python main.py          # 单股票分析（默认 NVDA）
tradingagents                  # 交互式 CLI
```

## Web Dashboard

```bash
cd TradingAgents
uv run python -m web           # 启动 Web Dashboard（端口 8765）
```

启动后访问 http://127.0.0.1:8765

## 环境配置

> 详见 @TradingAgents/.env.example

至少配置一个 LLM Provider API Key：
- `OPENAI_API_KEY` - 默认提供商
- `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` / `XAI_API_KEY` / `OPENROUTER_API_KEY` - 可选

### LLM 配置

LLM 配置通过 `TradingAgents/config.yaml` 管理（扁平格式）：

```yaml
llm_provider: "dashscope"           # LLM 提供商：openai, google, anthropic, xai, openrouter, dashscope
deep_think_llm: "glm-5"           # 深度推理模型
quick_think_llm: "glm-5"          # 快速推理模型
backend_url: "https://coding.dashscope.aliyuncs.com/v1"  # API 地址
```

配置优先级：**用户参数 > config.yaml > default_config.py**

### 数据源配置

项目支持多数据源切换，通过 `config.yaml` 配置：

```yaml
data_vendors:
  core_stock_apis: "tushare"    # 股价数据：tushare, yfinance, alpha_vantage
  technical_indicators: "tushare"  # 技术指标
  fundamental_data: "tushare"   # 基本面数据
  news_data: "yfinance"          # 新闻（tushare 不支持特定股票新闻）

# tool_vendors: 单工具级别路由（优先级更高）
tool_vendors: {}
```

A股数据使用 **tushare + citydata.club 代理**，需要在 `.env` 中配置：
```bash
CITYDATA_TOKEN=your_token_here
```

**数据流架构详见 [docs/dataflow-architecture.md](docs/dataflow-architecture.md)**

#### 添加新指标

1. `tradingagents/config/tools_registry.yaml` 添加配置：
   ```yaml
   get_gross_margin:
     category: fundamental_data
     description: "毛利率"
     vendors: [tushare]
   ```

2. `datasource/tushare/` 实现函数（纯实现，无需 decorator）

3. `datasource/tushare/__init__.py` 导出函数

#### 切换数据源

只需改 `config.yaml`：
```yaml
data_vendors:
  fundamental_data: "yfinance"  # 从 tushare 切到 yfinance
```

#### 添加新数据源

1. 创建 `datasource/my_vendor/` 目录
2. 实现函数并导出
3. 更新 `tools_registry.yaml` 的 vendors 列表
4. 配置 `config.yaml` 路由

## 核心架构

### 智能体团队

| 角色 | 文件 | 功能 |
|------|------|------|
| 基本面分析师 | `agents/analysts/fundamentals_analyst.py` | 公司财务分析 |
| 技术/市场分析师 | `agents/analysts/market_analyst.py` | 技术指标分析 |
| 新闻分析师 | `agents/analysts/news_analyst.py` | 新闻影响分析 |
| 社交媒体分析师 | `agents/analysts/social_media_analyst.py` | 情绪分析 |
| 多头研究员 | `agents/researchers/bull_researcher.py` | 正面观点辩论 |
| 空头研究员 | `agents/researchers/bear_researcher.py` | 负面观点辩论 |
| 风险辩论者 | `agents/risk_mgmt/*.py` | 风险评估辩论 |
| 交易员 | `agents/trader/trader.py` | 交易决策 |
| 投资组合经理 | `agents/managers/portfolio_manager.py` | 最终审批 |

### 工作流程

```
分析师 → 研究员辩论 → 风险评估 → 经理审批 → 交易员执行
```

### 目录结构

```
TradingAgents/
├── datasource/            # 数据源（解耦合架构）
│   └── tushare/           # tushare A股数据（citydata.club 代理）
│       ├── __init__.py    # 自动注册到 VENDOR_REGISTRY
│       ├── proxy.py       # citydata.club 代理层
│       ├── data.py        # 数据接口实现
│       └── symbols.py     # A股代码标准化
├── web/                    # Web Dashboard（独立模块，无翻译功能）
│   ├── dashboard.py       # HTTP 服务器
│   ├── runtime.py         # 分析运行时
│   ├── history.py         # 历史记录加载
│   ├── reporting.py       # 报告生成
│   ├── stats.py           # 统计处理
│   └── static/            # 前端资源
├── cli/                    # CLI 模块
└── tradingagents/         # 核心库
```

## Plan 工作流

### Plan 存放位置

| 位置 | 说明 |
|------|------|
| **全局** `~/.claude/plans/` | Claude Code ExitPlanMode 自动写入的位置 |
| **项目本地** `.claude/plans/` | 复制过来的当前 plan，仅本地记录 |

### 执行 Plan 前（按顺序执行）

1. **复制全局 Plan 到项目本地**
   ```bash
   cp ~/.claude/plans/proud-marinating-lynx.md .claude/plans/current.md
   ```

2. **Git 保存当前状态**（每次执行任务前必做）
   ```bash
   git add -A && git commit -m "WIP: 开始执行 plan"
   ```

3. **执行 plan**（Claude Code 从全局路径读取执行）

4. **执行完或被打断后**：再次 git commit 保存进度
   ```bash
   git add -A && git commit -m "WIP: plan 执行中/完成"
   ```

### Plan 文件规则

- 项目本地 `.claude/plans/` 目录下**只保留当前执行的 plan 文件**
- 不保留历史版本（历史由 Git commit 记录）
- 命名：`current.md`（当前 plan）

## Git 提交规则

**每次完成以下操作后，立即执行 `git add && git commit`**，不需要等待确认：

- 修改任何代码文件后
- 修改配置文件后
- 完成任意工具使用后

```bash
git add -A && git commit -m "描述"
```

## 注意

- `backtrader` 和 `redis` 在依赖中但未实际使用
- Web Dashboard 无翻译功能（如需翻译功能请使用 CLI）
