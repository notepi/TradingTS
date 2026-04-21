"""测试单个 Peter Lynch Researcher"""
import os
from dotenv import load_dotenv
load_dotenv()

from tradingagents.agents.researchers.peter_lynch_researcher import create_peter_lynch_researcher
from tradingagents.agents.utils.memory import FinancialSituationMemory
from tradingagents.default_config import DEFAULT_CONFIG

# 配置
TICKER = "688333.SH"
DATE = "2026-04-21"

# 加载已有报告（从之前的分析结果）
results_path = f"results/{TICKER}/{DATE}/dashboard_20260421_205218"

# 尝试加载
try:
    market_report = open(f"{results_path}/1_analysts/market.md").read()
    fundamentals_report = open(f"{results_path}/1_analysts/fundamentals.md").read()
    news_report = open(f"{results_path}/1_analysts/news.md").read()
    sentiment_report = open(f"{results_path}/1_analysts/sentiment.md").read()
except FileNotFoundError:
    print("报告文件不存在，请先运行完整分析")
    exit(1)

# 构造 state
state = {
    "market_report": market_report,
    "fundamentals_report": fundamentals_report,
    "news_report": news_report,
    "sentiment_report": sentiment_report,
    "investment_debate_state": {
        "history": "",
        "peter_lynch_history": "",
        "current_response": "",
        "count": 0,
    }
}

# 创建 LLM
from langchain_openai import ChatOpenAI

api_key = os.getenv("DASHSCOPE_API_KEY")
llm = ChatOpenAI(
    model=DEFAULT_CONFIG["deep_think_llm"],
    base_url=DEFAULT_CONFIG["backend_url"],
    api_key=api_key,
)

# 创建 memory（空记忆）
memory = FinancialSituationMemory("test_memory")

# 创建并运行 agent
peter_lynch_node = create_peter_lynch_researcher(llm, memory)
result = peter_lynch_node(state)

# 输出结果
print("=" * 60)
print(result["investment_debate_state"]["current_response"])