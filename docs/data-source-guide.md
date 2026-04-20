# 数据源扩展指南

本指南说明如何添加新工具、新数据源或切换数据源。

## 扩展场景

| 场景 | 改动位置 | 章节 |
|------|----------|------|
| 添加新工具 | 三层各一处 | 下文详细步骤 |
| 添加新数据源 | 数据源层 + registry.yaml | 添加新数据源 |
| 换数据源 | registry.yaml 或 config.yaml | 切换数据源 |

---

## 添加新工具（三层各改一处）

### Step 1: 数据源层

位置：`datasource/{vendor}/{domain}.py`

添加函数并使用 `@export` 装饰器：

```python
from datasource.tushare.data import export

@export
def get_new_metric(ticker: str, date: str) -> str:
    """获取新指标"""
    # 调用 API 获取数据
    data = api.get_new_metric(ticker, date)

    # 返回值需含字段说明（LLM 可读）
    header = "# New Metric data\n"
    header += "# 字段说明：\n"
    header += "# - field1: 字段1含义\n"
    header += "# - field2: 字段2含义\n"

    return header + data.to_csv(index=False)
```

**注意事项**：
- 函数签名定义标准参数（ticker、date 等）
- 返回值为字符串，包含字段说明
- 使用 `@export` 装饰器自动注册

### Step 2: 数仓层

位置：`datasource/datahub/servers/{domain}.py`

添加 `@tool` 函数：

```python
from datasource.datahub.servers.interface import tool

@tool
def get_new_metric(ticker: str, date: str) -> str:
    """获取新指标 - 用于分析XXX"""
    return route_to_vendor("get_new_metric", ticker, date)
```

**注意事项**：
- 函数签名必须与数据源层一致
- 使用 `route_to_vendor` 路由到配置的数据源
- 不写 vendor 参数，由配置层决定

### Step 3: 智能体层

位置：`tradingagents/config/agents_registry.yaml`

添加工具到智能体：

```yaml
agents:
  market_analyst:
    tools:
      - name: get_stock_data
      - name: get_indicators
      - name: get_new_metric  # 新增
```

### Step 4: registry.yaml（可选）

位置：`datasource/datahub/servers/registry.yaml`

添加工具定义：

```yaml
tools:
  get_new_metric:
    category: technical_indicators
    module_path: datasource.datahub.servers.indicator
    description: |
      新指标工具 - 用于分析XXX。
    vendors: [tushare, yfinance]
```

---

## 添加新数据源

### Step 1: 创建目录

```bash
mkdir -p datasource/new_vendor/
```

### Step 2: 创建入口文件

位置：`datasource/new_vendor/data.py`

```python
# 入口文件：导出所有函数
from .market import get_stock_data
from .fundamental import get_fundamentals

__all__ = ["get_stock_data", "get_fundamentals"]
```

### Step 3: 实现函数

位置：`datasource/new_vendor/market.py`

```python
from .data import export

@export
def get_stock_data(ticker: str, date: str) -> str:
    """获取股票价格数据"""
    # 实现数据获取逻辑
    ...
```

**关键**：函数签名必须与现有数据源一致。

### Step 4: 配置路由

位置：`config.yaml`

```yaml
vendor_paths:
  new_vendor: "datasource.new_vendor"
```

位置：`registry.yaml`

```yaml
tools:
  get_stock_data:
    vendors: [tushare, yfinance, new_vendor]  # 添加 new_vendor
```

---

## 切换数据源

### 方式一：类别级切换

位置：`config.yaml`

```yaml
data_vendors:
  core_stock_apis: "yfinance"  # 从 tushare 切换到 yfinance
```

### 方式二：工具级切换

位置：`config.yaml`

```yaml
tool_vendors:
  get_news: "alpha_vantage"  # 单个工具使用 alpha_vantage
```

**优先级**：`tool_vendors > data_vendors > 默认数据源`

---

## 函数签名约定

**必须与现有函数签名一致**：

| 参数 | 说明 |
|------|------|
| ticker | 股票代码 |
| date | 分析日期（YYYY-MM-DD） |

不一致时使用别名或包装函数适配：

```python
# 原函数签名不一致
def api_get_data(symbol, trading_day):

# 包装函数适配
@export
def get_stock_data(ticker: str, date: str) -> str:
    return api_get_data(ticker, date)
```

---

## 验证扩展

### 运行测试

```bash
uv run tradingagents test 600519.SH --date 2026-04-19
```

### 检查日志

查看 `message_tool.log` 确认新工具被调用：

```
10:00:00 [Tool Call] get_new_metric(ticker=600519.SH, date=2026-04-19)
```

---

---

## 数据单位规范

### 标准单位表

| 类型 | 单位 | 说明 |
|------|------|------|
| 货币金额 | 元 (CNY) | 所有 monetary value 输出 |
| 股份数量 | 股 | 所有 share count 输出 |
| 百分比 | % | ratios、增长率 |

### 单位换算规则

| 来源 | 目标 | 转换 |
|------|------|------|
| 万元 | 元 | `* 10000` |
| 万股 | 股 | `* 10000` |
| 千元 | 元 | `* 1000` |
| 亿元 | 元 | `* 100000000` |

### 实施层级

1. **Storage layer (sync pipeline)**：数据入库前完成单位转换，SQLite 存储元/股
2. **Display layer (data.py)**：输出时不再做二次转换，直接显示元/股

### 正确示例

```python
# 错误 - 输出亿元
f"Total Market Cap (亿元): {float(total_mv) / 10000:.2f}"

# 正确 - 输出元
f"Total Market Cap (元): {float(total_mv) * 10000:.2f}"
```

## 参考

详细设计见：[datahub-design.md](datahub-design.md) 第十章"如何扩展"