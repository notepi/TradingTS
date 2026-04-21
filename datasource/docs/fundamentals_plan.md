# 基本面表设计可行性分析与实施计划

## Context

用户设计了12张基本面表（fundamentals_prd.md），希望了解：
1. 数据源是否支持这些字段
2. 如何实现
3. 能不能实现

当前项目已有 SQLite 缓存层（tushare_sqlite_mirror），存储了基础财报表数据。

---

## 一、数据源支持情况评估

### 1.1 已有表 vs PRD 设计对照

| PRD 表名 | 现有表 | 支持度 | 备注 |
|----------|--------|--------|------|
| income_statement | income_statement | 85% | 缺少扣非净利润、综合收益明细 |
| balance_sheet | balance_sheet | 90% | 字段基本完整 |
| cash_flow_statement | cashflow | 90% | 字段基本完整 |
| market_valuation | fundamentals | 60% | 缺少 PS/PCF/EV 等 |
| company_profile | 无 | 100% | Tushare stock_basic 支持 |
| shares_and_holders | 无 | 70% | Tushare 有 top10_holders/stk_pledge |
| equity_change | 无 | 40% | Tushare 仅有部分字段 |
| financial_notes_keyfacts | 无 | 20% | **关键问题：大部分无 API** |

### 1.2 Tushare API 字段支持详情

**✅ 完全支持（有 API）**：
- 三大财务报表核心字段（income/balancesheet/cashflow）
- 每日估值（daily_basic：PE/PB/市值/换手率）
- 公司基本信息（stock_basic：行业/上市日期/地址等）
- 前十大股东（top10_holders/top10_floatholders）
- 实际控制人（controller）
- 股权质押（stk_pledge/stk_pledgedetail）
- 高管增减持（stk_rewards/stk_holdernumber_deal）
- 研发支出总额（rd_exp 在 income 表）
- 政府补助（subsidy/gov_subsidy 接口）

**⚠️ 无直接 API（需手动处理）**：
- 应收账龄结构（ar_aging_within_1y 等）
- 存货明细（原材料/在制品/成品）
- 在建工程项目明细（cip_major_projects）
- 前五大客户集中度（top5_customers_sales_ratio）
- 前五大供应商集中度
- 合同资产减值明细
- 关联交易总额
- 审计意见/关键审计事项（部分有 fina_indicator）

### 1.3 结论

**原始事实层（8张）**：
- 6张可完全实现：income_statement, balance_sheet, cash_flow_statement, market_valuation, company_profile, shares_and_holders
- 2张部分实现：equity_change（40%）、financial_notes_keyfacts（20%）

**派生指标层（4张）**：
- 100% 可程序计算实现：profitability_metrics, quality_metrics, operating_metrics, solvency_and_capex_metrics

---

## 二、实现方案

### 方案 A：分层渐进实现（推荐）

按照 PRD 的建议分两阶段：

**第一阶段：实现 6 张核心表**
1. 扩展现有 `income_statement` 表字段（扣非净利润、综合收益）
2. 扩展 `balance_sheet` 表（补齐缺失字段）
3. 扩展 `cashflow` 表（补齐缺失字段）
4. 新建 `company_profile` 表（从 stock_basic 拉取）
5. 新建 `shares_and_holders` 表（合并股东/质押/高管数据）
6. 扩展 `fundamentals` → 重命名为 `market_valuation`（增加 PS/EV 等）

**第二阶段：派生指标层**
1. `profitability_metrics` - 从 income/balance 计算毛利率/ROE/ROIC
2. `quality_metrics` - 从 income/cashflow 计算 CFO/净利润比率
3. `operating_metrics` - 从 income/balance 计算周转率/增长率
4. `solvency_and_capex_metrics` - 从 balance/cashflow 计算负债率/FCF

**第三阶段（可选）：附注数据**
- financial_notes_keyfacts 的 20% 字段需从 PDF 附注手动提取
- 建议先实现有 API 的字段，后续补充手动解析

### 方案 B：在现有架构上扩展

不新建表，直接扩展现有表字段，保持兼容性。

---

## 三、关键技术点

### 3.1 字段标准化

PRD 的口径字段设计很好，建议采纳：
- `period_mode`: cumulative/single_quarter/point_in_time/ttm
- `calc_method`: reported/derived/derived_from_cumulative
- `unit`: 统一为 yuan（现有实现已符合）
- `source_name/source_publish_date`: 溯源字段

### 3.2 单季值计算

已有实现（calculator.py），但建议：
- 存储 `period_mode` 字段区分累计/单季
- 每条记录明确标注，避免查询时混淆

### 3.3 数据同步

现有 pipeline.py 的模式：
- 调用 tushare 函数获取 DataFrame（raw=True）
- 存入 SQLite（upsert_dataframe）
- 记录 sync_batches 元数据

扩展新表只需：
1. 新增 sync 函数（如 sync_company_profile）
2. 在 run_pipeline 中调用
3. 在 storage.py 注册唯一键

---

## 四、实施步骤

### Step 1：评估现有表字段缺失

对比 PRD 字段与现有表 schema，列出缺失字段清单。

### Step 2：新增 Tushare API 调用

为缺失数据新增函数：
- `get_company_profile()` - 调用 stock_basic
- `get_shareholders()` - 调用 top10_holders + stk_pledge
- 扩展 `get_fundamentals()` - 增加 PS/EV/PCF

### Step 3：扩展 SQLite 表结构

ALTER TABLE ADD COLUMN 或新建表。

### Step 4：派生指标计算

扩展 calculator.py，实现四张派生指标表的计算函数。

### Step 5：测试验证

用实际股票数据测试，验证字段完整性和计算正确性。

---

## 五、风险与建议

### 风险

1. **financial_notes_keyfacts 80% 无 API**
   - 应收账龄、存货明细、客户集中度等需 PDF 解析
   - 建议：先实现有 API 的字段，标记"数据源不支持"

2. **追溯重述处理**
   - Tushare update_flag 字段可识别重述版本
   - 建议：保留所有版本，用 data_version 区分

3. **单位统一**
   - Tushare 部分字段单位是万元（如 total_mv）
   - 现有实现已处理（*10000 转元），需保持

### 建议

1. **先做 PRD 第一阶段的 6 张表**
   - 这些有完整 API 支持
   - 立即可用

2. **派生指标层用 calculator 模式**
   - 不存入 SQLite，每次从原始表计算
   - 或按需缓存，避免数据冗余

3. **附注数据暂缓**
   - 等有 PDF 解析能力后再实现
   - 或用 LLM 从公告文本提取

---

## 六、验证方法

1. 运行 sync_pipeline 同步一只股票数据
2. 检查新表字段完整性
3. 对比 Tushare API 文档字段列表
4. 测试派生指标计算逻辑

---

## 总结

| 维度 | 结论 |
|------|------|
| 能否实现 | 70% 可实现（有 API），30% 需手动处理 |
| 数据支持 | 三表+股东完整，附注明细缺 API |
| 推荐方案 | 分阶段实施，先做有 API 的表 |
| 派生指标 | 100% 可程序计算实现 |