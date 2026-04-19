# Dashboard 使用指南

Dashboard 提供可视化界面和 HTTP API 进行股票分析。

## 启动 Dashboard

```bash
# 默认端口 8765
uv run python -m web

# 自定义端口
uv run python -m web --port 9000
```

浏览器打开：`http://localhost:8765`

## 网页界面

界面组成：
- **左侧**：参数配置面板
- **右侧**：实时分析进度
- **底部**：历史记录管理

## 配置参数

### 基础参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| ticker | 股票代码 | 600519.SH |
| analysis_date | 分析日期 | 今天（YYYY-MM-DD） |
| output_language | 输出语言 | English |

### 分析师选择

| 分析师 | 数据类型 | 说明 |
|--------|----------|------|
| Market Analyst | 技术分析 | 价格、指标、成交量 |
| Social Analyst | 社交情绪 | 社交媒体数据 |
| News Analyst | 新闻事件 | 公司新闻、全球新闻 |
| Fundamentals Analyst | 基本面 | 财务数据、估值指标 |

### 研究深度

| 深度 | 辩论轮数 | 说明 |
|------|----------|------|
| Shallow | 1 | 快速分析 |
| Medium | 3 | 平衡分析 |
| Deep | 5 | 深度分析 |

### LLM 配置

| Provider | 推荐模型 | 特殊配置 |
|----------|----------|----------|
| openai | gpt-4o, gpt-4o-mini | reasoning_effort（low/medium/high） |
| anthropic | claude-sonnet-4-20250514 | effort（low/medium/high） |
| google | gemini-2.5-flash | thinking_level（high/minimal） |
| dashscope | glm-5, glm-5-mini | A股推荐 |
| xai | grok-3-beta | - |

## HTTP API

### GET /api/options

获取配置选项（下拉菜单数据）。

**响应**：
```json
{
  "defaults": { "ticker": "600519.SH", ... },
  "providers": ["openai", "anthropic", "google", "dashscope", "xai"],
  "models": { "openai": { "quick": [...], "deep": [...] }, ... },
  "languages": ["English", "Chinese", "Japanese", ...],
  "research_depths": [1, 3, 5],
  "analysts": ["market", "social", "news", "fundamentals"]
}
```

### POST /api/start

启动分析。

**请求体**：
```json
{
  "ticker": "600519.SH",
  "analysis_date": "2026-04-19",
  "analysts": ["market", "news", "fundamentals"],
  "research_depth": 3,
  "llm_provider": "dashscope",
  "quick_think_llm": "glm-5",
  "deep_think_llm": "glm-5",
  "output_language": "Chinese"
}
```

**响应**：202 Accepted + 当前 snapshot

### GET /api/state

获取当前状态（建议 2 秒轮询）。

**响应**：
```json
{
  "status": "running|completed|error|idle|stopping",
  "agent_status": { "Market Analyst": "completed", ... },
  "current_report": "### Market Analysis\n...",
  "stats": { "llm_calls": 5, "tool_calls": 12, ... },
  "results_path": "results/600519.SH/2026-04-19/dashboard_xxx",
  "started_at": "2026-04-19T10:00:00",
  "finished_at": null,
  "decision": null
}
```

### POST /api/stop

停止当前分析。

**响应**：202 Accepted + snapshot

### POST /api/reset

重置状态到 idle。

**响应**：200 OK + snapshot

### GET /api/history

获取历史分析记录。

**响应**：
```json
{
  "runs": [
    { "run_id": "xxx", "ticker": "600519.SH", "date": "2026-04-18", ... }
  ]
}
```

### POST /api/history/load

加载历史分析记录。

**请求体**：
```json
{
  "run_id": "xxx",
  "output_language": "Chinese"
}
```

**响应**：200 OK + historical snapshot

### POST /api/history/delete

删除历史记录。

**请求体**：
```json
{
  "run_id": "xxx"
}
```

**响应**：200 OK + updated runs list

## 状态监控

建议前端每 2 秒轮询 `/api/state`：

```javascript
setInterval(async () => {
  const state = await fetch('/api/state').then(r => r.json());
  if (state.status === 'completed') {
    // 显示结果、停止轮询
  }
}, 2000);
```

## 结果目录结构

```
results/{ticker}/{date}/dashboard_{timestamp}/
├── reports/
│   ├── market_report.md
│   ├── sentiment_report.md
│   ├── news_report.md
│   ├── fundamentals_report.md
│   ├── investment_plan.md
│   ├── trader_investment_plan.md
│   └── final_trade_decision.md
├── complete_report.md
├── analysis_stats.json
├── message_tool.log
└── translated/（翻译版本）
    └── Chinese/
        └── reports/
```

## 多语言输出

Dashboard 支持将报告翻译为以下语言：

- Chinese（中文）
- Japanese（日语）
- Korean（韩语）
- Spanish（西班牙语）
- Portuguese（葡萄牙语）
- French（法语）
- German（德语）
- Arabic（阿拉伯语）
- Russian（俄语）
- Hindi（印地语）

翻译使用配置的 LLM 进行，结果保存在 `translated/{language}/` 目录。

## 常见问题

### 端口冲突

使用 `--port` 参数更换端口。

### 分析无响应

检查 API Key 配置，确保 `.env` 文件正确。

### 结果未翻译

确保 `output_language` 不是 "English"，翻译需要额外时间。

## 下一步

- CLI 使用 → [cli-guide.md](cli-guide.md)
- 配置详解 → [configuration-guide.md](configuration-guide.md)