from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.config import get_config

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create a custom config with defaults
config = DEFAULT_CONFIG.copy()

# Override data_vendors from config.yaml if present
yaml_config = get_config()
if "data_vendors" in yaml_config:
    config["data_vendors"] = yaml_config["data_vendors"]

# Use LLM settings from config.yaml (don't hardcode gpt models)
if "llm_provider" in yaml_config:
    config["llm_provider"] = yaml_config["llm_provider"]
if "deep_think_llm" in yaml_config:
    config["deep_think_llm"] = yaml_config["deep_think_llm"]
if "quick_think_llm" in yaml_config:
    config["quick_think_llm"] = yaml_config["quick_think_llm"]

config["max_debate_rounds"] = 1  # Increase debate rounds

# Initialize with custom config
ta = TradingAgentsGraph(debug=True, config=config)

# forward propagate
_, decision = ta.propagate("600519.SH", "2024-05-10")
print(decision)

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
