from typing import Annotated
from .interface import route_to_vendor
from tradingagents.dataflows.decorators import auto_tool


@auto_tool()
def get_stock_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve stock price data (OHLCV) for a given ticker symbol.
    Uses the configured core_stock_apis vendor.
    Args:
        symbol (str): Ticker symbol of the company, e.g. AAPL, TSM
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted dataframe containing the stock price data for the specified ticker symbol in the specified date range.
    """
    return route_to_vendor("get_stock_data", symbol, start_date, end_date)


# ========== 技术分析数据（预处理） ==========

@auto_tool()
def get_price_daily(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"],
) -> str:
    """
    技术分析行情数据 - 获取 OHLCV 基础数据用于技术分析。
    包含开盘价、最高价、最低价、收盘价、成交量。
    数据来源：price_daily 表（预处理后的技术分析专用数据）。
    """
    return route_to_vendor("get_price_daily", symbol, start_date, end_date)


@auto_tool()
def get_trend_ma_daily(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"],
) -> str:
    """
    均线趋势数据 - 获取移动平均线和趋势标签。
    包含 SMA(5/10/20/60)、EMA(12/26) 以及自动生成的趋势标签。
    用于判断股价短期、中期、长期趋势方向。
    """
    return route_to_vendor("get_trend_ma_daily", symbol, start_date, end_date)


@auto_tool()
def get_momentum_volatility_daily(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"],
) -> str:
    """
    动量波动数据 - 获取动量指标、波动率指标和状态标签。
    包含 RSI(6/12/24)、MACD、ATR(14) 以及超买超卖、MACD 信号等状态标签。
    用于判断股价动量强弱和波动风险。
    """
    return route_to_vendor("get_momentum_volatility_daily", symbol, start_date, end_date)


@auto_tool()
def get_technical_labels_daily(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "start date YYYY-MM-DD"],
    end_date: Annotated[str, "end date YYYY-MM-DD"],
) -> str:
    """
    技术标签汇总 - 获取综合趋势、动量、风险标签。
    整合均线趋势、动量状态、波动风险的判断结果。
    提供整体技术面评估：趋势方向、动量强弱、风险等级。
    """
    return route_to_vendor("get_technical_labels_daily", symbol, start_date, end_date)
