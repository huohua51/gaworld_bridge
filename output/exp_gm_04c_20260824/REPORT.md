# EXP-GM-04c TASK-W1-review-loop Pilot

- 时间：2026-08-24T04:57:18.320037+00:00
- 状态：`pilot`，不可排名
- `conformance_result`：`pass`
- `agent_workflow_result`：`partial`
- 平台目标：私有隔离 / 权限 / 审核送达 / 返工触发
- 已诊断协议失败：`false_positive_revision`、`incomplete_required_change_adoption`
- 路线：04a → 04b → 04c → I1 → REL1；协议问题进 Backlog，不进底层平台修复
- v2 只进入 Reviewer 私有上下文；Executor 初始只持有 v1
- FullPass 要求 oracle_conditioned_success，碰巧过线或未采用 Review 不算干净成功

## 覆盖与主结果

- requested：54
- measurement_valid：54
- coverage：1.0
- oracle_conditioned FullPass Rate：0.6667
- target_correct Rate：0.7778

### 分轨

- Focused：1.0（control 1.0 / intervention 1.0）
- Full review：0.5（control 0.3333 / intervention 0.6667）
- Drop-review：0.5（control 1.0 / intervention 0.0）
- ReviewValue (Full − Drop)：0.0
- ReviewValue intervention only：0.6667
- ReviewPropagationGap (Focused − Full)：0.5

## 决策

Focused 高、Full 干预未满、Rule Full 高：平台审核通道能跑，失败在模型 Reviewer / Executor 协作，不进入第三步修复。

## 科学结论

EXP-GM-04c 的 Rule 负控全部按预期成立：消息送达时 control/intervention 都过；消息丢弃时 intervention 失败；Reviewer 写产物和 Executor 读私有 v2 被拒绝；旧版本 Review 与重复投递只采用一次。因此 R0 测量门有效，54 格全部 `measurement_valid`。

真模型（GLM-4-Flash）结果不是“平台审核机制坏了”，而是：

* **Focused = 1.0**：Executor 自己能完成 v1/v2 函数契约。
* **Drop 干预 = 0.0**：丢掉 Review 后变不出 v2，说明 v2 没有泄漏到 Executor。
* **Full 干预 = 0.6667**：工资门槛和剩余预算能走完“审核→送达→返工”；最低返还三次都是 Reviewer 意见正确（`advice=True`），Executor 把 `SPEC_VERSION` 改成 v2 却仍使用 0.3。这是“建议正确但不采用数值”，不是路由失败。
* **Full 控制 = 0.3333**：返还和预算上 Reviewer 在 v1 已正确时仍发 `revise`（`advice=False`）。最终产物仍过 v1 隐藏测试，所以 `target_correct=1`，但路径成功=0。

干预组 ReviewValue = 0.6667，ReviewPropagationGap = 0.5。这足以说：GAWorld 已经能在角色私有信息和权限隔离下传递审核意见；当前瓶颈是模型有没有批准对、以及 Executor 有没有按 `required_change` 改常数。

按路线图，这里**不进入修改 GAWorld 并复测**。完整 TASK-W1（Publisher / Planner / Coordinator）先不要加。建议暂停继续加厚 T3，转去补一个通信或关系类代表任务。

