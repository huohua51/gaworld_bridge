# EXP-GM-02 T2 household care

- 时间：2026-08-24T12:34:48.637760+00:00
- phase：rule；mode：rule
- ranking_eligible：false
- 动作接口：扁平 submit_care_action，control 必须填完整 NONE 占位

## 覆盖与主结果

- requested：18
- measurement_valid：18
- coverage：1.0
- gate：fill_repeats
- FullPass direct / full / drop：1.0 / 1.0 / 0.5
- TargetCorrect direct / full / drop：1.0 / 1.0 / 0.5
- EventValue_full (Full − Drop)：0.5

## 分变体诊断

- CareAdaptationRate direct / full / drop：1.0 / 1.0 / 0.0
- ControlStabilityRate direct / full / drop：1.0 / 1.0 / 1.0
- UnnecessaryReplanRate direct / full / drop：0.0 / 0.0 / 0.0

重点：没有家庭事件时，模型会不会像 GM-01 一样为了表现适应性而主动制造变化。

| instance | valid | FullPass | target_correct | first_error |
|---|---|---|---|---|
| child_fever_001_control_direct_household_state_s0 | True | 1 | True | none |
| child_fever_001_control_full_family_event_s0 | True | 1 | True | none |
| child_fever_001_control_drop_family_event_s0 | True | 1 | True | none |
| child_fever_001_intervention_direct_household_state_s0 | True | 1 | True | none |
| child_fever_001_intervention_full_family_event_s0 | True | 1 | True | none |
| child_fever_001_intervention_drop_family_event_s0 | True | 0 | False | care_event_not_delivered |
| elder_clinic_001_control_direct_household_state_s0 | True | 1 | True | none |
| elder_clinic_001_control_full_family_event_s0 | True | 1 | True | none |
| elder_clinic_001_control_drop_family_event_s0 | True | 1 | True | none |
| elder_clinic_001_intervention_direct_household_state_s0 | True | 1 | True | none |
| elder_clinic_001_intervention_full_family_event_s0 | True | 1 | True | none |
| elder_clinic_001_intervention_drop_family_event_s0 | True | 0 | False | care_event_not_delivered |
| postop_pickup_001_control_direct_household_state_s0 | True | 1 | True | none |
| postop_pickup_001_control_full_family_event_s0 | True | 1 | True | none |
| postop_pickup_001_control_drop_family_event_s0 | True | 1 | True | none |
| postop_pickup_001_intervention_direct_household_state_s0 | True | 1 | True | none |
| postop_pickup_001_intervention_full_family_event_s0 | True | 1 | True | none |
| postop_pickup_001_intervention_drop_family_event_s0 | True | 0 | False | care_event_not_delivered |
