# TradingAgents 3分钟上手

> 默认模式：A 股 + Tushare citydata 代理

详细说明见：[docs/USER_GUIDE.md](/Users/pan/Desktop/02%20开发项目/TradingAgents/docs/USER_GUIDE.md)

## 1. 准备环境

安装依赖：

```bash
pip install .
```

在 `.env` 中至少配置：

```bash
# LLM（任选其一）
DASHSCOPE_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
XAI_API_KEY=
OPENROUTER_API_KEY=

# Tushare citydata 代理（默认数据源必需）
CITYDATA_TOKEN=
# 或
TUSHARE_TOKEN=
```

## 2. 股票代码格式

当前项目只支持 A 股。

支持：

- `600519.SH`
- `000001.SZ`
- `688333.SH`
- `688333.SS`，会自动转成 `688333.SH`
- `600519` 这种 6 位代码，会自动补交易所后缀

不支持：

- `NVDA`
- `0700.HK`
- `7203.T`

## 3. 怎么运行

### 方式一：CLI

```bash
tradingagents
```

或：

```bash
python -m cli.main
```

### 方式二：直接跑示例

```bash
python main.py
```

### 方式三：Python API

```python
from dotenv import load_dotenv
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

load_dotenv()

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"
config["deep_think_llm"] = "glm-5"
config["quick_think_llm"] = "glm-5"
config["output_language"] = "Chinese"

ta = TradingAgentsGraph(debug=True, config=config)
final_state, decision = ta.propagate("600519.SH", "2025-04-02")

print(decision)
```

## 4. 会生成什么结果

程序会给你两层结果：

1. 最终评级

- `BUY`
- `OVERWEIGHT`
- `HOLD`
- `UNDERWEIGHT`
- `SELL`

2. 完整分析内容

`final_state` 中会包含：

- `market_report`
- `sentiment_report`
- `news_report`
- `fundamentals_report`
- `investment_plan`
- `trader_investment_plan`
- `final_trade_decision`

也会包含中间讨论：

- `investment_debate_state`
- `risk_debate_state`

## 5. 结果放在哪里

### Python / `main.py`

完整状态会自动写到：

```text
eval_results/<ticker>/TradingAgentsStrategy_logs/full_states_log_<trade_date>.json
```

例如：

```text
eval_results/600519.SH/TradingAgentsStrategy_logs/full_states_log_2025-04-02.json
```

### CLI

运行过程中的结果会写到：

```text
results/<ticker>/<analysis_date>/
```

如果你选择保存完整报告，还会额外生成：

```text
reports/<ticker>_<timestamp>/
```

其中包含：

- 分阶段报告目录
- `complete_report.md`

## 6. 当前版本注意事项

- 默认数据源四类都已切到 `tushare`
- 行情、指标、基本面是 Tushare 实数数据
- `get_news`、`get_global_news`、`get_insider_transactions` 目前是稳定占位返回，不是实时新闻源
