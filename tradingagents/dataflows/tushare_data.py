"""
Tushare 数据接口 - 使用 citydata.club 代理

与 y_finance.py 保持相同接口，实现平滑切换。
"""

from typing import Annotated
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import os
import sys

from .a_share_symbols import normalize_a_share_symbol

# 添加 srcMO 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "srcMO"))

try:
    from tushare_proxy import pro_api
except ImportError:
    pro_api = None

# 加载环境变量
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
        header += f"# Data source: Tushare (citydata.club proxy)\n"
        header += f"# 注意：Volume 单位为手(每手100股)，Amount 单位为千元\n\n"

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
    curr_date: Annotated[str, "current date"] = None
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

        # 按报告期降序排列，取最近的
        df = df.sort_values("end_date", ascending=False)

        if freq == "quarterly":
            df = df.head(8)  # 最近 8 个季度
        else:
            df = df.head(4)  # 最近 4 年

        csv_string = df.to_csv(index=False)

        header = f"# Balance Sheet data for {normalized_ticker} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: Tushare (citydata.club proxy)\n"
        header += f"# 注意：金额单位为元，如需亿元请除以1e8\n\n"

        return header + csv_string

    except Exception as e:
        return f"Error retrieving balance sheet for {ticker}: {str(e)}"


def get_cashflow(
    ticker: Annotated[str, "ticker symbol of the company"],
    freq: Annotated[str, "frequency of data: 'annual' or 'quarterly'"] = "quarterly",
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"] = None
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
        header += f"# Data source: Tushare (citydata.club proxy)\n"
        header += f"# 注意：金额单位为元，如需亿元请除以1e8\n\n"

        return header + csv_string

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
