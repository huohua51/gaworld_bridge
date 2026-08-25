# EXP-GM-04e-E Typed-patch Executor

- 时间：2026-08-24T07:48:53.533682+00:00
- 阶段：04e-E，Rule Reviewer 提供正确 patch，只测 Executor
- 开发集：工资 / 返还 / 预算；留出题未触碰
- 模型：GLM-4-Flash；温度 0；Executor 调用 1 次
- 状态：pilot，不可排名

## 主结果

- requested：18（旧协议 9 + 新协议 9）
- measurement_valid：18，coverage：1.0
- PatchAdoptionRate 旧：1.0 新：0.0
- 隐式测试（v2 过且 v1 不过）旧：1.0 新：0.0
- 进入 04e-Full：False

## 决策

开发集 Executor **未过门**。停止，不跑 04e-Full，不跑留出题。

04e-R 已经证明 Reviewer 单步可以做证据绑定审核。04e-E 证明：把保证正确的 typed patch 交给同一模型的 Executor 后，新协议采用率是 0。问题在 Executor 协议，不在 Reviewer，也还没轮到消息编排。按预注册门，这里必须停。

不要在同一开发集上继续改 typed-patch 提示词再跑。那会把 04e-E 调成开发集。需要改就另开协议版本。

## 过门条件

| 条件 | 结果 |
|---|---|
| PatchAdoptionRate 上升 | 1.0 → 0.0，下降 |
| coverage = 1 | 1.0 |
| 环境未代写文件 | 通过；失败产物仍是 v1 数值 |

## 失败形态

新协议 9 格全部未改登记常量。Verifier 按真实文件分类，不看模型自评：

- 工资 3/3：`APPLIED_PATCH_IDS = ["patch-01"]`，但 `THRESHOLD = 60000`，`SPEC_VERSION = "v1"`。承认了 patch，没有改值。
- 返还 3/3：同样保留 `RATE = 0.3`，只写了 `APPLIED_PATCH_IDS`。
- 预算 3/3：`BUDGET = 100` 未改，另外加了 `THRESHOLD = 80`。把 required_value 写到未登记符号上。

这与 04c 的「只改 SPEC_VERSION」同类，但是升级版：模型学会了填 `APPLIED_PATCH_IDS` 这种声明字段，仍然不改被 patch.path 指向的常量。版本号不能替代数值核验；这里连版本号也经常没改。

旧协议在相同条件下 9/9 采用：草稿 + 正确的 `required_change` 足以让 Executor 把工资/返还/预算都改到 v2。说明 Executor 并不是不会改数，而是 typed-patch 提交格式被当成了要填写的表格。

04c Full 里返还题 Executor 失败，不能直接读成「Executor 单步不会采用正确意见」。那是完整链。本轮把意见固定成 Rule 生成的正确 patch 之后，旧协议单步是过的。

## 与 04e-R 的关系

| 阶段 | 结果 | 含义 |
|---|---|---|
| 04e-R | 过门 | Reviewer 能绑定真实草稿事实 |
| 04e-E | 未过门 | Executor 不能把 typed patch 写成真实改值 |
| 04e-Full | 未跑 | 单步已失败，合起来无法归因 |
| 留出题 | 未跑 | 开发集改进不成立 |

## 下一步

不要跑 Full，不要跑留出题。Backlog：`AP-04e-E-01 typed_patch_acknowledged_not_applied`。若再开新协议，应让提交声明无法替代常量核验，并且不要丢掉旧协议已经能用的 `required_change` 载荷。

| instance | protocol | valid | applied | tests_ok | first_error |
|---|---|---|---|---|---|
| w1_budget_remaining_evidence_bound_s0 | evidence_bound | True | False | False | wrong_location_modified |
| w1_budget_remaining_evidence_bound_s1 | evidence_bound | True | False | False | wrong_location_modified |
| w1_budget_remaining_evidence_bound_s2 | evidence_bound | True | False | False | wrong_location_modified |
| w1_budget_remaining_legacy_s0 | legacy | True | True | True | none |
| w1_budget_remaining_legacy_s1 | legacy | True | True | True | none |
| w1_budget_remaining_legacy_s2 | legacy | True | True | True | none |
| w1_return_floor_evidence_bound_s0 | evidence_bound | True | False | False | patch_acknowledged_not_applied |
| w1_return_floor_evidence_bound_s1 | evidence_bound | True | False | False | patch_acknowledged_not_applied |
| w1_return_floor_evidence_bound_s2 | evidence_bound | True | False | False | patch_acknowledged_not_applied |
| w1_return_floor_legacy_s0 | legacy | True | True | True | none |
| w1_return_floor_legacy_s1 | legacy | True | True | True | none |
| w1_return_floor_legacy_s2 | legacy | True | True | True | none |
| w1_wage_gate_evidence_bound_s0 | evidence_bound | True | False | False | patch_acknowledged_not_applied |
| w1_wage_gate_evidence_bound_s1 | evidence_bound | True | False | False | patch_acknowledged_not_applied |
| w1_wage_gate_evidence_bound_s2 | evidence_bound | True | False | False | patch_acknowledged_not_applied |
| w1_wage_gate_legacy_s0 | legacy | True | True | True | none |
| w1_wage_gate_legacy_s1 | legacy | True | True | True | none |
| w1_wage_gate_legacy_s2 | legacy | True | True | True | none |
