"""
tushare_proxy.py - Tushare HTTP 代理层

## 项目中的两种调用方式

| 方式 | 模块 | 适用场景 |
|------|------|----------|
| **HTTP 代理** | 本文件 `proxy.py` | 基础数据接口（daily/income/balancesheet等） |
| **官方 SDK** | `import tushare as ts` | 需本地计算的接口（pro_bar + ma 参数） |

## HTTP 代理的局限

- 纯转发 HTTP 请求到 citydata.club
- **不支持 SDK 本地计算功能**（如 `ma` 参数的均线计算）
- `pro_bar` 虽然能调用，但无法返回 MA 列

## 何时用官方 SDK

需要以下功能时，直接用 `import tushare as ts`：

```python
import tushare as ts
ts.set_token(os.getenv('CITYDATA_TOKEN'))

# SMA 均线（SDK 本地计算）
df = ts.pro_bar(ts_code='000001.SZ', ma=[5, 10, 20, 50])
# 返回：ma5, ma10, ma20, ma50 列
```

## 用法（替换原生 tushare HTTP 调用）

    # 原来：
    import tushare as ts
    pro = ts.pro_api(token)
    df = pro.daily(ts_code='688333.SH')  # HTTP API

    # 现在（HTTP 代理）：
    from datasource.tushare.proxy import pro_api
    pro = pro_api(token)
    df = pro.daily(ts_code='688333.SH')  # 转发到 citydata

    # 业务代码无感知，接口签名完全一致
"""

import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

PROXY_BASE_URL = "https://tushare.citydata.club"


class TushareProxyAPI:
    """
    模拟 tushare.pro_api 对象。
    所有方法签名与 tushare 官方完全一致，底层走代理。
    """

    def __init__(self, token: str = None):
        self._token = (
            token
            or os.getenv("CITYDATA_TOKEN")
            or os.getenv("TUSHARE_TOKEN")
        )
        if not self._token:
            raise ValueError(
                "未找到 token，请在 .env 中设置 CITYDATA_TOKEN"
            )
        self._base_url = PROXY_BASE_URL

    def _call(self, api_name: str, **kwargs) -> pd.DataFrame:
        """
        通用代理调用。
        将 kwargs 转为 POST 表单，返回 DataFrame。
        """
        params = {"TOKEN": self._token}
        for k, v in kwargs.items():
            if v is not None and v != "":
                params[k] = v

        url = f"{self._base_url}/{api_name}"
        try:
            resp = requests.post(url, data=params, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 404:
                raise NotImplementedError(
                    f"代理服务不支持接口: {api_name}（404）"
                )
            raise

        data = resp.json()

        if isinstance(data, dict) and "data" in data:
            msg = str(data["data"])
            if "TOKEN" in msg or "失效" in msg or "token" in msg.lower():
                raise PermissionError(f"Token 无效或已过期: {msg}")

        if not data:
            return pd.DataFrame()

        return pd.DataFrame(data)

    def __getattr__(self, api_name: str):
        """
        动态代理任意 tushare 接口。
        pro.daily() / pro.income() / pro.balancesheet() ...
        全部自动路由到代理服务，无需逐一定义。
        """
        def _method(**kwargs):
            return self._call(api_name, **kwargs)
        _method.__name__ = api_name
        return _method

    def daily(self, ts_code: str = "", trade_date: str = "",
              start_date: str = "", end_date: str = "",
              fields: str = "") -> pd.DataFrame:
        """A股日线行情（amount 单位：千元）"""
        return self._call("daily", ts_code=ts_code, trade_date=trade_date,
                          start_date=start_date, end_date=end_date, fields=fields)

    def stock_basic(self, exchange: str = "", list_status: str = "L",
                    ts_code: str = "", fields: str = "") -> pd.DataFrame:
        """股票基础信息"""
        return self._call("stock_basic", exchange=exchange,
                          list_status=list_status, ts_code=ts_code, fields=fields)

    def index_daily(self, ts_code: str, start_date: str = "",
                    end_date: str = "", trade_date: str = "") -> pd.DataFrame:
        """指数日线行情"""
        return self._call("index_daily", ts_code=ts_code,
                          start_date=start_date, end_date=end_date,
                          trade_date=trade_date)

    def pro_bar(self, ts_code: str, start_date: str = "", end_date: str = "",
                adj: str = "qfq", freq: str = "D") -> pd.DataFrame:
        """复权行情"""
        return self._call("pro_bar", ts_code=ts_code, adj=adj, freq=freq,
                          start_date=start_date, end_date=end_date)

    def income(self, ts_code: str, period: str = "", start_date: str = "",
               end_date: str = "", fields: str = "") -> pd.DataFrame:
        """利润表"""
        return self._call("income", ts_code=ts_code, period=period,
                          start_date=start_date, end_date=end_date, fields=fields)

    def balancesheet(self, ts_code: str, period: str = "",
                     fields: str = "") -> pd.DataFrame:
        """资产负债表"""
        return self._call("balancesheet", ts_code=ts_code,
                          period=period, fields=fields)

    def cashflow(self, ts_code: str, period: str = "",
                 fields: str = "") -> pd.DataFrame:
        """现金流量表"""
        return self._call("cashflow", ts_code=ts_code,
                          period=period, fields=fields)

    def fina_indicator(self, ts_code: str, period: str = "",
                       fields: str = "") -> pd.DataFrame:
        """财务指标"""
        return self._call("fina_indicator", ts_code=ts_code,
                          period=period, fields=fields)


def pro_api(token: str = None) -> TushareProxyAPI:
    """
    替代 tushare.pro_api()，返回代理 API 对象。
    """
    return TushareProxyAPI(token=token)
