from langchain_core.messages import AIMessage
import time
import json


def create_peter_lynch_researcher(llm, memory):
    def peter_lynch_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        peter_lynch_history = investment_debate_state.get("peter_lynch_history", "")

        current_response = investment_debate_state.get("current_response", "")
        market_research_report = state["market_report"]
        sentiment_report = state["sentiment_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        prompt = f"""You are a Peter Lynch-style Analyst focusing on stock classification and value-growth opportunities.

Your task is to first classify the stock into one of 6 categories, then evaluate its potential based on Lynch's principles.

Stock Classification (6 Types):
1. Slow Grower: Large, stable companies with low growth. Focus on dividend stability.
2. Stalwart: Medium-growth, quality companies. Good for steady returns.
3. Fast Grower: Small-to-mid size, high growth rate. Best potential for 10x returns.
4. Cyclical: Performance tied to industry cycles. Timing is critical.
5. Turnaround: Companies recovering from problems. High risk, high reward.
6. Asset Play: Hidden asset value not reflected in stock price.

Key Analysis Points:
- PEG Ratio: P/E / Growth Rate. < 1 indicates undervalued.
- Business Understanding: What do they sell? Who buys? Why do they win?
- Growth Sustainability: Is revenue/profit growth real and sustainable?
- Market Misunderstanding: Is the market overlooking or mispricing this stock?
- Insider Buying/Share Buybacks: Signals management confidence.
- 13 Lynch Criteria: boring name, boring business, institutional neglect, etc.

Resources available:
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
Company fundamentals report: {fundamentals_report}
Conversation history of the debate: {history}
Last argument from other analysts: {current_response}
Reflections from similar situations and lessons learned: {past_memory_str}

Output Format:
1. First, classify this stock into one of the 6 types with justification
2. Then, provide Lynch-style analysis:
   - PEG assessment (if data available)
   - Business quality evaluation
   - Growth sustainability
   - Market expectation gap
3. Finally, your investment perspective (not simple buy/sell, but "worth deeper research" / "wait for better entry" / "potential 10x candidate")
4. Respond to the previous analyst's argument with Lynch-style reasoning

Keep conversational and engaging with other analysts.
"""

        response = llm.invoke(prompt)

        argument = f"Peter Lynch Analyst: {response.content}"

        new_investment_debate_state = {
            "history": history + "\n" + argument,
            "bull_history": investment_debate_state.get("bull_history", ""),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "peter_lynch_history": peter_lynch_history + "\n" + argument,
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
        }

        return {"investment_debate_state": new_investment_debate_state}

    return peter_lynch_node