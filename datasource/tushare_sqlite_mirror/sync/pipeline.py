from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

from tushare_sqlite_mirror.technical_indicators import calculate_indicator_frame

from .storage import connect, initialize_database, log_batch, upsert_dataframe

RAW_TABLES = [
    "stock_basic",
    "daily",
    "daily_basic",
    "income",
    "balancesheet",
    "cashflow",
    "fina_indicator",
    "dividend",
    "stk_rewards",
]
TECHNICAL_INDICATORS = [
    "close_10_ema",
    "close_50_sma",
    "close_200_sma",
    "macd",
    "macds",
    "macdh",
    "rsi",
    "mfi",
    "cci",
    "wr",
    "kdjk",
    "kdjd",
    "kdjj",
    "boll",
    "boll_ub",
    "boll_lb",
    "atr",
    "vwma",
]


def _resolve_client(client: object | None) -> object:
    if client is not None:
        return client
    from .client import CityDataClient

    return CityDataClient()


def _resolve_batch_id(batch_id: str | None) -> str:
    if batch_id:
        return batch_id
    env_batch = os.getenv("SYNC_BATCH_DATE")
    if env_batch:
        return env_batch
    return datetime.utcnow().strftime("%Y%m%d")


def _resolve_as_of_date(as_of_date: str | None) -> datetime:
    if as_of_date:
        return datetime.strptime(as_of_date, "%Y%m%d")
    env_date = os.getenv("SYNC_BATCH_DATE")
    if env_date:
        return datetime.strptime(env_date, "%Y%m%d")
    return datetime.utcnow()


def run_bootstrap(db_path: Path | str, client: object | None = None) -> Path:
    _ = client
    initialize_database(db_path)
    return Path(db_path)


def _upsert_raw(
    connection,
    *,
    table_name: str,
    frame: pd.DataFrame,
    batch_id: str,
) -> int:
    normalized = _normalize_raw_frame(table_name, frame)
    return upsert_dataframe(connection, f"{table_name}_raw", normalized, batch_id=batch_id)


def _infer_end_type(end_date: object) -> str:
    value = str(end_date or "").replace("-", "").replace("/", "")
    if value.endswith("0331"):
        return "1"
    if value.endswith("0630"):
        return "2"
    if value.endswith("0930"):
        return "3"
    if value.endswith("1231"):
        return "4"
    return ""


def _resolve_incremental_start(
    connection,
    *,
    raw_table_name: str,
    ts_code: str,
    date_column: str,
) -> str:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (raw_table_name,),
    ).fetchone()
    if exists is None:
        return ""
    row = connection.execute(
        f'SELECT MAX("{date_column}") FROM "{raw_table_name}" WHERE ts_code = ?',
        (ts_code,),
    ).fetchone()
    if not row or row[0] in (None, ""):
        return ""
    value = str(row[0]).replace("-", "").replace("/", "")
    if len(value) != 8 or not value.isdigit():
        return ""
    return value


def _normalize_raw_frame(table_name: str, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    normalized = frame.copy()
    if table_name in {"income", "balancesheet", "cashflow", "fina_indicator"}:
        if "end_type" not in normalized.columns and "end_date" in normalized.columns:
            normalized["end_type"] = normalized["end_date"].map(_infer_end_type)
        if "update_flag" not in normalized.columns:
            normalized["update_flag"] = ""

    return normalized


def _fetch_stock_basic(client: object, ts_codes: list[str] | None) -> pd.DataFrame:
    if ts_codes:
        frames = []
        for ts_code in ts_codes:
            frame = client.fetch("stock_basic", ts_code=ts_code)
            if not frame.empty:
                frames.append(frame)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["ts_code"], keep="last")

    return client.fetch("stock_basic", list_status="L")


