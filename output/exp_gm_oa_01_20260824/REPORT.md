# EXP-GM-OA-01 Over-adaptation gate

- 时间：2026-08-24T13:05:33.058482+00:00
- phase：all；mode：llm
- ranking_eligible：false
- 自变量：动作协议（legacy_direct vs need_change_gate）。模型、温度、预算、事件内容相同。
- 未改、未重跑 GM-01 / GM-02；未建留出集；未开 GM-03。

## 主报指标

- Coverage（全体）：1.0

| 协议 | Coverage | NeedChangeAccuracy | ControlStabilityRate | AdaptationRate | UnnecessaryReplanRate | ConditionalActionScore |
|---|---|---|---|---|---|---|
| legacy_direct | 1.0 | 1.0 | 0.6667 | 1.0 | 0.3333 | 0.8334 |
| need_change_gate | 1.0 | 1.0 | 0.6667 | 1.0 | 0.3333 | 0.8334 |

ConditionalActionScore = (ControlStabilityRate + AdaptationRate) / 2，只作附报，不替代两个分项。

预约时间与资源补充：两种协议 24/24 全过。失败全部来自责任安排对照格：模型判断为 keep / need_change=false，但把 target 填成 assignee_id 而不是 NONE，value 仍为 NONE，并没有改派 backup-01。

## 预注册改进门

- Coverage：1.0（要求 1.0）
- 新协议 ControlStabilityRate 提升：0.0（要求 ≥ 3/9 ≈ 0.3333）
- 新协议 AdaptationRate 下降：0.0（最多 1/9 ≈ 0.1111）
- UnnecessaryReplanRate 是否下降：False
- 一律不行动陷阱：False
- 改进是否成立：False

## 结果怎么读

- `need_change` 正确，但最终动作错误：判断会、执行映射不会。下一步改动作 schema、状态机和字段约束。

## 格子证据

