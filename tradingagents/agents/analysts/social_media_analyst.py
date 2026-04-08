from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import time
import json
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction
from tradingagents.agents.utils.news_data_tools import research_company_news
from tradingagents.dataflows.config import get_config


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            research_company_news,
        ]

        system_message = (
            "You are a stock news and sentiment analyst. Your task is to analyze company news and public sentiment.\n\n"
            "IMPORTANT: Use the research_company_news(ticker, start_date, end_date, look_back_days) tool first to "
            "get structured news data. This tool performs comprehensive multi-bucket search across:\n"
            "- official_disclosure (announcements)\n"
            "- mainstream_news (general news)\n"
            "- sector_context (industry news)\n"
            "- public_discussion (social media)\n"
            "- negative_risk (risk events)\n"
            "- positive_news (positive events)\n\n"
            "After receiving the structured JSON output, analyze the evidence items and write a comprehensive report.\n\n"
            "Your analysis should:\n"
            "1. Summarize the major findings from high-confidence sources\n"
            "2. Distinguish between confirmed facts, media interpretation, and speculation\n"
            "3. Identify key risk signals and positive drivers\n"
            "4. Assess overall sentiment and its implications for traders\n\n"
            "Provide specific, actionable insights with supporting evidence to help traders make informed decisions.\n\n"
            "IMPORTANT - 分析范围约束：\n"
            "- 你的职责是分析公司新闻和公众情绪，不是技术分析\n"
            "- 禁止在报告中包含：股价涨跌幅计算、最大回撤、夏普比率等技术指标\n"
            "- 如需引用市场数据，只引用 news_report 或 market_report 中已有的内容，不要自行计算或编造数字\n"
            "- 市场/技术分析属于 market_analyst 的职责，你的报告应聚焦于：\n"
            "  * 重大新闻事件识别和解读\n"
            "  * 公众/机构情绪评估\n"
            "  * 舆情风险信号\n\n"
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
            "sentiment_report": report,
        }

    return social_media_analyst_node
