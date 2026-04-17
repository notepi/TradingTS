# 架构重构：七层 → 三层

## Context

当前七层架构过于复杂：
- interface.py 跨三层，依赖方向混乱
- 配置文件分散
- tools 目录下文件职责混杂

用户需求：三层架构，数仓层内部两层分文件夹，依赖向下原则

---

## 三层架构设计

**核心原则**：servers/ 层是服务抽象层，提供稳定接口，智能体只调用它。底层变化（tools/、数据源）智能体无感知。

```
┌─────────────────────────────────────────────────────────────────┐
│ 3. 智能体层 - tradingagents/                                     │
│    职责：智能体实现 + LLM配置 + agents工具绑定                     │
│    文件：                                                        │
│      - config.yaml              ← LLM配置 + agents绑定（合并）    │
│      - agents/                  ← 智能体实现                      │
│    下对接：只调用 servers/ 的服务接口（稳定API）                    │
│    特点：底层变化无感知                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 调用稳定的服务接口
                              │

┌─────────────────────────────────────────────────────────────────┐
│ 2. 数仓层 - datasource/datahub/                                  │
│                                                                  │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ 2a. servers/ - 服务层（服务抽象层）                        │  │
│    │                                                          │  │
│    │     ├─ interface.py                                      │  │
│    │     │   内容：                                            │  │
│    │     │     - @tool 定义（传给 LLM）                        │  │
│    │     │     - 服务接口（业务逻辑、数据转换、缓存）            │  │
│    │     │     - get_config() + 配置缓存                       │  │
│    │     │   职责：                                            │  │
│    │     │     - 提供稳定的服务接口给智能体                      │  │
│    │     │     - 抽象业务逻辑，屏蔽底层变化                      │  │
│    │     │   上对接：被智能体调用                               │  │
│    │     │   下对接：调用 tools/ 获取数据                       │  │
│    │     │                                                    │  │
│    │     ├─ tools_registry.yaml                                │  │
│    │     │   内容：data_vendors + vendors 列表                 │  │
│    │     │   职责：注册表（衔接文件）                            │  │
│    │     │   定义：有哪些工具 + 支持哪些数据源                   │  │
│    │     │   被：interface.py 读取                             │  │
│    │     │                                                    │  │
│    │     └───────────────────────────────────────────────────  │  │
│    │                            ↓ 调用工具获取数据               │  │
│    │                            │                              │  │
│    │     ┌─────────────────────────────────────────────────┐  │  │
│    │     │ 2b. tools/ - 工具层（具体实现）                     │  │
│    │     │                                                    │  │
│    │     │     ├─ core_stock_tools.py                         │  │
│    │     │     ├─ technical_indicators_tools.py               │  │
│    │     │     ├─ fundamental_data_tools.py                   │  │
│    │     │     └─ news_data_tools.py                          │  │
│    │     │                                                    │  │
│    │     │     内容：纯函数，调用 vendor API                    │  │
│    │     │     职责：                                          │  │
│    │     │       - 实际获取数据（调用数据源API）                │  │
│    │     │       - 无 @tool 装饰器（由 servers 层定义）         │  │
│    │     │     上对接：被 servers/interface.py 调用             │  │
│    │     │     下对接：调用 datasource/{vendor}/              │  │
│    │     │                                                    │  │
│    │     └───────────────────────────────────────────────────  │  │
│    │                            ↓ 调用数据源                   │  │
│    │                            │                              │  │
│    └─────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. 数据源层 - datasource/{vendor}/                              │
│    职责：API实现 + 导出                                           │
│    文件：                                                        │
│      - data.py, stock.py        ← API实现                        │
│      - __init__.py              ← 导出门面 + 别名统一              │
│    产出：带字段说明的数据（LLM可读）                               │
│    上对接：被 tools/ 调用                                         │
└─────────────────────────────────────────────────────────────────┘
```

**依赖链（对接关系）**：
```
智能体层（只调用稳定的服务接口）
    ↓
servers/interface.py（服务层：@tool + 业务逻辑 + 数据转换）
    ↓
tools/*_tools.py（工具层：纯函数，调用 vendor API）
    ↓
数据源层
```

