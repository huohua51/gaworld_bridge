# EXP-GM-REL1 TASK-REL1 Trust Formation and Update

- 时间：2026-08-24T06:03:28.776903+00:00
- 状态：pilot，不可排名
- 路线：04a → 04b → 04c → I1 → REL1
- 只评 Dispatcher 两轮结构化动作；猜对但无合法信任证据不算干净成功
- 当前报告在 control/intervention 完全相同；唯一变化是历史谁被证明正确，以及反转后是否更新信任

## 覆盖与主结果

- requested：24
- measurement_valid：24
- coverage：1.0
- oracle_conditioned FullPass：0.5
- target_correct（形成且更新）：0.5
- StrictPair（全轨）：0.5；Focused 1.0；Full 1.0
- 策略锁死率：0.5
- 未经授权读取率：0.0

### 分轨与价值

- Focused：1.0
- Full：1.0（control 1.0 / intervention 1.0）
- Drop-trust：0.0（control 0.0 / intervention 0.0）
- No-history：0.0
- TrustDeliveryValue (Full − Drop)：1.0
- HistoryValue (Full − NoHistory)：1.0
- TrustPropagationGap (Focused − Full)：0.0

## 决策

Focused/Full 高、Drop 低：信任形成、送达和更新闭环有效。

| instance | valid | FullPass | formation | update | conditioned | first_error |
|---|---|---|---|---|---|---|
| road_status_001_control_focused_s0 | True | 1 | True | True | True | none |
| road_status_001_control_full_s0 | True | 1 | True | True | True | none |
| road_status_001_control_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| road_status_001_control_no_history_s0 | True | 0 | False | False | False | history_not_available |
| road_status_001_intervention_focused_s0 | True | 1 | True | True | True | none |
| road_status_001_intervention_full_s0 | True | 1 | True | True | True | none |
| road_status_001_intervention_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| road_status_001_intervention_no_history_s0 | True | 0 | False | False | False | history_not_available |
| shelter_capacity_001_control_focused_s0 | True | 1 | True | True | True | none |
| shelter_capacity_001_control_full_s0 | True | 1 | True | True | True | none |
| shelter_capacity_001_control_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_control_no_history_s0 | True | 0 | False | False | False | history_not_available |
| shelter_capacity_001_intervention_focused_s0 | True | 1 | True | True | True | none |
| shelter_capacity_001_intervention_full_s0 | True | 1 | True | True | True | none |
| shelter_capacity_001_intervention_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_intervention_no_history_s0 | True | 0 | False | False | False | history_not_available |
| clinic_service_001_control_focused_s0 | True | 1 | True | True | True | none |
| clinic_service_001_control_full_s0 | True | 1 | True | True | True | none |
| clinic_service_001_control_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| clinic_service_001_control_no_history_s0 | True | 0 | False | False | False | history_not_available |
| clinic_service_001_intervention_focused_s0 | True | 1 | True | True | True | none |
| clinic_service_001_intervention_full_s0 | True | 1 | True | True | True | none |
| clinic_service_001_intervention_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| clinic_service_001_intervention_no_history_s0 | True | 0 | False | False | False | history_not_available |
