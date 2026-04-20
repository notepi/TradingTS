"""
sync - 数据同步入库模块

调用 datasource.tushare 函数获取数据，存入 SQLite 缓存。
"""

from .pipeline import run_pipeline, run_bootstrap, run_daily_sync

__all__ = ["run_pipeline", "run_bootstrap", "run_daily_sync"]