"""
Tushare 数据接口 - 使用 citydata.club 代理

与 y_finance.py 保持相同接口，实现平滑切换。
"""

from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
import pandas as pd
import os

from ..symbols import normalize_a_share_symbol
from ..proxy import pro_api
from tradingagents.dataflows.decorators import dataflow_tool

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        pass

load_dotenv()


def _get_pro():
    """获取 Tushare API 客户端"""
    if pro_api is None:
        raise ValueError("tushare_proxy module is unavailable")
    token = os.getenv("CITYDATA_TOKEN") or os.getenv("TUSHARE_TOKEN")
    if not token:
        raise ValueError("CITYDATA_TOKEN or TUSHARE_TOKEN is not configured")
    return pro_api(token)


def _convert_symbol(symbol: str) -> str:
    """Normalize A-share ticker format for Tushare."""
    return normalize_a_share_symbol(symbol)


def get_Tushare_data_online(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
):
    """获取股票历史数据 (OHLCV)"""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")

    normalized_symbol = _convert_symbol(symbol)
    ts_code = normalized_symbol

    # 转换日期格式: 2025-04-02 -> 20250402
    start_dt = start_date.replace("-", "")
    end_dt = end_date.replace("-", "")

    try:
        pro = _get_pro()
        df = pro.daily(ts_code=ts_code, start_date=start_dt, end_date=end_dt)

        if df.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

        # 按日期升序排列
        df = df.sort_values("trade_date")

        # 重命名列以匹配 yfinance 格式
        # 注意：Tushare vol 单位是"手"(每手100股)，不是股数
        df = df.rename(columns={
            "trade_date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "vol": "Volume",
            "amount": "Amount"
        })

        # 选择需要的列
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]

        # 格式化日期
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

        # 转换为 CSV
        csv_string = df.to_csv(index=False)

        header = f"# Stock data for {normalized_symbol} from {start_date} to {end_date}\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += "# Data source: Tushare (citydata.club proxy)\n"
        header += "# 注意：Volume 单位为手(每手100股)，Amount 单位为千元\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving data for {symbol}: {str(e)}"


def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    """获取技术指标数据"""

    # 指标说明
    best_ind_params = {
        "close_50_sma": "50 SMA: A medium-term trend indicator.",
        "close_200_sma": "200 SMA: A long-term trend benchmark.",
        "close_10_ema": "10 EMA: A responsive short-term average.",
        "macd": "MACD: Computes momentum via differences of EMAs.",
        "macds": "MACD Signal: An EMA smoothing of the MACD line.",
        "macdh": "MACD Histogram: Shows the gap between the MACD line and its signal.",
        "rsi": "RSI: Measures momentum to flag overbought/oversold conditions.",
        "boll": "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands.",
        "boll_ub": "Bollinger Upper Band: Typically 2 standard deviations above the middle line.",
        "boll_lb": "Bollinger Lower Band: Typically 2 standard deviations below the middle line.",
        "atr": "ATR: Averages true range to measure volatility.",
        "vwma": "VWMA: A moving average weighted by volume.",
        "mfi": "MFI: The Money Flow Index.",
    }

    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
        )

    # 计算日期范围
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    normalized_symbol = _convert_symbol(symbol)
    ts_code = normalized_symbol
    start_dt = before.strftime("%Y%m%d")
    end_dt = curr_date_dt.strftime("%Y%m%d")

    try:
        pro = _get_pro()
        df = pro.daily(ts_code=ts_code, start_date=start_dt, end_date=end_dt)

        if df.empty:
            return f"No data found for {symbol}"

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
            "vol": "Volume"  # Tushare vol 单位是手(每手100股)
        })
        df["Date"] = pd.to_datetime(df["Date"])

        wrapped = wrap(df)

        # 计算指标
        _ = wrapped[indicator]

        value_by_date = {}
        for _, row in wrapped.iterrows():
            value_by_date[row["Date"].strftime("%Y-%m-%d")] = row.get(indicator)

        # 构建结果
        result_lines = []
        current_dt = curr_date_dt
        while current_dt >= before:
            date_str = current_dt.strftime("%Y-%m-%d")
            ind_value = value_by_date.get(date_str)
            if pd.isna(ind_value):
                result_lines.append(f"{date_str}: N/A: Not a trading day (weekend or holiday)")
            else:
                result_lines.append(f"{date_str}: {ind_value}")
            current_dt = current_dt - relativedelta(days=1)

        result_str = (
            f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n"
            + "\n".join(result_lines)
            + "\n\n"
            + best_ind_params.get(indicator, "No description available.")
            + "\n\n注意：Volume 单位为手(每手100股)，涉及成交量的指标(VWMA/MFI)需注意单位换算。"
        )

        return result_str

    except Exception as e:
        return f"Error getting indicator {indicator} for {symbol}: {str(e)}"


