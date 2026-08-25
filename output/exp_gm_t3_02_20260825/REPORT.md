# EXP-GM-T3-02

- 时间：2026-08-25T02:30:18.231924+00:00
- phase：seed0；gate：C_ceiling
- status：calibration_pass
- role：component_integration_positive_control
- ranking_eligible：false
- generalization_claim：false
- multi_agent_value_estimable：false
- parent：EXP-GM-T3-01；construct：component_to_workflow_integration
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

diagnostic_conclusion: The calibrated decision and execution contracts can be integrated without payload mutation or capability loss.

T3-01 失败应归因为组件接口和上下文组织不兼容，而不是 Reviewer 不会判断、Executor 不会修改，也不是 GAWorld 通道丢失信息。本实验只证明集成已经修好，不能证明多 Agent 更好。Single 与 Multi 同在天花板，不补 54 格。

## 测量门

- Coverage：1.0
- 初稿哈希一致：True
- 预算均为 3 次：True
- Drop 隔离：True
- 有传输时 payload 完整性（Single/Multi 三段 hash）：1.0
- Drop 不是“成功传输”：Reviewer 输出 hash 存在，通道 `dropped=true`，Executor 未读到 payload

## 主报

| 指标 | Single | Multi | Drop |
|---|---:|---:|---:|
| Coverage | 1.0 | 1.0 | 1.0 |
| ReviewDecisionAccuracy | 1.0 | 1.0 | 1.0 |
| PayloadIntegrity（有传输时） | 1.0 | 1.0 | 不适用（干预未交付） |
| CompleteChangeAdoptionRate | 1.0 | 1.0 | control 1.0 / intervention 0.0 |
| TargetCorrect | 1.0 | 1.0 | control 1.0 / intervention 0.0 |
| FullPass | 1.0 | 1.0 | 0.5 |
| StrictPair | 1.0 | 1.0 | 0.0 |

Drop 的 FullPass=0.5 与 CompleteChangeAdoptionRate 若写成 0.5，都是 control 与 intervention 两种变体的平均，不表示“部分采用”。intervention 三格均为 `review_payload_not_delivered`，采用率为 0。

- T3-01 FullPass：{'single': 0.0, 'multi': 0.0, 'drop': 0.0}
- T3-01 → T3-02 FullPass Gain：{'single': 1.0, 'multi': 1.0, 'drop': 0.5}
- OutcomeMultiAgentNetBenefit：{'value': 0.0, 'reason': 'multi_equals_single_ceiling'}（不可估计多智能体价值）
- WorkflowMultiAgentNetBenefit：{'value': 0.5, 'reason': 'multi_minus_drop'}
- ReviewDeliveryValue：{'value': 0.5, 'reason': 'drop_intervention_payload_not_delivered'}
- first_error：{'none': 15, 'review_payload_not_delivered': 3}

**结论：** 校准后的 keep/update 与 required_changes 契约可以接回工作流，且不发生 payload 变形或能力丢失。不能报告多智能体审核价值。不补重复。今后用作协议改动后的集成正控。

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
