"""
datasource.tushare_sqlite_mirror - SQLite 缓存数据源

SQLite 作为 datasource.tushare 的缓存，提供：
1. 对外服务：从 SQLite 取数，格式和 tushare 一致
2. sync 入库：调用 datasource.tushare 函数获取数据，存入 SQLite

## 使用方式

对外服务：
    from datasource.tushare_sqlite_mirror import get_stock_data
    data = get_stock_data("600519.SH", "2025-01-01", "2025-04-01")

入库：
    from datasource.tushare_sqlite_mirror import run_pipeline
    run_pipeline("tushare.db", symbol="600519.SH", start_date="2025-01-01", end_date="2025-04-01")
"""

# SQLite 缓存 API
from .api import get_api, SQLiteCacheAPI, pro_api

# 对外服务：数据函数（从 SQLite 取数）
from .data import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_insider_transactions,
    # 别名
    get_Tushare_data_online,
    get_stock_stats_indicators_window,
)

# Lynch 指标函数
from .indicators.enhanced_data import (
    get_peg_ratio,
    get_yoy_growth,
)

# 批量计算函数（从 SQLite 读数据，本地计算）
from .data import (
    get_peg_ratio_batch,
    get_yoy_growth_batch,
)

# 技术分析表查询函数
from .data import (
    get_price_daily,
    get_trend_ma_daily,
    get_momentum_volatility_daily,
    get_technical_labels_daily,
)

# sync 入库函数
from .sync import run_pipeline, run_bootstrap, run_daily_sync, run_technical_pipeline

__all__ = [
    # SQLite 缓存 API
    "get_api",
    "SQLiteCacheAPI",
    "pro_api",
    # 对外服务：数据函数
    "get_stock_data",
    "get_indicators",
    "get_fundamentals",
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_insider_transactions",
    # 别名
    "get_Tushare_data_online",
    "get_stock_stats_indicators_window",
    # Lynch 指标
    "get_peg_ratio",
    "get_yoy_growth",
    # 批量计算
    "get_peg_ratio_batch",
    "get_yoy_growth_batch",
    # 技术分析表
    "get_price_daily",
    "get_trend_ma_daily",
    "get_momentum_volatility_daily",
    "get_technical_labels_daily",
    # sync 入库
    "run_pipeline",
    "run_bootstrap",
    "run_daily_sync",
    "run_technical_pipeline",
]