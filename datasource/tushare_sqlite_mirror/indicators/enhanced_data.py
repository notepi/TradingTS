"""
datasource.tushare_sqlite_mirror.indicators.enhanced_data - Lynch 指标（SQLite 缓存）

从 SQLite 缓存取数，输出格式和 datasource.tushare 一致。
"""

from typing import Annotated

try:
    from tradingagents.dataflows.decorators import auto_tool
except ImportError:
    def auto_tool(*args, **kwargs):
        def _decorator(func):
            return func
        return _decorator

# 导入 provider
from ..provider import get_provider


@auto_tool(description="增长率数据 - 获取营收和净利润的同比增长率历史数据")
def get_yoy_growth(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str | None, "current date"] = None,
    raw: bool = False,
) -> str:
    """增长率数据 - 同比增长率历史

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_yoy_growth(ticker, curr_date, raw=raw)


@auto_tool(description="PEG Ratio - 市盈率相对盈利增长比率，估值指标")
def get_peg_ratio(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str | None, "current date"] = None,
    raw: bool = False,
) -> str:
    """PEG Ratio 数据

    Args:
        raw: False=格式化字符串（LLM用），True=DataFrame（入库用）
    """
    return get_provider().get_peg_ratio(ticker, curr_date, raw=raw)