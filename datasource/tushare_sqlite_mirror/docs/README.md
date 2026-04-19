# tushare_sqlite_mirror 产品说明书

> 本文档对 `/Users/pan/Desktop/02 开发项目/research/tushare_sqlite_mirror` 项目进行全面分析。

---

## 一、项目概述

**定位：** A 股金融数据本地 SQLite 镜像，对标 tushare Pro API 接口，离线可查。

**核心价值：**
- 查询零网络依赖（同步完成后）
- 无 API 频限
- 数据全部预计算好（技术指标、YoY、PEG 等）
- 多进程可并发读（SQLite WAL 模式）

**数据来源：** citydata.club（HTTP 代理，需 token）

---

## 二、代码架构

```
research/
├── tushare/                        # 在线模式（HTTP 代理）
│   ├── api.py                      # TushareAPI（proxy/sdk 双模式）
│   ├── proxy.py                    # TushareProxyAPI → citydata HTTP 转发
│   ├── data.py                     # 高层函数（调用 proxy）
│   ├── symbols.py                  # A 股代码标准化
│   └── indicators/enhanced_data.py
│
└── tushare_sqlite_mirror/         # 离线模式（SQLite）
    ├── api.py                      # SQLiteTushareAPI（查询接口）
    ├── data.py                     # 高层函数（调用 api.py）
    ├── symbols.py                  # A 股代码标准化（同上）
    ├── technical_indicators.py     # 纯 Python 技术指标（15 种）
    ├── indicators/
    │   └── enhanced_data.py        # get_peg_ratio, get_yoy_growth
    └── sync/                       # 数据同步管道
        ├── pipeline.py             # 同步主流程（4 阶段）
        ├── storage.py              # SQLite 连接、schema、upsert
        ├── client.py               # citydata HTTP 客户端
        └── cli.py                  # 命令行入口

    # 入口
    from tushare_sqlite_mirror import get_api, pro_api
    api = get_api()
```

### SQLiteTushareAPI 核心方法

| 方法 | 数据表 | 说明 |
|------|--------|------|
| `daily()` | `daily_raw` | 日线行情 |
| `stock_basic()` | `stock_basic_raw` | 股票基础信息 |
| `daily_basic()` | `daily_basic_raw` | 每日估值指标 |
| `income()` | `income_raw` | 利润表 |
| `balancesheet()` | `balancesheet_raw` | 资产负债表 |
| `cashflow()` | `cashflow_raw` | 现金流量表 |
| `fina_indicator()` | `fina_indicator_raw` | 财务指标 |
| `dividend()` | `dividend_raw` | 分红数据 |
| `stk_rewards()` | `stk_rewards_raw` | 高管薪酬/持股 |
| `index_daily()` | `index_daily_raw` | 指数日线 |

### 预计算特征表（直接可查）

| 方法 | 底层表 |
|------|--------|
| `market_daily_features()` | 日线 + 估值指标 JOIN |
| `financial_period_features()` | 财务四表 JOIN + 单季计算 + YoY |
| `dividend_features()` | 分红表（仅"实施"） |
| `result_fundamentals_latest()` | 每只股票最新财务快照 |
| `result_yoy_growth()` | YoY 增长率 |
| `result_peg_ratio()` | PEG = PE_TTM / 净利润增长率 |
| `result_technical_indicators_daily()` | 日线 + 17 种技术指标 |

---

## 三、数仓设计

### Raw 表（原始数据）

| 表名 | 唯一键 | 索引 |
|------|--------|------|
| `stock_basic_raw` | `ts_code` | — |
| `daily_raw` | `(ts_code, trade_date)` | — |
| `daily_basic_raw` | `(ts_code, trade_date)` | — |
| `income_raw` | `(ts_code, end_date, end_type, ann_date, update_flag)` | `(ts_code, end_date, end_type)`, `(ts_code, ann_date)` |
| `balancesheet_raw` | 同 income | 同 income |
| `cashflow_raw` | 同 income | 同 income |
| `fina_indicator_raw` | 同 income | 同 income |
| `dividend_raw` | `(ts_code, end_date, ann_date, div_proc)` | `(ts_code, ann_date)` |
| `stk_rewards_raw` | `(ts_code, ann_date, name)` | `(ts_code, ann_date)` |

