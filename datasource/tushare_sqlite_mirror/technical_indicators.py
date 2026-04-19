"""Lightweight technical indicator calculations used by the SQLite mirror."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14) -> pd.Series:
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    direction = typical_price.diff()
    positive = money_flow.where(direction > 0, 0.0)
    negative = money_flow.where(direction < 0, 0.0).abs()
    positive_sum = positive.rolling(period, min_periods=period).sum()
    negative_sum = negative.rolling(period, min_periods=period).sum()
    ratio = positive_sum / negative_sum.replace(0, np.nan)
    return 100 - (100 / (1 + ratio))


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    typical_price = (high + low + close) / 3
    sma = typical_price.rolling(period, min_periods=period).mean()
    mean_dev = typical_price.rolling(period, min_periods=period).apply(
        lambda values: np.mean(np.abs(values - values.mean())),
        raw=False,
    )
    return (typical_price - sma) / (0.015 * mean_dev.replace(0, np.nan))


def _wr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    highest_high = high.rolling(period, min_periods=period).max()
    lowest_low = low.rolling(period, min_periods=period).min()
    denominator = (highest_high - lowest_low).replace(0, np.nan)
    return -100 * ((highest_high - close) / denominator)


def _kdj(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    lowest_low = low.rolling(period, min_periods=period).min()
    highest_high = high.rolling(period, min_periods=period).max()
    rsv = ((close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)) * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    previous_close = close.shift(1)
    ranges = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )
    true_range = ranges.max(axis=1)
    return true_range.rolling(period, min_periods=period).mean()


def calculate_indicator_frame(df: pd.DataFrame, indicator: str) -> pd.DataFrame:
    """Return a copy of the OHLCV frame with the requested indicator column."""
    result = df.copy()
    close = result["Close"].astype(float)
    high = result["High"].astype(float)
    low = result["Low"].astype(float)
    volume = result["Volume"].astype(float)

    if indicator == "close_10_ema":
        result[indicator] = close.ewm(span=10, adjust=False).mean()
    elif indicator == "close_50_sma":
        result[indicator] = close.rolling(50, min_periods=50).mean()
    elif indicator == "close_200_sma":
        result[indicator] = close.rolling(200, min_periods=200).mean()
    elif indicator in {"macd", "macds", "macdh"}:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        result["macd"] = macd
        result["macds"] = signal
        result["macdh"] = histogram
    elif indicator == "rsi":
        result[indicator] = _rsi(close)
    elif indicator == "mfi":
        result[indicator] = _mfi(high, low, close, volume)
    elif indicator == "cci":
        result[indicator] = _cci(high, low, close)
    elif indicator == "wr":
        result[indicator] = _wr(high, low, close)
    elif indicator in {"kdjk", "kdjd", "kdjj"}:
        k, d, j = _kdj(high, low, close)
        result["kdjk"] = k
        result["kdjd"] = d
        result["kdjj"] = j
    elif indicator in {"boll", "boll_ub", "boll_lb"}:
        middle = close.rolling(20, min_periods=20).mean()
        std = close.rolling(20, min_periods=20).std(ddof=0)
        result["boll"] = middle
        result["boll_ub"] = middle + (std * 2)
        result["boll_lb"] = middle - (std * 2)
    elif indicator == "atr":
        result[indicator] = _atr(high, low, close)
    elif indicator == "vwma":
        result[indicator] = (
            (close * volume).rolling(14, min_periods=14).sum()
            / volume.rolling(14, min_periods=14).sum()
        )
    else:
        raise ValueError(f"Unsupported indicator: {indicator}")

    return result
