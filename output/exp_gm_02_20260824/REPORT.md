# EXP-GM-02 T2 household care

- 时间：2026-08-24T12:42:08.405269+00:00
- phase：all；mode：llm
- ranking_eligible：false
- 动作接口：扁平 submit_care_action，control 必须填完整 NONE 占位

## 覆盖与主结果

- requested：54
- measurement_valid：54
- coverage：1.0
- gate：completed_repeats
- FullPass direct / full / drop：0.1667 / 0.1111 / 0.3333
- TargetCorrect direct / full / drop：0.1667 / 0.1111 / 0.3333
- EventValue_full (Full − Drop)：-0.2222

## 分变体诊断

- CareAdaptationRate direct / full / drop：0.3333 / 0.2222 / 0.0
- ControlStabilityRate direct / full / drop：0.0 / 0.0 / 0.6667
- UnnecessaryReplanRate direct / full / drop：1.0 / 1.0 / 0.3333

重点：没有家庭事件时，模型会不会像 GM-01 一样为了表现适应性而主动制造变化。

## 解读

- Rule：Direct/Full 对照与干预都过；Drop 对照过、干预失败。平台通道可识别。
- Coverage=1.0，扁平契约成立。54 格全部可提取。
- ControlStabilityRate(direct/full)=0.0：看到家庭状态后几乎都会把登记照料者/患者 ID 填进本应是 `NONE` 的占位字段。多数仍是 `keep_schedule`、支出 0，不是把日程改成照料，但已经违反“无事件不认领”。
- Drop 对照 6/9 能保持 `NONE`（儿童发热、老人就医各 3/3）。看不到事件时更稳定，看到“无照料”状态后反而绑定成员。这是 GM-01 过度适应的跨任务复现。
- CareAdaptationRate：儿童发热干预 direct 3/3、full 2/3；老人/术后干预主要卡在 `schedule_decision=keep`（认领了、支出也对，但冲突槽未覆盖）。
- EventValue_full 为负，是对照假阳性把 Full 拉低、Drop 对照反而更稳的聚合假象。解释用分变体指标，不用这个差值对外下通道失效的结论。
- 不建 T2 留出题。

## 格子

| instance | valid | FullPass | target_correct | first_error |
|---|---|---|---|---|
| child_fever_001_control_direct_household_state_s0 | True | 0 | False | control_false_positive_care |
| child_fever_001_control_full_family_event_s0 | True | 0 | False | control_false_positive_care |
| child_fever_001_control_drop_family_event_s0 | True | 1 | True | none |
| child_fever_001_intervention_direct_household_state_s0 | True | 1 | True | none |
| child_fever_001_intervention_full_family_event_s0 | True | 1 | True | none |
| child_fever_001_intervention_drop_family_event_s0 | True | 0 | False | care_event_not_delivered |
| elder_clinic_001_control_direct_household_state_s0 | True | 0 | False | control_false_positive_care |
| elder_clinic_001_control_full_family_event_s0 | True | 0 | False | control_false_positive_care |
| elder_clinic_001_control_drop_family_event_s0 | True | 1 | True | none |
| elder_clinic_001_intervention_direct_household_state_s0 | True | 0 | False | conflicting_schedule_not_updated |
| elder_clinic_001_intervention_full_family_event_s0 | True | 0 | False | conflicting_schedule_not_updated |
| elder_clinic_001_intervention_drop_family_event_s0 | True | 0 | False | care_event_not_delivered |
| postop_pickup_001_control_direct_household_state_s0 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_control_full_family_event_s0 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_control_drop_family_event_s0 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_intervention_direct_household_state_s0 | True | 0 | False | conflicting_schedule_not_updated |
| postop_pickup_001_intervention_full_family_event_s0 | True | 0 | False | conflicting_schedule_not_updated |
| postop_pickup_001_intervention_drop_family_event_s0 | True | 0 | False | care_event_not_delivered |
| child_fever_001_control_direct_household_state_s1 | True | 0 | False | control_false_positive_care |
| child_fever_001_control_direct_household_state_s2 | True | 0 | False | control_false_positive_care |
| child_fever_001_control_full_family_event_s1 | True | 0 | False | control_false_positive_care |
| child_fever_001_control_full_family_event_s2 | True | 0 | False | control_false_positive_care |
| child_fever_001_control_drop_family_event_s1 | True | 1 | True | none |
| child_fever_001_control_drop_family_event_s2 | True | 1 | True | none |
| child_fever_001_intervention_direct_household_state_s1 | True | 1 | True | none |
| child_fever_001_intervention_direct_household_state_s2 | True | 1 | True | none |
| child_fever_001_intervention_full_family_event_s1 | True | 0 | False | conflicting_schedule_not_updated |
| child_fever_001_intervention_full_family_event_s2 | True | 1 | True | none |
| child_fever_001_intervention_drop_family_event_s1 | True | 0 | False | care_event_not_delivered |
| child_fever_001_intervention_drop_family_event_s2 | True | 0 | False | care_event_not_delivered |
| elder_clinic_001_control_direct_household_state_s1 | True | 0 | False | control_false_positive_care |
| elder_clinic_001_control_direct_household_state_s2 | True | 0 | False | control_false_positive_care |
| elder_clinic_001_control_full_family_event_s1 | True | 0 | False | control_false_positive_care |
| elder_clinic_001_control_full_family_event_s2 | True | 0 | False | control_false_positive_care |
| elder_clinic_001_control_drop_family_event_s1 | True | 1 | True | none |
| elder_clinic_001_control_drop_family_event_s2 | True | 1 | True | none |
| elder_clinic_001_intervention_direct_household_state_s1 | True | 0 | False | conflicting_schedule_not_updated |
| elder_clinic_001_intervention_direct_household_state_s2 | True | 0 | False | conflicting_schedule_not_updated |
| elder_clinic_001_intervention_full_family_event_s1 | True | 0 | False | conflicting_schedule_not_updated |
| elder_clinic_001_intervention_full_family_event_s2 | True | 0 | False | conflicting_schedule_not_updated |
| elder_clinic_001_intervention_drop_family_event_s1 | True | 0 | False | care_event_not_delivered |
| elder_clinic_001_intervention_drop_family_event_s2 | True | 0 | False | care_event_not_delivered |
| postop_pickup_001_control_direct_household_state_s1 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_control_direct_household_state_s2 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_control_full_family_event_s1 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_control_full_family_event_s2 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_control_drop_family_event_s1 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_control_drop_family_event_s2 | True | 0 | False | control_false_positive_care |
| postop_pickup_001_intervention_direct_household_state_s1 | True | 0 | False | conflicting_schedule_not_updated |
| postop_pickup_001_intervention_direct_household_state_s2 | True | 0 | False | conflicting_schedule_not_updated |
| postop_pickup_001_intervention_full_family_event_s1 | True | 0 | False | conflicting_schedule_not_updated |
| postop_pickup_001_intervention_full_family_event_s2 | True | 0 | False | conflicting_schedule_not_updated |
| postop_pickup_001_intervention_drop_family_event_s1 | True | 0 | False | care_event_not_delivered |
| postop_pickup_001_intervention_drop_family_event_s2 | True | 0 | False | care_event_not_delivered |
