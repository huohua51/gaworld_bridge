# 两种动作协议（等预算、各一次调用）

## legacy_direct

看到当前状态后直接提交最终行动。字段：

```json
{"action": "keep|revise", "target": "...", "value": "...", "evidence_event_id": "..."}
```

`keep` 时 `target` 与 `value` 必须为 `NONE`。这对应 GM-01/02「收到信息就交最终动作」的格式，不用旧题。

## need_change_gate

同一信息、同一次调用，但必须先判断这条信息是否要求改变：

```json
{
  "need_change": false,
  "action": "keep",
  "target": "NONE",
  "value": "NONE",
  "evidence_event_id": "event-001"
}
```

需要改变：

```json
{
  "need_change": true,
  "action": "revise",
  "target": "resource_stock",
  "value": 1,
  "evidence_event_id": "event-002"
}
```

规则：

- `need_change=false` ⇒ `action=keep`，其余可变字段为 `NONE`
- `need_change=true` ⇒ `action=revise`，并提交登记过的修改
- 判断与行动矛盾 ⇒ 失败
- 环境不得代改计划
