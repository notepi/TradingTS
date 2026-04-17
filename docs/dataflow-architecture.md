# 数据流架构文档

> 本文档说明 TradingAgents 的数据流三层架构、配置方式、以及如何添加新指标或切换数据源。
>
> **相关文档**：[datasource-tools-architecture.md](datasource-tools-architecture.md) - datasource/tools 层的七层架构详解。

## 三层架构

```
┌─────────────────────────────────────────────────────────────────┐
│ 第一层：Category（抽象类别）                                     │
│ 用户视角的语义分类，独立于实现                                    │
├─────────────────────────────────────────────────────────────────┤
│  core_stock_apis      │ 股票价格数据（OHLCV）                    │
│  technical_indicators │ 技术指标（MACD, RSI...）                 │
│  fundamental_data     │ 基本面数据（财报 + 衍生指标）            │
│  news_data            │ 新闻数据                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 第二层：Specification（计算口径）                                │
│ 定义指标是什么，计算公式                                          │
│                                                                  │
│  例如：                                                          │
│  - PEG Ratio = PE(TTM) / 净利润增长率                           │
│  - MACD = EMA(12) - EMA(26)                                    │
│  - YoY Growth = (本期 - 上期) / 上期 × 100%                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 第三层：Vendor（数据源实现）                                      │
│ 不同数据源有各自的计算逻辑                                        │
├─────────────────────────────────────────────────────────────────┤
│  tushare       │ A股专用（citydata.club 代理）                  │
│  yfinance      │ 全球市场（美股为主）                           │
│  alpha_vantage │ 美股专用                                        │
│  akshare       │ A股开源（可扩展）                              │
└─────────────────────────────────────────────────────────────────┘
```

## 核心文件

| 文件 | 作用 |
|------|------|
| `tradingagents/config/tools_registry.yaml` | 单表管理工具定义（category + vendors） |
| `tradingagents/config/agents_registry.yaml` | 智能体工具绑定配置 |
| `tradingagents/dataflows/interface.py` | 自动发现机制，启动时动态注册 |
| `tradingagents/dataflows/decorators.py` | `@auto_tool` 装饰器 |
| `tradingagents/config.yaml` | 数据源路由配置（vendor_paths + data_vendors） |
| `datasource/{vendor}/` | 函数实现 |

## tools_registry.yaml 配置格式

```yaml
tools:
  get_peg_ratio:
    category: fundamental_data    # 第一层：类别
    description: "PEG Ratio = PE / 净利润增长率"
    vendors: [tushare]            # 第三层：哪些数据源实现了

  get_stock_data:
    category: core_stock_apis
    description: "股票价格数据 OHLCV"
    vendors: [tushare, yfinance, alpha_vantage]  # 多数据源可选
```

### get_indicators 特殊配置

`get_indicators` 是唯一有 `vendors` + `indicators` + `indicator_docs` 嵌套结构的工具：

```yaml
get_indicators:
  category: technical_indicators
  description: "技术指标工具..."
  vendors:
    tushare:
      indicators: [close_10_ema, close_50_sma, ...]  # 支持的指标列表
      indicator_docs: |                               # 指标说明文档
        ## 移动平均线
        | close_10_ema | 10日指数移动平均，短周期快速均线 |
        ...
    yfinance:
      indicators: [macd, rsi, boll, adx, sma, ema]
```

**注意**: `indicator_docs` 已被 `indicator_docs_loader.py` 动态读取（见 `market_analyst.py`）。

## 数据源切换

### Category 级别切换

```yaml
# config.yaml
data_vendors:
  fundamental_data: "tushare"    # 整个类别用 tushare
  news_data: "yfinance"          # 新闻用 yfinance
```

### Tool 级别切换（优先级更高）

```yaml
# config.yaml
tool_vendors:
  get_peg_ratio: "alpha_vantage"  # 单个工具切换数据源
```

### 优先级

```
tool_vendors > data_vendors > default > yfinance（系统默认）
```

## 添加新指标

### 步骤 1：在 tools_registry.yaml 添加配置

```yaml
tools:
  get_gross_margin:              # 函数名
    category: fundamental_data   # 所属类别
    description: "毛利率 = (营收 - 成本) / 营收"
    vendors: [tushare]           # 哪些数据源实现
```

### 步骤 2：在数据源实现函数

```python
# datasource/tushare/indicators/my_indicators.py

def get_gross_margin(ticker: str, curr_date: str | None = None):
    """毛利率计算"""
    pro = _get_pro()
    income = pro.income(ts_code=_convert_symbol(ticker))
    # 计算毛利率...
    return result
```

### 步骤 3：导出函数

```python
# datasource/tushare/__init__.py

from .indicators.my_indicators import get_gross_margin

__all__ = [
    ...
    "get_gross_margin",
]
```

### 完成

添加指标只需：**配置 + 写函数 + 导出**，无需改 interface.py。

## 添加新数据源

