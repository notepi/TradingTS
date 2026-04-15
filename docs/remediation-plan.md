# TradingTS 代码问题分析与修复计划

## Context

ChatGPT 对 TradingTS 代码进行了审查，发现代码实现与文档描述存在显著偏差。本计划旨在系统性地修复这些问题，提升代码与文档的一致性，以及整体的工程化水平。

---

## 问题汇总

### P1 - 关键功能问题（需立即修复）

| # | 问题 | 位置 |
|---|------|------|
| P1-1 | alpha_vantage 函数名不匹配：`get_stock` vs 期望的 `get_stock_data` | `alpha_vantage_stock.py:4` |
| P1-2 | alpha_vantage 函数名不匹配：`get_indicator` vs 期望的 `get_indicators` | `alpha_vantage_indicator.py:3` |
| P1-3 | `__init__.py` 未导入 alpha_vantage_news，导致自动发现失败 | `__init__.py:1-13` |
| P1-4 | `config.yaml` 缺少 alpha_vantage 的 vendor_paths | `config.yaml:25-27` |
| P1-5 | Market/Social/News Analyst 工具硬编码，只有 Fundamentals 用 load_agent_tools() | `market_analyst.py:18`, `social_media_analyst.py:11`, `news_analyst.py:16` |
| P1-6 | News Analyst 遗漏 `get_insider_transactions` 工具 | `news_analyst.py:16-19` |
| P1-7 | interface.py 静默吞掉异常，难以调试 | `interface.py:96-97` |

### P2 - 配置/文档问题（应尽快修复）

| # | 问题 | 位置 |
|---|------|------|
| P2-1 | `max_debate_rounds`, `max_risk_discuss_rounds`, `max_recur_limit` 未被合并到 DEFAULT_CONFIG | `default_config.py:49-70` |
| P2-2 | `tool_vendors` 配置不生效 | `default_config.py` |
| P2-3 | `output_language` 配置不生效 | `default_config.py` |
| P2-4 | Analyst/Researcher/Trader 使用 quick_thinking_llm 而非 deep_thinking_llm | `setup.py:59-85` |
| P2-5 | recursion_limit 硬编码 100，文档描述 150 | `propagation.py:14` |
| P2-6 | Docs 陈旧：`indicator_docs` 已被代码读取但文档说没有 | `dataflow-architecture.md:84` |

### P3 - 测试性问题（长期改进）

| # | 问题 |
|---|------|
| P3-1 | 缺少依赖导致 pytest 在收集阶段失败 |
| P3-2 | 缺少多数据源切换的集成测试 |
| P3-3 | 缺少工具配置一致性验证测试 |

---

## 修复计划

### Phase 1: P1-1 ~ P1-4（多数据源切换）

**Step 1.1**: 修复 `alpha_vantage_stock.py` 函数名
- 文件: `tradingagents/dataflows/alpha_vantage_stock.py`
- 将 `get_stock` 重命名为 `get_stock_data`

**Step 1.2**: 修复 `alpha_vantage_indicator.py` 函数名
- 文件: `tradingagents/dataflows/alpha_vantage_indicator.py`
- 将 `get_indicator` 重命名为 `get_indicators`

**Step 1.3**: 更新 `alpha_vantage.py` 导入
- 文件: `tradingagents/dataflows/alpha_vantage.py`
- 更新导入语句匹配新函数名

**Step 1.4**: 添加 alpha_vantage_news 到 `__init__.py`
- 文件: `tradingagents/dataflows/__init__.py`
- 添加 `from .alpha_vantage_news import get_news, get_global_news, get_insider_transactions`

**Step 1.5**: 添加 alpha_vantage 到 vendor_paths
- 文件: `tradingagents/config.yaml`
- 添加 `alpha_vantage: "tradingagents.dataflows"`

**Step 1.6**: 添加异常日志
- 文件: `tradingagents/dataflows/interface.py`
- 将静默 `pass` 改为 `logging.debug()`

---

### Phase 2: P1-5 ~ P1-6（工具配置化）

**Step 2.1**: 重构 market_analyst.py
- 文件: `tradingagents/agents/analysts/market_analyst.py`
- 将硬编码 `tools = [get_stock_data, get_indicators]` 改为 `tools = load_agent_tools("market_analyst")`
- 保留 `get_stock_data` 和 `get_indicators` 导入（用于类型提示）

