"""Shared prompt instructions for all agents."""

DATA_ACCURACY_INSTRUCTION = """
MANDATORY CITATION RULE: Every time you use a NUMBER, PERCENTAGE, or SPECIFIC DATA POINT, you MUST cite its source.

Format: "source_report: [section_name] - [metric] = [value]"
Examples:
- "fundamentals_report: Cash Flow Statement - Operating CF = 0.96B CNY"
- "fundamentals_report: Income Statement - Q3 2025 Revenue = 1,160.73M CNY"
- "market_report: Technical Summary - Stock is above 200-day SMA"
- "sentiment_report: Key Coverage Theme - High Insider Ownership"

RULES:
1. ALWAYS cite when using numbers or specific data
2. If you cannot trace a number to a source, do NOT use it
3. After citing data, verify the scale makes sense

Failure to cite = hallucination. Trace every number.
"""
