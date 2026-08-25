# EXP-GM-REL1 TASK-REL1 Trust Formation and Update

- 时间：2026-08-24T06:32:48.728248+00:00
- 状态：pilot，不可排名
- 路线：04a → 04b → 04c → I1 → REL1
- 只评 Dispatcher 两轮结构化动作；猜对但无合法信任证据不算干净成功
- 当前报告在 control/intervention 完全相同；唯一变化是历史谁被证明正确，以及反转后是否更新信任

## 覆盖与主结果

- requested：72
- measurement_valid：72
- coverage：1.0
- oracle_conditioned FullPass：0.0833
- target_correct（形成且更新）：0.3333
- StrictPair（全轨）：0.0833；Focused 0.3333；Full 0.0
- 策略锁死率：0.5833
- 未经授权读取率：0.0

### 分轨与价值

- Focused：0.3333
- Full：0.0（control 0.0 / intervention 0.0）
- Drop-trust：0.0（control 0.0 / intervention 0.0）
- No-history：0.0
- TrustDeliveryValue (Full − Drop)：0.0
- HistoryValue (Full − NoHistory)：0.0
- TrustPropagationGap (Focused − Full)：0.3333

## 决策

Focused 部分可用、Full=0、Drop/No-history=0。Rule Full=1.0 且 Drop=0，不进入平台修复。真模型失败在信任形成/更新协议，以及 Dispatcher 契约填写。TrustDeliveryValue 与 HistoryValue 为 0 不能解释成“送达或历史没有价值”：那是 Full 被协议失败打到地板上的算术结果，负控仍按设计挡住了干净成功。

## 科学结论

TASK-REL1 在 I1 已验证的通信管线上，把静态可信表换成**多轮结果历史**。构念是 `registered_reliability_update`，不是广义人际信任。Oracle 明确 `latest_is_binding=true`：形成阶段用历史正确次数，更新阶段最新一条 outcome 绝对覆盖历史多数。当前报告在两个变体里完全相同；唯一变化是谁在历史上被证明正确，以及最新揭示是否要求按登记规则翻转。采用时写入 GAWorld `relationship_update`。

Rule 负控按预期：Focused/Full 两变体都过；Drop-trust 与 No-history 不能得到干净路径成功；Dispatcher 读历史账本和 TrustUpdater 提交动作被拒绝；v1 采用后可以再采用 v2，旧版本不能覆盖新版本；空历史不能发出信任状态。

72 格全部 `measurement_valid`。真模型主结果：

* **Full = 0.0，StrictPair Full = 0.0**：通道能把 TrustUpdater 的状态送到 Dispatcher，但内容不符合登记规则。control Full 形成正确、更新仍信历史多数，`majority_not_recency_update`。intervention Full 形成就信 A，`history_ignored_person_a_default`。这是功能能力失败，**不能**扩写为“模型不会形成人际信任”；H3 仍需人类 dyad 数据。
* **Drop-trust = 0.0，No-history = 0.0**：负控有效。未经授权读取率=0。control Drop 有时两轮动作碰巧等于 (value_a, value_b)，但版本/证据不合法，记 `stale_trust_used`，不算 FullPass。
* **direct_verified_state（内部轨名 focused）= 0.3333**：只有诊所两变体 6/6 干净通过。道路更新轮 `evidence_message_id="None"`。避难所复现 I1 契约错误。TrustPropagationGap 不可解释为人际信任增益。

平台结论：GAWorld 能隔离历史账本、送达信任状态、在采用时写入关系，并拒绝越权和陈旧信任。冻结本实验，不加自动信任更新器。下一步是 04d 协议改进；若结构化协议能跨留出题改善协作，再把同一种方法迁到 REL1。

