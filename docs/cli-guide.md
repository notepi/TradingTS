# CLI 使用指南

TradingAgents 提供两种 CLI 模式：交互式（analyze）和自动化（test）。

## 命令概览

| 命令 | 模式 | 说明 |
|------|------|------|
| `analyze` | 交互式 | 步骤引导选择参数 |
| `test` | 自动化 | 一条命令完成分析 |

## analyze 命令（交互式）

### 使用方式

```bash
uv run tradingagents analyze
```

### 交互流程（8 步）

1. **股票代码**：输入 ticker，如 688333.SH、SPY
2. **分析日期**：YYYY-MM-DD 格式，默认今天
3. **输出语言**：English、Chinese、Japanese 等 11 种
4. **分析师选择**：Market、Social、News、Fundamentals（可多选）
5. **研究深度**：Shallow（1轮）、Medium（3轮）、Deep（5轮）
6. **LLM Provider**：openai、anthropic、google、dashscope、xai 等
7. **浅思考模型**：用于快速决策
8. **深思考模型**：用于复杂推理

### 终端界面说明

分析过程中显示三个面板：

| 面板 | 内容 |
|------|------|
| **Progress** | 智能体状态（pending/in_progress/completed） |
| **Messages & Tools** | 工具调用日志、消息流 |
| **Current Report** | 当前生成的报告内容 |

底部显示统计：Agents 进度、LLM 调用次数、Tools 调用次数、Token 使用、耗时

### 结果保存

分析完成后可选择：
- 保存报告（默认路径：reports/{ticker}_{timestamp}）
- 显示完整报告

## test 命令（自动化）

### 使用方式

```bash
uv run tradingagents test <ticker> --date <YYYY-MM-DD>
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `ticker` | 股票代码 | 必填 |
| `--date` | 分析日期 | 今天 |

### 执行流程

1. 查找可用端口（随机）
2. 启动 Dashboard
3. 等待就绪（最长 60 秒）
4. 调用分析 API
5. 等待完成（轮询 /api/state）
6. 自动关闭 Dashboard

### 结果位置

`results/{ticker}/{date}/dashboard_*/reports/`

## 股票代码格式

| 市场 | 格式示例 |
|------|----------|
| A股 | 688333.SH, 600519.SH, 000001.SZ |
| 美股 | SPY, AAPL, TSLA |
| 港股 | 0700.HK, 0941.HK |
| 日股 | 7203.T（丰田） |
| 加股 | CNC.TO |
| 其他 | 使用交易所后缀 |

## 智能体流程

```
I. Analyst Team（分析师团队）
   → Market Analyst / Social Analyst / News Analyst / Fundamentals Analyst

II. Research Team（研究团队）
   → Bull Researcher / Bear Researcher 辩论
   → Research Manager 决策

III. Trading Team（交易团队）
   → Trader 制定计划

IV. Risk Management（风险管理）
   → Aggressive / Conservative / Neutral Analyst 辩论
   → Portfolio Manager 最终决策
```

## 常见问题

### 端口冲突

test 命令自动查找可用端口，不会冲突。

### 分析超时

默认最长等待 60 秒 Dashboard 启动，分析过程无超时限制。

### 股票代码格式错误

确保使用正确格式，A股需要交易所后缀（.SH 或 .SZ）。

### 模型选择

根据 LLM Provider 选择对应的模型：
- openai：gpt-4o, gpt-4o-mini
- dashscope：glm-5, glm-5-mini（A股推荐）
- anthropic：claude-sonnet-4-20250514
- google：gemini-2.5-flash

## 下一步

- Dashboard 使用 → [dashboard-guide.md](dashboard-guide.md)
- 配置详解 → [configuration-guide.md](configuration-guide.md)