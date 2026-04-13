"""
Tushare 数据接口 - 使用 citydata.club 代理

与 y_finance.py 保持相同接口，实现平滑切换。
"""

from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import os

from .symbols import normalize_a_share_symbol
from .proxy import pro_api

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

        header = "[Tool: get_stock_data] - 原始价格数据\n"
        header += f"# Stock data for {normalized_symbol} from {start_date} to {end_date}\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare (citydata.club proxy)\n"
        header += f"# 注意：Volume 单位为手(每手100股)，Amount 单位为千元\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving data for {symbol}: {str(e)}"


def get_stock_stats_indicators_window(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
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

    # 指标最小数据窗口需求（确保计算准确）
    # 注意：stockstats 需要足够的历史数据来初始化计算
    min_data_window = {
        "close_50_sma": 150,   # 50 SMA 需要 ~150 天确保准确
        "close_200_sma": 250,  # 200 SMA 需要更长历史数据
        "close_10_ema": 50,    # 10 EMA 需要足够数据初始化
        "macd": 50,            # MACD 需要 EMA 计算
        "macds": 50,
        "macdh": 50,
        "rsi": 50,             # RSI 计算需要足够历史数据
        "boll": 50,            # Bollinger 用 20 SMA + 标准差
        "boll_ub": 50,
        "boll_lb": 50,
        "atr": 50,             # ATR 计算需要足够数据
        "vwma": 50,
        "mfi": 50,
    }

    if indicator not in best_ind_params:
        raise ValueError(
            f"Indicator {indicator} is not supported. Please choose from: {list(best_ind_params.keys())}"
        )

    # 自动扩展数据窗口以满足指标最小需求
    min_required = min_data_window.get(indicator, 30)
    effective_look_back = max(look_back_days, min_required)

    # 计算日期范围
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=effective_look_back)

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
            f"[Tool: get_indicators] [Indicator: {indicator}]\n"
            f"## {indicator} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n"
            f"# 数据窗口: {effective_look_back} 天 (确保指标计算准确)\n\n"
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
    curr_date: Annotated[str, "current date"] = None
):
    """获取公司基本面数据"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()

        # 获取基本信息
        all_basic = pro.stock_basic()
        basic = all_basic[all_basic['ts_code'] == ts_code]

        # 获取财务指标
        indicator = pro.fina_indicator(ts_code=ts_code)

        # 获取市值和估值数据
        today_str = datetime.now().strftime("%Y%m%d")
        daily_basic = pro.daily_basic(ts_code=ts_code, start_date=today_str, end_date=today_str)
        if daily_basic.empty:
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
            if total_mv:
                lines.append(f"Total Market Cap (亿元): {float(total_mv) / 10000:.2f}")
            if circ_mv:
                lines.append(f"Circulating Market Cap (亿元): {float(circ_mv) / 10000:.2f}")
            if total_share:
                lines.append(f"Total Shares (亿股): {float(total_share) / 10000:.2f}")

        # 添加收入和利润数据（单位：亿元）
        if not income.empty:
            inc = income.iloc[0]
            revenue = inc.get('revenue', 0)
            n_income = inc.get('n_income', 0)
            if revenue:
                lines.append(f"Revenue (亿元): {float(revenue) / 1e8:.2f}")
            if n_income:
                lines.append(f"Net Income (亿元): {float(n_income) / 1e8:.2f}")

        # 添加现金流数据（单位：亿元）
        if not cashflow.empty:
            cf = cashflow.iloc[0]
            ocf = cf.get('n_cashflow_act', 0)
            if ocf:
                lines.append(f"Operating Cash Flow (亿元): {float(ocf) / 1e8:.2f}")

        # 添加股息历史数据
        try:
            dividend_df = pro.dividend(ts_code=ts_code, limit=20)
            if not dividend_df.empty:
                lines.append("")
                lines.append("# Dividend History (分红记录)")

                # 按 end_date 去重，优先显示"实施"状态
                dividend_df = dividend_df.sort_values('ann_date', ascending=False)
                # 过滤只显示"实施"状态的记录（实际执行的分红）
                implemented = dividend_df[dividend_df['div_proc'] == '实施'].copy()
                if implemented.empty:
                    # 如果没有实施记录，显示最新的预案
                    implemented = dividend_df.drop_duplicates(subset=['end_date'], keep='first')

                for _, div_row in implemented.head(6).iterrows():
                    end_date = str(div_row.get('end_date', 'N/A'))
                    year = end_date[:4]
                    period = "年报" if end_date.endswith('1231') else "半年报" if end_date.endswith('0630') else ""
                    cash = div_row.get('cash_div', 0)
                    stk = div_row.get('stk_div', 0)
                    pay = div_row.get('pay_date', 'N/A')
                    ex = div_row.get('ex_date', 'N/A')

                    # cash_div 单位是"元/股"，显示时转换为"每10股派现X元"
                    cash_str = f"每10股派现{float(cash)*10:.2f}元" if cash and float(cash) > 0 else ""
                    stk_str = f"每10股转增{float(stk):.1f}股" if stk and float(stk) > 0 else ""
                    pay_str = f", 派息日: {pay}" if pay and str(pay) != 'None' else ""
                    ex_str = f", 除息日: {ex}" if ex and str(ex) != 'None' else ""

                    div_info = f"{cash_str} {stk_str}".strip()
                    if not div_info:
                        div_info = "无分红"
                    lines.append(f"  {year}年{period}: {div_info}{pay_str}{ex_str}")
        except Exception:
            pass

        header = f"# Company Fundamentals for {normalized_ticker}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare (citydata.club proxy)\n"
        header += f"# 注意：金额单位已转换为亿元，比率单位为%\n\n"

        return header + "\n".join(lines)

    except Exception as e:
        return f"Error retrieving fundamentals for {ticker}: {str(e)}"


def get_balance_sheet(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
):
    """获取资产负债表"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.balancesheet(ts_code=ts_code)

        if df.empty:
            return f"No balance sheet data found for symbol '{ticker}'"

        df = df.sort_values("end_date", ascending=False)

        if freq == "quarterly":
            df = df.head(8)
        else:
            df = df.head(4)

        csv_string = df.to_csv(index=False)

        header = f"# Balance Sheet data for {normalized_ticker} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare (citydata.club proxy)\n"
        header += f"# 注意：金额单位为元，如需亿元请除以1e8\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