| instance | valid | FullPass | target_correct | oracle_conditioned | first_error | advice |
|---|---|---|---|---|---|---|
| w1_wage_gate_control_focused_s0 | True | 1 | True | True | none | None |
| w1_wage_gate_control_full_review_s0 | True | 1 | True | True | none | True |
| w1_wage_gate_control_drop_review_s0 | True | 1 | True | True | none | True |
| w1_wage_gate_intervention_focused_s0 | True | 1 | True | True | none | None |
| w1_wage_gate_intervention_full_review_s0 | True | 1 | True | True | none | True |
| w1_wage_gate_intervention_drop_review_s0 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_return_floor_control_focused_s0 | True | 1 | True | True | none | None |
| w1_return_floor_control_full_review_s0 | True | 0 | True | False | none | False |
| w1_return_floor_control_drop_review_s0 | True | 1 | True | True | none | False |
| w1_return_floor_intervention_focused_s0 | True | 1 | True | True | none | None |
| w1_return_floor_intervention_full_review_s0 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_return_floor_intervention_drop_review_s0 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_budget_remaining_control_focused_s0 | True | 1 | True | True | none | None |
| w1_budget_remaining_control_full_review_s0 | True | 0 | True | False | none | False |
| w1_budget_remaining_control_drop_review_s0 | True | 1 | True | True | none | False |
| w1_budget_remaining_intervention_focused_s0 | True | 1 | True | True | none | None |
| w1_budget_remaining_intervention_full_review_s0 | True | 1 | True | True | none | True |
| w1_budget_remaining_intervention_drop_review_s0 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_wage_gate_control_focused_s1 | True | 1 | True | True | none | None |
| w1_wage_gate_control_focused_s2 | True | 1 | True | True | none | None |
| w1_wage_gate_control_full_review_s1 | True | 1 | True | True | none | True |
| w1_wage_gate_control_full_review_s2 | True | 1 | True | True | none | True |
| w1_wage_gate_control_drop_review_s1 | True | 1 | True | True | none | True |
| w1_wage_gate_control_drop_review_s2 | True | 1 | True | True | none | True |
| w1_wage_gate_intervention_focused_s1 | True | 1 | True | True | none | None |
| w1_wage_gate_intervention_focused_s2 | True | 1 | True | True | none | None |
| w1_wage_gate_intervention_full_review_s1 | True | 1 | True | True | none | True |
| w1_wage_gate_intervention_full_review_s2 | True | 1 | True | True | none | True |
| w1_wage_gate_intervention_drop_review_s1 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_wage_gate_intervention_drop_review_s2 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_return_floor_control_focused_s1 | True | 1 | True | True | none | None |
| w1_return_floor_control_focused_s2 | True | 1 | True | True | none | None |
| w1_return_floor_control_full_review_s1 | True | 0 | True | False | none | False |
| w1_return_floor_control_full_review_s2 | True | 0 | True | False | none | False |
| w1_return_floor_control_drop_review_s1 | True | 1 | True | True | none | False |
| w1_return_floor_control_drop_review_s2 | True | 1 | True | True | none | False |
| w1_return_floor_intervention_focused_s1 | True | 1 | True | True | none | None |
| w1_return_floor_intervention_focused_s2 | True | 1 | True | True | none | None |
| w1_return_floor_intervention_full_review_s1 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_return_floor_intervention_full_review_s2 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_return_floor_intervention_drop_review_s1 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_return_floor_intervention_drop_review_s2 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_budget_remaining_control_focused_s1 | True | 1 | True | True | none | None |
| w1_budget_remaining_control_focused_s2 | True | 1 | True | True | none | None |
| w1_budget_remaining_control_full_review_s1 | True | 0 | True | False | none | False |
| w1_budget_remaining_control_full_review_s2 | True | 0 | True | False | none | False |
| w1_budget_remaining_control_drop_review_s1 | True | 1 | True | True | none | False |
| w1_budget_remaining_control_drop_review_s2 | True | 1 | True | True | none | False |
| w1_budget_remaining_intervention_focused_s1 | True | 1 | True | True | none | None |
| w1_budget_remaining_intervention_focused_s2 | True | 1 | True | True | none | None |
| w1_budget_remaining_intervention_full_review_s1 | True | 1 | True | True | none | True |
| w1_budget_remaining_intervention_full_review_s2 | True | 1 | True | True | none | True |
| w1_budget_remaining_intervention_drop_review_s1 | True | 0 | False | False | final_artifact_incorrect | True |
| w1_budget_remaining_intervention_drop_review_s2 | True | 0 | False | False | final_artifact_incorrect | True |