### Feature 表（预计算）

| 表名 | 唯一键 | 来源 |
|------|--------|------|
| `market_daily_features` | `(ts_code, trade_date)` | daily + daily_basic JOIN |
| `financial_period_features` | `(ts_code, end_date, end_type)` | 四张财务表 JOIN + 单季 + YoY |
| `dividend_features` | `(ts_code, end_date)` | dividend_raw（仅"实施"） |
| `result_technical_indicators_daily` | `(ts_code, trade_date)` | daily_raw + 17 种技术指标 |
| `result_fundamentals_latest` | `ts_code` | 各表最新行 |
| `result_yoy_growth` | `(ts_code, report_period, end_type)` | financial_period_features 子集 |
| `result_peg_ratio` | `(ts_code, end_date, end_type)` | features + market_daily |

### ER 关系

```
stock_basic_raw (1)──(M) daily_raw
                           │
                    (1)──(M) daily_basic_raw
                           │
                    (1)──(M) market_daily_features
                           │
stock_basic_raw (1)──(M) financial_period_features
                           │
                    (1)──(M) dividend_features
                           │
                    (1)──(M) result_fundamentals_latest
                                   │
                            (1)──(M) result_peg_ratio
```

### SQLite 配置
- WAL journal 模式（支持并发读）
- `NORMAL` sync mode
- `INSERT OR REPLACE` upsert（按唯一键覆盖）
- 每表自动带 `synced_at`, `source`, `batch_id` 三列

---

## 四、Sync 逻辑

### 按需自动同步

查询 SQLite 时，如果数据为空，API 会自动触发定向 sync 从 citydata 拉取数据并写入 SQLite，保证查询命中。无需手动跑 sync 命令。

覆盖范围：daily、income、balancesheet、cashflow、fina_indicator、dividend、stk_rewards。



### 四阶段流程

```
Phase 1: 同步 stock_basic（所有在册 L 股票）
              │
Phase 2: 对每只股票，同步 daily + daily_basic（近 365 天）
              │
Phase 3: 对每只股票，增量同步财务表
         income, balancesheet, cashflow, fina_indicator, dividend, stk_rewards
              │
Phase 4: 生成所有 feature 表
```

### Bootstrap vs Daily Sync

| | Bootstrap | Daily Sync |
|--|-----------|------------|
| `run_bootstrap()` | 仅创建 `sync_batches` 表，无数据拉取 | — |
| `run_daily_sync()` | — | 等于 `run_pipeline()`，全量 365 天市场数据 + 全量重算 feature |

**当前问题：** daily sync 并非真正的增量——市场数据每次全量回溯 365 天，财务数据才是增量的（按 `end_date` 断点）。

### citydata 拉取逻辑

```python
# 市场表（每日）
start_date = (as_of_date - timedelta(days=365)).strftime("%Y%m%d")
frame = client.fetch("daily", ts_code=ts_code, start_date=start_date, end_date=end_date)

# 财务表（增量）
start_date = _resolve_incremental_start(connection, raw_table_name, ts_code, date_column="end_date")
frame = client.fetch("income", ts_code=ts_code, start_date=start_date, end_date=end_date)
```

### citydata 有无 adj_factor？

**没有。** citydata 返回的 daily 数据就是 qfq 前复权数据，mirror 存储的也只有 qfq。**无法做 hfq 或不复权**，除非 citydata 本身提供复权因子接口。

---

## 五、入口用法

### 1. 查询 API（最常用）

```python
from tushare_sqlite_mirror import get_api, pro_api

api = get_api()           # 自动读 TUSHARE_SQLITE_PATH 环境变量
api = pro_api()           # 同上，别名

# 日线
df = api.daily(ts_code="000001.SZ", start_date="20240101", end_date="20241231")

# 财务
df = api.income(ts_code="000001.SZ", start_date="20230101", end_date="20241231")
df = api.balancesheet(ts_code="000001.SZ", period="20240630")

# 预计算特征
df = api.result_technical_indicators_daily(ts_code="000001.SZ")
df = api.result_fundamentals_latest(ts_code="000001.SZ")
df = api.result_peg_ratio(ts_code="000001.SZ")

# 带均线复权行情（本地计算）
df = api.pro_bar_with_ma(ts_code="000001.SZ", ma=[5, 10, 20, 50], adj="qfq")
# 返回: trade_date, open, high, low, close, vol, ma5, ma10, ma20, ma50
```

