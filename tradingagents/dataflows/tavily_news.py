"""Tavily-based news data fetching functions."""

import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Annotated

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


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