def get_fundamentals(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """获取公司基本面数据"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()

        # 获取基本信息 - 需要获取全部然后过滤
        all_basic = pro.stock_basic()
        basic = all_basic[all_basic['ts_code'] == ts_code]

        # 获取财务指标
        indicator = pro.fina_indicator(ts_code=ts_code)

        # 获取市值和估值数据
        today_str = datetime.now().strftime("%Y%m%d")
        daily_basic = pro.daily_basic(ts_code=ts_code, start_date=today_str, end_date=today_str)
        if daily_basic.empty:
            # 如果今天没数据，取最近可用交易日
            daily_basic = pro.daily_basic(ts_code=ts_code, end_date=today_str, limit=1)

        # 获取利润表
        income = pro.income(ts_code=ts_code)

        # 获取现金流量表
        cashflow = pro.cashflow(ts_code=ts_code)

        if basic.empty:
            return f"No fundamentals data found for symbol '{ticker}'"

        # 构建基本面信息
        lines = []
        lines.append(f"Ticker: {ts_code}")

        row = basic.iloc[0]
        lines.append(f"Name: {row.get('name', 'N/A')}")
        lines.append(f"Industry: {row.get('industry', 'N/A')}")
        lines.append(f"Market: {row.get('market', 'N/A')}")
        lines.append(f"Area: {row.get('area', 'N/A')}")

        if not indicator.empty:
            latest = indicator.iloc[0]
            lines.append(f"ROE (%): {latest.get('roe', 'N/A')}")
            lines.append(f"Net Profit Margin (%): {latest.get('netprofit_margin', 'N/A')}")
            lines.append(f"Gross Profit Margin (%): {latest.get('grossprofit_margin', 'N/A')}")
            lines.append(f"Debt to Asset Ratio (%): {latest.get('debt_to_assets', 'N/A')}")
            lines.append(f"Current Ratio: {latest.get('current_ratio', 'N/A')}")

        # 添加市值和估值数据
        if not daily_basic.empty:
            db = daily_basic.iloc[0]
            close = db.get('close', 0)
            pe = db.get('pe', 0)
            pe_ttm = db.get('pe_ttm', 0)
            pb = db.get('pb', 0)
            total_mv = db.get('total_mv', 0)
            circ_mv = db.get('circ_mv', 0)
            total_share = db.get('total_share', 0)
            if close:
                lines.append(f"Stock Price (元): {float(close):.2f}")
            if pe and float(pe) > 0:
                lines.append(f"P/E Ratio: {float(pe):.2f}")
            if pe_ttm and float(pe_ttm) > 0:
                lines.append(f"P/E Ratio (TTM): {float(pe_ttm):.2f}")
            if pb and float(pb) > 0:
                lines.append(f"P/B Ratio: {float(pb):.2f}")
            if total_mv is not None:
                lines.append(f"Total Market Cap (亿元): {float(total_mv) / 10000:.2f}")
            if circ_mv is not None:
                lines.append(f"Circulating Market Cap (亿元): {float(circ_mv) / 10000:.2f}")
            if total_share is not None:
                lines.append(f"Total Shares (亿股): {float(total_share) / 10000:.2f}")

        # 添加收入和利润数据（单位：亿元）
        if not income.empty:
            inc = income.iloc[0]
            revenue = inc.get('revenue', 0)
            n_income = inc.get('n_income', 0)
            if revenue is not None:
                lines.append(f"Revenue (亿元): {float(revenue) / 1e8:.2f}")
            if n_income is not None:
                lines.append(f"Net Income (亿元): {float(n_income) / 1e8:.2f}")

        # 添加现金流数据（单位：亿元）
        if not cashflow.empty:
            cf = cashflow.iloc[0]
            ocf = cf.get('n_cashflow_act', 0)
            if ocf is not None:
                lines.append(f"Operating Cash Flow (亿元): {float(ocf) / 1e8:.2f}")

        # 添加股息历史数据
        try:
            dividend_df = pro.dividend(ts_code=ts_code, limit=10)
            if not dividend_df.empty:
                lines.append("")
                lines.append("# Dividend History (近10次分红)")
                for _, div_row in dividend_df.head(6).iterrows():
                    year = str(div_row.get('end_date', 'N/A'))[:4]
                    cash = div_row.get('cash_div', 0)
                    stk = div_row.get('stk_div', 0)
                    pay = div_row.get('pay_date', 'N/A')
                    cash_str = f"{float(cash):.4f}元/股" if cash and float(cash) > 0 else "无现金分红"
                    stk_str = f"{float(stk):.1f}股/10股" if stk and float(stk) > 0 else ""
                    pay_str = f", 派息日: {pay}" if pay and str(pay) != 'None' else ""
                    lines.append(f"  {year}: {cash_str} {stk_str}{pay_str}")
        except Exception as e:
            logging.debug(f"Failed to retrieve dividend data for {ts_code}: {e}")

        # 添加股份回购数据
        try:
            repurchase_df = pro.repurchase(ts_code=ts_code, limit=10)
            repurchase_df = repurchase_df[repurchase_df['ts_code'] == ts_code]
            if not repurchase_df.empty:
                lines.append("")
                lines.append("# Share Repurchase History (近10次回购)")
                for _, rp_row in repurchase_df.head(5).iterrows():
                    ann = rp_row.get('ann_date', 'N/A')
                    vol = rp_row.get('vol', 0)
                    amount = rp_row.get('amount', 0)
                    proc = rp_row.get('proc', 0)
                    if vol and float(vol) > 0:
                        vol_str = f"{float(vol)/10000:.2f}万股"
                        amount_str = f"{float(amount)/10000:.2f}万元" if amount else "N/A"
                        proc_str = f", 价格: {proc}元" if proc and float(proc) > 0 else ""
                        lines.append(f"  公告日: {ann}, 数量: {vol_str}, 金额: {amount_str}{proc_str}")
        except Exception as e:
            logging.debug(f"Failed to retrieve repurchase data for {ts_code}: {e}")

        # 添加收入和利润同比增长率
        try:
            income_df = pro.income(ts_code=ts_code)
            if not income_df.empty:
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

                lines.append("")
                lines.append("# Income Growth Trend (近8期数据)")
                lines.append("# 注意：以下数据为'年初至报告期末'累计值，非单季值，非 TTM")
                lines.append(f"  {'报告期':<10} {'类型':>4} {'营收(亿)':>10} {'营收YOY%':>10} {'净利润(亿)':>12} {'净利润YOY%':>12}")
                lines.append("  " + "-" * 65)
                period_type_map = {'1': 'Q1', '2': 'Q2', '3': 'Q3', '4': '年报'}
                for _, inc_row in income_df.head(8).iterrows():
                    period = str(inc_row.get('end_date', 'N/A'))[:8]
                    end_type = str(inc_row.get('end_type', 'N/A'))
                    period_type = period_type_map.get(end_type, end_type)
                    rev = inc_row.get('revenue', 0)
                    ni = inc_row.get('n_income', 0)
                    rev_yoy = inc_row.get('revenue_yoy')
                    ni_yoy = inc_row.get('n_income_yoy')
                    rev_str = f"{float(rev)/1e8:.2f}" if rev else "N/A"
                    ni_str = f"{float(ni)/1e8:.2f}" if ni else "N/A"
                    rev_yoy_str = f"{float(rev_yoy):.1f}%" if rev_yoy is not None and not pd.isna(rev_yoy) else "N/A"
                    ni_yoy_str = f"{float(ni_yoy):.1f}%" if ni_yoy is not None and not pd.isna(ni_yoy) else "N/A"
                    lines.append(f"  {period:<10} {period_type:>4} {rev_str:>10} {rev_yoy_str:>10} {ni_str:>12} {ni_yoy_str:>12}")
        except Exception as e:
            logging.debug(f"Failed to retrieve income growth trend for {ts_code}: {e}")

        header = f"# Company Fundamentals for {normalized_ticker}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += "# Data source: Tushare (citydata.club proxy)\n"
        header += "# 注意：金额单位已转换为亿元，比率单位为%\n\n"

        return header + "\n".join(lines)

    except Exception as e:
        return f"Error retrieving fundamentals for {ticker}: {str(e)}"


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str | None, "current date in YYYY-MM-DD format"] = None
):
    """获取资产负债表"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.balancesheet(ts_code=ts_code)

        if df.empty:
            return f"No balance sheet data found for symbol '{ticker}'"

        # 按报告期降序排列，取最近的
        df = df.sort_values("end_date", ascending=False)

        if freq == "quarterly":
            df = df.head(8)  # 最近 8 个季度
        else:
            df = df.head(4)  # 最近 4 年

        csv_string = df.to_csv(index=False)

        header = f"# Balance Sheet data for {normalized_ticker} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += "# Data source: Tushare (citydata.club proxy)\n"
        header += "# 注意：金额单位为元，如需亿元请除以1e8\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str | None, "current date in YYYY-MM-DD format"] = None
):
    """获取现金流量表"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.cashflow(ts_code=ts_code)

        if df.empty:
            return f"No cash flow data found for symbol '{ticker}'"

        df = df.sort_values("end_date", ascending=False)

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        csv_string = df.to_csv(index=False)

        header = f"# Cash Flow data for {normalized_ticker} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += "# Data source: Tushare (citydata.club proxy)\n"
        header += "# 注意：金额单位为元，如需亿元请除以1e8\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str | None, "current date in YYYY-MM-DD format"] = None
):
    """获取利润表"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.income(ts_code=ts_code)

        if df.empty:
            return f"No income statement data found for symbol '{ticker}'"

        df = df.sort_values("end_date", ascending=False)

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        csv_string = df.to_csv(index=False)

        header = f"# Income Statement data for {normalized_ticker} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += "# Data source: Tushare (citydata.club proxy)\n"
        header += "# 注意：金额单位为元，如需亿元请除以1e8\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol of the company"]
):
    """Return stable placeholder text for unsupported insider data."""
    try:
        normalized_ticker = _convert_symbol(ticker)
    except ValueError as exc:
        return f"Error retrieving insider transactions for {ticker}: {str(exc)}"
    return (
        f"Insider transactions data is not available via Tushare citydata mode for "
        f"'{normalized_ticker}'."
    )


