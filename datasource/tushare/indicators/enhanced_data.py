"""
增长率与估值指标函数

提供 PEG Ratio 和增长率数据。
函数从 tools_registry.yaml 自动发现。
"""

from typing import Annotated
from datetime import datetime
import pandas as pd
import os

from tradingagents.dataflows.decorators import auto_tool
from ..data import _get_pro, _convert_symbol


@auto_tool(description="增长率数据 - 获取营收和净利润的同比增长率历史数据")
def get_yoy_growth(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """增长率数据 - 同比增长率历史"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        income_df = pro.income(ts_code=ts_code)

        if income_df.empty:
            return f"No income data found for '{ticker}'"

        # 第一步：去重 - 按(end_date, end_type)去重，保留最新ann_date的记录
        income_df = income_df.sort_values('ann_date', ascending=False)
        income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')

        # 第二步：分离季报(1,2,3)和年报(4)
        income_df['end_date_str'] = income_df['end_date'].astype(str)
        quarterly_df = income_df[income_df['end_type'].isin(['1', '2', '3'])].copy()

        # 第三步：按季度分组计算同比 (Q1对Q1, Q2对Q2, Q3对Q3)
        quarterly_df = quarterly_df.sort_values(['end_type', 'end_date'], ascending=[True, True])
        if len(quarterly_df) >= 4:
            quarterly_df['revenue_yoy'] = quarterly_df.groupby('end_type')['revenue'].pct_change(periods=1) * 100
            quarterly_df['n_income_yoy'] = quarterly_df.groupby('end_type')['n_income'].pct_change(periods=1) * 100

        # 第四步：合并YOY数据回主表
        income_df = income_df.merge(
            quarterly_df[['end_date', 'revenue_yoy', 'n_income_yoy']],
            on='end_date',
            how='left'
        )

        # 第五步：年报单独处理，计算同比
        annual_df = income_df[income_df['end_type'] == '4'].copy()
        annual_df = annual_df.sort_values('end_date', ascending=True)
        if len(annual_df) >= 2:
            annual_df['revenue_yoy'] = annual_df['revenue'].pct_change(periods=1) * 100
            annual_df['n_income_yoy'] = annual_df['n_income'].pct_change(periods=1) * 100
            # 合并年报YOY
            annual_yoy = annual_df[['end_date', 'revenue_yoy', 'n_income_yoy']].copy()
            annual_yoy.columns = ['end_date', 'revenue_yoy_annual', 'n_income_yoy_annual']
            income_df = income_df.merge(annual_yoy, on='end_date', how='left')
            # 年报用年报YOY，季报用季报YOY
            income_df['revenue_yoy'] = income_df['revenue_yoy'].fillna(income_df['revenue_yoy_annual'])
            income_df['n_income_yoy'] = income_df['n_income_yoy'].fillna(income_df['n_income_yoy_annual'])

        income_df = income_df.sort_values('end_date', ascending=False)

        lines = []
        lines.append(f"# 增长率数据 - {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)")
        lines.append("# 注意：数据为年初至报告期末累计值同比，非单季值，非TTM\n")

        # 增长率数据表
        lines.append(f"{'报告期':<10} {'类型':>4} {'营收(亿)':>10} {'营收YOY%':>10} {'净利润(亿)':>12} {'净利润YOY%':>12}")
        lines.append("-" * 65)

        period_type_map = {'1': 'Q1', '2': 'Q2', '3': 'Q3', '4': '年报'}
        for _, row in income_df.head(8).iterrows():
            period = str(row.get('end_date', 'N/A'))[:8]
            end_type = str(row.get('end_type', 'N/A'))
            period_type = period_type_map.get(end_type, end_type)
            rev = row.get('revenue', 0)
            ni = row.get('n_income', 0)
            rev_yoy = row.get('revenue_yoy')
            ni_yoy = row.get('n_income_yoy')

            rev_str = f"{float(rev)/1e8:.2f}" if rev is not None else "N/A"
            ni_str = f"{float(ni)/1e8:.2f}" if ni is not None else "N/A"
            rev_yoy_str = f"{float(rev_yoy):.1f}%" if rev_yoy is not None and not pd.isna(rev_yoy) else "N/A"
            ni_yoy_str = f"{float(ni_yoy):.1f}%" if ni_yoy is not None and not pd.isna(ni_yoy) else "N/A"

            lines.append(f"{period:<10} {period_type:>4} {rev_str:>10} {rev_yoy_str:>10} {ni_str:>12} {ni_yoy_str:>12}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving YoY growth data for {ticker}: {str(e)}"


@auto_tool(description="PEG 数据 - P/E 与增长率的比值")
def get_peg_ratio(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """PEG 数据 - P/E 与增长率的比值"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()

        # 获取估值数据
        today_str = datetime.now().strftime("%Y%m%d")
        daily_basic = pro.daily_basic(ts_code=ts_code, start_date=today_str, end_date=today_str)
        if daily_basic.empty:
            daily_basic = pro.daily_basic(ts_code=ts_code, end_date=today_str, limit=1)

        # 获取利润数据计算增长率
        income_df = pro.income(ts_code=ts_code)

        if daily_basic.empty or income_df.empty:
            return f"No data available for '{ticker}'"

        # 去重处理
        income_df = income_df.sort_values('ann_date', ascending=False)
        income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')

        # 计算年报净利润增长率
        annual_df = income_df[income_df['end_type'] == '4'].copy()
        annual_df = annual_df.sort_values('end_date', ascending=True)
        if len(annual_df) >= 2:
            annual_df['n_income_yoy'] = annual_df['n_income'].pct_change(periods=1) * 100

        # 获取最新年报增长率
        latest_annual = annual_df.iloc[-1] if len(annual_df) > 0 else None
        ni_yoy = latest_annual.get('n_income_yoy') if latest_annual is not None else None

        # 获取估值数据
        db = daily_basic.iloc[0]
        pe_ttm = db.get('pe_ttm', 0)
        close = db.get('close', 0)

        lines = []
        lines.append(f"# PEG 数据 - {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)\n")

        # 当前数据
        if close:
            lines.append(f"股价: {float(close):.2f} 元")
        if pe_ttm and float(pe_ttm) > 0:
            lines.append(f"P/E (TTM): {float(pe_ttm):.2f}")
        else:
            lines.append("P/E (TTM): N/A（亏损或数据缺失）")
        if ni_yoy is not None and not pd.isna(ni_yoy):
            lines.append(f"净利润增长率 (年报): {float(ni_yoy):.1f}%")
        else:
            lines.append("净利润增长率: 数据不足")

        # PEG 计算
        if pe_ttm and float(pe_ttm) > 0 and ni_yoy is not None and not pd.isna(ni_yoy):
            if float(ni_yoy) > 0:
                peg = float(pe_ttm) / float(ni_yoy)
                lines.append(f"PEG: {peg:.2f}")
            else:
                lines.append("PEG: N/A（净利润负增长）")
        else:
            lines.append("PEG: N/A（数据不足）")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving PEG data for {ticker}: {str(e)}"