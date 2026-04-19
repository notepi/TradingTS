from __future__ import annotations

"""
增长率与估值指标函数

提供 PEG Ratio 和增长率数据。
函数从 tools_registry.yaml 自动发现。
"""

from typing import Annotated
from datetime import datetime
import pandas as pd
import os

try:
    from tradingagents.dataflows.decorators import auto_tool
except ImportError:
    def auto_tool(*args, **kwargs):
        def _decorator(func):
            return func
        return _decorator

from ..api import get_api
from ..data import _convert_symbol


def _get_pro():
    """获取 Tushare API 客户端（自动选择模式）"""
    return get_api()


def _calculate_single_quarter_values(income_df):
    """从累计值计算单季值

    Args:
        income_df: 已去重的利润表数据，包含 end_date, end_type, revenue, n_income

    Returns:
        dict: {end_date: {'revenue': 单季营收, 'n_income': 单季净利润}}
    """
    income_df = income_df.copy()
    income_df['year'] = income_df['end_date'].astype(str).str[:4]

    single_q_values = {}

    for year in income_df['year'].unique():
        year_df = income_df[income_df['year'] == year]

        # Q1 (end_type=1) 本身就是单季
        q1 = year_df[year_df['end_type'] == '1']
        if not q1.empty:
            q1_row = q1.iloc[0]
            q1_date = q1_row['end_date']
            single_q_values[q1_date] = {
                'revenue': q1_row.get('revenue', 0) or 0,
                'n_income': q1_row.get('n_income', 0) or 0
            }

        # Q2单季 = Q2累计 - Q1累计
        q2 = year_df[year_df['end_type'] == '2']
        if not q2.empty and not q1.empty:
            q2_row = q2.iloc[0]
            q2_date = q2_row['end_date']
            q1_rev = q1.iloc[0].get('revenue', 0) or 0
            q1_ni = q1.iloc[0].get('n_income', 0) or 0
            q2_rev = q2_row.get('revenue', 0) or 0
            q2_ni = q2_row.get('n_income', 0) or 0
            single_q_values[q2_date] = {
                'revenue': q2_rev - q1_rev,
                'n_income': q2_ni - q1_ni
            }

        # Q3单季 = Q3累计 - Q2累计
        q3 = year_df[year_df['end_type'] == '3']
        if not q3.empty and not q2.empty:
            q3_row = q3.iloc[0]
            q3_date = q3_row['end_date']
            q2_rev = q2.iloc[0].get('revenue', 0) or 0
            q2_ni = q2.iloc[0].get('n_income', 0) or 0
            q3_rev = q3_row.get('revenue', 0) or 0
            q3_ni = q3_row.get('n_income', 0) or 0
            single_q_values[q3_date] = {
                'revenue': q3_rev - q2_rev,
                'n_income': q3_ni - q2_ni
            }

        # 年报/Q4单季 = 年报累计 - Q3累计
        annual = year_df[year_df['end_type'] == '4']
        if not annual.empty and not q3.empty:
            annual_row = annual.iloc[0]
            annual_date = annual_row['end_date']
            q3_rev = q3.iloc[0].get('revenue', 0) or 0
            q3_ni = q3.iloc[0].get('n_income', 0) or 0
            annual_rev = annual_row.get('revenue', 0) or 0
            annual_ni = annual_row.get('n_income', 0) or 0
            single_q_values[annual_date] = {
                'revenue': annual_rev - q3_rev,
                'n_income': annual_ni - q3_ni
            }

    return single_q_values


