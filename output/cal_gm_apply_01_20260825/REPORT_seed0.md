# CAL-GM-APPLY-01

- 时间：2026-08-25T01:58:38.298286+00:00
- phase：seed0
- ranking_eligible：false
- 构念：complete_change_adoption；角色：executor_component_calibration
- Reviewer / 决策：Rule；模型只做 Executor。Scorer 读取真实文件。
- 未使用 T3/N1/04e 原题。
- 冻结：a6ff231b8f49b0280f3f4be63556b4bc6d3aa07c

## 主报指标

| Coverage | FieldAdoptionRate | CompleteChangeAdoptionRate | PartialChangeRate | UnregisteredChangeRate | HiddenTestPass | AcknowledgementExecutionGap |
|---|---|---|---|---|---|---|
| 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 0.0 |

## 预注册门

- Coverage = 1.0（要求 1.0）
- FieldAdoptionRate = 1.0（要求 1.0）
- CompleteChangeAdoptionRate = 1.0（要求 1.0）
- PartialChangeRate = 0.0（要求 0）
- UnregisteredChangeRate = 0.0（要求 0）
- HiddenTestPass = 1.0（要求 1.0）
- AcknowledgementExecutionGap = 0.0（要求 0）
- 通过：True

**结论：** seed0 过预注册门。补齐三次重复后才能冻结协议。

## 格子证据

| instance | variant | valid | FullPass | adopted | complete | partial | hidden | first_error |
|---|---|---|---|---|---|---|---|---|
| cal_apply_limit_fallback_001_control_r0 | control | True | 1 | 1/1 | True | False | True | none |
| cal_apply_limit_fallback_001_intervention_r0 | intervention | True | 1 | 2/2 | True | False | True | none |
| cal_apply_weekday_weekend_001_control_r0 | control | True | 1 | 1/1 | True | False | True | none |
| cal_apply_weekday_weekend_001_intervention_r0 | intervention | True | 1 | 2/2 | True | False | True | none |
| cal_apply_normal_emergency_001_control_r0 | control | True | 1 | 1/1 | True | False | True | none |
| cal_apply_normal_emergency_001_intervention_r0 | intervention | True | 1 | 2/2 | True | False | True | none |

## 首错节点

| first_error | n |
|---|---|
| none | 6 |
