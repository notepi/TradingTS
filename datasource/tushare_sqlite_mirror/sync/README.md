# tushare_sqlite_mirror Sync PRD

> 本文档对 `tushare_sqlite_mirror/sync/` 数据同步管道进行全面分析。

---

## 一、定位与目标

**按需自动同步（On-Demand Sync）：** API 查询 SQLite 时，如果数据为空，会自动触发定向 sync 从 citydata 拉取数据并写入 SQLite，保证查询命中。无需手动跑 sync 命令。

覆盖范围：daily、income、balancesheet、cashflow、fina_indicator、dividend、stk_rewards。



**定位：** citydata.club → SQLite 的 ETL 管道，为查询层提供离线数据源。

**职责：**
1. 从 citydata.club 拉取原始数据（raw tables）
2. 预计算派生特征表（feature tables）
3. 记录同步元数据（sync_batches）

**设计原则：**
- 每次 sync 全量重算 feature 表（幂等替换）
- raw 表按唯一键 upsert（INSERT OR REPLACE）
- 财务表增量同步，市场表固定 365 天回溯

---

## 二、代码架构

```
sync/
├── __init__.py       # 导出 run_bootstrap / run_daily_sync / run_pipeline
├── __main__.py       # python -m tushare_sqlite_mirror.sync 入口
├── cli.py            # argparse 命令行封装
├── client.py         # citydata HTTP 客户端
├── storage.py        # SQLite 连接、schema、upsert、batch 日志
├── pipeline.py        # 四阶段同步主流程
└── tushare.db        # SQLite 数据库文件（已初始化）
```

### client.py — citydata HTTP 客户端

```python
class CityDataClient:
    def fetch(self, api_name: str, **kwargs) -> pd.DataFrame:
        # POST https://tushare.citydata.club/{api_name}
        # TOKEN 放在 form data 里
        # 返回: pd.DataFrame（citydata 直接返回 JSON 数组）
```

### storage.py — 基础设施

| 函数 | 职责 |
|------|------|
| `connect()` | 打开 SQLite，WAL + NORMAL sync |
| `initialize_database()` | 创建 `sync_batches` 元数据表 |
| `ensure_table()` | 建表或 ADD COLUMN，建唯一键索引 |
| `upsert_dataframe()` | INSERT OR REPLACE + 注入 metadata 列 |
| `log_batch()` | 写入 sync_batches 日志 |

### pipeline.py — 四阶段主流程

| 函数 | 职责 |
|------|------|
| `run_bootstrap()` | 仅创建 sync_batches，无数据拉取 |
| `run_pipeline()` | 完整四阶段同步（默认入口） |
| `run_daily_sync()` | 等同于 run_pipeline |

---

## 三、数据模型

### Raw 表（原始数据）

| citydata 接口 | SQLite 表 | 唯一键 |
|-------------|-----------|--------|
| `stock_basic` | `stock_basic_raw` | `ts_code` |
| `daily` | `daily_raw` | `(ts_code, trade_date)` |
| `daily_basic` | `daily_basic_raw` | `(ts_code, trade_date)` |
| `income` | `income_raw` | `(ts_code, end_date, end_type, ann_date, update_flag)` |
| `balancesheet` | `balancesheet_raw` | 同 income |
| `cashflow` | `cashflow_raw` | 同 income |
| `fina_indicator` | `fina_indicator_raw` | 同 income |
| `dividend` | `dividend_raw` | `(ts_code, end_date, ann_date, div_proc)` |
| `stk_rewards` | `stk_rewards_raw` | `(ts_code, ann_date, name)` |

### Feature 表（预计算）

| 表名 | 唯一键 | 来源 |
|------|--------|------|
| `market_daily_features` | `(ts_code, trade_date)` | daily_raw + daily_basic_raw JOIN |
| `financial_period_features` | `(ts_code, end_date, end_type)` | 四张财务表 JOIN + 单季 + YoY |
| `dividend_features` | `(ts_code, end_date)` | dividend_raw（仅 div_proc="实施"） |
| `result_technical_indicators_daily` | `(ts_code, trade_date)` | daily_raw + 17 种技术指标 |
| `result_fundamentals_latest` | `ts_code` | 各表最新行 JOIN |
| `result_yoy_growth` | `(ts_code, report_period, end_type)` | financial_period_features 子集 |
| `result_peg_ratio` | `(ts_code, end_date, end_type)` | financial + market_daily |

### 元数据表

```sql
CREATE TABLE sync_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL,       -- 批次 ID（日期或指定值）
    table_name TEXT NOT NULL,      -- 同步的表名
    status TEXT NOT NULL,          -- completed / failed
    row_count INTEGER NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

每张 raw/feature 表自动带三列：
- `synced_at` — UTC 时间戳
- `source` — "citydata"
- `batch_id` — 所属批次

---

## 四、四阶段同步流程

```
run_pipeline()
│
├─ Phase 1: _sync_stock_basic
│   └─ 获取所有 L（上市）股票列表
│
├─ Phase 2: _sync_market_table (daily + daily_basic)
│   └─ 对每只股票，回溯 365 天
│       client.fetch("daily", ts_code=ts_code,
│                    start_date=365天前, end_date=今天)
│
├─ Phase 3: _sync_financial_table
│   │   (income, balancesheet, cashflow,
│   │    fina_indicator, dividend, stk_rewards)
│   └─ 对每只股票，增量拉取
│       start_date = MAX(end_date) 已存在记录
│
└─ Phase 4: _publish (生成所有 feature 表)
    ├─ _build_market_daily_features
    ├─ _build_financial_period_features
    ├─ _build_dividend_features
    ├─ _build_result_technical_indicators
    ├─ _build_result_fundamentals
    ├─ _build_result_yoy_growth
    └─ _build_result_peg_ratio