def get_dividend_data(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """获取股票股息分红历史数据"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.dividend(ts_code=ts_code, limit=20)

        if df.empty:
            return f"No dividend data found for '{ticker}'"

        lines = []
        lines.append(f"# Dividend History for {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)\n")

        # 遍历分红记录
        for _, row in df.iterrows():
            end_date = row.get('end_date', 'N/A')
            ann_date = row.get('ann_date', 'N/A')
            cash_div = row.get('cash_div', 0)  # 现金分红（税前）
            stk_div = row.get('stk_div', 0)  # 股票分红（每10股送转）
            pay_date = row.get('pay_date', 'N/A')

            record = f"Year: {str(end_date)[:4]}, Announced: {ann_date}, "
            record += f"Cash Dividend: {cash_div}元/股"
            if stk_div and float(stk_div) > 0:
                record += f", Stock Dividend: {stk_div}股/10股"
            if pay_date and str(pay_date) != 'None':
                record += f", Pay Date: {pay_date}"
            lines.append(record)

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving dividend data for {ticker}: {str(e)}"


def get_share_repurchase_data(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """获取股票回购数据"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.repurchase(ts_code=ts_code, limit=20)

        # 过滤出该股票的数据
        df = df[df['ts_code'] == ts_code]

        if df.empty:
            return f"No share repurchase data found for '{ticker}'"

        lines = []
        lines.append(f"# Share Repurchase History for {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)\n")

        for _, row in df.iterrows():
            ann_date = row.get('ann_date', 'N/A')
            end_date = row.get('end_date', 'N/A')
            vol = row.get('vol', 0)  # 回购数量（股）
            amount = row.get('amount', 0)  # 回购金额（元）
            proc = row.get('proc', 0)  # 回购价格区间

            if vol and float(vol) > 0:
                vol_str = f"{float(vol)/10000:.2f}万股"
            else:
                vol_str = "N/A"
            if amount and float(amount) > 0:
                amount_str = f"{float(amount)/10000:.2f}万元"
            else:
                amount_str = "N/A"

            record = f"Announced: {ann_date}, Ended: {end_date}, "
            record += f"Volume: {vol_str}, Amount: {amount_str}"
            if proc and float(proc) > 0:
                record += f", Price Range: {proc}元"
            lines.append(record)

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving repurchase data for {ticker}: {str(e)}"


def get_income_statement_with_growth(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str | None, "current date in YYYY-MM-DD format"] = None
):
    """获取利润表数据，包含同比增长率"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.income(ts_code=ts_code)

        if df.empty:
            return f"No income statement data found for '{ticker}'"

        # 排序
        df = df.sort_values('end_date', ascending=False)

        lines = []
        lines.append(f"# Income Statement with Growth Rates for {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)")
        lines.append("# 注意：金额单位为元，增长率单位为%\n")

        # 获取列名
        cols = df.columns.tolist()

        # 计算同比增长率（针对季度数据，需要对比去年同期）
        # A股财务数据包含年报(end_date以1231结尾)和季报，混合使用 pct_change(periods=4) 会出错
        # 正确做法：先过滤年报，再按 quarter 分组，最后用 groupby + pct_change(periods=1) 计算同比
        df['end_date_str'] = df['end_date'].astype(str)
        quarterly_df = df[~df['end_date_str'].str.endswith('1231')].copy()
        # 提取季度 (Q1=03, Q2=06, Q3=09, Q4=12)
        quarterly_df['quarter'] = quarterly_df['end_date_str'].str[4:6]
        # 按 quarter+year 排序（确保 Q1对Q1，Q2对Q2）
        quarterly_df = quarterly_df.sort_values(['quarter', 'end_date'], ascending=[True, True])
        if len(quarterly_df) >= 4:
            quarterly_df['revenue_yoy'] = quarterly_df.groupby('quarter')['revenue'].pct_change(periods=1) * 100
            quarterly_df['n_income_yoy'] = quarterly_df.groupby('quarter')['n_income'].pct_change(periods=1) * 100
        # 合并回原数据框，保持原始顺序
        df = df.merge(
            quarterly_df[['end_date', 'revenue_yoy', 'n_income_yoy']],
            on='end_date',
            how='left'
        )

        # 输出表头
        header = f"{'Report Date':<12} {'Revenue':>15} {'Rev YoY%':>10} {'Net Income':>15} {'NI YoY%':>10}"
        lines.append(header)
        lines.append("-" * 70)

        # 输出数据行
        for _, row in df.head(12).iterrows():  # 最近12期
            end_date = str(row.get('end_date', 'N/A'))
            revenue = row.get('revenue', 0)
            n_income = row.get('n_income', 0)
            rev_yoy = row.get('revenue_yoy')
            ni_yoy = row.get('n_income_yoy')

            revenue_str = f"{float(revenue)/1e8:.2f}亿" if revenue is not None else "N/A"
            n_income_str = f"{float(n_income)/1e8:.2f}亿" if n_income is not None else "N/A"
            rev_yoy_str = f"{float(rev_yoy):.1f}%" if rev_yoy is not None and not pd.isna(rev_yoy) else "N/A"
            ni_yoy_str = f"{float(ni_yoy):.1f}%" if ni_yoy is not None and not pd.isna(ni_yoy) else "N/A"

            lines.append(f"{end_date:<12} {revenue_str:>15} {rev_yoy_str:>10} {n_income_str:>15} {ni_yoy_str:>10}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving income statement for {ticker}: {str(e)}"


def get_news(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"]
):
    """Return stable placeholder text for unsupported ticker news."""
    try:
        normalized_ticker = _convert_symbol(ticker)
    except ValueError as exc:
        return f"Error retrieving news for {ticker}: {str(exc)}"
    return (
        f"Company news data is not available via Tushare citydata mode for "
        f"'{normalized_ticker}' between {start_date} and {end_date}."
    )


def get_global_news(
    curr_date: Annotated[str, "current date YYYY-MM-DD"],
    look_back_days: Annotated[int, "days to look back"] = 7,
    limit: Annotated[int, "max number of news"] = 10
):
    """Return stable placeholder text for unsupported macro news."""
    return (
        "Global market news is not available via Tushare citydata mode. "
        f"Requested date: {curr_date}, look_back_days: {look_back_days}, limit: {limit}."
    )


@dataflow_tool("lynch_metrics")
def get_share_repurchase(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """获取股票回购历史数据（管理层信心信号）"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.repurchase(ts_code=ts_code, limit=20)

        # 过滤出该股票的数据
        df = df[df['ts_code'] == ts_code]

        if df.empty:
            return f"No share repurchase data found for '{ticker}'"

        lines = []
        lines.append(f"# Share Repurchase History for {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)")
        lines.append("# 注意：回购数据反映管理层对公司价值的信心\n")

        total_vol = 0
        total_amount = 0

        for _, row in df.iterrows():
            ann_date = row.get('ann_date', 'N/A')
            end_date = row.get('end_date', 'N/A')
            vol = row.get('vol', 0)  # 回购数量（股）
            amount = row.get('amount', 0)  # 回购金额（元）
            proc = row.get('proc', 0)  # 回购进度

            if vol and float(vol) > 0:
                vol_str = f"{float(vol)/10000:.2f}万股"
                total_vol += float(vol)
            else:
                vol_str = "N/A"

            if amount and float(amount) > 0:
                amount_str = f"{float(amount)/10000:.2f}万元"
                total_amount += float(amount)
            else:
                amount_str = "N/A"

            proc_str = str(proc) if proc else "N/A"

            lines.append(f"公告日: {ann_date}, 完成日: {end_date}, 数量: {vol_str}, 金额: {amount_str}, 进度: {proc_str}")

        # 添加汇总
        if total_vol > 0 or total_amount > 0:
            lines.append("")
            lines.append("--- 汇总 ---")
            if total_vol > 0:
                lines.append(f"累计回购数量: {total_vol/10000:.2f}万股")
            if total_amount > 0:
                lines.append(f"累计回购金额: {total_amount/10000:.2f}万元")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving repurchase data for {ticker}: {str(e)}"


