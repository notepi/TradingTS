from langchain_core.tools import tool
from typing import Annotated, Any
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.dataflows.tavily_news import (
    tavily_search,
    tavily_extract,
    OFFICIAL_DOMAINS,
    LOW_QUALITY_EXCLUDE,
    RISK_TERMS,
    POSITIVE_TERMS,
    EVENT_CATEGORIES,
    BUCKETS,
)

import json
from datetime import datetime
from urllib.parse import urlparse


# ============================================================================
# CONSTANTS
# ============================================================================

SOURCE_TYPE_MAPPING = {
    "eastmoney.com": "official_media",
    "sina.com.cn": "official_media",
    "finance.qq.com": "official_media",
    "caixin.com": "official_media",
    "cls.cn": "official_media",
    "10jqka.com.cn": "official_media",
    "xueqiu.com": "social",
    "tuchong.com": "social",
    "weibo.com": "social",
}

CREDIBILITY_SCORES = {
    "eastmoney.com": 0.95,
    "sina.com.cn": 0.90,
    "finance.qq.com": 0.88,
    "caixin.com": 0.92,
    "cls.cn": 0.85,
    "10jqka.com.cn": 0.82,
    "xueqiu.com": 0.70,
    "weibo.com": 0.60,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def resolve_company_profile(ticker: str) -> dict:
    """
    Resolve company profile from ticker using tushare data.

    Args:
        ticker: Stock ticker (e.g., "688333.SH" or "688333")

    Returns:
        dict with keys: ts_code, name, full_name, industry, area
    """
    try:
        from tradingagents.dataflows.tushare_data import _get_pro, _convert_symbol
    except ImportError:
        return {
            "ts_code": ticker,
            "name": ticker,
            "full_name": ticker,
            "industry": "",
            "area": "",
        }

    try:
        ts_code = _convert_symbol(ticker)
        pro = _get_pro()
        all_basic = pro.stock_basic()
        basic = all_basic[all_basic['ts_code'] == ts_code]

        if basic.empty:
            return {
                "ts_code": ts_code,
                "name": ticker,
                "full_name": ticker,
                "industry": "",
                "area": "",
            }

        row = basic.iloc[0]
        return {
            "ts_code": ts_code,
            "name": row.get('name', ticker),
            "full_name": row.get('name', ticker),  # tushare doesn't have full name separately
            "industry": row.get('industry', ''),
            "area": row.get('area', ''),
        }
    except Exception:
        return {
            "ts_code": ticker,
            "name": ticker,
            "full_name": ticker,
            "industry": "",
            "area": "",
        }


def build_query_plan(profile: dict) -> dict[str, list[str]]:
    """
    Build query plan from company profile.
    Generates 2-4 queries per bucket.

    Args:
        profile: Company profile dict from resolve_company_profile

    Returns:
        dict mapping bucket name to list of queries
    """
    name = profile.get("name", "")
    full_name = profile.get("full_name", "")
    industry = profile.get("industry", "")
    ts_code = profile.get("ts_code", "")

    # Extract pure ticker (without exchange suffix)
    pure_ticker = ts_code.replace(".SH", "").replace(".SZ", "")

    queries = {}

    # 1. official_disclosure: company announcements
    queries["official_disclosure"] = [
        f"{name} 公告",
        f"{pure_ticker} 公告",
    ]
    if len(full_name) > len(name):
        queries["official_disclosure"].append(f"{full_name} 公告")

    # 2. mainstream_news: general news
    queries["mainstream_news"] = [
        f"{name} 新闻",
        f"{pure_ticker} 新闻",
    ]
    if name != full_name and len(full_name) < 15:
        queries["mainstream_news"].append(f"{full_name} 新闻")

    # 3. sector_context: industry/sector news
    queries["sector_context"] = [
        f"{industry} 行业动态",
    ]
    if name:
        queries["sector_context"].append(f"{name} 行业")
    queries["sector_context"] = queries["sector_context"][:3]  # cap at 3

    # 4. public_discussion: social media discussion
    queries["public_discussion"] = [
        f"{name} 雪球",
        f"{name} 股吧",
    ]
    if len(name) <= 4:  # short names only
        queries["public_discussion"].append(f"{name} 投资者")

    # 5. negative_risk: risk events
    risk_queries = []
    for term in RISK_TERMS[:5]:  # use top 5 risk terms
        risk_queries.append(f"{name} {term}")
    queries["negative_risk"] = risk_queries

    # 6. positive_news: positive events
    positive_queries = []
    for term in POSITIVE_TERMS[:5]:  # use top 5 positive terms
        positive_queries.append(f"{name} {term}")
    queries["positive_news"] = positive_queries

    return queries


def _get_source_type(domain: str) -> str:
    """Get source type from domain."""
    return SOURCE_TYPE_MAPPING.get(domain, "mainstream")


def _get_credibility(domain: str) -> float:
    """Get credibility score from domain."""
    return CREDIBILITY_SCORES.get(domain, 0.5)


def _score_article(article: dict, seen_domains: set[str], article_index: int) -> float:
    """
    Score an article based on credibility, independence, and recency.

    Args:
        article: Article dict with url, published_date, score
        seen_domains: Set of domains already selected
        article_index: Index in original results (for novelty)

    Returns:
        Float score (higher is better)
    """
    url = article.get("url", "")
    try:
        domain = urlparse(url).netloc.replace("www.", "")
    except Exception:
        domain = ""

    # Credibility (0.4 weight)
    cred = _get_credibility(domain)

    # Independence (0.3 weight) - penalize same domain repeats
    if domain in seen_domains:
        independence = 0.5
    else:
        independence = 1.0

    # Novelty (0.3 weight) - newer articles score higher
    published = article.get("published_date", "")
    recency = 0.5  # default
    if published:
        try:
            pub_date = datetime.strptime(published[:10], "%Y-%m-%d")
            days_ago = (datetime.now() - pub_date).days
            if days_ago <= 7:
                recency = 1.0
            elif days_ago <= 14:
                recency = 0.8
            elif days_ago <= 30:
                recency = 0.5
            else:
                recency = 0.2
        except Exception:
            recency = 0.5

    # Base relevance score from Tavily
    base_score = article.get("score", 0.5)

    return 0.4 * cred * base_score + 0.3 * independence + 0.3 * recency


def select_and_extract(
    raw_articles: list[dict],
    query: str,
    max_per_bucket: int = 3,
) -> list[dict]:
    """
    Select top articles and extract full content.

    Args:
        raw_articles: List of raw article dicts from tavily_search
        query: Query for extraction relevance
        max_per_bucket: Maximum articles to select per bucket

    Returns:
        List of enriched article dicts with extracted content
    """
    if not raw_articles:
        return []

    # Score and sort articles
    seen_domains = set()
    scored = []
    for i, art in enumerate(raw_articles):
        url = art.get("url", "")
        try:
            domain = urlparse(url).netloc.replace("www.", "")
        except Exception:
            domain = ""
        score = _score_article(art, seen_domains, i)
        scored.append((score, domain, art))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Select top articles (max_per_bucket)
    selected = []
    selected_domains = set()
    for score, domain, art in scored:
        if len(selected) >= max_per_bucket:
            break
        if domain not in selected_domains or len(selected) < 2:  # allow at least 2 from same domain
            selected.append(art)
            selected_domains.add(domain)

    # Extract content from selected articles
    urls = [art.get("url", "") for art in selected if art.get("url")]
    if not urls:
        return selected

    extracted = tavily_extract(
        urls=urls,
        query=query,
        chunks_per_source=2,
        extract_depth="basic",
    )

    # Create URL to extracted content map
    extracted_map = {r.get("url", ""): r for r in extracted}

    # Enrich selected articles with extracted content
    for art in selected:
        url = art.get("url", "")
        if url in extracted_map:
            art["extracted_content"] = extracted_map[url].get("raw_content", "")
            art["content_summary"] = extracted_map[url].get("content", "")
        else:
            art["extracted_content"] = ""
            art["content_summary"] = art.get("content", "")[:200]

    return selected


def _detect_event_category(text: str) -> str:
    """
    Detect event category from text content.
    Returns the most likely category or "general_news".
    """
    text = text.lower()
    for category, keywords in EVENT_CATEGORIES.items():
        for kw in keywords:
            if kw in text:
                return category
    return "general_news"


def _detect_sentiment(text: str) -> str:
    """
    Detect sentiment from text content.
    Returns "positive", "negative", or "neutral".
    """
    text_lower = text.lower()

    # Check risk terms
    risk_count = sum(1 for t in RISK_TERMS if t in text_lower)
    # Check positive terms
    positive_count = sum(1 for t in POSITIVE_TERMS if t in text_lower)

    if risk_count > positive_count:
        return "negative"
    elif positive_count > risk_count:
        return "positive"
    else:
        return "neutral"


def build_evidence_output(
    profile: dict,
    query_plan: dict,
    bucket_results: dict[str, list[dict]],
    extracted_articles: list[dict],
) -> dict:
    """
    Build structured evidence output from extracted articles.

    Args:
        profile: Company profile dict
        query_plan: Query plan that was executed
        bucket_results: Raw results per bucket
        extracted_articles: Extracted and enriched articles

    Returns:
        Structured output dict with evidence_items and aggregated sentiment
    """
    evidence_items = []
    daily_sentiment = {}
    bucket_sentiment = {}

    for i, art in enumerate(extracted_articles):
        url = art.get("url", "")
        try:
            domain = urlparse(url).netloc.replace("www.", "")
        except Exception:
            domain = ""

        source_type = _get_source_type(domain)
        content = art.get("extracted_content", "") or art.get("content_summary", "")
        title = art.get("title", "")

        # Detect sentiment from content
        sentiment = _detect_sentiment(content + " " + title)

        # Detect event category
        event_cat = _detect_event_category(content + " " + title)

        # Detect relevance tags
        relevance_tags = []
        if any(kw in content for kw in ["机构", "基金", "举牌", "增持"]):
            relevance_tags.append("institutional")
        if any(kw in content for kw in ["公告", "年报", "季报"]):
            relevance_tags.append("official_disclosure")
        if any(kw in content for kw in ["风险", "亏损", "减持"]):
            relevance_tags.append("risk_signal")
        if len(relevance_tags) == 0:
            relevance_tags.append("general")

        # Determine evidence strength
        evidence_strength = "medium"
        if source_type == "official_media":
            evidence_strength = "strong"
        elif source_type == "social":
            evidence_strength = "weak"

        # Parse published date
        published_date = art.get("published_date", "")
        if not published_date:
            published_date = datetime.now().strftime("%Y-%m-%d")

        item = {
            "id": f"art_{i+1:03d}",
            "source": domain,
            "source_type": source_type,
            "published_date": published_date,
            "title": title,
            "content_summary": content[:300] if content else "",
            "relevance_tags": relevance_tags,
            "sentiment": sentiment,
            "event_category": event_cat,
            "evidence_strength": evidence_strength,
            "url": url,
        }
        evidence_items.append(item)

        # Aggregate by date
        date_key = published_date[:10] if published_date else "unknown"
        if date_key not in daily_sentiment:
            daily_sentiment[date_key] = {
                "sentiment": sentiment,
                "strength": evidence_strength,
                "key_events": [title],
            }
        else:
            # Override with stronger sentiment if evidence is strong
            if evidence_strength == "strong" and sentiment == "positive":
                daily_sentiment[date_key]["sentiment"] = "positive"
            elif evidence_strength == "strong" and sentiment == "negative":
                daily_sentiment[date_key]["sentiment"] = "negative"
            daily_sentiment[date_key]["key_events"].append(title)

    # Aggregate by bucket
    for bucket, articles in bucket_results.items():
        bucket_sentiment[bucket] = {
            "items": len(articles),
            "sentiment": "neutral",
        }
        if articles:
            sentiments = [_detect_sentiment(a.get("content", "") + " " + a.get("title", ""))
                         for a in articles]
            pos_count = sentiments.count("positive")
            neg_count = sentiments.count("negative")
            if pos_count > neg_count:
                bucket_sentiment[bucket]["sentiment"] = "positive"
            elif neg_count > pos_count:
                bucket_sentiment[bucket]["sentiment"] = "negative"

    # Generate major findings
    major_findings = []
    risk_signals = []
    uncertainties = []
    next_watch = []

    # Find strong evidence items
    strong_items = [e for e in evidence_items if e["evidence_strength"] == "strong"]

    if strong_items:
        major_findings.append(f"发现 {len(strong_items)} 条高可信度新闻事件")
        for item in strong_items[:3]:
            major_findings.append(f"- {item['title']}")

    # Risk signals
    risk_items = [e for e in evidence_items if e["sentiment"] == "negative"]
    if risk_items:
        risk_signals.append(f"发现 {len(risk_items)} 条负面新闻")
        for item in risk_items[:3]:
            risk_signals.append(f"- {item['title']}")
    else:
        risk_signals.append("未发现重大风险信号")

    # Overall sentiment verdict
    pos_count = sum(1 for e in evidence_items if e["sentiment"] == "positive")
    neg_count = sum(1 for e in evidence_items if e["sentiment"] == "negative")
    neu_count = len(evidence_items) - pos_count - neg_count

    if pos_count > neg_count:
        sentiment_verdict = "positive"
    elif neg_count > pos_count:
        sentiment_verdict = "negative"
    else:
        sentiment_verdict = "neutral"

    # Build output
    output = {
        "profile_summary": {
            "ticker": profile.get("ts_code", ""),
            "name": profile.get("name", ""),
            "industry": profile.get("industry", ""),
            "area": profile.get("area", ""),
        },
        "query_plan_executed": query_plan,
        "evidence_items": evidence_items,
        "aggregated": {
            "daily_sentiment": daily_sentiment,
            "bucket_sentiment": bucket_sentiment,
        },
        "major_findings": major_findings,
        "risk_signals": risk_signals,
        "uncertainties": uncertainties,
        "next_watch": next_watch,
        "sentiment_verdict": sentiment_verdict,
        "statistics": {
            "total_articles": len(evidence_items),
            "positive_count": pos_count,
            "negative_count": neg_count,
            "neutral_count": neu_count,
        },
    }

    return output


# ============================================================================
# HIGH-LEVEL TOOLS
# ============================================================================


@tool
def research_company_news(
    ticker: Annotated[str, "Stock ticker, e.g. 688333.SH"],
    start_date: Annotated[str | None, "Start date in yyyy-mm-dd format"] = None,
    end_date: Annotated[str | None, "End date in yyyy-mm-dd format"] = None,
    look_back_days: Annotated[int, "Days to look back if no dates provided"] = 7,
) -> str:
    """
    Structured company news research tool.
    Internally executes: company profile resolution -> query planning ->
    bucket search -> URL selection -> content extraction -> evidence output.

    This tool performs comprehensive news retrieval across multiple buckets:
    - official_disclosure: company announcements and disclosures
    - mainstream_news: general news coverage
    - sector_context: industry and sector news
    - public_discussion: social media discussion (Xueqiu, etc)
    - negative_risk: risk events (reductions, penalties, inquiries)
    - positive_news: positive events (repurchases, contracts, growth)

    Args:
        ticker: Stock ticker symbol
        start_date: Start date (optional, defaults to look_back_days ago)
        end_date: End date (optional, defaults to today)
        look_back_days: Days to look back if start_date not provided

    Returns:
        JSON string with structured news evidence
    """
    # Calculate date range if not provided
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        from dateutil.relativedelta import relativedelta
        start_dt = datetime.strptime(end_date, "%Y-%m-%d") - relativedelta(days=look_back_days)
        start_date = start_dt.strftime("%Y-%m-%d")

    # Step 1: Resolve company profile
    profile = resolve_company_profile(ticker)

    # Step 2: Build query plan
    query_plan = build_query_plan(profile)

    # Step 3: Execute bucket search
    bucket_results = {}
    for bucket, queries in query_plan.items():
        bucket_articles = []
        topic = "news" if bucket != "public_discussion" else "general"
        depth = "advanced" if bucket in ["official_disclosure", "negative_risk"] else "basic"

        for query in queries[:4]:  # max 4 queries per bucket
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
            bucket_articles.extend(results)

        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for art in bucket_articles:
            url = art.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(art)

        bucket_results[bucket] = unique_articles

    # Step 4: Select and extract
    # Flatten all articles for selection
    all_articles = []
    for bucket, articles in bucket_results.items():
        for art in articles:
            art["_bucket"] = bucket
        all_articles.extend(articles)

    # Score and select top articles
    company_name = profile.get("name", ticker)
    selected = select_and_extract(all_articles, f"{company_name} 主要事件", max_per_bucket=12)

    # Re-group by bucket for output
    selected_by_bucket = {}
    for art in selected:
        bucket = art.get("_bucket", "unknown")
        if bucket not in selected_by_bucket:
            selected_by_bucket[bucket] = []
        selected_by_bucket[bucket].append(art)

    # Step 5: Build evidence output
    output = build_evidence_output(profile, query_plan, selected_by_bucket, selected)

    return json.dumps(output, ensure_ascii=False, indent=2)


# ============================================================================
# MACRO NEWS RESEARCH (v4 - company-specific macro analysis)
# ============================================================================

# Macro channels per industry
INDUSTRY_MACRO_CHANNELS = {
    "国防军工": ["国防预算", "地缘政治", "军品订单", "原材料价格", "信贷环境"],
    "航空航天": ["国防预算", "民航订单", "原油价格", "地缘政治", "汇率"],
    "机械设备": ["制造业PMI", "原材料价格", "汇率", "信贷环境", "房地产投资"],
    "电子": ["半导体周期", "消费电子需求", "汇率", "原材料价格", "出口"],
    "医药": ["医保政策", "汇率", "消费支出", "大宗商品价格"],
    "汽车": ["新能源政策", "原材料价格", "汇率", "消费补贴", "房地产"],
    "能源": ["原油价格", "天然气价格", "汇率", "碳政策", "补贴政策"],
    "通信": ["运营商资本开支", "出口管制", "消费电子", "房地产"],
    "计算机": ["信创政策", "出口管制", "政府采购", "消费电子"],
}

# Default channels for unknown industries
DEFAULT_MACRO_CHANNELS = ["制造业PMI", "原材料价格", "汇率", "信贷环境", "消费支出"]

# High-quality macro news domains
MACRO_DOMAINS = [
    "eastmoney.com",
    "sina.com.cn",
    "finance.qq.com",
    "caixin.com",
    "cls.cn",
    "gov.cn",          # 政府官网
    "mof.gov.cn",      # 财政部
    "pboc.gov.cn",     # 央行
    "stats.gov.cn",    # 统计局
]


def resolve_macro_profile(industry: str, ticker: str = "") -> dict:
    """
    Resolve macro profile based on industry.

    Args:
        industry: Industry name from tushare
        ticker: Stock ticker for company name resolution

    Returns:
        dict with macro channels and query keywords
    """
    # Find matching channels
    matched_channels = []
    industry_lower = industry.lower() if industry else ""

    for ind_key, channels in INDUSTRY_MACRO_CHANNELS.items():
        if ind_key in industry or industry in ind_key:
            matched_channels = channels
            break

    if not matched_channels:
        matched_channels = DEFAULT_MACRO_CHANNELS

    # Resolve company name
    company_name = ticker
    if ticker:
        try:
            profile = resolve_company_profile(ticker)
            company_name = profile.get("name", ticker)
        except Exception:
            pass

    return {
        "industry": industry,
        "ticker": ticker,
        "company_name": company_name,
        "macro_channels": matched_channels,
    }


def build_macro_query_plan(profile: dict) -> dict[str, list[str]]:
    """
    Build targeted macro query plan from industry profile.

    Args:
        profile: Macro profile dict from resolve_macro_profile

    Returns:
        dict mapping channel type to list of queries
    """
    industry = profile.get("industry", "")
    company_name = profile.get("company_name", "")
    channels = profile.get("macro_channels", [])

    queries = {}

    # Map channels to query templates
    channel_query_map = {
        "国防预算": ["国防预算 2026", "军工订单 增长", "军费 增速"],
        "地缘政治": ["中东局势 军工", "伊朗 国防", "台海 军工", "地缘冲突 影响"],
        "军品订单": ["军工订单 增长", "军品 采购", "国防订单"],
        "原材料价格": ["钛合金 价格", "金属粉末 大宗商品", "原材料价格上涨 影响"],
        "汇率": ["人民币汇率 出口", "美元加息 影响", "汇率波动 出口"],
        "信贷环境": ["信贷宽松 制造业", "企业融资 成本", "银行贷款 制造业"],
        "制造业PMI": ["制造业PMI 2026", "工业生产 增长"],
        "消费支出": ["消费 增长", "居民消费 支出", "消费信心"],
        "房地产": ["房地产 投资", "房地产 需求", "基建 投资"],
        "原油价格": ["原油价格 上涨", "能源价格 通胀"],
        "新能源政策": ["新能源 补贴 政策", "新能源车 政策"],
        "半导体周期": ["半导体 周期", "芯片 行业 需求", "半导体 出口管制"],
        "出口": ["出口 增长", "外贸 形势", "出口订单"],
        "医保政策": ["医保 政策", "药品 集采", "医保谈判"],
        "碳政策": ["碳中和 政策", "碳交易"],
        "运营商资本开支": ["运营商 资本开支", "5G 投资"],
        "政府采购": ["政府采购 信创", "政府IT 支出"],
        "信创政策": ["信创政策", "国产替代"],
        "出口管制": ["出口管制 清单", "实体清单 影响"],
        "消费电子": ["消费电子 需求", "手机出货量"],
        "天然气价格": ["天然气价格 走势"],
        "补贴政策": ["政府补贴 制造业", "产业补贴"],
        "碳交易": ["碳交易 价格", "碳市场"],
    }

    for channel in channels:
        channel_queries = channel_query_map.get(channel, [f"{channel} 最新"])
        # Add industry context if possible
        if industry and len(industry) > 2:
            contextual_queries = [f"{industry} {channel}", channel]
            queries[channel] = list(set(contextual_queries))[:3]
        else:
            queries[channel] = channel_queries[:3]

    return queries


def _extract_macro_variable(article_content: str) -> dict | None:
    """
    Extract macro variable name and value from article content.
    Returns dict with variable, value, trend or None if not macro-related.
    """
    # Simple heuristic extraction
    macro_patterns = [
        (["利率", "联邦基金利率"], "美联储利率"),
        (["CPI", "通胀率", "通货膨胀"], "通胀率"),
        (["PMI", "采购经理指数"], "PMI"),
        (["GDP", "国内生产总值"], "GDP增速"),
        (["人民币", "美元", "汇率"], "汇率"),
        (["原油", "油价", "布伦特"], "原油价格"),
        (["国防预算", "军费", "国防支出"], "国防预算"),
        (["钛合金", "金属粉末", "原材料"], "原材料价格"),
    ]

    for keywords, var_name in macro_patterns:
        for kw in keywords:
            if kw in article_content:
                return {"variable": var_name, "found": True}

    return None


def _map_channel_confidence(article_content: str, channel: str) -> str:
    """Determine confidence level of macro->company transmission."""
    company_name = ""
    if company_name and company_name in article_content:
        return "high"
    # Check for specific mechanisms
    if "导致" in article_content or "因此" in article_content or "影响" in article_content:
        return "medium"
    return "low"


def build_macro_transmission_output(
    articles: list[dict],
    query_plan: dict,
    company_profile: dict,
) -> dict:
    """
    Build structured macro transmission analysis from extracted articles.

    Args:
        articles: List of extracted article dicts
        query_plan: The macro query plan that was executed
        company_profile: Company profile dict

    Returns:
        dict with macro_variables, transmission_channels, macro_verdict, key_watch
    """
    company_name = company_profile.get("company_name", "")
    industry = company_profile.get("industry", "")

    macro_variables = []
    transmission_channels = []
    key_watch = []

    # Define transmission channel templates
    channel_templates = {
        "国防预算": {
            "channel": "军工订单",
            "mechanism": "国防预算增加 → 军品需求扩大 → 军工企业订单增长",
        },
        "地缘政治": {
            "channel": "军工订单",
            "mechanism": "地缘政治紧张 → 国防支出预期上升 → 军品采购增加",
        },
        "军品订单": {
            "channel": "军工订单",
            "mechanism": "军品订单落地 → 公司直接受益 → 收入增长",
        },
        "原材料价格": {
            "channel": "成本压力",
            "mechanism": "原材料价格上涨 → 产品成本上升 → 毛利率承压",
        },
        "汇率": {
            "channel": "汇兑损益",
            "mechanism": "人民币贬值 → 出口收入增加 → 汇兑收益；进口成本上升",
        },
        "信贷环境": {
            "channel": "流动性",
            "mechanism": "信贷宽松 → 下游客户付款能力改善 → 公司现金流好转",
        },
        "制造业PMI": {
            "channel": "需求端",
            "mechanism": "PMI回升 → 制造业需求改善 → 公司订单预期好转",
        },
        "消费支出": {
            "channel": "需求端",
            "mechanism": "消费回升 → 下游需求改善 → 公司订单改善",
        },
        "原油价格": {
            "channel": "成本压力",
            "mechanism": "能源价格上涨 → 生产成本上升 → 毛利压缩",
        },
        "新能源政策": {
            "channel": "政策利好",
            "mechanism": "政策支持 → 行业需求扩容 → 公司订单增加",
        },
    }

    # Process articles by channel
    articles_by_channel = {}
    for art in articles:
        content = art.get("content_summary", "") or art.get("extracted_content", "") or ""
        title = art.get("title", "")
        combined = content + " " + title

        # Find which channel this article belongs to
        for channel, queries in query_plan.items():
            for q in queries:
                if q.lower() in combined.lower():
                    if channel not in articles_by_channel:
                        articles_by_channel[channel] = []
                    articles_by_channel[channel].append(art)
                    break

    # Build transmission channels
    for channel, arts in articles_by_channel.items():
        template = channel_templates.get(channel, {
            "channel": channel,
            "mechanism": f"{channel}变化通过行业传导链影响公司",
        })

        # Extract key content from articles
        key_findings = []
        for art in arts[:2]:
            title = art.get("title", "")
            content = (art.get("content_summary", "") or "")[:200]
            if title:
                key_findings.append(f"- {title}")

        # Build impact on company
        impact = _build_impact_statement(
            channel, template["channel"], company_name, industry, arts
        )

        # Determine confidence
        confidence = "medium"
        for art in arts:
            content = (art.get("content_summary", "") + " " + art.get("title", "")).lower()
            if company_name.lower() in content:
                confidence = "high"
                break
            if len(key_findings) > 1:
                confidence = "medium"

        transmission_channels.append({
            "channel": template["channel"],
            "mechanism": template["mechanism"],
            "impact_on_company": impact,
            "confidence": confidence,
            "key_findings": key_findings,
        })

    # Ensure at least the major channels are covered
    major_channels = ["国防预算", "地缘政治", "原材料价格", "汇率", "信贷环境"]
    covered_channels = {c["channel"] for c in transmission_channels}

    for channel in major_channels:
        if channel not in covered_channels:
            template = channel_templates.get(channel, {
                "channel": channel,
                "mechanism": f"{channel}通过行业传导影响公司",
            })
            transmission_channels.append({
                "channel": template["channel"],
                "mechanism": template["mechanism"],
                "impact_on_company": f"需关注{channel}变化对铂力特的影响",
                "confidence": "low",
                "key_findings": [],
            })

    # Build macro verdict
    pos_channels = sum(
        1 for c in transmission_channels if c["confidence"] in ["high", "medium"]
    )
    neg_channels = sum(
        1 for c in transmission_channels
        if c["channel"] in ["成本压力", "流动性"] and c["confidence"] in ["high", "medium"]
    )

    if pos_channels > neg_channels + 1:
        macro_verdict = f"偏多（{pos_channels}个传导通道显示利好，对{company_name}形成支撑）"
    elif neg_channels > pos_channels:
        macro_verdict = f"偏空（{neg_channels}个传导通道显示压力，需关注成本和流动性风险）"
    else:
        macro_verdict = f"中性（多空交织，需进一步观察各通道演化）"

    # Build key watch items
    for c in transmission_channels:
        if c["confidence"] in ["high", "medium"] and c["key_findings"]:
            key_watch.append(f"{c['channel']}：{'；'.join(c['key_findings'][:2])}")

    return {
        "macro_variables_found": [
            {"variable": c["channel"], "status": "analyzed"}
            for c in transmission_channels
        ],
        "transmission_channels": transmission_channels,
        "macro_verdict": macro_verdict,
        "key_watch": key_watch[:5],
        "company_name": company_name,
        "industry": industry,
    }


def _build_impact_statement(
    channel: str,
    channel_name: str,
    company_name: str,
    industry: str,
    articles: list[dict],
) -> str:
    """Build a specific impact statement on the company."""
    # Extract concrete data points from articles
    data_points = []
    for art in articles:
        content = (art.get("content_summary", "") or "")[:300]
        # Try to find numbers
        import re
        numbers = re.findall(r'\d+\.?\d*%', content)
        if numbers:
            data_points.extend(numbers[:2])

    if data_points:
        data_str = "；".join(data_points[:3])
        return f"{company_name}（{industry}）受{channel_name}影响，当前{data_str}"

    return f"{company_name}处于{industry}行业，需关注{channel}变化对公司的具体传导效应"


@tool
def research_macro_news(
    ticker: Annotated[str, "Stock ticker, e.g. 688333.SH"],
    industry: Annotated[str, "Company industry, e.g. 机械设备"],
    start_date: Annotated[str | None, "Start date in yyyy-mm-dd format"] = None,
    end_date: Annotated[str | None, "End date in yyyy-mm-dd format"] = None,
    look_back_days: Annotated[int, "Days to look back if no dates provided"] = 7,
) -> str:
    """
    Structured macro news research tool for a specific company.

    This tool performs targeted macro news retrieval and transmission analysis:
    - Resolves macro profile based on company's industry
    - Generates industry-specific macro queries (not generic global queries)
    - Searches high-quality macro sources (government, official financial)
    - Analyzes transmission channels from macro variables to THIS company
    - Outputs structured analysis with channel/mechanism/impact format

    Args:
        ticker: Stock ticker symbol
        industry: Company industry name
        start_date: Start date (optional, defaults to look_back_days ago)
        end_date: End date (optional, defaults to today)
        look_back_days: Days to look back if start_date not provided

    Returns:
        JSON string with structured macro transmission analysis
    """
    # Calculate date range if not provided
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        from dateutil.relativedelta import relativedelta
        start_dt = datetime.now() - relativedelta(days=look_back_days)
        start_date = start_dt.strftime("%Y-%m-%d")

    # Step 1: Resolve company and macro profile
    company_profile = resolve_company_profile(ticker)
    macro_profile = resolve_macro_profile(industry, ticker)

    # Step 2: Build macro query plan
    query_plan = build_macro_query_plan(macro_profile)

    # Step 3: Execute searches per channel
    all_articles = []
    channel_results = {}

    for channel, queries in query_plan.items():
        channel_articles = []
        for query in queries[:3]:  # max 3 queries per channel
            results = tavily_search(
                query=query,
                topic="news",
                search_depth="advanced",
                max_results=5,
                include_domains=MACRO_DOMAINS,
                exclude_domains=LOW_QUALITY_EXCLUDE,
                start_date=start_date,
                end_date=end_date,
            )
            channel_articles.extend(results)

        # Deduplicate
        seen_urls = set()
        unique_arts = []
        for art in channel_articles:
            url = art.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_arts.append(art)

        channel_results[channel] = unique_arts
        all_articles.extend(unique_arts)

    # Step 4: Select top articles
    company_name = company_profile.get("name", ticker)
    selected = select_and_extract(all_articles, f"{company_name} 宏观 影响", max_per_bucket=15)

    # Step 5: Build transmission output
    output = build_macro_transmission_output(selected, query_plan, company_profile)

    return json.dumps(output, ensure_ascii=False, indent=2)


@tool
def get_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """
    Retrieve news data for a given ticker symbol.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol
        start_date (str): Start date in yyyy-mm-dd format
        end_date (str): End date in yyyy-mm-dd format
    Returns:
        str: A formatted string containing news data
    """
    return route_to_vendor("get_news", ticker, start_date, end_date)

@tool
def get_global_news(
    curr_date: Annotated[str, "Current date in yyyy-mm-dd format"],
    look_back_days: Annotated[int, "Number of days to look back"] = 7,
    limit: Annotated[int, "Maximum number of articles to return"] = 5,
) -> str:
    """
    Retrieve global news data.
    Uses the configured news_data vendor.
    Args:
        curr_date (str): Current date in yyyy-mm-dd format
        look_back_days (int): Number of days to look back (default 7)
        limit (int): Maximum number of articles to return (default 5)
    Returns:
        str: A formatted string containing global news data
    """
    return route_to_vendor("get_global_news", curr_date, look_back_days, limit)

@tool
def get_insider_transactions(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve insider transaction information about a company.
    Uses the configured news_data vendor.
    Args:
        ticker (str): Ticker symbol of the company
    Returns:
        str: A report of insider transaction data
    """
    return route_to_vendor("get_insider_transactions", ticker)
