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
| P2-4 | Analyst/Researcher/Trader 使用 quick_thinking_llm 而非 deep_thinking_llm | `setup.py:59-85` | ⚠️ 暂不修复 |
| P2-5 | recursion_limit 硬编码 100，文档描述 150 | `propagation.py:14` | ⚠️ 暂不修复 |
| P2-6 | Docs 陈旧：`indicator_docs` 已被代码读取但文档说没有 | `dataflow-architecture.md:84` |
| P2-7 | agent-tools-configuration.md 声称"无需改任何 analyst 代码"，但实际 Market/Social/News Analyst 都是硬编码 | `agent-tools-configuration.md:5,163` |

### P3 - 测试性问题（长期改进）

| # | 问题 |
|---|------|
| P3-1 | 缺少依赖导致 pytest 在收集阶段失败 |
| P3-2 | 缺少多数据源切换的集成测试 |
| P3-3 | 缺少工具配置一致性验证测试 |

---

## 修复计划

### Phase 1: P1-1 ~ P1-4（多数据源切换 - 架构修正）

**架构目标**: 数据源放在 `datasource/` 目录，每个独立；`tradingagents/` 是抽象层与数据源无关。

**数据流机制**:
- `tools_registry.yaml` — 工具的 category/vendors 定义，用于 `interface.py` 路由发现
- `@auto_tool(description="...")` — 提供 LLM 工具描述，注册到 `TOOL_REGISTRY`
- `agents_registry.yaml` — 配置智能体能用什么工具（懒加载）
- `load_agent_tools()` — 从 `TOOL_REGISTRY` 取工具
- `llm.bind_tools(tools)` — 发送工具 schema 给 LLM

**Step 1.1**: 创建 `datasource/yfinance/` 目录并迁移文件
- 创建 `datasource/yfinance/__init__.py`
- 迁移 `tradingagents/dataflows/yfinance_news.py` → `datasource/yfinance/news.py`
- 迁移 `tradingagents/dataflows/y_finance.py` → `datasource/yfinance/stock.py`
- 迁移 `tradingagents/dataflows/stockstats_utils.py` → `datasource/yfinance/stockstats_utils.py`
- 确保 `@auto_tool` 装饰器正常工作

**Step 1.2**: 创建 `datasource/alpha_vantage/` 目录并迁移文件
- 创建 `datasource/alpha_vantage/__init__.py`
- 迁移 `tradingagents/dataflows/alpha_vantage_*.py` → `datasource/alpha_vantage/`
- 修复函数名：`get_stock` → `get_stock_data`, `get_indicator` → `get_indicators`
- 迁移 `alpha_vantage_common.py` → `datasource/alpha_vantage/common.py`

**Step 1.3**: 更新 `config.yaml` 的 vendor_paths
- 文件: `tradingagents/config.yaml`
- `yfinance: "datasource.yfinance"`（而非 `tradingagents.dataflows`）
- `alpha_vantage: "datasource.alpha_vantage"`（新增）
- `tushare: "datasource.tushare"`（已是正确格式）

**Step 1.4**: 清理 `tradingagents/dataflows/`
- 移除已迁移的 yfinance 和 alpha_vantage 相关文件
- 保留 `interface.py`, `decorators.py`, `config.py` 等抽象层文件

**Step 1.5**: 添加异常日志
- 文件: `tradingagents/dataflows/interface.py`
- 将静默 `pass` 改为 `logging.debug()`

**Step 1.6**: 验证 `discover_and_register()` 正确发现 `datasource.*` 路径下的工具

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

### Phase 4: P2-4 ~ P2-5（Graph 执行 - 暂不修改）

> 用户选择暂不修改 Graph 执行相关的配置偏差。

---

### Phase 5: P2-6 ~ P2-7（文档修复）

**Step 5.1**: 更新 dataflow-architecture.md
- 文件: `docs/dataflow-architecture.md`
- 修正第84行关于 `indicator_docs` 的描述

**Step 5.2**: 更新 agent-tools-configuration.md
- 文件: `docs/agent-tools-configuration.md`
- 移除"无需改任何 analyst 代码"的误导性表述
- 添加说明：目前只有 fundamentals_analyst 实现了全配置化，其他 analyst 需后续重构

