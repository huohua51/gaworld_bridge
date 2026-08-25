# EXP-GM-C1-03

- 时间：2026-08-25T08:30:10.044749+00:00
- phase：seed0_planid_rescore；status：stopped_at_seed0_retry_gate；measurement_result：pass
- 正式对象：Full Multi。Direct 非正式结果。不覆盖 C1-02。
- ranking_eligible：false；repeat_1_2_allowed：false；holdout_allowed：false
- Direct 可做：True（FullPass=1.0，仅校准）
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

- nack_path_exercised：3/3
- retry_evaluable：3/3
- system_retry_recovered：0/3
- semantic_retry_assignment_correct：0/3（诊断，不改变 FullPass）
- retry_contract_failure：2/3
- retry_not_adapted：1/3
- RetryRecoverySuccess：0.0
- ConstraintRegressionRate：0.0（重试未恢复时不得单独强调为好结果）
- EnvironmentAutoRepair：0

| 指标 | Multi | DropProtection | DropCoordinator |
|---|---:|---:|---:|
| Coverage | 1.0 | 1.0 | 1.0 |
| ActualFinalConflictFree | 0.6667 | 1.0 | 0.5 |
| ProtectedAssignmentRetention | 0.5 | 0.5 | 0.5 |
| LowPriorityReallocationCorrect | 0.3333 | 0.5 | 0.3333 |
| FullPass | 0.3333 | 0.5 | 0.0 |
| StrictPair | 0.0 | 0.0 | 0.0 |

- first_error：{'plan_not_delivered': 6, 'none': 5, 'protection_revision_not_delivered': 3, 'retry_not_recovered': 1, 'retry_plan_version_invalid': 2, 'invalid_joint_assignment': 1}
- 解释：C1-03 测量有效。平台成功让真模型三次进入优先级 NACK 重试，但没有一次形成系统可接受的正确终局：两次违反版本握手契约，一次在契约合规的情况下原样交回被拒绝方案。忽略版本后三格语义分配也均不正确。
- 不能说：Coverage 只有 0.6667；两格不可测量；C1 重试已经修好；三次都是优先级推理错误；C1 完整集体协调已经通过。

**结论：** 完整多智能体重试能力尚未通过。AP-C1-D-01 不能关闭。版本握手失败单列为 AP-C1-F-01。功能进度仍约 75%。

| instance | valid | FullPass | track | nack | first_error |
|---|---|---|---|---|---|
| c1_03_cryostat_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | False | plan_not_delivered |
| c1_03_cryostat_001_control_drop_protection_r0 | True | 1 | drop_protection | False | none |
| c1_03_cryostat_001_control_multi_r0 | True | 1 | multi | False | none |
| c1_03_cryostat_001_intervention_drop_coordinator_r0 | True | 0 | drop_coordinator | True | plan_not_delivered |
| c1_03_cryostat_001_intervention_drop_protection_r0 | True | 0 | drop_protection | False | protection_revision_not_delivered |
| c1_03_cryostat_001_intervention_multi_r0 | True | 0 | multi | True | retry_not_recovered |
| c1_03_electrophoresis_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | False | plan_not_delivered |
| c1_03_electrophoresis_001_control_drop_protection_r0 | True | 1 | drop_protection | False | none |
| c1_03_electrophoresis_001_control_multi_r0 | True | 1 | multi | False | none |
| c1_03_electrophoresis_001_intervention_drop_coordinator_r0 | True | 0 | drop_coordinator | True | plan_not_delivered |
| c1_03_electrophoresis_001_intervention_drop_protection_r0 | True | 0 | drop_protection | False | protection_revision_not_delivered |
| c1_03_electrophoresis_001_intervention_multi_r0 | True | 0 | multi | True | retry_plan_version_invalid |
| c1_03_incubator_shelf_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | False | plan_not_delivered |
| c1_03_incubator_shelf_001_control_drop_protection_r0 | True | 1 | drop_protection | False | none |
| c1_03_incubator_shelf_001_control_multi_r0 | True | 0 | multi | False | invalid_joint_assignment |
| c1_03_incubator_shelf_001_intervention_drop_coordinator_r0 | True | 0 | drop_coordinator | True | plan_not_delivered |
| c1_03_incubator_shelf_001_intervention_drop_protection_r0 | True | 0 | drop_protection | False | protection_revision_not_delivered |
| c1_03_incubator_shelf_001_intervention_multi_r0 | True | 0 | multi | True | retry_plan_version_invalid |
