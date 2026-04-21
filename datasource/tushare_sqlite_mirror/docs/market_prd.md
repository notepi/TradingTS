# 技术分析数据层 PRD（用于开发）

## 1. 文档目标

本文档用于定义技术分析模块的数据层设计，目标是为后续的技术面报告、规则判断、策略提示、LLM 文案生成提供稳定、可复用、可校验的数据基础。

本设计遵循以下原则：

1. **程序负责计算，模型负责解释**。
2. **技术指标不得由大模型在文本中自行推算**。
3. **所有结论必须基于结构化字段或规则标签输出**。
4. **表结构按分析维度拆分，而不是按 ETL 处理阶段拆分**。
5. **先满足单标的日线级分析，后续可平滑扩展至多标的、多周期。**

---

## 2. 适用范围

本 PRD 适用于以下场景：

- A 股个股日线级技术分析
- 技术分析日报 / 周报输入层
- 交易研究系统中的技术面模块
- LLM 技术分析报告生成输入层
- 技术信号、趋势状态、风险标签的结构化输出

当前版本仅覆盖：

- **日线级别**
- **后复权或统一口径价格序列**
- **股票维度单品种分析**

当前版本暂不覆盖：

- 分钟级别 / Tick 级别
- 多周期联动分析
- 板块相对强弱横向比较
- KDJ、布林带、唐奇安通道等扩展指标
- 自动策略交易执行

---

## 3. 总体设计

技术分析数据层拆分为四张核心表：

1. **基础行情表**：记录原始日线行情事实
2. **均线趋势表**：记录均线、趋势结构与均线关系
3. **动量波动表**：记录 RSI、MACD、ATR、量能、波动等指标
4. **规则标签表**：记录程序先验判断后的结构化标签，供报告和 LLM 使用

四张表分别回答四个问题：

- **基础行情**：今天发生了什么
- **均线趋势**：趋势结构是什么
- **动量波动**：强弱和波动如何
- **规则标签**：系统最终如何定性

---

## 4. 设计目标

### 4.1 业务目标

输出一套可复用的技术分析数据底座，支持：

- 技术分析报告自动生成
- 技术状态面板展示
- 趋势、动量、波动的统一口径判断
- 规则先行，避免 LLM 生成低级错误
- 后续扩展到交易提示与多因子诊断

### 4.2 技术目标

- 保证同一交易日、同一标的的技术指标可重复计算
- 支持从基础行情重建全部衍生表
- 支持字段级调试与回溯
- 支持新增指标时不破坏现有表结构逻辑
- 支持 SQLite 或其他关系型数据库落地

---

## 5. 核心原则

### 5.1 事实与解释分离

事实型字段与解释型字段必须分离：

- 原始价格、成交量、均线、RSI、MACD 属于事实
- bullish / bearish / neutral / spike_down 等属于解释标签

### 5.2 标签优先原则

在 LLM 使用场景下：

- 若规则标签已存在，则优先使用标签描述
- 若标签与模型推断冲突，以标签为准
- 模型不得自行根据文字推算均线关系、涨跌幅、支撑阻力、动量强弱

### 5.3 单一职责原则

每张表只承担一个主要分析维度：

- 基础行情表不放趋势判断
- 均线趋势表不放 RSI / MACD
- 动量波动表不放均线多空排列
- 规则标签表不重复存储大规模连续原始序列

### 5.4 可回算原则

除标签表外，所有衍生表必须可由基础行情表重建。

---

## 6. 四张表定义

## 6.1 基础行情表 `price_daily`

### 6.1.1 作用

存储技术分析所需的日线原始行情事实，是所有技术指标计算的基础数据源。

### 6.1.2 主键

- `trade_date`
- `symbol`

### 6.1.3 字段定义

| 字段名 | 类型 | 含义 | 是否必填 |
|---|---|---|---|
| trade_date | DATE / TEXT | 交易日 | 是 |
| symbol | TEXT | 股票代码，如 688333.SH | 是 |
| open | REAL | 开盘价 | 是 |
| high | REAL | 最高价 | 是 |
| low | REAL | 最低价 | 是 |
| close | REAL | 收盘价 | 是 |
| pre_close | REAL | 昨收价 | 否 |
| change | REAL | 涨跌额 | 否 |
| pct_chg | REAL | 涨跌幅，单位 % | 否 |
| vol | REAL | 成交量，建议统一为股或手，需固定口径 | 是 |
| amount | REAL | 成交额，单位元 | 是 |
| turnover_rate | REAL | 换手率，单位 % | 否 |
| amplitude | REAL | 振幅，单位 % | 否 |
| adj_type | TEXT | 复权类型，如 hfq / qfq / raw | 否 |
| data_source | TEXT | 数据源标识 | 否 |
| created_at | DATETIME | 入库时间 | 否 |
| updated_at | DATETIME | 更新时间 | 否 |