def _calculate_single_quarter_cashflow(df):
    """从累计值计算单季现金流值

    Args:
        df: 现金流数据，包含 end_date, end_type, n_cashflow_act, n_cashflow_inv_act, n_cash_flows_fnc_act

    Returns:
        dict: {end_date: {'ocf': 单季经营现金流, 'icf': 单季投资现金流, 'fcf': 单季筹资现金流}}
    """
    df = df.copy()
    df['year'] = df['end_date'].astype(str).str[:4]

    single_q_values = {}

    for year in df['year'].unique():
        year_df = df[df['year'] == year]

        # Q1 (end_type=1) 本身就是单季
        q1 = year_df[year_df['end_type'] == '1']
        if not q1.empty:
            q1_row = q1.iloc[0]
            q1_date = q1_row['end_date']
            single_q_values[q1_date] = {
                'ocf': q1_row.get('n_cashflow_act', 0) or 0,
                'icf': q1_row.get('n_cashflow_inv_act', 0) or 0,
                'fcf': q1_row.get('n_cash_flows_fnc_act', 0) or 0
            }

        # Q2单季 = Q2累计 - Q1累计
        q2 = year_df[year_df['end_type'] == '2']
        if not q2.empty and not q1.empty:
            q2_row = q2.iloc[0]
            q2_date = q2_row['end_date']
            q1_ocf = q1.iloc[0].get('n_cashflow_act', 0) or 0
            q1_icf = q1.iloc[0].get('n_cashflow_inv_act', 0) or 0
            q1_fcf = q1.iloc[0].get('n_cash_flows_fnc_act', 0) or 0
            q2_ocf = q2_row.get('n_cashflow_act', 0) or 0
            q2_icf = q2_row.get('n_cashflow_inv_act', 0) or 0
            q2_fcf = q2_row.get('n_cash_flows_fnc_act', 0) or 0
            single_q_values[q2_date] = {
                'ocf': q2_ocf - q1_ocf,
                'icf': q2_icf - q1_icf,
                'fcf': q2_fcf - q1_fcf
            }

        # Q3单季 = Q3累计 - Q2累计
        q3 = year_df[year_df['end_type'] == '3']
        if not q3.empty and not q2.empty:
            q3_row = q3.iloc[0]
            q3_date = q3_row['end_date']
            q2_ocf = q2.iloc[0].get('n_cashflow_act', 0) or 0
            q2_icf = q2.iloc[0].get('n_cashflow_inv_act', 0) or 0
            q2_fcf = q2.iloc[0].get('n_cash_flows_fnc_act', 0) or 0
            q3_ocf = q3_row.get('n_cashflow_act', 0) or 0
            q3_icf = q3_row.get('n_cashflow_inv_act', 0) or 0
            q3_fcf = q3_row.get('n_cash_flows_fnc_act', 0) or 0
            single_q_values[q3_date] = {
                'ocf': q3_ocf - q2_ocf,
                'icf': q3_icf - q2_icf,
                'fcf': q3_fcf - q2_fcf
            }

        # 年报/Q4单季 = 年报累计 - Q3累计
        annual = year_df[year_df['end_type'] == '4']
        if not annual.empty and not q3.empty:
            annual_row = annual.iloc[0]
            annual_date = annual_row['end_date']
            q3_ocf = q3.iloc[0].get('n_cashflow_act', 0) or 0
            q3_icf = q3.iloc[0].get('n_cashflow_inv_act', 0) or 0
            q3_fcf = q3.iloc[0].get('n_cash_flows_fnc_act', 0) or 0
            annual_ocf = annual_row.get('n_cashflow_act', 0) or 0
            annual_icf = annual_row.get('n_cashflow_inv_act', 0) or 0
            annual_fcf = annual_row.get('n_cash_flows_fnc_act', 0) or 0
            single_q_values[annual_date] = {
                'ocf': annual_ocf - q3_ocf,
                'icf': annual_icf - q3_icf,
                'fcf': annual_fcf - q3_fcf
            }

    return single_q_values


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
):
    """获取现金流量表 - 同时返回累计值和单季值"""
    normalized_ticker = _convert_symbol(ticker)
    ts_code = normalized_ticker

    try:
        pro = _get_pro()
        df = pro.cashflow(ts_code=ts_code)

        if df.empty:
            return f"No cash flow data found for symbol '{ticker}'"

        # 去重处理 - 优先使用修正后的数据 (update_flag=1)
        if 'update_flag' in df.columns:
            df['_sort_key'] = df['update_flag'].astype(int) * 10000000000 + df['ann_date'].astype(int)
            df = df.sort_values('_sort_key', ascending=False)
            df = df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')
            df = df.drop(columns=['_sort_key'])
        else:
            df = df.sort_values('ann_date', ascending=False)
            df = df.drop_duplicates(subset=['end_date', 'end_type'], keep='first')

        # 计算单季值
        single_q_values = _calculate_single_quarter_cashflow(df)

        df = df.sort_values("end_date", ascending=False)

        if freq == "quarterly":
            df_display = df.head(8)
        else:
            df_display = df.head(4)

        lines = []
        lines.append(f"# Cash Flow data for {normalized_ticker} ({freq})")
        lines.append("# 数据口径：累计值（年初至报告期末）+ 单季值（计算得出）")
        lines.append("# 来源：Tushare 最新报表，不含会计差错更正后数据")
        lines.append("# 金额单位：亿元\n")

        # 现金流数据表
        lines.append(f"{'报告期':<10} {'类型':>4} {'累计经营(亿)':>12} {'单季经营(亿)':>12} {'累计投资(亿)':>12} {'单季投资(亿)':>12} {'累计筹资(亿)':>12} {'单季筹资(亿)':>12}")
        lines.append("-" * 95)

        period_type_map = {'1': 'Q1', '2': 'Q2', '3': 'Q3', '4': '年报'}
        for _, row in df_display.iterrows():
            period = str(row.get('end_date', 'N/A'))[:8]
            end_type = str(row.get('end_type', 'N/A'))
            period_type = period_type_map.get(end_type, end_type)

            # 累计值
            ocf_cum = row.get('n_cashflow_act', 0) or 0
            icf_cum = row.get('n_cashflow_inv_act', 0) or 0
            fcf_cum = row.get('n_cash_flows_fnc_act', 0) or 0

            # 单季值
            end_date = row.get('end_date')
            single_q = single_q_values.get(end_date, {'ocf': 0, 'icf': 0, 'fcf': 0})
            ocf_single = single_q['ocf']
            icf_single = single_q['icf']
            fcf_single = single_q['fcf']

            ocf_cum_str = f"{float(ocf_cum)/1e8:.2f}"
            ocf_single_str = f"{float(ocf_single)/1e8:.2f}"
            icf_cum_str = f"{float(icf_cum)/1e8:.2f}"
            icf_single_str = f"{float(icf_single)/1e8:.2f}"
            fcf_cum_str = f"{float(fcf_cum)/1e8:.2f}"
            fcf_single_str = f"{float(fcf_single)/1e8:.2f}"

            lines.append(f"{period:<10} {period_type:>4} {ocf_cum_str:>12} {ocf_single_str:>12} {icf_cum_str:>12} {icf_single_str:>12} {fcf_cum_str:>12} {fcf_single_str:>12}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving cash flow for {ticker}: {str(e)}"


def get_income_statement(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
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
        header += f"# Data source: Tushare (citydata.club proxy)\n"
        header += f"# 注意：金额单位为元，如需亿元请除以1e8\n\n"

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


