好，按 **12 张表**给你一版能直接落库的设计。
我按你的思路来：

* **上层给智能体 / 报告用**
* **下层对接数据源**
* **原始事实** 和 **派生指标** 分开
* 核心目标不是“花哨”，而是 **不算错、不混口径、可追溯**

---

# 一、总设计原则

这 12 张表分成两层：

## A. 原始事实层（8 张）

这些表只存：

* 财报原始披露值
* 行情原始值
* 附注中抽取后的结构化事实

**原则：尽量不做主观判断，不让大模型自己推。**

---

## B. 派生指标层（4 张）

这些表只存：

* 你程序算出来的指标
* 明确公式、明确口径
* 模型只读，不重算

**原则：计算放程序里，解释放模型里。**

---

# 二、统一口径字段

这部分非常重要。
**12 张表里，凡是“按报告期”的表，建议都带这批公共字段。**

## 通用主键/追溯字段

```text
id
ticker
company_name
period_end
fiscal_year
fiscal_period
report_type
period_mode
statement_scope
currency
unit
is_restated
source_name
source_report_type
source_publish_date
source_report_id
source_line_ref
calc_method
data_version
created_at
updated_at
```

---

## 字段解释

### 时间/期别

* `period_end`：报告期末，比如 `2025-09-30`
* `fiscal_year`：`2025`
* `fiscal_period`：`Q1 / Q2 / Q3 / Q4`
* `report_type`：`Q1 / H1 / Q3 / FY`
* `period_mode`：

  * `cumulative`：累计值
  * `single_quarter`：单季度值
  * `point_in_time`：时点值（资产负债表）
  * `ttm`：滚动十二个月

### 范围/口径

* `statement_scope`：

  * `consolidated`
  * `parent_only`
* `currency`：默认 `CNY`
* `unit`：统一建议存 `yuan`
* `is_restated`：是否追溯重述
* `calc_method`：

  * `reported`：财报原始披露
  * `derived`：程序计算
  * `derived_from_cumulative`：由累计拆单季
  * `extracted_from_notes`：从附注抽取

### 溯源

* `source_name`：如 `tushare` / `cninfo_pdf` / `company_announcement`
* `source_report_type`：`annual_report` / `q3_report` / `semiannual_report`
* `source_publish_date`
* `source_report_id`
* `source_line_ref`：附注行号、表格行名、字段名

### 版本

* `data_version`：比如 `v1`, `v2-restated`
* `created_at`
* `updated_at`

---

# 三、12 张表总览

## 原始事实层

1. `company_profile`
2. `income_statement`
3. `balance_sheet`
4. `cash_flow_statement`
5. `equity_change`
6. `financial_notes_keyfacts`
7. `market_valuation`
8. `shares_and_holders`

## 派生指标层

9. `profitability_metrics`
10. `quality_metrics`
11. `operating_metrics`
12. `solvency_and_capex_metrics`

---

# 四、12 张表详细设计

---

## 1）company_profile

### 用途

公司静态资料表。
一家公司一条主记录，低频更新。

### 粒度

**1 company = 1 row（当前版本）**

### 主键

* `ticker`

### 核心字段

```text
ticker
company_name
company_name_short
exchange
board
industry_level_1
industry_level_2
industry_level_3
listing_date
registered_capital
legal_representative
chairman
general_manager
province
city
office_address
website
email
business_description
main_products
main_business_model
auditor
is_state_owned
is_high_tech_enterprise
status
created_at
updated_at
```

### 备注

这张表别塞太多历史。
如果以后你要做历史管理层变更，再拆 `company_profile_history`。

---

## 2）income_statement

### 用途

利润表原始事实表。

### 粒度

**1 ticker + 1 period_end + 1 report_type + 1 period_mode + 1 statement_scope = 1 row**

### 唯一约束

```text
(ticker, period_end, report_type, period_mode, statement_scope, data_version)
```

### 核心字段

```text
id
ticker
period_end
fiscal_year
fiscal_period
report_type
period_mode
statement_scope
is_restated

revenue
operating_cost
tax_and_surcharges
selling_expense
admin_expense
rd_expense
finance_expense

other_income
investment_income
fair_value_change_income
credit_impairment_loss
asset_impairment_loss
asset_disposal_income

operating_profit
non_operating_income
non_operating_expense
total_profit
income_tax_expense

net_profit
net_profit_parent
net_profit_minorities

other_comprehensive_income
comprehensive_income_total
comprehensive_income_parent
comprehensive_income_minorities

non_recurring_gain_loss
deducted_net_profit_parent

basic_eps
diluted_eps

source_name
source_report_type
source_publish_date
source_report_id
source_line_ref
calc_method
data_version
created_at
updated_at
```

