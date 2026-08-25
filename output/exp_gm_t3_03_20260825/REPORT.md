# EXP-GM-T3-03

- 时间：2026-08-25T03:04:28.937642+00:00
- phase：r0r1r2；gate：off_floor
- ranking_eligible：false
- generalization_claim：false
- multi_agent_value_estimable：True
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
Single 的 0.5 同样是 control=1.0、intervention=0.0：自检没有私有核验信息时判断 keep，不是部分采用。

- Direct FullPass：1.0
- OutcomeMultiAgentNetBenefit：{'value': 0.5, 'reason': 'multi_minus_single'}
- ReviewDeliveryValue：{'value': 0.5, 'reason': 'multi_minus_drop', 'drop_complete_not_partial_adoption': True}
- first_error：{'none': 36, 'review_decision_incorrect': 9, 'review_payload_not_delivered': 9}
- Single intervention first_error：{'review_decision_incorrect': 9}
- Drop intervention first_error：{'review_payload_not_delivered': 9}
- value_pattern：{'multi_gt_single': True, 'multi_gt_drop': True, 'pattern': True, 'single_intervention_first_error': {'review_decision_incorrect': 9}, 'drop_intervention_first_error': {'review_payload_not_delivered': 9}, 'first_error_locates_to_reviewer_private_info': True, 'advantage_vanishes_on_drop': True, 'estimable': True}

**结论：** 出现 Multi>Single 且 Multi>Drop，且首错定位到 Reviewer 提供的信息；丢弃后优势消失。仍不能作为排名分，也不能宣称泛化。

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| t3_free_ship_kg_001_control_single_r0 | True | 1 | single | none |
| t3_free_ship_kg_001_control_multi_r0 | True | 1 | multi | none |
| t3_free_ship_kg_001_control_drop_r0 | True | 1 | drop | none |
| t3_free_ship_kg_001_intervention_single_r0 | True | 0 | single | review_decision_incorrect |
| t3_free_ship_kg_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_free_ship_kg_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
| t3_redeem_points_001_control_single_r0 | True | 1 | single | none |
| t3_redeem_points_001_control_multi_r0 | True | 1 | multi | none |
| t3_redeem_points_001_control_drop_r0 | True | 1 | drop | none |
| t3_redeem_points_001_intervention_single_r0 | True | 0 | single | review_decision_incorrect |
| t3_redeem_points_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_redeem_points_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
| t3_alert_celsius_001_control_single_r0 | True | 1 | single | none |
| t3_alert_celsius_001_control_multi_r0 | True | 1 | multi | none |
| t3_alert_celsius_001_control_drop_r0 | True | 1 | drop | none |
| t3_alert_celsius_001_intervention_single_r0 | True | 0 | single | review_decision_incorrect |
| t3_alert_celsius_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_alert_celsius_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
| t3_free_ship_kg_001_control_single_r1 | True | 1 | single | none |
| t3_free_ship_kg_001_control_multi_r1 | True | 1 | multi | none |
| t3_free_ship_kg_001_control_drop_r1 | True | 1 | drop | none |
| t3_free_ship_kg_001_intervention_single_r1 | True | 0 | single | review_decision_incorrect |
| t3_free_ship_kg_001_intervention_multi_r1 | True | 1 | multi | none |
| t3_free_ship_kg_001_intervention_drop_r1 | True | 0 | drop | review_payload_not_delivered |
| t3_redeem_points_001_control_single_r1 | True | 1 | single | none |
| t3_redeem_points_001_control_multi_r1 | True | 1 | multi | none |
| t3_redeem_points_001_control_drop_r1 | True | 1 | drop | none |
| t3_redeem_points_001_intervention_single_r1 | True | 0 | single | review_decision_incorrect |
| t3_redeem_points_001_intervention_multi_r1 | True | 1 | multi | none |
| t3_redeem_points_001_intervention_drop_r1 | True | 0 | drop | review_payload_not_delivered |
| t3_alert_celsius_001_control_single_r1 | True | 1 | single | none |
| t3_alert_celsius_001_control_multi_r1 | True | 1 | multi | none |
| t3_alert_celsius_001_control_drop_r1 | True | 1 | drop | none |
| t3_alert_celsius_001_intervention_single_r1 | True | 0 | single | review_decision_incorrect |
| t3_alert_celsius_001_intervention_multi_r1 | True | 1 | multi | none |
| t3_alert_celsius_001_intervention_drop_r1 | True | 0 | drop | review_payload_not_delivered |
| t3_free_ship_kg_001_control_single_r2 | True | 1 | single | none |
| t3_free_ship_kg_001_control_multi_r2 | True | 1 | multi | none |
| t3_free_ship_kg_001_control_drop_r2 | True | 1 | drop | none |
| t3_free_ship_kg_001_intervention_single_r2 | True | 0 | single | review_decision_incorrect |
| t3_free_ship_kg_001_intervention_multi_r2 | True | 1 | multi | none |
| t3_free_ship_kg_001_intervention_drop_r2 | True | 0 | drop | review_payload_not_delivered |
| t3_redeem_points_001_control_single_r2 | True | 1 | single | none |
| t3_redeem_points_001_control_multi_r2 | True | 1 | multi | none |
| t3_redeem_points_001_control_drop_r2 | True | 1 | drop | none |
| t3_redeem_points_001_intervention_single_r2 | True | 0 | single | review_decision_incorrect |
| t3_redeem_points_001_intervention_multi_r2 | True | 1 | multi | none |
| t3_redeem_points_001_intervention_drop_r2 | True | 0 | drop | review_payload_not_delivered |
| t3_alert_celsius_001_control_single_r2 | True | 1 | single | none |
| t3_alert_celsius_001_control_multi_r2 | True | 1 | multi | none |
| t3_alert_celsius_001_control_drop_r2 | True | 1 | drop | none |
| t3_alert_celsius_001_intervention_single_r2 | True | 0 | single | review_decision_incorrect |
| t3_alert_celsius_001_intervention_multi_r2 | True | 1 | multi | none |
| t3_alert_celsius_001_intervention_drop_r2 | True | 0 | drop | review_payload_not_delivered |
