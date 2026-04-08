"""Tavily-based news data fetching functions."""

import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Annotated, Any

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


# ============================================================================
# CONSTANTS: Domain and Term Libraries
# ============================================================================

# Official financial news domains (high credibility)
OFFICIAL_DOMAINS = [
    "eastmoney.com",      # 东方财富
    "sina.com.cn",        # 新浪财经
    "finance.qq.com",     # 腾讯财经
    "caixin.com",         # 财新
    "cls.cn",             # 财联社
    "10jqka.com.cn",      # 同花顺
]

# High quality news domains
HIGH_QUALITY_NEWS_DOMAINS = [
    "eastmoney.com",
    "sina.com.cn",
    "finance.qq.com",
    "caixin.com",
    "cls.cn",
]

# Low quality domains to exclude (self-media aggregators)
LOW_QUALITY_EXCLUDE = [
    "baidu.com",          # 百度百家号
    "sogou.com",          # 搜狗
    "so.com",             # 360
    "360.cn",             # 360
    "163.com",            # 网易自媒体
    "ifeng.com",          # 凤凰自媒体
]

# General risk event terms
RISK_TERMS = [
    "减持", "解禁", "处罚", "立案", "问询", "诉讼", "仲裁",
    "业绩预告下调", "商誉减值", "债务违约", "亏损", "st",
    "警示函", "监管措施", "立案调查", "资产减值"
]

# General positive event terms
POSITIVE_TERMS = [
    "增持", "回购", "业绩预增", "中标", "战略合作", "技术创新",
    "新产品", "产能扩张", "行业政策利好", "业绩增长", "盈利",
    "突破", "领先", "独家", "订单", "合作"
]

# Event category mapping
EVENT_CATEGORIES = {
    "institutional_increase": ["举牌", "增持", "机构买入", "机构建仓"],
    "institutional_decrease": ["减持", "机构卖出", "机构减仓"],
    "share_repurchase": ["回购", "股票回购", "自家股票"],
    "dividend": ["分红", "股息", "现金分红", "送股"],
    "earnings_preview": ["业绩预增", "业绩预告", "年报预盈"],
    "earnings_miss": ["业绩预减", "业绩亏损", "年报预亏"],
    "contract_win": ["中标", "订单", "合同", "签约"],
    "product_launch": ["新产品", "新品发布", "上市"],
    "capacity_expansion": ["产能扩张", "扩产", "新建产能", "投产"],
    "insider_buying": ["高管增持", "董事长增持", "管理层买入"],
    "insider_selling": ["高管减持", "董事长减持", "管理层卖出"],
    "management_change": ["高管变动", "董事长辞职", "总裁离职", "人事变动"],
    "governance_issue": ["治理问题", "内部控制", "合规问题"],
    "regulatory_inquiry": ["问询函", "监管问询", "交易所问询"],
    "penalty": ["处罚", "罚款", "行政处罚", "警示函"],
    "litigation": ["诉讼", "仲裁", "法律纠纷", "官司"],
    "debt_default": ["债务违约", "违约", "无法偿还", "破产"],
    "sector_rally": ["板块上涨", "行业上涨", "概念股上涨"],
    "sector_selloff": ["板块下跌", "行业下跌", "概念股下跌"],
    "policy_benefit": ["政策利好", "政策支持", "行业政策"],
    "policy_risk": ["政策风险", "监管收紧", "行业整顿"],
}

# Bucket definitions
BUCKETS = [
    "official_disclosure",
    "mainstream_news",
    "sector_context",
    "public_discussion",
    "negative_risk",
    "positive_news",
]


def _get_client():
    """Get Tavily client with API key from environment."""
    if TavilyClient is None:
        raise ImportError("tavily-python is not installed. Run: uv add tavily-python")
    api_key = os.getenv("TAVILY_API_KEYS") or os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEYS or TAVILY_API_KEY is not configured in .env")
    return TavilyClient(api_key=api_key)