### 关键设计点

1. **累计值和单季度值分开存**

   * 不要只存累计后再临时拆
   * 最好既存 `cumulative`，也存 `single_quarter`

2. **扣非净利润单独留字段**

   * A股分析很常用

3. **信用减值 / 资产减值单独拆**

   * 对制造业很关键

---

## 3）balance_sheet

### 用途

资产负债表原始事实表。

### 粒度

**1 ticker + 1 period_end + 1 statement_scope = 1 row**

### 唯一约束

```text
(ticker, period_end, statement_scope, data_version)
```

### 核心字段

```text
id
ticker
period_end
fiscal_year
report_type
period_mode
statement_scope
is_restated

cash_and_equivalents
settlement_reserves
lending_funds
trading_fin_assets
derivative_fin_assets
notes_receivable
accounts_receivable
receivables_financing
prepayments
other_receivables
inventory
contract_assets
assets_held_for_sale
other_current_assets
current_assets_total

long_term_equity_investment
other_equity_instruments
investment_property
fixed_assets
construction_in_progress
right_of_use_assets
intangible_assets
development_expenditure
goodwill
long_term_deferred_expenses
deferred_tax_assets
other_non_current_assets
non_current_assets_total

assets_total

short_term_borrowings
trading_fin_liabilities
notes_payable
accounts_payable
advance_receipts
contract_liabilities
payroll_payable
tax_payable
other_payables
current_portion_non_current_liabilities
other_current_liabilities
current_liabilities_total

long_term_borrowings
bonds_payable
lease_liabilities
long_term_payables
provisions
deferred_income
deferred_tax_liabilities
other_non_current_liabilities
non_current_liabilities_total

liabilities_total

share_capital
other_equity_instruments
capital_reserve
treasury_shares
other_comprehensive_income
special_reserve
surplus_reserve
general_risk_reserve
retained_earnings
equity_parent_total
minority_interest
equity_total

source_name
source_report_type
source_publish_date
source_report_id
source_line_ref
calc_method
data_version
created_at
updated_at
```

### 关键设计点

1. `inventory`
2. `accounts_receivable`
3. `contract_assets`
4. `construction_in_progress`
5. `fixed_assets`
6. `long_term_borrowings`

这些字段对你这种制造业/扩产型公司非常重要。

---

## 4）cash_flow_statement

### 用途

现金流量表原始事实表。

### 粒度

**1 ticker + 1 period_end + 1 report_type + 1 period_mode = 1 row**

### 唯一约束

```text
(ticker, period_end, report_type, period_mode, statement_scope, data_version)
```

### 核心字段

```text
id
ticker
period_end
fiscal_year
fiscal_period
report_type
period_mode
statement_scope
is_restated

cfo_cash_inflow_from_sales
cfo_cash_inflow_from_tax_refund
cfo_other_cash_inflow
cfo_inflow_total

cfo_cash_paid_for_goods_services
cfo_cash_paid_to_employees
cfo_cash_paid_for_taxes
cfo_other_cash_outflow
cfo_outflow_total
cfo_net

cfi_cash_inflow_from_investment_recovery
cfi_cash_inflow_from_investment_income
cfi_cash_inflow_from_asset_disposal
cfi_other_cash_inflow
cfi_inflow_total

cfi_cash_paid_for_asset_purchase
cfi_cash_paid_for_investment
cfi_other_cash_outflow
cfi_outflow_total
cfi_net

cff_cash_inflow_from_borrowings
cff_cash_inflow_from_equity_financing
cff_other_cash_inflow
cff_inflow_total

cff_cash_paid_for_debt_repayment
cff_cash_paid_for_dividend_interest
cff_other_cash_outflow
cff_outflow_total
cff_net

fx_effect
net_cash_increase
cash_begin
cash_end

source_name
source_report_type
source_publish_date
source_report_id
source_line_ref
calc_method
data_version
created_at
updated_at
```

### 关键设计点

这张表是**重灾区**，一定同时保留：

