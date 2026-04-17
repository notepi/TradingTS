# 数仓层架构设计文档

> 本文档详述数仓层的设计思路、架构方案、边界划分。
>
> **相关文档**：
> - [datahub-architecture-review.md](datahub-architecture-review.md) - 架构演进过程、评审决策
> - [datahub-architecture.md](datahub-architecture.md) - 文件改动清单、实施步骤

---

## 一、当前架构问题

### 1.1 现有机制分析

当前数据调用存在**三层注册机制**，导致复杂度高：

| 注册机制 | 位置 | 职责 |
|----------|------|------|
| TOOL_REGISTRY | decorators.py | LangChain tool wrapper，给 LangGraph 用 |
| _VENDOR_REGISTRY | interface.py | vendor 具体实现函数 |
| TOOL_MODULES | agent_utils.py | 工具名到模块路径的硬编码映射 |

**问题**：
1. 三层注册职责重叠，维护成本高
2. TOOL_MODULES 硬编码，加工具需同步修改多处
3. 初始化依赖复杂，必须按正确顺序调用
4. servers 和 tools 边界模糊，职责不清

### 1.2 数据调用流程（现状）

```
智能体（LangGraph ToolNode）
    ↓ 从 TOOL_REGISTRY 获取 tool wrapper
@tool 装饰的函数（如 get_stock_data）
    ↓ 调用 route_to_vendor
interface.py：从 _VENDOR_REGISTRY 找 vendor 函数
    ↓
datasource/{vendor}/data.py：实际 API 调用
    ↓
返回数据（含字段说明） → 智能体
```

---

## 二、设计目标

### 2.1 核心诉求

1. **扩展简单**：加新函数改动最小（三层各改一处）
2. **对上抽象**：智能体只面向数仓，切换数据源不影响
3. **边界清晰**：servers/datasource 职责分明
4. **LangGraph 兼容**：@tool 机制正常工作
5. **架构稳定**：逻辑清晰，易于理解

### 2.2 设计原则

| 原则 | 说明 |
|------|------|
| **依赖向下** | 智能体 → 数仓 → 数据源，低层不依赖高层 |
| **职责单一** | 每层只做一件事 |
| **对上稳定** | 数仓对智能体暴露稳定接口，底层变化无感知 |
| **配置驱动** | vendor 路由通过配置，不硬编码 |

---

## 三、整体架构