def get_tavily_news(
    ticker: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news for a specific stock ticker using Tavily search API.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL", "688333.SH")
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        Formatted string containing news articles
    """
    try:
        client = _get_client()

        # Build search query - include ticker and company context
        query = f"{ticker} stock news"

        # Use Tavily search with finance topic
        response = client.search(
            query=query,
            search_depth="advanced",
            topic="finance",
            max_results=15,
            include_answer=True,
            start_date=start_date,
            end_date=end_date,
        )

        results = response.get("results", [])
        if not results:
            return f"No news found for {ticker} between {start_date} and {end_date}"

        news_str = ""
        for article in results:
            title = article.get("title", "No title")
            content = article.get("content", "")
            url = article.get("url", "")
            score = article.get("score", 0)

            # Format source from URL domain
            source = "Unknown"
            if url:
                try:
                    from urllib.parse import urlparse
                    source = urlparse(url).netloc.replace("www.", "")
                except Exception:
                    pass

            news_str += f"### {title} (source: {source}, relevance: {score:.2f})\n"
            if content:
                # Limit content length for readability
                content_preview = content[:500] if len(content) > 500 else content
                news_str += f"{content_preview}\n"
            if url:
                news_str += f"Link: {url}\n"
            news_str += "\n"

        header = f"## {ticker} News (via Tavily), from {start_date} to {end_date}:\n\n"

        # Include Tavily's AI-generated answer if available
        answer = response.get("answer", "")
        if answer:
            header += f"**Summary:** {answer}\n\n"

        return header + news_str

    except Exception as e:
        return f"Error fetching news for {ticker} via Tavily: {str(e)}"


def get_tavily_global_news(
    curr_date: Annotated[str, "current date in YYYY-MM-DD format"],
    look_back_days: Annotated[int, "days to look back"] = 7,
    limit: Annotated[int, "max number of news"] = 10,
) -> str:
    """
    Retrieve global/macro economic news using Tavily search API.

    Args:
        curr_date: Current date in yyyy-mm-dd format
        look_back_days: Number of days to look back
        limit: Maximum number of articles to return

    Returns:
        Formatted string containing global news articles
    """
    try:
        client = _get_client()

        # Calculate date range
        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        start_dt = curr_dt - relativedelta(days=look_back_days)
        start_date = start_dt.strftime("%Y-%m-%d")

        # Search queries for macro/global news
        query = "global stock market economy Federal Reserve interest rates inflation"

        response = client.search(
            query=query,
            search_depth="advanced",
            topic="news",
            max_results=limit,
            include_answer=True,
            time_range="week",
        )

        results = response.get("results", [])
        if not results:
            return f"No global news found for {curr_date}"

        news_str = ""
        for article in results[:limit]:
            title = article.get("title", "No title")
            content = article.get("content", "")
            url = article.get("url", "")

            source = "Unknown"
            if url:
                try:
                    from urllib.parse import urlparse
                    source = urlparse(url).netloc.replace("www.", "")
                except Exception:
                    pass

            news_str += f"### {title} (source: {source})\n"
            if content:
                content_preview = content[:500] if len(content) > 500 else content
                news_str += f"{content_preview}\n"
            if url:
                news_str += f"Link: {url}\n"
            news_str += "\n"

        header = f"## Global Market News (via Tavily), from {start_date} to {curr_date}:\n\n"

        answer = response.get("answer", "")
        if answer:
            header += f"**Summary:** {answer}\n\n"

        return header + news_str

    except Exception as e:
        return f"Error fetching global news via Tavily: {str(e)}"


# ============================================================================
# Lower-level Search and Extract Functions (for modular use)
# ============================================================================


def tavily_search(
    query: str,
    topic: str = "news",
    search_depth: str = "basic",
    max_results: int = 5,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    """
    Execute a Tavily search and return raw results.

    Args:
        query: Search query (keep short, <= 20 chars recommended)
        topic: "news", "general", or "finance"
        search_depth: "basic", "advanced", "fast", or "ultra-fast"
        max_results: Maximum number of results (0-20)
        include_domains: List of domains to include (whitelist)
        exclude_domains: List of domains to exclude (blacklist)
        start_date: Start date in yyyy-mm-dd format
        end_date: End date in yyyy-mm-dd format

    Returns:
        List of article dicts with keys: title, url, content, score, published_date
    """
    try:
        client = _get_client()

        kwargs = {
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "max_results": max_results,
            "include_answer": True,
        }

        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date

        response = client.search(**kwargs)
        return response.get("results", [])

    except Exception as e:
        return []


def tavily_extract(
    urls: list[str],
    query: str,
    chunks_per_source: int = 2,
    extract_depth: str = "basic",
) -> list[dict[str, Any]]:
    """
    Extract content from specific URLs using Tavily.

    Args:
        urls: List of URLs to extract from
        query: Query to guide extraction relevance
        chunks_per_source: Number of content chunks per source (1-5)
        extract_depth: "basic" or "advanced" (advanced extracts tables better)

    Returns:
        List of extracted content dicts with keys: url, raw_content, content
    """
    if not urls:
        return []

    try:
        client = _get_client()

        results = []
        for url in urls:
            try:
                response = client.extract(
                    urls=[url],
                    query=query,
                    chunks_per_source=chunks_per_source,
                    extract_depth=extract_depth,
                )
                extracted = response.get("results", [])
                if extracted:
                    results.append(extracted[0])
            except Exception:
                continue

        return results

    except Exception as e:
        return []


def tavily_search_debug(
    ticker: str,
    bucket: str,
    query: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    """
    Debug tool: Search a specific bucket for a ticker.
    Used for testing individual bucket queries.

    Args:
        ticker: Stock ticker
        bucket: One of the BUCKETS
        query: Search query
        start_date: Start date (optional)
        end_date: End date (optional)

    Returns:
        Formatted string of search results
    """
    if bucket not in BUCKETS:
        bucket = "mainstream_news"

    topic = "news" if bucket != "public_discussion" else "general"
    depth = "advanced" if bucket in ["official_disclosure", "negative_risk"] else "basic"

    results = tavily_search(
        query=query,
        topic=topic,
        search_depth=depth,
        max_results=5,
        include_domains=OFFICIAL_DOMAINS,
        exclude_domains=LOW_QUALITY_EXCLUDE,
        start_date=start_date,
        end_date=end_date,
    )

    if not results:
        return f"No results for {bucket}: {query}"

    output = f"=== {bucket} ===\nQuery: {query}\n\n"
    for i, r in enumerate(results, 1):
        output += f"{i}. [{r.get('score', 0):.2f}] {r.get('title', 'N/A')}\n"
        output += f"   Source: {r.get('url', 'N/A')}\n"
        content = r.get('content', '')
        if content:
            output += f"   Content: {content[:200]}...\n"
        output += "\n"

    return output


def tavily_extract_debug(
    urls: list[str],
    query: str,
) -> str:
    """
    Debug tool: Extract content from specific URLs.
    Used for testing URL extraction.

    Args:
        urls: List of URLs to extract
        query: Query to guide extraction

    Returns:
        Formatted string of extracted content
    """
    results = tavily_extract(urls=urls, query=query, chunks_per_source=2)

    if not results:
        return f"No content extracted from {urls}"

    output = f"=== Extracted Content ===\nQuery: {query}\n\n"
    for r in results:
        output += f"URL: {r.get('url', 'N/A')}\n"
        content = r.get('raw_content', r.get('content', ''))
        if content:
            output += f"Content ({len(content)} chars):\n{content[:500]}...\n"
        output += "\n"

    return output