# 互斥动作协议（单次调用，无 NONE）

保持不变时根本不存在修改对象：

```json
{"action": "keep_current_plan", "evidence_event_id": "event-001"}
```

真正修改时才允许出现 target / value：

```json
{"action": "revise_plan", "target": "assignee_id", "value": "backup-01", "evidence_event_id": "event-002"}
```

提交层条件 schema：

- `keep_current_plan` 携带 `target` 或 `value` → 直接拒绝
- `revise_plan` 缺少 `target` 或 `value` → 直接拒绝
- 不再使用 `"NONE"` 占位符，也不再输出 `need_change`
