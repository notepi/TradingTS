# 快速上手指南

本指南帮助新用户在 5 分钟内完成首次运行。

## 前置条件

- Python 3.10+
- uv 包管理器（[安装指南](https://docs.astral.sh/uv/)）
- API Keys（至少一个）

## 安装

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
uv sync
```

## 环境配置

创建 `.env` 文件：

```bash
# LLM API Keys（至少配置一个）
OPENAI_API_KEY=sk-xxx
DASHSCOPE_API_KEY=xxx      # A股用户推荐
GOOGLE_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
XAI_API_KEY=xxx

# 数据源 Token
CITYDATA_TOKEN=xxx          # A股数据源（Tushare）
```

## 三种运行方式

### 方式一：CLI 自动化（推荐）

一条命令完成分析，适合批量测试：

```bash
uv run tradingagents test 688333.SH --date 2026-04-19
```

参数：
- `ticker`：股票代码（必填）
- `--date`：分析日期（可选，默认今天）

执行流程：启动 Dashboard → 分析 → 自动关闭

结果目录：`results/{ticker}/{date}/dashboard_*/reports/`

### 方式二：Dashboard 网页

可视化界面，实时查看进度：

```bash
uv run python -m web
# 浏览器打开 http://localhost:8765
```

自定义端口：
```bash
uv run python -m web --port 9000
```

### 方式三：CLI 交互式

步骤引导选择参数：

```bash
uv run tradingagents analyze
```

交互流程（8 步）：
1. 输入股票代码（如 688333.SH, SPY）
2. 选择分析日期（YYYY-MM-DD）
3. 选择输出语言
4. 选择分析师（市场/新闻/基本面/情绪）
5. 选择研究深度（Shallow/Medium/Deep）
6. 选择 LLM Provider
7. 选择浅思考模型
8. 选择深思考模型

## 分析结果解读

结果目录结构：
```
results/{ticker}/{date}/dashboard_{timestamp}/
├── reports/
│   ├── market_report.md          # 市场分析
│   ├── sentiment_report.md       # 社交情绪
│   ├── news_report.md            # 新闻分析
│   ├── fundamentals_report.md    # 基本面分析
│   ├── investment_plan.md        # 研究团队决策
│   ├── trader_investment_plan.md # 交易团队计划
│   └── final_trade_decision.md   # 最终交易决策
├── complete_report.md            # 合成报告
└── analysis_stats.json           # 统计信息
```

## 股票代码格式

| 市场 | 格式示例 |
|------|----------|
| A股 | 688333.SH, 600519.SH |
| 美股 | SPY, AAPL |
| 港股 | 0700.HK |
| 日股 | 7203.T |
| 加股 | CNC.TO |

## 常见问题

### API Key 配置错误

检查 `.env` 文件是否存在且包含正确的 Key：
```bash
cat .env
```

### 数据源无权限

A股数据需要 CITYDATA_TOKEN（Tushare），美股数据使用 yfinance（免费）。

### 日期格式错误

日期格式必须为 `YYYY-MM-DD`，如 `2026-04-19`。

### 端口冲突

Dashboard 默认端口 8765，使用 `--port` 参数更换端口。

## 下一步

- CLI 详细使用 → [cli-guide.md](cli-guide.md)
- Dashboard 详细使用 → [dashboard-guide.md](dashboard-guide.md)
- 配置文件详解 → [configuration-guide.md](configuration-guide.md)