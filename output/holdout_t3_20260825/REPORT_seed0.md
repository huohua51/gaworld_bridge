# HO-GM-T3-01

- 时间：2026-08-25T12:44:21.536238+00:00
- phase：seed0；gate：off_floor
- ranking_eligible：false
- generalization_claim：false
- multi_agent_value_estimable：False
- parent：EXP-GM-T3-02；construct：independent_reviewer_private_information
- Direct 可做：True
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

## 测量门

- Coverage：1.0
- 初稿哈希一致：True
- 预算均为 3 次：True
- Drop 隔离：True
- 有传输时 payload 完整性：True

## 主报

| 指标 | Single | Multi | Drop |
|---|---:|---:|---:|
| Coverage | 1.0 | 1.0 | 1.0 |
| ReviewDecisionAccuracy | 0.5 | 1.0 | 1.0 |
| PayloadIntegrity（有传输时） | 1.0 | 1.0 | 不适用（干预未交付） |
| CompleteChangeAdoptionRate | 0.5 | 1.0 | control 1.0 / intervention 0.0 |
| TargetCorrect | 0.5 | 1.0 | control 1.0 / intervention 0.0 |
| FullPass | 0.5 | 1.0 | 0.5 |
| StrictPair | 0.0 | 1.0 | 0.0 |

Drop 的 pooled 平均若出现 0.5，是 control 与 intervention 两种变体的平均，不表示部分采用。

- Direct FullPass：1.0
- OutcomeMultiAgentNetBenefit：{'value': 0.5, 'reason': 'multi_minus_single'}
- ReviewDeliveryValue：{'value': 0.5, 'reason': 'multi_minus_drop', 'drop_complete_not_partial_adoption': True}
- first_error：{'none': 12, 'review_decision_incorrect': 3, 'review_payload_not_delivered': 3}
- Single intervention first_error：{'review_decision_incorrect': 3}
- Drop intervention first_error：{'review_payload_not_delivered': 3}
- value_pattern：{'multi_gt_single': True, 'multi_gt_drop': True, 'pattern': True, 'single_intervention_first_error': {'review_decision_incorrect': 3}, 'drop_intervention_first_error': {'review_payload_not_delivered': 3}, 'first_error_locates_to_reviewer_private_info': True, 'advantage_vanishes_on_drop': True, 'estimable': True}

**结论：** R0 有效且不共地板、不共天花板；方向符合 Multi>Single 且 Multi>Drop，首错指向 Reviewer 私有信息。补 repeat 1/2 后再报告。

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| t3_ho_queue_max_001_control_single_r0 | True | 1 | single | none |
| t3_ho_queue_max_001_control_multi_r0 | True | 1 | multi | none |
| t3_ho_queue_max_001_control_drop_r0 | True | 1 | drop | none |
| t3_ho_queue_max_001_intervention_single_r0 | True | 0 | single | review_decision_incorrect |
| t3_ho_queue_max_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_ho_queue_max_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
| t3_ho_battery_pct_001_control_single_r0 | True | 1 | single | none |
| t3_ho_battery_pct_001_control_multi_r0 | True | 1 | multi | none |
| t3_ho_battery_pct_001_control_drop_r0 | True | 1 | drop | none |
| t3_ho_battery_pct_001_intervention_single_r0 | True | 0 | single | review_decision_incorrect |
| t3_ho_battery_pct_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_ho_battery_pct_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
| t3_ho_noise_db_001_control_single_r0 | True | 1 | single | none |
| t3_ho_noise_db_001_control_multi_r0 | True | 1 | multi | none |
| t3_ho_noise_db_001_control_drop_r0 | True | 1 | drop | none |
| t3_ho_noise_db_001_intervention_single_r0 | True | 0 | single | review_decision_incorrect |
| t3_ho_noise_db_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_ho_noise_db_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
