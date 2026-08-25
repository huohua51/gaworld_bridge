# EXP-GM-01 T1 venue close

- 时间：2026-08-24T12:21:15.902528+00:00
- phase：rule；mode：rule
- ranking_eligible：false
- 动作接口：扁平 update_visit，不使用审核 JSON

## 覆盖与主结果

- requested：18
- measurement_valid：18
- coverage：1.0
- gate：fill_repeats
- FullPass direct / full / drop：1.0 / 1.0 / 0.0
- TargetCorrect direct / full / drop：1.0 / 1.0 / 0.5
- EventValue_full (Full − Drop)：1.0
- EventValue_target (Full − Drop)：0.5
- PropagationGap (direct − full)：0.0

| instance | valid | FullPass | target_correct | first_error |
|---|---|---|---|---|
| restaurant_close_001_control_direct_current_state_s0 | True | 1 | True | none |
| restaurant_close_001_control_full_event_s0 | True | 1 | True | none |
| restaurant_close_001_control_drop_event_s0 | True | 0 | True | event_not_delivered |
| restaurant_close_001_intervention_direct_current_state_s0 | True | 1 | True | none |
| restaurant_close_001_intervention_full_event_s0 | True | 1 | True | none |
| restaurant_close_001_intervention_drop_event_s0 | True | 0 | False | destination_closed |
| clinic_close_001_control_direct_current_state_s0 | True | 1 | True | none |
| clinic_close_001_control_full_event_s0 | True | 1 | True | none |
| clinic_close_001_control_drop_event_s0 | True | 0 | True | event_not_delivered |
| clinic_close_001_intervention_direct_current_state_s0 | True | 1 | True | none |
| clinic_close_001_intervention_full_event_s0 | True | 1 | True | none |
| clinic_close_001_intervention_drop_event_s0 | True | 0 | False | destination_closed |
| store_close_001_control_direct_current_state_s0 | True | 1 | True | none |
| store_close_001_control_full_event_s0 | True | 1 | True | none |
| store_close_001_control_drop_event_s0 | True | 0 | True | event_not_delivered |
| store_close_001_intervention_direct_current_state_s0 | True | 1 | True | none |
| store_close_001_intervention_full_event_s0 | True | 1 | True | none |
| store_close_001_intervention_drop_event_s0 | True | 0 | False | destination_closed |