| instance | valid | FullPass | formation | update | conditioned | first_error |
|---|---|---|---|---|---|---|
| road_status_001_control_focused_s0 | True | 0 | True | True | False | none |
| road_status_001_control_full_s0 | True | 0 | True | False | False | trust_not_updated |
| road_status_001_control_drop_trust_s0 | True | 0 | True | True | False | stale_trust_used |
| road_status_001_control_no_history_s0 | True | 0 | True | True | False | history_not_available |
| road_status_001_intervention_focused_s0 | True | 0 | True | True | False | none |
| road_status_001_intervention_full_s0 | True | 0 | False | False | False | formation_action_incorrect |
| road_status_001_intervention_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| road_status_001_intervention_no_history_s0 | True | 0 | False | False | False | history_not_available |
| shelter_capacity_001_control_focused_s0 | True | 0 | False | True | False | formation_action_incorrect |
| shelter_capacity_001_control_full_s0 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_control_drop_trust_s0 | True | 0 | True | True | False | stale_trust_used |
| shelter_capacity_001_control_no_history_s0 | True | 0 | False | True | False | history_not_available |
| shelter_capacity_001_intervention_focused_s0 | True | 0 | True | False | False | update_action_incorrect |
| shelter_capacity_001_intervention_full_s0 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_intervention_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_intervention_no_history_s0 | True | 0 | True | False | False | history_not_available |
| clinic_service_001_control_focused_s0 | True | 1 | True | True | True | none |
| clinic_service_001_control_full_s0 | True | 0 | True | False | False | trust_not_updated |
| clinic_service_001_control_drop_trust_s0 | True | 0 | True | True | False | stale_trust_used |
| clinic_service_001_control_no_history_s0 | True | 0 | True | False | False | history_not_available |
| clinic_service_001_intervention_focused_s0 | True | 1 | True | True | True | none |
| clinic_service_001_intervention_full_s0 | True | 0 | False | False | False | formation_action_incorrect |
| clinic_service_001_intervention_drop_trust_s0 | True | 0 | False | False | False | formation_action_incorrect |
| clinic_service_001_intervention_no_history_s0 | True | 0 | False | True | False | history_not_available |
| road_status_001_control_focused_s1 | True | 0 | True | True | False | none |
| road_status_001_control_focused_s2 | True | 0 | True | True | False | none |
| road_status_001_control_full_s1 | True | 0 | True | False | False | trust_not_updated |
| road_status_001_control_full_s2 | True | 0 | True | False | False | trust_not_updated |
| road_status_001_control_drop_trust_s1 | True | 0 | True | True | False | stale_trust_used |
| road_status_001_control_drop_trust_s2 | True | 0 | True | True | False | stale_trust_used |
| road_status_001_control_no_history_s1 | True | 0 | True | True | False | history_not_available |
| road_status_001_control_no_history_s2 | True | 0 | True | True | False | history_not_available |
| road_status_001_intervention_focused_s1 | True | 0 | True | True | False | none |
| road_status_001_intervention_focused_s2 | True | 0 | True | True | False | none |
| road_status_001_intervention_full_s1 | True | 0 | False | False | False | formation_action_incorrect |
| road_status_001_intervention_full_s2 | True | 0 | False | False | False | formation_action_incorrect |
| road_status_001_intervention_drop_trust_s1 | True | 0 | False | False | False | formation_action_incorrect |
| road_status_001_intervention_drop_trust_s2 | True | 0 | False | False | False | formation_action_incorrect |
| road_status_001_intervention_no_history_s1 | True | 0 | False | False | False | history_not_available |
| road_status_001_intervention_no_history_s2 | True | 0 | False | False | False | history_not_available |
| shelter_capacity_001_control_focused_s1 | True | 0 | False | True | False | formation_action_incorrect |
| shelter_capacity_001_control_focused_s2 | True | 0 | False | True | False | formation_action_incorrect |
| shelter_capacity_001_control_full_s1 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_control_full_s2 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_control_drop_trust_s1 | True | 0 | True | True | False | stale_trust_used |
| shelter_capacity_001_control_drop_trust_s2 | True | 0 | True | True | False | stale_trust_used |
| shelter_capacity_001_control_no_history_s1 | True | 0 | False | True | False | history_not_available |
| shelter_capacity_001_control_no_history_s2 | True | 0 | False | True | False | history_not_available |
| shelter_capacity_001_intervention_focused_s1 | True | 0 | True | False | False | update_action_incorrect |
| shelter_capacity_001_intervention_focused_s2 | True | 0 | True | False | False | update_action_incorrect |
| shelter_capacity_001_intervention_full_s1 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_intervention_full_s2 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_intervention_drop_trust_s1 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_intervention_drop_trust_s2 | True | 0 | False | False | False | formation_action_incorrect |
| shelter_capacity_001_intervention_no_history_s1 | True | 0 | True | False | False | history_not_available |
| shelter_capacity_001_intervention_no_history_s2 | True | 0 | True | False | False | history_not_available |
| clinic_service_001_control_focused_s1 | True | 1 | True | True | True | none |
| clinic_service_001_control_focused_s2 | True | 1 | True | True | True | none |
| clinic_service_001_control_full_s1 | True | 0 | True | False | False | trust_not_updated |
| clinic_service_001_control_full_s2 | True | 0 | True | False | False | trust_not_updated |
| clinic_service_001_control_drop_trust_s1 | True | 0 | True | True | False | stale_trust_used |
| clinic_service_001_control_drop_trust_s2 | True | 0 | True | True | False | stale_trust_used |
| clinic_service_001_control_no_history_s1 | True | 0 | True | False | False | history_not_available |
| clinic_service_001_control_no_history_s2 | True | 0 | True | False | False | history_not_available |
| clinic_service_001_intervention_focused_s1 | True | 1 | True | True | True | none |
| clinic_service_001_intervention_focused_s2 | True | 1 | True | True | True | none |
| clinic_service_001_intervention_full_s1 | True | 0 | False | False | False | formation_action_incorrect |
| clinic_service_001_intervention_full_s2 | True | 0 | False | False | False | formation_action_incorrect |
| clinic_service_001_intervention_drop_trust_s1 | True | 0 | False | False | False | formation_action_incorrect |
| clinic_service_001_intervention_drop_trust_s2 | True | 0 | False | False | False | formation_action_incorrect |
| clinic_service_001_intervention_no_history_s1 | True | 0 | False | True | False | history_not_available |
| clinic_service_001_intervention_no_history_s2 | True | 0 | False | True | False | history_not_available |
