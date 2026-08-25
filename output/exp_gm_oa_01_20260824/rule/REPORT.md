# EXP-GM-OA-01 Over-adaptation gate

- 时间：2026-08-24T12:59:55.755665+00:00
- phase：rule；mode：rule
- ranking_eligible：false
- 自变量：动作协议（legacy_direct vs need_change_gate）。模型、温度、预算、事件内容相同。
- 未改、未重跑 GM-01 / GM-02；未建留出集；未开 GM-03。

## 主报指标

- Coverage（全体）：1.0

| 协议 | Coverage | NeedChangeAccuracy | ControlStabilityRate | AdaptationRate | UnnecessaryReplanRate | ConditionalActionScore |
|---|---|---|---|---|---|---|
| legacy_direct | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 |
| need_change_gate | 1.0 | 1.0 | 1.0 | 1.0 | 0.0 | 1.0 |

ConditionalActionScore = (ControlStabilityRate + AdaptationRate) / 2，只作附报，不替代两个分项。

## 预注册改进门

- Coverage：1.0（要求 1.0）
- 新协议 ControlStabilityRate 提升：0.0（要求 ≥ 3/9 ≈ 0.3333）
- 新协议 AdaptationRate 下降：0.0（最多 1/9 ≈ 0.1111）
- UnnecessaryReplanRate 是否下降：False
- 一律不行动陷阱：False
- 改进是否成立：False

## 结果怎么读

- 新协议仍然过度适应：单靠动作格式解决不了。下一步增加独立的行动必要性检查器。

## 格子证据

| instance | protocol | variant | valid | FullPass | need_change | target_correct | first_error |
|---|---|---|---|---|---|---|---|
| appointment_update_control_legacy_direct_s0 | legacy_direct | control | True | 1 | True | True | none |
| appointment_update_control_need_change_gate_s0 | need_change_gate | control | True | 1 | True | True | none |
| appointment_update_intervention_legacy_direct_s0 | legacy_direct | intervention | True | 1 | True | True | none |
| appointment_update_intervention_need_change_gate_s0 | need_change_gate | intervention | True | 1 | True | True | none |
| resource_threshold_control_legacy_direct_s0 | legacy_direct | control | True | 1 | True | True | none |
| resource_threshold_control_need_change_gate_s0 | need_change_gate | control | True | 1 | True | True | none |
| resource_threshold_intervention_legacy_direct_s0 | legacy_direct | intervention | True | 1 | True | True | none |
| resource_threshold_intervention_need_change_gate_s0 | need_change_gate | intervention | True | 1 | True | True | none |
| responsibility_update_control_legacy_direct_s0 | legacy_direct | control | True | 1 | True | True | none |
| responsibility_update_control_need_change_gate_s0 | need_change_gate | control | True | 1 | True | True | none |
| responsibility_update_intervention_legacy_direct_s0 | legacy_direct | intervention | True | 1 | True | True | none |
| responsibility_update_intervention_need_change_gate_s0 | need_change_gate | intervention | True | 1 | True | True | none |
