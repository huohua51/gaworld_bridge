# EXP-GM-C1-02

- 时间：2026-08-25T06:56:35.444782+00:00
- phase：seed0；gate：off_floor
- 正式对象：Full Multi。Direct 非正式结果。
- ranking_eligible：false；不能说集体协调已经通过，除非 Full Multi 过门且按指标拆开报告。
- Direct 可做：True（FullPass=1.0，仅校准）
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

| 指标 | Multi | DropRevision | DropCoordinator |
|---|---:|---:|---:|
| Coverage | 1.0 | 1.0 | 1.0 |
| ActualFinalConflictFree | 1.0 | 1.0 | 0.5 |
| JointConstraintSatisfaction | 1.0 | 0.5 | 1.0 |
| JointPlanCommitted | 0.8333 | 0.5 | 0.8333 |
| ExecutionMatchesPlan | 0.8333 | 0.5 | 0.5 |
| RoleCompletion | 1.0 | 1.0 | 1.0 |
| ConflictRepairSuccess | 0.8333 | 0.5 | 0.5 |
| FullPass | 0.8333 | 0.5 | 0.0 |
| StrictPair | 0.6667 | 0.0 | 0.0 |

- first_error：{'none': 8, 'plan_not_delivered': 6, 'invalid_joint_assignment': 1, 'constraint_revision_not_delivered': 3}
- 解释：Full Multi 未处于地板。按首错定位方案形成、交付或执行。不能提前说集体协调已经通过。

**结论：** Full Multi 未处于地板。按首错定位方案形成、交付或执行。不能提前说集体协调已经通过。 组件修复通过不等于集体协调通过。

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| c1_02_optics_table_001_control_multi_r0 | True | 1 | multi | none |
| c1_02_optics_table_001_control_drop_revision_r0 | True | 1 | drop_revision | none |
| c1_02_optics_table_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_optics_table_001_intervention_multi_r0 | True | 0 | multi | invalid_joint_assignment |
| c1_02_optics_table_001_intervention_drop_revision_r0 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_optics_table_001_intervention_drop_coordinator_r0 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_greenhouse_001_control_multi_r0 | True | 1 | multi | none |
| c1_02_greenhouse_001_control_drop_revision_r0 | True | 1 | drop_revision | none |
| c1_02_greenhouse_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_greenhouse_001_intervention_multi_r0 | True | 1 | multi | none |
| c1_02_greenhouse_001_intervention_drop_revision_r0 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_greenhouse_001_intervention_drop_coordinator_r0 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_cold_store_001_control_multi_r0 | True | 1 | multi | none |
| c1_02_cold_store_001_control_drop_revision_r0 | True | 1 | drop_revision | none |
| c1_02_cold_store_001_control_drop_coordinator_r0 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_cold_store_001_intervention_multi_r0 | True | 1 | multi | none |
| c1_02_cold_store_001_intervention_drop_revision_r0 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_cold_store_001_intervention_drop_coordinator_r0 | True | 0 | drop_coordinator | plan_not_delivered |