### 2. 高层函数（data.py）

```python
from tushare_sqlite_mirror import (
    get_Tushare_data_online,     # OHLCV + yfinance 格式
    get_stock_stats_indicators_window,  # 技术指标
    get_fundamentals,            # 财务摘要
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_insider_transactions,
    get_peg_ratio,               # PEG 分析
    get_yoy_growth,              # YoY 增长率
)

# 技术指标（支持 15 种：MACD, RSI, KDJ, BOLL, ATR 等）
df = get_stock_stats_indicators_window("000001.SZ", "rsi", "20241201", look_back_days=365)

# 财务摘要
info = get_fundamentals("000001.SZ", curr_date="20241201")
```

### 3. 命令行同步

一般无需手动调用，API 会自动按需同步。如需主动同步：

```bash
# 初始化空库
python -m tushare_sqlite_mirror.sync.cli bootstrap --db tushare.db

# 全量同步
python -m tushare_sqlite_mirror.sync.cli sync_daily --db tushare.db

# 指定日期
python -m tushare_sqlite_mirror.sync.cli sync_daily --db tushare.db --as-of-date 20241201
```

---

## 六、未来扩展指南

### 新增 API 方法

在 `SQLiteTushareAPI` 中添加两个步骤：

**Step 1：** 在 `_RAW_TABLE_MAP` 或新增表映射

```python
# api.py line 18-29
_RAW_TABLE_MAP = {
    # 已有...
    "新接口名": "新表名_raw",   # 如果是 raw 表
}
```

**Step 2：** 添加具名方法（或走 `_query_api_table` 动态分发）

```python
def new_api(self, ts_code: str = "", start_date: str = "",
            end_date: str = "", fields: str = "", limit: int | None = None):
    """新接口说明"""
    return self._query_api_table("new_api", ts_code=ts_code,
                                  start_date=start_date, end_date=end_date,
                                  fields=fields, limit=limit)
```

### 新增 Feature 表

在 `sync/pipeline.py` 的 Phase 4 添加建表 + 插入逻辑：

```python
# 1. 在 TABLE_INDEXES / TABLE_UNIQUE_KEYS 注册
# 2. 在 pipeline.py Phase 4 添加
def _build_new_feature(connection, batch_id):
    query = """
    CREATE TABLE IF NOT EXISTS new_feature AS
    SELECT ... FROM source_table ...
    """
    connection.execute(query)
    # upsert metadata
```

### 新增技术指标

在 `technical_indicators.py` 添加纯函数，在 `calculate_indicator_frame` 的分发逻辑中注册：

```python
# technical_indicators.py
def _new_indicator(close, period=14):
    ...

# calculate_indicator_frame 中添加
elif indicator == "new_ind":
    result["new_ind"] = _new_indicator(result["close"])
```

---

## 七、对 tushare 目录的替代性评估

### ✅ 可完全替代

- `daily`, `stock_basic`, `daily_basic` — 核心日线
- `income`, `balancesheet`, `cashflow`, `fina_indicator` — 财务四表
- `dividend`, `stk_rewards` — 分红和高管数据
- `index_daily` — 指数日线
- `pro_bar_with_ma` — 均线计算（本地实现更稳定）
- 所有高层函数（`get_fundamentals`, `get_insider_transactions` 等）

### ❌ 无法替代

- **实时数据** — 无盘中 tick 数据

### 结论

| 维度 | 评估 |
|------|------|
| 量化研究/回测 | ✅ 完全可替代 |
| 机器学习特征工程 | ✅ 预计算 feature 表非常适合 |
| 盘中实时决策 | ❌ 不支持 |
| 复权数据 | ✅ 与 tushare 目录口径一致（均使用 daily 接口） |

**总体：** `tushare_sqlite_mirror` 与 `tushare/` 目录数据口径完全一致（均使用 `daily` 接口），可做**完整替代**。实时数据取决于 citydata 是否有对应接口。查询时空数据会自动按需同步，无需手动触发。
