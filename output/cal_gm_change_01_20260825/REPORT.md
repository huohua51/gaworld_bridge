# CAL-GM-CHANGE-01

- 时间：2026-08-25T01:40:36.241773+00:00
- phase：all
- ranking_eligible：false
- 构念：registered_change_decision；角色：cross_task_protocol_calibration
- 未使用 N1/T3/OA-02/GM-01/02/05 原题；无通信、Reviewer、文件生成。
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

## 主报指标

| Coverage | KeepAccuracy | UpdateAccuracy | FalsePositiveRevisionRate | MissedRevisionRate | EvidenceGroundingRate | StrictPair |
|---|---|---|---|---|---|---|
| 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.0 |

## 预注册门

- Coverage = 1.0（要求 1.0）
- KeepAccuracy = 1.0（要求 1.0）
- UpdateAccuracy = 1.0（要求 1.0）
- EvidenceGroundingRate = 1.0（要求 1.0）
- 通过：True
- control 全部乱 update：False

**结论：** 证据绑定的 keep/update 在这三道中性题上过门。这还不等于 N1/T3 已修复，也不建留出。

## 格子证据

| instance | variant | valid | FullPass | decision | keep/update | grounded | first_error |
|---|---|---|---|---|---|---|---|
| cal_service_capacity_001_control_r0 | control | True | 1 | keep | True | True | none |
| cal_service_capacity_001_intervention_r0 | intervention | True | 1 | update | True | True | none |
| cal_response_deadline_001_control_r0 | control | True | 1 | keep | True | True | none |
| cal_response_deadline_001_intervention_r0 | intervention | True | 1 | update | True | True | none |
| cal_eligibility_age_001_control_r0 | control | True | 1 | keep | True | True | none |
| cal_eligibility_age_001_intervention_r0 | intervention | True | 1 | update | True | True | none |
| cal_service_capacity_001_control_r1 | control | True | 1 | keep | True | True | none |
| cal_service_capacity_001_intervention_r1 | intervention | True | 1 | update | True | True | none |
| cal_response_deadline_001_control_r1 | control | True | 1 | keep | True | True | none |
| cal_response_deadline_001_intervention_r1 | intervention | True | 1 | update | True | True | none |
| cal_eligibility_age_001_control_r1 | control | True | 1 | keep | True | True | none |
| cal_eligibility_age_001_intervention_r1 | intervention | True | 1 | update | True | True | none |
| cal_service_capacity_001_control_r2 | control | True | 1 | keep | True | True | none |
| cal_service_capacity_001_intervention_r2 | intervention | True | 1 | update | True | True | none |
| cal_response_deadline_001_control_r2 | control | True | 1 | keep | True | True | none |
| cal_response_deadline_001_intervention_r2 | intervention | True | 1 | update | True | True | none |
| cal_eligibility_age_001_control_r2 | control | True | 1 | keep | True | True | none |
| cal_eligibility_age_001_intervention_r2 | intervention | True | 1 | update | True | True | none |

## 首错节点

| first_error | n |
|---|---|
| none | 18 |
