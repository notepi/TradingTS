"""
Lynch 指标函数 - Peter Lynch 分析方法

提供 PEG Ratio 和增长率分析，带有业务背景和 Lynch 方法论说明。
函数从 tools_registry.yaml 自动发现，无需 decorator。
"""

from typing import Annotated
from datetime import datetime
import pandas as pd
import os

from tradingagents.dataflows.decorators import auto_tool
from ..data import _get_pro, _convert_symbol


@auto_tool(description="增长率分析 - Peter Lynch 选股核心指标，稳定的增长率比短暂的高增长更重要")
def get_yoy_growth(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """增长率分析 - Peter Lynch 选股核心指标

    Peter Lynch 强调增长率是选股的核心指标。
    稳定的增长率比短暂的高增长更重要。
    """
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
        lines.append(f"# 增长率分析 - {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)\n")

        # 业务背景
        lines.append("## 业务背景")
        lines.append("Peter Lynch 强调增长率是选股的核心指标。")
        lines.append("他更看重增长率的稳定性，而非短暂的高增长。")
        lines.append("")
        lines.append("Lynch 增长率分类标准：")
        lines.append("- 0-10%: Slow Grower（缓慢增长型）- 大型成熟公司，股息稳定")
        lines.append("- 10-20%: Stalwart（稳定增长型）- Lynch 推荐，PEG < 1 时买入")
        lines.append("- 20-30%: Fast Grower（快速成长型）- 小型公司，需警惕增长放缓")
        lines.append("- >30%: 警惕！高增长往往难以持续")
        lines.append("")

        # 增长率数据
        lines.append("## 增长率数据")
        lines.append("# 注意：以下数据为'年初至报告期末'累计值同比，非单季值，非 TTM")
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

        # Lynch 判断建议
        lines.append("")
        lines.append("## Lynch 判断建议")
        lines.append("1. 增长率是否稳定？波动大则风险高，稳定增长更可靠")
        lines.append("2. 增长来源？内生增长优于并购驱动")
        lines.append("3. 增长可持续性？行业空间、竞争格局、公司护城河")
        lines.append("")
        lines.append("Lynch 金句：\"寻找那些增长率稳定在 10-20% 的公司，它们往往是最佳投资标的。\"")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving YoY growth data for {ticker}: {str(e)}"


@auto_tool(description="PEG Ratio 分析 - Peter Lynch 核心估值指标，将市盈率与增长率结合")
def get_peg_ratio(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """PEG Ratio 分析 - Peter Lynch 核心估值指标

    PEG (Price/Earnings to Growth) 是 Peter Lynch 发明的估值指标，
    将市盈率与增长率结合，弥补 PE 单独使用的缺陷。
    """
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
            return f"No data available for PEG analysis for '{ticker}'"

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
        lines.append(f"# PEG Ratio 分析 - {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)\n")

        # 业务背景
        lines.append("## 业务背景")
        lines.append("PEG (Price/Earnings to Growth) 是 Peter Lynch 发明的估值指标。")
        lines.append("它将市盈率与增长率结合，弥补 PE 单独使用的缺陷。")
        lines.append("")
        lines.append("Lynch 认为：高 PE + 高增长 可能是合理的；低 PE + 低增长 也可能是合理的。")
        lines.append("关键看 PE 与增长率的匹配程度。")
        lines.append("")

        # 计算公式
        lines.append("## 计算公式")
        lines.append("PEG = P/E (TTM) / 净利润增长率")
        lines.append("")

        # 当前数据
        lines.append("## 当前数据")
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
        lines.append("")

        # PEG 计算
        if pe_ttm and float(pe_ttm) > 0 and ni_yoy is not None and not pd.isna(ni_yoy):
            if float(ni_yoy) > 0:
                peg = float(pe_ttm) / float(ni_yoy)
                lines.append("## PEG 计算")
                lines.append(f"PEG = {float(pe_ttm):.2f} / {float(ni_yoy):.1f} = {peg:.2f}")
                lines.append("")

                # Lynch 估值判断
                lines.append("## Lynch 估值判断")
                if peg < 0.5:
                    lines.append(f"当前 PEG = {peg:.2f} < 0.5")
                    lines.append("判断: 显著低估，潜在 10x 股候选")
                    lines.append("Lynch 建议: 这类公司往往被市场忽视，值得深入研究其业务")
                elif peg < 1:
                    lines.append(f"当前 PEG = {peg:.2f}，在 0.5-1 区间")
                    lines.append("判断: 低估，值得深入研究")
                    lines.append("Lynch 建议: 寻找 PEG < 1 的公司是 Lynch 的核心选股策略")
                elif peg < 1.5:
                    lines.append(f"当前 PEG = {peg:.2f}，在 1-1.5 区间")
                    lines.append("判断: 合理估值")
                    lines.append("Lynch 建议: 可持有，但需关注增长率是否稳定")
                elif peg < 2:
                    lines.append(f"当前 PEG = {peg:.2f}，在 1.5-2 区间")
                    lines.append("判断: 略高估")
                    lines.append("Lynch 建议: 需谨慎，确认增长是否能维持")
                else:
                    lines.append(f"当前 PEG = {peg:.2f} > 2")
                    lines.append("判断: 高估，需谨慎")
                    lines.append("Lynch 建议: 可能市场过度乐观，等待回调或寻找更好标的")
            else:
                lines.append("## PEG 分析")
                lines.append(f"净利润增长率 = {float(ni_yoy):.1f}% < 0")
                lines.append("判断: 公司处于衰退期，PEG 计算无意义")
                lines.append("Lynch 建议: 这类公司不符合 Lynch 选股标准，应回避或等待 turnaround")
        else:
            lines.append("## PEG 分析")
            lines.append("无法计算 PEG（缺少 PE 或增长率数据）")
            lines.append("Lynch 建议: 数据不足，无法进行 PEG 分析")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving PEG analysis for {ticker}: {str(e)}"