**servers/ 层的价值**：
- 提供稳定的服务接口给智能体
- 底层 tools/ 或数据源变动，智能体无感知
- 可以做业务逻辑（数据转换、缓存、错误处理）

**servers/ 层文件职责**：

| 文件 | 职责 | 上对接 | 下对接 |
|------|------|--------|--------|
| interface.py | @tool定义 + 服务接口 + 业务逻辑 | 被智能体调用 | 调用 tools/ |
| tools_registry.yaml | 注册表（有哪些工具+数据源） | 无 | 被 interface.py 读取 |

**tools/ 层文件职责**：

| 文件 | 职责 | 上对接 | 下对接 |
|------|------|--------|--------|
| *_tools.py（4个） | 纯函数，实际获取数据 | 被 servers 调用 | 调用数据源层 |

---

## 目录结构

**重构后**：
```
datasource/datahub/
├── servers/                      ← 服务层（服务抽象层）
│   ├── interface.py              ← @tool 定义 + 服务接口 + get_config()
│   ├── tools_registry.yaml       ← 注册表
│   └── __init__.py               ← 导出所有 @tool
└── tools/                        ← 工具层（具体实现）
    ├── core_stock_tools.py       ← 纯函数，调用 vendor API
    ├── technical_indicators_tools.py
    ├── fundamental_data_tools.py
    ├── news_data_tools.py
    └── __init__.py               ← 导出所有函数
```

**代码示例**：

servers/interface.py（服务层）：
```python
@auto_tool()
def get_balance_sheet_service(ticker, freq, curr_date):
    """资产负债表服务接口（传给 LLM）"""
    # 业务逻辑：决定用哪个 vendor
    vendor = get_vendor("fundamental_data")
    # 调用工具层获取数据
    data = tools.get_balance_sheet_impl(ticker, freq, curr_date, vendor)
    # 业务逻辑：数据转换、添加说明
    return format_balance_sheet(data)
```

tools/fundamental_data_tools.py（工具层）：
```python
def get_balance_sheet_impl(ticker, freq, curr_date, vendor):
    """纯函数，获取数据（无 @tool 装饰器）"""
    if vendor == "tushare":
        return datasource.tushare.get_balance_sheet(ticker, freq, curr_date)
    elif vendor == "yfinance":
        return datasource.yfinance.get_balance_sheet(ticker, freq, curr_date)
```

