# 数仓层架构实施文档

> 本文档描述两层架构的文件改动清单、实施步骤。
>
> **相关文档**：
> - [datahub-design.md](datahub-design.md) - 架构设计详情
> - [datahub-architecture-review.md](datahub-architecture-review.md) - 架构演进过程、评审决策

---

## 一、架构概览

### 1.1 两层架构

```
┌─────────────────────────────────────────────────────────────────┐
│ 3. 智能体层 - tradingagents/                                     │
│    职责：智能体实现 + LLM配置 + 工具绑定                          │
│    文件：                                                        │
│      - config.yaml              ← LLM配置                        │
│      - agents_registry.yaml     ← 工具绑定                       │
│      - agents/                  ← 智能体实现                      │
│    下对接：只调用 servers/ 的 @tool 接口                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 调用 @tool

┌─────────────────────────────────────────────────────────────────┐
│ 2. 数仓层 - datasource/datahub/servers/                         │
│    职责：                                                        │
│      - @tool 定义        → 给 LangGraph 用                       │
│      - vendor 路由       → 读配置，决定用哪个数据源               │
│      - 直接调用数据源    → datasource/{vendor}/                  │
│    文件：                                                        │
│      - interface.py            ← 路由机制 + 自动注册              │
│      - fundamental.py          ← 基本面 @tool                    │
│      - market.py               ← 市场 @tool                      │
│      - news.py                 ← 新闻 @tool                      │
│      - indicator.py            ← 技术指标 @tool                  │
│      - registry.yaml           ← vendor 路由配置                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 直接调用

┌─────────────────────────────────────────────────────────────────┐
│ 1. 数据源层 - datasource/{vendor}/                              │
│    职责：                                                        │
│      - API 实现          → 调用外部数据 API                      │
│      - 字段说明          → 返回值内联字段说明                     │
│      - 函数签名定义      → 数据源层是基准                         │
│    文件：                                                        │
│      - data.py           ← 入口文件，自动收集导出                 │
│      - fundamental.py    ← 基本面函数实现                        │
│      - market.py         ← 市场函数实现                          │
│      - news.py           ← 新闻函数实现                          │
│      - indicator.py      ← 指标函数实现                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构

### 2.1 目标目录结构

```
datasource/
├── datahub/
│   └── servers/                  ← 数仓层
│       ├── interface.py          ← 路由机制 + 自动注册
│       ├── fundamental.py        ← 基本面 @tool
│       ├── market.py             ← 市场 @tool
│       ├── news.py               ← 新闻 @tool
│       ├── indicator.py          ← 技术指标 @tool
│       ├── registry.yaml         ← vendor 路由配置
│       └── __init__.py           ← 导出所有 @tool
│
├── tushare/                      ← 数据源层
│   ├── data.py                   ← 入口文件，自动收集导出
│   ├── fundamental.py            ← 基本面函数实现
│   ├── market.py                 ← 市场函数实现
│   ├── news.py                   ← 新闻函数实现
│   ├── indicator.py              ← 指标函数实现
│   ├── api.py                    ← API 客户端
│   └── __init__.py               ← 导出
│
├── yfinance/                     ← 数据源层
│   ├── data.py                   ← 入口文件
│   ├── fundamental.py            ← 基本面函数实现
│   ├── market.py                 ← 市场函数实现
│   └── __init__.py               ← 导出
│
└── alpha_vantage/                ← 数据源层（可选）
```

---

## 三、文件改动清单

### 3.1 目录重命名和移动

| 原位置 | 新位置 | 说明 |
|--------|--------|------|
| datasource/tools/ | datasource/datahub/ | 重命名 |
| datasource/tools/interface.py | datasource/datahub/servers/interface.py | 移动 |
| datasource/tools/tools_registry.yaml | datasource/datahub/servers/registry.yaml | 移动并简化 |
| datasource/tools/*_tools.py | 删除 | 不再需要 |

### 3.2 新增文件

| 文件 | 内容 |
|------|------|
| datasource/datahub/servers/fundamental.py | 基本面 @tool 定义 |
| datasource/datahub/servers/market.py | 市场 @tool 定义 |
| datasource/datahub/servers/news.py | 新闻 @tool 定义 |
| datasource/datahub/servers/indicator.py | 技术指标 @tool 定义 |
| datasource/datahub/servers/__init__.py | 导出所有 @tool |
| datasource/tushare/fundamental.py | 基本面函数实现（拆分） |
| datasource/tushare/market.py | 市场函数实现（拆分） |
| datasource/tushare/news.py | 新闻函数实现（拆分） |
| datasource/tushare/indicator.py | 指标函数实现（拆分） |

### 3.3 删除文件

| 文件 | 原因 |
|------|------|
| datasource/tools/*_tools.py（4个） | 不再需要中间层 |
| datasource/tools/config.py | 合并入 interface.py |

### 3.4 修改文件

| 文件 | 改动 |
|------|------|
| datasource/tushare/data.py | 改为入口文件，自动收集导出 |
| datasource/tushare/data.py | 添加 @export 装饰器 |
| datasource/tushare/data.py | 函数返回值添加字段说明 |
| datasource/datahub/servers/interface.py | 实现自动扫描注册机制 |
| datasource/datahub/servers/registry.yaml | 简化为 default_vendor + tool_vendors |
| tradingagents/agents/utils/agent_utils.py | 更新导入路径 |

---

## 四、配置文件结构

### 4.1 registry.yaml（简化版）

```yaml
# 默认数据源（全部工具用这个）
default_vendor: tushare

