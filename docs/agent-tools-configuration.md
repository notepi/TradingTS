# 智能体工具绑定配置化

## 概述

本系统实现了智能体工具的全流程配置化管理。加工具只需改配置文件，无需改动任何核心代码。

## 工具调用完整流程（7 步，全自动化）

| 环节 | 文件 | 自动/手动 | 说明 |
|------|------|----------|------|
| 1. 装饰器注册 | `@auto_tool` | 自动 | 注册到 TOOL_REGISTRY |
| 2. 工具定义 | `tools_registry.yaml` | 手动 | 定义 category + vendors |
| 3. 智能体绑定 | `agents_registry.yaml` | 手动 | 定义 agent 可用工具 |
| 4. 数据源发现 | `discover_and_register()` | 自动 | 启动时动态注册 |
| 5. 加载工具列表 | `load_agent_tools()` | 自动 | 从配置读取 |
| 6. Analyst 绑定 | `llm.bind_tools(tools)` | 自动 | 发送 schema 给 LLM |
| 7. ToolNode 注册 | `trading_graph.py` | 自动 | 用配置创建 ToolNode |

**结果：加工具只改步骤 1-3，其余自动生效。**

## 架构图

```
数据层                    注册层                    Agent层
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ @auto_tool  │ --> │ tools_registry  │ --> │ agents_registry  │ --> Agent Prompt
│ 数据函数    │     │ .yaml           │     │ .yaml            │     (自动追加)
└─────────────┘     └─────────────────┘     ┌──────────────────┐
                                            │ build_tools_usage │
                                            └──────────────────┘
                                                    ↓
                                            ┌──────────────────┐
                                            │ ToolNode         │  ← 也用配置加载
                                            │ load_agent_tools │
                                            └──────────────────┘
```

## 加工具流程

### 标准流程（3 步，不改代码）

| 步骤 | 文件 | 操作 |
|------|------|------|
| 1 | `datasource/{vendor}/xxx.py` | 写数据函数 + `@auto_tool` |
| 2 | `tradingagents/config/tools_registry.yaml` | 注册工具名、category、vendors |
| 3 | `tradingagents/config/agents_registry.yaml` | 添加到智能体工具列表 |

**ToolNode 自动生效，无需改 trading_graph.py。**

### 专业工具（需要 prompt 说明）

额外加 `usage` 字段：

```yaml
# agents_registry.yaml
agents:
  fundamentals_analyst:
    tools:
      - name: get_new_metric
        usage: "Use for XYZ analysis. Check ABC conditions."
```

`usage` 会自动追加到智能体的 prompt。

## 配置文件说明

### tools_registry.yaml

定义工具及其所属分类：

```yaml
tools:
  get_peg_ratio:
    category: fundamental_data
    description: "PEG Ratio = PE(TTM) / 净利润增长率"
    vendors: [tushare]
```

### agents_registry.yaml

定义智能体可用的工具列表：

```yaml
agents:
  fundamentals_analyst:
    tools:
      - name: get_fundamentals       # 无 usage，依赖 description
      - name: get_peg_ratio
        usage: "Use for PEG valuation. PEG < 1 = undervalued"  # 自动追加到 prompt
```

## Prompt 处理机制

| 工具类型 | 处理方式 |
|---------|---------|
| 无 usage | 依赖 `bind_tools` 发送的 description |
| 有 usage | 自动追加到 prompt（`build_tools_usage()`） |

**生成示例：**

```python
build_tools_usage("fundamentals_analyst")
# 输出：
#
# Tool usage guide:
# - `get_peg_ratio`: Use for Peter Lynch PEG valuation analysis.
# - `get_yoy_growth`: Use for year-over-year growth rate analysis.
```

## 装饰器使用

```python
from tradingagents.dataflows.decorators import auto_tool

@auto_tool(description="PEG Ratio 分析 - Lynch 核心指标")
def get_peg_ratio(ticker: str, curr_date: str = None):
    """函数实现"""
    ...
```

装饰器效果：
- 创建 LangChain tool wrapper
- 注册到 `TOOL_REGISTRY`
- 原函数仍可被 dataflows 路由调用

## 示例：添加新 Lynch 指标

### 1. 写数据函数

```python
# datasource/tushare/indicators/lynch.py
from tradingagents.dataflows.decorators import auto_tool

@auto_tool(description="Lynch 分类 - 判断公司类型")
def get_lynch_category(ticker: str, curr_date: str = None):
    """Peter Lynch 公司分类分析"""
    # 实现逻辑
    ...
```

### 2. 注册到 tools_registry.yaml

```yaml
# config/tools_registry.yaml
tools:
  get_lynch_category:
    category: fundamental_data
    description: "Lynch 公司分类（Slow Grower/Stalwart/Fast Grower）"
    vendors: [tushare]
```

### 3. 添加到智能体配置

```yaml
# config/agents_registry.yaml
agents:
  fundamentals_analyst:
    tools:
      - name: get_lynch_category
        usage: "Use to classify company type per Lynch methodology."
```

**完成！无需改任何 analyst 代码。**

## 验证

```bash
# 测试工具加载
uv run python -c "
from tradingagents.agents.utils.agent_utils import load_agent_tools, build_tools_usage
print('Tools:', [t.name for t in load_agent_tools('fundamentals_analyst')])
print(build_tools_usage('fundamentals_analyst'))
"
```

## 文件结构

```
tradingagents/
├── config/
│   ├── config.yaml              # vendor_paths + data_vendors
│   ├── tools_registry.yaml      # 工具定义（category + vendors）
│   └── agents_registry.yaml     # 智能体工具绑定
├── dataflows/
│   ├── decorators.py            # @auto_tool 装饰器 + TOOL_REGISTRY
│   ├── interface.py             # discover_and_register() + route_to_vendor()
│   └── yfinance_news.py         # yfinance 新闻实现
├── agents/
│   ├── utils/
│   │   └── agent_utils.py       # load_agent_tools(), build_tools_usage()
│   └── analysts/
│       └── fundamentals_analyst.py  # prompt 自动追加 usage
│       └── market_analyst.py
│       └── news_analyst.py
│       └── social_analyst.py
└── graph/
    └── trading_graph.py         # ToolNode(load_agent_tools(...))
```

## 数据源切换

切换数据源（如从 tushare 到 akshare）只需：

| 步骤 | 文件 | 操作 |
|------|------|------|
| 1 | `datasource/akshare/` | 创建目录 + 实现同名函数 |
| 2 | `tools_registry.yaml` | vendors 添加 `akshare` |
| 3 | `config.yaml` | vendor_paths + data_vendors 配置 |

详见 [docs/dataflow-architecture.md](docs/dataflow-architecture.md)。