# EXP-GM-01 T1 venue close

- 时间：2026-08-24T12:34:44.104836+00:00
- phase：all；mode：llm
- ranking_eligible：false
- 动作接口：扁平 update_visit，不使用审核 JSON

## 覆盖与主结果

- requested：54
- measurement_valid：54
- coverage：1.0
- gate：completed_repeats
- FullPass direct / full / drop：0.5 / 0.6667 / 0.0
- TargetCorrect direct / full / drop：0.6667 / 0.6667 / 0.3333
- EventValue_full (Full − Drop)：0.6667
- EventValue_target (Full − Drop)：0.3334
- PropagationGap (direct − full)：-0.1667

## 分变体诊断

- ClosureAdaptationRate direct / full / drop：1.0 / 1.0 / 0.0
- ControlStabilityRate direct / full / drop：0.3333 / 0.3333 / 0.6667
- UnnecessaryReplanRate direct / full / drop：0.6667 / 0.6667 / 0.3333

关闭事件能沿感知链送达并改变目的地与日程；模型在真正关闭时能稳定重规划，
但存在明显过度适应——场所没有关闭时也主动改道。平台通道通过，Agent 条件判断部分成功。
模型把“重新评估当前状态”误解成“必须重新选择地点”，缺少“状态未改变就保持原计划”的决策分支。
本实验冻结为 development pilot，不建 T1 留出题。

| instance | valid | FullPass | target_correct | first_error |
|---|---|---|---|---|
| clinic_close_001_control_direct_current_state_s0 | True | 0 | False | target_action_incorrect |
| clinic_close_001_control_direct_current_state_s1 | True | 0 | False | target_action_incorrect |
| clinic_close_001_control_direct_current_state_s2 | True | 0 | False | target_action_incorrect |
| clinic_close_001_control_drop_event_s0 | True | 0 | True | event_not_delivered |
| clinic_close_001_control_drop_event_s1 | True | 0 | True | event_not_delivered |
| clinic_close_001_control_drop_event_s2 | True | 0 | True | event_not_delivered |
| clinic_close_001_control_full_event_s0 | True | 0 | False | target_action_incorrect |
| clinic_close_001_control_full_event_s1 | True | 0 | False | target_action_incorrect |
| clinic_close_001_control_full_event_s2 | True | 0 | False | target_action_incorrect |
| clinic_close_001_intervention_direct_current_state_s0 | True | 1 | True | none |
| clinic_close_001_intervention_direct_current_state_s1 | True | 1 | True | none |
| clinic_close_001_intervention_direct_current_state_s2 | True | 1 | True | none |
| clinic_close_001_intervention_drop_event_s0 | True | 0 | False | destination_closed |
| clinic_close_001_intervention_drop_event_s1 | True | 0 | False | destination_closed |
| clinic_close_001_intervention_drop_event_s2 | True | 0 | False | destination_closed |
| clinic_close_001_intervention_full_event_s0 | True | 1 | True | none |
| clinic_close_001_intervention_full_event_s1 | True | 1 | True | none |
| clinic_close_001_intervention_full_event_s2 | True | 1 | True | none |
| restaurant_close_001_control_direct_current_state_s0 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_control_direct_current_state_s1 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_control_direct_current_state_s2 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_control_drop_event_s0 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_control_drop_event_s1 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_control_drop_event_s2 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_control_full_event_s0 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_control_full_event_s1 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_control_full_event_s2 | True | 0 | False | target_action_incorrect |
| restaurant_close_001_intervention_direct_current_state_s0 | True | 1 | True | none |
| restaurant_close_001_intervention_direct_current_state_s1 | True | 1 | True | none |
| restaurant_close_001_intervention_direct_current_state_s2 | True | 1 | True | none |
| restaurant_close_001_intervention_drop_event_s0 | True | 0 | False | destination_closed |
| restaurant_close_001_intervention_drop_event_s1 | True | 0 | False | destination_closed |
| restaurant_close_001_intervention_drop_event_s2 | True | 0 | False | destination_closed |
| restaurant_close_001_intervention_full_event_s0 | True | 1 | True | none |
| restaurant_close_001_intervention_full_event_s1 | True | 1 | True | none |
| restaurant_close_001_intervention_full_event_s2 | True | 1 | True | none |
| store_close_001_control_direct_current_state_s0 | True | 0 | True | event_not_adopted |
| store_close_001_control_direct_current_state_s1 | True | 0 | True | event_not_adopted |
| store_close_001_control_direct_current_state_s2 | True | 0 | True | event_not_adopted |
| store_close_001_control_drop_event_s0 | True | 0 | True | event_not_delivered |
| store_close_001_control_drop_event_s1 | True | 0 | True | event_not_delivered |
| store_close_001_control_drop_event_s2 | True | 0 | True | event_not_delivered |
| store_close_001_control_full_event_s0 | True | 1 | True | none |
| store_close_001_control_full_event_s1 | True | 1 | True | none |
| store_close_001_control_full_event_s2 | True | 1 | True | none |
| store_close_001_intervention_direct_current_state_s0 | True | 1 | True | none |
| store_close_001_intervention_direct_current_state_s1 | True | 1 | True | none |
| store_close_001_intervention_direct_current_state_s2 | True | 1 | True | none |
| store_close_001_intervention_drop_event_s0 | True | 0 | False | destination_closed |
| store_close_001_intervention_drop_event_s1 | True | 0 | False | destination_closed |
| store_close_001_intervention_drop_event_s2 | True | 0 | False | destination_closed |
| store_close_001_intervention_full_event_s0 | True | 1 | True | none |
| store_close_001_intervention_full_event_s1 | True | 1 | True | none |
| store_close_001_intervention_full_event_s2 | True | 1 | True | none |