**关键区别**：
- servers/interface.py：有 @tool 装饰器（传给 LLM）
- tools/*_tools.py：无 @tool 装饰器（纯函数实现）

---

## 文件改动清单

### 目录重命名和移动
| 原位置 | 新位置 |
|--------|--------|
| datasource/tools/ | datasource/datahub/ |
| datasource/tools/*_tools.py（4个） | datasource/datahub/tools/ |
| datasource/tools/interface.py | datasource/datahub/servers/ |
| datasource/tools/tools_registry.yaml | datasource/datahub/servers/ |

### 合并文件
| 原文件 | 合并到 |
|--------|--------|
| datasource/tools/config.py | datasource/datahub/servers/interface.py |
| tradingagents/config/agents_registry.yaml | tradingagents/config.yaml（agents部分） |

### 删除文件
| 文件 | 原因 |
|------|------|
| datasource/tools/config.py | 合并入 interface.py |

### 代码重构
| 文件 | 改动 |
|------|------|
| servers/interface.py | 移入 @tool 定义，添加服务接口逻辑 |
| tools/*_tools.py | 移除 @tool 装饰器，改为纯函数（*_impl） |

### 新增文件
| 文件 | 内容 |
|------|------|
| datasource/datahub/tools/__init__.py | 导出所有 *_impl 函数 |
| datasource/datahub/servers/__init__.py | 导出所有 @tool |

### 删除冗余
| 文件 | 删除内容 |
|------|----------|
| tools_registry.yaml | description 字段 |
| agent_utils.py | build_tools_usage 函数 |

### 更新导入路径
| 文件 | 改动 |
|------|------|
| tradingagents/agents/utils/agent_utils.py | `from datasource.datahub.servers import get_config, get_balance_sheet_service` |
| tradingagents/graph/*.py | 更新导入路径 |

### 改进数据实现
| 文件 | 改动 |
|------|------|
| datasource/tushare/data.py | get_balance_sheet 返回带字段说明的数据 |

---

## 配置文件最终结构

**tradingagents/config.yaml**：
```yaml
# LLM 配置
llm_provider: "dashscope"
deep_think_llm: "glm-5"
quick_think_llm: "glm-5"
backend_url: "https://coding.dashscope.aliyuncs.com/v1"

# 输出配置
output:
  language: "Chinese"
  log_level: "INFO"

# 智能体工具绑定（合并 agents_registry.yaml）
agents:
  fundamentals_analyst:
    tools: [get_fundamentals, get_balance_sheet, get_cashflow, get_income_statement, get_peg_ratio, get_yoy_growth]
  market_analyst:
    tools: [get_stock_data, get_indicators]
  social_analyst:
    tools: [get_news]
  news_analyst:
    tools: [get_news, get_global_news, get_insider_transactions]
```

**datasource/datahub/servers/tools_registry.yaml**：
```yaml
# 数据源决策
data_vendors:
  core_stock_apis: "tushare"
  technical_indicators: "tushare"
  fundamental_data: "tushare"
  news_data: "yfinance"

tool_vendors: {}

vendor_paths:
  tushare: "datasource.tushare"
  yfinance: "datasource.yfinance"
  alpha_vantage: "datasource.alpha_vantage"

# 工具注册表（只保留 category + vendors）
tools:
  get_stock_data:
    category: core_stock_apis
    vendors: [tushare, yfinance, alpha_vantage]
  get_indicators:
    category: technical_indicators
    vendors: [tushare, yfinance, alpha_vantage]
  get_balance_sheet:
    category: fundamental_data
    vendors: [tushare, yfinance, alpha_vantage]
  # ...（无 description）
```

---

## 实施步骤

1. **创建新目录结构**
   - 创建 datasource/datahub/servers/
   - 创建 datasource/datahub/tools/

2. **移动文件到新目录**
   - interface.py, tools_registry.yaml → servers/
   - *_tools.py → tools/

3. **合并 config.py 到 interface.py**
   - config.py 的 get_config() + 配置缓存逻辑移入 interface.py
   - 删除 config.py

4. **重构 @tool 定义**
   - 从 tools/*_tools.py 移除 @auto_tool 装饰器
   - 函数名改为 *_impl（如 get_balance_sheet_impl）
   - 在 servers/interface.py 定义 @tool 服务接口

5. **创建 __init__.py 导出文件**
   - servers/__init__.py 导出所有 @tool
   - tools/__init__.py 导出所有 *_impl 函数

6. **合并 agents_registry.yaml 入 config.yaml**

7. **删除冗余**
   - tools_registry.yaml 删除 description 字段
   - agent_utils.py 删除 build_tools_usage 函数

8. **更新导入路径**

9. **更新文档**

10. **改进数据实现**

---

## 遗留问题（下阶段重点讨论）

**tools/ 层的实际职责**：

当前架构保留 tools/ 文件夹，但具体职责尚未确定。下阶段需要讨论：

| 方案 | 职责 | 价值 |
|------|------|------|
| 数据预处理 | 添加字段说明、计算比率 | 解决 LLM 误读数据问题 |
| 数据缓存 | 缓存管理，避免重复请求 | 性能优化 |
| Vendor 封装 | 封装不同 vendor 差异 | 解耦 servers 与 vendor |

**当前决策**：
- 保留 tools/ 文件夹结构
- 暂时实现为简单转发层
- 下阶段根据实际需求确定具体职责

---

## 验证方式

1. 运行 `tradingagents test 688333.SH --date 2026-04-17`
2. 检查路由机制仍正常工作