def _sync_stock_basic(connection, client: object, batch_id: str, ts_codes: list[str] | None) -> list[str]:
    frame = _fetch_stock_basic(client, ts_codes)
    count = _upsert_raw(connection, table_name="stock_basic", frame=frame, batch_id=batch_id)
    log_batch(connection, batch_id=batch_id, table_name="stock_basic_raw", status="completed", row_count=count)
    if frame.empty:
        return []
    return frame["ts_code"].dropna().astype(str).tolist()


def _sync_market_table(
    connection,
    client: object,
    *,
    table_name: str,
    ts_codes: list[str],
    batch_id: str,
    as_of_date: datetime,
) -> None:
    total_rows = 0
    start_date = (as_of_date - timedelta(days=365)).strftime("%Y%m%d")
    end_date = as_of_date.strftime("%Y%m%d")

    for ts_code in ts_codes:
        frame = client.fetch(
            table_name,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )
        total_rows += _upsert_raw(connection, table_name=table_name, frame=frame, batch_id=batch_id)

    log_batch(
        connection,
        batch_id=batch_id,
        table_name=f"{table_name}_raw",
        status="completed",
        row_count=total_rows,
    )


def _sync_financial_table(
    connection,
    client: object,
    *,
    table_name: str,
    ts_codes: list[str],
    batch_id: str,
    as_of_date: datetime,
) -> None:
    total_rows = 0
    for ts_code in ts_codes:
        # 用 ann_date（公告日期）做增量过滤，能捕获财报修正
        start_date = _resolve_incremental_start(
            connection,
            raw_table_name=f"{table_name}_raw",
            ts_code=ts_code,
            date_column="ann_date",
        )
        frame = client.fetch(
            table_name,
            ts_code=ts_code,
            start_date=start_date,
            end_date=as_of_date.strftime("%Y%m%d"),
        )
        total_rows += _upsert_raw(connection, table_name=table_name, frame=frame, batch_id=batch_id)

    log_batch(
        connection,
        batch_id=batch_id,
        table_name=f"{table_name}_raw",
        status="completed",
        row_count=total_rows,
    )


def _read_table(connection, table_name: str, ts_codes: Iterable[str] | None = None) -> pd.DataFrame:
    sql = f"SELECT * FROM {table_name}"
    params: list[object] = []
    if ts_codes:
        ts_code_list = list(ts_codes)
        placeholders = ", ".join(["?"] * len(ts_code_list))
        sql += f" WHERE ts_code IN ({placeholders})"
        params.extend(ts_code_list)
    return pd.read_sql_query(sql, connection, params=params)


def _calculate_single_quarter(series_df: pd.DataFrame, value_columns: list[str]) -> pd.DataFrame:
    result = series_df.copy()
    result["year"] = result["end_date"].astype(str).str[:4]
    for column in value_columns:
        single_column = f"{column}_single"
        result[single_column] = 0.0
        for _, group in result.groupby(["ts_code", "year"], sort=False):
            previous_values: dict[str, float] = {}
            for index, row in group.sort_values("end_date").iterrows():
                end_type = str(row["end_type"])
                current_value = float(row.get(column, 0) or 0)
                if end_type == "1":
                    result.at[index, single_column] = current_value
                elif end_type in {"2", "3", "4"}:
                    previous = previous_values.get(str(int(end_type) - 1), 0.0)
                    result.at[index, single_column] = current_value - previous
                previous_values[end_type] = current_value
    return result.drop(columns=["year"])


def _calculate_yoy(features: pd.DataFrame, value_columns: list[str]) -> pd.DataFrame:
    result = features.copy()
    for column in value_columns:
        yoy_column = f"{column}_yoy"
        result[yoy_column] = pd.NA
        ordered = result.sort_values(["ts_code", "end_type", "end_date"])
        yoy_values = ordered.groupby(["ts_code", "end_type"])[column].pct_change() * 100
        result.loc[ordered.index, yoy_column] = yoy_values
    return result


