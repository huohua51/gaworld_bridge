# EXP-GM-C1-03

- 时间：2026-08-25T08:15:45.614591+00:00
- phase：seed0；gate：A_r0
- 正式对象：Full Multi。Direct 非正式结果。不覆盖 C1-02。
- ranking_eligible：false
- Direct 可做：True（FullPass=1.0，仅校准）
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

- NackPathCoverageIntervention：1.0
- RetryRecoverySuccess：0.0
- ConstraintRegressionRate：0.0
- EnvironmentAutoRepair：0

| 指标 | Multi | DropProtection | DropCoordinator |
|---|---:|---:|---:|
| Coverage | 0.6667 | 1.0 | 0.6667 |
| ActualFinalConflictFree | 1.0 | 1.0 | 0.75 |
| ProtectedAssignmentRetention | 0.75 | 0.5 | 0.75 |
| LowPriorityReallocationCorrect | 0.5 | 0.5 | 0.5 |
| FullPass | 0.5 | 0.5 | 0.0 |
| StrictPair | 0.0 | 0.0 | 0.0 |

- first_error：{'none': 5, 'plan_not_delivered': 8, 'protection_revision_not_delivered': 3, 'retry_not_recovered': 1, 'invalid_joint_assignment': 1}
- 解释：进入了 NACK 路径，但重试未形成完全正确的新方案。不能关闭 AP-C1-D-01。

**结论：** Coverage 或公平性未过，回到 R0。不解释能力。不关闭 AP-C1-D-01。

| instance | valid | FullPass | track | nack | first_error |
|---|---|---|---|---|---|
| c1_03_electrophoresis_001_control_multi_r0 | True | 1 | multi | False | none |
| c1_03_electrophoresis_001_control_drop_protection_r0 | True | 1 | drop_protection | False | none |
| c1_03_electrophoresis_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | False | plan_not_delivered |
| c1_03_electrophoresis_001_intervention_multi_r0 | False | None | multi | True | plan_not_delivered |
| c1_03_electrophoresis_001_intervention_drop_protection_r0 | True | 0 | drop_protection | False | protection_revision_not_delivered |
| c1_03_electrophoresis_001_intervention_drop_coordinator_r0 | False | None | drop_coordinator | True | plan_not_delivered |
| c1_03_cryostat_001_control_multi_r0 | True | 1 | multi | False | none |
| c1_03_cryostat_001_control_drop_protection_r0 | True | 1 | drop_protection | False | none |
| c1_03_cryostat_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | False | plan_not_delivered |
| c1_03_cryostat_001_intervention_multi_r0 | True | 0 | multi | True | retry_not_recovered |
| c1_03_cryostat_001_intervention_drop_protection_r0 | True | 0 | drop_protection | False | protection_revision_not_delivered |
| c1_03_cryostat_001_intervention_drop_coordinator_r0 | True | 0 | drop_coordinator | True | plan_not_delivered |
| c1_03_incubator_shelf_001_control_multi_r0 | True | 0 | multi | False | invalid_joint_assignment |
| c1_03_incubator_shelf_001_control_drop_protection_r0 | True | 1 | drop_protection | False | none |
| c1_03_incubator_shelf_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | False | plan_not_delivered |
| c1_03_incubator_shelf_001_intervention_multi_r0 | False | None | multi | True | plan_not_delivered |
| c1_03_incubator_shelf_001_intervention_drop_protection_r0 | True | 0 | drop_protection | False | protection_revision_not_delivered |
| c1_03_incubator_shelf_001_intervention_drop_coordinator_r0 | False | None | drop_coordinator | True | plan_not_delivered |
