"""从 tools_registry.yaml 动态加载 indicator_docs"""

import yaml
from pathlib import Path


def get_indicator_docs(vendor: str = "tushare") -> str:
    """从 tools_registry.yaml 动态读取 indicator_docs

    Args:
        vendor: 数据源 vendor 名，默认 tushare

    Returns:
        str: indicator_docs 字段内容，如果不存在返回空字符串
    """
    config_path = Path(__file__).parent.parent.parent.parent / "datasource" / "tools" / "tools_registry.yaml"
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    tool_config = config.get("tools", {}).get("get_indicators", {})
    vendor_config = tool_config.get("vendors", {}).get(vendor, {})
    return vendor_config.get("indicator_docs", "")
