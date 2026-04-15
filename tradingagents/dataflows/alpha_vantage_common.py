"""Alpha Vantage 异常定义

保留异常类供 interface.py 捕获。
实际实现已迁移到 datasource/alpha_vantage/common.py
"""

class AlphaVantageRateLimitError(Exception):
    """Exception raised when Alpha Vantage API rate limit is exceeded."""
    pass
