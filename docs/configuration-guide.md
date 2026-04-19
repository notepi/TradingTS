# 配置详解

TradingAgents 使用三个配置文件控制系统行为。

## 配置文件概览

| 文件 | 位置 | 用途 |
|------|------|------|
| config.yaml | tradingagents/config.yaml | LLM 和数据源主配置 |
| agents_registry.yaml | tradingagents/config/agents_registry.yaml | 智能体工具绑定 |
| registry.yaml | datasource/datahub/servers/registry.yaml | 工具定义 + vendor 路由 |

---

## config.yaml详解

### LLM 配置

```yaml
llm_provider: "dashscope"       # LLM 提供商
deep_think_llm: "glm-5"         # 深思考模型（复杂推理）
quick_think_llm: "glm-5"        # 浅思考模型（快速决策）
backend_url: "https://coding.dashscope.aliyuncs.com/v1"  # API 地址
```

**LLM Provider 选项**：

| Provider | 推荐模型 | API 地址 |
|----------|----------|----------|
| openai | gpt-4o, gpt-4o-mini | https://api.openai.com/v1 |
| anthropic | claude-sonnet-4-20250514 | https://api.anthropic.com/ |
| google | gemini-2.5-flash | https://generativelanguage.googleapis.com/v1 |
| dashscope | glm-5, glm-5-mini | https://coding.dashscope.aliyuncs.com/v1 |
| xai | grok-3-beta | https://api.x.ai/v1 |

### 输出配置

```yaml
output:
  language: "Chinese"  # 输出语言（English/Chinese/Japanese 等）
  log_level: "INFO"    # 日志级别（DEBUG/INFO/WARNING/ERROR）
```

### 数据源配置

```yaml
data_vendors:
  core_stock_apis: "tushare"      # 股价数据源
  technical_indicators: "tushare" # 技术指标数据源
  fundamental_data: "tushare"     # 基本面数据源
  news_data: "yfinance"           # 新闻数据源
```

**数据源选项**：

| 数据源 | 市场 | 特点 |
|--------|------|------|
| tushare | A股 | 需要 CITYDATA_TOKEN，数据全面 |
| yfinance | 全球 | 免费，美股推荐 |
| alpha_vantage | 全球 | 需要 API Key，备用 |
| tushare_sqlite_mirror | A股 | 本地镜像，离线使用 |

### 工具级数据源覆盖

```yaml
tool_vendors:
  get_news: "yfinance"  # 单个工具指定数据源（优先级最高）
```

### 数据源路径配置

```yaml
vendor_paths:
  tushare: "datasource.tushare"
  yfinance: "datasource.yfinance"
  alpha_vantage: "datasource.alpha_vantage"
  # my_metrics: "/path/to/my_metrics"  # 自定义数据源
```

---

## agents_registry.yaml详解

### 结构

```yaml
agents:
  fundamentals_analyst:
    tools:
      - name: get_fundamentals
      - name: get_balance_sheet
      - name: get_cashflow
      - name: get_income_statement
      - name: get_peg_ratio
      - name: get_yoy_growth
```

### 智能体工具绑定

| 智能体 | 可用工具 |
|--------|----------|
| fundamentals_analyst | get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_peg_ratio, get_yoy_growth |
| market_analyst | get_stock_data, get_indicators |
| social_analyst | get_news |
| news_analyst | get_news, get_global_news, get_insider_transactions |

---

## registry.yaml详解

### 工具定义结构

```yaml
tools:
  get_stock_data:
    category: core_stock_apis
    module_path: datasource.datahub.servers.market
    description: |
      股票价格数据（OHLCV）- 获取股票的历史行情数据。
    vendors: [tushare, yfinance, alpha_vantage]
```

### Category 分类

| Category | 工具 |
|----------|------|
| core_stock_apis | get_stock_data |
| technical_indicators | get_indicators |
| fundamental_data | get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_peg_ratio, get_yoy_growth |
| news_data | get_news, get_global_news, get_insider_transactions |

### Vendor 支持矩阵

| 工具 | tushare | yfinance | alpha_vantage |
|------|---------|----------|---------------|
| get_stock_data | Y | Y | Y |
| get_indicators | Y | Y | Y |
| get_fundamentals | Y | Y | Y |
| get_balance_sheet | Y | Y | Y |
| get_cashflow | Y | Y | Y |
| get_income_statement | Y | Y | Y |
| get_news | N | Y | Y |
| get_global_news | N | Y | Y |
| get_insider_transactions | N | Y | Y |
| get_peg_ratio | Y | N | N |
| get_yoy_growth | Y | N | N |

---

## 配置优先级

数据源选择优先级：

```
tool_vendors（工具级） > data_vendors（类别级） > 默认数据源
```

示例：
```yaml
data_vendors:
  news_data: "tushare"      # 类别级配置

tool_vendors:
  get_news: "yfinance"      # 工具级配置（生效）
```

---

## 常见配置场景

### 场景一：A股分析

推荐配置：
```yaml
llm_provider: "dashscope"
deep_think_llm: "glm-5"
quick_think_llm: "glm-5"

data_vendors:
  core_stock_apis: "tushare"
  technical_indicators: "tushare"
  fundamental_data: "tushare"
```

### 场景二：美股分析

推荐配置：
```yaml
llm_provider: "openai"
deep_think_llm: "gpt-4o"
quick_think_llm: "gpt-4o-mini"

data_vendors:
  core_stock_apis: "yfinance"
  technical_indicators: "yfinance"
  fundamental_data: "yfinance"
  news_data: "yfinance"
```

### 场景三：混合市场

```yaml
data_vendors:
  core_stock_apis: "tushare"    # A股用 tushare
  news_data: "yfinance"         # 新闻用 yfinance
```

---

## 配置验证

修改配置后，运行测试验证：

```bash
uv run tradingagents test 600519.SH --date 2026-04-19
```

检查工具调用日志确认数据源生效。

---

## 下一步

- 添加新工具 → [data-source-guide.md](data-source-guide.md)
- 理解架构 → [datahub-design.md](datahub-design.md)