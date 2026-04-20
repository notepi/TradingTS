"""
datasource/tushare/base_provider.py - A股数据提供者基类

子类只需实现 _fetch_xxx 数据获取方法，
基类自动处理格式化、输出说明。

支持的函数列表（data.py + enhanced_data.py）：
- get_stock_data / get_indicators / get_fundamentals
- get_balance_sheet / get_cashflow / get_income_statement
- get_insider_transactions
- get_peg_ratio / get_yoy_growth
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import pandas as pd

from .symbols import normalize_a_share_symbol


# 指标名称映射：stockstats 使用的名称 -> 指标说明
INDICATOR_DESCRIPTIONS = {
    # 移动平均
    "close_10_ema": "10 EMA: A short-term exponential moving average.",
    "close_50_sma": "50 SMA: A medium-term simple moving average.",
    "close_200_sma": "200 SMA: A long-term simple moving average.",
    # MACD 系列（配套使用）
    "macd": "MACD: Moving Average Convergence Divergence (12, 26, 9).",
    "macds": "MACD Signal: EMA of MACD line (9-period).",
    "macdh": "MACD Histogram: Difference between MACD and Signal line.",
    # 动量
    "rsi": "RSI: Relative Strength Index (14-period) - overbought/oversold.",
    "mfi": "MFI: Money Flow Index (14-period) - volume-weighted RSI.",
    "cci": "CCI: Commodity Channel Index (14-period) - trend strength.",
    "wr": "WR: Williams %R (14-period) - overbought/oversold.",
    # KDJ 随机指标（配套使用）
    "kdjk": "KDJ K: Stochastic Fast K line (9-period).",
    "kdjd": "KDJ D: Stochastic Slow D line (3-period SMA of K).",
    "kdjj": "KDJ J: Stochastic J line - volatility adjusted K.",
    # 布林带（配套使用）
    "boll": "Bollinger Middle: 20 SMA as basis for Bollinger Bands.",
    "boll_ub": "Bollinger Upper: Upper band (Middle + 2 std).",
    "boll_lb": "Bollinger Lower: Lower band (Middle - 2 std).",
    # 波动率
    "atr": "ATR: Average True Range (14-period) - market volatility.",
    "vwma": "VWMA: Volume Weighted Moving Average.",
}


class StockDataProvider:
    """A股数据提供者基类

    子类只需实现 _fetch_xxx 数据获取方法，
    基类自动处理格式化、输出说明。
    """

    # ========== 属性（子类可覆盖）==========
    @property
    def source_name(self) -> str:
        """数据源名称"""
        return self.__class__.__name__.replace("Provider", "")

    # ========== 辅助方法（基类实现）==========
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码"""
        return normalize_a_share_symbol(symbol)

    # ========== 数据获取接口（子类实现）==========
    def _fetch_stock_data(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票行情数据"""
        raise NotImplementedError

    def _fetch_indicators(
        self,
        ts_code: str,
        indicator: str,
        curr_date: str,
        look_back_days: int
    ) -> dict:
        """获取技术指标数据"""
        raise NotImplementedError

    def _fetch_fundamentals(self, ts_code: str, curr_date: str | None, start_date: str | None, end_date: str | None) -> dict | pd.DataFrame:
        """获取基本面数据

        Args:
            curr_date: 单日查询（返回 dict）
            start_date/end_date: 日期范围查询（返回 DataFrame）
        """
        raise NotImplementedError

    def _fetch_balance_sheet(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取资产负债表"""
        raise NotImplementedError

    def _fetch_cashflow(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取现金流量表"""
        raise NotImplementedError

    def _fetch_income_statement(self, ts_code: str, freq: str) -> pd.DataFrame:
        """获取利润表"""
        raise NotImplementedError

    def _fetch_insider_transactions(self, ts_code: str) -> pd.DataFrame:
        """获取内部交易数据"""
        raise NotImplementedError

    def _fetch_peg_ratio(self, ts_code: str, curr_date: str | None) -> pd.DataFrame:
        """获取 PEG 数据"""
        raise NotImplementedError

    def _fetch_yoy_growth(self, ts_code: str, curr_date: str | None) -> pd.DataFrame:
        """获取 YoY 增长数据"""
        raise NotImplementedError

    # ========== 格式化输出（基类实现）==========
    def get_stock_data(
        self,
        symbol: Annotated[str, "ticker symbol of the company"],
        start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
        end_date: Annotated[str, "End date in yyyy-mm-dd format"],
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """获取股票历史数据 (OHLCV)

        Args:
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
        """
        ts_code = self._normalize_symbol(symbol)
        df = self._fetch_stock_data(ts_code, start_date, end_date)

        if df is None or df.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

        if raw:
            df["ts_code"] = ts_code
            return df

        return self._format_stock_data(df, ts_code, start_date, end_date)

    def get_indicators(
        self,
        symbol: Annotated[str, "ticker symbol of the company"],
        indicator: Annotated[str, "technical indicator"],
        curr_date: Annotated[str, "The current trading date, YYYY-mm-dd"],
        look_back_days: Annotated[int, "how many days to display"] = 30,
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """获取技术指标数据

        Args:
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
        """
        if indicator not in INDICATOR_DESCRIPTIONS:
            return f"Indicator '{indicator}' is not supported. Available: {list(INDICATOR_DESCRIPTIONS.keys())}"

        ts_code = self._normalize_symbol(symbol)
        value_by_date = self._fetch_indicators(ts_code, indicator, curr_date, look_back_days)

        if raw:
            # 返回 DataFrame
            rows = []
            for date_str, value in value_by_date.items():
                rows.append({
                    "ts_code": ts_code,
                    "indicator": indicator,
                    "Date": date_str,
                    "value": value,
                })
            return pd.DataFrame(rows)

        return self._format_indicators(value_by_date, ts_code, indicator, curr_date, look_back_days)

    def get_fundamentals(
        self,
        ticker: Annotated[str, "ticker symbol of the company"],
        start_date: Annotated[str | None, "start date for history query"] = None,
        end_date: Annotated[str | None, "end date for history query"] = None,
        curr_date: Annotated[str | None, "single date query"] = None,
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """获取公司基本面数据

        Args:
            start_date: 开始日期（日期范围查询）
            end_date: 结束日期（日期范围查询）
            curr_date: 单日查询（返回该日期数据）
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）

        Returns:
            单日查询返回 dict/DataFrame（1行）
            日期范围查询返回 DataFrame（多行）
        """
        ts_code = self._normalize_symbol(ticker)

        # 调用 _fetch_fundamentals
        result = self._fetch_fundamentals(ts_code, curr_date, start_date, end_date)

        if result is None:
            return f"No fundamentals data found for symbol '{ticker}'"

        # 判断返回类型
        if isinstance(result, pd.DataFrame):
            # 日期范围查询返回 DataFrame
            if raw:
                result["ts_code"] = ts_code
                return result
            return self._format_fundamentals_history(result, ts_code, start_date, end_date)
        else:
            # 单日查询返回 dict
            if raw:
                df = pd.DataFrame([result])
                df["ts_code"] = ts_code
                return df
            return self._format_fundamentals(result, ts_code)

    def get_balance_sheet(
        self,
        ticker: Annotated[str, "ticker symbol of the company"],
        freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
        curr_date: Annotated[str | None, "current date"] = None,
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """获取资产负债表

        Args:
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
        """
        ts_code = self._normalize_symbol(ticker)
        df = self._fetch_balance_sheet(ts_code, freq)

        if df is None or df.empty:
            return f"No balance sheet data found for '{ticker}'"

        if raw:
            df["ts_code"] = ts_code
            return df

        return self._format_balance_sheet(df, ts_code, freq)

    def get_cashflow(
        self,
        ticker: Annotated[str, "ticker symbol of the company"],
        freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
        curr_date: Annotated[str | None, "current date"] = None,
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """获取现金流量表

        Args:
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
        """
        ts_code = self._normalize_symbol(ticker)
        df = self._fetch_cashflow(ts_code, freq)

        if df is None or df.empty:
            return f"No cash flow data found for '{ticker}'"

        if raw:
            df["ts_code"] = ts_code
            return df

        return self._format_cashflow(df, ts_code, freq)

    def get_income_statement(
        self,
        ticker: Annotated[str, "ticker symbol of the company"],
        freq: Annotated[str, "frequency: 'annual' or 'quarterly'"] = "quarterly",
        curr_date: Annotated[str | None, "current date"] = None,
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """获取利润表

        Args:
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
        """
        ts_code = self._normalize_symbol(ticker)
        df = self._fetch_income_statement(ts_code, freq)

        if df is None or df.empty:
            return f"No income statement data found for '{ticker}'"

        if raw:
            df["ts_code"] = ts_code
            return df

        return self._format_income_statement(df, ts_code, freq)

    def get_insider_transactions(
        self,
        ticker: Annotated[str, "ticker symbol of the company"],
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """获取高管和股东增减持数据

        Args:
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
        """
        ts_code = self._normalize_symbol(ticker)
        df = self._fetch_insider_transactions(ts_code)

        if df is None or df.empty:
            return f"No insider transactions data found for '{ticker}'"

        if raw:
            df["ts_code"] = ts_code
            return df

        return self._format_insider_transactions(df, ts_code)

    def get_peg_ratio(
        self,
        ticker: Annotated[str, "ticker symbol of the company"],
        curr_date: Annotated[str | None, "current date"] = None,
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """PEG估值指标 - PEG = PE(TTM) / 净利润增长率

        Args:
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
        """
        ts_code = self._normalize_symbol(ticker)
        df = self._fetch_peg_ratio(ts_code, curr_date)

        if df is None or df.empty:
            return f"No PEG ratio data found for '{ticker}'"

        if raw:
            df["ts_code"] = ts_code
            return df

        return self._format_peg_ratio(df, ts_code)

    def get_yoy_growth(
        self,
        ticker: Annotated[str, "ticker symbol of the company"],
        curr_date: Annotated[str | None, "current date"] = None,
        raw: bool = False,
    ) -> str | pd.DataFrame:
        """增长率数据 - 营收和净利润的同比增长率

        Args:
            raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
        """
        ts_code = self._normalize_symbol(ticker)
        df = self._fetch_yoy_growth(ts_code, curr_date)

        if df is None or df.empty:
            return f"No YoY growth data found for '{ticker}'"

        if raw:
            df["ts_code"] = ts_code
            return df

        return self._format_yoy_growth(df, ts_code)

    # ========== 格式化模板（基类实现）==========
    def _format_stock_data(
        self,
        df: pd.DataFrame,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> str:
        """格式化股票数据输出"""
        csv_string = df.to_csv(index=False)

        header = "[Tool: get_stock_data] - 原始价格数据\n"
        header += f"# Stock data for {ts_code} from {start_date} to {end_date}\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n"
        header += f"# Unit: Volume in Lots (1 Lot = 100 shares), Amount in Thousand CNY\n"
        header += f"# Conversion: Lots × 100 = Total shares\n\n"

        return header + csv_string

    def _format_indicators(
        self,
        value_by_date: dict,
        ts_code: str,
        indicator: str,
        curr_date: str,
        look_back_days: int,
    ) -> str:
        """格式化技术指标输出"""
        from datetime import timedelta

        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        display_start_dt = curr_dt - timedelta(days=look_back_days)

        result_lines = []
        current_dt = curr_dt
        while current_dt >= display_start_dt:
            date_str = current_dt.strftime("%Y-%m-%d")
            value = value_by_date.get(date_str)
            if value is None or pd.isna(value):
                result_lines.append(f"{date_str}: N/A: Not a trading day (weekend or holiday)")
            else:
                result_lines.append(f"{date_str}: {value}")
            current_dt = current_dt - timedelta(days=1)

        result_str = (
            f"[Tool: get_indicators] [Indicator: {indicator}]\n"
            f"## {indicator} values from {display_start_dt.strftime('%Y-%m-%d')} to {curr_date}:\n"
            f"# 计算: 使用历史数据确保准确，显示最近 {look_back_days} 天\n\n"
            + "\n".join(result_lines)
            + "\n\n"
            + INDICATOR_DESCRIPTIONS.get(indicator, "No description available.")
            + "\n\n注意：Volume 单位为手(每手100股)，涉及成交量的指标(VWMA/MFI)需注意单位换算。"
        )

        return result_str

    def _format_fundamentals_history(
        self,
        df: pd.DataFrame,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> str:
        """格式化基本面历史数据输出"""
        csv_string = df.to_csv(index=False)

        header = f"[Tool: get_fundamentals] # Fundamentals History for {ts_code}\n"
        header += f"# Period: {start_date} to {end_date}\n"
        header += f"# Total records: {len(df)}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n"
        header += f"# Unit: PE/PB ratios, Market Cap in CNY\n\n"

        return header + csv_string

    def _format_fundamentals(self, data: dict, ts_code: str) -> str:
        """格式化估值数据输出"""
        lines = []
        lines.append(f"Ticker: {ts_code}")
        lines.append(f"Date: {data.get('Date', 'N/A')}")

        # 估值数据
        for key in ["Stock_Price_元", "P/E_Ratio", "P/E_Ratio_TTM", "P/B_Ratio"]:
            if key in data:
                display_key = key.replace("_元", " (元)").replace("_", " ")
                lines.append(f"{display_key}: {data[key]}")

        # 市值数据
        for key in ["Total_Market_Cap_元", "Circulating_Market_Cap_元"]:
            if key in data:
                display_key = key.replace("_元", " (元)").replace("_", " ")
                lines.append(f"{display_key}: {data[key]}")

        header = f"[Tool: get_fundamentals] # Valuation Data for {ts_code}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n"
        header += f"# Unit: CNY (元) for market cap, ratios for PE/PB\n\n"

        return header + "\n".join(lines)

    def _format_balance_sheet(
        self,
        df: pd.DataFrame,
        ts_code: str,
        freq: str
    ) -> str:
        """格式化资产负债表输出"""
        csv_string = df.to_csv(index=False)

        header = f"[Tool: get_balance_sheet] # Balance Sheet for {ts_code} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n"
        header += f"# Unit: Yuan (CNY)\n\n"

        return header + csv_string

    def _format_cashflow(
        self,
        df: pd.DataFrame,
        ts_code: str,
        freq: str
    ) -> str:
        """格式化现金流量表输出"""
        csv_string = df.to_csv(index=False)

        header = f"[Tool: get_cashflow] # Cash Flow for {ts_code} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n"
        header += f"# Unit: Yuan (CNY)\n\n"

        return header + csv_string

    def _format_income_statement(
        self,
        df: pd.DataFrame,
        ts_code: str,
        freq: str
    ) -> str:
        """格式化利润表输出"""
        csv_string = df.to_csv(index=False)

        header = f"[Tool: get_income_statement] # Income Statement for {ts_code} ({freq})\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n"
        header += f"# Unit: Yuan (CNY)\n\n"

        return header + csv_string

    def _format_insider_transactions(
        self,
        df: pd.DataFrame,
        ts_code: str
    ) -> str:
        """格式化内部交易数据输出"""
        csv_string = df.to_csv(index=False)

        header = f"[Tool: get_insider_transactions] # 高管与股东增减持数据 - {ts_code}\n"
        header += f"# 共 {len(df)} 条记录\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n\n"

        return header + csv_string

    def _format_peg_ratio(self, df: pd.DataFrame, ts_code: str) -> str:
        """格式化 PEG 数据输出"""
        csv_string = df.to_csv(index=False)

        header = f"[Tool: get_peg_ratio] # PEG Ratio for {ts_code}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n"
        header += "# PEG = PE(TTM) / Net Profit Growth Rate (YoY%)\n"
        header += "# PEG < 1 indicates potential undervaluation\n\n"

        return header + csv_string

    def _format_yoy_growth(self, df: pd.DataFrame, ts_code: str) -> str:
        """格式化 YoY 增长数据输出"""
        csv_string = df.to_csv(index=False)

        header = f"[Tool: get_yoy_growth] # YoY Growth for {ts_code}\n"
        header += f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"# Data source: {self.source_name}\n"
        header += "# Unit: Yuan (CNY) for monetary values, YoY% are percentages\n\n"

        return header + csv_string


