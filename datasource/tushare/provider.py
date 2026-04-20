"""
datasource/tushare/provider.py - Tushare 数据提供者（在线 API）

继承 StockDataProvider，实现数据获取逻辑。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import pandas as pd

from .base_provider import StockDataProvider
from .api import get_api


# Provider 实例（延迟初始化）
_provider = None


def get_provider() -> TushareProvider:
    """获取 Provider 实例"""
    global _provider
    if _provider is None:
        _provider = TushareProvider()
    return _provider


class TushareProvider(StockDataProvider):
    """Tushare 数据提供者（在线 API）"""

    def __init__(self, mode="proxy", token=None):
        self.api = get_api(mode, token)

    @property
    def source_name(self) -> str:
        return "Tushare (citydata.club proxy)"

    # ========== 数据获取实现 ==========
    def _fetch_stock_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票行情数据"""
        start_dt = start_date.replace("-", "")
        end_dt = end_date.replace("-", "")

        df = self.api.daily(ts_code=ts_code, start_date=start_dt, end_date=end_dt)

        if df.empty:
            return pd.DataFrame()

        # 按日期升序排列
        df = df.sort_values("trade_date")

        # 重命名列
        df = df.rename(columns={
            "trade_date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "vol": "Volume",
            "amount": "Amount"
        })

        # 格式化日期
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    def _fetch_indicators(
        self,
        ts_code: str,
        indicator: str,
        curr_date: str,
        look_back_days: int
    ) -> dict:
        """获取技术指标数据"""
        DATA_WINDOW_DAYS = 365

        curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        data_start_dt = curr_date_dt - relativedelta(days=DATA_WINDOW_DAYS)

        start_dt = data_start_dt.strftime("%Y%m%d")
        end_dt = curr_date_dt.strftime("%Y%m%d")

        df = self.api.daily(ts_code=ts_code, start_date=start_dt, end_date=end_dt)

        if df.empty:
            return {}

        # 按日期升序排列
        df = df.sort_values("trade_date")

        # 使用 stockstats 计算指标
        from stockstats import wrap

        df = df.rename(columns={
            "trade_date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "vol": "Volume"
        })
        df["Date"] = pd.to_datetime(df["Date"])

        wrapped = wrap(df)

        # 计算指标
        _ = wrapped[indicator]

        value_by_date = {}
        for _, row in wrapped.iterrows():
            value_by_date[row["Date"].strftime("%Y-%m-%d")] = row.get(indicator)

        return value_by_date

    def _fetch_fundamentals(self, ts_code: str, curr_date: str | None, start_date: str | None, end_date: str | None) -> dict | pd.DataFrame:
        """获取估值数据

        Args:
            curr_date: 单日查询（返回估值 dict）
            start_date/end_date: 日期范围查询（返回估值历史 DataFrame）

        Returns:
            单日查询：dict（PE/PB/市值等估值数据）
            日期范围查询：DataFrame（每日估值历史）
        """
        # 日期范围查询：返回每日估值历史
        if start_date and end_date:
            start_dt = start_date.replace("-", "")
            end_dt = end_date.replace("-", "")

            daily_basic = self.api.daily_basic(ts_code=ts_code, start_date=start_dt, end_date=end_dt)

            if daily_basic.empty:
                return None

            daily_basic = daily_basic.sort_values("trade_date", ascending=True)

            rows = []
            for _, row in daily_basic.iterrows():
                rows.append({
                    "Date": row.get("trade_date"),
                    "close": row.get("close"),
                    "pe": row.get("pe"),
                    "pe_ttm": row.get("pe_ttm"),
                    "pb": row.get("pb"),
                    "total_mv": row.get("total_mv"),
                    "circ_mv": row.get("circ_mv"),
                    "total_share": row.get("total_share"),
                    "turnover_rate": row.get("turnover_rate"),
                })

            return pd.DataFrame(rows)

        # 单日查询：只返回估值数据（简化）
        date_str = curr_date.replace("-", "") if curr_date else datetime.now().strftime("%Y%m%d")

        daily_basic = self.api.daily_basic(ts_code=ts_code, start_date=date_str, end_date=date_str)
        if daily_basic.empty:
            daily_basic = self.api.daily_basic(ts_code=ts_code, end_date=date_str)

        if daily_basic.empty:
            return None

        row = daily_basic.iloc[0]

        data = {}
        data["Date"] = date_str

        close = row.get("close")
        if close:
            data["Stock_Price_元"] = f"{float(close):.2f}"

        pe = row.get("pe")
        if pe and float(pe) > 0:
            data["P/E_Ratio"] = f"{float(pe):.2f}"
        else:
            data["P/E_Ratio"] = "N/A"

        pe_ttm = row.get("pe_ttm")
        if pe_ttm and float(pe_ttm) > 0:
            data["P/E_Ratio_TTM"] = f"{float(pe_ttm):.2f}"
        else:
            data["P/E_Ratio_TTM"] = "N/A"

        pb = row.get("pb")
        if pb and float(pb) > 0:
            data["P/B_Ratio"] = f"{float(pb):.2f}"
        else:
            data["P/B_Ratio"] = "N/A"

        total_mv = row.get("total_mv")
        if total_mv:
            data["Total_Market_Cap_元"] = f"{float(total_mv) * 10000:.2f}"

        circ_mv = row.get("circ_mv")
        if circ_mv:
            data["Circulating_Market_Cap_元"] = f"{float(circ_mv) * 10000:.2f}"

        return data

    def _fetch_balance_sheet(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取资产负债表"""
        df = self.api.balancesheet(ts_code=ts_code)

        if df.empty:
            return pd.DataFrame()

        df = df.sort_values("end_date", ascending=False)

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        return df

    def _fetch_cashflow(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取现金流量表"""
        df = self.api.cashflow(ts_code=ts_code)

        if df.empty:
            return pd.DataFrame()

        # 去重处理
        if 'update_flag' in df.columns:
            df['_sort_key'] = df['update_flag'].astype(int) * 10000000000 + df['ann_date'].astype(int)
            df = df.sort_values('_sort_key', ascending=False)
            df = df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')
            df = df.drop(columns=['_sort_key'])
        else:
            df = df.sort_values('ann_date', ascending=False)
            df = df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        return df

    def _fetch_income_statement(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取利润表"""
        df = self.api.income(ts_code=ts_code)

        if df.empty:
            return pd.DataFrame()

        df = df.sort_values("end_date", ascending=False)

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        return df

    def _fetch_insider_transactions(self, ts_code: str) -> pd.DataFrame:
        """获取内部交易数据"""
        df = self.api.stk_rewards(ts_code=ts_code)

        if df.empty:
            return pd.DataFrame()

        df = df.sort_values("ann_date", ascending=False)

        # 字段说明
        field_names = {
            "ts_code": "股票代码",
            "ann_date": "公告日期",
            "end_date": "报告期",
            "name": "姓名",
            "title": "职务",
            "type": "类型",
            "reward": "薪酬",
            "holding_shares": "持股数量",
            "in_deal": "买入数量",
            "out_deal": "卖出数量",
            "change_reason": "变动原因",
        }

        # 只保留已知字段
        available_fields = [f for f in field_names.keys() if f in df.columns]
        df = df[available_fields]

        # 重命名为中文
        df = df.rename(columns=field_names)

        # 转换日期格式
        if "公告日期" in df.columns:
            df["公告日期"] = df["公告日期"].astype(str)
        if "报告期" in df.columns:
            df["报告期"] = df["报告期"].astype(str)

        # 取最近 30 条
        df = df.head(30)

        return df

    def _fetch_peg_ratio(self, ts_code: str, curr_date: str | None) -> pd.DataFrame:
        """获取 PEG 数据"""
        date_str = curr_date.replace("-", "") if curr_date else datetime.now().strftime("%Y%m%d")

        # 获取历史估值数据
        start_date = date_str[:4] + "0101"
        daily_basic = self.api.daily_basic(ts_code=ts_code, start_date=start_date, end_date=date_str)

        # 获取利润数据
        income_df = self.api.income(ts_code=ts_code)

        if daily_basic.empty or income_df.empty:
            return pd.DataFrame()

        # 去重处理
        if 'update_flag' in income_df.columns:
            income_df['_sort_key'] = income_df['update_flag'].astype(int) * 10000000000 + income_df['ann_date'].astype(int)
            income_df = income_df.sort_values('_sort_key', ascending=False)
            income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')
            income_df = income_df.drop(columns=['_sort_key'])
        else:
            income_df = income_df.sort_values('ann_date', ascending=False)
            income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')

        # 计算增长率
        income_df['year'] = income_df['end_date'].astype(str).str[:4]

        # 年报增长率
        annual_df = income_df[income_df['end_type'] == '4'].copy()
        annual_df = annual_df.sort_values('end_date', ascending=True)
        if len(annual_df) >= 2:
            annual_df['n_income_yoy'] = annual_df['n_income'].pct_change(periods=1) * 100

        # 季报增长率
        quarterly_df = income_df[income_df['end_type'].isin(['1', '2', '3'])].copy()
        quarterly_df = quarterly_df.sort_values(['end_type', 'end_date'], ascending=[True, True])
        if len(quarterly_df) >= 4:
            quarterly_df['n_income_yoy'] = quarterly_df.groupby('end_type')['n_income'].pct_change(periods=1) * 100

        # 合并
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

        # 构建输出 DataFrame
        period_type_map = {'1': 'Q1', '2': 'Q2', '3': 'Q3', '4': '年报'}
        rows = []

        income_df = income_df.sort_values('end_date', ascending=False)

        for _, row in income_df.head(8).iterrows():
            end_date = str(row.get('end_date', 'N/A'))[:8]
            end_type = str(row.get('end_type', 'N/A'))
            period_type = period_type_map.get(end_type, end_type)
            n_income = row.get('n_income', 0)
            ni_yoy = row.get('n_income_yoy')

            # PEG 计算
            if pe_ttm_current and float(pe_ttm_current) > 0 and ni_yoy is not None and not pd.isna(ni_yoy):
                if float(ni_yoy) > 0:
                    peg = float(pe_ttm_current) / float(ni_yoy)
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
                    peg = None
                    judgment = "负增长"
            else:
                peg = None
                judgment = "数据不足"

            rows.append({
                "end_date": end_date,
                "end_type": period_type,
                "n_income": n_income,
                "n_income_yoy": ni_yoy,
                "pe_ttm": pe_ttm_current,
                "peg": peg,
                "valuation": judgment,
            })

        return pd.DataFrame(rows)

    def _fetch_yoy_growth(self, ts_code: str, curr_date: str | None) -> pd.DataFrame:
        """获取 YoY 增长数据"""
        income_df = self.api.income(ts_code=ts_code)

        if income_df.empty:
            return pd.DataFrame()

        # 去重处理
        if 'update_flag' in income_df.columns:
            income_df['_sort_key'] = income_df['update_flag'].astype(int) * 10000000000 + income_df['ann_date'].astype(int)
            income_df = income_df.sort_values('_sort_key', ascending=False)
            income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')
            income_df = income_df.drop(columns=['_sort_key'])
        else:
            income_df = income_df.sort_values('ann_date', ascending=False)
            income_df = income_df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')

        # 季报增长率
        quarterly_df = income_df[income_df['end_type'].isin(['1', '2', '3'])].copy()
        quarterly_df = quarterly_df.sort_values(['end_type', 'end_date'], ascending=[True, True])
        if len(quarterly_df) >= 4:
            quarterly_df['revenue_yoy'] = quarterly_df.groupby('end_type')['revenue'].pct_change(periods=1) * 100
            quarterly_df['n_income_yoy'] = quarterly_df.groupby('end_type')['n_income'].pct_change(periods=1) * 100

        # 合并
        income_df = income_df.merge(
            quarterly_df[['end_date', 'revenue_yoy', 'n_income_yoy']],
            on='end_date',
            how='left'
        )

        # 年报增长率
        annual_df = income_df[income_df['end_type'] == '4'].copy()
        annual_df = annual_df.sort_values('end_date', ascending=True)
        if len(annual_df) >= 2:
            annual_df['revenue_yoy'] = annual_df['revenue'].pct_change(periods=1) * 100
            annual_df['n_income_yoy'] = annual_df['n_income'].pct_change(periods=1) * 100
            annual_yoy = annual_df[['end_date', 'revenue_yoy', 'n_income_yoy']].copy()
            annual_yoy.columns = ['end_date', 'revenue_yoy_annual', 'n_income_yoy_annual']
            income_df = income_df.merge(annual_yoy, on='end_date', how='left')
            income_df['revenue_yoy'] = income_df['revenue_yoy'].fillna(income_df['revenue_yoy_annual'])
            income_df['n_income_yoy'] = income_df['n_income_yoy'].fillna(income_df['n_income_yoy_annual'])

        # 计算单季值
        income_df['year'] = income_df['end_date'].astype(str).str[:4]
        single_q_values = {}

        for year in income_df['year'].unique():
            year_df = income_df[income_df['year'] == year]

            q1 = year_df[year_df['end_type'] == '1']
            if not q1.empty:
                q1_row = q1.iloc[0]
                q1_date = q1_row['end_date']
                single_q_values[q1_date] = {
                    'revenue': q1_row.get('revenue', 0) or 0,
                    'n_income': q1_row.get('n_income', 0) or 0
                }

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

        # 构建输出 DataFrame
        period_type_map = {'1': 'Q1', '2': 'Q2', '3': 'Q3', '4': '年报'}
        rows = []

        income_df = income_df.sort_values('end_date', ascending=False)

        for _, row in income_df.head(8).iterrows():
            end_date = str(row.get('end_date', 'N/A'))
            end_type = str(row.get('end_type', 'N/A'))
            period_type = period_type_map.get(end_type, end_type)

            rev_cum = row.get('revenue', 0)
            ni_cum = row.get('n_income', 0)

            single_q = single_q_values.get(end_date, {'revenue': 0, 'n_income': 0})
            rev_single = single_q['revenue']
            ni_single = single_q['n_income']

            rev_yoy = row.get('revenue_yoy')
            ni_yoy = row.get('n_income_yoy')

            rows.append({
                "end_date": end_date[:8],
                "end_type": period_type,
                "revenue_cum": rev_cum,
                "revenue_single": rev_single,
                "n_income_cum": ni_cum,
                "n_income_single": ni_single,
                "revenue_yoy": rev_yoy,
                "n_income_yoy": ni_yoy,
            })

        return pd.DataFrame(rows)