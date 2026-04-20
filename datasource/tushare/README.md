# Tushare 目录架构分析

## 完整架构：Trading System → Datahub → Vendors

```
┌─────────────────────────────────────────────────────────────┐
│              TradingAgents (Agents/Graph)                  │
│  - market_analyst, fundamentals_analyst, news_analyst       │
└─────────────────────────┬─────────────────────────────────┘
                          │ 调用 tool 函数
                          ▼
┌─────────────────────────────────────────────────────────────┐
│     datasource/datahub/servers/*.py                         │
│     (market.py, indicator.py, fundamental.py, news.py)      │
│  - 薄封装，使用 @auto_tool 装饰器                            │
│  - 调用 route_to_vendor(method_name, args...)              │
└─────────────────────────┬─────────────────────────────────┘
                          │ route_to_vendor()
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  datasource/datahub/servers/interface.py                   │
│  - _VENDOR_REGISTRY: {method: {vendor: func}}               │
│  - route_to_vendor() → 路由到配置的 vendor                  │
│  - discover_and_register() → 自动发现注册实现                │
└─────────────────────────┬─────────────────────────────────┘
                          │ 调用注册的函数
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              datasource/{vendor}/                           │
│              (tushare, yfinance, tushare_sqlite_mirror)    │
│  - 各 vendor 实现相同接口的函数签名                          │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
tushare/
├── __init__.py               # 包入口，对外暴露 API
├── api.py                    # 双模式入口 (proxy/sdk)
├── data.py                   # 高层数据函数（数据获取层）
├── proxy.py                  # HTTP 代理 (citydata.club)
├── symbols.py                # A股代码规范化
└── indicators/
    └── enhanced_data.py      # 高级指标（数据增强层）
```

## 模块职责

| 文件 | 职责 | 例子 |
|------|------|------|
| `__init__.py` | 包入口，对外暴露 API | 导出 get_stock_data 等 |
| `api.py` | 双模式入口 | get_api() 返回 proxy 或 sdk 模式 |
| `data.py` | 基础数据函数（数据获取层） | get_Tushare_data_online、get_fundamentals |
| `proxy.py` | HTTP 代理实现 | TushareProxyAPI.__getattr__ 动态路由 |
| `symbols.py` | A股代码规范化 | normalize_a_share_symbol() |
| `indicators/enhanced_data.py` | 高级指标（数据增强层） | get_peg_ratio、get_yoy_growth |

## Datahub 抽象层

### 核心接口 (interface.py)

- `_VENDOR_REGISTRY`: `{method: {vendor: func}}` - 方法到 vendor 函数的映射
- `route_to_vendor()`: 根据配置路由到对应 vendor
- `discover_and_register()`: 启动时自动发现并注册所有 vendor 实现

### 自动发现机制

1. 启动时调用 `discover_and_register()`
2. `load_tools_registry()` 加载 `registry.yaml`
3. 遍历 `registry.yaml` 中的每个工具
4. 对每个 vendor：`importlib.import_module(f"datasource.{vendor}")`
5. `getattr(module, tool_name)` 获取函数并注册到 `_VENDOR_REGISTRY`

### 统一函数签名 (所有 vendor 必须实现)

| 工具 | 函数签名 |
|------|---------|
| `get_stock_data` | `(symbol, start_date, end_date) -> str` |
| `get_indicators` | `(symbol, indicator, curr_date, look_back_days=120) -> str` |
| `get_fundamentals` | `(ticker, curr_date) -> str` |
| `get_balance_sheet` | `(ticker, freq="quarterly", curr_date=None) -> str` |
| `get_cashflow` | `(ticker, freq="quarterly", curr_date=None) -> str` |
| `get_income_statement` | `(ticker, freq="quarterly", curr_date=None) -> str` |
| `get_news` | `(symbol, curr_date) -> str` |
| `get_insider_transactions` | `(ticker) -> str` |

## 关键设计模式

### 1. Vendor Registry Pattern
- `_VENDOR_REGISTRY` 是 `{method: {vendor: func}}` 的嵌套字典
- 支持运行时 vendor 选择和 fallback

### 2. Auto-discovery Pattern
- `_discover_and_register_impl()` 扫描 `registry.yaml`
- 动态导入模块并注册 vendor 函数

### 3. 双模式模式（Tushare）
- `TUSHARE_MODE=proxy` → HTTP 转发到 `https://tushare.citydata.club`
- `TUSHARE_MODE=sdk` → 官方 tushare SDK

### 4. 动态代理模式（Tushare Proxy）
- `TushareProxyAPI.__getattr__` 拦截任意方法调用
- 无需为每个 tushare API 端点预定义方法

### 5. 季度计算模式
- 从累计报表推导单季度值
- `_calculate_single_quarter_values()` 处理 Q1 直接、Q2=Q2累计-Q1累计 等

## 配置

`tradingagents/config.yaml` 中的 `data_vendors` 配置：
```yaml
data_vendors:
  core_stock_apis: yfinance
  technical_indicators: yfinance
  fundamental_data: yfinance
  news_data: yfinance
```

`registry.yaml` 定义每个工具的元数据和 vendor 实现映射。

## 包入口文件 (__init__.py)

`__init__.py` 是**对外暴露的总接口**，定义该包提供什么：

```python
from .api import get_api, TushareAPI, pro_api  # API 入口
from .data import get_Tushare_data_online, ... # 数据函数
from .indicators.enhanced_data import get_peg_ratio, get_yoy_growth

# 别名映射（兼容 route_to_vendor 的函数名）
get_stock_data = get_Tushare_data_online
get_indicators = get_stock_stats_indicators_window

__all__ = ["get_api", "get_stock_data", "get_fundamentals", ...]
```

### 作用

- **声明公开 API**：外部调用 `datasource.tushare.get_stock_data` 时实际执行 `get_Tushare_data_online`
- **隐藏内部实现**：外部不需要知道 `data.py`、`proxy.py` 的具体细节
- **别名映射**：将内部函数名映射为统一的工具名（如 `get_stock_data`）

这遵循 Python 包的 **产品说明书** 模式：声明"我能提供什么"，隐藏"内部怎么实现"。

## 返回单位

所有函数输出的金额字段单位统一为**元 (CNY)**，header 注释标注 `# Unit: Yuan (CNY)`。

### 单位转换规则

| 数据类型 | Tushare 原始单位 | 处理方式 |
|---------|-----------------|---------|
| `total_mv`, `circ_mv` | 万元 | `get_fundamentals` 中手动 `* 10000` 转元 |
| `total_share` | 万股 | `get_fundamentals` 中手动 `* 10000` 转股 |
| `revenue`, `n_income` | 元 | 直接使用，无需转换 |
| `n_cashflow_act` 等 | 元 | 直接使用，无需转换 |

### 示例

```python
# get_fundamentals 输出：
# Total Market Cap (元): 86044565580000.00  # 已从万元转换
# Revenue (元): 1160730703.00              # 本身就是元

# get_balance_sheet / get_cashflow / get_income_statement 输出 CSV：
# Header: # Unit: Yuan (CNY)
# 列值直接是元，无需转换
```