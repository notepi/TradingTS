from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_company_industry,
    get_language_instruction,
)
from tradingagents.agents.utils.news_data_tools import (
    research_macro_news,
)
from tradingagents.dataflows.config import get_config


def create_news_analyst(llm):
    def news_analyst_node(state):
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        instrument_context = build_instrument_context(ticker)

        # Resolve industry for targeted macro research
        industry = get_company_industry(ticker)

        tools = [
            research_macro_news,
        ]

        system_message = (
            "You are a news researcher tasked with analyzing macro factors that affect a specific company. "
            "Your goal is to identify macro variables and explain HOW they transmit to THIS company, not write a generic global macro report.\n\n"
            "IMPORTANT: Use the research_macro_news(ticker, industry, start_date, end_date, look_back_days) tool FIRST to get structured macro transmission analysis. "
            "This tool returns JSON containing:\n"
            "- transmission_channels: each with channel name, mechanism, and specific impact_on_company\n"
            "- macro_verdict: overall assessment\n"
            "- key_watch: specific items to monitor\n\n"
            "After receiving the JSON output, write a company-specific macro analysis report that:\n"
            "1. Lists the key macro variables found (e.g. interest rates, raw material prices, defense budget)\n"
            "2. For EACH macro variable, explains the transmission channel to the company with SPECIFIC numbers when available\n"
            "3. Provides a clear macro verdict on how these factors collectively affect the company\n"
            "4. Lists actionable watch items for traders\n\n"
            "CRITICAL FORMATTING RULE: "
            "Each macro variable section must end with a line: '→ 对[公司名]的影响：[具体传导结论]' "
            "Do NOT write paragraphs that don't connect to the specific company. "
            "If a macro point doesn't have a clear transmission to this company, either find the connection or note it as 'indirect/unclear'.\n\n"
            "Provide specific, actionable insights with supporting evidence to help traders make informed decisions."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + f"\n\nCompany context: ticker={ticker}, industry={industry or 'unknown'}"
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "news_report": report,
        }

    return news_analyst_node