**切换数据源只需改动 3 个地方，核心代码不动：**

| 改动位置 | 文件 | 说明 |
|----------|------|------|
| **1. 数据实现** | `datasource/{new_vendor}/` | 实现同名函数 |
| **2. 工具定义** | `tools_registry.yaml` | vendors 添加新数据源 |
| **3. 系统配置** | `config.yaml` | vendor_paths + data_vendors |

### 步骤 1：创建目录结构

```
datasource/
└── akshare/
    ├── __init__.py      # 导出所有函数
    ├── data.py          # 基础数据函数
    └── indicators.py    # 指标函数（可选）
```

### 步骤 2：实现同名函数

```python
# datasource/akshare/data.py

def get_stock_data(ticker: str, start_date: str, end_date: str):
    """获取股价数据 - 函数名必须和 tools_registry.yaml 一致"""
    # 调用 akshare API...
    return result

def get_fundamentals(ticker: str, curr_date: str = None):
    """获取基本面数据"""
    return result
```

### 步骤 3：导出函数

```python
# datasource/akshare/__init__.py

from .data import get_stock_data, get_fundamentals, ...

__all__ = ["get_stock_data", "get_fundamentals", ...]
```

### 步骤 4：更新 tools_registry.yaml

```yaml
tools:
  get_stock_data:
    vendors: [tushare, akshare, yfinance]  # 添加 akshare
```

### 步骤 5：配置路由

```yaml
# config.yaml
vendor_paths:
  tushare: "datasource.tushare"
  akshare: "datasource.akshare"   # 新增：告诉系统去哪里找

data_vendors:
  core_stock_apis: "akshare"      # 切换到 akshare
```

### 完成！

无需改动：
- `agents/utils/*_tools.py` - 通过路由层自动适配
- `agents_registry.yaml` - 只关心工具名
- `tradingagents/graph/` - ToolNode 用配置加载

## 数据流调用流程

```
智能体/用户调用
    ↓
route_to_vendor("get_peg_ratio", "600519.SH")
    ↓
get_category_for_method() → category = "fundamental_data"
    ↓
get_vendor() → 查 config.yaml → vendor = "tushare"
    ↓
_VENDOR_REGISTRY["get_peg_ratio"]["tushare"]
    ↓
执行函数 → 返回结果
```

## 自动发现机制 (discover_and_register)

启动时自动扫描 `vendor_paths` 中的模块并注册：

```python
# tradingagents/dataflows/interface.py

_VENDOR_REGISTRY = {}  # 结构: {method: {vendor: function}}

def discover_and_register():
    """模块加载时自动执行"""
    # 1. 读取 tools_registry.yaml
    # 2. 遍历 vendor_paths
    # 3. 用 importlib.import_module 动态导入
    # 4. 调用 register_vendor(method, vendor, func)
```

## Fallback 机制

```yaml
# config.yaml - 多数据源 fallback
data_vendors:
  fundamental_data: "tushare,yfinance"  # 主用 tushare，备用 yfinance
```

当 tushare 失败时，自动切换到 yfinance。

**触发条件**: 目前只处理 `AlphaVantageRateLimitError`，其他异常不会触发 fallback。

## 文件结构总览

```
TradingAgents/
├── tradingagents/
│   ├── config/
│   │   ├── config.yaml              # 路由配置 + vendor_paths
│   │   ├── tools_registry.yaml      # 工具定义（单表）
│   │   └── agents_registry.yaml     # 智能体工具绑定
│   ├── dataflows/
│   │   ├── decorators.py            # @auto_tool 装饰器
│   │   ├── interface.py             # 自动发现 + 路由
│   │   └── yfinance_news.py         # yfinance 新闻实现
│   ├── agents/
│   │   └── utils/
│   │       └── agent_utils.py       # load_agent_tools(), build_tools_usage()
│   └── graph/
│       └── trading_graph.py         # ToolNode 用配置加载
├── datasource/
│   ├── tushare/                     # A股数据源
│   │   ├── __init__.py
│   │   ├── data.py
│   │   └── indicators/
│   │       └── enhanced_data.py     # Lynch 指标
│   └── {new_vendor}/                # 新数据源（按同样结构）
└── docs/
    └── dataflow-architecture.md     # 本文档
```

## 常见问题

### Q: 如何知道某个工具有哪些数据源可选？

查看 `tools_registry.yaml` 中该工具的 `vendors` 列表。

### Q: 数据源切换后代码需要改吗？

不需要。只需改 `config.yaml` 配置 + `datasource/{new_vendor}/` 目录。

### Q: 如何添加一个新的 category？

1. 在 `tools_registry.yaml` 添加工具时指定新 category
2. 在 `config.yaml` 的 `data_vendors` 添加路由配置

### Q: 为什么 yfinance 新闻函数在 dataflows 目录？

因为它是内置实现的，不属于外部数据源目录。vendor_paths 可以指向任意模块路径。

---

*最后更新：2026-04-14*
