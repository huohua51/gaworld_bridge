# EXP-GM-T3-01

- 时间：2026-08-25T01:31:17.373286+00:00
- phase：seed0；gate：r0_pass
- ranking_eligible：false
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

## 测量门

seed0 先看这四项，不比较谁更强。

- Coverage：1.0
- 初稿哈希一致：True
- 预算均为 3 次：True
- Drop 隔离且 Reviewer 实际运行：True
- FullPass Single / Multi / Drop：0.0 / 0.0 / 0.0

## 主报

- TargetCorrect：{'single': 0.0, 'multi': 0.0, 'drop': 0.0}
- OracleConditionedFullPass：{'single': 0.0, 'multi': 0.0, 'drop': 0.0}
- FalsePositiveRevisionRate：0.6667
- TrueRevisionRate：1.0
- VerifiedPatchAdoptionRate：0.4444
- Single−Multi：0.0
- Multi−Drop：0.0
- first_error：{'partial_change_applied': 7, 'required_change_not_read': 2, 'review_not_delivered': 3, 'false_positive_revision': 6}

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| t3_parking_threshold_001_control_single_r0 | True | 0 | single | partial_change_applied |
| t3_parking_threshold_001_control_multi_r0 | True | 0 | multi | partial_change_applied |
| t3_parking_threshold_001_control_drop_r0 | True | 0 | drop | partial_change_applied |
| t3_parking_threshold_001_intervention_single_r0 | True | 0 | single | required_change_not_read |
| t3_parking_threshold_001_intervention_multi_r0 | True | 0 | multi | required_change_not_read |
| t3_parking_threshold_001_intervention_drop_r0 | True | 0 | drop | review_not_delivered |
| t3_deposit_ratio_001_control_single_r0 | True | 0 | single | false_positive_revision |
| t3_deposit_ratio_001_control_multi_r0 | True | 0 | multi | false_positive_revision |
| t3_deposit_ratio_001_control_drop_r0 | True | 0 | drop | false_positive_revision |
| t3_deposit_ratio_001_intervention_single_r0 | True | 0 | single | partial_change_applied |
| t3_deposit_ratio_001_intervention_multi_r0 | True | 0 | multi | partial_change_applied |
| t3_deposit_ratio_001_intervention_drop_r0 | True | 0 | drop | review_not_delivered |
| t3_queue_cap_001_control_single_r0 | True | 0 | single | false_positive_revision |
| t3_queue_cap_001_control_multi_r0 | True | 0 | multi | false_positive_revision |
| t3_queue_cap_001_control_drop_r0 | True | 0 | drop | false_positive_revision |
| t3_queue_cap_001_intervention_single_r0 | True | 0 | single | partial_change_applied |
| t3_queue_cap_001_intervention_multi_r0 | True | 0 | multi | partial_change_applied |
| t3_queue_cap_001_intervention_drop_r0 | True | 0 | drop | review_not_delivered |