@dataflow_tool("lynch_metrics")
def get_yoy_growth(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """获取营收和净利润同比增长率数据"""
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
        lines.append(f"# YoY Growth Data for {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)")
        lines.append("# 注意：以下数据为'年初至报告期末'累计值同比，非单季值，非 TTM\n")
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


@dataflow_tool("lynch_metrics")
def get_lynch_metrics(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None
):
    """获取 Peter Lynch 分析所需的关键指标

    包括：
    - PEG Ratio (PE / EPS增长率)
    - 股票分类依据
    - 增长趋势评估
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
            return f"No data available for Lynch metrics for '{ticker}'"

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
        pb = db.get('pb', 0)
        close = db.get('close', 0)
        total_mv = db.get('total_mv', 0)

        lines = []
        lines.append(f"# Peter Lynch Metrics for {normalized_ticker}")
        lines.append("# Data source: Tushare (citydata.club proxy)\n")

        lines.append("## 估值指标")
        if close:
            lines.append(f"股价: {float(close):.2f} 元")
        if pe_ttm and float(pe_ttm) > 0:
            lines.append(f"P/E (TTM): {float(pe_ttm):.2f}")
        if pb and float(pb) > 0:
            lines.append(f"P/B: {float(pb):.2f}")
        if total_mv:
            lines.append(f"市值: {float(total_mv)/10000:.2f} 亿元")

        lines.append("")
        lines.append("## 增长率")
        if ni_yoy is not None and not pd.isna(ni_yoy):
            lines.append(f"净利润增长率 (年报): {float(ni_yoy):.1f}%")

            # 计算 PEG
            if pe_ttm and float(pe_ttm) > 0 and float(ni_yoy) > 0:
                peg = float(pe_ttm) / float(ni_yoy)
                lines.append("")
                lines.append("## PEG Ratio")
                lines.append(f"PEG = PE / 净利润增长率 = {float(pe_ttm):.2f} / {float(ni_yoy):.1f} = {peg:.2f}")

                # PEG 评估
                if peg < 0.5:
                    lines.append("PEG < 0.5: 显著低估（潜在 10x 股候选）")
                elif peg < 1:
                    lines.append("PEG < 1: 低估，值得深入研究")
                elif peg < 1.5:
                    lines.append("PEG 1-1.5: 合理估值")
                elif peg < 2:
                    lines.append("PEG 1.5-2: 略高估")
                else:
                    lines.append("PEG > 2: 高估，需谨慎")
        else:
            lines.append("净利润增长率: 数据不足，无法计算")
            lines.append("PEG: 无法计算（缺少增长率数据）")

        lines.append("")
        lines.append("## 股票分类参考")
        lines.append("根据 Lynch 的 6 种分类标准：")

        # 基于市值判断
        if total_mv:
            mv = float(total_mv) / 10000
            if mv < 50:
                lines.append(f"- 市值 {mv:.2f}亿 < 50亿: 可能是 Fast Grower（快速成长型）")
            elif mv < 200:
                lines.append(f"- 市值 {mv:.2f}亿 50-200亿: 可能是 Stalwart（稳定增长型）")
            else:
                lines.append(f"- 市值 {mv:.2f}亿 > 200亿: 可能是 Slow Grower（缓慢增长型）")

        lines.append("")
        lines.append("## Lynch 13 条选股标准参考")
        lines.append("1. 公司名字枯燥乏味?")
        lines.append("2. 公司业务枯燥乏味?")
        lines.append("3. 公司业务令人反感?")
        lines.append("4. 公司是从大公司分拆出来的?")
        lines.append("5. 机构投资者少，分析师不跟踪?")
        lines.append("6. 公司被谣言包围（谣言通常是假的）?")
        lines.append("7. 公司业务让人感到压抑?")
        lines.append("8. 公司处于零增长行业中?")
        lines.append("9. 公司有一个利基（细分市场壁垒）?")
        lines.append("10. 人们要不断购买公司的产品?")
        lines.append("11. 公司是技术用户（不是纯技术股）?")
        lines.append("12. 公司内部人在买入自家股票?")
        lines.append("13. 公司在回购股票?")

        lines.append("")
        lines.append("--- 需要人工判断以上标准 ---")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving Lynch metrics for {ticker}: {str(e)}"
