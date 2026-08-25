# EXP-GM-T3-01

- 时间：2026-08-24T14:02:59.836316+00:00
- phase：seed0；gate：A_r0
- ranking_eligible：false
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

## 测量门

seed0 先看这四项，不比较谁更强。

- Coverage：0.7778
- 初稿哈希一致：True
- 预算均为 3 次：True
- Drop 隔离且 Reviewer 实际运行：False
- FullPass Single / Multi / Drop：0.0 / 0.0 / 0.0

## 主报

- TargetCorrect：{'single': 0.0, 'multi': 0.0, 'drop': 0.0}
- OracleConditionedFullPass：{'single': 0.0, 'multi': 0.0, 'drop': 0.0}
- FalsePositiveRevisionRate：0.6667
- TrueRevisionRate：0.125
- VerifiedPatchAdoptionRate：0.375
- Single−Multi：0.0
- Multi−Drop：0.0
- first_error：{'fields_not_extractable': 4, 'partial_change_applied': 3, 'true_revision_missed': 7, 'false_positive_revision': 4}

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| t3_parking_threshold_001_control_single_r0 | False | None | single | fields_not_extractable |
| t3_parking_threshold_001_control_multi_r0 | True | 0 | multi | partial_change_applied |
| t3_parking_threshold_001_control_drop_r0 | True | 0 | drop | partial_change_applied |
| t3_parking_threshold_001_intervention_single_r0 | False | None | single | fields_not_extractable |
| t3_parking_threshold_001_intervention_multi_r0 | True | 0 | multi | true_revision_missed |
| t3_parking_threshold_001_intervention_drop_r0 | True | 0 | drop | true_revision_missed |
| t3_deposit_ratio_001_control_single_r0 | False | None | single | fields_not_extractable |
| t3_deposit_ratio_001_control_multi_r0 | True | 0 | multi | false_positive_revision |
| t3_deposit_ratio_001_control_drop_r0 | True | 0 | drop | false_positive_revision |
| t3_deposit_ratio_001_intervention_single_r0 | True | 0 | single | partial_change_applied |
| t3_deposit_ratio_001_intervention_multi_r0 | True | 0 | multi | true_revision_missed |
| t3_deposit_ratio_001_intervention_drop_r0 | True | 0 | drop | true_revision_missed |
| t3_queue_cap_001_control_single_r0 | False | None | single | fields_not_extractable |
| t3_queue_cap_001_control_multi_r0 | True | 0 | multi | false_positive_revision |
| t3_queue_cap_001_control_drop_r0 | True | 0 | drop | false_positive_revision |
| t3_queue_cap_001_intervention_single_r0 | True | 0 | single | true_revision_missed |
| t3_queue_cap_001_intervention_multi_r0 | True | 0 | multi | true_revision_missed |
| t3_queue_cap_001_intervention_drop_r0 | True | 0 | drop | true_revision_missed |

**分支：** Coverage 或公平性未过，停止。multi_agent_net_benefit=N/A。不改提示重跑。
