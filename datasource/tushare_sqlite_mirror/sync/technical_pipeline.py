"""
sync/technical_pipeline.py - 技术分析数据同步管道

数据流：
1. price_daily (从 tushare API)
2. trend_ma_daily (从 stockstats)
3. momentum_volatility_daily (从 stockstats)
4. technical_labels_daily (规则引擎)

参考：docs/market_prd.md
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from datasource.tushare import get_stock_data, get_indicators
from datasource.tushare.symbols import normalize_a_share_symbol
from datasource.tushare.base_provider import INDICATOR_DESCRIPTIONS

from .storage import connect, initialize_database, log_batch, upsert_dataframe


def _resolve_batch_id(batch_id: str | None) -> str:
    """解析批次 ID"""
    if batch_id:
        return batch_id
    return datetime.utcnow().strftime("%Y%m%d")


def sync_price_daily(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    batch_id: str,
) -> int:
    """同步 price_daily 表

    从 tushare API 获取 OHLCV 行情数据。
    如果 API 不可用，从现有 stock_data 表迁移数据。
    """
    ts_code = normalize_a_share_symbol(symbol)

    # 尝试调用 tushare API
    try:
        result = get_stock_data(symbol, start_date, end_date, raw=True)
        if isinstance(result, str) and (result.startswith("Error") or result.startswith("No data") or "No data found" in result):
            # API 返回错误，尝试从 stock_data 表迁移
            result = None
    except Exception:
        # API 异常，尝试从 stock_data 表迁移
        result = None

    if result is not None and hasattr(result, 'empty') and not result.empty:
        # 从 API 数据构建
        df = result
        price_df = pd.DataFrame({
            "symbol": ts_code,
            "trade_date": df["Date"],
            "open": df["Open"],
            "high": df["High"],
            "low": df["Low"],
            "close": df["Close"],
            "vol": df["Volume"],
        })
    else:
        # 从 stock_data 表迁移数据
        price_df = pd.read_sql_query(
            "SELECT ts_code as symbol, Date as trade_date, Open as open, High as high, Low as low, Close as close, Volume as vol FROM stock_data WHERE ts_code = ? AND Date >= ? AND Date <= ?",
            connection,
            params=[ts_code, start_date, end_date],
        )

    if price_df.empty:
        log_batch(
            connection,
            batch_id=batch_id,
            table_name="price_daily",
            status="error",
            row_count=0,
            message="No data available",
        )
        return 0

    count = upsert_dataframe(connection, "price_daily", price_df, batch_id=batch_id)
    log_batch(
        connection,
        batch_id=batch_id,
        table_name="price_daily",
        status="completed",
        row_count=count,
    )
    return count


def sync_trend_ma_daily(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    batch_id: str,
) -> int:
    """同步 trend_ma_daily 表

    从 stockstats 获取均线指标。
    """
    ts_code = normalize_a_share_symbol(symbol)

    # 获取价格数据（用于本地计算缺失的均线）
    price_df = pd.read_sql_query(
        "SELECT * FROM price_daily WHERE symbol = ? AND trade_date >= ? AND trade_date <= ? ORDER BY trade_date ASC",
        connection,
        params=[ts_code, start_date, end_date],
    )

    if price_df.empty:
        return 0

    close = price_df["close"]

    # 本地计算均线（stockstats 不支持的周期）
    sma_5 = close.rolling(window=5, min_periods=5).mean()
    sma_10 = close.rolling(window=10, min_periods=10).mean()
    sma_20 = close.rolling(window=20, min_periods=20).mean()
    sma_50 = close.rolling(window=50, min_periods=50).mean()
    sma_120 = close.rolling(window=120, min_periods=120).mean()
    sma_200 = close.rolling(window=200, min_periods=200).mean()

    # 本地计算 EMA
    ema_10 = close.ewm(span=10, min_periods=10, adjust=False).mean()
    ema_20 = close.ewm(span=20, min_periods=20, adjust=False).mean()
    ema_50 = close.ewm(span=50, min_periods=50, adjust=False).mean()

    # 构建输出 DataFrame（包含 close 用于计算位置标签）
    trend_df = pd.DataFrame({
        "symbol": ts_code,
        "trade_date": price_df["trade_date"],
        "close": close,
        "sma_5": sma_5,
        "sma_10": sma_10,
        "sma_20": sma_20,
        "sma_50": sma_50,
        "sma_120": sma_120,
        "sma_200": sma_200,
        "ema_10": ema_10,
        "ema_20": ema_20,
        "ema_50": ema_50,
    })

    # 计算位置标签
    trend_df["price_vs_sma20"] = trend_df.apply(
        lambda r: _determine_price_vs_ma(r["close"], r["sma_20"]), axis=1
    )
    trend_df["price_vs_sma50"] = trend_df.apply(
        lambda r: _determine_price_vs_ma(r["close"], r["sma_50"]), axis=1
    )
    trend_df["price_vs_sma200"] = trend_df.apply(
        lambda r: _determine_price_vs_ma(r["close"], r["sma_200"]), axis=1
    )
    trend_df["price_vs_ema10"] = trend_df.apply(
        lambda r: _determine_price_vs_ma(r["close"], r["ema_10"]), axis=1
    )

    # 计算均线关系
    trend_df["sma20_vs_sma50"] = trend_df.apply(
        lambda r: _determine_ma_vs_ma(r["sma_20"], r["sma_50"]), axis=1
    )
    trend_df["sma50_vs_sma200"] = trend_df.apply(
        lambda r: _determine_ma_vs_ma(r["sma_50"], r["sma_200"]), axis=1
    )

    # 计算趋势标签
    trend_df["trend_short"] = trend_df.apply(
        lambda r: _determine_trend_short(r["price_vs_ema10"], r["price_vs_sma20"]), axis=1
    )
    trend_df["trend_mid"] = trend_df.apply(
        lambda r: _determine_trend_mid(r["price_vs_sma50"], r["sma20_vs_sma50"]), axis=1
    )
    trend_df["trend_long"] = trend_df.apply(
        lambda r: _determine_trend_long(r["price_vs_sma200"], r["sma50_vs_sma200"]), axis=1
    )

    # 计算交叉信号
    trend_df["cross_signal"] = _detect_cross_signals(trend_df)

    # 移除 close 列（不属于 trend_ma_daily）
    trend_df = trend_df.drop(columns=["close"])

    count = upsert_dataframe(connection, "trend_ma_daily", trend_df, batch_id=batch_id)
    log_batch(
        connection,
        batch_id=batch_id,
        table_name="trend_ma_daily",
        status="completed",
        row_count=count,
    )
    return count


def sync_momentum_volatility_daily(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    batch_id: str,
) -> int:
    """同步 momentum_volatility_daily 表

    从 stockstats 获取动量波动指标。
    """
    ts_code = normalize_a_share_symbol(symbol)

    # 获取价格数据
    price_df = pd.read_sql_query(
        "SELECT * FROM price_daily WHERE symbol = ? AND trade_date >= ? AND trade_date <= ? ORDER BY trade_date ASC",
        connection,
        params=[ts_code, start_date, end_date],
    )

    if price_df.empty:
        return 0

    close = price_df["close"]
    high = price_df["high"]
    low = price_df["low"]
    vol = price_df["vol"]

    # 本地计算 RSI（stockstats 只有 14 周期）
    rsi_6 = _calc_rsi(close, 6)
    rsi_14 = _calc_rsi(close, 14)

    # 本地计算 MACD
    macd_dif, macd_dea, macd_hist = _calc_macd(close, 12, 26, 9)

    # 本地计算 ATR
    atr_14 = _calc_atr(high, low, close, 14)

    # 本地计算均量
    vol_avg_5 = vol.rolling(window=5, min_periods=5).mean()
    vol_avg_20 = vol.rolling(window=20, min_periods=20).mean()

    # 量比
    volume_ratio = vol / vol_avg_20

    # 高低点
    high_20d = high.rolling(window=20, min_periods=1).max()
    low_20d = low.rolling(window=20, min_periods=1).min()
    high_60d = high.rolling(window=60, min_periods=1).max()
    low_60d = low.rolling(window=60, min_periods=1).min()

    # 距离百分比
    distance_to_high_20d_pct = (close - high_20d) / high_20d * 100
    distance_to_low_20d_pct = (close - low_20d) / low_20d * 100
    distance_to_high_60d_pct = (close - high_60d) / high_60d * 100
    distance_to_low_60d_pct = (close - low_60d) / low_60d * 100

    # 振幅
    amplitude = (high - low) / close.shift(1) * 100

    # 构建输出 DataFrame
    momentum_df = pd.DataFrame({
        "symbol": ts_code,
        "trade_date": price_df["trade_date"],
        "rsi_6": rsi_6,
        "rsi_14": rsi_14,
        "macd_dif": macd_dif,
        "macd_dea": macd_dea,
        "macd_hist": macd_hist,
        "atr_14": atr_14,
        "vol_avg_5": vol_avg_5,
        "vol_avg_20": vol_avg_20,
        "volume_ratio": volume_ratio,
        "amplitude": amplitude,
        "high_20d": high_20d,
        "low_20d": low_20d,
        "high_60d": high_60d,
        "low_60d": low_60d,
        "distance_to_high_20d_pct": distance_to_high_20d_pct,
        "distance_to_low_20d_pct": distance_to_low_20d_pct,
        "distance_to_high_60d_pct": distance_to_high_60d_pct,
        "distance_to_low_60d_pct": distance_to_low_60d_pct,
    })

    # 计算状态标签
    momentum_df["rsi_zone"] = momentum_df["rsi_14"].apply(_determine_rsi_zone)

    # MACD 状态（需要前一天的 hist）
    momentum_df["macd_state"] = momentum_df.apply(
        lambda r: _determine_macd_state(r["macd_dif"], r["macd_dea"], r["macd_hist"]), axis=1
    )

    momentum_df["volume_state"] = momentum_df["volume_ratio"].apply(_determine_volume_state)

    # 波动状态（需要前一天的 amplitude 平均值）
    avg_amplitude = amplitude.rolling(window=20, min_periods=20).mean()
    momentum_df["volatility_state"] = momentum_df.apply(
        lambda r: _determine_volatility_state(r["amplitude"], avg_amplitude.get(r.name) if r.name in avg_amplitude.index else None), axis=1
    )

    count = upsert_dataframe(connection, "momentum_volatility_daily", momentum_df, batch_id=batch_id)
    log_batch(
        connection,
        batch_id=batch_id,
        table_name="momentum_volatility_daily",
        status="completed",
        row_count=count,
    )
    return count


def sync_technical_labels_daily(
    connection: sqlite3.Connection,
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    batch_id: str,
) -> int:
    """同步 technical_labels_daily 表

    从前三张事实表生成综合标签。
    """
    ts_code = normalize_a_share_symbol(symbol)

    # 查询趋势数据
    trend_df = pd.read_sql_query(
        "SELECT * FROM trend_ma_daily WHERE symbol = ? AND trade_date >= ? AND trade_date <= ?",
        connection,
        params=[ts_code, start_date, end_date],
    )

    # 查询动量波动数据
    momentum_df = pd.read_sql_query(
        "SELECT * FROM momentum_volatility_daily WHERE symbol = ? AND trade_date >= ? AND trade_date <= ?",
        connection,
        params=[ts_code, start_date, end_date],
    )

    if trend_df.empty or momentum_df.empty:
        return 0

    # 合并数据
    merged = trend_df.merge(momentum_df, on=["symbol", "trade_date"])

    # 构建标签 DataFrame
    labels_df = pd.DataFrame({
        "symbol": merged["symbol"],
        "trade_date": merged["trade_date"],
        # 趋势标签（直接引用）
        "short_trend_label": merged["trend_short"],
        "mid_trend_label": merged["trend_mid"],
        "long_trend_label": merged["trend_long"],
        # 指标标签（直接引用）
        "rsi_label": merged["rsi_zone"],
        "macd_label": merged["macd_state"],
        "volume_label": merged["volume_state"],
        "volatility_label": merged["volatility_state"],
        # 综合标签（需要规则计算）
        "trend_structure_label": merged.apply(_determine_trend_structure, axis=1),
        "risk_level_label": merged.apply(_determine_risk_level, axis=1),
        "summary_signal_label": merged.apply(_determine_summary_signal, axis=1),
    })

    count = upsert_dataframe(connection, "technical_labels_daily", labels_df, batch_id=batch_id)
    log_batch(
        connection,
        batch_id=batch_id,
        table_name="technical_labels_daily",
        status="completed",
        row_count=count,
    )
    return count


def run_technical_pipeline(
    db_path: Path | str,
    *,
    symbol: str,
    start_date: str,
    end_date: str,
    batch_id: str | None = None,
) -> Path:
    """运行技术分析完整同步管道"""
    initialize_database(db_path)
    resolved_batch_id = _resolve_batch_id(batch_id)

    connection = connect(db_path)
    try:
        # 1. 同步 price_daily
        sync_price_daily(
            connection,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            batch_id=resolved_batch_id,
        )

        # 2. 同步 trend_ma_daily（依赖 price_daily）
        sync_trend_ma_daily(
            connection,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            batch_id=resolved_batch_id,
        )

        # 3. 同步 momentum_volatility_daily（依赖 price_daily）
        sync_momentum_volatility_daily(
            connection,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            batch_id=resolved_batch_id,
        )

        # 4. 同步 technical_labels_daily（依赖前三张表）
        sync_technical_labels_daily(
            connection,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            batch_id=resolved_batch_id,
        )

        connection.commit()
        log_batch(
            connection,
            batch_id=resolved_batch_id,
            table_name="technical_pipeline",
            status="completed",
            row_count=0,
            message=f"Technical analysis synced for {symbol}",
        )
        connection.commit()
    except Exception as exc:
        connection.rollback()
        log_batch(
            connection,
            batch_id=resolved_batch_id,
            table_name="technical_pipeline",
            status="failed",
            row_count=0,
            message=str(exc),
        )
        connection.commit()
        raise
    finally:
        connection.close()

    return Path(db_path)


# ========== 技术指标计算函数 ==========

def _calc_rsi(series: pd.Series, window: int) -> pd.Series:
    """计算 RSI"""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=window - 1, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _calc_macd(series: pd.Series, fast: int, slow: int, signal: int):
    """计算 MACD"""
    ema_fast = series.ewm(span=fast, min_periods=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, min_periods=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, min_periods=signal, adjust=False).mean()
    hist = dif - dea
    return dif, dea, hist


def _calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> pd.Series:
    """计算 ATR"""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(com=window - 1, min_periods=window, adjust=False).mean()
    return atr


# ========== 标签判断函数 ==========

def _determine_price_vs_ma(close: float, ma: float, threshold_pct: float = 0.01) -> str:
    """价格相对均线位置"""
    if pd.isna(close) or pd.isna(ma):
        return "unknown"
    ratio = abs(close / ma - 1)
    if ratio <= threshold_pct:
        return "near"
    return "above" if close > ma else "below"


def _determine_ma_vs_ma(short_ma: float, long_ma: float) -> str:
    """均线关系"""
    if pd.isna(short_ma) or pd.isna(long_ma):
        return "unknown"
    ratio = abs(short_ma / long_ma - 1)
    if ratio <= 0.01:
        return "near"
    return "bullish" if short_ma > long_ma else "bearish"


def _determine_trend_short(price_vs_ema10: str, price_vs_sma20: str) -> str:
    """短期趋势"""
    if price_vs_ema10 == "above" and price_vs_sma20 == "above":
        return "bullish"
    if price_vs_ema10 == "below" and price_vs_sma20 == "below":
        return "bearish"
    return "neutral"


def _determine_trend_mid(price_vs_sma50: str, sma20_vs_sma50: str) -> str:
    """中期趋势"""
    if price_vs_sma50 == "above" and sma20_vs_sma50 == "bullish":
        return "bullish"
    if price_vs_sma50 == "below" and sma20_vs_sma50 == "bearish":
        return "bearish"
    return "neutral"


def _determine_trend_long(price_vs_sma200: str, sma50_vs_sma200: str) -> str:
    """长期趋势"""
    if price_vs_sma200 == "above" and sma50_vs_sma200 == "bullish":
        return "bullish"
    if price_vs_sma200 == "below" and sma50_vs_sma200 == "bearish":
        return "bearish"
    return "neutral"


def _detect_cross_signals(trend_df: pd.DataFrame) -> pd.Series:
    """检测金叉死叉"""
    signals = pd.Series("none", index=trend_df.index)

    # SMA20 vs SMA50 交叉
    prev_sma20 = trend_df["sma_20"].shift(1)
    prev_sma50 = trend_df["sma_50"].shift(1)

    golden_cross = (prev_sma20 <= prev_sma50) & (trend_df["sma_20"] > trend_df["sma_50"])
    death_cross = (prev_sma20 >= prev_sma50) & (trend_df["sma_20"] < trend_df["sma_50"])

    signals[golden_cross] = "golden_cross"
    signals[death_cross] = "death_cross"

    return signals


def _determine_rsi_zone(rsi: float) -> str:
    """RSI 分区"""
    if pd.isna(rsi):
        return "unknown"
    if rsi >= 70:
        return "overbought"
    if rsi >= 50:
        return "neutral_strong"
    if rsi > 30:
        return "neutral_weak"
    return "oversold"


def _determine_macd_state(dif: float, dea: float, hist: float) -> str:
    """MACD 状态"""
    if pd.isna(dif) or pd.isna(dea):
        return "unknown"

    if dif > dea and dif > 0:
        return "bullish"
    if dif < dea and dif < 0:
        return "bearish"
    if dif > dea and dif < 0:
        return "weakening_bear"
    return "weakening_bull"


def _determine_volume_state(volume_ratio: float) -> str:
    """成交量状态"""
    if pd.isna(volume_ratio):
        return "unknown"
    if volume_ratio < 0.7:
        return "contracted"
    if volume_ratio <= 1.3:
        return "normal"
    if volume_ratio <= 2.0:
        return "expanded"
    return "spike"


def _determine_volatility_state(amplitude: float, avg_amplitude: float | None) -> str:
    """波动状态"""
    if pd.isna(amplitude):
        return "unknown"

    if avg_amplitude is None or pd.isna(avg_amplitude):
        if amplitude < 2:
            return "low"
        if amplitude < 5:
            return "normal"
        if amplitude < 10:
            return "high"
        return "extreme"

    ratio = amplitude / avg_amplitude
    if ratio < 0.7:
        return "low"
    if ratio <= 1.3:
        return "normal"
    if ratio <= 2.0:
        return "high"
    return "extreme"


def _determine_trend_structure(row: pd.Series) -> str:
    """趋势结构综合标签"""
    short = row.get("trend_short", "neutral")
    mid = row.get("trend_mid", "neutral")
    long = row.get("trend_long", "neutral")

    if short == "bullish" and mid == "bullish" and long == "bullish":
        return "all_bullish"
    if short == "bearish" and mid == "bearish" and long == "bearish":
        return "all_bearish"

    parts = []
    for label, name in [(short, "short"), (mid, "mid"), (long, "long")]:
        parts.append(f"{name}_{label}")
    return "_".join(parts)


def _determine_risk_level(row: pd.Series) -> str:
    """风险等级"""
    rsi_label = row.get("rsi_label", "unknown")
    volatility_label = row.get("volatility_label", "unknown")
    volume_state = row.get("volume_state", "unknown")

    risk_score = 0

    if rsi_label == "overbought":
        risk_score += 2
    elif rsi_label == "oversold":
        risk_score += 1

    if volatility_label == "extreme":
        risk_score += 2
    elif volatility_label == "high":
        risk_score += 1

    if volume_state == "spike":
        risk_score += 1

    if risk_score >= 4:
        return "extreme"
    if risk_score >= 3:
        return "high"
    if risk_score >= 1:
        return "medium"
    return "low"


def _determine_summary_signal(row: pd.Series) -> str:
    """总信号"""
    short_trend = row.get("trend_short", "neutral")
    mid_trend = row.get("trend_mid", "neutral")
    long_trend = row.get("trend_long", "neutral")
    rsi_label = row.get("rsi_label", "unknown")
    macd_label = row.get("macd_label", "unknown")

    bullish_count = sum([
        short_trend == "bullish",
        mid_trend == "bullish",
        long_trend == "bullish",
        macd_label == "bullish",
        rsi_label in ["neutral_strong", "overbought"],
    ])

    bearish_count = sum([
        short_trend == "bearish",
        mid_trend == "bearish",
        long_trend == "bearish",
        macd_label == "bearish",
        rsi_label in ["neutral_weak", "oversold"],
    ])

    if bullish_count >= 4:
        return "strong_bullish"
    if bullish_count >= 3:
        return "bullish"
    if bullish_count >= 2 and bearish_count <= 1:
        return "neutral_to_bullish"
    if bearish_count >= 4:
        return "strong_bearish"
    if bearish_count >= 3:
        return "bearish"
    if bearish_count >= 2 and bullish_count <= 1:
        return "neutral_to_bearish"
    return "neutral"