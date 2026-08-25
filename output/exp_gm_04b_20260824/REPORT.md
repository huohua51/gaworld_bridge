# EXP-GM-04b TASK-W1-revision Pilot

- 时间：2026-08-24T04:25:30.615753+00:00
- 状态：`pilot`，`result=pass`，不可排名
- `conformance_target`：`M4_requirement_revision_propagation`
- 范围：1 Agent、1 次修订、确定性函数契约
- 路线：没有平台首错，不进入“修改 GAWorld 并复测”分支，下一步是 04c
- 对照：Focused=直接给最终有效版本 vs Pipeline=`submit(v1)→claim→revise(v2)→adapter`
- control 按 v1 隐藏测试验收；intervention 按 v2 验收
- FullPass 要求 `oracle_conditioned_success`（读到并采用正确版本），碰巧同时过 v1/v2 不算干净成功
- 不得与 04a 正控或 WorkDiag v0.3 混排

## 覆盖与主结果

- requested：36
- measurement_valid：36
- coverage：1.0
- oracle_conditioned FullPass Rate：1.0
- target_correct Rate：1.0

### 分格

- Focused control：1.0
- Focused intervention：1.0
- Pipeline control：1.0
- Pipeline intervention：1.0

## 决策

两轨全部高：当前单执行器修订链也不是瓶颈。可以进入 EXP-GM-04c（Reviewer—Executor 审核闭环）。

## 科学结论

EXP-GM-04b 证明：在单 Agent、单次需求修订、隐藏测试型微任务上，`submit(v1) → claim(v1) → WorkQueue.revise(v2) → Adapter 重读 brief → absorb` 可以把最新规格传到执行器，并用对应 Oracle 验收。抽查干预格显示 `claim_spec_version=v1`、`input_spec_version=v2`、`artifact_spec_version=v2`，且 v1 隐藏测试失败（`other_also=False`），不是碰巧同时过两版。

这仍不是完整 TASK-W1。实验不包含 Reviewer 发起修订、角色权限或只有 Publisher 能交付。下一步应做 EXP-GM-04c：把修订来源换成 Reviewer，而不是直接造六角色团队。

| task | variant | seed | Focused | Pipeline | EPG | focused first_error | pipeline first_error | focused in/art | pipeline in/art |
|---|---|---|---|---|---|---|---|---|---|
| w1_wage_gate | control | 0 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_wage_gate | control | 1 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_wage_gate | control | 2 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_wage_gate | intervention | 0 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |
| w1_wage_gate | intervention | 1 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |
| w1_wage_gate | intervention | 2 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |
| w1_return_floor | control | 0 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_return_floor | control | 1 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_return_floor | control | 2 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_return_floor | intervention | 0 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |
| w1_return_floor | intervention | 1 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |
| w1_return_floor | intervention | 2 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |
| w1_budget_remaining | control | 0 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_budget_remaining | control | 1 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_budget_remaining | control | 2 | 1 | 1 | 0 | none | none | v1/v1 | v1/v1 |
| w1_budget_remaining | intervention | 0 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |
| w1_budget_remaining | intervention | 1 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |
| w1_budget_remaining | intervention | 2 | 1 | 1 | 0 | none | none | v2/v2 | v2/v2 |

## 逐格

| instance | valid | FullPass | target_correct | oracle_conditioned | first_error |
|---|---|---|---|---|---|
| w1_wage_gate_control_focused_s0 | True | 1 | True | True | none |
| w1_wage_gate_control_focused_s1 | True | 1 | True | True | none |
| w1_wage_gate_control_focused_s2 | True | 1 | True | True | none |
| w1_wage_gate_control_pipeline_s0 | True | 1 | True | True | none |
| w1_wage_gate_control_pipeline_s1 | True | 1 | True | True | none |
| w1_wage_gate_control_pipeline_s2 | True | 1 | True | True | none |
| w1_wage_gate_intervention_focused_s0 | True | 1 | True | True | none |
| w1_wage_gate_intervention_focused_s1 | True | 1 | True | True | none |
| w1_wage_gate_intervention_focused_s2 | True | 1 | True | True | none |
| w1_wage_gate_intervention_pipeline_s0 | True | 1 | True | True | none |
| w1_wage_gate_intervention_pipeline_s1 | True | 1 | True | True | none |
| w1_wage_gate_intervention_pipeline_s2 | True | 1 | True | True | none |
| w1_return_floor_control_focused_s0 | True | 1 | True | True | none |
| w1_return_floor_control_focused_s1 | True | 1 | True | True | none |
| w1_return_floor_control_focused_s2 | True | 1 | True | True | none |
| w1_return_floor_control_pipeline_s0 | True | 1 | True | True | none |
| w1_return_floor_control_pipeline_s1 | True | 1 | True | True | none |
| w1_return_floor_control_pipeline_s2 | True | 1 | True | True | none |
| w1_return_floor_intervention_focused_s0 | True | 1 | True | True | none |
| w1_return_floor_intervention_focused_s1 | True | 1 | True | True | none |
| w1_return_floor_intervention_focused_s2 | True | 1 | True | True | none |
| w1_return_floor_intervention_pipeline_s0 | True | 1 | True | True | none |
| w1_return_floor_intervention_pipeline_s1 | True | 1 | True | True | none |
| w1_return_floor_intervention_pipeline_s2 | True | 1 | True | True | none |
| w1_budget_remaining_control_focused_s0 | True | 1 | True | True | none |
| w1_budget_remaining_control_focused_s1 | True | 1 | True | True | none |
| w1_budget_remaining_control_focused_s2 | True | 1 | True | True | none |
| w1_budget_remaining_control_pipeline_s0 | True | 1 | True | True | none |
| w1_budget_remaining_control_pipeline_s1 | True | 1 | True | True | none |
| w1_budget_remaining_control_pipeline_s2 | True | 1 | True | True | none |
| w1_budget_remaining_intervention_focused_s0 | True | 1 | True | True | none |
| w1_budget_remaining_intervention_focused_s1 | True | 1 | True | True | none |
| w1_budget_remaining_intervention_focused_s2 | True | 1 | True | True | none |
| w1_budget_remaining_intervention_pipeline_s0 | True | 1 | True | True | none |
| w1_budget_remaining_intervention_pipeline_s1 | True | 1 | True | True | none |
| w1_budget_remaining_intervention_pipeline_s2 | True | 1 | True | True | none |
