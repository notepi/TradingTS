import tradingagents.default_config as default_config
from typing import Dict

_config: Dict = None


def initialize_config():
    """初始化配置（直接使用 DEFAULT_CONFIG）"""
    global _config
    _config = default_config.DEFAULT_CONFIG.copy()


def set_config(config: Dict):
    """更新配置"""
    global _config
    if _config is None:
        initialize_config()
    _config.update(config)


def get_config() -> Dict:
    """获取当前配置"""
    if _config is None:
        initialize_config()
    return _config.copy()
