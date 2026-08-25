# EXP-GM-I1 TASK-I1 Verified Information Relay

- 时间：2026-08-24T05:24:32.590528+00:00
- 状态：pilot，不可排名
- 路线：04a → 04b → 04c → I1 → REL1
- 只评 Dispatcher 结构化动作；猜对但无合法核验证据不算干净成功

## 覆盖与主结果

- requested：72
- measurement_valid：72
- coverage：1.0
- oracle_conditioned FullPass：0.4583
- target_correct：0.5833
- StrictPair（全轨）：0.4167；Focused 0.6667；Full 1.0
- 策略锁死率：0.5
- 未经授权读取率：0.0

### 分轨与价值

- Focused：0.8333
- Full：1.0（control 1.0 / intervention 1.0）
- Drop-verified：0.0（control 0.0 / intervention 0.0）
- No-verification：0.0
- CommunicationValue (Full − Drop)：1.0
- VerificationValue (Full − NoVerify)：1.0
- CommunicationPropagationGap (Focused − Full)：-0.1667

## 决策

Focused/Full 高、Drop 低：通信与核验闭环有效。Rule Full=1，真模型 Full=1，不进入平台修复。

## 科学结论

TASK-I1 把通信从 04c 的代码审核里拆了出来。Rule 负控按预期：Focused/Full 两变体都过；Drop 与 No-verification 不能得到干净路径成功；Dispatcher 读可信表和 Verifier 提交动作被拒绝；重复核验只采用一次；旧版本核验不能覆盖新版本。

72 格全部 `measurement_valid`。真模型主结果：

* **Full = 1.0，StrictPair Full = 1.0**：三条社会场景上，Observer→Verifier→Dispatcher 都能把可信状态送到决策者，并且 control/intervention 动作随核实状态翻转。
* **Drop-verified = 0.0**：丢掉核验消息后没有干净成功，CommunicationValue=1.0。核验消息有因果价值，不是多调用一次模型的假象。
* **No-verification = 0.0**：只给冲突原始信号时不能稳定走通，VerificationValue=1.0。Verifier 角色必要。未经授权读取率=0。
* **Focused = 0.8333**：避难所 control 三次把 `action`/`value` 填反（`action=send_to_A, value=submit_shelter`）。这是 Dispatcher 契约填写错误，不是通道没送到。因此 CommunicationPropagationGap 为负，不解释成“完整链比上限更强的平台增益”。

No-verification 干预格有时 `target_correct=1` 但 `stale_state_used`：猜对了动作，没有合法核验证据，不记 FullPass。

I1 给出的平台结论是：GAWorld 能在角色隔离下完成可信信息核验与送达。关系任务 REL1 现在才有独立通信基线。04c 的两类协议失败仍在 Backlog，不在本次修改。

| instance | valid | FullPass | target_correct | conditioned | first_error |
|---|---|---|---|---|---|
| road_status_001_control_focused_s0 | True | 1 | True | True | none |
| road_status_001_control_focused_s1 | True | 1 | True | True | none |
| road_status_001_control_focused_s2 | True | 1 | True | True | none |
| road_status_001_control_full_s0 | True | 1 | True | True | none |
| road_status_001_control_full_s1 | True | 1 | True | True | none |
| road_status_001_control_full_s2 | True | 1 | True | True | none |
| road_status_001_control_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_no_verification_s0 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_no_verification_s1 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_no_verification_s2 | True | 0 | False | False | target_action_incorrect |
| road_status_001_intervention_focused_s0 | True | 1 | True | True | none |
| road_status_001_intervention_focused_s1 | True | 1 | True | True | none |
| road_status_001_intervention_focused_s2 | True | 1 | True | True | none |
| road_status_001_intervention_full_s0 | True | 1 | True | True | none |
| road_status_001_intervention_full_s1 | True | 1 | True | True | none |
| road_status_001_intervention_full_s2 | True | 1 | True | True | none |
| road_status_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| road_status_001_intervention_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| road_status_001_intervention_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| road_status_001_intervention_no_verification_s0 | True | 0 | True | False | stale_state_used |
| road_status_001_intervention_no_verification_s1 | True | 0 | True | False | stale_state_used |
| road_status_001_intervention_no_verification_s2 | True | 0 | True | False | stale_state_used |
| shelter_capacity_001_control_focused_s0 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_focused_s1 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_focused_s2 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_full_s0 | True | 1 | True | True | none |
| shelter_capacity_001_control_full_s1 | True | 1 | True | True | none |
| shelter_capacity_001_control_full_s2 | True | 1 | True | True | none |
| shelter_capacity_001_control_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_no_verification_s0 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_no_verification_s1 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_no_verification_s2 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_intervention_focused_s0 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_focused_s1 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_focused_s2 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_full_s0 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_full_s1 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_full_s2 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_intervention_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_intervention_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_intervention_no_verification_s0 | True | 0 | True | False | stale_state_used |
| shelter_capacity_001_intervention_no_verification_s1 | True | 0 | True | False | stale_state_used |
| shelter_capacity_001_intervention_no_verification_s2 | True | 0 | True | False | stale_state_used |
| clinic_service_001_control_focused_s0 | True | 1 | True | True | none |
| clinic_service_001_control_focused_s1 | True | 1 | True | True | none |
| clinic_service_001_control_focused_s2 | True | 1 | True | True | none |
| clinic_service_001_control_full_s0 | True | 1 | True | True | none |
| clinic_service_001_control_full_s1 | True | 1 | True | True | none |
| clinic_service_001_control_full_s2 | True | 1 | True | True | none |
| clinic_service_001_control_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_no_verification_s0 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_no_verification_s1 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_no_verification_s2 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_intervention_focused_s0 | True | 1 | True | True | none |
| clinic_service_001_intervention_focused_s1 | True | 1 | True | True | none |
| clinic_service_001_intervention_focused_s2 | True | 1 | True | True | none |
| clinic_service_001_intervention_full_s0 | True | 1 | True | True | none |
| clinic_service_001_intervention_full_s1 | True | 1 | True | True | none |
| clinic_service_001_intervention_full_s2 | True | 1 | True | True | none |
| clinic_service_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_intervention_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_intervention_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_intervention_no_verification_s0 | True | 0 | True | False | stale_state_used |
| clinic_service_001_intervention_no_verification_s1 | True | 0 | True | False | stale_state_used |
| clinic_service_001_intervention_no_verification_s2 | True | 0 | True | False | stale_state_used |
