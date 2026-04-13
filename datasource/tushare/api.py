"""
tushare 双模式 API 入口

## 两种模式

| 模式 | 实现 | 适用场景 |
|------|------|----------|
| **proxy** | HTTP 代理转发 | 基础数据接口（daily/income等） |
| **sdk** | 官方 SDK | 需本地计算的接口（pro_bar + ma） |

## 使用方式

    from datasource.tushare.api import get_api

    # 默认模式（从环境变量读取）
    api = get_api()

    # 显式选择模式
    api_proxy = get_api(mode='proxy')  # HTTP 代理
    api_sdk = get_api(mode='sdk')      # 官方 SDK

## 环境变量

    TUSHARE_MODE=proxy  # 或 sdk
    CITYDATA_TOKEN=xxx  # 代理 token
    TUSHARE_TOKEN=xxx   # SDK token（可选，默认用 CITYDATA_TOKEN）
"""

import os
from typing import Literal, Optional

Mode = Literal["proxy", "sdk"]


class TushareAPI:
    """双模式 API：HTTP 代理 + 官方 SDK"""

    def __init__(self, mode: Mode, token: Optional[str] = None):
        self.mode = mode
        self._token = token or os.getenv("CITYDATA_TOKEN") or os.getenv("TUSHARE_TOKEN")

        if not self._token:
            raise ValueError("未找到 token，请设置 CITYDATA_TOKEN 或 TUSHARE_TOKEN")

        if mode == "proxy":
            from .proxy import TushareProxyAPI
            self._impl = TushareProxyAPI(self._token)
        else:
            import tushare as ts
            ts.set_token(self._token)
            self._impl = ts.pro_api()

    # ========== 通用接口（两种模式都支持）==========

    def daily(self, ts_code: str = "", trade_date: str = "",
              start_date: str = "", end_date: str = "",
              fields: str = ""):
        """A股日线行情"""
        return self._impl.daily(ts_code=ts_code, trade_date=trade_date,
                                start_date=start_date, end_date=end_date,
                                fields=fields)

    def stock_basic(self, exchange: str = "", list_status: str = "L",
                    ts_code: str = "", fields: str = ""):
        """股票基础信息"""
        return self._impl.stock_basic(exchange=exchange, list_status=list_status,
                                       ts_code=ts_code, fields=fields)

    def daily_basic(self, ts_code: str = "", trade_date: str = "",
                    start_date: str = "", end_date: str = "",
                    fields: str = ""):
        """每日指标"""
        return self._impl.daily_basic(ts_code=ts_code, trade_date=trade_date,
                                       start_date=start_date, end_date=end_date,
                                       fields=fields)

    def income(self, ts_code: str = "", period: str = "",
               start_date: str = "", end_date: str = "",
               fields: str = ""):
        """利润表"""
        return self._impl.income(ts_code=ts_code, period=period,
                                 start_date=start_date, end_date=end_date,
                                 fields=fields)

    def balancesheet(self, ts_code: str = "", period: str = "",
                     fields: str = ""):
        """资产负债表"""
        return self._impl.balancesheet(ts_code=ts_code, period=period,
                                        fields=fields)

    def cashflow(self, ts_code: str = "", period: str = "",
                 fields: str = ""):
        """现金流量表"""
        return self._impl.cashflow(ts_code=ts_code, period=period,
                                   fields=fields)

    def fina_indicator(self, ts_code: str = "", period: str = "",
                       fields: str = ""):
        """财务指标"""
        return self._impl.fina_indicator(ts_code=ts_code, period=period,
                                          fields=fields)

    def dividend(self, ts_code: str = "", period: str = "",
                 fields: str = ""):
        """分红数据"""
        return self._impl.dividend(ts_code=ts_code, period=period,
                                   fields=fields)

    def index_daily(self, ts_code: str = "", trade_date: str = "",
                    start_date: str = "", end_date: str = ""):
        """指数日线行情"""
        return self._impl.index_daily(ts_code=ts_code, trade_date=trade_date,
                                       start_date=start_date, end_date=end_date)

    # ========== 动态代理（任意接口）==========

    def _call(self, api_name: str, **kwargs):
        """通用调用（两种模式都支持）"""
        if self.mode == "proxy":
            return self._impl._call(api_name, **kwargs)
        else:
            # SDK 模式：通过 __getattr__ 调用
            return getattr(self._impl, api_name)(**kwargs)

    # ========== SDK 特有功能 ==========

    def pro_bar_with_ma(self, ts_code: str, ma: list,
                        start_date: str = "", end_date: str = "",
                        adj: str = "qfq", freq: str = "D"):
        """
        获取带 MA 均线的数据（仅 SDK 模式）

        Args:
            ts_code: 股票代码
            ma: 均线周期列表，如 [5, 10, 20, 50]
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型（qfq/hfq/None）

        Returns:
            DataFrame 包含 ma5, ma10, ma20, ma50 等列

        Raises:
            ValueError: proxy 模式不支持此功能
        """
        if self.mode != "sdk":
            raise ValueError("pro_bar_with_ma 仅支持 SDK 模式，请设置 TUSHARE_MODE=sdk")

        import tushare as ts
        df = ts.pro_bar(ts_code=ts_code, start_date=start_date, end_date=end_date,
                        adj=adj, freq=freq, ma=ma)
        # SDK 返回倒序，正序排列
        if df is not None and len(df) > 0:
            df = df.sort_values('trade_date', ascending=True)
        return df


def get_api(mode: Optional[Mode] = None, token: Optional[str] = None) -> TushareAPI:
    """
    获取 API 实例

    Args:
        mode: 模式选择 ('proxy' 或 'sdk')，默认从环境变量读取
        token: token，默认从环境变量读取

    Returns:
        TushareAPI 实例
    """
    mode = mode or os.getenv("TUSHARE_MODE", "proxy")
    return TushareAPI(mode, token)


# ========== 兼容旧代码 ==========

def pro_api(token: Optional[str] = None) -> TushareAPI:
    """兼容旧代码的入口（默认 proxy 模式）"""
    return get_api(mode="proxy", token=token)