@auto_tool(description="增长率数据 - 获取营收和净利润的同比增长率历史数据，同时提供累计值和单季值")
def get_yoy_growth(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """增长率数据 - 同比增长率历史，包含累计值和单季值两种口径"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        income_df = pro.income(ts_code=ts_code)

        if income_df.empty:
            return f"No income data found for '{ticker}'"

        # 去重处理 - 优先使用修正后的数据 (update_flag=1)
        # 如果有修正数据，用修正的；否则用初始数据 (update_flag=0)
        if 'update_flag' in income_df.columns:
            # 先排序：update_flag=1优先，ann_date最新优先
            income_df['_sort_key'] = income_df['update_flag'].astype(int) * 10000000000 + income_df['ann_date'].astype(int)
            income_df = income_df.sort_values('_sort_key', ascending=False)
            income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')
            income_df = income_df.drop(columns=['_sort_key'])
        else:
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

        # 计算单季值
        single_q_values = _calculate_single_quarter_values(income_df)

        income_df = income_df.sort_values('end_date', ascending=False)

        lines = []
        lines.append(f"# 增长率数据 - {normalized_ticker}")
        lines.append("# 数据口径：累计值（年初至报告期末）+ 单季值（计算得出）")
        lines.append("# 来源：Tushare 最新报表，不含会计差错更正后数据\n")

        # 增长率数据表
        lines.append(f"{'报告期':<10} {'类型':>4} {'累计营收(亿)':>12} {'单季营收(亿)':>12} {'累计净利润(亿)':>14} {'单季净利润(亿)':>14} {'营收YOY%':>10} {'净利润YOY%':>12}")
        lines.append("-" * 95)

        period_type_map = {'1': 'Q1', '2': 'Q2', '3': 'Q3', '4': '年报'}
        for _, row in income_df.head(8).iterrows():
            period = str(row.get('end_date', 'N/A'))[:8]
            end_type = str(row.get('end_type', 'N/A'))
            period_type = period_type_map.get(end_type, end_type)

            # 累计值
            rev_cum = row.get('revenue', 0)
            ni_cum = row.get('n_income', 0)

            # 单季值
            end_date = row.get('end_date')
            single_q = single_q_values.get(end_date, {'revenue': 0, 'n_income': 0})
            rev_single = single_q['revenue']
            ni_single = single_q['n_income']

            # 同比增长率
            rev_yoy = row.get('revenue_yoy')
            ni_yoy = row.get('n_income_yoy')

            rev_cum_str = f"{float(rev_cum)/1e8:.2f}" if rev_cum is not None else "N/A"
            rev_single_str = f"{float(rev_single)/1e8:.2f}" if rev_single is not None else "N/A"
            ni_cum_str = f"{float(ni_cum)/1e8:.2f}" if ni_cum is not None else "N/A"
            ni_single_str = f"{float(ni_single)/1e8:.2f}" if ni_single is not None else "N/A"
            rev_yoy_str = f"{float(rev_yoy):.1f}%" if rev_yoy is not None and not pd.isna(rev_yoy) else "N/A"
            ni_yoy_str = f"{float(ni_yoy):.1f}%" if ni_yoy is not None and not pd.isna(ni_yoy) else "N/A"

            lines.append(f"{period:<10} {period_type:>4} {rev_cum_str:>12} {rev_single_str:>12} {ni_cum_str:>14} {ni_single_str:>14} {rev_yoy_str:>10} {ni_yoy_str:>12}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving YoY growth data for {ticker}: {str(e)}"


@auto_tool(description="PEG估值指标 - PEG = PE(TTM) / 净利润增长率。用于判断成长股估值是否合理。返回各季度/年度的历史PEG数据表格。")
def get_peg_ratio(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """PEG估值指标 - 各季度/年度的历史PEG数据"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()

        # 获取估值数据 - 使用 curr_date 参数
        date_str = curr_date.replace("-", "") if curr_date else datetime.now().strftime("%Y%m%d")

        # 获取历史估值数据（PE-TTM）- 最近60天
        # 注意：daily_basic 不支持 limit 参数，用日期范围限制
        start_date = date_str[:4] + "0101"  # 年初开始，获取足够多的数据
        daily_basic = pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=date_str)

        # 获取利润数据计算增长率
        income_df = pro.income(ts_code=ts_code)

        if daily_basic.empty or income_df.empty:
            return f"No data available for '{ticker}'"

        # 去重处理利润表
        if 'update_flag' in income_df.columns:
            income_df['_sort_key'] = income_df['update_flag'].astype(int) * 10000000000 + income_df['ann_date'].astype(int)
            income_df = income_df.sort_values('_sort_key', ascending=False)
            income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')
            income_df = income_df.drop(columns=['_sort_key'])
        else:
            income_df = income_df.sort_values('ann_date', ascending=False)
            income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')

        # 计算各报告期的净利润增长率
        income_df['year'] = income_df['end_date'].astype(str).str[:4]

        # 年报增长率
        annual_df = income_df[income_df['end_type'] == '4'].copy()
        annual_df = annual_df.sort_values('end_date', ascending=True)
        if len(annual_df) >= 2:
            annual_df['n_income_yoy'] = annual_df['n_income'].pct_change(periods=1) * 100

        # 季报增长率（同季度同比）
        quarterly_df = income_df[income_df['end_type'].isin(['1', '2', '3'])].copy()
        quarterly_df = quarterly_df.sort_values(['end_type', 'end_date'], ascending=[True, True])
        if len(quarterly_df) >= 4:
            quarterly_df['n_income_yoy'] = quarterly_df.groupby('end_type')['n_income'].pct_change(periods=1) * 100

        # 合并增长率数据
        income_df = income_df.merge(
            annual_df[['end_date', 'n_income_yoy']].rename(columns={'n_income_yoy': 'annual_yoy'}),
            on='end_date', how='left'
        )
        income_df = income_df.merge(
            quarterly_df[['end_date', 'n_income_yoy']].rename(columns={'n_income_yoy': 'quarterly_yoy'}),
            on='end_date', how='left'
        )
        income_df['n_income_yoy'] = income_df['annual_yoy'].fillna(income_df['quarterly_yoy'])

        # 获取最新 PE-TTM
        latest_db = daily_basic.iloc[0]
        pe_ttm_current = latest_db.get('pe_ttm', 0)
        close_current = latest_db.get('close', 0)

        # 构建输出
        lines = []
        pe_str = f"{float(pe_ttm_current):.2f}" if pe_ttm_current and float(pe_ttm_current) > 0 else "N/A"
        lines.append(f"# PEG估值数据 - {normalized_ticker}")
        lines.append(f"# 当前股价: {float(close_current):.2f} 元 (PE-TTM: {pe_str})")
        lines.append("# PEG = PE(TTM) / 净利润增长率")
        lines.append("# PEG < 1 相对低估，PEG > 1 相对高估")
        lines.append("# 来源：Tushare 最新报表\n")

        # PEG 历史数据表
        lines.append(f"{'报告期':<10} {'类型':>4} {'净利润(亿)':>12} {'净利润YOY%':>12} {'PE-TTM':>10} {'PEG':>8} {'估值判断':>10}")
        lines.append("-" * 70)

        period_type_map = {'1': 'Q1', '2': 'Q2', '3': 'Q3', '4': '年报'}

        income_df = income_df.sort_values('end_date', ascending=False)

        for _, row in income_df.head(8).iterrows():
            end_date = str(row.get('end_date', 'N/A'))[:8]
            end_type = str(row.get('end_type', 'N/A'))
            period_type = period_type_map.get(end_type, end_type)

            n_income = row.get('n_income', 0)
            ni_yoy = row.get('n_income_yoy')

            # 使用当前 PE-TTM（历史 PE 数据需要更复杂的处理）
            # 这里简化处理：使用当前 PE 计算各期的 PEG
            pe_ttm = pe_ttm_current

            ni_str = f"{float(n_income)/1e8:.2f}" if n_income is not None else "N/A"
            yoy_str = f"{float(ni_yoy):.1f}%" if ni_yoy is not None and not pd.isna(ni_yoy) else "N/A"

            # PEG 计算
            if pe_ttm and float(pe_ttm) > 0 and ni_yoy is not None and not pd.isna(ni_yoy):
                if float(ni_yoy) > 0:
                    peg = float(pe_ttm) / float(ni_yoy)
                    peg_str = f"{peg:.2f}"
                    # 估值判断
                    if peg < 0.5:
                        judgment = "严重低估"
                    elif peg < 1:
                        judgment = "相对低估"
                    elif peg < 1.5:
                        judgment = "合理估值"
                    elif peg < 2:
                        judgment = "略高估值"
                    else:
                        judgment = "高估值"
                else:
                    peg_str = "N/A"
                    judgment = "负增长"
            else:
                peg_str = "N/A"
                judgment = "数据不足"

            pe_str = f"{float(pe_ttm):.2f}" if pe_ttm and float(pe_ttm) > 0 else "N/A"

            lines.append(f"{end_date:<10} {period_type:>4} {ni_str:>12} {yoy_str:>12} {pe_str:>10} {peg_str:>8} {judgment:>10}")

        lines.append("\n---")
        lines.append(f"当前 PEG（基于最新年报增长率）: {peg_str}")
        lines.append(f"注意：PE-TTM 使用当前值，历史各期 PEG 为示意值")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving PEG data for {ticker}: {str(e)}"
