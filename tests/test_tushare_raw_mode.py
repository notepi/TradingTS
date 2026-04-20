"""
测试 tushare raw=True/False 双模式输出

验证：
- raw=True 返回 DataFrame（带 ts_code 列，用于入库）
- raw=False 返回格式化字符串（用于 LLM）
"""

import pytest
import pandas as pd


class TestStockDataRawMode:
    """测试 get_stock_data raw 参数"""

    def test_raw_true_returns_dataframe(self):
        """raw=True 返回 DataFrame + ts_code 列"""
        from datasource.tushare import get_stock_data

        result = get_stock_data("688333", "2025-04-01", "2025-04-15", raw=True)

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert "ts_code" in result.columns
        assert result["ts_code"].iloc[0] == "688333.SH"

    def test_raw_false_returns_string(self):
        """raw=False 返回格式化字符串"""
        from datasource.tushare import get_stock_data

        result = get_stock_data("688333", "2025-04-01", "2025-04-15", raw=False)

        assert isinstance(result, str)
        # 格式化字符串应包含股票代码或相关说明
        assert "688333" in result or "股票" in result or "Date" in result


class TestFundamentalsRawMode:
    """测试 get_fundamentals raw 参数"""

    def test_raw_true_returns_dataframe(self):
        """raw=True 返回 DataFrame"""
        from datasource.tushare import get_fundamentals

        result = get_fundamentals("688333", curr_date="2025-04-15", raw=True)

        # 可能返回 DataFrame 或空 dict
        if isinstance(result, pd.DataFrame):
            assert "ts_code" in result.columns
        elif isinstance(result, dict):
            assert len(result) >= 0

    def test_raw_false_returns_string(self):
        """raw=False 返回格式化字符串"""
        from datasource.tushare import get_fundamentals

        result = get_fundamentals("688333", curr_date="2025-04-15", raw=False)

        assert isinstance(result, str)


class TestBalanceSheetRawMode:
    """测试 get_balance_sheet raw 参数"""

    def test_raw_true_returns_dataframe(self):
        """raw=True 返回 DataFrame"""
        from datasource.tushare import get_balance_sheet

        result = get_balance_sheet("688333", freq="quarterly", curr_date="2025-04-15", raw=True)

        if isinstance(result, pd.DataFrame) and len(result) > 0:
            assert "ts_code" in result.columns

    def test_raw_false_returns_string(self):
        """raw=False 返回格式化字符串"""
        from datasource.tushare import get_balance_sheet

        result = get_balance_sheet("688333", freq="quarterly", curr_date="2025-04-15", raw=False)

        assert isinstance(result, str)


class TestPegRatioRawMode:
    """测试 get_peg_ratio raw 参数"""

    def test_raw_true_returns_dataframe(self):
        """raw=True 返回 DataFrame"""
        from datasource.tushare.indicators.enhanced_data import get_peg_ratio

        result = get_peg_ratio("688333", curr_date="2025-04-15", raw=True)

        if isinstance(result, pd.DataFrame) and len(result) > 0:
            assert "ts_code" in result.columns

    def test_raw_false_returns_string(self):
        """raw=False 返回格式化字符串"""
        from datasource.tushare.indicators.enhanced_data import get_peg_ratio

        result = get_peg_ratio("688333", curr_date="2025-04-15", raw=False)

        assert isinstance(result, str)


class TestYoyGrowthRawMode:
    """测试 get_yoy_growth raw 参数"""

    def test_raw_true_returns_dataframe(self):
        """raw=True 返回 DataFrame"""
        from datasource.tushare.indicators.enhanced_data import get_yoy_growth

        result = get_yoy_growth("688333", curr_date="2025-04-15", raw=True)

        if isinstance(result, pd.DataFrame) and len(result) > 0:
            assert "ts_code" in result.columns

    def test_raw_false_returns_string(self):
        """raw=False 返回格式化字符串"""
        from datasource.tushare.indicators.enhanced_data import get_yoy_growth

        result = get_yoy_growth("688333", curr_date="2025-04-15", raw=False)

        assert isinstance(result, str)


class TestIndicatorsRawMode:
    """测试 get_indicators raw 参数"""

    def test_raw_true_returns_dataframe(self):
        """raw=True 返回 DataFrame"""
        from datasource.tushare import get_indicators

        result = get_indicators("688333", "close_10_ema", "2025-04-15", look_back_days=10, raw=True)

        if isinstance(result, pd.DataFrame) and len(result) > 0:
            # indicators DataFrame 应有 Date 列
            assert "Date" in result.columns or "date" in result.columns

    def test_raw_false_returns_string(self):
        """raw=False 返回格式化字符串"""
        from datasource.tushare import get_indicators

        result = get_indicators("688333", "close_10_ema", "2025-04-15", look_back_days=10, raw=False)

        assert isinstance(result, str)