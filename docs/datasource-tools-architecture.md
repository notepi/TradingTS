# 数据源工具层架构

> 本文档定义 datasource/tools 层的七层架构、目录结构、职责划分和实施计划。

## 七层架构

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. 实现层 - datasource/{vendor}/*.py                            │
│    各 vendor 的 API 实现（分散在多个文件）                        │
│    例：tushare/data.py, tushare/indicators/enhanced_data.py     │
├─────────────────────────────────────────────────────────────────┤
│ 2. 接口层 - datasource/{vendor}/__init__.py                     │
│    统一对外导出（门面），供 interface.py 扫描注册                │
│    例：tushare/__init__.py 导出 get_balance_sheet               │
├─────────────────────────────────────────────────────────────────┤
│ 3. 抽象层 - datasource/tools/interface.py                       │
│    路由核心：route_to_vendor, _VENDOR_REGISTRY                  │
│    启动时扫描各 vendor 目录并注册函数                            │
├─────────────────────────────────────────────────────────────────┤
│ 4. 声明层 - datasource/tools/tools_registry.yaml                │
│    定义工具支持哪些 vendors（路由信息）                          │
│    例：get_balance_sheet: vendors: [tushare, yfinance]          │
├─────────────────────────────────────────────────────────────────┤
│ 5. 决策层 - tradingagents/config.yaml                           │
│    决定实际用哪个 vendor（data_vendors, tool_vendors）          │
│    例：fundamental_data: "tushare"                              │
├─────────────────────────────────────────────────────────────────┤
│ 6. 工具层 - datasource/tools/*_tools.py                         │
│    @tool 定义 + docstring description                           │
│    内部调用 route_to_vendor() 路由到具体实现                     │
├─────────────────────────────────────────────────────────────────┤
│ 7. 智能体层 - tradingagents/config/agents_registry.yaml         │
│    智能体权限控制（哪些 agent 用哪些 tools）                     │
└─────────────────────────────────────────────────────────────────┘
```

## 目录结构

```
datasource/
├── tushare/                   ← 实现层
│   ├── __init__.py            ← 对外接口：统一导出所有函数（门面）
│   ├── data.py                ← 实现：get_fundamentals, get_balance_sheet 等
│   ├── indicators/
│   │   └── enhanced_data.py   ← 实现：get_peg_ratio, get_yoy_growth
│   ├── api.py                 ← 内部：Tushare API 基础封装
│   ├── proxy.py               ← 内部：代理工具
│   └── symbols.py             ← 内部：股票代码处理
├── yfinance/
│   ├── __init__.py            ← 对外接口
│   ├── stock.py               ← 实现
│   ├── news.py                ← 实现
│   └── stockstats_utils.py    ← 内部
├── alpha_vantage/
│   └── ...
└── tools/                     ← 抽象层（路由 + @tool 定义）
    ├── interface.py           ← 路由核心：route_to_vendor, _VENDOR_REGISTRY
    ├── config.py              ← config.yaml 加载
    ├── tools_registry.yaml    ← 声明层：vendors 列表
    ├── core_stock_tools.py    ← @tool 定义 + docstring
    ├── technical_indicators_tools.py
    ├── fundamental_data_tools.py
    └── news_data_tools.py

tradingagents/
├── config.yaml                ← 决策层：决定用哪个 vendor
├── config/agents_registry.yaml ← 智能体-工具绑定
└── agents/utils/              ← 只保留智能体相关：agent_states, memory, agent_utils
```

## 职责划分

| 层级 | 文件 | 职责 |
|------|------|------|
| 实现层 | `datasource/{vendor}/*.py` | 各 vendor 的 API 实现（分散在多个文件） |
| 接口层 | `datasource/{vendor}/__init__.py` | 统一对外导出（门面），供 interface.py 扫描注册 |
| 抽象层 | `datasource/tools/interface.py` | 路由逻辑：route_to_vendor, _VENDOR_REGISTRY |
| 声明层 | `datasource/tools/tools_registry.yaml` | 定义工具支持哪些 vendors |
| 决策层 | `tradingagents/config.yaml` | 决定实际用哪个 vendor |
| 工具层 | `datasource/tools/*_tools.py` | @tool 定义 + docstring description |
| 智能体层 | `tradingagents/config/agents_registry.yaml` | 智能体权限控制 |

## LangChain 加载流程

```
LangChain 启动
    ↓
interface.py: _discover_and_register_impl()
    ↓ load_tools_registry() → 读取 tools_registry.yaml（知道有哪些工具）
    ↓ import_module("datasource.tushare") → 加载 __init__.py
    ↓ getattr(module, "get_balance_sheet") → 获取函数（来自 data.py）
    ↓ register_vendor() → 注册到 _VENDOR_REGISTRY
    ↓
agent_utils.load_agent_tools(agent_name)
    ↓ 读取 agents_registry.yaml → 知道要哪些 tools
    ↓ import datasource/tools/*_tools.py → @tool 注册，docstring 作为 description
    ↓ *_tools.py 内部调用 route_to_vendor() → 路由到具体 vendor 实现
    ↓ bind_tools() 发给 LLM
```

## 路由流程详解

```
route_to_vendor("get_balance_sheet", ticker, freq, curr_date)
    ↓ interface.py: get_category_for_method() → "fundamental_data"
    ↓ interface.py: get_vendor("fundamental_data") → "tushare"（来自 config.yaml）
    ↓ interface.py: _VENDOR_REGISTRY["get_balance_sheet"]["tushare"]
    ↓ interface.py: import_module("datasource.tushare")
    ↓ datasource/tushare/__init__.py: getattr(module, "get_balance_sheet")
    ↓ datasource/tushare/data.py: get_balance_sheet() 实际执行
```

## Vendor 机制

Vendor = 数据源提供商。每个 vendor 实现同名函数，但调用不同 API：

| Vendor | 说明 | 适用市场 |
|--------|------|----------|
| tushare | 中国 A 股数据 API | A 股（如 688333.SH） |
| yfinance | Yahoo Finance 免费 API | 美股、港股 |
| alpha_vantage | Alpha Vantage API | 美股 |

**切换数据源**只需改 `config.yaml`：

```yaml
data_vendors:
  fundamental_data: "tushare"  # 切换为 "yfinance" 即换源
```

## 文件移动清单

| 原位置 | 新位置 |
|--------|--------|
| `tradingagents/dataflows/interface.py` | `datasource/tools/interface.py` |
| `tradingagents/dataflows/config.py` | `datasource/tools/config.py` |
| `tradingagents/config/tools_registry.yaml` | `datasource/tools/tools_registry.yaml` |
| `tradingagents/agents/utils/core_stock_tools.py` | `datasource/tools/core_stock_tools.py` |
| `tradingagents/agents/utils/technical_indicators_tools.py` | `datasource/tools/technical_indicators_tools.py` |
| `tradingagents/agents/utils/fundamental_data_tools.py` | `datasource/tools/fundamental_data_tools.py` |
| `tradingagents/agents/utils/news_data_tools.py` | `datasource/tools/news_data_tools.py` |

## 相关文档

- [docs/dataflow-architecture.md](dataflow-architecture.md) - 数据流架构（三层设计）
- [docs/agent-tools-configuration.md](agent-tools-configuration.md) - 智能体工具绑定

---

*创建日期：2026-04-16*