# EXP-GM-C1-02

- 时间：2026-08-25T07:10:58.634497+00:00
- phase：all；gate：off_floor
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

- first_error：{'none': 24, 'plan_not_delivered': 18, 'invalid_joint_assignment': 3, 'constraint_revision_not_delivered': 9}

## 登记结论

C1 正式多智能体开发集测量有效。系统已经具备基本冲突消解能力，但没有完全通过登记式集体协调。

| 能力 | 结果 | 结论 |
| --- | ---: | --- |
| 发现并消除资源冲突 | 1.0 | 已具备 |
| 同时满足双方可行约束 | 1.0 | 已具备 |
| 按登记优先级形成唯一方案 | 0.8333 | 未完全通过 |
| control/intervention 成对适应 | 0.6667 | 未完全通过 |
| 完整协调闭环 | 0.8333 | 部分通过 |

不能说“集体协调已经通过”，也不能说“GAWorld 不会集体协调”。准确说法：GAWorld 多智能体系统能够稳定发现并消除资源冲突，但在光学台 intervention 上稳定违反优先级保持规则。缺口已经从“能否消除冲突”收缩到“能否在消除冲突时同时遵守分配政策”。

Drop Revision：`ActualFinalConflictFree=1.0` 且 `JointConstraintSatisfaction=0.5`，说明只检查最终是否冲突不够，必须同时检查每个 Agent 的最新私有约束。`RevisionDeliveryValue=0.8333-0.5=0.3333`。

Drop Coordinator：18/18 首错 `plan_not_delivered`，`RoleCompletion=1.0` 只表示角色执行过，不表示闭环完成。`CoordinatorDeliveryValue=0.8333-0=0.8333`。这两个值说明消息交付具有因果价值，不能扩写为一般性多智能体优势。

下一步：`CAL-GM-C1-PRIORITY-01`。不建留出，不开 L1，不覆盖 C1-02。

**结论：** 测量有效，部分通过。组件修复通过不等于集体协调通过。

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
| c1_02_optics_table_001_control_multi_r1 | True | 1 | multi | none |
| c1_02_optics_table_001_control_drop_revision_r1 | True | 1 | drop_revision | none |
| c1_02_optics_table_001_control_drop_coordinator_r1 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_optics_table_001_intervention_multi_r1 | True | 0 | multi | invalid_joint_assignment |
| c1_02_optics_table_001_intervention_drop_revision_r1 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_optics_table_001_intervention_drop_coordinator_r1 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_greenhouse_001_control_multi_r1 | True | 1 | multi | none |
| c1_02_greenhouse_001_control_drop_revision_r1 | True | 1 | drop_revision | none |
| c1_02_greenhouse_001_control_drop_coordinator_r1 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_greenhouse_001_intervention_multi_r1 | True | 1 | multi | none |
| c1_02_greenhouse_001_intervention_drop_revision_r1 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_greenhouse_001_intervention_drop_coordinator_r1 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_cold_store_001_control_multi_r1 | True | 1 | multi | none |
| c1_02_cold_store_001_control_drop_revision_r1 | True | 1 | drop_revision | none |
| c1_02_cold_store_001_control_drop_coordinator_r1 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_cold_store_001_intervention_multi_r1 | True | 1 | multi | none |
| c1_02_cold_store_001_intervention_drop_revision_r1 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_cold_store_001_intervention_drop_coordinator_r1 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_optics_table_001_control_multi_r2 | True | 1 | multi | none |
| c1_02_optics_table_001_control_drop_revision_r2 | True | 1 | drop_revision | none |
| c1_02_optics_table_001_control_drop_coordinator_r2 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_optics_table_001_intervention_multi_r2 | True | 0 | multi | invalid_joint_assignment |
| c1_02_optics_table_001_intervention_drop_revision_r2 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_optics_table_001_intervention_drop_coordinator_r2 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_greenhouse_001_control_multi_r2 | True | 1 | multi | none |
| c1_02_greenhouse_001_control_drop_revision_r2 | True | 1 | drop_revision | none |
| c1_02_greenhouse_001_control_drop_coordinator_r2 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_greenhouse_001_intervention_multi_r2 | True | 1 | multi | none |
| c1_02_greenhouse_001_intervention_drop_revision_r2 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_greenhouse_001_intervention_drop_coordinator_r2 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_cold_store_001_control_multi_r2 | True | 1 | multi | none |
| c1_02_cold_store_001_control_drop_revision_r2 | True | 1 | drop_revision | none |
| c1_02_cold_store_001_control_drop_coordinator_r2 | True | 0 | drop_coordinator | plan_not_delivered |
| c1_02_cold_store_001_intervention_multi_r2 | True | 1 | multi | none |
| c1_02_cold_store_001_intervention_drop_revision_r2 | True | 0 | drop_revision | constraint_revision_not_delivered |
| c1_02_cold_store_001_intervention_drop_coordinator_r2 | True | 0 | drop_coordinator | plan_not_delivered |