### 6.1.4 口径要求

- `pct_chg` 统一按百分比存储，例如 7.21 表示 7.21%
- `amount` 统一为人民币元
- `vol` 必须统一口径，全系统不可混用“股”和“手”
- `amplitude` 若源数据未提供，可按 `(high - low) / pre_close * 100` 计算
- 若使用复权数据，必须在 `adj_type` 中记录

### 6.1.5 备注

本表不承载任何趋势判断、信号解释、看多看空结论。

---

## 6.2 均线趋势表 `trend_ma_daily`

### 6.2.1 作用

存储均线类指标、均线相对关系、价格相对均线位置、趋势结构判断，用于回答“方向和结构”。

### 6.2.2 主键

- `trade_date`
- `symbol`

### 6.2.3 字段定义

| 字段名 | 类型 | 含义 | 是否必填 |
|---|---|---|---|
| trade_date | DATE / TEXT | 交易日 | 是 |
| symbol | TEXT | 股票代码 | 是 |
| sma_5 | REAL | 5日简单均线 | 否 |
| sma_10 | REAL | 10日简单均线 | 否 |
| sma_20 | REAL | 20日简单均线 | 否 |
| sma_50 | REAL | 50日简单均线 | 否 |
| sma_120 | REAL | 120日简单均线 | 否 |
| sma_200 | REAL | 200日简单均线 | 否 |
| ema_10 | REAL | 10日指数均线 | 否 |
| ema_20 | REAL | 20日指数均线 | 否 |
| ema_50 | REAL | 50日指数均线 | 否 |
| price_vs_sma20 | TEXT | above / below / near | 否 |
| price_vs_sma50 | TEXT | above / below / near | 否 |
| price_vs_sma200 | TEXT | above / below / near | 否 |
| price_vs_ema10 | TEXT | above / below / near | 否 |
| sma20_vs_sma50 | TEXT | bullish / bearish / near | 否 |
| sma50_vs_sma200 | TEXT | bullish / bearish / near | 否 |
| trend_short | TEXT | bullish / neutral / bearish | 否 |
| trend_mid | TEXT | bullish / neutral / bearish | 否 |
| trend_long | TEXT | bullish / neutral / bearish | 否 |
| cross_signal | TEXT | golden_cross / death_cross / none | 否 |
| created_at | DATETIME | 入库时间 | 否 |
| updated_at | DATETIME | 更新时间 | 否 |

### 6.2.4 规则口径

#### 价格相对均线标签

- `above`：价格高于均线超过阈值
- `below`：价格低于均线超过阈值
- `near`：价格与均线差距在阈值范围内

建议阈值：

- 默认 `abs(close / ma - 1) <= 1%` 记为 `near`

#### 趋势定义建议

- `trend_short`：综合 `close vs ema_10`、`close vs sma_20` 判断
- `trend_mid`：综合 `close vs sma_50`、`sma20 vs sma50` 判断
- `trend_long`：综合 `close vs sma_200`、`sma50 vs sma200` 判断

#### 金叉死叉定义建议

- `golden_cross`：短均线从下向上穿越长均线
- `death_cross`：短均线从上向下穿越长均线
- 若无新交叉发生，则为 `none`

### 6.2.5 备注

本表回答的是“结构与方向”，不负责表达强弱动量、放量与否、是否超卖等问题。

---

## 6.3 动量波动表 `momentum_volatility_daily`

### 6.3.1 作用

存储动量、波动、量能及阶段高低点相关指标，用于回答“速度、强度与波动是否异常”。

### 6.3.2 主键

- `trade_date`
- `symbol`

### 6.3.3 字段定义