def _build_market_daily_features(connection, *, ts_codes: list[str], batch_id: str) -> int:
    daily = _read_table(connection, "daily_raw", ts_codes)
    daily_basic = _read_table(connection, "daily_basic_raw", ts_codes)
    if daily.empty:
        return 0
    merged = daily.merge(
        daily_basic[
            ["ts_code", "trade_date", "pe", "pe_ttm", "pb", "total_mv", "circ_mv", "total_share"]
        ],
        on=["ts_code", "trade_date"],
        how="left",
    )
    return upsert_dataframe(connection, "market_daily_features", merged, batch_id=batch_id)


def _build_financial_period_features(connection, *, ts_codes: list[str], batch_id: str) -> int:
    income = _read_table(connection, "income_raw", ts_codes)
    if income.empty:
        return 0

    cashflow = _read_table(connection, "cashflow_raw", ts_codes)
    balancesheet = _read_table(connection, "balancesheet_raw", ts_codes)
    fina_indicator = _read_table(connection, "fina_indicator_raw", ts_codes)

    sort_columns = ["ts_code", "end_date", "end_type", "ann_date"]
    income = income.sort_values(sort_columns).drop_duplicates(["ts_code", "end_date", "end_type"], keep="last")
    cashflow = cashflow.sort_values(sort_columns).drop_duplicates(["ts_code", "end_date", "end_type"], keep="last")
    balancesheet = balancesheet.sort_values(sort_columns).drop_duplicates(["ts_code", "end_date", "end_type"], keep="last")
    fina_indicator = fina_indicator.sort_values(sort_columns).drop_duplicates(["ts_code", "end_date", "end_type"], keep="last")

    features = income.merge(
        cashflow[
            ["ts_code", "end_date", "end_type", "ann_date", "n_cashflow_act", "n_cashflow_inv_act", "n_cash_flows_fnc_act"]
        ],
        on=["ts_code", "end_date", "end_type", "ann_date"],
        how="left",
    ).merge(
        balancesheet[
            ["ts_code", "end_date", "end_type", "ann_date", "total_assets", "total_liab", "money_cap"]
        ],
        on=["ts_code", "end_date", "end_type", "ann_date"],
        how="left",
    ).merge(
        fina_indicator[
            [
                "ts_code",
                "end_date",
                "end_type",
                "ann_date",
                "roe",
                "netprofit_margin",
                "grossprofit_margin",
                "debt_to_assets",
                "current_ratio",
            ]
        ],
        on=["ts_code", "end_date", "end_type", "ann_date"],
        how="left",
    )

    features = features.sort_values(["ts_code", "end_date", "end_type"])
    features = _calculate_single_quarter(
        features,
        ["revenue", "n_income", "n_cashflow_act", "n_cashflow_inv_act", "n_cash_flows_fnc_act"],
    )
    features = _calculate_yoy(features, ["revenue", "n_income"])
    return upsert_dataframe(connection, "financial_period_features", features, batch_id=batch_id)


def _build_dividend_features(connection, *, ts_codes: list[str], batch_id: str) -> int:
    dividend = _read_table(connection, "dividend_raw", ts_codes)
    if dividend.empty:
        return 0
    dividend = dividend.sort_values(["ts_code", "end_date", "ann_date"], ascending=[True, False, False])
    implemented = dividend[dividend["div_proc"] == "实施"].copy()
    if implemented.empty:
        implemented = dividend.copy()
    features = implemented.drop_duplicates(["ts_code", "end_date"], keep="first")
    return upsert_dataframe(connection, "dividend_features", features, batch_id=batch_id)


