from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create a custom config
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "dashscope"       # Use DashScope (国内可用)
config["deep_think_llm"] = "glm-5"         # Deep thinking model
config["quick_think_llm"] = "glm-5"        # Quick thinking model
config["output_language"] = "Chinese"      # Chinese output
config["max_debate_rounds"] = 1            # Debate rounds
config["max_risk_discuss_rounds"] = 1      # Risk discussion rounds

# Default config already uses Tushare citydata proxy for A-share market data.

# Initialize with custom config
ta = TradingAgentsGraph(debug=True, config=config)

# forward propagate
_, decision = ta.propagate("688333.SH", "2025-04-02")
print(decision)

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
