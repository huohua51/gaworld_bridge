# HO-GM-I1-01 密封留出

- 时间：2026-08-25T12:47:41.960905+00:00
- 状态：sealed holdout，不可排名，只跑 seed0 一次
- 父实验：EXP-GM-I1（开发集分数不改）
- 只评 Dispatcher 结构化动作；猜对但无合法核验证据不算干净成功
- focused 轨对外登记为 direct_verified_state，不是能力上限

## 覆盖与主结果

- requested：24
- measurement_valid：24
- coverage：1.0
- oracle_conditioned FullPass：0.5
- target_correct：0.8333
- StrictPair（全轨）：0.5；direct_verified_state 1.0；Full 1.0
- 策略锁死率：0.25
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

| instance | valid | FullPass | target_correct | conditioned | first_error |
|---|---|---|---|---|---|
| pier_berth_001_control_focused_s0 | True | 1 | True | True | none |
| pier_berth_001_control_full_s0 | True | 1 | True | True | none |
| pier_berth_001_control_drop_verified_s0 | True | 0 | True | False | stale_state_used |
| pier_berth_001_control_no_verification_s0 | True | 0 | True | False | stale_state_used |
| pier_berth_001_intervention_focused_s0 | True | 1 | True | True | none |
| pier_berth_001_intervention_full_s0 | True | 1 | True | True | none |
| pier_berth_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| pier_berth_001_intervention_no_verification_s0 | True | 0 | False | False | target_action_incorrect |
| pump_station_001_control_focused_s0 | True | 1 | True | True | none |
| pump_station_001_control_full_s0 | True | 1 | True | True | none |
| pump_station_001_control_drop_verified_s0 | True | 0 | True | False | stale_state_used |
| pump_station_001_control_no_verification_s0 | True | 0 | True | False | stale_state_used |
| pump_station_001_intervention_focused_s0 | True | 1 | True | True | none |
| pump_station_001_intervention_full_s0 | True | 1 | True | True | none |
| pump_station_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| pump_station_001_intervention_no_verification_s0 | True | 0 | True | False | stale_state_used |
| library_hours_001_control_focused_s0 | True | 1 | True | True | none |
| library_hours_001_control_full_s0 | True | 1 | True | True | none |
| library_hours_001_control_drop_verified_s0 | True | 0 | True | False | stale_state_used |
| library_hours_001_control_no_verification_s0 | True | 0 | True | False | stale_state_used |
| library_hours_001_intervention_focused_s0 | True | 1 | True | True | none |
| library_hours_001_intervention_full_s0 | True | 1 | True | True | none |
| library_hours_001_intervention_drop_verified_s0 | True | 0 | False | False | target_action_incorrect |
| library_hours_001_intervention_no_verification_s0 | True | 0 | True | False | stale_state_used |
