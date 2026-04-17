# 智能体工具绑定配置化

## 概述

本系统实现了智能体工具的全流程配置化管理。

**相关文档**：
- [datahub-design.md](datahub-design.md) - 两层架构设计
- [datahub-architecture.md](datahub-architecture.md) - 文件改动清单

---

## 工具绑定流程

详见 [datahub-design.md](datahub-design.md) 第四章"智能体调用工具设计"。

---

## 配置文件说明

### agents_registry.yaml

定义智能体可用的工具列表：

```yaml
agents:
  fundamentals_analyst:
    tools:
      - get_fundamentals
      - get_balance_sheet
      - get_cashflow
      - get_income_statement
      - get_peg_ratio
      - get_yoy_growth
```

---

## 添加工具流程

详见 [datahub-design.md](datahub-design.md) 第十章"如何扩展"：

1. 数据源层：加 @export 函数
2. 数仓层：加 @tool 函数
3. 智能体层：agents_registry.yaml 绑定

---

## 工具列表

详见 [datahub-design.md](datahub-design.md) 第七章"主题域设计"。

---

*最后更新：2026-04-17*
