"""
增长率与估值指标函数

提供 PEG Ratio 和增长率数据。
函数从 tools_registry.yaml 自动发现。
"""

from typing import Annotated

from tradingagents.dataflows.decorators import auto_tool

# 导入 provider
from ..provider import get_provider


@auto_tool(description="PEG估值指标 - PEG = PE(TTM) / 净利润增长率。用于判断成长股估值是否合理。返回各季度/年度的历史PEG数据表格。")
def get_peg_ratio(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None,
    raw: bool = False,
) -> str:
    """PEG估值指标 - 各季度/年度的历史PEG数据

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_peg_ratio(ticker, curr_date, raw=raw)


@auto_tool(description="增长率数据 - 获取营收和净利润的同比增长率历史数据，同时提供累计值和单季值")
def get_yoy_growth(
    ticker: Annotated[str, "ticker symbol of the company"],
    curr_date: Annotated[str | None, "current date"] = None,
    raw: bool = False,
) -> str:
    """增长率数据 - 同比增长率历史，包含累计值和单季值两种口径

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_yoy_growth(ticker, curr_date, raw=raw)