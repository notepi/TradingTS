from typing import Annotated
from .interface import route_to_vendor
from tradingagents.dataflows.decorators import auto_tool

@auto_tool()
def get_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back, default 120"] = 120,
) -> str:
    """
    Retrieve technical indicators for a given ticker symbol.

    Supported indicators (tushare):
    - Moving averages: close_10_ema, close_50_sma, close_200_sma
    - MACD: macd, macds, macdh
    - Momentum: rsi, mfi, cci, wr
    - KDJ: kdjk, kdjd, kdjj
    - Bollinger: boll, boll_ub, boll_lb
    - Volatility: atr, vwma

    Usage guide:
    - Trend analysis: close_50_sma, close_200_sma, boll
    - Momentum: rsi, macd, kdjk
    - Overbought/oversold: rsi (>70 overbought, <30 oversold), wr, cci
    - Volatility: atr, boll (band narrowing = volatility expanding soon)

    Args:
        symbol: Ticker symbol of the company, e.g. AAPL, TSM
        indicator: Single indicator name (e.g., 'rsi', 'macd'). Call once per indicator.
        curr_date: The current trading date, YYYY-mm-dd
        look_back_days: How many days to look back, default 120

    Returns:
        Indicator values with field explanations
    """
    # LLMs sometimes pass multiple indicators as a comma-separated string;
    # split and process each individually.
    indicators = [i.strip().lower() for i in indicator.split(",") if i.strip()]
    results = []
    for ind in indicators:
        try:
            results.append(route_to_vendor("get_indicators", symbol, ind, curr_date, look_back_days))
        except ValueError as e:
            results.append(str(e))
    return "\n\n".join(results)