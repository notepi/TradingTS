import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

# Load environment variables from .env file (tokens only)
load_dotenv()


def load_config() -> dict:
    """Load config from config.yaml, merge with defaults."""
    config = DEFAULT_CONFIG.copy()

    # Load config.yaml if exists
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f) or {}

        # Apply yaml config to config dict
        llm = yaml_config.get("llm", {})
        if llm.get("provider"):
            config["llm_provider"] = llm["provider"]
        if llm.get("model"):
            config["deep_think_llm"] = llm["model"]
            config["quick_think_llm"] = llm["model"]

        output = yaml_config.get("output", {})
        if output.get("language"):
            config["output_language"] = output["language"]

    return config


# Create config
config = load_config()

# Initialize with custom config
ta = TradingAgentsGraph(debug=True, config=config)

# Get ticker from config.yaml or use default
ticker = "688333.SH"
config_path = Path(__file__).parent / "config.yaml"
if config_path.exists():
    with open(config_path, encoding="utf-8") as f:
        yaml_config = yaml.safe_load(f) or {}
    stock_list = yaml_config.get("stock_list", [])
    if stock_list:
        ticker = stock_list[0]

# forward propagate
_, decision = ta.propagate(ticker, "2025-04-02")
print(decision)

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
