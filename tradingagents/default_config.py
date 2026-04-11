import os
from pathlib import Path
import yaml

# 原项目的真正默认值
_BASE_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings - 原项目默认值
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    "backend_url": "https://api.openai.com/v1",
    "google_thinking_level": None,
    "openai_reasoning_effort": None,
    "anthropic_effort": None,
    "output_language": "English",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor - 原项目默认值
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "tool_vendors": {},
    "vendor_paths": {},
}


def _load_yaml_config() -> dict:
    """Load config.yaml from project root."""
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


# 构建最终配置 = 原项目默认值 + yaml 覆盖
DEFAULT_CONFIG = _BASE_CONFIG.copy()
_yaml = _load_yaml_config()

# 合并 data_vendors（如 yaml 有定义）
if "data_vendors" in _yaml:
    DEFAULT_CONFIG["data_vendors"] = _yaml["data_vendors"]

# 合并 LLM 配置（扁平格式）
if "llm_provider" in _yaml:
    DEFAULT_CONFIG["llm_provider"] = _yaml["llm_provider"]
if "deep_think_llm" in _yaml:
    DEFAULT_CONFIG["deep_think_llm"] = _yaml["deep_think_llm"]
if "quick_think_llm" in _yaml:
    DEFAULT_CONFIG["quick_think_llm"] = _yaml["quick_think_llm"]
if "backend_url" in _yaml:
    DEFAULT_CONFIG["backend_url"] = _yaml["backend_url"]

# 合并 vendor_paths（如 yaml 有定义）
if "vendor_paths" in _yaml:
    DEFAULT_CONFIG["vendor_paths"] = _yaml["vendor_paths"]
