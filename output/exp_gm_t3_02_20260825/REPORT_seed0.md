# EXP-GM-T3-02

- 时间：2026-08-25T02:30:18.231924+00:00
- phase：seed0；gate：C_ceiling
- ranking_eligible：false
- parent：EXP-GM-T3-01；construct：component_to_workflow_integration
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

## 测量门

- Coverage：1.0
- 初稿哈希一致：True
- 预算均为 3 次：True
- Drop 隔离：True
- Payload 完整性：True

## 主报

| 指标 | Single | Multi | Drop |
|---|---:|---:|---:|
| Coverage | 1.0 | 1.0 | 1.0 |
| ReviewDecisionAccuracy | 1.0 | 1.0 | 1.0 |
| PayloadIntegrity | 1.0 | 1.0 | 1.0 |
| CompleteChangeAdoptionRate | 1.0 | 1.0 | 0.5 |
| TargetCorrect | 1.0 | 1.0 | 0.5 |
| FullPass | 1.0 | 1.0 | 0.5 |
| StrictPair | 1.0 | 1.0 | 0.0 |

- T3-01 FullPass：{'single': 0.0, 'multi': 0.0, 'drop': 0.0}
- T3-01 → T3-02 FullPass Gain：{'single': 1.0, 'multi': 1.0, 'drop': 0.5}
- OutcomeMultiAgentNetBenefit：{'value': 0.0, 'reason': 'multi_minus_single'}
- WorkflowMultiAgentNetBenefit：{'value': 0.5, 'reason': 'multi_minus_drop'}
- ReviewDeliveryValue：{'value': 0.5, 'reason': 'multi_minus_drop'}
- first_error：{'none': 15, 'review_payload_not_delivered': 3}

**结论：** Single/Multi 都提升：组件契约集成有效。不补 54 格，不建留出。

| instance | valid | FullPass | track | first_error |
|---|---|---|---|---|
| t3_parking_threshold_001_control_single_r0 | True | 1 | single | none |
| t3_parking_threshold_001_control_multi_r0 | True | 1 | multi | none |
| t3_parking_threshold_001_control_drop_r0 | True | 1 | drop | none |
| t3_parking_threshold_001_intervention_single_r0 | True | 1 | single | none |
| t3_parking_threshold_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_parking_threshold_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
| t3_deposit_ratio_001_control_single_r0 | True | 1 | single | none |
| t3_deposit_ratio_001_control_multi_r0 | True | 1 | multi | none |
| t3_deposit_ratio_001_control_drop_r0 | True | 1 | drop | none |
| t3_deposit_ratio_001_intervention_single_r0 | True | 1 | single | none |
| t3_deposit_ratio_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_deposit_ratio_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
| t3_queue_cap_001_control_single_r0 | True | 1 | single | none |
| t3_queue_cap_001_control_multi_r0 | True | 1 | multi | none |
| t3_queue_cap_001_control_drop_r0 | True | 1 | drop | none |
| t3_queue_cap_001_intervention_single_r0 | True | 1 | single | none |
| t3_queue_cap_001_intervention_multi_r0 | True | 1 | multi | none |
| t3_queue_cap_001_intervention_drop_r0 | True | 0 | drop | review_payload_not_delivered |