def _build_result_technical_indicators(connection, *, ts_codes: list[str], batch_id: str) -> int:
    daily = _read_table(connection, "daily_raw", ts_codes)
    if daily.empty:
        return 0
    rows: list[pd.DataFrame] = []
    for ts_code, frame in daily.groupby("ts_code"):
        working = frame.sort_values("trade_date").rename(
            columns={
                "trade_date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "vol": "Volume",
            }
        )
        working["Date"] = pd.to_datetime(working["Date"])
        indicator_frame = working.copy()
        for indicator in TECHNICAL_INDICATORS:
            indicator_frame = calculate_indicator_frame(indicator_frame, indicator)
        result = pd.DataFrame(
            {
                "ts_code": ts_code,
                "trade_date": indicator_frame["Date"].dt.strftime("%Y%m%d"),
            }
        )
        for indicator in TECHNICAL_INDICATORS:
            result[indicator] = indicator_frame[indicator]
        rows.append(result)
    combined = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return upsert_dataframe(connection, "result_technical_indicators_daily", combined, batch_id=batch_id)


def _build_result_fundamentals(connection, *, ts_codes: list[str], batch_id: str) -> int:
    stock_basic = _read_table(connection, "stock_basic_raw", ts_codes).sort_values("ts_code")
    market = _read_table(connection, "market_daily_features", ts_codes).sort_values(["ts_code", "trade_date"])
    financial = _read_table(connection, "financial_period_features", ts_codes).sort_values(["ts_code", "end_date"])
    dividend = _read_table(connection, "dividend_features", ts_codes).sort_values(["ts_code", "ann_date"])
    if stock_basic.empty:
        return 0

    rows: list[dict[str, object]] = []
    for ts_code in ts_codes:
        basic_rows = stock_basic[stock_basic["ts_code"] == ts_code]
        if basic_rows.empty:
            continue
        basic = basic_rows.iloc[-1]
        market_rows = market[market["ts_code"] == ts_code]
        financial_rows = financial[financial["ts_code"] == ts_code]
        dividend_rows = dividend[dividend["ts_code"] == ts_code]
        market_latest = market_rows.iloc[-1] if not market_rows.empty else pd.Series(dtype=object)
        financial_latest = financial_rows.iloc[-1] if not financial_rows.empty else pd.Series(dtype=object)
        dividend_latest = dividend_rows.iloc[-1] if not dividend_rows.empty else pd.Series(dtype=object)
        rows.append(
            {
                "ts_code": ts_code,
                "name": basic.get("name"),
                "industry": basic.get("industry"),
                "market": basic.get("market"),
                "area": basic.get("area"),
                "close": market_latest.get("close"),
                "pe": market_latest.get("pe"),
                "pe_ttm": market_latest.get("pe_ttm"),
                "pb": market_latest.get("pb"),
                "total_mv": market_latest.get("total_mv"),
                "circ_mv": market_latest.get("circ_mv"),
                "total_share": market_latest.get("total_share"),
                "revenue": financial_latest.get("revenue"),
                "n_income": financial_latest.get("n_income"),
                "n_cashflow_act": financial_latest.get("n_cashflow_act"),
                "roe": financial_latest.get("roe"),
                "netprofit_margin": financial_latest.get("netprofit_margin"),
                "grossprofit_margin": financial_latest.get("grossprofit_margin"),
                "debt_to_assets": financial_latest.get("debt_to_assets"),
                "current_ratio": financial_latest.get("current_ratio"),
                "dividend_end_date": dividend_latest.get("end_date"),
                "dividend_cash_div": dividend_latest.get("cash_div"),
                "dividend_stk_div": dividend_latest.get("stk_div"),
                "dividend_pay_date": dividend_latest.get("pay_date"),
                "dividend_ex_date": dividend_latest.get("ex_date"),
            }
        )

    frame = pd.DataFrame(rows)
    return upsert_dataframe(connection, "result_fundamentals_latest", frame, batch_id=batch_id)


def _build_result_yoy_growth(connection, *, ts_codes: list[str], batch_id: str) -> int:
    financial = _read_table(connection, "financial_period_features", ts_codes)
    if financial.empty:
        return 0
    result = financial.copy()
    result["report_period"] = result["end_date"]
    return upsert_dataframe(connection, "result_yoy_growth", result, batch_id=batch_id)