```

### 增量策略

| 表类型 | 增量策略 |
|--------|----------|
| 市场表（daily, daily_basic） | 固定 365 天回溯，每次全量 |
| 财务表（income 等） | 按 `end_date` 断点增量 |
| stock_basic | 全量拉取去重 |
| Feature 表 | 每次全量重算（CREATE OR REPLACE） |

### Feature 计算逻辑

**单季值计算**（`_calculate_single_quarter`）：
- 累计值 - 上期累计值 = 单季值
- Q1 单季 = Q1 累计本身

**YoY 计算**（`_calculate_yoy`）：
- 按 `(ts_code, end_type)` 分组，计算 `pct_change(periods=1) * 100`

**技术指标**（17 种）：
- EMA / SMA / MACD / RSI / MFI / CCI / WR / KDJ / BOLL / ATR / VWMA
- 纯 pandas 实现，不依赖 stockstats

---

## 五、存储细节

### SQLite 配置

```python
connection.execute("PRAGMA journal_mode=WAL")   # 并发读支持
connection.execute("PRAGMA synchronous=NORMAL") # 写入性能
```

### Upsert 语义

```python
-- unique key 冲突时，整行替换
INSERT OR REPLACE INTO "daily_raw" (...) VALUES (...)
```

### Schema 演进

- `CREATE TABLE IF NOT EXISTS` — 首次建表
- `ALTER TABLE ADD COLUMN` — 新增列（不影响现有数据）
- `CREATE UNIQUE INDEX` — 按唯一键去重
- `CREATE INDEX` — 按查询热点创建复合索引

---

## 六、CLI 用法

```bash
# 初始化空库（仅创建 sync_batches）
python -m tushare_sqlite_mirror.sync bootstrap --db tushare.db

# 每日同步（全量）
python -m tushare_sqlite_mirror.sync sync_daily --db tushare.db

# 指定批次 ID
python -m tushare_sqlite_mirror.sync sync_daily --db tushare.db --batch-id 20260418

# 指定截止日期
python -m tushare_sqlite_mirror.sync sync_daily --db tushare.db --as-of-date 20260417

# 完整流程（等同于 sync_daily）
python -m tushare_sqlite_mirror.sync pipeline --db tushare.db
```

环境变量：
- `CITYDATA_TOKEN` 或 `TUSHARE_TOKEN` — citydata API token
- `SYNC_BATCH_DATE` — 覆盖 batch-id（格式：YYYYMMDD）

---

## 七、错误处理

| 场景 | 行为 |
|------|------|
| citydata 返回空 | 跳过，写入 row_count=0 |
| citydata 返回错误 dict | `RuntimeError` 终止 |
| HTTP 请求失败 | `requests` 异常上抛 |
| 任意阶段异常 | `connection.rollback()`，写入 failed 日志，异常上抛 |
| stock_basic 返回空 | `RuntimeError` 终止（无可用股票列表） |

---

## 八、与 tushare/ 目录的接口对应关系

| tushare/data.py 调用 | citydata 接口 | SQLite 表 |
|---------------------|--------------|-----------|
| `pro.daily()` | `daily` | `daily_raw` |
| `pro.stock_basic()` | `stock_basic` | `stock_basic_raw` |
| `pro.daily_basic()` | `daily_basic` | `daily_basic_raw` |
| `pro.income()` | `income` | `income_raw` |
| `pro.balancesheet()` | `balancesheet` | `balancesheet_raw` |
| `pro.cashflow()` | `cashflow` | `cashflow_raw` |
| `pro.fina_indicator()` | `fina_indicator` | `fina_indicator_raw` |
| `pro.dividend()` | `dividend` | `dividend_raw` |
| `pro.stk_rewards()` | `stk_rewards` | `stk_rewards_raw` |

**结论：** sync 拉取的口径与 `tushare/data.py` 查询的口径完全一致。

---

## 九、扩展指南

### 新增 Raw 表

**Step 1：** 在 `RAW_TABLES` 列表注册

```python
# pipeline.py line 14
RAW_TABLES = [
    # 已有...
    "新接口名",
]
```

**Step 2：** 在 `storage.py` 注册唯一键和索引

```python
# storage.py
TABLE_UNIQUE_KEYS["新接口名_raw"] = ["ts_code", "end_date"]
TABLE_INDEXES["新接口名_raw"] = [["ts_code", "end_date"]]
```

**Step 3：** 添加同步函数（如果是财务表走增量，如果是市场表走固定窗口）

```python
# pipeline.py
def _sync_new_table(connection, client, ts_codes, batch_id, as_of_date):
    ...
```

### 新增 Feature 表

**Step 1：** 在 `storage.py` 注册

```python
TABLE_UNIQUE_KEYS["new_feature"] = ["ts_code", "trade_date"]
TABLE_INDEXES["new_feature"] = [["ts_code", "trade_date"]]
```

**Step 2：** 在 `_publish()` 中添加

```python
# pipeline.py _publish()
counts["new_feature"] = _build_new_feature(connection, ts_codes=ts_codes, batch_id=batch_id)
```

---

## 十、当前已知特性

1. **Bootstrap 是空操作** — `run_bootstrap()` 仅创建 `sync_batches` 表，不拉取任何数据
2. **Daily sync 不真增量** — 市场表每次回溯 365 天，非真正的增量
3. **Feature 全量重算** — 每次 sync 所有 feature 表全量重建
4. **无并行拉取** — 当前逐只股票串行拉取，可优化为并发
