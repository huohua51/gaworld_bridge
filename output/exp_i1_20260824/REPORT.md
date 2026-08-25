# EXP-GM-I1 TASK-I1 Verified Information Relay

- 时间：2026-08-24T06:58:15.092278+00:00
- 状态：pilot，不可排名
- 路线：04a → 04b → 04c → I1 → REL1
- 只评 Dispatcher 结构化动作；猜对但无合法核验证据不算干净成功
- focused 轨对外登记为 direct_verified_state，不是能力上限

## 覆盖与主结果

- requested：72
- measurement_valid：72
- coverage：1.0
- oracle_conditioned FullPass：0.5
- target_correct：0.625
- StrictPair（全轨）：0.5；direct_verified_state 1.0；Full 1.0
- 策略锁死率：0.5
- 未经授权读取率：0.0

### 分轨与价值

- direct_verified_state（内部轨名 focused）：1.0
- Full：1.0（control 1.0 / intervention 1.0）
- Drop-verified：0.0（control 0.0 / intervention 0.0）
- No-verification：0.0
- CommunicationValue (Full − Drop)：1.0
- VerificationValue (Full − NoVerify)：1.0
- CommunicationPropagationGap (direct_verified_state − Full)：0.0

## 决策

direct_verified_state/Full 高、Drop 低：通信与核验闭环有效。

## 科学结论

TASK-I1 把通信从 04c 的代码审核里拆了出来。focused 轨对外登记为 **direct_verified_state**，不是能力上限。契约小修后只重跑了 18 格 focused；Full/Drop/NoVerify 54 格保持冻结。

* **direct_verified_state = 1.0，StrictPair = 1.0**：避难所 control 不再把 action/value 对调。CommunicationPropagationGap=0.0，现在可与 Full 比较。
* **Full = 1.0，Drop = 0，NoVerify = 0，未授权读取 = 0**：核验消息有因果价值，Verifier 角色必要。平台通信结论不变。
* 旧报告 Focused=0.833、Gap=-0.167 记为契约污染，不可解释为完整流程提升了能力。基线见 `REPORT_before_focused_contract.md`。

| instance | valid | FullPass | target_correct | conditioned | first_error |
|---|---|---|---|---|---|
| clinic_service_001_control_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_full_s0 | True | 1 | True | True | none |
| clinic_service_001_control_full_s1 | True | 1 | True | True | none |
| clinic_service_001_control_full_s2 | True | 1 | True | True | none |
| clinic_service_001_control_no_verification_s0 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_no_verification_s1 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_control_no_verification_s2 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_intervention_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_intervention_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| clinic_service_001_intervention_full_s0 | True | 1 | True | True | none |
| clinic_service_001_intervention_full_s1 | True | 1 | True | True | none |
| clinic_service_001_intervention_full_s2 | True | 1 | True | True | none |
| clinic_service_001_intervention_no_verification_s0 | True | 0 | True | False | stale_state_used |
| clinic_service_001_intervention_no_verification_s1 | True | 0 | True | False | stale_state_used |
| clinic_service_001_intervention_no_verification_s2 | True | 0 | True | False | stale_state_used |
| road_status_001_control_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_full_s0 | True | 1 | True | True | none |
| road_status_001_control_full_s1 | True | 1 | True | True | none |
| road_status_001_control_full_s2 | True | 1 | True | True | none |
| road_status_001_control_no_verification_s0 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_no_verification_s1 | True | 0 | False | False | target_action_incorrect |
| road_status_001_control_no_verification_s2 | True | 0 | False | False | target_action_incorrect |
| road_status_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| road_status_001_intervention_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| road_status_001_intervention_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| road_status_001_intervention_full_s0 | True | 1 | True | True | none |
| road_status_001_intervention_full_s1 | True | 1 | True | True | none |
| road_status_001_intervention_full_s2 | True | 1 | True | True | none |
| road_status_001_intervention_no_verification_s0 | True | 0 | True | False | stale_state_used |
| road_status_001_intervention_no_verification_s1 | True | 0 | True | False | stale_state_used |
| road_status_001_intervention_no_verification_s2 | True | 0 | True | False | stale_state_used |
| shelter_capacity_001_control_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_full_s0 | True | 1 | True | True | none |
| shelter_capacity_001_control_full_s1 | True | 1 | True | True | none |
| shelter_capacity_001_control_full_s2 | True | 1 | True | True | none |
| shelter_capacity_001_control_no_verification_s0 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_no_verification_s1 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_control_no_verification_s2 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_intervention_drop_verified_s1 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_intervention_drop_verified_s2 | True | 0 | False | False | target_action_incorrect |
| shelter_capacity_001_intervention_full_s0 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_full_s1 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_full_s2 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_no_verification_s0 | True | 0 | True | False | stale_state_used |
| shelter_capacity_001_intervention_no_verification_s1 | True | 0 | True | False | stale_state_used |
| shelter_capacity_001_intervention_no_verification_s2 | True | 0 | True | False | stale_state_used |
| road_status_001_control_focused_s0 | True | 1 | True | True | none |
| road_status_001_control_focused_s1 | True | 1 | True | True | none |
| road_status_001_control_focused_s2 | True | 1 | True | True | none |
| road_status_001_intervention_focused_s0 | True | 1 | True | True | none |
| road_status_001_intervention_focused_s1 | True | 1 | True | True | none |
| road_status_001_intervention_focused_s2 | True | 1 | True | True | none |
| shelter_capacity_001_control_focused_s0 | True | 1 | True | True | none |
| shelter_capacity_001_control_focused_s1 | True | 1 | True | True | none |
| shelter_capacity_001_control_focused_s2 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_focused_s0 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_focused_s1 | True | 1 | True | True | none |
| shelter_capacity_001_intervention_focused_s2 | True | 1 | True | True | none |
| clinic_service_001_control_focused_s0 | True | 1 | True | True | none |
| clinic_service_001_control_focused_s1 | True | 1 | True | True | none |
| clinic_service_001_control_focused_s2 | True | 1 | True | True | none |
| clinic_service_001_intervention_focused_s0 | True | 1 | True | True | none |
| clinic_service_001_intervention_focused_s1 | True | 1 | True | True | none |
| clinic_service_001_intervention_focused_s2 | True | 1 | True | True | none |
