# EXP-GM-L1-01c

- 时间：2026-08-25T11:33:01.921373+00:00
- phase：repeats；gate：development_regression_pass
- 正式对象：Full Multi。Direct 非正式结果。不覆盖 C1。
- ranking_eligible：false
- Direct 可做：True（FullPass=1.0，仅校准）
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c
- Coverage：1.0

| 指标 control/intervention | Multi | DropCheckpoint | DropHandoff |
|---|---|---|---|
| Coverage | 1.0 | 1.0 | 1.0 |
| checkpoint_created | 1.0/1.0 | 1.0/1.0 | 1.0/1.0 |
| checkpoint_delivered_to_successor | 1.0/1.0 | 1.0/0.0 | 1.0/1.0 |
| checkpoint_content_correct | 1.0/1.0 | 1.0/1.0 | 1.0/1.0 |
| handoff_delivered | 1.0/1.0 | 1.0/1.0 | 1.0/0.0 |
| handoff_adopted | 1.0/1.0 | 1.0/1.0 | 1.0/0.0 |
| resume_step_correct | 1.0/1.0 | 1.0/1.0 | 1.0/0.3333 |
| completed_step_not_repeated | 1.0/1.0 | 1.0/1.0 | 1.0/1.0 |
| remaining_step_not_skipped | 1.0/1.0 | 1.0/1.0 | 1.0/1.0 |
| target_correct | 1.0/1.0 | 1.0/0.6667 | 1.0/1.0 |
| FullPass | 1.0 | 0.5 | 0.5 |
| StrictPair | 1.0 | 0.0 | 0.0 |

- Full Multi：control 9/9；interruption 9/9；strict_pair 9/9
- Drop Checkpoint：control 9/9；interruption 0/9
- Drop Handoff：control 9/9；interruption 0/9
- RecoveryLatency（intervention multi）：7.0
- first_error：{'none': 36, 'checkpoint_not_delivered': 9, 'handoff_not_delivered': 9}
- 解释：54 格保持同一模式。开发集回归通过。不能写泛化通过或进入正式排名。

**结论：** 54 格开发集回归通过。不能写泛化或排名。 功能进度约 85% 是评测建设与机制覆盖，不是 GAWorld 能力得分。不做 C1-04。

```yaml
interruption_recovery_development_result: pass
checkpoint_causal_dependency: replicated
handoff_causal_dependency: replicated
resume_workflow_regression: pass
original_failure_status: resolved_on_development_regression
ranking_eligible: false
l1_01b_strict_pair_unchanged: 2_of_3
```

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| l1_01c_gas_cylinder_001_control_multi_r0 | True | 1 | multi | none |
| l1_01c_gas_cylinder_001_control_drop_checkpoint_r0 | True | 1 | drop_checkpoint | none |
| l1_01c_gas_cylinder_001_control_drop_handoff_r0 | True | 1 | drop_handoff | none |
| l1_01c_gas_cylinder_001_intervention_multi_r0 | True | 1 | multi | none |
| l1_01c_gas_cylinder_001_intervention_drop_checkpoint_r0 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_gas_cylinder_001_intervention_drop_handoff_r0 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_01c_balance_check_001_control_multi_r0 | True | 1 | multi | none |
| l1_01c_balance_check_001_control_drop_checkpoint_r0 | True | 1 | drop_checkpoint | none |
| l1_01c_balance_check_001_control_drop_handoff_r0 | True | 1 | drop_handoff | none |
| l1_01c_balance_check_001_intervention_multi_r0 | True | 1 | multi | none |
| l1_01c_balance_check_001_intervention_drop_checkpoint_r0 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_balance_check_001_intervention_drop_handoff_r0 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_01c_label_intake_001_control_multi_r0 | True | 1 | multi | none |
| l1_01c_label_intake_001_control_drop_checkpoint_r0 | True | 1 | drop_checkpoint | none |
| l1_01c_label_intake_001_control_drop_handoff_r0 | True | 1 | drop_handoff | none |
| l1_01c_label_intake_001_intervention_multi_r0 | True | 1 | multi | none |
| l1_01c_label_intake_001_intervention_drop_checkpoint_r0 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_label_intake_001_intervention_drop_handoff_r0 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_01c_gas_cylinder_001_control_multi_r1 | True | 1 | multi | none |
| l1_01c_gas_cylinder_001_control_drop_checkpoint_r1 | True | 1 | drop_checkpoint | none |
| l1_01c_gas_cylinder_001_control_drop_handoff_r1 | True | 1 | drop_handoff | none |
| l1_01c_gas_cylinder_001_intervention_multi_r1 | True | 1 | multi | none |
| l1_01c_gas_cylinder_001_intervention_drop_checkpoint_r1 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_gas_cylinder_001_intervention_drop_handoff_r1 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_01c_balance_check_001_control_multi_r1 | True | 1 | multi | none |
| l1_01c_balance_check_001_control_drop_checkpoint_r1 | True | 1 | drop_checkpoint | none |
| l1_01c_balance_check_001_control_drop_handoff_r1 | True | 1 | drop_handoff | none |
| l1_01c_balance_check_001_intervention_multi_r1 | True | 1 | multi | none |
| l1_01c_balance_check_001_intervention_drop_checkpoint_r1 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_balance_check_001_intervention_drop_handoff_r1 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_01c_label_intake_001_control_multi_r1 | True | 1 | multi | none |
| l1_01c_label_intake_001_control_drop_checkpoint_r1 | True | 1 | drop_checkpoint | none |
| l1_01c_label_intake_001_control_drop_handoff_r1 | True | 1 | drop_handoff | none |
| l1_01c_label_intake_001_intervention_multi_r1 | True | 1 | multi | none |
| l1_01c_label_intake_001_intervention_drop_checkpoint_r1 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_label_intake_001_intervention_drop_handoff_r1 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_01c_gas_cylinder_001_control_multi_r2 | True | 1 | multi | none |
| l1_01c_gas_cylinder_001_control_drop_checkpoint_r2 | True | 1 | drop_checkpoint | none |
| l1_01c_gas_cylinder_001_control_drop_handoff_r2 | True | 1 | drop_handoff | none |
| l1_01c_gas_cylinder_001_intervention_multi_r2 | True | 1 | multi | none |
| l1_01c_gas_cylinder_001_intervention_drop_checkpoint_r2 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_gas_cylinder_001_intervention_drop_handoff_r2 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_01c_balance_check_001_control_multi_r2 | True | 1 | multi | none |
| l1_01c_balance_check_001_control_drop_checkpoint_r2 | True | 1 | drop_checkpoint | none |
| l1_01c_balance_check_001_control_drop_handoff_r2 | True | 1 | drop_handoff | none |
| l1_01c_balance_check_001_intervention_multi_r2 | True | 1 | multi | none |
| l1_01c_balance_check_001_intervention_drop_checkpoint_r2 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_balance_check_001_intervention_drop_handoff_r2 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_01c_label_intake_001_control_multi_r2 | True | 1 | multi | none |
| l1_01c_label_intake_001_control_drop_checkpoint_r2 | True | 1 | drop_checkpoint | none |
| l1_01c_label_intake_001_control_drop_handoff_r2 | True | 1 | drop_handoff | none |
| l1_01c_label_intake_001_intervention_multi_r2 | True | 1 | multi | none |
| l1_01c_label_intake_001_intervention_drop_checkpoint_r2 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_01c_label_intake_001_intervention_drop_handoff_r2 | True | 0 | drop_handoff | handoff_not_delivered |
