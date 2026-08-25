# EXP-GM-OA-02 Exclusive keep / revise

- 时间：2026-08-24T13:15:30.657439+00:00
- phase：rule；mode：rule
- ranking_eligible：false
- OA-01 任务、结果、Scorer 冻结；旧协议 18 格读取 need_change_gate，不重跑。
- 未改 GM-01 / GM-02；未建留出集；未开 GM-03。

## 主报指标

| 来源 | Coverage | ActionSelectionAccuracy | ControlStabilityRate | AdaptationRate | ContractFailureRate | TargetCorrect | OracleConditionedFullPass |
|---|---|---|---|---|---|---|---|
| OA-01 need_change_gate（冻结） | 1.0 | 1.0 | 0.6667 | 1.0 | 0.0 | 0.8333 | 0.8333 |
| OA-02 exclusive_keep_revise | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 | 1.0 |

- 冻结基线说明：ContractFailureRate=0 是因为 OA-01 统一 JSON 接受了 keep 的占位字段；失败记在 TargetCorrect / FullPass，不是提交拒绝。

## 预注册通过条件（只看 OA-02 18 格）

- Coverage = 1.0（要求 1.0）
- ControlStabilityRate = 1.0（要求 1.0）
- AdaptationRate = 1.0（要求 1.0）
- ContractFailureRate = 0.0（要求 0）
- 通过：True

**结论：** 将 keep 与 revise 拆成两个动作，消除了开发集中的无意义占位符失败。这还不等于过度适应机制已解决，暂不建留出题。

## 格子证据

| instance | variant | valid | FullPass | action_sel | target_correct | contract_rejected | first_error |
|---|---|---|---|---|---|---|---|
| appointment_update_control_exclusive_keep_revise_s0 | control | True | 1 | True | True | False | none |
| appointment_update_intervention_exclusive_keep_revise_s0 | intervention | True | 1 | True | True | False | none |
| resource_threshold_control_exclusive_keep_revise_s0 | control | True | 1 | True | True | False | none |
| resource_threshold_intervention_exclusive_keep_revise_s0 | intervention | True | 1 | True | True | False | none |
| responsibility_update_control_exclusive_keep_revise_s0 | control | True | 1 | True | True | False | none |
| responsibility_update_intervention_exclusive_keep_revise_s0 | intervention | True | 1 | True | True | False | none |

## 首错节点

| first_error | n |
|---|---|
| none | 6 |