### 3.1 两层架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│ 第三层：智能体层 - tradingagents/                                │
│                                                                  │
│  角色：LLM 智能体（市场分析师、基本面分析师、新闻分析师等）         │
│  职责：                                                          │
│    ├─ 接收用户任务（分析某只股票）                                │
│    ├─ 决策调用哪些工具                                           │
│    ├─ 解读数据，生成分析报告                                      │
│    └─ 不关心数据从哪来，只关心数据内容                            │
│                                                                  │
│  组件：                                                          │
│    ├─ agents/analysts/*.py    → 智能体实现                       │
│    ├─ agents/managers/*.py    → 管理层智能体                     │
│    ├─ graph/trading_graph.py  → LangGraph 执行流程               │
│    └─ agents_registry.yaml    → 工具绑定配置                      │
│                                                                  │
│  调用方式：                                                      │
│    LangGraph ToolNode → 从 TOOL_REGISTRY 获取 @tool → 发起调用   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 调用 @tool（函数名 + 参数）
                              │ 返回数据（含字段说明）
                              ↓

┌─────────────────────────────────────────────────────────────────┐
│ 第二层：数仓层 - datasource/datahub/servers/                     │
│                                                                  │
│  角色：数据服务的唯一入口                                         │
│  职责：                                                          │
│    ├─ 对上：暴露稳定的 @tool 接口给智能体                         │
│    ├─ 路由：读配置，决定用哪个 vendor                             │
│    ├─ 对下：直接调用数据源层 API                                  │
│    └─ 智能体不知道底层怎么实现                                    │
│                                                                  │
│  组件：                                                          │
│    ├─ interface.py            → 路由机制 + 自动注册              │
│    ├─ fundamental.py          → 基本面主题域 @tool               │
│    ├─ market.py               → 市场主题域 @tool                 │
│    ├─ news.py                 → 新闻主题域 @tool                 │
│    ├─ indicator.py            → 技术指标主题域 @tool             │
│    └─ registry.yaml           → vendor 路由配置                 │
│                                                                  │
│  输入：函数名 + 参数（如 get_balance_sheet("600519.SH")）        │
│  输出：数据源层返回的数据（含字段说明）                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 调用 vendor API（ticker, date 等）
                              │ 返回数据（含字段说明）
                              ↓

┌─────────────────────────────────────────────────────────────────┐
│ 第一层：数据源层 - datasource/{vendor}/                         │
│                                                                  │
│  角色：外部数据 API 的封装                                        │
│  职责：                                                          │
│    ├─ 调用外部 API（Tushare、YFinance、Alpha Vantage）           │
│    ├─ 返回数据 + 字段说明                                        │
│    ├─ 不关心智能体怎么用数据                                      │
│    ├─ 函数签名定义（数据源层是基准）                              │
│    └─ 纯实现，不依赖任何层                                        │
│                                                                  │
│  组件：                                                          │
│    ├─ datasource/tushare/     → A股数据（Tushare API）          │
│    ├─ datasource/yfinance/    → 美股数据（Yahoo Finance）       │
│    └─ datasource/alpha_vantage/ → Alpha Vantage                 │
│                                                                  │
│  目录结构：                                                      │
│    ├─ data.py           → 入口文件，自动收集导出                  │
│    ├─ fundamental.py    → 基本面函数实现                         │
│    ├─ market.py         → 市场函数实现                           │
│    ├─ news.py           → 新闻函数实现                           │
│    └─ indicator.py      → 指标函数实现                           │
│                                                                  │
│  输入：API 参数（ticker, start_date, end_date 等）               │
│  输出：数据 + 字段说明（字符串格式）                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 各层职责对比

| 层 | 面向谁 | 输入 | 输出 | 知道什么 | 不知道什么 |
|----|--------|------|------|----------|-----------|
| 智能体层 | 用户/业务 | 用户任务 | 分析报告 | 工具能做什么 | 数据从哪来 |
| 数仓层 | 智能体 | 函数名+参数 | 数据源层返回值 | vendor 路由 | API 实现细节 |
| 数据源层 | 外部 API | API 参数 | 数据+字段说明 | API 接口、数据格式 | 智能体怎么用 |

---

## 四、智能体调用工具设计

### 4.1 智能体如何知道工具做什么？

**位置**：@tool docstring（数仓层 servers/{domain}.py）

```python
# servers/fundamental.py
@tool
def get_balance_sheet(ticker: str, freq: str = "quarterly"):
    """获取资产负债表数据"""
    ...
```

**不在 tools_registry.yaml 里做**

### 4.2 返回数据智能体如何分析？

**位置**：函数返回值（数据源层 datasource/{vendor}/data.py）

数据源层返回时直接包含字段说明：

```python
# datasource/tushare/data.py
def get_balance_sheet(...):
    ...
    header = "# Balance Sheet data\n"
    header += "# 字段说明：\n"
    header += "# - accounts_receivable: 应收账款\n"
    header += "# - notes_receivable: 应收票据\n"
    return header + csv_string
```

### 4.3 分工原则

| 层 | 职责 | 内容 |
|---|------|------|
| 数仓层 | 工具用途描述 | @tool docstring（给智能体决策） |
| 数据源层 | 字段含义说明 | 返回值内联（给智能体解读数据） |

---

## 五、数据流设计

### 5.1 调用流程

```
智能体发起请求："我要资产负债表"
    ↓
LangGraph ToolNode 查找 @tool
    ↓
servers/fundamental.py:get_balance_sheet()
    ├─ 读 registry.yaml 获取 vendor 配置
    ├─ vendor = "tushare"（配置决定）
    ↓
datasource/tushare/data.py:get_balance_sheet()
    ├─ 调用 Tushare API
    ├─ 添加字段说明
    ↓
返回给智能体：数据 + 字段说明（字符串格式）
    ↓
LLM 解读数据
```

### 5.2 vendor 路由流程

```
@tool 函数被调用
    ↓
servers/interface.py:route_to_vendor(tool_name)
    ├─ 读 registry.yaml
    ├─ 检查：tool_vendors[tool_name] → 有就用指定的
    ├─ 无 → 用 default_vendor
    ↓
获取 vendor 函数（启动时自动注册）
    ↓
调用 vendor 函数
    ↓
返回数据（含字段说明）
```

---

## 六、边界划分

### 6.1 数仓层（servers）职责

| 职责 | 说明 | 为什么在这里 |
|------|------|-------------|
| @tool 定义 | 暴露给 LangGraph | 必须在这里，智能体只看到这层 |
| vendor 路由 | 读配置决定数据源 | 集中管理，避免分散 |
| 直接调用数据源 | 调用 datasource/{vendor} | 简化流程，减少中间层 |

### 6.2 数据源层职责

| 职责 | 说明 | 为什么在这里 |
|------|------|-------------|
| API 实现 | 调用外部数据 API | 纯实现，不关心业务 |
| 数据获取 | 返回数据 | 数据源层只负责获取 |
| 字段说明 | 返回值内联 | 让 LLM 能读懂数据 |
| 函数签名定义 | 定义标准签名 | 数据源层是基准 |
| 别名适配 | 历史遗留函数适配 | 避免改动数仓层 |

### 6.3 数据源层目录结构

```
datasource/{vendor}/
├── data.py           → 入口文件，自动收集导出
├── fundamental.py    → 基本面函数实现
├── market.py         → 市场函数实现
├── news.py           → 新闻函数实现
└── indicator.py      → 指标函数实现
```

**设计原则**：分离实现和导出

- 实现文件：各模块独立，不关心命名适配
- 入口文件（data.py）：统一管理导出 + 别名

### 6.4 @export 装饰器自动注册

```python
# datasource/tushare/fundamental.py
@export  # 标记要导出的函数
def get_balance_sheet(ticker: str, freq: str):
    ...

# datasource/tushare/data.py
# 自动收集所有模块的 @export 函数
__all__ = collect_exported_functions()
```

**好处**：
- 写函数：加一行 `@export`
- 不需要在 data.py 手动维护列表
- 历史遗留函数不加装饰器，不会被导出

### 6.5 别名适配（历史遗留函数）

```python
# datasource/tushare/fundamental.py

# 历史遗留函数（参数名不一致）
def get_bal_sheet_old(code: str, period: str):
    ...

# 别名适配数仓层（函数名统一）
get_balance_sheet = get_bal_sheet_old

# 或包装适配（参数需要转换）
def get_balance_sheet(ticker: str, freq: str):
    return get_bal_sheet_old(ticker, freq)
```

### 6.6 边界对比

| 维度 | servers 层 | 数据源层 |
|------|-----------|----------|
| 面向 | 智能体 | 外部 API |
| 知道 | 主题域语义 | API 参数、数据格式 |
| 不知道 | API 具体实现细节 | 智能体怎么用数据 |
| 输出 | 数据源层返回值 | 数据 + 字段说明 |

---

## 七、主题域设计

### 7.1 主题域划分

| 主题域 | 智能体视角 | 暴露的工具 |
|--------|-----------|-----------|
| fundamental | "我要基本面" | get_balance_sheet, get_income_statement, get_cashflow, get_fundamentals |
| market | "我要市场数据" | get_stock_data, get_realtime_quote |
| news | "我要新闻" | get_news, get_global_news |
| indicator | "我要技术指标" | get_indicators, get_macd, get_rsi |

### 7.2 主题域价值

1. **智能体视角**：智能体说"我要基本面"，不说"我要 tushare"
2. **聚合工具**：相关工具聚合在一起，易于理解
3. **独立演进**：每个主题域独立，互不影响

---

## 八、配置设计

### 8.1 registry.yaml 结构

```yaml
# 默认数据源（全部工具用这个）
default_vendor: tushare

# 特殊情况单独指定（可选）
tool_vendors:
  get_stock_data: yfinance
  get_balance_sheet_us: yfinance
```

**设计原则**：函数层完全不关心 vendor，配置层统一管理。

### 8.2 路由优先级

```
tool_vendors（函数级指定） > default_vendor
```

**路由逻辑**：
- 调用工具时，先查 `tool_vendors[tool_name]`
- 无则用 `default_vendor`
- 函数层不写 vendor 参数

---

## 九、注册机制

### 9.1 自动扫描注册

```
启动时：
    ├─ 扫描 datasource/{vendor}/，收集所有 @export 函数
    ├─ 注册到 _REGISTRY[tool_name][vendor] = function
    ├─ 扫描 servers/*.py，收集所有 @tool 函数
    ├─ 注册到 TOOL_REGISTRY（供 LangGraph 使用）
    ↓

注册表结构：
    ├─ _REGISTRY: {tool_name: {vendor: function}}
    ├─ TOOL_REGISTRY: {tool_name: @tool wrapper}
```

**好处**：
- 写函数加 @export，自动注册
- 不需要手动维护注册列表

---

## 十、如何扩展

### 10.1 加新函数的步骤（三层各改一处）

```
1. 数据源层：datasource/{vendor}/{domain}.py
   - 加 @export 装饰器的函数实现
   - 返回值含字段说明

2. 数仓层：servers/{domain}.py
   - 加 @tool 函数（不写 vendor）
   - docstring 描述工具用途

3. 智能体层：agents_registry.yaml
   - 绑定工具到智能体

特殊情况才改 registry.yaml（指定某个函数用其他 vendor）
```

### 10.2 函数签名约定

**必须一致，数据源层是基准**：
- 数据源层定义标准函数签名
- 数仓层适配数据源层签名
- 历史遗留函数：用别名或包装函数适配
- 找不到函数报错

### 10.3 加新数据源的步骤

```
1. 数据源层：创建 datasource/{new_vendor}/ 目录
2. 数据源层：实现同名函数（签名一致）
3. 配置：在 registry.yaml 改 default_vendor 或 tool_vendors
```

---

## 十一、设计决策记录

### D1: 为什么是两层架构？

**理由**：
1. 智能体 → 数仓 → 数据源，职责清晰
2. 数仓层统一管理 @tool + 路由
3. 数据源层专注 API 实现 + 字段说明

**影响**：
- 每层职责单一
- 加新函数改动最小（三层各一处）

### D2: 为什么 vendor 路由用 registry.yaml 统一管理？

**理由**：
1. 函数层不应关心数据源，只写业务逻辑
2. 配置层统一管理，一目了然
3. 新函数自动用 default_vendor，特殊情况才配置

**影响**：
- @tool 函数不写 vendor 参数
- registry.yaml 只存 default_vendor + tool_vendors
- 换数据源只改配置，不改代码

### D3: 为什么函数签名必须一致？

**理由**：
1. 数据源层是基准，数仓层适配数据源层
2. 避免参数映射增加复杂度
3. 找不到函数报错，强制约定

**影响**：
- 数据源层定义标准签名
- 历史遗留函数用别名或包装适配
- 数仓层函数签名与数据源层一致

### D4: 为什么用 @export 装饰器自动注册？

**理由**：
1. 手动在 data.py 维护导出列表太重
2. 装饰器标记，写函数加一行即可
3. 自动扫描，避免配置和代码不一致

**影响**：
- 写函数：加 @export
- 入口文件 data.py 自动收集
- 历史遗留函数不加装饰器，不会被导出

### D5: 为什么字段说明在数据源层？

**理由**：
1. 数据源层知道数据字段的含义
2. 返回值内联，LLM 直接可读
3. 数仓层不需要额外处理

**影响**：
- 数据源层返回字符串（含字段说明）
- 数仓层透传返回值
- 智能体直接解读

---

## 十二、总结

### 核心设计

| 维度 | 方案 |
|------|------|
| 层数 | 2层（智能体→数仓servers→数据源） |
| 改动流程 | 三层各改一处 |
| vendor 路由 | registry.yaml 统一管理，函数层不关心 |
| 函数签名 | 数据源层定义，必须一致，找不到报错 |
| 注册机制 | @export 装饰器自动注册 |
| 数据源结构 | 入口文件 + 实现文件分离 |
| 字段说明 | 数据源层返回值内联 |

### 扩展改动对比

| 场景 | 改动位置 |
|------|---------|
| 加新函数 | 数据源层 + 数仓层 + 智能体层（各一处） |
| 加新数据源 | 数据源层 + registry.yaml |
| 换 vendor | registry.yaml |

### 遗留问题（已确认）

**智能体层 agents_registry.yaml 是否需要手动同步？**

答：**是的，必须手动配置**。智能体绑定什么工具是业务决策，由开发者从数仓层 @tool 函数名复制到 agents_registry.yaml。这样设计的好处：

1. **灵活控制**：哪个智能体用什么工具，由业务决定，不自动绑定
2. **显式配置**：工具绑定一目了然，便于审查
3. **扩展流程**：加新工具 → 数据源层 + 数仓层 + agents_registry.yaml（各一处）

---

*文档版本：2026-04-17*