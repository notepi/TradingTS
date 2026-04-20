"""
datasource/tushare_sqlite_mirror/calculator.py - 批量计算函数

从 SQLite 读数据，本地批量计算 PEG/增长率等指标。
不调用 API，纯本地计算。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .provider import _get_db_path


def calc_peg_ratio_batch(
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """批量计算 PEG（从 sqlite 读数据）

    Args:
        ts_code: 股票代码
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）

    Returns:
        DataFrame: Date, pe_ttm, n_income, n_income_yoy, peg, valuation
    """
    db_path = _get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    conn = sqlite3.connect(str(db_path))

    # 1. 读 income_statement 表（净利润历史）
    income_df = pd.read_sql_query(
        f"SELECT * FROM income_statement WHERE ts_code = ? ORDER BY end_date DESC",
        conn,
        params=[ts_code],
    )

    if income_df.empty:
        conn.close()
        return pd.DataFrame()

    # 去重（取每个报告期的最新数据）
    income_df = income_df.drop_duplicates(subset=["end_date", "end_type"], keep="first")

    # 2. 计算 YoY 增长率
    income_df = income_df.sort_values("end_date", ascending=True)

    # 年报增长率
    annual_df = income_df[income_df["end_type"] == "4"].copy()
    annual_yoy = None
    if len(annual_df) >= 2:
        annual_df["n_income_yoy"] = annual_df["n_income"].pct_change(periods=1) * 100
        annual_yoy = annual_df[["end_date", "n_income_yoy"]].rename(columns={"n_income_yoy": "annual_yoy"})

    # 季报增长率（同季度同比）
    quarterly_df = income_df[income_df["end_type"].isin(["1", "2", "3"])].copy()
    quarterly_df = quarterly_df.sort_values(["end_type", "end_date"], ascending=[True, True])
    quarterly_yoy = None
    if len(quarterly_df) >= 4:
        quarterly_df["n_income_yoy"] = quarterly_df.groupby("end_type")["n_income"].pct_change(periods=1) * 100
        quarterly_yoy = quarterly_df[["end_date", "n_income_yoy"]].rename(columns={"n_income_yoy": "quarterly_yoy"})

    # 合并增长率
    if annual_yoy is not None:
        income_df = income_df.merge(annual_yoy, on="end_date", how="left")
    else:
        income_df["annual_yoy"] = pd.NA

    if quarterly_yoy is not None:
        income_df = income_df.merge(quarterly_yoy, on="end_date", how="left")
    else:
        income_df["quarterly_yoy"] = pd.NA

    # 合并增长率（优先用年报，季报补充）
    income_df["n_income_yoy"] = income_df["annual_yoy"].combine_first(income_df["quarterly_yoy"])

    # 3. 读 fundamentals 表获取 PE_TTM
    fundamentals_df = pd.read_sql_query(
        f"SELECT Date, pe_ttm FROM fundamentals WHERE ts_code = ? ORDER BY Date DESC LIMIT 1",
        conn,
        params=[ts_code],
    )

    pe_ttm_current = 0
    if not fundamentals_df.empty:
        pe_ttm_current = fundamentals_df.iloc[0].get("pe_ttm", 0) or 0

    conn.close()

    # 4. 计算 PEG 和估值判断
    income_df = income_df.sort_values("end_date", ascending=False)

    rows = []
    period_type_map = {"1": "Q1", "2": "Q2", "3": "Q3", "4": "年报"}

    for _, row in income_df.head(8).iterrows():
        end_date = str(row.get("end_date", "N/A"))[:8]
        end_type = str(row.get("end_type", "N/A"))
        period_type = period_type_map.get(end_type, end_type)
        n_income = row.get("n_income", 0)
        ni_yoy = row.get("n_income_yoy")

        # PEG 计算
        peg = None
        valuation = "数据不足"

        if pe_ttm_current and float(pe_ttm_current) > 0 and ni_yoy is not None and not pd.isna(ni_yoy):
            if float(ni_yoy) > 0:
                peg = float(pe_ttm_current) / float(ni_yoy)
                if peg < 0.5:
                    valuation = "严重低估"
                elif peg < 1:
                    valuation = "相对低估"
                elif peg < 1.5:
                    valuation = "合理估值"
                elif peg < 2:
                    valuation = "略高估值"
                else:
                    valuation = "高估值"
            else:
                valuation = "负增长"

        rows.append({
            "end_date": end_date,
            "end_type": period_type,
            "n_income": n_income,
            "n_income_yoy": ni_yoy,
            "pe_ttm": pe_ttm_current,
            "peg": peg,
            "valuation": valuation,
        })

    return pd.DataFrame(rows)


def calc_yoy_growth_batch(
    ts_code: str,
) -> pd.DataFrame:
    """批量计算增长率（从 sqlite 读数据）

    Args:
        ts_code: 股票代码

    Returns:
        DataFrame: end_date, end_type, revenue, n_income, revenue_yoy, n_income_yoy
    """
    db_path = _get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    conn = sqlite3.connect(str(db_path))

    # 读 income_statement 表
    income_df = pd.read_sql_query(
        f"SELECT * FROM income_statement WHERE ts_code = ? ORDER BY end_date DESC",
        conn,
        params=[ts_code],
    )

    conn.close()

    if income_df.empty:
        return pd.DataFrame()

    # 去重
    income_df = income_df.drop_duplicates(subset=["end_date", "end_type"], keep="first")

    # 按日期升序
    income_df = income_df.sort_values("end_date", ascending=True)

    # 年报增长率
    annual_df = income_df[income_df["end_type"] == "4"].copy()
    annual_yoy = None
    if len(annual_df) >= 2:
        annual_df["revenue_yoy"] = annual_df["revenue"].pct_change(periods=1) * 100
        annual_df["n_income_yoy"] = annual_df["n_income"].pct_change(periods=1) * 100
        annual_yoy = annual_df[["end_date", "revenue_yoy", "n_income_yoy"]]

    # 季报增长率
    quarterly_df = income_df[income_df["end_type"].isin(["1", "2", "3"])].copy()
    quarterly_df = quarterly_df.sort_values(["end_type", "end_date"], ascending=[True, True])
    quarterly_yoy = None
    if len(quarterly_df) >= 4:
        quarterly_df["revenue_yoy"] = quarterly_df.groupby("end_type")["revenue"].pct_change(periods=1) * 100
        quarterly_df["n_income_yoy"] = quarterly_df.groupby("end_type")["n_income"].pct_change(periods=1) * 100
        quarterly_yoy = quarterly_df[["end_date", "revenue_yoy", "n_income_yoy"]]

    # 合并
    if annual_yoy is not None:
        income_df = income_df.merge(annual_yoy, on="end_date", how="left", suffixes=("", "_annual"))

    if quarterly_yoy is not None:
        income_df = income_df.merge(quarterly_yoy, on="end_date", how="left", suffixes=("", "_q"))

    # 优先用年报增长率，季报增长率作为补充
    if "revenue_yoy_q" in income_df.columns:
        income_df["revenue_yoy"] = income_df["revenue_yoy"].combine_first(income_df["revenue_yoy_q"])
    if "n_income_yoy_q" in income_df.columns:
        income_df["n_income_yoy"] = income_df["n_income_yoy"].combine_first(income_df["n_income_yoy_q"])

    # 按日期降序，取最近 8 条
    income_df = income_df.sort_values("end_date", ascending=False)

    period_type_map = {"1": "Q1", "2": "Q2", "3": "Q3", "4": "年报"}

    rows = []
    for _, row in income_df.head(8).iterrows():
        end_date = str(row.get("end_date", "N/A"))[:8]
        end_type = str(row.get("end_type", "N/A"))
        period_type = period_type_map.get(end_type, end_type)

        rows.append({
            "end_date": end_date,
            "end_type": period_type,
            "revenue": row.get("revenue", 0),
            "n_income": row.get("n_income", 0),
            "revenue_yoy": row.get("revenue_yoy"),
            "n_income_yoy": row.get("n_income_yoy"),
        })

    return pd.DataFrame(rows)