* `cfo_inflow_total`
* `cfo_outflow_total`
* `cfo_net`

同理：

* `cfi_inflow_total`
* `cfi_outflow_total`
* `cfi_net`
* `cff_inflow_total`
* `cff_outflow_total`
* `cff_net`

这样模型就不会把“小计”看成“净额”。

---

## 5）equity_change

### 用途

所有者权益变动表原始事实表。

### 粒度

**1 ticker + 1 period_end + 1 statement_scope = 1 row**

### 唯一约束

```text
(ticker, period_end, statement_scope, data_version)
```

### 核心字段

```text
id
ticker
period_end
fiscal_year
report_type
statement_scope
is_restated

equity_opening_total
share_capital_opening
capital_reserve_opening
other_comprehensive_income_opening
surplus_reserve_opening
retained_earnings_opening

net_profit_current_period
other_comprehensive_income_current_period
capital_injection
share_based_payment
treasury_share_change
special_reserve_change
profit_distribution
dividend_paid
restatement_adjustment
other_equity_change

equity_closing_total
share_capital_closing
capital_reserve_closing
other_comprehensive_income_closing
surplus_reserve_closing
retained_earnings_closing

source_name
source_report_type
source_publish_date
source_report_id
source_line_ref
calc_method
data_version
created_at
updated_at
```

### 关键设计点

这张表常被忽略，但很有用：

* 看增发
* 看回购
* 看利润留存
* 看追溯重述
* 看分红
* 看股权激励稀释

---

## 6）financial_notes_keyfacts

### 用途

附注关键事实表。
这是把附注里最重要、最影响基本面判断的东西抽出来。

### 粒度

**1 ticker + 1 period_end = 1 row**

### 唯一约束

```text
(ticker, period_end, report_type, statement_scope, data_version)
```

### 核心字段

```text
id
ticker
period_end
fiscal_year
report_type
statement_scope
is_restated

ar_aging_within_1y
ar_aging_1_2y
ar_aging_2_3y
ar_aging_over_3y
ar_bad_debt_provision

inventory_raw_materials
inventory_wip
inventory_finished_goods
inventory_goods_in_transit
inventory_write_down
inventory_write_down_ratio

contract_assets
contract_assets_impairment
contract_liabilities

top5_customers_sales_ratio
top1_customer_sales_ratio
top5_suppliers_purchase_ratio
top1_supplier_purchase_ratio

government_subsidy_total
government_subsidy_recurring
government_subsidy_non_recurring

rd_expensed
rd_capitalized
rd_capitalization_ratio

cip_major_projects_json
fixed_asset_additions
major_capex_commitments

short_term_debt_due_within_1y
long_term_debt_due_after_1y
pledged_assets_json

related_party_transactions_total
guarantees_total
contingent_liabilities_total
pending_litigation_json

restatement_note_summary
audit_opinion
key_audit_matters_json

source_name
source_report_type
source_publish_date
source_report_id
source_line_ref
calc_method
data_version
created_at
updated_at
```

### 关键设计点

1. 这张表不是为了“全附注结构化”
2. 而是为了抓 **最影响基本面判断的附注点**

### 为什么重要

很多雷不在三表里，在附注里：

* 应收账龄恶化
* 存货跌价
* 政府补助占利润比例高
* 研发资本化异常
* 前五大客户过于集中
* 在建工程异常大
* 会计差错更正

---

## 7）market_valuation

### 用途

市场行情和估值表。

### 粒度

**1 ticker + 1 trade_date = 1 row**

### 唯一约束

```text
(ticker, trade_date)
```

### 核心字段

```text
id
ticker
trade_date

open_price
high_price
low_price
close_price
pre_close
change_amount
change_pct
volume
amount
turnover_rate
amplitude

total_market_cap
free_float_market_cap

pe_lyr
pe_ttm
pb
ps_ttm
pcf_ocf_ttm
dividend_yield_ttm

ev
ev_ebit
ev_ebitda

shares_total
shares_float

valuation_basis_period_end
valuation_basis_net_profit_ttm
valuation_basis_book_value

source_name
calc_method
data_version
created_at
updated_at
```

### 关键设计点

估值一定和财务表分开。
不要把 `P/E`、`P/B` 塞进利润表或资产表里。

---

## 8）shares_and_holders

### 用途

股本结构 + 股东结构 + 管理层持股变化。

### 粒度