| 字段名 | 类型 | 含义 | 是否必填 |
|---|---|---|---|
| trade_date | DATE / TEXT | 交易日 | 是 |
| symbol | TEXT | 股票代码 | 是 |
| rsi_6 | REAL | RSI(6) | 否 |
| rsi_14 | REAL | RSI(14) | 否 |
| macd_dif | REAL | MACD DIF | 否 |
| macd_dea | REAL | MACD DEA | 否 |
| macd_hist | REAL | MACD 柱 | 否 |
| atr_14 | REAL | ATR(14) | 否 |
| vol_avg_5 | REAL | 5日平均成交量 | 否 |
| vol_avg_20 | REAL | 20日平均成交量 | 否 |
| amount_avg_20 | REAL | 20日平均成交额 | 否 |
| volume_ratio | REAL | 当日成交量 / 20日均量 | 否 |
| amplitude | REAL | 振幅，单位 % | 否 |
| high_20d | REAL | 近20日最高价 | 否 |
| low_20d | REAL | 近20日最低价 | 否 |
| high_60d | REAL | 近60日最高价 | 否 |
| low_60d | REAL | 近60日最低价 | 否 |
| distance_to_high_20d_pct | REAL | 距20日高点百分比 | 否 |
| distance_to_low_20d_pct | REAL | 距20日低点百分比 | 否 |
| distance_to_high_60d_pct | REAL | 距60日高点百分比 | 否 |
| distance_to_low_60d_pct | REAL | 距60日低点百分比 | 否 |
| rsi_zone | TEXT | overbought / neutral_strong / neutral_weak / oversold | 否 |
| macd_state | TEXT | bullish / bearish / weakening_bear / weakening_bull | 否 |
| volume_state | TEXT | contracted / normal / expanded / spike | 否 |
| volatility_state | TEXT | low / normal / high / extreme | 否 |
| created_at | DATETIME | 入库时间 | 否 |
| updated_at | DATETIME | 更新时间 | 否 |

### 6.3.4 规则口径

#### RSI 分区建议

- `overbought`：RSI >= 70
- `neutral_strong`：50 <= RSI < 70
- `neutral_weak`：30 < RSI < 50
- `oversold`：RSI <= 30

默认使用 `rsi_14` 作为主展示值。

#### MACD 状态建议

- `bullish`：DIF > DEA 且 DIF > 0
- `bearish`：DIF < DEA 且 DIF < 0
- `weakening_bear`：仍为负区但下跌动能收敛
- `weakening_bull`：仍为正区但上涨动能收敛

#### 成交量状态建议

按 `volume_ratio = vol / vol_avg_20` 定义：

- `< 0.7`：`contracted`
- `0.7 ~ 1.3`：`normal`
- `1.3 ~ 2.0`：`expanded`
- `> 2.0`：`spike`

#### 波动状态建议

波动状态可基于 ATR、振幅分位数或相对 20 日均值定义，首版建议：

- 使用 `amplitude / amplitude_20d_avg` 或 ATR 相对历史均值做等级划分

### 6.3.5 备注

本表允许同时存储数值和中间标签，但不能替代最终规则标签表。

---

## 6.4 规则标签表 `technical_labels_daily`

### 6.4.1 作用

记录程序根据基础行情、均线趋势、动量波动三张事实表计算出的最终结构化判断结果，供报告生成、LLM 读取、前端面板展示使用。

### 6.4.2 主键

- `trade_date`
- `symbol`

### 6.4.3 字段定义

| 字段名 | 类型 | 含义 | 是否必填 |
|---|---|---|---|
| trade_date | DATE / TEXT | 交易日 | 是 |
| symbol | TEXT | 股票代码 | 是 |
| short_trend_label | TEXT | 短期趋势标签 | 否 |
| mid_trend_label | TEXT | 中期趋势标签 | 否 |
| long_trend_label | TEXT | 长期趋势标签 | 否 |
| trend_structure_label | TEXT | 趋势结构综合标签 | 否 |
| rsi_label | TEXT | RSI 定性标签 | 否 |
| macd_label | TEXT | MACD 定性标签 | 否 |
| volume_label | TEXT | 量能定性标签 | 否 |
| volatility_label | TEXT | 波动定性标签 | 否 |
| breakout_label | TEXT | 突破状态标签 | 否 |
| breakdown_label | TEXT | 跌破状态标签 | 否 |
| reversal_signal_label | TEXT | 反转信号标签 | 否 |
| risk_level_label | TEXT | 风险等级标签 | 否 |
| tactical_state_label | TEXT | 操作状态标签 | 否 |
| summary_signal_label | TEXT | 技术面总信号 | 否 |
| created_at | DATETIME | 入库时间 | 否 |
| updated_at | DATETIME | 更新时间 | 否 |

### 6.4.4 标签定义建议

#### 趋势标签

- `bullish`
- `neutral`
- `bearish`

#### 趋势结构综合标签示例

- `short_bear_mid_bear_long_bull`
- `all_bullish`
- `mixed_structure`

#### 量能标签示例

- `volume_normal`
- `volume_expand_up`
- `volume_expand_down`
- `volume_spike_down`

#### 反转信号标签示例

- `none`
- `potential_bottoming`
- `potential_rebound`
- `failed_rebound`

#### 风险等级标签示例

- `low`
- `medium`
- `high`
- `extreme`

#### 操作状态标签示例

- `wait_and_see`
- `watch_support`
- `trend_follow`
- `high_risk_rebound`
- `avoid_chasing`