| instance | protocol | variant | valid | FullPass | need_change | target_correct | first_error |
|---|---|---|---|---|---|---|---|
| appointment_update_control_legacy_direct_s0 | legacy_direct | control | True | 1 | True | True | none |
| appointment_update_control_legacy_direct_s1 | legacy_direct | control | True | 1 | True | True | none |
| appointment_update_control_legacy_direct_s2 | legacy_direct | control | True | 1 | True | True | none |
| appointment_update_control_need_change_gate_s0 | need_change_gate | control | True | 1 | True | True | none |
| appointment_update_control_need_change_gate_s1 | need_change_gate | control | True | 1 | True | True | none |
| appointment_update_control_need_change_gate_s2 | need_change_gate | control | True | 1 | True | True | none |
| appointment_update_intervention_legacy_direct_s0 | legacy_direct | intervention | True | 1 | True | True | none |
| appointment_update_intervention_legacy_direct_s1 | legacy_direct | intervention | True | 1 | True | True | none |
| appointment_update_intervention_legacy_direct_s2 | legacy_direct | intervention | True | 1 | True | True | none |
| appointment_update_intervention_need_change_gate_s0 | need_change_gate | intervention | True | 1 | True | True | none |
| appointment_update_intervention_need_change_gate_s1 | need_change_gate | intervention | True | 1 | True | True | none |
| appointment_update_intervention_need_change_gate_s2 | need_change_gate | intervention | True | 1 | True | True | none |
| resource_threshold_control_legacy_direct_s0 | legacy_direct | control | True | 1 | True | True | none |
| resource_threshold_control_legacy_direct_s1 | legacy_direct | control | True | 1 | True | True | none |
| resource_threshold_control_legacy_direct_s2 | legacy_direct | control | True | 1 | True | True | none |
| resource_threshold_control_need_change_gate_s0 | need_change_gate | control | True | 1 | True | True | none |
| resource_threshold_control_need_change_gate_s1 | need_change_gate | control | True | 1 | True | True | none |
| resource_threshold_control_need_change_gate_s2 | need_change_gate | control | True | 1 | True | True | none |
| resource_threshold_intervention_legacy_direct_s0 | legacy_direct | intervention | True | 1 | True | True | none |
| resource_threshold_intervention_legacy_direct_s1 | legacy_direct | intervention | True | 1 | True | True | none |
| resource_threshold_intervention_legacy_direct_s2 | legacy_direct | intervention | True | 1 | True | True | none |
| resource_threshold_intervention_need_change_gate_s0 | need_change_gate | intervention | True | 1 | True | True | none |
| resource_threshold_intervention_need_change_gate_s1 | need_change_gate | intervention | True | 1 | True | True | none |
| resource_threshold_intervention_need_change_gate_s2 | need_change_gate | intervention | True | 1 | True | True | none |
| responsibility_update_control_legacy_direct_s0 | legacy_direct | control | True | 0 | True | False | keep_placeholder_not_none |
| responsibility_update_control_legacy_direct_s1 | legacy_direct | control | True | 0 | True | False | keep_placeholder_not_none |
| responsibility_update_control_legacy_direct_s2 | legacy_direct | control | True | 0 | True | False | keep_placeholder_not_none |
| responsibility_update_control_need_change_gate_s0 | need_change_gate | control | True | 0 | True | False | keep_placeholder_not_none |
| responsibility_update_control_need_change_gate_s1 | need_change_gate | control | True | 0 | True | False | keep_placeholder_not_none |
| responsibility_update_control_need_change_gate_s2 | need_change_gate | control | True | 0 | True | False | keep_placeholder_not_none |
| responsibility_update_intervention_legacy_direct_s0 | legacy_direct | intervention | True | 1 | True | True | none |
| responsibility_update_intervention_legacy_direct_s1 | legacy_direct | intervention | True | 1 | True | True | none |
| responsibility_update_intervention_legacy_direct_s2 | legacy_direct | intervention | True | 1 | True | True | none |
| responsibility_update_intervention_need_change_gate_s0 | need_change_gate | intervention | True | 1 | True | True | none |
| responsibility_update_intervention_need_change_gate_s1 | need_change_gate | intervention | True | 1 | True | True | none |
| responsibility_update_intervention_need_change_gate_s2 | need_change_gate | intervention | True | 1 | True | True | none |

## 首错节点

| first_error | n |
|---|---|
| none | 30 |
| keep_placeholder_not_none | 6 |

## 失败格原始动作

- `responsibility_update_control_legacy_direct_s0` first_error=keep_placeholder_not_none

```json
{
  "action": "keep",
  "target": "assignee_id",
  "value": "NONE",
  "evidence_event_id": "event-responsibility_update-control"
}
```

- `responsibility_update_control_legacy_direct_s1` first_error=keep_placeholder_not_none

```json
{
  "action": "keep",
  "target": "assignee_id",
  "value": "NONE",
  "evidence_event_id": "event-responsibility_update-control"
}
```

- `responsibility_update_control_legacy_direct_s2` first_error=keep_placeholder_not_none

```json
{
  "action": "keep",
  "target": "assignee_id",
  "value": "NONE",
  "evidence_event_id": "event-responsibility_update-control"
}
```

- `responsibility_update_control_need_change_gate_s0` first_error=keep_placeholder_not_none

```json
{
  "need_change": false,
  "action": "keep",
  "target": "assignee_id",
  "value": "NONE",
  "evidence_event_id": "event-responsibility_update-control"
}
```

- `responsibility_update_control_need_change_gate_s1` first_error=keep_placeholder_not_none

```json
{
  "need_change": false,
  "action": "keep",
  "target": "assignee_id",
  "value": "NONE",
  "evidence_event_id": "event-responsibility_update-control"
}
```

- `responsibility_update_control_need_change_gate_s2` first_error=keep_placeholder_not_none

```json
{
  "need_change": false,
  "action": "keep",
  "target": "assignee_id",
  "value": "NONE",
  "evidence_event_id": "event-responsibility_update-control"
}
```

