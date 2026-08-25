# EXP-GM-04e-R Evidence-bound Reviewer

- 时间：2026-08-24T07:36:18.575756+00:00
- 阶段：04e-R，只测 Reviewer，不跑 Executor
- 开发集：工资 / 返还 / 预算；留出题未触碰
- 模型：GLM-4-Flash；温度 0；Reviewer 调用预算新旧均为最多 2 次
- 状态：pilot，不可排名

## 主结果

- requested：36（旧协议 18 + 新协议 18）
- measurement_valid：36，coverage：1.0
- FalsePositiveRevisionRate 旧：0.3333 新：0.0
- TrueRevisionRate 旧：1.0 新：1.0
- EvidenceGroundingRate：1.0
- 可解析率 旧：1.0 新：1.0
- 人均 Reviewer 调用 旧：1.0 新：1.0（两边都没有用到重试）
- 进入 04e-E：True

## 决策

开发集 Reviewer **过门**。可以进入 04e-E。

本轮比较的是 Reviewer 单步能力，不是完整 Reviewer—Executor 链。旧协议 FalsePositiveRevisionRate=0.333 来自本矩阵的 legacy 对照，不是 04c Full 的 0.667：04c Full 里返还+预算 control 都会乱 revise，这里 reviewer-only 的预算题 control 已经能 approve，只有返还题 control 仍稳定 false-positive。新协议把返还题 control 也改成了 grounded approve。

Intervention 两侧 TrueRevisionRate 都是 1.0，证据核验也全部通过，没有靠 Verifier 代写审核。Nack 未启用，因此改进不是“多调用一次模型”。环境没有改产物。协议模板没有留出题字段名。

## 过门条件

| 条件 | 结果 |
|---|---|
| FalsePositiveRevisionRate 低于旧协议 | 0.0 < 0.3333 |
| TrueRevisionRate 不低于旧协议 | 1.0 = 1.0 |
| EvidenceGroundingRate = 1 | 1.0 |
| 无新增 Contract/Coverage 失败 | coverage=1，可解析率=1 |

## 方法说明

旧协议只检查 JSON 能否解析。新协议要求每条 mismatch 绑定本次草稿的 `ArtifactFact`：fact_id 属于本次草稿、observed 等于草稿、required 来自私有 criterion、operator 下确实不满足。control 已匹配时任何 mismatch 都被拒绝。Verifier 只能拒绝，不能生成正确 Review。

返还题 control 的旧协议仍会编造“整数截断所以不合格”之类理由并 `decision=revise`；同一草稿在证据绑定下只能 `approve` 且 `mismatches=[]`，因为 `RATE=0.3` 已经等于私有标准。

## 下一步

进入 04e-E：Rule Reviewer 提供一条保证正确的 typed patch，只测真模型 Executor 是否真实改值。不跑 Full，不跑留出题。

| instance | protocol | variant | valid | FP | true_rev | grounded | calls | first_error |
|---|---|---|---|---|---|---|---|---|
| w1_wage_gate_control_legacy_s0 | legacy | control | True | False | False | True | 1 | none |
| w1_wage_gate_control_legacy_s1 | legacy | control | True | False | False | True | 1 | none |
| w1_wage_gate_control_legacy_s2 | legacy | control | True | False | False | True | 1 | none |
| w1_wage_gate_intervention_legacy_s0 | legacy | intervention | True | False | True | True | 1 | none |
| w1_wage_gate_intervention_legacy_s1 | legacy | intervention | True | False | True | True | 1 | none |
| w1_wage_gate_intervention_legacy_s2 | legacy | intervention | True | False | True | True | 1 | none |
| w1_wage_gate_control_evidence_bound_s0 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_wage_gate_control_evidence_bound_s1 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_wage_gate_control_evidence_bound_s2 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_wage_gate_intervention_evidence_bound_s0 | evidence_bound | intervention | True | False | True | True | 1 | none |
| w1_wage_gate_intervention_evidence_bound_s1 | evidence_bound | intervention | True | False | True | True | 1 | none |
| w1_wage_gate_intervention_evidence_bound_s2 | evidence_bound | intervention | True | False | True | True | 1 | none |
| w1_return_floor_control_legacy_s0 | legacy | control | True | True | False | True | 1 | false_positive_revision |
| w1_return_floor_control_legacy_s1 | legacy | control | True | True | False | True | 1 | false_positive_revision |
| w1_return_floor_control_legacy_s2 | legacy | control | True | True | False | True | 1 | false_positive_revision |
| w1_return_floor_intervention_legacy_s0 | legacy | intervention | True | False | True | True | 1 | none |
| w1_return_floor_intervention_legacy_s1 | legacy | intervention | True | False | True | True | 1 | none |
| w1_return_floor_intervention_legacy_s2 | legacy | intervention | True | False | True | True | 1 | none |
| w1_return_floor_control_evidence_bound_s0 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_return_floor_control_evidence_bound_s1 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_return_floor_control_evidence_bound_s2 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_return_floor_intervention_evidence_bound_s0 | evidence_bound | intervention | True | False | True | True | 1 | none |
| w1_return_floor_intervention_evidence_bound_s1 | evidence_bound | intervention | True | False | True | True | 1 | none |
| w1_return_floor_intervention_evidence_bound_s2 | evidence_bound | intervention | True | False | True | True | 1 | none |
| w1_budget_remaining_control_legacy_s0 | legacy | control | True | False | False | True | 1 | none |
| w1_budget_remaining_control_legacy_s1 | legacy | control | True | False | False | True | 1 | none |
| w1_budget_remaining_control_legacy_s2 | legacy | control | True | False | False | True | 1 | none |
| w1_budget_remaining_intervention_legacy_s0 | legacy | intervention | True | False | True | True | 1 | none |
| w1_budget_remaining_intervention_legacy_s1 | legacy | intervention | True | False | True | True | 1 | none |
| w1_budget_remaining_intervention_legacy_s2 | legacy | intervention | True | False | True | True | 1 | none |
| w1_budget_remaining_control_evidence_bound_s0 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_budget_remaining_control_evidence_bound_s1 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_budget_remaining_control_evidence_bound_s2 | evidence_bound | control | True | False | False | True | 1 | none |
| w1_budget_remaining_intervention_evidence_bound_s0 | evidence_bound | intervention | True | False | True | True | 1 | none |
| w1_budget_remaining_intervention_evidence_bound_s1 | evidence_bound | intervention | True | False | True | True | 1 | none |
| w1_budget_remaining_intervention_evidence_bound_s2 | evidence_bound | intervention | True | False | True | True | 1 | none |
