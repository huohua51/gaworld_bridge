# EXP-GM-04d Protocol Retest

- 时间：2026-08-24T07:12:18.819980+00:00
- 状态：pilot，不可排名
- 开发集：工资/返还/预算；留出题未参与协议设计
- 旧协议来自冻结的 04c Full 格，不在同一 54 格上重训

## 04d-A 错误修改

- FalsePositiveRevisionRate 旧：0.6667
- FalsePositiveRevisionRate 新：0.6667
- ProtocolGain (旧−新，越大越好)：0.0

## 04d-B 意见采用

- PatchAdoptionRate 旧：0.6667
- PatchAdoptionRate 新：None
- ProtocolGain (新−旧，越大越好)：None

## 决策

开发集上**不成立**协议改进。不跑留出题。

1. control 错误修改率未下降：新旧都是 0.6667（返还+预算 6/9）。冻结规则只约束 `decision` 与 `mismatches` 自洽，挡不住在已匹配草稿上编造 mismatches。
2. intervention 意见采用率无法计算：新协议 9 格 `review_advice_correct=false`，分母为空。工资题旧协议 3/3 能给出正确 revise，新协议反而把意见写错。
3. Drop-review 干预仍失败，负控有效。
4. Rule 正负控通过；环境没有代改文件。
5. 留出题未跑，避免在未改善的协议上污染第二测试集。

这 27 格新协议 + 18 格冻结旧 Full 可作 regression。下一步若再改协议，需要能核对 mismatches 是否相对草稿真实成立，而不是只检查 JSON 自洽。

| instance | protocol | variant | track | valid | FullPass | FP | adopt | first_error |
|---|---|---|---|---|---|---|---|---|
| w1_budget_remaining_control_full_review_s0 | legacy_frozen | control | full_review | True | 0 | True | False | none |
| w1_budget_remaining_control_full_review_s1 | legacy_frozen | control | full_review | True | 0 | True | False | none |
| w1_budget_remaining_control_full_review_s2 | legacy_frozen | control | full_review | True | 0 | True | False | none |
| w1_budget_remaining_intervention_full_review_s0 | legacy_frozen | intervention | full_review | True | 1 | False | True | none |
| w1_budget_remaining_intervention_full_review_s1 | legacy_frozen | intervention | full_review | True | 1 | False | True | none |
| w1_budget_remaining_intervention_full_review_s2 | legacy_frozen | intervention | full_review | True | 1 | False | True | none |
| w1_return_floor_control_full_review_s0 | legacy_frozen | control | full_review | True | 0 | True | False | none |
| w1_return_floor_control_full_review_s1 | legacy_frozen | control | full_review | True | 0 | True | False | none |
| w1_return_floor_control_full_review_s2 | legacy_frozen | control | full_review | True | 0 | True | False | none |
| w1_return_floor_intervention_full_review_s0 | legacy_frozen | intervention | full_review | True | 0 | False | False | final_artifact_incorrect |
| w1_return_floor_intervention_full_review_s1 | legacy_frozen | intervention | full_review | True | 0 | False | False | final_artifact_incorrect |
| w1_return_floor_intervention_full_review_s2 | legacy_frozen | intervention | full_review | True | 0 | False | False | final_artifact_incorrect |
| w1_wage_gate_control_full_review_s0 | legacy_frozen | control | full_review | True | 1 | False | False | none |
| w1_wage_gate_control_full_review_s1 | legacy_frozen | control | full_review | True | 1 | False | False | none |
| w1_wage_gate_control_full_review_s2 | legacy_frozen | control | full_review | True | 1 | False | False | none |
| w1_wage_gate_intervention_full_review_s0 | legacy_frozen | intervention | full_review | True | 1 | False | True | none |
| w1_wage_gate_intervention_full_review_s1 | legacy_frozen | intervention | full_review | True | 1 | False | True | none |
| w1_wage_gate_intervention_full_review_s2 | legacy_frozen | intervention | full_review | True | 1 | False | True | none |
| w1_budget_remaining_control_full_review_s0 | mismatches_patch_v1 | control | full_review | True | 0 | True | False | none |
| w1_budget_remaining_control_full_review_s1 | mismatches_patch_v1 | control | full_review | True | 0 | True | False | none |
| w1_budget_remaining_control_full_review_s2 | mismatches_patch_v1 | control | full_review | True | 0 | True | False | none |
| w1_budget_remaining_intervention_drop_review_s0 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_budget_remaining_intervention_drop_review_s1 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_budget_remaining_intervention_drop_review_s2 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_budget_remaining_intervention_full_review_s0 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
| w1_budget_remaining_intervention_full_review_s1 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
| w1_budget_remaining_intervention_full_review_s2 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
| w1_return_floor_control_full_review_s0 | mismatches_patch_v1 | control | full_review | True | 0 | True | False | none |
| w1_return_floor_control_full_review_s1 | mismatches_patch_v1 | control | full_review | True | 0 | True | False | none |
| w1_return_floor_control_full_review_s2 | mismatches_patch_v1 | control | full_review | True | 0 | True | False | none |
| w1_return_floor_intervention_drop_review_s0 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_return_floor_intervention_drop_review_s1 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_return_floor_intervention_drop_review_s2 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_return_floor_intervention_full_review_s0 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
| w1_return_floor_intervention_full_review_s1 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
| w1_return_floor_intervention_full_review_s2 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
| w1_wage_gate_control_full_review_s0 | mismatches_patch_v1 | control | full_review | True | 1 | False | False | none |
| w1_wage_gate_control_full_review_s1 | mismatches_patch_v1 | control | full_review | True | 1 | False | False | none |
| w1_wage_gate_control_full_review_s2 | mismatches_patch_v1 | control | full_review | True | 1 | False | False | none |
| w1_wage_gate_intervention_drop_review_s0 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_wage_gate_intervention_drop_review_s1 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_wage_gate_intervention_drop_review_s2 | mismatches_patch_v1 | intervention | drop_review | True | 0 | False | False | final_artifact_incorrect |
| w1_wage_gate_intervention_full_review_s0 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
| w1_wage_gate_intervention_full_review_s1 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
| w1_wage_gate_intervention_full_review_s2 | mismatches_patch_v1 | intervention | full_review | True | 0 | False | False | review_not_adopted |