---

### Phase 6: P3（测试体系）

**Step 6.1**: 添加依赖到 requirements-dev.txt 或 pyproject.toml
- 添加 `langchain_openai`, `questionary`, `stockstats`

**Step 6.2**: 创建测试文件

**数据源迁移测试**:
- `tests/test_datasource_migration.py` — 验证 yfinance/alpha_vantage 迁移到 `datasource/` 后 `discover_and_register()` 正常工作
- `tests/test_multi_vendor_registration.py` — 验证多数据源注册和路由

**工具配置化测试**:
- `tests/test_tool_configurability.py` — 验证 Market/Social/News Analyst 通过 `load_agent_tools()` 加载工具

**配置合并测试**:
- `tests/test_config_merge.py` — 验证 `default_config.py` 正确合并 `max_debate_rounds`, `tool_vendors`, `output_language` 等配置项

**Step 6.3**: 验证测试可运行
```bash
python3 -m pytest -q
```

---

## 关键文件清单

| 文件 | 修改类型 |
|------|----------|
| `datasource/yfinance/` | 新目录，迁移 yfinance_news.py, y_finance.py, stockstats_utils.py |
| `datasource/alpha_vantage/` | 新目录，迁移 alpha_vantage_*.py |
| `tradingagents/config.yaml` | 更新 vendor_paths 指向 datasource.* |
| `tradingagents/dataflows/interface.py` | 添加异常日志 |
| `tradingagents/dataflows/` | 移除已迁移的 yfinance/alpha_vantage 文件 |
| `tradingagents/agents/analysts/market_analyst.py` | 使用 load_agent_tools() |
| `tradingagents/agents/analysts/social_media_analyst.py` | 使用 load_agent_tools() |
| `tradingagents/agents/analysts/news_analyst.py` | 使用 load_agent_tools() |
| `tradingagents/default_config.py` | 扩展配置合并 |
| `docs/dataflow-architecture.md` | 修复陈旧描述 |
| `docs/agent-tools-configuration.md` | 修正误导性表述 |
| `tests/test_datasource_migration.py` | 新测试文件 |
| `tests/test_multi_vendor_registration.py` | 新测试文件 |
| `tests/test_tool_configurability.py` | 新测试文件 |
| `tests/test_config_merge.py` | 新测试文件 |

---

## 验证方案

### Phase 1 - 数据源迁移验证
```bash
# 验证 discover_and_register 能发现 datasource 下的工具
python -c "from tradingagents.dataflows.interface import _VENDOR_REGISTRY; print('yfinance' in str(_VENDOR_REGISTRY)); print('alpha_vantage' in str(_VENDOR_REGISTRY))"

# 验证 vendor_paths 配置正确
python -c "from tradingagents.dataflows.config import get_config; print(get_config().get('vendor_paths'))"
```

### Phase 2 - 工具配置化验证
```bash
# 验证 Market/Social/News Analyst 使用 load_agent_tools
python -c "from tradingagents.agents.utils.agent_utils import load_agent_tools; print([t.name for t in load_agent_tools('news_analyst')])"

# 验证 news_analyst 包含 get_insider_transactions
python -c "from tradingagents.agents.utils.agent_utils import load_agent_tools; tools = load_agent_tools('news_analyst'); print('get_insider_transactions' in [t.name for t in tools])"
```

### Phase 3 - 配置合并验证
```bash
# 验证 default_config.py 正确合并各配置项
python -c "from tradingagents.default_config import DEFAULT_CONFIG; print('max_debate_rounds:', DEFAULT_CONFIG.get('max_debate_rounds')); print('tool_vendors:', DEFAULT_CONFIG.get('tool_vendors')); print('output_language:', DEFAULT_CONFIG.get('output_language'))"
```

### Phase 6 - 测试验证
```bash
# 运行所有测试
python3 -m pytest -q

# 运行特定测试
python3 -m pytest tests/test_datasource_migration.py -v
python3 -m pytest tests/test_tool_configurability.py -v
python3 -m pytest tests/test_config_merge.py -v
```

### 端到端验证
```bash
tradingagents test 688333.SH --date 2026-04-14
```

5. **测试**:
   ```bash
   python3 -m pytest -q
   ```