**Step 2.2**: 重构 social_media_analyst.py
- 文件: `tradingagents/agents/analysts/social_media_analyst.py`
- 将硬编码 `tools = [get_news]` 改为 `tools = load_agent_tools("social_analyst")`

**Step 2.3**: 重构 news_analyst.py
- 文件: `tradingagents/agents/analysts/news_analyst.py`
- 将硬编码 `tools = [get_news, get_global_news]` 改为 `tools = load_agent_tools("news_analyst")`
- 这会自动包含 `get_insider_transactions`

---

### Phase 3: P2-1 ~ P2-3（配置合并）

**Step 3.1**: 扩展 default_config.py 合并逻辑
- 文件: `tradingagents/default_config.py`
- 添加 `max_debate_rounds`, `max_risk_discuss_rounds`, `max_recur_limit` 合并
- 添加 `tool_vendors` 合并
- 添加 `output_language` 合并（从 `output.language` 路径）

---

### Phase 4: P2-4 ~ P2-5（Graph 执行）

**Step 4.1**: 修复 setup.py LLM 使用
- 文件: `tradingagents/graph/setup.py`
- 将 Market/Social/News/Fundamentals Analyst 改为使用 `deep_thinking_llm`
- 将 Bull/Bear Researcher 改为使用 `deep_thinking_llm`
- 将 Trader 改为使用 `deep_thinking_llm`

**Step 4.2**: 修复 propagation.py recursion_limit
- 文件: `tradingagents/graph/propagation.py`
- 将默认值从 `100` 改为 `150`

---

### Phase 5: P2-6（文档修复）

**Step 5.1**: 更新 dataflow-architecture.md
- 文件: `docs/dataflow-architecture.md`
- 修正第84行关于 `indicator_docs` 的描述

---

### Phase 6: P3（测试体系）

**Step 6.1**: 添加依赖到 requirements-dev.txt 或 pyproject.toml
- 添加 `langchain_openai`, `questionary`, `stockstats`

**Step 6.2**: 创建测试文件
- `tests/test_multi_vendor_registration.py`
- `tests/test_tool_configurability.py`

---

## 关键文件清单

| 文件 | 修改类型 |
|------|----------|
| `tradingagents/dataflows/alpha_vantage_stock.py` | 函数重命名 |
| `tradingagents/dataflows/alpha_vantage_indicator.py` | 函数重命名 |
| `tradingagents/dataflows/alpha_vantage.py` | 导入更新 |
| `tradingagents/dataflows/__init__.py` | 添加 alpha_vantage_news 导入 |
| `tradingagents/dataflows/interface.py` | 添加异常日志 |
| `tradingagents/config.yaml` | 添加 alpha_vantage 路径 |
| `tradingagents/agents/analysts/market_analyst.py` | 使用 load_agent_tools() |
| `tradingagents/agents/analysts/social_media_analyst.py` | 使用 load_agent_tools() |
| `tradingagents/agents/analysts/news_analyst.py` | 使用 load_agent_tools() |
| `tradingagents/default_config.py` | 扩展配置合并 |
| `tradingagents/graph/setup.py` | 修复 LLM 类型 |
| `tradingagents/graph/propagation.py` | 修复 recursion_limit |
| `docs/dataflow-architecture.md` | 修复陈旧描述 |

---

## 验证方案

1. **多数据源切换验证**:
   ```bash
   python -c "from tradingagents.dataflows.interface import _VENDOR_REGISTRY; print('alpha_vantage' in str(_VENDOR_REGISTRY))"
   ```

2. **工具配置化验证**:
   ```bash
   python -c "from tradingagents.agents.utils.agent_utils import load_agent_tools; print(load_agent_tools('news_analyst'))"
   ```

3. **配置合并验证**:
   ```bash
   python -c "from tradingagents.default_config import DEFAULT_CONFIG; print(DEFAULT_CONFIG.get('max_debate_rounds'))"
   ```

4. **端到端运行**:
   ```bash
   tradingagents test 688333.SH --date 2026-04-14
   ```

5. **测试**:
   ```bash
   python3 -m pytest -q
   ```
