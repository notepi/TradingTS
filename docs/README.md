# TradingAgents 文档
## 第一性原理的驱动
- 在基本面层面，大模型自己拿数据计算很容易出现错误，为 LLM构建基本面的指标库 又非常繁琐。基本面的数据不会高频变化，根据第一性原理，我们就让 ChatGPT 生成了一份，prompt 也提供了。
## 用户文档

| 文档 | 内容 | 适用人群 |
|------|------|----------|
| [getting-started.md](getting-started.md) | 快速上手指南 | 新用户 |
| [cli-guide.md](cli-guide.md) | CLI 使用指南 | 命令行用户 |
| [dashboard-guide.md](dashboard-guide.md) | Dashboard 使用指南 | 网页用户 |
| [configuration-guide.md](configuration-guide.md) | 配置文件详解 | 需定制配置的用户 |
| [data-source-guide.md](data-source-guide.md) | 数据源扩展指南 | 高级用户 |

## 开发者文档

| 文档 | 内容 | 适用人群 |
|------|------|----------|
| [datahub-design.md](datahub-design.md) | 数仓层两层架构设计 | 理解架构 |
| [agent-architecture.md](agent-architecture.md) | 智能体协作流程与辩论机制 | 智能体开发 |
| [graph-execution.md](graph-execution.md) | LangGraph 执行流程 | 图执行调试 |
| [add-new-agent.md](add-new-agent.md) | 添加新智能体指南与 Checklist | 智能体扩展 |

## 快速导航

- **新用户** → [getting-started.md](getting-started.md)
- **CLI 用户** → [cli-guide.md](cli-guide.md)
- **Dashboard 用户** → [dashboard-guide.md](dashboard-guide.md)
- **配置问题** → [configuration-guide.md](configuration-guide.md)
- **开发扩展** → [datahub-design.md](datahub-design.md)
- **添加工具** → [data-source-guide.md](data-source-guide.md)
- **添加智能体** → [add-new-agent.md](add-new-agent.md)