def _build_result_peg_ratio(connection, *, ts_codes: list[str], batch_id: str) -> int:
    financial = _read_table(connection, "financial_period_features", ts_codes)
    market = _read_table(connection, "market_daily_features", ts_codes).sort_values(["ts_code", "trade_date"])
    if financial.empty or market.empty:
        return 0

    latest_market = market.groupby("ts_code").tail(1)[["ts_code", "close", "pe_ttm"]]
    result = financial.merge(latest_market, on="ts_code", how="left")
    result["peg"] = pd.to_numeric(result["pe_ttm"], errors="coerce") / pd.to_numeric(
        result["n_income_yoy"], errors="coerce"
    )
    return upsert_dataframe(connection, "result_peg_ratio", result, batch_id=batch_id)


def _log_publish(connection, *, batch_id: str, table_name: str, row_count: int) -> None:
    log_batch(connection, batch_id=batch_id, table_name=table_name, status="completed", row_count=row_count)


def _publish(connection, *, ts_codes: list[str], batch_id: str) -> None:
    counts = {
        "market_daily_features": _build_market_daily_features(connection, ts_codes=ts_codes, batch_id=batch_id),
        "financial_period_features": _build_financial_period_features(connection, ts_codes=ts_codes, batch_id=batch_id),
        "dividend_features": _build_dividend_features(connection, ts_codes=ts_codes, batch_id=batch_id),
        "result_technical_indicators_daily": _build_result_technical_indicators(connection, ts_codes=ts_codes, batch_id=batch_id),
        "result_fundamentals_latest": _build_result_fundamentals(connection, ts_codes=ts_codes, batch_id=batch_id),
        "result_yoy_growth": _build_result_yoy_growth(connection, ts_codes=ts_codes, batch_id=batch_id),
        "result_peg_ratio": _build_result_peg_ratio(connection, ts_codes=ts_codes, batch_id=batch_id),
    }
    for table_name, row_count in counts.items():
        _log_publish(connection, batch_id=batch_id, table_name=table_name, row_count=row_count)


def run_pipeline(
    db_path: Path | str,
    *,
    batch_id: str | None = None,
    client: object | None = None,
    as_of_date: str | None = None,
    ts_codes: list[str] | None = None,
) -> Path:
    initialize_database(db_path)
    resolved_client = _resolve_client(client)
    resolved_batch_id = _resolve_batch_id(batch_id)
    resolved_date = _resolve_as_of_date(as_of_date)

    connection = connect(db_path)
    try:
        target_ts_codes = _sync_stock_basic(connection, resolved_client, resolved_batch_id, ts_codes)
        if not target_ts_codes:
            raise RuntimeError("stock_basic returned no listed securities")

        for table_name in ("daily", "daily_basic"):
            _sync_market_table(
                connection,
                resolved_client,
                table_name=table_name,
                ts_codes=target_ts_codes,
                batch_id=resolved_batch_id,
                as_of_date=resolved_date,
            )

        for table_name in ("income", "balancesheet", "cashflow", "fina_indicator", "dividend", "stk_rewards"):
            _sync_financial_table(
                connection,
                resolved_client,
                table_name=table_name,
                ts_codes=target_ts_codes,
                batch_id=resolved_batch_id,
                as_of_date=resolved_date,
            )

        _publish(connection, ts_codes=target_ts_codes, batch_id=resolved_batch_id)
        connection.commit()
    except Exception as exc:
        connection.rollback()
        log_batch(
            connection,
            batch_id=resolved_batch_id,
            table_name="pipeline",
            status="failed",
            row_count=0,
            message=str(exc),
        )
        connection.commit()
        raise
    finally:
        connection.close()

    return Path(db_path)


def run_daily_sync(
    db_path: Path | str,
    *,
    batch_id: str | None = None,
    client: object | None = None,
    as_of_date: str | None = None,
    ts_codes: list[str] | None = None,
) -> Path:
    return run_pipeline(
        db_path,
        batch_id=batch_id,
        client=client,
        as_of_date=as_of_date,
        ts_codes=ts_codes,
    )