# 特殊情况单独指定（可选）
tool_vendors:
  get_stock_data: yfinance
  get_balance_sheet_us: yfinance
```

**删除内容**：
- vendor_paths（自动扫描）
- data_vendors（改为 default_vendor）
- tools 列表（自动发现）

### 4.2 agents_registry.yaml（不变）

```yaml
agents:
  fundamentals_analyst:
    tools: [get_fundamentals, get_balance_sheet, get_cashflow, ...]
  market_analyst:
    tools: [get_stock_data, get_indicators]
  news_analyst:
    tools: [get_news, get_global_news]
```

---

## 五、代码示例

### 5.1 servers/fundamental.py

```python
from langchain_core.tools import tool
from .interface import route_to_vendor

@tool
def get_balance_sheet(ticker: str, freq: str = "quarterly"):
    """获取资产负债表数据"""
    return route_to_vendor("get_balance_sheet", ticker, freq=freq)

@tool
def get_income_statement(ticker: str, freq: str = "quarterly"):
    """获取利润表数据"""
    return route_to_vendor("get_income_statement", ticker, freq=freq)
```

### 5.2 servers/interface.py

```python
import yaml
from typing import Callable

_REGISTRY: dict[str, dict[str, Callable]] = {}
TOOL_REGISTRY: dict[str, Callable] = {}

def load_registry():
    """加载 registry.yaml"""
    with open("registry.yaml") as f:
        return yaml.safe_load(f)

def route_to_vendor(tool_name: str, *args, **kwargs):
    """路由到 vendor 函数"""
    registry = load_registry()
    
    # 检查 tool_vendors
    vendor = registry.get("tool_vendors", {}).get(tool_name)
    if not vendor:
        vendor = registry.get("default_vendor", "tushare")
    
    # 从注册表获取函数
    func = _REGISTRY.get(tool_name, {}).get(vendor)
    if not func:
        raise ValueError(f"Function {tool_name} not found for vendor {vendor}")
    
    return func(*args, **kwargs)

def discover_and_register():
    """自动扫描并注册"""
    # 扫描 datasource/{vendor}/
    # 注册 @export 函数到 _REGISTRY
    # 扫描 servers/*.py
    # 注册 @tool 函数到 TOOL_REGISTRY
    pass
```

### 5.3 datasource/tushare/fundamental.py

```python
from .export import export

@export
def get_balance_sheet(ticker: str, freq: str = "quarterly"):
    """获取资产负债表"""
    # 调用 API
    df = api.get_balance_sheet(ticker, freq)
    
    # 返回值含字段说明
    header = "# Balance Sheet data\n"
    header += "# 字段说明：\n"
    header += "# - accounts_receivable: 应收账款\n"
    header += "# - notes_receivable: 应收票据\n"
    
    return header + df.to_csv(index=False)
```

### 5.4 datasource/tushare/data.py

```python
from .fundamental import *
from .market import *
from .news import *
from .indicator import *
from .export import collect_exported_functions

__all__ = collect_exported_functions()
```

---

## 六、实施步骤

### Step 1: 创建新目录结构

```bash
mkdir -p datasource/datahub/servers
```

### Step 2: 移动文件

```bash
mv datasource/tools/interface.py datasource/datahub/servers/
mv datasource/tools/tools_registry.yaml datasource/datahub/servers/registry.yaml
```

### Step 3: 创建 servers 主题域文件

创建 fundamental.py, market.py, news.py, indicator.py

### Step 4: 重构数据源层

- 拆分 datasource/tushare/data.py 为多个模块
- 添加 @export 装饰器
- 添加字段说明到返回值

### Step 5: 实现自动注册机制

修改 interface.py，实现 discover_and_register()

### Step 6: 简化 registry.yaml

删除 vendor_paths、data_vendors、tools 列表

### Step 7: 删除旧文件

```bash
rm datasource/tools/*_tools.py
rm datasource/tools/config.py
```

### Step 8: 更新导入路径

更新 tradingagents/agents/utils/agent_utils.py 等文件

### Step 9: 测试验证

```bash
tradingagents test 688333.SH --date 2026-04-17
```

---

## 七、验证清单

| 验证项 | 方法 |
|--------|------|
| vendor 路由 | 测试 default_vendor 和 tool_vendors 生效 |
| @export 注册 | 新函数自动出现在 __all__ |
| 字段说明 | 检查返回值含字段说明 |
| 找不到报错 | 测试不存在函数报错 |
| 智能体调用 | 运行完整流程 |

---

## 八、风险和注意事项

| 风险 | 说明 | 建议 |
|------|------|------|
| 导入路径更新 | 多处文件引用旧路径 | 全面搜索替换 |
| 函数签名不一致 | 历史遗留函数 | 用别名适配 |
| 字段说明缺失 | 部分函数未添加 | 逐步补充 |

---

*文档版本：2026-04-17*