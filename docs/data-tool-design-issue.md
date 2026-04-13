# 数据工具设计问题排查报告

**日期**: 2026-04-13
**状态**: 已修复

---

## 问题发现

分析报告 `dashboard_20260413_112834` 中发现数据错误：

| 指标 | 报告值 | 实际值 | 状态 |
|------|--------|--------|------|
| **50 SMA** | 96.97 | **101.05** | ❌ 严重错误 |
| **10 EMA** | 91.81 | 91.82 | ✓ 基本一致 |
| PEG | N/A | N/A | ✓ 正确（负增长） |

---

## 根因分析

### 问题1: 技术指标精度问题

**现象**: `look_back_days` 参数由 LLM 决定，导致 SMA 计算不准确。

```python
# 错误设计：LLM 决定数据窗口
look_back_days: Annotated[int, "how many days to look back"]

# 测试结果
look_back_days=5  → 50 SMA = 92.25  ❌ 错误
look_back_days=180 → 50 SMA = 101.05 ✓ 正确
```

**原因**: 50 SMA 需要至少50天数据才能准确计算，200 SMA 需要200天。LLM 不了解这些技术细节，传入过小的值导致计算错误。

### 问题2: 来源标注缺失

**现象**: 工具输出没有来源标签，LLM 容易混淆数据来源。

**表现**: 在之前的测试中，LLM 把 `get_stock_data` 的收盘价当成 `get_indicators` 的 10EMA 历史值使用。

---

## 业界最佳实践

参考 [AgentEngineering](https://www.agentengineering.io/topics/articles/tool-use-patterns):

> **Structured Return Values** - Return consistent, parseable data with clear source attribution.

参考 y_finance.py 的正确做法：

```python
# y_finance.py: 固定获取5年数据，不依赖 LLM 参数
start_date = today_date - pd.DateOffset(years=5)

# LLM 无法控制数据窗口，只控制显示范围
look_back_days: Annotated[int, "how many days of values to display in the output"]
```

---

## 修复方案

### 方案1: 固定数据窗口

修改 `datasource/tushare/data.py`:

```python
def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days of values to display in the output"] = 30,
) -> str:
    """获取技术指标数据

    注意：此函数固定获取1年历史数据以确保指标计算准确，
    look_back_days 只控制输出显示的日期范围，不影响计算精度。
    """
    
    # 固定获取1年数据以确保所有指标计算准确
    DATA_WINDOW_DAYS = 365
    
    # 计算数据获取范围（用于计算）
    data_start_dt = curr_date_dt - relativedelta(days=DATA_WINDOW_DAYS)
    
    # 显示范围（用于输出）
    display_start_dt = curr_date_dt - relativedelta(days=look_back_days)
```

### 方案2: 来源标注

修改工具输出格式：

```python
# get_stock_data
header = "[Tool: get_stock_data] - 原始价格数据\n"

# get_indicators
header = f"[Tool: get_indicators] [Indicator: {indicator}]\n"
```

---

## 测试验证

### 修复前

```bash
look_back_days=5  → 50 SMA = 92.25   # 错误：数据不足
look_back_days=30 → 50 SMA = 92.13   # 错误：数据不足
look_back_days=180 → 50 SMA = 101.05 # 正确
```

### 修复后

```bash
look_back_days=5  → 50 SMA = 101.05  # 正确：固定使用365天数据
look_back_days=30 → 50 SMA = 101.05  # 正确：固定使用365天数据
look_back_days=100 → 50 SMA = 101.05 # 正确：固定使用365天数据
```

### 200 SMA 测试

```bash
# 需要200天以上历史数据
look_back_days=10 → 200 SMA = 82.91  # 正确（修复前会超时或错误）
```

---

## 设计原则

### 核心原则

> **工具不应该暴露"计算精度参数"给 LLM，只应暴露"显示范围参数"。**

### 参数分类

| 参数类型 | 用途 | LLM 是否可控 |
|----------|------|-------------|
| **计算精度参数** | 影响数据准确性 | ❌ 不应该 |
| **显示范围参数** | 影响输出格式 | ✓ 可以 |

### 示例

```python
# 错误设计
def get_50_sma(data_window_days: int):  # LLM 决定计算精度 ❌

# 正确设计
def get_50_sma(display_days: int):      # LLM 决定显示范围 ✓
    # 内部固定使用足够长的数据
    internal_data_window = 365
```

---

## 其他函数排查

| 函数 | 参数设计 | 问题状态 |
|------|----------|----------|
| `get_stock_data` | `start_date`, `end_date` 由 LLM 决定 | ⚠️ 需关注 |
| `get_fundamentals` | 只需 `ticker` | ✓ 无问题 |
| `get_balance_sheet` | 只需 `ticker`, `freq` | ✓ 无问题 |
| `get_cashflow` | 只需 `ticker`, `freq` | ✓ 无问题 |
| `get_income_statement` | 只需 `ticker`, `freq` | ✓ 无问题 |
| `get_peg_ratio` | 只需 `ticker` | ✓ 无问题 |
| `get_yoy_growth` | 只需 `ticker` | ✓ 无问题 |

### `get_stock_data` 待改进

当前设计让 LLM 决定 `start_date` 和 `end_date`，建议改为：

```python
# 改进建议
def get_stock_data(
    symbol: Annotated[str, "ticker symbol"],
    period: Annotated[str, "data period: '1y', '6m', '3m'"] = "1y",
) -> str:
    # 内部根据 period 计算日期范围
    if period == "1y":
        start_date = curr_date - relativedelta(years=1)
    # ...
```

---

## Git 提交记录

```bash
9c5af68 fix: technical indicators now use fixed 1-year data window
12ed991 fix: auto-extend data window for accurate SMA/EMA calculations
0b42d38 fix: add tool source labels to prevent LLM data confusion
```

---

## 参考文献

1. [AgentEngineering - Tool Use Patterns](https://www.agentengineering.io/topics/articles/tool-use-patterns)
2. Anthropic Tool Use Best Practices
3. `tradingagents/dataflows/y_finance.py` - 固定数据窗口设计