**1 ticker + 1 period_end = 1 row**

### 唯一约束

```text
(ticker, period_end, data_version)
```

### 核心字段

```text
id
ticker
period_end
report_type

total_shares
float_shares
restricted_shares
restricted_ratio

top10_shareholders_json
top10_float_shareholders_json

largest_shareholder_name
largest_shareholder_ratio
actual_controller
actual_controller_type

pledge_ratio
frozen_ratio

management_shareholding_total
management_shareholding_change
major_shareholder_change_json

equity_incentive_exists
equity_incentive_shares
equity_incentive_vesting_schedule_json

source_name
source_report_type
source_publish_date
source_report_id
calc_method
data_version
created_at
updated_at
```

### 关键设计点

为了保持 12 张表，不单独拆“股东明细表”。
先用 `json` 存。

以后如果你要做：

* 股东穿透
* 减持监控
* 高管持仓变化趋势

再拆：

* `holder_snapshot_detail`
* `management_holding_change_detail`

---

# 五、派生指标层（4 张）

---

## 9）profitability_metrics

### 用途

盈利能力指标表。

### 粒度

**1 ticker + 1 period_end + 1 period_mode = 1 row**

### 核心字段

```text
id
ticker
period_end
fiscal_year
report_type
period_mode
statement_scope

gross_margin
operating_margin
ebit_margin
ebitda_margin
net_margin
deducted_net_margin

roe_weighted
roe_simple
roa
roic
roce

expense_ratio_selling
expense_ratio_admin
expense_ratio_rd
expense_ratio_finance

other_income_ratio
government_subsidy_profit_ratio
non_recurring_profit_ratio

basic_eps
diluted_eps
bps

calc_formula_version
source_periods_json
created_at
updated_at
```

### 说明

这张表回答的是：

* 公司赚不赚钱
* 靠什么赚钱
* 利润结构健康不健康

---

## 10）quality_metrics

### 用途

利润质量 / 现金质量 / 利润真实性。

### 粒度

**1 ticker + 1 period_end + 1 period_mode = 1 row**

### 核心字段

```text
id
ticker
period_end
fiscal_year
report_type
period_mode
statement_scope

cfo_to_net_profit
cfo_to_operating_profit
cash_conversion_ratio
net_profit_cash_content

accrual_ratio
non_recurring_profit_ratio
government_subsidy_to_net_profit
credit_impairment_to_revenue
asset_impairment_to_revenue

ar_to_revenue_ratio
inventory_to_revenue_ratio
contract_assets_to_revenue_ratio

earnings_quality_score
earnings_quality_label

calc_formula_version
source_periods_json
created_at
updated_at
```

### 说明

这张表解决的是：

* 利润是不是纸面利润
* 利润有没有靠补助/非经常性撑起来
* 应收和存货是不是堆得太高

---

## 11）operating_metrics

### 用途

营运效率指标表。

### 粒度

**1 ticker + 1 period_end + 1 period_mode = 1 row**

### 核心字段

```text
id
ticker
period_end
fiscal_year
report_type
period_mode
statement_scope

accounts_receivable_turnover
accounts_receivable_days

inventory_turnover
inventory_days

accounts_payable_turnover
accounts_payable_days

cash_cycle
asset_turnover
fixed_asset_turnover
working_capital_turnover

revenue_growth_yoy
revenue_growth_qoq
net_profit_growth_yoy
net_profit_growth_qoq
deducted_net_profit_growth_yoy

rd_intensity
capex_intensity
cip_to_fixed_assets_ratio

calc_formula_version
source_periods_json
created_at
updated_at
```

### 说明

这张表回答：

* 周转快不快
* 扩产有没有转化成收入
* 增长是不是健康增长

---

## 12）solvency_and_capex_metrics

### 用途

偿债能力 + 资本开支 + 财务压力指标表。

### 粒度

**1 ticker + 1 period_end + 1 period_mode = 1 row**

### 核心字段

```text
id
ticker
period_end
fiscal_year
report_type
period_mode
statement_scope

current_ratio
quick_ratio
cash_ratio

debt_to_asset
debt_to_equity
interest_bearing_debt
interest_bearing_debt_to_equity
net_debt
net_debt_to_ebitda

interest_coverage
ebit_interest_coverage

capex
capex_to_revenue
capex_to_depreciation
construction_in_progress_ratio

fcf
fcf_margin
owner_earnings

short_term_debt_ratio
debt_maturity_pressure_score
financing_dependence_ratio

solvency_score
solvency_label

calc_formula_version
source_periods_json
created_at
updated_at
```

