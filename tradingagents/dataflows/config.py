import tradingagents.default_config as default_config
from pathlib import Path
from typing import Dict, Optional

import yaml

# Use default config but allow it to be overridden
_config: Optional[Dict] = None


def _load_yaml_config() -> Dict:
    """Load configuration from config.yaml if it exists."""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def initialize_config():
    """Initialize the configuration with default values and yaml overrides."""
    global _config
    if _config is None:
        _config = default_config.DEFAULT_CONFIG.copy()
        # Override data_vendors from config.yaml if present
        yaml_config = _load_yaml_config()
        if "data_vendors" in yaml_config:
            _config["data_vendors"] = yaml_config["data_vendors"]


def set_config(config: Dict):
    """Update the configuration with custom values."""
    global _config
    if _config is None:
        initialize_config()
    _config.update(config)


def get_config() -> Dict:
    """Get the current configuration."""
    if _config is None:
        initialize_config()
    return _config.copy()


# Initialize with default config
initialize_config()
