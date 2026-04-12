# 智能体工具绑定配置化

## 概述

本系统实现了智能体工具的配置化管理。加工具只需改配置文件，无需改动 analyst 代码。

## 架构

```
数据层                    注册层                    Agent层
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│ @auto_tool  │ --> │ tools_registry  │ --> │ agents_registry  │ --> Agent Prompt
│ 数据函数    │     │ .yaml           │     │ .yaml            │     (自动追加)
└─────────────┘     └─────────────────┘     ┌──────────────────┘
                                            │ build_tools_usage │
                                            └──────────────────┘
```

## 加工具流程

### 通用工具

只需改配置，无需改代码：

| 步骤 | 文件 | 操作 |
|------|------|------|
| 1 | `datasource/{vendor}/xxx.py` | 写数据函数 + `@auto_tool` |
| 2 | `tradingagents/config/tools_registry.yaml` | 注册工具名和描述 |
| 3 | `tradingagents/config/agents_registry.yaml` | 添加到智能体工具列表 |

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
│   ├── tools_registry.yaml      # 工具定义
│   └── agents_registry.yaml     # 智能体工具绑定
├── dataflows/
│   └── decorators.py            # @auto_tool 装饰器
├── agents/
│   ├── utils/
│   │   └── agent_utils.py       # load_agent_tools(), build_tools_usage()
│   └── analysts/
│       └── fundamentals_analyst.py  # prompt 自动追加
└── ...
```