#### 总信号示例

- `weak_bearish`
- `bearish`
- `neutral`
- `neutral_to_bullish`
- `bullish`

### 6.4.5 使用原则

- 本表是技术分析报告的优先输入表
- 若本表已有结论，LLM 必须优先使用本表标签进行表达
- 若本表为空，LLM 才可回退到事实表谨慎表述
- LLM 不得自造不存在的标签

---

## 7. 数据流设计

数据流如下：

1. 从数据源拉取日线行情，写入 `price_daily`
2. 基于 `price_daily` 计算均线趋势字段，写入 `trend_ma_daily`
3. 基于 `price_daily` 计算动量波动字段，写入 `momentum_volatility_daily`
4. 综合前三张表，运行规则引擎，写入 `technical_labels_daily`
5. 报告系统或 LLM 仅读取四张表中的必要字段，不在文本中重新计算

---

## 8. 开发边界

### 8.1 本期必须完成

- 四张表建表
- 日线行情入库
- SMA / EMA / RSI / MACD / ATR 基础计算
- 趋势标签、量能标签、RSI 分区、MACD 状态、风险标签首版规则
- 单标的单日输出能力

### 8.2 本期不做

- 分钟线扩展
- 多标的横截面对比
- 复杂形态识别（头肩顶、三角形、楔形）
- AI 自动交易决策
- 图形可视化输出

---

## 9. LLM 使用规范

用于技术分析生成时，Prompt 必须明确包含以下约束：

1. 只能使用输入中提供的技术字段与标签
2. 不得自行根据文本二次推算均线位置、涨跌幅、RSI、MACD 关系
3. 若数值字段与已有标签冲突，以标签为准
4. 若标签缺失，只能做保守描述，不得补造强结论
5. 禁止把“放量下跌”直接等同于“机构派发”或“恐慌出逃”，除非规则已明确支持该结论

建议标准约束语：

> 技术分析只能使用结构化输入中的指标值与规则标签，不得自行推算均线关系、涨跌幅、RSI 区间、MACD 状态或支撑阻力。若文字结论与标签冲突，以标签为准。

---

## 10. 验收标准

### 10.1 数据正确性

- 任意交易日的 OHLCV 与源数据一致
- 均线值可通过独立脚本复核
- RSI / MACD / ATR 与既定公式一致
- volume_ratio 与均量计算无口径冲突

### 10.2 表间一致性

- `trend_ma_daily` 和 `momentum_volatility_daily` 可由 `price_daily` 重建
- `technical_labels_daily` 的标签必须可追溯到前三张表中的事实字段
- 不允许出现标签与事实字段直接矛盾的记录

### 10.3 报告可用性

- LLM 使用四张表输入后，不再出现“高于/低于写反”
- 不再出现涨跌幅、距高点跌幅等低级算术错误
- 同一输入多次生成时，核心结论保持一致

---

## 11. 建议实现顺序

### Phase 1

- 建 `price_daily`
- 完成行情拉取与清洗
- 保证单标的数据完整

### Phase 2

- 建 `trend_ma_daily`
- 完成 SMA / EMA 与趋势结构判断

### Phase 3

- 建 `momentum_volatility_daily`
- 完成 RSI / MACD / ATR / 均量与高低点计算

### Phase 4

- 建 `technical_labels_daily`
- 完成规则引擎与首版标签输出

### Phase 5

- 接入 LLM 报告生成
- 验证模型只解释、不计算

---

## 12. 命名规范

表名固定如下：

- `price_daily`
- `trend_ma_daily`
- `momentum_volatility_daily`
- `technical_labels_daily`

字段命名原则：

- 小写英文 + 下划线
- 百分比字段统一以 `_pct` 结尾，若保留历史兼容字段可单独说明
- 标签字段统一以 `_label` 结尾
- 平均值字段统一以 `_avg_n` 或 `ma_type_n` 风格命名

---

## 13. 后续扩展建议

未来版本可考虑增加：

- 布林带与通道类指标
- 板块相对强弱表
- 多周期技术共振表
- 技术事件表（放量突破、均线拐点、缩量回踩）
- 快照视图表，用于直接给 LLM 或前端展示

但当前阶段不建议继续加表，先把四张表做稳定。

---

## 14. 最终结论

本技术分析数据层采用“四张表”设计：

- 基础行情
- 均线趋势
- 动量波动
- 规则标签

其核心价值不是数据库设计本身，而是确保：

1. 技术面事实由程序计算
2. 技术面解释由模型生成
3. 模型不再承担计算职责
4. 报告系统不再出现低级算术与逻辑错误

该设计适合作为当前技术分析模块的一期落地方案。