### 说明

这张表回答：

* 资金链紧不紧
* 扩产是不是太猛
* 自由现金流是不是恶化
* 债务有没有到期压力

---

# 六、四类最重要的“防错规则”

这是整个系统里最值钱的部分。

---

## 规则 1：累计值和单季度值必须同时存

例如利润表和现金流量表：

* `2025Q3 cumulative`
* `2025Q3 single_quarter`

不能只存一个。

因为分析里经常两种都要：

* 看经营趋势，要单季度
* 看同比披露，要累计

---

## 规则 2：追溯重述必须留痕

任何字段只要公司做了会计差错更正，都要保留：

* `is_restated`
* `data_version`
* `source_publish_date`

最好还能保留：

* `restatement_note_summary`

不然你会碰到：

* 去年Q3老口径
* 今年Q1引用的新口径

两边打架。

---

## 规则 3：所有金额统一存“元”

不要数据库里出现：

* 有些是亿元
* 有些是万元
* 有些是元

统一存：

* `currency = CNY`
* `unit = yuan`

展示层再格式化。

---

## 规则 4：估值和财报分开

不要在财报表里混进：

* PE
* PB
* 市值
* 股价

这些都放 `market_valuation`。

---

# 七、推荐的最小索引设计

为了你后面查起来快，建议这样建索引。

## 高频查询索引

### 财报类

```sql
idx_income_ticker_period
idx_balance_ticker_period
idx_cashflow_ticker_period
idx_notes_ticker_period
```

### 行情估值类

```sql
idx_market_ticker_trade_date
```

### 指标类

```sql
idx_profitability_ticker_period
idx_quality_ticker_period
idx_operating_ticker_period
idx_solvency_ticker_period
```

---

# 八、推荐的枚举值

## report_type

```text
Q1
H1
Q3
FY
```

## period_mode

```text
cumulative
single_quarter
point_in_time
ttm
```

## statement_scope

```text
consolidated
parent_only
```

## calc_method

```text
reported
derived
derived_from_cumulative
extracted_from_notes
```

---

# 九、推荐的数据流

你这个系统建议按这个顺序走：

## Step 1：抓原始数据

进：

* `income_statement`
* `balance_sheet`
* `cash_flow_statement`
* `equity_change`
* `market_valuation`

## Step 2：解析附注

进：

* `financial_notes_keyfacts`

## Step 3：补股本和股东

进：

* `shares_and_holders`

## Step 4：程序计算派生指标

进：

* `profitability_metrics`
* `quality_metrics`
* `operating_metrics`
* `solvency_and_capex_metrics`

## Step 5：模型读指标和事实，输出报告

只读，不重算。

---

# 十、你现在最适合的落地顺序

别一口气全干。

## 第一阶段，先做 6 张

先落：

1. `income_statement`
2. `balance_sheet`
3. `cash_flow_statement`
4. `financial_notes_keyfacts`
5. `market_valuation`
6. `profitability_metrics`

先把“营收-利润-现金流-扩产-估值”跑通。

---

## 第二阶段，再补全到 12 张

补：
7. `equity_change`
8. `shares_and_holders`
9. `quality_metrics`
10. `operating_metrics`
11. `solvency_and_capex_metrics`
12. `company_profile`

---

# 十一、我的建议：你再加一层“报告视图”

虽然表是 12 张，但给模型别直接读 12 张原表。

建议你程序再拼一个中间对象：

```json id="41093"
{
  "company_profile": {...},
  "reported_financials": {...},
  "notes_keyfacts": {...},
  "valuation_snapshot": {...},
  "derived_metrics": {...},
  "risk_flags": [...]
}
```

模型读这个，就很稳。

---

# 十二、最后给你一个结论

这套 12 表的核心，不是“数据库设计漂亮”，而是三件事：

1. **口径不混**
2. **能追溯**
3. **模型不再自己算基础财务数据**

也就是：

* **三表 + 权益表 + 附注事实 = 真相层**
* **指标表 = 计算层**
* **LLM = 解释层**

这才是你基本面系统的正确分工。

下一步我建议直接做这个：
**我给你把这 12 张表写成 SQL DDL 初稿。**
