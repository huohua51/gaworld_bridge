# HO-GM-L1-01

- 时间：2026-08-25T12:40:17.877102+00:00
- phase：seed0；gate：regression_pass
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

- Full Multi：control 3/3；interruption 3/3；strict_pair 3/3
- Drop Checkpoint：control 3/3；interruption 0/3
- Drop Handoff：control 3/3；interruption 0/3
- RecoveryLatency（intervention multi）：7.0
- first_error：{'none': 12, 'checkpoint_not_delivered': 3, 'handoff_not_delivered': 3}
- 解释：留出 seed0 通过预注册门。不补 repeat。不能写泛化或排名。

**结论：** 留出 seed0 通过预注册门。不补 repeat。不能写泛化或排名。 功能进度约 85% 是评测建设与机制覆盖，不是 GAWorld 能力得分。不做 C1-04。

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| l1_ho_crane_load_001_control_multi_r0 | True | 1 | multi | none |
| l1_ho_crane_load_001_control_drop_checkpoint_r0 | True | 1 | drop_checkpoint | none |
| l1_ho_crane_load_001_control_drop_handoff_r0 | True | 1 | drop_handoff | none |
| l1_ho_crane_load_001_intervention_multi_r0 | True | 1 | multi | none |
| l1_ho_crane_load_001_intervention_drop_checkpoint_r0 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_ho_crane_load_001_intervention_drop_handoff_r0 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_ho_fridge_log_001_control_multi_r0 | True | 1 | multi | none |
| l1_ho_fridge_log_001_control_drop_checkpoint_r0 | True | 1 | drop_checkpoint | none |
| l1_ho_fridge_log_001_control_drop_handoff_r0 | True | 1 | drop_handoff | none |
| l1_ho_fridge_log_001_intervention_multi_r0 | True | 1 | multi | none |
| l1_ho_fridge_log_001_intervention_drop_checkpoint_r0 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_ho_fridge_log_001_intervention_drop_handoff_r0 | True | 0 | drop_handoff | handoff_not_delivered |
| l1_ho_mail_bay_001_control_multi_r0 | True | 1 | multi | none |
| l1_ho_mail_bay_001_control_drop_checkpoint_r0 | True | 1 | drop_checkpoint | none |
| l1_ho_mail_bay_001_control_drop_handoff_r0 | True | 1 | drop_handoff | none |
| l1_ho_mail_bay_001_intervention_multi_r0 | True | 1 | multi | none |
| l1_ho_mail_bay_001_intervention_drop_checkpoint_r0 | True | 0 | drop_checkpoint | checkpoint_not_delivered |
| l1_ho_mail_bay_001_intervention_drop_handoff_r0 | True | 0 | drop_handoff | handoff_not_delivered |
